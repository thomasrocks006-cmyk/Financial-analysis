"""
src/api/routes/runs.py
----------------------
Session 15 — Phase 4: /api/v1/runs routes

All pipeline-run endpoints:
  POST   /api/v1/runs                     — start a new run
  GET    /api/v1/runs                     — list all runs
  GET    /api/v1/runs/{run_id}            — get run summary / status
  DELETE /api/v1/runs/{run_id}            — cancel + delete a run
  GET    /api/v1/runs/{run_id}/result     — get full pipeline result
  GET    /api/v1/runs/{run_id}/events     — SSE event stream
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

from research_pipeline.schemas.run_request import RunRequest
from api.services.run_manager import ApiRunStatus, RunManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/runs", tags=["runs"])


# ── Dependency: inject RunManager from app state ─────────────────────────────

def get_run_manager(request: Request) -> RunManager:
    return request.app.state.run_manager


# ── POST /runs — start a new run ─────────────────────────────────────────────

@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a new pipeline run",
    response_description="Returns the run_id immediately; run executes in the background.",
)
async def start_run(
    run_request: RunRequest,
    manager: RunManager = Depends(get_run_manager),
) -> dict[str, Any]:
    run_id = await manager.start_run(run_request)
    return {
        "run_id": run_id,
        "status": ApiRunStatus.RUNNING,
        "universe_count": len(run_request.universe),
        "events_url": f"/api/v1/runs/{run_id}/events",
        "status_url": f"/api/v1/runs/{run_id}",
        "result_url": f"/api/v1/runs/{run_id}/result",
    }


# ── GET /runs — list all runs ────────────────────────────────────────────────

@router.get("", summary="List all pipeline runs")
async def list_runs(
    manager: RunManager = Depends(get_run_manager),
) -> dict[str, Any]:
    return {"runs": manager.list_runs(), "count": len(manager.list_runs())}


# ── GET /runs/{run_id} — run status ─────────────────────────────────────────

@router.get("/{run_id}", summary="Get run status and summary")
async def get_run_status(
    run_id: str,
    manager: RunManager = Depends(get_run_manager),
) -> dict[str, Any]:
    run = manager.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run not found: {run_id}",
        )
    return run.to_summary() | {
        "error": run.error,
        "has_result": run.result is not None,
    }


# ── GET /runs/{run_id}/result — full result ──────────────────────────────────

@router.get("/{run_id}/result", summary="Get the full pipeline result")
async def get_result(
    run_id: str,
    manager: RunManager = Depends(get_run_manager),
) -> dict[str, Any]:
    run = manager.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    if run.status in (ApiRunStatus.QUEUED, ApiRunStatus.RUNNING):
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={
                "run_id": run_id,
                "status": run.status,
                "message": "Run is still in progress; poll again or subscribe to /events",
            },
        )

    if run.result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No result available for run {run_id} (status: {run.status})",
        )

    return run.result


# ── DELETE /runs/{run_id} ────────────────────────────────────────────────────

@router.delete("/{run_id}", summary="Cancel and delete a run")
async def delete_run(
    run_id: str,
    manager: RunManager = Depends(get_run_manager),
) -> dict[str, Any]:
    deleted = manager.delete_run(run_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    return {"run_id": run_id, "deleted": True}


# ── GET /runs/{run_id}/events — SSE stream ───────────────────────────────────

@router.get("/{run_id}/events", summary="Stream pipeline events via SSE")
async def stream_events(
    run_id: str,
    manager: RunManager = Depends(get_run_manager),
) -> StreamingResponse:
    run = manager.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    async def _sse_generator():
        """Yield Server-Sent Events for every PipelineEvent in the run queue."""
        # Send an initial connection confirmation
        yield _sse("connected", {"run_id": run_id, "status": run.status})

        async for event in manager.event_stream(run_id):
            payload = event.to_sse_data() if hasattr(event, "to_sse_data") else json.dumps({"heartbeat": True})
            yield _sse(event.event_type if hasattr(event, "event_type") else "heartbeat", payload)

        # Terminal event
        yield _sse("stream_closed", {"run_id": run_id})

    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def _sse(event_name: str, data: Any) -> str:
    """Format a single SSE message frame."""
    if isinstance(data, str):
        payload = data
    else:
        payload = json.dumps(data)
    return f"event: {event_name}\ndata: {payload}\n\n"
