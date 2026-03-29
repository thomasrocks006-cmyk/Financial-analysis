"""
tests/test_session13.py
-----------------------
Session 13 — Depth & Quality Improvements

Covers:
  1. BaseAgent._build_macro_header()
  2. BaseAgent.format_input() macro injection
  3. DCFEngine.macro_adjusted_wacc()
  4. DCFEngine.build_full_valuation_pack()
  5. FREDFactorFetcher + FactorRefitResult
  6. SectorDataService (synthetic path)
  7. ReportNarrativeAgent
  8. PipelineEngine Session 13 wiring
"""

from __future__ import annotations
import json
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_economy_analysis(**kw):
    defaults = {
        "rba_cash_rate_thesis": "RBA on hold at 4.35%",
        "fed_funds_thesis": "Fed easing gradually",
        "au_cpi_headline": 3.5,
        "us_cpi_headline": 2.8,
        "key_macro_risks": ["Stagflation", "China slowdown"],
    }
    defaults.update(kw)
    return defaults


def _make_macro_scenario(composite_type="base", **kw):
    defaults = {
        "composite_type": composite_type,
        "composite_description": "Balanced environment",
        "probability": 0.55,
    }
    defaults.update(kw)
    return defaults


# ---------------------------------------------------------------------------
# 1. BaseAgent._build_macro_header()
# ---------------------------------------------------------------------------

class TestBuildMacroHeader:
    @pytest.fixture
    def agent(self):
        from research_pipeline.agents.economy_analyst import EconomyAnalystAgent
        return EconomyAnalystAgent(model="gemini-1.5-flash")

    def test_empty_inputs_returns_empty_string(self, agent):
        assert agent._build_macro_header({}) == ""

    def test_economy_analysis_returns_block(self, agent):
        result = agent._build_macro_header({"economy_analysis": _make_economy_analysis()})
        assert "MACRO REGIME CONTEXT" in result
        assert "RBA on hold" in result

    def test_macro_scenario_returns_block(self, agent):
        result = agent._build_macro_header({"macro_scenario": _make_macro_scenario("bear")})
        assert "bear" in result

    def test_both_present_returns_combined(self, agent):
        result = agent._build_macro_header({
            "economy_analysis": _make_economy_analysis(fed_funds_thesis="Fed hiking"),
            "macro_scenario": _make_macro_scenario("bull"),
        })
        assert "Fed hiking" in result
        assert "bull" in result

    def test_fi_suffix_variant(self, agent):
        result = agent._build_macro_header(
            {"economy_analysis_fi": _make_economy_analysis(rba_cash_rate_thesis="RBA hiking 50bp")}
        )
        assert "RBA hiking" in result

    def test_pm_suffix_variant(self, agent):
        result = agent._build_macro_header(
            {"economy_analysis_pm": _make_economy_analysis(fed_funds_thesis="Fed pausing")}
        )
        assert "Fed pausing" in result


# ---------------------------------------------------------------------------
# 2. BaseAgent.format_input() macro injection
# ---------------------------------------------------------------------------

class TestBaseAgentFormatInputMacroInjection:
    """Use ReportNarrativeAgent whose format_input accepts a plain dict."""

    @pytest.fixture
    def agent(self):
        from research_pipeline.agents.report_narrative_agent import ReportNarrativeAgent
        return ReportNarrativeAgent(model="gemini-1.5-flash")

    def test_no_macro_yields_json_body(self, agent):
        # Without economy data, _build_macro_header returns "" and the result
        # should contain no MACRO header marker
        result = agent.format_input({"run_id": "test"})
        assert "MACRO REGIME CONTEXT" not in result

    def test_with_macro_prepends_header(self, agent):
        result = agent.format_input({
            "run_id": "test",
            "economy_analysis": _make_economy_analysis(),
        })
        assert "MACRO REGIME CONTEXT" in result

    def test_json_body_present_after_header(self, agent):
        result = agent.format_input({
            "run_id": "test-001",
            "economy_analysis": _make_economy_analysis(),
        })
        assert "test-001" in result


