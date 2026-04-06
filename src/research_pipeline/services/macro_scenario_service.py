"""Session 12 — MacroScenarioService.

Builds a 3-scenario matrix (base / bull / bear) across 5 macro axes:
  - AU rates (RBA hiking / on-hold / cutting)
  - US rates (Fed hiking / on-hold / cutting)
  - AU inflation (above / on-target / below)
  - AU housing (accelerating / stable / correcting)
  - AUD/USD direction (strengthening / stable / weakening)

Input: EconomicIndicators (from EconomicIndicatorService)
Output: MacroScenario (used by EconomyAnalystAgent)

Scenario probabilities are derived from rule-based heuristics over
the current indicator readings. No LLM calls — deterministic service.
"""

from __future__ import annotations

import logging
from typing import Optional

from research_pipeline.schemas.macro_economy import (
    AxisScenario,
    AudUsdDirection,
    EconomicIndicators,
    HousingTrend,
    InflationTrend,
    MacroScenario,
    RBAStance,
    ScenarioType,
)

logger = logging.getLogger(__name__)


def _classify_rba_stance(au_cpi: Optional[float], rba_rate: Optional[float]) -> RBAStance:
    """Classify the RBA's likely stance from current CPI and cash rate."""
    if au_cpi is None or rba_rate is None:
        return RBAStance.UNKNOWN
    if au_cpi > 3.5:
        return RBAStance.HIKING
    if au_cpi < 2.5:
        return RBAStance.CUTTING
    return RBAStance.ON_HOLD


def _classify_fed_stance(us_cpi: Optional[float], fed_rate: Optional[float]) -> str:
    """Classify the Fed's likely stance."""
    if us_cpi is None or fed_rate is None:
        return "unknown"
    if us_cpi > 3.0 and fed_rate < 5.0:
        return "hiking"
    if us_cpi < 2.2:
        return "cutting"
    return "on_hold"


def _inflation_trend(trimmed_mean: Optional[float]) -> InflationTrend:
    if trimmed_mean is None:
        return InflationTrend.UNKNOWN
    if trimmed_mean > 3.0:
        return InflationTrend.ABOVE_TARGET
    if trimmed_mean < 2.0:
        return InflationTrend.BELOW_TARGET
    return InflationTrend.ON_TARGET


def _housing_trend(housing_chg: Optional[float], clearance: Optional[float]) -> HousingTrend:
    if housing_chg is None:
        return HousingTrend.UNKNOWN
    if housing_chg > 5.0 or (clearance and clearance > 70.0):
        return HousingTrend.ACCELERATING
    if housing_chg < -3.0 or (clearance and clearance < 55.0):
        return HousingTrend.CORRECTING
    return HousingTrend.STABLE


def _aud_usd_direction(
    aud: Optional[float], us_rate: Optional[float], rba_rate: Optional[float]
) -> AudUsdDirection:
    if aud is None:
        return AudUsdDirection.UNKNOWN
    if aud > 0.67:
        return AudUsdDirection.STRENGTHENING
    if aud < 0.62:
        return AudUsdDirection.WEAKENING
    return AudUsdDirection.STABLE


# ── Scenario text builders ────────────────────────────────────────────────


def _build_au_rates_scenario(indicators: EconomicIndicators) -> AxisScenario:
    au = indicators.au
    rba = _classify_rba_stance(au.au_cpi_trimmed_mean_pct, au.rba_cash_rate_pct)
    rate = au.rba_cash_rate_pct or 4.35

    if rba == RBAStance.HIKING:
        base_prob, bull_prob, bear_prob = 0.35, 0.15, 0.50
        base = f"RBA hikes to {rate + 0.25:.2f}% — persistent inflation forces further tightening"
        bull = "Inflation falls sharply; RBA skips hike and signals cuts"
        bear = f"RBA hikes 2-3 more times to {rate + 0.75:.2f}%; recession risk rises"
    elif rba == RBAStance.CUTTING:
        base_prob, bull_prob, bear_prob = 0.45, 0.35, 0.20
        base = f"RBA cuts to {rate - 0.25:.2f}% — disinflation on track; labour market softening"
        bull = f"Accelerated easing: 4 cuts to {rate - 1.00:.2f}% by year-end; risk-on rally"
        bear = "RBA pauses cuts on inflation resurgence; market re-prices higher path"
    else:
        base_prob, bull_prob, bear_prob = 0.50, 0.25, 0.25
        base = f"RBA on-hold at {rate:.2f}%; watching trimmed mean CPI and wages before acting"
        bull = f"RBA cuts 2x to {rate - 0.50:.2f}% on faster disinflation than expected"
        bear = f"RBA forced to hike to {rate + 0.25:.2f}% on sticky services inflation"

    return AxisScenario(
        axis="au_rates",
        base=base,
        bull=bull,
        bear=bear,
        base_probability=base_prob,
        bull_probability=bull_prob,
        bear_probability=bear_prob,
    )


