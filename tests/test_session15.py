"""
tests/test_session15.py
-----------------------
Session 15 — FastAPI Event-Streaming API Layer

Covers:
  1. PipelineEvent schema — construction, serialisation, convenience methods
  2. RunRequest schema — validation, defaults, normalisation
  3. RunManager — run lifecycle, event stream generator
  4. FastAPI app — health, root, openapi
  5. FastAPI /api/v1/runs — CRUD + SSE routes
  6. Engine — event callback attribute and _timed_stage emit
"""

from __future__ import annotations

import json
import sys
import os

import pytest

# Ensure src/ is on the path for ``api`` package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ---------------------------------------------------------------------------
# 1. PipelineEvent — schema
# ---------------------------------------------------------------------------


class TestPipelineEventSchema:
    def test_stage_started_convenience(self):
        from research_pipeline.schemas.events import PipelineEvent

        e = PipelineEvent.stage_started("r-001", 5)
        assert e.event_type == "stage_started"
        assert e.stage == 5
        assert e.stage_label == "Evidence Library"
        assert e.run_id == "r-001"

    def test_stage_completed_has_duration(self):
        from research_pipeline.schemas.events import PipelineEvent

        e = PipelineEvent.stage_completed("r-001", 3, 1234.5)
        assert e.event_type == "stage_completed"
        assert e.duration_ms == pytest.approx(1234.5)
        assert e.stage == 3

    def test_stage_failed_has_stage(self):
        from research_pipeline.schemas.events import PipelineEvent

        e = PipelineEvent.stage_failed("r-001", 7, reason="LLM error")
        assert e.event_type == "stage_failed"
        assert e.data["reason"] == "LLM error"

    def test_agent_started(self):
        from research_pipeline.schemas.events import PipelineEvent

        e = PipelineEvent.agent_started("r-001", "ValuationAnalyst", stage=7)
        assert e.event_type == "agent_started"
        assert e.agent_name == "ValuationAnalyst"
        assert e.stage == 7

    def test_agent_completed_has_tokens(self):
        from research_pipeline.schemas.events import PipelineEvent

        e = PipelineEvent.agent_completed("r-001", "ValuationAnalyst", 820.0, tokens_used=512)
        assert e.data["tokens_used"] == 512
        assert e.duration_ms == pytest.approx(820.0)

    def test_llm_call_events(self):
        from research_pipeline.schemas.events import PipelineEvent

        s = PipelineEvent.llm_call_started("r-001", "PM", "claude-sonnet-4-6")
        c = PipelineEvent.llm_call_completed(
            "r-001", "PM", "claude-sonnet-4-6", 600.0, tokens_used=400
        )
        assert s.event_type == "llm_call_started"
        assert c.event_type == "llm_call_completed"
        assert c.data["tokens_used"] == 400

    def test_pipeline_started(self):
        from research_pipeline.schemas.events import PipelineEvent

        e = PipelineEvent.pipeline_started("r-001", ["NVDA", "AMD", "AVGO"])
        assert e.event_type == "pipeline_started"
        assert e.data["ticker_count"] == 3

    def test_pipeline_completed(self):
        from research_pipeline.schemas.events import PipelineEvent

        e = PipelineEvent.pipeline_completed("r-001", 45_000.0)
        assert e.event_type == "pipeline_completed"
        assert e.duration_ms == pytest.approx(45_000.0)

    def test_pipeline_failed_blocked_at(self):
        from research_pipeline.schemas.events import PipelineEvent

        e = PipelineEvent.pipeline_failed("r-001", blocked_at=2)
        assert e.event_type == "pipeline_failed"
        assert e.data["blocked_at"] == 2

    def test_artifact_written(self):
        from research_pipeline.schemas.events import PipelineEvent

        e = PipelineEvent.artifact_written("r-001", "/storage/report.md", "report")
        assert e.event_type == "artifact_written"
        assert "/storage/report.md" in e.data["path"]

    def test_to_sse_data_is_valid_json(self):
        from research_pipeline.schemas.events import PipelineEvent

        e = PipelineEvent.stage_started("r-001", 0)
        raw = e.to_sse_data()
        parsed = json.loads(raw)
        assert parsed["event_type"] == "stage_started"
        assert parsed["run_id"] == "r-001"

    def test_timestamp_is_utc(self):
        from research_pipeline.schemas.events import PipelineEvent

        e = PipelineEvent.pipeline_completed("r-001", 1.0)
        assert e.timestamp.tzinfo is not None

    def test_unknown_stage_label(self):
        from research_pipeline.schemas.events import PipelineEvent

        # Stage 99 doesn't exist in labels
        e = PipelineEvent.stage_started("r-001", 99)
        assert "99" in e.stage_label  # fallback includes the number


# ---------------------------------------------------------------------------
# 2. RunRequest schema
# ---------------------------------------------------------------------------


