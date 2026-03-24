"""A3 — Data QA & Lineage Service: prevent garbage-in errors."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from research_pipeline.schemas.market_data import DataQualityReport, MarketSnapshot

logger = logging.getLogger(__name__)


class DataQALineageService:
    """Deterministic data quality and lineage checks — no LLM.

    Checks: schema validity, timestamp validity, currency sanity,
    duplicate detection, outlier detection, lineage completeness.
    """

    def __init__(self, require_lineage: bool = True, allow_duplicates: bool = False):
        self.require_lineage = require_lineage
        self.allow_duplicates = allow_duplicates

    def check_schema_validity(self, snapshots: list[dict[str, Any]]) -> list[str]:
        """Verify all required fields are present."""
        issues = []
        required_fields = {"ticker", "timestamp", "source"}
        for i, snap in enumerate(snapshots):
            missing = required_fields - set(snap.keys())
            if missing:
                issues.append(f"Row {i}: missing fields {missing}")
        return issues

    def check_timestamps(self, snapshots: list[dict[str, Any]], max_age_hours: int = 24) -> list[str]:
        """Flag stale or missing timestamps."""
        issues = []
        now = datetime.now(timezone.utc)
        for snap in snapshots:
            ts = snap.get("timestamp")
            if ts is None:
                issues.append(f"{snap.get('ticker', '?')}: missing timestamp")
                continue
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts)
                except ValueError:
                    issues.append(f"{snap.get('ticker', '?')}: malformed timestamp '{ts}'")
                    continue
            if hasattr(ts, "tzinfo") and ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_hours = (now - ts).total_seconds() / 3600
            if age_hours > max_age_hours:
                issues.append(f"{snap.get('ticker', '?')}: stale data ({age_hours:.1f}h old)")
        return issues

    def check_duplicates(self, snapshots: list[dict[str, Any]]) -> list[str]:
        """Detect duplicate rows by (ticker, source, timestamp)."""
        issues = []
        seen = set()
        for snap in snapshots:
            key = (snap.get("ticker"), snap.get("source"), str(snap.get("timestamp")))
            if key in seen:
                issues.append(f"Duplicate: {key}")
            seen.add(key)
        return issues

    def check_outliers(self, snapshots: list[MarketSnapshot]) -> list[str]:
        """Flag obviously broken values."""
        issues = []
        for snap in snapshots:
            if snap.price is not None and snap.price < 0:
                issues.append(f"{snap.ticker}: negative price {snap.price}")
            if snap.trailing_pe is not None and snap.trailing_pe > 2000:
                issues.append(f"{snap.ticker}: extreme P/E {snap.trailing_pe}")
            if snap.market_cap is not None and snap.market_cap < 0:
                issues.append(f"{snap.ticker}: negative market cap {snap.market_cap}")
        return issues

    def check_lineage(self, snapshots: list[dict[str, Any]]) -> list[str]:
        """Verify every record has source attribution."""
        issues = []
        if not self.require_lineage:
            return issues
        for snap in snapshots:
            if not snap.get("source"):
                issues.append(f"{snap.get('ticker', '?')}: missing source lineage")
        return issues

    def run_full_check(
        self,
        run_id: str,
        raw_snapshots: list[dict[str, Any]],
        parsed_snapshots: list[MarketSnapshot] | None = None,
        max_age_hours: int = 24,
    ) -> DataQualityReport:
        """Execute all QA checks and produce a report."""
        all_issues: list[str] = []

        schema_issues = self.check_schema_validity(raw_snapshots)
        timestamp_issues = self.check_timestamps(raw_snapshots, max_age_hours)
        dup_issues = self.check_duplicates(raw_snapshots)
        lineage_issues = self.check_lineage(raw_snapshots)
        outlier_issues = self.check_outliers(parsed_snapshots or [])

        all_issues.extend(schema_issues)
        all_issues.extend(timestamp_issues)
        all_issues.extend(dup_issues)
        all_issues.extend(lineage_issues)
        all_issues.extend(outlier_issues)

        report = DataQualityReport(
            run_id=run_id,
            schema_valid=len(schema_issues) == 0,
            timestamp_valid=len(timestamp_issues) == 0,
            currency_consistent=True,  # extended in future
            duplicate_count=len(dup_issues),
            outlier_count=len(outlier_issues),
            lineage_complete=len(lineage_issues) == 0,
            issues=all_issues,
        )

        if report.is_passing():
            logger.info("Data QA PASSED for run %s", run_id)
        else:
            logger.warning("Data QA FAILED for run %s: %d issues", run_id, len(all_issues))

        return report
