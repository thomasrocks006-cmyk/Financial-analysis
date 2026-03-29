"""
src/research_pipeline/schemas/run_request.py
---------------------------------------------
Session 15 — Phase 3: RunRequest schema

The canonical request body for starting a pipeline run via the API or CLI.
All fields mirror settings/config parameters so any consumer can drive the
full pipeline without needing to understand the internal config structure.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# ── Default universes ────────────────────────────────────────────────────────

_DEFAULT_US_UNIVERSE = [
    "NVDA", "AMD", "AVGO", "MRVL", "ARM", "TSM",
    "MSFT", "AMZN", "GOOGL", "META",
    "EQIX", "DLR", "VRT", "DELL", "SMCI",
]

_DEFAULT_AU_UNIVERSE = [
    "CBA.AX", "WBC.AX", "NAB.AX", "ANZ.AX",
    "BHP.AX", "RIO.AX", "FMG.AX",
    "TLS.AX", "WES.AX", "WOW.AX",
]


class RunRequest(BaseModel):
    """API request body for starting a new pipeline run.

    Mirrors the internal Settings + PipelineConfig in a consumer-friendly,
    API-stable schema.  The FastAPI layer maps these fields onto the engine
    before launching the run.
    """

    # ── Core run config ──────────────────────────────────────────────────
    universe: list[str] = Field(
        default_factory=lambda: list(_DEFAULT_US_UNIVERSE),
        min_length=1,
        max_length=100,
        description="List of ticker symbols to analyse.",
    )
    run_label: Optional[str] = Field(
        default=None,
        max_length=120,
        description="Human-readable label for this run (surfaced in UI + reports).",
    )

    # ── LLM config ───────────────────────────────────────────────────────
    llm_model: str = Field(
        default="claude-sonnet-4-6",
        description="LLM model identifier passed to BaseAgent.",
    )
    llm_temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for all LLM calls.",
    )

    # ── Portfolio config ─────────────────────────────────────────────────
    max_positions: int = Field(
        default=25,
        ge=1,
        le=100,
        description="Maximum number of positions in the constructed portfolio.",
    )
    benchmark_ticker: str = Field(
        default="^GSPC",
        description="Benchmark ticker for attribution (e.g. ^GSPC, ^AXJO, SPY).",
    )
    portfolio_variants: list[str] = Field(
        default_factory=lambda: ["balanced", "higher_return", "lower_volatility"],
        description="Portfolio variant labels to construct.",
    )

    # ── Market targeting ─────────────────────────────────────────────────
    market: Literal["us", "au", "global", "mixed"] = Field(
        default="us",
        description="Target market — influences which sector agents and benchmarks are used.",
    )

    # ── AU client context (Session 14) ───────────────────────────────────
    client_profile: Optional[Any] = Field(
        default=None,
        description="ClientProfile schema for AU super fund / SMSF / HNW clients.",
    )

    # ── Validation ───────────────────────────────────────────────────────
    @field_validator("universe")
    @classmethod
    def universe_must_be_non_empty(cls, v: list[str]) -> list[str]:
        cleaned = [t.strip().upper() for t in v if t.strip()]
        if not cleaned:
            raise ValueError("universe must contain at least one non-empty ticker")
        return cleaned

    @field_validator("run_label")
    @classmethod
    def sanitise_label(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip()[:120]
        return v

    # ── Convenience methods ───────────────────────────────────────────────
    def to_settings_overrides(self) -> dict[str, Any]:
        """Return kwargs suitable for overriding Settings fields."""
        return {
            "llm_model": self.llm_model,
            "llm_temperature": self.llm_temperature,
        }
