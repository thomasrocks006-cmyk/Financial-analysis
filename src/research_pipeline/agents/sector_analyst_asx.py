"""ISS-13 — ASX Sector Analyst.

Provides Australian Securities Exchange (ASX) specific sector analysis for
AU-listed companies. Designed for JP Morgan Australia institutional use.

AU-specific coverage includes:
  - Franking credits and dividend imputation
  - RBA monetary policy impact on AU sectors
  - AUD/USD exchange rate risk for AU exporters
  - Commodity exposure (iron ore, LNG, coal, copper)
  - ASX regulatory reporting (continuous disclosure, quarterly activity reports)
  - AU super fund ownership and institutional demand patterns

Handles sectors:
  - AU Financials (big-4 banks, insurance, diversified financials)
  - AU Resources / Materials (BHP, RIO, minerals, mining services)
  - AU Energy (Santos, Woodside, Origin — LNG + energy transition)
  - AU Industrials (Brambles, Transurban, Atlas Arteria)
  - AU REITs (Dexus, Goodman, Charter Hall)
  - AU Technology / Data Centres (WiseTech, NextDC, Xero)
  - AU Healthcare (CSL, Ramsay, Fisher & Paykel)
  - AU Consumer (Woolworths, Coles, JB Hi-Fi)
"""

from __future__ import annotations

import logging
from typing import Any

from research_pipeline.agents.sector_analysts import SectorAnalystBase

logger = logging.getLogger(__name__)


