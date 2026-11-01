import json
import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

CATEGORY_PROMPT = """You are an intelligence analyst creating a neutral, unbiased daily synthesis. Below are articles from multiple sources covering "{category_name}".

--- ARTICLES ---
{articles_section}

{clusters_section}

Generate a structured intelligence brief for this category. Respond ONLY with valid JSON. No markdown, no code fences, no extra text.

Use this exact structure:
{{
  "summary": "1-2 sentence global summary of all major developments in this category today",
  "developments": [
    {{
      "headline": "Short headline (max 10 words)",
      "what": "2-3 sentences explaining what is happening",
      "consensus": "1 sentence on how sources align or differ on this story",
      "why_matters": "1 sentence explaining significance"
    }}
  ],
  "bias_signals": "2-3 sentences on framing differences across sources. Skip if only one source type.",
  "watch_next": [
    "predictive bullet based strictly on reported facts"
  ]
}}

Rules:
- Be completely neutral. Do not take sides.
- Max 5 developments.
- If a perspective comes only from one side, note it factually.
- watch_next: 1-3 items, based only on reported developments.
- Use plain text."""

GLOBAL_SIGNAL_PROMPT = """You are an intelligence analyst. Below are daily news summaries across categories:

{summaries_text}

Identify the dominant theme of today's news cycle with ONE short label (max 45 characters).

Respond with ONLY valid JSON:
{{"signal": "the label"}}

Examples: "Geopolitics-heavy day", "Domestic policy + elections focus", "Tech regulation + AI acceleration", "Mixed — regional conflicts and trade", "Quiet news day", "Economic policy dominates"."""


class IntelligenceSynthesizer:
    def __init__(self, ollama_config: dict):
        self.model = ollama_config.get("model", "llama3.2")
        self.base_url = ollama_config.get("base_url", "http://localhost:11434")
        self.temperature = 0.2
        self.timeout = 120

    def _call_llm(self, prompt: str, temperature: float | None = None) -> str | None:
        try:
            resp = httpx.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": temperature or self.temperature,
                    "stream": False,
                    "format": "json",
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            raw = data.get("response", "").strip()
            json_start = raw.find("{")
            json_end = raw.rfind("}")
            if json_start >= 0 and json_end > json_start:
                return raw[json_start:json_end + 1]
            return raw
        except Exception as e:
            logger.warning("Intelligence LLM call failed: %s", e)
            return None

    @staticmethod
    def _build_articles_section(articles: list, max_per_source: int = 10) -> str:
        by_source: dict[str, list] = {}
        for a in articles:
            by_source.setdefault(a.source_name, []).append(a)

        lines = []
        for src_name, src_articles in by_source.items():
            bias = src_articles[0].source_bias if src_articles else "unknown"
            lines.append(f"--- {src_name} (bias: {bias}) ---")
            for a in src_articles[:max_per_source]:
                lines.append(f"- {a.title}")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _build_clusters_section(clusters: list) -> str:
        if not clusters:
            return ""
        lines = ["--- MULTI-SOURCE STORIES ---"]
        for i, c in enumerate(clusters, 1):
            sources = ", ".join(c.unique_sources)
            lines.append(f'{i}. "{c.title}"')
            lines.append(f"   Sources: {sources}")
            if c.analysis:
                facts = c.analysis.get("common_facts", "")
                narr = c.analysis.get("narratives", "")
                if facts:
                    lines.append(f"   Consensus: {facts}")
                if narr:
                    lines.append(f"   Framing: {narr}")
            lines.append("")
        return "\n".join(lines)

    def synthesize_category(
        self, cat_name: str, articles: list, clusters: list
    ) -> dict | None:
        if not articles:
            return None

        articles_section = self._build_articles_section(articles)
        clusters_section = self._build_clusters_section(clusters)

        prompt = CATEGORY_PROMPT.format(
            category_name=cat_name,
            articles_section=articles_section,
            clusters_section=clusters_section,
        )

        raw = self._call_llm(prompt)
        if not raw:
            return None

        try:
            parsed = json.loads(raw)
            return {
                "summary": parsed.get("summary", ""),
                "developments": parsed.get("developments", []),
                "bias_signals": parsed.get("bias_signals", ""),
                "watch_next": parsed.get("watch_next", []),
            }
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("Failed to parse intelligence output for %s: %s", cat_name, e)
            return None

    def global_signal(self, category_results: dict[str, dict]) -> str:
        summaries_text = ""
        for cat_key, result in category_results.items():
            if result and result.get("summary"):
                summaries_text += f"- {cat_key}: {result['summary']}\n"

        if not summaries_text:
            return "No data"

        prompt = GLOBAL_SIGNAL_PROMPT.format(summaries_text=summaries_text)
        raw = self._call_llm(prompt, temperature=0.1)
        if not raw:
            return "No data"

        try:
            parsed = json.loads(raw)
            return parsed.get("signal", "No data")
        except (json.JSONDecodeError, KeyError):
            return "No data"

    def process(
        self,
        articles_by_category: dict[str, list],
        clusters_by_category: dict[str, list],
        config_categories: dict,
    ) -> dict:
        results: dict[str, dict] = {}
        for cat_key, cat_config in config_categories.items():
            cat_name = cat_config.get("name", cat_key)
            articles = articles_by_category.get(cat_key, [])
            clusters = clusters_by_category.get(cat_key, [])
            if not articles:
                continue
            result = self.synthesize_category(cat_name, articles, clusters)
            if result:
                results[cat_key] = result
            logger.info("Synthesized intelligence for %s", cat_name)

        signal = self.global_signal(results)
        return {
            "signal": signal,
            "categories": results,
        }
