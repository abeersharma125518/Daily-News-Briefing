import logging
from datetime import datetime, timezone
from typing import Optional
from itertools import combinations

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer

from fetcher import Article

logger = logging.getLogger(__name__)

TRIAD_STATUS_3SOURCE = "3-source"
TRIAD_STATUS_2SOURCE = "2-source"

class ArticleCluster:
    def __init__(self, articles: list[Article], similarity: float, category_slug: str = ""):
        self.articles = sorted(articles, key=lambda a: a.published or datetime.min, reverse=True)
        self.similarity = similarity
        self.analysis: Optional[dict] = None
        self.category_slug = category_slug

    @property
    def title(self) -> str:
        return self.articles[0].title

    @property
    def unique_sources(self) -> list[str]:
        seen = set()
        result = []
        for a in self.articles:
            if a.source_name not in seen:
                seen.add(a.source_name)
                result.append(a.source_name)
        return result

    @property
    def status(self) -> str:
        return TRIAD_STATUS_3SOURCE if len(self.unique_sources) >= 3 else TRIAD_STATUS_2SOURCE

    def get_source_coverage(self, category_sources: list[str]) -> list[Optional[Article]]:
        mapping = {a.source_name: a for a in self.articles}
        return [mapping.get(s) for s in category_sources]


class ArticleMatcher:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2",
                 threshold: float = 0.75,
                 min_sources: int = 2):
        logger.info("Loading embedding model: %s", model_name)
        self.model = SentenceTransformer(model_name)
        self.threshold = threshold
        self.min_sources = min_sources

    def cluster_category(self, articles: list[Article],
                         category_sources: list[str]) -> list[ArticleCluster]:
        if len(articles) < self.min_sources:
            return []

        texts = []
        for a in articles:
            t = a.title
            if a.summary:
                t += ". " + a.summary[:500]
            texts.append(t)

        embeddings = self.model.encode(texts, show_progress_bar=False)
        sim_matrix = cosine_similarity(embeddings, embeddings)

        assigned = set()
        clusters = []

        indices_by_date = sorted(
            range(len(articles)),
            key=lambda i: articles[i].published.timestamp() if articles[i].published else 0,
            reverse=True,
        )

        for i in indices_by_date:
            if i in assigned:
                continue

            matches = []
            source_set = {articles[i].source_name}

            for j in range(len(articles)):
                if i == j or j in assigned:
                    continue
                if articles[j].source_name in source_set:
                    continue
                score = float(sim_matrix[i][j])
                if score >= self.threshold:
                    matches.append((j, score))
                    source_set.add(articles[j].source_name)

            if len(source_set) >= self.min_sources:
                cluster_indices = [i] + [m[0] for m in matches]
                avg_sim = np.mean([sim_matrix[i][j] for j, _ in matches])
                cluster_articles = [articles[idx] for idx in cluster_indices]
                clusters.append(ArticleCluster(cluster_articles, float(avg_sim), articles[i].category_slug))
                for idx in cluster_indices:
                    assigned.add(idx)
            elif len(articles) >= 2:
                assigned.add(i)

        clusters.sort(key=lambda c: (len(c.unique_sources), c.articles[0].published.timestamp()
                                     if c.articles[0].published else 0), reverse=True)
        logger.info("Found %d clusters in category", len(clusters))
        return clusters

    def process(self, articles: list[Article],
                categories: dict) -> list[ArticleCluster]:
        by_category: dict[str, list[Article]] = {}
        all_clusters: list[ArticleCluster] = []

        for a in articles:
            by_category.setdefault(a.category_slug, []).append(a)

        for cat_key, cat_articles in by_category.items():
            if cat_key not in categories:
                continue
            cat_config = categories[cat_key]
            source_names = [s['name'] for s in cat_config['sources']]
            clusters = self.cluster_category(cat_articles, source_names)
            all_clusters.extend(clusters)

        all_clusters.sort(
            key=lambda c: (len(c.unique_sources), c.articles[0].published.timestamp()
                           if c.articles[0].published else 0),
            reverse=True,
        )
        return all_clusters
