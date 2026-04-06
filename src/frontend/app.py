"""AI Infrastructure Research Pipeline — Streamlit Frontend v8.

Run with:
    cd /workspaces/Financial-analysis
    .venv/bin/streamlit run src/frontend/app.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

logger = logging.getLogger(__name__)

# ── Path setup ────────────────────────────────────────────────────────────
ROOT = Path(__file__).parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from frontend.client_profile import ClientProfile, INVESTMENT_THEMES, RISK_PROFILES
from frontend.pipeline_adapter import (
    STAGES,
    PipelineRunner,
    RunResult,
)  # ACT-S6-4: use adapter (pipeline_runner deprecated)
from frontend.cost_estimator import estimate_run_cost, calculate_actual_cost, format_cost
from frontend.storage import save_run, list_saved_runs, load_run, delete_run, REPORTS_DIR


# ── PDF export helper (ACT-S6-3) ──────────────────────────────────────────
def _generate_report_pdf(run_id: str, tickers: list[str], report_md: str) -> bytes:
    """Render a simple PDF from the markdown report using fpdf2.

    Strips markdown formatting to plain text, emits sections with bold headings,
    and includes a cover page. Returns raw PDF bytes suitable for st.download_button.
    """
    try:
        from fpdf import FPDF
    except ImportError:
        return b""  # fpdf2 not installed — graceful degradation

    A4_W, A4_H = 210, 297
    MARGIN = 18
    CONTENT_W = A4_W - 2 * MARGIN

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.compress = False  # disable per-stream compression so content is scannable
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(MARGIN, MARGIN, MARGIN)

    # ── Cover page ────────────────────────────────────────────────────────
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
    pdf.multi_cell(
        CONTENT_W,
        6,
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        align="C",
    )
    pdf.ln(16)
    pdf.set_font("Helvetica", "I", 8)
    disclaimer = (
        "This report is produced by an automated AI research pipeline using public-source data only. "
        "It does not constitute investment advice. Past performance is not indicative of future results."
    )
    pdf.multi_cell(CONTENT_W, 5, disclaimer, align="C")

    # ── Report body ───────────────────────────────────────────────────────
    pdf.add_page()

    _RE_HEADING1 = re.compile(r"^#\s+(.+)$")
    _RE_HEADING2 = re.compile(r"^##\s+(.+)$")
    _RE_HEADING3 = re.compile(r"^###\s+(.+)$")
    _RE_BOLD = re.compile(r"\*\*(.+?)\*\*")
    _RE_ITALIC = re.compile(r"\*(.+?)\*")
    _RE_CODE = re.compile(r"`(.+?)`")
    _RE_HR = re.compile(r"^---+$")

    def _strip_md(line: str) -> str:
        line = _RE_BOLD.sub(r"\1", line)
        line = _RE_ITALIC.sub(r"\1", line)
        line = _RE_CODE.sub(r"\1", line)
        return line.strip()

    for raw_line in report_md.splitlines():
        line = raw_line.rstrip()

        if _RE_HEADING1.match(line):
            text = _strip_md(_RE_HEADING1.match(line).group(1))
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 14)
            pdf.multi_cell(CONTENT_W, 8, text)
            pdf.ln(1)
        elif _RE_HEADING2.match(line):
            text = _strip_md(_RE_HEADING2.match(line).group(1))
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 12)
            pdf.multi_cell(CONTENT_W, 7, text)
            pdf.ln(1)
        elif _RE_HEADING3.match(line):
            text = _strip_md(_RE_HEADING3.match(line).group(1))
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 10)
            pdf.multi_cell(CONTENT_W, 6, text)
        elif _RE_HR.match(line):
            pdf.ln(2)
            pdf.set_draw_color(200, 200, 200)
            x = pdf.get_x()
            y = pdf.get_y()
            pdf.line(MARGIN, y, A4_W - MARGIN, y)
            pdf.ln(2)
        elif line.startswith("- ") or line.startswith("* "):
            text = _strip_md(line[2:])
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(CONTENT_W - 4, 5, f"- {text}", new_x="LMARGIN")
        elif line == "":
            pdf.ln(2)
        else:
            pdf.set_font("Helvetica", "", 9)
            text = _strip_md(line)
            if text:
                pdf.multi_cell(CONTENT_W, 5, text, new_x="LMARGIN")

    return bytes(pdf.output())


# ── .env loader ───────────────────────────────────────────────────────────
def _read_env() -> dict[str, str]:
    """Parse ROOT/.env and return a {KEY: VALUE} dict (ignores comments)."""
    env: dict[str, str] = {}
    env_file = ROOT / ".env"
    if not env_file.exists():
        return env
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        env[key.strip()] = val.strip()
    return env


_ENV = _read_env()


# ── Page config ───────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Institutional Research Platform",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Professional dark theme CSS ───────────────────────────────────────────
st.markdown(
    """
