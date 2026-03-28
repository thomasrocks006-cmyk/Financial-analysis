"""B6 — Valuation Analyst: interpret model outputs, not generate raw arithmetic."""

from __future__ import annotations

from typing import Any

from research_pipeline.agents.base_agent import BaseAgent


class ValuationAnalystAgent(BaseAgent):
    """The ONLY role that produces price targets and return scenarios.

    Uses DCF engine outputs, relative valuation tables, reverse DCF.
    Must label methodology, sensitivity, confidence level.
    Cannot present single-point fair value without ranges.
    """

    def __init__(self, **kwargs):
        super().__init__(name="valuation_analyst", **kwargs)

    def default_system_prompt(self) -> str:
        return """You are the Valuation Analyst for an institutional AI infrastructure research platform.

YOU ARE THE ONLY PERSON WHO SETS PRICE TARGETS AND RETURN SCENARIOS.

INPUTS YOU RECEIVE:
- Sector analyst four-box outputs (from Compute, Power/Energy, Infrastructure analysts)
- Evidence-cleared claim ledger
- DCF engine outputs (deterministic math — you interpret, not recalculate)
- Market data snapshots (prices, multiples, consensus targets)

YOUR MANDATORY OUTPUT PER NAME:
{
  "ticker": "TICKER",
  "date": "YYYY-MM-DD",
  "section_1_valuation_snapshot": {
    "current_price": 0.00,
    "market_cap": 0.00,
    "trailing_pe": 0.00,
    "forward_pe": 0.00,
    "ev_ebitda": 0.00,
    "sources": "Tier 3 dated"
  },
  "section_2_historical_context": "Where multiples sit vs 3-year history and sector peers. State limitation if data unavailable.",
  "section_3_upside_decomposition": {
    "revenue_growth_contribution": "X%",
    "margin_expansion_contribution": "X%",
    "multiple_rerate_contribution": "X%",
    "dividend_return_contribution": "X%",
    "primary_driver": "revenue_growth | margin_expansion | multiple_rerate",
    "note": "If upside is mostly multiple re-rating, state explicitly — least defensible driver"
  },
  "section_4_consensus": {
    "target_12m": 0.00,
    "target_range": "low - high",
    "num_analysts": 0,
    "rating_distribution": "Buy/Hold/Sell",
    "limitation": "Snapshot from aggregated platforms. No revision history available."
  },
  "section_5_scenarios": [
    {
      "case": "base",
      "probability_pct": 50,
      "revenue_cagr": "X%",
      "exit_multiple": "Xx",
      "exit_multiple_rationale": "why this multiple",
      "implied_return_1y": "X%",
      "implied_return_3y": "X% [HOUSE VIEW]",
      "key_assumption": "what must be true",
      "what_breaks_it": "what falsifies this"
    }
  ],
  "entry_quality": "STRONG | ACCEPTABLE | STRETCHED | POOR",
  "expectation_pressure_score": "0-10",
  "crowding_score": "0-10",
  "methodology_tag": "HOUSE VIEW"
}

HARD RULES:
- All 3-year and 5-year targets labelled [HOUSE VIEW]
- If 1-year target is consensus-derived, say so
- Do NOT treat consensus as truth
- When current price is above consensus target, flag explicitly
- No single-point fair values — always provide ranges
- methodology_tag is MANDATORY — every output must have it set (not null/empty)

Return a JSON array of valuation outputs."""

    def format_input(self, inputs: dict[str, Any]) -> str:
        import json
        return json.dumps(inputs, indent=2, default=str)

    def parse_output(self, raw_response: str) -> dict[str, Any]:
        """Enforce mandatory methodology_tag on every price target."""
        from research_pipeline.agents.base_agent import StructuredOutputError

        parsed = super().parse_output(raw_response)
        entries = parsed if isinstance(parsed, list) else parsed.get("valuations", [])

        if not isinstance(entries, list) or len(entries) == 0:
            raise StructuredOutputError(
                "ValuationAnalyst: expected a JSON array of valuation outputs; got empty."
            )

        violations: list[str] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            ticker = entry.get("ticker", "?")
            meth_tag = entry.get("methodology_tag", "")
            entry_quality = entry.get("entry_quality", "")
            if not meth_tag:
                violations.append(f"[{ticker}] missing 'methodology_tag' — all targets must be tagged HOUSE VIEW or methodology")
            if not entry_quality:
                violations.append(f"[{ticker}] missing 'entry_quality' field")
            scenarios = entry.get("section_5_scenarios", [])
            for sc in (scenarios if isinstance(scenarios, list) else []):
                if isinstance(sc, dict) and not sc.get("what_breaks_it"):
                    violations.append(f"[{ticker}] scenario '{sc.get('case', '?')}' missing 'what_breaks_it' falsification")

        if violations:
            raise StructuredOutputError(
                "ValuationAnalyst: methodology or structure violations:\n"
                + "\n".join(violations)
            )

        if isinstance(parsed, list):
            return {"valuations": parsed}
        return parsed
