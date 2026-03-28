"""Session 14 — AustralianTaxService: CGT, franking credits, and SMSF logic.

Handles:
- CGT discount (50% for assets held >12 months by individuals/trusts)
- Franking credit imputation (Australian dividend imputation system)
- Dividend withholding tax for foreign equities (US dividends: 15% WHT under DTA)
- SMSF tax rate (accumulation: 15%, pension phase: 0%)
- CGT-aware rebalancing: flag trades that trigger CGT events vs tax-loss harvesting
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

EntityType = Literal["individual", "super_fund_accumulation", "super_fund_pension", "smsf_accumulation", "smsf_pension", "trust", "company"]
TaxResidency = Literal["au_resident", "au_non_resident"]


class FrankingCreditCalc(BaseModel):
    """Franking credit calculation for an Australian dividend."""

    ticker: str
    dividend_per_share: float = 0.0
    franking_percentage: float = 100.0       # % of dividend that is franked
    corporate_tax_rate: float = 30.0         # Australian company tax rate (%)
    franking_credit_per_share: float = 0.0
    grossed_up_dividend: float = 0.0
    effective_yield_boost_pct: float = 0.0   # extra return from imputation for tax-exempt entity


class CGTEvent(BaseModel):
    """A capital gains tax event."""

    ticker: str
    purchase_date: date
    sale_date: Optional[date] = None
    cost_base: float = 0.0                   # purchase price per unit
    proceeds: float = 0.0                    # sale price per unit
    capital_gain: float = 0.0               # proceeds - cost_base
    discount_applied: bool = False           # 50% CGT discount
    net_capital_gain: float = 0.0           # after discount
    tax_payable: float = 0.0
    is_tax_loss: bool = False
    holding_period_days: int = 0


class CGTRebalanceTrade(BaseModel):
    """A rebalance trade evaluated for CGT impact."""

    ticker: str
    trade_type: Literal["buy", "sell"]
    units: float = 0.0
    current_price: float = 0.0
    estimated_gain_loss: float = 0.0
    cgt_impact: float = 0.0                  # estimated tax cost
    is_tax_loss_harvest: bool = False        # negative CGT = tax benefit
    recommendation: Literal["proceed", "defer", "harvest"] = "proceed"
    notes: str = ""


class TaxAwareRebalanceResult(BaseModel):
    """Result of tax-aware rebalance analysis."""

    entity_type: EntityType
    trades: list[CGTRebalanceTrade] = Field(default_factory=list)
    total_cgt_cost: float = 0.0
    total_tax_loss_harvest: float = 0.0
    net_tax_impact: float = 0.0
    tax_efficient_trades: list[str] = Field(default_factory=list)
    deferred_trades: list[str] = Field(default_factory=list)
    summary: str = ""


class AustralianTaxService:
    """AU tax calculations relevant to super fund and SMSF investors."""

    # Tax rates by entity type
    TAX_RATES: dict[str, float] = {
        "individual": 0.47,                    # top marginal rate
        "super_fund_accumulation": 0.15,       # SGC § concessional contributions tax
        "super_fund_pension": 0.0,             # pension phase: tax-free
        "smsf_accumulation": 0.15,
        "smsf_pension": 0.0,
        "trust": 0.47,                          # trust distribution taxed at beneficiary rate
        "company": 0.30,
    }

    # US dividend withholding tax rate under AU-US DTA
    US_DIVIDEND_WHT_PCT = 15.0

    def compute_franking_credit(
        self,
        ticker: str,
        dividend_per_share: float,
        franking_percentage: float = 100.0,
        corporate_tax_rate: float = 30.0,
    ) -> FrankingCreditCalc:
        """Calculate franking credit and grossed-up dividend.

        Franking credit = (dividend × franking%) × (tax_rate / (1 - tax_rate))
        """
        franked_portion = dividend_per_share * (franking_percentage / 100)
        franking_credit = franked_portion * (corporate_tax_rate / 100) / (1 - corporate_tax_rate / 100)
        grossed_up = dividend_per_share + franking_credit

        # For a tax-exempt entity (super pension / charity), full refund value
        effective_boost = (franking_credit / dividend_per_share * 100) if dividend_per_share > 0 else 0

        return FrankingCreditCalc(
            ticker=ticker,
            dividend_per_share=round(dividend_per_share, 4),
            franking_percentage=franking_percentage,
            corporate_tax_rate=corporate_tax_rate,
            franking_credit_per_share=round(franking_credit, 4),
            grossed_up_dividend=round(grossed_up, 4),
            effective_yield_boost_pct=round(effective_boost, 2),
        )

    def compute_cgt(
        self,
        ticker: str,
        cost_base: float,
        proceeds: float,
        purchase_date: date,
        sale_date: Optional[date] = None,
        entity_type: EntityType = "individual",
    ) -> CGTEvent:
        """Calculate CGT for a disposal event.

        Applies 50% discount for assets held >12 months by eligible entities.
        """
        sd = sale_date or date.today()
        holding_days = (sd - purchase_date).days

        capital_gain = proceeds - cost_base
        is_loss = capital_gain < 0

        discount_eligible_entities = {
            "individual", "trust", "super_fund_accumulation",
            "smsf_accumulation",
        }
        discount_applied = (
            holding_days > 365
            and capital_gain > 0
            and entity_type in discount_eligible_entities
        )

        net_gain = capital_gain * (0.5 if discount_applied else 1.0)
        tax_rate = self.TAX_RATES.get(entity_type, 0.30)
        tax_payable = max(0.0, net_gain * tax_rate)

        return CGTEvent(
            ticker=ticker,
            purchase_date=purchase_date,
            sale_date=sd,
            cost_base=round(cost_base, 4),
            proceeds=round(proceeds, 4),
            capital_gain=round(capital_gain, 4),
            discount_applied=discount_applied,
            net_capital_gain=round(net_gain, 4),
            tax_payable=round(tax_payable, 4),
            is_tax_loss=is_loss,
            holding_period_days=holding_days,
        )

    def tax_aware_rebalance(
        self,
        run_id: str,
        target_weights: dict[str, float],
        current_weights: dict[str, float],
        cost_bases: dict[str, float],
        current_prices: dict[str, float],
        purchase_dates: dict[str, date],
        entity_type: EntityType = "super_fund_accumulation",
        total_portfolio_value: float = 1_000_000.0,
    ) -> TaxAwareRebalanceResult:
        """Generate CGT-aware rebalancing recommendations.

        For each sell trade:
        - Calculate estimated CGT cost
        - Flag tax-loss harvesting opportunities (sells with embedded losses)
        - Defer sells where CGT cost is >1% of trade value (close to 12m threshold)
        """
        trades: list[CGTRebalanceTrade] = []
        total_cgt_cost = 0.0
        total_harvested = 0.0
        tax_efficient: list[str] = []
        deferred: list[str] = []

        all_tickers = set(target_weights) | set(current_weights)

        for ticker in all_tickers:
            target_w = target_weights.get(ticker, 0.0)
            current_w = current_weights.get(ticker, 0.0)
            weight_diff = target_w - current_w  # positive = buy, negative = sell

            if abs(weight_diff) < 0.5:  # ignore trivial changes
                continue

            trade_value = abs(weight_diff / 100) * total_portfolio_value
            current_price = current_prices.get(ticker, 100.0)
            units = trade_value / current_price if current_price > 0 else 0

            if weight_diff < 0:  # sell trade
                cost_base = cost_bases.get(ticker, current_price)
                purchase_date = purchase_dates.get(ticker, date(2023, 1, 1))
                holding_days = (date.today() - purchase_date).days

                cgt_event = self.compute_cgt(
                    ticker=ticker,
                    cost_base=cost_base * units,
                    proceeds=current_price * units,
                    purchase_date=purchase_date,
                    entity_type=entity_type,
                )

                cgt_cost = cgt_event.tax_payable
                is_harvest = cgt_event.is_tax_loss

                # Deferral logic: if close to 12m discount threshold, defer 30 days
                close_to_discount = (345 <= holding_days <= 365) and not cgt_event.discount_applied

                if is_harvest:
                    recommendation = "harvest"
                    total_harvested += abs(cgt_cost)
                elif close_to_discount and cgt_event.capital_gain > 0:
                    recommendation = "defer"
                    deferred.append(ticker)
                else:
                    recommendation = "proceed"
                    total_cgt_cost += cgt_cost

                if recommendation in ("proceed", "harvest"):
                    tax_efficient.append(ticker)

                trades.append(CGTRebalanceTrade(
                    ticker=ticker,
                    trade_type="sell",
                    units=round(units, 2),
                    current_price=round(current_price, 2),
                    estimated_gain_loss=round(cgt_event.capital_gain, 2),
                    cgt_impact=round(cgt_cost, 2),
                    is_tax_loss_harvest=is_harvest,
                    recommendation=recommendation,
                    notes=(
                        f"Holding {holding_days}d; "
                        f"{'50% CGT discount applies' if cgt_event.discount_applied else 'no discount'}"
                        + ("; DEFER: 12m discount threshold approaching" if close_to_discount else "")
                    ),
                ))
            else:  # buy trade
                trades.append(CGTRebalanceTrade(
                    ticker=ticker,
                    trade_type="buy",
                    units=round(units, 2),
                    current_price=round(current_prices.get(ticker, 100.0), 2),
                    recommendation="proceed",
                ))

        net_tax = total_cgt_cost - total_harvested

        return TaxAwareRebalanceResult(
            entity_type=entity_type,
            trades=trades,
            total_cgt_cost=round(total_cgt_cost, 2),
            total_tax_loss_harvest=round(total_harvested, 2),
            net_tax_impact=round(net_tax, 2),
            tax_efficient_trades=tax_efficient,
            deferred_trades=deferred,
            summary=(
                f"Tax-aware rebalance: {len(trades)} trades. "
                f"Estimated CGT cost: ${total_cgt_cost:,.0f}. "
                f"Tax-loss harvest: ${total_harvested:,.0f}. "
                f"Net tax impact: ${net_tax:,.0f}. "
                f"{len(deferred)} trade(s) deferred for CGT discount optimisation."
            ),
        )
