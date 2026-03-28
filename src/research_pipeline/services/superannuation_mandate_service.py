"""Session 14 — SuperannuationMandateService: AU super fund mandate types.

Supports the following mandate types:
- Growth (aggressive): 75-85% growth assets
- Balanced: 60-70% growth assets
- Conservative: 30-45% growth assets
- Lifecycle (age-based): glides from growth to conservative over time
- Direct Investment Option (DIO): member-directed allocation

Mandate gate checks against APRA SPS 530 diversification requirements.
"""

from __future__ import annotations

import logging
from typing import Literal, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

MandateType = Literal[
    "growth",
    "balanced",
    "conservative",
    "lifecycle",
    "direct_investment_option",
    "hnw_bespoke",
]


class SuperMandateConstraints(BaseModel):
    """Asset allocation constraints for a super fund mandate type."""

    mandate_type: MandateType
    min_growth_assets_pct: float
    max_growth_assets_pct: float
    min_defensive_assets_pct: float
    max_defensive_assets_pct: float
    max_single_stock_pct: float = 5.0       # APRA SPS 530 concentration limit
    max_single_sector_pct: float = 30.0
    max_international_equities_pct: float = 50.0
    max_unlisted_assets_pct: float = 30.0   # APRA liquidity requirement
    min_liquidity_pct: float = 5.0          # cash + liquid equivalents
    allows_direct_equities: bool = True
    requires_diversification: bool = True   # SPS 530 diversification obligation


class SuperMandateViolation(BaseModel):
    """A specific mandate constraint violation."""

    constraint: str
    description: str
    actual_value: float = 0.0
    limit_value: float = 0.0
    severity: Literal["critical", "warning", "info"] = "warning"


class SuperMandateCheckResult(BaseModel):
    """Result of checking a portfolio against super fund mandate constraints."""

    mandate_type: MandateType
    is_compliant: bool = True
    violations: list[SuperMandateViolation] = Field(default_factory=list)
    growth_assets_pct: float = 0.0
    defensive_assets_pct: float = 0.0
    largest_single_position_pct: float = 0.0
    international_equities_pct: float = 0.0
    apra_sps530_compliant: bool = True
    notes: str = ""


# Default mandate configurations
_MANDATE_CONFIGS: dict[MandateType, SuperMandateConstraints] = {
    "growth": SuperMandateConstraints(
        mandate_type="growth",
        min_growth_assets_pct=75.0,
        max_growth_assets_pct=90.0,
        min_defensive_assets_pct=10.0,
        max_defensive_assets_pct=25.0,
    ),
    "balanced": SuperMandateConstraints(
        mandate_type="balanced",
        min_growth_assets_pct=60.0,
        max_growth_assets_pct=75.0,
        min_defensive_assets_pct=25.0,
        max_defensive_assets_pct=40.0,
    ),
    "conservative": SuperMandateConstraints(
        mandate_type="conservative",
        min_growth_assets_pct=30.0,
        max_growth_assets_pct=45.0,
        min_defensive_assets_pct=55.0,
        max_defensive_assets_pct=70.0,
        max_single_stock_pct=3.0,
        max_international_equities_pct=20.0,
    ),
    "lifecycle": SuperMandateConstraints(
        mandate_type="lifecycle",
        min_growth_assets_pct=50.0,   # mid-career baseline
        max_growth_assets_pct=80.0,
        min_defensive_assets_pct=20.0,
        max_defensive_assets_pct=50.0,
    ),
    "direct_investment_option": SuperMandateConstraints(
        mandate_type="direct_investment_option",
        min_growth_assets_pct=0.0,
        max_growth_assets_pct=100.0,
        min_defensive_assets_pct=0.0,
        max_defensive_assets_pct=100.0,
        max_single_stock_pct=20.0,  # DIO allows higher concentration
        requires_diversification=False,
    ),
    "hnw_bespoke": SuperMandateConstraints(
        mandate_type="hnw_bespoke",
        min_growth_assets_pct=0.0,
        max_growth_assets_pct=100.0,
        min_defensive_assets_pct=0.0,
        max_defensive_assets_pct=100.0,
        max_single_stock_pct=15.0,
    ),
}

# GICS sector → growth or defensive classification
_GROWTH_SECTORS = {
    "Information Technology", "Consumer Discretionary", "Industrials",
    "Materials", "Real Estate", "Communication Services", "Energy",
    "Health Care",  # counted as growth for AU super allocation purposes
    "Semiconductors", "Infrastructure", "Power & Energy", "compute",
    "power_energy", "infrastructure",
}
_DEFENSIVE_SECTORS = {
    "Consumer Staples", "Utilities", "Financials",
    "Fixed Income", "Cash",
}


