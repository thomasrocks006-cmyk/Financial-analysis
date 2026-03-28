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
