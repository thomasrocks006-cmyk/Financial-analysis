"""Governance, compliance, and investment committee schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Investment Committee ────────────────────────────────────────────────────

class CommitteeVote(str, Enum):
    APPROVE = "approve"
    APPROVE_WITH_CONDITIONS = "approve_with_conditions"
    REJECT = "reject"
    ABSTAIN = "abstain"


class CommitteeMember(BaseModel):
    """A voting member of the investment committee."""
    member_id: str
    role: str  # "chair", "pm", "risk_officer", "analyst", "compliance"
    name: str = ""


class CommitteeVoteRecord(BaseModel):
    """A single vote in a committee decision."""
    member: CommitteeMember
    vote: CommitteeVote
    rationale: str = ""
    conditions: list[str] = []
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CommitteeRecord(BaseModel):
    """Full record of an investment committee decision."""
    record_id: str
    run_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    agenda_items: list[str] = []
    votes: list[CommitteeVoteRecord] = []
    outcome: CommitteeVote = CommitteeVote.REJECT
    conditions: list[str] = []
    minutes: str = ""
    quorum_met: bool = False
    required_votes: int = 3

    @property
    def approve_count(self) -> int:
        return sum(1 for v in self.votes if v.vote in (CommitteeVote.APPROVE, CommitteeVote.APPROVE_WITH_CONDITIONS))

    @property
    def reject_count(self) -> int:
        return sum(1 for v in self.votes if v.vote == CommitteeVote.REJECT)

    @property
    def is_approved(self) -> bool:
        return self.quorum_met and self.outcome in (CommitteeVote.APPROVE, CommitteeVote.APPROVE_WITH_CONDITIONS)


# ── Mandate Compliance ──────────────────────────────────────────────────────

class MandateRule(BaseModel):
    """A single investment mandate constraint."""
    rule_id: str
    rule_type: str  # "max_weight", "sector_cap", "liquidity_floor", "esg_exclusion"
    description: str = ""
    parameter: str = ""  # e.g. ticker, sector name
    threshold: float = 0.0
    hard_limit: bool = True  # hard limits block; soft limits warn


class MandateConfig(BaseModel):
    """Full mandate configuration for a portfolio."""
    mandate_id: str
    name: str = "Default Mandate"
    rules: list[MandateRule] = []
    max_single_name_pct: float = 15.0
    max_sector_pct: float = 40.0
    min_positions: int = 8
    max_positions: int = 25
    min_liquidity_adv_days: float = 5.0  # minimum 5 days ADV to liquidate


class MandateViolation(BaseModel):
    """A violation of a mandate constraint."""
    rule: MandateRule
    actual_value: float
    breach_severity: str = "hard"  # "hard" or "soft"
    description: str = ""


class MandateCheckResult(BaseModel):
    """Result of checking a portfolio against its mandate."""
    run_id: str
    mandate_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    violations: list[MandateViolation] = []
    is_compliant: bool = True
    warnings: list[str] = []


# ── ESG ─────────────────────────────────────────────────────────────────────

class ESGRating(str, Enum):
    AAA = "AAA"
    AA = "AA"
    A = "A"
    BBB = "BBB"
    BB = "BB"
    B = "B"
    CCC = "CCC"


class ESGScore(BaseModel):
    """ESG score for a single ticker."""
    ticker: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    overall_rating: ESGRating = ESGRating.BBB
    environmental_score: float = 5.0  # 0-10
    social_score: float = 5.0
    governance_score: float = 5.0
    carbon_intensity_tco2e_per_m_revenue: float = 0.0
    tcfd_alignment_flag: bool = False
    apra_cps230_alignment_flag: bool = False
    controversy_flag: bool = False
    excluded: bool = False
    exclusion_reason: str = ""
    source: str = "public_estimates"


class ESGConfig(BaseModel):
    """ESG mandate configuration."""
    exclude_below_rating: ESGRating = ESGRating.CCC
    exclude_controversial: bool = True
    min_esg_score: float = 3.0
    exclusion_list: list[str] = []  # tickers explicitly excluded


# ── Audit Trail ─────────────────────────────────────────────────────────────

class AuditEntry(BaseModel):
    """A single audit trail entry."""
    entry_id: str
    run_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    action: str  # "gate_check", "override", "committee_vote", "publication"
    stage: Optional[int] = None
    actor: str = "system"
    details: dict[str, Any] = {}
    outcome: str = ""


class AuditTrail(BaseModel):
    """Complete audit trail for a run."""
    run_id: str
    entries: list[AuditEntry] = []

    def add_entry(self, action: str, stage: int | None = None, actor: str = "system",
                  details: dict[str, Any] | None = None, outcome: str = "") -> None:
        entry_id = f"AUD-{self.run_id}-{len(self.entries)+1:04d}"
        self.entries.append(AuditEntry(
            entry_id=entry_id, run_id=self.run_id, action=action,
            stage=stage, actor=actor, details=details or {}, outcome=outcome,
        ))


# ── Research trend monitoring ───────────────────────────────────────────────

class ResearchTrend(BaseModel):
    """Cross-run change alert for a tracked research metric."""

    ticker: str
    metric: str
    current_value: float
    prior_value: float
    delta_pct: float
    alert_level: str = "info"  # "info" | "warning" | "critical"
    run_id: str = ""


# ── Self-Audit Packet ────────────────────────────────────────────────────────

class SelfAuditPacket(BaseModel):
    """Per-run structured self-audit attached to every published output.

    Built at Stage 13 and included in the final report as the mandatory
    'Audit Appendix'. Enables external verification of evidence quality
    without re-running the full pipeline.
    """
    run_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Evidence quality metrics
    total_claims: int = 0
    tier1_claims: int = 0
    tier2_claims: int = 0
    tier3_claims: int = 0
    tier4_claims: int = 0
    pass_claims: int = 0
    caveat_claims: int = 0
    fail_claims: int = 0

    # Methodology compliance
    methodology_tags_present: bool = False
    dates_complete: bool = False
    source_hygiene_score: float = 0.0  # 0-10

    # Agent outcomes
    agents_succeeded: list[str] = []
    agents_failed: list[str] = []
    total_retries: int = 0
    llm_provider_used: str = ""
    agent_retry_telemetry: list[dict[str, Any]] = Field(default_factory=list)

    # Gate outcomes
    gates_passed: list[int] = []
    gates_failed: list[int] = []

    # Red team coverage
    tickers_with_red_team: list[str] = []
    min_falsification_tests: int = 0  # minimum across all tickers

    # IC outcome
    ic_approved: Optional[bool] = None
    ic_vote_breakdown: dict[str, str] = {}  # member → vote

    # Mandate & ESG
    mandate_compliant: Optional[bool] = None
    esg_exclusions: list[str] = []

    # Operational metrics (ACT-S7-3)
    stage_latencies_ms: dict[str, float] = Field(default_factory=dict)  # "stage_0" -> ms
    total_pipeline_duration_s: float = 0.0

    # Prompt versioning (ACT-S8-4)
    prompt_drift_reports: list[dict] = Field(default_factory=list)  # PromptDriftReport dicts

    # Rebalancing snapshot (ACT-S9-3)
    rebalancing_summary: dict = Field(default_factory=dict)  # turnover, trade count, impact

    # Cross-run change detection
    research_trends: list[ResearchTrend] = Field(default_factory=list)

    # Summary verdict
    publication_quality_score: float = 0.0  # 0-10 derived metric
    blockers: list[str] = []

    @property
    def tier1_2_pct(self) -> float:
        """Percentage of claims with Tier 1 or 2 sources."""
        if self.total_claims == 0:
            return 0.0
        return round((self.tier1_claims + self.tier2_claims) / self.total_claims * 100, 1)

    def compute_quality_score(self) -> float:
        """Derive publication quality score 0-10 from gathered metrics."""
        score = 10.0
        if self.fail_claims > 0:
            score -= min(4.0, self.fail_claims * 0.5)
        if self.caveat_claims > 0:
            score -= min(2.0, self.caveat_claims * 0.2)
        if not self.methodology_tags_present:
            score -= 2.0
        if not self.dates_complete:
            score -= 0.5
        if self.min_falsification_tests < 3:
            score -= 1.0
        if self.agents_failed:
            score -= min(2.0, len(self.agents_failed) * 0.5)
        self.publication_quality_score = max(0.0, round(score, 1))
        return self.publication_quality_score
