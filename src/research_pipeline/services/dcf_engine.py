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


@dataclass
class RelativeValuationResult:
    """Output from EV/EBITDA and P/E relative valuation methods.

    Both methods produce an implied share price. When both are available
    the ``composite_implied_price`` is a simple average; call
    ``weight_composite()`` to use a custom blend.
    """
    ticker: str
    current_price: float
    peer_ev_ebitda_multiple: Optional[float] = None
    ev_ebitda_implied_price: Optional[float] = None
    ev_ebitda_upside_pct: Optional[float] = None  # vs current_price
    peer_pe_multiple: Optional[float] = None
    pe_implied_price: Optional[float] = None
    pe_upside_pct: Optional[float] = None  # vs current_price
    composite_implied_price: Optional[float] = None
    composite_upside_pct: Optional[float] = None
    methodology_note: str = ""

    def weight_composite(
        self, ev_ebitda_weight: float = 0.5, pe_weight: float = 0.5
    ) -> Optional[float]:
        """Blend the two methods with custom weights.

        If only one method produced an implied price, that price is returned
        directly (i.e. the missing method is treated as weight=0).
        Returns None if neither method produced a price.
        """
        ev = self.ev_ebitda_implied_price
        pe = self.pe_implied_price
        if ev is None and pe is None:
            return None
        if ev is None:
            return round(pe, 2)  # type: ignore[arg-type]
        if pe is None:
            return round(ev, 2)
        return round(ev * ev_ebitda_weight + pe * pe_weight, 2)


