"""Persistent storage for completed pipeline runs.

Reports are saved to the workspace reports/ directory and survive
server restarts and port closures.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Storage root ──────────────────────────────────────────────────────────
ROOT       = Path(__file__).parents[2]           # /workspaces/Financial-analysis
REPORTS_DIR = ROOT / "reports"
REPORTS_DIR.mkdir(exist_ok=True)




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
    md_path   = REPORTS_DIR / f"{run_id}.md"

    # Serialise the full result
    try:
        payload = {
            "run_id":              run_result.run_id,
            "tickers":             run_result.tickers,
            "model":               run_result.model,
            "started_at":          run_result.started_at,
            "completed_at":        run_result.completed_at,
            "success":             run_result.success,
            "publication_status":  run_result.publication_status,
            "final_report_md":     run_result.final_report_md,
            "stages": [
                {
                    "stage_num":    s.stage_num,
                    "stage_name":   s.stage_name,
                    "status":       s.status,
                    "elapsed_secs": s.elapsed_secs,
                    "error":        s.error,
                    "raw_text":     s.raw_text,
                    "output":       s.output,
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

    return json_path


def list_saved_runs() -> list[dict]:
    """
    Return metadata for all saved runs, newest first.

    Each entry has: run_id, tickers, model, completed_at, success,
                    word_count, json_path, md_path
    """
    entries = []
    for jf in sorted(REPORTS_DIR.glob("DEMO-*.json"), reverse=True):
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
            md_path = jf.with_suffix(".md")
            entries.append({
                "run_id":       data.get("run_id", jf.stem),
                "tickers":      data.get("tickers", []),
                "model":        data.get("model", "unknown"),
                "completed_at": data.get("completed_at", ""),
                "success":      data.get("success", False),
                "word_count":   len((data.get("final_report_md") or "").split()),
                "json_path":    str(jf),
                "md_path":      str(md_path) if md_path.exists() else None,
            })
        except Exception as exc:
            logger.warning("Could not read saved run %s: %s", jf, exc)
    return entries


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
