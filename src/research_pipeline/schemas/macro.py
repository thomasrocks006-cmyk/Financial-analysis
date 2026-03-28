"""Macroeconomic schemas for AU/US market intelligence."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class EconomicIndicators(BaseModel):
    """Normalized AU/US macro indicators used across the pipeline."""

    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    us_fed_funds_rate: float = 4.5
    us_ten_year_yield: float = 4.2
    us_two_year_yield: float = 4.5
    us_cpi_yoy: float = 3.0
    us_pce_yoy: float = 2.8
    us_unemployment_rate: float = 4.0
    us_ism_pmi: float = 50.0
    us_credit_spread_ig_bps: float = 125.0
    au_rba_cash_rate: float = 4.35
    au_ten_year_yield: float = 4.1
    au_cpi_yoy: float = 3.2
    au_trimmed_mean_cpi_yoy: float = 3.4
    au_unemployment_rate: float = 4.1
    au_wage_price_index_yoy: float = 3.7
    au_housing_price_growth_yoy: float = 5.0
    aud_usd: float = 0.66
    copper_price_usd_lb: float = 4.1
    oil_price_usd_bbl: float = 78.0
    vix: float = 18.0
    source_summary: dict[str, str] = Field(default_factory=dict)


class MacroScenarioAxis(BaseModel):
    """One axis of a macro scenario matrix."""

    base: str = ""
    bull: str = ""
    bear: str = ""


class MacroScenario(BaseModel):
    """Scenario matrix for the macro overlay."""

    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    probabilities: dict[str, float] = Field(
        default_factory=lambda: {"base": 0.5, "bull": 0.25, "bear": 0.25}
    )
    au_rates: MacroScenarioAxis = Field(default_factory=MacroScenarioAxis)
    us_rates: MacroScenarioAxis = Field(default_factory=MacroScenarioAxis)
    au_inflation: MacroScenarioAxis = Field(default_factory=MacroScenarioAxis)
    growth: MacroScenarioAxis = Field(default_factory=MacroScenarioAxis)
    au_housing: MacroScenarioAxis = Field(default_factory=MacroScenarioAxis)
    aud_usd: MacroScenarioAxis = Field(default_factory=MacroScenarioAxis)
    implications: list[str] = Field(default_factory=list)


class EconomyAnalysis(BaseModel):
    """Structured sovereign macro analysis for AU and US markets."""

    run_id: str = ""
    as_of: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rba_cash_rate_thesis: str = ""
    fed_funds_thesis: str = ""
    au_cpi_assessment: str = ""
    us_cpi_assessment: str = ""
    au_housing_assessment: str = ""
    au_wage_growth: str = ""
    aud_usd_outlook: str = ""
    cogs_inflation_impact: str = ""
    asx200_vs_sp500_divergence: str = ""
    global_credit_conditions: str = ""
    key_risks_au: list[str] = Field(default_factory=list)
    key_risks_us: list[str] = Field(default_factory=list)
    scenario_implications: list[str] = Field(default_factory=list)


class RegimeDetectionResult(BaseModel):
    """Quant regime classification used alongside macro commentary."""

    regime: str = "sideways"
    regime_probability: float = 0.5
    state_probabilities: dict[str, float] = Field(default_factory=dict)
    methodology: str = "heuristic"
