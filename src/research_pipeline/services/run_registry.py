"""A7 — Run Registry Service: log every run and replay context."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from research_pipeline.schemas.registry import (
    HumanOverride,
    PromptVersion,
    RunRecord,
    RunStatus,
    SelfAudit,
)

logger = logging.getLogger(__name__)


class RunRegistryService:
    """Persistent run registry — every run is logged for reproducibility.

    Uses a SQLite-backed store with legacy JSON migration for backward
    compatibility with earlier sessions.
    """

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir / "registry"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self.storage_dir / "registry.db"
        self._runs_file = self.storage_dir / "runs.json"
        self._prompts_file = self.storage_dir / "prompt_versions.json"
        self._overrides_file = self.storage_dir / "overrides.json"
        self._init_db()
        self._migrate_legacy_json_if_needed()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    status TEXT NOT NULL,
                    completed_at TEXT,
                    record_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS prompt_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_name TEXT NOT NULL,
                    changed_at TEXT NOT NULL,
                    prompt_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS overrides (
                    override_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    override_json TEXT NOT NULL
                );
                """
            )

    def _migrate_legacy_json_if_needed(self) -> None:
        """One-time import from historical JSON registry files."""
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM runs").fetchone()
            existing_runs = int(row["count"]) if row else 0
        if existing_runs > 0:
            return

        legacy_runs = self._load_json(self._runs_file, {})
        if isinstance(legacy_runs, dict) and legacy_runs:
            for payload in legacy_runs.values():
                try:
                    self._upsert_run(RunRecord.model_validate(payload))
                except Exception as exc:  # pragma: no cover
                    logger.warning("Failed to migrate legacy run registry row: %s", exc)

        legacy_prompts = self._load_json(self._prompts_file, [])
        if isinstance(legacy_prompts, list):
            for payload in legacy_prompts:
                try:
                    self._insert_prompt(PromptVersion.model_validate(payload))
                except Exception as exc:  # pragma: no cover
                    logger.warning("Failed to migrate legacy prompt registry row: %s", exc)

        legacy_overrides = self._load_json(self._overrides_file, [])
        if isinstance(legacy_overrides, list):
            for payload in legacy_overrides:
                try:
                    self._insert_override(HumanOverride.model_validate(payload))
                except Exception as exc:  # pragma: no cover
                    logger.warning("Failed to migrate legacy override row: %s", exc)

    # ── Run management ─────────────────────────────────────────────────
    def create_run(
        self,
        universe: list[str],
        config: dict[str, Any],
        agent_versions: dict[str, str] | None = None,
    ) -> RunRecord:
        """Create a new run and return its record."""
        run_id = (
            f"run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        )
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

    def update_run(self, record: RunRecord) -> None:
        """Persist an already-mutated RunRecord back to storage."""
        self._save_run(record)
        logger.debug("Updated run record %s", record.run_id)

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

    def delete_run(self, run_id: str) -> bool:
        """Delete a run from the registry store."""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
            deleted = cur.rowcount > 0
        return deleted

    # ── Override logging ───────────────────────────────────────────────
    def log_override(self, override: HumanOverride) -> None:
        self._insert_override(override)
        logger.info("Logged override %s for run %s", override.override_id, override.run_id)

    # ── Prompt versioning ──────────────────────────────────────────────
    def register_prompt(self, pv: PromptVersion) -> None:
        self._insert_prompt(pv)

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
        with self._connect() as conn:
            rows = conn.execute("SELECT run_id, record_json FROM runs").fetchall()
        return {
            str(row["run_id"]): RunRecord.model_validate(json.loads(str(row["record_json"])))
            for row in rows
        }

    def _save_run(self, record: RunRecord) -> None:
        self._upsert_run(record)

    def _upsert_run(self, record: RunRecord) -> None:
        payload = record.model_dump(mode="json")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, timestamp, status, completed_at, record_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    timestamp = excluded.timestamp,
                    status = excluded.status,
                    completed_at = excluded.completed_at,
                    record_json = excluded.record_json
                """,
                (
                    record.run_id,
                    record.timestamp.isoformat(),
                    record.status.value,
                    record.completed_at.isoformat() if record.completed_at else None,
                    json.dumps(payload, default=str),
                ),
            )

    def _insert_prompt(self, pv: PromptVersion) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO prompt_versions (agent_name, changed_at, prompt_json)
                VALUES (?, ?, ?)
                """,
                (
                    pv.agent_name,
                    pv.changed_at.isoformat(),
                    pv.model_dump_json(),
                ),
            )

    def _insert_override(self, override: HumanOverride) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO overrides (override_id, run_id, timestamp, override_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    override.override_id,
                    override.run_id,
                    override.timestamp.isoformat(),
                    override.model_dump_json(),
                ),
            )

    def _load_json(self, path: Path, default: Any) -> Any:
        if path.exists():
            return json.loads(path.read_text())
        return default

    def _write_json(self, path: Path, data: Any) -> None:
        path.write_text(json.dumps(data, indent=2, default=str))
