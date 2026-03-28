"""B7 — Macro & Regime Strategist (extended Session 12: GlobalMacroRegime)."""

from __future__ import annotations

from typing import Any, Optional

from research_pipeline.agents.base_agent import BaseAgent


class MacroStrategistAgent(BaseAgent):
    """Assign current macro regime and sensitivities across the portfolio.

    Session 12 extension: can receive EconomyAnalysis output and produce a
    GlobalMacroRegime with AU-specific and US-specific regime flags alongside
    the existing AI infra regime classification.
    """

    # ISS-12: Required output key contract — fatal if missing in production runs
    _REQUIRED_OUTPUT_KEYS: list[str] = ["regime_classification", "confidence"]
    _VALIDATION_FATAL: bool = True

    def __init__(self, **kwargs):
        super().__init__(name="macro_strategist", **kwargs)

    def default_system_prompt(self) -> str:
        return """You are the Macro & Regime Strategist for an institutional AI infrastructure research platform with an Australian client base.

YOUR ROLE:
- Classify the current macro regime (expansion, late-cycle, slowdown, recession, recovery)
- Identify key macro variables affecting the AI infrastructure investment universe
- Map regime winners and losers across the portfolio
- Assess rate sensitivity and cyclical sensitivity per name
- When AU/US economy analysis is provided, extend your output with AU and US specific regime flags

YOUR OUTPUT:
{
  "regime_classification": "e.g. late-cycle expansion with elevated AI investment",
  "confidence": "HIGH | MEDIUM | LOW",
  "key_macro_variables": {
    "fed_funds_rate": "current + expectations",
    "10y_yield": "current + direction",
    "pmi": "current reading",
    "capex_cycle_phase": "early | mid | late",
    "ai_investment_cycle_phase": "early | mid | late"
  },
  "regime_winners": ["tickers that benefit in current regime"],
  "regime_losers": ["tickers disadvantaged"],
  "rate_sensitivity": {
    "TICKER": "HIGH | MEDIUM | LOW — explanation"
  },
  "cyclical_sensitivity": {
    "TICKER": "HIGH | MEDIUM | LOW — explanation"
  },
  "key_risks_to_regime": ["what would change the regime classification"],
  "policy_watch": ["upcoming macro events/decisions to monitor"],
  "au_regime_flag": "AU-specific regime characterisation (e.g. 'AU rate peak — transition to neutral cycle')",
  "au_equity_regime": "regime implication for ASX 200 specifically",
  "au_fixed_income_regime": "RBA path impact on AU bond duration positioning",
  "au_currency_regime": "AUD/USD regime — hedging implications for AU investors",
  "us_regime_flag": "US-specific regime characterisation (e.g. 'Fed higher-for-longer')",
  "us_equity_regime": "S&P 500 regime implication",
  "us_credit_regime": "IG/HY spread regime signal",
  "economy_analysis_summary": "2-3 sentence summary of how EconomyAnalysis shaped this regime assessment"
}

RULES:
- Use publicly available macro data
- Distinguish current state from forward expectations
- Be explicit about what is priced vs what would be a surprise
- AU regime flags are required when economy_analysis context is provided"""

    def build_global_macro_regime(
        self,
        raw_output: dict[str, Any],
        run_id: str,
        economy_analysis: Optional[Any] = None,
    ) -> "GlobalMacroRegime":
        """Parse MacroStrategistAgent output into a GlobalMacroRegime schema.

        Session 12: accepts an optional EconomyAnalysis to enrich the regime
        with AU and US specific flags.
        """
        from research_pipeline.schemas.macro_economy import GlobalMacroRegime

        has_economy = economy_analysis is not None

        # Derive AU/US flags from economy analysis if available
        au_regime_flag = raw_output.get("au_regime_flag", "")
        au_equity_regime = raw_output.get("au_equity_regime", "")
        au_fixed_income_regime = raw_output.get("au_fixed_income_regime", "")
        au_currency_regime = raw_output.get("au_currency_regime", "")
        us_regime_flag = raw_output.get("us_regime_flag", "")
        us_equity_regime = raw_output.get("us_equity_regime", "")
        us_credit_regime = raw_output.get("us_credit_regime", "")
        economy_summary = raw_output.get("economy_analysis_summary", "")

        # Enrich from EconomyAnalysis if available and fields are empty
        if has_economy and not au_regime_flag:
            stance = getattr(economy_analysis, "rba_stance", None)
            au_regime_flag = f"RBA {getattr(stance, 'value', 'unknown')} cycle" if stance else ""
        if has_economy and not us_regime_flag:
            fed = getattr(economy_analysis, "fed_stance", None)
            us_regime_flag = f"Fed {getattr(fed, 'value', 'unknown')} cycle" if fed else ""
        if has_economy and not economy_summary:
            rba_thesis = getattr(economy_analysis, "rba_cash_rate_thesis", "")
            fed_thesis = getattr(economy_analysis, "fed_funds_thesis", "")
            if rba_thesis or fed_thesis:
                economy_summary = (
                    f"RBA: {rba_thesis[:120]}... | Fed: {fed_thesis[:120]}..."
                    if rba_thesis and fed_thesis
                    else (rba_thesis or fed_thesis)[:200]
                )

        def safe_list(val: Any) -> list[str]:
            if isinstance(val, list):
                return [str(x) for x in val]
            if isinstance(val, str):
                return [val]
            return []

        def safe_dict(val: Any) -> dict[str, str]:
            if isinstance(val, dict):
                return {str(k): str(v) for k, v in val.items()}
            return {}

        return GlobalMacroRegime(
            run_id=run_id,
            regime_classification=raw_output.get("regime_classification", "unknown"),
            confidence=raw_output.get("confidence", "MEDIUM"),
            key_macro_variables=safe_dict(raw_output.get("key_macro_variables", {})),
            regime_winners=safe_list(raw_output.get("regime_winners", [])),
            regime_losers=safe_list(raw_output.get("regime_losers", [])),
            rate_sensitivity=safe_dict(raw_output.get("rate_sensitivity", {})),
            cyclical_sensitivity=safe_dict(raw_output.get("cyclical_sensitivity", {})),
            key_risks_to_regime=safe_list(raw_output.get("key_risks_to_regime", [])),
            policy_watch=safe_list(raw_output.get("policy_watch", [])),
            au_regime_flag=au_regime_flag,
            au_equity_regime=au_equity_regime,
            au_fixed_income_regime=au_fixed_income_regime,
            au_currency_regime=au_currency_regime,
            us_regime_flag=us_regime_flag,
            us_equity_regime=us_equity_regime,
            us_credit_regime=us_credit_regime,
            economy_analysis_summary=economy_summary,
            has_economy_analysis=has_economy,
        )



