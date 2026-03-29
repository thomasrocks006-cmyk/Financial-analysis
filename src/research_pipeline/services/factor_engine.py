"""Factor Exposure Engine — compute factor loadings for portfolio positions."""

from __future__ import annotations

import logging
from typing import Any, Optional

import numpy as np

from research_pipeline.schemas.performance import FactorExposure, FactorAttribution

logger = logging.getLogger(__name__)

# Default factor returns (annualized, for estimation when no data feed available)
DEFAULT_FACTOR_PREMIA = {
    "market": 0.08,
    "size": 0.02,
    "value": 0.03,
    "momentum": 0.04,
    "quality": 0.025,
}

# Heuristic factor loadings by subtheme (used when no regression data available)
SUBTHEME_FACTOR_PROFILES = {
    "compute": {"market_beta": 1.35, "size_loading": -0.3, "value_loading": -0.5, "momentum_loading": 0.4, "quality_loading": 0.3, "volatility_loading": 0.4},
    "power": {"market_beta": 0.85, "size_loading": 0.1, "value_loading": 0.2, "momentum_loading": 0.2, "quality_loading": 0.4, "volatility_loading": -0.1},
    "infrastructure": {"market_beta": 1.05, "size_loading": 0.2, "value_loading": 0.1, "momentum_loading": 0.15, "quality_loading": 0.2, "volatility_loading": 0.0},
    "materials": {"market_beta": 1.10, "size_loading": 0.0, "value_loading": 0.3, "momentum_loading": -0.1, "quality_loading": 0.1, "volatility_loading": 0.2},
    "etf": {"market_beta": 1.0, "size_loading": 0.0, "value_loading": 0.0, "momentum_loading": 0.0, "quality_loading": 0.0, "volatility_loading": 0.0},
}

# Ticker -> subtheme mapping
TICKER_SUBTHEMES = {
    "NVDA": "compute", "AVGO": "compute", "TSM": "compute", "AMD": "compute", "ANET": "compute",
    "CEG": "power", "VST": "power", "GEV": "power", "NLR": "power",
    "PWR": "infrastructure", "ETN": "infrastructure", "HUBB": "infrastructure",
    "APH": "infrastructure", "FIX": "infrastructure", "NXT": "infrastructure",
    "FCX": "materials", "BHP": "materials",
}


