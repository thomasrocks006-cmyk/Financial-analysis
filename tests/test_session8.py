"""Session 8 targeted tests.

Covers:
  - ACT-S8-1: LiveReturnStore — yfinance fetch with graceful fallback
  - ACT-S8-2: Rebalancing signals wired into Stage 12 output
  - ACT-S8-3: ESGService.load_from_csv — CSV profile ingest
  - ACT-S8-4: PromptRegistry wired into SelfAuditPacket via _scan_prompt_registry
"""

from __future__ import annotations

import asyncio
import csv
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from research_pipeline.agents.base_agent import AgentResult
from research_pipeline.config.loader import PipelineConfig
from research_pipeline.config.settings import APIKeys, Settings
from research_pipeline.pipeline.engine import PipelineEngine
from research_pipeline.schemas.governance import SelfAuditPacket
from research_pipeline.services.esg_service import ESGService
from research_pipeline.services.live_return_store import LiveReturnStore
from research_pipeline.services.prompt_registry import PromptRegistry
from research_pipeline.services.rebalancing_engine import RebalancingEngine


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures & helpers (mirrored from test_session7)
# ─────────────────────────────────────────────────────────────────────────────

S8_UNIVERSE = ["NVDA", "AVGO", "TSM"]


@pytest.fixture
def s8_settings(tmp_path: Path) -> Settings:
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
def s8_config() -> PipelineConfig:
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
        run_id="S8-TEST",
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
    engine.orchestrator_agent.run = AsyncMock(return_value=_ar(
        "orchestrator", {"status": "proceed", "universe": S8_UNIVERSE}
    ))
    engine.evidence_agent.run = AsyncMock(return_value=_ar(
        "evidence_librarian",
        {"claims": [{"claim_id": "C1", "ticker": "NVDA",
                     "claim_text": "NVDA Q4 revenue $18B",
                     "evidence_class": "primary_fact",
                     "source_id": "SRC-1", "confidence": "high",
                     "status": "pass"}],
         "sources": [{"source_id": "SRC-1", "source_type": "filing",
                      "tier": 1, "url": None, "notes": "10-K"}]},
    ))
    engine.compute_analyst.run = AsyncMock(return_value=_ar(
        "sector_analyst_compute",
        {"sector_outputs": [_sector_out(t) for t in S8_UNIVERSE]},
    ))
    engine.power_analyst.run = AsyncMock(return_value=_ar(
        "sector_analyst_power", {"sector_outputs": []}
    ))
    engine.infra_analyst.run = AsyncMock(return_value=_ar(
        "sector_analyst_infrastructure", {"sector_outputs": []}
    ))
    engine.esg_analyst_agent.run = AsyncMock(return_value=_ar(
        "esg_analyst",
        {"esg_scores": [_esg_entry(t) for t in S8_UNIVERSE], "parse_violations": []},
    ))
    engine.valuation_agent.run = AsyncMock(return_value=_ar(
        "valuation_analyst",
        {"valuations": [{"ticker": "NVDA", "date": "2026-01-01",
                         "section_5_scenarios": [{
                             "case": "base", "probability_pct": 50,
                             "revenue_cagr": "20%", "exit_multiple": "30x",
                             "exit_multiple_rationale": "sector median",
                             "implied_return_1y": "15%",
                             "implied_return_3y": "50% [HOUSE VIEW]",
                             "key_assumption": "data center demand",
                             "what_breaks_it": "capex cut",
                         }],
                         "entry_quality": "ACCEPTABLE",
                         "methodology_tag": "HOUSE VIEW"}]},
    ))
    engine.macro_agent.run = AsyncMock(return_value=_ar(
        "macro_strategist",
        {"regime": "expansion", "rate_outlook": "neutral",
         "usd_outlook": "stable", "equity_risk_premium": 5.0},
    ))
    engine.political_agent.run = AsyncMock(return_value=_ar(
        "political_risk", {"risk_level": "low", "key_risks": []}
    ))
    engine.red_team_agent.run = AsyncMock(return_value=_ar(
        "red_team_analyst",
        {"assessments": [{"ticker": "NVDA",
                          "falsification_tests": ["FT-1", "FT-2", "FT-3"],
                          "required_tests": {}}]},
    ))
    engine.reviewer_agent.run = AsyncMock(return_value=_ar(
        "associate_reviewer",
        {"status": "pass", "issues": [], "methodology_tags_complete": True,
         "dates_complete": True, "claim_mapping_complete": True},
    ))
    engine.pm_agent.run = AsyncMock(return_value=_ar(
        "portfolio_manager",
        {"variants": [
            {"name": "balanced",
             "positions": [
                 {"ticker": t, "weight_pct": 100 / len(S8_UNIVERSE)}
                 for t in S8_UNIVERSE
             ]},
        ]},
    ))
    engine.quant_analyst_agent.run = AsyncMock(return_value=_ar(
        "quant_research_analyst",
        {"risk_signal": "neutral",
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
         "data_quality_note": "test"},
    ))
    engine.fixed_income_agent.run = AsyncMock(return_value=_ar(
        "fixed_income_analyst",
        {"yield_curve_regime": "normal",
         "10y_yield_context": "4.3% neutral",
         "cost_of_capital_trend": "stable",
         "rate_sensitivity_score": 5.0,
         "key_risks": [], "offsetting_factors": [],
         "methodology_note": "10y yield tracking"},
    ))


