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

{% if au_disclosures %}
---

## Australian Regulatory Disclosures
{{ au_disclosures }}
{% endif %}
"""

# ── AU regulatory disclosure text ──────────────────────────────────────────
AU_DISCLOSURES_TEMPLATE = """
**Financial Services Guide (FSG) Notice**
This document is provided for informational purposes only and does not constitute
financial product advice. Any general advice contained herein has been prepared
without taking into account your objectives, financial situation or needs. Before
acting on any information, consider whether it is appropriate for you.

**ASIC § 1013D Product Disclosure Statement Notice**
Past performance is not an indicator of future performance. The value of
investments and the income from them can fall as well as rise. You may get back
less than you originally invested.

**APRA Regulated Entity Disclosure**
This research has been prepared for use by Australian Prudential
Regulation Authority (APRA) regulated entities and takes into account APRA
SPS 530 Investment Governance requirements, including the diversification
benchmarks under § 60 of that Standard.

**AFSL Disclaimer**
This report is issued pursuant to the requirements of an Australian Financial
Services Licence (AFSL). JP Morgan Asset Management Australia Limited is
licensed under an AFSL to provide general financial product advice.

**Tax Considerations**
Tax treatment depends on the individual circumstances of each investor. The
tax information provided is of a general nature and does not constitute tax
advice. Investors should seek independent tax advice before making investment
decisions. Different tax treatments apply to superannuation funds (15%
accumulation rate, 1/3 CGT discount), SMSFs, high-net-worth individuals
(50% CGT discount) and other entities under Australian taxation law.
"""


def build_au_disclosures(
    client_profile: object | None = None,
    tax_summary: dict | None = None,
    afsl_number: str = "",
) -> str:
    """Build AU regulatory disclosure text for the report.

    Args:
        client_profile: Optional ClientProfile — used to add SMSF / super context.
        tax_summary: Optional output of AustralianTaxService.portfolio_tax_summary().
        afsl_number: Optional AFSL number to include in the AFSL disclaimer.

    Returns:
        Formatted Markdown string suitable for injection into the report.
    """
    lines = [AU_DISCLOSURES_TEMPLATE.strip()]

    # Superannuation-specific addendum
    client_type = getattr(client_profile, "client_type", None)
    if client_type in ("super_fund", "smsf"):
        is_smsf = getattr(client_profile, "is_smsf", client_type == "smsf")
        fund_type = getattr(client_profile, "super_fund_type", None) or "N/A"
        pension = getattr(client_profile, "smsf_pension_phase", False)
        lines.append(
            f"\n**Superannuation Fund Disclosure**\n"
            f"This report has been prepared for a "
            f"{'Self-Managed Superannuation Fund (SMSF)' if is_smsf else 'APRA-regulated superannuation fund'}\n"
            f"operating a {'pension-phase' if pension else 'accumulation-phase'} "
            f"account under the Superannuation Industry (Supervision) Act 1993 (SIS Act).\n"
            f"Option type: **{fund_type.title()}**.\n"
            f"Compliance with APRA Superannuation Prudential Standard SPS 530 "
            f"(Investment Governance) has been applied throughout this analysis."
        )

    # Tax summary addendum
    if tax_summary:
        drag = tax_summary.get("estimated_tax_drag_bps", 0)
        aft = tax_summary.get("after_tax_yield_pct", 0)
        rate = tax_summary.get("income_tax_rate_pct", 0)
        lines.append(
            f"\n**Estimated Tax Impact**\n"
            f"Indicative income tax rate: {rate:.1f}%. "
            f"Estimated annual tax drag on portfolio yield: **{drag:.0f} bps**. "
            f"After-tax yield estimate: **{aft:.2f}%**. "
            f"These are estimates only and do not constitute tax advice."
        )

    if afsl_number:
        lines.append(f"\nAFSL Number: **{afsl_number}**")

    return "\n".join(lines)


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
        narrative_sections: dict[str, str] | None = None,  # Session 13: LLM-generated prose
        au_disclosures: str | None = None,  # Session 14: AU regulatory text
    ) -> FinalReport:
        """Assemble the final report. Only runs if review passed.

        Session 13: When ``narrative_sections`` is provided (from
        ReportNarrativeAgent), its values override the static ``sections``
        entries, producing institutionally-worded prose rather than
        hardcoded template strings.
        """
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

        # Merge: start with static sections, overlay LLM narrative where available
        merged_sections = dict(sections)
        if narrative_sections:
            for key, text in narrative_sections.items():
                if text and not text.startswith("["):  # skip placeholder strings
                    merged_sections[key] = text

        # Merge AU disclosures into sections map
        if au_disclosures:
            merged_sections["au_disclosures"] = au_disclosures

        report_sections = []
        for name in [
            "executive_summary",
            "methodology",
            "valuation_appendix",
            "risk_appendix",
            "self_audit_appendix",
            "claim_register_appendix",
            "au_disclosures",
        ]:
            content = merged_sections.get(name, "")
            if name == "self_audit_appendix" and not content:
                content = self_audit_text
            if name == "claim_register_appendix" and not content:
                content = claim_register_text
            # Only include au_disclosures section when content is present
            if name == "au_disclosures" and not content:
                continue
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
            au_disclosures=section_map.get("au_disclosures", ""),
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
