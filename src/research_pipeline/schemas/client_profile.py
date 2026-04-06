"""Client profile schema — Session 14: Australian Client Context.

Captures the client-type, AU residency, superannuation type, and
allocation targets needed to:
  1. Route to the correct SuperannuationMandate (APRA SPS 530)
  2. Compute tax-adjusted returns (AustralianTaxService)
  3. Inject AU-specific disclosures into the final report
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ── Type literals ──────────────────────────────────────────────────────────
ClientType = Literal["super_fund", "smsf", "hnw", "institutional", "retail"]

SuperFundMandateType = Literal[
    "growth",  # 60–85 % growth assets — typical default MySuper option
    "balanced",  # 40–70 % growth assets — most common balanced option
    "conservative",  # 0–30 % growth assets — capital preservation focus
    "lifecycle",  # glide-path: high-growth when young → conservative at 55
    "dio",  # Direct Investment Option — no APRA growth limits
]


class ClientProfile(BaseModel):
    """Complete client profile for AU-context-aware pipeline runs.

    Mandatory fields: client_id, client_type.
    Everything else has sensible defaults so existing tests remain unaffected.
    """

    # ── Identity ─────────────────────────────────────────────────────────
    client_id: str = "default"
    client_name: str = ""
    client_type: ClientType = "institutional"

    # ── Australian context ────────────────────────────────────────────────
    au_resident: bool = True
    is_smsf: bool = False
    super_fund_type: Optional[SuperFundMandateType] = None
    apra_regulated: bool = False
    smsf_pension_phase: bool = False  # True → 0 % tax on pension-phase earnings
    afsl_number: str = ""  # Authorised Financial Services Licence

    # ── Allocation targets (%) ────────────────────────────────────────────
    target_au_pct: float = Field(default=60.0, ge=0.0, le=100.0)
    target_us_pct: float = Field(default=30.0, ge=0.0, le=100.0)
    target_fi_pct: float = Field(default=10.0, ge=0.0, le=100.0)

    # ── Optional metadata ─────────────────────────────────────────────────
    notes: str = ""

    @model_validator(mode="after")
    def _infer_apra_and_smsf(self) -> "ClientProfile":
        """Auto-set apra_regulated and is_smsf from client_type."""
        if self.client_type == "super_fund":
            object.__setattr__(self, "apra_regulated", True)
        if self.client_type == "smsf":
            object.__setattr__(self, "is_smsf", True)
        return self

    # ── Derived properties ────────────────────────────────────────────────
    @property
    def is_super(self) -> bool:
        """True if client is any kind of superannuation entity."""
        return self.client_type in ("super_fund", "smsf")

    @property
    def effective_marginal_tax_rate(self) -> float:
        """Indicative marginal income tax rate for the client."""
        if self.client_type == "smsf":
            return 0.0 if self.smsf_pension_phase else 0.15
        if self.client_type == "super_fund":
            return 0.15
        if self.client_type == "hnw":
            return 0.47  # top marginal rate + Medicare levy
        return 0.325  # approximate mid-rate for retail / institutional

    @property
    def effective_cgt_discount(self) -> float:
        """CGT discount fraction (fraction of gain that is exempt after 12mo)."""
        if self.client_type == "smsf":
            if self.smsf_pension_phase:
                return 1.0  # fully exempt in pension phase
            return 0.333  # 1/3 discount for super funds (net effective 10%)
        if self.client_type == "super_fund":
            return 0.333
        # individuals — 50% discount on long-term gains
        return 0.50


# ── Convenience constructors ───────────────────────────────────────────────


def default_super_fund_profile(
    fund_type: SuperFundMandateType = "balanced",
    client_id: str = "super_fund_default",
) -> ClientProfile:
    """Return a typical large APRA-regulated super fund profile."""
    return ClientProfile(
        client_id=client_id,
        client_name="AU Superannuation Fund",
        client_type="super_fund",
        super_fund_type=fund_type,
        apra_regulated=True,
        au_resident=True,
        target_au_pct=55.0,
        target_us_pct=30.0,
        target_fi_pct=15.0,
    )


def default_smsf_profile(
    pension_phase: bool = False,
    client_id: str = "smsf_default",
) -> ClientProfile:
    """Return a typical SMSF (self-managed super fund) profile."""
    return ClientProfile(
        client_id=client_id,
        client_name="Self-Managed Super Fund",
        client_type="smsf",
        is_smsf=True,
        smsf_pension_phase=pension_phase,
        au_resident=True,
        target_au_pct=60.0,
        target_us_pct=30.0,
        target_fi_pct=10.0,
    )


def default_hnw_profile(client_id: str = "hnw_default") -> ClientProfile:
    """Return a typical high-net-worth AU individual profile."""
    return ClientProfile(
        client_id=client_id,
        client_name="HNW AU Individual",
        client_type="hnw",
        au_resident=True,
        target_au_pct=50.0,
        target_us_pct=40.0,
        target_fi_pct=10.0,
    )
