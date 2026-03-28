"""Australian tax helper for super/SMSF reporting."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AustralianTaxAssessment:
    cgt_discount_pct: float
    effective_tax_rate_pct: float
    franking_credit_benefit_pct: float
    withholding_tax_pct: float
    summary: str


class AustralianTaxService:
    """Deterministic AU tax overlays for reports and rebalancing."""

    def assess(
        self,
        client_type: str = "institutional",
        holding_period_days: int = 365,
        dividend_yield_pct: float = 0.0,
        includes_us_equities: bool = True,
    ) -> AustralianTaxAssessment:
        is_smsf = client_type.lower() == "smsf"
        cgt_discount = 50.0 if holding_period_days >= 365 else 0.0
        effective_tax = 15.0 if is_smsf else 30.0 if client_type.lower() == "corporate" else 22.5
        franking_benefit = round(dividend_yield_pct * 0.30, 2)
        withholding = 15.0 if includes_us_equities else 0.0
        summary = (
            f"Australian tax overlay for {client_type}: CGT discount {cgt_discount:.0f}% "
            f"after 12 months, effective tax rate {effective_tax:.1f}%, "
            f"franking uplift ~{franking_benefit:.2f}% of yield, "
            f"US withholding {withholding:.1f}%."
        )
        return AustralianTaxAssessment(
            cgt_discount_pct=cgt_discount,
            effective_tax_rate_pct=effective_tax,
            franking_credit_benefit_pct=franking_benefit,
            withholding_tax_pct=withholding,
            summary=summary,
        )
