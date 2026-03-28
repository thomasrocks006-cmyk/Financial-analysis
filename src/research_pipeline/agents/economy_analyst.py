"""Session 12 — EconomyAnalystAgent.

Full AU + US macro analyst agent. Receives EconomicIndicators and MacroScenario,
produces EconomyAnalysis with 12 structured fields covering:

  Australian:
    rba_cash_rate_thesis, au_cpi_assessment, au_housing_assessment,
    au_wage_growth, aud_usd_outlook

  United States:
    fed_funds_thesis, us_cpi_assessment

  Cross-market:
    cogs_inflation_impact, asx200_vs_sp500_divergence, global_credit_conditions

  Risk:
    key_risks_au, key_risks_us

Part of Session 12: Macro Economy & AU/US Markets.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from research_pipeline.agents.base_agent import BaseAgent
from research_pipeline.schemas.macro_economy import (
    AudUsdDirection,
    EconomicIndicators,
    EconomyAnalysis,
    FedStance,
    HousingTrend,
    InflationTrend,
    MacroScenario,
    RBAStance,
)

logger = logging.getLogger(__name__)


class EconomyAnalystAgent(BaseAgent):
    """AU/US Macro Economy Analyst — 12-field structured output.

    This agent synthesises EconomicIndicators and MacroScenario into a
    comprehensive EconomyAnalysis that feeds MacroStrategistAgent.

    Required output keys:
        rba_cash_rate_thesis, fed_funds_thesis, au_cpi_assessment,
        us_cpi_assessment, au_housing_assessment, au_wage_growth,
        aud_usd_outlook, cogs_inflation_impact,
        asx200_vs_sp500_divergence, global_credit_conditions,
        key_risks_au, key_risks_us
    """

    _REQUIRED_OUTPUT_KEYS: list[str] = [
        "rba_cash_rate_thesis",
        "fed_funds_thesis",
        "au_cpi_assessment",
        "us_cpi_assessment",
        "key_risks_au",
        "key_risks_us",
    ]
    _VALIDATION_FATAL: bool = True

    def __init__(self, **kwargs):
        super().__init__(name="economy_analyst", **kwargs)

    def default_system_prompt(self) -> str:
        return """You are the Macro Economy Analyst for a JP Morgan Australia-style institutional asset management office.

YOUR ROLE:
- Provide comprehensive AU and US macro analysis for an Australian-based portfolio manager
- Cover RBA and Fed policy, inflation, housing, currency, credit conditions
- Be specific about AU vs US divergence and the implications for AU investors holding US equities

YOUR OUTPUT (JSON with these 12 fields — all required):
{
  "rba_cash_rate_thesis": "Detailed RBA policy thesis with cash rate path, trigger conditions for cuts/hikes, and probability weighting",
  "fed_funds_thesis": "Fed policy thesis — current stance, dot-plot path, key data dependencies, and risk of deviation",
  "au_cpi_assessment": "AU inflation analysis — headline vs trimmed mean, services stickiness, wages pass-through, target timeline",
  "us_cpi_assessment": "US CPI/PCE analysis — shelter lag, goods deflation, PCE vs CPI divergence, Fed's forward tolerance",
  "au_housing_assessment": "AU housing market — dwelling prices, mortgage stress, credit growth, supply pipeline, rate sensitivity",
  "au_wage_growth": "AU WPI trend — enterprise bargaining outcomes, productivity offset, minimum wage decisions, pass-through risk",
  "aud_usd_outlook": "AUD/USD outlook — rate differential carry, terms of trade (iron ore, LNG), China demand, portfolio implications",
  "cogs_inflation_impact": "Input cost pressure on AU companies — energy prices, labour costs, freight, impact on listed AU industrials and retailers",
  "asx200_vs_sp500_divergence": "Macro-driven divergence — sector composition (banks vs tech), currency effects, valuation gap, rotation signals",
  "global_credit_conditions": "Credit environment — IG/HY spreads, bank lending standards, shadow banking, EM spillover risk to AU",
  "key_risks_au": ["list of 3-5 specific AU macro risks with brief description each"],
  "key_risks_us": ["list of 3-5 specific US macro risks with brief description each"],
  "rba_stance": "hiking | on_hold | cutting | unknown",
  "fed_stance": "hiking | on_hold | cutting | unknown",
  "au_inflation_trend": "above_target | on_target | below_target | unknown",
  "au_housing_trend": "accelerating | stable | correcting | unknown",
  "aud_usd_direction": "strengthening | stable | weakening | unknown",
  "confidence": "HIGH | MEDIUM | LOW"
}

