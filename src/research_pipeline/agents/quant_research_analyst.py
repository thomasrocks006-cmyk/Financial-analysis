"""B7 — Quant Research Analyst: interprets deterministic quant outputs for the IC.

Receives output from the deterministic quant services (factor engine, VaR engine,
benchmark module, ETF overlap engine) and produces structured risk commentary
designed for consumption by the Investment Committee and Portfolio Manager.

The agent does NO arithmetic — it interprets results that have already been
computed by the deterministic services layer.
"""

from __future__ import annotations

from typing import Any

from research_pipeline.agents.base_agent import BaseAgent, StructuredOutputError


class QuantResearchAnalystAgent(BaseAgent):
    """Quant Research Analyst — interprets factor exposures, VaR, benchmark analytics.

    Strictly read-only: this agent never adjusts or overrides quant model numbers.
    It translates model outputs into investment-relevant language for the IC.
    """

    _REQUIRED_TOP_LEVEL_FIELDS = (
        "section_1_factor_interpretation",
        "section_2_risk_assessment",
        "section_3_benchmark_divergence",
        "section_4_construction_signal",
        "risk_signal",
        "primary_concern",
        "recommended_action",
    )

    _VALID_RISK_SIGNALS = {"positive", "neutral", "cautious", "negative"}

    def __init__(self, **kwargs):
        super().__init__(name="quant_research_analyst", **kwargs)

    def default_system_prompt(self) -> str:
        return """You are the Quant Research Analyst for an institutional AI infrastructure
research platform. Your role is to INTERPRET — not recalculate — the outputs
of the deterministic quantitative services.

INPUTS YOU RECEIVE:
- factor_exposures: size, value, momentum, quality loadings per ticker
- var_metrics: parametric VaR (95%, 99%), CVaR, max drawdown, recovery time
- benchmark_analytics: active weight per ticker, tracking error vs index, information ratio
- etf_overlap: differentiation_score, per-ETF overlap percentages
- risk_engine: concentration HHI, max single-name weight, contribution-to-variance table
- scenario_results: 7-scenario stress test P&L impacts

YOUR MANDATORY OUTPUT (single JSON object):
{
  "run_id": "RUN-xxx",
  "date": "YYYY-MM-DD",
  "universe": "portfolio name",

  "section_1_factor_interpretation": {
    "dominant_factors": ["momentum", "quality"],
    "factor_tilt_narrative": "Portfolio is significantly overweight momentum vs benchmark due to...",
    "size_tilt": "large-cap tilt — systematic, not idiosyncratic",
    "value_vs_growth": "deep growth tilt — implies multiple compression sensitivity",
    "quality_commentary": "High quality composite driven by NVDA and AVGO balance sheets",
    "concerns": ["momentum crowding risk", "extreme growth multiple sensitivity"]
  },

  "section_2_risk_assessment": {
    "var_95_commentary": "1-day 95% VaR of X% implies max daily loss of $Xm on $100m AUM",
    "var_99_commentary": "Tail risk elevated due to concentration in 3 names >60% weight combined",
    "drawdown_commentary": "Max drawdown profile is consistent with AI infrastructure thematic; peer drawdown in 2022 was -40%",
    "concentration_commentary": "HHI=XXXX suggests moderate concentration; single-name cap breach risk if NVDA moves >5%",
    "stress_scenario_worst": "Scenario X implies -X% portfolio loss — acceptable given conviction",
    "overall_risk_verdict": "Within mandate | Elevated | Breach"
  },

  "section_3_benchmark_divergence": {
    "tracking_error_commentary": "Tracking error of X% vs NDX is intentional high-active-share strategy",
    "etf_differentiation_score": 0,
    "etf_overlap_summary": "Portfolio overlaps AIQ by X% and BOTZ by X% — meaningful differentiation remaining",
    "etf_replication_risk": true,
    "active_bets_narrative": "Key active overweights vs benchmark: NVDA +XX%, CEG +XX%. Key underweights: MSFT -XX%",
    "information_ratio_signal": "IR of X.XX is acceptable / sub-1.0 / strong"
  },

  "section_4_construction_signal": {
    "factor_tilt_recommendation": "Reduce momentum overweight if IR falls below 0.5",
    "concentration_recommendation": "Consider trimming NVDA to below 15% to reduce single-name HHI contribution",
    "benchmark_recommendation": "ETF overlap is manageable; portfolio earns its fee vs passive alternatives",
    "risk_budget_utilisation": "X% of risk budget used",
    "constructive_changes": [
      "Add FCX to diversify away from pure semiconductor exposure",
      "Consider PWR/ETN hedging for infrastructure segment concentration"
    ]
  },

  "risk_signal": "positive | neutral | cautious | negative",
  "primary_concern": "single most important risk flag from the analysis",
  "recommended_action": "what the PM or IC should do based on quant findings",
  "analyst_confidence": "high | medium | low",
  "data_quality_note": "any missing inputs or model limitations that affect reliability"
}

HARD RULES:
- You interpret model numbers — you do NOT recalculate or adjust them
- Always state when data is unavailable rather than estimating
- risk_signal must reflect ALL sections — do not default to 'positive' without justification
- primary_concern must be concrete and specific, not a generic macro statement
- If ETF differentiation_score < 40, flag etf_replication_risk = true
- Do NOT recommend specific price targets — that is the Valuation Analyst's role
- Concentrate on factor, risk, and construction signals only

Return a single JSON object (not an array)."""

    def format_input(self, inputs: dict[str, Any]) -> str:
        import json

        sections = []

        if "factor_exposures" in inputs:
            sections.append("=== FACTOR EXPOSURES ===")
            sections.append(json.dumps(inputs["factor_exposures"], indent=2, default=str))

        if "var_metrics" in inputs:
            sections.append("=== VaR / DRAWDOWN METRICS ===")
            sections.append(json.dumps(inputs["var_metrics"], indent=2, default=str))

        if "benchmark_analytics" in inputs:
            sections.append("=== BENCHMARK ANALYTICS (TRACKING ERROR, ACTIVE WEIGHT) ===")
            sections.append(json.dumps(inputs["benchmark_analytics"], indent=2, default=str))

        if "etf_overlap" in inputs:
            sections.append("=== ETF OVERLAP ANALYSIS ===")
            sections.append(json.dumps(inputs["etf_overlap"], indent=2, default=str))

        if "risk_engine" in inputs:
            sections.append("=== RISK ENGINE (HHI, CONCENTRATION) ===")
            sections.append(json.dumps(inputs["risk_engine"], indent=2, default=str))

        if "scenario_results" in inputs:
            sections.append("=== SCENARIO / STRESS TEST RESULTS ===")
            sections.append(json.dumps(inputs["scenario_results"], indent=2, default=str))

        if "prior_context" in inputs:
            sections.append("=== PRIOR RESEARCH CONTEXT ===")
            sections.append(str(inputs["prior_context"]))

        if not sections:
            import json

            sections.append(json.dumps(inputs, indent=2, default=str))

        return "\n\n".join(sections)

    def parse_output(self, raw_response: str) -> dict[str, Any]:
        """Enforce all mandatory quant output fields."""
        parsed = super().parse_output(raw_response)

        # Normalise: should be a single dict, not a list
        if isinstance(parsed, list):
            if len(parsed) == 1 and isinstance(parsed[0], dict):
                parsed = parsed[0]
            else:
                raise StructuredOutputError(
                    "QuantResearchAnalyst: expected a single JSON object, got a list."
                )

        violations: list[str] = []

        for field in self._REQUIRED_TOP_LEVEL_FIELDS:
            if not parsed.get(field):
                violations.append(f"Missing required field '{field}'")

        risk_signal = str(parsed.get("risk_signal", "")).lower()
        if risk_signal not in self._VALID_RISK_SIGNALS:
            violations.append(
                f"'risk_signal' must be one of {sorted(self._VALID_RISK_SIGNALS)}; got '{risk_signal}'"
            )

        # section_3: if etf_differentiation_score < 40, etf_replication_risk must be True
        s3 = parsed.get("section_3_benchmark_divergence")
        if isinstance(s3, dict):
            score = s3.get("etf_differentiation_score")
            etf_risk = s3.get("etf_replication_risk")
            if score is not None:
                try:
                    if float(score) < 40.0 and not etf_risk:
                        violations.append(
                            f"etf_differentiation_score={score} is below 40 but "
                            f"etf_replication_risk is not True — must flag replication risk"
                        )
                except (TypeError, ValueError):
                    pass

        if violations:
            raise StructuredOutputError(
                "QuantResearchAnalyst: output validation failed:\n"
                + "\n".join(f"  • {v}" for v in violations)
            )

        return parsed
