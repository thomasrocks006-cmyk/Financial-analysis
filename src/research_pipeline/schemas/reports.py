"""Report and output schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


class StockCard(BaseModel):
    """A complete stock card for the final report."""
    ticker: str
    company_name: str
    subtheme: str
    four_box_summary: str = ""
    valuation_summary: str = ""
    entry_quality: str = ""
    thesis_integrity: str = ""
    key_risks: list[str] = []
    red_team_summary: str = ""
    weight_in_balanced: Optional[float] = None


class ReportSection(BaseModel):
    """A section of the final assembled report."""
    section_name: str
    content: str = ""
    approved: bool = False
    source_stage: Optional[int] = None


class FinalReport(BaseModel):
    """The assembled final report package."""
    run_id: str
    title: str = "AI Infrastructure Investment Research"
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sections: list[ReportSection] = []
    stock_cards: list[StockCard] = []
    publication_status: str = "draft"

    def get_section(self, name: str) -> Optional[ReportSection]:
        for s in self.sections:
            if s.section_name == name:
                return s
        return None


class DiffSummary(BaseModel):
    """Monitoring diff between two snapshots."""
    ticker: str
    field: str
    previous_value: Optional[float] = None
    current_value: Optional[float] = None
    change_pct: Optional[float] = None
    flagged: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ScenarioResult(BaseModel):
    """Result of a stress scenario for one name."""
    ticker: str
    scenario_name: str
    impact_description: str = ""
    estimated_impact_pct: Optional[float] = None
    severity: str = "moderate"  # "low", "moderate", "high", "severe"


class RiskPacket(BaseModel):
    """Quantitative risk output for the portfolio.

    Action 6 — VaR and drawdown fields added so the full quantitative
    picture is surfaced in one packet rather than across separate objects.

    ``var_analysis`` and ``drawdown_analysis`` are stored as plain dicts
    (model_dump() of VaRResult / DrawdownAnalysis) so this schema has no
    cross-package import dependency.
    """
    run_id: str
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_matrix: dict[str, dict[str, float]] = {}
    concentration_report: dict[str, float] = {}
    etf_overlap: dict[str, list[str]] = {}
    volatility_contributions: dict[str, float] = {}
    scenario_results: list[ScenarioResult] = []
    drawdown_risk_summary: str = ""
    # Action 6 — VaR / drawdown from VaREngine embedded at build time
    var_analysis: Optional[dict[str, Any]] = None     # VaRResult.model_dump()
    drawdown_analysis: Optional[dict[str, Any]] = None  # DrawdownAnalysis.model_dump()
    var_method: str = ""                              # "parametric" | "historical"
    confidence_level: Optional[float] = None          # e.g. 0.95
    # Convenience read-only properties
    @property
    def var_pct(self) -> Optional[float]:
        return (self.var_analysis or {}).get("var_pct")

    @property
    def cvar_pct(self) -> Optional[float]:
        return (self.var_analysis or {}).get("cvar_pct")

    @property
    def max_drawdown_pct(self) -> Optional[float]:
        return (self.drawdown_analysis or {}).get("max_drawdown_pct")


# ── StockCard Adapter (ISS-4) ──────────────────────────────────────────────

def build_stock_card_from_pipeline_outputs(
    ticker: str,
    valuation_card: Any,  # ValuationCard from Stage 7
    four_box: Any | None = None,  # FourBoxOutput from Stage 6
    red_team: Any | None = None,  # RedTeamAssessment from Stage 10
    weight_in_balanced: float | None = None,
) -> StockCard:
    """Adapter to build StockCard for final report from pipeline stage outputs.
    
    Required by: ARC-2 (real stock cards in Stage 13), ISS-4 (typed adapter).
    
    Args:
        ticker: Stock ticker symbol
        valuation_card: ValuationCard from Stage 7 (valuation agent)
        four_box: FourBoxOutput from Stage 6 (sector analyst)
        red_team: RedTeamAssessment from Stage 10 (red team agent)
        weight_in_balanced: Recommended weight from Stage 12 (PM agent)
    
    Returns:
        Fully populated StockCard for inclusion in FinalReport.
    """
    # Extract company name from four_box if available, otherwise use ticker
    company_name = ticker
    if four_box and hasattr(four_box, "company_name"):
        company_name = four_box.company_name
    
    # Extract subtheme from four_box analyst role
    subtheme = "AI Infrastructure"
    if four_box and hasattr(four_box, "analyst_role"):
        role_map = {
            "compute": "AI Compute & Chips",
            "power_energy": "Power & Energy",
            "infrastructure": "Cloud & Data Center"
        }
        subtheme = role_map.get(four_box.analyst_role, "AI Infrastructure")
    
    # Build four-box summary
    four_box_summary = ""
    if four_box:
        four_box_summary = f"Judgment: {getattr(four_box, 'box4_analyst_judgment', '')[:200]}"
    
    # Build valuation summary
    valuation_summary = ""
    if valuation_card:
        snapshot = getattr(valuation_card, "snapshot", None)
        if snapshot:
            implied_price = getattr(snapshot, "implied_price_per_share", None)
            current = getattr(snapshot, "current_price", None)
            upside = getattr(snapshot, "upside_pct", None)
            if implied_price and current:
                valuation_summary = f"Current: ${current:.2f}, Implied: ${implied_price:.2f}"
                if upside is not None:
                    valuation_summary += f" (upside: {upside:+.1f}%)"
        
        # Add entry quality
        entry_qual = getattr(valuation_card, "entry_quality", "acceptable")
        if entry_qual:
            valuation_summary += f" | Entry: {entry_qual}"
    
    # Entry quality string
    entry_quality = str(getattr(valuation_card, "entry_quality", "acceptable")) if valuation_card else "unknown"
    
    # Thesis integrity (placeholder until we have a real source)
    thesis_integrity = "Under review"
    
    # Collect key risks from both four-box and valuation
    key_risks = []
    if four_box and hasattr(four_box, "key_risks"):
        key_risks.extend(four_box.key_risks[:3])
    if valuation_card and hasattr(valuation_card, "scenarios"):
        for scenario in getattr(valuation_card, "scenarios", [])[:2]:
            if hasattr(scenario, "name"):
                key_risks.append(scenario.name)
    
    # Red team summary
    red_team_summary = ""
    if red_team:
        if hasattr(red_team, "summary_verdict"):
            red_team_summary = red_team.summary_verdict[:200]
        elif hasattr(red_team, "stress_test_results"):
            results = red_team.stress_test_results
            if results:
                red_team_summary = f"{len(results)} stress tests performed"
    
    return StockCard(
        ticker=ticker,
        company_name=company_name,
        subtheme=subtheme,
        four_box_summary=four_box_summary,
        valuation_summary=valuation_summary,
        entry_quality=entry_quality,
        thesis_integrity=thesis_integrity,
        key_risks=key_risks[:5],  # Max 5 risks per card
        red_team_summary=red_team_summary,
        weight_in_balanced=weight_in_balanced,
    )
