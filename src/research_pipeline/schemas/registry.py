"""Run registry and governance schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    INITIALIZED = "initialized"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PUBLISHED = "published"


class RunRecord(BaseModel):
    """A complete run registry entry — every run is logged."""
    run_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    universe: list[str] = []
    config_hash: str = ""
    agent_versions: dict[str, str] = {}
    prompt_versions: dict[str, str] = {}
    dataset_versions: dict[str, str] = {}
    status: RunStatus = RunStatus.INITIALIZED
    stages_completed: list[int] = []
    stages_failed: list[int] = []
    outputs_generated: list[str] = []
    final_gate_outcome: str = ""
    overrides: list["HumanOverride"] = []
    metadata: dict[str, Any] = {}
    completed_at: Optional[datetime] = None


class HumanOverride(BaseModel):
    """When a human overrides an automated gate or decision."""
    override_id: str
    run_id: str
    approver: str
    stage: str
    reason: str
    original_status: str
    override_status: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PromptVersion(BaseModel):
    """Track prompt/agent versions for reproducibility."""
    agent_name: str
    prompt_version: str
    prompt_hash: str
    changed_at: datetime = Field(default_factory=datetime.utcnow)
    owner: str = ""
    regression_status: str = "untested"


class GoldenTest(BaseModel):
    """A regression test case."""
    test_id: str
    category: str  # claim_classification, reconciliation, gating, etc.
    input_fixture: dict[str, Any] = {}
    expected_output_rule: str = ""
    last_run: Optional[datetime] = None
    passed: Optional[bool] = None


class SelfAudit(BaseModel):
    """Self-audit scorecard appended to every report."""
    run_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source_tier_mix: dict[str, int] = {}  # tier -> count
    claim_counts_pass: int = 0
    claim_counts_caveat: int = 0
    claim_counts_fail: int = 0
    stale_data_summary: str = ""
    unresolved_items_count: int = 0
    publishability_score: float = 0.0
    institutional_ceiling_statement: str = (
        "This report uses public-source data only. Broker consensus history, "
        "revision depth, and premium comp data remain structurally unavailable "
        "without licensed terminal data (Bloomberg / FactSet / LSEG)."
    )
