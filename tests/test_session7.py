"""Session 7 targeted tests.

Covers:
  - ACT-S7-1: BHB Performance Attribution (synthetic returns) wired into Stage 14
  - ACT-S7-2: ESG data enrichment — ESGService baseline profiles passed to EsgAnalystAgent
  - ACT-S7-3: SelfAuditPacket per-stage latencies and total_pipeline_duration_s
  - ACT-S7-4: Portfolio weights optimiser (risk parity / min-var / max-sharpe) in Stage 12
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from research_pipeline.agents.base_agent import AgentResult
from research_pipeline.agents.esg_analyst import EsgAnalystAgent
from research_pipeline.config.loader import PipelineConfig
from research_pipeline.config.settings import APIKeys, Settings
from research_pipeline.pipeline.engine import PipelineEngine
from research_pipeline.schemas.governance import SelfAuditPacket
from research_pipeline.services.esg_service import ESGService
from research_pipeline.services.portfolio_optimisation import PortfolioOptimisationEngine


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures & helpers (mirrored from test_session6)
# ─────────────────────────────────────────────────────────────────────────────

S7_UNIVERSE = ["NVDA", "AVGO", "TSM"]


@pytest.fixture
def s7_settings(tmp_path: Path) -> Settings:
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
def s7_config() -> PipelineConfig:
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
        run_id="S7-TEST",
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
    """Patch every LLM agent so the smoke pipeline runs without network calls."""
    engine.orchestrator_agent.run = AsyncMock(
        return_value=_ar("orchestrator", {"status": "proceed", "universe": S7_UNIVERSE})
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
            {"sector_outputs": [_sector_out(t) for t in S7_UNIVERSE]},
        )
    )
    engine.power_analyst.run = AsyncMock(
        return_value=_ar("sector_analyst_power", {"sector_outputs": []})
    )
    engine.infra_analyst.run = AsyncMock(
        return_value=_ar("sector_analyst_infrastructure", {"sector_outputs": []})
    )
    engine.esg_analyst_agent.run = AsyncMock(
        return_value=_ar(
            "esg_analyst",
            {"esg_scores": [_esg_entry(t) for t in S7_UNIVERSE], "parse_violations": []},
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
                            {"ticker": t, "weight_pct": 100 / len(S7_UNIVERSE)} for t in S7_UNIVERSE
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
                "methodology_note": "10y yield tracking",
            },
        )
    )


@pytest.fixture
def s7_engine(s7_settings, s7_config, tmp_path):
    """Fully mocked PipelineEngine for session 7 smoke runs."""
    engine = PipelineEngine(s7_settings, s7_config)
    _patch_all_agents(engine)

    # Patch ingestor to return deterministic market data
    async def _mock_ingest(tickers):
        return [_ingest_row(t) for t in tickers]

    engine.ingestor.ingest_universe = _mock_ingest
    return engine


@pytest.fixture
def s7_result(s7_engine):
    """Run the full pipeline once and return the result dict."""
    return asyncio.run(s7_engine.run_full_pipeline(S7_UNIVERSE))


# ─────────────────────────────────────────────────────────────────────────────
# ACT-S7-1: Performance Attribution
# ─────────────────────────────────────────────────────────────────────────────


class TestPerformanceAttribution:
    """Tests for BHB attribution wired into Stage 14."""

    def test_synthetic_returns_shape(self, s7_engine):
        """_generate_synthetic_returns returns n_days values per ticker."""
        result = s7_engine._generate_synthetic_returns(["NVDA", "AVGO"], n_days=63)
        assert set(result.keys()) == {"NVDA", "AVGO"}
        assert len(result["NVDA"]) == 63
        assert len(result["AVGO"]) == 63

    def test_synthetic_returns_deterministic(self, s7_engine):
        """Same ticker and seed_offset always produces the same return series."""
        r1 = s7_engine._generate_synthetic_returns(["NVDA"], n_days=30, seed_offset=0)
        r2 = s7_engine._generate_synthetic_returns(["NVDA"], n_days=30, seed_offset=0)
        assert r1["NVDA"] == r2["NVDA"]

    def test_synthetic_returns_different_seeds(self, s7_engine):
        """Different seed_offset produces different returns."""
        r1 = s7_engine._generate_synthetic_returns(["NVDA"], n_days=50, seed_offset=0)
        r2 = s7_engine._generate_synthetic_returns(["NVDA"], n_days=50, seed_offset=99)
        assert r1["NVDA"] != r2["NVDA"]

    def test_bhb_attribution_in_stage14(self, s7_engine, s7_result):
        """Stage 14 output contains an 'attribution' dict after a full run."""
        attribution = s7_engine.stage_outputs.get(14, {}).get("attribution", {})
        assert isinstance(attribution, dict)
        assert attribution  # non-empty

    def test_bhb_attribution_mandatory_fields(self, s7_engine, s7_result):
        """All BHB return fields are present in the attribution output."""
        attribution = s7_engine.stage_outputs[14]["attribution"]
        for field in (
            "total_portfolio_return_pct",
            "total_benchmark_return_pct",
            "excess_return_pct",
            "allocation_effect_pct",
            "selection_effect_pct",
            "interaction_effect_pct",
        ):
            assert field in attribution, f"Missing field: {field}"

    def test_bhb_decomposition_approximate(self, s7_engine, s7_result):
        """Allocation + Selection + Interaction approximately equals Excess Return."""
        attr = s7_engine.stage_outputs[14]["attribution"]
        alloc = attr["allocation_effect_pct"]
        sel = attr["selection_effect_pct"]
        interact = attr["interaction_effect_pct"]
        excess = attr["excess_return_pct"]
        # BHB identity: alloc + sel + interact = excess (within floating-point tolerance)
        assert abs((alloc + sel + interact) - excess) < 0.1, (
            f"BHB identity failed: {alloc} + {sel} + {interact} = "
            f"{alloc + sel + interact} != {excess}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# ACT-S7-4: Portfolio Optimisation
# ─────────────────────────────────────────────────────────────────────────────


class TestPortfolioOptimisation:
    """Tests for risk-parity / min-variance / max-sharpe wired into Stage 12."""

    def test_three_methods_in_stage12(self, s7_engine, s7_result):
        """Stage 12 output contains all three optimisation methods."""
        opt = s7_engine.stage_outputs.get(12, {}).get("optimisation_results", {})
        assert "risk_parity" in opt, "risk_parity missing from optimisation_results"
        assert "min_variance" in opt, "min_variance missing from optimisation_results"
        assert "max_sharpe" in opt, "max_sharpe missing from optimisation_results"

    def test_risk_parity_weights_non_empty(self, s7_engine, s7_result):
        """Risk parity weights dict is non-empty after a full run."""
        weights = s7_engine.stage_outputs[12]["optimisation_results"]["risk_parity"]["weights"]
        assert isinstance(weights, dict) and weights

    def test_risk_parity_weights_sum_to_100(self, s7_engine, s7_result):
        """Risk parity weights sum to approximately 100%."""
        weights = s7_engine.stage_outputs[12]["optimisation_results"]["risk_parity"]["weights"]
        total = sum(weights.values())
        assert abs(total - 100.0) < 1.0, f"Risk parity weights sum = {total}, expected ~100"

    def test_min_variance_weights_sum_to_100(self, s7_engine, s7_result):
        """Min-variance weights sum to approximately 100%."""
        weights = s7_engine.stage_outputs[12]["optimisation_results"]["min_variance"]["weights"]
        total = sum(weights.values())
        assert abs(total - 100.0) < 1.0, f"Min-variance weights sum = {total}, expected ~100"

    def test_standalone_optimiser_risk_parity(self):
        """PortfolioOptimisationEngine.compute_risk_parity works independently."""
        import numpy as np

        rng = np.random.default_rng(42)
        tickers = ["A", "B", "C"]
        returns = {t: rng.normal(0.0005, 0.02, 252).tolist() for t in tickers}
        engine = PortfolioOptimisationEngine()
        result = engine.compute_risk_parity(tickers, returns)
        assert result.method == "risk_parity"
        assert set(result.weights.keys()) == set(tickers)
        assert abs(sum(result.weights.values()) - 100.0) < 1.0


# ─────────────────────────────────────────────────────────────────────────────
# ACT-S7-2: ESG Data Enrichment
# ─────────────────────────────────────────────────────────────────────────────


class TestEsgDataEnrichment:
    """Tests for ESGService baseline profiles enriching EsgAnalystAgent prompts."""

    def test_format_input_includes_baseline_section(self):
        """format_input includes 'ESG BASELINE PROFILES' when profiles are provided."""
        agent = EsgAnalystAgent(
            model="claude-opus-4-6",
            prompts_dir=Path("/tmp"),
        )
        baseline_profiles = [
            {
                "ticker": "NVDA",
                "overall_rating": "AA",
                "environmental_score": 6.5,
                "social_score": 7.0,
                "governance_score": 8.0,
                "controversy_flag": False,
            }
        ]
        rendered = agent.format_input(
            {
                "tickers": ["NVDA"],
                "esg_baseline_profiles": baseline_profiles,
            }
        )
        assert "ESG BASELINE PROFILES" in rendered
        assert "NVDA" in rendered

    def test_format_input_empty_baseline_no_section(self):
        """When no baseline profiles are supplied the section is omitted."""
        agent = EsgAnalystAgent(
            model="claude-opus-4-6",
            prompts_dir=Path("/tmp"),
        )
        rendered = agent.format_input({"tickers": ["NVDA"], "esg_baseline_profiles": []})
        assert "ESG BASELINE PROFILES" not in rendered

    def test_format_input_baseline_scores_visible(self):
        """E/S/G scores from baseline profiles appear in the formatted prompt."""
        agent = EsgAnalystAgent(
            model="claude-opus-4-6",
            prompts_dir=Path("/tmp"),
        )
        rendered = agent.format_input(
            {
                "tickers": ["META"],
                "esg_baseline_profiles": [
                    {
                        "ticker": "META",
                        "overall_rating": "BBB",
                        "environmental_score": 5.5,
                        "social_score": 4.5,
                        "governance_score": 6.0,
                        "controversy_flag": True,
                    }
                ],
            }
        )
        assert "E=5.5" in rendered or "5.5" in rendered
        # Controversy flag should be flagged
        assert "controversy" in rendered.lower()

    def test_esg_service_returns_profiles_for_known_tickers(self):
        """ESGService.get_portfolio_scores returns correct ESGScore objects."""
        svc = ESGService()
        scores = svc.get_portfolio_scores(["NVDA", "META"])
        assert len(scores) == 2
        tickers_returned = {s.ticker for s in scores}
        assert tickers_returned == {"NVDA", "META"}
        # NVDA should have no controversy (established heuristic)
        nvda = next(s for s in scores if s.ticker == "NVDA")
        assert nvda.controversy_flag is False
        # META should have controversy=True
        meta = next(s for s in scores if s.ticker == "META")
        assert meta.controversy_flag is True

    def test_engine_passes_baseline_to_esg_agent(self, s7_engine, s7_result):
        """The ESG analyst agent was called with 'esg_baseline_profiles' in its inputs."""
        call_args = s7_engine.esg_analyst_agent.run.call_args
        # Second positional arg is the context dict
        context = call_args[0][1]
        assert "esg_baseline_profiles" in context, (
            f"ESG agent not receiving esg_baseline_profiles: context keys = {list(context.keys())}"
        )
        assert isinstance(context["esg_baseline_profiles"], list)


# ─────────────────────────────────────────────────────────────────────────────
# ACT-S7-3: SelfAuditPacket Latency Fields
# ─────────────────────────────────────────────────────────────────────────────


class TestSelfAuditLatency:
    """Tests for per-stage timing fields in SelfAuditPacket."""

    def test_schema_has_latency_fields(self):
        """SelfAuditPacket model has the two new latency fields."""
        fields = SelfAuditPacket.model_fields
        assert "stage_latencies_ms" in fields, "Missing stage_latencies_ms field"
        assert "total_pipeline_duration_s" in fields, "Missing total_pipeline_duration_s field"

    def test_latency_field_defaults(self):
        """Latency fields default to empty dict and 0.0 respectively."""
        packet = SelfAuditPacket(run_id="test")
        assert packet.stage_latencies_ms == {}
        assert packet.total_pipeline_duration_s == 0.0

    def test_stage_latencies_populated_after_run(self, s7_engine, s7_result):
        """After a full run, audit_packet.stage_latencies_ms is non-empty."""
        audit = s7_result.get("audit_packet") or {}
        latencies = audit.get("stage_latencies_ms", {})
        assert latencies, "stage_latencies_ms is empty — timing was not captured"

    def test_stage_latency_keys_format(self, s7_engine, s7_result):
        """All latency keys match the 'stage_N' format."""
        audit = s7_result.get("audit_packet") or {}
        latencies = audit.get("stage_latencies_ms", {})
        for key in latencies:
            assert re.match(r"^stage_\d+$", key), f"Unexpected latency key format: '{key}'"

    def test_total_pipeline_duration_positive(self, s7_engine, s7_result):
        """total_pipeline_duration_s is a positive number after a full run."""
        audit = s7_result.get("audit_packet") or {}
        dur = audit.get("total_pipeline_duration_s", 0)
        assert dur > 0, f"Expected positive duration, got {dur}"

    def test_latency_values_are_positive_numbers(self, s7_engine, s7_result):
        """All per-stage latency values are positive floats."""
        audit = s7_result.get("audit_packet") or {}
        latencies = audit.get("stage_latencies_ms", {})
        for key, ms in latencies.items():
            assert isinstance(ms, (int, float)) and ms >= 0, f"Latency for {key} is invalid: {ms}"

    def test_stage_timings_tracked_in_engine(self, s7_engine, s7_result):
        """Engine._stage_timings dict is populated after run_full_pipeline."""
        assert s7_engine._stage_timings, "_stage_timings was not populated"
        # Should have entries for all stages that ran (0 through 13 minimum)
        assert len(s7_engine._stage_timings) >= 14