class FactorExposureEngine:
    """Compute factor loadings for portfolio tickers.

    When historical return series are available, uses OLS regression
    against factor return series. Otherwise, uses heuristic loadings
    based on subtheme classification.
    """

    def compute_factor_exposures(
        self,
        tickers: list[str],
        returns: dict[str, list[float]] | None = None,
        factor_returns: dict[str, list[float]] | None = None,
    ) -> list[FactorExposure]:
        """Compute factor loadings for each ticker."""
        results = []

        for ticker in tickers:
            ticker_returns = (returns or {}).get(ticker, [])

            if len(ticker_returns) >= 60 and factor_returns:
                # Use regression when sufficient data exists
                exposure = self._regression_factors(ticker, ticker_returns, factor_returns)
            else:
                # Fall back to heuristic loadings
                exposure = self._heuristic_factors(ticker)

            results.append(exposure)

        return results

    def _regression_factors(
        self, ticker: str, returns: list[float], factor_returns: dict[str, list[float]]
    ) -> FactorExposure:
        """Estimate factor loadings via OLS regression."""
        n = min(len(returns), *(len(v) for v in factor_returns.values()))
        y = np.array(returns[:n])

        factor_names = ["market", "size", "value", "momentum", "quality"]
        X_cols = []
        for fn in factor_names:
            if fn in factor_returns:
                X_cols.append(np.array(factor_returns[fn][:n]))

        if not X_cols:
            return self._heuristic_factors(ticker)

        X = np.column_stack(X_cols)
        # Add intercept
        X = np.column_stack([np.ones(n), X])

        try:
            betas, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
        except np.linalg.LinAlgError:
            return self._heuristic_factors(ticker)

        loadings = {}
        for i, fn in enumerate(factor_names):
            if fn in factor_returns:
                loadings[fn] = float(betas[i + 1])

        return FactorExposure(
            ticker=ticker,
            market_beta=round(loadings.get("market", 1.0), 4),
            size_loading=round(loadings.get("size", 0.0), 4),
            value_loading=round(loadings.get("value", 0.0), 4),
            momentum_loading=round(loadings.get("momentum", 0.0), 4),
            quality_loading=round(loadings.get("quality", 0.0), 4),
        )

    def _heuristic_factors(self, ticker: str) -> FactorExposure:
        """Use subtheme-based heuristic loadings."""
        subtheme = TICKER_SUBTHEMES.get(ticker, "infrastructure")
        profile = SUBTHEME_FACTOR_PROFILES.get(subtheme, SUBTHEME_FACTOR_PROFILES["infrastructure"])

        return FactorExposure(
            ticker=ticker,
            market_beta=profile["market_beta"],
            size_loading=profile["size_loading"],
            value_loading=profile["value_loading"],
            momentum_loading=profile["momentum_loading"],
            quality_loading=profile["quality_loading"],
            volatility_loading=profile.get("volatility_loading", 0.0),
        )

    def portfolio_factor_exposure(
        self,
        exposures: list[FactorExposure],
        weights: dict[str, float],
    ) -> dict[str, float]:
        """Compute weighted portfolio-level factor exposures."""
        portfolio = {
            "market_beta": 0.0, "size_loading": 0.0, "value_loading": 0.0,
            "momentum_loading": 0.0, "quality_loading": 0.0, "volatility_loading": 0.0,
        }

        total_weight = sum(weights.values())
        if total_weight == 0:
            return portfolio

        for exp in exposures:
            w = weights.get(exp.ticker, 0) / total_weight
            portfolio["market_beta"] += exp.market_beta * w
            portfolio["size_loading"] += exp.size_loading * w
            portfolio["value_loading"] += exp.value_loading * w
            portfolio["momentum_loading"] += exp.momentum_loading * w
            portfolio["quality_loading"] += exp.quality_loading * w
            portfolio["volatility_loading"] += exp.volatility_loading * w

        return {k: round(v, 4) for k, v in portfolio.items()}

    def compute_factor_attribution(
        self,
        run_id: str,
        exposures: list[FactorExposure],
        weights: dict[str, float],
        factor_returns_period: dict[str, float],
        total_portfolio_return: float,
        period_start: Any = None,
        period_end: Any = None,
    ) -> FactorAttribution:
        """Attribute portfolio returns to factor contributions."""
        from datetime import datetime, timezone

        port_exposure = self.portfolio_factor_exposure(exposures, weights)

        market_contrib = port_exposure["market_beta"] * factor_returns_period.get("market", 0)
        size_contrib = port_exposure["size_loading"] * factor_returns_period.get("size", 0)
        value_contrib = port_exposure["value_loading"] * factor_returns_period.get("value", 0)
        mom_contrib = port_exposure["momentum_loading"] * factor_returns_period.get("momentum", 0)
        quality_contrib = port_exposure["quality_loading"] * factor_returns_period.get("quality", 0)

        explained = market_contrib + size_contrib + value_contrib + mom_contrib + quality_contrib
        residual_alpha = total_portfolio_return - explained

        now = datetime.now(timezone.utc)
        return FactorAttribution(
            run_id=run_id,
            period_start=period_start or now,
            period_end=period_end or now,
            total_return_pct=round(total_portfolio_return, 4),
            market_contribution_pct=round(market_contrib, 4),
            size_contribution_pct=round(size_contrib, 4),
            value_contribution_pct=round(value_contrib, 4),
            momentum_contribution_pct=round(mom_contrib, 4),
            quality_contribution_pct=round(quality_contrib, 4),
            residual_alpha_pct=round(residual_alpha, 4),
        )


