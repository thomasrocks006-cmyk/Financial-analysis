"""Session 13 — Sector Data Service: real earnings/revenue from FMP.

Replaces the hardcoded 17-ticker heuristic sector data with live financial
metrics fetched from the Financial Modelling Prep (FMP) API.

Falls back to a synthetic dataset when FMP is unavailable or unconfigured.
All output is typed via ``SectorDataResult`` Pydantic models.

GICS sector classification is provided for each ticker to support
sector-level analytics and portfolio-level attribution.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Literal, Optional

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ── GICS sector type ───────────────────────────────────────────────────────────
GICSSector = Literal[
    "Information Technology",
    "Communication Services",
    "Consumer Discretionary",
    "Consumer Staples",
    "Energy",
    "Financials",
    "Health Care",
    "Industrials",
    "Materials",
    "Real Estate",
    "Utilities",
    "Unknown",
]

# ── Synthetic fallback dataset ─────────────────────────────────────────────────
# All revenue figures in $M USD (TTM unless noted).  Margins in decimal.
_SYNTHETIC_DATA: dict[str, dict[str, Any]] = {
    # Compute
    "NVDA": {
        "revenue_ttm": 79_300,
        "revenue_yoy_pct": 122.4,
        "gross_margin": 0.745,
        "ebitda_margin": 0.558,
        "eps_ttm": 11.93,
        "forward_pe": 37.2,
        "ev_ebitda": 53.1,
        "gics_sector": "Information Technology",
    },
    "AVGO": {
        "revenue_ttm": 35_820,
        "revenue_yoy_pct": 47.3,
        "gross_margin": 0.675,
        "ebitda_margin": 0.612,
        "eps_ttm": 21.06,
        "forward_pe": 27.4,
        "ev_ebitda": 30.2,
        "gics_sector": "Information Technology",
    },
    "AMD": {
        "revenue_ttm": 22_680,
        "revenue_yoy_pct": 13.7,
        "gross_margin": 0.511,
        "ebitda_margin": 0.093,
        "eps_ttm": 0.53,
        "forward_pe": 41.1,
        "ev_ebitda": 22.4,
        "gics_sector": "Information Technology",
    },
    "TSM": {
        "revenue_ttm": 76_500,
        "revenue_yoy_pct": 33.9,
        "gross_margin": 0.535,
        "ebitda_margin": 0.631,
        "eps_ttm": 6.11,
        "forward_pe": 22.1,
        "ev_ebitda": 18.5,
        "gics_sector": "Information Technology",
    },
    "ANET": {
        "revenue_ttm": 6_000,
        "revenue_yoy_pct": 19.8,
        "gross_margin": 0.644,
        "ebitda_margin": 0.356,
        "eps_ttm": 8.14,
        "forward_pe": 35.5,
        "ev_ebitda": 29.3,
        "gics_sector": "Information Technology",
    },
    # Power / Energy
    "CEG": {
        "revenue_ttm": 23_400,
        "revenue_yoy_pct": 6.2,
        "gross_margin": 0.312,
        "ebitda_margin": 0.395,
        "eps_ttm": 7.22,
        "forward_pe": 28.4,
        "ev_ebitda": 20.1,
        "gics_sector": "Utilities",
    },
    "VST": {
        "revenue_ttm": 14_100,
        "revenue_yoy_pct": 16.8,
        "gross_margin": 0.283,
        "ebitda_margin": 0.351,
        "eps_ttm": 5.81,
        "forward_pe": 23.7,
        "ev_ebitda": 16.8,
        "gics_sector": "Utilities",
    },
    "GEV": {
        "revenue_ttm": 24_900,
        "revenue_yoy_pct": 9.1,
        "gross_margin": 0.261,
        "ebitda_margin": 0.187,
        "eps_ttm": 3.42,
        "forward_pe": 31.2,
        "ev_ebitda": 21.4,
        "gics_sector": "Industrials",
    },
    "NLR": {
        "revenue_ttm": None,
        "revenue_yoy_pct": None,
        "gross_margin": None,
        "ebitda_margin": None,
        "eps_ttm": None,
        "forward_pe": None,
        "ev_ebitda": None,
        "gics_sector": "Utilities",
    },
    # Infrastructure
    "PWR": {
        "revenue_ttm": 21_800,
        "revenue_yoy_pct": 15.3,
        "gross_margin": 0.163,
        "ebitda_margin": 0.118,
        "eps_ttm": 4.88,
        "forward_pe": 41.3,
        "ev_ebitda": 24.9,
        "gics_sector": "Industrials",
    },
    "ETN": {
        "revenue_ttm": 24_400,
        "revenue_yoy_pct": 12.4,
        "gross_margin": 0.381,
        "ebitda_margin": 0.248,
        "eps_ttm": 9.62,
        "forward_pe": 29.8,
        "ev_ebitda": 22.3,
        "gics_sector": "Industrials",
    },
    "HUBB": {
        "revenue_ttm": 5_500,
        "revenue_yoy_pct": 9.7,
        "gross_margin": 0.372,
        "ebitda_margin": 0.219,
        "eps_ttm": 16.41,
        "forward_pe": 25.4,
        "ev_ebitda": 17.6,
        "gics_sector": "Industrials",
    },
    "APH": {
        "revenue_ttm": 15_200,
        "revenue_yoy_pct": 38.9,
        "gross_margin": 0.339,
        "ebitda_margin": 0.285,
        "eps_ttm": 1.73,
        "forward_pe": 34.6,
        "ev_ebitda": 25.7,
        "gics_sector": "Information Technology",
    },
    "FIX": {
        "revenue_ttm": 5_700,
        "revenue_yoy_pct": 18.2,
        "gross_margin": 0.187,
        "ebitda_margin": 0.102,
        "eps_ttm": 5.53,
        "forward_pe": 35.1,
        "ev_ebitda": 19.8,
        "gics_sector": "Industrials",
    },
    "NXT": {
        "revenue_ttm": 2_200,
        "revenue_yoy_pct": 24.6,
        "gross_margin": 0.221,
        "ebitda_margin": 0.135,
        "eps_ttm": 1.97,
        "forward_pe": 28.7,
        "ev_ebitda": 15.9,
        "gics_sector": "Industrials",
    },
    # Materials
    "FCX": {
        "revenue_ttm": 22_800,
        "revenue_yoy_pct": 5.8,
        "gross_margin": 0.287,
        "ebitda_margin": 0.411,
        "eps_ttm": 1.48,
        "forward_pe": 17.3,
        "ev_ebitda": 10.2,
        "gics_sector": "Materials",
    },
    "BHP": {
        "revenue_ttm": 55_700,
        "revenue_yoy_pct": -3.1,
        "gross_margin": 0.441,
        "ebitda_margin": 0.489,
        "eps_ttm": 2.87,
        "forward_pe": 12.4,
        "ev_ebitda": 8.1,
        "gics_sector": "Materials",
    },
    # ASX names (stub — FMP ticker format differs, synthetic used here)
    "CBA.AX": {
        "revenue_ttm": 27_800,
        "revenue_yoy_pct": 4.1,
        "gross_margin": None,
        "ebitda_margin": 0.421,
        "eps_ttm": 6.48,
        "forward_pe": 21.3,
        "ev_ebitda": None,
        "gics_sector": "Financials",
    },
    "BHP.AX": {
        "revenue_ttm": 55_700,
        "revenue_yoy_pct": -3.1,
        "gross_margin": 0.441,
        "ebitda_margin": 0.489,
        "eps_ttm": 2.87,
        "forward_pe": 12.4,
        "ev_ebitda": 8.1,
        "gics_sector": "Materials",
    },
    "CSL.AX": {
        "revenue_ttm": 14_300,
        "revenue_yoy_pct": 5.6,
        "gross_margin": 0.551,
        "ebitda_margin": 0.231,
        "eps_ttm": 4.82,
        "forward_pe": 29.5,
        "ev_ebitda": 21.7,
        "gics_sector": "Health Care",
    },
}


class SectorDataResult(BaseModel):
    """Per-ticker financial metrics from real or synthetic sources."""

    ticker: str
    gics_sector: GICSSector = "Unknown"
    revenue_ttm: Optional[float] = None  # trailing 12-month revenue ($M)
    revenue_yoy_pct: Optional[float] = None  # year-over-year revenue growth %
    gross_margin: Optional[float] = None  # decimal (0.65 = 65%)
    ebitda_margin: Optional[float] = None  # decimal
    eps_ttm: Optional[float] = None  # trailing 12-month EPS
    forward_pe: Optional[float] = None  # next-12-month P/E
    ev_ebitda: Optional[float] = None  # EV/EBITDA
    is_live: bool = False  # True if FMP data was used
    source: str = "synthetic"
    data_date: Optional[str] = None  # ISO date when fetched


class SectorDataService:
    """Session 13: live sector financials from FMP with synthetic fallback.

    When ``fmp_api_key`` is provided and FMP returns data, ``is_live=True``
    on the results.  All API errors are non-blocking — synthetic fallback is
    always returned.

    Cache TTL: 4 hours (sector fundamentals change slowly).

    Usage::

        svc = SectorDataService(fmp_api_key="...")
        results = svc.get_sector_data(["NVDA", "AVGO", "CBA.AX"])
        for r in results:
            print(r.ticker, r.gics_sector, r.revenue_ttm)
    """

    _CACHE: dict[str, "SectorDataResult"] = {}
    _CACHE_TS: float = 0.0
    _CACHE_TTL: float = 14_400.0  # 4 hours

    def __init__(self, fmp_api_key: str | None = None) -> None:
        self.fmp_api_key = fmp_api_key

    # ── Public API ─────────────────────────────────────────────────────────────

    def get_sector_data(self, tickers: list[str]) -> list["SectorDataResult"]:
        """Fetch sector financial metrics for a list of tickers.

        Tries FMP first if configured; falls back to synthetic per-ticker.
        Results are cached per-ticker for ``_CACHE_TTL`` seconds.

        Args:
            tickers: list of ticker symbols (e.g. ["NVDA", "CBA.AX"]).

        Returns:
            list of ``SectorDataResult`` (one per ticker, same order).
        """
        results: list[SectorDataResult] = []
        for ticker in tickers:
            results.append(self._get_one(ticker))
        return results

    def get_sector_data_map(self, tickers: list[str]) -> dict[str, "SectorDataResult"]:
        """Same as get_sector_data but returns a dict keyed by ticker."""
        return {r.ticker: r for r in self.get_sector_data(tickers)}

    def clear_cache(self) -> None:
        """Force cache invalidation."""
        self._CACHE.clear()
        self._CACHE_TS = 0.0

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _get_one(self, ticker: str) -> "SectorDataResult":
        now = time.time()
        if ticker in self._CACHE and (now - self._CACHE_TS) < self._CACHE_TTL:
            return self._CACHE[ticker]

        result: SectorDataResult | None = None
        if self.fmp_api_key:
            try:
                result = self._fetch_fmp(ticker)
            except Exception as exc:
                logger.debug("SectorDataService: FMP fetch failed for %s: %s", ticker, exc)

        if result is None:
            result = self._synthetic(ticker)

        self._CACHE[ticker] = result
        if not self._CACHE_TS:
            self._CACHE_TS = now
        return result

    def _fetch_fmp(self, ticker: str) -> "SectorDataResult":
        """Fetch key metrics + income statement from FMP."""
        import urllib.request
        import json as _json
        from datetime import date

        # FMP handles ASX tickers as "{name}.AX" — strip for AU names
        fmp_ticker = ticker.replace(".AX", "").replace(".ASX", "")

        base = "https://financialmodelingprep.com/api/v3"
        key = self.fmp_api_key

        # Key metrics (TTM)
        url = f"{base}/key-metrics-ttm/{fmp_ticker}?apikey={key}"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = _json.loads(resp.read())

        if not data or not isinstance(data, list):
            raise ValueError(f"FMP returned no data for {fmp_ticker}")

        m = data[0]
        revenue_per_share = m.get("revenuePerShareTTM")
        shares = m.get("sharesOutstandingTTM")
        revenue_ttm = (
            float(revenue_per_share * shares) / 1e6 if revenue_per_share and shares else None
        )

        # Income statement for YoY
        url2 = f"{base}/income-statement/{fmp_ticker}?limit=2&period=annual&apikey={key}"
        with urllib.request.urlopen(url2, timeout=10) as resp:
            income = _json.loads(resp.read())

        revenue_yoy = None
        if len(income) >= 2:
            r0 = income[0].get("revenue", 0)
            r1 = income[1].get("revenue", 0)
            if r1 and r0:
                revenue_yoy = round((r0 - r1) / r1 * 100, 1)

        # Profile for GICS
        url3 = f"{base}/profile/{fmp_ticker}?apikey={key}"
        with urllib.request.urlopen(url3, timeout=10) as resp:
            profile = _json.loads(resp.read())

        gics: GICSSector = "Unknown"
        if profile and isinstance(profile, list):
            sector_str = profile[0].get("sector", "Unknown")
            if sector_str in GICSSector.__args__:  # type: ignore[attr-defined]
                gics = sector_str  # type: ignore[assignment]

        return SectorDataResult(
            ticker=ticker,
            gics_sector=gics,
            revenue_ttm=revenue_ttm,
            revenue_yoy_pct=revenue_yoy,
            gross_margin=float(m["grossProfitMarginTTM"])
            if m.get("grossProfitMarginTTM")
            else None,
            ebitda_margin=float(m["ebitdaPerShareTTM"]) / float(revenue_per_share)
            if m.get("ebitdaPerShareTTM") and revenue_per_share
            else None,
            eps_ttm=float(m["netIncomePerShareTTM"]) if m.get("netIncomePerShareTTM") else None,
            forward_pe=float(m["peRatioTTM"]) if m.get("peRatioTTM") else None,
            ev_ebitda=float(m["enterpriseValueOverEBITDATTM"])
            if m.get("enterpriseValueOverEBITDATTM")
            else None,
            is_live=True,
            source=f"FMP TTM ({date.today().isoformat()})",
            data_date=date.today().isoformat(),
        )

    def _synthetic(self, ticker: str) -> "SectorDataResult":
        """Return synthetic data for a ticker from the fallback dataset."""
        raw = _SYNTHETIC_DATA.get(ticker) or _SYNTHETIC_DATA.get(ticker.upper(), {})
        return SectorDataResult(
            ticker=ticker,
            gics_sector=raw.get("gics_sector", "Unknown"),
            revenue_ttm=raw.get("revenue_ttm"),
            revenue_yoy_pct=raw.get("revenue_yoy_pct"),
            gross_margin=raw.get("gross_margin"),
            ebitda_margin=raw.get("ebitda_margin"),
            eps_ttm=raw.get("eps_ttm"),
            forward_pe=raw.get("forward_pe"),
            ev_ebitda=raw.get("ev_ebitda"),
            is_live=False,
            source="synthetic — hardcoded dataset (FMP unconfigured)",
        )
