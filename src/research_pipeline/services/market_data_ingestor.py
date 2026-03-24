"""A1 — Market Data Ingestor: FMP + Finnhub ingestion into canonical tables."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from research_pipeline.schemas.market_data import (
    AnalystEstimate,
    ConsensusSnapshot,
    EarningsEvent,
    MarketSnapshot,
    RatingsSnapshot,
)

logger = logging.getLogger(__name__)


class MarketDataIngestor:
    """Ingest market data from FMP and Finnhub into canonical schemas.

    Deterministic service — no LLM calls.  Handles:
    - fetch_quotes / ratios / estimates / price_targets / recommendations / earnings_calendar
    - stale data detection
    - retry logic
    - request budget tracking
    """

    def __init__(self, fmp_key: str, finnhub_key: str, max_retries: int = 3):
        self.fmp_key = fmp_key
        self.finnhub_key = finnhub_key
        self.max_retries = max_retries
        self._fmp_base = "https://financialmodelingprep.com/api/v3"
        self._finnhub_base = "https://finnhub.io/api/v1"
        self._request_count = 0

    # ── helpers ─────────────────────────────────────────────────────────
    async def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        params = params or {}
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(url, params=params)
                    resp.raise_for_status()
                    self._request_count += 1
                    return resp.json()
            except (httpx.HTTPStatusError, httpx.ReadTimeout) as exc:
                logger.warning("Attempt %d failed for %s: %s", attempt, url, exc)
                if attempt == self.max_retries:
                    raise
        return None

    # ── FMP endpoints ──────────────────────────────────────────────────
    async def fetch_fmp_quote(self, ticker: str) -> MarketSnapshot:
        data = await self._get(
            f"{self._fmp_base}/quote/{ticker}", {"apikey": self.fmp_key}
        )
        row = data[0] if data else {}
        return MarketSnapshot(
            ticker=ticker,
            source="fmp",
            price=row.get("price"),
            market_cap=row.get("marketCap"),
            ev=row.get("enterpriseValue"),
            trailing_pe=row.get("pe"),
            forward_pe=row.get("forwardPE"),
            ev_to_ebitda=row.get("evToEbitda"),
            dividend_yield=row.get("dividendYield"),
        )

    async def fetch_fmp_ratios(self, ticker: str) -> dict[str, Any]:
        data = await self._get(
            f"{self._fmp_base}/ratios/{ticker}", {"apikey": self.fmp_key, "limit": 1}
        )
        return data[0] if data else {}

    async def fetch_fmp_analyst_estimates(self, ticker: str) -> list[AnalystEstimate]:
        data = await self._get(
            f"{self._fmp_base}/analyst-estimates/{ticker}",
            {"apikey": self.fmp_key, "limit": 4},
        )
        results = []
        for row in (data or []):
            results.append(AnalystEstimate(
                ticker=ticker,
                period=row.get("date", "unknown"),
                source="fmp",
                eps_estimate=row.get("estimatedEpsAvg"),
                revenue_estimate=row.get("estimatedRevenueAvg"),
                num_analysts=row.get("numberAnalystEstimatedRevenue"),
            ))
        return results

    async def fetch_fmp_price_targets(self, ticker: str) -> ConsensusSnapshot:
        data = await self._get(
            f"{self._fmp_base}/price-target-consensus/{ticker}",
            {"apikey": self.fmp_key},
        )
        row = data[0] if isinstance(data, list) and data else (data or {})
        return ConsensusSnapshot(
            ticker=ticker,
            source="fmp",
            target_low=row.get("targetLow"),
            target_median=row.get("targetMedian"),
            target_high=row.get("targetHigh"),
            target_mean=row.get("targetConsensus"),
        )

    # ── Finnhub endpoints ──────────────────────────────────────────────
    async def fetch_finnhub_recommendation(self, ticker: str) -> RatingsSnapshot:
        data = await self._get(
            f"{self._finnhub_base}/stock/recommendation",
            {"symbol": ticker, "token": self.finnhub_key},
        )
        row = data[0] if data else {}
        total = sum([
            row.get("strongBuy", 0), row.get("buy", 0),
            row.get("hold", 0), row.get("sell", 0), row.get("strongSell", 0),
        ]) or 1
        return RatingsSnapshot(
            ticker=ticker,
            source="finnhub",
            buy_pct=round((row.get("strongBuy", 0) + row.get("buy", 0)) / total * 100, 1),
            hold_pct=round(row.get("hold", 0) / total * 100, 1),
            sell_pct=round((row.get("sell", 0) + row.get("strongSell", 0)) / total * 100, 1),
        )

    async def fetch_finnhub_price_target(self, ticker: str) -> ConsensusSnapshot:
        data = await self._get(
            f"{self._finnhub_base}/stock/price-target",
            {"symbol": ticker, "token": self.finnhub_key},
        )
        data = data or {}
        return ConsensusSnapshot(
            ticker=ticker,
            source="finnhub",
            target_low=data.get("targetLow"),
            target_median=data.get("targetMedian"),
            target_high=data.get("targetHigh"),
            target_mean=data.get("targetMean"),
            num_analysts=data.get("lastUpdated"),
        )

    async def fetch_finnhub_earnings_calendar(
        self, from_date: str, to_date: str
    ) -> list[EarningsEvent]:
        data = await self._get(
            f"{self._finnhub_base}/calendar/earnings",
            {"from": from_date, "to": to_date, "token": self.finnhub_key},
        )
        results = []
        for row in (data or {}).get("earningsCalendar", []):
            results.append(EarningsEvent(
                ticker=row.get("symbol", ""),
                date=datetime.fromisoformat(row.get("date", "2000-01-01")),
                eps_estimate=row.get("epsEstimate"),
                eps_actual=row.get("epsActual"),
                surprise_pct=row.get("surprisePercent"),
                source="finnhub",
            ))
        return results

    # ── Full ingest for a ticker ───────────────────────────────────────
    async def ingest_ticker(self, ticker: str) -> dict[str, Any]:
        """Run full ingest for a single ticker. Returns all raw snapshots."""
        now = datetime.now(timezone.utc)
        fmp_quote = await self.fetch_fmp_quote(ticker)
        fmp_targets = await self.fetch_fmp_price_targets(ticker)
        fmp_estimates = await self.fetch_fmp_analyst_estimates(ticker)
        finnhub_rec = await self.fetch_finnhub_recommendation(ticker)
        finnhub_targets = await self.fetch_finnhub_price_target(ticker)

        return {
            "ticker": ticker,
            "timestamp": now.isoformat(),
            "fmp_quote": fmp_quote.model_dump(),
            "fmp_targets": fmp_targets.model_dump(),
            "fmp_estimates": [e.model_dump() for e in fmp_estimates],
            "finnhub_recommendation": finnhub_rec.model_dump(),
            "finnhub_targets": finnhub_targets.model_dump(),
        }

    async def ingest_universe(self, tickers: list[str]) -> list[dict[str, Any]]:
        """Ingest all tickers in the universe."""
        results = []
        for ticker in tickers:
            try:
                result = await self.ingest_ticker(ticker)
                results.append(result)
                logger.info("Ingested %s", ticker)
            except Exception as exc:
                logger.error("Failed to ingest %s: %s", ticker, exc)
                results.append({"ticker": ticker, "error": str(exc)})
        return results

    def detect_stale(self, snapshot: MarketSnapshot, max_hours: int = 24) -> bool:
        """Return True if the snapshot is older than max_hours."""
        age = (datetime.now(timezone.utc) - snapshot.timestamp.replace(tzinfo=timezone.utc))
        return age.total_seconds() > max_hours * 3600
