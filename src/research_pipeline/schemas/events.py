"""
src/research_pipeline/schemas/events.py
----------------------------------------
Session 15 — Phase 2: PipelineEvent contract

Every significant thing that happens during a pipeline run is represented as a
typed PipelineEvent.  The engine emits these via an optional async callback;
the FastAPI layer consumes them and streams them over SSE to connected clients.

Event types (strict ordering within a run):
  pipeline_started         → run begins
  stage_started            → a numbered stage begins (0–14)
  agent_started            → an LLM agent call begins
  llm_call_started         → raw LLM request is dispatched
  llm_call_completed       → raw LLM response received
  agent_completed          → agent returned a result
  stage_completed          → stage finished successfully
  stage_failed             → stage returned False (hard gate failure)
  artifact_written         → a file was saved to storage
  pipeline_completed       → run_full_pipeline() returned successfully
  pipeline_failed          → run_full_pipeline() returned with status=failed
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# ── Event type literal ──────────────────────────────────────────────────────

PipelineEventType = Literal[
    "pipeline_started",
    "stage_started",
    "stage_completed",
    "stage_failed",
    "agent_started",
    "agent_completed",
    "llm_call_started",
    "llm_call_completed",
    "artifact_written",
    "pipeline_completed",
    "pipeline_failed",
]

# Stage labels for human-readable display
STAGE_LABELS: dict[int, str] = {
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


class PipelineEvent(BaseModel):
    """A single observable event emitted during pipeline execution.

    Consumers (SSE clients, test hooks) receive a stream of these as the run
    progresses.  The `data` dict carries event-specific payload — always safe
    to ignore unknown keys for forward-compatibility.
    """

    run_id: str
    event_type: PipelineEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stage: Optional[int] = None
    stage_label: Optional[str] = None
    agent_name: Optional[str] = None
    duration_ms: Optional[float] = None
    data: dict[str, Any] = Field(default_factory=dict)

    # ── Convenience constructors ────────────────────────────────────────

    @classmethod
    def pipeline_started(cls, run_id: str, universe: list[str]) -> "PipelineEvent":
        return cls(
            run_id=run_id,
            event_type="pipeline_started",
            data={"universe": universe, "ticker_count": len(universe)},
        )

    @classmethod
    def stage_started(cls, run_id: str, stage: int) -> "PipelineEvent":
        label = STAGE_LABELS.get(stage, f"Stage {stage}")
        return cls(
            run_id=run_id,
            event_type="stage_started",
            stage=stage,
            stage_label=label,
            data={"stage_label": label},
        )

    @classmethod
    def stage_completed(cls, run_id: str, stage: int, duration_ms: float) -> "PipelineEvent":
        label = STAGE_LABELS.get(stage, f"Stage {stage}")
        return cls(
            run_id=run_id,
            event_type="stage_completed",
            stage=stage,
            stage_label=label,
            duration_ms=duration_ms,
            data={"stage_label": label, "duration_ms": duration_ms},
        )

    @classmethod
    def stage_failed(cls, run_id: str, stage: int, reason: str = "") -> "PipelineEvent":
        label = STAGE_LABELS.get(stage, f"Stage {stage}")
        return cls(
            run_id=run_id,
            event_type="stage_failed",
            stage=stage,
            stage_label=label,
            data={"stage_label": label, "reason": reason},
        )

    @classmethod
    def agent_started(
        cls, run_id: str, agent_name: str, stage: Optional[int] = None
    ) -> "PipelineEvent":
        return cls(
            run_id=run_id,
            event_type="agent_started",
            stage=stage,
            agent_name=agent_name,
            data={"agent": agent_name},
        )

    @classmethod
    def agent_completed(
        cls,
        run_id: str,
        agent_name: str,
        duration_ms: float,
        stage: Optional[int] = None,
        tokens_used: Optional[int] = None,
    ) -> "PipelineEvent":
        return cls(
            run_id=run_id,
            event_type="agent_completed",
            stage=stage,
            agent_name=agent_name,
            duration_ms=duration_ms,
            data={"agent": agent_name, "duration_ms": duration_ms, "tokens_used": tokens_used},
        )

    @classmethod
    def llm_call_started(
        cls,
        run_id: str,
        agent_name: str,
        model: str,
        stage: Optional[int] = None,
    ) -> "PipelineEvent":
        return cls(
            run_id=run_id,
            event_type="llm_call_started",
            stage=stage,
            agent_name=agent_name,
            data={"agent": agent_name, "model": model},
        )

    @classmethod
    def llm_call_completed(
        cls,
        run_id: str,
        agent_name: str,
        model: str,
        duration_ms: float,
        tokens_used: Optional[int] = None,
        stage: Optional[int] = None,
    ) -> "PipelineEvent":
        return cls(
            run_id=run_id,
            event_type="llm_call_completed",
            stage=stage,
            agent_name=agent_name,
            duration_ms=duration_ms,
            data={
                "agent": agent_name,
                "model": model,
                "duration_ms": duration_ms,
                "tokens_used": tokens_used,
            },
        )

    @classmethod
    def artifact_written(
        cls, run_id: str, artifact_path: str, artifact_type: str = ""
    ) -> "PipelineEvent":
        return cls(
            run_id=run_id,
            event_type="artifact_written",
            data={"path": artifact_path, "artifact_type": artifact_type},
        )

    @classmethod
    def pipeline_completed(cls, run_id: str, duration_ms: float) -> "PipelineEvent":
        return cls(
            run_id=run_id,
            event_type="pipeline_completed",
            duration_ms=duration_ms,
            data={"duration_ms": duration_ms},
        )

    @classmethod
    def pipeline_failed(
        cls, run_id: str, blocked_at: Optional[int] = None, reason: str = ""
    ) -> "PipelineEvent":
        return cls(
            run_id=run_id,
            event_type="pipeline_failed",
            stage=blocked_at,
            data={"blocked_at": blocked_at, "reason": reason},
        )

    def to_sse_data(self) -> str:
        """Serialize to a JSON string suitable for embedding in an SSE `data:` line."""
        return self.model_dump_json()
