"""Macro economy and regime analysis schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MacroRegime(str, Enum):
    """Current macro environment classification."""

    EXPANSION = "expansion"
    LATE_CYCLE = "late_cycle"
    SLOWDOWN = "slowdown"
    RECESSION = "recession"
    RECOVERY = "recovery"
    UNKNOWN = "unknown"


class ConfidenceLevel(str, Enum):
    """Confidence in macro analysis."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SensitivityLevel(str, Enum):
    """Ticker sensitivity to macro/rate factors."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class MacroContextPacket(BaseModel):
    """Typed macro context from Stage 8 for threading through downstream stages.

    This packet is created by _get_macro_context() helper (ARC-1) and passed
    to Stages 9, 10, 11, 12 to ensure consistent macro awareness across
    risk assessment, red team, review, and portfolio construction.

    Required by: ISS-1 (typed validation), ARC-1 (macro context helper).
    """

    run_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Core regime classification
    regime_classification: str = "unknown"
    regime_enum: MacroRegime = MacroRegime.UNKNOWN
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM

    # Key macro variables
    fed_funds_rate: Optional[str] = None  # "current + expectations"
    ten_year_yield: Optional[str] = None
    pmi: Optional[str] = None
    capex_cycle_phase: Optional[str] = None
    ai_investment_cycle_phase: Optional[str] = None

    # Additional macro variables (key-value pairs from agent output)
    key_macro_variables: dict[str, str] = Field(default_factory=dict)

    # Winners and losers in current regime
    regime_winners: list[str] = Field(default_factory=list)
    regime_losers: list[str] = Field(default_factory=list)

    # Sensitivity mappings
    rate_sensitivity: dict[str, str] = Field(
        default_factory=dict
    )  # ticker -> "HIGH | MEDIUM | LOW — reason"
    cyclical_sensitivity: dict[str, str] = Field(default_factory=dict)

    # Risk and policy watch
    key_risks_to_regime: list[str] = Field(default_factory=list)
    policy_watch: list[str] = Field(default_factory=list)

    # Political risk context (from Stage 8 political agent)
    political_risk_present: bool = False
    political_summary: str = ""

    # Quality flag
    is_valid: bool = True
    validation_errors: list[str] = Field(default_factory=list)

    @classmethod
    def from_stage_8_output(cls, stage_8_dict: dict, run_id: str) -> MacroContextPacket:
        """Parse Stage 8 output dict into typed MacroContextPacket.

        Stage 8 may contain {"macro": {...}, "political": {...}} or just macro dict.
        """
        macro_data = {}
        political_data = {}

        # Handle both {"macro": ..., "political": ...} and direct macro dict
        if "macro" in stage_8_dict:
            macro_data = stage_8_dict.get("macro", {})
            political_data = stage_8_dict.get("political", {})
        else:
            macro_data = stage_8_dict

        # Extract macro fields with defaults
        regime_class = macro_data.get("regime_classification", "unknown")

        # Try to map regime_classification string to enum
        regime_enum = MacroRegime.UNKNOWN
        regime_lower = regime_class.lower().replace(" ", "_").replace("-", "_")
        for r in MacroRegime:
            if r.value in regime_lower or regime_lower in r.value:
                regime_enum = r
                break

        # Parse confidence
        confidence_str = macro_data.get("confidence", "MEDIUM").upper()
        confidence = ConfidenceLevel.MEDIUM
        try:
            confidence = ConfidenceLevel(confidence_str)
        except ValueError:
            pass

        # Extract key macro variables
        key_vars = macro_data.get("key_macro_variables", {})

        # Build packet
        packet = cls(
            run_id=run_id,
            regime_classification=regime_class,
            regime_enum=regime_enum,
            confidence=confidence,
            fed_funds_rate=key_vars.get("fed_funds_rate"),
            ten_year_yield=key_vars.get("10y_yield"),
            pmi=key_vars.get("pmi"),
            capex_cycle_phase=key_vars.get("capex_cycle_phase"),
            ai_investment_cycle_phase=key_vars.get("ai_investment_cycle_phase"),
            key_macro_variables=key_vars,
            regime_winners=macro_data.get("regime_winners", []),
            regime_losers=macro_data.get("regime_losers", []),
            rate_sensitivity=macro_data.get("rate_sensitivity", {}),
            cyclical_sensitivity=macro_data.get("cyclical_sensitivity", {}),
            key_risks_to_regime=macro_data.get("key_risks_to_regime", []),
            policy_watch=macro_data.get("policy_watch", []),
            political_risk_present=bool(political_data),
            political_summary=political_data.get("summary", "") if political_data else "",
        )

        # Validate critical fields
        if not packet.regime_classification or packet.regime_classification == "unknown":
            packet.validation_errors.append("regime_classification missing or unknown")
            packet.is_valid = False

        if not packet.key_macro_variables:
            packet.validation_errors.append("key_macro_variables empty")
            packet.is_valid = False

        return packet

    def summary_text(self) -> str:
        """One-line summary for logs and agent prompts."""
        return (
            f"Regime: {self.regime_classification} (confidence: {self.confidence.value}), "
            f"Winners: {', '.join(self.regime_winners[:3]) if self.regime_winners else 'none'}, "
            f"Key risks: {', '.join(self.key_risks_to_regime[:2]) if self.key_risks_to_regime else 'none'}"
        )
