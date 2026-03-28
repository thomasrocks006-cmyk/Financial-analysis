"""Load and validate pipeline YAML configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

# ── Sector routing: maps analyst role → list of covered tickers ──────────────
# ARC-5: externalised from engine.py hardcoded sets — edit here, engine picks up.
# Tickers not in any list are handled by GenericSectorAnalystAgent as a fallback.
SECTOR_ROUTING: dict[str, list[str]] = {
    "compute": ["NVDA", "AVGO", "TSM", "AMD", "ANET"],
    "power_energy": ["CEG", "VST", "GEV", "NLR"],
    "infrastructure": ["PWR", "ETN", "HUBB", "APH", "FIX", "FCX", "BHP", "NXT"],
}


# ── Threshold sub-models ────────────────────────────────────────────────────
class ReconciliationThresholds(BaseModel):
    price_drift_amber_pct: float = 0.5
    price_drift_red_pct: float = 2.0
    target_divergence_amber_pct: float = 5.0
    target_divergence_red_pct: float = 15.0
    estimate_divergence_amber_pct: float = 5.0
    estimate_divergence_red_pct: float = 20.0
    stale_data_hours: int = 24


class PublishGateThresholds(BaseModel):
    max_fail_claims: int = 0
    max_disclosure_claims: int = 3
    require_methodology_tag_for_targets: bool = True
    require_date_for_all_numbers: bool = True
    require_traceable_claims: bool = True


class DataQualityThresholds(BaseModel):
    require_lineage_for_all_final_fields: bool = True
    allow_duplicate_rows: bool = False
    allow_currency_mismatch: bool = False


class Thresholds(BaseModel):
    reconciliation: ReconciliationThresholds = ReconciliationThresholds()
    publish_gate: PublishGateThresholds = PublishGateThresholds()
    data_quality: DataQualityThresholds = DataQualityThresholds()


# ── Stage definition ────────────────────────────────────────────────────────
class StageConfig(BaseModel):
    name: str
    owners: list[str] = []


# ── Top-level pipeline config ──────────────────────────────────────────────
class PipelineConfig(BaseModel):
    version: str = "v8"
    project_name: str = "ai_infrastructure_research_platform"
    thresholds: Thresholds = Thresholds()
    stages: dict[int, StageConfig] = {}
    # ARC-5: sector routing — override defaults by providing a config file entry
    sector_routing: dict[str, list[str]] = Field(default_factory=lambda: dict(SECTOR_ROUTING))
    portfolio_variants: list[str] = Field(default=["balanced", "higher_return", "lower_volatility"])
    report_sections: list[str] = Field(
        default=[
            "executive_summary",
            "methodology",
            "stock_cards",
            "valuation_appendix",
            "risk_appendix",
            "self_audit_appendix",
            "claim_register_appendix",
        ]
    )
    test_categories: list[str] = Field(
        default=[
            "claim_classification",
            "reconciliation",
            "gating",
            "portfolio_output_stability",
            "report_generation",
        ]
    )


def load_pipeline_config(config_path: Path | str | None = None) -> PipelineConfig:
    """Load pipeline config from YAML, falling back to defaults."""
    if config_path is None:
        return PipelineConfig()

    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    with open(path, "r") as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    # Parse thresholds
    thresholds_raw = raw.get("thresholds", {})
    thresholds = Thresholds(
        reconciliation=ReconciliationThresholds(**thresholds_raw.get("reconciliation", {})),
        publish_gate=PublishGateThresholds(**thresholds_raw.get("publish_gate", {})),
        data_quality=DataQualityThresholds(**thresholds_raw.get("data_quality", {})),
    )

    # Parse stages
    stages = {}
    for k, v in raw.get("stages", {}).items():
        stages[int(k)] = StageConfig(**v)

    # Parse outputs
    portfolio_raw = raw.get("portfolio_outputs", {})
    report_raw = raw.get("report_outputs", {})

    return PipelineConfig(
        version=raw.get("version", "v8"),
        project_name=raw.get("project_name", "ai_infrastructure_research_platform"),
        thresholds=thresholds,
        stages=stages,
        portfolio_variants=portfolio_raw.get(
            "required_variants", PipelineConfig.model_fields["portfolio_variants"].default
        ),
        report_sections=report_raw.get(
            "required_sections", PipelineConfig.model_fields["report_sections"].default
        ),
        test_categories=raw.get("testing", {}).get(
            "categories", PipelineConfig.model_fields["test_categories"].default
        ),
    )
