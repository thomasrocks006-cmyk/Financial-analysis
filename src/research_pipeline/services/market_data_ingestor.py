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
        # FMP migrated from /api/v3/ (deprecated Aug 2025) to /stable/
        self._fmp_base = "https://financialmodelingprep.com/stable"
        self._finnhub_base = "https://finnhub.io/api/v1"
        self._request_count = 0

    # ── helpers ─────────────────────────────────────────────────────────
    async def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        """GET with retry.  The AsyncClient is created ONCE per call, outside
        the retry loop, so we don't pay the TCP handshake cost on every attempt.
        """
        params = params or {}
        async with httpx.AsyncClient(timeout=30) as client:
            for attempt in range(1, self.max_retries + 1):
                try:
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
        # FMP stable endpoint uses symbol= query param, not path segment
        data = await self._get(
            f"{self._fmp_base}/quote", {"symbol": ticker, "apikey": self.fmp_key}
        )
        row = data[0] if isinstance(data, list) and data else {}
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
            f"{self._fmp_base}/ratios", {"symbol": ticker, "apikey": self.fmp_key, "limit": 1}
        )
        return data[0] if isinstance(data, list) and data else {}

    async def fetch_fmp_analyst_estimates(self, ticker: str) -> list[AnalystEstimate]:
        data = await self._get(
            f"{self._fmp_base}/analyst-estimates",
            {"symbol": ticker, "apikey": self.fmp_key, "limit": 4},
        )
        results = []
        for row in (data or []):
            if not isinstance(row, dict):
                continue
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
            f"{self._fmp_base}/price-target-consensus",
            {"symbol": ticker, "apikey": self.fmp_key},
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
    async def fetch_finnhub_quote(self, ticker: str) -> MarketSnapshot:
        """Fetch real-time quote from Finnhub (/quote endpoint).
        Fields: c=current, d=change, dp=change%, h=day_high, l=day_low,
                o=open, pc=prev_close, t=unix_timestamp.
        """
        data = await self._get(
            f"{self._finnhub_base}/quote",
            {"symbol": ticker, "token": self.finnhub_key},
        )
        data = data or {}
        return MarketSnapshot(
            ticker=ticker,
            source="finnhub",
            price=data.get("c"),       # current price
            market_cap=None,           # not provided by /quote
            ev=None,
            trailing_pe=None,
            forward_pe=None,
            ev_to_ebitda=None,
            dividend_yield=None,
        )

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
            # Bug fix: was mapping lastUpdated (a date string) to num_analysts
            num_analysts=data.get("numberAnalysts"),
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

    # ── yfinance fallback ─────────────────────────────────────────────
    async def fetch_yfinance_quote(self, ticker: str) -> MarketSnapshot:
        """Fetch a lightweight quote from yfinance.

        yfinance is a synchronous library; we wrap it in ``asyncio.to_thread``
        so it doesn't block the event loop.  Only called as a *last-resort
        fallback* when both FMP and Finnhub price fetches fail.
        """
        import asyncio  # already imported at module level in stdlib; safe repeat

        try:
            import yfinance as yf  # optional dep; gracefully handled below
        except ImportError:
            raise RuntimeError("yfinance is not installed; run: pip install yfinance")

        def _blocking_fetch() -> dict:
            yticker = yf.Ticker(ticker)
            fi = yticker.fast_info
            return {
                "price":       getattr(fi, "last_price", None),
                "market_cap":  getattr(fi, "market_cap", None),
                "trailing_pe": getattr(fi, "pe_ratio", None),
                "forward_pe":  getattr(fi, "forward_pe", None),
            }

        data = await asyncio.to_thread(_blocking_fetch)
        return MarketSnapshot(
            ticker=ticker,
            source="yfinance",
            price=data.get("price"),
            market_cap=data.get("market_cap"),
            trailing_pe=data.get("trailing_pe"),
            forward_pe=data.get("forward_pe"),
        )

    # ── Full ingest for a ticker ───────────────────────────────────────
    async def ingest_ticker(self, ticker: str) -> dict[str, Any]:
        """Run full ingest for a single ticker.

        Each source call is individually error-handled so that a 402 (FMP free
        tier limit) or a network error on one endpoint does not discard data
        from other endpoints that succeeded.

        Source hierarchy:
          1. FMP (primary — broadest fundamental data)
          2. Finnhub (free-tier fallback, good for real-time price)
          3. yfinance (last-resort — used only when both FMP and Finnhub price
             fetches fail)
        """
        now = datetime.now(timezone.utc)
        result: dict[str, Any] = {
            "ticker": ticker,
            "source": "fmp_finnhub",   # satisfies DataQA lineage check
            "timestamp": now.isoformat(),
            "errors": {},
        }

        # FMP — treated as primary but optional (free tier covers limited universe)
        for fetch_fn, key in [
            (self.fetch_fmp_quote,             "fmp_quote"),
            (self.fetch_fmp_price_targets,      "fmp_targets"),
            (self.fetch_fmp_analyst_estimates,  "fmp_estimates"),
            (self.fetch_fmp_ratios,             "fmp_ratios"),   # DSQ-13: ROE, ROIC, FCF yield, margins
        ]:
            try:
                value = await fetch_fn(ticker)
                if isinstance(value, list):
                    result[key] = [
                        e.model_dump() if hasattr(e, "model_dump") else e
                        for e in value
                    ]
                elif hasattr(value, "model_dump"):
                    result[key] = value.model_dump()
                else:
                    # Plain dict (e.g. fetch_fmp_ratios) — store as-is
                    result[key] = value
            except Exception as exc:
                code = getattr(getattr(exc, "response", None), "status_code", "ERR")
                result["errors"][key] = f"{code}: {exc}"
                logger.warning("[%s] %s failed (%s): %s", ticker, key, code, exc)

        # Finnhub — free tier covers all tickers; primary fallback for price
        for fetch_fn, key in [
            (self.fetch_finnhub_quote,          "finnhub_quote"),
            (self.fetch_finnhub_recommendation,  "finnhub_recommendation"),
            (self.fetch_finnhub_price_target,    "finnhub_targets"),
        ]:
            try:
                result[key] = (await fetch_fn(ticker)).model_dump()
            except Exception as exc:
                code = getattr(getattr(exc, "response", None), "status_code", "ERR")
                result["errors"][key] = f"{code}: {exc}"
                logger.warning("[%s] %s failed (%s): %s", ticker, key, code, exc)

        # yfinance fallback — only when both primary sources have no price
        fmp_price = (result.get("fmp_quote") or {}).get("price")
        finnhub_price = (result.get("finnhub_quote") or {}).get("price")
        if fmp_price is None and finnhub_price is None:
            logger.info("[%s] Both FMP and Finnhub price missing — trying yfinance", ticker)
            try:
                yf_snap = await self.fetch_yfinance_quote(ticker)
                result["yfinance_quote"] = yf_snap.model_dump()
                result["source"] = "yfinance"
                logger.info("[%s] yfinance fallback succeeded: price=%s", ticker, yf_snap.price)
            except Exception as exc:
                logger.warning("[%s] yfinance fallback failed: %s", ticker, exc)
                result["errors"]["yfinance_quote"] = str(exc)

        return result

    async def ingest_universe(self, tickers: list[str], max_concurrent: int = 5) -> list[dict[str, Any]]:
        """Ingest all tickers concurrently using asyncio.gather with a semaphore for rate control.

        max_concurrent limits simultaneous outbound requests to avoid hitting API rate limits.
        """
        import asyncio
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _ingest_with_sem(ticker: str) -> dict[str, Any]:
            async with semaphore:
                try:
                    result = await self.ingest_ticker(ticker)
                    logger.info("Ingested %s", ticker)
                    return result
                except Exception as exc:
                    logger.error("Failed to ingest %s: %s", ticker, exc)
                    return {"ticker": ticker, "error": str(exc)}

        results = await asyncio.gather(*(_ingest_with_sem(t) for t in tickers))
        return list(results)

    def detect_stale(self, snapshot: MarketSnapshot, max_hours: int = 24) -> bool:
        """Return True if the snapshot is older than max_hours."""
        ts = snapshot.timestamp
        # Normalise to tz-aware: if naive, assume UTC
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age = datetime.now(timezone.utc) - ts
        return age.total_seconds() > max_hours * 3600
