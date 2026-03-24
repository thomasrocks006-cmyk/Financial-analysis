"""A7 — Run Registry Service: log every run and replay context."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from research_pipeline.schemas.registry import (
    GoldenTest,
    HumanOverride,
    PromptVersion,
    RunRecord,
    RunStatus,
    SelfAudit,
)

logger = logging.getLogger(__name__)


class RunRegistryService:
    """Persistent run registry — every run is logged for reproducibility.

    Uses a JSON-file-based store (upgradeable to SQLite/Postgres).
    """

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir / "registry"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._runs_file = self.storage_dir / "runs.json"
        self._prompts_file = self.storage_dir / "prompt_versions.json"
        self._overrides_file = self.storage_dir / "overrides.json"

    # ── Run management ─────────────────────────────────────────────────
    def create_run(
        self,
        universe: list[str],
        config: dict[str, Any],
        agent_versions: dict[str, str] | None = None,
    ) -> RunRecord:
        """Create a new run and return its record."""
        run_id = f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        config_hash = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:16]

        record = RunRecord(
            run_id=run_id,
            universe=universe,
            config_hash=config_hash,
            agent_versions=agent_versions or {},
            status=RunStatus.INITIALIZED,
        )

        self._save_run(record)
        logger.info("Created run %s with %d tickers", run_id, len(universe))
        return record

    def update_run_status(self, run_id: str, status: RunStatus, **kwargs: Any) -> RunRecord:
        """Update the status of an existing run."""
        record = self.get_run(run_id)
        if record is None:
            raise ValueError(f"Run not found: {run_id}")
        record.status = status
        for k, v in kwargs.items():
            if hasattr(record, k):
                setattr(record, k, v)
        if status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.PUBLISHED):
            record.completed_at = datetime.now(timezone.utc)
        self._save_run(record)
        return record

    def mark_stage_complete(self, run_id: str, stage: int) -> None:
        record = self.get_run(run_id)
        if record and stage not in record.stages_completed:
            record.stages_completed.append(stage)
            record.stages_completed.sort()
            self._save_run(record)

    def mark_stage_failed(self, run_id: str, stage: int) -> None:
        record = self.get_run(run_id)
        if record and stage not in record.stages_failed:
            record.stages_failed.append(stage)
            self._save_run(record)

    def get_run(self, run_id: str) -> Optional[RunRecord]:
        runs = self._load_runs()
        return runs.get(run_id)

    def list_runs(self, limit: int = 20) -> list[RunRecord]:
        runs = self._load_runs()
        sorted_runs = sorted(runs.values(), key=lambda r: r.timestamp, reverse=True)
        return sorted_runs[:limit]

    # ── Override logging ───────────────────────────────────────────────
    def log_override(self, override: HumanOverride) -> None:
        overrides = self._load_json(self._overrides_file, [])
        overrides.append(override.model_dump(mode="json"))
        self._write_json(self._overrides_file, overrides)
        logger.info("Logged override %s for run %s", override.override_id, override.run_id)

    # ── Prompt versioning ──────────────────────────────────────────────
    def register_prompt(self, pv: PromptVersion) -> None:
        prompts = self._load_json(self._prompts_file, [])
        prompts.append(pv.model_dump(mode="json"))
        self._write_json(self._prompts_file, prompts)

    # ── Self-audit ─────────────────────────────────────────────────────
    def build_self_audit(self, run_id: str, claim_ledger: Any) -> SelfAudit:
        """Build self-audit scorecard from a claim ledger."""
        tier_mix: dict[str, int] = {}
        pass_count = caveat_count = fail_count = 0

        if hasattr(claim_ledger, "claims"):
            for claim in claim_ledger.claims:
                pass_count += claim.status.value == "pass"
                caveat_count += claim.status.value == "caveat"
                fail_count += claim.status.value == "fail"
            for source in getattr(claim_ledger, "sources", []):
                tier_key = f"tier_{source.tier.value}"
                tier_mix[tier_key] = tier_mix.get(tier_key, 0) + 1

        total = pass_count + caveat_count + fail_count
        score = (pass_count / total * 10) if total > 0 else 0

        return SelfAudit(
            run_id=run_id,
            source_tier_mix=tier_mix,
            claim_counts_pass=pass_count,
            claim_counts_caveat=caveat_count,
            claim_counts_fail=fail_count,
            unresolved_items_count=fail_count + caveat_count,
            publishability_score=round(score, 1),
        )

    # ── persistence helpers ────────────────────────────────────────────
    def _load_runs(self) -> dict[str, RunRecord]:
        data = self._load_json(self._runs_file, {})
        return {k: RunRecord(**v) for k, v in data.items()}

    def _save_run(self, record: RunRecord) -> None:
        runs = self._load_json(self._runs_file, {})
        runs[record.run_id] = record.model_dump(mode="json")
        self._write_json(self._runs_file, runs)

    def _load_json(self, path: Path, default: Any) -> Any:
        if path.exists():
            return json.loads(path.read_text())
        return default

    def _write_json(self, path: Path, data: Any) -> None:
        path.write_text(json.dumps(data, indent=2, default=str))