# ── Session 13: FRED Fama-French factor fetcher ───────────────────────────────

# FRED series IDs for Kenneth French's 5-factor data (daily)
_FRED_FF5_SERIES: dict[str, str] = {
    "mkt_rf": "F-F_Research_Data_5_Factors_2x3_daily_MKT-RF",
    "smb":    "F-F_Research_Data_5_Factors_2x3_daily_SMB",
    "hml":    "F-F_Research_Data_5_Factors_2x3_daily_HML",
    "rmw":    "F-F_Research_Data_5_Factors_2x3_daily_RMW",
    "cma":    "F-F_Research_Data_5_Factors_2x3_daily_CMA",
    "rf":     "F-F_Research_Data_5_Factors_2x3_daily_RF",
}

# Synthetic daily factor return distributions (used when FRED is unavailable)
# Annualised premia → divide by 252 for daily
_SYNTHETIC_FACTOR_DAILY: dict[str, float] = {
    "mkt_rf": 0.08 / 252,
    "smb":    0.02 / 252,
    "hml":    0.03 / 252,
    "rmw":    0.025 / 252,
    "cma":    0.015 / 252,
    "rf":     0.05 / 252,
}


class FactorRefitResult:
    """Result from a FRED-based factor model refit.

    Attributes:
        factor_returns: dict of factor → list[float] (daily, annualised)
        r_squared: dict of ticker → R² from OLS regression
        alpha: dict of ticker → alpha (excess return unexplained by factors)
        is_live: True when FRED data was actually used; False for synthetic
        obs_count: number of daily observations fetched
        source: human-readable data source description
    """

    def __init__(
        self,
        factor_returns: dict[str, list[float]],
        r_squared: dict[str, float] | None = None,
        alpha: dict[str, float] | None = None,
        is_live: bool = False,
        obs_count: int = 0,
        source: str = "synthetic",
    ) -> None:
        self.factor_returns = factor_returns
        self.r_squared = r_squared or {}
        self.alpha = alpha or {}
        self.is_live = is_live
        self.obs_count = obs_count
        self.source = source

    def to_dict(self) -> dict:
        return {
            "is_live": self.is_live,
            "obs_count": self.obs_count,
            "source": self.source,
            "factor_returns_mean": {k: round(float(np.mean(v)), 6) for k, v in self.factor_returns.items() if v},
            "r_squared": self.r_squared,
            "alpha": self.alpha,
        }


