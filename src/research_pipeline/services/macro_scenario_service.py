"""Session 12 — MacroScenarioService: 3-scenario matrix for AU + US macro axes.

Inputs:   EconomicIndicators
Outputs:  MacroScenario with base / bull / bear for each key axis:
            - AU rates (RBA hiking / on-hold / cutting)
            - US rates (Fed hiking / on-hold / cutting)
            - AU inflation (above / on-target / below)
            - AU housing (accelerating / stable / correcting)
            - AUD/USD direction
            - Global credit (tight / neutral / loose)
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field

from research_pipeline.services.economic_indicator_service import EconomicIndicators

logger = logging.getLogger(__name__)


ScenarioType = Literal["base", "bull", "bear"]


class RateScenario(BaseModel):
    """Single-axis rate scenario."""

    scenario_type: ScenarioType
    rate_move_bp: int = 0
    policy_stance: str = "on-hold"
    rationale: str = ""
    probability: float = 0.0


class MacroAxisScenarios(BaseModel):
    """Three-scenario set for one macro axis."""

    axis: str
    base: RateScenario
    bull: RateScenario
    bear: RateScenario

    @property
    def current(self) -> RateScenario:
        return self.base


class MacroScenario(BaseModel):
    """Complete macro scenario matrix — AU + US axes."""

    au_rates: MacroAxisScenarios
    us_rates: MacroAxisScenarios
    au_inflation: MacroAxisScenarios
    au_housing: MacroAxisScenarios
    aud_usd: MacroAxisScenarios
    global_credit: MacroAxisScenarios

    # Composite regime
    composite_regime: Literal["risk-on", "risk-neutral", "risk-off"] = "risk-neutral"
    regime_rationale: str = ""

    # Impact on AI infrastructure equity thesis
    ai_infra_impact_base: str = ""
    ai_infra_impact_bull: str = ""
    ai_infra_impact_bear: str = ""

    # Impact on AU super fund allocation
    au_super_impact: str = ""

    # VaR stress scenario parameters (for integration with Stage 9)
    stress_return_bear_pct: float = -25.0
    stress_return_bull_pct: float = 20.0


class MacroScenarioService:
    """Build macro scenario matrices from live EconomicIndicators."""

    def build_scenarios(self, indicators: EconomicIndicators) -> MacroScenario:
        """Derive the 3-scenario matrix from current indicator readings."""
        au = indicators.au
        us = indicators.us

        au_rate_scenarios = self._build_au_rate_scenarios(au.rba_cash_rate_pct, au.au_cpi_yoy_pct)
        us_rate_scenarios = self._build_us_rate_scenarios(us.fed_funds_rate_pct, us.us_cpi_yoy_pct)
        au_inflation_scenarios = self._build_au_inflation_scenarios(au.au_cpi_yoy_pct, au.au_trimmed_mean_cpi_pct)
        au_housing_scenarios = self._build_au_housing_scenarios(au.au_housing_price_yoy_pct)
        aud_usd_scenarios = self._build_aud_usd_scenarios(au.aud_usd_rate, us.fed_funds_rate_pct, au.rba_cash_rate_pct)
        credit_scenarios = self._build_credit_scenarios(us.us_credit_spread_ig_bp, us.us_credit_spread_hy_bp)

        # Composite regime
        risk_score = self._compute_risk_score(au, us)
        if risk_score >= 0.4:
            composite = "risk-on"
        elif risk_score <= -0.4:
            composite = "risk-off"
        else:
            composite = "risk-neutral"

        regime_rationale = (
            f"RBA at {au.rba_cash_rate_pct:.2f}% ({au.rba_policy_stance}); "
            f"Fed at {us.fed_funds_rate_pct:.2f}% ({us.fed_policy_stance}); "
            f"AU CPI {au.au_cpi_yoy_pct:.1f}%; AUD/USD {au.aud_usd_rate:.3f}; "
            f"US 10Y yield {us.us_10y_treasury_yield_pct:.2f}%"
        )

        return MacroScenario(
            au_rates=au_rate_scenarios,
            us_rates=us_rate_scenarios,
            au_inflation=au_inflation_scenarios,
            au_housing=au_housing_scenarios,
            aud_usd=aud_usd_scenarios,
            global_credit=credit_scenarios,
            composite_regime=composite,
            regime_rationale=regime_rationale,
            ai_infra_impact_base=(
                "Stable rate environment supports AI infrastructure capex discipline. "
                "DCF valuations reflect current discount rates."
            ),
            ai_infra_impact_bull=(
                "Rate cuts reduce cost of capital — DCF valuations expand; "
                "AI infrastructure capex cycle accelerates."
            ),
            ai_infra_impact_bear=(
                "Rate hikes compress DCF terminal value multiples; "
                "credit tightening constrains hyperscaler capex; thesis is weakened."
            ),
            au_super_impact=(
                f"Australian super funds face {'tailwind' if composite == 'risk-on' else 'headwind'} "
                f"on international equity allocation. AUD/USD at {au.aud_usd_rate:.3f} "
                f"{'reduces' if au.aud_usd_trend == 'strengthening' else 'enhances'} unhedged US equity returns."
            ),
            stress_return_bear_pct=-30.0 if composite == "risk-off" else -20.0,
            stress_return_bull_pct=25.0 if composite == "risk-on" else 15.0,
        )

    def _compute_risk_score(self, au: "AustralianIndicators", us: "USIndicators") -> float:  # type: ignore[name-defined]
        """Score from -1 (risk-off) to +1 (risk-on) based on macro conditions."""
        score = 0.0
        # Real rates — negative real rates = risk-on (loose financial conditions)
        us_real_rate = us.fed_funds_rate_pct - us.us_cpi_yoy_pct
        if us_real_rate < 0.5:
            score += 0.3
        elif us_real_rate > 2.0:
            score -= 0.3

        # Yield curve — steepening = risk-on
        if us.us_yield_curve_spread_bp > 0:
            score += 0.2
        elif us.us_yield_curve_spread_bp < -50:
            score -= 0.2

        # Credit spreads — tight = risk-on
        if us.us_credit_spread_hy_bp < 300:
            score += 0.2
        elif us.us_credit_spread_hy_bp > 500:
            score -= 0.3

        # AUD/USD trend
        if au.aud_usd_trend == "strengthening":
            score += 0.1
        elif au.aud_usd_trend == "weakening":
            score -= 0.1

        return max(-1.0, min(1.0, score))

    def _build_au_rate_scenarios(self, cash_rate: float, cpi: float) -> MacroAxisScenarios:
        base_stance = "on-hold" if abs(cash_rate - 4.35) < 0.5 else ("hiking" if cash_rate < cpi - 1 else "cutting")
        return MacroAxisScenarios(
            axis="au_rates",
            base=RateScenario(
                scenario_type="base", rate_move_bp=0, policy_stance=base_stance,
                rationale=f"RBA holds at {cash_rate:.2f}%; trimmed mean CPI tracking toward target",
                probability=0.55,
            ),
            bull=RateScenario(
                scenario_type="bull", rate_move_bp=-75, policy_stance="cutting",
                rationale="CPI falls to target faster than expected; RBA cuts 3×25bp",
                probability=0.25,
            ),
            bear=RateScenario(
                scenario_type="bear", rate_move_bp=50, policy_stance="hiking",
                rationale="Inflation re-accelerates; RBA forced to hike further",
                probability=0.20,
            ),
        )

    def _build_us_rate_scenarios(self, fed_rate: float, cpi: float) -> MacroAxisScenarios:
        base_stance = "on-hold" if fed_rate > cpi + 1.5 else "hiking"
        return MacroAxisScenarios(
            axis="us_rates",
            base=RateScenario(
                scenario_type="base", rate_move_bp=-50, policy_stance="cutting",
                rationale=f"Fed cuts 2×25bp as PCE approaches 2% target; funds at {fed_rate-0.5:.2f}%",
                probability=0.50,
            ),
            bull=RateScenario(
                scenario_type="bull", rate_move_bp=-150, policy_stance="cutting",
                rationale="US recession forces 6 cuts; AI capex pause but long duration equities rally",
                probability=0.20,
            ),
            bear=RateScenario(
                scenario_type="bear", rate_move_bp=75, policy_stance="hiking",
                rationale="Sticky inflation forces 3 additional hikes; multiple compression for growth stocks",
                probability=0.30,
            ),
        )

    def _build_au_inflation_scenarios(self, cpi: float, trimmed: float) -> MacroAxisScenarios:
        on_target = abs(trimmed - 2.5) < 0.8
        return MacroAxisScenarios(
            axis="au_inflation",
            base=RateScenario(
                scenario_type="base", rate_move_bp=0,
                policy_stance="on-target" if on_target else "above-target",
                rationale=f"AU CPI {cpi:.1f}%; trimmed mean {trimmed:.1f}% — gradual disinflation",
                probability=0.55,
            ),
            bull=RateScenario(
                scenario_type="bull", rate_move_bp=0,
                policy_stance="below-target",
                rationale="Services inflation collapses; CPI dips below 2.5%",
                probability=0.20,
            ),
            bear=RateScenario(
                scenario_type="bear", rate_move_bp=0,
                policy_stance="above-target",
                rationale="Housing + wages push trimmed mean above 4%; stagflation risk",
                probability=0.25,
            ),
        )

    def _build_au_housing_scenarios(self, housing_yoy: float) -> MacroAxisScenarios:
        return MacroAxisScenarios(
            axis="au_housing",
            base=RateScenario(
                scenario_type="base", rate_move_bp=0,
                policy_stance="stable",
                rationale=f"AU dwelling prices +{housing_yoy:.1f}% YoY — tight supply supports values",
                probability=0.50,
            ),
            bull=RateScenario(
                scenario_type="bull", rate_move_bp=0,
                policy_stance="accelerating",
                rationale="Rate cuts reignite demand; Sydney/Melbourne prices +15% YoY",
                probability=0.25,
            ),
            bear=RateScenario(
                scenario_type="bear", rate_move_bp=0,
                policy_stance="correcting",
                rationale="Rate hikes + tight credit cause 10-15% correction; household wealth shock",
                probability=0.25,
            ),
        )

    def _build_aud_usd_scenarios(self, spot: float, fed_rate: float, rba_rate: float) -> MacroAxisScenarios:
        rate_diff = rba_rate - fed_rate
        trend = "weakening" if rate_diff < -0.5 else ("strengthening" if rate_diff > 0.5 else "stable")
        return MacroAxisScenarios(
            axis="aud_usd",
            base=RateScenario(
                scenario_type="base", rate_move_bp=0,
                policy_stance=trend,
                rationale=f"AUD/USD {spot:.3f}; AU-US rate differential {rate_diff:+.2f}%",
                probability=0.50,
            ),
            bull=RateScenario(
                scenario_type="bull", rate_move_bp=0,
                policy_stance="strengthening",
                rationale="China stimulus boosts AU commodity exports; AUD strengthens to 0.70+",
                probability=0.25,
            ),
            bear=RateScenario(
                scenario_type="bear", rate_move_bp=0,
                policy_stance="weakening",
                rationale="USD safe-haven bid; AUD falls to 0.58; negative for unhedged US equity returns",
                probability=0.25,
            ),
        )

    def _build_credit_scenarios(self, ig_spread: float, hy_spread: float) -> MacroAxisScenarios:
        stance = "tight" if ig_spread > 120 else ("loose" if ig_spread < 80 else "neutral")
        return MacroAxisScenarios(
            axis="global_credit",
            base=RateScenario(
                scenario_type="base", rate_move_bp=0,
                policy_stance=stance,
                rationale=f"IG spreads {ig_spread:.0f}bp, HY {hy_spread:.0f}bp — benign credit conditions",
                probability=0.55,
            ),
            bull=RateScenario(
                scenario_type="bull", rate_move_bp=0,
                policy_stance="loose",
                rationale="Credit spreads tighten as soft landing confirmed; HY below 300bp",
                probability=0.25,
            ),
            bear=RateScenario(
                scenario_type="bear", rate_move_bp=0,
                policy_stance="tight",
                rationale="Credit crunch; HY spreads blow out to 600bp+; AI capex financing constrained",
                probability=0.20,
            ),
        )
