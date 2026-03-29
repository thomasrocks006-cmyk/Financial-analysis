"""
src/api/routes/runs.py
----------------------
Session 15+16 — Full API surface

All pipeline-run endpoints:
  POST   /api/v1/runs                          — start a new run
  GET    /api/v1/runs                          — list all runs
  GET    /api/v1/runs/{run_id}                 — get run summary / status
  DELETE /api/v1/runs/{run_id}                 — cancel + delete a run
  GET    /api/v1/runs/{run_id}/result          — get full pipeline result
  GET    /api/v1/runs/{run_id}/events          — SSE event stream
  GET    /api/v1/runs/{run_id}/report          — get report markdown
  GET    /api/v1/runs/{run_id}/stages          — list all stages with outputs
  GET    /api/v1/runs/{run_id}/stages/{stage}  — single stage detail
  GET    /api/v1/runs/{run_id}/audit           — self-audit packet
  GET    /api/v1/runs/{run_id}/artifacts       — list artifact files
  GET    /api/v1/runs/{run_id}/timings         — per-stage timing breakdown
  GET    /api/v1/runs/{run_id}/provenance      — traceability & provenance packet
  GET    /api/v1/saved-runs                    — list saved runs from disk
  GET    /api/v1/saved-runs/{run_id}           — load saved run detail
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
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


# ── GET /runs/{run_id}/report — report markdown ─────────────────────────────

@router.get("/{run_id}/report", summary="Get pipeline report markdown")
async def get_report(
    run_id: str,
    manager: RunManager = Depends(get_run_manager),
) -> dict[str, Any]:
    """Return the report markdown for a completed run, plus word/page counts."""
    run = manager.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    if run.status in (ApiRunStatus.QUEUED, ApiRunStatus.RUNNING):
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"run_id": run_id, "status": run.status, "message": "Run in progress"},
        )
    report_md = ""
    if run.result:
        # Try engine result first
        stage13 = run.result.get("stage_outputs", {}).get("13", run.result.get("stage_outputs", {}).get(13, {}))
        if isinstance(stage13, dict):
            report_md = stage13.get("report_markdown", stage13.get("report", ""))
            if not report_md and "report_path" in stage13:
                rp = Path(stage13["report_path"])
                if rp.exists():
                    try:
                        report_md = rp.read_text(encoding="utf-8")
                    except Exception:
                        pass
    words = len(report_md.split()) if report_md else 0
    return {
        "run_id": run_id,
        "report_markdown": report_md,
        "word_count": words,
        "estimated_pages": max(1, words // 300) if words else 0,
    }


# ── GET /runs/{run_id}/stages — all stages ──────────────────────────────────

@router.get("/{run_id}/stages", summary="List all stages with timing and gate status")
async def get_stages(
    run_id: str,
    manager: RunManager = Depends(get_run_manager),
) -> dict[str, Any]:
    run = manager.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    stages = manager.get_stages(run_id)
    return {"run_id": run_id, "stages": stages, "count": len(stages)}


# ── GET /runs/{run_id}/stages/{stage_num} — single stage ────────────────────

@router.get("/{run_id}/stages/{stage_num}", summary="Get single stage detail")
async def get_stage_detail(
    run_id: str,
    stage_num: int,
    manager: RunManager = Depends(get_run_manager),
) -> dict[str, Any]:
    run = manager.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    if stage_num < 0 or stage_num > 14:
        raise HTTPException(status_code=400, detail=f"Invalid stage number: {stage_num}")
    stages = manager.get_stages(run_id)
    for s in stages:
        if s.get("stage_num") == stage_num:
            return s
    raise HTTPException(status_code=404, detail=f"Stage {stage_num} not found")


# ── GET /runs/{run_id}/audit — self-audit packet ────────────────────────────

@router.get("/{run_id}/audit", summary="Get self-audit packet")
async def get_audit(
    run_id: str,
    manager: RunManager = Depends(get_run_manager),
) -> dict[str, Any]:
    run = manager.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    audit = manager.get_audit_packet(run_id)
    return {"run_id": run_id, "audit_packet": audit}


# ── GET /runs/{run_id}/timings — stage timing breakdown ─────────────────────

@router.get("/{run_id}/timings", summary="Get per-stage timing breakdown")
async def get_timings(
    run_id: str,
    manager: RunManager = Depends(get_run_manager),
) -> dict[str, Any]:
    run = manager.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    timings = manager.get_timings(run_id)
    return {"run_id": run_id, "timings": timings}


# ── GET /runs/{run_id}/artifacts — list output artifact files ────────────────

@router.get("/{run_id}/artifacts", summary="List artifact files for a run")
async def list_artifacts(
    run_id: str,
    manager: RunManager = Depends(get_run_manager),
) -> dict[str, Any]:
    run = manager.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    artifacts = manager.list_artifacts(run_id)
    return {"run_id": run_id, "artifacts": artifacts, "count": len(artifacts)}


# ── GET /runs/{run_id}/provenance — traceability & provenance packet ─────────

@router.get("/{run_id}/provenance", summary="Get traceability & provenance packet")
async def get_provenance(
    run_id: str,
    manager: RunManager = Depends(get_run_manager),
) -> dict[str, Any]:
    """Return the provenance packet with per-stage lineage cards and report section provenance."""
    run = manager.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    if run.status in (ApiRunStatus.QUEUED, ApiRunStatus.RUNNING):
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content={"run_id": run_id, "status": run.status, "message": "Run in progress"},
        )
    provenance = manager.get_provenance(run_id)
    return {"run_id": run_id, "provenance": provenance}


# ── Saved runs endpoints (disk-persisted runs) ──────────────────────────────

saved_router = APIRouter(prefix="/saved-runs", tags=["saved-runs"])


@saved_router.get("", summary="List saved completed runs from disk")
async def list_saved_runs(
    request: Request,
) -> dict[str, Any]:
    try:
        from frontend.storage import list_saved_runs as _list_saved  # noqa: PLC0415
        runs = _list_saved()
        return {"runs": runs, "count": len(runs)}
    except ImportError:
        return {"runs": [], "count": 0, "note": "Storage module not available"}


@saved_router.get("/{run_id}", summary="Load a saved run from disk")
async def load_saved_run(
    run_id: str,
) -> dict[str, Any]:
    try:
        from frontend.storage import load_run  # noqa: PLC0415
        data = load_run(run_id)
        if data is None:
            raise HTTPException(status_code=404, detail=f"Saved run not found: {run_id}")
        return data
    except ImportError:
        raise HTTPException(status_code=503, detail="Storage module not available")
