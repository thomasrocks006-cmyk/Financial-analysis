"""Tests for Phase 6 & 7 new services.

Covers:
  - ETF Overlap Engine (Phase 2.7)
  - Observability Service (Phase 7.5)
  - Universe Config (Phase 7.6)
  - Report Formats (Phase 7.9)
  - SelfAuditPacket schema (Phase 1.10)
  - Scheduler hardening (Phase 7.10)
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import pytest


# ── ETF Overlap Engine ────────────────────────────────────────────────────────

class TestETFOverlapEngine:
    """ETF overlap engine differentiates portfolio from common tech ETFs."""

    def setup_method(self):
        from research_pipeline.services.etf_overlap_engine import ETFOverlapEngine
        self.engine = ETFOverlapEngine()

    def test_analyse_portfolio_returns_report(self):
        weights = {"NVDA": 0.30, "AMD": 0.20, "MSFT": 0.10, "GOOGL": 0.10, "AMZN": 0.10}
        report = self.engine.analyse_portfolio("RUN-001", weights)
        assert report.run_id == "RUN-001"
        assert 0.0 <= report.differentiation_score <= 100.0

    def test_differentiation_score_range(self):
        weights = {"NVDA": 0.5, "MSFT": 0.5}
        report = self.engine.analyse_portfolio("RUN-002", weights)
        assert isinstance(report.differentiation_score, float)

    def test_distinct_portfolio_has_higher_score(self):
        """Portfolio of niche names should be more differentiated than pure mega-cap AI."""
        big_tech_weights = {"NVDA": 0.30, "MSFT": 0.25, "GOOGL": 0.20, "AMZN": 0.15, "AMD": 0.10}
        niche_weights = {"VST": 0.30, "CEG": 0.30, "AES": 0.20, "MRVL": 0.20}

        big_report = self.engine.analyse_portfolio("RUN-A", big_tech_weights)
        niche_report = self.engine.analyse_portfolio("RUN-B", niche_weights)

        # Niche names should score higher differentiation (less ETF overlap)
        assert niche_report.differentiation_score >= big_report.differentiation_score

    def test_overlap_summary_returns_string(self):
        weights = {"NVDA": 0.5, "MSFT": 0.5}
        report = self.engine.analyse_portfolio("RUN-003", weights)
        summary = self.engine.get_overlap_summary(report)
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_flag_etf_replication_returns_bool(self):
        weights = {"NVDA": 0.30, "MSFT": 0.25, "GOOGL": 0.20, "AMD": 0.15, "AMZN": 0.10}
        report = self.engine.analyse_portfolio("RUN-004", weights)
        flag = self.engine.flag_etf_replication(report)
        assert isinstance(flag, bool)

    def test_to_dict_serialisable(self):
        weights = {"NVDA": 0.5, "MSFT": 0.5}
        report = self.engine.analyse_portfolio("RUN-005", weights)
        d = report.to_dict()
        # Must be JSON-serialisable
        json_str = json.dumps(d)
        reparsed = json.loads(json_str)
        assert reparsed["run_id"] == "RUN-005"

    def test_empty_portfolio(self):
        report = self.engine.analyse_portfolio("RUN-006", {})
        assert report.differentiation_score == 100.0   # empty = maximally distinct

    def test_default_etfs_analysed(self):
        from research_pipeline.services.etf_overlap_engine import ETFOverlapEngine
        engine = ETFOverlapEngine()
        weights = {"NVDA": 1.0}
        report = engine.analyse_portfolio("RUN-007", weights)
        # At minimum XLK and SOXX cover NVDA
        assert len(report.etf_overlaps) >= 1


# ── Observability Service ─────────────────────────────────────────────────────

class TestObservabilityService:
    """Observability service tracks stage metrics and cost per run."""

    def setup_method(self):
        from research_pipeline.services.observability import ObservabilityService
        self.tmp = tempfile.mkdtemp()
        self.obs = ObservabilityService(output_dir=Path(self.tmp))

    def test_start_and_end_run(self):
        from research_pipeline.services.observability import RunObservability
        run = self.obs.start_run("RUN-001")
        assert run.run_id == "RUN-001"
        assert run.started_at is not None

        ended = self.obs.end_run("RUN-001")
        assert ended.completed_at is not None
        assert ended.total_duration_seconds >= 0.0

    def test_stage_metrics_recorded(self):
        self.obs.start_run("RUN-002")
        stage = self.obs.start_stage("RUN-002", 5, "Evidence Librarian")
        assert stage.stage == 5
        assert stage.stage_name == "Evidence Librarian"

        completed = self.obs.end_stage(
            "RUN-002", 5, success=True,
            llm_input_tokens=1000, llm_output_tokens=500,
            llm_model="claude-opus-4-6",
        )
        assert completed.success is True
        assert completed.llm_input_tokens == 1000

    def test_cost_calculation(self):
        self.obs.start_run("RUN-003")
        self.obs.start_stage("RUN-003", 5, "Evidence")
        stage = self.obs.end_stage(
            "RUN-003", 5, success=True,
            llm_input_tokens=10_000, llm_output_tokens=2_000,
            llm_model="claude-opus-4-6",
        )
        assert stage.llm_cost_usd > 0, "Cost should be non-zero for claude-opus-4-6"

    def test_save_creates_json_file(self):
        self.obs.start_run("RUN-004")
        self.obs.start_stage("RUN-004", 1, "Universe")
        self.obs.end_stage("RUN-004", 1, success=True)
        self.obs.end_run("RUN-004")

        path = self.obs.save("RUN-004")
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["run_id"] == "RUN-004"

    def test_failed_stage_tracked(self):
        self.obs.start_run("RUN-005")
        self.obs.start_stage("RUN-005", 3, "Reconciliation")
        self.obs.end_stage("RUN-005", 3, success=False)
        run = self.obs.end_run("RUN-005")
        assert 3 in run.failed_stages

    def test_summary_table_returns_string(self):
        self.obs.start_run("RUN-006")
        self.obs.start_stage("RUN-006", 1, "Bootstrap")
        self.obs.end_stage("RUN-006", 1, success=True)
        self.obs.end_run("RUN-006")
        table = self.obs.summary_table("RUN-006")
        assert isinstance(table, str)
        assert "Bootstrap" in table

    def test_all_runs_summary_includes_completed_runs(self):
        self.obs.start_run("RUN-007")
        self.obs.end_run("RUN-007")
        summary = self.obs.all_runs_summary()
        run_ids = [r["run_id"] for r in summary]
        assert "RUN-007" in run_ids


# ── Universe Config ────────────────────────────────────────────────────────────

class TestUniverseConfig:
    """Universe config provides correct ticker lists."""

    def test_ai_infrastructure_universe_returns_list(self):
        from research_pipeline.config.universe_config import get_universe
        tickers = get_universe("ai_infrastructure")
        assert isinstance(tickers, list)
        assert len(tickers) >= 14
        assert "NVDA" in tickers

    def test_global_tech_universe_larger_than_ai_infra(self):
        from research_pipeline.config.universe_config import get_universe
        ai = get_universe("ai_infrastructure")
        gt = get_universe("global_tech")
        assert len(gt) > len(ai)

    def test_unknown_universe_raises_key_error(self):
        from research_pipeline.config.universe_config import get_universe
        with pytest.raises(KeyError, match="Unknown universe"):
            get_universe("nonexistent_universe")

    def test_list_universes_returns_all_registered(self):
        from research_pipeline.config.universe_config import list_universes
        universes = list_universes()
        assert "ai_infrastructure" in universes
        assert "global_tech" in universes
        assert "fixed_income" in universes

    def test_get_subtheme_map_returns_dict(self):
        from research_pipeline.config.universe_config import get_subtheme_map
        themes = get_subtheme_map("ai_infrastructure")
        assert "ai_chips" in themes
        assert "NVDA" in themes["ai_chips"]

    def test_get_subtheme_specific(self):
        from research_pipeline.config.universe_config import get_subtheme
        chips = get_subtheme("ai_infrastructure", "ai_chips")
        assert "NVDA" in chips

    def test_unknown_subtheme_raises_key_error(self):
        from research_pipeline.config.universe_config import get_subtheme
        with pytest.raises(KeyError, match="Unknown subtheme"):
            get_subtheme("ai_infrastructure", "nonexistent")

    def test_ticker_to_subtheme(self):
        from research_pipeline.config.universe_config import ticker_to_subtheme
        theme = ticker_to_subtheme("NVDA", "ai_infrastructure")
        assert theme == "ai_chips"

    def test_ticker_not_in_universe_returns_none(self):
        from research_pipeline.config.universe_config import ticker_to_subtheme
        theme = ticker_to_subtheme("XYZ", "ai_infrastructure")
        assert theme is None

    def test_get_universe_returns_copy(self):
        """Mutating the returned list should not affect the registry."""
        from research_pipeline.config.universe_config import get_universe
        tickers = get_universe("ai_infrastructure")
        original_len = len(tickers)
        tickers.append("FAKE")
        tickers2 = get_universe("ai_infrastructure")
        assert len(tickers2) == original_len


# ── Report Formats ─────────────────────────────────────────────────────────────

class TestReportFormatService:
    """Report format service renders three output formats."""

    def setup_method(self):
        from research_pipeline.services.report_formats import ReportFormatService, ReportFormat
        self.tmp = tempfile.mkdtemp()
        self.service = ReportFormatService(output_dir=Path(self.tmp))
        self.ReportFormat = ReportFormat
        self.run_id = "RUN-FMT-001"
        self.pipeline_output = {
            "final_report": {
                "title": "Test Report",
                "portfolio_summary": "Concentrated AI infrastructure portfolio.",
                "key_risks": ["Regulatory risk", "Competition"],
                "publication_status": "DRAFT",
                "authors": ["Test Author"],
            },
            "portfolio": {
                "variant": "CONCENTRATED",
                "positions": [
                    {"ticker": "NVDA", "weight": 0.25, "sector": "semis", "thesis_sentence": "AI chip leader"},
                    {"ticker": "MSFT", "weight": 0.20, "sector": "cloud"},
                ],
                "cash_weight": 0.05,
            },
            "risk_package": {
                "var_95": {"portfolio": "-2.1%"},
                "var_99": {"portfolio": "-3.4%"},
                "factor_exposures": {"momentum": {"portfolio": 0.8}},
                "max_drawdown_estimate": "-22%",
            },
            "ic_outcome": {
                "decision": "APPROVED",
                "rationale": "Strong conviction in AI buildout theme.",
                "vote_breakdown": {"for": 4, "against": 1},
            },
            "mandate_result": {"is_compliant": True, "violations": []},
        }

    def test_executive_summary_render(self):
        rendered = self.service.render(self.run_id, self.pipeline_output, "executive_summary")
        assert "AI INFRASTRUCTURE" in rendered.content
        assert "NVDA" in rendered.content
        assert rendered.format_type.value == "executive_summary"

    def test_institutional_pdf_returns_valid_json(self):
        rendered = self.service.render(self.run_id, self.pipeline_output, "institutional_pdf")
        doc = json.loads(rendered.content)
        assert doc["document_type"] == "JPAM_RESEARCH_REPORT"
        assert doc["metadata"]["run_id"] == self.run_id
        assert "sections" in doc

    def test_factsheet_render(self):
        rendered = self.service.render(self.run_id, self.pipeline_output, "factsheet")
        assert "WEIGHTS" in rendered.content
        assert "NVDA" in rendered.content

    def test_render_all_returns_three_formats(self):
        all_rendered = self.service.render_all(self.run_id, self.pipeline_output)
        assert len(all_rendered) == 3

    def test_save_creates_files(self):
        paths = self.service.save_all(self.run_id, self.pipeline_output)
        assert len(paths) == 3
        for p in paths:
            assert p.exists()

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            self.service.render(self.run_id, self.pipeline_output, "unsupported_format")


# ── SelfAuditPacket ────────────────────────────────────────────────────────────

class TestSelfAuditPacket:
    """SelfAuditPacket schema collects audit evidence and scores quality."""

    def setup_method(self):
        from research_pipeline.schemas.governance import SelfAuditPacket
        self.SelfAuditPacket = SelfAuditPacket

    def _make_packet(self, **overrides):
        defaults = {
            "run_id": "RUN-AUDIT-001",
            "total_claims": 30,
            "tier1_claims": 15,
            "tier2_claims": 10,
            "tier3_claims": 4,
            "tier4_claims": 1,
            "pass_claims": 25,
            "caveat_claims": 3,
            "fail_claims": 2,
            "methodology_tags_present": True,
            "dates_complete": True,
            "source_hygiene_score": 8.5,
            "agents_succeeded": ["evidence_librarian", "valuation_analyst"],
            "agents_failed": [],
            "total_retries": 2,
            "gates_passed": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13],
            "gates_failed": [],
            "tickers_with_red_team": ["NVDA", "AMD", "MSFT", "GOOGL"],
            "min_falsification_tests": 3,
            "ic_approved": True,
            "ic_vote_breakdown": {"analyst_a": "FOR", "analyst_b": "FOR"},
            "mandate_compliant": True,
            "esg_exclusions": [],
        }
        defaults.update(overrides)
        return self.SelfAuditPacket(**defaults)

    def test_packet_instantiation(self):
        pkt = self._make_packet()
        assert pkt.run_id == "RUN-AUDIT-001"

    def test_tier1_2_pct_calculation(self):
        pkt = self._make_packet(
            total_claims=100, tier1_claims=60, tier2_claims=20,
            tier3_claims=15, tier4_claims=5,
        )
        # 80% should be tier 1/2
        assert pkt.tier1_2_pct == pytest.approx(80.0)

    def test_tier1_2_pct_zero_when_no_claims(self):
        pkt = self._make_packet(total_claims=0, tier1_claims=0, tier2_claims=0)
        assert pkt.tier1_2_pct == 0.0

    def test_quality_score_returns_float(self):
        pkt = self._make_packet()
        score = pkt.compute_quality_score()
        assert 0.0 <= score <= 10.0

    def test_high_quality_packet_scores_above_7(self):
        pkt = self._make_packet(
            total_claims=100, tier1_claims=70, tier2_claims=20,
            tier3_claims=8, tier4_claims=2,
            pass_claims=100, fail_claims=0, caveat_claims=0,
            agents_failed=[],
            total_retries=0,
            gates_failed=[],
            ic_approved=True,
            mandate_compliant=True,
            methodology_tags_present=True,
            dates_complete=True,
            min_falsification_tests=4,
        )
        score = pkt.compute_quality_score()
        assert score >= 7.0, f"Expected high-quality score >= 7, got {score}"

    def test_poor_quality_packet_scores_below_5(self):
        pkt = self._make_packet(
            total_claims=100, tier1_claims=10, tier2_claims=10,
            tier3_claims=50, tier4_claims=30,
            pass_claims=40, fail_claims=40, caveat_claims=20,
            agents_failed=["agent_a", "agent_b", "agent_c"],
            total_retries=15,
            gates_failed=[5, 9, 11],
            ic_approved=False,
            mandate_compliant=False,
        )
        score = pkt.compute_quality_score()
        assert score < 6.0, f"Expected poor-quality score < 6, got {score}"


# ── Scheduler Hardening ───────────────────────────────────────────────────────

class TestSchedulerHardening:
    """Phase 7.10 scheduler hardening tests."""

    def setup_method(self):
        from research_pipeline.services.scheduler import SchedulerMonitoringService
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.state_path = self.tmp_dir / "state.json"
        self.scheduler = SchedulerMonitoringService(state_path=self.state_path)

    def test_not_ran_today_initially(self):
        assert self.scheduler.already_ran_today() is False

    def test_mark_run_completed_persists(self):
        self.scheduler.mark_run_completed("RUN-SCH-001")
        assert self.scheduler.already_ran_today() is True

    def test_state_file_created(self):
        self.scheduler.mark_run_completed("RUN-SCH-002")
        assert self.state_path.exists()
        data = json.loads(self.state_path.read_text())
        assert data["last_successful_run_id"] == "RUN-SCH-002"

    def test_get_last_run_id(self):
        self.scheduler.mark_run_completed("RUN-SCH-003")
        assert self.scheduler.get_last_run_id() == "RUN-SCH-003"

    @pytest.mark.asyncio
    async def test_run_with_alert_success_marks_completed(self):
        async def fake_pipeline(run_id: str):
            return {"status": "completed"}

        result = await self.scheduler.run_with_alert(
            fake_pipeline, "RUN-SCH-004", skip_if_already_ran=False
        )
        assert result == {"status": "completed"}
        assert self.scheduler.already_ran_today() is True

    @pytest.mark.asyncio
    async def test_run_with_alert_calls_alert_fn_on_failure(self):
        alerts_fired = []

        async def fake_pipeline(run_id: str):
            raise RuntimeError("pipeline failure")

        async def fake_alert(run_id: str, exc: Exception):
            alerts_fired.append((run_id, str(exc)))

        with pytest.raises(RuntimeError, match="pipeline failure"):
            await self.scheduler.run_with_alert(
                fake_pipeline, "RUN-SCH-005",
                alert_fn=fake_alert, skip_if_already_ran=False,
            )

        assert len(alerts_fired) == 1
        assert alerts_fired[0][0] == "RUN-SCH-005"

    @pytest.mark.asyncio
    async def test_skip_if_already_ran(self):
        self.scheduler.mark_run_completed("RUN-SCH-006")

        called = []

        async def fake_pipeline(run_id: str):
            called.append(run_id)
            return {"status": "completed"}

        result = await self.scheduler.run_with_alert(
            fake_pipeline, "RUN-SCH-006", skip_if_already_ran=True
        )
        assert result is None
        assert not called, "Pipeline should not have been called — already ran today"

    def test_watchlist_trigger_price_move(self):
        from research_pipeline.schemas.reports import DiffSummary
        diffs = [
            DiffSummary(ticker="NVDA", field="price", previous_value=100, current_value=108, change_pct=8.0, flagged=True),
            DiffSummary(ticker="MSFT", field="price", previous_value=300, current_value=301, change_pct=0.3, flagged=False),
        ]
        triggered = self.scheduler.check_watchlist_triggers(
            diffs, watchlist=["NVDA", "MSFT"], trigger_pct=5.0
        )
        assert "NVDA" in triggered
        assert "MSFT" not in triggered

    def test_watchlist_trigger_no_price_diff_ignored(self):
        from research_pipeline.schemas.reports import DiffSummary
        # Field is 'trailing_pe', not 'price' — should not trigger
        diffs = [
            DiffSummary(ticker="NVDA", field="trailing_pe", previous_value=50, current_value=60, change_pct=20.0, flagged=True),
        ]
        triggered = self.scheduler.check_watchlist_triggers(diffs, watchlist=["NVDA"])
        assert "NVDA" not in triggered
