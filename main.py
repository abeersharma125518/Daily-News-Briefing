#!/usr/bin/env python3
"""Personal News Briefing - Daily email with paired opposing-source articles."""

import argparse
import logging
import os
import shutil
import sys
import time
from datetime import datetime, timezone

import yaml

from fetcher import fetch_all
from matcher import ArticleMatcher
from analyzer import NewsAnalyzer
from formatter import generate_briefing
from intelligence import IntelligenceSynthesizer
from deliverer import send_email, save_html_local
from state import load_state, save_state, filter_new_articles, mark_sent

logger = logging.getLogger("main")

MAX_RETRIES = 3
RETRY_DELAY_SEC = 10


def setup_logging(log_file: str | None, verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    handlers = [logging.StreamHandler()]
    if log_file:
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def ensure_config(path: str = "config.yaml") -> bool:
    """Create `path` from config.example.yaml on first run.

    Returns True if the config already existed, False if it was freshly
    created from the example (in which case the caller should exit and let
    the user fill in their credentials).
    """
    if os.path.exists(path):
        return True

    example = os.path.join(os.path.dirname(os.path.abspath(path)), "config.example.yaml")
    if not os.path.exists(example):
        logger.error("Config file not found: %s", path)
        logger.error("Also looked for config.example.yaml next to it, but that is missing too.")
        logger.error("Restore config.example.yaml from the repository, or create the config manually.")
        sys.exit(1)

    shutil.copyfile(example, path)
    logger.warning("Created %s from config.example.yaml", path)
    logger.warning("Open it and set your email sender, app password, and recipient.")
    logger.warning("Get a Gmail app password at https://myaccount.google.com/apppasswords")
    return False


def retry(fn, *args, label: str = "operation", **kwargs):
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            last_exc = e
            logger.warning("%s failed (attempt %d/%d): %s", label, attempt, MAX_RETRIES, e)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SEC)
    logger.error("%s failed after %d attempts", label, MAX_RETRIES)
    raise last_exc


