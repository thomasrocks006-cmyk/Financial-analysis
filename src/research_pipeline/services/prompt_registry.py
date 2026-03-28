"""Prompt Registry — version tracking, drift detection, and regression harness for agent prompts."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PromptVersion(BaseModel):
    """A versioned snapshot of an agent prompt."""
    prompt_id: str  # e.g. "sector_analyst_compute"
    version: int = 1
    prompt_hash: str
    prompt_text: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = {}
    regression_status: str = "untested"  # "untested", "passed", "failed"
    regression_run_id: str = ""


class PromptDriftReport(BaseModel):
    """Report of prompt changes between runs."""
    agent_name: str
    previous_hash: str
    current_hash: str
    changed: bool = False
    previous_version: int = 0
    current_version: int = 0
    regression_required: bool = False


class PromptRegistry:
    """Track prompt versions, detect drift, and manage regression testing — no LLM.

    Every agent prompt is hashed and versioned. When a prompt changes,
    the system flags it for regression testing via the golden test suite.
    """

    def __init__(self, storage_dir: Path | str = "data/prompt_registry"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._registry_file = self.storage_dir / "registry.json"
        self._registry: dict[str, list[dict[str, Any]]] = self._load_registry()

    def _load_registry(self) -> dict[str, list[dict[str, Any]]]:
        if self._registry_file.exists():
            try:
                return json.loads(self._registry_file.read_text())
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_registry(self) -> None:
        self._registry_file.write_text(
            json.dumps(self._registry, indent=2, default=str)
        )

    @staticmethod
    def compute_hash(prompt_text: str) -> str:
        """Compute a deterministic hash of a prompt."""
        # Normalize whitespace for consistent hashing
        normalized = " ".join(prompt_text.split())
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def register_prompt(
        self,
        prompt_id: str,
        prompt_text: str,
        metadata: dict[str, Any] | None = None,
    ) -> PromptVersion:
        """Register a prompt version. Creates a new version if the prompt has changed."""
        current_hash = self.compute_hash(prompt_text)

        # Check if this prompt already exists with same hash
        versions = self._registry.get(prompt_id, [])
        if versions:
            latest = versions[-1]
            if latest.get("prompt_hash") == current_hash:
                return PromptVersion(**latest)

        # New version
        new_version = len(versions) + 1
        version = PromptVersion(
            prompt_id=prompt_id,
            version=new_version,
            prompt_hash=current_hash,
            prompt_text=prompt_text,
            metadata=metadata or {},
        )

        if prompt_id not in self._registry:
            self._registry[prompt_id] = []
        self._registry[prompt_id].append(version.model_dump(mode="json"))
        self._save_registry()

        if new_version > 1:
            logger.warning(
                "Prompt %s changed: v%d → v%d (hash: %s → %s). Regression required.",
                prompt_id, new_version - 1, new_version,
                versions[-1].get("prompt_hash", "unknown"), current_hash,
            )
        else:
            logger.info("Prompt %s registered: v1 (hash: %s)", prompt_id, current_hash)

        return version

    def get_latest_version(self, prompt_id: str) -> PromptVersion | None:
        """Get the latest version of a prompt."""
        versions = self._registry.get(prompt_id, [])
        if not versions:
            return None
        return PromptVersion(**versions[-1])

    def get_version(self, prompt_id: str, version: int) -> PromptVersion | None:
        """Get a specific version of a prompt."""
        versions = self._registry.get(prompt_id, [])
        for v in versions:
            if v.get("version") == version:
                return PromptVersion(**v)
        return None

    def check_drift(self, prompt_id: str, current_text: str) -> PromptDriftReport:
        """Check if a prompt has drifted from its registered version."""
        current_hash = self.compute_hash(current_text)
        latest = self.get_latest_version(prompt_id)

        if not latest:
            return PromptDriftReport(
                agent_name=prompt_id,
                previous_hash="",
                current_hash=current_hash,
                changed=True,
                regression_required=True,
            )

        changed = latest.prompt_hash != current_hash
        return PromptDriftReport(
            agent_name=prompt_id,
            previous_hash=latest.prompt_hash,
            current_hash=current_hash,
            changed=changed,
            previous_version=latest.version,
            current_version=latest.version + 1 if changed else latest.version,
            regression_required=changed,
        )

    def check_all_drift(self, current_prompts: dict[str, str]) -> list[PromptDriftReport]:
        """Check drift for all registered prompts."""
        reports = []
        for prompt_id, text in current_prompts.items():
            reports.append(self.check_drift(prompt_id, text))
        return reports

    def mark_regression_passed(self, prompt_id: str, run_id: str) -> None:
        """Mark the latest version of a prompt as regression-passed."""
        versions = self._registry.get(prompt_id, [])
        if versions:
            versions[-1]["regression_status"] = "passed"
            versions[-1]["regression_run_id"] = run_id
            self._save_registry()

    def mark_regression_failed(self, prompt_id: str, run_id: str) -> None:
        """Mark the latest version as regression-failed."""
        versions = self._registry.get(prompt_id, [])
        if versions:
            versions[-1]["regression_status"] = "failed"
            versions[-1]["regression_run_id"] = run_id
            self._save_registry()

    def get_all_prompts(self) -> dict[str, PromptVersion]:
        """Get latest version of all registered prompts."""
        result = {}
        for prompt_id, versions in self._registry.items():
            if versions:
                result[prompt_id] = PromptVersion(**versions[-1])
        return result

    @property
    def stats(self) -> dict[str, Any]:
        """Registry statistics."""
        total_prompts = len(self._registry)
        total_versions = sum(len(v) for v in self._registry.values())
        untested = sum(
            1 for versions in self._registry.values()
            if versions and versions[-1].get("regression_status") == "untested"
        )
        return {
            "total_prompts": total_prompts,
            "total_versions": total_versions,
            "untested_versions": untested,
        }
