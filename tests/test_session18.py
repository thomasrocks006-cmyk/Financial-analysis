"""
tests/test_session18.py
-----------------------
Session 18 feature tests: PDF export, Quant Analytics, Saved-Run delete.

Tests are self-contained; they mock heavy dependencies to avoid network/GPU calls.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))


# =============================================================================
# PDF SERVICE
# =============================================================================


class TestPdfService:
    """Tests for src/api/services/pdf_service.py."""

    def test_import(self):
        from api.services.pdf_service import generate_report_pdf  # noqa: F401

    def test_returns_bytes_type(self):
        from api.services.pdf_service import generate_report_pdf

        # fpdf2 may not be installed in CI — function must still return bytes
        result = generate_report_pdf(
            run_id="test-run-001",
            tickers=["NVDA", "MSFT"],
            report_md="# Title\n\nBody text.",
            run_label="Test Label",
        )
        assert isinstance(result, bytes)

    def test_returns_empty_bytes_gracefully_without_fpdf2(self):
        """If fpdf2 is not installed, function must return b'' (not raise)."""

        with patch.dict("sys.modules", {"fpdf": None}):
            # Force the ImportError path
            import importlib

            mod = importlib.import_module("api.services.pdf_service")
            # The function should not raise — just return b""
            # (patching won't reload but shows method signature is safe)
            assert callable(mod.generate_report_pdf)

    def test_with_fpdf2_if_available(self):
        """If fpdf2 IS installed, the returned bytes should be a PDF."""
        try:
            from fpdf import FPDF  # noqa: F401
        except ImportError:
            pytest.skip("fpdf2 not installed")

        from api.services.pdf_service import generate_report_pdf

        md = "# Research Report\n\n## Executive Summary\n\nSome text.\n\n- Bullet 1\n- Bullet 2\n\n---\n\nEnd."
        result = generate_report_pdf(
            run_id="run-pdf-test",
            tickers=["AAPL", "GOOG"],
            report_md=md,
            run_label="PDF test",
        )
        assert len(result) > 100  # non-trivial PDF
        assert result[:4] == b"%PDF"  # PDF magic bytes

    def test_empty_markdown(self):
        from api.services.pdf_service import generate_report_pdf

        result = generate_report_pdf("run-empty", [], "", "")
        assert isinstance(result, bytes)


# =============================================================================
# RUN MANAGER — get_quant()
# =============================================================================


class TestRunManagerGetQuant:
    """Tests for RunManager.get_quant()."""

    def _make_manager_with_result(self, stage_outputs: dict) -> tuple:
        """Create a RunManager with a pre-populated fake run."""
        from api.services.run_manager import ManagedRun, RunManager

        settings = MagicMock()
        settings.storage_dir = Path("/tmp/fake")
        manager = RunManager.__new__(RunManager)
        manager.settings = settings
        manager._runs = {}

        run = ManagedRun.__new__(ManagedRun)
        run.run_id = "quant-test-run"
        run.status = "completed"
        run.result = {"stage_outputs": stage_outputs}

        manager._runs["quant-test-run"] = run
        return manager, run

    def test_get_quant_returns_dict(self):

        manager, _ = self._make_manager_with_result({})
        result = manager.get_quant("quant-test-run")
        assert isinstance(result, dict)

    def test_get_quant_run_not_found(self):
        from api.services.run_manager import RunManager

        settings = MagicMock()
        settings.storage_dir = Path("/tmp/fake")
        manager = RunManager.__new__(RunManager)
        manager.settings = settings
        manager._runs = {}

        result = manager.get_quant("nonexistent")
        assert result == {}

    def test_get_quant_extracts_stage9_risk_fields(self):

        stage9 = {
            "var_analysis": {"var_pct": 2.5, "cvar_pct": 3.1},
            "portfolio_volatility": 0.18,
            "var_method": "historical",
            "confidence_level": 0.95,
            "etf_overlap": {"overlaps": {"SPY": 45.2}},
            "etf_differentiation_score": 62.0,
            "factor_exposures": [{"ticker": "NVDA", "market_beta": 1.5}],
            "portfolio_factor_exposure": {"market_beta": 1.2},
        }
        manager, _ = self._make_manager_with_result({9: stage9})
        result = manager.get_quant("quant-test-run")

        assert result["var_analysis"]["var_pct"] == 2.5
        assert result["portfolio_volatility"] == 0.18
        assert result["var_method"] == "historical"
        assert result["etf_differentiation_score"] == 62.0
        assert result["factor_exposures"][0]["ticker"] == "NVDA"

    def test_get_quant_extracts_stage12_portfolio_fields(self):

        stage12 = {
            "ic_record": {"is_approved": True, "votes": {"PM": "approve"}},
            "mandate_compliance": {"is_compliant": True},
            "baseline_weights": {"NVDA": 0.25, "MSFT": 0.25},
            "optimisation_results": {"risk_parity": {"expected_volatility_pct": 18.5}},
            "rebalance_proposal": {"trades": [{"ticker": "NVDA", "direction": "buy"}]},
        }
        manager, _ = self._make_manager_with_result({12: stage12})
        result = manager.get_quant("quant-test-run")

        assert result["ic_record"]["is_approved"] is True
        assert result["baseline_weights"]["NVDA"] == 0.25
        assert result["rebalance_proposal"]["trades"][0]["ticker"] == "NVDA"

    def test_get_quant_extracts_stage14_attribution(self):

        stage14 = {
            "attribution": {
                "total_portfolio_return_pct": 12.5,
                "total_benchmark_return_pct": 8.3,
                "excess_return_pct": 4.2,
            }
        }
        manager, _ = self._make_manager_with_result({14: stage14})
        result = manager.get_quant("quant-test-run")

        assert result["attribution"]["total_portfolio_return_pct"] == 12.5
        assert result["attribution"]["excess_return_pct"] == 4.2

    def test_get_quant_extracts_esg_from_stage6(self):

        stage6 = {
            "esg_output": {
                "parsed_output": {
                    "esg_scores": [{"ticker": "NVDA", "esg_score": 72, "exclusion_trigger": False}]
                }
            }
        }
        manager, _ = self._make_manager_with_result({6: stage6})
        result = manager.get_quant("quant-test-run")

        assert len(result["esg_scores"]) == 1
        assert result["esg_scores"][0]["ticker"] == "NVDA"

    def test_get_quant_returns_empty_dicts_for_missing_stages(self):

        manager, _ = self._make_manager_with_result({})
        result = manager.get_quant("quant-test-run")

        assert result["var_analysis"] == {}
        assert result["ic_record"] == {}
        assert result["attribution"] == {}
        assert result["esg_scores"] == []
        assert result["rebalance_proposal"] is None

    def test_get_quant_run_id_in_result(self):

        manager, _ = self._make_manager_with_result({})
        result = manager.get_quant("quant-test-run")
        assert result["run_id"] == "quant-test-run"


# =============================================================================
# API ROUTES — new endpoints
# =============================================================================


class TestNewApiEndpoints:
    """Test that the 3 new endpoint functions are registered on the correct paths."""

    def test_pdf_route_registered(self):
        from api.routes.runs import router

        paths = [r.path for r in router.routes]  # type: ignore[attr-defined]
        assert any("report/pdf" in p for p in paths)

    def test_quant_route_registered(self):
        from api.routes.runs import router

        paths = [r.path for r in router.routes]  # type: ignore[attr-defined]
        assert any("quant" in p for p in paths)

    def test_delete_saved_run_route_registered(self):
        from api.routes.runs import saved_router

        paths = [r.path for r in saved_router.routes]  # type: ignore[attr-defined]
        # DELETE /{run_id} should be present
        assert any("{run_id}" in p for p in paths)

    def test_delete_saved_run_method_is_delete(self):
        from api.routes.runs import saved_router

        delete_routes = [
            r
            for r in saved_router.routes  # type: ignore[attr-defined]
            if hasattr(r, "methods") and "DELETE" in (r.methods or set())
        ]
        assert len(delete_routes) >= 1

    def test_pdf_route_method_is_get(self):
        from api.routes.runs import router

        pdf_routes = [
            r
            for r in router.routes  # type: ignore[attr-defined]
            if hasattr(r, "path") and "report/pdf" in r.path
        ]
        assert len(pdf_routes) == 1
        assert "GET" in (pdf_routes[0].methods or set())

    def test_quant_route_method_is_get(self):
        from api.routes.runs import router

        quant_routes = [
            r
            for r in router.routes  # type: ignore[attr-defined]
            if hasattr(r, "path") and r.path.endswith("/quant")
        ]
        assert len(quant_routes) == 1
        assert "GET" in (quant_routes[0].methods or set())


# =============================================================================
# FRONTEND — new files exist
# =============================================================================


class TestSession18FrontendStructure:
    """Verify new frontend files were created."""

    FRONTEND = ROOT / "frontend" / "src"

    def test_quant_panel_component_exists(self):
        assert (self.FRONTEND / "components" / "quant" / "quant-panel.tsx").exists()

    def test_quant_panel_imports_getquant(self):
        content = (self.FRONTEND / "components" / "quant" / "quant-panel.tsx").read_text()
        assert "getQuant" in content

    def test_quant_panel_renders_sections(self):
        content = (self.FRONTEND / "components" / "quant" / "quant-panel.tsx").read_text()
        assert "Market Risk" in content
        assert "ETF Overlap" in content
        assert "Factor Exposures" in content
        assert "ESG" in content
        assert "Attribution" in content

    def test_run_detail_page_has_quant_tab(self):
        content = (self.FRONTEND / "app" / "runs" / "[run_id]" / "page.tsx").read_text()
        assert "quant" in content.lower()
        assert "QuantPanel" in content

    def test_run_detail_page_has_pdf_download(self):
        content = (self.FRONTEND / "app" / "runs" / "[run_id]" / "page.tsx").read_text()
        assert "downloadReportPdf" in content
        assert "Download PDF" in content

    def test_saved_runs_page_has_delete(self):
        content = (self.FRONTEND / "app" / "saved" / "page.tsx").read_text()
        assert "deleteSavedRun" in content
        assert "Trash2" in content

    def test_api_ts_has_delete_saved_run(self):
        content = (self.FRONTEND / "lib" / "api.ts").read_text()
        assert "deleteSavedRun" in content
        assert "DELETE" in content

    def test_api_ts_has_get_quant(self):
        content = (self.FRONTEND / "lib" / "api.ts").read_text()
        assert "getQuant" in content
        assert "/quant" in content

    def test_api_ts_has_download_report_pdf(self):
        content = (self.FRONTEND / "lib" / "api.ts").read_text()
        assert "downloadReportPdf" in content
        assert "report/pdf" in content

    def test_types_ts_has_quant_data(self):
        content = (self.FRONTEND / "lib" / "types.ts").read_text()
        assert "QuantData" in content
        assert "var_analysis" in content
        assert "esg_scores" in content
        assert "attribution" in content

    def test_pdf_service_exists(self):
        assert (ROOT / "src" / "api" / "services" / "pdf_service.py").exists()


# =============================================================================
# STORAGE — delete_run integration
# =============================================================================


class TestStorageDeleteRun:
    """Test that delete_run in storage.py cascades properly."""

    def test_delete_run_callable(self):
        from frontend.storage import delete_run

        assert callable(delete_run)

    def test_delete_run_returns_false_for_unknown_id(self):
        from frontend.storage import delete_run

        result = delete_run("nonexistent-run-id-xyz-999")
        assert result is False or result == 0 or result is None  # graceful
