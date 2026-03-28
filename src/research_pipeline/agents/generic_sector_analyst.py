"""Generic Sector Analyst — fallback for tickers not covered by specialist routes.

ARC-5 / ISS-3: tickers not in SECTOR_ROUTING land here so the pipeline
never silently skips a position.  The generic analyst produces the same
four-box output format as the three specialist analysts but without
subtheme-specific framing.
"""

from __future__ import annotations

from typing import Any

from research_pipeline.agents.sector_analysts import SectorAnalystBase


class GenericSectorAnalystAgent(SectorAnalystBase):
    """Fallback sector analyst for tickers not covered by specialist routing.

    Produces identical four-box output to the specialist analysts so
    Stage 6 gate and downstream stages see no structural difference.
    Used only when at least one ticker remains unrouted after
    compute/power_energy/infrastructure routing in Stage 6.
    """

    # Critical output keys: a four-box entry must be present per ticker
    _REQUIRED_OUTPUT_KEYS = ["sector_outputs"]

    def __init__(self, **kwargs):
        super().__init__(name="generic_sector_analyst", **kwargs)

    def default_system_prompt(self) -> str:
        four_box = self._four_box_prompt_section()
        return f"""You are an Institutional Equity Research Analyst covering companies
outside the primary AI compute, power, and infrastructure themes.

YOUR ROLE:
- Provide rigorous four-box analysis for any publicly traded company
- Apply the same evidence quality standards as a specialist sector analyst
- Identify the company's primary business, end-markets, and investment thesis
- Assess how the company relates to, or benefits from, AI infrastructure investment

{four_box}

ADDITIONAL GUIDANCE FOR GENERIC COVERAGE:
- First classify the company's primary sector (technology, industrials, energy, materials, etc.)
- Note any indirect exposure to AI infrastructure themes
- Be explicit about what you do NOT know rather than speculating
- Use the same tier classification for sources as specialist analysts

CRITICAL RULES:
- Never skip a ticker — produce a four-box entry for EVERY ticker provided
- Label your output as generic/cross-sector coverage, not specialist
- Do not fabricate company-specific data you lack confidence in

OUTPUT:
Return a JSON array at the top-level. Example:
{{
  "sector_outputs": [
    {{
      "ticker": "TICKER",
      "company_name": "Company Name",
      "analyst_role": "generic",
      "sector_classification": "primary sector",
      "ai_infrastructure_exposure": "direct | indirect | none",
      "date": "YYYY-MM-DD",
      "box1_verified_facts": "...",
      "box2_management_guidance": "...",
      "box3_consensus_market_view": "...",
      "box4_analyst_judgment": "...",
      "key_risks": ["risk1", "risk2"],
      "claims_for_librarian": []
    }}
  ]
}}"""

    def format_input(self, inputs: dict[str, Any]) -> str:
        tickers = inputs.get("tickers", [])
        market_data = inputs.get("market_data", [])
        macro_context = inputs.get("macro_context_summary", "")

        parts = [
            f"TICKERS TO ANALYSE (generic/cross-sector): {', '.join(tickers)}",
            "",
            "These tickers are not covered by specialist sector analysts (compute/power/infrastructure).",
            "Apply full four-box analysis using publicly available information.",
        ]

        if macro_context:
            parts += ["", f"MACRO CONTEXT: {macro_context}"]

        if market_data:
            parts += ["", "MARKET DATA SNAPSHOT:"]
            for md in market_data[:10]:
                if isinstance(md, dict) and md.get("ticker") in tickers:
                    price = md.get("price") or md.get("market_data", {}).get("price", "N/A")
                    cap = md.get("market_cap") or md.get("market_data", {}).get("market_cap", "N/A")
                    parts.append(f"  {md.get('ticker', '?')}: price={price} market_cap={cap}")

        return "\n".join(parts)
