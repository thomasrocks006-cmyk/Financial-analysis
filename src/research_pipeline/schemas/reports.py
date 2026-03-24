"""Report and output schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

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
    date: datetime = Field(default_factory=datetime.utcnow)
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
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ScenarioResult(BaseModel):
    """Result of a stress scenario for one name."""
    ticker: str
    scenario_name: str
    impact_description: str = ""
    estimated_impact_pct: Optional[float] = None
    severity: str = "moderate"  # "low", "moderate", "high", "severe"


class RiskPacket(BaseModel):
    """Quantitative risk output for the portfolio."""
    run_id: str
    date: datetime = Field(default_factory=datetime.utcnow)
    correlation_matrix: dict[str, dict[str, float]] = {}
    concentration_report: dict[str, float] = {}
    etf_overlap: dict[str, list[str]] = {}
    volatility_contributions: dict[str, float] = {}
    scenario_results: list[ScenarioResult] = []
    drawdown_risk_summary: str = ""
