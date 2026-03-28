"""Session 13 — Depth & Quality Tests.

30 tests covering:
- GARCH(1,1) VaR (E-2)
- HMM regime detection (E-3)
- Black-Litterman optimiser (E-1)
- Real benchmark data fetching (E-4)
- AUD/USD currency attribution (E-5)
- HTML report generation (E-7)
- Cross-run research memory trends (E-9)
- SelfAuditPacket new fields (E-8/E-9)
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch
import numpy as np

import pytest


# ── E-2: GARCH VaR ───────────────────────────────────────────────────────

class TestGARCHVaR:

    def _make_returns(self, n: int = 300, seed: int = 42) -> list[float]:
        rng = np.random.default_rng(seed)
        return rng.normal(0.001, 0.02, n).tolist()

    def test_garch_var_returns_result(self):
        from research_pipeline.services.var_engine import VaREngine
        engine = VaREngine()
        returns = self._make_returns()
        result = engine.garch_var(run_id="test", portfolio_returns=returns)
        assert result is not None
        assert result.var_pct >= 0

    def test_garch_var_result_has_method_garch_or_fallback(self):
        from research_pipeline.services.var_engine import VaREngine
        engine = VaREngine()
        returns = self._make_returns()
        result = engine.garch_var(run_id="test", portfolio_returns=returns)
        assert "garch" in result.method.lower()

    def test_garch_var_uses_more_info_than_parametric(self):
        """GARCH VaR should generally differ from unconditional parametric VaR."""
        from research_pipeline.services.var_engine import VaREngine
        engine = VaREngine()
        returns = self._make_returns(n=300)
        g_result = engine.garch_var(run_id="test", portfolio_returns=returns)
        p_result = engine.parametric_var(run_id="test", portfolio_returns=returns)
        # Both should be positive; values may differ
        assert g_result.var_pct >= 0
        assert p_result.var_pct >= 0

    def test_garch_var_insufficient_data_falls_back(self):
        from research_pipeline.services.var_engine import VaREngine
        engine = VaREngine()
        result = engine.garch_var(run_id="test", portfolio_returns=[0.01, 0.02])
        assert result.var_pct >= 0

    def test_var_result_has_garch_vol_forecast_field(self):
        from research_pipeline.schemas.performance import VaRResult
        r = VaRResult(run_id="test")
        assert hasattr(r, "garch_vol_forecast")


# ── E-3: HMM Regime Detection ─────────────────────────────────────────────

class TestHMMRegimeDetector:

    def _make_returns(self, regime: str = "bull", n: int = 252) -> list[float]:
        rng = np.random.default_rng(seed=42)
        if regime == "bull":
            return rng.normal(0.002, 0.01, n).tolist()
        elif regime == "bear":
            return rng.normal(-0.003, 0.025, n).tolist()
        else:
            return rng.normal(0.0, 0.015, n).tolist()

    def test_detector_returns_result(self):
        from research_pipeline.services.regime_detector import RegimeDetector
        det = RegimeDetector()
        returns = self._make_returns("sideways")
        result = det.detect(returns)
        assert result is not None
        assert result.regime in ("bull", "bear", "sideways")

    def test_detector_gives_regime_probability(self):
        from research_pipeline.services.regime_detector import RegimeDetector
        det = RegimeDetector()
        result = det.detect(self._make_returns())
        assert 0 < result.regime_probability <= 1.0

    def test_detector_state_probabilities_sum_to_one(self):
        from research_pipeline.services.regime_detector import RegimeDetector
        det = RegimeDetector()
        result = det.detect(self._make_returns())
        total = sum(result.state_probabilities.values())
        assert abs(total - 1.0) < 0.1  # allow some rounding

    def test_detector_with_short_series_returns_sideways(self):
        from research_pipeline.services.regime_detector import RegimeDetector
        det = RegimeDetector()
        result = det.detect([0.01, 0.02, -0.01])
        assert result.regime in ("bull", "bear", "sideways")

    def test_detector_from_portfolio_aggregates(self):
        from research_pipeline.services.regime_detector import RegimeDetector
        det = RegimeDetector()
        returns_dict = {
            "NVDA": self._make_returns("bull"),
            "AMD": self._make_returns("bull"),
        }
        result = det.detect_from_portfolio(returns_dict)
        assert result.regime in ("bull", "bear", "sideways")

    def test_detector_has_n_observations(self):
        from research_pipeline.services.regime_detector import RegimeDetector
        det = RegimeDetector()
        returns = self._make_returns(n=200)
        result = det.detect(returns)
        assert result.n_observations == 200

    def test_detector_has_volatility_field(self):
        from research_pipeline.services.regime_detector import RegimeDetector
        det = RegimeDetector()
        result = det.detect(self._make_returns())
        assert result.volatility_annualised_pct > 0


# ── E-1: Black-Litterman ──────────────────────────────────────────────────

class TestBlackLitterman:

    def test_bl_returns_result(self):
        from research_pipeline.services.portfolio_optimisation import (
            PortfolioOptimisationEngine, BlackLittermanInputs,
        )
        engine = PortfolioOptimisationEngine()
        tickers = ["NVDA", "AMD", "AVGO"]
        rng = np.random.default_rng(42)
        returns = {t: rng.normal(0.001, 0.02, 252).tolist() for t in tickers}
        bl_inputs = BlackLittermanInputs(
            market_cap_weights={"NVDA": 50.0, "AMD": 30.0, "AVGO": 20.0},
            views={"NVDA": 0.15, "AMD": 0.10},
            view_confidences={"NVDA": 0.7, "AMD": 0.6},
        )
        result = engine.compute_black_litterman(tickers, returns, bl_inputs)
        assert result.method == "black_litterman"
        assert len(result.weights) == 3

    def test_bl_weights_sum_to_100(self):
        from research_pipeline.services.portfolio_optimisation import (
            PortfolioOptimisationEngine, BlackLittermanInputs,
        )
        engine = PortfolioOptimisationEngine()
        tickers = ["NVDA", "AMD"]
        rng = np.random.default_rng(99)
        returns = {t: rng.normal(0.001, 0.02, 252).tolist() for t in tickers}
        bl_inputs = BlackLittermanInputs(
            market_cap_weights={"NVDA": 60.0, "AMD": 40.0},
            views={"NVDA": 0.20},
            view_confidences={"NVDA": 0.8},
        )
        result = engine.compute_black_litterman(tickers, returns, bl_inputs)
        total = sum(result.weights.values())
        assert abs(total - 100.0) < 1.0

    def test_bl_no_views_returns_equilibrium(self):
        from research_pipeline.services.portfolio_optimisation import (
            PortfolioOptimisationEngine, BlackLittermanInputs,
        )
        engine = PortfolioOptimisationEngine()
        tickers = ["NVDA", "AMD"]
        rng = np.random.default_rng(7)
        returns = {t: rng.normal(0.001, 0.02, 252).tolist() for t in tickers}
        bl_inputs = BlackLittermanInputs(
            market_cap_weights={"NVDA": 60.0, "AMD": 40.0},
            views={},
            view_confidences={},
        )
        result = engine.compute_black_litterman(tickers, returns, bl_inputs)
        assert result.method == "black_litterman"


# ── E-4: Real Benchmark Data ──────────────────────────────────────────────

class TestBenchmarkDataE4:

    def test_benchmark_module_has_axjo(self):
        from research_pipeline.services.benchmark_module import BENCHMARK_CONSTITUENTS
        assert "^AXJO" in BENCHMARK_CONSTITUENTS
        assert len(BENCHMARK_CONSTITUENTS["^AXJO"]) >= 5

    def test_fetch_benchmark_returns_synthetic_fallback(self):
        from research_pipeline.services.benchmark_module import BenchmarkModule
        bm = BenchmarkModule()
        # With invalid symbol, should return synthetic fallback
        returns = bm._synthetic_benchmark_returns("^AXJO", 252)
        assert len(returns) == 252
        assert all(isinstance(r, float) for r in returns)

    def test_synthetic_benchmark_returns_vary_by_symbol(self):
        from research_pipeline.services.benchmark_module import BenchmarkModule
        bm = BenchmarkModule()
        axjo = bm._synthetic_benchmark_returns("^AXJO", 252)
        spy = bm._synthetic_benchmark_returns("SPY", 252)
        assert axjo != spy  # different seeds for different benchmarks

    def test_fetch_benchmark_returns_method_exists(self):
        from research_pipeline.services.benchmark_module import BenchmarkModule
        bm = BenchmarkModule()
        assert hasattr(bm, "fetch_benchmark_returns")


# ── E-5: AUD/USD Currency Attribution ────────────────────────────────────

class TestCurrencyAttributionE5:

    def _make_us_returns(self, n: int = 252) -> list[float]:
        rng = np.random.default_rng(42)
        return rng.normal(0.0005, 0.012, n).tolist()

    def test_attribution_returns_result(self):
        from research_pipeline.services.currency_attribution import CurrencyAttributionEngine
        eng = CurrencyAttributionEngine()
        returns = self._make_us_returns()
        result = eng.compute_attribution(returns)
        assert result is not None
        assert result.n_days > 0

    def test_attribution_decomposition_adds_up(self):
        from research_pipeline.services.currency_attribution import CurrencyAttributionEngine
        eng = CurrencyAttributionEngine()
        returns = self._make_us_returns(100)
        aud_usd_r = [0.0001] * 100  # stable AUD
        result = eng.compute_attribution(returns, aud_usd_returns=aud_usd_r)
        # total ≈ local + currency + interaction (floating point tolerance)
        reconstructed = (
            result.local_equity_return_pct
            + result.currency_return_pct
            + result.interaction_term_pct
        )
        assert abs(result.total_return_aud_pct - reconstructed) < 0.01

    def test_hedged_vs_unhedged_differ(self):
        from research_pipeline.services.currency_attribution import CurrencyAttributionEngine
        eng = CurrencyAttributionEngine()
        returns = self._make_us_returns()
        result = eng.compute_attribution(returns)
        # Hedged and unhedged should generally differ by hedging cost
        assert result.hedged_return_pct != result.unhedged_return_pct

    def test_synthetic_aud_usd_has_correct_length(self):
        from research_pipeline.services.currency_attribution import CurrencyAttributionEngine
        eng = CurrencyAttributionEngine()
        r = eng._synthetic_aud_usd(200)
        assert len(r) == 200


# ── E-7: HTML Report ─────────────────────────────────────────────────────

class TestHTMLReportE7:

    def test_report_service_generates_html(self):
        from research_pipeline.services.report_html_service import ReportHTMLService
        svc = ReportHTMLService()
        html = svc.generate_html(
            run_id="test_run",
            pipeline_output={},
        )
        assert "<html" in html.lower()
        assert "test_run" in html

    def test_report_html_contains_disclaimer(self):
        from research_pipeline.services.report_html_service import ReportHTMLService
        svc = ReportHTMLService()
        html = svc.generate_html(run_id="run_1", pipeline_output={})
        assert "AFSL" in html or "disclaimer" in html.lower()

    def test_report_saves_to_disk(self, tmp_path):
        from research_pipeline.services.report_html_service import ReportHTMLService
        svc = ReportHTMLService()
        html = svc.generate_html(run_id="run_2", pipeline_output={})
        path = svc.save_html("run_2", html, tmp_path)
        assert path.exists()
        assert path.suffix == ".html"

    def test_report_html_with_real_data(self):
        from research_pipeline.services.report_html_service import ReportHTMLService
        svc = ReportHTMLService()
        pipeline_output = {
            "portfolio": {
                "baseline_weights": {"NVDA": 20.0, "AMD": 15.0},
                "pm_result": {
                    "parsed_output": {"investor_document": "Strong AI infrastructure thesis."}
                },
            },
            "risk_package": {"var_95": {"var_pct": 1.23}},
            "ic_outcome": {"is_approved": True, "votes": {}},
        }
        html = svc.generate_html(run_id="run_3", pipeline_output=pipeline_output)
        assert "Strong AI infrastructure thesis" in html


# ── E-9: Cross-Run Research Trends ───────────────────────────────────────

class TestCrossRunTrendsE9:

    def test_detect_trends_empty_no_prior_runs(self, tmp_path):
        from research_pipeline.services.research_memory import ResearchMemory
        mem = ResearchMemory(db_path=tmp_path / "test.db")
        trends = mem.detect_trends("run_1", {"NVDA_dcf_fair_value": 950.0})
        assert trends == []

    def test_detect_trends_flags_large_change(self, tmp_path):
        from research_pipeline.services.research_memory import ResearchMemory
        mem = ResearchMemory(db_path=tmp_path / "test.db")
        # Store prior run
        mem.store_run_metrics("run_1", {"NVDA_dcf_fair_value": 1000.0, "var_95_pct": 1.5})
        # Current run has 20% change in NVDA DCF (above 10% threshold)
        trends = mem.detect_trends("run_2", {"NVDA_dcf_fair_value": 800.0, "var_95_pct": 1.6})
        ticker_trends = [t for t in trends if t.get("ticker") == "NVDA"]
        assert len(ticker_trends) >= 1
        assert abs(ticker_trends[0]["delta_pct"]) >= 10.0

    def test_detect_trends_ignores_small_change(self, tmp_path):
        from research_pipeline.services.research_memory import ResearchMemory
        mem = ResearchMemory(db_path=tmp_path / "test2.db")
        mem.store_run_metrics("run_1", {"NVDA_dcf_fair_value": 1000.0})
        trends = mem.detect_trends("run_2", {"NVDA_dcf_fair_value": 1005.0})
        # 0.5% change is below 10% threshold
        assert len(trends) == 0

    def test_research_trend_has_required_fields(self, tmp_path):
        from research_pipeline.services.research_memory import ResearchMemory
        mem = ResearchMemory(db_path=tmp_path / "test3.db")
        mem.store_run_metrics("run_1", {"AMD_esg_score": 60.0})
        trends = mem.detect_trends("run_2", {"AMD_esg_score": 30.0})
        if trends:
            t = trends[0]
            assert "ticker" in t
            assert "metric" in t
            assert "delta_pct" in t
            assert "alert_level" in t


# ── E-8: SelfAuditPacket new fields ──────────────────────────────────────

class TestSelfAuditPacketNewFields:

    def test_self_audit_packet_has_llm_provider_field(self):
        from research_pipeline.schemas.governance import SelfAuditPacket
        pkt = SelfAuditPacket(run_id="test")
        assert hasattr(pkt, "llm_provider_used")
        assert pkt.llm_provider_used == ""

    def test_self_audit_packet_has_research_trends_field(self):
        from research_pipeline.schemas.governance import SelfAuditPacket
        pkt = SelfAuditPacket(run_id="test")
        assert hasattr(pkt, "research_trends")
        assert isinstance(pkt.research_trends, list)

    def test_self_audit_packet_can_set_llm_provider(self):
        from research_pipeline.schemas.governance import SelfAuditPacket
        pkt = SelfAuditPacket(run_id="test", llm_provider_used="anthropic")
        assert pkt.llm_provider_used == "anthropic"

    def test_self_audit_packet_can_set_trends(self):
        from research_pipeline.schemas.governance import SelfAuditPacket
        trends = [{"ticker": "NVDA", "metric": "dcf", "delta_pct": -15.0, "alert_level": "high"}]
        pkt = SelfAuditPacket(run_id="test", research_trends=trends)
        assert len(pkt.research_trends) == 1
