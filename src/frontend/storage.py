"""Persistent storage for completed pipeline runs.

Reports are saved to the workspace reports/ directory and survive
server restarts and port closures.

A-2 Unification:
  ``save_run()`` now also writes a record to the backend
  ``RunRegistryService`` so that both the frontend file store and the
  backend registry remain in sync.  This is purely additive — if the
  registry is unavailable (import error, permission issue) the function
  falls back gracefully to file-only storage.

  ``list_saved_runs()`` merges the registry listing with the file-based
  listing, deduplicating by run_id (registry wins on conflict).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Storage root ──────────────────────────────────────────────────────────
ROOT = Path(__file__).parents[2]  # /workspaces/Financial-analysis
REPORTS_DIR = ROOT / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

# Backend registry storage — co-located with the frontend reports dir by default
_REGISTRY_DIR = Path(os.environ.get("PIPELINE_STORAGE_DIR", str(ROOT / "storage")))


def _get_registry():
    """Return a RunRegistryService instance, or None if unavailable."""
    try:
        from research_pipeline.services.run_registry import RunRegistryService  # noqa: PLC0415

        return RunRegistryService(storage_dir=_REGISTRY_DIR)
    except Exception as exc:  # pragma: no cover
        logger.debug("RunRegistryService unavailable: %s", exc)
        return None


def save_run(run_result) -> Path:
    """
    Persist a completed RunResult to disk.

    Writes two files:
      reports/{run_id}.json   — full structured data (reload-able)
      reports/{run_id}.md     — final report markdown for easy access

    Returns the .json path.
    """
    run_id = run_result.run_id
    json_path = REPORTS_DIR / f"{run_id}.json"
    md_path = REPORTS_DIR / f"{run_id}.md"

    # Serialise the full result
    try:
        payload = {
            "run_id": run_result.run_id,
            "tickers": run_result.tickers,
            "model": run_result.model,
            "started_at": run_result.started_at,
            "completed_at": run_result.completed_at,
            "success": run_result.success,
            "publication_status": run_result.publication_status,
            "final_report_md": run_result.final_report_md,
            "stages": [
                {
                    "stage_num": s.stage_num,
                    "stage_name": s.stage_name,
                    "status": s.status,
                    "elapsed_secs": s.elapsed_secs,
                    "error": s.error,
                    "raw_text": s.raw_text,
                    "output": s.output,
                }
                for s in run_result.stages
            ],
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        md_path.write_text(run_result.final_report_md or "", encoding="utf-8")
        logger.info("Run %s saved to %s", run_id, json_path)
    except Exception as exc:
        logger.error("Failed to save run %s: %s", run_id, exc)
        raise

    # ── A-2: Mirror to backend RunRegistryService ─────────────────────
    # Additive — failure here never blocks the return value.
    _mirror_to_registry(run_result)

    return json_path


def _mirror_to_registry(run_result) -> None:
    """Write/update the backend RunRegistryService with the completed run.

    Creates a new registry record if one doesn't exist yet, then marks it
    COMPLETED.  Silently swallows errors so callers are never affected.
    """
    registry = _get_registry()
    if registry is None:
        return
    try:
        from research_pipeline.schemas.registry import RunStatus  # noqa: PLC0415

        run_id = run_result.run_id
        existing = registry.get_run(run_id)
        if existing is None:
            # Create a minimal registry record for runs started outside PipelineEngine
            registry.create_run(
                universe=getattr(run_result, "tickers", []),
                config={"model": getattr(run_result, "model", "unknown")},
            )
        final_status = (
            RunStatus.COMPLETED if getattr(run_result, "success", False) else RunStatus.FAILED
        )
        registry.update_run_status(
            run_id,
            final_status,
            final_gate_outcome=getattr(run_result, "publication_status", ""),
        )
        logger.debug("Run %s mirrored to registry with status %s", run_id, final_status)
    except Exception as exc:  # pragma: no cover
        logger.warning("Registry mirror failed for run %s: %s", run_result.run_id, exc)


def list_saved_runs() -> list[dict]:
    """
    Return metadata for all saved runs, newest first.

    Merges two sources (deduplicating by run_id, file-store wins on conflict):
      1. JSON files in reports/  — full detail, always available
      2. Backend RunRegistryService — adds registry-only entries (runs
         executed via PipelineEngine without going through the frontend
         save_run() path)

    Each entry has: run_id, tickers, model, completed_at, success,
                    word_count, json_path, md_path
    """
    # ── 1. File-based entries ─────────────────────────────────────────
    entries_by_id: dict[str, dict] = {}
    for jf in sorted(REPORTS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
            md_path = jf.with_suffix(".md")
            rid = data.get("run_id", jf.stem)
            entries_by_id[rid] = {
                "run_id": rid,
                "tickers": data.get("tickers", []),
                "model": data.get("model", "unknown"),
                "completed_at": data.get("completed_at", ""),
                "success": data.get("success", False),
                "word_count": len((data.get("final_report_md") or "").split()),
                "json_path": str(jf),
                "md_path": str(md_path) if md_path.exists() else None,
            }
        except Exception as exc:
            logger.warning("Could not read saved run %s: %s", jf, exc)

    # ── 2. Registry entries (fill gaps not covered by file store) ─────
    registry = _get_registry()
    if registry is not None:
        try:
            for record in registry.list_runs(limit=100):
                if record.run_id in entries_by_id:
                    continue  # file store has full detail — don't overwrite
                completed = record.completed_at.isoformat() if record.completed_at else ""
                entries_by_id[record.run_id] = {
                    "run_id": record.run_id,
                    "tickers": record.universe,
                    "model": record.agent_versions.get("orchestrator", "unknown"),
                    "completed_at": completed,
                    "success": str(record.status) in ("RunStatus.COMPLETED", "completed"),
                    "word_count": 0,
                    "json_path": None,
                    "md_path": None,
                    "_source": "registry",
                }
        except Exception as exc:
            logger.debug("Registry listing failed: %s", exc)

    return sorted(entries_by_id.values(), key=lambda e: e.get("completed_at", ""), reverse=True)


def load_run(run_id: str) -> Optional[dict]:
    """Load the full JSON payload for a saved run. Returns None if not found."""
    jf = REPORTS_DIR / f"{run_id}.json"
    if not jf.exists():
        return None
    try:
        return json.loads(jf.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.error("Failed to load run %s: %s", run_id, exc)
        return None


def delete_run(run_id: str) -> bool:
    """Delete a saved run. Returns True if deleted."""
    deleted = False
    for suffix in (".json", ".md"):
        p = REPORTS_DIR / f"{run_id}{suffix}"
        if p.exists():
            p.unlink()
            deleted = True
    return deleted
