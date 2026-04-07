"""
NewsApiService — NewsAPI.org wrapper with publisher allowlist.
Stage 8 Macro/Political ONLY. Do NOT use for company-specific claims.
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass

import httpx

from research_pipeline.services.article_extraction_service import ArticleExtractionService, ExtractedArticle

logger = logging.getLogger(__name__)

ALLOWED_PUBLISHERS = frozenset([
    "reuters.com", "apnews.com", "ft.com", "wsj.com", "bloomberg.com",
    "theatlantic.com", "technologyreview.mit.edu", "theinformation.com",
    "semafor.com", "arstechnica.com",
])

BLOCKED_PUBLISHERS = frozenset([
    "yahoo.com", "msn.com", "seeking-alpha.com",
])

AI_INFRA_TOPICS = [
    "semiconductor", "data center", "AI chip", "export control",
    "TSMC", "NVIDIA", "grid interconnection", "AI regulation",
    "chip sanctions", "hyperscaler capex",
]


@dataclass
class NewsArticle:
    title: str
    source: str
    url: str
    url_hash: str
    published_at: str
    description: str = ""
    body_text: str = ""
    is_allowlisted: bool = False

    def to_prompt_line(self) -> str:
        return f"[{self.source}] {self.title} ({self.published_at[:10]})"


class NewsApiService:
    """
    NewsAPI.org wrapper with publisher allowlist enforcement.
    Used only in Stage 8 for macro/regulatory/geopolitical context.
    Gracefully no-ops when NEWS_API_KEY is absent.
    """
    BASE_URL = "https://newsapi.org/v2/everything"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("NEWS_API_KEY", "")
        self._extractor = ArticleExtractionService()

    def _is_key_available(self) -> bool:
        return bool(self.api_key)

    def _is_allowed_source(self, url: str, source_domain: str) -> bool:
        domain = source_domain.lower()
        url_lower = url.lower()
        if any(blocked in domain or blocked in url_lower for blocked in BLOCKED_PUBLISHERS):
            return False
        return any(allowed in domain or allowed in url_lower for allowed in ALLOWED_PUBLISHERS)

    async def get_policy_news(
        self,
        topics: list[str] | None = None,
        days_back: int = 7,
        max_articles: int = 20,
    ) -> list[NewsArticle]:
        """
        Fetch allowlisted macro/regulatory/geopolitical news.
        Returns empty list when API key absent or request fails.
        """
        if not self._is_key_available():
            logger.info("NewsApiService: NEWS_API_KEY absent — skipping news fetch")
            return []

        query_topics = topics or AI_INFRA_TOPICS[:5]
        query = " OR ".join(f'"{t}"' for t in query_topics[:3])

        try:
            from_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).strftime("%Y-%m-%d")
            params = {
                "q": query,
                "from": from_date,
                "sortBy": "relevancy",
                "pageSize": min(max_articles * 2, 100),
                "apiKey": self.api_key,
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(self.BASE_URL, params=params)
                if resp.status_code != 200:
                    logger.warning("NewsAPI returned %s: %s", resp.status_code, resp.text[:200])
                    return []
                data = resp.json()
        except Exception as exc:
            logger.warning("NewsApiService.get_policy_news failed: %s", exc)
            return []

        articles: list[NewsArticle] = []
        seen_hashes: set[str] = set()

        for raw in data.get("articles", []):
            source_name = raw.get("source", {}).get("name", "")
            url = raw.get("url", "")
            if not url:
                continue

            extracted = self._extractor.extract_from_text(
                url=url,
                title=raw.get("title", ""),
                raw_text=(raw.get("description") or "") + " " + (raw.get("content") or ""),
            )

            if extracted.url_hash in seen_hashes:
                continue
            seen_hashes.add(extracted.url_hash)

            is_allowed = self._is_allowed_source(url, source_name)

            article = NewsArticle(
                title=raw.get("title", ""),
                source=source_name,
                url=url,
                url_hash=extracted.url_hash,
                published_at=raw.get("publishedAt", ""),
                description=raw.get("description", ""),
                body_text=extracted.truncate_for_prompt(300),
                is_allowlisted=is_allowed,
            )

            if is_allowed:
                articles.append(article)
                if len(articles) >= max_articles:
                    break

        logger.info("NewsApiService: returned %d allowlisted articles", len(articles))
        return articles

    def format_for_prompt(self, articles: list[NewsArticle], max_items: int = 15) -> str:
        """Format article list as prompt-ready text."""
        if not articles:
            return "No macro/policy news available."
        lines = [a.to_prompt_line() for a in articles[:max_items]]
        return "\n".join(lines)