<style>
/* ── Base ── */
[data-testid="stAppViewContainer"] { background: #0d1117; }
[data-testid="stSidebar"]          { background: #0d1117; border-right: 1px solid #21262d; }
[data-testid="stHeader"]           { background: transparent; }
section.main > div                 { padding-top: 1rem; }

/* ── Typography ── */
h1, h2, h3, h4          { color: #e6edf3; font-weight: 600; }
p, li, label, span      { color: #c9d1d9; }
.stMarkdown p           { color: #c9d1d9; }
.stCaption              { color: #8b949e !important; }

/* ── Cards ── */
.card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 10px;
}
.card-header {
    font-size: 0.70rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #8b949e;
    margin-bottom: 4px;
}
.card-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: #e6edf3;
}
.card-sub {
    font-size: 0.78rem;
    color: #8b949e;
    margin-top: 2px;
}

/* ── Stage track ── */
.stage-row {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 7px 12px;
    border-radius: 8px;
    margin: 3px 0;
    background: #161b22;
    border: 1px solid #21262d;
    transition: all 0.2s;
}
.stage-row.done    { border-left: 3px solid #3fb950; }
.stage-row.running { border-left: 3px solid #f0883e; background: #1c1810; animation: pulse 1.5s infinite; }
.stage-row.failed  { border-left: 3px solid #f85149; background: #1c1010; }
.stage-row.pending { border-left: 3px solid #30363d; opacity: 0.6; }
.stage-name  { flex: 1; font-size: 0.84rem; color: #e6edf3; }
.stage-icon  { font-size: 0.9rem; width: 18px; text-align: center; padding-top: 1px; }

@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.6} }

/* ── Cost badge ── */
.cost-badge {
    display: inline-flex; align-items: center; gap: 6px;
    background: #1c2128; border: 1px solid #30363d;
    border-radius: 20px; padding: 4px 14px;
    font-size: 0.8rem; color: #c9d1d9;
}
.cost-badge .amt { color: #58a6ff; font-weight: 700; font-size: 1rem; }

/* ── Live stream ── */
.live-stream {
    background: #0d1117;
    border: 1px solid #21262d;
    border-radius: 10px;
    padding: 16px;
    font-size: 0.82rem;
    line-height: 1.6;
    max-height: 540px;
    overflow-y: auto;
    color: #c9d1d9;
    font-family: 'SF Mono', 'Monaco', 'Cascadia Code', monospace;
    white-space: pre-wrap;
    word-wrap: break-word;
}

/* ── Live activity strip ── */
.activity-strip {
    background: #0f1923;
    border: 1px solid #1f3a5f;
    border-left: 3px solid #58a6ff;
    border-radius: 8px;
    padding: 10px 14px;
    margin-bottom: 8px;
    font-size: 0.80rem;
    color: #c9d1d9;
    font-family: 'SF Mono', monospace;
    display: flex;
    align-items: center;
    gap: 10px;
}
.activity-strip .dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: #58a6ff;
    flex-shrink: 0;
    animation: blink 1s ease-in-out infinite;
}
.activity-strip.idle {
    border-left-color: #30363d; background: #0d1117; opacity: 0.5;
}
.activity-strip.idle .dot { background: #30363d; animation: none; }
.activity-strip.error { border-left-color: #f85149; background: #1c0f0f; }
.activity-strip.error .dot { background: #f85149; animation: none; }
.activity-strip.done { border-left-color: #3fb950; background: #0d1f0f; }
.activity-strip.done .dot { background: #3fb950; animation: none; }

@keyframes blink { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:0.3;transform:scale(0.7)} }

/* ── Report ── */
.report-wrap {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 28px 36px;
    color: #e6edf3;
    line-height: 1.75;
}
.report-wrap h1 { color: #58a6ff; border-bottom: 1px solid #30363d; padding-bottom: 8px; }
.report-wrap h2 { color: #79c0ff; margin-top: 1.6em; }
.report-wrap h3 { color: #cae8ff; }
.report-wrap table { width: 100%; border-collapse: collapse; margin: 12px 0; }
.report-wrap th { background: #1c2128; color: #8b949e; padding: 8px 12px; font-size: 0.78rem;
                  text-transform: uppercase; letter-spacing: 0.05em; border-bottom: 1px solid #30363d; }
.report-wrap td { padding: 8px 12px; border-bottom: 1px solid #21262d; color: #c9d1d9; font-size: 0.86rem; }
.report-wrap blockquote { border-left: 3px solid #388bfd; padding: 8px 16px; background: #1c2128;
                          color: #8b949e; border-radius: 0 6px 6px 0; }
.report-wrap code { background: #1c2128; padding: 2px 6px; border-radius: 4px;
                    font-size: 0.82em; color: #79c0ff; }

/* ── Metric override ── */
[data-testid="stMetricValue"] { color: #58a6ff !important; font-size: 1.3rem !important; }
[data-testid="stMetricLabel"] { color: #8b949e !important; font-size: 0.72rem !important; }

/* ── Buttons ── */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #238636, #2ea043) !important;
    color: white !important; border: none !important;
    border-radius: 8px !important; font-weight: 600 !important;
    font-size: 0.95rem !important; padding: 10px 0 !important;
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #2ea043, #3fb950) !important;
}
.stButton > button:not([kind="primary"]) {
    background: #21262d !important; color: #c9d1d9 !important;
    border: 1px solid #30363d !important; border-radius: 6px !important;
}

/* ── Tabs ── */
[data-testid="stTabs"] [role="tablist"] { border-bottom: 1px solid #21262d; gap: 0; }
[data-testid="stTabs"] button[role="tab"] {
    color: #8b949e; background: transparent; border: none;
    border-bottom: 2px solid transparent; padding: 10px 20px;
    font-size: 0.88rem; font-weight: 500;
}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    color: #e6edf3; border-bottom-color: #f0883e;
}

/* ── Sidebar inputs ── */
[data-testid="stSidebar"] label { color: #8b949e !important; font-size: 0.78rem !important; }
[data-testid="stSidebar"] input { background: #161b22 !important; border-color: #30363d !important;
                                   color: #c9d1d9 !important; }

/* ── Progress bar ── */
[data-testid="stProgressBar"] > div > div { background: linear-gradient(90deg, #238636, #3fb950) !important; }

/* ── Dividers ── */
hr { border-color: #21262d !important; }
.section-title {
    font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.1em;
    color: #8b949e; margin: 14px 0 8px; font-weight: 600;
}

/* ── Ticker chips ── */
.ticker-chip {
    display: inline-block; background: #1c2128; border: 1px solid #388bfd;
    color: #58a6ff; border-radius: 12px; padding: 2px 10px;
    font-size: 0.76rem; font-family: monospace; margin: 2px;
}
.ticker-chip.compute  { border-color: #3fb950; color: #3fb950; }
.ticker-chip.power    { border-color: #f0883e; color: #f0883e; }
.ticker-chip.infra    { border-color: #a371f7; color: #a371f7; }

/* ── Universe card ── */
.uni-card {
    background: #161b22; border: 1px solid #30363d; border-radius: 8px;
    padding: 12px 14px; text-align: center;
}
.uni-card .symbol  { font-size: 1.0rem; font-weight: 700; color: #e6edf3; }
.uni-card .name    { font-size: 0.7rem; color: #8b949e; margin: 2px 0; }
.uni-card .price   { font-size: 1.1rem; font-weight: 700; color: #58a6ff; }

/* ── Supervisor health panel ── */
.supervisor-panel {
    background: #0f1923;
    border: 1px solid #1f3a5f;
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 10px;
}
.supervisor-panel .sup-header {
    display: flex; align-items: center; gap: 10px;
    font-size: 0.72rem; text-transform: uppercase;
    letter-spacing: 0.08em; color: #8b949e; margin-bottom: 8px;
}
.supervisor-panel .sup-badge {
    display: inline-block; border-radius: 12px;
    padding: 2px 10px; font-size: 0.74rem; font-weight: 600;
}
.sup-ok      { background: #0d2810; color: #3fb950; border: 1px solid #238636; }
.sup-degraded{ background: #1c1810; color: #f0883e; border: 1px solid #bd561d; }
.sup-failed  { background: #1c0f0f; color: #f85149; border: 1px solid #da3633; }
.sup-unknown { background: #1c1c1c; color: #8b949e; border: 1px solid #30363d; }
.supervisor-issue { color: #f85149; font-size: 0.80rem; padding: 3px 0; }
.supervisor-warn  { color: #f0883e; font-size: 0.80rem; padding: 2px 0; }
.supervisor-rem   { color: #58a6ff; font-size: 0.80rem; padding: 2px 0; }
</style>
""",
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────────────────
# Helper render functions
# ─────────────────────────────────────────────────────────────────────────
def _render_stage_card(placeholder, num: int, name: str, status: str, outputs: dict) -> None:
    """Render a single stage row card into a Streamlit placeholder."""
    icon_map = {"pending": "○", "running": "◌", "done": "●", "failed": "✕"}
    color_map = {"done": "#3fb950", "running": "#f0883e", "failed": "#f85149", "pending": "#30363d"}
    icon = icon_map.get(status, "○")
    color = color_map.get(status, "#30363d")

    # Short output snippet for done stages
    out = outputs.get(num)
    snippet_html = ""
    if status == "done" and out:
        raw = out if isinstance(out, str) else json.dumps(out, default=str)
        snippet = raw[:90].replace("\n", " ").replace("<", "&lt;").replace(">", "&gt;").strip()
        if len(raw) > 90:
            snippet += "…"
        snippet_html = (
            f'<div style="font-size:0.68rem;color:#8b949e;margin-top:2px">{snippet}</div>'
        )

    placeholder.markdown(
        f"""
<div class="stage-row {status}">
  <span class="stage-icon" style="color:{color}">{icon}</span>
  <div class="stage-name">
    <b>S{num}</b> {name}
    {snippet_html}
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_stream(placeholder, log: list) -> None:
    """Render the live output stream panel."""
    if not log:
        placeholder.markdown(
            """
<div class="live-stream" style="color:#30363d;font-style:italic">
Waiting for pipeline to start…
</div>
""",
            unsafe_allow_html=True,
        )
        return

    lines = []
    for stage_num, stage_name, text in log[-8:]:
        safe = str(text)[:700].strip().replace("<", "&lt;").replace(">", "&gt;")
        lines.append(
            f'<div style="color:#58a6ff;font-size:0.70rem;margin:8px 0 2px">'
            f"━━ S{stage_num}: {stage_name} ━━━━━━━━━━━━</div>"
            f'<div style="color:#c9d1d9;margin-bottom:6px">{safe}{"…" if len(str(text)) > 700 else ""}</div>'
        )

    html = '<div class="live-stream">' + "".join(lines) + "</div>"
    placeholder.markdown(html, unsafe_allow_html=True)


def _render_stage_output(output) -> None:
    """Render full stage output inside an already-open st.expander context."""
    if output is None:
        st.caption("No output recorded for this stage.")
        return
    if isinstance(output, str):
        st.markdown(output)
    elif isinstance(output, dict):
        st.json(output)
    else:
        st.code(str(output))


def _render_activity(placeholder, current_activity: str, running: bool) -> None:
    """Render the live activity strip showing the current in-flight operation."""
    if not current_activity:
        placeholder.markdown(
            '<div class="activity-strip idle"><span class="dot"></span>'
            '<span style="color:#8b949e;font-size:0.75rem">Idle — no pipeline running</span></div>',
            unsafe_allow_html=True,
        )
        return

    if running:
        state_cls = ""
        label = current_activity
    elif "failed" in current_activity.lower() or "error" in current_activity.lower():
        state_cls = " error"
        label = current_activity
    else:
        state_cls = " done"
        label = current_activity

    safe = label.replace("<", "&lt;").replace(">", "&gt;")
    html = (
        f'<div class="activity-strip{state_cls}">'
        f'<span class="dot"></span>'
        f'<span style="font-size:0.75rem">{safe}</span>'
        f"</div>"
    )
    placeholder.markdown(html, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────
# Supervisor health panel renderer
# ─────────────────────────────────────────────────────────────────────────


def _render_supervisor_panel(supervisor_report: dict) -> None:
    """Render the pipeline supervisor health panel from a supervisor_report dict."""
    if not supervisor_report:
        return

    overall = supervisor_report.get("overall_health", "unknown")
    health_pct = supervisor_report.get("health_pct", 0)
    stages_ok = supervisor_report.get("stages_ok", 0)
    stages_degraded = supervisor_report.get("stages_degraded", 0)
    stages_failed = supervisor_report.get("stages_failed", 0)
    stages_skipped = supervisor_report.get("stages_skipped", 0)
    critical_issues = supervisor_report.get("critical_issues", [])
    all_warnings = supervisor_report.get("all_warnings", [])
    remediation = supervisor_report.get("remediation_summary", [])
    interrupted_at = supervisor_report.get("pipeline_interrupted_at")

    badge_cls = {
        "ok": "sup-ok",
        "degraded": "sup-degraded",
        "failed": "sup-failed",
    }.get(overall, "sup-unknown")

    badge_label = {
        "ok": "✅ Healthy",
        "degraded": "⚠️ Degraded",
        "failed": "❌ Failed",
    }.get(overall, "⬜ Unknown")

    # Header row
    h1, h2, h3, h4, h5 = st.columns([3, 1, 1, 1, 1])
    h1.markdown(
        f'<div class="supervisor-panel">'
        f'<div class="sup-header">🤖 Pipeline Supervisor</div>'
        f'<span class="sup-badge {badge_cls}">{badge_label}</span>'
        f'<span style="font-size:0.78rem;color:#8b949e;margin-left:8px">{health_pct:.0f}% healthy</span>'
        f"</div>",
        unsafe_allow_html=True,
    )
    h2.metric("✅ OK", stages_ok)
    h3.metric("⚠️ Degraded", stages_degraded)
    h4.metric("❌ Failed", stages_failed)
    h5.metric("⬜ Skipped", stages_skipped)

    if interrupted_at is not None:
        st.warning(f"⛔ Pipeline interrupted at Stage {interrupted_at}")

    # Issues, warnings, remediation
    if critical_issues or all_warnings or remediation:
        with st.expander(
            f"🔍 Supervisor Details — {len(critical_issues)} issues · {len(all_warnings)} warnings",
            expanded=bool(critical_issues),
        ):
            if critical_issues:
                st.markdown("**Critical Issues**")
                for issue in critical_issues[:10]:
                    st.markdown(
                        f'<div class="supervisor-issue">⚠ {issue}</div>',
                        unsafe_allow_html=True,
                    )
            if remediation:
                st.markdown("**Suggested Remediation**")
                for rem in remediation[:8]:
                    st.markdown(
                        f'<div class="supervisor-rem">→ {rem}</div>',
                        unsafe_allow_html=True,
                    )
            if all_warnings:
                st.markdown("**Warnings**")
                for warn in all_warnings[:8]:
                    st.markdown(
                        f'<div class="supervisor-warn">⚡ {warn}</div>',
                        unsafe_allow_html=True,
                    )


# ─────────────────────────────────────────────────────────────────────────
# Session state bootstrap
# ─────────────────────────────────────────────────────────────────────────
# LLM stages that produce meaningful text for the live stream
_LLM_STREAM_STAGES = {5, 6, 7, 8, 9, 10, 11, 12, 13}


def _init_state():
    defaults: dict = {
        "run_result": None,
        "stage_statuses": {i: "pending" for i, _ in STAGES},
        "stage_outputs": {},
        "running": False,
        "current_stage": -1,
        "live_log": [],
        "loaded_run": None,
        "pipeline_error": "",
        "current_activity": "",  # what the pipeline is doing RIGHT NOW
        "activity_feed": [],  # list of (stage_num, event_msg) for recent events
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    # Pre-seed API key fields from .env on first load only
    if "key_ant" not in st.session_state:
        st.session_state.key_ant = _ENV.get("ANTHROPIC_API_KEY", "")
    if "key_oai" not in st.session_state:
        st.session_state.key_oai = _ENV.get("OPENAI_API_KEY", "")
    if "key_gem" not in st.session_state:
        st.session_state.key_gem = _ENV.get("GOOGLE_API_KEY", "")
    if "key_fmp" not in st.session_state:
        st.session_state.key_fmp = _ENV.get("FMP_API_KEY", "")
    if "key_fhub" not in st.session_state:
        st.session_state.key_fhub = _ENV.get("FINNHUB_API_KEY", "")


_init_state()


# ─────────────────────────────────────────────────────────────────────────
# Model constants
# ─────────────────────────────────────────────────────────────────────────
ALL_MODELS = [
    ("claude-opus-4-6", "Opus 4.6", "$15/$75"),
    ("claude-sonnet-4-6", "Sonnet 4.6", "$3/$15"),
    ("claude-haiku-4-5", "Haiku 4.5", "$0.80/$4"),
    ("gpt-5.4", "GPT-5.4", "$2.50/$10"),
    ("gpt-5.4-mini", "GPT-5.4 mini", "$0.40/$1.60"),
    ("gpt-5.4-nano", "GPT-5.4 nano", "$0.15/$0.60"),
    ("gemini-3.1-pro-preview", "Gemini 3.1 Pro", "$2/$8"),
    ("gemini-2.5-pro", "Gemini 2.5 Pro", "$1.25/$10"),
    ("gemini-2.5-flash", "Gemini 2.5 Flash", "$0.30/$2.50"),
    ("gemini-2.5-flash-lite", "Flash-Lite", "$0.10/$0.40"),
]
ALL_IDS = [m[0] for m in ALL_MODELS]
ALL_LABELS = [f"{m[1]}  ·  {m[2]}" for m in ALL_MODELS]

STAGE_DEFAULTS = {
    5: "claude-sonnet-4-6",
    6: "claude-opus-4-6",
    7: "claude-sonnet-4-6",
    8: "gemini-2.5-pro",
    9: "gemini-2.5-flash",
    10: "claude-opus-4-6",
    11: "claude-sonnet-4-6",
    12: "gpt-5.4",
}
LLM_STAGES = [
    (5, "Evidence Librarian"),
    (6, "Sector Analysis ★"),
    (7, "Valuation"),
    (8, "Macro & Political"),
    (9, "Quant Risk"),
    (10, "Red Team ★"),
    (11, "Associate Review"),
    (12, "Portfolio"),
]


def _prov(m: str) -> str:
    if m.startswith("claude"):
        return "anthropic"
    if m.startswith("gpt") or m.startswith("o"):
        return "openai"
    return "gemini"


# ─────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        """
<div style="padding:14px 0 8px">
  <div style="font-size:1.05rem;font-weight:700;color:#e6edf3;letter-spacing:-0.02em">
    🏦 JPM Research Platform
  </div>
  <div style="font-size:0.72rem;color:#8b949e;margin-top:2px">
    Institutional Asset Management · v8.0
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.divider()

    # ── Client Profile (Onboarding) ───────────────────────────────────────
    st.markdown('<div class="section-title">Client Profile</div>', unsafe_allow_html=True)
    client_name = st.text_input(
        "Client name",
        value="Client",
        key="client_name",
        label_visibility="collapsed",
        placeholder="Client name",
    )

    obj_options = ["total_return", "growth", "income", "preservation"]
    obj_labels_map = {
        "total_return": "Total Return",
        "growth": "Capital Growth",
        "income": "Income Generation",
        "preservation": "Capital Preservation",
    }
    primary_obj = st.selectbox(
        "Primary Objective",
        obj_options,
        format_func=lambda x: obj_labels_map[x],
        index=0,
        key="primary_obj",
        label_visibility="collapsed",
    )

    risk_tol = st.selectbox(
        "Risk Tolerance",
        list(RISK_PROFILES.keys()),
        format_func=lambda x: RISK_PROFILES[x]["label"],
        index=1,
        key="risk_tol",
        label_visibility="collapsed",
    )
    risk_info = RISK_PROFILES[risk_tol]
    st.caption(f"{risk_info['description']}")

    time_horizon = st.slider(
        "Time horizon (years)", 1, 20, 5, key="time_horizon", label_visibility="collapsed"
    )
    st.caption(f"Horizon: {time_horizon} years")

    investment_amt = st.number_input(
        "Investment amount ($)",
        min_value=10_000,
        max_value=100_000_000,
        value=1_000_000,
        step=100_000,
        key="invest_amt",
        label_visibility="collapsed",
    )

    st.divider()

    # ── Investment Theme & Universe ───────────────────────────────────────
    st.markdown('<div class="section-title">Investment Theme</div>', unsafe_allow_html=True)
    theme_key = st.selectbox(
        "Theme",
        list(INVESTMENT_THEMES.keys()),
        format_func=lambda k: INVESTMENT_THEMES[k]["name"],
        index=0,
        key="theme_sel",
        label_visibility="collapsed",
    )
    theme_info = INVESTMENT_THEMES[theme_key]
    st.caption(theme_info["description"])

    if theme_key == "custom":
        custom_input = st.text_area(
            "Enter tickers (comma-separated)",
            value="NVDA, AAPL, MSFT, AMZN",
            key="custom_tickers",
            label_visibility="collapsed",
            height=68,
        )
        selected_tickers: list[str] = [
            t.strip().upper() for t in custom_input.split(",") if t.strip()
        ]
    else:
        default_tickers = theme_info["default_tickers"]
        selected_tickers = st.multiselect(
            "Tickers",
            default_tickers,
            default=default_tickers,
            key="theme_tickers",
            label_visibility="collapsed",
        )

    if selected_tickers:
        chip_html = ""
        for t in selected_tickers:
            chip_html += f'<span class="ticker-chip">{t}</span>'
        st.markdown(chip_html, unsafe_allow_html=True)

    st.divider()

    # ── ESG / Mandate Constraints ─────────────────────────────────────────
    with st.expander("Mandate & Constraints", expanded=False):
        esg_mandate = st.checkbox("ESG mandate", value=False, key="esg")
        excl_tobacco = st.checkbox("Exclude tobacco", value=False, key="excl_tobacco")
        excl_weapons = st.checkbox("Exclude weapons", value=False, key="excl_weapons")
        excl_fossil = st.checkbox("Exclude fossil fuels", value=False, key="excl_fossil")
        min_mktcap = st.number_input("Min market cap ($B)", 0.0, 500.0, 5.0, key="min_cap")
        benchmark = st.selectbox(
            "Benchmark", ["SPY", "QQQ", "IWM", "DIA", "VTI"], index=0, key="benchmark"
        )
        special_instr = st.text_area(
            "Special instructions",
            value="",
            key="special_instr",
            label_visibility="collapsed",
            placeholder="e.g. Focus on companies with >20% FCF yield",
            height=60,
        )

    st.divider()

    # ── API Keys ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">LLM API Keys</div>', unsafe_allow_html=True)
    anthropic_key = st.text_input(
        "Anthropic",
        type="password",
        key="key_ant",
        placeholder="sk-ant-…",
        label_visibility="collapsed",
    )
    openai_key = st.text_input(
        "OpenAI",
        type="password",
        key="key_oai",
        placeholder="sk-… (OpenAI)",
        label_visibility="collapsed",
    )
    gemini_key = st.text_input(
        "Google",
        type="password",
        key="key_gem",
        placeholder="AIza… (Gemini)",
        label_visibility="collapsed",
    )

    st.markdown(
        '<div class="section-title" style="margin-top:8px">Data API Keys</div>',
        unsafe_allow_html=True,
    )
    fmp_key = st.text_input(
        "FMP",
        type="password",
        key="key_fmp",
        placeholder="FMP API key",
        label_visibility="collapsed",
    )
    finnhub_key = st.text_input(
        "Finnhub",
        type="password",
        key="key_fhub",
        placeholder="Finnhub API key",
        label_visibility="collapsed",
    )

    provider_keys: dict[str, str] = {
        k: v
        for k, v in {
            "anthropic": anthropic_key,
            "openai": openai_key,
            "gemini": gemini_key,
            "fmp": fmp_key,
            "finnhub": finnhub_key,
        }.items()
        if v
    }
    any_key = bool(
        {k: v for k, v in provider_keys.items() if k in ("anthropic", "openai", "gemini")}
    )

    if any_key:
        badges = []
        if anthropic_key:
            badges.append("🟢 Anthropic")
        if openai_key:
            badges.append("🟢 OpenAI")
        if gemini_key:
            badges.append("🟢 Google")
        if fmp_key:
            badges.append("🟢 FMP")
        if finnhub_key:
            badges.append("🟢 Finnhub")
        st.caption("  ".join(badges))
        if _ENV:
            st.caption("🔑 Auto-loaded from `.env`")

    st.divider()

    # ── Model ─────────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Model & Temperature</div>', unsafe_allow_html=True)
    temperature = st.slider(
        "Temperature",
        0.0,
        1.0,
        0.3,
        0.05,
        key="temp_slider",
        label_visibility="collapsed",
        help="Low (0.2–0.4) = deterministic research; high = more creative",
    )
    st.caption(f"Temperature: {temperature:.2f}")

    use_same = st.checkbox("Single model for all stages", value=True, key="use_same")
    if use_same:
        def_idx = ALL_IDS.index("claude-sonnet-4-6")
        g_idx = st.selectbox(
            "Model",
            range(len(ALL_MODELS)),
            format_func=lambda i: ALL_LABELS[i],
            index=def_idx,
            key="global_model",
            label_visibility="collapsed",
        )
        stage_models: dict[int, str] = {n: ALL_IDS[g_idx] for n, _ in LLM_STAGES}
        model_choice = ALL_IDS[g_idx]
    else:
        stage_models = {}
        with st.expander("Per-stage model", expanded=False):
            st.caption("★ = highest-impact stages")
            for sn, sl in LLM_STAGES:
                def_idx = ALL_IDS.index(STAGE_DEFAULTS.get(sn, "claude-sonnet-4-6"))
                idx = st.selectbox(
                    f"S{sn}: {sl}",
                    range(len(ALL_MODELS)),
                    format_func=lambda i: ALL_LABELS[i],
                    index=def_idx,
                    key=f"sm_{sn}",
                    label_visibility="collapsed",
                )
                stage_models[sn] = ALL_IDS[idx]
        model_choice = stage_models.get(6, "claude-opus-4-6")

    # Missing key warning
    if stage_models:
        missing = {_prov(m) for m in stage_models.values()} - set(provider_keys)
        if missing and any_key:
            st.warning(f"⚠️ Missing key: {', '.join(sorted(missing))}", icon="⚠️")

    st.divider()

    # ── Cost Estimate ─────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Run Cost Estimate</div>', unsafe_allow_html=True)
    if selected_tickers and stage_models:
        try:
            est = estimate_run_cost(selected_tickers, stage_models, model_choice)
            st.markdown(
                f"""
<div class="cost-badge">
  💰 <span class="amt">{format_cost(est.total_cost_usd)}</span>
  &nbsp;·&nbsp; {format_cost(est.low_usd)} – {format_cost(est.high_usd)}
</div>
<div style="font-size:0.72rem;color:#8b949e;margin-top:6px">
  {len(selected_tickers)} tickers · {len(LLM_STAGES)} LLM stages
</div>
""",
                unsafe_allow_html=True,
            )
        except Exception:
            st.caption("Cost estimate unavailable")

    st.divider()
    st.caption("💾 `reports/` — survives restarts")

# ── Build client profile from sidebar inputs ──────────────────────────────
client_profile = ClientProfile(
    name=client_name,
    primary_objective=primary_obj,
    investment_theme=theme_key,
    time_horizon_years=time_horizon,
    risk_tolerance=risk_tol,
    tickers=selected_tickers,
    esg_mandate=esg_mandate,
    exclude_tobacco=excl_tobacco,
    exclude_weapons=excl_weapons,
    exclude_fossil_fuel=excl_fossil,
    min_market_cap_bn=min_mktcap,
    benchmark=benchmark,
    investment_amount_usd=float(investment_amt),
    special_instructions=special_instr,
)


# ─────────────────────────────────────────────────────────────────────────
# Page header
# ─────────────────────────────────────────────────────────────────────────
st.markdown(
    """
<div style="padding:8px 0 18px">
  <div style="font-size:1.6rem;font-weight:800;color:#e6edf3;letter-spacing:-0.03em">
    Institutional Research Platform
  </div>
  <div style="font-size:0.82rem;color:#8b949e;margin-top:4px">
    JPM-style asset management · 15-stage multi-agent pipeline · Live data (FMP + Finnhub)
  </div>
</div>
""",
    unsafe_allow_html=True,
)

tab_pipeline, tab_report, tab_saved, tab_about = st.tabs(
    ["⚡ Pipeline", "📄 Report", "🗂️ Saved Runs", "ℹ️ About"]
)


# ═════════════════════════════════════════════════════════════════════════
# TAB 1 — PIPELINE
# ═════════════════════════════════════════════════════════════════════════
with tab_pipeline:
    # ── Controls ──────────────────────────────────────────────────────────
    cc1, cc2, cc3 = st.columns([3, 1, 4])
    with cc1:
        run_disabled = st.session_state.running or not any_key or not selected_tickers
        run_btn = st.button(
            "▶  Run Full Pipeline",
            disabled=run_disabled,
            type="primary",
            use_container_width=True,
            help="Enter an API key and choose tickers to begin.",
        )
    with cc2:
        reset_btn = st.button("↺  Reset", use_container_width=True)
        if reset_btn:
            st.session_state.run_result = None
            st.session_state.loaded_run = None
            st.session_state.stage_statuses = {i: "pending" for i, _ in STAGES}
            st.session_state.stage_outputs = {}
            st.session_state.running = False
            st.session_state.current_stage = -1
            st.session_state.live_log = []
            st.rerun()

    if not any_key:
        st.info("👈  Enter at least one API key in the sidebar to enable pipeline runs.")

    # Show persistent error from last run (cleared when a new run starts)
    if st.session_state.get("pipeline_error"):
        st.error(f"❌ Last run failed: {st.session_state.pipeline_error}")

    # ── Two-column layout ─────────────────────────────────────────────────
    col_stages, col_live = st.columns([5, 7])

    with col_stages:
        st.markdown('<div class="section-title">Stage Tracker</div>', unsafe_allow_html=True)
        stage_placeholders: dict[int, object] = {}
        for num, name in STAGES:
            status = st.session_state.stage_statuses.get(num, "pending")
            output = st.session_state.stage_outputs.get(num)
            # Compact status row — updated live during pipeline run
            row_ph = st.empty()
            stage_placeholders[num] = row_ph
            _render_stage_card(row_ph, num, name, status, st.session_state.stage_outputs)
            # Full-output expander — only rendered when stage is done with output
            if status == "done" and output:
                with st.expander(f"📄 S{num:02d} — view full output", expanded=False):
                    _render_stage_output(output)

    with col_live:
        st.markdown('<div class="section-title">Live Activity</div>', unsafe_allow_html=True)
        activity_ph = st.empty()  # live activity strip (updates every callback)
        _render_activity(
            activity_ph, st.session_state.current_activity, running=st.session_state.running
        )
        st.markdown(
            '<div class="section-title" style="margin-top:10px">Completed Stage Outputs</div>',
            unsafe_allow_html=True,
        )
        stream_ph = st.empty()
        _render_stream(stream_ph, st.session_state.live_log)

    # ── Progress / status area ────────────────────────────────────────────
    progress_ph = st.empty()
    status_ph = st.empty()

    # Show last run's cost/status if not currently running
    if not st.session_state.running and st.session_state.run_result:
        rr = st.session_state.run_result
        if rr.token_log:
            c = calculate_actual_cost(rr.token_log)
            status_ph.success(
                f"✅ {rr.run_id} · {len(rr.tickers)} stocks · "
                f"Actual cost **{format_cost(c.total_cost_usd)}** · "
                f"{c.total_input_tokens + c.total_output_tokens:,} tokens · Saved"
            )
        # Show supervisor panel if available
        if getattr(rr, "supervisor_report", None):
            st.markdown("---")
            _render_supervisor_panel(rr.supervisor_report)

    # ─────────────────────────────────────────────────────────────────────
    # Run pipeline
    # ─────────────────────────────────────────────────────────────────────
    if run_btn and any_key and selected_tickers:
        # Reset state
        st.session_state.running = True
        st.session_state.stage_statuses = {i: "pending" for i, _ in STAGES}
        st.session_state.stage_outputs = {}
        st.session_state.run_result = None
        st.session_state.live_log = []
        st.session_state.pipeline_error = ""  # clear any previous error
        st.session_state.current_activity = "Initialising pipeline…"
        st.session_state.activity_feed = []

        progress_bar = progress_ph.progress(0, text="Initialising pipeline…")

        runner = PipelineRunner(
            provider_keys=provider_keys,
            model=model_choice,
            tickers=selected_tickers,
            temperature=temperature,
            stage_models=stage_models,
            client_profile=client_profile,
        )

        total_stages = len(STAGES)
        done_count = [0]

        def _progress_cb(stage_num: int, stage_name: str, status: str, output) -> None:
            st.session_state.stage_statuses[stage_num] = status
            if output is not None:
                st.session_state.stage_outputs[stage_num] = output

            # Refresh stage card immediately
            ph = stage_placeholders.get(stage_num)
            if ph:
                _render_stage_card(
                    ph, stage_num, stage_name, status, st.session_state.stage_outputs
                )

            if status == "running":
                # Update live activity strip with what stage just started
                msg = f"S{stage_num:02d}: {stage_name} — starting…"
                st.session_state.current_activity = msg
                _render_activity(activity_ph, msg, running=True)
                # Progress bar: give small increment for early stages
                pct = max(1, int(stage_num / total_stages * 15))
                progress_bar.progress(pct, text=f"Stage {stage_num}/{total_stages}: {stage_name}…")

            elif status == "done":
                # Append text output to live log for LLM stages
                if stage_num in _LLM_STREAM_STAGES:
                    text = output if isinstance(output, str) else ""
                    if text:
                        st.session_state.live_log.append((stage_num, stage_name, text))
                _render_stream(stream_ph, st.session_state.live_log)
                done_count[0] += 1
                pct = min(int(done_count[0] / total_stages * 95), 95)
                progress_bar.progress(pct, text=f"Stage {stage_num}: {stage_name} ✓")

            elif status == "failed":
                msg = f"S{stage_num:02d}: {stage_name} — ❌ FAILED"
                st.session_state.current_activity = msg
                _render_activity(activity_ph, msg, running=False)

        def _activity_cb(msg: str) -> None:
            """Called from _call_llm before each API request."""
            st.session_state.current_activity = msg
            st.session_state.activity_feed.append(msg)
            _render_activity(activity_ph, msg, running=True)

        async def _run_pipeline() -> RunResult:
            return await runner.run(
                progress_callback=_progress_cb,
                activity_callback=_activity_cb,
            )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        run_result: RunResult | None = None
        try:
            run_result = loop.run_until_complete(_run_pipeline())
        except Exception as exc:
            st.session_state.running = False
            st.session_state.pipeline_error = str(exc)
            logger.exception("Pipeline crashed: %s", exc)
        finally:
            loop.close()

        if run_result is None:
            # Re-render to show the error banner and re-enable the Run button
            st.rerun()

        # Sync authoritative stage statuses from RunResult
        for sr in run_result.stages:
            st.session_state.stage_statuses[sr.stage_num] = sr.status
            if sr.raw_text:
                st.session_state.stage_outputs[sr.stage_num] = sr.raw_text
            elif sr.output:
                st.session_state.stage_outputs[sr.stage_num] = sr.output

        st.session_state.run_result = run_result
        st.session_state.current_stage = 14
        st.session_state.running = False

        # Persist to disk
        try:
            save_run(run_result)
        except Exception as exc:
            logger.warning("Could not save run to disk: %s", exc)

        progress_ph.progress(100, text="Pipeline complete!")

        if run_result.token_log:
            c = calculate_actual_cost(run_result.token_log)
            st.session_state.current_activity = (
                f"Pipeline complete — {format_cost(c.total_cost_usd)} actual cost"
            )
            _render_activity(activity_ph, st.session_state.current_activity, running=False)
            status_ph.success(
                f"✅ {run_result.run_id} complete · "
                f"Cost: **{format_cost(c.total_cost_usd)}** · "
                f"{c.total_input_tokens + c.total_output_tokens:,} tokens · Auto-saved"
            )
        else:
            st.session_state.current_activity = "Pipeline complete"
            _render_activity(activity_ph, "Pipeline complete", running=False)
            status_ph.success(f"✅ {run_result.run_id} complete · Auto-saved to disk")

        st.rerun()


# ═════════════════════════════════════════════════════════════════════════
# TAB 2 — REPORT
# ═════════════════════════════════════════════════════════════════════════
with tab_report:
    active_result: RunResult | None = st.session_state.get("run_result")
    loaded: dict | None = st.session_state.get("loaded_run")

    if active_result is None and loaded is None:
        # ── Empty state ───────────────────────────────────────────────────
        st.markdown(
            """
<div style="text-align:center;padding:60px 0;color:#8b949e">
  <div style="font-size:3rem;margin-bottom:14px">📄</div>
  <div style="font-size:1rem;font-weight:600;color:#c9d1d9;margin-bottom:8px">
    No report yet
  </div>
  <div style="font-size:0.84rem">
    Run the pipeline from the ⚡ Pipeline tab — or load a saved run from 🗂️ Saved Runs
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

        # Universe preview
        if selected_tickers:
            st.markdown("---")
            st.markdown('<div class="section-title">Universe Preview</div>', unsafe_allow_html=True)
            st.caption(
                f"{len(selected_tickers)} tickers · {INVESTMENT_THEMES.get(theme_key, {}).get('name', 'Custom')}"
            )
            chip_html = " ".join(f'<span class="ticker-chip">{t}</span>' for t in selected_tickers)
            st.markdown(chip_html, unsafe_allow_html=True)
    else:
        # ── Display report ────────────────────────────────────────────────
        if loaded:
            run_id = loaded.get("run_id", "?")
            tickers = loaded.get("tickers", [])
            model = loaded.get("model", "?")
            report_md = loaded.get("final_report_md", "")
            stages_raw = loaded.get("stages", [])
            token_log_src: list = []
        else:
            run_id = active_result.run_id
            tickers = active_result.tickers
            model = active_result.model
            report_md = active_result.final_report_md
            stages_raw = [
                {
                    "stage_num": s.stage_num,
                    "stage_name": s.stage_name,
                    "status": s.status,
                    "elapsed_secs": s.elapsed_secs,
                    "error": s.error,
                }
                for s in active_result.stages
            ]
            token_log_src = active_result.token_log

        word_count = len(report_md.split())
        pages_est = max(1, word_count // 250)
        stages_ok = sum(1 for s in stages_raw if s.get("status") == "done")

        # Metrics row
        mc = st.columns(5)
        mc[0].markdown(
            f'<div class="card"><div class="card-header">Run ID</div>'
            f'<div class="card-value" style="font-size:0.82rem;font-family:monospace">{run_id}</div></div>',
            unsafe_allow_html=True,
        )
        mc[1].markdown(
            f'<div class="card"><div class="card-header">Coverage</div>'
            f'<div class="card-value">{len(tickers)}</div>'
            f'<div class="card-sub">stocks</div></div>',
            unsafe_allow_html=True,
        )
        mc[2].markdown(
            f'<div class="card"><div class="card-header">Stages</div>'
            f'<div class="card-value">{stages_ok}'
            f'<span style="font-size:1rem;color:#8b949e">/{len(STAGES)}</span></div>'
            f'<div class="card-sub">complete</div></div>',
            unsafe_allow_html=True,
        )
        mc[3].markdown(
            f'<div class="card"><div class="card-header">Report</div>'
            f'<div class="card-value">{word_count:,}</div>'
            f'<div class="card-sub">words · ~{pages_est}pp</div></div>',
            unsafe_allow_html=True,
        )
        if token_log_src:
            c = calculate_actual_cost(token_log_src)
            mc[4].markdown(
                f'<div class="card"><div class="card-header">Actual Cost</div>'
                f'<div class="card-value">{format_cost(c.total_cost_usd)}</div>'
                f'<div class="card-sub">{c.total_input_tokens + c.total_output_tokens:,} tokens</div></div>',
                unsafe_allow_html=True,
            )
        else:
            mc[4].markdown(
                f'<div class="card"><div class="card-header">Model</div>'
                f'<div class="card-value" style="font-size:0.78rem">{model[:22]}</div></div>',
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # Download buttons
        dc1, dc2, dc3, _dc4 = st.columns([2, 2, 2, 3])
        with dc1:
            st.download_button(
                "⬇️  Download .md",
                data=report_md,
                file_name=f"Research_{run_id}.md",
                mime="text/markdown",
                type="primary",
                use_container_width=True,
            )
        with dc2:
            json_payload = json.dumps(
                loaded
                if loaded
                else {
                    "run_id": run_id,
                    "tickers": tickers,
                    "model": model,
                    "final_report_md": report_md,
                    "stages": stages_raw,
                },
                indent=2,
                default=str,
            )
            st.download_button(
                "⬇️  Download .json",
                data=json_payload,
                file_name=f"Research_{run_id}.json",
                mime="application/json",
                use_container_width=True,
            )
        with dc3:
            # ACT-S6-3: PDF export — generate on demand via fpdf2
            pdf_bytes = _generate_report_pdf(run_id, tickers, report_md)
            if pdf_bytes:
                st.download_button(
                    "📥  Download PDF",
                    data=pdf_bytes,
                    file_name=f"Research_{run_id}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            else:
                st.caption("PDF unavailable (fpdf2 not installed)")

        st.markdown("---")

        # ── Supervisor Health Panel ───────────────────────────────────────
        _sup_report = None
        if active_result and getattr(active_result, "supervisor_report", None):
            _sup_report = active_result.supervisor_report
        elif loaded and loaded.get("supervisor_report"):
            _sup_report = loaded["supervisor_report"]
        if _sup_report:
            _render_supervisor_panel(_sup_report)
            st.markdown("---")

        # Report body
        st.markdown('<div class="report-wrap">', unsafe_allow_html=True)
        if report_md:
            st.markdown(report_md)
        else:
            st.markdown(
                "*Report content not available. "
                "The pipeline may have completed without generating a final report.*"
            )
        st.markdown("</div>", unsafe_allow_html=True)

        # Stage timing expander
        if stages_raw:
            with st.expander("⏱️  Stage Timing & Errors", expanded=False):
                cols_t = st.columns(2)
                for i, s in enumerate(stages_raw):
                    sn = s.get("stage_num", "?")
                    sname = s.get("stage_name", "?")
                    ss = s.get("status", "?")
                    el = s.get("elapsed_secs", 0) or 0
                    err = s.get("error") or ""
                    icon = "✅" if ss == "done" else "❌" if ss == "failed" else "⬜"
                    line = f"{icon} **S{sn}: {sname}** — {el:.1f}s"
                    if err:
                        line += f" · ⚠️ `{err[:60]}`"
                    cols_t[i % 2].markdown(line)

                # ACT-S7-3: per-stage ms from SelfAuditPacket
                _rr = st.session_state.get("run_result")
                _ap = (getattr(_rr, "audit_packet", None) or {}) if _rr else {}
                _lat = _ap.get("stage_latencies_ms", {})
                _dur = _ap.get("total_pipeline_duration_s", 0)
                if _lat:
                    st.markdown("---")
                    st.markdown("**Engine-level stage latencies (ms)**")
                    lat_cols = st.columns(4)
                    for j, (skey, ms) in enumerate(
                        sorted(_lat.items(), key=lambda x: int(x[0].replace("stage_", "") or 0))
                    ):
                        lat_cols[j % 4].metric(skey, f"{ms:.0f} ms")
                    if _dur:
                        st.metric("Total pipeline duration", f"{_dur:.1f} s")

                # ACT-S9-3: Rebalancing summary from SelfAuditPacket
                _rs = _ap.get("rebalancing_summary", {})
                if _rs:
                    st.markdown("---")
                    st.markdown("**Rebalancing snapshot (Audit Packet)**")
                    rs_cols = st.columns(4)
                    rs_cols[0].metric("Trades", _rs.get("trade_count", 0))
                    rs_cols[1].metric("Turnover", f"{_rs.get('total_turnover_pct', 0):.1f}%")
                    rs_cols[2].metric(
                        "Est. Impact", f"{_rs.get('estimated_total_impact_bps', 0):.1f} bps"
                    )
                    rs_cols[3].metric("Trigger", _rs.get("trigger", "—") or "—")
                    if _rs.get("summary"):
                        st.caption(_rs["summary"])

        # Token/cost breakdown expander
        if token_log_src:
            with st.expander("💰  Token & Cost Breakdown", expanded=False):
                c = calculate_actual_cost(token_log_src)
                for entry in c.stage_costs:
                    sn = entry.get("stage_num", "?")
                    m = entry.get("model", "?")
                    it = entry.get("input_tokens", 0)
                    ot = entry.get("output_tokens", 0)
                    cu = entry.get("cost_usd", 0.0)
                    st.caption(f"S{sn} · `{m}` · {it:,}↑ {ot:,}↓ · **{format_cost(cu)}**")
                st.markdown(
                    f"**Total: {format_cost(c.total_cost_usd)}** "
                    f"({c.total_input_tokens + c.total_output_tokens:,} tokens)"
                )

        # ── P-4: Quant Analytics panel ────────────────────────────────────
        # Displays ETF overlap, VaR/drawdown, factor exposures, and IC vote
        # from Stage 9 and Stage 12 outputs (available for both live and loaded runs).
        def _stage_out(n: int) -> dict:
            """Extract stage output dict from loaded run or live session state."""
            if loaded:
                for s in loaded.get("stages", []):
                    if isinstance(s, dict) and s.get("stage_num") == n:
                        out = s.get("output")
                        if isinstance(out, dict):
                            return out
                return {}
            return st.session_state.stage_outputs.get(n, {})

        risk_out = _stage_out(9)
        portfolio_out = _stage_out(12)

        if risk_out or portfolio_out:
            with st.expander("📊  Quant Analytics", expanded=False):
                # ── Market Risk Metrics ───────────────────────────────────
                var_d = risk_out.get("var_analysis") or risk_out.get("var_95") or {}
                dd_d = risk_out.get("drawdown_analysis") or {}
                if var_d or dd_d:
                    st.markdown("#### 📈 Market Risk Metrics")
                    rm1, rm2, rm3, rm4 = st.columns(4)
                    rm1.metric("VaR 95% (1-day)", f"{var_d.get('var_pct', 0):.2f}%")
                    rm2.metric("CVaR 95% (1-day)", f"{var_d.get('cvar_pct', 0):.2f}%")
                    dd_pct = dd_d.get("max_drawdown_pct") or risk_out.get("max_drawdown", 0)
                    rm3.metric("Max Drawdown", f"{dd_pct:.2f}%")
                    port_vol = risk_out.get("portfolio_volatility") or 0
                    rm4.metric("Portfolio Volatility", f"{port_vol * 100:.2f}%")
                    var_method = risk_out.get("var_method", "")
                    conf_level = risk_out.get("confidence_level", 0.95) or 0.95
                    if var_method:
                        st.caption(
                            f"VaR method: **{var_method}** · "
                            f"confidence level: **{conf_level * 100:.0f}%**"
                        )

                # ── ETF Overlap ───────────────────────────────────────────
                etf_data = risk_out.get("etf_overlap", {})
                diff_score = risk_out.get("etf_differentiation_score")
                if etf_data or diff_score is not None:
                    st.markdown("---")
                    st.markdown("#### 🔄 ETF Overlap & Differentiation")
                    if diff_score is not None:
                        score_colour = (
                            "#2ea043"
                            if diff_score >= 70
                            else "#f0a500"
                            if diff_score >= 40
                            else "#f85149"
                        )
                        st.markdown(
                            f"**Differentiation Score:** "
                            f"<span style='color:{score_colour};font-size:1.15rem;"
                            f"font-weight:700'>{diff_score:.1f} / 100</span>",
                            unsafe_allow_html=True,
                        )
                        if diff_score < 40:
                            st.warning(
                                "⚠️ Portfolio closely replicates a passive ETF "
                                "— active share is low."
                            )
                        elif diff_score >= 70:
                            st.success(
                                "✅ Portfolio is well-differentiated from common ETF benchmarks."
                            )

                    if isinstance(etf_data, dict):
                        # Support both {"overlaps": {ETF: pct}} and
                        # {"etf_overlaps": {ETF: pct}} key variants
                        overlaps = etf_data.get("overlaps") or etf_data.get("etf_overlaps") or {}
                        if isinstance(overlaps, dict) and overlaps:
                            etf_rows = [
                                {
                                    "ETF": etf,
                                    "Overlap %": (
                                        f"{pct:.1f}%" if isinstance(pct, (int, float)) else str(pct)
                                    ),
                                }
                                for etf, pct in overlaps.items()
                            ]
                            st.table(etf_rows)

                # ── Factor Exposures ──────────────────────────────────────
                factor_data = risk_out.get("factor_exposures", [])
                if factor_data:
                    st.markdown("---")
                    st.markdown("#### 🎯 Factor Exposures")
                    fe_rows = []
                    for fe in factor_data:
                        if isinstance(fe, dict):
                            fe_rows.append(
                                {
                                    "Ticker": fe.get("ticker", ""),
                                    "β Market": f"{fe.get('market_beta', 0):.2f}",
                                    "β Size": f"{fe.get('size_loading', 0):.2f}",
                                    "β Value": f"{fe.get('value_loading', 0):.2f}",
                                    "β Momentum": f"{fe.get('momentum_loading', 0):.2f}",
                                    "β Quality": f"{fe.get('quality_loading', 0):.2f}",
                                }
                            )
                    if fe_rows:
                        st.table(fe_rows)
                    pf_exp = risk_out.get("portfolio_factor_exposure")
                    if isinstance(pf_exp, dict):
                        st.caption(
                            f"Portfolio composite — "
                            f"β(market)={pf_exp.get('market_beta', 0):.2f}  "
                            f"β(size)={pf_exp.get('size_loading', 0):.2f}  "
                            f"β(momentum)={pf_exp.get('momentum_loading', 0):.2f}"
                        )

                # ── Investment Committee ──────────────────────────────────
                ic_record = portfolio_out.get("ic_record", {})
                if ic_record:
                    st.markdown("---")
                    st.markdown("#### 🏛️ Investment Committee")
                    ic_approved = ic_record.get("is_approved", False)
                    ic_c1, ic_c2 = st.columns([2, 3])
                    with ic_c1:
                        if ic_approved:
                            st.success("✅ IC Approved")
                        else:
                            st.error("❌ IC Not Approved")
                        votes = ic_record.get("votes", {})
                        if isinstance(votes, dict):
                            for member, vote in votes.items():
                                v_str = str(vote).lower()
                                icon = "✅" if v_str in ("approve", "yes", "pass") else "❌"
                                st.caption(f"{icon} {member}: {vote}")
                    with ic_c2:
                        rationale = ic_record.get("rationale") or ic_record.get(
                            "decision_rationale", ""
                        )
                        if rationale:
                            st.markdown(f"*{rationale[:400]}*")
                        flags = ic_record.get("condition_flags", [])
                        if flags:
                            st.caption(f"Condition flags: {', '.join(str(f) for f in flags)}")

                # ── Mandate Compliance ────────────────────────────────────
                mandate = portfolio_out.get("mandate_compliance", {})
                if mandate:
                    st.markdown("---")
                    st.markdown("#### 📋 Mandate Compliance")
                    is_compliant = mandate.get("is_compliant", True)
                    if is_compliant:
                        st.success("✅ Portfolio passed all mandate constraints")
                    else:
                        st.warning("⚠️ Mandate violations detected")
                        for v in mandate.get("violations", []):
                            desc = v.get("description", str(v)) if isinstance(v, dict) else str(v)
                            st.caption(f"• {desc}")

                # ── ESG Analytics (ACT-S6-2) ──────────────────────────────
                stage6_out = _stage_out(6)
                esg_out = stage6_out.get("esg_output") or {} if isinstance(stage6_out, dict) else {}
                esg_parsed = {}
                if isinstance(esg_out, dict):
                    esg_parsed = esg_out.get("parsed_output") or {}
                esg_scores = (
                    esg_parsed.get("esg_scores", []) if isinstance(esg_parsed, dict) else []
                )
                if esg_scores:
                    st.markdown("---")
                    st.markdown("#### 🌱 ESG Analytics")
                    # Summary metrics
                    composite_scores = [
                        s.get("esg_score", 0)
                        for s in esg_scores
                        if isinstance(s, dict) and s.get("esg_score") is not None
                    ]
                    exclusions = [
                        s.get("ticker", "?")
                        for s in esg_scores
                        if isinstance(s, dict) and s.get("exclusion_trigger")
                    ]
                    if composite_scores:
                        em1, em2, em3 = st.columns(3)
                        em1.metric(
                            "Portfolio ESG Avg",
                            f"{sum(composite_scores) / len(composite_scores):.0f} / 100",
                        )
                        em2.metric("Tickers Scored", str(len(esg_scores)))
                        em3.metric(
                            "Exclusion Triggers",
                            str(len(exclusions)),
                            delta=f"{', '.join(exclusions)}" if exclusions else None,
                            delta_color="inverse",
                        )
                    if exclusions:
                        st.warning(f"⚡ Exclusion triggered for: {', '.join(exclusions)}")

                    # Per-ticker table
                    esg_rows = []
                    for s in esg_scores:
                        if not isinstance(s, dict):
                            continue
                        ticker = s.get("ticker", "?")
                        flags = s.get("controversy_flags", [])
                        flag_str = "; ".join(flags[:2]) if flags else "—"
                        esg_rows.append(
                            {
                                "Ticker": ticker,
                                "ESG": s.get("esg_score", "—"),
                                "E": s.get("e_score", "—"),
                                "S": s.get("s_score", "—"),
                                "G": s.get("g_score", "—"),
                                "Exclusion": "❌ YES" if s.get("exclusion_trigger") else "✅ No",
                                "Top Controversy": flag_str,
                            }
                        )
                    if esg_rows:
                        st.table(esg_rows)
                        # ACT-S10-2: ESG CSV download button
                        try:
                            import csv
                            import io
                            from research_pipeline.services.esg_service import (
                                ESGService as _ESGService,
                            )

                            _esg_svc = _ESGService()
                            _csv_buf = io.StringIO()
                            _fieldnames = [
                                "ticker",
                                "overall_rating",
                                "e_score",
                                "s_score",
                                "g_score",
                                "controversy_flag",
                            ]
                            _writer = csv.DictWriter(_csv_buf, fieldnames=_fieldnames)
                            _writer.writeheader()
                            for _row_data in esg_rows:
                                _ticker_val = _row_data.get("Ticker", "")
                                if _ticker_val:
                                    _sc = _esg_svc.get_score(_ticker_val)
                                    _writer.writerow(
                                        {
                                            "ticker": _ticker_val,
                                            "overall_rating": _sc.overall_rating.value,
                                            "e_score": _sc.environmental_score,
                                            "s_score": _sc.social_score,
                                            "g_score": _sc.governance_score,
                                            "controversy_flag": _sc.controversy_flag,
                                        }
                                    )
                            st.download_button(
                                label="⬇️ Download ESG CSV",
                                data=_csv_buf.getvalue(),
                                file_name="esg_scores.csv",
                                mime="text/csv",
                                key="esg_csv_download",
                            )
                        except Exception:
                            pass  # ESG download is best-effort; do not crash UI

                    # Methodology note from first entry
                    first_note = next(
                        (
                            s.get("methodology_note")
                            for s in esg_scores
                            if isinstance(s, dict) and s.get("methodology_note")
                        ),
                        None,
                    )
                    if first_note:
                        st.caption(f"📝 {first_note}")

                # ── Fixed-Income Context (P-7) ───────────────────────────
                fi_ctx = risk_out.get("fixed_income_context", {})
                if fi_ctx:
                    st.markdown("---")
                    st.markdown("#### 🏦 Fixed-Income Macro Context")
                    fc1, fc2, fc3 = st.columns(3)
                    fc1.metric(
                        "Rate Sensitivity",
                        f"{fi_ctx.get('rate_sensitivity_score', '—')} / 10",
                    )
                    fc2.metric(
                        "Yield Curve",
                        str(fi_ctx.get("yield_curve_regime", "—")).capitalize(),
                    )
                    fc3.metric(
                        "Cost of Capital",
                        str(fi_ctx.get("cost_of_capital_trend", "—")).capitalize(),
                    )
                    if fi_ctx.get("sector_rotation_read"):
                        st.caption(fi_ctx["sector_rotation_read"])
                    key_risks = fi_ctx.get("key_risks", [])
                    if key_risks:
                        with st.expander("Key Rate / Credit Risks", expanded=False):
                            for r in key_risks:
                                st.markdown(f"• {r}")
                    offsets = fi_ctx.get("offsetting_factors", [])
                    if offsets:
                        with st.expander("Mitigating Factors", expanded=False):
                            for o in offsets:
                                st.markdown(f"• {o}")
                    if fi_ctx.get("methodology_note"):
                        st.caption(f"📝 {fi_ctx['methodology_note']}")

                # ── Baseline Weights ──────────────────────────────────────
                baseline_w = portfolio_out.get("baseline_weights", {})
                if isinstance(baseline_w, dict) and baseline_w:
                    st.markdown("---")
                    st.markdown("#### ⚖️ Portfolio Weights (Baseline — Equal Weight)")
                    w_cols = st.columns(min(len(baseline_w), 6))
                    for i, (ticker, wt) in enumerate(
                        sorted(baseline_w.items(), key=lambda x: -x[1])
                    ):
                        w_cols[i % len(w_cols)].metric(ticker, f"{wt * 100:.1f}%")

                # ── Portfolio Optimisation (ACT-S7-4) ─────────────────────
                opt_results = portfolio_out.get("optimisation_results", {})
                if opt_results:
                    st.markdown("---")
                    st.markdown("#### 🎯 Portfolio Optimisation (Synthetic Returns)")
                    rp = opt_results.get("risk_parity", {})
                    mv = opt_results.get("min_variance", {})
                    ms = opt_results.get("max_sharpe", {})
                    if rp or mv or ms:
                        oc1, oc2, oc3 = st.columns(3)
                        with oc1:
                            st.markdown("**Risk Parity**")
                            if rp:
                                st.metric(
                                    "Expected Vol", f"{rp.get('expected_volatility_pct', 0):.1f}%"
                                )
                                st.metric(
                                    "Expected Ret", f"{rp.get('expected_return_pct', 0):.1f}%"
                                )
                        with oc2:
                            st.markdown("**Min Variance**")
                            if mv:
                                st.metric(
                                    "Expected Vol", f"{mv.get('expected_volatility_pct', 0):.1f}%"
                                )
                                st.metric("Sharpe", f"{mv.get('sharpe_ratio', 0):.2f}")
                        with oc3:
                            st.markdown("**Max Sharpe**")
                            if ms:
                                st.metric("Sharpe", f"{ms.get('sharpe_ratio', 0):.2f}")
                                st.metric(
                                    "Expected Ret", f"{ms.get('expected_return_pct', 0):.1f}%"
                                )

                        # Risk Parity weights detail
                        rp_weights = rp.get("weights", {})
                        if rp_weights:
                            with st.expander("Risk Parity Weights vs Baseline", expanded=False):
                                import pandas as pd  # noqa: PLC0415

                                rows = []
                                for t in sorted(rp_weights, key=lambda x: -rp_weights.get(x, 0)):
                                    bw = (
                                        baseline_w.get(t, 0) * 100
                                        if isinstance(baseline_w, dict)
                                        else 0.0
                                    )
                                    rows.append(
                                        {
                                            "Ticker": t,
                                            "Baseline %": round(bw, 1),
                                            "Risk Parity %": round(rp_weights[t], 1),
                                            "Active %": round(rp_weights[t] - bw, 1),
                                            "Risk Contrib %": round(
                                                rp.get("risk_contributions", {}).get(t, 0), 1
                                            ),
                                        }
                                    )
                                if rows:
                                    st.dataframe(
                                        pd.DataFrame(rows).set_index("Ticker"),
                                        use_container_width=True,
                                    )
                    st.caption(
                        "Optimisation uses synthetic return data — for structural illustration only. Use live price data for production weights."
                    )

                # ── Rebalancing Signals (ACT-S8-2) ────────────────────────
                rebal_data = portfolio_out.get("rebalance_proposal")
                if rebal_data and rebal_data.get("trades"):
                    st.markdown("---")
                    st.markdown("#### ⚖️ Rebalancing Signals (Risk Parity vs Baseline)")
                    rb1, rb2, rb3 = st.columns(3)
                    rb1.metric(
                        "Trades Required", rebal_data.get("trade_count", len(rebal_data["trades"]))
                    )
                    rb2.metric("Turnover", f"{rebal_data.get('total_turnover_pct', 0):.1f}%")
                    rb3.metric(
                        "Est. Avg Impact",
                        f"{rebal_data.get('estimated_total_impact_bps', 0):.1f} bps",
                    )
                    with st.expander("Trade-Level Detail", expanded=False):
                        import pandas as pd  # noqa: PLC0415

                        trade_rows = []
                        for t in rebal_data["trades"]:
                            trade_rows.append(
                                {
                                    "Ticker": t["ticker"],
                                    "Direction": t["direction"].upper(),
                                    "Current %": t["current_weight_pct"],
                                    "Target %": t["target_weight_pct"],
                                    "Delta %": t["delta_weight_pct"],
                                    "Est. Value $": f"{t.get('estimated_value', 0):,.0f}",
                                    "Impact bps": t.get("market_impact_bps", 0),
                                    "Priority": t.get("priority", "normal"),
                                }
                            )
                        if trade_rows:
                            st.dataframe(
                                pd.DataFrame(trade_rows).set_index("Ticker"),
                                use_container_width=True,
                            )
                    if rebal_data.get("summary"):
                        st.caption(rebal_data["summary"])

                # ── Performance Attribution (BHB) (ACT-S7-1) ──────────────
                stage14_out = _stage_out(14)
                attribution = stage14_out.get("attribution", {})
                if attribution:
                    st.markdown("---")
                    st.markdown("#### 📈 Performance Attribution (Brinson-Hood-Beebower)")
                    ac1, ac2, ac3, ac4 = st.columns(4)
                    ac1.metric(
                        "Portfolio Return",
                        f"{attribution.get('total_portfolio_return_pct', 0):.2f}%",
                    )
                    ac2.metric(
                        "Benchmark Return (SPY)",
                        f"{attribution.get('total_benchmark_return_pct', 0):.2f}%",
                    )
                    ac3.metric("Excess Return", f"{attribution.get('excess_return_pct', 0):.2f}%")
                    ac4.metric(
                        "Allocation Effect", f"{attribution.get('allocation_effect_pct', 0):.3f}%"
                    )

                    ac5, ac6, _ = st.columns(3)
                    ac5.metric(
                        "Selection Effect", f"{attribution.get('selection_effect_pct', 0):.3f}%"
                    )
                    ac6.metric(
                        "Interaction Effect", f"{attribution.get('interaction_effect_pct', 0):.3f}%"
                    )

                    sect_alloc = attribution.get("sector_allocation", {})
                    sect_sel = attribution.get("sector_selection", {})
                    if sect_alloc:
                        with st.expander("Sector Attribution Detail", expanded=False):
                            import pandas as pd  # noqa: PLC0415

                            rows = []
                            for sector in sorted(sect_alloc):
                                rows.append(
                                    {
                                        "Sector": sector,
                                        "Allocation Effect %": round(sect_alloc.get(sector, 0), 4),
                                        "Selection Effect %": round(sect_sel.get(sector, 0), 0),
                                    }
                                )
                            if rows:
                                st.dataframe(
                                    pd.DataFrame(rows).set_index("Sector"), use_container_width=True
                                )
                    st.caption(
                        "Attribution uses live price data where available (yfinance), falling back to synthetic returns for tickers that cannot be fetched."
                    )


# ═════════════════════════════════════════════════════════════════════════
# TAB 3 — SAVED RUNS
# ═════════════════════════════════════════════════════════════════════════
with tab_saved:
    st.markdown('<div class="section-title">Saved Runs</div>', unsafe_allow_html=True)
    st.markdown("")

    saved_runs = list_saved_runs()

    if not saved_runs:
        st.markdown(
            """
<div style="text-align:center;padding:48px;color:#8b949e">
  <div style="font-size:2.5rem;margin-bottom:10px">🗂️</div>
  <div style="font-weight:600;color:#c9d1d9;margin-bottom:6px">No saved runs yet</div>
  <div style="font-size:0.82rem">
    Reports are automatically saved when a pipeline run completes.
    They persist across server restarts.
  </div>
</div>
""",
            unsafe_allow_html=True,
        )
        st.caption(f"Storage → `{REPORTS_DIR}`")
    else:
        st.caption(f"{len(saved_runs)} saved run(s)  ·  `{REPORTS_DIR}`")
        st.markdown("")

        for run in saved_runs:
            rid = run.get("run_id", "?")
            ticks = run.get("tickers", [])
            tick_s = ", ".join(ticks[:6]) + ("…" if len(ticks) > 6 else "")
            dt_raw = run.get("completed_at", "")
            try:
                dt_fmt = datetime.fromisoformat(dt_raw).strftime("%d %b %Y  %H:%M UTC")
            except Exception:
                dt_fmt = dt_raw or "?"
            wc = run.get("word_count", 0)
            ok = "✅" if run.get("success") else "⚠️"
            model = run.get("model", "?")

            with st.container():
                rc1, rc2, rc3, rc4 = st.columns([6, 2, 2, 2])
                with rc1:
                    st.markdown(
                        f"""
<div class="card" style="padding:10px 16px;margin-bottom:0">
  <div style="display:flex;align-items:center;gap:10px">
    <span style="font-size:1.2rem">{ok}</span>
    <div>
      <div style="font-family:monospace;color:#58a6ff;font-size:0.90rem;font-weight:600">{rid}</div>
      <div style="font-size:0.72rem;color:#8b949e;margin-top:2px">
        {dt_fmt} &nbsp;·&nbsp; {tick_s} &nbsp;·&nbsp; {wc:,} words &nbsp;·&nbsp; {model[:26]}
      </div>
    </div>
  </div>
</div>
""",
                        unsafe_allow_html=True,
                    )
                with rc2:
                    if st.button(
                        "📂  Load",
                        key=f"load_{rid}",
                        use_container_width=True,
                        help="Open in Report tab",
                    ):
                        data = load_run(rid)
                        if data:
                            st.session_state.loaded_run = data
                            st.session_state.run_result = None
                            st.rerun()
                        else:
                            st.error("Could not read file.")
                with rc3:
                    md_path = run.get("md_path")
                    if md_path and Path(md_path).exists():
                        md_bytes = Path(md_path).read_bytes()
                        st.download_button(
                            "⬇️  .md",
                            data=md_bytes,
                            file_name=f"{rid}.md",
                            mime="text/markdown",
                            key=f"dl_{rid}",
                            use_container_width=True,
                        )
                    else:
                        st.button(
                            "⬇️  .md", disabled=True, key=f"dl_{rid}", use_container_width=True
                        )
                with rc4:
                    if st.button("🗑️  Delete", key=f"del_{rid}", use_container_width=True):
                        delete_run(rid)
                        loaded_now = st.session_state.get("loaded_run")
                        if isinstance(loaded_now, dict) and loaded_now.get("run_id") == rid:
                            st.session_state.loaded_run = None
                        st.rerun()

                st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════
# TAB 4 — ABOUT
# ═════════════════════════════════════════════════════════════════════════
with tab_about:
    st.markdown(
        """
<div class="card">
  <h3 style="margin:0 0 6px;color:#58a6ff">Institutional Research Platform v8</h3>
  <p style="margin:0;font-size:0.86rem;color:#8b949e;line-height:1.6">
    Emulates JPMorgan Asset Management's institutional research workflow.
    15-stage multi-agent pipeline with client profiling, live market data
    (FMP + Finnhub + yfinance), and tailored portfolio construction for
    high-net-worth individuals.
  </p>
</div>
""",
        unsafe_allow_html=True,
    )

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### Architecture")
        st.markdown("""
| Layer | Components |
|---|---|
| **Client Onboarding** | Risk profiling, investment objectives, mandate constraints, ESG screening |
| **Quantitative Data** | FMP (primary) + Finnhub (secondary) + yfinance (fallback), cross-validation |
| **Qualitative Intelligence** | 8-source engine: news, press releases, earnings transcripts, SEC filings, analyst actions, insider trading, forward estimates, sentiment |
| **Deterministic** | Data ingestion, reconciliation, QA, DCF engine, risk math, scenario engine |
| **LLM Agents** | Evidence librarian, sector analysts (Six-Box), valuation, red team, reviewer, PM, macro |
| **Qual-Quant Correlation** | Automated divergence/convergence detection between qualitative signals and quantitative data |
| **Governance** | Prompt versioning, golden tests, self-audit, human override log |
""")
        st.markdown("#### Supported Providers")
        st.markdown("""
| Provider | Models |
|---|---|
| **Anthropic** | Opus 4.6, Sonnet 4.6, Haiku 4.5 |
| **OpenAI** | GPT-5.4, GPT-5.4 mini, GPT-5.4 nano |
| **Google** | Gemini 3.1 Pro, 2.5 Pro, 2.5 Flash, Flash-Lite |

| Data Source | Quantitative | Qualitative |
|---|---|---|
| **FMP** | Quotes, financials, key metrics, price targets, income/cashflow | News, press releases, earnings transcripts, SEC filings, analyst actions, insider trading, estimates, social sentiment |
| **Finnhub** | Quotes, analyst recs, fundamental metrics, cross-validation | Company news (14-day window), insider sentiment (MSPR), news sentiment scores |
| **yfinance** | Fallback prices and fundamentals | — |
""")

    with col_b:
        st.markdown("#### Pipeline Stages")
        for num, name in STAGES:
            tag = "🤖" if num in {5, 6, 7, 8, 9, 10, 11, 12} else "⚙️"
            st.markdown(f"`{tag} S{num:02d}` {name}")

        st.markdown("#### Investment Themes")
        for key, info in INVESTMENT_THEMES.items():
            if key != "custom":
                st.markdown(f"**{info['name']}**: {info['description']}")

        st.markdown("#### Qualitative Intelligence Sources")
        st.markdown("""
1. **Company News** — FMP + Finnhub (deduplicated, 14-day window)
2. **Press Releases** — Official corporate communications (FMP)
3. **Earnings Transcripts** — Management commentary & forward guidance (FMP)
4. **SEC Filings** — 8-K, 10-K, 10-Q material events (FMP)
5. **Analyst Actions** — Upgrades/downgrades with firm attribution (FMP)
6. **Insider Trading** — Executive buy/sell patterns & net sentiment (FMP)
7. **Forward Estimates** — Consensus revenue/EPS with estimate spread (FMP)
8. **Sentiment Signals** — Social media (StockTwits/Reddit) + news sentiment (FMP + Finnhub)
""")

    st.divider()
    st.caption(
        "> **Disclaimer**: This platform uses live market data from FMP, Finnhub, and Yahoo Finance APIs. "
        "Qualitative intelligence sourced from 8 channels per ticker. "
        "All [HOUSE VIEW] content reflects analytical opinion. Not investment advice. "
        "AI-generated research for analytical purposes only."
    )
    st.caption(
        f"Pipeline v8.1 · Deep Qualitative Intelligence · Python 3.12 · Streamlit · "
        f"Reports stored in `{REPORTS_DIR.relative_to(ROOT)}/`"
    )
