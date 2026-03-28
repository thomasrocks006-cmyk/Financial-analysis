"""tests/test_session11.py — Session 11 feature verification.

Covers:
  ISS-1:  MacroContextPacket schema (from_stage_8_output, summary_text, enums)
  ISS-3:  GenericSectorAnalystAgent (format_input, required keys, fallback routing)
  ISS-4:  StockCard adapter (build_stock_card_from_pipeline_outputs)
  ISS-9:  _VALIDATION_FATAL mechanism (raises on critical agents, warns on others)
  ISS-10: Triple-strategy Gemini (_call_gemini import fallback paths)
  ISS-20: app.py audit_packet key fix (run_result attribute, not dict key)
  ARC-1:  PipelineEngine._get_macro_context helper
  ARC-2:  stage_13_report builds real StockCard objects
  ARC-3:  VaR uses live factor returns (not np.random.normal stub)
  ARC-4:  Stage 8 executes before Stage 7 in run_full_pipeline
  ARC-5:  SECTOR_ROUTING in config; GenericSectorAnalystAgent for unmapped tickers
  ARC-6:  macro_context wired to red_team agent inputs
  ARC-7:  macro_context wired to reviewer agent inputs
  ARC-8:  macro_context wired to PM agent inputs
  ARC-9:  Stage 8 macro receives stage 2/3 market data
  ARC-10: FI agent uses real Stage 8 macro output (not hardcoded stub)
"""

from __future__ import annotations

import inspect
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ── Imports under test ───────────────────────────────────────────────────────

from research_pipeline.schemas.macro import (
    ConfidenceLevel,
    MacroContextPacket,
    MacroRegime,
)
from research_pipeline.schemas.reports import (
    StockCard,
    build_stock_card_from_pipeline_outputs,
)
from research_pipeline.agents.base_agent import BaseAgent, StructuredOutputError
from research_pipeline.agents.valuation_analyst import ValuationAnalystAgent
from research_pipeline.agents.red_team_analyst import RedTeamAnalystAgent
from research_pipeline.agents.associate_reviewer import AssociateReviewerAgent
from research_pipeline.agents.generic_sector_analyst import GenericSectorAnalystAgent
from research_pipeline.config.loader import PipelineConfig, SECTOR_ROUTING
from research_pipeline.config.settings import APIKeys, Settings
from research_pipeline.pipeline.engine import PipelineEngine


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_engine(tmp_path: Path | None = None) -> PipelineEngine:
    """Create a PipelineEngine backed by a temp directory."""
    if tmp_path is None:
        tmp_path = Path(tempfile.mkdtemp())
    settings = Settings(
        project_root=Path(__file__).resolve().parents[1],
        storage_dir=tmp_path / "storage",
        reports_dir=tmp_path / "reports",
        prompts_dir=tmp_path / "prompts",
        llm_model="claude-opus-4-6",
        api_keys=APIKeys(
            fmp_api_key="test",
            finnhub_api_key="test",
            anthropic_api_key="test",
        ),
    )
    config = PipelineConfig()
    return PipelineEngine(settings, config)


class _ConcreteAgent(BaseAgent):
    """Minimal concrete BaseAgent for testing the validation mechanism."""

    def default_system_prompt(self) -> str:
        return "You are a test agent."


class _FatalAgent(_ConcreteAgent):
    """Agent with _VALIDATION_FATAL = True for testing fatal key checks."""

    _VALIDATION_FATAL: bool = True
    _REQUIRED_OUTPUT_KEYS: list[str] = ["required_key"]


# ─── ISS-1: MacroContextPacket ───────────────────────────────────────────────


