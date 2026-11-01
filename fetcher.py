import feedparser
import logging
import ssl
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from dateutil import parser as dateparser

logger = logging.getLogger(__name__)

_ssl_ctx = ssl.create_default_context()

@dataclass
class Article:
    title: str
    url: str
    summary: str
    published: Optional[datetime]
    source_name: str
    source_bias: str
    category: str
    category_slug: str
    guid: str

def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        dt = dateparser.parse(date_str)
        if dt and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def fetch_feed(url: str, source_name: str, timeout: int = 15) -> list[feedparser.FeedParserDict]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PersonalNewsBriefing/1.0"})
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx) as resp:
            raw = resp.read()
        feed = feedparser.parse(raw)
        if feed.bozo and not feed.entries:
            logger.warning("Failed to parse feed %s: %s", source_name, feed.bozo_exception)
            return []
        return feed.entries
    except Exception as e:
        logger.warning("Failed to parse feed %s: %s", source_name, e)
        return []

def fetch_category(cat_key: str, cat_config: dict) -> list[Article]:
    articles: list[Article] = []
    max_per_source = 30

    for source in cat_config['sources']:
        entries = fetch_feed(source['rss'], source['name'])
        for entry in entries[:max_per_source]:
            title = getattr(entry, 'title', None) or ''
            url = getattr(entry, 'link', None) or ''
            summary = ''
            if hasattr(entry, 'summary'):
                summary = entry.summary
            elif hasattr(entry, 'description'):
                summary = entry.description
            published = parse_date(getattr(entry, 'published', None))
            guid = getattr(entry, 'id', None) or url

            if not title or not url:
                continue

            articles.append(Article(
                title=title,
                url=url,
                summary=summary,
                published=published,
                source_name=source['name'],
                source_bias=source['bias'],
                category=cat_config['name'],
                category_slug=cat_key,
                guid=guid,
            ))

    logger.info("Fetched %d articles from %s", len(articles), cat_config['name'])
    return articles

def fetch_all(config: dict) -> list[Article]:
    all_articles: list[Article] = []
    for cat_key, cat_config in config['categories'].items():
        articles = fetch_category(cat_key, cat_config)
        all_articles.extend(articles)
    return all_articles