# ---------------------------------------------------------------------------
# 3. DCFEngine.macro_adjusted_wacc()
# ---------------------------------------------------------------------------

class TestMacroAdjustedWacc:
    @pytest.fixture
    def engine(self):
        from research_pipeline.services.dcf_engine import DCFEngine
        return DCFEngine()

    def test_no_context_unchanged(self, engine):
        assert engine.macro_adjusted_wacc(0.10) == pytest.approx(0.10)

    def test_bear_scenario_increases_wacc(self, engine):
        adj = engine.macro_adjusted_wacc(0.10, macro_scenario=_make_macro_scenario("au_rates_bear"))
        assert adj > 0.10

    def test_bull_scenario_decreases_wacc(self, engine):
        adj = engine.macro_adjusted_wacc(0.10, macro_scenario=_make_macro_scenario("us_rates_bull"))
        assert adj < 0.10

    def test_hawkish_fed_increases_wacc(self, engine):
        adj = engine.macro_adjusted_wacc(
            0.10,
            economy_analysis=_make_economy_analysis(fed_funds_thesis="Fed hiking aggressively")
        )
        assert adj > 0.10

    def test_dovish_rba_decreases_wacc(self, engine):
        adj = engine.macro_adjusted_wacc(
            0.10,
            economy_analysis=_make_economy_analysis(rba_cash_rate_thesis="RBA cutting rates")
        )
        assert adj < 0.10

    def test_floor_at_5pct(self, engine):
        adj = engine.macro_adjusted_wacc(
            0.05,
            macro_scenario=_make_macro_scenario("bull"),
            economy_analysis=_make_economy_analysis(fed_funds_thesis="Fed cutting 200bp")
        )
        assert adj >= 0.05

    def test_none_economy_none_scenario_unchanged(self, engine):
        adj = engine.macro_adjusted_wacc(0.09, economy_analysis=None, macro_scenario=None)
        assert adj == pytest.approx(0.09)


# ---------------------------------------------------------------------------
# 4. DCFEngine.build_full_valuation_pack()
# ---------------------------------------------------------------------------

class TestBuildFullValuationPack:
    @pytest.fixture
    def engine_and_assumptions(self):
        from research_pipeline.services.dcf_engine import DCFEngine, DCFAssumptions
        eng = DCFEngine()
        assum = DCFAssumptions(
            ticker="NVDA",
            revenue_base=79_300,
            revenue_growth_rates=[0.15, 0.15, 0.12, 0.10, 0.08],
            ebitda_margin_path=[0.55, 0.55, 0.54, 0.53, 0.52],
            wacc=0.10,
            terminal_growth=0.03,
            shares_outstanding=24_400,
        )
        return eng, assum

    def test_returns_dcf_key(self, engine_and_assumptions):
        eng, assum = engine_and_assumptions
        result = eng.build_full_valuation_pack(assum, net_debt=-5_000)
        assert "dcf" in result

    def test_returns_sensitivity_key_with_grid(self, engine_and_assumptions):
        eng, assum = engine_and_assumptions
        result = eng.build_full_valuation_pack(assum, net_debt=0)
        assert "sensitivity" in result
        assert "grid" in result["sensitivity"]
        assert len(result["sensitivity"]["grid"]) >= 3

    def test_returns_relative_valuation_key(self, engine_and_assumptions):
        eng, assum = engine_and_assumptions
        result = eng.build_full_valuation_pack(
            assum, net_debt=0, ebitda=43_000, peer_ev_ebitda_multiple=30.0
        )
        assert "relative_valuation" in result
        assert result["relative_valuation"]["ev_ebitda_implied"] is not None

    def test_bear_scenario_increases_macro_adjusted_wacc(self, engine_and_assumptions):
        eng, assum = engine_and_assumptions
        result = eng.build_full_valuation_pack(
            assum, net_debt=0, macro_scenario=_make_macro_scenario("bear")
        )
        assert "macro_adjusted_wacc" in result
        assert result["macro_adjusted_wacc"] >= 0.10

    def test_ticker_in_result(self, engine_and_assumptions):
        eng, assum = engine_and_assumptions
        result = eng.build_full_valuation_pack(assum, net_debt=0)
        assert result["ticker"] == "NVDA"

    def test_bull_scenario_lowers_wacc(self, engine_and_assumptions):
        eng, assum = engine_and_assumptions
        result = eng.build_full_valuation_pack(
            assum, net_debt=0, macro_scenario=_make_macro_scenario("bull")
        )
        assert result["macro_adjusted_wacc"] <= 0.10


