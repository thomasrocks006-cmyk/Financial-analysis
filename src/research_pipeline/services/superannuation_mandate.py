"""Superannuation Mandate Service — Session 14: Australian Client Context.

Implements APRA SPS 530 Investment Governance diversification requirements
for the five standard MySuper option types:
  growth / balanced / conservative / lifecycle / dio

Key regulatory context:
  - APRA SPS 530 requires super funds to set and enforce investment objectives
    and a risk management framework including single-name and asset-class limits.
  - The ATO mandates SMSF trustees document their investment strategy.
  - APRA CPG 530 guidance recommends no single-name concentration >5% for
    APRA-regulated funds (soft benchmark, commonly adopted as hard limit).
"""

from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel, Field

from research_pipeline.schemas.governance import (
    MandateCheckResult,
    MandateRule,
    MandateViolation,
)

logger = logging.getLogger(__name__)


# ── Mandate parameter model ────────────────────────────────────────────────

class SuperannuationMandate(BaseModel):
    """Investment mandate parameters for a super fund option type."""

    mandate_type: str           # "growth" | "balanced" | "conservative" | etc.
    description: str = ""

    # Single-name concentration (APRA SPS 530 § 60 — diversification)
    max_single_name_pct: float = 5.0

    # Growth-asset bandwidth (equities + property + alternatives)
    max_growth_assets_pct: float = 85.0
    min_growth_assets_pct: float = 0.0

    # International exposure cap (most large APRA funds use 60–65%)
    max_international_pct: float = 65.0

    # Minimum AU domestic allocation (not statutory, strong convention)
    min_au_allocation_pct: float = 20.0

    # Maximum illiquid assets (APRA liquidity management guidance)
    max_illiquid_pct: float = 30.0

    # Whether APRA SPS 530 diversification requirements apply
    apra_sps530: bool = True


# ── Pre-built mandate library ──────────────────────────────────────────────

SUPER_MANDATES: dict[str, SuperannuationMandate] = {
    "growth": SuperannuationMandate(
        mandate_type="growth",
        description="MySuper Growth — 60–85% growth assets, long-term horizon",
        max_single_name_pct=5.0,
        max_growth_assets_pct=85.0,
        min_growth_assets_pct=60.0,
        max_international_pct=65.0,
        min_au_allocation_pct=20.0,
    ),
    "balanced": SuperannuationMandate(
        mandate_type="balanced",
        description="MySuper Balanced — 40–70% growth assets, moderate risk",
        max_single_name_pct=5.0,
        max_growth_assets_pct=70.0,
        min_growth_assets_pct=40.0,
        max_international_pct=50.0,
        min_au_allocation_pct=25.0,
    ),
    "conservative": SuperannuationMandate(
        mandate_type="conservative",
        description="MySuper Conservative — 0–30% growth, capital preservation",
        max_single_name_pct=3.0,
        max_growth_assets_pct=30.0,
        min_growth_assets_pct=0.0,
        max_international_pct=30.0,
        min_au_allocation_pct=30.0,
    ),
    "lifecycle": SuperannuationMandate(
        mandate_type="lifecycle",
        description=(
            "MySuper Lifecycle — glide path from high-growth (<40) to "
            "conservative (>55); modelled at peak growth phase"
        ),
        max_single_name_pct=5.0,
        max_growth_assets_pct=80.0,
        min_growth_assets_pct=0.0,
        max_international_pct=60.0,
        min_au_allocation_pct=20.0,
    ),
    "dio": SuperannuationMandate(
        mandate_type="dio",
        description=(
            "Direct Investment Option — member-directed; APRA single-name "
            "diversification still applies"
        ),
        max_single_name_pct=20.0,   # higher limit; member accepts concentration
        max_growth_assets_pct=100.0,
        min_growth_assets_pct=0.0,
        max_international_pct=100.0,
        min_au_allocation_pct=0.0,
        apra_sps530=True,
    ),
}


# ── Service ────────────────────────────────────────────────────────────────

