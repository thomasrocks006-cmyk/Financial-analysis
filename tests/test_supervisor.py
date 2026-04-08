"""Tests for the PipelineSupervisorAgent and retry logic in PipelineEngine."""

from __future__ import annotations

import asyncio

import pytest

from research_pipeline.agents.pipeline_supervisor import (
    PipelineSupervisorAgent,
    StageHealth,
    SupervisorReport,
)
from research_pipeline.pipeline.engine import PipelineEngine


# ── PipelineSupervisorAgent tests ─────────────────────────────────────────


class TestPipelineSupervisorAgent:
    """Unit tests for PipelineSupervisorAgent deterministic health checks."""

    def setup_method(self):
        self.supervisor = PipelineSupervisorAgent(run_id="test-run-001")

    def test_init(self):
        assert self.supervisor.run_id == "test-run-001"
        assert self.supervisor._records == {}

    def test_check_stage_ok(self):
        """Passing stage with complete output is marked OK."""
        record = self.supervisor.check_stage(
            stage_num=0,
            stage_passed=True,
            stage_output={"universe": ["NVDA"], "config_valid": True},
            duration_ms=500,
        )
        assert record.health == StageHealth.OK
        assert record.stage_num == 0
        assert record.issues == []

    def test_check_stage_failed_gate(self):
        """A stage that returns False should be FAILED."""
        record = self.supervisor.check_stage(
            stage_num=2,
            stage_passed=False,
            stage_output=None,
            duration_ms=300,
        )
        assert record.health == StageHealth.FAILED
        assert len(record.issues) > 0

    def test_check_stage_with_exception(self):
        """An exception is properly captured and results in FAILED health."""
        exc = ConnectionError("API connection refused")
        record = self.supervisor.check_stage(
            stage_num=2,
            stage_passed=False,
            stage_output=None,
            duration_ms=100,
            exception=exc,
        )
        assert record.health == StageHealth.FAILED
        assert any("ConnectionError" in issue for issue in record.issues)
        assert len(record.remediation) > 0

    def test_remediation_for_network_error(self):
        """Network errors include connectivity remediation suggestions."""
        exc = TimeoutError("Request timed out after 30s")
        record = self.supervisor.check_stage(
            stage_num=3,
            stage_passed=False,
            stage_output=None,
            exception=exc,
        )
        assert any("timeout" in r.lower() or "network" in r.lower() for r in record.remediation)

    def test_remediation_for_auth_error(self):
        """Auth errors include API key remediation suggestions."""
        exc = Exception("AuthenticationError: 401 Unauthorized")
        record = self.supervisor.check_stage(
            stage_num=5,
            stage_passed=False,
            stage_output=None,
            exception=exc,
        )
        assert any(
            "api key" in r.lower() or "authentication" in r.lower() for r in record.remediation
        )

    def test_degraded_when_required_key_missing(self):
        """Stage 0 output missing required 'config_valid' key is DEGRADED."""
        record = self.supervisor.check_stage(
            stage_num=0,
            stage_passed=True,
            stage_output={"universe": ["NVDA"]},  # missing config_valid
            duration_ms=100,
        )
        assert record.health == StageHealth.DEGRADED
        assert any("config_valid" in issue for issue in record.issues)

    def test_degraded_when_output_is_none(self):
        """A stage that passes but produces None output is DEGRADED."""
        record = self.supervisor.check_stage(
            stage_num=5,
            stage_passed=True,
            stage_output=None,
            duration_ms=200,
        )
        assert record.health == StageHealth.DEGRADED

    def test_slow_stage_warning(self):
        """A stage exceeding the slow threshold gets a timing warning."""
        # Stage 0 threshold is 10,000 ms
        record = self.supervisor.check_stage(
            stage_num=0,
            stage_passed=True,
            stage_output={"universe": ["NVDA"], "config_valid": True},
            duration_ms=25_000,  # well above 10s threshold
        )
        assert any("took" in w for w in record.warnings)

    def test_mark_skipped(self):
        """mark_skipped produces a SKIPPED health record."""
        record = self.supervisor.mark_skipped(stage_num=7)
        assert record.health == StageHealth.SKIPPED
        assert record.stage_num == 7
        assert self.supervisor._records[7] is record

    def test_note_stage_transition_records_planned_non_linear_jump(self):
        """Intentional stage jumps are logged without being treated as unexpected."""
        self.supervisor.note_stage_transition(
            stage_num=8,
            from_stage=6,
            expected_previous_stage=6,
            transition_kind="planned_non_linear",
            note="Stage 8 intentionally runs before Stage 7.",
        )

        report = self.supervisor.build_report()
        assert len(report.transition_log) == 1
        assert report.transition_log[0]["transition_kind"] == "planned_non_linear"
        assert report.unexpected_transitions == []

    def test_current_snapshot_exposes_latest_transition_and_stage_health(self):
        """Live snapshots include latest transition context and last evaluated stage."""
        self.supervisor.note_stage_transition(
            stage_num=0,
            from_stage=None,
            expected_previous_stage=None,
            transition_kind="initial",
            note="Initial bootstrap stage.",
        )
        self.supervisor.check_stage(
            stage_num=0,
            stage_passed=True,
            stage_output={"universe": ["NVDA"], "config_valid": True},
            duration_ms=150,
        )

        snapshot = self.supervisor.current_snapshot()
        assert snapshot["overall_health"] == "ok"
        assert snapshot["latest_transition"]["stage_num"] == 0
        assert snapshot["latest_transition"]["transition_kind"] == "initial"
        assert snapshot["latest_stage_record"]["stage_num"] == 0
        assert snapshot["latest_stage_record"]["health"] == "ok"

    def test_build_report_all_ok(self):
        """Report reflects correctly aggregated counts."""
        stage_outputs = {
            0: {"universe": ["NVDA"], "config_valid": True},
            1: {"universe": ["NVDA"]},
            2: {"data": "something"},
        }
        for s in [0, 1, 2]:
            self.supervisor.check_stage(
                stage_num=s,
                stage_passed=True,
                stage_output=stage_outputs[s],
                duration_ms=100,
            )
        report = self.supervisor.build_report()
        assert isinstance(report, SupervisorReport)
        assert report.stages_checked == 3
        assert report.stages_ok == 3
        assert report.stages_failed == 0
        assert report.overall_health == StageHealth.OK

    def test_build_report_with_failures(self):
        """Report overall health is FAILED when any stage is FAILED."""
        self.supervisor.check_stage(
            stage_num=0,
            stage_passed=True,
            stage_output={"universe": ["NVDA"], "config_valid": True},
            duration_ms=100,
        )
        self.supervisor.check_stage(
            stage_num=2, stage_passed=False, stage_output=None, duration_ms=50
        )
        for s in range(3, 15):
            self.supervisor.mark_skipped(s)
        report = self.supervisor.build_report()
        assert report.overall_health == StageHealth.FAILED
        assert report.stages_failed >= 1
        assert report.stages_skipped >= 1
        assert report.pipeline_interrupted_at == 2
        assert len(report.critical_issues) > 0
        assert len(report.remediation_summary) > 0

    def test_build_report_to_display_dict(self):
        """to_display_dict() returns a dict with the expected keys."""
        self.supervisor.check_stage(
            stage_num=1, stage_passed=True, stage_output={"universe": ["NVDA"]}, duration_ms=100
        )
        report = self.supervisor.build_report()
        d = report.to_display_dict()
        expected_keys = {
            "run_id",
            "overall_health",
            "health_pct",
            "stages_checked",
            "stages_ok",
            "stages_degraded",
            "stages_failed",
            "stages_skipped",
            "critical_issues",
            "all_warnings",
            "remediation_summary",
            "pipeline_interrupted_at",
            "total_duration_ms",
            "stage_records",
        }
        assert expected_keys.issubset(set(d.keys()))

    def test_stage_record_to_dict(self):
        """StageHealthRecord.to_dict() returns serialisable data."""
        record = self.supervisor.check_stage(
            stage_num=3, stage_passed=True, stage_output={"data": 1}, duration_ms=250
        )
        d = record.to_dict()
        assert d["stage_num"] == 3
        assert d["health"] == "ok"
        assert isinstance(d["issues"], list)
        assert isinstance(d["warnings"], list)
        assert isinstance(d["remediation"], list)

    def test_health_pct_all_ok(self):
        stage_outputs = {
            0: {"universe": ["NVDA"], "config_valid": True},
            1: {"universe": ["NVDA"]},
            2: {"data": "something"},
            3: {"data": "something"},
            4: {"data": "something"},
        }
        for s in range(5):
            self.supervisor.check_stage(
                stage_num=s, stage_passed=True, stage_output=stage_outputs[s], duration_ms=100
            )
        report = self.supervisor.build_report()
        assert report.health_pct == 100.0

    def test_health_pct_empty(self):
        """health_pct is 0 when no stages checked."""
        report = self.supervisor.build_report()
        assert report.health_pct == 0.0


