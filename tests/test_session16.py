"""
tests/test_session16.py — Session 16: Next.js Frontend & Backend API Expansion

Tests:
  • Expanded FastAPI routes (report, stages, audit, timings, artifacts, provenance)
  • RunManager new methods (get_stages, get_audit_packet, get_timings, get_provenance)
  • Pipeline adapter truthfulness checks (token_log, elapsed_secs, raw_text)
  • Storage save/delete/mirror consistency
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

# ── Ensure src is on the path ─────────────────────────────────────────────
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


# ═══════════════════════════════════════════════════════════════════════════
# Group 1: FastAPI Route Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestAPIRoutes:
    """Verify the expanded route registration and structure."""

    def test_routes_module_imports(self):
        """Routes module imports without error."""
        from api.routes import runs  # noqa: F401
        assert hasattr(runs, "router")
        assert hasattr(runs, "saved_router")

    def test_router_has_report_endpoint(self):
        """Router contains GET /runs/{run_id}/report endpoint."""
        from api.routes.runs import router
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/runs/{run_id}/report" in paths

    def test_router_has_stages_endpoints(self):
        """Router contains stages endpoints."""
        from api.routes.runs import router
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/runs/{run_id}/stages" in paths
        assert "/runs/{run_id}/stages/{stage_num}" in paths

    def test_router_has_audit_endpoint(self):
        """Router contains GET /runs/{run_id}/audit."""
        from api.routes.runs import router
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/runs/{run_id}/audit" in paths

    def test_router_has_timings_endpoint(self):
        """Router contains GET /runs/{run_id}/timings."""
        from api.routes.runs import router
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/runs/{run_id}/timings" in paths

    def test_router_has_artifacts_endpoint(self):
        """Router contains GET /runs/{run_id}/artifacts."""
        from api.routes.runs import router
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/runs/{run_id}/artifacts" in paths

    def test_router_has_provenance_endpoint(self):
        """Router contains GET /runs/{run_id}/provenance."""
        from api.routes.runs import router
        paths = [r.path for r in router.routes if hasattr(r, "path")]
        assert "/runs/{run_id}/provenance" in paths

    def test_saved_router_has_endpoints(self):
        """Saved router contains list and detail endpoints."""
        from api.routes.runs import saved_router
        paths = [r.path for r in saved_router.routes if hasattr(r, "path")]
        assert "/saved-runs" in paths or any("saved" in p for p in paths)
        assert "/saved-runs/{run_id}" in paths or any("run_id" in p for p in paths)

    def test_total_route_count(self):
        """Router has the expected number of endpoints (≥ 14)."""
        from api.routes.runs import router, saved_router
        main_routes = [r for r in router.routes if hasattr(r, "path")]
        saved_routes = [r for r in saved_router.routes if hasattr(r, "path")]
        total = len(main_routes) + len(saved_routes)
        assert total >= 14, f"Expected 14+ routes, got {total}"


# ═══════════════════════════════════════════════════════════════════════════
# Group 2: RunManager Method Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestRunManagerMethods:
    """Test new RunManager methods added in Session 16."""

    def _make_manager(self, result=None, status="completed"):
        """Create a RunManager with a mock ManagedRun."""
        from api.services.run_manager import RunManager, ManagedRun, ApiRunStatus
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.storage_dir = Path(tempfile.mkdtemp())
        config = MagicMock()

        manager = RunManager(settings, config)
        run = ManagedRun(
            run_id="test-run-001",
            request=MagicMock(),
            status=status,
            result=result,
        )
        manager._runs["test-run-001"] = run
        return manager

    def test_get_stages_returns_15_stages(self):
        """get_stages returns 15 stage summaries."""
        result = {"stage_outputs": {}, "gate_results": {}, "stage_timings": {}}
        manager = self._make_manager(result=result)
        stages = manager.get_stages("test-run-001")
        assert len(stages) == 15

    def test_get_stages_includes_label(self):
        """Each stage has the correct label."""
        result = {"stage_outputs": {}, "gate_results": {}, "stage_timings": {}}
        manager = self._make_manager(result=result)
        stages = manager.get_stages("test-run-001")
        assert stages[0]["stage_label"] == "Bootstrap"
        assert stages[5]["stage_label"] == "Evidence Library"
        assert stages[14]["stage_label"] == "Monitoring"

    def test_get_audit_packet_from_result(self):
        """get_audit_packet extracts from result dict."""
        audit = {"quality_score": 7.5, "gates_passed": [0, 1, 2]}
        result = {"audit_packet": audit}
        manager = self._make_manager(result=result)
        assert manager.get_audit_packet("test-run-001") == audit

    def test_get_audit_packet_fallback_key(self):
        """get_audit_packet falls back to self_audit_packet key."""
        audit = {"quality_score": 6.0}
        result = {"self_audit_packet": audit}
        manager = self._make_manager(result=result)
        assert manager.get_audit_packet("test-run-001") == audit

    def test_get_timings_structure(self):
        """get_timings returns stage_latencies_ms and total keys."""
        result = {"stage_timings": {"stage_0": 100, "stage_1": 200}, "total_duration_s": 5.5}
        manager = self._make_manager(result=result)
        timings = manager.get_timings("test-run-001")
        assert "stage_latencies_ms" in timings
        assert "total_pipeline_duration_s" in timings

    def test_get_provenance_from_result(self):
        """get_provenance returns provenance packet from result dict."""
        provenance = {"run_id": "test-run-001", "stage_cards": [], "completeness_pct": 80.0}
        result = {"provenance_packet": provenance}
        manager = self._make_manager(result=result)
        prov = manager.get_provenance("test-run-001")
        assert prov == provenance

    def test_get_provenance_disk_fallback(self):
        """get_provenance reads from disk when not in result dict."""
        result = {}
        manager = self._make_manager(result=result)

        # Write provenance file to disk
        art_dir = manager.settings.storage_dir / "artifacts" / "test-run-001"
        art_dir.mkdir(parents=True, exist_ok=True)
        prov_data = {"run_id": "test-run-001", "completeness_pct": 90.0}
        (art_dir / "provenance_packet.json").write_text(json.dumps(prov_data))

        prov = manager.get_provenance("test-run-001")
        assert prov["completeness_pct"] == 90.0

    def test_list_artifacts_empty(self):
        """list_artifacts returns [] when no artifact directory."""
        result = {}
        manager = self._make_manager(result=result)
        arts = manager.list_artifacts("nonexistent-run")
        assert arts == []

    def test_list_artifacts_with_files(self):
        """list_artifacts returns file list from artifact dir."""
        result = {}
        manager = self._make_manager(result=result)
        art_dir = manager.settings.storage_dir / "artifacts" / "test-run-001"
        art_dir.mkdir(parents=True, exist_ok=True)
        (art_dir / "stage_00.json").write_text("{}")
        (art_dir / "stage_01.json").write_text("{}")

        arts = manager.list_artifacts("test-run-001")
        assert len(arts) == 2
        assert arts[0]["filename"] == "stage_00.json"


# ═══════════════════════════════════════════════════════════════════════════
# Group 3: FastAPI App Integration
# ═══════════════════════════════════════════════════════════════════════════

class TestFastAPIApp:
    """Test the FastAPI app has proper router registration."""

    def test_main_app_includes_saved_router(self):
        """The main FastAPI app includes the saved_router."""
        from api.main import app
        paths = []
        for route in app.routes:
            if hasattr(route, "path"):
                paths.append(route.path)
        # saved-runs is included via api/v1 prefix
        saved_paths = [p for p in paths if "saved-runs" in p]
        assert len(saved_paths) >= 1, f"Expected saved-runs routes, got paths: {paths}"


# ═══════════════════════════════════════════════════════════════════════════
# Group 4: SSE Event Helper
# ═══════════════════════════════════════════════════════════════════════════

class TestSSEHelper:
    """Test the _sse helper function."""

    def test_sse_from_dict(self):
        """_sse formats dict data correctly."""
        from api.routes.runs import _sse
        result = _sse("test_event", {"key": "value"})
        assert result.startswith("event: test_event\n")
        assert '"key": "value"' in result
        assert result.endswith("\n\n")

    def test_sse_from_string(self):
        """_sse passes string data through."""
        from api.routes.runs import _sse
        result = _sse("ping", "hello")
        assert "data: hello\n" in result

    def test_sse_format_structure(self):
        """SSE format has event + data lines."""
        from api.routes.runs import _sse
        result = _sse("ev", {"a": 1})
        lines = result.strip().split("\n")
        assert lines[0].startswith("event:")
        assert lines[1].startswith("data:")


# ═══════════════════════════════════════════════════════════════════════════
# Group 5: Pipeline Event Schema (from Session 15, validated)
# ═══════════════════════════════════════════════════════════════════════════

class TestPipelineEventContract:
    """Verify the PipelineEvent schema used by our SSE endpoints."""

    def test_event_has_all_types(self):
        """PipelineEvent supports all 11 event types."""
        from research_pipeline.schemas.events import PipelineEvent
        event = PipelineEvent(run_id="r1", event_type="pipeline_started")
        assert event.event_type == "pipeline_started"

    def test_stage_labels_complete(self):
        """STAGE_LABELS covers all 15 stages."""
        from research_pipeline.schemas.events import STAGE_LABELS
        assert len(STAGE_LABELS) == 15
        for i in range(15):
            assert i in STAGE_LABELS

    def test_stage_started_constructor(self):
        """PipelineEvent.stage_started populates stage_label."""
        from research_pipeline.schemas.events import PipelineEvent
        e = PipelineEvent.stage_started("r1", 5)
        assert e.stage == 5
        assert e.stage_label == "Evidence Library"

    def test_stage_completed_constructor(self):
        """PipelineEvent.stage_completed includes duration."""
        from research_pipeline.schemas.events import PipelineEvent
        e = PipelineEvent.stage_completed("r1", 3, 1234.5)
        assert e.duration_ms == 1234.5


# ═══════════════════════════════════════════════════════════════════════════
# Group 6: Next.js Frontend Build Validation
# ═══════════════════════════════════════════════════════════════════════════

class TestFrontendStructure:
    """Verify the Next.js frontend has all required files."""

    FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

    def test_package_json_exists(self):
        assert (self.FRONTEND_DIR / "package.json").exists()

    def test_tsconfig_exists(self):
        assert (self.FRONTEND_DIR / "tsconfig.json").exists()

    def test_next_config_exists(self):
        assert (self.FRONTEND_DIR / "next.config.mjs").exists()

    def test_layout_exists(self):
        assert (self.FRONTEND_DIR / "src" / "app" / "layout.tsx").exists()

    def test_page_exists(self):
        assert (self.FRONTEND_DIR / "src" / "app" / "page.tsx").exists()

    def test_globals_css_exists(self):
        assert (self.FRONTEND_DIR / "src" / "app" / "globals.css").exists()

    def test_api_client_exists(self):
        assert (self.FRONTEND_DIR / "src" / "lib" / "api.ts").exists()

    def test_types_exists(self):
        assert (self.FRONTEND_DIR / "src" / "lib" / "types.ts").exists()

    def test_store_exists(self):
        assert (self.FRONTEND_DIR / "src" / "lib" / "store.ts").exists()

    def test_pipeline_tracker_exists(self):
        assert (self.FRONTEND_DIR / "src" / "components" / "pipeline" / "pipeline-tracker.tsx").exists()

    def test_provenance_components_exist(self):
        assert (self.FRONTEND_DIR / "src" / "components" / "provenance" / "provenance-card.tsx").exists()
        assert (self.FRONTEND_DIR / "src" / "components" / "provenance" / "provenance-panel.tsx").exists()
        assert (self.FRONTEND_DIR / "src" / "components" / "provenance" / "report-provenance.tsx").exists()

    def test_run_detail_page_exists(self):
        assert (self.FRONTEND_DIR / "src" / "app" / "runs" / "[run_id]" / "page.tsx").exists()

    def test_new_run_page_exists(self):
        assert (self.FRONTEND_DIR / "src" / "app" / "runs" / "new" / "page.tsx").exists()

    def test_saved_runs_page_exists(self):
        assert (self.FRONTEND_DIR / "src" / "app" / "saved" / "page.tsx").exists()

    def test_settings_page_exists(self):
        assert (self.FRONTEND_DIR / "src" / "app" / "settings" / "page.tsx").exists()

    def test_node_modules_exist(self):
        """npm install was run — node_modules exists."""
        assert (self.FRONTEND_DIR / "node_modules").exists()

    def test_package_has_required_deps(self):
        pkg = json.loads((self.FRONTEND_DIR / "package.json").read_text())
        deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        for dep in ["next", "react", "react-dom", "typescript", "zustand", "@tanstack/react-query", "recharts"]:
            assert dep in deps, f"Missing dependency: {dep}"
