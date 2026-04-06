"""
src/api/services/pdf_service.py
---------------------------------
PDF report generation using fpdf2.

Ported from src/frontend/app.py _generate_report_pdf (ACT-S6-3).
Returns raw PDF bytes; gracefully returns empty bytes if fpdf2 not installed.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

A4_W = 210
MARGIN = 20
CONTENT_W = A4_W - 2 * MARGIN


def generate_report_pdf(
    run_id: str,
    tickers: list[str],
    report_md: str,
    run_label: str = "",
) -> bytes:
    """Render a PDF from a markdown report using fpdf2.

    Includes a cover page with run metadata and a paginated body section.
    Returns raw PDF bytes, or an empty bytes object if fpdf2 is not installed.
    """
    try:
        from fpdf import FPDF  # type: ignore[import]
    except ImportError:
        logger.debug("fpdf2 not installed — PDF generation skipped")
        return b""

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.compress = False
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(MARGIN, MARGIN, MARGIN)

    # ── Cover page ──────────────────────────────────────────────────────
    pdf.add_page()
    pdf.set_xy(MARGIN, 60)
    pdf.set_font("Helvetica", "B", 22)
    pdf.multi_cell(CONTENT_W, 10, "AI Infrastructure Research", align="C")
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 13)
    pdf.multi_cell(CONTENT_W, 8, "Institutional-Style Equity Research Report", align="C")
    pdf.ln(12)
    pdf.set_font("Courier", "", 9)
    pdf.multi_cell(CONTENT_W, 6, f"Run ID: {run_id}", align="C")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(CONTENT_W, 6, f"Universe: {', '.join(tickers)}", align="C")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(CONTENT_W, 6, f"Generated: {now}", align="C")
    if run_label:
        pdf.ln(2)
        pdf.multi_cell(CONTENT_W, 6, run_label, align="C")
    pdf.ln(16)
    pdf.set_font("Helvetica", "I", 8)
    disclaimer = (
        "FOR INFORMATIONAL PURPOSES ONLY - NOT INVESTMENT ADVICE. "
        "AI-generated content may contain errors. "
        "Past performance is no guarantee of future results."
    )
    pdf.multi_cell(CONTENT_W, 5, disclaimer, align="C")

    # ── Report body page ─────────────────────────────────────────────────
    pdf.add_page()
    pdf.set_font("Helvetica", "", 10)

    # Normalize to latin-1 safe characters so fpdf2 doesn't crash on Unicode
    _UNICODE_MAP = str.maketrans(
        {
            "\u2014": "--",  # em dash
            "\u2013": "-",  # en dash
            "\u2026": "...",  # ellipsis
            "\u2018": "'",  # left single quote
            "\u2019": "'",  # right single quote
            "\u201c": '"',  # left double quote
            "\u201d": '"',  # right double quote
            "\u2022": "*",  # bullet
            "\u00b7": "*",  # middle dot
            "\u2212": "-",  # minus sign
            "\u00a0": " ",  # non-breaking space
        }
    )

    def _safe(text: str) -> str:
        text = text.translate(_UNICODE_MAP)
        # Drop any remaining non-latin-1 characters
        return text.encode("latin-1", errors="replace").decode("latin-1")

    def _strip_md(line: str) -> str:
        """Strip common markdown formatting for plain-text PDF rendering."""
        return (
            line.replace("**", "")
            .replace("*", "")
            .replace("`", "")
            .replace("# ", "")
            .replace("## ", "")
            .replace("### ", "")
        )

    for raw_line in report_md.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            pdf.ln(2)
        elif stripped.startswith("### "):
            text = _safe(stripped[4:].strip())
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 10)
            pdf.multi_cell(CONTENT_W, 6, text)
            pdf.ln(1)
        elif stripped.startswith("## "):
            text = _safe(stripped[3:].strip())
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 12)
            pdf.multi_cell(CONTENT_W, 7, text)
            pdf.ln(1)
        elif stripped.startswith("# "):
            text = _safe(stripped[2:].strip())
            pdf.ln(2)
            pdf.set_draw_color(200, 200, 200)
            y = pdf.get_y()
            pdf.line(MARGIN, y, A4_W - MARGIN, y)
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 14)
            pdf.multi_cell(CONTENT_W, 8, text)
            pdf.ln(1)
        elif stripped.startswith("---"):
            pdf.ln(2)
            pdf.set_draw_color(200, 200, 200)
            y = pdf.get_y()
            pdf.line(MARGIN, y, A4_W - MARGIN, y)
            pdf.ln(2)
        elif stripped.startswith("- ") or stripped.startswith("* "):
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(CONTENT_W, 5, f"  * {_safe(_strip_md(stripped[2:]))}")
        else:
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(CONTENT_W, 5, _safe(_strip_md(stripped)))
            pdf.ln(1)

    try:
        return bytes(pdf.output())
    except Exception as exc:
        logger.warning("PDF output() failed: %s", exc)
        return b""
