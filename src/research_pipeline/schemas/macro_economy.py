"""Session 12 — Macro Economy schemas.

Defines the structured Pydantic models consumed and produced by:
  - EconomicIndicatorService  (raw data fetch + cache)
  - MacroScenarioService      (scenario matrix builder)
  - EconomyAnalystAgent       (LLM AU/US macro analyst)
  - MacroStrategistAgent      (extended with AU/US regime flags)
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────


class ScenarioType(str, Enum):
    BASE = "base"
    BULL = "bull"
    BEAR = "bear"


class RBAStance(str, Enum):
    HIKING = "hiking"
    ON_HOLD = "on_hold"
    CUTTING = "cutting"
    UNKNOWN = "unknown"


class FedStance(str, Enum):
    HIKING = "hiking"
    ON_HOLD = "on_hold"
    CUTTING = "cutting"
    UNKNOWN = "unknown"


class HousingTrend(str, Enum):
    ACCELERATING = "accelerating"
    STABLE = "stable"
    CORRECTING = "correcting"
    UNKNOWN = "unknown"


class AudUsdDirection(str, Enum):
    STRENGTHENING = "strengthening"
    STABLE = "stable"
    WEAKENING = "weakening"
    UNKNOWN = "unknown"


class InflationTrend(str, Enum):
    ABOVE_TARGET = "above_target"
    ON_TARGET = "on_target"
    BELOW_TARGET = "below_target"
    UNKNOWN = "unknown"


# ── EconomicIndicators — raw data from FRED / RBA / ABS ───────────────────


class AustralianIndicators(BaseModel):
    """Key economic indicators for Australia."""

    rba_cash_rate_pct: Optional[float] = None  # e.g. 4.35
    rba_cash_rate_outlook: Optional[str] = None  # "on-hold into 2025"
    au_cpi_yoy_pct: Optional[float] = None  # trimmed mean CPI y/y
    au_cpi_trimmed_mean_pct: Optional[float] = None  # trimmed mean (RBA target measure)
    au_unemployment_rate_pct: Optional[float] = None
    au_wpi_yoy_pct: Optional[float] = None  # Wage Price Index y/y
    au_gdp_growth_qoq_pct: Optional[float] = None
    au_housing_price_index_change_pct: Optional[float] = None
    au_auction_clearance_rate_pct: Optional[float] = None
    au_credit_growth_yoy_pct: Optional[float] = None
    au_10y_government_yield_pct: Optional[float] = None
    au_3y_government_yield_pct: Optional[float] = None
    aud_usd: Optional[float] = None  # spot rate
    data_freshness: str = "synthetic_fallback"


class USIndicators(BaseModel):
    """Key economic indicators for the United States."""

    fed_funds_rate_pct: Optional[float] = None  # upper bound target
    fed_funds_futures_1y: Optional[float] = None  # market-implied 1Y forward
    us_cpi_yoy_pct: Optional[float] = None
    us_pce_yoy_pct: Optional[float] = None  # Fed preferred measure
    us_core_pce_yoy_pct: Optional[float] = None
    us_unemployment_rate_pct: Optional[float] = None
    us_nonfarm_payrolls_change_k: Optional[float] = None  # thousands
    us_gdp_growth_qoq_annualised_pct: Optional[float] = None
    us_ism_manufacturing: Optional[float] = None
    us_ism_services: Optional[float] = None
    us_10y_treasury_yield_pct: Optional[float] = None
    us_2y_treasury_yield_pct: Optional[float] = None
    us_yield_curve_spread_10y_2y: Optional[float] = None
    us_hy_spread_bps: Optional[float] = None  # high yield credit spread
    us_ig_spread_bps: Optional[float] = None  # investment grade spread
    data_freshness: str = "synthetic_fallback"


class EconomicIndicators(BaseModel):
    """Aggregated AU + US economic indicators from EconomicIndicatorService.

    This is the primary input to MacroScenarioService and EconomyAnalystAgent.
    Data sourced from: FRED API (US), RBA Statistical Tables (AU), ABS (AU).
    """

    run_id: str
    fetch_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    au: AustralianIndicators = Field(default_factory=AustralianIndicators)
    us: USIndicators = Field(default_factory=USIndicators)
    # Global
    vix: Optional[float] = None
    global_pmi_composite: Optional[float] = None
    # Data quality
    is_live_data: bool = False
    sources_used: list[str] = Field(default_factory=list)
    fetch_errors: list[str] = Field(default_factory=list)


# ── MacroScenario — 3-scenario matrix output ──────────────────────────────


class AxisScenario(BaseModel):
    """A single axis in the macro scenario matrix."""

    axis: str  # e.g. "au_rates", "us_rates", "au_inflation", "au_housing", "aud_usd"
    base: str
    bull: str
    bear: str
    base_probability: float = 0.5
    bull_probability: float = 0.25
    bear_probability: float = 0.25


class MacroScenario(BaseModel):
    """3-scenario matrix across 5 macro axes for AU + US markets.

    Output of MacroScenarioService; input to EconomyAnalystAgent.
    """

    run_id: str
    scenario_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    based_on_indicators: Optional[str] = None  # fetch_timestamp ISO string

    # Per-axis scenarios
    au_rates: AxisScenario = Field(
        default_factory=lambda: AxisScenario(
            axis="au_rates",
            base="RBA on-hold at 4.35% through 2025",
            bull="RBA cuts 2x by mid-2025 (easing cycle begins)",
            bear="RBA hikes 1x more on persistent inflation",
        )
    )
    us_rates: AxisScenario = Field(
        default_factory=lambda: AxisScenario(
            axis="us_rates",
            base="Fed funds at 5.25-5.50%; 2 cuts priced in 2025",
            bull="Fed cuts 4x (125bp easing cycle)",
            bear="Fed holds higher-for-longer; re-hike risk",
        )
    )
    au_inflation: AxisScenario = Field(
        default_factory=lambda: AxisScenario(
            axis="au_inflation",
            base="Trimmed mean CPI gradually returns to 2-3% band by late 2025",
            bull="CPI falls quickly — no more hikes needed; real wages recover",
            bear="CPI re-accelerates above 4%; wages-price spiral risk",
        )
    )
    au_housing: AxisScenario = Field(
        default_factory=lambda: AxisScenario(
            axis="au_housing",
            base="Prices flat to +3% nationally; supply constraints persist",
            bull="Rate cuts spark new rally; +8-12% nationally",
            bear="Prices fall 10-15%; mortgage stress rises sharply",
        )
    )
    aud_usd: AxisScenario = Field(
        default_factory=lambda: AxisScenario(
            axis="aud_usd",
            base="AUD/USD 0.63-0.67; driven by commodity prices and Fed diff",
            bull="AUD strengthens to 0.70+ on rate diff narrowing and iron ore rally",
            bear="AUD weakens to 0.60 on China slowdown and widening rate diff",
        )
    )

    # Composite scenario assessment
    composite_scenario: ScenarioType = ScenarioType.BASE
    composite_description: str = ""

    # Impact on asset classes
    au_equities_impact: str = ""
    us_equities_impact: str = ""
    au_fixed_income_impact: str = ""
    unhedged_us_equity_aud_impact: str = ""


# ── EconomyAnalysis — 12-field LLM output ─────────────────────────────────


class EconomyAnalysis(BaseModel):
    """Structured output from EconomyAnalystAgent — 12 AU/US macro fields.

    This is the primary macro intelligence packet that feeds into
    MacroStrategistAgent's GlobalMacroRegime classification.
    """

    run_id: str
    analysis_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: Literal["HIGH", "MEDIUM", "LOW"] = "MEDIUM"

    # ── RBA & Fed policy theses ───────────────────────────────────────────
    rba_cash_rate_thesis: str = ""
    """E.g. 'RBA holds at 4.35% — services inflation and tight labour market
    preclude cuts before Q3 2025. First cut likely November 2025 meeting.'"""

    fed_funds_thesis: str = ""
    """E.g. 'Fed pausing — PCE sticky above 2.5%. Two 25bp cuts priced
    for 2025 but data-dependent; higher-for-longer risk remains elevated.'"""

    # ── Inflation assessments ─────────────────────────────────────────────
    au_cpi_assessment: str = ""
    """Trimmed mean CPI trend, services component stickiness, wages pass-through."""

    us_cpi_assessment: str = ""
    """PCE/CPI decomposition, shelter lag, goods deflation, services persistence."""

    # ── Australian specifics ──────────────────────────────────────────────
    au_housing_assessment: str = ""
    """Dwelling prices, auction clearance rates, credit growth, RBA sensitivity."""

    au_wage_growth: str = ""
    """WPI trend, enterprise bargaining outcomes, productivity offset."""

    # ── Currency and trade ────────────────────────────────────────────────
    aud_usd_outlook: str = ""
    """Rate differential, terms of trade (iron ore/LNG), China demand, carry."""

    # ── Portfolio implications ────────────────────────────────────────────
    cogs_inflation_impact: str = ""
    """Input cost pressures on AU-listed industrials, retailers, and energy users."""

    asx200_vs_sp500_divergence: str = ""
    """Sector composition difference (banks vs tech), currency effect, valuation gap."""

    global_credit_conditions: str = ""
    """IG/HY spreads, bank lending standards, shadow banking, EM contagion risk."""

    # ── Key risks ────────────────────────────────────────────────────────
    key_risks_au: list[str] = Field(default_factory=list)
    """Top 3-5 risks specific to Australian macro outlook."""

    key_risks_us: list[str] = Field(default_factory=list)
    """Top 3-5 risks specific to US macro outlook."""

    # ── Stance classifications ────────────────────────────────────────────
    rba_stance: RBAStance = RBAStance.UNKNOWN
    fed_stance: FedStance = FedStance.UNKNOWN
    au_inflation_trend: InflationTrend = InflationTrend.UNKNOWN
    au_housing_trend: HousingTrend = HousingTrend.UNKNOWN
    aud_usd_direction: AudUsdDirection = AudUsdDirection.UNKNOWN