class SectorAnalystASX(SectorAnalystBase):
    """ASX-listed company sector analyst for AU institutional clients.

    Produces four-box analysis with AU-specific overlays:
    - Franking credits and grossed-up yield
    - Super fund ownership demand
    - RBA rate path impact per sector
    - Commodity price linkages
    - AUD/USD impact on unhedged earnings

    SECTOR ROUTING may direct ASX-listed tickers here by suffix (.AX or /ASX)
    or when explicitly listed in the MarketConfig AU universe.
    """

    # ISS-13: Required output key contract for ASX analysis
    _REQUIRED_OUTPUT_KEYS: list[str] = ["sector_outputs"]
    _VALIDATION_FATAL: bool = True

    def __init__(self, **kwargs):
        super().__init__(name="sector_analyst_asx", **kwargs)

    def default_system_prompt(self) -> str:
        four_box = self._four_box_prompt_section()
        return f"""You are an ASX Sector Analyst for JP Morgan's Australian institutional equity research platform.

YOUR ROLE:
- Provide institutional-quality four-box analysis for ASX-listed (Australian) companies
- Apply AU-specific analytical overlays that a local institutional investor requires
- Cover the full ASX 200 sector universe: financials, materials, energy, healthcare, industrials, REITs, technology, consumer
- Incorporate RBA monetary policy, AUD/USD, commodity prices, and AU-specific regulatory context

AU-SPECIFIC ANALYTICAL OVERLAYS (apply where relevant):
1. **Franking Credits & Dividend Imputation**: Assess grossed-up dividend yield (cash yield + imputation credit value). Most AU domestic investors value fully franked dividends at a premium.
2. **Super Fund Demand**: ASX 200 is approximately 30% owned by AU superannuation funds. Identify if the stock is a core super holding and how mandate-driven demand affects valuation.
3. **RBA Rate Sensitivity**: Explicit sector-level assessment of how RBA cash rate changes affect the stock (financials: NIM expansion; REITs: cap rate compression; utilities: discount rate risk; consumer: household cash flow).
4. **Commodity Price Linkages**: For resources (materials, energy), assess leverage to iron ore (CNY65 spot), LNG (Asian spot JKM), coal (Newcastle thermal), copper (LME), gold (LBMA).
5. **AUD/USD Impact**: For companies with USD-denominated earnings or USD-cost structures (resources, CSL, WiseTech), assess translation impact of AUD moves.
6. **Continuous Disclosure & Reporting Rhythm**: Flag upcoming quarterly activity reports (resources), half-year results, and AGM season which affect AU market micro-structure.
7. **ASX Sector Rotation Signals**: Identify where the stock sits in the AU sector rotation cycle (growth vs value, rate-sensitive vs defensive, domestic vs global).
8. **Capital Management**: AU boards frequently return capital via buybacks and special dividends — assess likelihood and quantum.

{four_box}

OUTPUT:
Return a JSON object with a "sector_outputs" array. Each entry must include:
{{
  "sector_outputs": [
    {{
      "ticker": "BHP.AX",
      "company_name": "BHP Group Limited",
      "analyst_role": "asx_sector_analyst",
      "au_sector": "materials | financials | energy | healthcare | industrials | reit | technology | consumer | utilities",
      "asx_index_membership": "ASX 200 | ASX 300 | ASX All Ords | Other",
      "date": "YYYY-MM-DD",
      "box1_verified_facts": "Recent reporting data, ASX announcements, earnings results...",
      "box2_management_guidance": "FY guidance, operational targets, capital allocation priorities...",
      "box3_consensus_market_view": "Bloomberg consensus, broker target price range, AU analyst views...",
      "box4_analyst_judgment": "Independent thesis, key inflection points, risk-adjusted view...",
      "au_specific": {{
        "franking_status": "fully_franked | partially_franked | unfranked",
        "grossed_up_yield_pct": null,
        "rba_rate_sensitivity": "HIGH_POSITIVE | MODERATE_POSITIVE | NEUTRAL | MODERATE_NEGATIVE | HIGH_NEGATIVE",
        "rba_sensitivity_rationale": "Brief explanation of RBA rate path impact",
        "aud_usd_sensitivity": "POSITIVE_AUD | NEUTRAL | NEGATIVE_AUD",
        "aud_sensitivity_rationale": "How AUD moves affect earnings/valuation",
        "super_fund_relevance": "CORE_HOLDING | ACTIVE_WEIGHT | NON-BENCHMARK | EXCLUSION_RISK",
        "commodity_exposure": ["iron_ore", "lng", "coal", "copper", "gold", "none"],
        "capital_management_outlook": "Potential for buyback / special dividend / base dividend growth"
      }},
      "key_risks": ["risk1 specific to AU context", "risk2"],
      "claims_for_librarian": []
    }}
  ]
}}

RULES:
- Always include "au_specific" block — this is mandatory for ASX analysis
- Use ASX ticker format where known (e.g., BHP.AX, CBA.AX, CSL.AX, WDS.AX)
- Reference RBA meetings explicitly when discussing rate sensitivity
- Never fabricate ASX announcement data — note as "management disclosure pending" if unknown
- Distinguish AU-listed vs dual-listed companies (e.g., BHP trades on both ASX and LSE)"""

    def format_input(self, inputs: dict[str, Any]) -> str:
        """Build the formatted input string for ASX sector analysis."""
        import json

        tickers = inputs.get("tickers", [])
        market_data = inputs.get("market_data", [])
        macro_context = inputs.get("macro_context_summary", "")
        economy_analysis = inputs.get("economy_analysis", {})
        au_sectors = inputs.get("au_sectors", {})  # Optional: pre-assigned sector map

        parts = [
            f"ASX TICKERS TO ANALYSE: {', '.join(tickers)}",
            "",
            "Apply full AU-specific four-box analysis with required 'au_specific' block per ticker.",
        ]

        # Macro context: standard and economy analyst
        if macro_context:
            parts += ["", f"MACRO CONTEXT: {macro_context}"]

        if economy_analysis:
            rba = economy_analysis.get("rba_cash_rate_thesis", "")
            aud = economy_analysis.get("aud_usd_outlook", "")
            rba_stance = economy_analysis.get("rba_stance", "")
            if rba:
                parts += ["", f"RBA THESIS: {rba}"]
            if rba_stance:
                parts += [f"RBA STANCE: {rba_stance}"]
            if aud:
                parts += [f"AUD/USD OUTLOOK: {aud}"]
            au_risks = economy_analysis.get("key_risks_au", [])
            if au_risks:
                parts += ["", "KEY AU MACRO RISKS:"]
                for r in au_risks[:3]:
                    parts.append(f"  - {r}")

        if au_sectors:
            parts += ["", "PRE-ASSIGNED AU SECTORS:"]
            for t, sec in au_sectors.items():
                if t in tickers:
                    parts.append(f"  {t}: {sec}")

        if market_data:
            parts += ["", "MARKET DATA SNAPSHOT:"]
            for md in market_data[:15]:
                if isinstance(md, dict) and md.get("ticker") in tickers:
                    price = md.get("price") or (md.get("market_data") or {}).get("price", "N/A")
                    cap = md.get("market_cap") or (md.get("market_data") or {}).get("market_cap", "N/A")
                    parts.append(f"  {md.get('ticker','?')}: price={price} market_cap={cap}")

        return "\n".join(parts)


# ── ASX ticker routing constants ─────────────────────────────────────────────

# Well-known ASX tickers that should be routed to SectorAnalystASX
ASX_TICKER_SUFFIXES = (".AX", ".ASX")

# Explicit AU universe — can be extended via MarketConfig
DEFAULT_ASX_UNIVERSE: list[str] = [
    # Big-4 banks
    "CBA.AX", "WBC.AX", "NAB.AX", "ANZ.AX",
    # Resources / materials
    "BHP.AX", "RIO.AX", "FMG.AX", "S32.AX", "MIN.AX",
    # Energy
    "WDS.AX", "STO.AX", "ORG.AX", "AGL.AX",
    # Healthcare
    "CSL.AX", "RHC.AX",
    # Industrials / infrastructure
    "BXB.AX", "TCL.AX", "ALX.AX",
    # Technology / data centres
    "WTC.AX", "NXT.AX", "XRO.AX",
    # Consumer
    "WOW.AX", "COL.AX", "JBH.AX",
    # Insurance / diversified financials
    "IAG.AX", "SUN.AX", "MQG.AX",
    # REITs
    "DXS.AX", "GMG.AX", "CHC.AX",
]


def is_asx_ticker(ticker: str) -> bool:
    """Return True if the ticker looks like an ASX-listed stock."""
    upper = ticker.upper()
    return any(upper.endswith(sfx.upper()) for sfx in ASX_TICKER_SUFFIXES)