class TestRunRequestSchema:
    def test_default_universe_is_non_empty(self):
        from research_pipeline.schemas.run_request import RunRequest

        r = RunRequest()
        assert len(r.universe) > 0
        assert "NVDA" in r.universe

    def test_custom_universe_normalised_to_upper(self):
        from research_pipeline.schemas.run_request import RunRequest

        r = RunRequest(universe=["nvda", "amd ", "avgo"])
        assert "NVDA" in r.universe
        assert "AMD" in r.universe
        assert "AVGO" in r.universe

    def test_empty_universe_raises(self):
        from research_pipeline.schemas.run_request import RunRequest

        with pytest.raises(Exception):
            RunRequest(universe=[])

    def test_whitespace_only_tickers_stripped(self):
        from research_pipeline.schemas.run_request import RunRequest

        r = RunRequest(universe=["NVDA", "  "])
        # "  " should be filtered out
        assert all(t.strip() for t in r.universe)
        assert "NVDA" in r.universe

    def test_run_label_stripped(self):
        from research_pipeline.schemas.run_request import RunRequest

        r = RunRequest(universe=["NVDA"], run_label="  My Run  ")
        assert r.run_label == "My Run"

    def test_temperature_bounds(self):
        from research_pipeline.schemas.run_request import RunRequest
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            RunRequest(universe=["NVDA"], llm_temperature=3.0)

    def test_max_positions_bounds(self):
        from research_pipeline.schemas.run_request import RunRequest
        import pydantic

        with pytest.raises(pydantic.ValidationError):
            RunRequest(universe=["NVDA"], max_positions=0)

    def test_to_settings_overrides(self):
        from research_pipeline.schemas.run_request import RunRequest

        r = RunRequest(universe=["NVDA"], llm_model="gemini-1.5-flash", llm_temperature=0.5)
        overrides = r.to_settings_overrides()
        assert overrides["llm_model"] == "gemini-1.5-flash"
        assert overrides["llm_temperature"] == pytest.approx(0.5)

    def test_market_field_defaults_to_us(self):
        from research_pipeline.schemas.run_request import RunRequest

        r = RunRequest(universe=["NVDA"])
        assert r.market == "us"


# ---------------------------------------------------------------------------
# 3. RunManager — lifecycle (no real pipeline execution)
# ---------------------------------------------------------------------------


class TestRunManagerLifecycle:
    @pytest.fixture
    def manager(self, tmp_path):
        from research_pipeline.config.loader import load_pipeline_config
        from research_pipeline.config.settings import Settings
        from api.services.run_manager import RunManager

        s = Settings(storage_dir=tmp_path, prompts_dir=tmp_path / "prompts")
        return RunManager(settings=s, config=load_pipeline_config())

    @pytest.mark.asyncio
    async def test_start_run_returns_run_id(self, manager):
        from research_pipeline.schemas.run_request import RunRequest

        req = RunRequest(universe=["NVDA", "AMD"])
        run_id = await manager.start_run(req)
        assert isinstance(run_id, str)
        assert len(run_id) > 0

    @pytest.mark.asyncio
    async def test_get_run_returns_managed_run(self, manager):
        from research_pipeline.schemas.run_request import RunRequest
        from api.services.run_manager import ManagedRun

        req = RunRequest(universe=["NVDA"])
        run_id = await manager.start_run(req)
        run = manager.get_run(run_id)
        assert run is not None
        assert run.run_id == run_id
        assert isinstance(run, ManagedRun)

    @pytest.mark.asyncio
    async def test_list_runs_includes_started_run(self, manager):
        from research_pipeline.schemas.run_request import RunRequest

        run_id = await manager.start_run(RunRequest(universe=["NVDA"]))
        summaries = manager.list_runs()
        assert any(s["run_id"] == run_id for s in summaries)

    @pytest.mark.asyncio
    async def test_cancel_run(self, manager):
        from research_pipeline.schemas.run_request import RunRequest
        from api.services.run_manager import ApiRunStatus

        run_id = await manager.start_run(RunRequest(universe=["NVDA"]))
        cancelled = manager.cancel_run(run_id)
        assert cancelled is True
        run = manager.get_run(run_id)
        assert run.status == ApiRunStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_delete_run_removes_from_list(self, manager):
        from research_pipeline.schemas.run_request import RunRequest

        run_id = await manager.start_run(RunRequest(universe=["NVDA"]))
        manager.delete_run(run_id)
        assert manager.get_run(run_id) is None

    @pytest.mark.asyncio
    async def test_get_result_none_while_running(self, manager):
        from research_pipeline.schemas.run_request import RunRequest

        run_id = await manager.start_run(RunRequest(universe=["NVDA"]))
        # Immediately after start, result should be None (run not complete yet)
        result = manager.get_result(run_id)
        # Could be None or a dict if engine completes instantly
        assert result is None or isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_run(self, manager):
        cancelled = manager.cancel_run("does-not-exist")
        assert cancelled is False


