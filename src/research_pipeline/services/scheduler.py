"""A9 — Scheduler / Monitoring Service: recurring diff checks and monitoring."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from research_pipeline.schemas.market_data import MarketSnapshot
from research_pipeline.schemas.reports import DiffSummary

logger = logging.getLogger(__name__)


class SchedulerMonitoringService:
    """Deterministic monitoring and diff engine — no LLM.

    Cadence:
    - Daily:  data refresh + diff detection
    - Weekly: watchlist refresh + crowding re-score
    - Report-day: full revalidation
    """

    def __init__(self, alert_threshold_pct: float = 5.0):
        self.alert_threshold_pct = alert_threshold_pct

    def compute_diffs(
        self,
        previous: list[MarketSnapshot],
        current: list[MarketSnapshot],
    ) -> list[DiffSummary]:
        """Compare two snapshots and produce diff summaries."""
        prev_map = {s.ticker: s for s in previous}
        diffs: list[DiffSummary] = []

        for curr in current:
            prev = prev_map.get(curr.ticker)
            if prev is None:
                continue

            for field_name in ["price", "trailing_pe", "forward_pe", "market_cap"]:
                old_val = getattr(prev, field_name, None)
                new_val = getattr(curr, field_name, None)
                if old_val is None or new_val is None:
                    continue

                if old_val == 0:
                    change_pct = None
                else:
                    change_pct = round((new_val - old_val) / abs(old_val) * 100, 2)

                flagged = change_pct is not None and abs(change_pct) >= self.alert_threshold_pct

                if change_pct is not None and abs(change_pct) > 0.01:
                    diffs.append(DiffSummary(
                        ticker=curr.ticker,
                        field=field_name,
                        previous_value=old_val,
                        current_value=new_val,
                        change_pct=change_pct,
                        flagged=flagged,
                    ))

        return diffs

    def generate_alert_log(self, diffs: list[DiffSummary]) -> list[str]:
        """Produce human-readable alerts for flagged changes."""
        alerts = []
        for d in diffs:
            if d.flagged:
                alerts.append(
                    f"ALERT: {d.ticker} {d.field} changed {d.change_pct:+.1f}% "
                    f"({d.previous_value} → {d.current_value})"
                )
        return alerts

    def check_revalidation_needed(
        self, diffs: list[DiffSummary], threshold: float = 10.0
    ) -> list[str]:
        """Return tickers that need revalidation due to large moves."""
        tickers = set()
        for d in diffs:
            if d.change_pct is not None and abs(d.change_pct) >= threshold:
                tickers.add(d.ticker)
        return sorted(tickers)
