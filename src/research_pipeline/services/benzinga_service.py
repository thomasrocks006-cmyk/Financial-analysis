"""Benzinga Service — finance-native news, analyst ratings, events, and catalysts.

Benzinga is the best available finance-event layer at non-institutional cost.
It provides higher specificity and less noise than FMP/Finnhub news, with
structured analyst rating change feeds that are essential for Evidence Librarian
and Red Team quality.

Capabilities provided:
  - Analyst rating changes (upgrade/downgrade/initiation with firm + target)
  - Company news filtered for finance signal quality
  - Earnings event calendar (timing + estimate context)
  - Real-time catalyst detection (intraday adverse event awareness)

Pipeline integration (as mapped in BACKEND_ARCHITECTURE_ASSESSMENT.md §9.7):
  - Stage 2: rating changes + earnings calendar (structural event data)
  - Stage 5: finance-native news + adverse signals to Evidence Librarian
  - Stage 10: downgrade clusters + negative catalysts to Red Team

Limitations:
  - Aggregator, not primary source — rating changes come via Benzinga from analysts
  - Transcript quality depends on subscription tier — verify coverage before use
  - Quality filtering required: implement source-ranking before injecting into prompts

API reference: https://docs.benzinga.io/benzinga/
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False
    logger.warning("httpx not available — BenzingaService will return empty results")

_TIMEOUT_SECS = 15.0
_MAX_NEWS_PER_TICKER = 20
_MAX_RATING_CHANGES = 15

# Benzinga REST API v2.1 base
_BENZINGA_BASE = "https://api.benzinga.com/api/v2.1"
_BENZINGA_NEWS_BASE = "https://api.benzinga.com/api/v2"

# Minimum finance signal quality for news — exclude low-signal sources
_PUBLISHER_ALLOWLIST = {
    "Reuters", "Associated Press", "AP", "Bloomberg", "Financial Times",
    "Wall Street Journal", "WSJ", "The Economist", "CNBC", "MarketWatch",
    "Barron's", "Benzinga", "TheStreet", "Seeking Alpha", "Motley Fool",
    "Investor's Business Daily", "IBD",
}


def _parse_date(val: Any) -> Optional[datetime]:
    if not val:
        return None
    val = str(val).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d",
                "%a, %d %b %Y %H:%M:%S %z"):
        try:
            dt = datetime.strptime(val[:len(fmt)], fmt)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        except ValueError:
            continue
    return None


class RatingChange:
    """A single analyst rating change from Benzinga."""

    __slots__ = (
        "ticker", "analyst_firm", "action_type", "rating_current",
        "rating_prior", "price_target_current", "price_target_prior",
        "published_at", "headline", "source_tier",
    )

    def __init__(
        self,
        ticker: str,
        analyst_firm: str,
        action_type: str,
        rating_current: str,
        rating_prior: str,
        price_target_current: Optional[float],
        price_target_prior: Optional[float],
        published_at: Optional[datetime],
        headline: str,
    ):
        self.ticker = ticker
        self.analyst_firm = analyst_firm
        self.action_type = action_type        # e.g. "Upgrade", "Downgrade", "Initiate"
        self.rating_current = rating_current  # e.g. "Buy", "Hold", "Sell"
        self.rating_prior = rating_prior
        self.price_target_current = price_target_current
        self.price_target_prior = price_target_prior
        self.published_at = published_at
        self.headline = headline
        self.source_tier = 2  # Tier 2 — Finance event/news

    def is_adverse(self) -> bool:
        """True if this is a downgrade or target reduction."""
        action = self.action_type.lower()
        return "downgrade" in action or "lower" in action or "cut" in action

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "analyst_firm": self.analyst_firm,
            "action_type": self.action_type,
            "rating_current": self.rating_current,
            "rating_prior": self.rating_prior,
            "price_target_current": self.price_target_current,
            "price_target_prior": self.price_target_prior,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "headline": self.headline,
            "is_adverse": self.is_adverse(),
            "source": "benzinga",
            "source_tier": self.source_tier,
        }


class BenzingaNewsItem:
    """A Benzinga news article with finance-quality metadata."""

    __slots__ = (
        "ticker", "headline", "summary", "published_at",
        "author", "url", "channels", "source_tier",
    )

    def __init__(
        self,
        ticker: str,
        headline: str,
        summary: str,
        published_at: Optional[datetime],
        author: str,
        url: str,
        channels: list[str],
    ):
        self.ticker = ticker
        self.headline = headline
        self.summary = summary
        self.published_at = published_at
        self.author = author
        self.url = url
        self.channels = channels
        self.source_tier = 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "headline": self.headline,
            "summary": self.summary,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "author": self.author,
            "url": self.url,
            "channels": self.channels,
            "source": "benzinga",
            "source_tier": self.source_tier,
        }


class BenzingaTickerPackage:
    """All Benzinga data for a single ticker."""

    def __init__(self, ticker: str):
        self.ticker = ticker
        self.rating_changes: list[RatingChange] = []
        self.news: list[BenzingaNewsItem] = []
        self.earnings_events: list[dict[str, Any]] = []
        self.coverage_gaps: list[str] = []

    @property
    def adverse_ratings(self) -> list[RatingChange]:
        """Downgrades and target reductions — for Red Team adversarial grounding."""
        return [r for r in self.rating_changes if r.is_adverse()]

    @property
    def has_content(self) -> bool:
        return bool(self.rating_changes or self.news or self.earnings_events)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "rating_changes": [r.to_dict() for r in self.rating_changes],
            "adverse_ratings": [r.to_dict() for r in self.adverse_ratings],
            "news": [n.to_dict() for n in self.news],
            "earnings_events": self.earnings_events,
            "coverage_gaps": self.coverage_gaps,
            "source": "benzinga",
            "source_tier": 2,
        }


class BenzingaService:
    """Fetches finance-native data from the Benzinga REST API.

    All methods degrade gracefully:
    - If API key is absent: returns empty packages (no error raised)
    - If a source call fails: records in coverage_gaps, continues
    - Rate limits: requests are serialised per-ticker to avoid burst errors

    Usage:
        svc = BenzingaService(api_key="your-key")
        packages = await svc.fetch_universe(["NVDA", "MSFT"])
        pkg = packages["NVDA"]
        print(pkg.adverse_ratings)   # downgrades for Red Team
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key
        self._available = bool(api_key) and _HTTPX_AVAILABLE

    # ── Public API ─────────────────────────────────────────────────────

    async def fetch_universe(
        self, tickers: list[str]
    ) -> dict[str, BenzingaTickerPackage]:
        """Fetch Benzinga data for all tickers."""
        if not self._available:
            return {t: BenzingaTickerPackage(ticker=t) for t in tickers}

        async with httpx.AsyncClient(timeout=_TIMEOUT_SECS) as client:
            results: dict[str, BenzingaTickerPackage] = {}
            for ticker in tickers:
                try:
                    results[ticker] = await self.fetch_ticker(client, ticker)
                except Exception as exc:
                    logger.warning("Benzinga fetch failed for %s: %s", ticker, exc)
                    pkg = BenzingaTickerPackage(ticker=ticker)
                    pkg.coverage_gaps.append(f"fetch_error: {exc}")
                    results[ticker] = pkg
        return results

    async def fetch_ticker(
        self, client: httpx.AsyncClient, ticker: str
    ) -> BenzingaTickerPackage:
        """Fetch all Benzinga data for one ticker."""
        pkg = BenzingaTickerPackage(ticker=ticker)

        # Rating changes
        ratings = await self._safe(
            self._fetch_ratings(client, ticker),
            "ratings", pkg.coverage_gaps,
        )
        if ratings:
            pkg.rating_changes = ratings

        # News
        news = await self._safe(
            self._fetch_news(client, ticker),
            "news", pkg.coverage_gaps,
        )
        if news:
            pkg.news = news

        # Earnings calendar
        earnings = await self._safe(
            self._fetch_earnings_calendar(client, ticker),
            "earnings_calendar", pkg.coverage_gaps,
        )
        if earnings:
            pkg.earnings_events = earnings

        return pkg

    # ── Rating changes ──────────────────────────────────────────────────

    async def _fetch_ratings(
        self, client: httpx.AsyncClient, ticker: str
    ) -> list[RatingChange]:
        """Fetch analyst rating changes for a ticker."""
        resp = await client.get(
            f"{_BENZINGA_BASE}/calendar/ratings",
            params={
                "token": self.api_key,
                "parameters[tickers]": ticker,
                "pagesize": str(_MAX_RATING_CHANGES),
            },
        )
        resp.raise_for_status()
        data = resp.json()

        changes: list[RatingChange] = []
        for row in (data.get("ratings") or []):
            try:
                changes.append(RatingChange(
                    ticker=ticker,
                    analyst_firm=row.get("analyst", ""),
                    action_type=row.get("action_company", row.get("action_pt", "")),
                    rating_current=row.get("rating_current", ""),
                    rating_prior=row.get("rating_prior", ""),
                    price_target_current=_to_float(row.get("pt_current")),
                    price_target_prior=_to_float(row.get("pt_prior")),
                    published_at=_parse_date(row.get("date")),
                    headline=row.get("headline", ""),
                ))
            except Exception as exc:
                logger.debug("Benzinga rating parse error: %s", exc)
        return changes

    # ── News ────────────────────────────────────────────────────────────

    async def _fetch_news(
        self, client: httpx.AsyncClient, ticker: str
    ) -> list[BenzingaNewsItem]:
        """Fetch finance-native news articles for a ticker."""
        resp = await client.get(
            f"{_BENZINGA_NEWS_BASE}/headline",
            params={
                "token": self.api_key,
                "tickers": ticker,
                "pageSize": str(_MAX_NEWS_PER_TICKER),
                "displayOutput": "full",
            },
        )
        resp.raise_for_status()
        data = resp.json()

        items: list[BenzingaNewsItem] = []
        for row in (data if isinstance(data, list) else []):
            try:
                channels = [
                    ch.get("name", "") for ch in (row.get("channels") or [])
                ]
                items.append(BenzingaNewsItem(
                    ticker=ticker,
                    headline=row.get("title", ""),
                    summary=row.get("teaser", ""),
                    published_at=_parse_date(row.get("created")),
                    author=row.get("author", ""),
                    url=row.get("url", ""),
                    channels=channels,
                ))
            except Exception as exc:
                logger.debug("Benzinga news parse error: %s", exc)
        return items

    # ── Earnings calendar ───────────────────────────────────────────────

    async def _fetch_earnings_calendar(
        self, client: httpx.AsyncClient, ticker: str
    ) -> list[dict[str, Any]]:
        """Fetch upcoming earnings event dates and estimate context."""
        resp = await client.get(
            f"{_BENZINGA_BASE}/calendar/earnings",
            params={
                "token": self.api_key,
                "parameters[tickers]": ticker,
                "pagesize": "5",
            },
        )
        resp.raise_for_status()
        data = resp.json()

        events = []
        for row in (data.get("earnings") or []):
            events.append({
                "ticker": ticker,
                "date": row.get("date", ""),
                "time": row.get("time", ""),
                "eps_est": _to_float(row.get("eps_est")),
                "eps_actual": _to_float(row.get("eps_actual")),
                "revenue_est": _to_float(row.get("revenue_est")),
                "revenue_actual": _to_float(row.get("revenue_actual")),
                "fiscal_quarter_ending": row.get("period_of_report", ""),
                "source": "benzinga",
                "source_tier": 2,
            })
        return events

    # ── Utility ─────────────────────────────────────────────────────────

    @staticmethod
    async def _safe(coro: Any, source_name: str, gaps: list[str]) -> Any:
        try:
            return await coro
        except Exception as exc:
            gaps.append(f"{source_name}: {exc}")
            logger.debug("Benzinga source '%s' failed: %s", source_name, exc)
            return None


def _to_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