RULES:
- AU-specific context first — this is an Australian institutional perspective
- Be explicit about AUD hedging implications for AU investors with US equity exposure
- Distinguish current state vs 12-month forward expectations
- Cite specific data points from the indicators provided when available
- key_risks_au and key_risks_us must be arrays of specific strings, not nested objects"""

    def format_input(
        self,
        indicators: EconomicIndicators,
        scenario: MacroScenario,
        run_id: str,
    ) -> dict[str, Any]:
        """Build the agent input dict from indicators and scenario."""
        return {
            "au_indicators": {
                "rba_cash_rate_pct": indicators.au.rba_cash_rate_pct,
                "rba_cash_rate_outlook": indicators.au.rba_cash_rate_outlook,
                "au_cpi_yoy_pct": indicators.au.au_cpi_yoy_pct,
                "au_cpi_trimmed_mean_pct": indicators.au.au_cpi_trimmed_mean_pct,
                "au_unemployment_rate_pct": indicators.au.au_unemployment_rate_pct,
                "au_wpi_yoy_pct": indicators.au.au_wpi_yoy_pct,
                "au_gdp_growth_qoq_pct": indicators.au.au_gdp_growth_qoq_pct,
                "au_housing_price_index_change_pct": indicators.au.au_housing_price_index_change_pct,
                "au_auction_clearance_rate_pct": indicators.au.au_auction_clearance_rate_pct,
                "au_10y_government_yield_pct": indicators.au.au_10y_government_yield_pct,
                "aud_usd": indicators.au.aud_usd,
                "data_freshness": indicators.au.data_freshness,
            },
            "us_indicators": {
                "fed_funds_rate_pct": indicators.us.fed_funds_rate_pct,
                "us_cpi_yoy_pct": indicators.us.us_cpi_yoy_pct,
                "us_core_pce_yoy_pct": indicators.us.us_core_pce_yoy_pct,
                "us_unemployment_rate_pct": indicators.us.us_unemployment_rate_pct,
                "us_10y_treasury_yield_pct": indicators.us.us_10y_treasury_yield_pct,
                "us_yield_curve_spread_10y_2y": indicators.us.us_yield_curve_spread_10y_2y,
                "us_hy_spread_bps": indicators.us.us_hy_spread_bps,
                "data_freshness": indicators.us.data_freshness,
            },
            "macro_scenario": {
                "composite_scenario": scenario.composite_scenario.value,
                "composite_description": scenario.composite_description,
                "au_rates_base": scenario.au_rates.base,
                "au_rates_bear": scenario.au_rates.bear,
                "us_rates_base": scenario.us_rates.base,
                "aud_usd_base": scenario.aud_usd.base,
                "au_equities_impact": scenario.au_equities_impact,
                "us_equities_impact": scenario.us_equities_impact,
            },
            "run_id": run_id,
        }

    def parse_economy_analysis(
        self, raw_output: dict[str, Any], run_id: str
    ) -> EconomyAnalysis:
        """Parse agent JSON output into a typed EconomyAnalysis model."""
        def safe_list(val: Any) -> list[str]:
            if isinstance(val, list):
                return [str(x) for x in val]
            if isinstance(val, str):
                return [val]
            return []

        def safe_enum(cls, val: str, default):
            try:
                return cls(val.lower())
            except (ValueError, AttributeError):
                return default

        return EconomyAnalysis(
            run_id=run_id,
            confidence=raw_output.get("confidence", "MEDIUM"),
            rba_cash_rate_thesis=raw_output.get("rba_cash_rate_thesis", ""),
            fed_funds_thesis=raw_output.get("fed_funds_thesis", ""),
            au_cpi_assessment=raw_output.get("au_cpi_assessment", ""),
            us_cpi_assessment=raw_output.get("us_cpi_assessment", ""),
            au_housing_assessment=raw_output.get("au_housing_assessment", ""),
            au_wage_growth=raw_output.get("au_wage_growth", ""),
            aud_usd_outlook=raw_output.get("aud_usd_outlook", ""),
            cogs_inflation_impact=raw_output.get("cogs_inflation_impact", ""),
            asx200_vs_sp500_divergence=raw_output.get("asx200_vs_sp500_divergence", ""),
            global_credit_conditions=raw_output.get("global_credit_conditions", ""),
            key_risks_au=safe_list(raw_output.get("key_risks_au", [])),
            key_risks_us=safe_list(raw_output.get("key_risks_us", [])),
            rba_stance=safe_enum(RBAStance, raw_output.get("rba_stance", ""), RBAStance.UNKNOWN),
            fed_stance=safe_enum(FedStance, raw_output.get("fed_stance", ""), FedStance.UNKNOWN),
            au_inflation_trend=safe_enum(
                InflationTrend, raw_output.get("au_inflation_trend", ""), InflationTrend.UNKNOWN
            ),
            au_housing_trend=safe_enum(
                HousingTrend, raw_output.get("au_housing_trend", ""), HousingTrend.UNKNOWN
            ),
            aud_usd_direction=safe_enum(
                AudUsdDirection, raw_output.get("aud_usd_direction", ""), AudUsdDirection.UNKNOWN
            ),
        )

    async def run_economy_analysis(
        self,
        indicators: EconomicIndicators,
        scenario: MacroScenario,
        run_id: str,
    ) -> EconomyAnalysis:
        """Run the full macro analysis: format inputs → call LLM → parse output.

        Falls back to a synthetic economy analysis if LLM call fails.
        """
        formatted = self.format_input(indicators, scenario, run_id)
        result = await self.run(
            user_message=f"Analyse the following macro indicators and scenario matrix:\n{json.dumps(formatted, indent=2, default=str)}",
            run_id=run_id,
        )

        if result.success and result.parsed_output:
            try:
                return self.parse_economy_analysis(result.parsed_output, run_id)
            except Exception as exc:
                logger.warning("EconomyAnalystAgent parse failed: %s — using fallback", exc)

        return self._synthetic_fallback(indicators, scenario, run_id)

    def _synthetic_fallback(
        self,
        indicators: EconomicIndicators,
        scenario: MacroScenario,
        run_id: str,
    ) -> EconomyAnalysis:
        """Return a minimally populated EconomyAnalysis for offline/test use."""
        au = indicators.au
        us = indicators.us
        rate = au.rba_cash_rate_pct or 4.35
        fed = us.fed_funds_rate_pct or 5.375

        return EconomyAnalysis(
            run_id=run_id,
            confidence="LOW",
            rba_cash_rate_thesis=(
                f"RBA cash rate at {rate:.2f}%. {scenario.au_rates.base}"
            ),
            fed_funds_thesis=(
                f"Fed funds at {fed:.2f}%. {scenario.us_rates.base}"
            ),
            au_cpi_assessment=(
                f"AU trimmed mean CPI at {au.au_cpi_trimmed_mean_pct or 'N/A'}% — "
                f"{scenario.au_inflation.base}"
            ),
            us_cpi_assessment=(
                f"US CPI at {us.us_cpi_yoy_pct or 'N/A'}% — "
                f"{scenario.us_rates.base}"
            ),
            au_housing_assessment=scenario.au_housing.base,
            au_wage_growth=(
                f"WPI at {au.au_wpi_yoy_pct or 'N/A'}% — monitoring enterprise bargaining outcomes"
            ),
            aud_usd_outlook=scenario.aud_usd.base,
            cogs_inflation_impact="Input cost pressures broadly in line with CPI — monitor energy and wages",
            asx200_vs_sp500_divergence=(
                "ASX 200 financials-heavy vs S&P 500 tech-heavy — different rate sensitivity profiles"
            ),
            global_credit_conditions=(
                f"IG spreads {us.us_ig_spread_bps or 'N/A'} bps, HY spreads {us.us_hy_spread_bps or 'N/A'} bps — "
                "broadly stable credit environment"
            ),
            key_risks_au=[
                "Persistent services inflation forcing additional RBA hike",
                "Housing market correction triggering mortgage stress and bank NPL increase",
                "China demand slowdown reducing commodity export revenues",
            ],
            key_risks_us=[
                "PCE re-acceleration forcing Fed to abandon easing plans",
                "US commercial real estate credit losses spreading to regional banks",
                "Geopolitical escalation triggering risk-off and broad asset sell-off",
            ],
        )
