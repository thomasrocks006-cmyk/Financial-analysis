"""Australian Tax Service — Session 14: Australian Client Context.

Provides deterministic (no LLM) tax calculations for AU investors:
  - CGT discount (50% individuals, 1/3 super funds, 0% corporate)
  - Franking credit gross-up (fully-franked AU dividends)
  - US dividend withholding (AU/US tax treaty reduced 15% rate)
  - SMSF accumulation vs pension-phase tax differentiation
  - Annual tax-drag estimate in basis points on portfolio yield

Tax rates (FY2024–25, subject to change):
  SMSF accumulation:   15% income tax, 10% effective CGT (1/3 discount)
  SMSF pension phase:   0% income tax,  0% CGT
  APRA super fund:     15% income tax, 10% effective CGT (1/3 discount)
  HNW individual:      47% marginal income tax, 23.5% effective CGT (50% discount)
  Retail individual:   32.5% approx income tax, 16.25% effective CGT
  Corporate:           30% flat, no CGT discount

References:
  - ATO Income Tax Assessment Act 1997 (ITAA97) Div 115 — CGT discount
  - ATO Tax Office info for super funds — tax.gov.au
  - AU/US Double Tax Agreement (2010 update), Art 10 — 15% withholding
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from research_pipeline.schemas.client_profile import ClientProfile


# ── Tax settings model (lightweight dataclass — no Pydantic overhead) ──────


@dataclass
class TaxSettings:
    """Effective tax parameters for a client category."""

    client_type: str
    income_tax_rate: float  # marginal rate for income & short-term CGT
    cgt_discount_rate: float  # fraction of gain exempt after 12 months
    smsf_pension_phase: bool = False

    # Withholding
    au_dividend_withholding_pct: float = 0.0  # domestic — none for AU entities
    us_dividend_withholding_pct: float = 15.0  # AU/US treaty rate

    # AU corporate tax (for franking gross-up)
    au_corporate_tax_rate: float = 0.30

    @property
    def effective_cgt_rate(self) -> float:
        """Effective CGT rate on long-term gains after discount."""
        return self.income_tax_rate * (1.0 - self.cgt_discount_rate)

    @property
    def effective_short_cgt_rate(self) -> float:
        """Effective CGT rate on short-term gains (< 12 months)."""
        return self.income_tax_rate


# ── Pre-built tax setting instances ───────────────────────────────────────

TAX_SUPER_FUND = TaxSettings(
    client_type="super_fund",
    income_tax_rate=0.15,
    cgt_discount_rate=0.333,  # 1/3 discount → 10% effective CGT
)

TAX_SMSF_ACCUMULATION = TaxSettings(
    client_type="smsf",
    income_tax_rate=0.15,
    cgt_discount_rate=0.333,
)

TAX_SMSF_PENSION = TaxSettings(
    client_type="smsf_pension",
    income_tax_rate=0.0,
    cgt_discount_rate=1.0,  # fully exempt
    smsf_pension_phase=True,
    us_dividend_withholding_pct=15.0,
)

TAX_HNW = TaxSettings(
    client_type="hnw",
    income_tax_rate=0.47,  # highest marginal rate + 2% Medicare levy
    cgt_discount_rate=0.50,  # 50% discount → 23.5% effective CGT
)

TAX_RETAIL = TaxSettings(
    client_type="retail",
    income_tax_rate=0.325,  # 32.5% middle bracket (approximation)
    cgt_discount_rate=0.50,
)

TAX_INSTITUTIONAL = TaxSettings(
    client_type="institutional",
    income_tax_rate=0.30,  # corporate tax rate
    cgt_discount_rate=0.0,  # corporates do not get CGT discount
)


# ── Service ────────────────────────────────────────────────────────────────


class AustralianTaxService:
    """Deterministic AU tax calculations for portfolio income and capital gains.

    All methods are pure functions — no LLM calls, no external API calls.
    """

    # ── Tax settings lookup ──────────────────────────────────────────────

    def get_tax_settings(self, client_profile: "ClientProfile") -> TaxSettings:
        """Return the correct TaxSettings for a given ClientProfile."""
        ct = getattr(client_profile, "client_type", "institutional")

        if ct == "smsf":
            pension = getattr(client_profile, "smsf_pension_phase", False)
            return TAX_SMSF_PENSION if pension else TAX_SMSF_ACCUMULATION

        if ct == "super_fund":
            return TAX_SUPER_FUND

        if ct == "hnw":
            return TAX_HNW

        if ct == "retail":
            return TAX_RETAIL

        return TAX_INSTITUTIONAL  # default for institutional / unknown

    # ── CGT calculations ─────────────────────────────────────────────────

    def apply_cgt(
        self,
        capital_gain: float,
        held_days: int,
        tax_settings: TaxSettings,
    ) -> float:
        """Compute the tax payable on a capital gain.

        Args:
            capital_gain: Gross capital gain in dollars (or %).
            held_days: Number of days the asset was held.
            tax_settings: Client-specific tax parameters.

        Returns:
            Tax amount after applying the CGT discount if held ≥ 365 days.
        """
        if capital_gain <= 0:
            return 0.0

        if held_days >= 365:
            taxable_gain = capital_gain * (1.0 - tax_settings.cgt_discount_rate)
        else:
            taxable_gain = capital_gain

        return round(taxable_gain * tax_settings.income_tax_rate, 4)

    def after_tax_gain(
        self,
        capital_gain: float,
        held_days: int,
        tax_settings: TaxSettings,
    ) -> float:
        """Return the after-tax capital gain (i.e. gain minus tax payable)."""
        return capital_gain - self.apply_cgt(capital_gain, held_days, tax_settings)

    # ── Franking credits ─────────────────────────────────────────────────

    def compute_franking_credit(
        self,
        cash_dividend: float,
        franking_pct: float = 1.0,
        corporate_tax_rate: float = 0.30,
    ) -> float:
        """Compute the franking credit attached to an AU dividend.

        Standard formula: credit = (dividend × franking%) × (corp_tax / (1 - corp_tax))

        Args:
            cash_dividend: The cash dividend per share (or total).
            franking_pct: Fraction that is franked (0–1). 1.0 = fully franked.
            corporate_tax_rate: AU corporate tax rate (default 0.30).

        Returns:
            Franking credit amount.
        """
        if corporate_tax_rate >= 1.0:
            return 0.0
        franked_amount = cash_dividend * franking_pct
        return round(franked_amount * corporate_tax_rate / (1.0 - corporate_tax_rate), 6)

    def grossed_up_dividend(
        self,
        cash_dividend: float,
        franking_pct: float = 1.0,
        corporate_tax_rate: float = 0.30,
    ) -> float:
        """Return the grossed-up dividend (cash + franking credit)."""
        return cash_dividend + self.compute_franking_credit(
            cash_dividend, franking_pct, corporate_tax_rate
        )

    def franking_benefit(
        self,
        cash_dividend: float,
        tax_settings: TaxSettings,
        franking_pct: float = 1.0,
        corporate_tax_rate: float = 0.30,
    ) -> float:
        """Compute the net benefit or cost of franking credits to the investor.

        If the investor's tax rate < corporate rate, they receive a refund.
        If the investor's tax rate > corporate rate, the credit offsets some tax.

        Returns:
            Net franking benefit (positive = benefit, negative = cost).
        """
        credit = self.compute_franking_credit(cash_dividend, franking_pct, corporate_tax_rate)
        grossed_up = cash_dividend + credit
        # Tax on grossed-up dividend at investor's marginal rate
        investor_tax = grossed_up * tax_settings.income_tax_rate
        # Net position: credit received minus additional tax owed
        return round(credit - investor_tax + cash_dividend * tax_settings.income_tax_rate * 0, 6)

    # ── US dividend withholding ──────────────────────────────────────────

    def compute_net_us_dividend(
        self,
        gross_dividend: float,
        tax_settings: TaxSettings,
    ) -> float:
        """Compute the after-withholding, after-income-tax US dividend.

        AU/US tax treaty (Article 10) reduces withholding from 30% to 15%
        for AU pension funds and 15% for other AU residents in most cases.

        Returns:
            Net dividend after US withholding and AU income tax on the residual.
        """
        after_withholding = gross_dividend * (
            1.0 - tax_settings.us_dividend_withholding_pct / 100.0
        )
        # AU income tax applies on the after-withholding amount
        # (withholding is a foreign tax credit, simplification: offset assumed)
        after_income_tax = after_withholding * (1.0 - tax_settings.income_tax_rate)
        return round(after_income_tax, 6)

    # ── Tax drag estimate ────────────────────────────────────────────────

    def compute_tax_drag_bps(
        self,
        income_yield_pct: float,
        tax_settings: TaxSettings,
    ) -> float:
        """Estimate annual tax drag in basis points on portfolio income yield.

        Args:
            income_yield_pct: Annualised portfolio income yield as a percentage
                (e.g. 3.0 for 3%).
            tax_settings: Client-specific tax settings.

        Returns:
            Annual tax drag in basis points (1 bp = 0.01%).
        """
        gross_income_bps = income_yield_pct * 100.0  # e.g. 3% → 300 bps
        drag_bps = gross_income_bps * tax_settings.income_tax_rate
        return round(drag_bps, 1)

    def after_tax_yield_pct(
        self,
        gross_yield_pct: float,
        tax_settings: TaxSettings,
    ) -> float:
        """Return after-tax income yield as a percentage."""
        return round(gross_yield_pct * (1.0 - tax_settings.income_tax_rate), 4)

    # ── Portfolio-level summary ──────────────────────────────────────────

    def portfolio_tax_summary(
        self,
        client_profile: "ClientProfile",
        portfolio_yield_pct: float = 3.0,
        au_equity_weight_pct: float = 60.0,
        us_equity_weight_pct: float = 30.0,
    ) -> dict:
        """Return a summary dict suitable for inclusion in report disclosures."""
        ts = self.get_tax_settings(client_profile)
        after_tax = self.after_tax_yield_pct(portfolio_yield_pct, ts)
        drag = self.compute_tax_drag_bps(portfolio_yield_pct, ts)

        return {
            "client_type": ts.client_type,
            "income_tax_rate_pct": round(ts.income_tax_rate * 100, 1),
            "cgt_discount_rate_pct": round(ts.cgt_discount_rate * 100, 1),
            "effective_cgt_rate_pct": round(ts.effective_cgt_rate * 100, 1),
            "us_withholding_rate_pct": ts.us_dividend_withholding_pct,
            "gross_portfolio_yield_pct": round(portfolio_yield_pct, 2),
            "after_tax_yield_pct": after_tax,
            "estimated_tax_drag_bps": drag,
            "au_equity_weight_pct": au_equity_weight_pct,
            "us_equity_weight_pct": us_equity_weight_pct,
            "smsf_pension_phase": ts.smsf_pension_phase,
        }
