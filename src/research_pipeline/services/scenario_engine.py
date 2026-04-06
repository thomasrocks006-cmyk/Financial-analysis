"""A6 — Scenario & Stress Engine: deterministic scenario propagation."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from research_pipeline.schemas.reports import ScenarioResult

if TYPE_CHECKING:
    from research_pipeline.schemas.macro_economy import MacroScenario

logger = logging.getLogger(__name__)


# ── Built-in scenario definitions (from v8 spec) ──────────────────────────
BUILTIN_SCENARIOS = {
    "ai_capex_slowdown": {
        "name": "AI Capex Slowdown",
        "description": "One or more top-5 hyperscalers pauses or reduces AI capex for 2-3 quarters.",
        "default_impact_pct": -15.0,
        "high_exposure_tickers": ["NVDA", "AVGO", "TSM"],
        "low_exposure_tickers": ["CEG", "FCX", "BHP"],
    },
    "higher_rates": {
        "name": "Higher Rates (+150bp)",
        "description": "Rates rise 150bp, compressing growth multiples and increasing WACC.",
        "default_impact_pct": -12.0,
        "high_exposure_tickers": ["NVDA", "AVGO", "NXT"],
        "low_exposure_tickers": ["FCX", "BHP"],
    },
    "power_permitting_delays": {
        "name": "Power Permitting Delays",
        "description": "New generation and grid interconnection permits delayed 12-18 months.",
        "default_impact_pct": -10.0,
        "high_exposure_tickers": ["CEG", "VST", "GEV", "PWR"],
        "low_exposure_tickers": ["NVDA", "AVGO"],
    },
    "export_control_escalation": {
        "name": "Export Control Escalation",
        "description": "US broadens chip export restrictions to additional countries/entities.",
        "default_impact_pct": -20.0,
        "high_exposure_tickers": ["NVDA", "TSM", "AVGO"],
        "low_exposure_tickers": ["CEG", "ETN", "FIX"],
    },
    "recession": {
        "name": "Recession / Industrial Slowdown",
        "description": "Broad recession reduces enterprise IT spending and industrial activity.",
        "default_impact_pct": -18.0,
        "high_exposure_tickers": ["PWR", "FIX", "ETN", "HUBB"],
        "low_exposure_tickers": ["CEG"],
    },
    "energy_price_shock": {
        "name": "Energy Price Shock",
        "description": "Natural gas prices spike 3x, disrupting power economics.",
        "default_impact_pct": -8.0,
        "high_exposure_tickers": ["VST", "GEV"],
        "low_exposure_tickers": ["NVDA", "AVGO", "TSM"],
    },
    "ai_efficiency_shock": {
        "name": "AI Efficiency Shock (DeepSeek-style)",
        "description": "Compute efficiency improvement reduces compute required per unit by 40-60%.",
        "default_impact_pct": -25.0,
        "high_exposure_tickers": ["NVDA", "AVGO", "TSM"],
        "low_exposure_tickers": ["FCX", "BHP", "CEG"],
    },
}


@dataclass
class ScenarioConfig:
    name: str
    description: str
    default_impact_pct: float
    ticker_overrides: dict[str, float] = field(default_factory=dict)
    high_exposure_tickers: list[str] = field(default_factory=list)
    low_exposure_tickers: list[str] = field(default_factory=list)


class ScenarioStressEngine:
    """Deterministic scenario propagation — no LLM.

    Applies predefined stress scenarios to portfolio names and produces
    per-name and portfolio-level impact estimates.
    """

    def __init__(self, custom_scenarios: dict[str, ScenarioConfig] | None = None):
        self.scenarios: dict[str, ScenarioConfig] = {}
        # Load builtins
        for key, cfg in BUILTIN_SCENARIOS.items():
            self.scenarios[key] = ScenarioConfig(
                name=cfg["name"],
                description=cfg["description"],
                default_impact_pct=cfg["default_impact_pct"],
                high_exposure_tickers=cfg.get("high_exposure_tickers", []),
                low_exposure_tickers=cfg.get("low_exposure_tickers", []),
            )
        # Merge custom
        if custom_scenarios:
            self.scenarios.update(custom_scenarios)

    def apply_scenario(self, scenario_key: str, tickers: list[str]) -> list[ScenarioResult]:
        """Apply a scenario to a list of tickers."""
        scenario = self.scenarios.get(scenario_key)
        if not scenario:
            logger.warning("Unknown scenario: %s", scenario_key)
            return []

        results = []
        for ticker in tickers:
            # Determine impact
            if ticker in scenario.ticker_overrides:
                impact = scenario.ticker_overrides[ticker]
            elif ticker in scenario.high_exposure_tickers:
                impact = scenario.default_impact_pct * 1.5
            elif ticker in scenario.low_exposure_tickers:
                impact = scenario.default_impact_pct * 0.3
            else:
                impact = scenario.default_impact_pct

            severity = "low"
            if abs(impact) >= 20:
                severity = "severe"
            elif abs(impact) >= 15:
                severity = "high"
            elif abs(impact) >= 8:
                severity = "moderate"

            results.append(
                ScenarioResult(
                    ticker=ticker,
                    scenario_name=scenario.name,
                    impact_description=scenario.description,
                    estimated_impact_pct=round(impact, 1),
                    severity=severity,
                )
            )
        return results

    def run_all_scenarios(self, tickers: list[str]) -> list[ScenarioResult]:
        """Run all registered scenarios across all tickers."""
        all_results: list[ScenarioResult] = []
        for key in self.scenarios:
            all_results.extend(self.apply_scenario(key, tickers))
        return all_results

    def portfolio_stress_summary(
        self, tickers: list[str], weights: dict[str, float]
    ) -> dict[str, float]:
        """Weighted portfolio-level impact per scenario.

        Args:
            tickers:  List of tickers in the portfolio.
            weights:  Position weights as PERCENTAGES (0–100), not fractions.
                      E.g. 33.3 for a 33.3% position.  Fractions will produce
                      results ~100x too small.
        """
        summary: dict[str, float] = {}
        for key in self.scenarios:
            results = self.apply_scenario(key, tickers)
            weighted_impact = sum(
                (r.estimated_impact_pct or 0) * weights.get(r.ticker, 0) / 100 for r in results
            )
            summary[self.scenarios[key].name] = round(weighted_impact, 2)
        return summary

    def register_macro_scenarios(self, macro_scenario: "MacroScenario") -> list[str]:
        """Session 12: register MacroScenario bear axes as stress scenarios.

        Converts the bear outcome from each macro scenario axis into a
        ScenarioConfig and registers it with this engine. This allows
        AU/US macro-driven stress tests to run alongside the built-in
        AI infrastructure scenarios.

        Returns the list of newly registered scenario keys.
        """
        # Axis definitions: (axis_name, bear_description, base_impact_pct, high_exposure, low_exposure)
        # Impact percentages are indicative — AU/global macro bear scenarios
        MACRO_AXIS_IMPACTS = [
            (
                "au_rates_bear",
                macro_scenario.au_rates.bear,
                -10.0,
                [
                    "CBA.AX",
                    "WBC.AX",
                    "ANZ.AX",
                    "NAB.AX",
                    "MQG.AX",
                    "WES.AX",
                ],  # rate-sensitive AU names
                ["BHP.AX", "CSL.AX", "GMG.AX"],
            ),
            (
                "us_rates_bear",
                macro_scenario.us_rates.bear,
                -12.0,
                ["NVDA", "AVGO", "NXT", "ANET"],  # duration-sensitive growth names
                ["FCX", "BHP", "CEG"],
            ),
            (
                "au_inflation_bear",
                macro_scenario.au_inflation.bear,
                -8.0,
                ["WOW.AX", "WES.AX", "CBA.AX"],  # consumer / margin-squeeze names
                ["BHP.AX", "CSL.AX"],
            ),
            (
                "au_housing_bear",
                macro_scenario.au_housing.bear,
                -14.0,
                ["CBA.AX", "WBC.AX", "ANZ.AX", "NAB.AX"],  # bank mortgage book
                ["GMG.AX", "CSL.AX", "BHP.AX"],
            ),
            (
                "aud_usd_bear",
                macro_scenario.aud_usd.bear,
                -6.0,
                ["WOW.AX", "WES.AX"],  # import-cost exposed AU names
                [
                    "BHP.AX",
                    "CSL.AX",  # exporters benefit from weak AUD
                    "NVDA",
                    "AVGO",
                ],
            ),  # USD assets: AUD return improves
        ]

        registered: list[str] = []
        for key, description, impact_pct, high_exp, low_exp in MACRO_AXIS_IMPACTS:
            if key not in self.scenarios:
                self.scenarios[key] = ScenarioConfig(
                    name=f"Macro Bear — {key.replace('_', ' ').title()}",
                    description=description,
                    default_impact_pct=impact_pct,
                    high_exposure_tickers=high_exp,
                    low_exposure_tickers=low_exp,
                )
                registered.append(key)

        logger.info(
            "ScenarioStressEngine: registered %d macro scenarios from MacroScenario (run_id=%s)",
            len(registered),
            macro_scenario.run_id,
        )
        return registered
