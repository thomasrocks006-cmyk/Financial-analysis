"""Factor Exposure Engine — compute factor loadings for portfolio positions."""

from __future__ import annotations

import logging
from typing import Any

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
    "compute": {
        "market_beta": 1.35,
        "size_loading": -0.3,
        "value_loading": -0.5,
        "momentum_loading": 0.4,
        "quality_loading": 0.3,
        "volatility_loading": 0.4,
    },
    "power": {
        "market_beta": 0.85,
        "size_loading": 0.1,
        "value_loading": 0.2,
        "momentum_loading": 0.2,
        "quality_loading": 0.4,
        "volatility_loading": -0.1,
    },
    "infrastructure": {
        "market_beta": 1.05,
        "size_loading": 0.2,
        "value_loading": 0.1,
        "momentum_loading": 0.15,
        "quality_loading": 0.2,
        "volatility_loading": 0.0,
    },
    "materials": {
        "market_beta": 1.10,
        "size_loading": 0.0,
        "value_loading": 0.3,
        "momentum_loading": -0.1,
        "quality_loading": 0.1,
        "volatility_loading": 0.2,
    },
    "etf": {
        "market_beta": 1.0,
        "size_loading": 0.0,
        "value_loading": 0.0,
        "momentum_loading": 0.0,
        "quality_loading": 0.0,
        "volatility_loading": 0.0,
    },
}

# Ticker -> subtheme mapping
TICKER_SUBTHEMES = {
    "NVDA": "compute",
    "AVGO": "compute",
    "TSM": "compute",
    "AMD": "compute",
    "ANET": "compute",
    "CEG": "power",
    "VST": "power",
    "GEV": "power",
    "NLR": "power",
    "PWR": "infrastructure",
    "ETN": "infrastructure",
    "HUBB": "infrastructure",
    "APH": "infrastructure",
    "FIX": "infrastructure",
    "NXT": "infrastructure",
    "FCX": "materials",
    "BHP": "materials",
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
            "market_beta": 0.0,
            "size_loading": 0.0,
            "value_loading": 0.0,
            "momentum_loading": 0.0,
            "quality_loading": 0.0,
            "volatility_loading": 0.0,
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