class FREDFactorFetcher:
    """Session 13: fetch Fama-French 5-factor daily data from FRED.

    Falls back to synthetic factor returns when the FRED API is unavailable
    or when no API key is configured.  The synthetic fallback uses long-run
    premia from academic literature (Fama & French, 2015).

    Usage:
        fetcher = FREDFactorFetcher(fred_api_key="...")
        result = fetcher.fetch(obs=252)  # 1Y of daily data
        factor_returns = result.factor_returns   # dict[str, list[float]]
    """

    _CACHE: dict[str, "FactorRefitResult"] = {}
    _CACHE_TS: float = 0.0
    _CACHE_TTL: float = 3600.0  # 1 hour

    def __init__(self, fred_api_key: str | None = None) -> None:
        self.fred_api_key = fred_api_key

    def fetch(self, obs: int = 252) -> "FactorRefitResult":
        """Fetch factor returns; returns live FRED data or synthetic fallback.

        Args:
            obs: Number of daily observations to request (default 252 = 1Y).

        Returns:
            FactorRefitResult with factor_returns dict keyed by factor name.
        """
        import time
        now = time.time()
        cache_key = f"ff5_{obs}"
        if cache_key in self._CACHE and (now - self._CACHE_TS) < self._CACHE_TTL:
            return self._CACHE[cache_key]

        if self.fred_api_key:
            try:
                result = self._fetch_fred(obs)
                self._CACHE[cache_key] = result
                self._CACHE_TS = now
                return result
            except Exception as exc:
                logger.warning("FREDFactorFetcher: FRED fetch failed (%s) — using synthetic", exc)

        result = self._synthetic(obs)
        self._CACHE[cache_key] = result
        self._CACHE_TS = now
        return result

    def _fetch_fred(self, obs: int) -> "FactorRefitResult":
        """Attempt to pull factor data from FRED REST API."""
        import urllib.request
        import json as _json

        factor_returns: dict[str, list[float]] = {}
        for factor_name, series_id in _FRED_FF5_SERIES.items():
            url = (
                f"https://api.stlouisfed.org/fred/series/observations"
                f"?series_id={series_id}&api_key={self.fred_api_key}"
                f"&file_type=json&sort_order=desc&limit={obs}"
            )
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = _json.loads(resp.read())
            observations = data.get("observations", [])
            values: list[float] = []
            for o in observations:
                v = o.get("value", ".")
                if v != ".":
                    try:
                        values.append(float(v) / 100)  # FRED returns %, convert to decimal
                    except ValueError:
                        pass
            factor_returns[factor_name] = list(reversed(values))

        n = min(len(v) for v in factor_returns.values()) if factor_returns else 0
        return FactorRefitResult(
            factor_returns=factor_returns,
            is_live=True,
            obs_count=n,
            source=f"FRED Fama-French 5-Factor (daily), {n} obs",
        )

    def _synthetic(self, obs: int) -> "FactorRefitResult":
        """Generate synthetic factor return series using long-run premia."""
        rng = np.random.default_rng(seed=42)
        factor_returns: dict[str, list[float]] = {}
        for name, daily_mean in _SYNTHETIC_FACTOR_DAILY.items():
            noise = rng.normal(loc=daily_mean, scale=abs(daily_mean) * 2, size=obs)
            factor_returns[name] = [round(float(v), 6) for v in noise]
        return FactorRefitResult(
            factor_returns=factor_returns,
            is_live=False,
            obs_count=obs,
            source="Synthetic — long-run Fama-French premia (FRED unavailable)",
        )

    def refit_exposures(
        self,
        ticker_returns: dict[str, list[float]],
        factor_result: "FactorRefitResult",
    ) -> dict[str, dict[str, float]]:
        """OLS refit of ticker returns against fetched factor series.

        Args:
            ticker_returns: dict of ticker → list of daily returns (same length as factors).
            factor_result: output of fetch().

        Returns:
            dict of ticker → {factor: beta, ..., r_squared, alpha}
        """
        results: dict[str, dict[str, float]] = {}
        factor_names = [n for n in factor_result.factor_returns if n != "rf"]
        fr = factor_result.factor_returns
        n = min(len(fr.get(f, [])) for f in factor_names) if factor_names else 0

        for ticker, ret_series in ticker_returns.items():
            if len(ret_series) < 30 or n < 30:
                results[ticker] = {"r_squared": 0.0, "alpha": 0.0}
                continue

            m = min(len(ret_series), n)
            rf_series = fr.get("rf", [0.0] * m)
            y = np.array(ret_series[:m]) - np.array(rf_series[:m])
            X_cols = [np.array(fr[f][:m]) for f in factor_names]
            X = np.column_stack([np.ones(m)] + X_cols)

            try:
                betas, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
                y_hat = X @ betas
                ss_res = float(np.sum((y - y_hat) ** 2))
                ss_tot = float(np.sum((y - np.mean(y)) ** 2))
                r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
                row: dict[str, float] = {"r_squared": round(r2, 4), "alpha": round(float(betas[0]), 6)}
                for i, f in enumerate(factor_names):
                    row[f] = round(float(betas[i + 1]), 4)
                results[ticker] = row
            except np.linalg.LinAlgError:
                results[ticker] = {"r_squared": 0.0, "alpha": 0.0}

        return results