def _build_us_rates_scenario(indicators: EconomicIndicators) -> AxisScenario:
    us = indicators.us
    fed = _classify_fed_stance(us.us_cpi_yoy_pct, us.fed_funds_rate_pct)
    rate = us.fed_funds_rate_pct or 5.375

    if fed == "hiking":
        base_prob, bull_prob, bear_prob = 0.30, 0.10, 0.60
        base = f"Fed hikes to {rate + 0.25:.2f}%; CPI above 3% keeps pressure on"
        bull = "CPI surprise to downside; Fed pivots — two 25bp cuts announced"
        bear = f"Inflation entrenched; Fed hikes 3x to {rate + 0.75:.2f}%; hard landing risk"
    elif fed == "cutting":
        base_prob, bull_prob, bear_prob = 0.50, 0.30, 0.20
        base = f"Fed cutting cycle underway at {rate:.2f}%; gradual normalisation"
        bull = "Rapid easing cycle — 4+ cuts; risk assets rally on soft landing"
        bear = "Inflation re-accelerates; Fed stops cutting early; rates plateau higher"
    else:
        base_prob, bull_prob, bear_prob = 0.45, 0.30, 0.25
        base = f"Fed on hold at {rate:.2f}%; 2 cuts priced for year-end, data dependent"
        bull = "PCE falls to 2.2%; Fed front-loads 4 cuts; long-end yields fall sharply"
        bear = "PCE re-accelerates on services; no cuts in 2025; higher-for-longer confirmed"

    return AxisScenario(
        axis="us_rates",
        base=base,
        bull=bull,
        bear=bear,
        base_probability=base_prob,
        bull_probability=bull_prob,
        bear_probability=bear_prob,
    )


def _build_au_inflation_scenario(indicators: EconomicIndicators) -> AxisScenario:
    trend = _inflation_trend(indicators.au.au_cpi_trimmed_mean_pct)
    cpi = indicators.au.au_cpi_trimmed_mean_pct or 3.2

    if trend == InflationTrend.ABOVE_TARGET:
        base_prob, bull_prob, bear_prob = 0.40, 0.20, 0.40
        base = f"Trimmed mean CPI at {cpi:.1f}% — gradual return to 2-3% band by late 2025"
        bull = "Rapid disinflation: trimmed mean hits 2.5% mid-year; RBA can cut"
        bear = f"CPI re-accelerates to {cpi + 0.8:.1f}% on wage catch-up and rent — RBA must hike"
    elif trend == InflationTrend.BELOW_TARGET:
        base_prob, bull_prob, bear_prob = 0.50, 0.30, 0.20
        base = "Inflation below target; RBA can ease — supportive for equities and housing"
        bull = "Deflationary pulse: CPI falls to 1.5% — aggressive RBA easing cycle"
        bear = "Surprise rebound — supply chain shock re-ignites CPI"
    else:
        base_prob, bull_prob, bear_prob = 0.55, 0.20, 0.25
        base = f"Trimmed mean CPI {cpi:.1f}% — within RBA 2-3% target band; benign"
        bull = "Below-target on services deflation; real wages rise; consumer confidence recovers"
        bear = "Wages-price spiral emerges; services CPI re-accelerates to 4%+"

    return AxisScenario(
        axis="au_inflation",
        base=base,
        bull=bull,
        bear=bear,
        base_probability=base_prob,
        bull_probability=bull_prob,
        bear_probability=bear_prob,
    )


