"""Tests for quantitative research engines — factor, benchmark, VaR, portfolio optimisation."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from research_pipeline.services.factor_engine import FactorExposureEngine
from research_pipeline.services.benchmark_module import BenchmarkModule, BENCHMARK_CONSTITUENTS
from research_pipeline.services.portfolio_optimisation import (
    PortfolioOptimisationEngine,
    BlackLittermanInputs,
)


# ── Factor Exposure Engine ─────────────────────────────────────────────────


class TestFactorExposureEngine:
    def setup_method(self):
        self.engine = FactorExposureEngine()

    def test_heuristic_factors_known_ticker(self):
        # NVDA is in the compute subtheme
        exposures = self.engine.compute_factor_exposures(["NVDA"])
        assert len(exposures) == 1
        exposure = exposures[0]
        assert exposure.ticker == "NVDA"
        assert exposure.market_beta > 0
        assert isinstance(exposure.size_loading, float)
        assert isinstance(exposure.momentum_loading, float)

    def test_heuristic_factors_unknown_ticker(self):
        exposures = self.engine.compute_factor_exposures(["UNKNOWN_TICKER"])
        assert len(exposures) == 1
        exposure = exposures[0]
        assert exposure.ticker == "UNKNOWN_TICKER"
        # Unknown falls back to infrastructure profile
        assert isinstance(exposure.market_beta, float)

    def test_regression_factors_with_data(self):
        np.random.seed(42)
        returns_data = {
            "TEST": np.random.normal(0.001, 0.02, 60).tolist(),
        }
        factor_data = {
            "market": np.random.normal(0.0008, 0.015, 60).tolist(),
            "size": np.random.normal(0.0002, 0.005, 60).tolist(),
            "value": np.random.normal(0.0001, 0.004, 60).tolist(),
            "momentum": np.random.normal(0.0003, 0.006, 60).tolist(),
            "quality": np.random.normal(0.0001, 0.003, 60).tolist(),
        }
        exposures = self.engine.compute_factor_exposures(
            ["TEST"], returns=returns_data, factor_returns=factor_data
        )
        assert len(exposures) == 1
        assert exposures[0].ticker == "TEST"
        assert isinstance(exposures[0].market_beta, float)

    def test_portfolio_factor_exposure(self):
        weights = {"NVDA": 0.30, "EQIX": 0.30, "CEG": 0.40}
        exposures = self.engine.compute_factor_exposures(list(weights.keys()))
        portfolio_exp = self.engine.portfolio_factor_exposure(exposures, weights)
        assert isinstance(portfolio_exp, dict)
        assert "market_beta" in portfolio_exp
        assert isinstance(portfolio_exp["market_beta"], float)

    def test_factor_attribution(self):
        now = datetime.now(timezone.utc)
        weights = {"NVDA": 0.50, "AVGO": 0.50}
        exposures = self.engine.compute_factor_exposures(list(weights.keys()))
        factor_returns_period = {
            "market": 0.05,
            "size": -0.01,
            "value": 0.02,
            "momentum": 0.03,
            "quality": 0.01,
        }
        portfolio_return = 8.0  # percentage
        attr = self.engine.compute_factor_attribution(
            run_id="RUN-001",
            exposures=exposures,
            weights=weights,
            factor_returns_period=factor_returns_period,
            total_portfolio_return=portfolio_return,
            period_start=now,
            period_end=now,
        )
        assert attr.run_id == "RUN-001"
        assert isinstance(attr.residual_alpha_pct, float)


# ── Benchmark Module ───────────────────────────────────────────────────────


class TestBenchmarkModule:
    def setup_method(self):
        self.module = BenchmarkModule()

    def test_active_weights(self):
        portfolio = {"NVDA": 15.0, "AAPL": 10.0, "MSFT": 5.0}
        active = self.module.compute_active_weights(portfolio, benchmark_name="SPY")
        assert isinstance(active, dict)
        assert "NVDA" in active
        # NVDA should have positive active weight (overweight vs SPY ~6.5%)
        assert active["NVDA"] > 0

    def test_tracking_error(self):
        np.random.seed(42)
        port_returns = np.random.normal(0.001, 0.02, 60).tolist()
        bench_returns = np.random.normal(0.0008, 0.015, 60).tolist()
        te = self.module.compute_tracking_error(port_returns, bench_returns)
        assert te > 0

    def test_information_ratio(self):
        np.random.seed(42)
        port_returns = np.random.normal(0.001, 0.02, 60).tolist()
        bench_returns = np.random.normal(0.0008, 0.015, 60).tolist()
        ir = self.module.compute_information_ratio(port_returns, bench_returns)
        assert isinstance(ir, float)

    def test_sharpe_ratio(self):
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 252).tolist()
        sharpe = self.module.compute_sharpe_ratio(returns, risk_free_rate=0.05)
        assert isinstance(sharpe, float)

    def test_max_drawdown(self):
        # Create returns with a drawdown — max_drawdown returns negative pct
        returns = [0.01, 0.02, -0.05, -0.04, -0.03, 0.02, 0.01, 0.03]
        dd = self.module.compute_max_drawdown(returns)
        assert dd < 0  # drawdowns are negative
        assert dd >= -100.0

    def test_full_comparison(self):
        np.random.seed(42)
        port_returns = np.random.normal(0.001, 0.02, 60).tolist()
        bench_returns = np.random.normal(0.0008, 0.015, 60).tolist()
        comparison = self.module.full_comparison(
            run_id="RUN-001",
            benchmark_name="SPY",
            portfolio_returns=port_returns,
            benchmark_returns=bench_returns,
        )
        assert comparison.benchmark_name == "SPY"
        assert comparison.run_id == "RUN-001"
        assert isinstance(comparison.tracking_error_pct, float)

    def test_known_benchmarks(self):
        """All configured benchmarks should be loadable."""
        for name in ["SPY", "QQQ", "XLK", "SOXX"]:
            weights = BENCHMARK_CONSTITUENTS.get(name, {})
            assert len(weights) > 0, f"Benchmark {name} has no constituents"


# ── VaR Engine ─────────────────────────────────────────────────────────────


class TestVaREngine:
    def setup_method(self):
        try:
            from research_pipeline.services.var_engine import VaREngine

            self.engine = VaREngine()
            self.available = True
        except ImportError:
            self.available = False

    def test_parametric_var(self):
        if not self.available:
            pytest.skip("scipy not available")
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 252).tolist()
        result = self.engine.parametric_var(
            run_id="RUN-001", portfolio_returns=returns, confidence_level=0.95
        )
        assert result.method == "parametric"
        assert result.var_pct > 0
        assert result.cvar_pct >= result.var_pct  # CVaR always >= VaR

    def test_historical_var(self):
        if not self.available:
            pytest.skip("scipy not available")
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 252).tolist()
        result = self.engine.historical_var(
            run_id="RUN-001", portfolio_returns=returns, confidence_level=0.95
        )
        assert result.method == "historical"
        assert result.var_pct > 0

    def test_drawdown_analysis(self):
        if not self.available:
            pytest.skip("scipy not available")
        returns = [0.01, 0.02, -0.05, -0.04, -0.03, 0.02, 0.01, 0.03, 0.01]
        result = self.engine.compute_drawdown_analysis("RUN-001", returns)
        assert result.max_drawdown_pct < 0  # drawdowns are negative

    def test_portfolio_var(self):
        if not self.available:
            pytest.skip("scipy not available")
        np.random.seed(42)
        ticker_returns = {
            "NVDA": np.random.normal(0.001, 0.03, 60).tolist(),
            "AVGO": np.random.normal(0.0008, 0.025, 60).tolist(),
        }
        weights = {"NVDA": 0.5, "AVGO": 0.5}
        result = self.engine.compute_portfolio_var(
            run_id="RUN-001",
            ticker_returns=ticker_returns,
            weights=weights,
            confidence_level=0.95,
        )
        assert result.var_pct > 0

    def test_var_99_higher_than_95(self):
        if not self.available:
            pytest.skip("scipy not available")
        np.random.seed(42)
        returns = np.random.normal(0.001, 0.02, 252).tolist()
        var_95 = self.engine.parametric_var(
            "RUN-001", portfolio_returns=returns, confidence_level=0.95
        )
        var_99 = self.engine.parametric_var(
            "RUN-001", portfolio_returns=returns, confidence_level=0.99
        )
        assert var_99.var_pct > var_95.var_pct


# ── Portfolio Optimisation ─────────────────────────────────────────────────


class TestPortfolioOptimisation:
    def setup_method(self):
        self.engine = PortfolioOptimisationEngine()
        np.random.seed(42)
        self.tickers = ["NVDA", "AVGO", "TSM", "EQIX", "CEG"]
        self.returns = {t: np.random.normal(0.001, 0.02, 60).tolist() for t in self.tickers}

    def test_minimum_variance(self):
        result = self.engine.compute_minimum_variance(
            tickers=self.tickers,
            returns=self.returns,
        )
        assert result.method == "min_variance"
        assert abs(sum(result.weights.values()) - 100.0) < 1.0

    def test_max_sharpe(self):
        result = self.engine.compute_max_sharpe(
            tickers=self.tickers,
            returns=self.returns,
        )
        assert result.method == "max_sharpe"
        assert abs(sum(result.weights.values()) - 100.0) < 1.0

    def test_risk_parity(self):
        result = self.engine.compute_risk_parity(
            tickers=self.tickers,
            returns=self.returns,
        )
        assert result.method == "risk_parity"
        assert abs(sum(result.weights.values()) - 100.0) < 1.0

    def test_black_litterman(self):
        bl_inputs = BlackLittermanInputs(
            market_cap_weights={t: 20.0 for t in self.tickers},
            views={"NVDA": 0.02},  # NVDA expected +2% excess
            view_confidences={"NVDA": 0.7},
        )
        result = self.engine.compute_black_litterman(
            tickers=self.tickers,
            returns=self.returns,
            bl_inputs=bl_inputs,
        )
        assert result.method == "black_litterman"
        assert abs(sum(result.weights.values()) - 100.0) < 1.0

    def test_weight_constraints_applied(self):
        result = self.engine.compute_minimum_variance(
            tickers=self.tickers,
            returns=self.returns,
            min_weight=0.05,
            max_weight=0.40,
        )
        for w in result.weights.values():
            assert w >= 5.0 - 1.0  # pct, with tolerance
            assert w <= 40.0 + 1.0
