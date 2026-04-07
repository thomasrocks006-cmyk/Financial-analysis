"""
SourceRankingService — publisher trust scores and URL-hash deduplication.
"""
import hashlib
import logging
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)

PUBLISHER_TRUST_SCORES: dict[str, float] = {
    "reuters.com": 0.95,
    "apnews.com": 0.95,
    "ft.com": 0.92,
    "wsj.com": 0.90,
    "bloomberg.com": 0.90,
    "theinformation.com": 0.88,
    "semafor.com": 0.80,
    "arstechnica.com": 0.78,
    "technologyreview.mit.edu": 0.85,
    "theatlantic.com": 0.75,
    "cnbc.com": 0.70,
    "businessinsider.com": 0.60,
    "yahoo.com": 0.30,
    "msn.com": 0.25,
    "seeking-alpha.com": 0.35,
}


class RankedSource(BaseModel):
    url: str
    url_hash: str
    source_domain: str
    trust_score: float = 0.5
    title: str = ""
    body_snippet: str = ""


class SourceRankingService:
    """
    Publisher trust scores (0.0–1.0), URL-hash deduplication,
    source diversity enforcement.
    """

    def __init__(self) -> None:
        self._seen_hashes: set[str] = set()

    def get_trust_score(self, domain: str) -> float:
        domain = domain.lower()
        for key, score in PUBLISHER_TRUST_SCORES.items():
            if key in domain:
                return score
        return 0.5  # Default for unknown publisher

    def hash_url(self, url: str) -> str:
        return hashlib.sha256(url.strip().lower().encode()).hexdigest()[:16]

    def rank_and_deduplicate(
        self, sources: list[dict], max_per_publisher: int = 3
    ) -> list[RankedSource]:
        """
        Takes list of {"url": ..., "source": ..., "title": ..., "body": ...}.
        Returns deduplicated, trust-ranked sources, capped per publisher.
        """
        result: list[RankedSource] = []
        publisher_counts: dict[str, int] = {}

        # Sort by trust score descending
        scored = []
        for s in sources:
            url = s.get("url", "")
            domain = s.get("source", "")
            score = self.get_trust_score(domain)
            scored.append((score, url, s))
        scored.sort(key=lambda x: x[0], reverse=True)

        for score, url, s in scored:
            url_hash = self.hash_url(url)
            if url_hash in self._seen_hashes:
                continue

            domain = s.get("source", "unknown")
            pub_count = publisher_counts.get(domain, 0)
            if pub_count >= max_per_publisher:
                continue

            self._seen_hashes.add(url_hash)
            publisher_counts[domain] = pub_count + 1

            result.append(RankedSource(
                url=url,
                url_hash=url_hash,
                source_domain=domain,
                trust_score=score,
                title=s.get("title", ""),
                body_snippet=s.get("body", "")[:200],
            ))

        return result

    def reset_seen(self) -> None:
        self._seen_hashes.clear()
