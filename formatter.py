import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from jinja2 import Template

from matcher import ArticleCluster, TRIAD_STATUS_3SOURCE

logger = logging.getLogger(__name__)

KOLKATA_OFFSET = timedelta(hours=5, minutes=30)

TEMPLATE_STR = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body { font-family: Georgia, 'Times New Roman', serif; color: #222; max-width: 680px; margin: 0 auto; padding: 20px; background: #fafafa; }
.header { text-align: center; border-bottom: 3px solid #1a1a2e; padding: 25px 0 20px; margin-bottom: 25px; }
.header h1 { font-size: 26px; margin: 0; color: #1a1a2e; letter-spacing: 1px; }
.header .subtitle { font-size: 13px; color: #888; margin-top: 6px; }
.header .date { font-size: 15px; color: #555; margin-top: 4px; font-weight: bold; }

.part-header { text-align: center; padding: 20px 0 5px; margin: 0; }
.part-header h2 { font-size: 20px; margin: 0; letter-spacing: 0.5px; }
.part-header .sub { font-size: 12px; color: #888; margin-top: 2px; }
.section-divider { border: none; border-top: 2px solid #ddd; margin: 30px 0 10px; }

.category { margin: 28px 0; background: #fff; border-radius: 6px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); overflow: hidden; }
.category-header { padding: 12px 18px; font-size: 17px; font-weight: bold; color: #fff; }

.source-group { padding: 8px 18px; border-bottom: 1px solid #f0f0f0; }
.source-group:last-child { border-bottom: none; }
.source-header { font-size: 13px; font-weight: bold; margin-bottom: 4px; display: flex; align-items: center; gap: 8px; }
.headline-row { padding: 2px 0 2px 20px; font-size: 13px; line-height: 1.5; }
.headline-row a { color: #333; text-decoration: none; }
.headline-row a:hover { text-decoration: underline; color: #1a1a2e; }
.dd-tag { display: inline-block; font-size: 10px; color: #1565c0; margin-left: 6px; font-weight: bold; }

.bias-tag { display: inline-block; padding: 1px 7px; font-size: 10px; font-weight: bold; border-radius: 3px; margin-right: 8px; flex-shrink: 0; margin-top: 1px; text-transform: uppercase; letter-spacing: 0.3px; }
.bias-left { background: #dbeafe; color: #1e40af; }
.bias-right { background: #ffe0e0; color: #b71c1c; }
.bias-center { background: #f0f0f0; color: #555; }
.bias-western { background: #e8f5e9; color: #2e7d32; }
.bias-non-western { background: #fff3e0; color: #e65100; }

.story { padding: 16px 18px; border-bottom: 1px solid #eee; }
.story:last-child { border-bottom: none; }
.story-title { font-size: 15px; font-weight: bold; margin: 0 0 10px; color: #1a1a2e; }
.source-row { display: flex; align-items: flex-start; margin: 4px 0; font-size: 13px; line-height: 1.4; }
.source-link { color: #333; text-decoration: none; flex: 1; }
.source-link:hover { text-decoration: underline; color: #1a1a2e; }

.analysis { margin: 12px 0 0; padding: 12px 14px; background: #f8f9fa; border-left: 3px solid #1a1a2e; border-radius: 0 4px 4px 0; font-size: 13px; line-height: 1.5; }
.analysis h4 { font-size: 12px; font-weight: bold; margin: 8px 0 3px; text-transform: uppercase; letter-spacing: 0.5px; }
.analysis h4:first-child { margin-top: 0; }
.analysis h4.facts { color: #2e7d32; }
.analysis h4.disc { color: #c62828; }
.analysis h4.narr { color: #1565c0; }
.analysis p { margin: 2px 0 6px; color: #444; }

.empty-message { padding: 16px 18px; color: #999; font-style: italic; text-align: center; }

.signal-banner { background: #1a1a2e; color: #fff; text-align: center; padding: 12px 18px; font-size: 14px; }
.signal-label { font-weight: bold; }
.signal-value { font-weight: normal; }
.intel-content { padding: 12px 18px; }
.intel-section { margin: 14px 0; }
.intel-section:first-child { margin-top: 0; }
.intel-label { font-size: 14px; font-weight: bold; color: #1a1a2e; margin-bottom: 6px; }
.intel-dev { margin: 10px 0; padding: 10px 12px; background: #f8f9fa; border-left: 3px solid #1a1a2e; border-radius: 0 4px 4px 0; }
.intel-dev-title { font-size: 14px; font-weight: bold; color: #1a1a2e; margin-bottom: 4px; }
.intel-dev p { margin: 3px 0; font-size: 13px; line-height: 1.5; color: #444; }
.intel-dev p strong { color: #222; }
.intel-section ul { margin: 4px 0; padding-left: 20px; }
.intel-section li { font-size: 13px; line-height: 1.5; color: #444; margin: 4px 0; }

.footer { text-align: center; font-size: 11px; color: #999; padding: 20px 0 10px; }
</style>
</head>
<body>
<div class="header">
  <h1>Personal News Briefing</h1>
  <div class="date">{{ date }}</div>
  <div class="subtitle">{{ num_categories }} categories &middot; {{ num_sources }} sources &middot; AI-analyzed</div>
</div>

<div class="part-header">
  <h2>📰 News Brief</h2>
  <div class="sub">All major headlines across every outlet &mdash; {{ total_articles }} articles today</div>
</div>

{% for cat in categories %}
<div class="category">
  <div class="category-header" style="background: {{ cat.color }};">
    {{ cat.icon }} {{ cat.name }}
  </div>
  {% for sg in cat.source_groups %}
  <div class="source-group">
    <div class="source-header">
      <span class="bias-tag bias-{{ sg.bias_class }}">{{ sg.bias_label }}</span>
      {{ sg.name }}
    </div>
    {% for a in sg.articles[:5] %}
    <div class="headline-row">
      <a href="{{ a.url }}" target="_blank">{{ a.title }}</a>
      {% if a.is_deep_dive %}<span class="dd-tag">&rarr; Deep Dive</span>{% endif %}
    </div>
    {% endfor %}
  </div>
  {% endfor %}
  {% if not cat.source_groups %}
  <div class="empty-message">No articles from this category today.</div>
  {% endif %}
</div>
{% endfor %}

<hr class="section-divider">

<div class="part-header">
  <h2>🔍 Deep Dive</h2>
  <div class="sub">Stories covered by multiple sources &mdash; with AI analysis</div>
</div>

{% for cat in categories %}
<div class="category">
  <div class="category-header" style="background: {{ cat.color }};">
    {{ cat.icon }} {{ cat.name }}
  </div>
  {% for story in cat.stories %}
  <div class="story">
    <div class="story-title">{{ story.title }}</div>
    {% for src in story.sources %}
    <div class="source-row">
      <span class="bias-tag bias-{{ src.bias_class }}">{{ src.bias_label }}</span>
      <a class="source-link" href="{{ src.url }}" target="_blank">{{ src.name }}</a>
    </div>
    {% endfor %}
    {% if story.analysis %}
    <div class="analysis">
      <h4 class="facts">&#10003; Common Facts</h4>
      <p>{{ story.analysis.common_facts }}</p>
      <h4 class="disc">&#10007; Points of Disagreement</h4>
      <p>{{ story.analysis.disagreements }}</p>
      <h4 class="narr">&#8635; Narrative Differences</h4>
      <p>{{ story.analysis.narratives }}</p>
    </div>
    {% endif %}
  </div>
  {% endfor %}
  {% if not cat.stories %}
  <div class="empty-message">No multi-source stories found for this category today.</div>
  {% endif %}
</div>
{% endfor %}

{% if intel_data and intel_data.categories %}
<hr class="section-divider">

<div class="part-header">
  <h2>🧠 Intelligence Brief</h2>
  <div class="sub">5-minute synthesis &mdash; what matters and why</div>
</div>

{% if intel_data.signal %}
<div class="signal-banner">
  <span class="signal-label">🧭 Today's Signal:</span>
  <span class="signal-value">{{ intel_data.signal }}</span>
</div>
{% endif %}

{% for intel_cat in intel_categories %}
<div class="category">
  <div class="category-header" style="background: {{ intel_cat.color }};">
    {{ intel_cat.icon }} {{ intel_cat.name }}
  </div>
  <div class="intel-content">
    {% if intel_cat.summary %}
    <div class="intel-section">
      <div class="intel-label">🌐 What's happening</div>
      <p>{{ intel_cat.summary }}</p>
    </div>
    {% endif %}

    {% if intel_cat.developments %}
    <div class="intel-section">
      <div class="intel-label">🧩 Key Developments</div>
      {% for dev in intel_cat.developments %}
      <div class="intel-dev">
        <div class="intel-dev-title">{{ dev.headline }}</div>
        <p><strong>What:</strong> {{ dev.what }}</p>
        {% if dev.consensus %}<p><strong>Consensus:</strong> {{ dev.consensus }}</p>{% endif %}
        <p><strong>Why it matters:</strong> {{ dev.why_matters }}</p>
      </div>
      {% endfor %}
    </div>
    {% endif %}

    {% if intel_cat.bias_signals %}
    <div class="intel-section">
      <div class="intel-label">⚖️ Narrative / Bias Signals</div>
      <p>{{ intel_cat.bias_signals }}</p>
    </div>
    {% endif %}

    {% if intel_cat.watch_next %}
    <div class="intel-section">
      <div class="intel-label">🔥 What to Watch Next</div>
      <ul>
      {% for item in intel_cat.watch_next %}
        <li>{{ item }}</li>
      {% endfor %}
      </ul>
    </div>
    {% endif %}
  </div>
</div>
{% endfor %}
{% endif %}

<div class="footer">
  Generated at {{ time }} IST by Personal News Briefing
</div>
</body>
</html>"""

CATEGORY_COLORS = {
    "world_us": "#1a237e",
    "india": "#e65100",
    "pakistan": "#1b5e20",
    "ai": "#4a148c",
    "defense": "#37474f",
    "conflicts_geopolitics": "#b71c1c",
}

BIAS_LABELS = {
    "left": "LEFT",
    "right": "RIGHT",
    "center": "CENTER",
    "western": "WESTERN",
    "non-western": "NON-WESTERN",
}

MAX_STORIES_PER_CATEGORY = 5
MAX_ARTICLES_PER_SOURCE = 5

template = Template(TEMPLATE_STR)


def generate_briefing(
    clusters: list[ArticleCluster],
    config: dict,
    all_articles_by_category: dict[str, list] | None = None,
    intelligence_data: dict | None = None,
) -> str:
    now_kolkata = datetime.now(timezone.utc) + KOLKATA_OFFSET
    date_str = now_kolkata.strftime("%A, %B %d, %Y")
    time_str = now_kolkata.strftime("%I:%M %p")

    # Build clustered GUID set for Deep Dive tags
    clustered_guids: set[str] = set()
    for c in clusters:
        for a in c.articles:
            clustered_guids.add(a.guid)

    # Group clusters by category
    clusters_by_category: dict[str, list[ArticleCluster]] = {}
    for c in clusters:
        clusters_by_category.setdefault(c.category_slug, []).append(c)

    category_data = []
    total_articles = 0

    for cat_key, cat_config in config["categories"].items():
        color = CATEGORY_COLORS.get(cat_key, "#333")
        icon = cat_config.get("icon", "")

        # --- Part 1: Source groups ---
        source_groups = []
        article_order = [s["name"] for s in cat_config["sources"]]
        cat_articles = (all_articles_by_category or {}).get(cat_key, [])
        total_articles += len(cat_articles)

        for src_name in article_order:
            src_articles = [a for a in cat_articles if a.source_name == src_name][:MAX_ARTICLES_PER_SOURCE]
            if not src_articles:
                continue
            bias_class = src_articles[0].source_bias
            source_groups.append({
                "name": src_name,
                "bias_class": bias_class,
                "bias_label": BIAS_LABELS.get(bias_class, bias_class.upper()),
                "articles": [
                    {
                        "title": a.title,
                        "url": a.url,
                        "is_deep_dive": a.guid in clustered_guids,
                    }
                    for a in src_articles
                ],
            })

        # --- Part 2: Clustered stories ---
        stories = []
        for cluster in clusters_by_category.get(cat_key, [])[:MAX_STORIES_PER_CATEGORY]:
            source_rows = []
            for a in cluster.articles:
                bias_class = a.source_bias if a.source_bias else "center"
                bias_label = BIAS_LABELS.get(bias_class, bias_class.upper())
                source_rows.append({
                    "name": a.source_name,
                    "url": a.url,
                    "bias_class": bias_class,
                    "bias_label": bias_label,
                })

            analysis = None
            if cluster.analysis:
                analysis = {
                    "common_facts": cluster.analysis.get("common_facts", ""),
                    "disagreements": cluster.analysis.get("disagreements", ""),
                    "narratives": cluster.analysis.get("narratives", ""),
                }

            stories.append({
                "title": cluster.title,
                "sources": source_rows,
                "analysis": analysis,
            })

        category_data.append({
            "name": cat_config["name"],
            "color": color,
            "icon": icon,
            "source_groups": source_groups,
            "stories": stories,
        })

    num_sources = sum(len(sg) for cat in category_data for sg in cat["source_groups"])

    # Part 3: Intelligence
    intel_categories = []
    if intelligence_data and intelligence_data.get("categories"):
        for cat_key, cat_config in config["categories"].items():
            cat_intel = intelligence_data["categories"].get(cat_key)
            if not cat_intel:
                continue
            intel_categories.append({
                "name": cat_config.get("name", cat_key),
                "color": CATEGORY_COLORS.get(cat_key, "#333"),
                "icon": cat_config.get("icon", ""),
                "summary": cat_intel.get("summary", ""),
                "developments": cat_intel.get("developments", []),
                "bias_signals": cat_intel.get("bias_signals", ""),
                "watch_next": cat_intel.get("watch_next", []),
            })

    return template.render(
        categories=category_data,
        date=date_str,
        time=time_str,
        total_articles=total_articles,
        num_categories=len(config["categories"]),
        num_sources=num_sources,
        intel_data=intelligence_data,
        intel_categories=intel_categories,
    )
