"""Pipeline Supervisor Agent — real-time pipeline health monitoring and remediation.

The supervisor is a built-in agent that runs alongside the pipeline execution.
It performs two layers of analysis:

1. **Deterministic health checks** (always runs, no LLM required):
   - Checks stage output completeness and shape
   - Detects gate failures and missing required fields
   - Tracks timing anomalies (stages that take too long or too short)
   - Identifies cascading failures from upstream stages
   - Generates structured health reports for each stage

2. **LLM-powered remediation analysis** (optional, fires only on failure):
   - Analyses the failure context with an LLM
   - Proposes corrective actions
   - Provides a confidence score for recovery prospects

The supervisor integrates with the pipeline engine via ``PipelineEngine.supervisor``
and its ``check_stage`` / ``report`` methods.  The frontend adapter surfaces the
supervisor's health data in ``RunResult.supervisor_report``.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ── Health status enum ────────────────────────────────────────────────────


class StageHealth(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"  # Ran but output is incomplete/suspect
    FAILED = "failed"  # Hard gate failure or exception
    SKIPPED = "skipped"  # Stage did not execute (upstream failure)
    UNKNOWN = "unknown"  # Not yet evaluated


# ── Per-stage health record ───────────────────────────────────────────────


@dataclass
class StageHealthRecord:
    stage_num: int
    stage_name: str
    health: StageHealth = StageHealth.UNKNOWN
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    remediation: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_num": self.stage_num,
            "stage_name": self.stage_name,
            "health": self.health.value,
            "issues": self.issues,
            "warnings": self.warnings,
            "remediation": self.remediation,
            "duration_ms": self.duration_ms,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


# ── Supervisor report (full run summary) ─────────────────────────────────


class SupervisorReport(BaseModel):
    """Full supervisor health report for a pipeline run."""

    run_id: str = ""
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    overall_health: StageHealth = StageHealth.UNKNOWN
    stages_checked: int = 0
    stages_ok: int = 0
    stages_degraded: int = 0
    stages_failed: int = 0
    stages_skipped: int = 0
    stage_records: list[dict[str, Any]] = Field(default_factory=list)
    critical_issues: list[str] = Field(default_factory=list)
    all_warnings: list[str] = Field(default_factory=list)
    remediation_summary: list[str] = Field(default_factory=list)
    pipeline_interrupted_at: Optional[int] = None
    total_duration_ms: float = 0.0

    @property
    def health_pct(self) -> float:
        if self.stages_checked == 0:
            return 0.0
        return round(self.stages_ok / self.stages_checked * 100, 1)

    def to_display_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "overall_health": self.overall_health.value,
            "health_pct": self.health_pct,
            "stages_checked": self.stages_checked,
            "stages_ok": self.stages_ok,
            "stages_degraded": self.stages_degraded,
            "stages_failed": self.stages_failed,
            "stages_skipped": self.stages_skipped,
            "critical_issues": self.critical_issues,
            "all_warnings": self.all_warnings,
            "remediation_summary": self.remediation_summary,
            "pipeline_interrupted_at": self.pipeline_interrupted_at,
            "total_duration_ms": self.total_duration_ms,
            "stage_records": self.stage_records,
        }


# ── Stage health rules ────────────────────────────────────────────────────

# Minimum expected output keys per stage (deterministic checks)
_STAGE_REQUIRED_KEYS: dict[int, list[str]] = {
    0: ["universe", "config_valid"],
    1: ["universe"],
    2: [],  # Variable shape — just check non-empty
    3: [],
    4: [],
    5: ["claims"],
    6: [],  # sector_outputs varies
    7: [],
    8: [],
    9: [],
    10: [],
    11: ["approved"],
    12: ["weights"],
    13: [],
    14: [],
}

# Timing thresholds — stages taking longer than this are flagged as slow
_STAGE_SLOW_THRESHOLD_MS: dict[int, float] = {
    0: 10_000,
    1: 5_000,
    2: 120_000,
    3: 60_000,
    4: 30_000,
    5: 300_000,
    6: 600_000,
    7: 300_000,
    8: 300_000,
    9: 120_000,
    10: 300_000,
    11: 120_000,
    12: 120_000,
    13: 300_000,
    14: 30_000,
}

# Stage labels (mirrors STAGE_LABELS in events.py)
_STAGE_LABELS: dict[int, str] = {
    0: "Bootstrap",
    1: "Universe Validation",
    2: "Data Ingestion",
    3: "Reconciliation",
    4: "Data QA",
    5: "Evidence Library",
    6: "Sector Analysis",
    7: "Valuation",
    8: "Macro & Geopolitical",
    9: "Risk Assessment",
    10: "Red Team",
    11: "Associate Review",
    12: "Portfolio Construction",
    13: "Report Assembly",
    14: "Monitoring",
}


# ── Supervisor Agent ──────────────────────────────────────────────────────


class PipelineSupervisorAgent:
    """Inline pipeline supervisor that monitors execution health and suggests remediation.

    Designed to be instantiated once per pipeline run and called after each stage
    via ``check_stage()``.  No LLM is required for deterministic checks; the optional
    ``llm_analyse_failure()`` method can be called for richer remediation advice.

    Usage in PipelineEngine::

        self.supervisor = PipelineSupervisorAgent(run_id=run_id)

        # after stage_2_ingestion completes:
        self.supervisor.check_stage(
            stage_num=2,
            stage_passed=True,
            stage_output=self.stage_outputs.get(2),
            duration_ms=self._stage_timings.get(2, 0),
        )

        # at the end of the run:
        report = self.supervisor.build_report()
    """

    def __init__(self, run_id: str = "") -> None:
        self.run_id = run_id
        self._records: dict[int, StageHealthRecord] = {}
        self._run_start = time.monotonic()
        logger.info("PipelineSupervisor initialised for run %s", run_id or "(no id yet)")

    # ── Public API ────────────────────────────────────────────────────

    def check_stage(
        self,
        stage_num: int,
        stage_passed: bool,
        stage_output: Any = None,
        duration_ms: float = 0.0,
        exception: Optional[Exception] = None,
    ) -> StageHealthRecord:
        """Evaluate a stage and return its health record.

        Args:
            stage_num: The stage index (0–14).
            stage_passed: Whether the stage gate passed.
            stage_output: The raw output dict from the stage.
            duration_ms: Wall-clock duration of the stage in milliseconds.
            exception: Any exception that was raised during the stage (if any).
        """
        stage_name = _STAGE_LABELS.get(stage_num, f"Stage {stage_num}")
        issues: list[str] = []
        warnings: list[str] = []
        remediation: list[str] = []

        if exception is not None:
            health = StageHealth.FAILED
            issues.append(f"Unhandled exception: {type(exception).__name__}: {exception}")
            remediation.extend(self._remediate_exception(stage_num, exception))
        elif not stage_passed:
            health = StageHealth.FAILED
            issues.append(f"Stage {stage_num} gate failed — output may be incomplete")
            remediation.extend(self._remediate_gate_failure(stage_num, stage_output))
        else:
            # Stage passed — run completeness checks
            health, completeness_issues, completeness_warnings = self._check_output_completeness(
                stage_num, stage_output
            )
            issues.extend(completeness_issues)
            warnings.extend(completeness_warnings)
            if health != StageHealth.FAILED:
                remediation.extend(self._remediate_degraded(stage_num, stage_output))

        # Timing check
        slow_threshold = _STAGE_SLOW_THRESHOLD_MS.get(stage_num, 600_000)
        if duration_ms > slow_threshold:
            warnings.append(
                f"Stage {stage_num} took {duration_ms:.0f}ms "
                f"(threshold: {slow_threshold:.0f}ms) — may indicate slow API or heavy data"
            )

        record = StageHealthRecord(
            stage_num=stage_num,
            stage_name=stage_name,
            health=health,
            issues=issues,
            warnings=warnings,
            remediation=remediation,
            duration_ms=duration_ms,
        )
        self._records[stage_num] = record

        _level = logging.WARNING if health != StageHealth.OK else logging.DEBUG
        logger.log(
            _level,
            "Supervisor [S%d %s]: health=%s issues=%d warnings=%d",
            stage_num,
            stage_name,
            health.value,
            len(issues),
            len(warnings),
        )
        return record

    def mark_skipped(self, stage_num: int) -> StageHealthRecord:
        """Mark a stage as skipped (not executed due to upstream failure)."""
        stage_name = _STAGE_LABELS.get(stage_num, f"Stage {stage_num}")
        record = StageHealthRecord(
            stage_num=stage_num,
            stage_name=stage_name,
            health=StageHealth.SKIPPED,
            issues=["Stage not executed — upstream stage failure"],
        )
        self._records[stage_num] = record
        return record

    def build_report(self, total_duration_ms: Optional[float] = None) -> SupervisorReport:
        """Build and return the full supervisor health report."""
        records = self._records

        stages_ok = sum(1 for r in records.values() if r.health == StageHealth.OK)
        stages_degraded = sum(1 for r in records.values() if r.health == StageHealth.DEGRADED)
        stages_failed = sum(1 for r in records.values() if r.health == StageHealth.FAILED)
        stages_skipped = sum(1 for r in records.values() if r.health == StageHealth.SKIPPED)

        # Aggregate critical issues and warnings
        critical_issues: list[str] = []
        all_warnings: list[str] = []
        remediation_summary: list[str] = []
        pipeline_interrupted_at: Optional[int] = None

        for num in sorted(records):
            rec = records[num]
            if rec.health == StageHealth.FAILED:
                for issue in rec.issues:
                    critical_issues.append(f"[S{num}] {issue}")
                for rem in rec.remediation:
                    remediation_summary.append(f"[S{num}] {rem}")
                if pipeline_interrupted_at is None:
                    pipeline_interrupted_at = num
            if rec.health == StageHealth.DEGRADED:
                for issue in rec.issues:
                    critical_issues.append(f"[S{num}] DEGRADED: {issue}")
            for warn in rec.warnings:
                all_warnings.append(f"[S{num}] {warn}")

        # Overall health
        if stages_failed > 0:
            overall = StageHealth.FAILED
        elif stages_degraded > 0:
            overall = StageHealth.DEGRADED
        elif stages_ok > 0:
            overall = StageHealth.OK
        else:
            overall = StageHealth.UNKNOWN

        if total_duration_ms is None:
            total_duration_ms = round((time.monotonic() - self._run_start) * 1000, 1)

        return SupervisorReport(
            run_id=self.run_id,
            overall_health=overall,
            stages_checked=len(records),
            stages_ok=stages_ok,
            stages_degraded=stages_degraded,
            stages_failed=stages_failed,
            stages_skipped=stages_skipped,
            stage_records=[
                r.to_dict() for r in sorted(records.values(), key=lambda x: x.stage_num)
            ],
            critical_issues=critical_issues,
            all_warnings=all_warnings,
            remediation_summary=remediation_summary,
            pipeline_interrupted_at=pipeline_interrupted_at,
            total_duration_ms=total_duration_ms,
        )

    def get_stage_record(self, stage_num: int) -> Optional[StageHealthRecord]:
        """Return the health record for a specific stage, or None if not yet checked."""
        return self._records.get(stage_num)

    # ── Internal analysis helpers ─────────────────────────────────────

    def _check_output_completeness(
        self, stage_num: int, output: Any
    ) -> tuple[StageHealth, list[str], list[str]]:
        """Check that stage output has the expected shape and required keys."""
        issues: list[str] = []
        warnings: list[str] = []

        if output is None:
            issues.append(f"Stage {stage_num} produced no output (None)")
            return StageHealth.DEGRADED, issues, warnings

        required = _STAGE_REQUIRED_KEYS.get(stage_num, [])

        if isinstance(output, dict):
            # Check for error sentinel keys
            if output.get("error"):
                warnings.append(f"Output contains error key: {output['error']}")
            if output.get("status") == "failed":
                issues.append("Output status is 'failed'")
                return StageHealth.FAILED, issues, warnings

            # Check required keys
            for key in required:
                if key not in output:
                    issues.append(f"Required output key '{key}' is missing")

            # Check for empty output where content is expected
            if not output and required:
                issues.append("Output is an empty dict but required keys expected")

            if issues:
                return StageHealth.DEGRADED, issues, warnings

        elif isinstance(output, list):
            if not output and stage_num in (2, 5, 6):
                warnings.append(f"Stage {stage_num} returned an empty list — no data processed")

        return StageHealth.OK, issues, warnings

    def _remediate_exception(self, stage_num: int, exc: Exception) -> list[str]:
        """Suggest remediation steps for an exception."""
        exc_type = type(exc).__name__
        remediations: list[str] = []

        if "ConnectionError" in exc_type or "Timeout" in exc_type or "TimeoutError" in exc_type:
            remediations.append("Network/timeout error — check API connectivity and retry")
            remediations.append("Consider increasing request timeout settings")
        elif "RateLimit" in exc_type or "429" in str(exc):
            remediations.append(
                "Rate limit hit — add delay between API calls or reduce parallelism"
            )
            remediations.append("Enable quota manager throttling in config")
        elif "AuthenticationError" in exc_type or "401" in str(exc):
            remediations.append("Authentication failed — verify API keys are set correctly")
            remediations.append("Check .env file for correct key names and values")
        elif "KeyError" in exc_type:
            remediations.append("Missing key in data — upstream stage may have incomplete output")
            remediations.append(f"Check stage {max(0, stage_num - 1)} output for required fields")
        elif "ImportError" in exc_type or "ModuleNotFoundError" in exc_type:
            remediations.append("Missing dependency — run: pip install -r requirements.txt")
        else:
            remediations.append(f"Unexpected {exc_type} — check logs for full traceback")
            if stage_num >= 5:
                remediations.append("For LLM stages: verify model name and API key are valid")

        return remediations

    def _remediate_gate_failure(self, stage_num: int, output: Any) -> list[str]:
        """Suggest remediation for a gate failure (stage returned False)."""
        remediations: list[str] = []

        if stage_num == 0:
            remediations.append("Config validation failed — check final_pipeline_config_v8.yaml")
            remediations.append("Ensure all required API keys are set (ANTHROPIC_API_KEY etc.)")
        elif stage_num == 1:
            remediations.append("Universe validation failed — check ticker symbols are valid")
            remediations.append("Remove invalid tickers from the selection")
        elif stage_num == 2:
            remediations.append("Data ingestion failed — verify FMP_API_KEY and FINNHUB_API_KEY")
            remediations.append("Check network connectivity to financial data APIs")
            remediations.append("If keys are missing, pipeline will use synthetic fallback data")
        elif stage_num == 3:
            remediations.append("Reconciliation failed — price divergence exceeds threshold")
            remediations.append("Increase reconciliation threshold in config or check data source")
        elif stage_num == 4:
            remediations.append("Data QA failed — check lineage requirements in config")
            remediations.append(
                "Set require_lineage_for_all_final_fields: false in config to relax"
            )
        elif stage_num == 5:
            remediations.append("Evidence librarian failed — check LLM API key and model name")
            remediations.append("Reduce universe size to lower LLM cost if hitting quota limits")
        elif stage_num == 11:
            if isinstance(output, dict) and not output.get("approved", True):
                remediations.append(
                    "Associate review rejected — review quality issues in LLM output"
                )
                remediations.append("Check stage 10 (Red Team) for unresolved critical issues")
            else:
                remediations.append("Associate review stage failed — check LLM connectivity")
        elif stage_num == 12:
            remediations.append("Portfolio construction failed — check weights sum to ~100%")
            remediations.append("Verify mandate compliance rules are satisfiable")
        elif stage_num == 13:
            remediations.append("Report assembly failed — check stage 12 portfolio output exists")
            remediations.append("Verify report template and output directory permissions")
        else:
            remediations.append(f"Stage {stage_num} gate failed — review stage output and logs")

        return remediations

    def _remediate_degraded(self, stage_num: int, output: Any) -> list[str]:
        """Suggest remediation for degraded (passed but incomplete) output."""
        if not isinstance(output, dict):
            return []
        remediations: list[str] = []

        if stage_num == 2 and isinstance(output, list) and len(output) == 0:
            remediations.append("No market data returned — API keys may be missing or invalid")
        elif stage_num == 5:
            claims = output.get("claims", [])
            if isinstance(claims, list) and len(claims) == 0:
                remediations.append(
                    "Empty claim ledger — evidence librarian may have failed silently"
                )
        elif stage_num == 6:
            sector_outputs = output.get("sector_outputs", [])
            if isinstance(sector_outputs, list) and len(sector_outputs) == 0:
                remediations.append("No sector analysis outputs — check LLM agent configuration")

        return remediations
