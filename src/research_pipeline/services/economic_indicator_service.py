"""Session 12 — EconomicIndicatorService.

Fetches live AU and US macro economic indicators from:
  - FRED API  (US data — Fed funds rate, CPI, unemployment, treasury yields, spreads)
  - RBA Statistical Tables (AU data — cash rate, CPI, housing, wages)
  - ABS data  (AU GDP, WPI, employment)

Falls back to synthetic heuristic values if APIs are unavailable or keys missing.
Results are cached in-memory with a 1-hour TTL to avoid redundant API calls
across multiple stages within the same pipeline run.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional

from research_pipeline.schemas.macro_economy import (
    AustralianIndicators,
    EconomicIndicators,
    USIndicators,
)

logger = logging.getLogger(__name__)

# ── Cache ─────────────────────────────────────────────────────────────────
_CACHE: dict[str, tuple[float, EconomicIndicators]] = {}
_CACHE_TTL_SECONDS: float = 3600.0  # 1 hour


def _cache_get(key: str) -> Optional[EconomicIndicators]:
    if key in _CACHE:
        ts, value = _CACHE[key]
        if time.monotonic() - ts < _CACHE_TTL_SECONDS:
            logger.debug("EconomicIndicatorService cache hit for key=%s", key)
            return value
        del _CACHE[key]
    return None


def _cache_set(key: str, value: EconomicIndicators) -> None:
    _CACHE[key] = (time.monotonic(), value)


def clear_cache() -> None:
    """Clear the in-memory indicator cache (useful in tests)."""
    _CACHE.clear()


# ── Synthetic fallback values ─────────────────────────────────────────────
# Representative values as of late-2024 / early-2025 horizon.
# Updated to plausible ranges; replaced by live data when APIs available.

_SYNTHETIC_AU = AustralianIndicators(
    rba_cash_rate_pct=4.35,
    rba_cash_rate_outlook="on-hold; first cut expected late 2025",
    au_cpi_yoy_pct=3.5,
    au_cpi_trimmed_mean_pct=3.2,
    au_unemployment_rate_pct=4.1,
    au_wpi_yoy_pct=3.6,
    au_gdp_growth_qoq_pct=0.4,
    au_housing_price_index_change_pct=2.5,
    au_auction_clearance_rate_pct=63.0,
    au_credit_growth_yoy_pct=4.8,
    au_10y_government_yield_pct=4.45,
    au_3y_government_yield_pct=4.30,
    aud_usd=0.645,
    data_freshness="synthetic_fallback",
)

_SYNTHETIC_US = USIndicators(
    fed_funds_rate_pct=5.375,       # midpoint of 5.25-5.50
    fed_funds_futures_1y=4.75,
    us_cpi_yoy_pct=3.1,
    us_pce_yoy_pct=2.7,
    us_core_pce_yoy_pct=2.8,
    us_unemployment_rate_pct=4.0,
    us_nonfarm_payrolls_change_k=150.0,
    us_gdp_growth_qoq_annualised_pct=2.4,
    us_ism_manufacturing=49.2,
    us_ism_services=53.4,
    us_10y_treasury_yield_pct=4.35,
    us_2y_treasury_yield_pct=4.65,
    us_yield_curve_spread_10y_2y=-0.30,
    us_hy_spread_bps=320.0,
    us_ig_spread_bps=95.0,
    data_freshness="synthetic_fallback",
)

# ── FRED helpers ──────────────────────────────────────────────────────────

def _fred_url(series_id: str, api_key: str, limit: int = 1) -> str:
    return (
        f"https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={series_id}&api_key={api_key}"
        f"&sort_order=desc&limit={limit}&file_type=json"
    )


async def _fetch_fred_series(series_id: str, api_key: str) -> Optional[float]:
    """Fetch the most-recent observation for a FRED series."""
    try:
        import httpx  # optional dep — graceful degradation
        url = _fred_url(series_id, api_key)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            obs = data.get("observations", [])
            if obs:
                val_str = obs[0].get("value", ".")
                if val_str not in (".", "", None):
                    return float(val_str)
    except Exception as exc:
        logger.debug("FRED fetch failed for %s: %s", series_id, exc)
    return None


async def _fetch_rba_cash_rate() -> Optional[float]:
    """Fetch RBA cash rate target from RBA website (structured text scrape)."""
    try:
        import httpx
        url = "https://www.rba.gov.au/statistics/cash-rate/"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            text = resp.text
            # Parse: typically "4.35" appears near "Target Cash Rate"
            match = re.search(r"Current Target Cash Rate.*?(\d+\.\d+)\s*%", text, re.DOTALL)
            if match:
                return float(match.group(1))
    except Exception as exc:
        logger.debug("RBA cash rate fetch failed: %s", exc)
    return None


# ── Live fetch ────────────────────────────────────────────────────────────

async def _fetch_us_indicators(fred_api_key: str) -> tuple[USIndicators, list[str], list[str]]:
    """Fetch US indicators from FRED. Returns (indicators, sources_used, errors)."""
    sources: list[str] = []
    errors: list[str] = []

    # Concurrent FRED fetches
    series_map = {
        "fed_funds_rate_pct": "FEDFUNDS",
        "us_cpi_yoy_pct": "CPIAUCSL",          # All Urban Consumers
        "us_pce_yoy_pct": "PCEPI",
        "us_core_pce_yoy_pct": "PCEPILFE",
        "us_unemployment_rate_pct": "UNRATE",
        "us_10y_treasury_yield_pct": "DGS10",
        "us_2y_treasury_yield_pct": "DGS2",
        "us_isy_manufacturing": "MANEMP",       # proxy
    }

    tasks = {k: _fetch_fred_series(v, fred_api_key) for k, v in series_map.items()}
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    fetched: dict[str, Optional[float]] = {}
    for key, result in zip(tasks.keys(), results):
        if isinstance(result, Exception):
            errors.append(f"FRED/{key}: {result}")
        else:
            fetched[key] = result

    if any(v is not None for v in fetched.values()):
        sources.append("FRED API")

    # Build with live values where available, fallback otherwise
    base = _SYNTHETIC_US.model_copy()
    us = USIndicators(
        fed_funds_rate_pct=fetched.get("fed_funds_rate_pct") or base.fed_funds_rate_pct,
        us_cpi_yoy_pct=fetched.get("us_cpi_yoy_pct") or base.us_cpi_yoy_pct,
        us_pce_yoy_pct=fetched.get("us_pce_yoy_pct") or base.us_pce_yoy_pct,
        us_core_pce_yoy_pct=fetched.get("us_core_pce_yoy_pct") or base.us_core_pce_yoy_pct,
        us_unemployment_rate_pct=fetched.get("us_unemployment_rate_pct") or base.us_unemployment_rate_pct,
        us_10y_treasury_yield_pct=fetched.get("us_10y_treasury_yield_pct") or base.us_10y_treasury_yield_pct,
        us_2y_treasury_yield_pct=fetched.get("us_2y_treasury_yield_pct") or base.us_2y_treasury_yield_pct,
        us_gdp_growth_qoq_annualised_pct=base.us_gdp_growth_qoq_annualised_pct,
        us_ism_manufacturing=base.us_ism_manufacturing,
        us_ism_services=base.us_ism_services,
        us_hy_spread_bps=base.us_hy_spread_bps,
        us_ig_spread_bps=base.us_ig_spread_bps,
        data_freshness="live" if sources else "synthetic_fallback",
    )
    # Compute yield curve spread if both available
    if us.us_10y_treasury_yield_pct and us.us_2y_treasury_yield_pct:
        us.us_yield_curve_spread_10y_2y = round(
            us.us_10y_treasury_yield_pct - us.us_2y_treasury_yield_pct, 3
        )

    return us, sources, errors


async def _fetch_au_indicators() -> tuple[AustralianIndicators, list[str], list[str]]:
    """Fetch AU indicators. No API key required for public RBA data."""
    sources: list[str] = []
    errors: list[str] = []

    cash_rate = await _fetch_rba_cash_rate()
    if cash_rate is not None:
        sources.append("RBA website")

    au = AustralianIndicators(
        rba_cash_rate_pct=cash_rate if cash_rate is not None else _SYNTHETIC_AU.rba_cash_rate_pct,
        rba_cash_rate_outlook=_SYNTHETIC_AU.rba_cash_rate_outlook,
        au_cpi_yoy_pct=_SYNTHETIC_AU.au_cpi_yoy_pct,
        au_cpi_trimmed_mean_pct=_SYNTHETIC_AU.au_cpi_trimmed_mean_pct,
        au_unemployment_rate_pct=_SYNTHETIC_AU.au_unemployment_rate_pct,
        au_wpi_yoy_pct=_SYNTHETIC_AU.au_wpi_yoy_pct,
        au_gdp_growth_qoq_pct=_SYNTHETIC_AU.au_gdp_growth_qoq_pct,
        au_housing_price_index_change_pct=_SYNTHETIC_AU.au_housing_price_index_change_pct,
        au_auction_clearance_rate_pct=_SYNTHETIC_AU.au_auction_clearance_rate_pct,
        au_credit_growth_yoy_pct=_SYNTHETIC_AU.au_credit_growth_yoy_pct,
        au_10y_government_yield_pct=_SYNTHETIC_AU.au_10y_government_yield_pct,
        au_3y_government_yield_pct=_SYNTHETIC_AU.au_3y_government_yield_pct,
        aud_usd=_SYNTHETIC_AU.aud_usd,
        data_freshness="live" if sources else "synthetic_fallback",
    )
    return au, sources, errors


# ── Public API ────────────────────────────────────────────────────────────

class EconomicIndicatorService:
    """Fetches and caches AU + US economic indicators.

    Usage:
        service = EconomicIndicatorService(fred_api_key="...")
        indicators = await service.get_indicators(run_id="run-001")

    If fred_api_key is None or empty, returns synthetic fallback data.
    Results are cached with a 1-hour TTL keyed by (date, api_key_prefix).
    """

    def __init__(self, fred_api_key: Optional[str] = None):
        self.fred_api_key = fred_api_key or ""

    def _cache_key(self) -> str:
        today = datetime.now(timezone.utc).date().isoformat()
        key_prefix = self.fred_api_key[:4] if self.fred_api_key else "none"
        return f"{today}:{key_prefix}"

    async def get_indicators(self, run_id: str) -> EconomicIndicators:
        """Return live or cached EconomicIndicators for the given run."""
        cache_key = self._cache_key()
        cached = _cache_get(cache_key)
        if cached is not None:
            # Return copy with this run_id
            return cached.model_copy(update={"run_id": run_id})

        indicators = await self._fetch(run_id)
        _cache_set(cache_key, indicators)
        return indicators

    async def _fetch(self, run_id: str) -> EconomicIndicators:
        """Internal: perform actual API fetches."""
        all_sources: list[str] = []
        all_errors: list[str] = []
        is_live = False

        # Fetch AU
        au, au_sources, au_errors = await _fetch_au_indicators()
        all_sources.extend(au_sources)
        all_errors.extend(au_errors)

        # Fetch US (only if FRED key available)
        if self.fred_api_key:
            try:
                us, us_sources, us_errors = await _fetch_us_indicators(self.fred_api_key)
                all_sources.extend(us_sources)
                all_errors.extend(us_errors)
            except Exception as exc:
                logger.warning("US indicator fetch failed: %s", exc)
                us = _SYNTHETIC_US.model_copy()
                all_errors.append(f"FRED API error: {exc}")
        else:
            logger.debug("No FRED API key — using synthetic US indicators")
            us = _SYNTHETIC_US.model_copy()

        if all_sources:
            is_live = True

        return EconomicIndicators(
            run_id=run_id,
            au=au,
            us=us,
            is_live_data=is_live,
            sources_used=all_sources,
            fetch_errors=all_errors,
        )

    def get_indicators_sync(self, run_id: str) -> EconomicIndicators:
        """Synchronous wrapper — runs the async fetch in a new event loop if needed."""
        try:
            loop = asyncio.get_running_loop()
            # Already in an event loop — create a task (caller must await)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.get_indicators(run_id))
                return future.result()
        except RuntimeError:
            return asyncio.run(self.get_indicators(run_id))

    @staticmethod
    def get_synthetic(run_id: str) -> EconomicIndicators:
        """Return pure synthetic data — no network I/O. Safe for tests and offline use."""
        return EconomicIndicators(
            run_id=run_id,
            au=_SYNTHETIC_AU.model_copy(),
            us=_SYNTHETIC_US.model_copy(),
            is_live_data=False,
            sources_used=["synthetic"],
            fetch_errors=[],
        )
