"""P-7 — Fixed Income Analyst Agent.

Analyses how macroeconomic fixed-income conditions (yield curve, credit spreads,
rate path) affect the AI infrastructure equity thesis.  This agent does NOT
trade bonds — it provides interest-rate and credit-context commentary for equity
investment decisions.

Context produced:
- Rate sensitivity score per ticker (duration-proxy via growth premium analysis)
- Credit quality / leverage flag (ND/EBITDA, interest coverage)
- Yield curve regime classification and sector rotation read-through
- Spread context for capital-markets risk (refinancing, cost of capital)
"""

from __future__ import annotations

from typing import Any

from research_pipeline.agents.base_agent import BaseAgent


class FixedIncomeAnalystAgent(BaseAgent):
    """Fixed-income context agent for the equity research pipeline.

    Integrates with Stage 9 (Quant Risk & Scenario Testing) to provide
    macro rate/credit commentary alongside the quantitative risk packet.

    Mandatory output keys
    ─────────────────────
    ``rate_sensitivity_score``  —  1 (defensive) – 10 (highly rate-sensitive)
    ``yield_curve_regime``      —  "steepening" | "flattening" | "inverted" | "normal"
    ``cost_of_capital_trend``   —  "rising" | "stable" | "falling"
    ``credit_quality_flags``    —  per-ticker net-debt/EBITDA, IC ratio alerts
    ``sector_rotation_read``    —  equity sector rotation implication
    ``key_risks``               —  list of specific rate/credit risks
    ``offsetting_factors``      —  list of mitigants (e.g. asset-light models)
    ``methodology_note``        —  method/data transparency tag
    """

    def __init__(self, **kwargs):
        super().__init__(name="fixed_income_analyst", **kwargs)

    def default_system_prompt(self) -> str:
        return """\
You are the Fixed Income Macro Analyst for an institutional equity research platform
focused on AI infrastructure (semiconductors, power, data centres, connectivity).

YOUR ROLE:
Provide interest-rate and credit-market context that informs, but does not replace,
the equity investment thesis. You never set price targets — that is the Valuation
Analyst's role. You interpret *macro fixed-income conditions* and their *equity
read-throughs*.

INPUTS YOU RECEIVE:
- Portfolio universe (ticker list with subtheme labels)
- Macro context: prevailing 10Y UST yield, credit spread index (IG/HY OAD), yield
  curve shape (2Y-10Y spread)
- Company leverage data: net debt / EBITDA, interest coverage ratios (where available
  from DCF/market data)
- VaR and scenario outputs from the quant risk engine

YOUR MANDATORY JSON OUTPUT:
{
  "yield_curve_regime": "steepening | flattening | inverted | normal",
  "10y_yield_context": "brief commentary on rate level vs historical, Fed path",
  "cost_of_capital_trend": "rising | stable | falling",
  "rate_sensitivity_score": 1-10,
  "rate_sensitivity_rationale": "explanation — which subthemes are most exposed",
  "sector_rotation_read": "which subthemes benefit/suffer in current rate regime",
  "credit_quality_flags": [
    {
      "ticker": "TICKER",
      "net_debt_ebitda": float_or_null,
      "interest_coverage_ratio": float_or_null,
      "flag": "clean | elevated | watch | distressed",
      "note": "brief context"
    }
  ],
  "capital_markets_risk": "commentary on refinancing risk, spread widening impact",
  "key_risks": [
    "Specific rate/credit risk 1",
    "Specific rate/credit risk 2"
  ],
  "offsetting_factors": [
    "Mitigant 1 (e.g. asset-light revenue model reduces duration)",
    "Mitigant 2"
  ],
  "duration_proxy_commentary": "how AI infrastructure growth premiums embed rate risk",
  "methodology_note": "data sources and limitations — required field"
}

HARD RULES:
1. Do NOT set equity price targets or return forecasts.
2. Always populate ``methodology_note`` — never leave it blank.
3. If credit/leverage data is unavailable, state this explicitly in the flag note.
4. ``rate_sensitivity_score`` 1 = utility-like defensive, 10 = hyper-growth with
   zero earnings and maximum duration risk.
5. Semiconductor foundries (TSM), power utilities (CEG, VST) and infrastructure
   contractors (PWR, ETN) carry very different rate profiles — differentiate them.
6. Flag if current yield level exceeds the discount rate in provided DCF assumptions.

JPAM MACRO REGIME AWARENESS (Session 13):
A MACRO REGIME CONTEXT block is prepended to each input message.
Use it to:
- Anchor yield_curve_regime to actual RBA/Fed stance (not guessed)
- Set cost_of_capital_trend based on current policy trajectory
- Flag AU/US duration divergence in key_risks when central bank paths differ
- Adjust rate_sensitivity_score upward in rising-rate regimes
- Reference current cash rate level in methodology_note

Return a single flat JSON object (not an array)."""

    def format_input(self, inputs: dict[str, Any]) -> str:
        import json

        return json.dumps(inputs, indent=2, default=str)

    def parse_output(self, raw_response: str) -> dict[str, Any]:
        """Validate mandatory fields; fill safe defaults on partial output."""
        parsed = super().parse_output(raw_response)

        # Normalise list-vs-dict response: we expect a flat dict
        if isinstance(parsed, list):
            parsed = parsed[0] if parsed else {}

        # Enforce mandatory fields
        required = {
            "yield_curve_regime": "unknown",
            "cost_of_capital_trend": "unknown",
            "rate_sensitivity_score": 5,
            "methodology_note": "",
            "key_risks": [],
            "offsetting_factors": [],
            "credit_quality_flags": [],
        }
        for key, default in required.items():
            if key not in parsed or parsed[key] is None:
                parsed[key] = default

        # Clamp rate_sensitivity_score to [1, 10]
        try:
            score = float(parsed["rate_sensitivity_score"])
            parsed["rate_sensitivity_score"] = max(1.0, min(10.0, score))
        except (TypeError, ValueError):
            parsed["rate_sensitivity_score"] = 5.0

        if not parsed.get("methodology_note"):
            parsed["methodology_note"] = (
                "No methodology note provided by model — treat as indicative/unverified"
            )

        return parsed
