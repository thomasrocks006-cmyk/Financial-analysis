"""
ASXAnnouncementService — ASX public announcements API.
No authentication required. Free public access.
AU ticker parity equivalent to SEC API for US tickers.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

PERIODIC_CATEGORIES = {
    "Periodic Reports", "Annual Report to shareholders",
    "Half Yearly Report", "Quarterly Activities Report",
    "Quarterly Cash Flow Report",
}
MATERIAL_CATEGORIES = {
    "Change of Activities", "Material Contracts", "Material Price Sensitive",
    "Market Update", "Strategy Update", "Acquisition", "Divestiture",
}


class ASXAnnouncement(BaseModel):
    ticker: str
    document_date: str
    headline: str
    category: str
    url: str = ""
    is_periodic: bool = False
    is_material: bool = False

    def to_prompt_line(self) -> str:
        tag = "PERIODIC" if self.is_periodic else ("MATERIAL" if self.is_material else "OTHER")
        return f"[ASX/{self.ticker}][{tag}] {self.headline} ({self.document_date[:10]})"


def _is_asx_ticker(ticker: str) -> bool:
    """Identify ASX-listed tickers (suffix .AX or 2-3 uppercase chars)."""
    return ticker.endswith(".AX") or (1 < len(ticker) <= 3 and ticker.isupper())


class ASXAnnouncementService:
    """
    ASX public announcements API at asx.com.au.
    Equivalent role to SEC API for AU-listed tickers.
    """
    BASE_URL = "https://www.asx.com.au/asx/1/company/{ticker}/announcements"

    def _normalize_ticker(self, ticker: str) -> str:
        return ticker.replace(".AX", "").upper()

    async def get_recent_announcements(
        self, asx_ticker: str, days_back: int = 30
    ) -> list[ASXAnnouncement]:
        """Recent ASX company announcements."""
        clean_ticker = self._normalize_ticker(asx_ticker)
        try:
            url = self.BASE_URL.format(ticker=clean_ticker)
            params = {"count": 20, "market_sensitive": "false"}
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    logger.warning(
                        "ASX API %s for %s status %s", url, clean_ticker, resp.status_code
                    )
                    return []
                data = resp.json()
            return self._parse_announcements(clean_ticker, data, days_back)
        except Exception as exc:
            logger.warning(
                "ASXAnnouncementService.get_recent_announcements failed for %s: %s",
                clean_ticker,
                exc,
            )
            return []

    def _parse_announcements(
        self, ticker: str, data: dict, days_back: int
    ) -> list[ASXAnnouncement]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        results = []
        for item in data.get("data", []):
            doc_date_str = item.get("document_date", "")
            try:
                doc_date = datetime.fromisoformat(doc_date_str.replace("Z", "+00:00"))
                if doc_date < cutoff:
                    continue
            except Exception:
                pass

            category = item.get("document_type", "")
            headline = item.get("headline", item.get("documentType", category))

            ann = ASXAnnouncement(
                ticker=ticker,
                document_date=doc_date_str,
                headline=headline,
                category=category,
                url=item.get("url", ""),
                is_periodic=category in PERIODIC_CATEGORIES,
                is_material=category in MATERIAL_CATEGORIES,
            )
            results.append(ann)
        return results

    async def get_periodic_reports(self, asx_ticker: str) -> list[ASXAnnouncement]:
        anns = await self.get_recent_announcements(asx_ticker, days_back=365)
        return [a for a in anns if a.is_periodic]

    async def get_material_events(
        self, asx_ticker: str, days_back: int = 30
    ) -> list[ASXAnnouncement]:
        anns = await self.get_recent_announcements(asx_ticker, days_back=days_back)
        return [a for a in anns if a.is_material]