def _build_au_housing_scenario(indicators: EconomicIndicators) -> AxisScenario:
    trend = _housing_trend(
        indicators.au.au_housing_price_index_change_pct,
        indicators.au.au_auction_clearance_rate_pct,
    )
    chg = indicators.au.au_housing_price_index_change_pct or 2.5

    if trend == HousingTrend.ACCELERATING:
        base_prob, bull_prob, bear_prob = 0.40, 0.35, 0.25
        base = f"Housing up {chg:.1f}% — low supply supports prices; RBA cuts risk re-acceleration"
        bull = "Rate cuts trigger another +15% cycle; FOMO returns; wealth effect boosts spending"
        bear = "APRA macro-pru intervention or RBA hike reverses momentum; prices -8% in 12m"
    elif trend == HousingTrend.CORRECTING:
        base_prob, bull_prob, bear_prob = 0.35, 0.30, 0.35
        base = "Modest correction continues; variable-rate holders under mortgage stress"
        bull = "RBA cuts early; confidence returns; correction bottoms; prices stabilise"
        bear = "Forced selling accelerates; prices -20%; banking system NPL risk rises"
    else:
        base_prob, bull_prob, bear_prob = 0.50, 0.25, 0.25
        base = "Prices stable to +3%; immigration demand offset by affordability constraint"
        bull = "Rate cuts trigger +10% rally; construction activity recovers"
        bear = "Supply overhang in apartments + rate shock causes -12% nationalwide correction"

    return AxisScenario(
        axis="au_housing",
        base=base,
        bull=bull,
        bear=bear,
        base_probability=base_prob,
        bull_probability=bull_prob,
        bear_probability=bear_prob,
    )


def _build_aud_usd_scenario(indicators: EconomicIndicators) -> AxisScenario:
    direction = _aud_usd_direction(
        indicators.au.aud_usd,
        indicators.us.fed_funds_rate_pct,
        indicators.au.rba_cash_rate_pct,
    )
    aud = indicators.au.aud_usd or 0.645

    if direction == AudUsdDirection.STRENGTHENING:
        base_prob, bull_prob, bear_prob = 0.40, 0.40, 0.20
        base = f"AUD/USD {aud:.3f} — terms of trade supportive; carry narrowing vs USD"
        bull = "AUD rallies to 0.72 on iron ore spike and broad USD weakness"
        bear = "Risk-off reversal; AUD gives back gains; China demand disappointment"
    elif direction == AudUsdDirection.WEAKENING:
        base_prob, bull_prob, bear_prob = 0.35, 0.30, 0.35
        base = f"AUD/USD {aud:.3f} — wide rate differential + China growth risk weighs"
        bull = "China stimulus surprise lifts commodity prices; AUD recovers to 0.66"
        bear = "AUD breaks 0.60 on global risk-off; capital outflows from AU market"
    else:
        base_prob, bull_prob, bear_prob = 0.50, 0.25, 0.25
        base = f"AUD/USD {aud:.3f} — range-bound; rate differential offset by commodity support"
        bull = "Fed cuts before RBA; AUD/USD moves to 0.68-0.70; unhedged US equity drag"
        bear = "Widening AU-US rate gap; AUD weakens to 0.61; unhedged US equity gain"

    return AxisScenario(
        axis="aud_usd",
        base=base,
        bull=bull,
        bear=bear,
        base_probability=base_prob,
        bull_probability=bull_prob,
        bear_probability=bear_prob,
    )


def _derive_composite_scenario(indicators: EconomicIndicators) -> tuple[ScenarioType, str]:
    """Derive an overall composite scenario from indicator readings."""
    au = indicators.au
    us = indicators.us

    rba = _classify_rba_stance(au.au_cpi_trimmed_mean_pct, au.rba_cash_rate_pct)
    housing = _housing_trend(au.au_housing_price_index_change_pct, au.au_auction_clearance_rate_pct)
    inflation = _inflation_trend(au.au_cpi_trimmed_mean_pct)
    fed = _classify_fed_stance(us.us_cpi_yoy_pct, us.fed_funds_rate_pct)

    bear_signals = sum(
        [
            rba == RBAStance.HIKING,
            housing == HousingTrend.CORRECTING,
            inflation == InflationTrend.ABOVE_TARGET,
            fed == "hiking",
            (us.us_yield_curve_spread_10y_2y or 0.0) < -0.5,
        ]
    )
    bull_signals = sum(
        [
            rba == RBAStance.CUTTING,
            housing == HousingTrend.ACCELERATING,
            inflation == InflationTrend.BELOW_TARGET,
            fed == "cutting",
            (us.us_hy_spread_bps or 400) < 300,
        ]
    )

    if bear_signals >= 3:
        return ScenarioType.BEAR, (
            "Multiple contractionary signals: tight monetary policy, inflation pressure, "
            "housing stress, or credit tightening dominate the outlook."
        )
    if bull_signals >= 3:
        return ScenarioType.BULL, (
            "Multiple expansionary signals: easing monetary policy, disinflation, "
            "housing support, and tightening credit spreads support risk assets."
        )
    return ScenarioType.BASE, (
        "Mixed signals: some easing, some tightening pressures — balanced base case "
        "with moderate growth and gradual disinflation."
    )


