"""Load and validate pipeline YAML configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel, Field

# ── Sector routing: maps analyst role → list of covered tickers ──────────────
# ARC-5: externalised from engine.py hardcoded sets — edit here, engine picks up.
# Tickers not in any list are handled by GenericSectorAnalystAgent as a fallback.
SECTOR_ROUTING: dict[str, list[str]] = {
    "compute":         ["NVDA", "AVGO", "TSM", "AMD", "ANET"],
    "power_energy":    ["CEG", "VST", "GEV", "NLR"],
    "infrastructure":  ["PWR", "ETN", "HUBB", "APH", "FIX", "FCX", "BHP", "NXT"],
}

# ── ASX universe — Session 12 ─────────────────────────────────────────────
# P0 ASX tickers for the AU market support expansion.
# Suffixed with .AX for yfinance compatibility; benchmark ^AXJO (ASX 200).
ASX_UNIVERSE: list[str] = [
    "CBA.AX",   # Commonwealth Bank of Australia — largest AU bank
    "BHP.AX",   # BHP Group — global mining, already in US universe
    "CSL.AX",   # CSL Limited — AU biotech, major super fund holding
    "NAB.AX",   # National Australia Bank
    "WBC.AX",   # Westpac
    "ANZ.AX",   # ANZ Group
    "MQG.AX",   # Macquarie Group
    "WES.AX",   # Wesfarmers — diversified AU conglomerate
    "GMG.AX",   # Goodman Group — industrial REIT (data centre exposure)
    "WOW.AX",   # Woolworths Group — AU consumer staples
]

# ── Market priority tiers — Session 12 ────────────────────────────────────

class MarketEntry(BaseModel):
    """A single market in the MarketConfig universe."""
    market_name: str
    priority: Literal["P0", "P1", "P2", "P3"] = "P1"
    benchmark_index: str = ""
    benchmark_ticker: str = ""          # yfinance / FRED ticker for benchmark
    currency: str = "USD"
    is_au_market: bool = False
    default_tickers: list[str] = Field(default_factory=list)
    sector_routing_key: Optional[str] = None   # maps to SECTOR_ROUTING key if applicable
    notes: str = ""


class MarketConfig(BaseModel):
    """Multi-market configuration for the pipeline.

    Session 12: formal market scope beyond the original US AI infra universe.
    Priority levels:
      P0 — fully built and actively used
      P1 — partial or planned for current session block
      P2 — planned future session
      P3 — low priority / aspirational
    """
    markets: list[MarketEntry] = Field(default_factory=list)
    fred_api_key: Optional[str] = None
    default_currency: str = "AUD"    # AU-based client office default presentation currency

    def get_p0_markets(self) -> list[MarketEntry]:
        return [m for m in self.markets if m.priority == "P0"]

    def get_au_markets(self) -> list[MarketEntry]:
        return [m for m in self.markets if m.is_au_market]

    def get_all_default_tickers(self) -> list[str]:
        """Return all default tickers across all P0+P1 markets."""
        tickers: list[str] = []
        for m in self.markets:
            if m.priority in ("P0", "P1"):
                tickers.extend(m.default_tickers)
        return list(dict.fromkeys(tickers))  # deduplicated, order-preserving


# ── Default MarketConfig instance ─────────────────────────────────────────
DEFAULT_MARKET_CONFIG = MarketConfig(
    markets=[
        MarketEntry(
            market_name="US Large Cap / AI Infrastructure",
            priority="P0",
            benchmark_index="S&P 500 / NASDAQ-100",
            benchmark_ticker="^GSPC",
            currency="USD",
            is_au_market=False,
            default_tickers=["NVDA", "AVGO", "TSM", "AMD", "ANET", "CEG", "VST", "GEV",
                              "NLR", "PWR", "ETN", "HUBB", "APH", "FIX", "FCX", "BHP", "NXT"],
            notes="Primary AI infrastructure universe — fully built",
        ),
        MarketEntry(
            market_name="ASX (Australian Equities)",
            priority="P0",
            benchmark_index="ASX 200",
            benchmark_ticker="^AXJO",
            currency="AUD",
            is_au_market=True,
            default_tickers=ASX_UNIVERSE,
            notes="Session 12 build — AU domestic equities, super fund default universe",
        ),
        MarketEntry(
            market_name="AU Fixed Income",
            priority="P1",
            benchmark_index="Bloomberg AusBond",
            benchmark_ticker="^IRZ25.AX",
            currency="AUD",
            is_au_market=True,
            default_tickers=[],
            notes="AU 10Y government bond, IG credit spreads — Session 12 partial",
        ),
        MarketEntry(
            market_name="US Broad Market",
            priority="P1",
            benchmark_index="S&P 500",
            benchmark_ticker="^GSPC",
            currency="USD",
            is_au_market=False,
            default_tickers=["SPY", "IWM"],
            notes="Russell 2000 + S&P 500 Equal Weight — future session",
        ),
        MarketEntry(
            market_name="Global Thematic / Tech",
            priority="P1",
            benchmark_index="MSCI World Tech",
            benchmark_ticker="URTH",
            currency="USD",
            is_au_market=False,
            default_tickers=[],
            notes="MSCI World thematic overlay — future session",
        ),
        MarketEntry(
            market_name="Asian Technology",
            priority="P2",
            benchmark_index="Nikkei 225 / KOSPI",
            benchmark_ticker="^N225",
            currency="JPY",
            is_au_market=False,
            default_tickers=["TSM", "6758.T", "005930.KS"],
            notes="Taiwan/Japan/Korea AI supply chain — P2",
        ),
        MarketEntry(
            market_name="European Equities",
            priority="P3",
            benchmark_index="Euro Stoxx 50",
            benchmark_ticker="^STOXX50E",
            currency="EUR",
            is_au_market=False,
            default_tickers=[],
            notes="Diversification overlay — minimal current exposure",
        ),
    ]
)

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
    # Session 12: multi-market config — AU/US/Global market scope
    market_config: MarketConfig = Field(default_factory=lambda: DEFAULT_MARKET_CONFIG)
    portfolio_variants: list[str] = Field(
        default=["balanced", "higher_return", "lower_volatility"]
    )
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
        portfolio_variants=portfolio_raw.get("required_variants", PipelineConfig.model_fields["portfolio_variants"].default),
        report_sections=report_raw.get("required_sections", PipelineConfig.model_fields["report_sections"].default),
        test_categories=raw.get("testing", {}).get("categories", PipelineConfig.model_fields["test_categories"].default),
    )