# ── PipelineEngine integration tests ─────────────────────────────────────


class TestPipelineEngineErrorHandling:
    """Tests for retry logic and supervisor integration in PipelineEngine."""

    def _make_engine(self):
        import tempfile
        from pathlib import Path

        from research_pipeline.config.loader import load_pipeline_config
        from research_pipeline.config.settings import Settings

        tmpdir = Path(tempfile.mkdtemp())
        settings = Settings(
            storage_dir=tmpdir,
            prompts_dir=tmpdir / "prompts",
            reports_dir=tmpdir / "reports",
        )
        config = load_pipeline_config()
        return PipelineEngine(settings=settings, config=config)

    def test_engine_has_supervisor_attribute(self):
        """Engine should have a supervisor attribute."""
        engine = self._make_engine()
        # Before run, supervisor is None (initialised in run_full_pipeline)
        assert hasattr(engine, "supervisor")
        assert engine.supervisor is None

    def test_is_transient_error_rate_limit(self):
        """RateLimit errors are recognised as transient."""
        assert PipelineEngine._is_transient_error(Exception("RateLimitError: 429"))
        assert PipelineEngine._is_transient_error(Exception("ServiceUnavailable"))
        assert PipelineEngine._is_transient_error(Exception("overloaded"))

    def test_is_transient_error_connection(self):
        """Connection/timeout errors are recognised as transient."""
        assert PipelineEngine._is_transient_error(ConnectionError("connection refused"))
        assert PipelineEngine._is_transient_error(TimeoutError("request timed out"))

    def test_is_not_transient_error_key_error(self):
        """KeyError and ValueError are NOT transient."""
        assert not PipelineEngine._is_transient_error(KeyError("missing_key"))
        assert not PipelineEngine._is_transient_error(ValueError("invalid value"))

    def test_build_failure_return_marks_skipped(self):
        """_build_failure_return marks remaining stages as skipped in supervisor."""
        engine = self._make_engine()
        # Manually bootstrap supervisor
        engine.supervisor = PipelineSupervisorAgent(run_id="test")
        engine.supervisor.check_stage(
            0,
            stage_passed=True,
            stage_output={"universe": ["X"], "config_valid": True},
            duration_ms=100,
        )
        engine.supervisor.check_stage(2, stage_passed=False, stage_output=None, duration_ms=50)

        # Simulate a run_record
        from research_pipeline.schemas.registry import RunRecord, RunStatus

        engine.run_record = RunRecord(run_id="test-run", tickers=["X"], status=RunStatus.RUNNING)

        result = engine._build_failure_return(blocked_at=2, audit_packet=None, total_stages=15)

        assert result["status"] == "failed"
        assert result["blocked_at"] == 2
        assert result["supervisor_report"] is not None
        assert "stages_skipped" in result["supervisor_report"]
        # Stages 3-14 should all be skipped
        skipped = result["supervisor_report"]["stages_skipped"]
        assert skipped >= 12  # stages 3 through 14 = 12 stages

    def test_retry_config_exists(self):
        """Engine has retry configuration constants."""
        assert hasattr(PipelineEngine, "_TRANSIENT_RETRY_ATTEMPTS")
        assert hasattr(PipelineEngine, "_TRANSIENT_RETRY_BACKOFF_BASE")
        assert PipelineEngine._TRANSIENT_RETRY_ATTEMPTS >= 1
        assert PipelineEngine._TRANSIENT_RETRY_BACKOFF_BASE > 0

    def test_timed_stage_propagates_non_transient_exception(self):
        """Non-transient exceptions from _timed_stage propagate immediately."""
        engine = self._make_engine()
        engine.supervisor = PipelineSupervisorAgent(run_id="test")

        from research_pipeline.schemas.registry import RunRecord, RunStatus

        engine.run_record = RunRecord(run_id="test-run", tickers=["X"], status=RunStatus.RUNNING)

        async def _failing_coro():
            raise ValueError("permanent failure")

        with pytest.raises(ValueError, match="permanent failure"):
            asyncio.run(engine._timed_stage(1, _failing_coro()))

        # Supervisor should have recorded a failure for stage 1
        rec = engine.supervisor.get_stage_record(1)
        assert rec is not None
        assert rec.health == StageHealth.FAILED

    def test_supervisor_report_attribute_on_engine(self):
        """Engine stores supervisor report in _supervisor_report attribute."""
        engine = self._make_engine()
        assert hasattr(engine, "_supervisor_report")
        assert engine._supervisor_report is None

    def test_run_with_retry_succeeds_on_first_attempt(self):
        """_run_with_retry returns result when factory succeeds first time."""
        engine = self._make_engine()

        async def _run():
            return await engine._run_with_retry(5, lambda: self._coro_returning("ok"))

        result = asyncio.run(_run())
        assert result == "ok"

    @staticmethod
    async def _coro_returning(value):
        return value

    def test_run_with_retry_retries_on_transient_error(self):
        """_run_with_retry retries on transient errors and succeeds."""
        engine = self._make_engine()
        call_count = [0]

        async def _factory():
            call_count[0] += 1
            if call_count[0] < 2:
                raise Exception("RateLimitError: retry please")
            return "success"

        # Override backoff to 0 for test speed
        original_backoff = PipelineEngine._TRANSIENT_RETRY_BACKOFF_BASE
        PipelineEngine._TRANSIENT_RETRY_BACKOFF_BASE = 0.0
        try:
            result = asyncio.run(engine._run_with_retry(5, _factory, max_attempts=3))
            assert result == "success"
            assert call_count[0] == 2
        finally:
            PipelineEngine._TRANSIENT_RETRY_BACKOFF_BASE = original_backoff

    def test_run_with_retry_raises_non_transient_immediately(self):
        """_run_with_retry does not retry non-transient errors."""
        engine = self._make_engine()
        call_count = [0]

        async def _factory():
            call_count[0] += 1
            raise ValueError("permanent error")

        with pytest.raises(ValueError, match="permanent error"):
            asyncio.run(engine._run_with_retry(5, _factory, max_attempts=3))
        # Should only be called once — no retry for non-transient
        assert call_count[0] == 1