# ---------------------------------------------------------------------------
# 5. FREDFactorFetcher + FactorRefitResult
# ---------------------------------------------------------------------------

class TestFREDFactorFetcher:
    @pytest.fixture
    def fetcher(self):
        from research_pipeline.services.factor_engine import FREDFactorFetcher
        return FREDFactorFetcher()  # no API key → synthetic

    def test_synthetic_has_all_factors(self, fetcher):
        result = fetcher.fetch(obs=60)
        for f in ["mkt_rf", "smb", "hml", "rmw", "cma", "rf"]:
            assert f in result.factor_returns, f"Missing factor: {f}"

    def test_synthetic_obs_count(self, fetcher):
        result = fetcher.fetch(obs=60)
        assert result.obs_count == 60

    def test_synthetic_is_live_false(self, fetcher):
        assert fetcher.fetch(obs=60).is_live is False

    def test_synthetic_source_description(self, fetcher):
        result = fetcher.fetch(obs=60)
        assert result.source  # non-empty string

    def test_to_dict_has_expected_keys(self, fetcher):
        d = fetcher.fetch(obs=30).to_dict()
        # to_dict exposes factor_returns_mean, alpha dict, is_live, obs_count
        assert "factor_returns_mean" in d
        assert "is_live" in d
        assert "obs_count" in d

    def test_refit_exposures_sufficient_data(self, fetcher):
        import numpy as np
        rng = np.random.default_rng(42)
        result = fetcher.fetch(obs=252)
        ticker_returns = {"NVDA": rng.normal(0.001, 0.02, 252).tolist()}
        refits = fetcher.refit_exposures(ticker_returns, result)
        assert "NVDA" in refits
        assert "r_squared" in refits["NVDA"]
        # Factor betas are stored as individual keys (mkt_rf, smb, hml, …)
        assert "mkt_rf" in refits["NVDA"]
        assert 0.0 <= refits["NVDA"]["r_squared"] <= 1.0

    def test_refit_exposures_insufficient_data_returns_zero(self, fetcher):
        result = fetcher.fetch(obs=252)
        refits = fetcher.refit_exposures({"AAPL": [0.01, 0.02]}, result)
        assert refits["AAPL"]["r_squared"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 6. SectorDataService (synthetic path)
# ---------------------------------------------------------------------------

class TestSectorDataService:
    @pytest.fixture
    def svc(self):
        from research_pipeline.services.sector_data_service import SectorDataService
        return SectorDataService()  # no FMP key → synthetic

    def test_nvda_gics_sector(self, svc):
        result = svc.get_sector_data_map(["NVDA"])
        assert result["NVDA"].gics_sector == "Information Technology"

    def test_nvda_revenue_ttm(self, svc):
        result = svc.get_sector_data_map(["NVDA"])
        assert result["NVDA"].revenue_ttm == pytest.approx(79_300, rel=0.01)

    def test_cba_ax_financials_sector(self, svc):
        result = svc.get_sector_data_map(["CBA.AX"])
        assert result["CBA.AX"].gics_sector == "Financials"

    def test_csl_ax_health_care_sector(self, svc):
        result = svc.get_sector_data_map(["CSL.AX"])
        assert result["CSL.AX"].gics_sector == "Health Care"

    def test_bhp_ax_materials_sector(self, svc):
        result = svc.get_sector_data_map(["BHP.AX"])
        assert result["BHP.AX"].gics_sector == "Materials"

    def test_all_synthetic_tickers_return_data(self, svc):
        from research_pipeline.services.sector_data_service import _SYNTHETIC_DATA
        results = svc.get_sector_data(list(_SYNTHETIC_DATA.keys()))
        assert len(results) == len(_SYNTHETIC_DATA)

    def test_unconfigured_is_live_false(self, svc):
        results = svc.get_sector_data(["NVDA"])
        assert results[0].is_live is False

    def test_unknown_ticker_returned(self, svc):
        results = svc.get_sector_data(["ZZZZZ"])
        assert len(results) == 1
        assert results[0].ticker == "ZZZZZ"

    def test_get_sector_data_map_keys_match(self, svc):
        tickers = ["NVDA", "BHP.AX"]
        result = svc.get_sector_data_map(tickers)
        assert set(result.keys()) == set(tickers)


# ---------------------------------------------------------------------------
# 7. ReportNarrativeAgent
# ---------------------------------------------------------------------------

class TestReportNarrativeAgent:
    @pytest.fixture
    def agent(self):
        from research_pipeline.agents.report_narrative_agent import ReportNarrativeAgent
        return ReportNarrativeAgent(model="gemini-1.5-flash")

    def test_required_output_keys(self, agent):
        assert "executive_summary" in agent._REQUIRED_OUTPUT_KEYS
        assert "methodology" in agent._REQUIRED_OUTPUT_KEYS

    def test_validation_fatal_is_false(self, agent):
        assert agent._VALIDATION_FATAL is False

    def test_name(self, agent):
        assert agent.name == "report_narrative"

    def test_system_prompt_references_jpam(self, agent):
        prompt = agent.default_system_prompt()
        assert "JP Morgan" in prompt or "JPAM" in prompt or "Goldman" in prompt

    def test_parse_output_fills_all_sections(self, agent):
        from research_pipeline.agents.report_narrative_agent import NARRATIVE_SECTIONS
        raw = json.dumps({
            "executive_summary": "Strong portfolio. All positions on target.",
            "methodology": "15-stage pipeline using LLM agents.",
        })
        result = agent.parse_output(raw)
        for section in NARRATIVE_SECTIONS:
            assert section in result
            assert result[section]  # non-empty

    def test_parse_output_missing_all_sections_still_works(self, agent):
        result = agent.parse_output("{}")
        assert "executive_summary" in result

    def test_format_input_includes_macro_when_present(self, agent):
        inputs = {
            "run_id": "test-001",
            "economy_analysis": _make_economy_analysis(),
        }
        result = agent.format_input(inputs)
        assert "MACRO REGIME CONTEXT" in result


# ---------------------------------------------------------------------------
# 8. PipelineEngine — Session 13 wiring
# ---------------------------------------------------------------------------

class TestEngineSession13Init:
    @pytest.fixture(scope="class")
    def engine(self, tmp_path_factory):
        from pathlib import Path
        from research_pipeline.pipeline.engine import PipelineEngine
        from research_pipeline.config.settings import Settings
        from research_pipeline.config.loader import load_pipeline_config

        tmp = tmp_path_factory.mktemp("engine_s13")
        (tmp / "prompts").mkdir()
        s = Settings(
            storage_dir=tmp,
            prompts_dir=tmp / "prompts",
            llm_model="gemini-1.5-flash",
        )
        return PipelineEngine(s, load_pipeline_config())

    def test_has_sector_data_svc(self, engine):
        from research_pipeline.services.sector_data_service import SectorDataService
        assert isinstance(engine.sector_data_svc, SectorDataService)

    def test_has_fred_factor_fetcher(self, engine):
        from research_pipeline.services.factor_engine import FREDFactorFetcher
        assert isinstance(engine.fred_factor_fetcher, FREDFactorFetcher)

    def test_has_report_narrative_agent(self, engine):
        from research_pipeline.agents.report_narrative_agent import ReportNarrativeAgent
        assert isinstance(engine.report_narrative_agent, ReportNarrativeAgent)
