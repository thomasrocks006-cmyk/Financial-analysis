"""Session 6 targeted tests.

Covers:
  - ACT-S6-1: SelfAuditPacket wiring into run_full_pipeline
  - ACT-S6-2: EsgAnalystAgent parse_output, clamping, exclusion logic
  - ACT-S6-3: PDF export (_generate_report_pdf) smoke test
  - ACT-S6-4: pipeline_runner deprecation warning emitted on import
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from research_pipeline.agents.base_agent import AgentResult
from research_pipeline.agents.esg_analyst import EsgAnalystAgent
from research_pipeline.config.loader import PipelineConfig
from research_pipeline.config.settings import APIKeys, Settings
from research_pipeline.pipeline.engine import PipelineEngine


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures & helpers
# ─────────────────────────────────────────────────────────────────────────────

S6_UNIVERSE = ["NVDA", "AVGO", "TSM"]


@pytest.fixture
def s6_settings(tmp_path: Path) -> Settings:
    return Settings(
        project_root=Path(__file__).resolve().parents[1],
        storage_dir=tmp_path / "storage",
        reports_dir=tmp_path / "reports",
        prompts_dir=tmp_path / "prompts",
        llm_model="claude-opus-4-6",
        api_keys=APIKeys(
            fmp_api_key="test-fmp-key",
            finnhub_api_key="test-finnhub-key",
            anthropic_api_key="test-anthropic-key",
        ),
    )


@pytest.fixture
def s6_config() -> PipelineConfig:
    return PipelineConfig()


def _ingest_row(ticker: str) -> dict:
    from datetime import datetime, timezone

    return {
        "ticker": ticker,
        "source": "fmp",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fmp_quote": {"ticker": ticker, "price": 500.0, "source": "fmp"},
        "finnhub_quote": {"price": 501.0},
        "fmp_targets": {},
        "finnhub_targets": {},
    }


def _ar(agent_name: str, parsed: dict) -> AgentResult:
    return AgentResult(
        agent_name=agent_name,
        run_id="S6-TEST",
        success=True,
        raw_response=json.dumps(parsed),
        parsed_output=parsed,
    )


def _sector_out(ticker: str) -> dict:
    return {
        "ticker": ticker,
        "box1_verified_facts": f"{ticker} revenue grew",
        "box2_management_guidance": "Strong",
        "box3_consensus_market_view": "Buy",
        "box4_analyst_judgment": "High conviction",
        "key_risks": "macro",
    }


def _esg_entry(ticker: str) -> dict:
    return {
        "ticker": ticker,
        "esg_score": 70,
        "e_score": 65,
        "s_score": 75,
        "g_score": 70,
        "controversy_flags": [],
        "exclusion_trigger": False,
        "exclusion_reason": "",
        "primary_esg_risk": "Supply chain emissions",
        "methodology_note": "Public-source ESG assessment",
    }


def _patch_all_agents(engine: PipelineEngine) -> None:
    """Patch all agents including the new ESG agent added in session 6."""
    engine.orchestrator_agent.run = AsyncMock(
        return_value=_ar("orchestrator", {"status": "proceed", "universe": S6_UNIVERSE})
    )
    engine.evidence_agent.run = AsyncMock(
        return_value=_ar(
            "evidence_librarian",
            {
                "claims": [
                    {
                        "claim_id": "C1",
                        "ticker": "NVDA",
                        "claim_text": "NVDA Q4 revenue $18B",
                        "evidence_class": "primary_fact",
                        "source_id": "SRC-1",
                        "confidence": "high",
                        "status": "pass",
                    }
                ],
                "sources": [
                    {
                        "source_id": "SRC-1",
                        "source_type": "filing",
                        "tier": 1,
                        "url": None,
                        "notes": "10-K",
                    }
                ],
            },
        )
    )
    engine.compute_analyst.run = AsyncMock(
        return_value=_ar(
            "sector_analyst_compute",
            {"sector_outputs": [_sector_out(t) for t in S6_UNIVERSE]},
        )
    )
    engine.power_analyst.run = AsyncMock(
        return_value=_ar("sector_analyst_power", {"sector_outputs": []})
    )
    engine.infra_analyst.run = AsyncMock(
        return_value=_ar("sector_analyst_infrastructure", {"sector_outputs": []})
    )
    # ACT-S6-2: ESG analyst mock
    engine.esg_analyst_agent.run = AsyncMock(
        return_value=_ar(
            "esg_analyst",
            {"esg_scores": [_esg_entry(t) for t in S6_UNIVERSE], "parse_violations": []},
        )
    )
    engine.valuation_agent.run = AsyncMock(
        return_value=_ar(
            "valuation_analyst",
            {
                "valuations": [
                    {
                        "ticker": "NVDA",
                        "date": "2026-01-01",
                        "section_5_scenarios": [
                            {
                                "case": "base",
                                "probability_pct": 50,
                                "revenue_cagr": "20%",
                                "exit_multiple": "30x",
                                "exit_multiple_rationale": "sector median",
                                "implied_return_1y": "15%",
                                "implied_return_3y": "50% [HOUSE VIEW]",
                                "key_assumption": "data center demand",
                                "what_breaks_it": "capex cut",
                            }
                        ],
                        "entry_quality": "ACCEPTABLE",
                        "methodology_tag": "HOUSE VIEW",
                    }
                ]
            },
        )
    )
    engine.macro_agent.run = AsyncMock(
        return_value=_ar(
            "macro_strategist",
            {
                "regime": "expansion",
                "rate_outlook": "neutral",
                "usd_outlook": "stable",
                "equity_risk_premium": 5.0,
            },
        )
    )
    engine.political_agent.run = AsyncMock(
        return_value=_ar("political_risk", {"risk_level": "low", "key_risks": []})
    )
    engine.red_team_agent.run = AsyncMock(
        return_value=_ar(
            "red_team_analyst",
            {
                "assessments": [
                    {
                        "ticker": "NVDA",
                        "falsification_tests": ["FT-1", "FT-2", "FT-3"],
                        "required_tests": {},
                    }
                ]
            },
        )
    )
    engine.reviewer_agent.run = AsyncMock(
        return_value=_ar(
            "associate_reviewer",
            {
                "status": "pass",
                "issues": [],
                "methodology_tags_complete": True,
                "dates_complete": True,
                "claim_mapping_complete": True,
            },
        )
    )
    engine.pm_agent.run = AsyncMock(
        return_value=_ar(
            "portfolio_manager",
            {
                "variants": [
                    {
                        "name": "balanced",
                        "positions": [
                            {"ticker": "NVDA", "weight_pct": 34.0},
                            {"ticker": "AVGO", "weight_pct": 33.0},
                            {"ticker": "TSM", "weight_pct": 33.0},
                        ],
                    },
                    {
                        "name": "higher_return",
                        "positions": [
                            {"ticker": "NVDA", "weight_pct": 50.0},
                            {"ticker": "AVGO", "weight_pct": 30.0},
                            {"ticker": "TSM", "weight_pct": 20.0},
                        ],
                    },
                    {
                        "name": "lower_volatility",
                        "positions": [
                            {"ticker": "NVDA", "weight_pct": 25.0},
                            {"ticker": "AVGO", "weight_pct": 40.0},
                            {"ticker": "TSM", "weight_pct": 35.0},
                        ],
                    },
                ]
            },
        )
    )
    engine.quant_analyst_agent.run = AsyncMock(
        return_value=_ar(
            "quant_research_analyst",
            {
                "risk_signal": "neutral",
                "primary_concern": "concentration",
                "recommended_action": "monitor",
                "section_1_factor_interpretation": {"dominant_factors": ["momentum"]},
                "section_2_risk_assessment": {"var_95_commentary": "moderate"},
                "section_3_benchmark_divergence": {
                    "etf_differentiation_score": 60,
                    "etf_replication_risk": False,
                    "tracking_error_commentary": "high active share",
                    "active_bets_narrative": "NVDA+12%",
                    "information_ratio_signal": "IR=0.7",
                    "etf_overlap_summary": "60% differentiated",
                },
                "section_4_construction_signal": {
                    "factor_tilt_recommendation": "maintain",
                    "concentration_recommendation": "trim NVDA",
                    "benchmark_recommendation": "differentiated",
                    "constructive_changes": [],
                },
                "analyst_confidence": "medium",
                "data_quality_note": "test",
            },
        )
    )
    engine.fixed_income_agent.run = AsyncMock(
        return_value=_ar(
            "fixed_income_analyst",
            {
                "yield_curve_regime": "normal",
                "10y_yield_context": "4.3% neutral",
                "cost_of_capital_trend": "stable",
                "rate_sensitivity_score": 5.0,
                "key_risks": [],
                "offsetting_factors": [],
                "sector_rotation_read": "neutral",
                "methodology_note": "test",
            },
        )
    )

    # Deterministic services: mandate OK, IC approved
    from research_pipeline.schemas.governance import (
        CommitteeRecord,
        CommitteeVote,
        MandateCheckResult,
    )

    engine.mandate_engine.check_compliance = MagicMock(
        return_value=MandateCheckResult(
            run_id="S6-TEST", mandate_id="test-mandate", is_compliant=True
        )
    )
    engine.investment_committee.evaluate_and_vote = MagicMock(
        return_value=CommitteeRecord(
            record_id="IC-S6",
            run_id="S6-TEST",
            outcome=CommitteeVote.APPROVE,
            quorum_met=True,
            minutes="Approved — session 6 test",
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# ACT-S6-1: SelfAuditPacket wiring
# ─────────────────────────────────────────────────────────────────────────────


class TestSelfAuditPacketWiring:
    """Verify that run_full_pipeline attaches a SelfAuditPacket to the result."""

    @pytest.mark.asyncio
    async def test_audit_packet_in_result(self, s6_settings, s6_config):
        """run_full_pipeline should return an 'audit_packet' key on success."""
        engine = PipelineEngine(settings=s6_settings, config=s6_config)
        ingest_data = [_ingest_row(t) for t in S6_UNIVERSE]
        _patch_all_agents(engine)

        with patch.object(
            engine.ingestor, "ingest_universe", new=AsyncMock(return_value=ingest_data)
        ):
            result = await engine.run_full_pipeline(S6_UNIVERSE)

        assert result.get("status") == "completed", f"Pipeline did not complete: {result}"
        assert "audit_packet" in result, "audit_packet missing from run_full_pipeline result"
        packet = result["audit_packet"]
        assert packet is not None, "audit_packet should not be None on a successful run"
        assert isinstance(packet, dict), "audit_packet should be serialised as a dict"

    @pytest.mark.asyncio
    async def test_audit_packet_fields(self, s6_settings, s6_config):
        """SelfAuditPacket dict must contain all mandatory top-level fields."""
        engine = PipelineEngine(settings=s6_settings, config=s6_config)
        ingest_data = [_ingest_row(t) for t in S6_UNIVERSE]
        _patch_all_agents(engine)

        with patch.object(
            engine.ingestor, "ingest_universe", new=AsyncMock(return_value=ingest_data)
        ):
            result = await engine.run_full_pipeline(S6_UNIVERSE)

        packet = result.get("audit_packet") or {}
        mandatory = [
            "run_id",
            "generated_at",
            "gates_passed",
            "gates_failed",
            "agents_succeeded",
            "agents_failed",
            "publication_quality_score",
        ]
        for field in mandatory:
            assert field in packet, f"SelfAuditPacket missing field: {field}"

    @pytest.mark.asyncio
    async def test_audit_packet_gates_populated(self, s6_settings, s6_config):
        """gates_passed should include stage numbers for all passed gates."""
        engine = PipelineEngine(settings=s6_settings, config=s6_config)
        ingest_data = [_ingest_row(t) for t in S6_UNIVERSE]
        _patch_all_agents(engine)

        with patch.object(
            engine.ingestor, "ingest_universe", new=AsyncMock(return_value=ingest_data)
        ):
            result = await engine.run_full_pipeline(S6_UNIVERSE)

        packet = result.get("audit_packet") or {}
        gates_passed = packet.get("gates_passed", [])
        assert len(gates_passed) > 0, "gates_passed should be non-empty after a successful run"
        assert all(isinstance(g, int) for g in gates_passed), (
            "gates_passed should be int stage numbers"
        )

    @pytest.mark.asyncio
    async def test_audit_packet_persisted_to_disk(self, s6_settings, s6_config):
        """SelfAuditPacket should be written to disk as self_audit_packet.json."""
        engine = PipelineEngine(settings=s6_settings, config=s6_config)
        ingest_data = [_ingest_row(t) for t in S6_UNIVERSE]
        _patch_all_agents(engine)

        with patch.object(
            engine.ingestor, "ingest_universe", new=AsyncMock(return_value=ingest_data)
        ):
            result = await engine.run_full_pipeline(S6_UNIVERSE)

        assert result.get("status") == "completed"
        run_id = result["run_id"]
        artifact_path = s6_settings.storage_dir / "artifacts" / run_id / "self_audit_packet.json"
        assert artifact_path.exists(), f"self_audit_packet.json not found at {artifact_path}"
        raw = json.loads(artifact_path.read_text())
        assert raw.get("run_id") == run_id

    @pytest.mark.asyncio
    async def test_audit_packet_run_record_field(self, s6_settings, s6_config):
        """run_record.self_audit_packet should be set after a completed run."""
        engine = PipelineEngine(settings=s6_settings, config=s6_config)
        ingest_data = [_ingest_row(t) for t in S6_UNIVERSE]
        _patch_all_agents(engine)

        with patch.object(
            engine.ingestor, "ingest_universe", new=AsyncMock(return_value=ingest_data)
        ):
            await engine.run_full_pipeline(S6_UNIVERSE)

        assert engine.run_record is not None
        assert engine.run_record.self_audit_packet is not None, (
            "run_record.self_audit_packet should be set after a completed run"
        )

    @pytest.mark.asyncio
    async def test_audit_packet_build_standalone(self, s6_settings, s6_config):
        """_build_self_audit_packet runs without error on a minimal engine state."""
        from research_pipeline.schemas.governance import SelfAuditPacket
        from research_pipeline.schemas.registry import RunRecord

        engine = PipelineEngine(settings=s6_settings, config=s6_config)
        # Provide minimal run_record
        engine.run_record = RunRecord(run_id="TEST-STANDALONE", universe=["NVDA"])

        # Minimal gate_results
        from research_pipeline.pipeline.gates import GateResult

        engine.gate_results = {
            0: GateResult(stage=0, passed=True),
            1: GateResult(stage=1, passed=True),
            5: GateResult(stage=5, passed=False, reason="not enough claims"),
        }

        packet = engine._build_self_audit_packet(["NVDA"])
        assert isinstance(packet, SelfAuditPacket)
        assert packet.run_id == "TEST-STANDALONE"
        assert 0 in packet.gates_passed
        assert 1 in packet.gates_passed
        assert 5 in packet.gates_failed
        assert isinstance(packet.publication_quality_score, float)


# ─────────────────────────────────────────────────────────────────────────────
# ACT-S6-2: EsgAnalystAgent
# ─────────────────────────────────────────────────────────────────────────────


class TestEsgAnalystAgent:
    """Unit tests for EsgAnalystAgent.parse_output() validation and clamping."""

    @pytest.fixture
    def agent(self, tmp_path) -> EsgAnalystAgent:
        return EsgAnalystAgent(
            model="claude-opus-4-6",
            temperature=0.0,
            prompts_dir=tmp_path / "prompts",
        )

    def _valid_entry(self, ticker: str = "NVDA") -> dict:
        return {
            "ticker": ticker,
            "esg_score": 72,
            "e_score": 65,
            "s_score": 78,
            "g_score": 73,
            "controversy_flags": [],
            "exclusion_trigger": False,
            "exclusion_reason": "",
            "primary_esg_risk": "Supply chain carbon exposure",
            "methodology_note": "Public-source assessment",
        }

    def test_parse_valid_output(self, agent):
        """Valid ESG output should parse without errors."""
        raw = json.dumps({"esg_scores": [self._valid_entry()]})
        result = agent.parse_output(raw)
        assert "esg_scores" in result
        assert result["esg_scores"][0]["ticker"] == "NVDA"

    def test_parse_bare_list(self, agent):
        """Bare JSON array (without wrapper) should also be accepted."""
        raw = json.dumps([self._valid_entry("AVGO")])
        result = agent.parse_output(raw)
        assert result["esg_scores"][0]["ticker"] == "AVGO"

    def test_score_clamping_above_100(self, agent):
        """Scores above 100 should be clamped to 100."""
        entry = self._valid_entry()
        entry["esg_score"] = 150
        entry["e_score"] = 999
        raw = json.dumps({"esg_scores": [entry]})
        result = agent.parse_output(raw)
        scores = result["esg_scores"][0]
        assert scores["esg_score"] == 100
        assert scores["e_score"] == 100

    def test_score_clamping_below_0(self, agent):
        """Negative scores should be clamped to 0."""
        entry = self._valid_entry()
        entry["esg_score"] = -10
        entry["s_score"] = -99
        raw = json.dumps({"esg_scores": [entry]})
        result = agent.parse_output(raw)
        scores = result["esg_scores"][0]
        assert scores["esg_score"] == 0
        assert scores["s_score"] == 0

    def test_exclusion_trigger_with_reason(self, agent):
        """exclusion_trigger=true with reason should parse without violations."""
        entry = self._valid_entry()
        entry["exclusion_trigger"] = True
        entry["exclusion_reason"] = "Thermal coal >30% of revenue"
        raw = json.dumps({"esg_scores": [entry]})
        result = agent.parse_output(raw)
        violations = result.get("parse_violations", [])
        # No exclusion-trigger violation when reason is present
        exclusion_violations = [v for v in violations if "exclusion_reason" in v]
        assert len(exclusion_violations) == 0, f"Unexpected violations: {exclusion_violations}"

    def test_exclusion_trigger_without_reason_flags_violation(self, agent):
        """exclusion_trigger=true with empty reason should note a violation."""
        entry = self._valid_entry()
        entry["exclusion_trigger"] = True
        entry["exclusion_reason"] = ""
        raw = json.dumps({"esg_scores": [entry]})
        result = agent.parse_output(raw)
        violations = result.get("parse_violations", [])
        assert any("exclusion_reason" in v for v in violations), (
            "Expected a parse violation about empty exclusion_reason"
        )

    def test_controversy_flags_default_to_list(self, agent):
        """controversy_flags missing or non-list should default to []."""
        entry = self._valid_entry()
        del entry["controversy_flags"]
        raw = json.dumps({"esg_scores": [entry]})
        result = agent.parse_output(raw)
        assert isinstance(result["esg_scores"][0]["controversy_flags"], list)

    def test_missing_methodology_note_flags_violation(self, agent):
        """Missing methodology_note should produce a parse violation."""
        entry = self._valid_entry()
        entry["methodology_note"] = ""
        raw = json.dumps({"esg_scores": [entry]})
        result = agent.parse_output(raw)
        violations = result.get("parse_violations", [])
        assert any("methodology_note" in v for v in violations)

    def test_primary_esg_risk_default(self, agent):
        """Missing primary_esg_risk should be defaulted to 'Not assessed'."""
        entry = self._valid_entry()
        del entry["primary_esg_risk"]
        raw = json.dumps({"esg_scores": [entry]})
        result = agent.parse_output(raw)
        assert result["esg_scores"][0].get("primary_esg_risk") == "Not assessed"

    def test_multiple_tickers(self, agent):
        """Multiple ticker entries in one response should all be preserved."""
        entries = [self._valid_entry(t) for t in ["NVDA", "AVGO", "TSM"]]
        raw = json.dumps({"esg_scores": entries})
        result = agent.parse_output(raw)
        tickers = [e["ticker"] for e in result["esg_scores"]]
        assert tickers == ["NVDA", "AVGO", "TSM"]

    def test_empty_scores_raises(self, agent):
        """Empty esg_scores array should raise StructuredOutputError."""
        from research_pipeline.agents.base_agent import StructuredOutputError

        raw = json.dumps({"esg_scores": []})
        with pytest.raises(StructuredOutputError):
            agent.parse_output(raw)

    def test_invalid_root_type_raises(self, agent):
        """Non-list, non-dict root should raise StructuredOutputError."""
        from research_pipeline.agents.base_agent import StructuredOutputError

        raw = '"just a string"'
        with pytest.raises((StructuredOutputError, Exception)):
            agent.parse_output(raw)

    def test_esg_agent_instantiation(self, agent):
        """EsgAnalystAgent should have name 'esg_analyst' and a system prompt."""
        assert agent.name == "esg_analyst"
        prompt = agent.default_system_prompt()
        assert "ESG" in prompt
        assert "exclusion_trigger" in prompt
        assert "methodology_note" in prompt

    def test_esg_agent_wired_in_engine(self, s6_settings, s6_config):
        """PipelineEngine should expose an esg_analyst_agent attribute."""
        engine = PipelineEngine(settings=s6_settings, config=s6_config)
        assert hasattr(engine, "esg_analyst_agent"), (
            "PipelineEngine missing 'esg_analyst_agent' — wiring incomplete"
        )
        assert isinstance(engine.esg_analyst_agent, EsgAnalystAgent)


# ─────────────────────────────────────────────────────────────────────────────
# ACT-S6-3: PDF export smoke test
# ─────────────────────────────────────────────────────────────────────────────


class TestPDFExportRoute:
    """Smoke tests for the _generate_report_pdf helper in app.py."""

    def _load_pdf_fn(self, tmp_path: Path):
        """Load _generate_report_pdf by partial source execution."""
        src_path = Path(__file__).resolve().parents[1] / "src" / "frontend" / "app.py"
        if not src_path.exists():
            pytest.skip("app.py not found")
        src_text = src_path.read_text()
        # Ensure fpdf2 is available before attempting to run the function
        try:
            from fpdf import FPDF  # noqa: F401
        except ImportError:
            pytest.skip("fpdf2 not installed")

        # Build a namespace that mirrors the imports the function needs
        from datetime import datetime, timezone
        import re
        import textwrap

        namespace: dict = {
            "__name__": "test_pdf_extract",
            "re": re,
            "datetime": datetime,
            "timezone": timezone,
            "bytes": bytes,
        }

        # Extract the function definition from the source
        fn_start = src_text.find("def _generate_report_pdf(")
        if fn_start == -1:
            pytest.skip("_generate_report_pdf not found in app.py")
        fn_end = src_text.find("\n\n\n", fn_start)
        fn_source = src_text[fn_start : fn_end if fn_end != -1 else fn_start + 5000]
        exec(textwrap.dedent(fn_source), namespace)  # noqa: S102
        return namespace["_generate_report_pdf"]

    def test_pdf_returns_bytes(self, tmp_path):
        """_generate_report_pdf should return non-empty bytes."""
        fn = self._load_pdf_fn(tmp_path)
        report_md = "# Test Report\n\nSome content about NVDA.\n\n## Section 2\n\nMore data."
        result = fn("RUN-001", ["NVDA", "AVGO"], report_md)
        assert isinstance(result, bytes), "PDF output should be bytes"
        assert len(result) > 0, "PDF output should not be empty"

    def test_pdf_starts_with_pdf_header(self, tmp_path):
        """PDF bytes should begin with the %PDF magic header."""
        fn = self._load_pdf_fn(tmp_path)
        result = fn("RUN-002", ["TSM"], "# Report\n\nContent.")
        assert result[:4] == b"%PDF", "PDF bytes should start with %PDF magic header"

    def test_pdf_with_empty_report(self, tmp_path):
        """Empty report_md should produce a cover page only — not crash."""
        fn = self._load_pdf_fn(tmp_path)
        result = fn("RUN-003", [], "")
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_pdf_with_markdown_formatting(self, tmp_path):
        """Report with headings, bullets, bold, HR should not crash."""
        fn = self._load_pdf_fn(tmp_path)
        report_md = (
            "# Main Title\n\n"
            "## Section One\n\n"
            "### Sub-section\n\n"
            "**Bold text** and *italic text* and `code`.\n\n"
            "- Bullet one\n"
            "- Bullet two\n\n"
            "---\n\n"
            "More text after horizontal rule."
        )
        result = fn("RUN-004", ["NVDA"], report_md)
        assert isinstance(result, bytes)
        assert len(result) > 500, "PDF with formatted content should be at least 500 bytes"

    def test_pdf_run_id_in_cover(self, tmp_path):
        """The run_id should appear somewhere in the PDF bytes."""
        fn = self._load_pdf_fn(tmp_path)
        run_id = "UNIQUE-RUN-XYZ-99"
        result = fn(run_id, ["NVDA"], "# Report\n\nContent.")
        # PDF text in fpdf2 is embedded as UTF-8; run_id should appear in raw bytes
        assert (
            run_id.encode("latin-1", errors="replace") in result
            or run_id.encode("utf-8", errors="replace") in result
        ), "run_id should appear in the PDF binary content"


# ─────────────────────────────────────────────────────────────────────────────
# ACT-S6-4: pipeline_runner deprecation warning
# ─────────────────────────────────────────────────────────────────────────────


class TestPipelineRunnerDeprecation:
    """Verify that importing pipeline_runner emits a DeprecationWarning."""

    def test_deprecation_warning_emitted(self):
        """Importing or reloading pipeline_runner should emit DeprecationWarning."""
        import importlib
        import sys

        # Remove the cached module so the warning fires again on import
        sys.modules.pop("frontend.pipeline_runner", None)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                importlib.import_module("frontend.pipeline_runner")
            except ImportError:
                pytest.skip("frontend.pipeline_runner not on path")

        dep_warnings = [
            w
            for w in caught
            if issubclass(w.category, DeprecationWarning)
            and "pipeline_runner" in str(w.message).lower()
        ]
        assert len(dep_warnings) >= 1, (
            "Expected a DeprecationWarning from frontend.pipeline_runner import; "
            f"got: {[str(w.message) for w in caught]}"
        )

    def test_deprecation_message_mentions_adapter(self):
        """The deprecation message should mention pipeline_adapter."""
        import importlib
        import sys

        sys.modules.pop("frontend.pipeline_runner", None)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                importlib.import_module("frontend.pipeline_runner")
            except ImportError:
                pytest.skip("frontend.pipeline_runner not on path")

        dep_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        if not dep_warnings:
            pytest.skip("No DeprecationWarning captured")

        msg = str(dep_warnings[0].message)
        assert "pipeline_adapter" in msg, (
            f"DeprecationWarning should mention 'pipeline_adapter'; got: {msg}"
        )
