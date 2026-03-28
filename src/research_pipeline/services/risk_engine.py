"""A5 — Risk Engine: quantitative portfolio risk computation."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from research_pipeline.schemas.reports import RiskPacket

logger = logging.getLogger(__name__)


class RiskEngine:
    """Deterministic quantitative risk engine — no LLM.

    Computes:
    - rolling correlation matrix
    - covariance matrix
    - concentration metrics
    - contribution to variance
    - ETF overlap analysis
    """

    def compute_correlation_matrix(
        self, returns: dict[str, list[float]]
    ) -> dict[str, dict[str, float]]:
        """Compute pairwise correlation matrix from return series."""
        tickers = sorted(returns.keys())
        n = len(tickers)
        if n == 0:
            return {}

        # Align lengths
        min_len = min(len(returns[t]) for t in tickers)
        data = np.array([returns[t][:min_len] for t in tickers])

        if min_len < 2:
            return {t: {t2: 0.0 for t2 in tickers} for t in tickers}

        corr = np.corrcoef(data)
        result = {}
        for i, t1 in enumerate(tickers):
            result[t1] = {}
            for j, t2 in enumerate(tickers):
                result[t1][t2] = round(float(corr[i, j]), 4)
        return result

    def compute_concentration(
        self, weights: dict[str, float], subthemes: dict[str, str]
    ) -> dict[str, float]:
        """Compute subtheme concentration percentages."""
        concentration: dict[str, float] = {}
        for ticker, weight in weights.items():
            theme = subthemes.get(ticker, "other")
            concentration[theme] = concentration.get(theme, 0) + weight
        return {k: round(v, 2) for k, v in concentration.items()}

    def compute_contribution_to_variance(
        self,
        weights: dict[str, float],
        returns: dict[str, list[float]],
    ) -> dict[str, float]:
        """Compute each position's contribution to portfolio variance."""
        tickers = sorted(weights.keys())
        if not tickers:
            return {}

        min_len = min(len(returns.get(t, [])) for t in tickers)
        if min_len < 2:
            return {t: 0.0 for t in tickers}

        data = np.array([returns[t][:min_len] for t in tickers])
        cov = np.cov(data)
        w = np.array([weights[t] for t in tickers])
        port_var = float(w @ cov @ w)
        if port_var == 0:
            return {t: 0.0 for t in tickers}

        contributions = {}
        marginal = cov @ w
        for i, t in enumerate(tickers):
            contributions[t] = round(float(w[i] * marginal[i]) / port_var * 100, 2)
        return contributions

    def detect_etf_overlap(
        self, portfolio_tickers: list[str], etf_holdings: dict[str, list[str]]
    ) -> dict[str, list[str]]:
        """Identify which portfolio names overlap with ETF constituents."""
        overlap: dict[str, list[str]] = {}
        port_set = set(portfolio_tickers)
        for etf, holdings in etf_holdings.items():
            common = port_set.intersection(holdings)
            if common:
                overlap[etf] = sorted(common)
        return overlap

    def build_risk_packet(
        self,
        run_id: str,
        weights: dict[str, float],
        returns: dict[str, list[float]],
        subthemes: dict[str, str],
        etf_holdings: dict[str, list[str]] | None = None,
        var_result: Any | None = None,
        drawdown: Any | None = None,
    ) -> RiskPacket:
        """Produce the full risk packet.

        Args:
            run_id: Pipeline run identifier.
            weights: Portfolio weights {ticker: weight_pct}.
            returns: Historical return series {ticker: [r1, r2, ...]}.
            subthemes: Subtheme mapping {ticker: subtheme_name}.
            etf_holdings: ETF constituent lists {etf_ticker: [holdings]}.
            var_result: Optional VaRResult (or its model_dump()) from VaREngine.
            drawdown: Optional DrawdownAnalysis (or its model_dump()) from VaREngine.
        """
        corr = self.compute_correlation_matrix(returns)
        concentration = self.compute_concentration(weights, subthemes)
        vol_contrib = self.compute_contribution_to_variance(weights, returns)
        etf_overlap = self.detect_etf_overlap(list(weights.keys()), etf_holdings or {})

        # Normalise var_result and drawdown to plain dicts
        def _to_dict(obj: Any) -> dict | None:
            if obj is None:
                return None
            if isinstance(obj, dict):
                return obj
            if hasattr(obj, "model_dump"):
                return obj.model_dump()
            return dict(obj)

        var_dict = _to_dict(var_result)
        dd_dict = _to_dict(drawdown)

        return RiskPacket(
            run_id=run_id,
            correlation_matrix=corr,
            concentration_report=concentration,
            etf_overlap=etf_overlap,
            volatility_contributions=vol_contrib,
            var_analysis=var_dict,
            drawdown_analysis=dd_dict,
            var_method=(var_dict or {}).get("method", ""),
            confidence_level=(var_dict or {}).get("confidence_level"),
        )
