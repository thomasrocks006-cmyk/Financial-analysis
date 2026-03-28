"""A9 — Scheduler / Monitoring Service: recurring diff checks and monitoring."""

from __future__ import annotations

import asyncio
import json
import logging
import traceback
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from research_pipeline.schemas.market_data import MarketSnapshot
from research_pipeline.schemas.reports import DiffSummary

logger = logging.getLogger(__name__)

# ── Types ─────────────────────────────────────────────────────────────────────

AlertFn = Callable[[str, Exception], Awaitable[None]]  # (run_id, exc) -> None
PipelineFn = Callable[[str], Awaitable[Any]]            # (run_id) -> result



class SchedulerMonitoringService:
    """Deterministic monitoring and diff engine — no LLM.

    Cadence:
    - Daily:  data refresh + diff detection
    - Weekly: watchlist refresh + crowding re-score
    - Report-day: full revalidation

    Phase 7.10 hardening adds:
    - run_with_alert: wraps any async pipeline callable and fires an alert on failure
    - schedule_state: persist daily completion flag to disk to avoid double-runs
    - watchlist_check: flag tickers with moves ≥ watchlist_trigger_pct for priority re-run
    """

    _DEFAULT_STATE_PATH = Path("output/schedule_state.json")

    def __init__(
        self,
        alert_threshold_pct: float = 5.0,
        watchlist_trigger_pct: float = 5.0,
        state_path: Path | None = None,
    ):
        self.alert_threshold_pct = alert_threshold_pct
        self.watchlist_trigger_pct = watchlist_trigger_pct
        self._state_path = state_path or self._DEFAULT_STATE_PATH
        self._state: dict[str, Any] = self._load_state()

    # ── State Persistence ────────────────────────────────────────────────────

    def _load_state(self) -> dict[str, Any]:
        if self._state_path.exists():
            try:
                return json.loads(self._state_path.read_text())
            except Exception:
                return {}
        return {}

    def _save_state(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(self._state, indent=2, default=str))

    def mark_run_completed(self, run_id: str) -> None:
        """Record that a run completed successfully today."""
        today = date.today().isoformat()
        self._state.setdefault("completed_runs", {})[today] = run_id
        self._state["last_successful_run_id"] = run_id
        self._state["last_successful_at"] = datetime.now(timezone.utc).isoformat()
        self._save_state()

    def already_ran_today(self) -> bool:
        """Return True if a successful run was already recorded for today."""
        today = date.today().isoformat()
        return today in self._state.get("completed_runs", {})

    def get_last_run_id(self) -> str | None:
        """Return the run_id of the last successful pipeline run."""
        return self._state.get("last_successful_run_id")

    # ── Alert-on-Failure Wrapper ─────────────────────────────────────────────

    async def run_with_alert(
        self,
        run_fn: PipelineFn,
        run_id: str,
        alert_fn: AlertFn | None = None,
        skip_if_already_ran: bool = True,
    ) -> Any:
        """Run pipeline callable, mark completion, and fire alert on failure.

        Args:
            run_fn: Async callable receiving run_id, returning pipeline result.
            run_id: Unique run identifier (used for dedup and alerting).
            alert_fn: Optional async callable(run_id, exc) invoked on failure.
                      Defaults to logging the error.
            skip_if_already_ran: If True and already_ran_today() is True,
                                  skip execution and return None.

        Returns:
            Pipeline result on success, or None if skipped.

        Raises:
            Exception: re-raises any exception AFTER calling alert_fn.
        """
        if skip_if_already_ran and self.already_ran_today():
            logger.info(
                "Scheduler: skipping run %s — already completed today (%s)",
                run_id, date.today().isoformat(),
            )
            return None

        logger.info("Scheduler: starting run %s", run_id)
        try:
            result = await run_fn(run_id)
            self.mark_run_completed(run_id)
            logger.info("Scheduler: run %s completed successfully", run_id)
            return result

        except Exception as exc:
            tb = traceback.format_exc()
            logger.error(
                "Scheduler: run %s FAILED — %s\n%s", run_id, exc, tb
            )
            # Persist the failure for diagnostics
            self._state.setdefault("failed_runs", []).append({
                "run_id": run_id,
                "failed_at": datetime.now(timezone.utc).isoformat(),
                "error": str(exc),
            })
            self._save_state()

            # Fire alert callback
            if alert_fn is not None:
                try:
                    await alert_fn(run_id, exc)
                except Exception as alert_exc:
                    logger.error("Scheduler: alert_fn itself failed: %s", alert_exc)
            raise

    # ── Watchlist Monitoring ─────────────────────────────────────────────────

    def check_watchlist_triggers(
        self,
        diffs: list[DiffSummary],
        watchlist: list[str],
        trigger_pct: float | None = None,
    ) -> list[str]:
        """Return tickers on the watchlist that moved beyond the trigger threshold.

        These tickers should be queued for an immediate re-analysis run.
        """
        threshold = trigger_pct if trigger_pct is not None else self.watchlist_trigger_pct
        watching = set(watchlist)
        triggered: list[str] = []

        for diff in diffs:
            if diff.ticker not in watching:
                continue
            if diff.field != "price":
                continue
            if diff.change_pct is not None and abs(diff.change_pct) >= threshold:
                triggered.append(diff.ticker)
                logger.warning(
                    "WATCHLIST TRIGGER: %s price moved %+.1f%% (threshold ±%.1f%%)",
                    diff.ticker, diff.change_pct, threshold,
                )

        return sorted(set(triggered))

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
                    # Flag a transition FROM zero (e.g. halted stock resuming)
                    flagged = new_val != 0
                    if flagged:
                        # Always record this — zero-origin means infinite % change
                        diffs.append(DiffSummary(
                            ticker=curr.ticker,
                            field=field_name,
                            previous_value=old_val,
                            current_value=new_val,
                            change_pct=None,
                            flagged=True,
                        ))
                else:
                    change_pct = round((new_val - old_val) / abs(old_val) * 100, 2)
                    flagged = abs(change_pct) >= self.alert_threshold_pct

                    if abs(change_pct) > 0.01:
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
                pct_str = f"{d.change_pct:+.1f}%" if d.change_pct is not None else "↑ from zero"
                alerts.append(
                    f"ALERT: {d.ticker} {d.field} changed {pct_str} "
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
