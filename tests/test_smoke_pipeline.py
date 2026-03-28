"""End-to-end pipeline smoke tests.

These tests run the full PipelineEngine through all 15 stages with mocked
external dependencies (no live API calls, no real LLM calls).

They verify:
  - PipelineEngine can be instantiated and orchestrates all stages correctly
  - Stage outputs persist to disk and stage_outputs[] is populated
  - Gate logic runs and a final result dict is returned
  - No stage crashes the pipeline (regression guard)

The mocking strategy:
  - MarketDataIngestor.ingest_universe → returns fixture market data
  - All agent.run() → returns AgentResult(success=True, parsed_output=<minimal valid output>)
  - All other deterministic services run unmodified (they have no API calls)
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from research_pipeline.agents.base_agent import AgentResult
from research_pipeline.config.loader import PipelineConfig
from research_pipeline.config.settings import APIKeys, Settings
from research_pipeline.pipeline.engine import PipelineEngine


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def smoke_settings(tmp_path: Path) -> Settings:
    """Settings with fake API keys and a temporary storage directory."""
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
def smoke_config() -> PipelineConfig:
    return PipelineConfig()


SMOKE_UNIVERSE = ["NVDA", "AVGO", "TSM"]   # must be ≥ 3 for gate_1; all compute tickers


def _ingest_result(ticker: str) -> dict:
    """Minimal market data dict that passes gate_2 *and* gate_4 (Data QA).

    DataQALineageService requires each row to have:
      - ticker   (gate_2 + data_qa schema check)
      - source   (data_qa schema + lineage check)
      - timestamp within 24 h (data_qa timestamp check)
    """
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


def _agent_result(agent_name: str, run_id: str, parsed_output: dict) -> AgentResult:
    return AgentResult(
        agent_name=agent_name,
        run_id=run_id,
        success=True,
        raw_response=json.dumps(parsed_output),
        parsed_output=parsed_output,
    )


def _sector_output(ticker: str) -> dict:
    return {
        "ticker": ticker,
        "company_name": f"{ticker} Corp",
        "date": "2026-03-28",
        "box1_verified_facts": f"{ticker} revenue grew Q4",
        "box2_management_guidance": "Strong guidance",
        "box3_consensus_market_view": "Consensus: Buy",
        "box4_analyst_judgment": "Conviction: high",
        "key_risks": "Competition and macro",
    }


def _make_agent_mocks(run_id: str) -> dict[str, AsyncMock]:
    """Build AsyncMock factories for all agent.run() methods."""
    return {
        "orchestrator": AsyncMock(return_value=_agent_result(
            "orchestrator", run_id,
            {"status": "proceed", "universe": SMOKE_UNIVERSE},
        )),
        "evidence": AsyncMock(return_value=_agent_result(
            "evidence_librarian", run_id,
            {"claims": [
                {
                    "claim_id": "CLM-001",
                    "ticker": "NVDA",
                    "claim_text": "NVDA data-center revenue was $18.4B in Q4 FY2025.",
                    "evidence_class": "primary_fact",
                    "source_id": "SRC-NVDA-10K-2025",
                    "confidence": "high",
                    "status": "pass",
                }
            ]},
        )),
        "compute": AsyncMock(return_value=_agent_result(
            "sector_analyst_compute", run_id,
            {"sector_outputs": [_sector_output(t) for t in SMOKE_UNIVERSE]},
        )),
        "power": AsyncMock(return_value=_agent_result(
            "sector_analyst_power", run_id,
            {"sector_outputs": []},
        )),
        "infra": AsyncMock(return_value=_agent_result(
            "sector_analyst_infrastructure", run_id,
            {"sector_outputs": []},
        )),
        "valuation": AsyncMock(return_value=_agent_result(
            "valuation_analyst", run_id,
            {"valuations": [{
                "ticker": "NVDA",
                "date": "2026-03-28",
                "section_5_scenarios": [{
                    "case": "base", "probability_pct": 50,
                    "revenue_cagr": "20%", "exit_multiple": "30x",
                    "exit_multiple_rationale": "sector median",
                    "implied_return_1y": "15%",
                    "implied_return_3y": "50% [HOUSE VIEW]",
                    "key_assumption": "data center demand holds",
                    "what_breaks_it": "hyperscaler capex cut",
                }],
                "entry_quality": "ACCEPTABLE",
                "methodology_tag": "HOUSE VIEW",
            }]},
        )),
        "macro": AsyncMock(return_value=_agent_result(
            "macro_strategist", run_id,
            {"regime": "expansion", "rate_outlook": "neutral",
             "usd_outlook": "stable", "equity_risk_premium": 5.0},
        )),
        "political": AsyncMock(return_value=_agent_result(
            "political_risk", run_id,
            {"risk_level": "low", "key_risks": ["US-China tech tensions"]},
        )),
        "red_team": AsyncMock(return_value=_agent_result(
            "red_team_analyst", run_id,
            {"assessments": [{
                "ticker": "NVDA",
                "section_2_falsification_tests": [
                    {"test_id": "FT-1", "test": "Hyperscaler spend cut >30%"},
                    {"test_id": "FT-2", "test": "AMD/Intel regain GPU share"},
                    {"test_id": "FT-3", "test": "Export controls tighten further"},
                ],
                "required_tests": {"hyperscaler_dependency": True},
            }]},
        )),
        "reviewer": AsyncMock(return_value=_agent_result(
            "associate_reviewer", run_id,
            {"status": "pass", "publication_status": "pass", "issues": [],
             "required_corrections": []},
        )),
        "portfolio": AsyncMock(return_value=_agent_result(
            "portfolio_manager", run_id,
            {"variants": [
                {"name": "balanced", "positions": [
                    {"ticker": "NVDA", "weight_pct": 35.0},
                    {"ticker": "AVGO", "weight_pct": 30.0},
                    {"ticker": "TSM",  "weight_pct": 35.0},
                ]},
                {"name": "higher_return", "positions": [
                    {"ticker": "NVDA", "weight_pct": 50.0},
                    {"ticker": "AVGO", "weight_pct": 30.0},
                    {"ticker": "TSM",  "weight_pct": 20.0},
                ]},
                {"name": "lower_volatility", "positions": [
                    {"ticker": "NVDA", "weight_pct": 25.0},
                    {"ticker": "AVGO", "weight_pct": 35.0},
                    {"ticker": "TSM",  "weight_pct": 40.0},
                ]},
            ]},
        )),
        "quant": AsyncMock(return_value=_agent_result(
            "quant_research_analyst", run_id,
            {
                "risk_signal": "neutral",
                "primary_concern": "Concentration risk in compute names",
                "recommended_action": "Monitor NVDA weight",
                "section_1_factor_interpretation": {"dominant_factors": ["momentum"]},
                "section_2_risk_assessment": {"var_95_commentary": "Moderate VaR"},
                "section_3_benchmark_divergence": {
                    "etf_differentiation_score": 60,
                    "etf_replication_risk": False,
                    "tracking_error_commentary": "High active share",
                    "active_bets_narrative": "NVDA +12% vs NDX",
                    "information_ratio_signal": "IR=0.7",
                    "etf_overlap_summary": "60% differentiated",
                },
                "section_4_construction_signal": {
                    "factor_tilt_recommendation": "Maintain",
                    "concentration_recommendation": "Trim NVDA",
                    "benchmark_recommendation": "Differentiated",
                    "constructive_changes": [],
                },
                "analyst_confidence": "medium",
                "data_quality_note": "Synthetic returns used",
            },
        )),
        "fixed_income": AsyncMock(return_value=_agent_result(
            "fixed_income_analyst", run_id,
            {
                "yield_curve_regime": "normal",
                "10y_yield_context": "4.3% — neutral for equities",
                "cost_of_capital_trend": "stable",
                "rate_sensitivity_score": 5.0,
                "key_risks": ["rate hike risk"],
                "offsetting_factors": ["strong earnings growth"],
                "sector_rotation_read": "neutral",
                "methodology_note": "Smoke test mock — no live yield data",
            },
        )),
    }


# ── Smoke tests ───────────────────────────────────────────────────────────

class TestPipelineEngineSmokeTest:
    """Full end-to-end pipeline smoke test with all external calls mocked."""

    def _build_engine(self, smoke_settings, smoke_config):
        return PipelineEngine(settings=smoke_settings, config=smoke_config)

    def _patch_agents(self, engine, mocks):
        engine.orchestrator_agent.run = mocks["orchestrator"]
        engine.evidence_agent.run = mocks["evidence"]
        engine.compute_analyst.run = mocks["compute"]
        engine.power_analyst.run = mocks["power"]
        engine.infra_analyst.run = mocks["infra"]
        engine.valuation_agent.run = mocks["valuation"]
        engine.macro_agent.run = mocks["macro"]
        engine.political_agent.run = mocks["political"]
        engine.red_team_agent.run = mocks["red_team"]
        engine.reviewer_agent.run = mocks["reviewer"]
        engine.pm_agent.run = mocks["portfolio"]
        engine.quant_analyst_agent.run = mocks["quant"]
        engine.fixed_income_agent.run = mocks["fixed_income"]

        # Mock mandate engine + IC: the 3-ticker smoke universe violates production
        # mandates (33% single-name > 15% max, 3/8 min positions).  These services
        # are deterministic — mock them so smoke tests verify orchestration not rules.
        from research_pipeline.schemas.governance import (
            CommitteeRecord, CommitteeVote, MandateCheckResult,
        )
        _mandate_ok = MandateCheckResult(
            run_id="smoke", mandate_id="smoke-mandate", is_compliant=True,
        )
        engine.mandate_engine.check_compliance = MagicMock(return_value=_mandate_ok)
        _ic_approved = CommitteeRecord(
            record_id="IC-smoke", run_id="smoke",
            outcome=CommitteeVote.APPROVE, quorum_met=True,
            minutes="Approved — smoke test mock",
        )
        engine.investment_committee.evaluate_and_vote = MagicMock(return_value=_ic_approved)

    @pytest.mark.asyncio
    async def test_pipeline_runs_to_completion(self, smoke_settings, smoke_config):
        """Pipeline should complete all 15 stages without crashing."""
        engine = self._build_engine(smoke_settings, smoke_config)
        ingest_data = [_ingest_result(t) for t in SMOKE_UNIVERSE]

        with patch.object(engine.ingestor, "ingest_universe", new=AsyncMock(return_value=ingest_data)):
            mocks = _make_agent_mocks("SMOKE-001")
            # Pre-set run_record so mocks can reference a stable run_id
            self._patch_agents(engine, mocks)
            result = await engine.run_full_pipeline(SMOKE_UNIVERSE)

        assert isinstance(result, dict)
        assert "status" in result or "run_id" in result

    @pytest.mark.asyncio
    async def test_stage_outputs_populated(self, smoke_settings, smoke_config):
        """All 15 stage outputs should be saved after a complete run."""
        engine = self._build_engine(smoke_settings, smoke_config)
        ingest_data = [_ingest_result(t) for t in SMOKE_UNIVERSE]

        with patch.object(engine.ingestor, "ingest_universe", new=AsyncMock(return_value=ingest_data)):
            mocks = _make_agent_mocks("SMOKE-002")
            self._patch_agents(engine, mocks)
            await engine.run_full_pipeline(SMOKE_UNIVERSE)

        # All 15 stages (0-14) should have output saved
        for stage_num in range(15):
            assert stage_num in engine.stage_outputs, f"Stage {stage_num} output missing"

    @pytest.mark.asyncio
    async def test_run_record_created(self, smoke_settings, smoke_config):
        """A run_record should be created and persisted."""
        engine = self._build_engine(smoke_settings, smoke_config)
        ingest_data = [_ingest_result(t) for t in SMOKE_UNIVERSE]

        with patch.object(engine.ingestor, "ingest_universe", new=AsyncMock(return_value=ingest_data)):
            mocks = _make_agent_mocks("SMOKE-003")
            self._patch_agents(engine, mocks)
            await engine.run_full_pipeline(SMOKE_UNIVERSE)

        assert engine.run_record is not None
        assert engine.run_record.run_id.startswith("run_")
        assert len(engine.run_record.universe) == len(SMOKE_UNIVERSE)

    @pytest.mark.asyncio
    async def test_gate_results_populated(self, smoke_settings, smoke_config):
        """Gate results for each stage should be recorded."""
        engine = self._build_engine(smoke_settings, smoke_config)
        ingest_data = [_ingest_result(t) for t in SMOKE_UNIVERSE]

        with patch.object(engine.ingestor, "ingest_universe", new=AsyncMock(return_value=ingest_data)):
            mocks = _make_agent_mocks("SMOKE-004")
            self._patch_agents(engine, mocks)
            await engine.run_full_pipeline(SMOKE_UNIVERSE)

        assert len(engine.gate_results) > 0, "No gate results recorded"
        # Gate 0 should have passed (fake API keys satisfy validate())
        # Gate 2 should have passed (ingest data covers all tickers)
        assert engine.gate_results.get(2) is not None
        assert engine.gate_results[2].passed is True

    @pytest.mark.asyncio
    async def test_ingestion_failure_blocks_pipeline(self, smoke_settings, smoke_config):
        """If ingestion returns no data, gate_2 should fail and pipeline should stop."""
        engine = self._build_engine(smoke_settings, smoke_config)

        with patch.object(
            engine.ingestor, "ingest_universe",
            new=AsyncMock(return_value=[{"ticker": "NVDA", "error": "API unavailable"}]),
        ):
            mocks = _make_agent_mocks("SMOKE-005")
            self._patch_agents(engine, mocks)
            result = await engine.run_full_pipeline(SMOKE_UNIVERSE)

        # Pipeline should have short-circuited — gate_2 fails (AVGO and TSM missing)
        assert result.get("blocked_at") == 2 or result.get("status") == "failed"

    @pytest.mark.asyncio
    async def test_evidence_agent_failure_blocks_stage5(self, smoke_settings, smoke_config):
        """If evidence agent returns no claims, gate_5 should fail."""
        engine = self._build_engine(smoke_settings, smoke_config)
        ingest_data = [_ingest_result(t) for t in SMOKE_UNIVERSE]

        with patch.object(engine.ingestor, "ingest_universe", new=AsyncMock(return_value=ingest_data)):
            mocks = _make_agent_mocks("SMOKE-006")
            # Evidence agent returns empty claims — gate_5 should block
            mocks["evidence"] = AsyncMock(return_value=AgentResult(
                agent_name="evidence_librarian",
                run_id="SMOKE-006",
                success=False,
                error="LLM unavailable",
            ))
            self._patch_agents(engine, mocks)
            result = await engine.run_full_pipeline(SMOKE_UNIVERSE)

        assert result.get("blocked_at") == 5 or result.get("status") == "failed"

    @pytest.mark.asyncio
    async def test_reviewer_fail_blocks_stage11(self, smoke_settings, smoke_config):
        """If associate reviewer returns FAIL, gate_11 should fail and pipeline stops."""
        engine = self._build_engine(smoke_settings, smoke_config)
        ingest_data = [_ingest_result(t) for t in SMOKE_UNIVERSE]

        with patch.object(engine.ingestor, "ingest_universe", new=AsyncMock(return_value=ingest_data)):
            mocks = _make_agent_mocks("SMOKE-007")
            mocks["reviewer"] = AsyncMock(return_value=_agent_result(
                "associate_reviewer", "SMOKE-007",
                {"status": "fail", "publication_status": "fail",
                 "issues": [{"severity": "critical", "description": "Insufficient evidence sourcing"}]},
            ))
            self._patch_agents(engine, mocks)
            result = await engine.run_full_pipeline(SMOKE_UNIVERSE)

        assert result.get("blocked_at") == 11 or result.get("status") == "failed"

    @pytest.mark.asyncio
    async def test_all_agents_called_once(self, smoke_settings, smoke_config):
        """Every LLM agent expected in a typical run should be called exactly once."""
        engine = self._build_engine(smoke_settings, smoke_config)
        ingest_data = [_ingest_result(t) for t in SMOKE_UNIVERSE]

        with patch.object(engine.ingestor, "ingest_universe", new=AsyncMock(return_value=ingest_data)):
            mocks = _make_agent_mocks("SMOKE-008")
            self._patch_agents(engine, mocks)
            await engine.run_full_pipeline(SMOKE_UNIVERSE)

        # Core agents must each be called once
        for agent_key in ("evidence", "valuation", "macro", "political",
                          "red_team", "reviewer", "portfolio"):
            assert mocks[agent_key].call_count == 1, (
                f"Agent '{agent_key}' was called {mocks[agent_key].call_count} times (expected 1)"
            )
        # Compute analyst called once (all 3 tickers are compute sector)
        assert mocks["compute"].call_count == 1
        # Power and infra have no matching tickers in SMOKE_UNIVERSE → skipped
        # The engine logs "Skipping <agent> — no tickers in universe" for these
        assert mocks["power"].call_count == 0, "Power analyst should not run when no power tickers present"
        assert mocks["infra"].call_count == 0, "Infra analyst should not run when no infra tickers present"


class TestPipelineEngineInstantiation:
    """Test that PipelineEngine can be constructed cleanly with various config shapes."""

    def test_instantiation_with_defaults(self, smoke_settings, smoke_config):
        engine = PipelineEngine(settings=smoke_settings, config=smoke_config)
        assert engine is not None
        assert engine.gates is not None

    def test_all_agents_present(self, smoke_settings, smoke_config):
        engine = PipelineEngine(settings=smoke_settings, config=smoke_config)
        expected_agents = [
            "orchestrator_agent", "evidence_agent", "compute_analyst",
            "power_analyst", "infra_analyst", "valuation_agent", "macro_agent",
            "political_agent", "red_team_agent", "reviewer_agent", "pm_agent",
            "quant_analyst_agent",
        ]
        for attr in expected_agents:
            assert hasattr(engine, attr), f"Missing agent: {attr}"

    def test_all_services_present(self, smoke_settings, smoke_config):
        engine = PipelineEngine(settings=smoke_settings, config=smoke_config)
        expected_services = [
            "ingestor", "reconciliation", "data_qa", "dcf_engine",
            "risk_engine", "scenario_engine", "factor_engine", "var_engine",
            "mandate_engine", "investment_committee", "etf_overlap_engine",
            "observability", "report_format_service", "quant_analyst_agent",
        ]
        for attr in expected_services:
            assert hasattr(engine, attr), f"Missing service: {attr}"

    def test_stage_outputs_empty_on_init(self, smoke_settings, smoke_config):
        engine = PipelineEngine(settings=smoke_settings, config=smoke_config)
        assert engine.stage_outputs == {}
        assert engine.gate_results == {}
        assert engine.run_record is None


# ── Adapter tests ─────────────────────────────────────────────────────────

class TestPipelineAdapter:
    """Verify the thin pipeline_adapter shim has the expected interface."""

    def test_stages_constant(self):
        from frontend.pipeline_adapter import STAGES
        assert len(STAGES) == 15
        assert STAGES[0] == (0, "Bootstrap & Configuration")
        assert STAGES[14] == (14, "Monitoring & Run Registry")

    def test_stage_result_dataclass(self):
        from frontend.pipeline_adapter import StageResult
        sr = StageResult(stage_num=3, stage_name="Reconciliation")
        assert sr.status == "pending"
        assert sr.output == {}
        assert sr.elapsed_secs == 0.0

    def test_run_result_dataclass(self):
        from frontend.pipeline_adapter import RunResult
        rr = RunResult(run_id="x", tickers=["NVDA"], model="claude", started_at="2026-01-01")
        assert rr.success is False
        assert rr.publication_status == "PASS"
        assert rr.stages == []

    def test_pipeline_runner_alias(self):
        from frontend.pipeline_adapter import PipelineRunner, PipelineEngineAdapter
        assert PipelineRunner is PipelineEngineAdapter

    def test_adapter_instantiation(self, tmp_path):
        from frontend.pipeline_adapter import PipelineEngineAdapter
        adapter = PipelineEngineAdapter(
            provider_keys={
                "fmp": "test-fmp",
                "finnhub": "test-finnhub",
                "anthropic": "test-anthropic",
            },
            tickers=["NVDA", "AVGO", "TSM"],
        )
        assert adapter.tickers == ["NVDA", "AVGO", "TSM"]
        assert adapter.model == "claude-opus-4-6"
        assert adapter._settings is not None
        assert adapter._config is not None

    def test_adapter_default_tickers(self):
        from frontend.pipeline_adapter import PipelineEngineAdapter
        adapter = PipelineEngineAdapter(provider_keys={})
        assert adapter.tickers == ["NVDA", "CEG", "PWR"]

    @pytest.mark.asyncio
    async def test_adapter_run_returns_run_result(self, tmp_path):
        """Adapter.run() should return a RunResult with the expected shape."""
        import os
        from frontend.pipeline_adapter import PipelineEngineAdapter, RunResult

        os.environ["PIPELINE_STORAGE_DIR"] = str(tmp_path)
        adapter = PipelineEngineAdapter(
            provider_keys={
                "fmp": "test-fmp",
                "finnhub": "test-finnhub",
                "anthropic": "test-anthropic",
            },
            tickers=SMOKE_UNIVERSE,
        )

        # Re-use the same engine-level mocking pattern
        ingest_data = [_ingest_result(t) for t in SMOKE_UNIVERSE]

        with patch.object(adapter._settings.__class__, "__post_init__", lambda self: None):
            pass  # settings already constructed; no re-init needed

        engine_instance = PipelineEngine(settings=adapter._settings, config=adapter._config)
        mocks = _make_agent_mocks("ADAPTER-001")
        engine_instance.ingestor.ingest_universe = AsyncMock(return_value=ingest_data)
        engine_instance.orchestrator_agent.run = mocks["orchestrator"]
        engine_instance.evidence_agent.run = mocks["evidence"]
        engine_instance.compute_analyst.run = mocks["compute"]
        engine_instance.power_analyst.run = mocks["power"]
        engine_instance.infra_analyst.run = mocks["infra"]
        engine_instance.valuation_agent.run = mocks["valuation"]
        engine_instance.macro_agent.run = mocks["macro"]
        engine_instance.political_agent.run = mocks["political"]
        engine_instance.red_team_agent.run = mocks["red_team"]
        engine_instance.reviewer_agent.run = mocks["reviewer"]
        engine_instance.pm_agent.run = mocks["portfolio"]
        engine_instance.quant_analyst_agent.run = mocks["quant"]
        engine_instance.fixed_income_agent.run = mocks["fixed_income"]

        # Same mandate + IC mocking as TestPipelineEngineSmokeTest._patch_agents
        from research_pipeline.schemas.governance import (
            CommitteeRecord, CommitteeVote, MandateCheckResult,
        )
        _mandate_ok = MandateCheckResult(
            run_id="adapter-smoke", mandate_id="smoke-mandate", is_compliant=True,
        )
        engine_instance.mandate_engine.check_compliance = MagicMock(return_value=_mandate_ok)
        _ic_approved = CommitteeRecord(
            record_id="IC-adapter-smoke", run_id="adapter-smoke",
            outcome=CommitteeVote.APPROVE, quorum_met=True,
            minutes="Approved — adapter smoke test mock",
        )
        engine_instance.investment_committee.evaluate_and_vote = MagicMock(return_value=_ic_approved)

        # Patch PipelineEngine.__init__ to return our pre-built instance
        with patch("frontend.pipeline_adapter.PipelineEngine", return_value=engine_instance):
            result = await adapter.run()

        assert isinstance(result, RunResult)
        assert result.run_id.startswith("run_")
        assert result.tickers == SMOKE_UNIVERSE
        assert result.started_at != ""
        assert result.completed_at != ""
        assert len(result.stages) == 15
        assert result.success is True

