"""
tests/test_session17.py — Session 17: Traceability & Provenance

Tests:
  • ProvenanceCard schema
  • ReportSectionProvenance schema
  • ProvenancePacket completeness
  • ProvenanceService.build_stage_card
  • ProvenanceService.build_report_provenance
  • ProvenanceService.build_packet
  • ProvenanceService.save_packet
  • STAGE_INPUTS / STAGE_OUTPUTS / STAGE_ASSUMPTIONS coverage
  • Engine integration (provenance attribute)
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


# ═══════════════════════════════════════════════════════════════════════════
# Group 1: Provenance Schema Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestProvenanceSchemas:
    """Test the provenance Pydantic models."""

    def test_data_source_creation(self):
        from research_pipeline.schemas.provenance import DataSource
        ds = DataSource(name="fmp_financials", source_type="api")
        assert ds.name == "fmp_financials"
        assert ds.source_type == "api"
        assert ds.stage_origin is None

    def test_data_source_with_origin(self):
        from research_pipeline.schemas.provenance import DataSource
        ds = DataSource(name="stage_2_data", source_type="upstream_stage", stage_origin=2)
        assert ds.stage_origin == 2

    def test_stage_output_creation(self):
        from research_pipeline.schemas.provenance import StageOutput
        so = StageOutput(name="validated_universe", output_type="data", description="Confirmed tickers")
        assert so.name == "validated_universe"
        assert so.output_type == "data"

    def test_provenance_card_creation(self):
        from research_pipeline.schemas.provenance import ProvenanceCard
        card = ProvenanceCard(
            stage_num=5,
            stage_label="Evidence Library",
            run_id="test-001",
            agent_name="evidence_librarian",
        )
        assert card.stage_num == 5
        assert card.stage_label == "Evidence Library"
        assert card.gate_passed is None
        assert card.inputs == []
        assert card.outputs == []
        assert card.assumptions == []

    def test_provenance_card_serialization(self):
        from research_pipeline.schemas.provenance import ProvenanceCard
        card = ProvenanceCard(
            stage_num=0,
            stage_label="Bootstrap",
            run_id="test-001",
            gate_passed=True,
            gate_reason="All checks passed",
        )
        data = card.model_dump(mode="json")
        assert data["stage_num"] == 0
        assert data["gate_passed"] is True
        assert "timestamp" in data

    def test_report_section_provenance(self):
        from research_pipeline.schemas.provenance import ReportSectionProvenance
        rsp = ReportSectionProvenance(
            section_title="Executive Summary",
            section_index=1,
            source_stages=[5, 6, 7, 12],
            source_agents=["orchestrator"],
            confidence_level="medium",
        )
        assert rsp.section_title == "Executive Summary"
        assert 5 in rsp.source_stages
        assert rsp.confidence_level == "medium"

    def test_provenance_packet_completeness(self):
        from research_pipeline.schemas.provenance import ProvenancePacket, ProvenanceCard
        cards = [
            ProvenanceCard(stage_num=i, stage_label=f"S{i}", run_id="r1")
            for i in range(10)
        ]
        packet = ProvenancePacket(run_id="r1", stage_cards=cards)
        packet.compute_completeness()
        assert packet.stages_with_provenance == 10
        assert packet.completeness_pct == pytest.approx(66.7, abs=0.1)

    def test_provenance_packet_full_completeness(self):
        from research_pipeline.schemas.provenance import ProvenancePacket, ProvenanceCard
        cards = [
            ProvenanceCard(stage_num=i, stage_label=f"S{i}", run_id="r1")
            for i in range(15)
        ]
        packet = ProvenancePacket(run_id="r1", stage_cards=cards)
        packet.compute_completeness()
        assert packet.stages_with_provenance == 15
        assert packet.completeness_pct == 100.0

    def test_provenance_packet_serialization(self):
        from research_pipeline.schemas.provenance import ProvenancePacket
        packet = ProvenancePacket(run_id="r1")
        data = json.loads(packet.model_dump_json())
        assert data["run_id"] == "r1"
        assert data["stage_cards"] == []
        assert data["report_sections"] == []


# ═══════════════════════════════════════════════════════════════════════════
# Group 2: ProvenanceService Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestProvenanceService:
    """Test the ProvenanceService business logic."""

    def test_build_stage_card(self):
        from research_pipeline.services.provenance_service import ProvenanceService
        svc = ProvenanceService(run_id="r1", model="gpt-4o", temperature=0.3)
        card = svc.build_stage_card(
            stage_num=2,
            stage_label="Data Ingestion",
            stage_output={"agent_name": "data_agent"},
            gate_passed=True,
            gate_reason="Data quality sufficient",
            duration_ms=4500.0,
        )
        assert card.stage_num == 2
        assert card.agent_name == "data_agent"
        assert card.model_used == "gpt-4o"
        assert card.gate_passed is True
        assert card.duration_ms == 4500.0
        # Has inputs from STAGE_INPUTS[2]
        assert len(card.inputs) > 0
        # Has outputs from STAGE_OUTPUTS[2]
        assert len(card.outputs) > 0
        # Has assumptions from STAGE_ASSUMPTIONS[2]
        assert len(card.assumptions) > 0

    def test_build_stage_card_accumulates(self):
        """Multiple calls accumulate cards internally."""
        from research_pipeline.services.provenance_service import ProvenanceService
        svc = ProvenanceService(run_id="r1")
        svc.build_stage_card(0, "Bootstrap", {}, True)
        svc.build_stage_card(1, "Universe", {}, True)
        svc.build_stage_card(2, "Ingestion", {}, True)
        assert len(svc._cards) == 3

    def test_build_stage_card_with_error(self):
        from research_pipeline.services.provenance_service import ProvenanceService
        svc = ProvenanceService(run_id="r1")
        card = svc.build_stage_card(
            stage_num=5,
            stage_label="Evidence",
            stage_output={},
            gate_passed=False,
            gate_reason="Failed",
            gate_blockers=["Missing data"],
            error="API timeout",
        )
        assert card.gate_passed is False
        assert card.error == "API timeout"
        assert "Missing data" in card.gate_blockers

    def test_build_report_provenance(self):
        from research_pipeline.services.provenance_service import ProvenanceService
        svc = ProvenanceService(run_id="r1")
        md = """# Report Title
