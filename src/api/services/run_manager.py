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
