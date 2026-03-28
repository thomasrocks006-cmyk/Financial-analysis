"""Interactive HTML research report rendering."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import BaseLoader, Environment


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{{ title }}</title>
  <style>
    body { font-family: Arial, sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 24px; }
    h1, h2, h3 { color: #f8fafc; }
    .card { background: #111827; border: 1px solid #334155; border-radius: 12px; padding: 16px; margin: 16px 0; }
    .metric-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
    .metric { background: #1e293b; border-radius: 8px; padding: 12px; }
    .muted { color: #94a3b8; }
    ul { padding-left: 20px; }
    pre { white-space: pre-wrap; background: #020617; padding: 12px; border-radius: 8px; }
  </style>
</head>
<body>
  <h1>{{ title }}</h1>
  <p class="muted">Run ID: {{ run_id }} · Generated: {{ generated_at }}</p>

  <div class="card">
    <h2>Executive Summary</h2>
    <p>{{ executive_summary }}</p>
  </div>

  <div class="metric-grid">
    <div class="metric"><strong>Publication Status</strong><br />{{ publication_status }}</div>
    <div class="metric"><strong>Stock Cards</strong><br />{{ stock_card_count }}</div>
    <div class="metric"><strong>Sections</strong><br />{{ section_count }}</div>
  </div>

  {% for section in sections %}
  <div class="card">
    <h2>{{ section.section_name.replace("_", " ").title() }}</h2>
    <pre>{{ section.content }}</pre>
  </div>
  {% endfor %}

  <div class="card">
    <h2>Stock Cards</h2>
    {% for card in stock_cards %}
    <div class="card">
      <h3>{{ card.ticker }} — {{ card.company_name }}</h3>
      <p><strong>Subtheme:</strong> {{ card.subtheme }}</p>
      <p><strong>Entry Quality:</strong> {{ card.entry_quality }} · <strong>Thesis Integrity:</strong> {{ card.thesis_integrity }}</p>
      <p>{{ card.four_box_summary }}</p>
      <p><strong>Valuation:</strong> {{ card.valuation_summary }}</p>
      <p><strong>Red Team:</strong> {{ card.red_team_summary }}</p>
      {% if card.key_risks %}
      <ul>
      {% for risk in card.key_risks %}
        <li>{{ risk }}</li>
      {% endfor %}
      </ul>
      {% endif %}
    </div>
    {% endfor %}
  </div>
</body>
</html>
"""


class ReportHtmlService:
    """Render a self-contained HTML report from final report data."""

    def __init__(self) -> None:
        self._env = Environment(loader=BaseLoader())

    def render(self, report: dict[str, Any]) -> str:
        """Render report dict into HTML."""
        template = self._env.from_string(HTML_TEMPLATE)
        sections = report.get("sections", [])
        stock_cards = report.get("stock_cards", [])
        executive_summary = ""
        for section in sections:
            if section.get("section_name") == "executive_summary":
                executive_summary = section.get("content", "")
                break
        return template.render(
            title=report.get("title", "AI Infrastructure Investment Research"),
            run_id=report.get("run_id", ""),
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            publication_status=report.get("publication_status", "draft"),
            section_count=len(sections),
            stock_card_count=len(stock_cards),
            executive_summary=executive_summary,
            sections=sections,
            stock_cards=stock_cards,
        )

    def save(self, report: dict[str, Any], output_dir: Path) -> Path:
        """Write rendered HTML report to disk."""
        output_dir.mkdir(parents=True, exist_ok=True)
        run_id = report.get("run_id", "unknown")
        path = output_dir / f"{run_id}_interactive_report.html"
        path.write_text(self.render(report), encoding="utf-8")
        return path
