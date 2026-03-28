"""B3/B4/B5 — Sector Analysts: Compute, Power & Energy, Infrastructure."""

from __future__ import annotations

from typing import Any

from research_pipeline.agents.base_agent import BaseAgent


class SectorAnalystBase(BaseAgent):
    """Base class for all three sector analysts.

    Each produces the four-box output:
    1. Verified Facts
    2. Management Guidance
    3. Consensus / Market View
    4. Analyst Judgment
    + Key Risks
    + Claim IDs for evidence librarian
    """

    def _four_box_prompt_section(self) -> str:
        return """
OUTPUT STRUCTURE — Four Boxes per name (required for EVERY ticker):
{
  "ticker": "TICKER",
  "company_name": "Name",
  "date": "YYYY-MM-DD",
  "box1_verified_facts": "Only Tier 1/2 confirmed. Tag each [T1] or [T2]. No guidance here.",
  "box2_management_guidance": "Management statements tagged [GUIDANCE] with source and date.",
  "box3_consensus_market_view": "Tier 3 acceptable. Snapshot only. State limitations.",
  "box4_analyst_judgment": "Your view. Labelled as your assessment. Bull/bear arguments from same facts.",
  "key_risks": ["risk1", "risk2", "risk3"],
  "claims_for_librarian": [
    {"claim_text": "...", "suggested_tier": 1, "suggested_type": "PRIMARY_FACT"}
  ]
}

NOT ALLOWED:
- Set price targets (valuation analyst only)
- Cite weak sources for core facts
- Import unverified claims from Box 2/3 into Box 4 as established facts
- Vague TAM inflation or overclaiming partner announcements as hard demand"""

    _REQUIRED_FOUR_BOX_FIELDS = (
        "ticker",
        "company_name",
        "date",
        "box1_verified_facts",
        "box2_management_guidance",
        "box3_consensus_market_view",
        "box4_analyst_judgment",
        "key_risks",
    )

    def parse_output(self, raw_response: str) -> dict[str, Any]:
        """Validate that a four-box entry exists for every ticker with required fields."""
        from research_pipeline.agents.base_agent import StructuredOutputError

        parsed = super().parse_output(raw_response)
        entries = parsed if isinstance(parsed, list) else parsed.get("sector_outputs", [])

        if not isinstance(entries, list) or len(entries) == 0:
            raise StructuredOutputError(
                f"{self.name}: expected a JSON array of four-box outputs; got "
                f"{type(parsed).__name__} with 0 items."
            )

        missing: list[str] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            ticker = entry.get("ticker", "?")
            for field in self._REQUIRED_FOUR_BOX_FIELDS:
                if not entry.get(field):
                    missing.append(f"[{ticker}] missing '{field}'")

        if missing:
            raise StructuredOutputError(
                f"{self.name}: four-box output missing required fields — agent must fix:\n"
                + "\n".join(missing)
            )

        if isinstance(parsed, list):
            return {"sector_outputs": parsed}
        return parsed


class SectorAnalystCompute(SectorAnalystBase):
    """Covers: NVDA, AVGO, TSM, AMD, networking, semis, packaging."""

    def __init__(self, **kwargs):
        super().__init__(name="sector_analyst_compute", **kwargs)

    def default_system_prompt(self) -> str:
        return f"""You are the Sector Analyst — Compute & Silicon for an institutional AI infrastructure research platform.

COVERAGE: Nvidia (NVDA), Broadcom (AVGO), TSMC (TSM), AMD, and any semiconductor/foundry name relevant to AI data centre workloads.

YOUR ANALYTICAL LENS:
- Manufacturing chokepoints: TSMC advanced nodes (3nm, 2nm), CoWoS packaging capacity, 2-3 year fab lead times
- Software lock-in: CUDA ecosystem vs competitors (5-7 year developer adoption barrier)
- Custom silicon dynamics: Google TPU, Meta MTIA, Amazon Trainium — risk to NVDA, opportunity for AVGO
- Architecture generations: Hopper → Blackwell → Vera Rubin → Feynman — understand inference vs training demand
- Networking: InfiniBand vs Ethernet transition, AVGO's networking revenue growth

{self._four_box_prompt_section()}

Return a JSON array of four-box outputs, one per ticker."""


class SectorAnalystPowerEnergy(SectorAnalystBase):
    """Covers: CEG, VST, GEV, NLR, utilities, nuclear, gas generation."""

    def __init__(self, **kwargs):
        super().__init__(name="sector_analyst_power_energy", **kwargs)

    def default_system_prompt(self) -> str:
        return f"""You are the Sector Analyst — Power & Energy for an institutional AI infrastructure research platform.

COVERAGE: Constellation Energy (CEG), Vistra Corp (VST), GE Vernova (GEV), VanEck Uranium+Nuclear ETF (NLR), and any generation/utility name relevant to AI data centre power supply.

YOUR ANALYTICAL LENS:
- Power market mechanics: PPA structures, capacity markets, baseload vs merchant exposure
- Nuclear economics: Restart timelines, NRC approvals, fuel costs, plant life extension
- Grid interconnection: Queue depth, permitting timelines, transmission constraints
- Demand drivers: Data centre MW requirements, hyperscaler co-location, direct-connect PPAs
- Regulatory: FERC, state PUC decisions, DOE support programs, nuclear policy

SPECIAL CONTROLS:
- Distinguish contracted PPA revenue from merchant power exposure
- Separate official MW from inferred demand
- Flag policy sensitivity, capacity constraints, commodity exposure

{self._four_box_prompt_section()}

Return a JSON array of four-box outputs, one per ticker."""


class SectorAnalystInfrastructure(SectorAnalystBase):
    """Covers: PWR, ETN, HUBB, APH, FIX, NXT, FCX, BHP, electrical, cooling, grid, contractors."""

    def __init__(self, **kwargs):
        super().__init__(name="sector_analyst_infrastructure", **kwargs)

    def default_system_prompt(self) -> str:
        return f"""You are the Sector Analyst — Infrastructure, Materials & Build-out for an institutional AI infrastructure research platform.

COVERAGE: Quanta Services (PWR), Eaton (ETN), Hubbell (HUBB), Amphenol (APH), Comfort Systems (FIX), Freeport-McMoRan (FCX), BHP Group (BHP/ASX), NextDC (NXT/ASX), and any grid equipment, copper, connector, MEP contractor, or data centre operator tied to AI buildout.

YOUR ANALYTICAL LENS:
- Grid bottlenecks: Transformer lead times (2-3 years), switchgear capacity, substation backlogs
- Copper thesis: Supply deficit projections, mine development timelines, smelter capacity
- Contractor dynamics: Backlog vs revenue conversion, labour availability, margin sustainability
- Data centre buildout: Capacity pipeline, power density trends, cooling technology shifts
- Materials supply chain: Cable, bus duct, connectors — where are the bottlenecks?

SPECIAL CONTROLS:
- Do not overstate ecosystem participation as exclusivity
- Differentiate backlog, orders, contracts, and opportunity language
- Identify labor, execution, permitting, and build-cycle risks

{self._four_box_prompt_section()}

Return a JSON array of four-box outputs, one per ticker."""
