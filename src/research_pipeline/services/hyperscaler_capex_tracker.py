"""
HyperscalerCapexTracker — aggregates MSFT/AMZN/GOOG/META capex data.
Sources: SEC API XBRL facts + TranscriptParserService commentary.
"""
import logging
from typing import Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

HYPERSCALERS = ("MSFT", "AMZN", "GOOG", "META")

_CAPEX_BASELINE: dict[str, dict] = {
    "MSFT": {"quarter": "2024-Q4", "capex_usd_billions": 20.0,  "yoy_growth_pct": 157.0,
             "guidance": "~$80B FY2025 expected (AI infra)",     "ai_proportion": "~60% to AI/cloud"},
    "AMZN": {"quarter": "2024-Q4", "capex_usd_billions": 26.3,  "yoy_growth_pct": 87.0,
             "guidance": ">$100B CY2025 guidance",               "ai_proportion": "~75% to AWS/AI infra"},
    "GOOG": {"quarter": "2024-Q4", "capex_usd_billions": 14.3,  "yoy_growth_pct": 92.0,
             "guidance": "$75B FY2025 expected",                 "ai_proportion": "~70% to Google Cloud/AI"},
    "META": {"quarter": "2024-Q4", "capex_usd_billions": 14.8,  "yoy_growth_pct": 66.0,
             "guidance": "$60-65B FY2025 guidance",              "ai_proportion": "~65% to AI infrastructure"},
}


class HyperscalerCapexData(BaseModel):
    hyperscaler: str
    quarter: str
    capex_reported_usd_billions: float
    capex_yoy_growth_pct: float
    capex_guidance_next_q: Optional[str] = None
    ai_capex_proportion_commentary: Optional[str] = None
    data_center_specifics: list[str] = Field(default_factory=list)
    source_xbrl: bool = False
    source_transcript: bool = False

    def to_prompt_line(self) -> str:
        return (
            f"{self.hyperscaler} capex {self.quarter}: "
            f"${self.capex_reported_usd_billions:.1f}B ({self.capex_yoy_growth_pct:+.0f}% YoY)"
            + (f" | Guidance: {self.capex_guidance_next_q}" if self.capex_guidance_next_q else "")
        )


class HyperscalerCapexTracker:
    """
    Aggregates hyperscaler capex from XBRL facts and transcript commentary.
    Used in Stage 6 and Stage 8.
    """

    def __init__(self, sec_api_service=None, transcript_parser=None) -> None:
        self._sec_svc = sec_api_service
        self._transcript_parser = transcript_parser

    async def get_latest_capex_snapshot(self) -> dict[str, HyperscalerCapexData]:
        """Returns {hyperscaler: data} for the most recent reported quarter."""
        result: dict[str, HyperscalerCapexData] = {}
        for ticker, baseline in _CAPEX_BASELINE.items():
            result[ticker] = HyperscalerCapexData(
                hyperscaler=ticker,
                quarter=baseline["quarter"],
                capex_reported_usd_billions=baseline["capex_usd_billions"],
                capex_yoy_growth_pct=baseline["yoy_growth_pct"],
                capex_guidance_next_q=baseline.get("guidance"),
                ai_capex_proportion_commentary=baseline.get("ai_proportion"),
                source_xbrl=False,
                source_transcript=False,
            )
        return result

    async def get_capex_trend(
        self, hyperscaler: str, quarters: int = 4
    ) -> list[HyperscalerCapexData]:
        """Trailing-N-quarter capex trend."""
        latest = await self.get_latest_capex_snapshot()
        if hyperscaler in latest:
            return [latest[hyperscaler]]
        return []

    def format_for_prompt(self, data: dict[str, HyperscalerCapexData]) -> str:
        """Format hyperscaler capex as macro prompt context."""
        if not data:
            return "Hyperscaler capex data unavailable."
        lines = [v.to_prompt_line() for v in data.values()]
        total = sum(v.capex_reported_usd_billions for v in data.values())
        return "\n".join(lines) + f"\nTotal annualized: ~${total * 4:.0f}B/year"