# ── GlobalMacroRegime — extended MacroStrategistAgent output ──────────────


class GlobalMacroRegime(BaseModel):
    """Extended macro regime output from MacroStrategistAgent (Session 12).

    Wraps the existing AI infrastructure regime classification with
    AU-specific and US-specific regime flags from EconomyAnalystAgent.
    """

    run_id: str
    regime_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # ── Existing fields (AI infra regime) ────────────────────────────────
    regime_classification: str = "unknown"
    confidence: str = "MEDIUM"
    key_macro_variables: dict[str, str] = Field(default_factory=dict)
    regime_winners: list[str] = Field(default_factory=list)
    regime_losers: list[str] = Field(default_factory=list)
    rate_sensitivity: dict[str, str] = Field(default_factory=dict)
    cyclical_sensitivity: dict[str, str] = Field(default_factory=dict)
    key_risks_to_regime: list[str] = Field(default_factory=list)
    policy_watch: list[str] = Field(default_factory=list)

    # ── New AU-specific regime flags (Session 12) ─────────────────────────
    au_regime_flag: str = ""
    """E.g. 'AU rate peak — transition from tightening to neutral cycle'"""

    au_equity_regime: str = ""
    """Current regime implication for ASX 200 specifically."""

    au_fixed_income_regime: str = ""
    """RBA path impact on AU bond duration positioning."""

    au_currency_regime: str = ""
    """AUD/USD regime — hedging recommendations for AU investors in US equities."""

    # ── New US-specific regime flags (Session 12) ─────────────────────────
    us_regime_flag: str = ""
    """E.g. 'Fed higher-for-longer — duration compression risk persists'"""

    us_equity_regime: str = ""
    """S&P 500 regime implication — valuation sensitivity to rate path."""

    us_credit_regime: str = ""
    """IG/HY spread regime — risk-on/risk-off signal."""

    # ── Economy analysis reference ────────────────────────────────────────
    economy_analysis_summary: str = ""
    """Brief summary of EconomyAnalysis inputs that shaped this regime."""

    has_economy_analysis: bool = False
