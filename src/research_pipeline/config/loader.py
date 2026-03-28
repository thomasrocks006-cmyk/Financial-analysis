"""Load and validate pipeline YAML configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


DEFAULT_SECTOR_ROUTING: dict[str, list[str]] = {
    "compute": ["NVDA", "AVGO", "TSM", "AMD", "ANET", "MRVL", "QCOM", "INTC"],
    "power": ["CEG", "VST", "GEV", "NLR"],
    "infrastructure": [
        "PWR",
        "ETN",
        "HUBB",
        "APH",
        "FIX",
        "FCX",
        "BHP",
        "BHP.AX",
        "NXT",
        "NXT.AX",
        "CBA.AX",
        "CSL.AX",
    ],
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
    reconciliation: ReconciliationThresholds = Field(default_factory=ReconciliationThresholds)
    publish_gate: PublishGateThresholds = Field(default_factory=PublishGateThresholds)
    data_quality: DataQualityThresholds = Field(default_factory=DataQualityThresholds)


class MarketConfig(BaseModel):
    primary_market: str = "US"
    supported_markets: list[str] = Field(default_factory=lambda: ["US", "AU"])
    benchmark: str = "SPY"
    benchmark_fallback: str = "^AXJO"
    aud_usd_symbol: str = "AUDUSD=X"
    asx_suffix: str = ".AX"


class LLMConfig(BaseModel):
    preferred_provider: str = "anthropic"
    fallback_chain: list[str] = Field(
        default_factory=lambda: ["anthropic", "openai", "azure_openai", "gemini", "local_stub"]
    )
    azure_deployment: str = ""
    local_stub_enabled: bool = True


class AUClientConfig(BaseModel):
    client_type: str = "institutional"
    residency: str = "AU"
    super_mandate_type: str = "growth"
    include_afsl_disclosure: bool = True
    include_fsg_notice: bool = True
    include_asic_notice: bool = True
    smsf_tax_rate: float = 0.15
    cgt_discount_pct: float = 50.0


# ── Stage definition ────────────────────────────────────────────────────────
class StageConfig(BaseModel):
    name: str
    owners: list[str] = Field(default_factory=list)


# ── Top-level pipeline config ──────────────────────────────────────────────
class PipelineConfig(BaseModel):
    version: str = "v8"
    project_name: str = "ai_infrastructure_research_platform"
    thresholds: Thresholds = Field(default_factory=Thresholds)
    stages: dict[int, StageConfig] = Field(default_factory=dict)
    sector_routing: dict[str, list[str]] = Field(
        default_factory=lambda: {k: list(v) for k, v in DEFAULT_SECTOR_ROUTING.items()}
    )
    market: MarketConfig = Field(default_factory=MarketConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    au_client: AUClientConfig = Field(default_factory=AUClientConfig)
    portfolio_variants: list[str] = Field(
        default_factory=lambda: ["balanced", "higher_return", "lower_volatility"]
    )
    report_sections: list[str] = Field(
        default_factory=lambda: [
            "executive_summary",
            "methodology",
            "stock_cards",
            "valuation_appendix",
            "risk_appendix",
            "self_audit_appendix",
            "claim_register_appendix",
            "disclosures",
        ]
    )
    test_categories: list[str] = Field(
        default_factory=lambda: [
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

    with open(path, "r", encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    thresholds_raw = raw.get("thresholds", {})
    thresholds = Thresholds(
        reconciliation=ReconciliationThresholds(**thresholds_raw.get("reconciliation", {})),
        publish_gate=PublishGateThresholds(**thresholds_raw.get("publish_gate", {})),
        data_quality=DataQualityThresholds(**thresholds_raw.get("data_quality", {})),
    )

    stages: dict[int, StageConfig] = {}
    for k, v in raw.get("stages", {}).items():
        stages[int(k)] = StageConfig(**v)

    portfolio_raw = raw.get("portfolio_outputs", {})
    report_raw = raw.get("report_outputs", {})

    return PipelineConfig(
        version=raw.get("version", "v8"),
        project_name=raw.get("project_name", "ai_infrastructure_research_platform"),
        thresholds=thresholds,
        stages=stages,
        sector_routing=raw.get("sector_routing", DEFAULT_SECTOR_ROUTING),
        market=MarketConfig(**raw.get("market", {})),
        llm=LLMConfig(**raw.get("llm", {})),
        au_client=AUClientConfig(**raw.get("au_client", {})),
        portfolio_variants=portfolio_raw.get(
            "required_variants",
            PipelineConfig.model_fields["portfolio_variants"].default_factory(),
        ),
        report_sections=report_raw.get(
            "required_sections",
            PipelineConfig.model_fields["report_sections"].default_factory(),
        ),
        test_categories=raw.get(
            "testing",
            {},
        ).get(
            "categories",
            PipelineConfig.model_fields["test_categories"].default_factory(),
        ),
    )
