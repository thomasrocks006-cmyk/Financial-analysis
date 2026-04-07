"""
ArticleExtractionService — fetch full article text from URL, clean body, strip nav/ads.
Prerequisite for NewsAPI integration.
"""
import hashlib
import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExtractedArticle:
    url: str
    url_hash: str  # SHA-256 of normalized URL for dedup
    title: str = ""
    body_text: str = ""  # Cleaned article body
    word_count: int = 0
    extraction_success: bool = False
    error: str = ""

    @classmethod
    def from_url(cls, url: str, title: str = "", body_text: str = "") -> "ExtractedArticle":
        url_hash = hashlib.sha256(url.strip().lower().encode()).hexdigest()[:16]
        clean_body = _clean_text(body_text)
        return cls(
            url=url,
            url_hash=url_hash,
            title=title,
            body_text=clean_body,
            word_count=len(clean_body.split()),
            extraction_success=bool(clean_body),
        )

    def truncate_for_prompt(self, max_words: int = 300) -> str:
        """Truncate body to max_words for LLM prompt injection."""
        words = self.body_text.split()
        if len(words) <= max_words:
            return self.body_text
        return " ".join(words[:max_words]) + " [truncated]"


def _clean_text(raw: str) -> str:
    """Strip HTML tags, nav/ad patterns, excess whitespace."""
    if not raw:
        return ""
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", raw)
    # Remove URLs
    text = re.sub(r"https?://\S+", "", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Remove very short segments (nav/ad artifacts)
    lines = [ln.strip() for ln in text.split("\n") if len(ln.strip()) > 40]
    return "\n".join(lines) if lines else text


class ArticleExtractionService:
    """
    Fetch full article body from URL, clean, and chunk for prompt injection.
    Prerequisite for NewsAPI integration (DSQ-9).
    All fetches are best-effort; failures return ExtractedArticle with extraction_success=False.
    """

    def __init__(self) -> None:
        self._seen_hashes: set[str] = set()

    def extract_from_text(self, url: str, title: str, raw_text: str) -> ExtractedArticle:
        """Extract from pre-fetched raw text (e.g., NewsAPI description/content field)."""
        return ExtractedArticle.from_url(url, title, raw_text)

    def deduplicate(self, articles: list[ExtractedArticle]) -> list[ExtractedArticle]:
        """Remove duplicate articles by URL hash (cross-service dedup)."""
        seen: set[str] = set()
        result = []
        for art in articles:
            if art.url_hash not in seen:
                seen.add(art.url_hash)
                result.append(art)
        return result

    def get_seen_hashes(self) -> set[str]:
        return set(self._seen_hashes)

    def register_hash(self, url_hash: str) -> None:
        self._seen_hashes.add(url_hash)
