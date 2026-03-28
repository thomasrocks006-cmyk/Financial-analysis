"""Economic indicator service for AU/US macro context."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from research_pipeline.schemas.macro import EconomicIndicators

logger = logging.getLogger(__name__)


class EconomicIndicatorService:
    """Fetch and normalise a compact AU/US macro indicator set.

    The service prefers live public endpoints when API keys are available and
    otherwise degrades to heuristic defaults. Results are cached in-memory so
    repeated stage-8 calls do not refetch within the TTL window.
    """

    FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
    TTL_SECONDS = 3600

    _FRED_SERIES = {
        "us_fed_funds_rate": "FEDFUNDS",
        "us_cpi_yoy": "CPIAUCSL",
        "us_unemployment_rate": "UNRATE",
        "us_10y_yield": "DGS10",
        "us_2y_yield": "DGS2",
    }

    def __init__(self, fred_api_key: str = "", timeout_seconds: float = 10.0):
        self.fred_api_key = fred_api_key
        self.timeout_seconds = timeout_seconds
        self._cache: EconomicIndicators | None = None
        self._cache_ts: float = 0.0

    async def get_indicators(self) -> EconomicIndicators:
        """Return economic indicators with one-hour TTL caching."""
        now = time.time()
        if self._cache is not None and now - self._cache_ts < self.TTL_SECONDS:
            return self._cache

        indicators = self._build_heuristic_defaults()
        live_values: dict[str, float] = {}
        if self.fred_api_key:
            try:
                live_values = await self._fetch_fred_values()
            except Exception as exc:
                logger.warning("EconomicIndicatorService FRED fetch failed: %s", exc)

        # AU defaults remain heuristic in the absence of RBA/ABS credentials.
        indicators.us_fed_funds_rate = live_values.get(
            "us_fed_funds_rate", indicators.us_fed_funds_rate
        )
        indicators.us_cpi_yoy = self._derive_yoy_from_index(
            live_values.get("us_cpi_yoy"), indicators.us_cpi_yoy
        )
        indicators.us_unemployment_rate = live_values.get(
            "us_unemployment_rate", indicators.us_unemployment_rate
        )
        indicators.us_10y_yield = live_values.get("us_10y_yield", indicators.us_10y_yield)
        indicators.us_2y_yield = live_values.get("us_2y_yield", indicators.us_2y_yield)
        indicators.us_yield_curve_10y_2y = round(
            indicators.us_10y_yield - indicators.us_2y_yield,
            2,
        )
        indicators.source_notes.extend(
            [
                "US macro indicators sourced from FRED when available.",
                "Australian macro indicators currently use public-source heuristics "
                "until dedicated RBA/ABS connectors are configured.",
            ]
        )

        self._cache = indicators
        self._cache_ts = now
        return indicators

    def _build_heuristic_defaults(self) -> EconomicIndicators:
        return EconomicIndicators(
            as_of=datetime.now(timezone.utc),
            au_rba_cash_rate=4.35,
            au_cpi_yoy=3.4,
            au_trimmed_mean_cpi=3.7,
            au_unemployment_rate=4.1,
            au_wage_price_index=4.1,
            au_housing_price_growth_yoy=8.0,
            au_10y_yield=4.20,
            us_fed_funds_rate=5.25,
            us_cpi_yoy=3.2,
            us_pce_yoy=2.7,
            us_unemployment_rate=4.0,
            us_10y_yield=4.25,
            us_2y_yield=4.60,
            aud_usd=0.66,
            global_pmi=51.2,
            vix=16.0,
            copper_price_usd_per_lb=4.15,
        )

    async def _fetch_fred_values(self) -> dict[str, float]:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            tasks = [
                self._fetch_fred_latest(client, target_name, series_id)
                for target_name, series_id in self._FRED_SERIES.items()
            ]
            results = await asyncio.gather(*tasks)
        return {
            name: value
            for name, value in results
            if value is not None
        }

    async def _fetch_fred_latest(
        self,
        client: httpx.AsyncClient,
        target_name: str,
        series_id: str,
    ) -> tuple[str, float | None]:
        params = {
            "series_id": series_id,
            "api_key": self.fred_api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 15,
        }
        response = await client.get(self.FRED_BASE, params=params)
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
        observations = payload.get("observations", [])
        for observation in reversed(observations):
            value = observation.get("value")
            if value in (None, "."):
                continue
            try:
                return target_name, float(value)
            except (TypeError, ValueError):
                continue
        return target_name, None

    @staticmethod
    def _derive_yoy_from_index(value: float | None, fallback: float) -> float:
        """Very small helper for CPI series that may arrive as an index level.

        If the live series looks like a CPI index level rather than a YoY rate,
        keep the fallback heuristic rather than pretending the level is a rate.
        """
        if value is None:
            return fallback
        if value > 20:
            return fallback
        return value
