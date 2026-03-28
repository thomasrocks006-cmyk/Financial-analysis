"""Mandate Compliance Engine — check portfolios against investment guidelines."""

from __future__ import annotations

import logging

from research_pipeline.schemas.governance import (
    MandateConfig,
    MandateRule,
    MandateViolation,
    MandateCheckResult,
)

logger = logging.getLogger(__name__)

# Default subtheme mapping
TICKER_SUBTHEMES = {
    "NVDA": "compute",
    "AVGO": "compute",
    "TSM": "compute",
    "AMD": "compute",
    "ANET": "compute",
    "CEG": "power",
    "VST": "power",
    "GEV": "power",
    "NLR": "power",
    "PWR": "infrastructure",
    "ETN": "infrastructure",
    "HUBB": "infrastructure",
    "APH": "infrastructure",
    "FIX": "infrastructure",
    "NXT": "infrastructure",
    "FCX": "materials",
    "BHP": "materials",
}


def default_mandate() -> MandateConfig:
    """Return the default AI Infrastructure mandate."""
    return MandateConfig(
        mandate_id="AI_INFRA_DEFAULT",
        name="AI Infrastructure Thematic Mandate",
        max_single_name_pct=15.0,
        max_sector_pct=40.0,
        min_positions=8,
        max_positions=25,
        min_liquidity_adv_days=5.0,
        rules=[
            MandateRule(
                rule_id="R001",
                rule_type="max_weight",
                description="No single name >15%",
                threshold=15.0,
                hard_limit=True,
            ),
            MandateRule(
                rule_id="R002",
                rule_type="sector_cap",
                description="No sector >40%",
                parameter="compute",
                threshold=40.0,
                hard_limit=True,
            ),
            MandateRule(
                rule_id="R003",
                rule_type="sector_cap",
                description="No sector >40%",
                parameter="power",
                threshold=40.0,
                hard_limit=True,
            ),
            MandateRule(
                rule_id="R004",
                rule_type="sector_cap",
                description="No sector >40%",
                parameter="infrastructure",
                threshold=40.0,
                hard_limit=True,
            ),
            MandateRule(
                rule_id="R005",
                rule_type="min_positions",
                description="Minimum 8 positions",
                threshold=8.0,
                hard_limit=True,
            ),
            MandateRule(
                rule_id="R006",
                rule_type="max_positions",
                description="Maximum 25 positions",
                threshold=25.0,
                hard_limit=False,
            ),
        ],
    )


class MandateComplianceEngine:
    """Check portfolio weights against mandate constraints — no LLM.

    Returns a list of violations that must be resolved before publication.
    """

    def __init__(self, mandate: MandateConfig | None = None):
        self.mandate = mandate or default_mandate()

    def check_compliance(
        self,
        run_id: str,
        weights: dict[str, float],
        subthemes: dict[str, str] | None = None,
        liquidity_days: dict[str, float] | None = None,
    ) -> MandateCheckResult:
        """Check a portfolio against all mandate rules."""
        subthemes = subthemes or TICKER_SUBTHEMES
        violations: list[MandateViolation] = []
        warnings: list[str] = []

        # Check single-name limits
        for ticker, weight in weights.items():
            if weight > self.mandate.max_single_name_pct:
                rule = MandateRule(
                    rule_id="R_NAME",
                    rule_type="max_weight",
                    description=f"{ticker} exceeds {self.mandate.max_single_name_pct}% limit",
                    parameter=ticker,
                    threshold=self.mandate.max_single_name_pct,
                    hard_limit=True,
                )
                violations.append(
                    MandateViolation(
                        rule=rule,
                        actual_value=weight,
                        breach_severity="hard",
                        description=f"{ticker}: {weight:.1f}% > {self.mandate.max_single_name_pct}% max",
                    )
                )

        # Check sector concentration
        sector_weights: dict[str, float] = {}
        for ticker, weight in weights.items():
            sector = subthemes.get(ticker, "other")
            sector_weights[sector] = sector_weights.get(sector, 0) + weight

        for sector, total in sector_weights.items():
            if total > self.mandate.max_sector_pct:
                rule = MandateRule(
                    rule_id=f"R_SECTOR_{sector.upper()}",
                    rule_type="sector_cap",
                    description=f"Sector '{sector}' exceeds {self.mandate.max_sector_pct}% cap",
                    parameter=sector,
                    threshold=self.mandate.max_sector_pct,
                    hard_limit=True,
                )
                violations.append(
                    MandateViolation(
                        rule=rule,
                        actual_value=total,
                        breach_severity="hard",
                        description=f"Sector '{sector}': {total:.1f}% > {self.mandate.max_sector_pct}% max",
                    )
                )

        # Check position count
        n_positions = len(weights)
        if n_positions < self.mandate.min_positions:
            violations.append(
                MandateViolation(
                    rule=MandateRule(
                        rule_id="R_MIN_POS",
                        rule_type="min_positions",
                        description=f"Below minimum {self.mandate.min_positions} positions",
                        threshold=self.mandate.min_positions,
                        hard_limit=True,
                    ),
                    actual_value=n_positions,
                    breach_severity="hard",
                    description=f"Only {n_positions} positions, minimum is {self.mandate.min_positions}",
                )
            )

        if n_positions > self.mandate.max_positions:
            warnings.append(
                f"Portfolio has {n_positions} positions, above soft limit of {self.mandate.max_positions}"
            )

        # Check liquidity
        if liquidity_days:
            for ticker, days in liquidity_days.items():
                if days > self.mandate.min_liquidity_adv_days * 2:
                    warnings.append(
                        f"{ticker}: {days:.1f} days to liquidate exceeds 2x ADV threshold"
                    )

        is_compliant = len([v for v in violations if v.breach_severity == "hard"]) == 0

        return MandateCheckResult(
            run_id=run_id,
            mandate_id=self.mandate.mandate_id,
            violations=violations,
            is_compliant=is_compliant,
            warnings=warnings,
        )
