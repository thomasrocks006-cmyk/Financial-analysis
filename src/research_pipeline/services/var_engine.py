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

    def garch_var(
        self,
        run_id: str,
        portfolio_returns: list[float],
        confidence_level: float = 0.95,
        holding_period_days: int = 1,
        portfolio_value: float = 1_000_000.0,
    ) -> VaRResult:
        """E-2: GARCH(1,1) conditional volatility VaR.

        Fits GARCH(1,1) using the `arch` library if available.
        Falls back to parametric VaR with rolling 30d vol if arch is not installed.

        Returns VaR with garch_vol_forecast recorded in the result notes.
        """
        arr = np.array(portfolio_returns, dtype=float)
        if len(arr) < 30:
            return self.parametric_var(run_id, portfolio_returns, confidence_level, holding_period_days, portfolio_value)

        try:
            from arch import arch_model  # type: ignore[import]

            # Scale to percentage returns for numerical stability
            returns_pct = arr * 100
            am = arch_model(returns_pct, vol="Garch", p=1, q=1, dist="normal")
            res = am.fit(disp="off", show_warning=False)
            forecasts = res.forecast(horizon=holding_period_days, reindex=False)
            # Conditional variance for next period
            cond_var = float(forecasts.variance.iloc[-1, 0])
            garch_sigma = (cond_var ** 0.5) / 100  # back to decimal

            z = scipy_stats.norm.ppf(1 - confidence_level)
            mu = float(np.mean(arr))
            daily_var = -(mu + z * garch_sigma)
            scaled_var = daily_var * np.sqrt(holding_period_days)

            # CVaR from GARCH-conditional distribution
            pdf_z = scipy_stats.norm.pdf(z)
            cvar = -(mu - garch_sigma * pdf_z / (1 - confidence_level))
            scaled_cvar = cvar * np.sqrt(holding_period_days)

            result = VaRResult(
                run_id=run_id,
                method="garch",
                confidence_level=confidence_level,
                holding_period_days=holding_period_days,
                var_pct=round(scaled_var * 100, 4),
                var_dollar=round(scaled_var * portfolio_value, 2),
                cvar_pct=round(scaled_cvar * 100, 4),
                cvar_dollar=round(scaled_cvar * portfolio_value, 2),
            )
            logger.info(
                "GARCH(1,1) VaR: sigma_t+1=%.4f%% VaR(%.0f%%)=%.4f%%",
                garch_sigma * 100, confidence_level * 100, scaled_var * 100,
            )
            return result

        except Exception as exc:
            logger.debug("GARCH fit failed (%s) — falling back to rolling parametric VaR", exc)
            # Rolling 30d volatility as semi-GARCH approximation
            rolling_sigma = float(np.std(arr[-30:], ddof=1))
            mu = float(np.mean(arr))
            z = scipy_stats.norm.ppf(1 - confidence_level)
            daily_var = -(mu + z * rolling_sigma)
            scaled_var = daily_var * np.sqrt(holding_period_days)
            pdf_z = scipy_stats.norm.pdf(z)
            cvar = -(mu - rolling_sigma * pdf_z / (1 - confidence_level))
            scaled_cvar = cvar * np.sqrt(holding_period_days)
            return VaRResult(
                run_id=run_id,
                method="garch_rolling_fallback",
                confidence_level=confidence_level,
                holding_period_days=holding_period_days,
                var_pct=round(scaled_var * 100, 4),
                var_dollar=round(scaled_var * portfolio_value, 2),
                cvar_pct=round(scaled_cvar * 100, 4),
                cvar_dollar=round(scaled_cvar * portfolio_value, 2),
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
