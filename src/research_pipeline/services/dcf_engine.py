"""A4 — DCF / Model Engine: deterministic valuation math."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class DCFAssumptions:
    """Input assumptions for a DCF model."""
    ticker: str
    revenue_base: float  # current year revenue
    revenue_growth_rates: list[float] = field(default_factory=lambda: [0.10] * 5)
    ebitda_margin_path: list[float] = field(default_factory=lambda: [0.30] * 5)
    capex_pct_revenue: float = 0.08
    tax_rate: float = 0.21
    wacc: float = 0.10
    terminal_growth: float = 0.03
    shares_outstanding: float = 1.0  # in millions


@dataclass
class DCFResult:
    """Output from a DCF calculation."""
    ticker: str
    enterprise_value: float
    equity_value: float
    implied_share_price: float
    fcf_projections: list[float]
    terminal_value: float


@dataclass
class SensitivityTable:
    """2D sensitivity grid."""
    row_label: str  # e.g. "WACC"
    col_label: str  # e.g. "Terminal Growth"
    row_values: list[float] = field(default_factory=list)
    col_values: list[float] = field(default_factory=list)
    grid: list[list[float]] = field(default_factory=list)  # implied price per cell


class DCFEngine:
    """Deterministic DCF computation — no LLM.

    Engine computes; agent interprets.
    """

    def compute_dcf(self, assumptions: DCFAssumptions, net_debt: float = 0.0) -> DCFResult:
        """Run a standard unlevered FCF → enterprise value DCF."""
        revenues: list[float] = []
        fcfs: list[float] = []
        rev = assumptions.revenue_base

        for i in range(len(assumptions.revenue_growth_rates)):
            rev *= (1 + assumptions.revenue_growth_rates[i])
            revenues.append(rev)
            ebitda = rev * assumptions.ebitda_margin_path[i]
            capex = rev * assumptions.capex_pct_revenue
            nopat = ebitda * (1 - assumptions.tax_rate)
            fcf = nopat - capex
            fcfs.append(fcf)

        # Terminal value (Gordon growth)
        terminal_fcf = fcfs[-1] * (1 + assumptions.terminal_growth)
        terminal_value = terminal_fcf / (assumptions.wacc - assumptions.terminal_growth)

        # Discount back
        discount_factors = [(1 + assumptions.wacc) ** (i + 1) for i in range(len(fcfs))]
        pv_fcfs = sum(f / d for f, d in zip(fcfs, discount_factors))
        pv_terminal = terminal_value / discount_factors[-1]

        ev = pv_fcfs + pv_terminal
        equity = ev - net_debt
        price = equity / assumptions.shares_outstanding if assumptions.shares_outstanding > 0 else 0

        return DCFResult(
            ticker=assumptions.ticker,
            enterprise_value=round(ev, 2),
            equity_value=round(equity, 2),
            implied_share_price=round(price, 2),
            fcf_projections=[round(f, 2) for f in fcfs],
            terminal_value=round(terminal_value, 2),
        )

    def reverse_dcf(
        self,
        ticker: str,
        current_price: float,
        shares_outstanding: float,
        net_debt: float,
        wacc: float,
        terminal_growth: float,
        revenue_base: float,        # REQUIRED: current revenue ($M), NOT normalised
        years: int = 5,
        ebitda_margin: float = 0.30,
        capex_pct: float = 0.08,
        tax_rate: float = 0.21,
    ) -> float:
        """Solve for the implied revenue CAGR that justifies the current price.

        The binary search compares compute_dcf(revenue_base, shares_outstanding)
        against (current_price * shares_outstanding + net_debt) in the SAME
        dollar units.  Previous version used revenue_base=1.0 / shares=1.0
        (normalised), causing a multi-trillion EV vs sub-1 EV comparison that
        always converged to the upper bound (50% CAGR).
        """
        target_ev = current_price * shares_outstanding + net_debt

        # Binary search for growth rate
        low, high = -0.10, 0.50
        for _ in range(100):
            mid = (low + high) / 2
            assumptions = DCFAssumptions(
                ticker=ticker,
                revenue_base=revenue_base,          # actual revenue
                revenue_growth_rates=[mid] * years,
                ebitda_margin_path=[ebitda_margin] * years,
                capex_pct_revenue=capex_pct,
                tax_rate=tax_rate,
                wacc=wacc,
                terminal_growth=terminal_growth,
                shares_outstanding=shares_outstanding,  # actual share count
            )
            result = self.compute_dcf(assumptions, net_debt=net_debt)
            if result.enterprise_value < target_ev:
                low = mid
            else:
                high = mid
        return round(mid, 4)

    def sensitivity_table(
        self,
        assumptions: DCFAssumptions,
        net_debt: float,
        wacc_range: list[float] | None = None,
        tg_range: list[float] | None = None,
    ) -> SensitivityTable:
        """Build WACC × Terminal Growth sensitivity grid."""
        wacc_range = wacc_range or [0.08, 0.09, 0.10, 0.11, 0.12]
        tg_range = tg_range or [0.02, 0.025, 0.03, 0.035, 0.04]
        grid = []
        for w in wacc_range:
            row = []
            for tg in tg_range:
                a = DCFAssumptions(
                    ticker=assumptions.ticker,
                    revenue_base=assumptions.revenue_base,
                    revenue_growth_rates=assumptions.revenue_growth_rates,
                    ebitda_margin_path=assumptions.ebitda_margin_path,
                    capex_pct_revenue=assumptions.capex_pct_revenue,
                    tax_rate=assumptions.tax_rate,
                    wacc=w,
                    terminal_growth=tg,
                    shares_outstanding=assumptions.shares_outstanding,
                )
                result = self.compute_dcf(a, net_debt)
                row.append(round(result.implied_share_price, 2))
            grid.append(row)
        return SensitivityTable(
            row_label="WACC",
            col_label="Terminal Growth",
            row_values=wacc_range,
            col_values=tg_range,
            grid=grid,
        )
