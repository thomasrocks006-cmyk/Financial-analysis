"""Shared helpers for stage persistence and gate bookkeeping.

This module is a first step in decomposing `engine.py` by moving generic
stage-runtime concerns out of the main pipeline orchestration class.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from research_pipeline.pipeline.gates import GateResult
from research_pipeline.schemas.events import STAGE_LABELS

logger = logging.getLogger(__name__)


def persist_stage_output(
    *,
    stage_outputs: dict[int, Any],
    storage_dir: Path,
    run_id: str,
    stage: int,
    data: Any,
) -> Path:
    """Persist stage output to in-memory state and disk."""
    stage_outputs[stage] = data
    output_dir = storage_dir / "artifacts" / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / f"stage_{stage:02d}.json"
    filepath.write_text(json.dumps(data, indent=2, default=str))
    logger.info("Stage %d output saved to %s", stage, filepath)
    return filepath


def build_provenance_for_stage(
    *,
    provenance: Any,
    stage: int,
    data: Any,
    gate_results: dict[int, GateResult],
    stage_timings: dict[int, float],
) -> None:
    """Build a provenance card for a completed stage when enabled."""
    if provenance is None:
        return
    gate_data = gate_results.get(stage)
    provenance.build_stage_card(
        stage_num=stage,
        stage_label=STAGE_LABELS.get(stage, f"Stage {stage}"),
        stage_output=data,
        gate_passed=gate_data.passed if gate_data else None,
        gate_reason=gate_data.reason if gate_data else "",
        gate_blockers=gate_data.blockers if gate_data else [],
        duration_ms=stage_timings.get(stage, 0.0),
        error=None,
    )


def record_gate_result(
    *,
    gate_results: dict[int, GateResult],
    registry: Any,
    run_id: str,
    gate_result: GateResult,
) -> bool:
    """Store the gate result and mirror completion/failure to the registry."""
    gate_results[gate_result.stage] = gate_result
    if gate_result.passed:
        logger.info("Gate %d PASSED: %s", gate_result.stage, gate_result.reason)
        registry.mark_stage_complete(run_id, gate_result.stage)
    else:
        logger.error(
            "Gate %d FAILED: %s — %s",
            gate_result.stage,
            gate_result.reason,
            gate_result.blockers,
        )
        registry.mark_stage_failed(run_id, gate_result.stage)
    return gate_result.passed
