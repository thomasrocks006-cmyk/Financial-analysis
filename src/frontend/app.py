"""AI Infrastructure Research Pipeline — Streamlit Frontend.

Run with:
    cd /workspaces/Financial-analysis
    .venv/bin/streamlit run src/frontend/app.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

import streamlit as st

# ── Path setup so local packages resolve ─────────────────────────────────
ROOT = Path(__file__).parents[2]
SRC  = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from frontend.mock_data import (
    FULL_UNIVERSE, MARKET_SNAPSHOTS, DEMO_DATE, QUICK_DEMO_UNIVERSE
)
from frontend.pipeline_runner import STAGES, PipelineRunner, RunResult


# ── Page config ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Infra Research Pipeline",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────
st.markdown("""
<style>
.stage-card {
    border-left: 4px solid #ddd;
    padding: 8px 16px;
    margin: 4px 0;
    border-radius: 4px;
    background: #fafafa;
}
.stage-done   { border-left-color: #28a745; background: #f0fff4; }
.stage-running{ border-left-color: #ffc107; background: #fffdf0; }
.stage-failed { border-left-color: #dc3545; background: #fff5f5; }
.stage-pending{ border-left-color: #9da8b3; }
.metric-box {
    background: #f8f9fa;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    padding: 12px;
    text-align: center;
}
.report-container {
    background: white;
    padding: 2rem;
    border: 1px solid #dee2e6;
    border-radius: 8px;
    max-height: 80vh;
    overflow-y: auto;
}
</style>
""", unsafe_allow_html=True)


# ── Session state initialisation ─────────────────────────────────────────
def init_state():
    defaults = {
        "run_result": None,
        "stage_statuses": {i: "pending" for i, _ in STAGES},
        "stage_outputs": {},
        "running": False,
        "current_stage": -1,
        "logs": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()


# ── Sidebar ───────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📊 AI Infra Research Pipeline\n**v8.0**")
    st.divider()

    # API Configuration
    st.markdown("### 🔑 API Configuration")
    api_key = st.text_input(
        "Anthropic API Key",
        type="password",
        placeholder="sk-ant-...",
        help="Your Anthropic API key. Used only for this session.",
    )

    model_choice = st.selectbox(
        "Model",
        ["claude-opus-4-5", "claude-sonnet-4-5", "claude-haiku-4-5"],
        index=0,
        help="claude-opus-4-5 gives richest output. claude-haiku-4-5 is fastest.",
    )

    temperature = st.slider("Temperature", 0.0, 1.0, 0.3, 0.05,
                             help="Lower = more deterministic. 0.2–0.4 recommended.")

    st.divider()

    # Universe selection
    st.markdown("### 🌐 Universe")
    mode = st.radio(
        "Mode",
        ["Quick Demo (3 stocks)", "Full Universe (12 stocks)", "Custom"],
        index=0,
    )

    if mode == "Quick Demo (3 stocks)":
        selected_tickers = ["NVDA", "CEG", "PWR"]
    elif mode == "Full Universe (12 stocks)":
        selected_tickers = list(MARKET_SNAPSHOTS.keys())
    else:
        all_tickers = list(MARKET_SNAPSHOTS.keys())
        selected_tickers = st.multiselect(
            "Select tickers",
            all_tickers,
            default=["NVDA", "AVGO", "CEG", "PWR"],
            format_func=lambda t: f"{t} — {MARKET_SNAPSHOTS[t]['company_name']}",
        )

    if selected_tickers:
        compute = [t for t in selected_tickers if MARKET_SNAPSHOTS.get(t, {}).get("subtheme") == "compute"]
        power   = [t for t in selected_tickers if MARKET_SNAPSHOTS.get(t, {}).get("subtheme") == "power_energy"]
        infra   = [t for t in selected_tickers if MARKET_SNAPSHOTS.get(t, {}).get("subtheme") == "infrastructure"]
        st.caption(f"🖥️ Compute: {', '.join(compute) or 'none'}")
        st.caption(f"⚡ Power: {', '.join(power) or 'none'}")
        st.caption(f"🏗️ Infra: {', '.join(infra) or 'none'}")

    st.divider()
    st.caption(f"📅 Report date: {DEMO_DATE}")
    st.caption("⚠️ Demo mode: illustrative data only")


# ── Main layout ───────────────────────────────────────────────────────────
st.title("📊 AI Infrastructure Research Pipeline")
st.caption(f"Institutional-grade equity research platform · v8.0 · {DEMO_DATE}")

tab_pipeline, tab_report, tab_about = st.tabs(["🔄 Pipeline", "📄 Final Report", "ℹ️ About"])


# ═════════════════════════════════════════════════════════════════════════
# TAB 1: Pipeline
# ═════════════════════════════════════════════════════════════════════════
with tab_pipeline:

    col_run, col_reset = st.columns([3, 1])
    with col_run:
        run_disabled = (
            st.session_state.running
            or not api_key
            or not selected_tickers
        )
        run_btn = st.button(
            "▶ Run Full Pipeline",
            disabled=run_disabled,
            type="primary",
            use_container_width=True,
            help="Requires Anthropic API key and at least one ticker selected.",
        )
    with col_reset:
        if st.button("↺ Reset", use_container_width=True):
            st.session_state.run_result = None
            st.session_state.stage_statuses = {i: "pending" for i, _ in STAGES}
            st.session_state.stage_outputs  = {}
            st.session_state.running = False
            st.session_state.current_stage = -1
            st.session_state.logs = []
            st.rerun()

    if not api_key:
        st.info("👈 Enter your Anthropic API key in the sidebar to run the pipeline.")

    # ── Stage progress display ────────────────────────────────────────────
    st.markdown("### Pipeline Stages")
    stage_placeholders = []
    for i, (num, name) in enumerate(STAGES):
        status = st.session_state.stage_statuses.get(num, "pending")
        icon = {"pending": "⬜", "running": "🔄", "done": "✅", "failed": "❌"}.get(status, "⬜")
        css  = {"pending": "stage-pending", "running": "stage-running",
                "done": "stage-done", "failed": "stage-failed"}.get(status, "stage-pending")

        ph = st.empty()
        ph.markdown(
            f'<div class="stage-card {css}">{icon} <b>Stage {num}</b>: {name} '
            f'{"<small><i>(running...)</i></small>" if status == "running" else ""}</div>',
            unsafe_allow_html=True,
        )
        stage_placeholders.append(ph)

    # Output expanders (shown after run)
    st.markdown("### Stage Outputs")
    output_expanders: dict[int, st.delta_generator.DeltaGenerator] = {}
    for num, name in STAGES:
        if st.session_state.stage_outputs.get(num):
            with st.expander(f"Stage {num}: {name}", expanded=(num == st.session_state.current_stage)):
                out = st.session_state.stage_outputs[num]
                if isinstance(out, str) and len(out) > 100:
                    st.markdown(out)
                elif isinstance(out, dict):
                    st.json(out)
                else:
                    st.write(out)

    # ── Run logic ─────────────────────────────────────────────────────────
    if run_btn and api_key and selected_tickers:
        st.session_state.running = True
        st.session_state.stage_statuses = {i: "pending" for i, _ in STAGES}
        st.session_state.stage_outputs  = {}
        st.session_state.run_result = None

        runner = PipelineRunner(
            api_key=api_key,
            model=model_choice,
            tickers=selected_tickers,
            temperature=temperature,
        )

        # Progress callback updates session state (not thread-safe but works for single user)
        pending_updates: list[tuple] = []

        def progress_cb(stage_num: int, stage_name: str, status: str, output: dict):
            pending_updates.append((stage_num, stage_name, status, output))

        # Progress bar
        progress_bar = st.progress(0)
        status_text  = st.empty()

        total_stages = len(STAGES)
        stages_done  = 0

        async def _run():
            nonlocal stages_done
            result = await runner.run(progress_callback=progress_cb)
            return result

        # Kick off async run
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Run in a way that allows UI updates
            status_text.text("🚀 Starting pipeline...")
            run_result: RunResult = loop.run_until_complete(_run())
        finally:
            loop.close()

        # Apply all pending updates at the end (Streamlit can't update mid-async easily)
        for stage_num, stage_name, status, output in pending_updates:
            st.session_state.stage_statuses[stage_num] = status
            if output:
                st.session_state.stage_outputs[stage_num] = output

        # Apply final stage outputs from run_result
        for sr in run_result.stages:
            st.session_state.stage_statuses[sr.stage_num] = sr.status
            if sr.raw_text:
                st.session_state.stage_outputs[sr.stage_num] = sr.raw_text
            elif sr.output:
                st.session_state.stage_outputs[sr.stage_num] = sr.output

        st.session_state.current_stage = 13
        st.session_state.run_result = run_result
        st.session_state.running = False

        progress_bar.progress(100)
        if run_result.success:
            status_text.success(f"✅ Pipeline complete! Run ID: {run_result.run_id}")
        else:
            failed = [s.stage_name for s in run_result.stages if s.status == "failed"]
            status_text.error(f"⚠️ Pipeline completed with failures in: {', '.join(failed)}")

        st.rerun()


# ═════════════════════════════════════════════════════════════════════════
# TAB 2: Final Report
# ═════════════════════════════════════════════════════════════════════════
with tab_report:
    result: RunResult | None = st.session_state.get("run_result")

    if result is None:
        st.info("Run the pipeline first (Pipeline tab) to generate the report.")

        # Show universe preview as a teaser
        st.markdown("### Universe Preview")
        if selected_tickers:
            cols = st.columns(min(len(selected_tickers), 4))
            for i, ticker in enumerate(selected_tickers):
                snap = MARKET_SNAPSHOTS.get(ticker, {})
                with cols[i % 4]:
                    upside = (snap.get("consensus_target_12m", 0) - snap.get("price", 0)) / snap.get("price", 1) * 100
                    st.markdown(f"""
<div class="metric-box">
<b>{ticker}</b><br>
<small>{snap.get('company_name', '')}</small><br>
<big>${snap.get('price', 0):.2f}</big><br>
<small>Fwd P/E: {snap.get('forward_pe', 0):.1f}x</small><br>
<small>Cons. target: ${snap.get('consensus_target_12m', 0):.2f} ({upside:+.1f}%)</small>
</div>
""", unsafe_allow_html=True)
    else:
        # Report metadata header
        col_meta1, col_meta2, col_meta3, col_meta4 = st.columns(4)
        with col_meta1:
            st.metric("Run ID", result.run_id)
        with col_meta2:
            st.metric("Stocks Covered", len(result.tickers))
        with col_meta3:
            stages_ok = sum(1 for s in result.stages if s.status == "done")
            st.metric("Stages Passed", f"{stages_ok}/{len(STAGES)}")
        with col_meta4:
            total_words = len(result.final_report_md.split())
            st.metric("Report Words", f"~{total_words:,}")

        # Word count guidance
        pages_est = total_words // 250
        st.caption(f"📄 Estimated length: ~{pages_est} pages at 250 words/page | Model: {result.model}")

        st.divider()

        # Download button
        st.download_button(
            label="⬇️  Download Report (.md)",
            data=result.final_report_md,
            file_name=f"AI_Infra_Research_{result.run_id}_{DEMO_DATE}.md",
            mime="text/markdown",
            type="primary",
        )

        # Render report
        st.markdown("---")
        st.markdown(result.final_report_md, unsafe_allow_html=False)

        # Stage timing summary
        if result.stages:
            with st.expander("⏱️ Stage Timing Summary"):
                timing_data = [
                    {
                        "Stage": f"{s.stage_num}: {s.stage_name}",
                        "Status": s.status,
                        "Time (s)": f"{s.elapsed_secs:.1f}",
                        "Error": s.error or "",
                    }
                    for s in result.stages
                ]
                st.table(timing_data)


# ═════════════════════════════════════════════════════════════════════════
# TAB 3: About
# ═════════════════════════════════════════════════════════════════════════
with tab_about:
    st.markdown("""
## AI Infrastructure Research Pipeline v8

### Architecture

This platform implements a **15-stage research pipeline** for institutional-grade
AI infrastructure equity research. It separates deterministic services from LLM reasoning agents,
with a governance/audit layer throughout.

### Three-Layer Design

| Layer | Components |
|-------|-----------|
| **Deterministic Services** | Market data ingestion, reconciliation, QA, DCF engine, risk math, scenario engine, registry |
| **LLM Reasoning Agents** | Sector analysts (×3), evidence librarian, valuation analyst, red team, associate reviewer, portfolio manager, macro/political |
| **Governance Layer** | Run registry, prompt versioning, golden tests, self-audit, human override log |

### Coverage Universe

| Sub-theme | Tickers | Focus |
|-----------|---------|-------|
| Compute & Silicon | NVDA, AVGO, TSM | GPU monopoly, custom ASICs, foundry |
| Power & Energy | CEG, VST, GEV | Nuclear, generation, grid equipment |
| Infrastructure & Materials | PWR, ETN, APH, FIX, FCX, NXT | Grid build, cooling, copper, solar |

### Report Structure (~60-80 pages, full universe)

1. Executive Summary & Universe Snapshot
2. Evidence Library & Claim Ledger (Stage 5)
3. Sector Analysis — Four-Box per stock (Stage 6)
4. Valuation & Return Scenarios (Stage 7)
5. Macro & Political Risk Overlay (Stage 8)
6. Quant Risk & Stress Scenarios (Stage 9)
7. Red Team Falsification Analysis (Stage 10)
8. Portfolio Construction — 3 variants (Stage 12)
9. Associate Review & Self-Audit (Stage 11)
10. Appendices (claim register, run metadata)

### Data Sources

| Mode | Market Data | LLM |
|------|------------|-----|
| **Demo (this app)** | Illustrative snapshots | Anthropic Claude |
| **Production** | FMP API + Finnhub API | Anthropic Claude / OpenAI |

### Disclaimer

> This tool is for research and development purposes. Demo data is illustrative only.
> All [HOUSE VIEW] content is analytical opinion. Not investment advice.
> No live market data is used in demo mode.

---

*Pipeline v8 | Built on Anthropic Claude | Python 3.12 | Streamlit*
    """)
