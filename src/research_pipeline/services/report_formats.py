"""Phase 7.9 — Client Report Format Service.

Supports three output formats:
  • institutional_pdf  — Full research report, structured JSON compatible
                          with downstream LaTeX/WeasyPrint rendering.
  • executive_summary  — 1-page condensed text for senior readers.
  • factsheet          — Compact KPI table format (NAV, weights, exposure, VaR).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class ReportFormat(str, Enum):
    INSTITUTIONAL_PDF = "institutional_pdf"
    EXECUTIVE_SUMMARY = "executive_summary"
    FACTSHEET = "factsheet"


@dataclass
class RenderedReport:
    """Output of a ReportFormatService.render() call."""
    run_id: str
    format_type: ReportFormat
    content: str           # JSON string (institutional_pdf) or text (others)
    rendered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    content_type: str = "text/plain"

    def save(self, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        ext = ".json" if self.content_type == "application/json" else ".txt"
        path = output_dir / f"{self.run_id}_{self.format_type.value}{ext}"
        path.write_text(self.content, encoding="utf-8")
        return path


class InstitutionalPDFFormat:
    """Full institutional research report — JSON structure for LaTeX/WeasyPrint.

    Sections follow JPAM-equivalent research memorandum convention:
      1. Cover & metadata
      2. Executive summary
      3. Portfolio construction thesis
      4. Position detail per position (four-box + valuation + red team)
      5. Risk package (VaR, factor exposure, scenario stresses)
      6. Mandate & ESG compliance
      7. IC decision & dissents
      8. Appendices
    """

    def render(self, run_id: str, pipeline_output: dict[str, Any]) -> str:
        final_report = pipeline_output.get("final_report", {})
        portfolio = pipeline_output.get("portfolio", {})
        risk = pipeline_output.get("risk_package", {})
        ic_outcome = pipeline_output.get("ic_outcome", {})
        mandate = pipeline_output.get("mandate_result", {})

        doc = {
            "document_type": "JPAM_RESEARCH_REPORT",
            "schema_version": "8.0",
            "metadata": {
                "run_id": run_id,
                "publication_date": date.today().isoformat(),
                "status": final_report.get("publication_status", "DRAFT"),
                "classification": "CONFIDENTIAL — FOR INSTITUTIONAL CLIENTS ONLY",
                "report_title": final_report.get("title", f"AI Infrastructure Portfolio — {run_id}"),
                "authors": final_report.get("authors", ["Research Division"]),
            },
            "sections": {
                "1_executive_summary": {
                    "portfolio_summary": final_report.get("portfolio_summary", ""),
                    "total_positions": len(portfolio.get("positions", [])),
                    "ic_decision": ic_outcome.get("decision", ""),
                    "ic_rationale": ic_outcome.get("rationale", ""),
                    "key_risks": final_report.get("key_risks", []),
                },
                "2_portfolio_construction": {
                    "variant": portfolio.get("variant", ""),
                    "positions": portfolio.get("positions", []),
                    "cash_weight": portfolio.get("cash_weight", 0.0),
                    "concentration_rationale": portfolio.get("concentration_rationale", ""),
                },
                "3_position_detail": {
                    "four_box_outputs": pipeline_output.get("sector_outputs", []),
                    "valuations": pipeline_output.get("valuations", []),
                    "red_team_assessments": pipeline_output.get("red_team", []),
                },
                "4_risk": {
                    "var_95": risk.get("var_95", {}),
                    "var_99": risk.get("var_99", {}),
                    "factor_exposures": risk.get("factor_exposures", {}),
                    "scenario_stresses": risk.get("scenario_stresses", []),
                    "max_drawdown_estimate": risk.get("max_drawdown_estimate"),
                },
                "5_compliance": {
                    "mandate_compliant": mandate.get("is_compliant", False),
                    "mandate_violations": mandate.get("violations", []),
                    "esg_exclusions_triggered": pipeline_output.get("esg_exclusions", []),
                    "position_limits_respected": mandate.get("position_limits_ok", True),
                },
                "6_ic_record": {
                    "vote_breakdown": ic_outcome.get("vote_breakdown", {}),
                    "conditions": ic_outcome.get("conditions", []),
                    "dissents": ic_outcome.get("dissents", []),
                    "approved_at": ic_outcome.get("approved_at", ""),
                },
            },
        }

        return json.dumps(doc, indent=2, default=str)


class ExecutiveSummaryFormat:
    """1-page condensed text report for senior readers / CIO distribution."""

    def render(self, run_id: str, pipeline_output: dict[str, Any]) -> str:
        final_report = pipeline_output.get("final_report", {})
        portfolio = pipeline_output.get("portfolio", {})
        risk = pipeline_output.get("risk_package", {})
        ic_outcome = pipeline_output.get("ic_outcome", {})

        positions = portfolio.get("positions", [])
        top_positions = sorted(positions, key=lambda p: p.get("weight", 0), reverse=True)[:5]

        lines = [
            "=" * 72,
            f"  AI INFRASTRUCTURE RESEARCH PORTFOLIO — EXECUTIVE SUMMARY",
            f"  Run: {run_id}   |   Date: {date.today().isoformat()}",
            "=" * 72,
            "",
            "PORTFOLIO THESIS",
            "-" * 40,
            final_report.get("portfolio_summary", "No summary available."),
            "",
            "IC DECISION",
            "-" * 40,
            f"Decision : {ic_outcome.get('decision', 'PENDING')}",
            f"Rationale: {ic_outcome.get('rationale', '')}",
            "",
            "TOP 5 POSITIONS",
            "-" * 40,
        ]

        for pos in top_positions:
            ticker = pos.get("ticker", "")
            weight = pos.get("weight", 0) * 100
            target = pos.get("price_target", "N/A")
            thesis = pos.get("thesis_sentence", "")
            lines.append(f"  {ticker:<6}  {weight:5.1f}%  PT:{target:>8}  {thesis[:50]}")

        lines += [
            "",
            "KEY RISKS",
            "-" * 40,
        ]
        for risk_item in final_report.get("key_risks", [])[:5]:
            lines.append(f"  • {risk_item}")

        var_95 = risk.get("var_95", {})
        lines += [
            "",
            "RISK METRICS",
            "-" * 40,
            f"  VaR 95% (1-day) : {var_95.get('portfolio', 'N/A')}",
            f"  Max drawdown est: {risk.get('max_drawdown_estimate', 'N/A')}",
            "",
            "=" * 72,
            "  CONFIDENTIAL — FOR INSTITUTIONAL CLIENTS ONLY",
            "=" * 72,
        ]

        return "\n".join(lines)


class FactsheetFormat:
    """Compact KPI factsheet — NAV, weights, exposure summary, VaR."""

    def render(self, run_id: str, pipeline_output: dict[str, Any]) -> str:
        portfolio = pipeline_output.get("portfolio", {})
        risk = pipeline_output.get("risk_package", {})
        factor_exp = risk.get("factor_exposures", {})

        positions = portfolio.get("positions", [])
        positions_sorted = sorted(positions, key=lambda p: p.get("weight", 0), reverse=True)

        lines = [
            "── FACTSHEET ──────────────────────────────────────────────────",
            f"Run ID   : {run_id}",
            f"Date     : {date.today().isoformat()}",
            f"Positions: {len(positions)}",
            f"Status   : {portfolio.get('variant', 'N/A')}",
            "",
            "── WEIGHTS ────────────────────────────────────────────────────",
            f"{'TICKER':<8}{'WEIGHT':>8}{'SECTOR':>20}",
            "─" * 38,
        ]

        for pos in positions_sorted:
            ticker = pos.get("ticker", "")
            weight = pos.get("weight", 0) * 100
            sector = pos.get("sector", "")[:18]
            lines.append(f"{ticker:<8}{weight:7.1f}%{sector:>20}")

        cash = portfolio.get("cash_weight", 0) * 100
        lines.append(f"{'CASH':<8}{cash:7.1f}%")

        lines += [
            "",
            "── FACTOR EXPOSURE ────────────────────────────────────────────",
        ]
        for factor_name, exp in factor_exp.items():
            if isinstance(exp, dict):
                p_beta = exp.get("portfolio", "N/A")
                lines.append(f"  {factor_name:<20}: {p_beta}")
            elif exp is not None:
                lines.append(f"  {factor_name:<20}: {exp}")

        var_95 = risk.get("var_95", {})
        var_99 = risk.get("var_99", {})
        lines += [
            "",
            "── RISK ───────────────────────────────────────────────────────",
            f"  VaR 95% (1-day) : {var_95.get('portfolio', 'N/A')}",
            f"  VaR 99% (1-day) : {var_99.get('portfolio', 'N/A')}",
            f"  Max DD estimate : {risk.get('max_drawdown_estimate', 'N/A')}",
            "─" * 64,
        ]

        return "\n".join(lines)


class ReportFormatService:
    """Entry point for generating any report format from pipeline output.

    Usage::

        service = ReportFormatService()
        rendered = service.render(
            run_id="RUN-20250101-1200",
            pipeline_output=stage15_result,
            format_type=ReportFormat.EXECUTIVE_SUMMARY,
        )
        rendered.save(Path("output/reports"))
    """

    def __init__(self, output_dir: Path | None = None):
        self._output_dir = output_dir or Path("output/reports")
        self._formats = {
            ReportFormat.INSTITUTIONAL_PDF: InstitutionalPDFFormat(),
            ReportFormat.EXECUTIVE_SUMMARY: ExecutiveSummaryFormat(),
            ReportFormat.FACTSHEET: FactsheetFormat(),
        }

    def render(
        self,
        run_id: str,
        pipeline_output: dict[str, Any],
        format_type: ReportFormat | str = ReportFormat.EXECUTIVE_SUMMARY,
    ) -> RenderedReport:
        """Render pipeline output into a formatted report."""
        if isinstance(format_type, str):
            format_type = ReportFormat(format_type)

        renderer = self._formats[format_type]
        content = renderer.render(run_id, pipeline_output)
        content_type = "application/json" if format_type == ReportFormat.INSTITUTIONAL_PDF else "text/plain"

        return RenderedReport(
            run_id=run_id,
            format_type=format_type,
            content=content,
            content_type=content_type,
        )

    def render_all(
        self, run_id: str, pipeline_output: dict[str, Any]
    ) -> list[RenderedReport]:
        """Render all three formats and return them."""
        return [
            self.render(run_id, pipeline_output, fmt)
            for fmt in ReportFormat
        ]

    def save_all(
        self, run_id: str, pipeline_output: dict[str, Any]
    ) -> list[Path]:
        """Render all formats and save to output_dir."""
        reports = self.render_all(run_id, pipeline_output)
        return [r.save(self._output_dir) for r in reports]