## Executive Summary
Some content here.
## Sector Analysis
Sector details.
## Valuation
DCF models.
## Risk Assessment
Risk details.
## Portfolio Construction
Weights.
"""
        sections = svc.build_report_provenance(md)
        assert len(sections) >= 5
        titles = [s.section_title for s in sections]
        assert "Executive Summary" in titles
        assert "Sector Analysis" in titles
        assert "Valuation" in titles

    def test_report_section_source_stages(self):
        """Report provenance maps sections to correct source stages."""
        from research_pipeline.services.provenance_service import ProvenanceService
        svc = ProvenanceService(run_id="r1")
        md = "## Valuation\nDCF models."
        sections = svc.build_report_provenance(md)
        assert len(sections) == 1
        assert 7 in sections[0].source_stages  # Valuation = stage 7

    def test_build_packet(self):
        from research_pipeline.services.provenance_service import ProvenanceService
        svc = ProvenanceService(run_id="r1")
        svc.build_stage_card(0, "Bootstrap", {}, True, duration_ms=100)
        svc.build_stage_card(1, "Universe", {}, True, duration_ms=200)
        packet = svc.build_packet(report_md="## Executive Summary\nContent.")
        assert packet.stages_with_provenance == 2
        assert len(packet.report_sections) == 1
        assert packet.completeness_pct == pytest.approx(13.3, abs=0.1)

    def test_save_packet(self):
        from research_pipeline.services.provenance_service import ProvenanceService
        from research_pipeline.schemas.provenance import ProvenancePacket
        svc = ProvenanceService(run_id="r1")
        packet = ProvenancePacket(run_id="r1")
        with tempfile.TemporaryDirectory() as tmpdir:
            path = svc.save_packet(packet, Path(tmpdir))
            assert path.exists()
            data = json.loads(path.read_text())
            assert data["run_id"] == "r1"


# ═══════════════════════════════════════════════════════════════════════════
# Group 3: STAGE_INPUTS / STAGE_OUTPUTS / STAGE_ASSUMPTIONS Coverage
# ═══════════════════════════════════════════════════════════════════════════

class TestStageMetadata:
    """Verify the stage metadata dictionaries are complete."""

    def test_stage_inputs_covers_all_stages(self):
        from research_pipeline.services.provenance_service import STAGE_INPUTS
        for i in range(15):
            assert i in STAGE_INPUTS, f"STAGE_INPUTS missing stage {i}"

    def test_stage_outputs_covers_all_stages(self):
        from research_pipeline.services.provenance_service import STAGE_OUTPUTS
        for i in range(15):
            assert i in STAGE_OUTPUTS, f"STAGE_OUTPUTS missing stage {i}"

    def test_stage_assumptions_covers_all_stages(self):
        from research_pipeline.services.provenance_service import STAGE_ASSUMPTIONS
        for i in range(15):
            assert i in STAGE_ASSUMPTIONS, f"STAGE_ASSUMPTIONS missing stage {i}"

    def test_inputs_have_required_fields(self):
        from research_pipeline.services.provenance_service import STAGE_INPUTS
        for stage, inputs in STAGE_INPUTS.items():
            for inp in inputs:
                assert "name" in inp, f"Stage {stage} input missing 'name'"
                assert "source_type" in inp, f"Stage {stage} input missing 'source_type'"

    def test_outputs_have_required_fields(self):
        from research_pipeline.services.provenance_service import STAGE_OUTPUTS
        for stage, outputs in STAGE_OUTPUTS.items():
            for out in outputs:
                assert "name" in out, f"Stage {stage} output missing 'name'"


# ═══════════════════════════════════════════════════════════════════════════
# Group 4: Engine Integration
# ═══════════════════════════════════════════════════════════════════════════

class TestEngineProvenance:
    """Verify the engine has provenance wiring."""

    def test_engine_has_provenance_attribute(self):
        """PipelineEngine initialises _provenance to None."""
        from research_pipeline.pipeline.engine import PipelineEngine
        from unittest.mock import MagicMock
        settings = MagicMock()
        settings.storage_dir = Path(tempfile.mkdtemp())
        settings.prompts_dir = Path(tempfile.mkdtemp())
        settings.api_keys = MagicMock()
        settings.api_keys.fmp_api_key = ""
        settings.api_keys.finnhub_api_key = ""
        settings.llm_model = "gpt-4o"
        settings.llm_temperature = 0.3
        config = MagicMock()
        config.thresholds = MagicMock()
        config.thresholds.reconciliation = MagicMock()
        config.thresholds.data_quality = MagicMock()
        config.market_config = MagicMock()
        config.market_config.fred_api_key = ""
        engine = PipelineEngine(settings, config)
        assert hasattr(engine, "_provenance")
        assert engine._provenance is None

    def test_provenance_service_import(self):
        """ProvenanceService can be imported from the engine module context."""
        from research_pipeline.services.provenance_service import ProvenanceService
        svc = ProvenanceService(run_id="test", model="gpt-4o")
        assert svc.run_id == "test"

    def test_confidence_assessment(self):
        """_assess_confidence returns correct levels."""
        from research_pipeline.services.provenance_service import ProvenanceService
        assert ProvenanceService._assess_confidence([]) == "low"
        assert ProvenanceService._assess_confidence([0, 1, 2, 3]) == "high"
        assert ProvenanceService._assess_confidence([5, 6, 7]) == "medium"
        assert ProvenanceService._assess_confidence([2, 5]) == "medium"

    def test_section_mapping(self):
        """_map_section_to_sources maps known sections correctly."""
        from research_pipeline.services.provenance_service import ProvenanceService
        stages, agents, methods = ProvenanceService._map_section_to_sources("Sector Analysis")
        assert 6 in stages
        assert "sector_analyst" in agents

        stages2, _, _ = ProvenanceService._map_section_to_sources("Risk Assessment")
        assert 9 in stages2

        stages3, _, _ = ProvenanceService._map_section_to_sources("Portfolio Construction")
        assert 12 in stages3
