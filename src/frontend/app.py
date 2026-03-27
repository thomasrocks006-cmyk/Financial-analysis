"""AI Infrastructure Research Pipeline — Streamlit Frontend v8.

Run with:
    cd /workspaces/Financial-analysis
    .venv/bin/streamlit run src/frontend/app.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

logger = logging.getLogger(__name__)

# ── Path setup ────────────────────────────────────────────────────────────
ROOT = Path(__file__).parents[2]
SRC  = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from frontend.mock_data import FULL_UNIVERSE, MARKET_SNAPSHOTS, DEMO_DATE
from frontend.pipeline_runner import STAGES, PipelineRunner, RunResult
from frontend.cost_estimator import estimate_run_cost, calculate_actual_cost, format_cost
from frontend.storage import save_run, list_saved_runs, load_run, delete_run, REPORTS_DIR


# ── Page config ───────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Infra Research Pipeline",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Professional dark theme CSS ───────────────────────────────────────────
st.markdown("""
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

/* ── Expander styling ── */
[data-testid="stExpander"] { background: #161b22 !important; border: 1px solid #21262d !important;
                              border-radius: 8px !important; }
[data-testid="stExpander"] summary { color: #c9d1d9 !important; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────
# Helper render functions
# ─────────────────────────────────────────────────────────────────────────
def _render_stage_card(placeholder, num: int, name: str, status: str, outputs: dict) -> None:
    """Render a single stage row card into a Streamlit placeholder."""
    icon_map  = {"pending": "○", "running": "◌", "done": "●", "failed": "✕"}
    color_map = {"done": "#3fb950", "running": "#f0883e", "failed": "#f85149", "pending": "#30363d"}
    icon  = icon_map.get(status, "○")
    color = color_map.get(status, "#30363d")

    # Short output snippet for done stages
    out = outputs.get(num)
    snippet_html = ""
    if status == "done" and out:
        raw = out if isinstance(out, str) else json.dumps(out, default=str)
        snippet = raw[:90].replace("\n", " ").replace("<", "&lt;").replace(">", "&gt;").strip()
        if len(raw) > 90:
            snippet += "…"
        snippet_html = f'<div style="font-size:0.68rem;color:#8b949e;margin-top:2px">{snippet}</div>'

    placeholder.markdown(f"""
<div class="stage-row {status}">
  <span class="stage-icon" style="color:{color}">{icon}</span>
  <div class="stage-name">
    <b>S{num}</b> {name}
    {snippet_html}
  </div>
</div>
""", unsafe_allow_html=True)


def _render_stream(placeholder, log: list) -> None:
    """Render the live output stream panel."""
    if not log:
        placeholder.markdown("""
<div class="live-stream" style="color:#30363d;font-style:italic">
Waiting for pipeline to start…
</div>
""", unsafe_allow_html=True)
        return

    lines = []
    for stage_num, stage_name, text in log[-8:]:
        safe = str(text)[:700].strip().replace("<", "&lt;").replace(">", "&gt;")
        lines.append(
            f'<div style="color:#58a6ff;font-size:0.70rem;margin:8px 0 2px">'
            f'━━ S{stage_num}: {stage_name} ━━━━━━━━━━━━</div>'
            f'<div style="color:#c9d1d9;margin-bottom:6px">{safe}{"…" if len(str(text)) > 700 else ""}</div>'
        )

    html = '<div class="live-stream">' + "".join(lines) + "</div>"
    placeholder.markdown(html, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────
# Session state bootstrap
# ─────────────────────────────────────────────────────────────────────────
def _init_state():
    defaults: dict = {
        "run_result":     None,
        "stage_statuses": {i: "pending" for i, _ in STAGES},
        "stage_outputs":  {},
        "running":        False,
        "current_stage":  -1,
        "live_log":       [],
        "loaded_run":     None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ─────────────────────────────────────────────────────────────────────────
# Model constants
# ─────────────────────────────────────────────────────────────────────────
ALL_MODELS = [
    ("claude-opus-4-6",         "Opus 4.6",         "$15/$75"),
    ("claude-sonnet-4-6",       "Sonnet 4.6",       "$3/$15"),
    ("claude-haiku-4-5",        "Haiku 4.5",        "$0.80/$4"),
    ("gpt-5.4",                 "GPT-5.4",          "$2.50/$10"),
    ("gpt-5.4-mini",            "GPT-5.4 mini",     "$0.40/$1.60"),
    ("gpt-5.4-nano",            "GPT-5.4 nano",     "$0.15/$0.60"),
    ("gemini-3.1-pro-preview",  "Gemini 3.1 Pro",   "$2/$8"),
    ("gemini-2.5-pro",          "Gemini 2.5 Pro",   "$1.25/$10"),
    ("gemini-2.5-flash",        "Gemini 2.5 Flash", "$0.30/$2.50"),
    ("gemini-2.5-flash-lite",   "Flash-Lite",       "$0.10/$0.40"),
]
ALL_IDS    = [m[0] for m in ALL_MODELS]
ALL_LABELS = [f"{m[1]}  ·  {m[2]}" for m in ALL_MODELS]

STAGE_DEFAULTS = {
    5: "claude-sonnet-4-6",  6: "claude-opus-4-6",  7: "claude-sonnet-4-6",
    8: "gemini-2.5-pro",     9: "gemini-2.5-flash", 10: "claude-opus-4-6",
    11: "claude-sonnet-4-6", 12: "gpt-5.4",
}
LLM_STAGES = [
    (5,  "Evidence Librarian"), (6,  "Sector Analysis ★"),
    (7,  "Valuation"),          (8,  "Macro & Political"),
    (9,  "Quant Risk"),         (10, "Red Team ★"),
    (11, "Associate Review"),   (12, "Portfolio"),
]

def _prov(m: str) -> str:
    if m.startswith("claude"):                   return "anthropic"
    if m.startswith("gpt") or m.startswith("o"): return "openai"
    return "gemini"


# ─────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
<div style="padding:14px 0 8px">
  <div style="font-size:1.05rem;font-weight:700;color:#e6edf3;letter-spacing:-0.02em">
    📊 AI Infra Research
  </div>
  <div style="font-size:0.72rem;color:#8b949e;margin-top:2px">
    Institutional Pipeline · v8.0
  </div>
</div>
""", unsafe_allow_html=True)
    st.divider()

    # ── API Keys ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">API Keys</div>', unsafe_allow_html=True)
    anthropic_key = st.text_input(
        "Anthropic", type="password", key="key_ant", placeholder="sk-ant-…",
        label_visibility="collapsed"
    )
    openai_key = st.text_input(
        "OpenAI", type="password", key="key_oai", placeholder="sk-… (OpenAI)",
        label_visibility="collapsed"
    )
    gemini_key = st.text_input(
        "Google", type="password", key="key_gem", placeholder="AIza… (Gemini)",
        label_visibility="collapsed"
    )

    provider_keys: dict[str, str] = {k: v for k, v in {
        "anthropic": anthropic_key, "openai": openai_key, "gemini": gemini_key,
    }.items() if v}
    any_key = bool(provider_keys)

    if any_key:
        badges = []
        if anthropic_key: badges.append("🟢 Anthropic")
        if openai_key:    badges.append("🟢 OpenAI")
        if gemini_key:    badges.append("🟢 Google")
        st.caption("  ".join(badges))

    st.divider()

    # ── Model ─────────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Model & Temperature</div>', unsafe_allow_html=True)
    temperature = st.slider(
        "Temperature", 0.0, 1.0, 0.3, 0.05, key="temp_slider",
        label_visibility="collapsed",
        help="Low (0.2–0.4) = deterministic research; high = more creative",
    )
    st.caption(f"Temperature: {temperature:.2f}")

    use_same = st.checkbox("Single model for all stages", value=True, key="use_same")
    if use_same:
        def_idx = ALL_IDS.index("claude-sonnet-4-6")
        g_idx = st.selectbox(
            "Model", range(len(ALL_MODELS)),
            format_func=lambda i: ALL_LABELS[i],
            index=def_idx, key="global_model",
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
                    f"S{sn}: {sl}", range(len(ALL_MODELS)),
                    format_func=lambda i: ALL_LABELS[i],
                    index=def_idx, key=f"sm_{sn}",
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

    # ── Universe ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Universe</div>', unsafe_allow_html=True)
    mode = st.radio(
        "Mode", ["Quick — 3 stocks", "Full — 12 stocks", "Custom"],
        index=0, key="universe_mode", label_visibility="collapsed",
    )

    if mode == "Quick — 3 stocks":
        selected_tickers: list[str] = ["NVDA", "CEG", "PWR"]
    elif mode == "Full — 12 stocks":
        selected_tickers = list(MARKET_SNAPSHOTS.keys())
    else:
        all_tickers = list(MARKET_SNAPSHOTS.keys())
        selected_tickers = st.multiselect(
            "Tickers", all_tickers, default=["NVDA", "AVGO", "CEG", "PWR"],
            format_func=lambda t: f"{t} — {MARKET_SNAPSHOTS[t].get('company_name', t)}",
            label_visibility="collapsed",
        )

    if selected_tickers:
        chip_html = ""
        for t in selected_tickers:
            sub = MARKET_SNAPSHOTS.get(t, {}).get("subtheme", "")
            css = {"compute": "compute", "power": "power", "infrastructure": "infra"}.get(sub, "")
            chip_html += f'<span class="ticker-chip {css}">{t}</span>'
        st.markdown(chip_html, unsafe_allow_html=True)

    st.divider()

    # ── Cost Estimate ─────────────────────────────────────────────────────
    st.markdown('<div class="section-title">Run Cost Estimate</div>', unsafe_allow_html=True)
    if selected_tickers and stage_models:
        try:
            est = estimate_run_cost(selected_tickers, stage_models, model_choice)
            st.markdown(f"""
<div class="cost-badge">
  💰 <span class="amt">{format_cost(est.total_cost_usd)}</span>
  &nbsp;·&nbsp; {format_cost(est.low_usd)} – {format_cost(est.high_usd)}
</div>
<div style="font-size:0.72rem;color:#8b949e;margin-top:6px">
  {len(selected_tickers)} tickers · {len(LLM_STAGES)} LLM stages
</div>
""", unsafe_allow_html=True)
        except Exception:
            st.caption("Cost estimate unavailable")

    st.divider()
    st.caption(f"📅 {DEMO_DATE} · Demo mode")
    st.caption(f"💾 `reports/` — survives restarts")


# ─────────────────────────────────────────────────────────────────────────
# Page header
# ─────────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="padding:8px 0 18px">
  <div style="font-size:1.6rem;font-weight:800;color:#e6edf3;letter-spacing:-0.03em">
    AI Infrastructure Research Pipeline
  </div>
  <div style="font-size:0.82rem;color:#8b949e;margin-top:4px">
    Institutional-grade equity research · 15-stage multi-agent pipeline · v8.0
  </div>
</div>
""", unsafe_allow_html=True)

tab_pipeline, tab_report, tab_saved, tab_about = st.tabs([
    "⚡ Pipeline", "📄 Report", "🗂️ Saved Runs", "ℹ️ About"
])


# ═════════════════════════════════════════════════════════════════════════
# TAB 1 — PIPELINE
# ═════════════════════════════════════════════════════════════════════════
with tab_pipeline:

    # ── Controls ──────────────────────────────────────────────────────────
    cc1, cc2, cc3 = st.columns([3, 1, 4])
    with cc1:
        run_disabled = (
            st.session_state.running
            or not any_key
            or not selected_tickers
        )
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
            st.session_state.run_result      = None
            st.session_state.loaded_run      = None
            st.session_state.stage_statuses  = {i: "pending" for i, _ in STAGES}
            st.session_state.stage_outputs   = {}
            st.session_state.running         = False
            st.session_state.current_stage   = -1
            st.session_state.live_log        = []
            st.rerun()

    if not any_key:
        st.info("👈  Enter at least one API key in the sidebar to enable pipeline runs.")

    # ── Two-column layout ─────────────────────────────────────────────────
    col_stages, col_live = st.columns([5, 7])

    with col_stages:
        st.markdown('<div class="section-title">Stage Tracker</div>', unsafe_allow_html=True)
        stage_placeholders: dict[int, object] = {}
        for num, name in STAGES:
            ph = st.empty()
            stage_placeholders[num] = ph
            _render_stage_card(
                ph, num, name,
                st.session_state.stage_statuses.get(num, "pending"),
                st.session_state.stage_outputs,
            )

    with col_live:
        st.markdown('<div class="section-title">Live Output Stream</div>', unsafe_allow_html=True)
        stream_ph = st.empty()
        _render_stream(stream_ph, st.session_state.live_log)

    # ── Progress / status area ────────────────────────────────────────────
    progress_ph = st.empty()
    status_ph   = st.empty()

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

    # ─────────────────────────────────────────────────────────────────────
    # Run pipeline
    # ─────────────────────────────────────────────────────────────────────
    if run_btn and any_key and selected_tickers:
        # Reset state
        st.session_state.running        = True
        st.session_state.stage_statuses = {i: "pending" for i, _ in STAGES}
        st.session_state.stage_outputs  = {}
        st.session_state.run_result     = None
        st.session_state.live_log       = []

        progress_bar = progress_ph.progress(0, text="Initialising pipeline…")

        runner = PipelineRunner(
            provider_keys=provider_keys,
            model=model_choice,
            tickers=selected_tickers,
            temperature=temperature,
            stage_models=stage_models,
        )

        total_stages = len(STAGES)
        done_count   = [0]

        def _progress_cb(stage_num: int, stage_name: str, status: str, output) -> None:
            st.session_state.stage_statuses[stage_num] = status
            if output is not None:
                st.session_state.stage_outputs[stage_num] = output

            # Refresh stage card
            ph = stage_placeholders.get(stage_num)
            if ph:
                _render_stage_card(ph, stage_num, stage_name, status,
                                   st.session_state.stage_outputs)

            # Append to live log when stage finishes
            if status == "done":
                text = output if isinstance(output, str) else (
                    json.dumps(output, default=str) if output else ""
                )
                if text:
                    st.session_state.live_log.append((stage_num, stage_name, text))
                done_count[0] += 1
                pct = min(int(done_count[0] / total_stages * 95), 95)
                progress_bar.progress(pct, text=f"Stage {stage_num}: {stage_name} ✓")

            _render_stream(stream_ph, st.session_state.live_log)

        async def _run_pipeline() -> RunResult:
            return await runner.run(progress_callback=_progress_cb)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        run_result: RunResult | None = None
        try:
            run_result = loop.run_until_complete(_run_pipeline())
        except Exception as exc:
            st.session_state.running = False
            status_ph.error(f"❌ Pipeline error: {exc}")
            logger.exception("Pipeline crashed: %s", exc)
        finally:
            loop.close()

        if run_result is None:
            st.rerun()
            st.stop()

        # Sync authoritative stage statuses from RunResult
        for sr in run_result.stages:
            st.session_state.stage_statuses[sr.stage_num] = sr.status
            if sr.raw_text:
                st.session_state.stage_outputs[sr.stage_num] = sr.raw_text
            elif sr.output:
                st.session_state.stage_outputs[sr.stage_num] = sr.output

        st.session_state.run_result   = run_result
        st.session_state.current_stage = 14
        st.session_state.running       = False

        # Persist to disk
        try:
            save_run(run_result)
        except Exception as exc:
            logger.warning("Could not save run to disk: %s", exc)

        progress_ph.progress(100, text="Pipeline complete!")

        if run_result.token_log:
            c = calculate_actual_cost(run_result.token_log)
            status_ph.success(
                f"✅ {run_result.run_id} complete · "
                f"Cost: **{format_cost(c.total_cost_usd)}** · "
                f"{c.total_input_tokens + c.total_output_tokens:,} tokens · Auto-saved"
            )
        else:
            status_ph.success(f"✅ {run_result.run_id} complete · Auto-saved to disk")

        st.rerun()


# ═════════════════════════════════════════════════════════════════════════
# TAB 2 — REPORT
# ═════════════════════════════════════════════════════════════════════════
with tab_report:

    active_result: RunResult | None = st.session_state.get("run_result")
    loaded: dict | None             = st.session_state.get("loaded_run")

    if active_result is None and loaded is None:
        # ── Empty state ───────────────────────────────────────────────────
        st.markdown("""
<div style="text-align:center;padding:60px 0;color:#8b949e">
  <div style="font-size:3rem;margin-bottom:14px">📄</div>
  <div style="font-size:1rem;font-weight:600;color:#c9d1d9;margin-bottom:8px">
    No report yet
  </div>
  <div style="font-size:0.84rem">
    Run the pipeline from the ⚡ Pipeline tab — or load a saved run from 🗂️ Saved Runs
  </div>
</div>
""", unsafe_allow_html=True)

        # Universe preview
        if selected_tickers:
            st.markdown("---")
            st.markdown('<div class="section-title">Universe Preview</div>', unsafe_allow_html=True)
            cols = st.columns(min(len(selected_tickers), 4))
            for i, ticker in enumerate(selected_tickers):
                snap   = MARKET_SNAPSHOTS.get(ticker, {})
                price  = snap.get("price", 0)
                target = snap.get("consensus_target_12m", price)
                upside = (target - price) / price * 100 if price else 0
                color  = "#3fb950" if upside >= 0 else "#f85149"
                sign   = "+" if upside >= 0 else ""
                with cols[i % 4]:
                    st.markdown(f"""
<div class="uni-card">
  <div class="symbol">{ticker}</div>
  <div class="name">{snap.get('company_name', '')[:22]}</div>
  <div class="price">${price:.2f}</div>
  <div style="font-size:0.72rem;color:{color};margin-top:2px">{sign}{upside:.1f}% vs cons.</div>
  <div style="font-size:0.70rem;color:#8b949e;margin-top:2px">P/E {snap.get('forward_pe',0):.1f}×</div>
</div>
""", unsafe_allow_html=True)
    else:
        # ── Display report ────────────────────────────────────────────────
        if loaded:
            run_id    = loaded.get("run_id", "?")
            tickers   = loaded.get("tickers", [])
            model     = loaded.get("model", "?")
            report_md = loaded.get("final_report_md", "")
            stages_raw = loaded.get("stages", [])
            token_log_src: list = []
        else:
            run_id    = active_result.run_id
            tickers   = active_result.tickers
            model     = active_result.model
            report_md = active_result.final_report_md
            stages_raw = [
                {"stage_num": s.stage_num, "stage_name": s.stage_name,
                 "status": s.status, "elapsed_secs": s.elapsed_secs,
                 "error": s.error}
                for s in active_result.stages
            ]
            token_log_src = active_result.token_log

        word_count = len(report_md.split())
        pages_est  = max(1, word_count // 250)
        stages_ok  = sum(1 for s in stages_raw if s.get("status") == "done")

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
        dc1, dc2, _dc3 = st.columns([2, 2, 5])
        with dc1:
            st.download_button(
                "⬇️  Download .md",
                data=report_md,
                file_name=f"AI_Infra_{run_id}_{DEMO_DATE}.md",
                mime="text/markdown",
                type="primary",
                use_container_width=True,
            )
        with dc2:
            json_payload = json.dumps(
                loaded if loaded else {
                    "run_id": run_id, "tickers": tickers,
                    "model": model, "final_report_md": report_md,
                    "stages": stages_raw,
                },
                indent=2, default=str,
            )
            st.download_button(
                "⬇️  Download .json",
                data=json_payload,
                file_name=f"AI_Infra_{run_id}_{DEMO_DATE}.json",
                mime="application/json",
                use_container_width=True,
            )

        st.markdown("---")

        # Report body
        st.markdown('<div class="report-wrap">', unsafe_allow_html=True)
        st.markdown(report_md)
        st.markdown("</div>", unsafe_allow_html=True)

        # Stage timing expander
        if stages_raw:
            with st.expander("⏱️  Stage Timing & Errors", expanded=False):
                cols_t = st.columns(2)
                for i, s in enumerate(stages_raw):
                    sn    = s.get("stage_num", "?")
                    sname = s.get("stage_name", "?")
                    ss    = s.get("status", "?")
                    el    = s.get("elapsed_secs", 0) or 0
                    err   = s.get("error") or ""
                    icon  = "✅" if ss == "done" else "❌" if ss == "failed" else "⬜"
                    line  = f"{icon} **S{sn}: {sname}** — {el:.1f}s"
                    if err:
                        line += f" · ⚠️ `{err[:60]}`"
                    cols_t[i % 2].markdown(line)

        # Token/cost breakdown expander
        if token_log_src:
            with st.expander("💰  Token & Cost Breakdown", expanded=False):
                c = calculate_actual_cost(token_log_src)
                for entry in c.stage_costs:
                    sn = entry.get("stage_num", "?")
                    m  = entry.get("model", "?")
                    it = entry.get("input_tokens", 0)
                    ot = entry.get("output_tokens", 0)
                    cu = entry.get("cost_usd", 0.0)
                    st.caption(
                        f"S{sn} · `{m}` · {it:,}↑ {ot:,}↓ · **{format_cost(cu)}**"
                    )
                st.markdown(
                    f"**Total: {format_cost(c.total_cost_usd)}** "
                    f"({c.total_input_tokens + c.total_output_tokens:,} tokens)"
                )


# ═════════════════════════════════════════════════════════════════════════
# TAB 3 — SAVED RUNS
# ═════════════════════════════════════════════════════════════════════════
with tab_saved:
    st.markdown('<div class="section-title">Saved Runs</div>', unsafe_allow_html=True)
    st.markdown("")

    saved_runs = list_saved_runs()

    if not saved_runs:
        st.markdown("""
<div style="text-align:center;padding:48px;color:#8b949e">
  <div style="font-size:2.5rem;margin-bottom:10px">🗂️</div>
  <div style="font-weight:600;color:#c9d1d9;margin-bottom:6px">No saved runs yet</div>
  <div style="font-size:0.82rem">
    Reports are automatically saved when a pipeline run completes.
    They persist across server restarts.
  </div>
</div>
""", unsafe_allow_html=True)
        st.caption(f"Storage → `{REPORTS_DIR}`")
    else:
        st.caption(f"{len(saved_runs)} saved run(s)  ·  `{REPORTS_DIR}`")
        st.markdown("")

        for run in saved_runs:
            rid    = run.get("run_id", "?")
            ticks  = run.get("tickers", [])
            tick_s = ", ".join(ticks[:6]) + ("…" if len(ticks) > 6 else "")
            dt_raw = run.get("completed_at", "")
            try:
                dt_fmt = datetime.fromisoformat(dt_raw).strftime("%d %b %Y  %H:%M UTC")
            except Exception:
                dt_fmt = dt_raw or "?"
            wc    = run.get("word_count", 0)
            ok    = "✅" if run.get("success") else "⚠️"
            model = run.get("model", "?")

            with st.container():
                rc1, rc2, rc3, rc4 = st.columns([6, 2, 2, 2])
                with rc1:
                    st.markdown(f"""
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
""", unsafe_allow_html=True)
                with rc2:
                    if st.button("📂  Load", key=f"load_{rid}", use_container_width=True,
                                 help="Open in Report tab"):
                        data = load_run(rid)
                        if data:
                            st.session_state.loaded_run  = data
                            st.session_state.run_result  = None
                            st.rerun()
                        else:
                            st.error("Could not read file.")
                with rc3:
                    md_path = run.get("md_path")
                    if md_path and Path(md_path).exists():
                        md_bytes = Path(md_path).read_bytes()
                        st.download_button(
                            "⬇️  .md", data=md_bytes,
                            file_name=f"{rid}.md", mime="text/markdown",
                            key=f"dl_{rid}", use_container_width=True,
                        )
                    else:
                        st.button("⬇️  .md", disabled=True, key=f"dl_{rid}",
                                  use_container_width=True)
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
    st.markdown("""
<div class="card">
  <h3 style="margin:0 0 6px;color:#58a6ff">AI Infrastructure Research Pipeline v8</h3>
  <p style="margin:0;font-size:0.86rem;color:#8b949e;line-height:1.6">
    Institutional-grade equity research platform. 15-stage multi-agent pipeline covering
    AI infrastructure equities across compute, power, and infrastructure sub-themes.
    Combines deterministic financial services with specialised LLM reasoning agents and
    a full governance layer.
  </p>
</div>
""", unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("#### Architecture")
        st.markdown("""
| Layer | Components |
|---|---|
| **Deterministic** | Data ingestion, reconciliation, QA, DCF engine, risk math, scenario engine, run registry |
| **LLM Agents** | Evidence librarian, 3× sector analysts, valuation, red team, associate reviewer, PM, macro |
| **Governance** | Prompt versioning, golden tests, self-audit, human override log |
""")
        st.markdown("#### Supported Providers")
        st.markdown("""
| Provider | Models |
|---|---|
| **Anthropic** | Opus 4.6, Sonnet 4.6, Haiku 4.5 |
| **OpenAI** | GPT-5.4, GPT-5.4 mini, GPT-5.4 nano |
| **Google** | Gemini 3.1 Pro, 2.5 Pro, 2.5 Flash, Flash-Lite |
""")

    with col_b:
        st.markdown("#### Pipeline Stages")
        for num, name in STAGES:
            tag = "🤖" if num in {5, 6, 7, 8, 9, 10, 11, 12} else "⚙️"
            st.markdown(f"`{tag} S{num:02d}` {name}")

    st.divider()
    st.markdown("#### Coverage Universe")
    st.markdown("""
| Sub-theme | Tickers | Focus |
|---|---|---|
| Compute & Silicon | NVDA · AVGO · TSM | GPU monopoly, custom ASICs, foundry |
| Power & Energy | CEG · VST · GEV | Nuclear, merchant gen, grid services |
| Infrastructure | PWR · ETN · APH · FIX · FCX · NXT | Grid buildout, cooling, copper, solar |
""")
    st.divider()
    st.caption(
        "> **Disclaimer**: Demo mode uses illustrative data only. "
        "All [HOUSE VIEW] content reflects analytical opinion. Not investment advice."
    )
    st.caption(
        f"Pipeline v8.0 · Python 3.12 · Streamlit · "
        f"Reports stored in `{REPORTS_DIR.relative_to(ROOT)}/`"
    )
