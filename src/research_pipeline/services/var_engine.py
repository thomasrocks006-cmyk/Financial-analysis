"""VaR Engine — Value at Risk and Conditional VaR computation."""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from scipy import stats as scipy_stats

from research_pipeline.schemas.performance import VaRResult, DrawdownAnalysis

logger = logging.getLogger(__name__)


class VaREngine:
    """Deterministic VaR / CVaR engine — no LLM.

    Supports:
    - Parametric VaR (normal distribution assumption)
    - Historical VaR (empirical quantile)
    - Conditional VaR (Expected Shortfall)
    - Maximum drawdown analysis
    """

    def parametric_var(
        self,
        run_id: str,
        portfolio_returns: list[float],
        confidence_level: float = 0.95,
        holding_period_days: int = 1,
        portfolio_value: float = 1_000_000.0,
    ) -> VaRResult:
        """Compute parametric VaR assuming normal distribution."""
        if len(portfolio_returns) < 10:
            return VaRResult(run_id=run_id, method="parametric", confidence_level=confidence_level)

        arr = np.array(portfolio_returns)
        mu = float(np.mean(arr))
        sigma = float(np.std(arr, ddof=1))

        z = scipy_stats.norm.ppf(1 - confidence_level)
        daily_var = -(mu + z * sigma)
        scaled_var = daily_var * np.sqrt(holding_period_days)

        # CVaR (Expected Shortfall)
        pdf_z = scipy_stats.norm.pdf(z)
        cvar = -(mu - sigma * pdf_z / (1 - confidence_level))
        scaled_cvar = cvar * np.sqrt(holding_period_days)

        return VaRResult(
            run_id=run_id,
            method="parametric",
            confidence_level=confidence_level,
            holding_period_days=holding_period_days,
            var_pct=round(scaled_var * 100, 4),
            var_dollar=round(scaled_var * portfolio_value, 2),
            cvar_pct=round(scaled_cvar * 100, 4),
            cvar_dollar=round(scaled_cvar * portfolio_value, 2),
        )

    def historical_var(
        self,
        run_id: str,
        portfolio_returns: list[float],
        confidence_level: float = 0.95,
        holding_period_days: int = 1,
        portfolio_value: float = 1_000_000.0,
    ) -> VaRResult:
        """Compute historical VaR from empirical return distribution."""
        if len(portfolio_returns) < 10:
            return VaRResult(run_id=run_id, method="historical", confidence_level=confidence_level)

        arr = np.array(portfolio_returns)
        percentile = (1 - confidence_level) * 100
        var_daily = -float(np.percentile(arr, percentile))
        scaled_var = var_daily * np.sqrt(holding_period_days)

        # CVaR: mean of returns below the VaR threshold
        threshold = np.percentile(arr, percentile)
        tail_returns = arr[arr <= threshold]
        if len(tail_returns) > 0:
            cvar_daily = -float(np.mean(tail_returns))
        else:
            cvar_daily = var_daily
        scaled_cvar = cvar_daily * np.sqrt(holding_period_days)

        return VaRResult(
            run_id=run_id,
            method="historical",
            confidence_level=confidence_level,
            holding_period_days=holding_period_days,
            var_pct=round(scaled_var * 100, 4),
            var_dollar=round(scaled_var * portfolio_value, 2),
            cvar_pct=round(scaled_cvar * 100, 4),
            cvar_dollar=round(scaled_cvar * portfolio_value, 2),
        )

    def compute_drawdown_analysis(
        self,
        run_id: str,
        returns: list[float],
    ) -> DrawdownAnalysis:
        """Compute maximum drawdown and recovery statistics."""
        if not returns:
            return DrawdownAnalysis(run_id=run_id)

        cumulative = np.cumprod(1 + np.array(returns))
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - running_max) / running_max

        max_dd = float(np.min(drawdowns)) * 100
        trough_idx = int(np.argmin(drawdowns))

        # Find peak before trough
        peak_idx = int(np.argmax(cumulative[:trough_idx + 1])) if trough_idx > 0 else 0

        # Find recovery after trough
        recovery_idx = None
        peak_value = cumulative[peak_idx]
        for i in range(trough_idx, len(cumulative)):
            if cumulative[i] >= peak_value:
                recovery_idx = i
                break

        recovery_days = (recovery_idx - trough_idx) if recovery_idx is not None else None

        # Current drawdown
        current_dd = float(drawdowns[-1]) * 100

        # Underwater days (days below previous high)
        underwater = int(np.sum(drawdowns < 0))

        return DrawdownAnalysis(
            run_id=run_id,
            max_drawdown_pct=round(max_dd, 2),
            recovery_days=recovery_days,
            current_drawdown_pct=round(current_dd, 2),
            underwater_days=underwater,
        )

    def compute_portfolio_var(
        self,
        run_id: str,
        ticker_returns: dict[str, list[float]],
        weights: dict[str, float],
        confidence_level: float = 0.95,
        method: str = "parametric",
        portfolio_value: float = 1_000_000.0,
    ) -> VaRResult:
        """Compute portfolio-level VaR from individual position returns."""
        tickers = sorted(weights.keys())
        if not tickers:
            return VaRResult(run_id=run_id, method=method)

        # Build weighted portfolio return series
        min_len = min(len(ticker_returns.get(t, [])) for t in tickers)
        if min_len < 10:
            return VaRResult(run_id=run_id, method=method)

        total_weight = sum(weights.values())
        portfolio_returns = np.zeros(min_len)
        for t in tickers:
            w = weights[t] / total_weight
            portfolio_returns += np.array(ticker_returns[t][:min_len]) * w

        if method == "historical":
            return self.historical_var(
                run_id, portfolio_returns.tolist(),
                confidence_level=confidence_level,
                portfolio_value=portfolio_value,
            )
        else:
            return self.parametric_var(
                run_id, portfolio_returns.tolist(),
                confidence_level=confidence_level,
                portfolio_value=portfolio_value,
            )
