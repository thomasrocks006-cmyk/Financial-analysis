"""
src/api/services/run_manager.py
--------------------------------
Session 15 — Phase 4: RunManager

Central service that owns:
  • All active (and recently completed) pipeline runs
  • Per-run asyncio.Queue[PipelineEvent] for SSE streaming
  • Background asyncio.Task per run (engine.run_full_pipeline)
  • Thread-safe result storage

Thread- / async-safety contract:
  Everything is accessed from a single asyncio event loop (FastAPI's).
  The engine runs as an asyncio.Task on the same loop, so all queue.put_nowait
  calls happen on the same thread — no locks required.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

from research_pipeline.config.loader import PipelineConfig, load_pipeline_config
from research_pipeline.config.settings import Settings
from research_pipeline.pipeline.engine import PipelineEngine
from research_pipeline.schemas.events import PipelineEvent
from research_pipeline.schemas.run_request import RunRequest

logger = logging.getLogger(__name__)

# ── Run status ────────────────────────────────────────────────────────────────

class ApiRunStatus:
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ManagedRun:
    """All state associated with a single managed pipeline run."""

    run_id: str
    request: RunRequest
    status: str = ApiRunStatus.QUEUED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None

    # SSE event queue — None until the run starts
    event_queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=512))
    # Sentinel value put on the queue when the run finishes
    SENTINEL: str = "__done__"
    # asyncio task handle (cancel() supported)
    task: Optional[asyncio.Task] = None

    def to_summary(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "run_label": self.request.run_label,
            "universe": self.request.universe,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class RunManager:
    """Manages the lifecycle of all pipeline runs for the API layer.

    Usage pattern:

        manager = RunManager(settings)

        # Start a run (returns immediately)
        run_id = await manager.start_run(run_request)

        # Stream events
        async for event in manager.event_stream(run_id):
            yield event.to_sse_data()

        # Get final result
        result = manager.get_result(run_id)
    """

    def __init__(self, settings: Settings, config: Optional[PipelineConfig] = None):
        self.settings = settings
        self.config = config or load_pipeline_config()
        self._runs: dict[str, ManagedRun] = {}

    # ── Public API ────────────────────────────────────────────────────────

    async def start_run(self, request: RunRequest) -> str:
        """Create a new managed run and schedule it in the background.

        Returns the ``run_id`` immediately.  The pipeline runs asynchronously;
        callers should subscribe to :meth:`event_stream` to follow progress.
        """
        # Build an engine with per-request overrides
        overrides = request.to_settings_overrides()
        from dataclasses import replace
        run_settings = replace(self.settings, **overrides)

        # Apply client_profile and benchmark overrides to config
        run_config = self.config.model_copy(
            update={"client_profile": request.client_profile}
        ) if request.client_profile is not None else self.config

        engine = PipelineEngine(run_settings, run_config)

        # Reserve a placeholder run_id from the engine's registry
        tmp_record = engine.registry.create_run(
            universe=request.universe,
            config={"llm_model": request.llm_model, "run_label": request.run_label},
        )
        run_id = tmp_record.run_id

        # Pre-set the run_record so Stage 0 bootstrap finds it
        engine.run_record = tmp_record

        managed = ManagedRun(run_id=run_id, request=request)
        self._runs[run_id] = managed

        # Schedule the actual pipeline execution
        task = asyncio.create_task(
            self._execute_run(engine, managed),
            name=f"pipeline_{run_id}",
        )
        managed.task = task
        logger.info("Scheduled pipeline run %s (%d tickers)", run_id, len(request.universe))
        return run_id

    def get_run(self, run_id: str) -> Optional[ManagedRun]:
        return self._runs.get(run_id)

    def list_runs(self) -> list[dict[str, Any]]:
        return [r.to_summary() for r in reversed(list(self._runs.values()))]

    def get_result(self, run_id: str) -> Optional[dict[str, Any]]:
        run = self._runs.get(run_id)
        return run.result if run else None

    def get_stages(self, run_id: str) -> list[dict[str, Any]]:
        """Return per-stage summaries with timing, output, gate status."""
        from research_pipeline.schemas.events import STAGE_LABELS
        run = self._runs.get(run_id)
        if run is None:
            return []

        stages: list[dict[str, Any]] = []
        engine = run.engine if hasattr(run, "engine") else None
        result = run.result or {}
        stage_outputs = result.get("stage_outputs", {})

        for stage_num in range(15):
            label = STAGE_LABELS.get(stage_num, f"Stage {stage_num}")

            # Get output — try both int and string keys
            output = stage_outputs.get(stage_num, stage_outputs.get(str(stage_num), {}))

            # Gate info
            gate_passed = None
            gate_reason = ""
            gates = result.get("gate_results", {})
            gate_data = gates.get(stage_num, gates.get(str(stage_num)))
            if isinstance(gate_data, dict):
                gate_passed = gate_data.get("passed")
                gate_reason = gate_data.get("reason", "")

            # Timing
            timing_ms = 0.0
            timings = result.get("stage_timings", {})
            timing_ms = timings.get(f"stage_{stage_num}", timings.get(stage_num, 0.0))

            # Status
            if isinstance(output, dict) and output:
                st = "completed" if gate_passed is not False else "failed"
            elif stage_num in {int(k) if isinstance(k, str) and k.isdigit() else k for k in stage_outputs}:
                st = "completed"
            else:
                st = "pending" if run.status in (ApiRunStatus.QUEUED, ApiRunStatus.RUNNING) else "skipped"

            stages.append({
                "stage_num": stage_num,
                "stage_label": label,
                "status": st,
                "duration_ms": timing_ms,
                "gate_passed": gate_passed,
                "gate_reason": gate_reason,
                "output": output if isinstance(output, dict) else {"data": output} if output else {},
                "has_output": bool(output),
            })
        return stages

    def get_audit_packet(self, run_id: str) -> dict[str, Any]:
        """Return the self-audit packet for a completed run."""
        run = self._runs.get(run_id)
        if run is None or run.result is None:
            return {}
        return run.result.get("audit_packet", run.result.get("self_audit_packet", {}))

    def get_timings(self, run_id: str) -> dict[str, Any]:
        """Stage timing breakdown for a run."""
        run = self._runs.get(run_id)
        if run is None or run.result is None:
            return {}
        timings = run.result.get("stage_timings", {})
        total = run.result.get("total_duration_s", 0)
        return {"stage_latencies_ms": timings, "total_pipeline_duration_s": total}

    def get_provenance(self, run_id: str) -> dict[str, Any]:
        """Return the provenance packet for a completed run."""
        run = self._runs.get(run_id)
        if run is None or run.result is None:
            return {}
        packet = run.result.get("provenance_packet")
        if packet:
            return packet
        # Fallback: try loading from disk
        prov_path = self.settings.storage_dir / "artifacts" / run_id / "provenance_packet.json"
        if prov_path.exists():
            import json as _json
            try:
                return _json.loads(prov_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def list_artifacts(self, run_id: str) -> list[dict[str, Any]]:
        """List artifact files for a run from the storage directory."""
        artifact_dir = self.settings.storage_dir / "artifacts" / run_id
        if not artifact_dir.exists():
            return []
        artifacts = []
        for f in sorted(artifact_dir.iterdir()):
            if f.is_file():
                artifacts.append({
                    "filename": f.name,
                    "size_bytes": f.stat().st_size,
                    "path": str(f),
                })
        return artifacts

    def cancel_run(self, run_id: str) -> bool:
        """Cancel a queued or running pipeline. Returns True if cancelled."""
        run = self._runs.get(run_id)
        if run is None:
            return False
        if run.task is not None and not run.task.done():
            run.task.cancel()
            run.status = ApiRunStatus.CANCELLED
            return True
        return False

    def delete_run(self, run_id: str) -> bool:
        """Remove a run from the manager. Cancels first if still running."""
        self.cancel_run(run_id)
        return self._runs.pop(run_id, None) is not None

    async def event_stream(self, run_id: str) -> AsyncGenerator[PipelineEvent, None]:
        """Async generator that yields PipelineEvents for the given run.

        Yields events as they arrive and exits when the pipeline finishes
        (sentinel detected) or if the run is not found.
        """
        run = self._runs.get(run_id)
        if run is None:
            return

        while True:
            try:
                item = await asyncio.wait_for(run.event_queue.get(), timeout=30.0)
                if item == run.SENTINEL:
                    # Pipeline finished — drain any remaining events then stop
                    while not run.event_queue.empty():
                        extra = run.event_queue.get_nowait()
                        if extra != run.SENTINEL:
                            yield extra
                    break
                yield item
            except asyncio.TimeoutError:
                # Keep-alive: yield a "heartbeat" if nothing received for 30s
                yield PipelineEvent(
                    run_id=run_id,
                    event_type="stage_started",  # reuse a valid type
                    data={"heartbeat": True},
                )
            except asyncio.CancelledError:
                break

    # ── Internal ──────────────────────────────────────────────────────────

    async def _event_callback(self, managed: ManagedRun):
        """Return an async callback that enqueues events for ``managed``."""

        async def _cb(event: PipelineEvent) -> None:
            try:
                managed.event_queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("Event queue full for run %s — dropping event", managed.run_id)

        return _cb

    async def _execute_run(self, engine: PipelineEngine, managed: ManagedRun) -> None:
        """Background task: run the pipeline and update managed state."""
        managed.status = ApiRunStatus.RUNNING
        managed.started_at = datetime.now(timezone.utc)

        cb = await self._event_callback(managed)

        try:
            result = await engine.run_full_pipeline(
                universe=managed.request.universe,
                event_callback=cb,
            )
            managed.result = result
            if result.get("status") == "completed":
                managed.status = ApiRunStatus.COMPLETED
            else:
                managed.status = ApiRunStatus.FAILED
                managed.error = f"blocked_at stage {result.get('blocked_at')}"
        except asyncio.CancelledError:
            managed.status = ApiRunStatus.CANCELLED
            logger.info("Run %s was cancelled", managed.run_id)
        except Exception as exc:
            managed.status = ApiRunStatus.FAILED
            managed.error = str(exc)
            logger.exception("Run %s failed with exception", managed.run_id)
        finally:
            managed.completed_at = datetime.now(timezone.utc)
            # Signal SSE subscribers that the stream is done
            try:
                managed.event_queue.put_nowait(managed.SENTINEL)
            except asyncio.QueueFull:
                pass
