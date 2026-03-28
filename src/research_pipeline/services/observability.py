"""Phase 7.5 — Observability Service: stage latency, token usage, cost tracking per run."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Approximate per-token costs (USD) for current model versions
_MODEL_COST_PER_1K_TOKENS: dict[str, dict[str, float]] = {
    "claude-opus-4-6":   {"input": 0.015,  "output": 0.075},
    "claude-sonnet-4-5": {"input": 0.003,  "output": 0.015},
    "gpt-4o":            {"input": 0.005,  "output": 0.015},
    "gpt-4o-mini":       {"input": 0.00015,"output": 0.0006},
    "gemini-1.5-pro":    {"input": 0.00125,"output": 0.005},
}
_DEFAULT_COST = {"input": 0.01, "output": 0.03}


@dataclass
class StageMetrics:
    """Metrics for a single pipeline stage."""
    stage: int
    stage_name: str
    start_time: float = 0.0
    end_time: float = 0.0
    success: bool = True
    error: Optional[str] = None
    agent_calls: int = 0
    llm_input_tokens: int = 0
    llm_output_tokens: int = 0
    llm_model: str = ""
    llm_retries: int = 0
    api_calls: int = 0       # FMP/Finnhub
    cache_hits: int = 0

    @property
    def duration_seconds(self) -> float:
        if self.end_time > self.start_time:
            return round(self.end_time - self.start_time, 3)
        return 0.0

    @property
    def llm_cost_usd(self) -> float:
        """Approximate LLM cost for this stage."""
        if not self.llm_model:
            return 0.0
        costs = _MODEL_COST_PER_1K_TOKENS.get(self.llm_model, _DEFAULT_COST)
        return round(
            self.llm_input_tokens / 1000 * costs["input"]
            + self.llm_output_tokens / 1000 * costs["output"],
            6,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "name": self.stage_name,
            "duration_s": self.duration_seconds,
            "success": self.success,
            "error": self.error,
            "agent_calls": self.agent_calls,
            "llm_tokens_in": self.llm_input_tokens,
            "llm_tokens_out": self.llm_output_tokens,
            "llm_model": self.llm_model,
            "llm_retries": self.llm_retries,
            "llm_cost_usd": self.llm_cost_usd,
            "api_calls": self.api_calls,
            "cache_hits": self.cache_hits,
        }


@dataclass
class RunObservability:
    """Full observability record for a pipeline run."""
    run_id: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    stages: list[StageMetrics] = field(default_factory=list)
    total_api_calls: int = 0
    total_cache_hits: int = 0

    @property
    def total_duration_seconds(self) -> float:
        return sum(s.duration_seconds for s in self.stages)

    @property
    def total_llm_input_tokens(self) -> int:
        return sum(s.llm_input_tokens for s in self.stages)

    @property
    def total_llm_output_tokens(self) -> int:
        return sum(s.llm_output_tokens for s in self.stages)

    @property
    def total_llm_cost_usd(self) -> float:
        return round(sum(s.llm_cost_usd for s in self.stages), 4)

    @property
    def total_retries(self) -> int:
        return sum(s.llm_retries for s in self.stages)

    @property
    def failed_stages(self) -> list[int]:
        return [s.stage for s in self.stages if not s.success]

    def stage_for(self, stage_num: int) -> Optional[StageMetrics]:
        for s in self.stages:
            if s.stage == stage_num:
                return s
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_duration_s": self.total_duration_seconds,
            "total_llm_tokens_in": self.total_llm_input_tokens,
            "total_llm_tokens_out": self.total_llm_output_tokens,
            "total_llm_cost_usd": self.total_llm_cost_usd,
            "total_retries": self.total_retries,
            "total_api_calls": self.total_api_calls,
            "total_cache_hits": self.total_cache_hits,
            "failed_stages": self.failed_stages,
            "stages": [s.to_dict() for s in self.stages],
        }


_STAGE_NAMES = {
    0: "bootstrap",        1: "universe",       2: "data_ingestion",
    3: "reconciliation",   4: "data_qa",         5: "evidence",
    6: "sector_analysis",  7: "valuation",       8: "macro",
    9: "risk_scenarios",   10: "red_team",        11: "review",
    12: "portfolio",       13: "report_assembly", 14: "monitoring",
}


class ObservabilityService:
    """Tracks stage latency, token usage, API calls, and cost per pipeline run.

    Usage:
        obs = ObservabilityService(output_dir=Path("output/telemetry"))
        obs.start_run("RUN-001")
        obs.start_stage(2, "data_ingestion")
        # ... stage runs ...
        obs.end_stage(2, success=True, api_calls=30)
        obs.end_run("RUN-001")
        obs.save("RUN-001")
    """

    def __init__(self, output_dir: Path | None = None):
        self._output_dir = output_dir or Path("output/telemetry")
        self._runs: dict[str, RunObservability] = {}

    def start_run(self, run_id: str) -> RunObservability:
        """Register the start of a new pipeline run."""
        record = RunObservability(run_id=run_id)
        self._runs[run_id] = record
        logger.info("Observability started for run %s", run_id)
        return record

    def start_stage(self, run_id: str, stage: int, stage_name: str | None = None) -> StageMetrics:
        """Record stage start. Creates a StageMetrics and begins timer."""
        name = stage_name or _STAGE_NAMES.get(stage, f"stage_{stage}")
        metrics = StageMetrics(stage=stage, stage_name=name, start_time=time.monotonic())
        record = self._runs.get(run_id)
        if record:
            record.stages.append(metrics)
        return metrics

    def end_stage(
        self,
        run_id: str,
        stage: int,
        success: bool = True,
        error: str | None = None,
        agent_calls: int = 0,
        llm_input_tokens: int = 0,
        llm_output_tokens: int = 0,
        llm_model: str = "",
        llm_retries: int = 0,
        api_calls: int = 0,
        cache_hits: int = 0,
    ) -> Optional[StageMetrics]:
        """Record stage completion and update metrics."""
        record = self._runs.get(run_id)
        if not record:
            return None
        metrics = record.stage_for(stage)
        if not metrics:
            # Start hadn't been called — create retroactively
            metrics = self.start_stage(run_id, stage)

        metrics.end_time = time.monotonic()
        metrics.success = success
        metrics.error = error
        metrics.agent_calls = agent_calls
        metrics.llm_input_tokens = llm_input_tokens
        metrics.llm_output_tokens = llm_output_tokens
        metrics.llm_model = llm_model
        metrics.llm_retries = llm_retries
        metrics.api_calls = api_calls
        metrics.cache_hits = cache_hits

        record.total_api_calls += api_calls
        record.total_cache_hits += cache_hits

        logger.debug(
            "[%s] Stage %d %s in %.2fs — LLM $%.4f, retries=%d",
            run_id, stage, "OK" if success else "FAIL",
            metrics.duration_seconds, metrics.llm_cost_usd, llm_retries,
        )
        return metrics

    def end_run(self, run_id: str) -> Optional[RunObservability]:
        """Mark run as complete."""
        record = self._runs.get(run_id)
        if record:
            record.completed_at = datetime.now(timezone.utc)
            logger.info(
                "Run %s complete — %.1fs, $%.4f LLM, %d stages, %d failures",
                run_id,
                record.total_duration_seconds,
                record.total_llm_cost_usd,
                len(record.stages),
                len(record.failed_stages),
            )
        return record

    def get_run(self, run_id: str) -> Optional[RunObservability]:
        return self._runs.get(run_id)

    def save(self, run_id: str) -> Path:
        """Persist observability record as JSON to output_dir."""
        record = self._runs.get(run_id)
        if not record:
            raise KeyError(f"No observability record for run {run_id}")

        self._output_dir.mkdir(parents=True, exist_ok=True)
        path = self._output_dir / f"{run_id}_telemetry.json"
        path.write_text(json.dumps(record.to_dict(), indent=2))
        logger.info("Telemetry saved to %s", path)
        return path

    def summary_table(self, run_id: str) -> str:
        """Return ASCII table of stage durations for quick inspection."""
        record = self._runs.get(run_id)
        if not record:
            return f"No telemetry for run {run_id}"

        lines = [
            f"{'Stage':>5}  {'Name':<20}  {'Duration':>10}  {'Cost':>10}  {'Status'}",
            "-" * 65,
        ]
        for s in record.stages:
            status = "✓" if s.success else "✗ " + (s.error or "")[:20]
            lines.append(
                f"{s.stage:>5}  {s.stage_name:<20}  {s.duration_seconds:>9.2f}s"
                f"  ${s.llm_cost_usd:>8.4f}  {status}"
            )
        lines.append("-" * 65)
        lines.append(
            f"{'TOTAL':>5}  {'':20}  {record.total_duration_seconds:>9.2f}s"
            f"  ${record.total_llm_cost_usd:>8.4f}"
        )
        return "\n".join(lines)

    def all_runs_summary(self) -> list[dict[str, Any]]:
        """Return summary metrics for all tracked runs."""
        return [
            {
                "run_id": r.run_id,
                "duration_s": r.total_duration_seconds,
                "cost_usd": r.total_llm_cost_usd,
                "tokens_in": r.total_llm_input_tokens,
                "tokens_out": r.total_llm_output_tokens,
                "failed_stages": r.failed_stages,
                "retries": r.total_retries,
            }
            for r in self._runs.values()
        ]
