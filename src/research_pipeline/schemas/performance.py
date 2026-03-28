"""Performance attribution, benchmarking, and analytics schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Portfolio Snapshot (for historical tracking) ────────────────────────────

class PortfolioSnapshot(BaseModel):
    """Price-stamped portfolio at a point in time."""
    run_id: str
    snapshot_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    variant_name: str  # "balanced", "higher_return", "lower_volatility"
    positions: dict[str, float] = {}  # ticker -> weight_pct
    prices: dict[str, float] = {}  # ticker -> price at snapshot
    nav: float = 100.0  # normalized to 100 at inception
    benchmark_nav: float = 100.0


# ── Brinson-Hood-Beebower Attribution ───────────────────────────────────────

class BHBAttribution(BaseModel):
    """Brinson-Hood-Beebower return attribution decomposition."""
    run_id: str
    period_start: datetime
    period_end: datetime
    total_portfolio_return_pct: float = 0.0
    total_benchmark_return_pct: float = 0.0
    excess_return_pct: float = 0.0
    allocation_effect_pct: float = 0.0
    selection_effect_pct: float = 0.0
    interaction_effect_pct: float = 0.0
    sector_allocation: dict[str, float] = {}  # sector -> allocation effect
    sector_selection: dict[str, float] = {}  # sector -> selection effect


class CurrencyAttributionResult(BaseModel):
    """Decompose offshore returns into local, FX, and interaction effects."""

    base_currency: str = "AUD"
    foreign_currency: str = "USD"
    local_return_pct: float = 0.0
    currency_return_pct: float = 0.0
    interaction_return_pct: float = 0.0
    total_unhedged_return_pct: float = 0.0
    total_hedged_return_pct: float = 0.0


# ── Factor Attribution ──────────────────────────────────────────────────────

class FactorExposure(BaseModel):
    """Factor loadings for a single ticker."""
    ticker: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    market_beta: float = 1.0
    size_loading: float = 0.0  # SMB
    value_loading: float = 0.0  # HML
    momentum_loading: float = 0.0  # MOM / UMD
    quality_loading: float = 0.0
    volatility_loading: float = 0.0


class FactorAttribution(BaseModel):
    """Attribution of returns to factor exposures."""
    run_id: str
    period_start: datetime
    period_end: datetime
    total_return_pct: float = 0.0
    market_contribution_pct: float = 0.0
    size_contribution_pct: float = 0.0
    value_contribution_pct: float = 0.0
    momentum_contribution_pct: float = 0.0
    quality_contribution_pct: float = 0.0
    residual_alpha_pct: float = 0.0


# ── Benchmark Analytics ─────────────────────────────────────────────────────

class BenchmarkComparison(BaseModel):
    """Portfolio vs benchmark comparison."""
    run_id: str
    benchmark_name: str  # "SPY", "QQQ", "XLK", etc.
    period_days: int = 0
    portfolio_return_pct: float = 0.0
    benchmark_return_pct: float = 0.0
    excess_return_pct: float = 0.0
    tracking_error_pct: float = 0.0
    information_ratio: float = 0.0
    portfolio_sharpe: float = 0.0
    benchmark_sharpe: float = 0.0
    max_drawdown_portfolio_pct: float = 0.0
    max_drawdown_benchmark_pct: float = 0.0
    correlation: float = 0.0


# ── Thesis Tracking ────────────────────────────────────────────────────────

class ThesisStatus(str, Enum):
    ACTIVE = "active"
    CONFIRMED = "confirmed"
    CHALLENGED = "challenged"
    INVALIDATED = "invalidated"


class ThesisRecord(BaseModel):
    """Track a thesis from creation through validation."""
    thesis_id: str
    run_id: str  # originating run
    ticker: str
    thesis_text: str
    claim_ids: list[str] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: ThesisStatus = ThesisStatus.ACTIVE
    price_at_creation: Optional[float] = None
    current_price: Optional[float] = None
    return_since_pct: Optional[float] = None
    invalidation_trigger: str = ""
    notes: str = ""
    last_reviewed: Optional[datetime] = None


# ── VaR / Drawdown ──────────────────────────────────────────────────────────

class VaRResult(BaseModel):
    """Value at Risk computation result."""
    run_id: str
    method: str = "parametric"  # "parametric", "historical", "monte_carlo"
    confidence_level: float = 0.95
    holding_period_days: int = 1
    var_pct: float = 0.0  # portfolio VaR as percentage loss
    var_dollar: float = 0.0
    cvar_pct: float = 0.0  # conditional VaR (expected shortfall)
    cvar_dollar: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DrawdownAnalysis(BaseModel):
    """Maximum drawdown analysis."""
    run_id: str
    max_drawdown_pct: float = 0.0
    drawdown_start: Optional[datetime] = None
    drawdown_trough: Optional[datetime] = None
    recovery_date: Optional[datetime] = None
    recovery_days: Optional[int] = None
    current_drawdown_pct: float = 0.0
    underwater_days: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Liquidity Profile ──────────────────────────────────────────────────────

class LiquidityProfile(BaseModel):
    """Liquidity analysis for a single position."""
    ticker: str
    avg_daily_volume: float = 0.0  # shares
    avg_daily_value: float = 0.0  # dollars
    position_value: float = 0.0
    days_to_liquidate: float = 0.0  # at 20% of ADV
    liquidity_score: float = 5.0  # 0-10 (10 = most liquid)
    market_impact_estimate_bps: float = 0.0
