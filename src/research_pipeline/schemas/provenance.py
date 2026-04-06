"""
src/research_pipeline/schemas/provenance.py
--------------------------------------------
Session 17 — Traceability & Provenance

Typed schemas for tracking the lineage of every data point and claim
throughout the pipeline.  Each stage produces a ProvenanceCard that
documents:
  • Inputs consumed (data sources, upstream stage outputs)
  • Outputs produced (artifacts, decisions)
  • Gate outcome and reasoning
  • Assumptions made
  • Agent involved and model used
  • Wall-clock timing

The ReportSection provenance links each section of the final report
back to the stage(s) and data sources that produced it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class DataSource(BaseModel):
    """A single data source consumed by a stage."""

    name: str
    source_type: str = "unknown"  # api | file | llm | upstream_stage | computed
    stage_origin: Optional[int] = None  # stage number that produced this
    freshness: Optional[str] = None  # e.g. "2024-01-15" or "live"
    confidence: Optional[float] = None  # 0.0-1.0


class StageOutput(BaseModel):
    """A single output produced by a stage."""

    name: str
    output_type: str = "data"  # data | artifact | decision | metric
    description: str = ""
    artifact_path: Optional[str] = None


class ProvenanceCard(BaseModel):
    """Provenance record for a single pipeline stage.

    Built automatically after each stage completes.  Consumers can
    render these as expandable cards in the UI to show full lineage.
    """

    stage_num: int
    stage_label: str
    run_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Who did the work
    agent_name: Optional[str] = None
    model_used: Optional[str] = None
    model_temperature: Optional[float] = None

    # What went in
    inputs: list[DataSource] = Field(default_factory=list)

    # What came out
    outputs: list[StageOutput] = Field(default_factory=list)

    # Gate outcome
    gate_passed: Optional[bool] = None
    gate_reason: str = ""
    gate_blockers: list[str] = Field(default_factory=list)

    # Assumptions
    assumptions: list[str] = Field(default_factory=list)

    # Timing
    duration_ms: float = 0.0

    # Error info
    error: Optional[str] = None


class ReportSectionProvenance(BaseModel):
    """Links a section of the final report to its source stages/data."""

    section_title: str
    section_index: int = 0
    source_stages: list[int] = Field(default_factory=list)
    source_agents: list[str] = Field(default_factory=list)
    data_sources: list[DataSource] = Field(default_factory=list)
    confidence_level: str = "medium"  # low | medium | high
    methodology_tags: list[str] = Field(default_factory=list)


class ProvenancePacket(BaseModel):
    """Complete provenance record for an entire pipeline run.

    Aggregates all per-stage ProvenanceCards and report-section
    provenance into a single packet for storage and UI display.
    """

    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stage_cards: list[ProvenanceCard] = Field(default_factory=list)
    report_sections: list[ReportSectionProvenance] = Field(default_factory=list)
    total_stages: int = 15
    stages_with_provenance: int = 0
    completeness_pct: float = 0.0

    def compute_completeness(self) -> None:
        """Calculate how complete the provenance record is."""
        self.stages_with_provenance = len(self.stage_cards)
        if self.total_stages > 0:
            self.completeness_pct = round(
                (self.stages_with_provenance / self.total_stages) * 100, 1
            )
