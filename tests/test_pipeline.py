"""Tests for the pipeline engine module."""

from __future__ import annotations

import pytest

from research_pipeline.pipeline.gates import GateResult, PipelineGates
from research_pipeline.pipeline.engine import PipelineEngine


class TestPipelineEngine:
    """Tests for the pipeline engine."""

    def test_engine_imports(self):
        """Verify the engine module can be imported."""
        assert PipelineEngine is not None

    def test_gate_result_structure(self):
        result = GateResult(stage=0, passed=True, reason="test")
        assert result.stage == 0
        assert result.passed is True
        assert result.reason == "test"
        assert result.blockers == []

    def test_gate_result_failure(self):
        result = GateResult(
            stage=3, passed=False, reason="reconciliation failed",
            blockers=["RED: NVDA price — divergence 5.2%"],
        )
        assert result.passed is False
        assert len(result.blockers) == 1

    def test_all_gate_methods_exist(self):
        """Verify all 15 gate methods exist on PipelineGates."""
        expected_gates = [
            "gate_0_configuration",
            "gate_1_universe",
            "gate_2_ingestion",
            "gate_3_reconciliation",
            "gate_4_data_qa",
            "gate_5_evidence",
            "gate_6_sector_analysis",
            "gate_7_valuation",
            "gate_8_macro",
            "gate_9_risk",
            "gate_10_red_team",
            "gate_11_review",
            "gate_12_portfolio",
            "gate_13_report",
        ]
        for gate_name in expected_gates:
            assert hasattr(PipelineGates, gate_name), f"Missing gate: {gate_name}"

    def test_engine_has_new_services(self):
        """Verify new quantitative, governance, and monitoring services are wired."""
        import tempfile
        from pathlib import Path

        from research_pipeline.config.loader import PipelineConfig, load_pipeline_config
        from research_pipeline.config.settings import Settings

        # Construct a minimal Settings object for instantiation check
        tmpdir = Path(tempfile.mkdtemp())
        settings = Settings(
            storage_dir=tmpdir,
            prompts_dir=tmpdir / "prompts",
            reports_dir=tmpdir / "reports",
        )
        config = load_pipeline_config()
        engine = PipelineEngine(settings=settings, config=config)

        # Quantitative Research Division
        assert hasattr(engine, "factor_engine")
        assert hasattr(engine, "benchmark_module")
        assert hasattr(engine, "var_engine")
        assert hasattr(engine, "portfolio_optimisation")
        assert hasattr(engine, "position_sizing")

        # Governance & Compliance Division
        assert hasattr(engine, "mandate_engine")
        assert hasattr(engine, "esg_service")
        assert hasattr(engine, "investment_committee")
        assert hasattr(engine, "audit_exporter")

        # Performance & Monitoring Division
        assert hasattr(engine, "performance_tracker")
        assert hasattr(engine, "monitoring_engine")
        assert hasattr(engine, "rebalancing_engine")
        assert hasattr(engine, "cache")
        assert hasattr(engine, "quota_manager")
