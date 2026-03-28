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
    garch_vol_forecast: dict[str, float] = {}
    macro_scenarios: dict[str, Any] = {}
    benchmark_comparison: Optional[dict[str, Any]] = None
    currency_attribution: Optional[dict[str, Any]] = None
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