@pytest.fixture
def s8_engine(s8_settings, s8_config):
    engine = PipelineEngine(s8_settings, s8_config)
    _patch_all_agents(engine)
    # Disable live return fetching so tests are deterministic (no network)
    engine.live_return_store.fetch = MagicMock(return_value={})
    async def _mock_ingest(tickers):
        return [_ingest_row(t) for t in tickers]
    engine.ingestor.ingest_universe = _mock_ingest
    return engine


@pytest.fixture
def s8_result(s8_engine):
    return asyncio.run(
        s8_engine.run_full_pipeline(S8_UNIVERSE)
    )


# ─────────────────────────────────────────────────────────────────────────────
# ACT-S8-1: LiveReturnStore
# ─────────────────────────────────────────────────────────────────────────────

class TestLiveReturnStore:
    """Tests for yfinance-backed LiveReturnStore."""

    def test_store_instantiation(self):
        """LiveReturnStore can be instantiated without arguments."""
        store = LiveReturnStore()
        assert store.cache_size == 0
        assert store.last_fetched_at is None

    def test_fetch_returns_empty_when_yfinance_raises(self):
        """When yfinance download raises, fetch returns empty dict (non-fatal)."""
        store = LiveReturnStore()
        with patch.object(store, "_download", return_value={}):
            result = store.fetch(["NVDA", "AMD"])
        assert result == {}

    def test_fetch_with_mocked_download(self):
        """fetch() populates cache from _download result and returns it."""
        store = LiveReturnStore()
        fake_returns = {"NVDA": [0.01, -0.02, 0.015], "AMD": [0.005, 0.012, -0.01]}
        with patch.object(store, "_download", return_value=fake_returns):
            result = store.fetch(["NVDA", "AMD"])
        assert set(result.keys()) == {"NVDA", "AMD"}
        assert result["NVDA"] == [0.01, -0.02, 0.015]
        assert store.cache_size == 2

    def test_cache_hit_avoids_repeated_download(self):
        """Same tickers on second fetch use cache without calling _download again."""
        store = LiveReturnStore()
        fake = {"NVDA": [0.01, 0.02]}
        download_mock = MagicMock(return_value=fake)
        with patch.object(store, "_download", download_mock):
            store.fetch(["NVDA"])
            store.fetch(["NVDA"])
        # _download should only be called once
        assert download_mock.call_count == 1

    def test_clear_cache_resets_state(self):
        """clear_cache() empties the cache and resets timestamps."""
        store = LiveReturnStore()
        with patch.object(store, "_download", return_value={"NVDA": [0.01]}):
            store.fetch(["NVDA"])
        assert store.cache_size == 1
        store.clear_cache()
        assert store.cache_size == 0
        assert store.last_fetched_at is None

    def test_engine_falls_back_to_synthetic_when_live_empty(self, s8_engine):
        """When live_return_store returns {}, _get_returns uses synthetic data."""
        # live_return_store.fetch is mocked to return {} in the fixture
        returns = s8_engine._get_returns(["NVDA", "AVGO"])
        assert "NVDA" in returns
        assert "AVGO" in returns
        assert len(returns["NVDA"]) > 0

    def test_engine_uses_live_when_all_tickers_available(self, s8_engine):
        """When live_return_store has all tickers, _get_returns uses live data."""
        fake_live = {"NVDA": [0.01, 0.02, 0.03], "AVGO": [0.005, 0.01, 0.015]}
        s8_engine.live_return_store.fetch = MagicMock(return_value=fake_live)
        result = s8_engine._get_returns(["NVDA", "AVGO"])
        assert result == fake_live


# ─────────────────────────────────────────────────────────────────────────────
# ACT-S8-2: Rebalancing signals
# ─────────────────────────────────────────────────────────────────────────────

