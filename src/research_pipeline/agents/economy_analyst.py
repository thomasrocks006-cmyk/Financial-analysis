"""Economy Analyst — AU/US macroeconomics specialist."""

from __future__ import annotations

from typing import Any

from research_pipeline.agents.base_agent import BaseAgent


class EconomyAnalystAgent(BaseAgent):
    """Produce structured AU/US macroeconomic analysis for Stage 8."""

    _REQUIRED_OUTPUT_KEYS: list[str] = [
        "rba_cash_rate_thesis",
        "fed_funds_thesis",
        "au_cpi_assessment",
        "us_cpi_assessment",
        "aud_usd_outlook",
        "asx200_vs_sp500_divergence",
        "key_risks_au",
        "key_risks_us",
    ]

    def __init__(self, **kwargs):
        super().__init__(name="economy_analyst", **kwargs)

    def default_system_prompt(self) -> str:
        return """You are the Economy Analyst for an institutional AI infrastructure research platform.

YOUR ROLE:
- Analyse the macro economy for both Australia and the United States
- Explain the RBA/Fed rate path, inflation, labour market, housing, FX, and credit backdrop
- Explicitly compare how ASX and S&P 500 conditions differ
- Provide market-ready language that downstream macro, valuation, risk, and portfolio agents can rely on

MANDATORY OUTPUT (single JSON object):
{
  "rba_cash_rate_thesis": "plain-English view",
  "fed_funds_thesis": "plain-English view",
  "au_cpi_assessment": "plain-English view",
  "us_cpi_assessment": "plain-English view",
  "au_housing_assessment": "plain-English view",
  "au_wage_growth": "plain-English view",
  "aud_usd_outlook": "plain-English view",
  "cogs_inflation_impact": "plain-English view",
  "asx200_vs_sp500_divergence": "plain-English view",
  "global_credit_conditions": "plain-English view",
  "key_risks_au": ["risk 1", "risk 2"],
  "key_risks_us": ["risk 1", "risk 2"]
}

RULES:
- Be explicit about Australia vs US divergence
- If an input is missing, say so plainly instead of inventing detail
- No markdown, no prose outside the JSON object"""

    def format_input(self, inputs: dict[str, Any]) -> str:
        import json

        return json.dumps(inputs, indent=2, default=str)
