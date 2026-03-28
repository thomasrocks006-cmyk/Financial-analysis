"""A8 — Report Assembly Service: compile final report from approved sections only."""

from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, BaseLoader

from research_pipeline.schemas.portfolio import AssociateReviewResult, PublicationStatus
from research_pipeline.schemas.reports import FinalReport, ReportSection, StockCard

logger = logging.getLogger(__name__)

# ── Default Markdown report template ───────────────────────────────────
DEFAULT_TEMPLATE = """# {{ title }}
**Date:** {{ date }}
**Run ID:** {{ run_id }}
**Publication Status:** {{ publication_status }}

---

## Executive Summary
{{ executive_summary }}

---

## Methodology
{{ methodology }}

---

## Stock Cards

{% for card in stock_cards %}
### {{ card.ticker }} — {{ card.company_name }}
**Subtheme:** {{ card.subtheme }}
**Entry Quality:** {{ card.entry_quality }}
**Thesis Integrity:** {{ card.thesis_integrity }}

{{ card.four_box_summary }}

**Valuation Summary:**
{{ card.valuation_summary }}

**Key Risks:**
{% for risk in card.key_risks %}- {{ risk }}
{% endfor %}

**Red Team Summary:**
{{ card.red_team_summary }}

{% if card.weight_in_balanced %}**Portfolio Weight (Balanced):** {{ card.weight_in_balanced }}%{% endif %}

---
{% endfor %}

## Valuation Appendix
{{ valuation_appendix }}

---

## Risk Appendix
{{ risk_appendix }}

---

## Self-Audit Appendix
{{ self_audit_appendix }}

---

## Claim Register Appendix
{{ claim_register_appendix }}

---

*This report uses public-source data only. Broker consensus history, revision depth,
and premium comp data remain structurally unavailable without licensed terminal data
(Bloomberg / FactSet / LSEG).*
"""


class ReportAssemblyService:
    """Compile the final report from approved sections only — no LLM.

    Rules:
    - No unpublished content from failed stages
    - Auto-append self-audit
    - Auto-append claim register
    """

    def __init__(self, templates_dir: Path | None = None):
        if templates_dir and templates_dir.exists():
            self.env = Environment(loader=FileSystemLoader(str(templates_dir)))
        else:
            self.env = Environment(loader=BaseLoader())

    def assemble_report(
        self,
        run_id: str,
        review_result: AssociateReviewResult,
        sections: dict[str, str],
        stock_cards: list[StockCard],
        self_audit_text: str = "",
        claim_register_text: str = "",
    ) -> FinalReport:
        """Assemble the final report. Only runs if review passed."""
        if not review_result.is_publishable:
            logger.error("Cannot assemble report: review status is %s", review_result.status)
            return FinalReport(
                run_id=run_id,
                publication_status="blocked",
                sections=[
                    ReportSection(
                        section_name="error",
                        content=f"Report blocked: review status {review_result.status.value}",
                        approved=False,
                    )
                ],
            )

        report_sections = []
        for name in [
            "executive_summary",
            "methodology",
            "valuation_appendix",
            "risk_appendix",
            "self_audit_appendix",
            "claim_register_appendix",
        ]:
            content = sections.get(name, "")
            if name == "self_audit_appendix" and not content:
                content = self_audit_text
            if name == "claim_register_appendix" and not content:
                content = claim_register_text
            report_sections.append(
                ReportSection(
                    section_name=name,
                    content=content,
                    approved=True,
                )
            )

        status = (
            "published"
            if review_result.status == PublicationStatus.PASS
            else "published_with_disclosure"
        )

        return FinalReport(
            run_id=run_id,
            sections=report_sections,
            stock_cards=stock_cards,
            publication_status=status,
        )

    def render_markdown(self, report: FinalReport) -> str:
        """Render the report as Markdown using the template."""
        template = self.env.from_string(DEFAULT_TEMPLATE)

        section_map = {s.section_name: s.content for s in report.sections}

        return template.render(
            title=report.title,
            date=report.date.strftime("%Y-%m-%d"),
            run_id=report.run_id,
            publication_status=report.publication_status,
            executive_summary=section_map.get("executive_summary", ""),
            methodology=section_map.get("methodology", ""),
            stock_cards=[c.model_dump() for c in report.stock_cards],
            valuation_appendix=section_map.get("valuation_appendix", ""),
            risk_appendix=section_map.get("risk_appendix", ""),
            self_audit_appendix=section_map.get("self_audit_appendix", ""),
            claim_register_appendix=section_map.get("claim_register_appendix", ""),
        )

    def save_report(self, report: FinalReport, output_dir: Path) -> Path:
        """Save rendered report to disk."""
        output_dir.mkdir(parents=True, exist_ok=True)
        md_content = self.render_markdown(report)
        filename = f"report_{report.run_id}_{report.date.strftime('%Y%m%d')}.md"
        path = output_dir / filename
        path.write_text(md_content)
        logger.info("Report saved: %s", path)
        return path