def main():
    parser = argparse.ArgumentParser(description="Personal News Briefing")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument("--output", "-o", help="Save HTML to file instead of sending email")
    parser.add_argument("--no-analyze", action="store_true", help="Skip LLM analysis")
    parser.add_argument("--no-intel", action="store_true", help="Skip intelligence synthesis")
    parser.add_argument("--max-triads", type=int, default=5, help="Max triads per category")
    parser.add_argument("--log-file", help="Path to log file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    parser.add_argument("--force", action="store_true", help="Send even if no clusters found")
    args = parser.parse_args()

    setup_logging(args.log_file, args.verbose)
    logger.info("Starting Personal News Briefing")

    if not ensure_config(args.config):
        logger.error("Fill in the email settings in %s, then run again.", args.config)
        sys.exit(1)

    config = load_config(args.config)
    matching_cfg = config.get("matching", {})
    max_triads = args.max_triads or matching_cfg.get("max_triads_per_category", 5)
    threshold = matching_cfg.get("similarity_threshold", 0.65)
    min_sources = matching_cfg.get("min_sources_for_triad", 2)

    state = load_state()

    # Step 1: Fetch
    logger.info("Fetching articles from %d categories...", len(config["categories"]))
    try:
        raw_articles = retry(fetch_all, config, label="fetch_all")
    except Exception:
        logger.error("Failed to fetch articles. Check network and RSS feed URLs in config.yaml.")
        sys.exit(2)
    logger.info("Total articles fetched: %d", len(raw_articles))

    # Step 2: Deduplicate
    new_articles = filter_new_articles(raw_articles, state)
    logger.info("New articles (not previously sent): %d", len(new_articles))

    if not new_articles:
        logger.info("No new articles to process. Nothing to send.")
        return

    # Step 3: Cluster
    logger.info("Clustering articles by topic similarity (threshold=%.2f)...", threshold)
    matcher = ArticleMatcher(threshold=threshold, min_sources=min_sources)
    clusters = matcher.process(new_articles, config["categories"])

    # Cap per category
    category_counts: dict[str, int] = {}
    capped_clusters = []
    for c in clusters:
        slug = c.category_slug
        category_counts.setdefault(slug, 0)
        if category_counts[slug] < max_triads:
            capped_clusters.append(c)
            category_counts[slug] += 1

    logger.info("Formed %d topic clusters (max %d/category)", len(capped_clusters), max_triads)

    if not capped_clusters and not args.force:
        logger.info("No clusters formed. Part 2 (Deep Dive) will be empty, but Parts 1 and 3 will still run.")

    # Step 4: Analyze with Ollama
    if not args.no_analyze:
        analyzer = NewsAnalyzer(config.get("ollama", {}))
        if analyzer.is_available():
            logger.info("Analyzing clusters with Ollama (%s)...", config["ollama"]["model"])
            for i, cluster in enumerate(capped_clusters):
                try:
                    cluster.analysis = retry(
                        analyzer.analyze, cluster,
                        label=f"analyze cluster {i+1}/{len(capped_clusters)}",
                    )
                except Exception:
                    logger.warning("Skipping analysis for cluster %d after retries", i + 1)
                    cluster.analysis = None
            analyzed = sum(1 for c in capped_clusters if c and c.analysis)
            logger.info("Analyzed %d/%d clusters", analyzed, len(capped_clusters))
        else:
            logger.warning("Ollama not available at %s. Skipping analysis.", config["ollama"]["base_url"])

    # Step 5: Build category groupings
    articles_by_category: dict[str, list] = {}
    for a in new_articles:
        articles_by_category.setdefault(a.category_slug, []).append(a)

    clusters_by_category: dict[str, list] = {}
    for c in clusters:
        clusters_by_category.setdefault(c.category_slug, []).append(c)

    # Step 6: Intelligence synthesis (Part 3)
    intelligence_data = None
    if not args.no_analyze and not args.no_intel:
        try:
            synthesizer = IntelligenceSynthesizer(config.get("ollama", {}))
            intelligence_data = synthesizer.process(
                articles_by_category, clusters_by_category, config["categories"]
            )
            if intelligence_data and intelligence_data.get("categories"):
                logger.info("Intelligence brief generated for %d categories",
                            len(intelligence_data["categories"]))
        except Exception as e:
            logger.warning("Intelligence synthesis failed: %s", e)

    # Step 7: Generate HTML
    html = generate_briefing(capped_clusters, config, articles_by_category, intelligence_data)

    # Step 8: Deliver
    if args.output:
        save_html_local(html, args.output)
        logger.info("Briefing saved to %s", args.output)
    else:
        email_cfg = config.get("email", {})
        if not email_cfg.get("sender") or email_cfg["sender"] == "your-email@gmail.com":
            logger.warning("Email not configured. Set sender/password in config.yaml first.")
            logger.warning("Saving to briefings/ instead.")
            os.makedirs("briefings", exist_ok=True)
            date_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            save_html_local(html, f"briefings/briefing_{date_str}.html")
            sys.exit(0)

        try:
            sent = retry(send_email, html, email_cfg, label="send_email")
        except Exception:
            logger.error("Email sending failed after retries. Briefing saved to briefings/")
            os.makedirs("briefings", exist_ok=True)
            date_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            save_html_local(html, f"briefings/briefing_{date_str}.html")
            sys.exit(3)

        if sent:
            if capped_clusters:
                for c in capped_clusters:
                    mark_sent(c.articles, state)
            else:
                mark_sent(new_articles, state)
            save_state(state)
            logger.info("Email sent and state updated.")
        else:
            logger.warning("Email not sent. Check SMTP settings in config.yaml.")
            sys.exit(4)

    logger.info("Done.")


if __name__ == "__main__":
    main()
