"""Benchmark Analytics Module — benchmark-relative portfolio analysis."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import numpy as np

from research_pipeline.schemas.performance import BenchmarkComparison

logger = logging.getLogger(__name__)

# Default benchmark constituent weights (top holdings approximation)
# E-4: Extended with ASX 200 proxy constituents
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
    # E-4: ASX 200 proxy — top constituents by weight
    "^AXJO": {
        "CBA.AX": 9.2, "BHP.AX": 6.8, "CSL.AX": 5.8, "NAB.AX": 4.3,
        "WBC.AX": 4.0, "ANZ.AX": 3.8, "WES.AX": 3.0, "MQG.AX": 2.8,
        "RIO.AX": 2.5, "FMG.AX": 2.0, "TCL.AX": 1.8, "WOW.AX": 1.6,
        "REA.AX": 1.4, "XRO.AX": 1.2, "STO.AX": 1.0,
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

    def fetch_benchmark_returns(
        self,
        benchmark_symbol: str = "^AXJO",
        n_days: int = 252,
    ) -> list[float]:
        """E-4: Fetch real benchmark returns from yfinance.

        Supports both US (SPY, QQQ) and AU (^AXJO) benchmarks.
        Falls back to synthetic if yfinance is unavailable.
        """
        try:
            import yfinance as yf  # type: ignore[import]

            ticker = yf.Ticker(benchmark_symbol)
            hist = ticker.history(period=f"{max(n_days // 21 + 2, 13)}mo")
            if hist.empty:
                raise ValueError("empty history")

            closes = hist["Close"].dropna().values
            if len(closes) < 2:
                raise ValueError("insufficient data")

            returns = [(closes[i] / closes[i - 1]) - 1 for i in range(1, len(closes))]
            if len(returns) > n_days:
                returns = returns[-n_days:]

            logger.info(
                "Fetched %d days of live benchmark returns for %s",
                len(returns), benchmark_symbol,
            )
            return [round(float(r), 6) for r in returns]

        except Exception as exc:
            logger.debug(
                "Live benchmark fetch failed for %s (%s) — using synthetic", benchmark_symbol, exc
            )
            return self._synthetic_benchmark_returns(benchmark_symbol, n_days)

    def _synthetic_benchmark_returns(self, symbol: str, n_days: int) -> list[float]:
        """Generate deterministic synthetic benchmark returns as fallback."""
        import hashlib

        # Annualised assumptions by benchmark type
        _PARAMS = {
            "^AXJO": (0.09, 0.14),   # 9% return, 14% vol
            "SPY": (0.12, 0.16),
            "QQQ": (0.16, 0.22),
            "default": (0.10, 0.16),
        }
        mu_ann, sig_ann = _PARAMS.get(symbol, _PARAMS["default"])
        seed = int(hashlib.md5(symbol.encode()).hexdigest()[:8], 16) % (2 ** 31)
        rng = np.random.default_rng(seed)
        daily_ret = rng.normal(mu_ann / 252, sig_ann / (252 ** 0.5), n_days)
        return [round(float(r), 6) for r in daily_ret]

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
