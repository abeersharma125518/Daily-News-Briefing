import json
import logging
from typing import Optional
import httpx

from matcher import ArticleCluster

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """You are a media analysis assistant. Below are news articles from different sources covering the same topic.

{articles_text}

Analyze these articles. Respond with valid JSON only. No markdown, no code fences. Use this exact structure:
{{
  "common_facts": "What specific facts do all sources agree on? List each fact concisely.",
  "disagreements": "Where do the sources differ in facts, emphasis, or framing? Be specific.",
  "narratives": "What underlying narrative or perspective does each source emphasize? Write as plain text like 'The Hindu: focuses on... OpIndia: emphasizes...' Do NOT use Python dict syntax."
}}"""


def build_articles_text(cluster: ArticleCluster) -> str:
    parts = []
    for i, a in enumerate(cluster.articles, 1):
        summary = a.summary[:800] if a.summary else "(no summary)"
        parts.append(f"Article {i} ({a.source_name}, bias: {a.source_bias}): {a.title}\n{summary}")
    return "\n\n".join(parts)


class NewsAnalyzer:
    def __init__(self, ollama_config: dict):
        self.model = ollama_config.get("model", "llama3.2")
        self.base_url = ollama_config.get("base_url", "http://localhost:11434")
        self.temperature = ollama_config.get("temperature", 0.3)
        self.timeout = 120

    def analyze(self, cluster: ArticleCluster) -> Optional[dict]:
        if len(cluster.articles) < 2:
            return None

        articles_text = build_articles_text(cluster)
        prompt = ANALYSIS_PROMPT.format(articles_text=articles_text)

        try:
            resp = httpx.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "temperature": self.temperature,
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
                raw = raw[json_start:json_end + 1]

            parsed = json.loads(raw)
            return {
                "common_facts": parsed.get("common_facts", ""),
                "disagreements": parsed.get("disagreements", ""),
                "narratives": parsed.get("narratives", ""),
            }
        except httpx.ConnectError:
            logger.warning("Cannot connect to Ollama at %s. Is it running?", self.base_url)
            return None
        except (httpx.RequestError, json.JSONDecodeError, KeyError) as e:
            logger.warning("Ollama analysis failed: %s", e)
            return None

    def is_available(self) -> bool:
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False
