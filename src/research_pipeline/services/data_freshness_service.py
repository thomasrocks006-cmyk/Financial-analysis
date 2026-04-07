from enum import Enum
from datetime import datetime, timezone
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


class FreshnessTier(str, Enum):
    LIVE = "live"          # < 15 minutes
    INTRADAY = "intraday"  # < 4 hours
    DAILY = "daily"        # < 24 hours
    RECENT = "recent"      # < 7 days
    STALE = "stale"        # 7–30 days
    EXPIRED = "expired"    # > 30 days


class FieldFreshness(BaseModel):
    field_key: str
    ticker: str
    source_service: str
    fetch_time: datetime
    value_period: str = ""
    freshness_tier: FreshnessTier = FreshnessTier.RECENT
    staleness_minutes: int = 0


class DataFreshnessCatalog(BaseModel):
    run_id: str
    fields: dict[str, FieldFreshness] = Field(default_factory=dict)
    stale_fields: list[str] = Field(default_factory=list)
    expired_fields: list[str] = Field(default_factory=list)

    def register(
        self,
        field_key: str,
        ticker: str,
        source_service: str,
        fetch_time: datetime | None = None,
        value_period: str = "",
    ) -> FieldFreshness:
        now = fetch_time or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        staleness_minutes = 0  # Always fresh when registered
        tier = FreshnessTier.LIVE if staleness_minutes < 15 else FreshnessTier.INTRADAY
        freshness = FieldFreshness(
            field_key=field_key,
            ticker=ticker,
            source_service=source_service,
            fetch_time=now,
            value_period=value_period,
            freshness_tier=tier,
            staleness_minutes=staleness_minutes,
        )
        self.fields[field_key] = freshness
        return freshness

    def get_stale_summary(self) -> str:
        if not self.stale_fields and not self.expired_fields:
            return "All fields fresh."
        parts = []
        if self.expired_fields:
            parts.append(f"EXPIRED: {', '.join(self.expired_fields[:5])}")
        if self.stale_fields:
            parts.append(f"STALE: {', '.join(self.stale_fields[:5])}")
        return "; ".join(parts)

    def to_audit_list(self) -> list[str]:
        return self.stale_fields + self.expired_fields