class SuperannuationMandateService:
    """Deterministic APRA SPS 530 mandate checks for super fund portfolios.

    No LLM calls — all checks are arithmetic on portfolio weights.
    """

    def get_mandate(self, mandate_type: str) -> SuperannuationMandate:
        """Return mandate parameters; falls back to 'balanced' if unknown."""
        key = (mandate_type or "balanced").lower()
        if key not in SUPER_MANDATES:
            logger.warning(
                "Unknown super mandate type '%s', falling back to 'balanced'", key
            )
            key = "balanced"
        return SUPER_MANDATES[key]

    def check_compliance(
        self,
        run_id: str,
        mandate_type: str,
        weights: dict[str, float],
        asx_tickers: Optional[list[str]] = None,
    ) -> MandateCheckResult:
        """Check portfolio weights against APRA SPS 530 super mandate rules.

        Args:
            run_id: Pipeline run identifier.
            mandate_type: One of growth / balanced / conservative / lifecycle / dio.
            weights: Ticker → weight % mapping (values should sum to ~100).
            asx_tickers: Explicit list of tickers treated as AU domestic.
                If None, any ticker ending in .AX or .ASX is classified as AU.

        Returns:
            MandateCheckResult with violations and warnings.
        """
        mandate = self.get_mandate(mandate_type)
        violations: list[MandateViolation] = []
        warnings: list[str] = []

        # Classify tickers as AU domestic vs international
        if asx_tickers is not None:
            au_set = set(asx_tickers)
        else:
            au_set = {
                t for t in weights
                if t.endswith(".AX") or t.endswith(".ASX")
            }

        # 1 ── APRA SPS 530 §60: single-name concentration limit ────────
        for ticker, weight in weights.items():
            if weight > mandate.max_single_name_pct:
                violations.append(
                    MandateViolation(
                        rule=MandateRule(
                            rule_id=f"SPS530_NAME_{ticker}",
                            rule_type="max_weight",
                            description=(
                                f"APRA SPS 530: {ticker} exceeds "
                                f"{mandate.max_single_name_pct:.0f}% single-name limit"
                            ),
                            parameter=ticker,
                            threshold=mandate.max_single_name_pct,
                            hard_limit=True,
                        ),
                        actual_value=weight,
                        breach_severity="hard",
                        description=(
                            f"{ticker}: {weight:.1f}% > "
                            f"{mandate.max_single_name_pct:.0f}% SPS 530 single-name cap"
                        ),
                    )
                )

        # 2 ── International allocation cap ──────────────────────────────
        intl_total = sum(
            w for t, w in weights.items() if t not in au_set
        )
        if intl_total > mandate.max_international_pct:
            violations.append(
                MandateViolation(
                    rule=MandateRule(
                        rule_id="SPS530_INTL",
                        rule_type="international_cap",
                        description=(
                            f"International allocation exceeds "
                            f"{mandate.max_international_pct:.0f}% cap"
                        ),
                        threshold=mandate.max_international_pct,
                        hard_limit=True,
                    ),
                    actual_value=intl_total,
                    breach_severity="hard",
                    description=(
                        f"International: {intl_total:.1f}% > "
                        f"{mandate.max_international_pct:.0f}% limit"
                    ),
                )
            )

        # 3 ── AU domestic minimum (soft warning) ────────────────────────
        au_total = sum(w for t, w in weights.items() if t in au_set)
        if mandate.min_au_allocation_pct > 0 and au_total < mandate.min_au_allocation_pct:
            warnings.append(
                f"AU domestic allocation {au_total:.1f}% is below the "
                f"recommended minimum of {mandate.min_au_allocation_pct:.0f}% "
                f"for a {mandate.mandate_type} super fund option."
            )

        # 4 ── Growth-asset floor (soft warning) ─────────────────────────
        # Approximate: treat all equities as growth assets
        growth_total = sum(weights.values())  # 100% equity portfolio
        if mandate.min_growth_assets_pct > 0 and growth_total < mandate.min_growth_assets_pct:
            warnings.append(
                f"Growth asset allocation {growth_total:.1f}% is below "
                f"the {mandate.mandate_type} option minimum of "
                f"{mandate.min_growth_assets_pct:.0f}%."
            )

        is_compliant = all(v.breach_severity != "hard" for v in violations)
        mandate_id = f"AU_SUPER_{mandate_type.upper()}_SPS530"

        logger.info(
            "Super mandate check — type=%s compliant=%s violations=%d warnings=%d",
            mandate_type,
            is_compliant,
            len(violations),
            len(warnings),
        )

        return MandateCheckResult(
            run_id=run_id,
            mandate_id=mandate_id,
            violations=violations,
            is_compliant=is_compliant,
            warnings=warnings,
        )

    def describe_mandate(self, mandate_type: str) -> str:
        """Return a human-readable description of the mandate type."""
        m = self.get_mandate(mandate_type)
        return (
            f"{m.mandate_type.title()} Option ({m.description}) — "
            f"max single-name {m.max_single_name_pct:.0f}%, "
            f"growth assets {m.min_growth_assets_pct:.0f}–{m.max_growth_assets_pct:.0f}%, "
            f"max international {m.max_international_pct:.0f}%, "
            f"min AU domestic {m.min_au_allocation_pct:.0f}%."
        )
