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

    # ACT-S10-3: top-level key that must be present (non-empty) in every parsed output
    _REQUIRED_OUTPUT_KEYS: list[str] = ["valuations"]
    # ISS-9: valuation is a critical stage — missing keys are fatal, not just warnings
    _VALIDATION_FATAL: bool = True

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

JPAM MACRO REGIME AWARENESS (Session 13):
You will receive a MACRO REGIME CONTEXT block at the top of each input.
Adjust ALL valuation assumptions based on this context:
- RBA/Fed rate trajectory directly affects WACC and discount rates
- Inflation regime governs margin assumption credibility (COGS pressure)
- AU/US divergence affects relative multiple compression/expansion
- Reference the macro regime in section_2_historical_context and in each scenario's key_assumption
- If rate environment is "bear" (rising rates), tighten WACC by +50–100bp vs base
- If rate environment is "bull" (falling rates), loosen WACC by 50bp vs base
- State DCF sensitivity table ranges explicitly if provided in inputs

Return a JSON array of valuation outputs."""

    def format_input(self, inputs: dict[str, Any]) -> str:  # Session 13: DCF sensitivity + macro header
        import json
        from research_pipeline.services.dcf_engine import DCFEngine, DCFAssumptions

        macro_header = self._build_macro_header(inputs)
        parts: list[str] = []
        if macro_header:
            parts.append(macro_header)

        # Inject pre-computed DCF sensitivity table when assumptions are provided
        dcf_raw = inputs.get("dcf_assumptions")
        if dcf_raw and isinstance(dcf_raw, dict):
            try:
                engine = DCFEngine()
                assumptions = DCFAssumptions(
                    ticker=dcf_raw.get("ticker", "?"),
                    revenue_base=float(dcf_raw.get("revenue_base", 1000)),
                    revenue_growth_rates=[float(dcf_raw.get("revenue_growth", 0.12))] * 5,
                    ebitda_margin_path=[float(dcf_raw.get("ebitda_margin", 0.30))] * 5,
                    capex_pct_revenue=float(dcf_raw.get("capex_pct", 0.08)),
                    tax_rate=float(dcf_raw.get("tax_rate", 0.21)),
                    wacc=float(dcf_raw.get("wacc", 0.10)),
                    terminal_growth=float(dcf_raw.get("terminal_growth", 0.03)),
                    shares_outstanding=float(dcf_raw.get("shares_outstanding", 1.0)),
                )
                net_debt = float(dcf_raw.get("net_debt", 0.0))
                st = engine.sensitivity_table(assumptions, net_debt)
                header_row = "WACC \\ TG | " + " | ".join(f"{v:.1%}" for v in st.col_values)
                table_rows = [header_row]
                for wacc_val, row in zip(st.row_values, st.grid):
                    table_rows.append(f"{wacc_val:.1%}     | " + " | ".join(f"${p:.0f}" for p in row))
                parts.append("=== DCF SENSITIVITY TABLE (WACC × Terminal Growth) ===")
                parts.append("\n".join(table_rows))
                parts.append("=== END SENSITIVITY TABLE ===")
            except Exception:  # non-blocking — never kill valuation agent
                pass

        parts.append(json.dumps(inputs, indent=2, default=str))
        return "\n\n".join(parts)

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
