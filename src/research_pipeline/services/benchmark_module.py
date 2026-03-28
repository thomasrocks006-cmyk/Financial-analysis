"""Benchmark Analytics Module — benchmark-relative portfolio analysis."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from research_pipeline.schemas.performance import BenchmarkComparison

logger = logging.getLogger(__name__)

# Default benchmark constituent weights (top holdings approximation)
BENCHMARK_CONSTITUENTS = {
    "SPY": {  # S&P 500 proxy — AI infra relevant names
        "NVDA": 6.5, "AVGO": 1.8, "TSM": 0.0,  # TSM not in S&P 500
        "CEG": 0.15, "VST": 0.10, "GEV": 0.12,
        "ETN": 0.25, "APH": 0.15, "PWR": 0.10,
        "FCX": 0.15, "FIX": 0.05, "HUBB": 0.05,
    },
    "QQQ": {  # Nasdaq 100 proxy
        "NVDA": 8.5, "AVGO": 2.5, "TSM": 0.0,
        "CEG": 0.0, "VST": 0.0, "GEV": 0.0,
    },
    "XLK": {  # Tech Select proxy
        "NVDA": 14.0, "AVGO": 4.5,
    },
    "SOXX": {  # Semiconductor ETF proxy
        "NVDA": 10.0, "AVGO": 8.0, "TSM": 7.0, "AMD": 6.0,
    },
}


class BenchmarkModule:
    """Benchmark-relative analytics — no LLM.

    Computes:
    - Active weights vs benchmark
    - Tracking error
    - Information ratio
    - Relative drawdown
    - Sharpe ratio comparison
    """

    def compute_active_weights(
        self,
        portfolio_weights: dict[str, float],
        benchmark_name: str = "SPY",
    ) -> dict[str, float]:
        """Compute active weight (portfolio weight - benchmark weight) per ticker."""
        bench = BENCHMARK_CONSTITUENTS.get(benchmark_name, {})
        all_tickers = set(portfolio_weights.keys()) | set(bench.keys())
        active = {}
        for ticker in all_tickers:
            pw = portfolio_weights.get(ticker, 0.0)
            bw = bench.get(ticker, 0.0)
            active[ticker] = round(pw - bw, 4)
        return active

    def compute_tracking_error(
        self,
        portfolio_returns: list[float],
        benchmark_returns: list[float],
        annualize: bool = True,
    ) -> float:
        """Compute tracking error (std dev of excess returns)."""
        n = min(len(portfolio_returns), len(benchmark_returns))
        if n < 2:
            return 0.0

        excess = np.array(portfolio_returns[:n]) - np.array(benchmark_returns[:n])
        te = float(np.std(excess, ddof=1))

        if annualize:
            te *= np.sqrt(252)

        return round(te, 4)

    def compute_information_ratio(
        self,
        portfolio_returns: list[float],
        benchmark_returns: list[float],
    ) -> float:
        """Compute information ratio (annualized excess return / tracking error)."""
        n = min(len(portfolio_returns), len(benchmark_returns))
        if n < 2:
            return 0.0

        excess = np.array(portfolio_returns[:n]) - np.array(benchmark_returns[:n])
        mean_excess = float(np.mean(excess)) * 252
        te = float(np.std(excess, ddof=1)) * np.sqrt(252)

        if te == 0:
            return 0.0

        return round(mean_excess / te, 4)

    def compute_sharpe_ratio(
        self,
        returns: list[float],
        risk_free_rate: float = 0.045,
    ) -> float:
        """Compute annualized Sharpe ratio."""
        if len(returns) < 2:
            return 0.0

        arr = np.array(returns)
        mean_daily = float(np.mean(arr))
        std_daily = float(np.std(arr, ddof=1))

        if std_daily == 0:
            return 0.0

        daily_rf = risk_free_rate / 252
        sharpe = (mean_daily - daily_rf) / std_daily * np.sqrt(252)
        return round(float(sharpe), 4)

    def compute_max_drawdown(self, returns: list[float]) -> float:
        """Compute maximum drawdown from a return series."""
        if not returns:
            return 0.0

        cumulative = np.cumprod(1 + np.array(returns))
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = (cumulative - running_max) / running_max
        return round(float(np.min(drawdowns)) * 100, 2)

    def full_comparison(
        self,
        run_id: str,
        portfolio_returns: list[float],
        benchmark_returns: list[float],
        benchmark_name: str = "SPY",
    ) -> BenchmarkComparison:
        """Produce a full portfolio vs benchmark comparison."""
        n = min(len(portfolio_returns), len(benchmark_returns))

        port_total = float(np.prod(1 + np.array(portfolio_returns[:n])) - 1) * 100 if n > 0 else 0
        bench_total = float(np.prod(1 + np.array(benchmark_returns[:n])) - 1) * 100 if n > 0 else 0

        te = self.compute_tracking_error(portfolio_returns, benchmark_returns)
        ir = self.compute_information_ratio(portfolio_returns, benchmark_returns)
        port_sharpe = self.compute_sharpe_ratio(portfolio_returns)
        bench_sharpe = self.compute_sharpe_ratio(benchmark_returns)
        port_dd = self.compute_max_drawdown(portfolio_returns)
        bench_dd = self.compute_max_drawdown(benchmark_returns)

        corr = 0.0
        if n >= 2:
            corr = round(float(np.corrcoef(portfolio_returns[:n], benchmark_returns[:n])[0, 1]), 4)

        return BenchmarkComparison(
            run_id=run_id,
            benchmark_name=benchmark_name,
            period_days=n,
            portfolio_return_pct=round(port_total, 2),
            benchmark_return_pct=round(bench_total, 2),
            excess_return_pct=round(port_total - bench_total, 2),
            tracking_error_pct=te,
            information_ratio=ir,
            portfolio_sharpe=port_sharpe,
            benchmark_sharpe=bench_sharpe,
            max_drawdown_portfolio_pct=port_dd,
            max_drawdown_benchmark_pct=bench_dd,
            correlation=corr,
        )
