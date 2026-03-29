"""B9 — Red Team Analyst: break the thesis."""

from __future__ import annotations

from typing import Any

from research_pipeline.agents.base_agent import BaseAgent


class RedTeamAnalystAgent(BaseAgent):
    """Adversarial analyst — tries to break the thesis before publication.

    Minimum 3 falsification paths per top idea.
    """

    # ISS-9: red team is critical — missing top-level assessments block must be fatal
    _REQUIRED_OUTPUT_KEYS: list[str] = ["assessments"]
    _VALIDATION_FATAL: bool = True

    def __init__(self, **kwargs):
        super().__init__(name="red_team_analyst", **kwargs)

    def default_system_prompt(self) -> str:
        return """You are the Red Team Analyst for an institutional AI infrastructure research platform.

YOUR JOB: Try to break the thesis. If you cannot break it, it is stronger for surviving. If you can, you saved the team from publishing weak work.

You are NOT producing a bearish conclusion. You are forcing every bullish assumption to be explicitly defended.

INPUTS:
- Sector analyst four-box outputs (Box 4 — analyst judgment)
- Valuation analyst scenarios
- Claim ledger (evidence quality)

YOUR MANDATORY OUTPUT PER NAME:
{
  "ticker": "TICKER",
  "date": "YYYY-MM-DD",
  
  "section_1_what_is_priced_in": {
    "consensus_view": "What the market already believes",
    "is_thesis_differentiated": true/false,
    "edge_justification": "If consensus-confirming, why expect above-market returns?"
  },
  
  "section_2_falsification_tests": [
    {
      "assumption": "The specific bullish assumption being tested",
      "test": "If [assumption] is wrong, the thesis [breaks/weakens/survives]",
      "evidence_trigger": "What data in next 2 quarters would confirm the bear case",
      "current_probability": "LOW | MEDIUM | HIGH"
    }
  ],
  
  "required_tests": {
    "ai_efficiency_shock": "DeepSeek-style 40-60% compute efficiency — impact per name",
    "hyperscaler_capex_pause": "Top-5 pauses AI capex 2-3 quarters — backlog impact",
    "valuation_compression": "Sector P/E de-rates 20% — what return remains?",
    "execution_failure": "Company-specific operational catalyst fails",
    "geopolitical_shock": "Taiwan Strait escalation (TSM-specific + correlated drawdown)"
  },
  
  "section_3_crowding_assessment": {
    "consensus_crowding_score": 0-10,
    "positioning_risk": "description",
    "what_would_cause_unwind": "trigger event"
  },
  
  "section_4_correlated_risks": [
    "Risk that affects multiple positions simultaneously"
  ],
  
  "thesis_integrity_score": "ROBUST | MODERATE | FRAGILE",
  "summary": "One paragraph: strongest bear argument in plain language"
}

PORTFOLIO-LEVEL OUTPUT:
{
  "portfolio_correlation_risks": ["risks affecting 3+ names"],
  "worst_case_scenario": "description of maximum correlated drawdown",
  "concentration_concern": "where the portfolio is most vulnerable"
}

HARD RULES:
- Minimum 3 concrete disconfirming risks per name (not generic)
- Identify story/valuation mismatch risk
- If current price > consensus target, thesis integrity cannot be ROBUST

JPAM MACRO REGIME AWARENESS (Session 13):
A MACRO REGIME CONTEXT block is prepended to each input.
Use it to:
- Add macro/rate regime as a required_test where applicable (e.g. "rates_rise_150bp")
- Assess whether bull-case multiples are defensible against current rate environment
- Flag AU/USD sensitivity for AU-listed names when RBA path available
- Reference macro scenario type in portfolio_summary.macro_risk_flags

Return a JSON object with keys "assessments" (array, one per ticker) and "portfolio_summary" (object)."""

    def format_input(self, inputs: dict[str, Any]) -> str:
        import json
        return json.dumps(inputs, indent=2, default=str)

    def parse_output(self, raw_response: str) -> dict[str, Any]:
        """Enforce minimum 3 falsification tests per ticker."""
        from research_pipeline.agents.base_agent import StructuredOutputError

        parsed = super().parse_output(raw_response)

        # Accept either {"assessments": [...]} or a bare list
        assessments = parsed.get("assessments", parsed) if isinstance(parsed, dict) else parsed

        if isinstance(assessments, list):
            violations: list[str] = []
            for assessment in assessments:
                if not isinstance(assessment, dict):
                    continue
                ticker = assessment.get("ticker", "?")
                tests = assessment.get("section_2_falsification_tests", [])
                if not isinstance(tests, list) or len(tests) < 3:
                    violations.append(
                        f"[{ticker}] has {len(tests) if isinstance(tests, list) else 0} "
                        f"falsification tests — minimum 3 required per name"
                    )
                required = assessment.get("required_tests", {})
                if not isinstance(required, dict) or len(required) < 3:
                    violations.append(
                        f"[{ticker}] missing required_tests block (ai_efficiency_shock, "
                        f"hyperscaler_capex_pause, etc.)"
                    )

            if violations:
                raise StructuredOutputError(
                    "RedTeam: insufficient falsification coverage — agent must fix:\n"
                    + "\n".join(violations)
                )

        if isinstance(parsed, list):
            return {"assessments": parsed}
        return parsed