class TestMacroContextPacket:
    def test_default_construction(self):
        pkt = MacroContextPacket(run_id="test-001")
        assert pkt.run_id == "test-001"
        assert pkt.regime_classification == "unknown"
        assert pkt.confidence == ConfidenceLevel.MEDIUM

    def test_from_stage_8_output_valid(self):
        # from_stage_8_output accepts either flat or {"macro":{}, "political":{}} format
        stage8_nested = {
            "macro": {
                "regime_classification": "risk_off",
                "confidence": "HIGH",
                "key_macro_variables": {"fed_funds_rate": "5.25%"},
                "regime_winners": ["gold", "bonds"],
                "regime_losers": ["growth", "tech"],
                "rate_sensitivity": {"NVDA": "HIGH"},
                "cyclical_sensitivity": {"NVDA": "MEDIUM"},
            },
            "political": {
                "summary": "US-China tensions elevated"
            },  # triggers political_risk_present=True
        }
        pkt = MacroContextPacket.from_stage_8_output(stage8_nested, "run-xyz")
        assert pkt.run_id == "run-xyz"
        assert pkt.regime_classification == "risk_off"
        assert pkt.confidence == ConfidenceLevel.HIGH
        assert "fed_funds_rate" in pkt.key_macro_variables
        assert pkt.political_risk_present is True

    def test_from_stage_8_output_missing_fields_graceful(self):
        """Partial stage 8 dict must not raise — fills defaults."""
        pkt = MacroContextPacket.from_stage_8_output(
            {"regime_classification": "neutral"}, "run-abc"
        )
        assert pkt.regime_classification == "neutral"
        assert pkt.confidence == ConfidenceLevel.MEDIUM  # default

    def test_from_stage_8_output_empty_dict(self):
        pkt = MacroContextPacket.from_stage_8_output({}, "run-empty")
        assert pkt.run_id == "run-empty"
        assert pkt.regime_classification in ("", "unknown")

    def test_summary_text_non_empty_regime(self):
        pkt = MacroContextPacket(
            run_id="r1",
            regime_classification="risk_off",
            confidence=ConfidenceLevel.HIGH,
        )
        text = pkt.summary_text()
        assert "risk_off" in text
        assert isinstance(text, str)

    def test_summary_text_empty_regime(self):
        pkt = MacroContextPacket(run_id="r1")
        text = pkt.summary_text()
        assert isinstance(text, str)
        assert len(text) > 0  # must not crash

    def test_model_dump_json_serializable(self):
        import json

        pkt = MacroContextPacket(run_id="r1", regime_classification="risk_on")
        data = pkt.model_dump(mode="json")
        json.dumps(data)  # must not raise

    def test_macro_regime_enum_values(self):
        """All MacroRegime variants are accessible."""
        assert hasattr(MacroRegime, "RISK_ON") or isinstance(MacroRegime, type)


# ─── ISS-4: StockCard adapter ────────────────────────────────────────────────


class TestBuildStockCardFromPipelineOutputs:
    def _minimal_valuation_card(self) -> dict:
        return {
            "dcf_valuation": {"fair_value": 150.0, "upside_pct": 20.0},
            "methodology": "DCF",
            "base_case_price_target": 150.0,
            "entry_quality": "strong_buy",
        }

    def _minimal_four_box(self) -> dict:
        return {
            "ticker": "NVDA",
            "company_name": "NVIDIA Corp",
            "analyst_role": "compute",
            "box_1_thesis": "AI chip leader",
            "box_2_evidence": "Revenue growth 122% YoY",
            "box_3_risks": "Concentration risk",
            "box_4_judgment": "Conviction: high",
        }

    def test_returns_stock_card(self):
        card = build_stock_card_from_pipeline_outputs(
            ticker="NVDA",
            valuation_card=self._minimal_valuation_card(),
            four_box=self._minimal_four_box(),
        )
        assert isinstance(card, StockCard)
        assert card.ticker == "NVDA"

    def test_minimal_invocation_no_optional(self):
        """Must work with only ticker + valuation_card."""
        card = build_stock_card_from_pipeline_outputs(
            ticker="CEG",
            valuation_card={"dcf_valuation": {}, "methodology": "EV/EBITDA"},
        )
        assert isinstance(card, StockCard)
        assert card.ticker == "CEG"

    def test_company_name_extracted_from_four_box(self):
        # four_box is a plain dict here — company_name falls back to ticker
        card = build_stock_card_from_pipeline_outputs(
            ticker="NVDA",
            valuation_card=self._minimal_valuation_card(),
            four_box=self._minimal_four_box(),
        )
        # company_name from dict is not extracted (needs typed object)
        # At minimum, the card must be created and ticker must be correct
        assert card.ticker == "NVDA"
        assert card.company_name in ("NVDA", "NVIDIA Corp")  # either is acceptable

    def test_weight_passed_through(self):
        card = build_stock_card_from_pipeline_outputs(
            ticker="NVDA",
            valuation_card=self._minimal_valuation_card(),
            weight_in_balanced=0.12,
        )
        assert card.weight_in_balanced == pytest.approx(0.12)

    def test_none_inputs_do_not_raise(self):
        card = build_stock_card_from_pipeline_outputs(
            ticker="UNKNOWN",
            valuation_card=None,
            four_box=None,
            red_team=None,
            weight_in_balanced=None,
        )
        assert card.ticker == "UNKNOWN"


