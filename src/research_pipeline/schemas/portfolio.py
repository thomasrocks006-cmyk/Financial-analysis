"""Portfolio construction and valuation schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EntryQuality(str, Enum):
    STRONG = "strong"
    ACCEPTABLE = "acceptable"
    STRETCHED = "stretched"
    POOR = "poor"


class ThesisIntegrity(str, Enum):
    ROBUST = "robust"
    MODERATE = "moderate"
    FRAGILE = "fragile"


class PublicationStatus(str, Enum):
    PASS = "pass"
    PASS_WITH_DISCLOSURE = "pass_with_disclosure"
    FAIL = "fail"


# ── Valuation schemas ──────────────────────────────────────────────────────
class ValuationSnapshot(BaseModel):
    """Current valuation metrics for a name."""
    ticker: str
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    price: float
    market_cap: Optional[float] = None
    trailing_pe: Optional[float] = None
    forward_pe: Optional[float] = None
    ev_ebitda: Optional[float] = None
    dividend_yield: Optional[float] = None


class ReturnScenario(BaseModel):
    """A single bull / base / bear scenario."""
    label: str  # "base", "bull", "bear"
    probability_pct: Optional[float] = None
    revenue_cagr_pct: float
    exit_multiple: float
    exit_multiple_rationale: str = ""
    implied_return_1y_pct: Optional[float] = None
    implied_return_3y_pct: Optional[float] = None
    implied_return_5y_pct: Optional[float] = None
    key_driver: str = ""
    methodology_tag: str = "HOUSE VIEW"


class DriverDecomposition(BaseModel):
    """Decompose expected return into drivers."""
    revenue_growth_pct: float = 0.0
    margin_expansion_pct: float = 0.0
    multiple_rerate_pct: float = 0.0
    dividend_return_pct: float = 0.0
    primary_driver: str = ""


class ValuationCard(BaseModel):
    """Complete valuation output for one name."""
    ticker: str
    run_id: str
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    snapshot: ValuationSnapshot
    historical_context: str = ""
    peer_comparison: str = ""
    consensus_target_low: Optional[float] = None
    consensus_target_median: Optional[float] = None
    consensus_target_high: Optional[float] = None
    num_analysts: Optional[int] = None
    scenarios: list[ReturnScenario] = []
    driver_decomposition: Optional[DriverDecomposition] = None
    expectation_pressure_score: Optional[float] = None  # 0-10
    crowding_score: Optional[float] = None  # 0-10
    entry_quality: EntryQuality = EntryQuality.ACCEPTABLE
    methodology_tag: str = "HOUSE VIEW"


# ── Sector analysis schemas ────────────────────────────────────────────────
class FourBoxOutput(BaseModel):
    """Structured four-box sector analyst output per name."""
    ticker: str
    company_name: str
    analyst_role: str  # "compute", "power_energy", "infrastructure"
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_id: str = ""
    box1_verified_facts: str = ""
    box2_management_guidance: str = ""
    box3_consensus_market_view: str = ""
    box4_analyst_judgment: str = ""
    key_risks: list[str] = []
    claim_ids: list[str] = []  # links to claim ledger


# ── Red team schemas ───────────────────────────────────────────────────────
class FalsificationTest(BaseModel):
    """A single falsification test result."""
    test_name: str
    assumption_challenged: str
    outcome_if_wrong: str  # "breaks", "weakens significantly", "survives"
    evidence_trigger: str = ""  # what near-term data would confirm this


class RedTeamAssessment(BaseModel):
    """Red team output for one name or the portfolio."""
    target: str  # ticker or "PORTFOLIO"
    run_id: str
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    what_is_priced_in: str = ""
    falsification_tests: list[FalsificationTest] = []
    thesis_integrity: ThesisIntegrity = ThesisIntegrity.MODERATE
    variant_bear_cases: list[str] = []
    crowding_risk_notes: str = ""
    correlated_risks: list[str] = []


# ── Macro & geopolitical schemas ───────────────────────────────────────────
class MacroRegimeMemo(BaseModel):
    """Macro and regime strategist output."""
    run_id: str
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    regime_classification: str = ""  # e.g. "late-cycle expansion"
    key_macro_variables: dict[str, str] = {}
    regime_winners: list[str] = []
    regime_losers: list[str] = []
    rate_sensitivity_notes: str = ""
    cyclical_sensitivity_notes: str = ""


class PoliticalRiskAssessment(BaseModel):
    """Political and geopolitical risk analyst output."""
    run_id: str
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ticker: str = ""
    policy_dependency_score: Optional[float] = None  # 0-10
    geopolitical_dependency_score: Optional[float] = None  # 0-10
    jurisdiction_map: dict[str, str] = {}
    key_event_triggers: list[str] = []
    export_control_exposure: str = ""
    taiwan_risk_notes: str = ""


# ── Portfolio schemas ──────────────────────────────────────────────────────
class PortfolioPosition(BaseModel):
    """A single position in a portfolio variant."""
    ticker: str
    weight_pct: float
    subtheme: str  # "compute", "power", "infrastructure", "materials", "etf"
    entry_quality: EntryQuality
    thesis_integrity: ThesisIntegrity
    rationale: str = ""
    constraints_binding: list[str] = []


class PortfolioVariant(BaseModel):
    """One of the three required portfolio variants."""
    variant_name: str  # "balanced", "higher_return", "lower_volatility"
    run_id: str
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    positions: list[PortfolioPosition] = []
    total_weight_pct: float = 0.0
    implementation_notes: str = ""

    def validate_constraints(self) -> list[str]:
        """Check portfolio construction constraints. Returns list of violations."""
        violations = []
        for pos in self.positions:
            if pos.weight_pct > 15.0:
                violations.append(f"{pos.ticker}: weight {pos.weight_pct}% exceeds 15% max")
            if pos.thesis_integrity == ThesisIntegrity.FRAGILE:
                violations.append(f"{pos.ticker}: FRAGILE thesis — must be removed")
        # Subtheme concentration
        subtheme_weights: dict[str, float] = {}
        for pos in self.positions:
            subtheme_weights[pos.subtheme] = subtheme_weights.get(pos.subtheme, 0) + pos.weight_pct
        limits = {"compute": 40, "power": 25, "infrastructure": 20, "materials": 15, "etf": 100}
        for theme, weight in subtheme_weights.items():
            limit = limits.get(theme, 100)
            if weight > limit:
                violations.append(f"Subtheme '{theme}': {weight}% exceeds {limit}% limit")
        return violations


# ── Review gate schemas ────────────────────────────────────────────────────
class ReviewIssue(BaseModel):
    """An issue found during associate review."""
    severity: str  # "critical", "major", "minor"
    description: str
    ticker: Optional[str] = None
    stage: Optional[str] = None
    resolution: str = ""


class AssociateReviewResult(BaseModel):
    """Associate reviewer gate output."""
    run_id: str
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: PublicationStatus = PublicationStatus.FAIL
    issues: list[ReviewIssue] = []
    self_audit_score: Optional[float] = None
    unresolved_count: int = 0
    methodology_tags_complete: bool = False
    dates_complete: bool = False
    claim_mapping_complete: bool = False
    notes: str = ""

    @property
    def is_publishable(self) -> bool:
        return self.status in (PublicationStatus.PASS, PublicationStatus.PASS_WITH_DISCLOSURE)