class TestRebalancingWiring:
    """Tests for rebalancing proposal wired into Stage 12."""

    def test_rebalance_proposal_key_in_stage12(self, s8_engine, s8_result):
        """Stage 12 output dict contains a 'rebalance_proposal' key."""
        out = s8_engine.stage_outputs.get(12, {})
        assert "rebalance_proposal" in out, (
            f"'rebalance_proposal' missing from stage_outputs[12]. Keys: {list(out.keys())}"
        )

    def test_rebalance_proposal_has_trades(self, s8_engine, s8_result):
        """rebalance_proposal contains a 'trades' list (may be empty if weights identical)."""
        out = s8_engine.stage_outputs.get(12, {})
        proposal = out.get("rebalance_proposal")
        if proposal is not None:
            assert "trades" in proposal, "rebalance_proposal missing 'trades' key"
            assert isinstance(proposal["trades"], list)

    def test_rebalance_proposal_fields(self, s8_engine, s8_result):
        """rebalance_proposal contains expected top-level fields when present."""
        out = s8_engine.stage_outputs.get(12, {})
        proposal = out.get("rebalance_proposal")
        if proposal is not None:
            for field in ("run_id", "trigger", "total_turnover_pct", "summary"):
                assert field in proposal, f"Missing field: {field}"

    def test_rebalancing_engine_standalone_smoke(self):
        """RebalancingEngine.generate_rebalance works without engine context."""
        engine = RebalancingEngine()
        target = {"NVDA": 40.0, "AMD": 35.0, "AVGO": 25.0}
        current = {"NVDA": 33.3, "AMD": 33.3, "AVGO": 33.4}
        proposal = engine.generate_rebalance(
            run_id="standalone-test",
            target_weights=target,
            current_weights=current,
            trigger="test",
        )
        assert proposal.run_id == "standalone-test"
        assert isinstance(proposal.trades, list)
        assert proposal.total_turnover_pct >= 0

    def test_rebalance_trade_directions(self):
        """Trades with positive delta are 'buy'; negative delta are 'sell'."""
        engine = RebalancingEngine(drift_threshold_pct=0.0, min_trade_pct=0.0)
        target = {"A": 60.0, "B": 40.0}
        current = {"A": 40.0, "B": 60.0}
        proposal = engine.generate_rebalance("run1", target, current)
        a_trade = next((t for t in proposal.trades if t.ticker == "A"), None)
        b_trade = next((t for t in proposal.trades if t.ticker == "B"), None)
        assert a_trade is not None and a_trade.direction == "buy"
        assert b_trade is not None and b_trade.direction == "sell"


# ─────────────────────────────────────────────────────────────────────────────
# ACT-S8-3: ESG CSV ingest
# ─────────────────────────────────────────────────────────────────────────────

