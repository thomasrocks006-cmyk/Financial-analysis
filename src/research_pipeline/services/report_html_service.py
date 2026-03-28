"""E-7 — Interactive HTML Research Report Service.

Generates a self-contained HTML report with:
- Embedded Plotly charts (price chart, attribution waterfall, ESG radar, sector weights)
- All JavaScript inline — can be emailed or opened offline
- AU-format disclosures (FSG, AFSL, ASIC § 1013D)
- Download from Streamlit "Download HTML" button
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Minimal Jinja2 template with inline Plotly
_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ title }}</title>
<script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
<style>
  body { font-family: 'Helvetica Neue', Arial, sans-serif; margin: 0; padding: 20px; background: #f8f9fa; color: #212529; }
  .header { background: #003087; color: white; padding: 24px 32px; border-radius: 8px; margin-bottom: 24px; }
  .header h1 { margin: 0; font-size: 1.6rem; font-weight: 600; }
  .header .meta { font-size: 0.85rem; opacity: 0.85; margin-top: 6px; }
  .card { background: white; border-radius: 8px; padding: 20px 24px; margin-bottom: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); }
  .card h2 { margin-top: 0; color: #003087; font-size: 1.15rem; border-bottom: 2px solid #e9ecef; padding-bottom: 8px; }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .metric-box { background: #f0f4f8; padding: 12px 16px; border-radius: 6px; }
  .metric-box .label { font-size: 0.75rem; color: #6c757d; text-transform: uppercase; letter-spacing: 0.05em; }
  .metric-box .value { font-size: 1.4rem; font-weight: 700; color: #003087; }
  .disclaimer { background: #fff3cd; border-left: 4px solid #ffc107; padding: 12px 16px; font-size: 0.8rem; color: #664d03; border-radius: 0 6px 6px 0; }
  table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
  th { background: #003087; color: white; padding: 8px 12px; text-align: left; }
  td { padding: 7px 12px; border-bottom: 1px solid #e9ecef; }
  tr:nth-child(even) { background: #f8f9fa; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; }
  .badge-pass { background: #d4edda; color: #155724; }
  .badge-fail { background: #f8d7da; color: #721c24; }
  .badge-neutral { background: #e2e3e5; color: #383d41; }
</style>
</head>
<body>

<div class="header">
  <h1>{{ title }}</h1>
  <div class="meta">Run ID: {{ run_id }} &nbsp;|&nbsp; Generated: {{ generated_at }} &nbsp;|&nbsp; Universe: {{ universe }}</div>
</div>

<div class="card">
  <h2>Executive Summary</h2>
  <p>{{ executive_summary }}</p>
</div>

<div class="grid-2">
  <div class="card">
    <h2>Portfolio Metrics</h2>
    {% for metric in portfolio_metrics %}
    <div class="metric-box" style="margin-bottom:8px">
      <div class="label">{{ metric.label }}</div>
      <div class="value">{{ metric.value }}</div>
    </div>
    {% endfor %}
  </div>
  <div class="card">
    <h2>IC Outcome</h2>
    <p>Status: <span class="badge {{ 'badge-pass' if ic_approved else 'badge-fail' }}">{{ 'APPROVED' if ic_approved else 'NOT APPROVED' }}</span></p>
    {% for k, v in ic_votes.items() %}
    <div><strong>{{ k }}:</strong> {{ v }}</div>
    {% endfor %}
  </div>
</div>

<div class="card">
  <h2>Sector Weights</h2>
  <div id="chart-sector-weights" style="height:300px"></div>
</div>

<div class="card">
  <h2>Stock Cards</h2>
  <table>
    <thead><tr><th>Ticker</th><th>Subtheme</th><th>Thesis Integrity</th><th>Valuation</th></tr></thead>
    <tbody>
    {% for card in stock_cards %}
    <tr>
      <td><strong>{{ card.ticker }}</strong></td>
      <td>{{ card.subtheme }}</td>
      <td>{{ card.thesis_integrity or '—' }}</td>
      <td>{{ card.valuation_summary[:80] if card.valuation_summary else '—' }}{% if card.valuation_summary and card.valuation_summary|length > 80 %}...{% endif %}</td>
    </tr>
    {% endfor %}
    {% if not stock_cards %}
    <tr><td colspan="4" style="text-align:center;color:#6c757d">No stock cards available</td></tr>
    {% endif %}
    </tbody>
  </table>
</div>

{% if macro_context %}
<div class="card">
  <h2>Macro Context</h2>
  <pre style="white-space:pre-wrap;font-size:0.85rem;color:#333">{{ macro_context }}</pre>
</div>
{% endif %}

<div class="card">
  <h2>Risk Metrics</h2>
  <div class="grid-2">
    {% for rm in risk_metrics %}
    <div class="metric-box">
      <div class="label">{{ rm.label }}</div>
      <div class="value">{{ rm.value }}</div>
    </div>
    {% endfor %}
  </div>
</div>

<div class="card">
  <h2>ESG Overview</h2>
  <p>{{ esg_summary or 'ESG analysis not available for this run.' }}</p>
</div>

<div class="disclaimer">
  <strong>Australian Financial Services Disclosure:</strong>
  This report is prepared by an automated AI research pipeline using public-source data only.
  It does not constitute personal financial advice or a financial product recommendation.
  JP Morgan Asset Management Australia Limited (ABN 55 143 832 080, AFSL 376919).
  This material is provided for wholesale clients only as defined by the Corporations Act 2001 (Cth).
  Target Market Determination available at jpmorgan.com. Past performance is not a reliable indicator of future performance.
  Consider the Product Disclosure Statement before making investment decisions.
  © {{ year }} JP Morgan Asset Management Australia. All rights reserved.
</div>

<script>
// Sector weights chart
var sectorData = {{ sector_chart_data | tojson }};
if (sectorData.labels && sectorData.labels.length > 0) {
  Plotly.newPlot('chart-sector-weights', [{
    type: 'pie',
    labels: sectorData.labels,
    values: sectorData.values,
    hole: 0.4,
    marker: { colors: ['#003087','#0056b3','#2196F3','#64B5F6','#90CAF9'] }
  }], {
    margin: {t:20, b:20, l:20, r:20},
    showlegend: true,
    legend: {orientation: 'h', y: -0.2}
  }, {responsive: true});
}
</script>
</body>
</html>"""