class SuperannuationMandateService:
    """Check portfolio weights against super fund mandate constraints.

    Handles AU-specific APRA SPS 530 diversification requirements.
    """

    def get_constraints(self, mandate_type: MandateType) -> SuperMandateConstraints:
        """Return the constraint set for the given mandate type."""
        return _MANDATE_CONFIGS.get(
            mandate_type, _MANDATE_CONFIGS["balanced"]
        )

    def check_mandate(
        self,
        run_id: str,
        portfolio_weights: dict[str, float],
        mandate_type: MandateType = "balanced",
        sector_map: Optional[dict[str, str]] = None,
        member_age: Optional[int] = None,
    ) -> SuperMandateCheckResult:
        """Check portfolio weights against super fund mandate constraints.

        Args:
            portfolio_weights: ticker -> weight (percentages summing to ~100)
            mandate_type: super fund mandate type
            sector_map: ticker -> sector label for growth/defensive classification
            member_age: for lifecycle mandates, adjusts growth allocation
        """
        constraints = self.get_constraints(mandate_type)

        # Lifecycle adjustment: reduce growth allocation as member ages
        if mandate_type == "lifecycle" and member_age is not None:
            if member_age >= 60:
                constraints = SuperMandateConstraints(
                    **{**constraints.model_dump(),
                       "min_growth_assets_pct": 30.0,
                       "max_growth_assets_pct": 50.0,
                       "min_defensive_assets_pct": 50.0,
                       "max_defensive_assets_pct": 70.0}
                )
            elif member_age >= 50:
                constraints = SuperMandateConstraints(
                    **{**constraints.model_dump(),
                       "min_growth_assets_pct": 50.0,
                       "max_growth_assets_pct": 65.0}
                )

        sm = sector_map or {}
        violations: list[SuperMandateViolation] = []

        # Classify weights as growth vs defensive
        total_weight = sum(portfolio_weights.values()) or 1.0
        growth_pct = 0.0
        defensive_pct = 0.0
        for ticker, weight in portfolio_weights.items():
            sector = sm.get(ticker, "Information Technology")
            w_pct = weight / total_weight * 100
            if sector in _GROWTH_SECTORS:
                growth_pct += w_pct
            else:
                defensive_pct += w_pct

        # If no sector map given, treat all as growth (equity portfolio)
        if not sm:
            growth_pct = 100.0
            defensive_pct = 0.0

        # Largest single position
        max_pos_pct = max(
            (w / total_weight * 100 for w in portfolio_weights.values()), default=0.0
        )

        # International equities: non-.AX tickers
        intl_pct = sum(
            w / total_weight * 100
            for t, w in portfolio_weights.items()
            if not t.endswith(".AX")
        )

        # Check violations
        if growth_pct < constraints.min_growth_assets_pct and constraints.requires_diversification:
            violations.append(SuperMandateViolation(
                constraint="min_growth_assets",
                description=f"Growth assets {growth_pct:.1f}% below minimum {constraints.min_growth_assets_pct:.0f}%",
                actual_value=growth_pct,
                limit_value=constraints.min_growth_assets_pct,
                severity="warning",
            ))
        if growth_pct > constraints.max_growth_assets_pct:
            violations.append(SuperMandateViolation(
                constraint="max_growth_assets",
                description=f"Growth assets {growth_pct:.1f}% exceeds maximum {constraints.max_growth_assets_pct:.0f}%",
                actual_value=growth_pct,
                limit_value=constraints.max_growth_assets_pct,
                severity="critical",
            ))
        if max_pos_pct > constraints.max_single_stock_pct:
            violations.append(SuperMandateViolation(
                constraint="max_single_stock",
                description=f"Largest position {max_pos_pct:.1f}% exceeds SPS 530 limit {constraints.max_single_stock_pct:.0f}%",
                actual_value=max_pos_pct,
                limit_value=constraints.max_single_stock_pct,
                severity="critical",
            ))
        if intl_pct > constraints.max_international_equities_pct:
            violations.append(SuperMandateViolation(
                constraint="max_international",
                description=f"International equities {intl_pct:.1f}% exceeds limit {constraints.max_international_equities_pct:.0f}%",
                actual_value=intl_pct,
                limit_value=constraints.max_international_equities_pct,
                severity="warning",
            ))

        apra_compliant = not any(v.severity == "critical" for v in violations)
        is_compliant = len(violations) == 0

        return SuperMandateCheckResult(
            mandate_type=mandate_type,
            is_compliant=is_compliant,
            violations=violations,
            growth_assets_pct=round(growth_pct, 2),
            defensive_assets_pct=round(defensive_pct, 2),
            largest_single_position_pct=round(max_pos_pct, 2),
            international_equities_pct=round(intl_pct, 2),
            apra_sps530_compliant=apra_compliant,
            notes=(
                f"Mandate: {mandate_type.replace('_', ' ').title()}. "
                f"{'APRA SPS 530 compliant.' if apra_compliant else 'APRA SPS 530 violation detected.'}"
            ),
        )
