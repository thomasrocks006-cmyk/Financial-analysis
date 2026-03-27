"""Market data, consensus, and reconciliation schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ReconciliationStatus(str, Enum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"
    MISSING = "missing"  # both sources absent — distinct from a real divergence


class MarketSnapshot(BaseModel):
    """Point-in-time market data for a single ticker."""
    ticker: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str  # "fmp" or "finnhub"
    price: Optional[float] = None
    market_cap: Optional[float] = None
    ev: Optional[float] = None
    trailing_pe: Optional[float] = None
    forward_pe: Optional[float] = None
    ev_to_ebitda: Optional[float] = None
    dividend_yield: Optional[float] = None
    revenue_ttm: Optional[float] = None
    net_income_ttm: Optional[float] = None


class ConsensusSnapshot(BaseModel):
    """Analyst consensus data for a single ticker."""
    ticker: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str
    target_low: Optional[float] = None
    target_median: Optional[float] = None
    target_high: Optional[float] = None
    target_mean: Optional[float] = None
    num_analysts: Optional[int] = None
    strong_buy: int = 0
    buy: int = 0
    hold: int = 0
    sell: int = 0
    strong_sell: int = 0


class RatingsSnapshot(BaseModel):
    """Ratings and recommendation trends."""
    ticker: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str
    overall_rating: Optional[str] = None
    rating_score: Optional[float] = None  # 1-5 scale
    buy_pct: Optional[float] = None
    hold_pct: Optional[float] = None
    sell_pct: Optional[float] = None


class EarningsEvent(BaseModel):
    """Upcoming or past earnings event."""
    ticker: str
    date: datetime
    eps_estimate: Optional[float] = None
    eps_actual: Optional[float] = None
    surprise_pct: Optional[float] = None
    revenue_estimate: Optional[float] = None
    revenue_actual: Optional[float] = None
    source: str = ""


class AnalystEstimate(BaseModel):
    """Forward earnings/revenue estimates."""
    ticker: str
    period: str  # "FY2026", "Q1_2026", etc.
    source: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    eps_estimate: Optional[float] = None
    revenue_estimate: Optional[float] = None
    ebitda_estimate: Optional[float] = None
    num_analysts: Optional[int] = None


class ReconciliationField(BaseModel):
    """A single field-level reconciliation result."""
    field_name: str
    ticker: str
    source_a: str
    source_a_value: Optional[float] = None
    source_b: str
    source_b_value: Optional[float] = None
    preferred_source: str = ""
    divergence_pct: Optional[float] = None
    status: ReconciliationStatus = ReconciliationStatus.GREEN
    reviewer_required: bool = False
    notes: str = ""


class ReconciliationReport(BaseModel):
    """Complete reconciliation output for a run."""
    run_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fields: list[ReconciliationField] = []

    @property
    def red_count(self) -> int:
        return sum(1 for f in self.fields if f.status == ReconciliationStatus.RED)

    @property
    def amber_count(self) -> int:
        return sum(1 for f in self.fields if f.status == ReconciliationStatus.AMBER)

    def has_blocking_reds(self) -> bool:
        return self.red_count > 0

    def get_reds(self) -> list[ReconciliationField]:
        return [f for f in self.fields if f.status == ReconciliationStatus.RED]


class DataQualityReport(BaseModel):
    """Data QA & lineage check results."""
    run_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_valid: bool = True
    timestamp_valid: bool = True
    currency_consistent: bool = True
    duplicate_count: int = 0
    outlier_count: int = 0
    lineage_complete: bool = True
    issues: list[str] = []

    def is_passing(self) -> bool:
        return (
            self.schema_valid
            and self.timestamp_valid
            and self.currency_consistent
            and self.duplicate_count == 0
            and self.lineage_complete
        )