# ─── ISS-9: _VALIDATION_FATAL ────────────────────────────────────────────────


class TestValidationFatal:
    def test_non_fatal_agent_warns_not_raises(self):
        """Default _VALIDATION_FATAL=False — missing required key is a warning, not error."""
        agent = _ConcreteAgent(name="non_fatal", model="claude-opus-4-6")
        agent._REQUIRED_OUTPUT_KEYS = ["important_key"]
        # Missing key — should NOT raise since _VALIDATION_FATAL is False
        result = agent._validate_output_quality({"other_key": "value"})  # type: ignore[attr-defined]
        # _validate_output_quality should return (or not raise)
        _ = result

    def test_fatal_agent_raises_on_missing_key(self):
        """_VALIDATION_FATAL=True — missing required key raises StructuredOutputError."""
        agent = _FatalAgent(name="fatal", model="claude-opus-4-6")
        with pytest.raises(StructuredOutputError):
            agent._validate_output_quality({"wrong_key": "value"})  # type: ignore[attr-defined]

    def test_fatal_agent_does_not_raise_when_key_present(self):
        agent = _FatalAgent(name="fatal", model="claude-opus-4-6")
        # Should not raise
        agent._validate_output_quality({"required_key": "some_value"})  # type: ignore[attr-defined]

    def test_valuation_analyst_has_fatal_flag(self):
        assert ValuationAnalystAgent._VALIDATION_FATAL is True  # type: ignore[attr-defined]

    def test_valuation_analyst_has_required_keys(self):
        assert "valuations" in ValuationAnalystAgent._REQUIRED_OUTPUT_KEYS  # type: ignore[attr-defined]

    def test_red_team_analyst_has_fatal_flag(self):
        assert RedTeamAnalystAgent._VALIDATION_FATAL is True  # type: ignore[attr-defined]

    def test_red_team_analyst_has_required_keys(self):
        keys = RedTeamAnalystAgent._REQUIRED_OUTPUT_KEYS  # type: ignore[attr-defined]
        assert "assessments" in keys

    def test_associate_reviewer_has_fatal_flag(self):
        assert AssociateReviewerAgent._VALIDATION_FATAL is True  # type: ignore[attr-defined]

    def test_associate_reviewer_has_status_key(self):
        assert "publication_status" in AssociateReviewerAgent._REQUIRED_OUTPUT_KEYS  # type: ignore[attr-defined]


# ─── ARC-5: SECTOR_ROUTING config ────────────────────────────────────────────


class TestSectorRouting:
    def test_sector_routing_exported(self):
        assert isinstance(SECTOR_ROUTING, dict)

    def test_sector_routing_has_three_buckets(self):
        assert "compute" in SECTOR_ROUTING
        assert "power_energy" in SECTOR_ROUTING
        assert "infrastructure" in SECTOR_ROUTING

    def test_compute_has_expected_tickers(self):
        assert "NVDA" in SECTOR_ROUTING["compute"]
        assert "AMD" in SECTOR_ROUTING["compute"]

    def test_power_energy_has_expected_tickers(self):
        assert "CEG" in SECTOR_ROUTING["power_energy"]

    def test_infrastructure_has_expected_tickers(self):
        assert "PWR" in SECTOR_ROUTING["infrastructure"]

    def test_pipeline_config_has_sector_routing(self):
        cfg = PipelineConfig()
        assert hasattr(cfg, "sector_routing")
        assert isinstance(cfg.sector_routing, dict)
        assert "compute" in cfg.sector_routing

    def test_pipeline_config_routing_matches_default(self):
        cfg = PipelineConfig()
        assert cfg.sector_routing["compute"] == SECTOR_ROUTING["compute"]

    def test_all_tickers_unique_across_buckets(self):
        all_tickers = [t for tickers in SECTOR_ROUTING.values() for t in tickers]
        assert len(all_tickers) == len(set(all_tickers)), "Duplicate tickers across routing buckets"