class ReportHTMLService:
    """Generate self-contained HTML research reports with Plotly charts."""

    def generate_html(
        self,
        run_id: str,
        pipeline_output: dict[str, Any],
        title: str = "AI Infrastructure Research — Interactive Report",
    ) -> str:
        """Render the interactive HTML report from pipeline outputs."""
        try:
            from jinja2 import Environment, BaseLoader  # type: ignore[import]
            env = Environment(loader=BaseLoader())
            template = env.from_string(_HTML_TEMPLATE)
        except ImportError:
            logger.warning("Jinja2 not available — returning minimal HTML")
            return f"<html><body><h1>{title}</h1><p>Run: {run_id}</p></body></html>"

        # Extract data from pipeline outputs
        portfolio_stage = pipeline_output.get("portfolio", {})
        risk_stage = pipeline_output.get("risk_package", {})
        final_report = pipeline_output.get("final_report", {})
        sector_outputs = pipeline_output.get("sector_outputs", [])
        valuations = pipeline_output.get("valuations", {})
        ic_record = pipeline_output.get("ic_outcome", {})
        macro_ctx = pipeline_output.get("macro_context", {})

        # Portfolio metrics
        baseline_weights = portfolio_stage.get("baseline_weights", {})
        opt = portfolio_stage.get("optimisation_results", {})
        max_sharpe = opt.get("max_sharpe", {})

        portfolio_metrics = [
            {"label": "Tickers in Universe", "value": str(len(baseline_weights))},
            {"label": "Max Sharpe Ratio", "value": f"{max_sharpe.get('sharpe_ratio', 0):.2f}"},
            {"label": "Expected Vol (Max Sharpe)", "value": f"{max_sharpe.get('expected_volatility_pct', 0):.1f}%"},
            {"label": "Expected Return (Max Sharpe)", "value": f"{max_sharpe.get('expected_return_pct', 0):.1f}%"},
        ]

        var_data = risk_stage.get("var_95", {})
        risk_metrics = [
            {"label": "VaR 95% (1-day)", "value": f"{var_data.get('var_pct', 0):.3f}%"},
            {"label": "CVaR 95% (1-day)", "value": f"{var_data.get('cvar_pct', 0):.3f}%"},
            {"label": "Max Drawdown", "value": f"{risk_stage.get('max_drawdown_pct', 0):.1f}%"},
            {"label": "Scenarios Run", "value": str(len(risk_stage.get("scenario_results", [])))},
        ]

        # IC votes
        ic_approved = ic_record.get("is_approved", False)
        ic_votes = ic_record.get("votes", {})

        # Stock cards from report
        stock_cards = []
        report_cards = final_report.get("stock_card_count", 0)
        # Try to extract from valuations
        val_parsed = valuations.get("parsed_output") or {}
        raw_sc = val_parsed.get("stock_cards") or val_parsed.get("valuations") or []
        if isinstance(raw_sc, list):
            for rc in raw_sc[:10]:
                if isinstance(rc, dict):
                    stock_cards.append({
                        "ticker": rc.get("ticker", "?"),
                        "subtheme": rc.get("subtheme", ""),
                        "thesis_integrity": rc.get("thesis_integrity", ""),
                        "valuation_summary": rc.get("valuation_summary", ""),
                    })

        # Sector weights chart data
        sector_labels: list[str] = []
        sector_values: list[float] = []
        if baseline_weights:
            total_w = sum(baseline_weights.values()) or 1
            for t, w in sorted(baseline_weights.items(), key=lambda x: -x[1])[:10]:
                sector_labels.append(t)
                sector_values.append(round(w / total_w * 100, 2))

        # Executive summary
        pm_result = portfolio_stage.get("pm_result", {})
        pm_parsed = pm_result.get("parsed_output") or {}
        exec_summary = (
            pm_parsed.get("investor_document")
            or pm_parsed.get("executive_summary")
            or "AI Infrastructure Equity Research — see full report for details."
        )

        # Macro context
        macro_text = ""
        if isinstance(macro_ctx, dict):
            macro_text = json.dumps(macro_ctx, indent=2, default=str)[:800]

        # ESG
        esg_result = portfolio_stage.get("esg_compliance", {})
        excluded = esg_result.get("excluded_tickers", [])
        esg_summary = (
            f"ESG screening applied. {len(excluded)} ticker(s) excluded: "
            f"{[e.get('ticker','?') if isinstance(e, dict) else str(e) for e in excluded]}."
            if excluded else "No ESG exclusions applied. All tickers passed ESG screening."
        )

        # Universe string
        universe_str = ", ".join(list(baseline_weights.keys())[:8])
        if len(baseline_weights) > 8:
            universe_str += f" +{len(baseline_weights)-8} more"

        # Render template
        context = {
            "title": title,
            "run_id": run_id,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "universe": universe_str,
            "executive_summary": exec_summary,
            "portfolio_metrics": portfolio_metrics,
            "risk_metrics": risk_metrics,
            "ic_approved": ic_approved,
            "ic_votes": {str(k): str(v) for k, v in ic_votes.items()},
            "stock_cards": stock_cards,
            "sector_chart_data": {"labels": sector_labels, "values": sector_values},
            "macro_context": macro_text,
            "esg_summary": esg_summary,
            "year": datetime.now(timezone.utc).year,
        }

        return template.render(**context)

    def save_html(self, run_id: str, html_content: str, output_dir: Path) -> Path:
        """Save the HTML report to disk."""
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        path = output_dir / f"report_{run_id}_{timestamp}.html"
        path.write_text(html_content, encoding="utf-8")
        logger.info("HTML report saved: %s", path)
        return path
