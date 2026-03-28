"""Session 12 — EconomyAnalystAgent: full AU + US macroeconomic analysis.

Outputs 12 structured fields covering:
- RBA and Fed monetary policy thesis
- AU and US inflation assessment
- AU housing market
- AU wage growth
- AUD/USD outlook
- COGS inflation impact on AI infrastructure
- ASX 200 vs S&P 500 macro divergence
- Global credit conditions
- Key risks (AU and US)
"""

from __future__ import annotations

import logging

from research_pipeline.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# Required output keys for quality gate (ACT-S10-3)
_REQUIRED_KEYS = [
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


class EconomyAnalystAgent(BaseAgent):
    """AU/US macroeconomic analyst — 12-field structured output.

    Interprets live EconomicIndicators + MacroScenario data and produces
    qualitative theses across all key macro axes relevant to an Australian
    institutional investor.
    """

    _REQUIRED_OUTPUT_KEYS = _REQUIRED_KEYS

    def __init__(self, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(name="economy_analyst", **kwargs)

    def default_system_prompt(self) -> str:
        return (
            "You are a senior macroeconomist at JP Morgan Asset Management Australia. "
            "Your role is to produce concise, institutional-quality macro analysis across "
            "Australian and US economies for equity and portfolio research teams.\n\n"
            "You must produce a JSON object with EXACTLY these 12 keys:\n"
            "- rba_cash_rate_thesis: string — current RBA stance, trajectory, and market implications\n"
            "- fed_funds_thesis: string — Fed policy trajectory, dot-plot implications, market pricing\n"
            "- au_cpi_assessment: string — AU CPI vs RBA target band; trimmed mean trajectory\n"
            "- us_cpi_assessment: string — US CPI/PCE vs 2% target; disinflation progress\n"
            "- au_housing_assessment: string — dwelling price trend, credit growth, auction clearance\n"
            "- au_wage_growth: string — WPI trend, wage-price spiral risk, productivity context\n"
            "- aud_usd_outlook: string — near-term direction, commodity link, rate differential\n"
            "- cogs_inflation_impact: string — supply chain/COGS pressure on AI infrastructure margins\n"
            "- asx200_vs_sp500_divergence: string — relative performance and key drivers of divergence\n"
            "- global_credit_conditions: string — IG/HY spreads, credit availability, refinancing risk\n"
            "- key_risks_au: list[string] — top 3-5 AU-specific macro risks\n"
            "- key_risks_us: list[string] — top 3-5 US-specific macro risks\n\n"
            "Use the provided economic indicators as inputs. All values are real data unless marked synthetic.\n"
            "Calibrate for an Australian institutional audience — super funds, SMSF, HNW clients.\n"
            "Return ONLY the JSON object with these 12 keys. No preamble, no markdown."
        )

    def format_input(self, inputs: dict) -> str:  # type: ignore[override]
        import json

        economic_indicators = inputs.get("economic_indicators", {})
        macro_scenario = inputs.get("macro_scenario", {})
        universe = inputs.get("universe", [])

        return json.dumps(
            {
                "task": "macro_analysis",
                "universe": universe,
                "economic_indicators": economic_indicators,
                "macro_scenario_summary": macro_scenario,
                "output_format": "json_12_fields",
            },
            indent=2,
            default=str,
        )