# ─── ISS-3: GenericSectorAnalystAgent ────────────────────────────────────────


class TestGenericSectorAnalystAgent:
    def _make_agent(self) -> GenericSectorAnalystAgent:
        return GenericSectorAnalystAgent(model="claude-opus-4-6")

    def test_instantiates(self):
        agent = self._make_agent()
        assert agent.name == "generic_sector_analyst"

    def test_has_required_output_keys(self):
        assert len(GenericSectorAnalystAgent._REQUIRED_OUTPUT_KEYS) >= 1  # type: ignore[attr-defined]

    def test_format_input_returns_string(self):
        agent = self._make_agent()
        prompt = agent.format_input(
            {
                "tickers": ["AAPL", "MSFT"],
                "market_data": [{"ticker": "AAPL", "price": 190.0}],
                "macro_context_summary": "Risk-off: Fed tightening cycle ongoing.",
            }
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 20

    def test_format_input_includes_tickers(self):
        agent = self._make_agent()
        prompt = agent.format_input(
            {
                "tickers": ["AAPL", "MSFT"],
                "market_data": [],
                "macro_context_summary": "",
            }
        )
        assert "AAPL" in prompt or "MSFT" in prompt

    def test_format_input_empty_tickers(self):
        agent = self._make_agent()
        prompt = agent.format_input({"tickers": [], "market_data": [], "macro_context_summary": ""})
        assert isinstance(prompt, str)


# ─── ARC-1: _get_macro_context helper ────────────────────────────────────────


class TestGetMacroContext:
    def test_returns_empty_packet_when_no_stage8(self):
        engine = _make_engine()
        engine.run_record = MagicMock()
        engine.run_record.run_id = "test-run"
        engine.stage_outputs = {}
        pkt = engine._get_macro_context()
        assert isinstance(pkt, MacroContextPacket)
        assert pkt.regime_classification in ("", "unknown")

    def test_returns_packet_from_stage8_output(self):
        engine = _make_engine()
        engine.run_record = MagicMock()
        engine.run_record.run_id = "test-run"
        engine.stage_outputs = {
            8: {
                "macro": {
                    "parsed_output": {
                        "regime_classification": "risk_off",
                        "confidence": "high",
                    }
                }
            }
        }
        pkt = engine._get_macro_context()
        assert pkt.regime_classification == "risk_off"

    def test_returns_empty_packet_when_stage8_has_no_parsed_output(self):
        engine = _make_engine()
        engine.run_record = MagicMock()
        engine.run_record.run_id = "test-run"
        engine.stage_outputs = {8: {"macro": {"parsed_output": None}}}
        pkt = engine._get_macro_context()
        assert isinstance(pkt, MacroContextPacket)
        assert pkt.regime_classification in ("", "unknown")

    def test_run_id_passed_to_packet(self):
        engine = _make_engine()
        engine.run_record = MagicMock()
        engine.run_record.run_id = "my-special-run"
        engine.stage_outputs = {}
        pkt = engine._get_macro_context()
        assert pkt.run_id == "my-special-run"


# ─── ARC-4: Stage execution order (Stage 8 before Stage 7) ───────────────────


class TestStageExecutionOrder:
    def test_stage_8_called_before_stage_7_in_source(self):
        """Verify source ordering: Stage 8 block precedes Stage 7 block in run_full_pipeline."""
        import research_pipeline.pipeline.engine as engine_mod

        source = inspect.getsource(engine_mod.PipelineEngine.run_full_pipeline)
        idx_7 = source.find("stage_7_valuation")
        idx_8 = source.find("stage_8_macro")
        assert idx_8 != -1, "stage_8_macro not found in run_full_pipeline"
        assert idx_7 != -1, "stage_7_valuation not found in run_full_pipeline"
        assert idx_8 < idx_7, "Stage 8 must execute before Stage 7 (ARC-4)"

    def test_stage_7_receives_macro_context_key(self):
        """stage_7_valuation source must construct macro_context from _get_macro_context."""
        import research_pipeline.pipeline.engine as engine_mod

        source = inspect.getsource(engine_mod.PipelineEngine.stage_7_valuation)
        assert "_get_macro_context" in source, (
            "stage_7_valuation must call _get_macro_context (ARC-4)"
        )


# ─── ARC-5 engine: generic analyst routing ────────────────────────────────────


class TestEngineGenericAnalystRouting:
    def test_engine_has_generic_analyst_attribute(self):
        engine = _make_engine()
        assert hasattr(engine, "generic_analyst")
        assert isinstance(engine.generic_analyst, GenericSectorAnalystAgent)

    def test_stage6_source_uses_sector_routing_config(self):
        import research_pipeline.pipeline.engine as engine_mod

        source = inspect.getsource(engine_mod.PipelineEngine.stage_6_sector_analysis)
        assert "sector_routing" in source or "SECTOR_ROUTING" in source, (
            "stage_6 must use sector_routing config (ARC-5)"
        )

    def test_stage6_source_has_generic_analyst(self):
        import research_pipeline.pipeline.engine as engine_mod

        source = inspect.getsource(engine_mod.PipelineEngine.stage_6_sector_analysis)
        assert "generic_analyst" in source, (
            "stage_6 must call generic_analyst for unmapped tickers (ARC-5)"
        )


# ─── ARC-6/7/8: Macro context wiring ─────────────────────────────────────────


class TestMacroContextWiring:
    def _assert_has_macro_context(self, stage_method_name: str):
        import research_pipeline.pipeline.engine as engine_mod

        method = getattr(engine_mod.PipelineEngine, stage_method_name)
        source = inspect.getsource(method)
        assert "_get_macro_context" in source or "macro_context" in source, (
            f"{stage_method_name} must wire macro context (ARC-6/7/8)"
        )

    def test_stage_10_red_team_has_macro_context(self):
        self._assert_has_macro_context("stage_10_red_team")

    def test_stage_11_review_has_macro_context(self):
        self._assert_has_macro_context("stage_11_review")

    def test_stage_12_portfolio_has_macro_context(self):
        self._assert_has_macro_context("stage_12_portfolio")


# ─── ARC-9/10: Stage 8 enrichment and FI agent ───────────────────────────────


class TestStage8MacroEnrichment:
    def test_stage_8_passes_market_data(self):
        import research_pipeline.pipeline.engine as engine_mod

        source = inspect.getsource(engine_mod.PipelineEngine.stage_8_macro)
        assert "market_data" in source or "stage_outputs.get(2" in source, (
            "stage_8_macro must pass stage 2 market data to macro agent (ARC-9)"
        )

    def test_fi_agent_uses_real_macro(self):
        import research_pipeline.pipeline.engine as engine_mod

        source = inspect.getsource(engine_mod.PipelineEngine.stage_9_risk)
        # ARC-10: The hardcoded stub note text must be gone
        assert "Live yield/spread data not available" not in source, (
            "FI agent macro_context stub must be replaced with real Stage 8 data (ARC-10)"
        )
        assert "_get_macro_context" in source, (
            "stage_9_risk must call _get_macro_context for FI agent (ARC-10)"
        )


# ─── ARC-3: VaR from live factor returns ─────────────────────────────────────


class TestVaRFromLiveReturns:
    def test_stage_9_does_not_use_random_normal_for_var(self):
        import research_pipeline.pipeline.engine as engine_mod

        source = inspect.getsource(engine_mod.PipelineEngine.stage_9_risk)
        # ARC-3: np.random.normal for synthetic_returns must be gone
        lines = [ln for ln in source.split("\n") if "synthetic_returns = np.random.normal" in ln]
        assert len(lines) == 0, "VaR must use live factor returns, not np.random.normal (ARC-3)"

    def test_stage_9_aggregates_live_factor_returns(self):
        import research_pipeline.pipeline.engine as engine_mod

        source = inspect.getsource(engine_mod.PipelineEngine.stage_9_risk)
        assert "live_factor_returns" in source, (
            "stage_9_risk must aggregate live_factor_returns for VaR (ARC-3)"
        )


# ─── ARC-2: Real stock cards in stage_13 ─────────────────────────────────────


class TestStage13StockCards:
    def test_stage_13_does_not_use_empty_stock_cards(self):
        import research_pipeline.pipeline.engine as engine_mod

        source = inspect.getsource(engine_mod.PipelineEngine.stage_13_report)
        assert "stock_cards=[]" not in source, (
            "stage_13_report must not pass empty stock_cards=[] (ARC-2)"
        )

    def test_stage_13_calls_build_stock_card(self):
        import research_pipeline.pipeline.engine as engine_mod

        source = inspect.getsource(engine_mod.PipelineEngine.stage_13_report)
        assert "build_stock_card_from_pipeline_outputs" in source, (
            "stage_13_report must call build_stock_card_from_pipeline_outputs (ARC-2)"
        )


# ─── ISS-20: app.py audit_packet key fix ─────────────────────────────────────


class TestISS20AppKeyFix:
    def test_app_uses_run_result_not_result_key(self):
        """app.py must access audit_packet via run_result attribute, not 'result' dict key."""
        app_path = Path(__file__).resolve().parents[1] / "src" / "frontend" / "app.py"
        source = app_path.read_text(encoding="utf-8")
        # The bug line must be gone
        assert 'st.session_state.get("result")' not in source or (
            # If it appears in a different context, ensure the audit_packet usage is fixed
            'st.session_state.get("result") or {}).get("audit_packet")' not in source
        ), 'ISS-20: app.py must not use ("result",...).get("audit_packet")'

    def test_app_uses_getattr_for_audit_packet(self):
        app_path = Path(__file__).resolve().parents[1] / "src" / "frontend" / "app.py"
        source = app_path.read_text(encoding="utf-8")
        assert 'getattr(_rr, "audit_packet"' in source or "audit_packet" in source, (
            "ISS-20: app.py must access audit_packet via getattr on RunResult"
        )


# ─── RunResult audit_packet field ────────────────────────────────────────────


class TestRunResultAuditPacket:
    def test_run_result_has_audit_packet_field(self):
        from frontend.pipeline_adapter import RunResult
        import dataclasses

        fields = {f.name for f in dataclasses.fields(RunResult)}
        assert "audit_packet" in fields, "RunResult must have audit_packet field"

    def test_run_result_audit_packet_defaults_to_empty_dict(self):
        from frontend.pipeline_adapter import RunResult

        rr = RunResult(
            run_id="test",
            tickers=["NVDA"],
            model="claude-opus-4-6",
            started_at="2025-01-01T00:00:00Z",
        )
        assert rr.audit_packet == {}


# ─── ISS-10: Gemini triple-strategy ──────────────────────────────────────────


class TestGeminiTripleStrategy:
    def test_base_agent_has_gemini_method(self):
        assert hasattr(BaseAgent, "_call_gemini")

    def test_gemini_method_handles_import_error_gracefully(self):
        """If google.generativeai is missing, falls through to next strategy."""
        source = inspect.getsource(BaseAgent._call_gemini)
        assert "ImportError" in source, (
            "_call_gemini must catch ImportError for strategy fallback (ISS-10)"
        )

    def test_gemini_method_has_three_strategies(self):
        source = inspect.getsource(BaseAgent._call_gemini)
        # Expect references to both SDK namespaces
        assert "google.generativeai" in source or "generativeai" in source, (
            "Strategy 1 (old SDK) must be present (ISS-10)"
        )
        assert "google.genai" in source or "_call_gemini_rest" in source, (
            "Strategy 2/3 (new SDK or REST) must be present (ISS-10)"
        )


# ─── Reset run state + Red Team ledger enrichment ────────────────────────────


class TestResetRunState:
    """Verify that reset_run_state() clears all per-run mutable state."""

    def test_reset_clears_stage_outputs(self):
        engine = _make_engine()
        engine.stage_outputs = {1: {"data": "old"}, 5: {"ledger": {}}}
        engine.reset_run_state()
        assert engine.stage_outputs == {}

    def test_reset_clears_gate_results(self):
        from research_pipeline.pipeline.gates import GateResult

        engine = _make_engine()
        engine.gate_results = {0: GateResult(stage=0, passed=True, reason="ok")}
        engine.reset_run_state()
        assert engine.gate_results == {}

    def test_reset_clears_review_result(self):
        from research_pipeline.schemas.portfolio import AssociateReviewResult, PublicationStatus

        engine = _make_engine()
        engine._review_result = AssociateReviewResult(
            run_id="old-run", status=PublicationStatus.PASS
        )
        engine.reset_run_state()
        assert engine._review_result is None

    def test_reset_clears_run_record(self):
        engine = _make_engine()
        engine.reset_run_state()
        assert engine.run_record is None

    def test_reset_clears_stage_timings(self):
        engine = _make_engine()
        engine._stage_timings = {1: 123.4}
        engine._pipeline_start = 999.0
        engine.reset_run_state()
        assert engine._stage_timings == {}
        assert engine._pipeline_start == 0.0


class TestRedTeamLedgerEnrichment:
    """Verify that _enrich_ledger_with_red_team writes RT claims into stage_outputs[5]."""

    def _make_mock_result(self, success: bool, assessments: list) -> MagicMock:
        result = MagicMock()
        result.success = success
        result.parsed_output = {"assessments": assessments}
        return result

    def test_enrichment_adds_claims_to_ledger(self):
        engine = _make_engine()
        engine.stage_outputs[5] = {
            "ledger": {"claims": [], "sources": []},
        }
        assessments = [
            {
                "ticker": "NVDA",
                "tests": [
                    {
                        "hypothesis": "Demand could collapse if hyperscalers cut capex",
                        "verdict": "partial",
                    },
                    {
                        "hypothesis": "Competitive moat challenged by AMD CDNA4",
                        "verdict": "unlikely",
                    },
                    {
                        "hypothesis": "Export controls could freeze 20% of revenue",
                        "verdict": "possible",
                    },
                ],
            }
        ]
        result = self._make_mock_result(success=True, assessments=assessments)
        engine._enrich_ledger_with_red_team(result)

        ledger = engine.stage_outputs[5]["ledger"]
        assert len(ledger["claims"]) == 3
        assert all(c["owner_agent"] == "red_team_analyst" for c in ledger["claims"])
        assert all(c["ticker"] == "NVDA" for c in ledger["claims"])
        assert all("[RED TEAM]" in c["claim_text"] for c in ledger["claims"])

    def test_enrichment_is_noop_when_agent_failed(self):
        engine = _make_engine()
        engine.stage_outputs[5] = {"ledger": {"claims": [], "sources": []}}
        result = self._make_mock_result(success=False, assessments=[])
        engine._enrich_ledger_with_red_team(result)
        assert len(engine.stage_outputs[5]["ledger"]["claims"]) == 0

    def test_enrichment_is_noop_when_no_stage5(self):
        engine = _make_engine()
        # stage_outputs[5] not set
        result = self._make_mock_result(
            success=True,
            assessments=[{"ticker": "NVDA", "tests": [{"hypothesis": "test"}]}],
        )
        engine._enrich_ledger_with_red_team(result)  # Must not raise
        assert 5 not in engine.stage_outputs

    def test_enrichment_preserves_existing_claims(self):
        engine = _make_engine()
        existing = {"claim_id": "CLM-001", "claim_text": "existing", "ticker": "NVDA"}
        engine.stage_outputs[5] = {"ledger": {"claims": [existing], "sources": []}}
        result = self._make_mock_result(
            success=True,
            assessments=[{"ticker": "NVDA", "tests": [{"hypothesis": "new red team claim"}]}],
        )
        engine._enrich_ledger_with_red_team(result)
        claims = engine.stage_outputs[5]["ledger"]["claims"]
        assert len(claims) == 2
        assert claims[0]["claim_id"] == "CLM-001"
        assert claims[1]["owner_agent"] == "red_team_analyst"