def _composite_impacts(composite: ScenarioType) -> dict[str, str]:
    """Return simple asset class impact strings per composite scenario."""
    if composite == ScenarioType.BULL:
        return {
            "au_equities_impact": "Positive: rate cuts support valuations; housing wealth effect boosts consumer discretionary and banks",
            "us_equities_impact": "Positive: Fed easing expands multiples; growth stocks outperform; small caps benefit from rate relief",
            "au_fixed_income_impact": "Positive: yields fall as RBA cuts; long-duration AU government bonds outperform",
            "unhedged_us_equity_aud_impact": "Mixed: AUD strengthening reduces AUD returns on unhedged US positions — consider hedging",
        }
    if composite == ScenarioType.BEAR:
        return {
            "au_equities_impact": "Negative: rate hikes compress PE multiples; mortgage stress weighs on banks; consumer staples defensive",
            "us_equities_impact": "Negative: tight financial conditions; credit crunch risk; defensives and energy outperform",
            "au_fixed_income_impact": "Negative (short duration): yields rising; reduce duration; shift to floating rate and cash",
            "unhedged_us_equity_aud_impact": "Potentially positive via AUD weakness — unhedged US provides currency hedge in risk-off",
        }
    return {
        "au_equities_impact": "Neutral to positive: incremental rate relief supports valuations; earnings growth modest",
        "us_equities_impact": "Neutral: rate plateau; earnings carry market; AI infra remains structural winner",
        "au_fixed_income_impact": "Neutral: yields stable; credit spreads tight; modest carry advantage in short-dated paper",
        "unhedged_us_equity_aud_impact": "Neutral: AUD range-bound; limited currency drag or benefit on US exposures",
    }


# ── Public API ────────────────────────────────────────────────────────────


class MacroScenarioService:
    """Builds a 3-scenario macro matrix from EconomicIndicators.

    All logic is deterministic — no LLM calls, no network I/O.

    Usage:
        svc = MacroScenarioService()
        scenario = svc.build_scenario(indicators)
    """

    def build_scenario(self, indicators: EconomicIndicators) -> MacroScenario:
        """Given EconomicIndicators, produce a MacroScenario with 5-axis matrix."""
        composite_type, composite_desc = _derive_composite_scenario(indicators)
        impacts = _composite_impacts(composite_type)

        scenario = MacroScenario(
            run_id=indicators.run_id,
            based_on_indicators=indicators.fetch_timestamp.isoformat(),
            au_rates=_build_au_rates_scenario(indicators),
            us_rates=_build_us_rates_scenario(indicators),
            au_inflation=_build_au_inflation_scenario(indicators),
            au_housing=_build_au_housing_scenario(indicators),
            aud_usd=_build_aud_usd_scenario(indicators),
            composite_scenario=composite_type,
            composite_description=composite_desc,
            **impacts,
        )

        logger.info(
            "MacroScenarioService: composite=%s for run_id=%s",
            composite_type.value,
            indicators.run_id,
        )
        return scenario

    @staticmethod
    def build_scenario_from_synthetic(run_id: str) -> MacroScenario:
        """Convenience: build a scenario from synthetic indicators."""
        from research_pipeline.services.economic_indicator_service import (
            EconomicIndicatorService,
        )

        indicators = EconomicIndicatorService.get_synthetic(run_id)
        return MacroScenarioService().build_scenario(indicators)
