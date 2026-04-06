"""Claim and evidence schemas — the provenance backbone of the platform."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EvidenceClass(str, Enum):
    PRIMARY_FACT = "primary_fact"
    MGMT_GUIDANCE = "mgmt_guidance"
    INDEPENDENT_CONFIRMATION = "independent_confirmation"
    CONSENSUS_DATAPOINT = "consensus_datapoint"
    HOUSE_INFERENCE = "house_inference"


class SourceTier(int, Enum):
    TIER_1_PRIMARY = 1
    TIER_2_INDEPENDENT = 2
    TIER_3_CONSENSUS = 3
    TIER_4_HOUSE = 4


class ClaimStatus(str, Enum):
    PASS = "pass"
    CAVEAT = "caveat"
    FAIL = "fail"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Source(BaseModel):
    """A provenance source record."""

    source_id: str
    url: Optional[str] = None
    source_type: str  # e.g. "10-K", "earnings_call", "FMP_API"
    tier: SourceTier
    published_date: Optional[datetime] = None
    accessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notes: str = ""


class Claim(BaseModel):
    """A single evidence-backed claim in the claim ledger."""

    claim_id: str  # e.g. NVDA-001
    run_id: str
    ticker: str
    claim_text: str
    evidence_class: EvidenceClass
    source_id: str
    source_url: Optional[str] = None
    source_date: Optional[datetime] = None
    corroborated: bool = False
    corroboration_source: Optional[str] = None
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    status: ClaimStatus = ClaimStatus.CAVEAT
    caveat_note: str = ""
    owner_agent: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ClaimLedger(BaseModel):
    """Full claim ledger for a pipeline run."""

    run_id: str
    claims: list[Claim] = []
    sources: list[Source] = []

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.claims if c.status == ClaimStatus.FAIL)

    @property
    def caveat_count(self) -> int:
        return sum(1 for c in self.claims if c.status == ClaimStatus.CAVEAT)

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.claims if c.status == ClaimStatus.PASS)

    def get_claims_for_ticker(self, ticker: str) -> list[Claim]:
        return [c for c in self.claims if c.ticker == ticker]

    def has_unresolved_fails(self) -> bool:
        return self.fail_count > 0
