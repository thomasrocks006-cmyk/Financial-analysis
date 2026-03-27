"""Tests for deterministic services — matching actual implementations."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from research_pipeline.schemas.market_data import MarketSnapshot, ReconciliationStatus
from research_pipeline.schemas.reports import DiffSummary, ScenarioResult


# ── Consensus Reconciliation ───────────────────────────────────────────────

class TestConsensusReconciliation:
    """Tests for the consensus reconciliation service."""

    def _make_service(self):
        """Build service with mock thresholds."""
        from unittest.mock import MagicMock
        from research_pipeline.services.consensus_reconciliation import ConsensusReconciliationService

        thresholds = MagicMock()
        thresholds.price_drift_amber_pct = 0.5
        thresholds.price_drift_red_pct = 2.0
        thresholds.target_divergence_amber_pct = 5.0
        thresholds.target_divergence_red_pct = 15.0
        return ConsensusReconciliationService(thresholds=thresholds)

    def test_classify_green(self):
        svc = self._make_service()
        result = svc._classify(0.3, amber_thr=0.5, red_thr=2.0)
        assert result == ReconciliationStatus.GREEN

    def test_classify_amber(self):
        svc = self._make_service()
        result = svc._classify(1.0, amber_thr=0.5, red_thr=2.0)
        assert result == ReconciliationStatus.AMBER

    def test_classify_red(self):
        svc = self._make_service()
        result = svc._classify(3.0, amber_thr=0.5, red_thr=2.0)
        assert result == ReconciliationStatus.RED

    def test_classify_none_is_missing(self):
        # None diff_pct means both sources absent — must return MISSING, not AMBER,
        # so absent data is distinguishable from a genuine ~5% divergence.
        svc = self._make_service()
        result = svc._classify(None, amber_thr=0.5, red_thr=2.0)
        assert result == ReconciliationStatus.MISSING

    def test_pct_diff(self):
        diff = self._make_service()._pct_diff(100.0, 105.0)
        assert diff is not None
        assert abs(diff - 4.76) < 0.1  # |100-105|/max(100,105)*100

    def test_pct_diff_zero_both(self):
        diff = self._make_service()._pct_diff(0.0, 0.0)
        assert diff == 0.0

    def test_pct_diff_none_input(self):
        diff = self._make_service()._pct_diff(None, 105.0)
        assert diff is None


# ── DCF Engine ─────────────────────────────────────────────────────────────

class TestDCFEngine:
    """Tests for the DCF engine."""

    def _make_assumptions(self):
        from research_pipeline.services.dcf_engine import DCFAssumptions
        return DCFAssumptions(
            ticker="NVDA",
            revenue_base=60e9,
            revenue_growth_rates=[0.30, 0.25, 0.20, 0.15, 0.10],
            ebitda_margin_path=[0.50, 0.48, 0.45, 0.43, 0.40],
            capex_pct_revenue=0.08,
            tax_rate=0.21,
            wacc=0.10,
            terminal_growth=0.03,
            shares_outstanding=24.5e9,
        )

    def test_compute_dcf(self):
        from research_pipeline.services.dcf_engine import DCFEngine
        engine = DCFEngine()
        assumptions = self._make_assumptions()
        result = engine.compute_dcf(assumptions)
        assert result.implied_share_price > 0
        assert result.enterprise_value > 0
        assert result.ticker == "NVDA"
        assert len(result.fcf_projections) == 5

    def test_reverse_dcf(self):
        from research_pipeline.services.dcf_engine import DCFEngine
        engine = DCFEngine()
        implied_growth = engine.reverse_dcf(
            ticker="NVDA",
            current_price=125.0,
            shares_outstanding=24.5e9,
            net_debt=0,
            wacc=0.10,
            terminal_growth=0.03,
            # revenue_base is now required so the search compares real-dollar EVs;
            # NVDA FY2025 revenue ~$130B.
            revenue_base=130e9,
        )
        assert isinstance(implied_growth, float)
        assert -0.10 <= implied_growth <= 0.50

    def test_sensitivity_table(self):
        from research_pipeline.services.dcf_engine import DCFEngine
        engine = DCFEngine()
        assumptions = self._make_assumptions()
        table = engine.sensitivity_table(assumptions, net_debt=0)
        assert len(table.row_values) > 0
        assert len(table.col_values) > 0
        assert len(table.grid) == len(table.row_values)
        assert len(table.grid[0]) == len(table.col_values)

    def test_compute_dcf_wacc_equals_terminal_growth_raises(self):
        """WACC == terminal_growth produces infinite TV; engine must raise, not silently divide by zero."""
        import pytest
        from research_pipeline.services.dcf_engine import DCFAssumptions, DCFEngine
        engine = DCFEngine()
        bad_assumptions = DCFAssumptions(
            ticker="TEST",
            revenue_base=10e9,
            wacc=0.03,
            terminal_growth=0.03,  # equal — division by zero in Gordon Growth formula
            shares_outstanding=1e9,
        )
        with pytest.raises(ValueError, match="WACC"):
            engine.compute_dcf(bad_assumptions)

    def test_compute_dcf_wacc_less_than_terminal_growth_raises(self):
        """WACC < terminal_growth produces a negative TV denominator; must also raise."""
        import pytest
        from research_pipeline.services.dcf_engine import DCFAssumptions, DCFEngine
        engine = DCFEngine()
        bad_assumptions = DCFAssumptions(
            ticker="TEST",
            revenue_base=10e9,
            wacc=0.02,
            terminal_growth=0.04,  # terminal_growth > wacc
            shares_outstanding=1e9,
        )
        with pytest.raises(ValueError, match="WACC"):
            engine.compute_dcf(bad_assumptions)


# ── Scenario Stress Engine ─────────────────────────────────────────────────

class TestScenarioEngine:
    """Tests for the scenario stress engine."""

    def test_built_in_scenarios(self):
        from research_pipeline.services.scenario_engine import ScenarioStressEngine
        engine = ScenarioStressEngine()
        assert len(engine.scenarios) >= 7

    def test_apply_scenario(self):
        from research_pipeline.services.scenario_engine import ScenarioStressEngine
        engine = ScenarioStressEngine()
        results = engine.apply_scenario("ai_capex_slowdown", ["NVDA"])
        assert len(results) == 1
        assert results[0].scenario_name == "AI Capex Slowdown"
        assert results[0].ticker == "NVDA"
        assert results[0].estimated_impact_pct is not None

    def test_apply_scenario_unknown(self):
        from research_pipeline.services.scenario_engine import ScenarioStressEngine
        engine = ScenarioStressEngine()
        results = engine.apply_scenario("nonexistent_scenario", ["NVDA"])
        assert results == []

    def test_run_all_scenarios(self):
        from research_pipeline.services.scenario_engine import ScenarioStressEngine
        engine = ScenarioStressEngine()
        results = engine.run_all_scenarios(["NVDA"])
        assert len(results) >= 7

    def test_high_exposure_amplification(self):
        from research_pipeline.services.scenario_engine import ScenarioStressEngine
        engine = ScenarioStressEngine()
        # NVDA is high_exposure for ai_capex_slowdown (-15% default × 1.5)
        results = engine.apply_scenario("ai_capex_slowdown", ["NVDA"])
        assert results[0].estimated_impact_pct == -22.5

    def test_low_exposure_dampening(self):
        from research_pipeline.services.scenario_engine import ScenarioStressEngine
        engine = ScenarioStressEngine()
        # CEG is low_exposure for ai_capex_slowdown (-15% default × 0.3)
        results = engine.apply_scenario("ai_capex_slowdown", ["CEG"])
        assert results[0].estimated_impact_pct == -4.5

    def test_portfolio_stress_summary(self):
        from research_pipeline.services.scenario_engine import ScenarioStressEngine
        engine = ScenarioStressEngine()
        tickers = ["NVDA", "CEG", "PWR"]
        weights = {"NVDA": 12.5, "CEG": 10.0, "PWR": 10.0}
        summary = engine.portfolio_stress_summary(tickers, weights)
        assert len(summary) >= 7


# ── Golden Test Harness ────────────────────────────────────────────────────

class TestGoldenTests:
    """Tests for the golden test harness."""

    def test_golden_tests_exist(self):
        from research_pipeline.services.golden_tests import GoldenTestHarness
        harness = GoldenTestHarness()
        assert len(harness.tests) >= 5

    def test_run_all_golden_tests(self):
        from research_pipeline.services.golden_tests import GoldenTestHarness
        harness = GoldenTestHarness()
        results = harness.run_all()
        assert results["total"] >= 5
        assert results["passed"] + results["failed"] == results["total"]

    def test_claim_classification_valid_primary_fact(self):
        from research_pipeline.services.golden_tests import GoldenTestHarness
        harness = GoldenTestHarness()
        passed = harness.run_claim_classification_test({
            "claim_text": "Revenue was $35.1B in Q3 FY2025",
            "evidence_class": "primary_fact",
            "source_tier": 1,
        })
        assert passed is True

    def test_claim_classification_guidance_as_primary_fails(self):
        from research_pipeline.services.golden_tests import GoldenTestHarness
        harness = GoldenTestHarness()
        passed = harness.run_claim_classification_test({
            "claim_text": "Management expects 20% growth next year",
            "evidence_class": "primary_fact",
            "source_tier": 1,
        })
        assert passed is False


# ── Run Registry Service ──────────────────────────────────────────────────

class TestRunRegistry:
    """Tests for the run registry service."""

    def test_create_run(self, tmp_path):
        from research_pipeline.services.run_registry import RunRegistryService
        registry = RunRegistryService(tmp_path)
        record = registry.create_run(
            config={"test": True},
            universe=["NVDA", "AVGO"],
        )
        assert record.run_id.startswith("run_")
        assert record.status.value == "initialized"

    def test_update_run_status(self, tmp_path):
        from research_pipeline.services.run_registry import RunRegistryService
        from research_pipeline.schemas.registry import RunStatus
        registry = RunRegistryService(tmp_path)
        record = registry.create_run(config={"test": True}, universe=["NVDA"])
        registry.update_run_status(record.run_id, RunStatus.COMPLETED)
        updated = registry.get_run(record.run_id)
        assert updated is not None
        assert updated.status == RunStatus.COMPLETED

    def test_mark_stage_complete(self, tmp_path):
        from research_pipeline.services.run_registry import RunRegistryService
        registry = RunRegistryService(tmp_path)
        record = registry.create_run(config={"test": True}, universe=["NVDA"])
        registry.mark_stage_complete(record.run_id, 0)
        updated = registry.get_run(record.run_id)
        assert 0 in updated.stages_completed

    def test_list_runs(self, tmp_path):
        from research_pipeline.services.run_registry import RunRegistryService
        registry = RunRegistryService(tmp_path)
        registry.create_run(config={"test": True}, universe=["NVDA"])
        registry.create_run(config={"test": True}, universe=["AVGO"])
        runs = registry.list_runs()
        assert len(runs) == 2


# ── Scheduler Monitoring ──────────────────────────────────────────────────

class TestScheduler:
    """Tests for the scheduler monitoring service."""

    def test_compute_diffs(self):
        from research_pipeline.services.scheduler import SchedulerMonitoringService
        svc = SchedulerMonitoringService()
        previous = [
            MarketSnapshot(ticker="NVDA", source="fmp", price=120.0, trailing_pe=50.0),
        ]
        current = [
            MarketSnapshot(ticker="NVDA", source="fmp", price=130.0, trailing_pe=55.0),
        ]
        diffs = svc.compute_diffs(previous, current)
        assert len(diffs) > 0
        price_diffs = [d for d in diffs if d.field == "price"]
        assert len(price_diffs) == 1
        assert price_diffs[0].change_pct is not None
        assert abs(price_diffs[0].change_pct - 8.33) < 0.1

    def test_generate_alert_log(self):
        from research_pipeline.services.scheduler import SchedulerMonitoringService
        svc = SchedulerMonitoringService()
        diffs = [
            DiffSummary(
                ticker="NVDA", field="price",
                previous_value=120.0, current_value=130.0,
                change_pct=8.33, flagged=True,
            )
        ]
        alerts = svc.generate_alert_log(diffs)
        assert len(alerts) > 0
        assert "NVDA" in alerts[0]

    def test_check_revalidation_needed(self):
        from research_pipeline.services.scheduler import SchedulerMonitoringService
        svc = SchedulerMonitoringService()
        diffs = [
            DiffSummary(ticker="NVDA", field="price", change_pct=12.0, flagged=True),
            DiffSummary(ticker="AVGO", field="price", change_pct=3.0, flagged=False),
        ]
        need_reval = svc.check_revalidation_needed(diffs)
        assert "NVDA" in need_reval
        assert "AVGO" not in need_reval


# ── Data QA & Lineage ────────────────────────────────────────────────────

class TestDataQA:
    """Tests for the data QA & lineage service."""

    def test_check_schema_validity_pass(self):
        from research_pipeline.services.data_qa_lineage import DataQALineageService
        svc = DataQALineageService()
        data = [{"ticker": "NVDA", "timestamp": "2026-03-24", "source": "fmp", "price": 125.0}]
        issues = svc.check_schema_validity(data)
        assert len(issues) == 0

    def test_check_schema_missing_field(self):
        from research_pipeline.services.data_qa_lineage import DataQALineageService
        svc = DataQALineageService()
        data = [{"ticker": "NVDA"}]  # missing timestamp and source
        issues = svc.check_schema_validity(data)
        assert len(issues) > 0

    def test_check_duplicates(self):
        from research_pipeline.services.data_qa_lineage import DataQALineageService
        svc = DataQALineageService()
        data = [
            {"ticker": "NVDA", "source": "fmp", "timestamp": "2026-03-24"},
            {"ticker": "NVDA", "source": "fmp", "timestamp": "2026-03-24"},
        ]
        dupes = svc.check_duplicates(data)
        assert len(dupes) > 0

    def test_check_lineage_pass(self):
        from research_pipeline.services.data_qa_lineage import DataQALineageService
        svc = DataQALineageService(require_lineage=True)
        data = [{"ticker": "NVDA", "source": "fmp"}]
        issues = svc.check_lineage(data)
        assert len(issues) == 0

    def test_check_lineage_missing(self):
        from research_pipeline.services.data_qa_lineage import DataQALineageService
        svc = DataQALineageService(require_lineage=True)
        data = [{"ticker": "NVDA", "source": ""}]
        issues = svc.check_lineage(data)
        assert len(issues) > 0