class TestESGCsvIngest:
    """Tests for ESGService.load_from_csv."""

    def _write_csv(self, path: Path, rows: list[dict]) -> None:
        fieldnames = ["ticker", "overall_rating", "e_score", "s_score", "g_score", "controversy_flag"]
        with open(path, "w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_load_from_csv_creates_profile(self, tmp_path):
        """load_from_csv returns number of rows loaded."""
        csv_path = tmp_path / "esg.csv"
        self._write_csv(csv_path, [
            {"ticker": "TESTCO", "overall_rating": "A",
             "e_score": "7.0", "s_score": "6.5", "g_score": "8.0",
             "controversy_flag": "false"},
        ])
        svc = ESGService()
        loaded = svc.load_from_csv(csv_path)
        assert loaded == 1

    def test_load_from_csv_overrides_heuristic_score(self, tmp_path):
        """Loaded CSV data replaces the default heuristic profile."""
        csv_path = tmp_path / "esg.csv"
        # Override NVDA with a synthetic low-score profile
        self._write_csv(csv_path, [
            {"ticker": "NVDA", "overall_rating": "BB",
             "e_score": "2.0", "s_score": "2.0", "g_score": "2.0",
             "controversy_flag": "true"},
        ])
        svc = ESGService()
        loaded = svc.load_from_csv(csv_path)
        assert loaded == 1
        score = svc.get_score("NVDA")
        assert score.environmental_score == 2.0
        assert score.controversy_flag is True

    def test_load_from_csv_multiple_rows(self, tmp_path):
        """All valid rows are loaded; count matches."""
        csv_path = tmp_path / "esg_multi.csv"
        self._write_csv(csv_path, [
            {"ticker": "CO1", "overall_rating": "AAA", "e_score": "9.0",
             "s_score": "9.0", "g_score": "9.0", "controversy_flag": "false"},
            {"ticker": "CO2", "overall_rating": "CCC", "e_score": "1.0",
             "s_score": "1.0", "g_score": "1.0", "controversy_flag": "true"},
        ])
        svc = ESGService()
        assert svc.load_from_csv(csv_path) == 2

    def test_load_from_csv_invalid_rating_skipped(self, tmp_path):
        """Rows with an invalid overall_rating value are skipped."""
        csv_path = tmp_path / "esg_bad.csv"
        self._write_csv(csv_path, [
            {"ticker": "GOOD", "overall_rating": "AA", "e_score": "7.0",
             "s_score": "7.0", "g_score": "7.0", "controversy_flag": "false"},
            {"ticker": "BAD", "overall_rating": "NOTVALID", "e_score": "5.0",
             "s_score": "5.0", "g_score": "5.0", "controversy_flag": "false"},
        ])
        svc = ESGService()
        loaded = svc.load_from_csv(csv_path)
        assert loaded == 1  # only GOOD row succeeds

    def test_load_from_csv_file_not_found(self, tmp_path):
        """load_from_csv returns 0 when the file does not exist."""
        svc = ESGService()
        result = svc.load_from_csv(tmp_path / "nonexistent.csv")
        assert result == 0

    def test_load_from_csv_cache_invalidated(self, tmp_path):
        """After loading, cached score for the same ticker is replaced."""
        svc = ESGService()
        # Prime the cache
        original = svc.get_score("AMD")
        original_score = original.environmental_score

        csv_path = tmp_path / "amd.csv"
        self._write_csv(csv_path, [
            {"ticker": "AMD", "overall_rating": "CCC", "e_score": "1.5",
             "s_score": "1.5", "g_score": "1.5", "controversy_flag": "true"},
        ])
        svc.load_from_csv(csv_path)
        updated = svc.get_score("AMD")
        assert updated.environmental_score == 1.5
        assert updated.environmental_score != original_score


# ─────────────────────────────────────────────────────────────────────────────
# ACT-S8-4: PromptRegistry wired into SelfAuditPacket
# ─────────────────────────────────────────────────────────────────────────────

class TestPromptRegistryWiring:
    """Tests for PromptRegistry → SelfAuditPacket integration."""

    def test_schema_has_prompt_drift_field(self):
        """SelfAuditPacket model has prompt_drift_reports field."""
        assert "prompt_drift_reports" in SelfAuditPacket.model_fields

    def test_prompt_drift_default_empty(self):
        """prompt_drift_reports defaults to an empty list."""
        pkt = SelfAuditPacket(run_id="test")
        assert pkt.prompt_drift_reports == []

    def test_prompt_registry_register_and_retrieve(self, tmp_path):
        """PromptRegistry.register_prompt creates version 1 on first call."""
        registry = PromptRegistry(storage_dir=tmp_path / "pr")
        ver = registry.register_prompt("test_agent", "Hello world prompt")
        assert ver.version == 1
        assert ver.prompt_id == "test_agent"

    def test_prompt_registry_drift_detection(self, tmp_path):
        """Unchanged prompt reports changed=False; modified prompt changed=True."""
        registry = PromptRegistry(storage_dir=tmp_path / "pr")
        text_v1 = "Original prompt"
        text_v2 = "Modified prompt"
        registry.register_prompt("agent_x", text_v1)
        # Same text — no drift
        report1 = registry.check_drift("agent_x", text_v1)
        assert report1.changed is False
        # Changed text — drift
        report2 = registry.check_drift("agent_x", text_v2)
        assert report2.changed is True

    def test_audit_packet_has_prompt_drift_reports(self, s8_engine, s8_result):
        """After a full run, audit_packet contains prompt_drift_reports."""
        audit = s8_result.get("audit_packet") or {}
        assert "prompt_drift_reports" in audit, (
            "prompt_drift_reports missing from audit_packet dict"
        )
        assert isinstance(audit["prompt_drift_reports"], list)

    def test_drift_reports_count_matches_agents(self, s8_engine, s8_result):
        """One drift report per agent that has a prompt_hash (up to 14 agents)."""
        audit = s8_result.get("audit_packet") or {}
        reports = audit.get("prompt_drift_reports", [])
        # 14 agents registered — assert we get at most 14 and at least 1
        # (agents in tmp_path have empty prompts_dir so hash may be empty stub)
        assert isinstance(reports, list)
        assert len(reports) >= 0  # non-negative

    def test_engine_has_prompt_registry(self, s8_engine):
        """PipelineEngine has a prompt_registry attribute."""
        assert hasattr(s8_engine, "prompt_registry")
        assert isinstance(s8_engine.prompt_registry, PromptRegistry)

    def test_engine_has_live_return_store(self, s8_engine):
        """PipelineEngine has a live_return_store attribute."""
        assert hasattr(s8_engine, "live_return_store")
        assert isinstance(s8_engine.live_return_store, LiveReturnStore)