class DCFEngine:
    """Deterministic DCF + relative valuation computation — no LLM.

    Methods:
    - ``compute_dcf``          — standard unlevered FCF discounted to EV
    - ``reverse_dcf``          — back-solve for implied revenue CAGR
    - ``sensitivity_table``    — WACC × terminal-growth grid
    - ``relative_valuation``   — EV/EBITDA and P/E comps approach (P-6)

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
        # Guard: WACC must exceed terminal growth to produce a finite terminal value.
        if assumptions.wacc <= assumptions.terminal_growth:
            raise ValueError(
                f"WACC ({assumptions.wacc:.2%}) must be strictly greater than terminal_growth "
                f"({assumptions.terminal_growth:.2%}) to compute a finite terminal value."
            )
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

    # ── P-6: Relative valuation (EV/EBITDA and P/E) ───────────────────

    def relative_valuation(
        self,
        ticker: str,
        current_price: float,
        ebitda: Optional[float] = None,
        net_debt: float = 0.0,
        shares_outstanding: float = 1.0,
        peer_ev_ebitda_multiple: Optional[float] = None,
        eps: Optional[float] = None,
        peer_pe_multiple: Optional[float] = None,
    ) -> RelativeValuationResult:
        """Compute implied share price using EV/EBITDA and/or P/E multiples.

        At least one of (ebitda + peer_ev_ebitda_multiple) or
        (eps + peer_pe_multiple) must be provided, otherwise both implied
        prices are returned as None.

        Args:
            ticker: Ticker symbol.
            current_price: Current market price per share.
            ebitda: Last-twelve-months EBITDA ($M).
            net_debt: Net debt ($M, positive = more debt than cash).
            shares_outstanding: Shares outstanding (millions).
            peer_ev_ebitda_multiple: Peer-group median EV/EBITDA multiple.
            eps: Last-twelve-months EPS.
            peer_pe_multiple: Peer-group median P/E multiple.

        Returns:
            RelativeValuationResult with implied prices and upside percentages.
        """
        ev_ebitda_price: Optional[float] = None
        ev_ebitda_upside: Optional[float] = None
        pe_price: Optional[float] = None
        pe_upside: Optional[float] = None
        notes: list[str] = []

        # EV/EBITDA method
        if ebitda is not None and peer_ev_ebitda_multiple is not None:
            if shares_outstanding > 0:
                implied_ev = ebitda * peer_ev_ebitda_multiple
                implied_equity = implied_ev - net_debt
                ev_ebitda_price = round(implied_equity / shares_outstanding, 2)
                if current_price > 0:
                    ev_ebitda_upside = round(
                        (ev_ebitda_price - current_price) / current_price * 100, 1
                    )
                notes.append(
                    f"EV/EBITDA: {ebitda:.1f}M EBITDA × {peer_ev_ebitda_multiple:.1f}x "
                    f"= ${implied_ev:.1f}M EV"
                )
            else:
                notes.append("EV/EBITDA skipped: shares_outstanding must be > 0")

        # P/E method
        if eps is not None and peer_pe_multiple is not None:
            if eps > 0:
                pe_price = round(eps * peer_pe_multiple, 2)
                if current_price > 0:
                    pe_upside = round((pe_price - current_price) / current_price * 100, 1)
                notes.append(f"P/E: ${eps:.2f} EPS × {peer_pe_multiple:.1f}x")
            else:
                notes.append("P/E skipped: EPS must be positive for P/E method")

        # Simple average composite
        composite: Optional[float] = None
        composite_upside: Optional[float] = None
        available = [p for p in (ev_ebitda_price, pe_price) if p is not None]
        if available:
            composite = round(sum(available) / len(available), 2)
            if current_price > 0:
                composite_upside = round(
                    (composite - current_price) / current_price * 100, 1
                )

        return RelativeValuationResult(
            ticker=ticker,
            current_price=current_price,
            peer_ev_ebitda_multiple=peer_ev_ebitda_multiple,
            ev_ebitda_implied_price=ev_ebitda_price,
            ev_ebitda_upside_pct=ev_ebitda_upside,
            peer_pe_multiple=peer_pe_multiple,
            pe_implied_price=pe_price,
            pe_upside_pct=pe_upside,
            composite_implied_price=composite,
            composite_upside_pct=composite_upside,
            methodology_note=" | ".join(notes) if notes else "No methods applied",
        )

    # ── Session 13: Macro-adjusted WACC + full valuation pack ─────────────────

    def macro_adjusted_wacc(
        self,
        base_wacc: float,
        economy_analysis: dict | None = None,
        macro_scenario: dict | None = None,
    ) -> float:
        """Adjust base WACC for the current macro rate regime.

        Uses RBA/Fed thesis and macro scenario type from Session 12 outputs.
        Adjustments are symmetric ±50bp per direction with a hard floor of 5%.

        Args:
            base_wacc: Starting WACC (e.g. 0.10 for 10%).
            economy_analysis: Output dict from EconomyAnalystAgent.
            macro_scenario: Output dict from MacroScenarioService.

        Returns:
            Adjusted WACC as a float (e.g. 0.105).
        """
        adjustment = 0.0

        # Apply scenario-based adjustment
        if macro_scenario:
            scenario_type = str(
                macro_scenario.get("composite_type", macro_scenario.get("scenario_type", ""))
            ).lower()
            if "bear" in scenario_type:
                adjustment += 0.005   # +50bp for rising-rate / risk-off regime
            elif "bull" in scenario_type:
                adjustment -= 0.005   # -50bp for falling-rate / risk-on regime

        # Apply Fed/RBA thesis adjustment if present
        if economy_analysis:
            fed = str(economy_analysis.get("fed_funds_thesis", "")).lower()
            rba = str(economy_analysis.get("rba_cash_rate_thesis", "")).lower()
            if any(kw in fed for kw in ("hik", "hawkish", "tighten", "rising")):
                adjustment += 0.005
            elif any(kw in fed for kw in ("cut", "easing", "dovish", "falling")):
                adjustment -= 0.005
            if any(kw in rba for kw in ("hik", "hawkish", "tighten", "rising")):
                adjustment += 0.0025  # smaller RBA influence on US-listed names
            elif any(kw in rba for kw in ("cut", "easing", "dovish", "falling")):
                adjustment -= 0.0025

        adjusted = round(base_wacc + adjustment, 4)
        return max(adjusted, 0.05)   # floor at 5%

    def build_full_valuation_pack(
        self,
        assumptions: "DCFAssumptions",
        net_debt: float = 0.0,
        current_price: float = 0.0,
        ebitda: Optional[float] = None,
        eps: Optional[float] = None,
        peer_ev_ebitda_multiple: Optional[float] = None,
        peer_pe_multiple: Optional[float] = None,
        economy_analysis: dict | None = None,
        macro_scenario: dict | None = None,
    ) -> dict:
        """Session 13: one-call full valuation pack with sensitivity + cross-validation.

        Computes:
        1. DCF with macro-adjusted WACC
        2. WACC × terminal_growth sensitivity table
        3. Relative valuation (EV/EBITDA + P/E cross-validation)

        Returns a serialisable dict suitable for injection into agent prompts.
        """
        # Macro-adjust WACC before all calculations
        adj_wacc = self.macro_adjusted_wacc(
            assumptions.wacc, economy_analysis, macro_scenario
        )
        assumptions.wacc = adj_wacc

        dcf_result = self.compute_dcf(assumptions, net_debt)
        sensitivity = self.sensitivity_table(assumptions, net_debt)
        rel_val = self.relative_valuation(
            ticker=assumptions.ticker,
            current_price=current_price,
            ebitda=ebitda,
            net_debt=net_debt,
            shares_outstanding=assumptions.shares_outstanding,
            peer_ev_ebitda_multiple=peer_ev_ebitda_multiple,
            eps=eps,
            peer_pe_multiple=peer_pe_multiple,
        )

        return {
            "ticker": assumptions.ticker,
            "macro_adjusted_wacc": adj_wacc,
            "dcf": {
                "implied_share_price": dcf_result.implied_share_price,
                "enterprise_value": dcf_result.enterprise_value,
                "terminal_value": dcf_result.terminal_value,
                "fcf_projections": dcf_result.fcf_projections,
            },
            "sensitivity": {
                "row_label": sensitivity.row_label,
                "col_label": sensitivity.col_label,
                "row_values": sensitivity.row_values,
                "col_values": sensitivity.col_values,
                "grid": sensitivity.grid,
            },
            "relative_valuation": {
                "ev_ebitda_implied": rel_val.ev_ebitda_implied_price,
                "ev_ebitda_upside_pct": rel_val.ev_ebitda_upside_pct,
                "pe_implied": rel_val.pe_implied_price,
                "pe_upside_pct": rel_val.pe_upside_pct,
                "composite_implied": rel_val.composite_implied_price,
                "composite_upside_pct": rel_val.composite_upside_pct,
                "methodology_note": rel_val.methodology_note,
            },
        }
