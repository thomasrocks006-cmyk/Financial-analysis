"""Australian superannuation mandate helper service."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SuperMandateProfile:
    mandate_type: str
    max_single_name_pct: float
    max_equity_pct: float
    min_defensive_assets_pct: float
    description: str


_MANDATE_PROFILES: dict[str, SuperMandateProfile] = {
    "conservative": SuperMandateProfile(
        mandate_type="conservative",
        max_single_name_pct=8.0,
        max_equity_pct=50.0,
        min_defensive_assets_pct=40.0,
        description="Capital preservation focus with high defensive exposure.",
    ),
    "balanced": SuperMandateProfile(
        mandate_type="balanced",
        max_single_name_pct=10.0,
        max_equity_pct=70.0,
        min_defensive_assets_pct=20.0,
        description="Balanced growth and income profile used by mainstream super options.",
    ),
    "growth": SuperMandateProfile(
        mandate_type="growth",
        max_single_name_pct=12.0,
        max_equity_pct=85.0,
        min_defensive_assets_pct=5.0,
        description="Growth-tilted profile appropriate for long-horizon super members.",
    ),
    "lifecycle": SuperMandateProfile(
        mandate_type="lifecycle",
        max_single_name_pct=10.0,
        max_equity_pct=75.0,
        min_defensive_assets_pct=15.0,
        description="Lifecycle default option with moderate diversification constraints.",
    ),
    "dio": SuperMandateProfile(
        mandate_type="dio",
        max_single_name_pct=15.0,
        max_equity_pct=100.0,
        min_defensive_assets_pct=0.0,
        description="Direct investment option with looser asset-mix limits but single-name caps.",
    ),
}


class SuperannuationMandateService:
    """Return AU super mandate profiles and derived limits."""

    def get_profile(self, mandate_type: str) -> SuperMandateProfile:
        return _MANDATE_PROFILES.get(mandate_type.lower(), _MANDATE_PROFILES["growth"])

    def get_limits(self, mandate_type: str) -> dict[str, float | str]:
        profile = self.get_profile(mandate_type)
        return {
            "mandate_type": profile.mandate_type,
            "max_single_name_pct": profile.max_single_name_pct,
            "max_equity_pct": profile.max_equity_pct,
            "min_defensive_assets_pct": profile.min_defensive_assets_pct,
            "description": profile.description,
        }
