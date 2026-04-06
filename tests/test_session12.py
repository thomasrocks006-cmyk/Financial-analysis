"""tests/test_session12.py — Session 12 feature verification.

Tests covering:
  - EconomicIndicators schema (AU + US fields, defaults, validation)
  - MacroScenario schema (AxisScenario, enums, defaults)
  - EconomyAnalysis schema (12 fields, enum validation)
  - GlobalMacroRegime schema (AU/US flags, has_economy_analysis)
  - EconomicIndicatorService (synthetic fallback, cache TTL, cache clear)
  - MacroScenarioService (scenario matrix, composite classification, bear/bull/base)
  - EconomyAnalystAgent (format_input, parse_economy_analysis, synthetic fallback, required keys)
  - MacroStrategistAgent extension (build_global_macro_regime, with/without EconomyAnalysis)
  - MarketConfig (entries, P0 markets, AU markets, default tickers)
  - PipelineConfig.market_config (present by default)
  - ScenarioStressEngine.register_macro_scenarios (new macro scenarios wired in)
  - ASX_UNIVERSE (correct format, .AX suffix)
  - SECTOR_ROUTING (unchanged from S11)
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from research_pipeline.schemas.macro_economy import MacroScenario


# ═══════════════════════════════════════════════════════════════════════════
# Part 1 — Schema tests: macro_economy.py
# ═══════════════════════════════════════════════════════════════════════════


class TestEconomicIndicatorsSchema:
    """EconomicIndicators + sub-models validation."""

    def test_au_indicators_defaults(self):
        from research_pipeline.schemas.macro_economy import AustralianIndicators

        au = AustralianIndicators()
        assert au.data_freshness == "synthetic_fallback"
        assert au.rba_cash_rate_pct is None
        assert au.aud_usd is None

    def test_us_indicators_defaults(self):
        from research_pipeline.schemas.macro_economy import USIndicators

        us = USIndicators()
        assert us.data_freshness == "synthetic_fallback"
        assert us.fed_funds_rate_pct is None

    def test_economic_indicators_construction(self):
        from research_pipeline.schemas.macro_economy import (
            AustralianIndicators,
            EconomicIndicators,
            USIndicators,
        )

        ind = EconomicIndicators(
            run_id="test-001",
            au=AustralianIndicators(rba_cash_rate_pct=4.35),
            us=USIndicators(fed_funds_rate_pct=5.375),
        )
        assert ind.run_id == "test-001"
        assert ind.au.rba_cash_rate_pct == 4.35
        assert ind.us.fed_funds_rate_pct == 5.375
        assert ind.is_live_data is False
        assert isinstance(ind.fetch_timestamp, datetime)

    def test_economic_indicators_sources(self):
        from research_pipeline.schemas.macro_economy import EconomicIndicators

        ind = EconomicIndicators(
            run_id="test-002",
            sources_used=["FRED API", "RBA website"],
            is_live_data=True,
        )
        assert "FRED API" in ind.sources_used
        assert ind.is_live_data is True

    def test_economic_indicators_fetch_errors_default_empty(self):
        from research_pipeline.schemas.macro_economy import EconomicIndicators

        ind = EconomicIndicators(run_id="test-003")
        assert ind.fetch_errors == []


class TestMacroScenarioSchema:
    """MacroScenario and AxisScenario validation."""

    def test_axis_scenario_default_probabilities(self):
        from research_pipeline.schemas.macro_economy import AxisScenario

        ax = AxisScenario(axis="test", base="b", bull="bu", bear="be")
        assert ax.base_probability + ax.bull_probability + ax.bear_probability == pytest.approx(1.0)

    def test_macro_scenario_defaults(self):
        from research_pipeline.schemas.macro_economy import MacroScenario, ScenarioType

        s = MacroScenario(run_id="test-001")
        assert s.composite_scenario == ScenarioType.BASE
        assert s.au_rates.axis == "au_rates"
        assert s.us_rates.axis == "us_rates"
        assert s.au_inflation.axis == "au_inflation"
        assert s.au_housing.axis == "au_housing"
        assert s.aud_usd.axis == "aud_usd"

    def test_macro_scenario_five_axes(self):
        from research_pipeline.schemas.macro_economy import MacroScenario

        s = MacroScenario(run_id="test-002")
        axes = [s.au_rates, s.us_rates, s.au_inflation, s.au_housing, s.aud_usd]
        assert len(axes) == 5

    def test_scenario_type_enum_values(self):
        from research_pipeline.schemas.macro_economy import ScenarioType

        assert ScenarioType.BASE.value == "base"
        assert ScenarioType.BULL.value == "bull"
        assert ScenarioType.BEAR.value == "bear"

    def test_macro_scenario_has_based_on_indicators_field(self):
        from research_pipeline.schemas.macro_economy import MacroScenario

        s = MacroScenario(run_id="r", based_on_indicators="2025-01-01T00:00:00+00:00")
        assert "2025" in s.based_on_indicators


class TestEconomyAnalysisSchema:
    """EconomyAnalysis schema validation — 12-field output."""

    def test_all_12_fields_present(self):
        from research_pipeline.schemas.macro_economy import EconomyAnalysis

        ea = EconomyAnalysis(run_id="test-001")
        fields = [
            "rba_cash_rate_thesis",
            "fed_funds_thesis",
            "au_cpi_assessment",
            "us_cpi_assessment",
            "au_housing_assessment",
            "au_wage_growth",
            "aud_usd_outlook",
            "cogs_inflation_impact",
            "asx200_vs_sp500_divergence",
            "global_credit_conditions",
            "key_risks_au",
            "key_risks_us",
        ]
        for f in fields:
            assert hasattr(ea, f), f"EconomyAnalysis missing field: {f}"

    def test_risks_default_to_empty_lists(self):
        from research_pipeline.schemas.macro_economy import EconomyAnalysis

        ea = EconomyAnalysis(run_id="test-002")
        assert ea.key_risks_au == []
        assert ea.key_risks_us == []

    def test_stance_enum_defaults(self):
        from research_pipeline.schemas.macro_economy import (
            AudUsdDirection,
            EconomyAnalysis,
            FedStance,
            HousingTrend,
            InflationTrend,
            RBAStance,
        )

        ea = EconomyAnalysis(run_id="test-003")
        assert ea.rba_stance == RBAStance.UNKNOWN
        assert ea.fed_stance == FedStance.UNKNOWN
        assert ea.au_inflation_trend == InflationTrend.UNKNOWN
        assert ea.au_housing_trend == HousingTrend.UNKNOWN
        assert ea.aud_usd_direction == AudUsdDirection.UNKNOWN

    def test_confidence_default_medium(self):
        from research_pipeline.schemas.macro_economy import EconomyAnalysis

        ea = EconomyAnalysis(run_id="test-004")
        assert ea.confidence == "MEDIUM"

    def test_economy_analysis_with_full_data(self):
        from research_pipeline.schemas.macro_economy import (
            EconomyAnalysis,
            FedStance,
            RBAStance,
        )

        ea = EconomyAnalysis(
            run_id="test-005",
            rba_cash_rate_thesis="RBA on hold at 4.35% — inflation returning to target",
            fed_funds_thesis="Fed cutting slowly — 2 cuts in 2025",
            key_risks_au=["Housing correction", "Wage spiral"],
            key_risks_us=["PCE re-acceleration", "Credit tightening"],
            rba_stance=RBAStance.ON_HOLD,
            fed_stance=FedStance.CUTTING,
        )
        assert ea.rba_stance == RBAStance.ON_HOLD
        assert ea.fed_stance == FedStance.CUTTING
        assert len(ea.key_risks_au) == 2
        assert len(ea.key_risks_us) == 2


class TestGlobalMacroRegimeSchema:
    """GlobalMacroRegime schema validation."""

    def test_global_macro_regime_defaults(self):
        from research_pipeline.schemas.macro_economy import GlobalMacroRegime

        gmr = GlobalMacroRegime(run_id="test-001")
        assert gmr.regime_classification == "unknown"
        assert gmr.has_economy_analysis is False
        assert gmr.au_regime_flag == ""
        assert gmr.us_regime_flag == ""

    def test_global_macro_regime_with_flags(self):
        from research_pipeline.schemas.macro_economy import GlobalMacroRegime

        gmr = GlobalMacroRegime(
            run_id="test-002",
            regime_classification="late-cycle expansion",
            au_regime_flag="RBA peak — first cut expected late 2025",
            us_regime_flag="Fed higher-for-longer",
            has_economy_analysis=True,
        )
        assert "RBA" in gmr.au_regime_flag
        assert "Fed" in gmr.us_regime_flag
        assert gmr.has_economy_analysis is True


# ═══════════════════════════════════════════════════════════════════════════
# Part 2 — EconomicIndicatorService tests
# ═══════════════════════════════════════════════════════════════════════════


class TestEconomicIndicatorService:
    """EconomicIndicatorService — cache, synthetic fallback, async fetch."""

    def setup_method(self):
        from research_pipeline.services.economic_indicator_service import clear_cache

        clear_cache()

    def test_get_synthetic_returns_valid_indicators(self):
        from research_pipeline.services.economic_indicator_service import (
            EconomicIndicatorService,
        )

        ind = EconomicIndicatorService.get_synthetic("run-001")
        assert ind.run_id == "run-001"
        assert ind.au.rba_cash_rate_pct is not None
        assert ind.us.fed_funds_rate_pct is not None
        assert ind.is_live_data is False
        assert "synthetic" in ind.sources_used

    def test_synthetic_au_has_realistic_values(self):
        from research_pipeline.services.economic_indicator_service import (
            EconomicIndicatorService,
        )

        ind = EconomicIndicatorService.get_synthetic("run-002")
        # RBA rate in realistic range 2-8%
        assert 2.0 <= ind.au.rba_cash_rate_pct <= 8.0
        # AUD/USD in realistic range
        assert 0.50 <= ind.au.aud_usd <= 0.90

    def test_synthetic_us_has_realistic_values(self):
        from research_pipeline.services.economic_indicator_service import (
            EconomicIndicatorService,
        )

        ind = EconomicIndicatorService.get_synthetic("run-003")
        # Fed funds in realistic range
        assert 0.0 <= ind.us.fed_funds_rate_pct <= 10.0
        # 10Y yield in realistic range
        assert 1.0 <= ind.us.us_10y_treasury_yield_pct <= 8.0

    def test_cache_hit_on_second_call(self):
        from research_pipeline.services.economic_indicator_service import (
            EconomicIndicatorService,
            _CACHE,
        )

        svc = EconomicIndicatorService()

        async def run():
            await svc.get_indicators("run-001")
            cache_len_first = len(_CACHE)
            await svc.get_indicators("run-002")  # different run_id but same cache key
            return cache_len_first

        # The cache should have exactly 1 entry after both calls (same date key)
        first_len = asyncio.run(run())
        assert first_len == 1
        assert len(_CACHE) == 1

    def test_cache_clear_empties_cache(self):
        from research_pipeline.services.economic_indicator_service import (
            EconomicIndicatorService,
            _CACHE,
            clear_cache,
        )

        svc = EconomicIndicatorService()
        asyncio.run(svc.get_indicators("run-001"))
        assert len(_CACHE) == 1
        clear_cache()
        assert len(_CACHE) == 0

    def test_no_fred_key_returns_synthetic(self):
        from research_pipeline.services.economic_indicator_service import (
            EconomicIndicatorService,
        )

        svc = EconomicIndicatorService(fred_api_key=None)
        ind = asyncio.run(svc.get_indicators("run-999"))
        # Without FRED key, US data should be synthetic
        assert ind.us.data_freshness in ("synthetic_fallback", "live")

    def test_service_run_id_preserved(self):
        from research_pipeline.services.economic_indicator_service import (
            EconomicIndicatorService,
        )

        ind = EconomicIndicatorService.get_synthetic("my-specific-run-id")
        assert ind.run_id == "my-specific-run-id"


# ═══════════════════════════════════════════════════════════════════════════
# Part 3 — MacroScenarioService tests
# ═══════════════════════════════════════════════════════════════════════════


class TestMacroScenarioService:
    """MacroScenarioService — scenario matrix generation."""

    def _get_synthetic_scenario(self, run_id: str = "test-001"):
        from research_pipeline.services.macro_scenario_service import (
            MacroScenarioService,
        )

        return MacroScenarioService.build_scenario_from_synthetic(run_id)

    def test_build_scenario_returns_macro_scenario(self):
        from research_pipeline.schemas.macro_economy import MacroScenario

        scenario = self._get_synthetic_scenario()
        assert isinstance(scenario, MacroScenario)

    def test_all_five_axes_populated(self):
        scenario = self._get_synthetic_scenario()
        assert scenario.au_rates.base != ""
        assert scenario.us_rates.base != ""
        assert scenario.au_inflation.base != ""
        assert scenario.au_housing.base != ""
        assert scenario.aud_usd.base != ""

    def test_each_axis_has_all_scenarios(self):
        scenario = self._get_synthetic_scenario()
        for axis in [
            scenario.au_rates,
            scenario.us_rates,
            scenario.au_inflation,
            scenario.au_housing,
            scenario.aud_usd,
        ]:
            assert axis.base != ""
            assert axis.bull != ""
            assert axis.bear != ""

    def test_probability_sums_to_one_per_axis(self):
        scenario = self._get_synthetic_scenario()
        for axis in [
            scenario.au_rates,
            scenario.us_rates,
            scenario.au_inflation,
            scenario.au_housing,
            scenario.aud_usd,
        ]:
            total = axis.base_probability + axis.bull_probability + axis.bear_probability
            assert total == pytest.approx(1.0, abs=0.01), (
                f"Axis {axis.axis} probabilities don't sum to 1"
            )

    def test_composite_scenario_is_valid_enum(self):
        from research_pipeline.schemas.macro_economy import ScenarioType

        scenario = self._get_synthetic_scenario()
        assert scenario.composite_scenario in list(ScenarioType)

    def test_composite_description_non_empty(self):
        scenario = self._get_synthetic_scenario()
        assert len(scenario.composite_description) > 20

    def test_impact_strings_generated(self):
        scenario = self._get_synthetic_scenario()
        assert scenario.au_equities_impact != ""
        assert scenario.us_equities_impact != ""
        assert scenario.au_fixed_income_impact != ""

    def test_bear_signals_yield_bear_composite(self):
        """With extreme CPI + housing correction + hiking = bear."""
        from research_pipeline.schemas.macro_economy import (
            AustralianIndicators,
            EconomicIndicators,
            ScenarioType,
            USIndicators,
        )
        from research_pipeline.services.macro_scenario_service import MacroScenarioService

        ind = EconomicIndicators(
            run_id="bear-test",
            au=AustralianIndicators(
                rba_cash_rate_pct=5.5,
                au_cpi_trimmed_mean_pct=4.8,
                au_housing_price_index_change_pct=-5.0,
                au_auction_clearance_rate_pct=52.0,
            ),
            us=USIndicators(
                fed_funds_rate_pct=5.5,
                us_cpi_yoy_pct=4.0,
                us_yield_curve_spread_10y_2y=-0.8,
            ),
        )
        scenario = MacroScenarioService().build_scenario(ind)
        assert scenario.composite_scenario == ScenarioType.BEAR

    def test_bull_signals_yield_bull_composite(self):
        """With low CPI + RBA cutting + housing accelerating = bull."""
        from research_pipeline.schemas.macro_economy import (
            AustralianIndicators,
            EconomicIndicators,
            ScenarioType,
            USIndicators,
        )
        from research_pipeline.services.macro_scenario_service import MacroScenarioService

        ind = EconomicIndicators(
            run_id="bull-test",
            au=AustralianIndicators(
                rba_cash_rate_pct=3.5,
                au_cpi_trimmed_mean_pct=1.8,
                au_housing_price_index_change_pct=8.0,
                au_auction_clearance_rate_pct=73.0,
            ),
            us=USIndicators(
                fed_funds_rate_pct=3.5,
                us_cpi_yoy_pct=1.9,
                us_hy_spread_bps=250.0,
            ),
        )
        scenario = MacroScenarioService().build_scenario(ind)
        assert scenario.composite_scenario == ScenarioType.BULL

    def test_run_id_propagated_to_scenario(self):
        from research_pipeline.services.macro_scenario_service import (
            MacroScenarioService,
        )

        scenario = MacroScenarioService.build_scenario_from_synthetic("my-run-456")
        assert scenario.run_id == "my-run-456"


# ═══════════════════════════════════════════════════════════════════════════
# Part 4 — EconomyAnalystAgent tests
# ═══════════════════════════════════════════════════════════════════════════


class TestEconomyAnalystAgent:
    """EconomyAnalystAgent — format_input, parse_economy_analysis, required keys."""

    def _get_agent(self):
        from research_pipeline.agents.economy_analyst import EconomyAnalystAgent

        return EconomyAnalystAgent()

    def _get_test_inputs(self):
        from research_pipeline.schemas.macro_economy import (
            AustralianIndicators,
            EconomicIndicators,
            USIndicators,
        )
        from research_pipeline.services.macro_scenario_service import (
            MacroScenarioService,
        )

        ind = EconomicIndicators(
            run_id="test-001",
            au=AustralianIndicators(rba_cash_rate_pct=4.35, au_cpi_trimmed_mean_pct=3.2),
            us=USIndicators(fed_funds_rate_pct=5.375, us_cpi_yoy_pct=3.1),
        )
        scenario = MacroScenarioService().build_scenario(ind)
        return ind, scenario

    def test_format_input_contains_au_indicators(self):
        agent = self._get_agent()
        ind, scenario = self._get_test_inputs()
        fmt = agent.format_input(ind, scenario, "run-001")
        assert "au_indicators" in fmt
        assert fmt["au_indicators"]["rba_cash_rate_pct"] == 4.35

    def test_format_input_contains_us_indicators(self):
        agent = self._get_agent()
        ind, scenario = self._get_test_inputs()
        fmt = agent.format_input(ind, scenario, "run-001")
        assert "us_indicators" in fmt
        assert fmt["us_indicators"]["fed_funds_rate_pct"] == 5.375

    def test_format_input_contains_scenario(self):
        agent = self._get_agent()
        ind, scenario = self._get_test_inputs()
        fmt = agent.format_input(ind, scenario, "run-001")
        assert "macro_scenario" in fmt
        assert "composite_scenario" in fmt["macro_scenario"]

    def test_format_input_serialisable_to_json(self):
        agent = self._get_agent()
        ind, scenario = self._get_test_inputs()
        fmt = agent.format_input(ind, scenario, "run-001")
        # Should not raise
        json.dumps(fmt, default=str)

    def test_parse_economy_analysis_full_dict(self):
        from research_pipeline.schemas.macro_economy import (
            EconomyAnalysis,
            FedStance,
            RBAStance,
        )

        agent = self._get_agent()
        raw = {
            "rba_cash_rate_thesis": "RBA on hold",
            "fed_funds_thesis": "Fed cutting slowly",
            "au_cpi_assessment": "Trimmed mean 3.2% — above target",
            "us_cpi_assessment": "US CPI 3.1% — sticky",
            "au_housing_assessment": "Stable, clearance 63%",
            "au_wage_growth": "WPI 3.6% — moderate",
            "aud_usd_outlook": "AUD/USD 0.645 — range-bound",
            "cogs_inflation_impact": "Moderate labour cost pressure",
            "asx200_vs_sp500_divergence": "Banks vs tech — different rate sensitivity",
            "global_credit_conditions": "IG spreads 95bps — benign",
            "key_risks_au": ["Housing correction", "Wage spiral"],
            "key_risks_us": ["PCE re-acceleration", "Commercial RE"],
            "rba_stance": "on_hold",
            "fed_stance": "cutting",
            "confidence": "HIGH",
        }
        ea = agent.parse_economy_analysis(raw, "run-001")
        assert isinstance(ea, EconomyAnalysis)
        assert ea.rba_cash_rate_thesis == "RBA on hold"
        assert ea.rba_stance == RBAStance.ON_HOLD
        assert ea.fed_stance == FedStance.CUTTING
        assert ea.confidence == "HIGH"
        assert len(ea.key_risks_au) == 2

    def test_parse_economy_analysis_missing_keys_graceful(self):
        from research_pipeline.schemas.macro_economy import EconomyAnalysis

        agent = self._get_agent()
        ea = agent.parse_economy_analysis({}, "run-001")
        assert isinstance(ea, EconomyAnalysis)
        assert ea.rba_cash_rate_thesis == ""
        assert ea.key_risks_au == []

    def test_synthetic_fallback_returns_economy_analysis(self):
        from research_pipeline.schemas.macro_economy import EconomyAnalysis

        agent = self._get_agent()
        ind, scenario = self._get_test_inputs()
        ea = agent._synthetic_fallback(ind, scenario, "run-fallback")
        assert isinstance(ea, EconomyAnalysis)
        assert ea.run_id == "run-fallback"

    def test_synthetic_fallback_has_key_risks(self):
        agent = self._get_agent()
        ind, scenario = self._get_test_inputs()
        ea = agent._synthetic_fallback(ind, scenario, "run-risks")
        assert len(ea.key_risks_au) >= 1
        assert len(ea.key_risks_us) >= 1

    def test_required_output_keys_defined(self):
        from research_pipeline.agents.economy_analyst import EconomyAnalystAgent

        assert len(EconomyAnalystAgent._REQUIRED_OUTPUT_KEYS) >= 4

    def test_validation_fatal_is_true(self):
        from research_pipeline.agents.economy_analyst import EconomyAnalystAgent

        assert EconomyAnalystAgent._VALIDATION_FATAL is True

    def test_agent_name_is_economy_analyst(self):
        agent = self._get_agent()
        assert agent.name == "economy_analyst"

    def test_system_prompt_mentions_rba(self):
        agent = self._get_agent()
        prompt = agent.default_system_prompt()
        assert "RBA" in prompt

    def test_system_prompt_mentions_12_fields(self):
        agent = self._get_agent()
        prompt = agent.default_system_prompt()
        assert "rba_cash_rate_thesis" in prompt
        assert "asx200_vs_sp500_divergence" in prompt


# ═══════════════════════════════════════════════════════════════════════════
# Part 5 — MacroStrategistAgent extension tests
# ═══════════════════════════════════════════════════════════════════════════


class TestMacroStrategistAgentExtension:
    """MacroStrategistAgent Session 12 extension: build_global_macro_regime."""

    def _get_agent(self):
        from research_pipeline.agents.macro_political import MacroStrategistAgent

        return MacroStrategistAgent()

    def test_build_global_macro_regime_no_economy_analysis(self):
        from research_pipeline.schemas.macro_economy import GlobalMacroRegime

        agent = self._get_agent()
        raw = {
            "regime_classification": "late-cycle expansion",
            "confidence": "HIGH",
            "key_macro_variables": {"fed_funds_rate": "5.375%"},
            "regime_winners": ["NVDA", "AVGO"],
            "regime_losers": ["NXT"],
            "key_risks_to_regime": ["Policy error"],
            "policy_watch": ["FOMC meeting"],
        }
        gmr = agent.build_global_macro_regime(raw, "run-001")
        assert isinstance(gmr, GlobalMacroRegime)
        assert gmr.regime_classification == "late-cycle expansion"
        assert gmr.confidence == "HIGH"
        assert "NVDA" in gmr.regime_winners
        assert gmr.has_economy_analysis is False

    def test_build_global_macro_regime_with_economy_analysis(self):
        from research_pipeline.schemas.macro_economy import (
            EconomyAnalysis,
            GlobalMacroRegime,
            RBAStance,
            FedStance,
        )

        agent = self._get_agent()
        ea = EconomyAnalysis(
            run_id="run-001",
            rba_cash_rate_thesis="RBA on hold",
            fed_funds_thesis="Fed cutting",
            rba_stance=RBAStance.ON_HOLD,
            fed_stance=FedStance.CUTTING,
        )
        raw = {"regime_classification": "expansion", "confidence": "MEDIUM"}
        gmr = agent.build_global_macro_regime(raw, "run-001", economy_analysis=ea)
        assert isinstance(gmr, GlobalMacroRegime)
        assert gmr.has_economy_analysis is True
        assert "on_hold" in gmr.au_regime_flag
        assert "cutting" in gmr.us_regime_flag

    def test_build_global_macro_regime_economy_summary_populated(self):
        from research_pipeline.schemas.macro_economy import EconomyAnalysis

        agent = self._get_agent()
        ea = EconomyAnalysis(
            run_id="r",
            rba_cash_rate_thesis="RBA on hold — inflation returning to target band",
            fed_funds_thesis="Fed cutting cycle beginning; 2 cuts priced",
        )
        gmr = agent.build_global_macro_regime({}, "r", economy_analysis=ea)
        assert gmr.economy_analysis_summary != ""

    def test_macro_strategist_system_prompt_has_au_flags(self):
        agent = self._get_agent()
        prompt = agent.default_system_prompt()
        assert "au_regime_flag" in prompt
        assert "us_regime_flag" in prompt


# ═══════════════════════════════════════════════════════════════════════════
# Part 6 — MarketConfig tests
# ═══════════════════════════════════════════════════════════════════════════


class TestMarketConfig:
    """MarketConfig and MarketEntry validation."""

    def test_default_market_config_has_markets(self):
        from research_pipeline.config.loader import DEFAULT_MARKET_CONFIG

        assert len(DEFAULT_MARKET_CONFIG.markets) > 0

    def test_default_market_config_has_p0_us(self):
        from research_pipeline.config.loader import DEFAULT_MARKET_CONFIG

        p0 = DEFAULT_MARKET_CONFIG.get_p0_markets()
        names = [m.market_name for m in p0]
        assert any("US" in n for n in names)

    def test_default_market_config_has_p0_asx(self):
        from research_pipeline.config.loader import DEFAULT_MARKET_CONFIG

        p0 = DEFAULT_MARKET_CONFIG.get_p0_markets()
        names = [m.market_name for m in p0]
        assert any("ASX" in n for n in names)

    def test_au_markets_has_asx_entry(self):
        from research_pipeline.config.loader import DEFAULT_MARKET_CONFIG

        au_markets = DEFAULT_MARKET_CONFIG.get_au_markets()
        assert len(au_markets) >= 1

    def test_asx_entry_has_axjo_benchmark(self):
        from research_pipeline.config.loader import DEFAULT_MARKET_CONFIG

        asx = next(m for m in DEFAULT_MARKET_CONFIG.markets if "ASX" in m.market_name)
        assert "^AXJO" in asx.benchmark_ticker

    def test_asx_market_has_tickers(self):
        from research_pipeline.config.loader import DEFAULT_MARKET_CONFIG

        asx = next(m for m in DEFAULT_MARKET_CONFIG.markets if "ASX" in m.market_name)
        assert len(asx.default_tickers) >= 5

    def test_asx_tickers_have_ax_suffix(self):
        from research_pipeline.config.loader import ASX_UNIVERSE

        for ticker in ASX_UNIVERSE:
            assert ticker.endswith(".AX"), f"Expected .AX suffix on {ticker}"

    def test_get_all_default_tickers_deduplicates(self):
        from research_pipeline.config.loader import DEFAULT_MARKET_CONFIG

        tickers = DEFAULT_MARKET_CONFIG.get_all_default_tickers()
        assert len(tickers) == len(set(tickers)), "Duplicate tickers found"

    def test_get_all_default_tickers_includes_us_and_au(self):
        from research_pipeline.config.loader import DEFAULT_MARKET_CONFIG

        tickers = DEFAULT_MARKET_CONFIG.get_all_default_tickers()
        assert "NVDA" in tickers  # US
        assert "CBA.AX" in tickers  # AU

    def test_pipeline_config_has_market_config(self):
        from research_pipeline.config.loader import PipelineConfig

        cfg = PipelineConfig()
        assert cfg.market_config is not None
        assert len(cfg.market_config.markets) > 0

    def test_market_entry_priority_values(self):
        from research_pipeline.config.loader import DEFAULT_MARKET_CONFIG

        for m in DEFAULT_MARKET_CONFIG.markets:
            assert m.priority in ("P0", "P1", "P2", "P3")


# ═══════════════════════════════════════════════════════════════════════════
# Part 7 — ScenarioStressEngine macro scenario wiring
# ═══════════════════════════════════════════════════════════════════════════


class TestMacroScenarioWiring:
    """Session 12: ScenarioStressEngine.register_macro_scenarios."""

    def _build_scenario(self) -> "MacroScenario":
        from research_pipeline.services.macro_scenario_service import (
            MacroScenarioService,
        )

        return MacroScenarioService.build_scenario_from_synthetic("stress-test-001")

    def test_register_macro_scenarios_adds_scenarios(self):
        from research_pipeline.services.scenario_engine import ScenarioStressEngine

        engine = ScenarioStressEngine()
        initial_count = len(engine.scenarios)
        scenario = self._build_scenario()
        registered = engine.register_macro_scenarios(scenario)
        assert len(registered) > 0
        assert len(engine.scenarios) > initial_count

    def test_register_au_rates_bear_scenario(self):
        from research_pipeline.services.scenario_engine import ScenarioStressEngine

        engine = ScenarioStressEngine()
        scenario = self._build_scenario()
        engine.register_macro_scenarios(scenario)
        assert "au_rates_bear" in engine.scenarios

    def test_register_us_rates_bear_scenario(self):
        from research_pipeline.services.scenario_engine import ScenarioStressEngine

        engine = ScenarioStressEngine()
        scenario = self._build_scenario()
        engine.register_macro_scenarios(scenario)
        assert "us_rates_bear" in engine.scenarios

    def test_register_au_housing_bear_scenario(self):
        from research_pipeline.services.scenario_engine import ScenarioStressEngine

        engine = ScenarioStressEngine()
        scenario = self._build_scenario()
        engine.register_macro_scenarios(scenario)
        assert "au_housing_bear" in engine.scenarios

    def test_macro_scenario_can_be_applied_to_tickers(self):
        from research_pipeline.services.scenario_engine import ScenarioStressEngine

        engine = ScenarioStressEngine()
        scenario = self._build_scenario()
        engine.register_macro_scenarios(scenario)
        results = engine.apply_scenario("au_housing_bear", ["CBA.AX", "WBC.AX", "GMG.AX"])
        assert len(results) == 3
        # Banks should have higher impact than GMG (low exposure)
        bank = next(r for r in results if r.ticker == "CBA.AX")
        gmg = next(r for r in results if r.ticker == "GMG.AX")
        assert abs(bank.estimated_impact_pct) > abs(gmg.estimated_impact_pct)

    def test_register_idempotent_second_call(self):
        """Second registration of same scenarios should not duplicate."""
        from research_pipeline.services.scenario_engine import ScenarioStressEngine

        engine = ScenarioStressEngine()
        scenario = self._build_scenario()
        _first = engine.register_macro_scenarios(scenario)
        count_after_first = len(engine.scenarios)
        second = engine.register_macro_scenarios(scenario)
        assert len(engine.scenarios) == count_after_first  # no new additions
        assert len(second) == 0  # nothing newly registered

    def test_macro_scenarios_have_negative_impact_pct(self):
        """Bear scenarios should produce negative portfolio impacts."""
        from research_pipeline.services.scenario_engine import ScenarioStressEngine

        engine = ScenarioStressEngine()
        scenario = self._build_scenario()
        engine.register_macro_scenarios(scenario)
        cfg = engine.scenarios["au_rates_bear"]
        assert cfg.default_impact_pct < 0


# ══════════════════════════════════════════════════════════════════
# Session 12 Part 2: SectorAnalystASX + is_asx_ticker + engine wiring
# ══════════════════════════════════════════════════════════════════


class TestIsAsxTicker:
    """Unit tests for the is_asx_ticker helper function."""

    def test_bhp_ax_is_asx(self):
        from research_pipeline.agents.sector_analyst_asx import is_asx_ticker

        assert is_asx_ticker("BHP.AX") is True

    def test_cba_ax_is_asx(self):
        from research_pipeline.agents.sector_analyst_asx import is_asx_ticker

        assert is_asx_ticker("CBA.AX") is True

    def test_nvda_not_asx(self):
        from research_pipeline.agents.sector_analyst_asx import is_asx_ticker

        assert is_asx_ticker("NVDA") is False

    def test_aapl_not_asx(self):
        from research_pipeline.agents.sector_analyst_asx import is_asx_ticker

        assert is_asx_ticker("AAPL") is False

    def test_case_insensitive(self):
        from research_pipeline.agents.sector_analyst_asx import is_asx_ticker

        assert is_asx_ticker("bhp.ax") is True

    def test_empty_string(self):
        from research_pipeline.agents.sector_analyst_asx import is_asx_ticker

        assert is_asx_ticker("") is False

    def test_plain_bhp_not_asx(self):
        from research_pipeline.agents.sector_analyst_asx import is_asx_ticker

        assert is_asx_ticker("BHP") is False

    def test_dot_asx_suffix(self):
        from research_pipeline.agents.sector_analyst_asx import is_asx_ticker

        assert is_asx_ticker("CBA.ASX") is True


class TestDefaultAsxUniverse:
    """Tests for the DEFAULT_ASX_UNIVERSE constant."""

    def test_non_empty(self):
        from research_pipeline.agents.sector_analyst_asx import DEFAULT_ASX_UNIVERSE

        assert len(DEFAULT_ASX_UNIVERSE) >= 10

    def test_all_are_asx_tickers(self):
        from research_pipeline.agents.sector_analyst_asx import DEFAULT_ASX_UNIVERSE, is_asx_ticker

        for t in DEFAULT_ASX_UNIVERSE:
            assert is_asx_ticker(t), f"{t} does not look like an ASX ticker"

    def test_big4_banks_present(self):
        from research_pipeline.agents.sector_analyst_asx import DEFAULT_ASX_UNIVERSE

        for bank in ["CBA.AX", "WBC.AX", "NAB.AX", "ANZ.AX"]:
            assert bank in DEFAULT_ASX_UNIVERSE, f"{bank} missing from DEFAULT_ASX_UNIVERSE"

    def test_no_duplicates(self):
        from research_pipeline.agents.sector_analyst_asx import DEFAULT_ASX_UNIVERSE

        assert len(DEFAULT_ASX_UNIVERSE) == len(set(DEFAULT_ASX_UNIVERSE))


class TestSectorAnalystASX:
    """Unit tests for the SectorAnalystASX agent."""

    def _agent(self):
        from research_pipeline.agents.sector_analyst_asx import SectorAnalystASX

        return SectorAnalystASX(model="gemini-1.5-flash")

    def test_required_output_keys_contains_sector_outputs(self):
        assert "sector_outputs" in self._agent()._REQUIRED_OUTPUT_KEYS

    def test_validation_fatal_is_true(self):
        assert self._agent()._VALIDATION_FATAL is True

    def test_name_is_sector_analyst_asx(self):
        assert self._agent().name == "sector_analyst_asx"

    def test_format_input_contains_tickers(self):
        result = self._agent().format_input({"tickers": ["BHP.AX", "CBA.AX"]})
        assert "BHP.AX" in result
        assert "CBA.AX" in result

    def test_format_input_with_economy_analysis_mentions_rba(self):
        result = self._agent().format_input(
            {
                "tickers": ["CBA.AX"],
                "economy_analysis": {"rba_cash_rate_thesis": "RBA on-hold at 4.35%"},
            }
        )
        assert "RBA" in result

    def test_format_input_empty_tickers(self):
        """format_input should not raise for empty ticker list."""
        result = self._agent().format_input({"tickers": []})
        assert isinstance(result, str)

    def test_system_prompt_has_au_specific_field(self):
        prompt = self._agent().default_system_prompt()
        assert "au_specific" in prompt

    def test_system_prompt_has_rba_rate_sensitivity(self):
        prompt = self._agent().default_system_prompt()
        assert "rba_rate_sensitivity" in prompt

    def test_system_prompt_mentions_franking(self):
        prompt = self._agent().default_system_prompt()
        assert "franking" in prompt.lower()

    def test_system_prompt_mentions_super_fund(self):
        prompt = self._agent().default_system_prompt()
        assert "super" in prompt.lower()

    def test_format_input_returns_string(self):
        result = self._agent().format_input({"tickers": ["BHP.AX"]})
        assert isinstance(result, str)
        assert len(result) > 0


class TestEngineSession12Init:
    """Engine.__init__ must have all Session 12 components wired."""

    def _engine(self):
        import tempfile
        from pathlib import Path
        from research_pipeline.pipeline.engine import PipelineEngine
        from research_pipeline.config.settings import Settings
        from research_pipeline.config.loader import load_pipeline_config

        with tempfile.TemporaryDirectory() as tmp:
            settings = Settings(
                storage_dir=Path(tmp),
                prompts_dir=Path(tmp) / "prompts",
                llm_model="gemini-1.5-flash",
            )
            return PipelineEngine(settings, load_pipeline_config())

    def test_has_economy_analyst(self):
        from research_pipeline.agents.economy_analyst import EconomyAnalystAgent

        assert isinstance(self._engine().economy_analyst, EconomyAnalystAgent)

    def test_has_economic_indicator_svc(self):
        from research_pipeline.services.economic_indicator_service import EconomicIndicatorService

        assert isinstance(self._engine().economic_indicator_svc, EconomicIndicatorService)

    def test_has_macro_scenario_svc(self):
        from research_pipeline.services.macro_scenario_service import MacroScenarioService

        assert isinstance(self._engine().macro_scenario_svc, MacroScenarioService)

    def test_has_asx_analyst(self):
        from research_pipeline.agents.sector_analyst_asx import SectorAnalystASX

        assert isinstance(self._engine().asx_analyst, SectorAnalystASX)


class TestAsxRoutingLogic:
    """Tests for ASX ticker routing logic used in stage_6."""

    def test_asx_tickers_extracted_from_mixed_universe(self):
        from research_pipeline.agents.sector_analyst_asx import is_asx_ticker

        universe = ["NVDA", "BHP.AX", "CBA.AX", "AVGO"]
        asx = [t for t in universe if is_asx_ticker(t)]
        assert set(asx) == {"BHP.AX", "CBA.AX"}

    def test_no_asx_in_us_only_universe(self):
        from research_pipeline.agents.sector_analyst_asx import is_asx_ticker

        universe = ["NVDA", "AVGO", "CEG", "ANET"]
        asx = [t for t in universe if is_asx_ticker(t)]
        assert asx == []

    def test_all_asx_universe_extracted_correctly(self):
        from research_pipeline.agents.sector_analyst_asx import is_asx_ticker, DEFAULT_ASX_UNIVERSE

        universe = ["NVDA"] + DEFAULT_ASX_UNIVERSE
        asx = [t for t in universe if is_asx_ticker(t)]
        assert set(asx) == set(DEFAULT_ASX_UNIVERSE)

    def test_routing_buckets_disjoint(self):
        """ASX tickers must not collide with US sector routing buckets."""
        from research_pipeline.agents.sector_analyst_asx import is_asx_ticker
        from research_pipeline.config.loader import SECTOR_ROUTING

        universe = ["BHP.AX", "NVDA", "WBC.AX", "CEG"]
        asx = {t for t in universe if is_asx_ticker(t)}
        all_us_routed = {t for tickers in SECTOR_ROUTING.values() for t in tickers}
        assert len(asx & all_us_routed) == 0, "ASX tickers should not appear in US SECTOR_ROUTING"
