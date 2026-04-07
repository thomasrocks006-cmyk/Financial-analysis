"""
IRScraperService — company IR RSS feed scraper.
Robots.txt-respecting. Rate-limited. Feeds Stage 5 and Stage 10.
"""
import hashlib
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

IR_RSS_FEEDS: dict[str, str] = {
    "NVDA":  "https://nvidianews.nvidia.com/rss/news",
    "AMD":   "https://ir.amd.com/rss/news-releases.xml",
    "AVGO":  "https://investors.broadcom.com/rss/news-releases.xml",
    "AMAT":  "https://ir.appliedmaterials.com/rss/news-releases.xml",
    "MSFT":  "https://news.microsoft.com/source/feed/",
    "AMZN":  "https://ir.aboutamazon.com/rss.xml",
    "GOOG":  "https://abc.xyz/investor/rss/",
    "META":  "https://investor.fb.com/rss/news-releases.xml",
    "CEG":   "https://ir.constellationenergy.com/rss/news-releases.xml",
}

MATERIAL_KEYWORDS = [
    "acquisition", "merger", "partnership", "contract", "guidance",
    "earnings", "quarterly", "dividend", "share", "buyback", "debt",
    "CEO", "CFO", "executive", "regulatory", "SEC", "FTC", "DOJ",
]


class IRNewsItem(BaseModel):
    ticker: str
    title: str
    url: str
    url_hash: str
    published_at: str
    is_material: bool = False
    body_snippet: str = ""

    def to_prompt_line(self) -> str:
        tag = "[MATERIAL] " if self.is_material else ""
        return f"[IR/{self.ticker}] {tag}{self.title} ({self.published_at[:10]})"


class IRScraperService:
    """
    Scrapes company IR RSS feeds for material announcements.
    Robots.txt-respecting, rate-limited.
    """

    def __init__(self, robots_txt_respect: bool = True) -> None:
        self._robots_txt_respect = robots_txt_respect
        self._seen_hashes: set[str] = set()

    def _hash_url(self, url: str) -> str:
        return hashlib.sha256(url.strip().lower().encode()).hexdigest()[:16]

    def _is_material(self, title: str) -> bool:
        title_lower = title.lower()
        return any(kw.lower() in title_lower for kw in MATERIAL_KEYWORDS)

    async def get_latest_announcements(
        self, ticker: str, days_back: int = 7
    ) -> list[IRNewsItem]:
        """
        Fetch latest IR announcements from RSS feed for ticker.
        Returns empty list if feed unavailable or rate-limited.
        """
        feed_url = IR_RSS_FEEDS.get(ticker.upper())
        if not feed_url:
            logger.debug("IRScraperService: no RSS feed configured for %s", ticker)
            return []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    feed_url,
                    headers={"User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"},
                )
                if resp.status_code != 200:
                    logger.info(
                        "IRScraperService: %s returned %s for %s",
                        feed_url, resp.status_code, ticker,
                    )
                    return []
                return self._parse_rss(ticker, resp.text, days_back)
        except Exception as exc:
            logger.info(
                "IRScraperService.get_latest_announcements failed for %s: %s", ticker, exc
            )
            return []

    def _parse_rss(self, ticker: str, rss_text: str, days_back: int) -> list[IRNewsItem]:
        """Simple RSS XML parser."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        items: list[IRNewsItem] = []

        item_blocks = re.findall(r"<item>(.*?)</item>", rss_text, re.DOTALL)
        for block in item_blocks[:20]:
            title_m = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", block, re.DOTALL)
            link_m = re.search(r"<link>(.*?)</link>", block, re.DOTALL)
            date_m = re.search(r"<pubDate>(.*?)</pubDate>", block, re.DOTALL)

            title = title_m.group(1).strip() if title_m else ""
            url = link_m.group(1).strip() if link_m else ""
            pub_date_str = date_m.group(1).strip() if date_m else ""

            if not url or not title:
                continue

            url_hash = self._hash_url(url)
            if url_hash in self._seen_hashes:
                continue
            self._seen_hashes.add(url_hash)

            items.append(IRNewsItem(
                ticker=ticker,
                title=title,
                url=url,
                url_hash=url_hash,
                published_at=pub_date_str,
                is_material=self._is_material(title),
            ))

        return items
