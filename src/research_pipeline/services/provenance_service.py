"""
src/research_pipeline/services/provenance_service.py
----------------------------------------------------
Session 17 — Provenance Service

Builds ProvenanceCards from PipelineEngine state after each stage.
Called by the engine after stage execution to populate lineage data.

Also builds ReportSectionProvenance records by parsing the final
report markdown and matching sections to source stages.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Optional

from research_pipeline.schemas.provenance import (
    DataSource,
    ProvenanceCard,
    ProvenancePacket,
    ReportSectionProvenance,
    StageOutput,
)

logger = logging.getLogger(__name__)

# ── Stage → input mapping (what each stage consumes) ─────────────────────

STAGE_INPUTS: dict[int, list[dict[str, str]]] = {
    0: [
        {"name": "pipeline_config", "source_type": "file"},
        {"name": "api_keys", "source_type": "file"},
        {"name": "golden_tests", "source_type": "computed"},
    ],
    1: [
        {"name": "ticker_universe", "source_type": "api"},
        {"name": "fmp_validation", "source_type": "api"},
    ],
    2: [
        {"name": "fmp_financials", "source_type": "api"},
        {"name": "yfinance_prices", "source_type": "api"},
        {"name": "finnhub_metrics", "source_type": "api"},
    ],
    3: [
        {"name": "stage_2_data", "source_type": "upstream_stage", "stage_origin": "2"},
    ],
    4: [
        {"name": "stage_2_data", "source_type": "upstream_stage", "stage_origin": "2"},
        {"name": "stage_3_reconciled", "source_type": "upstream_stage", "stage_origin": "3"},
    ],
    5: [
        {"name": "stage_2_data", "source_type": "upstream_stage", "stage_origin": "2"},
        {"name": "qualitative_sources", "source_type": "api"},
    ],
    6: [
        {"name": "stage_5_evidence", "source_type": "upstream_stage", "stage_origin": "5"},
        {"name": "stage_2_data", "source_type": "upstream_stage", "stage_origin": "2"},
        {"name": "sector_fundamentals", "source_type": "api"},
    ],
    7: [
        {"name": "stage_2_data", "source_type": "upstream_stage", "stage_origin": "2"},
        {"name": "stage_6_sector", "source_type": "upstream_stage", "stage_origin": "6"},
        {"name": "dcf_computation", "source_type": "computed"},
    ],
    8: [
        {"name": "economic_indicators", "source_type": "api"},
        {"name": "fred_data", "source_type": "api"},
        {"name": "stage_2_data", "source_type": "upstream_stage", "stage_origin": "2"},
    ],
    9: [
        {"name": "stage_2_data", "source_type": "upstream_stage", "stage_origin": "2"},
        {"name": "stage_7_valuations", "source_type": "upstream_stage", "stage_origin": "7"},
        {"name": "stage_8_macro", "source_type": "upstream_stage", "stage_origin": "8"},
        {"name": "returns_data", "source_type": "computed"},
    ],
    10: [
        {"name": "all_prior_outputs", "source_type": "upstream_stage"},
        {"name": "stage_5_claims", "source_type": "upstream_stage", "stage_origin": "5"},
    ],
    11: [
        {"name": "all_prior_outputs", "source_type": "upstream_stage"},
        {"name": "stage_10_red_team", "source_type": "upstream_stage", "stage_origin": "10"},
    ],
    12: [
        {"name": "stage_6_sector", "source_type": "upstream_stage", "stage_origin": "6"},
        {"name": "stage_7_valuations", "source_type": "upstream_stage", "stage_origin": "7"},
        {"name": "stage_9_risk", "source_type": "upstream_stage", "stage_origin": "9"},
        {"name": "client_mandate", "source_type": "file"},
    ],
    13: [
        {"name": "all_stage_outputs", "source_type": "upstream_stage"},
        {"name": "stage_11_review", "source_type": "upstream_stage", "stage_origin": "11"},
    ],
    14: [
        {"name": "stage_13_report", "source_type": "upstream_stage", "stage_origin": "13"},
        {"name": "run_record", "source_type": "computed"},
        {"name": "audit_packet", "source_type": "computed"},
    ],
}

# ── Stage → output descriptions ──────────────────────────────────────────

STAGE_OUTPUTS: dict[int, list[dict[str, str]]] = {
    0: [
        {
            "name": "config_validated",
            "output_type": "data",
            "description": "Validated configuration and API keys",
        }
    ],
    1: [
        {
            "name": "validated_universe",
            "output_type": "data",
            "description": "Confirmed and filtered ticker list",
        }
    ],
    2: [
        {
            "name": "financial_data",
            "output_type": "data",
            "description": "Ingested financial data per ticker",
        }
    ],
    3: [
        {
            "name": "reconciled_data",
            "output_type": "data",
            "description": "Cross-validated and reconciled dataset",
        }
    ],
    4: [
        {
            "name": "qa_scores",
            "output_type": "metric",
            "description": "Data quality scores and lineage metadata",
        }
    ],
    5: [
        {
            "name": "evidence_library",
            "output_type": "data",
            "description": "Verified claims with source citations",
        }
    ],
    6: [
        {
            "name": "sector_analyses",
            "output_type": "data",
            "description": "6-box sector analysis per ticker/sector",
        }
    ],
    7: [
        {
            "name": "valuation_models",
            "output_type": "data",
            "description": "DCF + multi-methodology valuations",
        }
    ],
    8: [
        {
            "name": "macro_overlay",
            "output_type": "data",
            "description": "Macroeconomic and geopolitical context",
        }
    ],
    9: [
        {
            "name": "risk_assessment",
            "output_type": "data",
            "description": "Scenario analysis and risk metrics",
        }
    ],
    10: [
        {
            "name": "red_team_report",
            "output_type": "data",
            "description": "Falsification tests and risk challenges",
        }
    ],
    11: [
        {
            "name": "review_result",
            "output_type": "decision",
            "description": "Associate review pass/fail with feedback",
        }
    ],
    12: [
        {
            "name": "portfolio",
            "output_type": "decision",
            "description": "Portfolio weights, IC decision, mandate compliance",
        }
    ],
    13: [
        {
            "name": "final_report",
            "output_type": "artifact",
            "description": "Assembled research report markdown",
        }
    ],
    14: [
        {
            "name": "monitoring_record",
            "output_type": "data",
            "description": "Run registry record and audit artefact",
        }
    ],
}

# ── Stage → assumptions ──────────────────────────────────────────────────

STAGE_ASSUMPTIONS: dict[int, list[str]] = {
    0: ["API keys are valid and have sufficient quota"],
    1: ["Ticker symbols are valid and trading on major exchanges"],
    2: ["FMP/yfinance/Finnhub APIs return current data", "Missing data fields are non-critical"],
    3: ["Source data agreement within 10% is acceptable"],
    4: ["Quality score ≥ 0.6 is sufficient to proceed"],
    5: [
        "LLM-generated claims are subject to hallucination risk",
        "Source tier classification is heuristic",
    ],
    6: ["Sector boundaries are correctly assigned per GICS classification"],
    7: [
        "DCF terminal growth rate of 3% is appropriate",
        "WACC assumptions match current market conditions",
    ],
    8: [
        "Economic indicators are representative of macro conditions",
        "Political risk assessment may lag current events",
    ],
    9: [
        "Synthetic returns are used when live data unavailable",
        "VaR/CVaR computed at 95% confidence",
    ],
    10: [
        "Red team prompts cover major risk categories",
        "Falsification tests may miss novel risks",
    ],
    11: ["Review agent applies consistent scoring methodology"],
    12: [
        "Portfolio constraints match client mandate",
        "Optimisation uses available return/risk data",
    ],
    13: ["Report structure follows standard research format"],
    14: ["Monitoring snapshot reflects end-of-pipeline state"],
}


class ProvenanceService:
    """Builds and manages provenance records for pipeline runs."""

    def __init__(self, run_id: str, model: str = "unknown", temperature: float = 0.3):
        self.run_id = run_id
        self.model = model
        self.temperature = temperature
        self._cards: list[ProvenanceCard] = []

    def build_stage_card(
        self,
        stage_num: int,
        stage_label: str,
        stage_output: Any,
        gate_passed: Optional[bool],
        gate_reason: str = "",
        gate_blockers: Optional[list[str]] = None,
        duration_ms: float = 0.0,
        error: Optional[str] = None,
    ) -> ProvenanceCard:
        """Build a ProvenanceCard for a completed stage."""

        # Agent name from output
        agent_name = None
        if isinstance(stage_output, dict):
            agent_name = stage_output.get("agent_name")

        # Build DataSource inputs
        inputs = []
        for inp in STAGE_INPUTS.get(stage_num, []):
            origin = int(inp["stage_origin"]) if "stage_origin" in inp else None
            inputs.append(
                DataSource(
                    name=inp["name"],
                    source_type=inp.get("source_type", "unknown"),
                    stage_origin=origin,
                )
            )

        # Build StageOutput outputs
        outputs = []
        for out in STAGE_OUTPUTS.get(stage_num, []):
            outputs.append(
                StageOutput(
                    name=out["name"],
                    output_type=out.get("output_type", "data"),
                    description=out.get("description", ""),
                )
            )

        card = ProvenanceCard(
            stage_num=stage_num,
            stage_label=stage_label,
            run_id=self.run_id,
            agent_name=agent_name,
            model_used=self.model,
            model_temperature=self.temperature,
            inputs=inputs,
            outputs=outputs,
            gate_passed=gate_passed,
            gate_reason=gate_reason,
            gate_blockers=gate_blockers or [],
            assumptions=STAGE_ASSUMPTIONS.get(stage_num, []),
            duration_ms=duration_ms,
            error=error,
        )

        self._cards.append(card)
        return card

    def build_report_provenance(self, report_md: str) -> list[ReportSectionProvenance]:
        """Parse report markdown and build section-level provenance."""
        sections: list[ReportSectionProvenance] = []

        # Extract top-level sections (## headers)
        lines = report_md.split("\n")
        current_title = ""
        current_idx = 0

        for line in lines:
            header_match = re.match(r"^##\s+(.+)$", line)
            if header_match:
                current_title = header_match.group(1).strip()
                current_idx += 1

                # Map section titles to source stages
                source_stages, source_agents, methodology = self._map_section_to_sources(
                    current_title
                )

                sections.append(
                    ReportSectionProvenance(
                        section_title=current_title,
                        section_index=current_idx,
                        source_stages=source_stages,
                        source_agents=source_agents,
                        methodology_tags=methodology,
                        confidence_level=self._assess_confidence(source_stages),
                    )
                )

        return sections

    def build_packet(self, report_md: str = "") -> ProvenancePacket:
        """Build the complete ProvenancePacket."""
        report_sections = self.build_report_provenance(report_md) if report_md else []

        packet = ProvenancePacket(
            run_id=self.run_id,
            stage_cards=self._cards,
            report_sections=report_sections,
        )
        packet.compute_completeness()
        return packet

    def save_packet(self, packet: ProvenancePacket, storage_dir: Path) -> Path:
        """Persist the provenance packet to disk."""
        output_dir = storage_dir / "artifacts" / self.run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "provenance_packet.json"
        path.write_text(packet.model_dump_json(indent=2))
        logger.info("Provenance packet saved to %s", path)
        return path

    # ── Private helpers ──────────────────────────────────────────────────

    @staticmethod
    def _map_section_to_sources(title: str) -> tuple[list[int], list[str], list[str]]:
        """Map a report section title to its contributing stages."""
        title_lower = title.lower()
        stage_map: list[tuple[list[str], list[int], list[str], list[str]]] = [
            (["executive summary", "overview"], [5, 6, 7, 12], ["orchestrator"], ["synthesis"]),
            (["universe", "ticker", "coverage"], [1, 2], ["data_ingestion"], ["validation"]),
            (["data quality", "qa", "lineage"], [3, 4], ["reconciliation"], ["data_qa"]),
            (["evidence", "claim", "source"], [5], ["evidence_librarian"], ["claim_verification"]),
            (["sector", "industry"], [6], ["sector_analyst"], ["six_box_analysis"]),
            (
                ["valuation", "dcf", "fair value", "target price"],
                [7],
                ["valuation_analyst"],
                ["dcf", "multi_methodology"],
            ),
            (
                ["macro", "economic", "political", "geopolit"],
                [8],
                ["macro_agent", "political_agent"],
                ["macro_overlay"],
            ),
            (
                ["risk", "scenario", "stress", "var", "drawdown"],
                [9],
                ["risk_analyst"],
                ["scenario_analysis", "var"],
            ),
            (
                ["red team", "falsif", "challenge", "devil"],
                [10],
                ["red_team_analyst"],
                ["falsification"],
            ),
            (
                ["review", "methodology", "compliance"],
                [11],
                ["associate_reviewer"],
                ["methodology_review"],
            ),
            (
                ["portfolio", "weight", "allocation", "construct", "ic ", "investment committee"],
                [12],
                ["portfolio_manager"],
                ["portfolio_construction"],
            ),
            (["esg", "sustain", "environment"], [6, 12], ["esg_analyst"], ["esg_screening"]),
            (["monitor", "next step", "watch"], [14], ["monitoring"], ["monitoring"]),
            (
                ["appendix", "disclaimer", "disclosure"],
                [13, 14],
                ["report_narrative"],
                ["disclosure"],
            ),
        ]

        for keywords, stages, agents, methods in stage_map:
            if any(kw in title_lower for kw in keywords):
                return stages, agents, methods

        return [5, 6, 7], ["orchestrator"], ["general"]

    @staticmethod
    def _assess_confidence(source_stages: list[int]) -> str:
        """Heuristic confidence based on how many stages contributed."""
        if not source_stages:
            return "low"
        # Deterministic stages (0-4) are high confidence
        if all(s <= 4 for s in source_stages):
            return "high"
        # LLM-heavy stages (5-12) are medium
        if any(s >= 5 for s in source_stages):
            return "medium"
        return "medium"