# ---------------------------------------------------------------------------
# 4. FastAPI app — health / root / openapi
# ---------------------------------------------------------------------------


class TestFastAPIApp:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from api.main import app

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_root_returns_api_name(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "API" in data.get("name", "") or "Research" in data.get("name", "")

    def test_openapi_schema_accessible(self, client):
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert "paths" in schema

    def test_docs_accessible(self, client):
        resp = client.get("/docs")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 5. FastAPI /api/v1/runs — CRUD routes
# ---------------------------------------------------------------------------


class TestRunsRoutes:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from api.main import app

        with TestClient(app, raise_server_exceptions=False) as c:
            yield c

    def test_list_runs_empty(self, client):
        resp = client.get("/api/v1/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert "runs" in data
        assert "count" in data

    def test_start_run_returns_202(self, client):
        payload = {"universe": ["NVDA", "AMD", "AVGO"]}
        resp = client.post("/api/v1/runs", json=payload)
        assert resp.status_code == 202
        data = resp.json()
        assert "run_id" in data
        assert "events_url" in data

    def test_start_run_increments_list(self, client):
        before = client.get("/api/v1/runs").json()["count"]
        client.post("/api/v1/runs", json={"universe": ["NVDA"]})
        after = client.get("/api/v1/runs").json()["count"]
        assert after == before + 1

    def test_get_run_status_after_start(self, client):
        start_resp = client.post("/api/v1/runs", json={"universe": ["NVDA"]})
        run_id = start_resp.json()["run_id"]
        status_resp = client.get(f"/api/v1/runs/{run_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["run_id"] == run_id

    def test_get_nonexistent_run_404(self, client):
        resp = client.get("/api/v1/runs/run_does_not_exist")
        assert resp.status_code == 404

    def test_delete_run(self, client):
        start_resp = client.post("/api/v1/runs", json={"universe": ["NVDA"]})
        run_id = start_resp.json()["run_id"]
        del_resp = client.delete(f"/api/v1/runs/{run_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["deleted"] is True

    def test_delete_nonexistent_404(self, client):
        resp = client.delete("/api/v1/runs/no-such-run")
        assert resp.status_code == 404

    def test_result_202_while_running(self, client):
        start_resp = client.post("/api/v1/runs", json={"universe": ["NVDA"]})
        run_id = start_resp.json()["run_id"]
        result_resp = client.get(f"/api/v1/runs/{run_id}/result")
        # Either 202 (still running) or 200 (if completed instantly in test env)
        assert result_resp.status_code in (200, 202, 404)

    def test_start_run_with_label(self, client):
        payload = {"universe": ["NVDA"], "run_label": "Test Run Session 15"}
        resp = client.post("/api/v1/runs", json=payload)
        assert resp.status_code == 202


# ---------------------------------------------------------------------------
# 6. PipelineEngine — event callback attribute
# ---------------------------------------------------------------------------


class TestEngineEventCallbackWiring:
    @pytest.fixture(scope="class")
    def engine(self, tmp_path_factory):
        from research_pipeline.pipeline.engine import PipelineEngine
        from research_pipeline.config.settings import Settings
        from research_pipeline.config.loader import load_pipeline_config

        tmp = tmp_path_factory.mktemp("engine_s15")
        (tmp / "prompts").mkdir()
        s = Settings(
            storage_dir=tmp,
            prompts_dir=tmp / "prompts",
            llm_model="gemini-1.5-flash",
        )
        return PipelineEngine(s, load_pipeline_config())

    def test_event_callback_attribute_exists(self, engine):
        assert hasattr(engine, "_event_callback")
        assert engine._event_callback is None  # default

    def test_emit_method_exists(self, engine):
        assert hasattr(engine, "_emit")

    @pytest.mark.asyncio
    async def test_emit_does_nothing_with_no_callback(self, engine):
        from research_pipeline.schemas.events import PipelineEvent

        # Should complete without error even when callback is None
        e = PipelineEvent.stage_started("test", 0)
        await engine._emit(e)  # must not raise

    @pytest.mark.asyncio
    async def test_emit_calls_callback(self, engine):
        from research_pipeline.schemas.events import PipelineEvent

        received: list[PipelineEvent] = []

        async def cb(event: PipelineEvent) -> None:
            received.append(event)

        engine._event_callback = cb
        e = PipelineEvent.pipeline_started("test", ["NVDA"])
        await engine._emit(e)
        assert len(received) == 1
        assert received[0].event_type == "pipeline_started"
        # Cleanup
        engine._event_callback = None

    @pytest.mark.asyncio
    async def test_emit_swallows_callback_exception(self, engine):
        from research_pipeline.schemas.events import PipelineEvent

        async def bad_cb(event: PipelineEvent) -> None:
            raise RuntimeError("callback error")

        engine._event_callback = bad_cb
        e = PipelineEvent.stage_started("test", 1)
        # Should NOT raise even though callback throws
        await engine._emit(e)
        engine._event_callback = None
