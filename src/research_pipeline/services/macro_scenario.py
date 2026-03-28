"""MacroScenarioService — derive base/bull/bear scenarios from indicators."""

from __future__ import annotations

from research_pipeline.schemas.macro import EconomicIndicators, MacroScenario


class MacroScenarioService:
    """Build a structured macro scenario matrix from current indicators."""

    def build_scenarios(self, indicators: EconomicIndicators) -> MacroScenario:
        fed = indicators.us.fed_funds_rate
        rba = indicators.au.rba_cash_rate
        aud_usd = indicators.global_market.aud_usd
        au_cpi = indicators.au.trimmed_mean_cpi_yoy
        us_cpi = indicators.us.cpi_yoy

        if fed >= 4.75:
            us_rate = "Fed on-hold to cutting bias"
        elif fed >= 3.5:
            us_rate = "Fed hiking pause, data dependent"
        else:
            us_rate = "Fed easing support regime"

        if rba >= 4.0:
            au_rate = "RBA restrictive / mortgage-sensitive regime"
        elif rba >= 3.0:
            au_rate = "RBA on hold with inflation vigilance"
        else:
            au_rate = "RBA supportive / easing regime"

        if au_cpi >= 3.5 or us_cpi >= 3.5:
            inflation = "sticky"
        elif au_cpi <= 2.5 and us_cpi <= 2.5:
            inflation = "normalising"
        else:
            inflation = "above target but easing"

        if aud_usd >= 0.70:
            fx = "AUD strengthening"
        elif aud_usd <= 0.62:
            fx = "AUD weakening"
        else:
            fx = "AUD range-bound"

        growth = (
            "soft landing"
            if indicators.global_market.global_pmi >= 50
            else "growth scare / hard landing risk"
        )
        housing = (
            "accelerating"
            if indicators.au.housing_price_growth_yoy >= 4.0
            else "stable"
            if indicators.au.housing_price_growth_yoy >= 0.0
            else "correcting"
        )

        return MacroScenario(
            base_case={
                "us_rates": us_rate,
                "au_rates": au_rate,
                "inflation": inflation,
                "growth": growth,
                "housing": housing,
                "aud_usd": fx,
            },
            bull_case={
                "us_rates": "Fed orderly cuts with stable credit",
                "au_rates": "RBA cuts without housing stress",
                "inflation": "disinflation without recession",
                "growth": "soft landing with AI capex resilience",
                "housing": "stable / supportive",
                "aud_usd": "AUD stable to mildly stronger",
            },
            bear_case={
                "us_rates": "Higher for longer or disorderly growth scare",
                "au_rates": "RBA forced restrictive stance amid sticky CPI",
                "inflation": "sticky inflation / margin squeeze",
                "growth": "hard landing / capex pause",
                "housing": "housing correction, mortgage stress rise",
                "aud_usd": "AUD weakens, imported inflation rises",
            },
            probability_weights={"base": 0.5, "bull": 0.25, "bear": 0.25},
        )