class PoliticalRiskAnalystAgent(BaseAgent):
    """B8 — Assess export controls, Taiwan risk, tariffs, permitting, nuclear policy."""

    def __init__(self, **kwargs):
        super().__init__(name="political_risk_analyst", **kwargs)

    def default_system_prompt(self) -> str:
        return """You are the Political & Geopolitical Risk Analyst for an institutional AI infrastructure research platform.

YOUR ROLE:
- Assess export control exposure per name
- Evaluate Taiwan/geopolitical concentration risk
- Analyze tariff and trade policy impacts
- Review permitting and regulatory risks (FERC, NRC, state PUC)
- Assess nuclear policy direction and election effects

YOUR OUTPUT PER NAME:
{
  "ticker": "TICKER",
  "policy_dependency_score": 0-10,
  "geopolitical_dependency_score": 0-10,
  "jurisdiction_map": {"US_revenue_pct": "X%", "Taiwan_exposure": "direct|indirect|none"},
  "export_control_exposure": "description of current and potential exposure",
  "taiwan_risk": "NVDA/TSM specific assessment",
  "tariff_exposure": "current tariff impact + escalation scenario",
  "permitting_risk": "for power/infrastructure names",
  "nuclear_policy": "for CEG/NLR — direction and triggers",
  "key_event_triggers": ["events that would materially change assessment"],
  "election_sensitivity": "how upcoming elections affect this name"
}

RULES:
- Use named sources for policy positions
- Distinguish announced policy from speculation
- Quantify where possible (revenue at risk, earnings impact)"""
