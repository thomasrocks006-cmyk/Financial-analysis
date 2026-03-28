"""Session 12 — Macro Economy & AU/US Markets Tests.

36 tests covering:
- EconomicIndicatorService (FRED + RBA + fallback)
- MacroScenarioService (3-scenario matrix)
- EconomyAnalystAgent (12-field output)
- MarketConfig in PipelineConfig
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from research_pipeline.services.economic_indicator_service import (
    AustralianIndicators,
    EconomicIndicatorService,
    EconomicIndicators,
    USIndicators,
)
from research_pipeline.services.macro_scenario_service import (
    MacroScenario,
    MacroScenarioService,
)
from research_pipeline.config.loader import MarketConfig, PipelineConfig


# ── EconomicIndicators Schema ─────────────────────────────────────────────

class TestEconomicIndicatorSchemas:

    def test_australian_indicators_defaults(self):
        au = AustralianIndicators()
        assert au.rba_cash_rate_pct > 0
        assert au.au_cpi_yoy_pct > 0
        assert au.aud_usd_rate > 0
        assert au.rba_policy_stance in ("hiking", "on-hold", "cutting")

    def test_us_indicators_defaults(self):
        us = USIndicators()
        assert us.fed_funds_rate_pct > 0
        assert us.us_cpi_yoy_pct > 0
        assert us.us_10y_treasury_yield_pct > 0
        assert us.fed_policy_stance in ("hiking", "on-hold", "cutting")

    def test_economic_indicators_composite(self):
        indicators = EconomicIndicators()
        assert isinstance(indicators.au, AustralianIndicators)
        assert isinstance(indicators.us, USIndicators)
        assert indicators.fetched_at is not None

    def test_us_yield_curve_spread_can_be_negative(self):
        us = USIndicators(us_2y_treasury_yield_pct=5.0, us_10y_treasury_yield_pct=4.5, us_yield_curve_spread_bp=-50.0)
        assert us.us_yield_curve_spread_bp == -50.0

    def test_au_housing_data_present(self):
        au = AustralianIndicators()
        assert hasattr(au, "au_housing_price_yoy_pct")
        assert hasattr(au, "au_wpi_yoy_pct")

    def test_au_bond_yields_present(self):
        au = AustralianIndicators()
        assert hasattr(au, "au_10y_bond_yield_pct")
        assert hasattr(au, "au_2y_bond_yield_pct")


# ── EconomicIndicatorService ──────────────────────────────────────────────

class TestEconomicIndicatorService:

    def test_service_creates_without_api_key(self):
        svc = EconomicIndicatorService()
        assert svc is not None

    def test_service_cache_initially_invalid(self):
        svc = EconomicIndicatorService()
        assert not svc._cache_valid()

    async def test_get_indicators_returns_economic_indicators(self):
        svc = EconomicIndicatorService()
        # Should not require API key — uses synthetic fallback
        result = await svc.get_indicators()
        assert isinstance(result, EconomicIndicators)

    async def test_get_indicators_caches_result(self):
        svc = EconomicIndicatorService()
        r1 = await svc.get_indicators()
        r2 = await svc.get_indicators()
        assert r1 is r2  # same object from cache

    def test_invalidate_cache_resets_state(self):
        svc = EconomicIndicatorService()
        svc._cache = MagicMock()
        svc._cache_time = 9999999.0
        svc.invalidate_cache()
        assert svc._cache is None
        assert svc._cache_time == 0.0

    async def test_synthetic_fallback_always_returns_data(self):
        svc = EconomicIndicatorService()
        result = svc._synthetic_fallback()
        assert isinstance(result, EconomicIndicators)
        assert result.au.data_source == "synthetic_fallback"

    async def test_service_with_invalid_fred_key_uses_fallback(self):
        svc = EconomicIndicatorService(fred_api_key="INVALID_KEY_TEST")
        result = await svc.get_indicators()
        # Should succeed via fallback
        assert isinstance(result, EconomicIndicators)


# ── MacroScenarioService ──────────────────────────────────────────────────

class TestMacroScenarioService:

    def _make_indicators(self) -> EconomicIndicators:
        return EconomicIndicators(
            au=AustralianIndicators(
                rba_cash_rate_pct=4.35, au_cpi_yoy_pct=3.4,
                au_trimmed_mean_cpi_pct=3.2, au_housing_price_yoy_pct=5.2,
                aud_usd_rate=0.635, aud_usd_trend="stable",
            ),
            us=USIndicators(
                fed_funds_rate_pct=5.25, us_cpi_yoy_pct=3.1,
                us_10y_treasury_yield_pct=4.45, us_2y_treasury_yield_pct=4.72,
                us_yield_curve_spread_bp=-27.0,
                us_credit_spread_ig_bp=98.0, us_credit_spread_hy_bp=320.0,
            ),
        )

    def test_build_scenarios_returns_macro_scenario(self):
        svc = MacroScenarioService()
        indicators = self._make_indicators()
        result = svc.build_scenarios(indicators)
        assert isinstance(result, MacroScenario)

    def test_scenario_has_six_axes(self):
        svc = MacroScenarioService()
        indicators = self._make_indicators()
        result = svc.build_scenarios(indicators)
        assert result.au_rates is not None
        assert result.us_rates is not None
        assert result.au_inflation is not None
        assert result.au_housing is not None
        assert result.aud_usd is not None
        assert result.global_credit is not None

    def test_each_axis_has_base_bull_bear(self):
        svc = MacroScenarioService()
        indicators = self._make_indicators()
        result = svc.build_scenarios(indicators)
        for axis in [result.au_rates, result.us_rates, result.au_inflation,
                     result.au_housing, result.aud_usd, result.global_credit]:
            assert axis.base is not None
            assert axis.bull is not None
            assert axis.bear is not None

    def test_probabilities_sum_to_one_per_axis(self):
        svc = MacroScenarioService()
        indicators = self._make_indicators()
        result = svc.build_scenarios(indicators)
        for axis in [result.au_rates, result.us_rates]:
            total = axis.base.probability + axis.bull.probability + axis.bear.probability
            assert abs(total - 1.0) < 0.01, f"Probabilities for {axis.axis} sum to {total}"

    def test_composite_regime_is_valid(self):
        svc = MacroScenarioService()
        indicators = self._make_indicators()
        result = svc.build_scenarios(indicators)
        assert result.composite_regime in ("risk-on", "risk-neutral", "risk-off")

    def test_regime_rationale_nonempty(self):
        svc = MacroScenarioService()
        indicators = self._make_indicators()
        result = svc.build_scenarios(indicators)
        assert len(result.regime_rationale) > 10

    def test_au_super_impact_nonempty(self):
        svc = MacroScenarioService()
        indicators = self._make_indicators()
        result = svc.build_scenarios(indicators)
        assert len(result.au_super_impact) > 5

    def test_ai_infra_impacts_nonempty(self):
        svc = MacroScenarioService()
        indicators = self._make_indicators()
        result = svc.build_scenarios(indicators)
        assert result.ai_infra_impact_base
        assert result.ai_infra_impact_bull
        assert result.ai_infra_impact_bear

    def test_stress_return_bear_negative(self):
        svc = MacroScenarioService()
        indicators = self._make_indicators()
        result = svc.build_scenarios(indicators)
        assert result.stress_return_bear_pct < 0

    def test_stress_return_bull_positive(self):
        svc = MacroScenarioService()
        indicators = self._make_indicators()
        result = svc.build_scenarios(indicators)
        assert result.stress_return_bull_pct > 0

    def test_inverted_yield_curve_raises_risk_off_probability(self):
        svc = MacroScenarioService()
        indicators = EconomicIndicators(
            au=AustralianIndicators(rba_cash_rate_pct=5.0, au_cpi_yoy_pct=5.0),
            us=USIndicators(
                fed_funds_rate_pct=6.0, us_cpi_yoy_pct=4.0,
                us_yield_curve_spread_bp=-100.0,
                us_credit_spread_hy_bp=600.0,
            ),
        )
        result = svc.build_scenarios(indicators)
        # Inverted curve + wide HY spreads should push toward risk-off
        assert result.composite_regime in ("risk-neutral", "risk-off")


# ── EconomyAnalystAgent ───────────────────────────────────────────────────

class TestEconomyAnalystAgent:

    def test_agent_instantiates(self):
        from research_pipeline.agents.economy_analyst import EconomyAnalystAgent
        agent = EconomyAnalystAgent(model="gpt-4o")
        assert agent.name == "economy_analyst"

    def test_agent_has_required_output_keys(self):
        from research_pipeline.agents.economy_analyst import EconomyAnalystAgent, _REQUIRED_KEYS
        assert len(_REQUIRED_KEYS) == 12
        assert "rba_cash_rate_thesis" in _REQUIRED_KEYS
        assert "fed_funds_thesis" in _REQUIRED_KEYS
        assert "au_cpi_assessment" in _REQUIRED_KEYS
        assert "aud_usd_outlook" in _REQUIRED_KEYS
        assert "key_risks_au" in _REQUIRED_KEYS
        assert "key_risks_us" in _REQUIRED_KEYS

    def test_agent_default_system_prompt_nonempty(self):
        from research_pipeline.agents.economy_analyst import EconomyAnalystAgent
        agent = EconomyAnalystAgent(model="gpt-4o")
        prompt = agent.default_system_prompt()
        assert len(prompt) > 100
        assert "rba_cash_rate_thesis" in prompt

    def test_agent_format_input_serializes_indicators(self):
        import json
        from research_pipeline.agents.economy_analyst import EconomyAnalystAgent
        agent = EconomyAnalystAgent(model="gpt-4o")
        inputs = {
            "universe": ["NVDA", "AMD"],
            "economic_indicators": {"rba_rate": 4.35},
            "macro_scenario": {"regime": "risk-neutral"},
        }
        output = agent.format_input(inputs)
        parsed = json.loads(output)
        assert parsed["task"] == "macro_analysis"
        assert parsed["universe"] == ["NVDA", "AMD"]


# ── MarketConfig ──────────────────────────────────────────────────────────

class TestMarketConfig:

    def test_market_config_asx_enabled_by_default(self):
        mc = MarketConfig()
        assert mc.asx_equities is True

    def test_market_config_au_benchmark_is_axjo(self):
        mc = MarketConfig()
        assert mc.au_benchmark == "^AXJO"

    def test_market_config_aud_usd_attribution_enabled(self):
        mc = MarketConfig()
        assert mc.aud_usd_attribution is True

    def test_pipeline_config_contains_market_config(self):
        cfg = PipelineConfig(market=MarketConfig(asx_equities=False))
        assert cfg.market.asx_equities is False
