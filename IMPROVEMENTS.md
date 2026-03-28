# Platform Improvements & Full-Polish Roadmap

> **Document type:** Living engineering + product roadmap  
> **Last updated:** March 28, 2026  
> **Current state:** Sessions 1–11 complete · 667 / 667 tests passing · commit `2b6a360`  
> **Owner:** Engineering (all divisions)

---

## Purpose

This platform emulates the full capabilities of a **JP Morgan Asset Management Australia** institutional office. The target user is an Australian-based asset manager whose clients hold diversified portfolios spread across **Australian equities (ASX), US large-cap equities (S&P 500 / NASDAQ), fixed income, and global thematic exposure**.

The system operates as a complete **AI-driven research, analysis, and portfolio management pipeline** — replacing or augmenting the work of:

- Equity Research Analysts (sector, valuation, ESG)
- Macro / Country Economists (RBA, Fed, CPI, housing, COGS)
- Quantitative Analysts (factor models, VaR, optimisation)
- Portfolio Managers (construction, mandate compliance, rebalancing)
- Risk Managers (scenario analysis, stress testing)
- Investment Governance / Compliance (IC, audit, mandate gate)
- Client Solutions (reporting, PDF, portal)
- Performance Attribution (BHB, benchmark-relative)

---

## Goal

Achieve a **weighted platform score of 9.0 / 10** across all eight JPAM-aligned divisions (currently **8.8 / 10** ex-macro), with special emphasis on:

1. **Data-flow integrity** — every agent has the correct inputs; no stage discards its output silently
2. **Macro economy depth** — real AU/US macroeconomic analysis (rates, inflation, housing, COGS) integrated throughout the pipeline
3. **Market breadth** — ASX coverage alongside US large cap; currency attribution; AU super mandate logic
4. **Institutional-quality output** — reports that read like a real research note, not scaffold text
5. **Production-hardness** — live data, CI gates, observability, multi-LLM fallback

---

## Part A — Architecture Repair (Session 11) ✅ COMPLETE — `2b6a360` ✅ Complete — `2b6a360`

Critical bugs that prevent correct data flow through the 15-stage pipeline.  
All fixes are in `src/research_pipeline/pipeline/engine.py`.

### ARC-1 · Stage 8 macro output silently discarded *(Very High impact)*

**What is wrong:** Stage 8 computes macro and political analysis and stores the result in `self.stage_outputs[8]`. However Stages 9, 10, 11, and 12 never read this key. The macro context that the entire pipeline should be grounded in is thrown away.

**Fix:** Implement `_get_macro_context()` helper that safely extracts `stage_outputs[8]`. Thread this into every downstream stage's `format_input` dict.

**Acceptance:** `stage_outputs[8]` is consumed by at minimum Stages 9, 10, 11, 12.

---

### ARC-2 · Stage 13 final report is a stub *(High impact)*

**What is wrong:** `assemble_report()` is called with `stock_cards=[]` (always empty list) and hardcoded section strings `"AI Infrastructure Investment Research — Executive Summary"`. The PM agent's `investor_document` (produced in Stage 12) and all valuation cards (produced in Stage 7) are never passed into the report.

**Fix:** Build `stock_cards` by iterating `stage_outputs[7]` valuation outputs; extract `investor_document` from `stage_outputs[12]` and use it as the executive summary.

**Acceptance:** Final report contains real stock cards and real executive summary text.

---

### ARC-3 · VaR ignores live returns *(Medium impact)*

**What is wrong:** `live_factor_returns` (a `dict[str, list[float]]`) is computed earlier in Stage 9 via `self._get_returns()`. Immediately after, the VaR call discards it and substitutes `np.random.normal(0.001, 0.02, 252)` — a fictitious synthetic distribution.

**Fix:** Aggregate `live_factor_returns.values()` into a portfolio-level return series; pass that to `parametric_var()`.

**Acceptance:** VaR result varies between run-with-live-data and run-without; no `np.random.normal` call in `stage_9_risk`.

---

### ARC-4 · Execution order: valuation before macro *(Medium impact)*

**What is wrong:** `run_full_pipeline()` awaits Stage 7 (Valuation) before Stage 8 (Macro). Valuation models therefore cannot be informed by macro regime — e.g. a rising-rate environment should compress DCF terminal-value multiples.

**Fix:** Swap the two `await` calls so Stage 8 runs before Stage 7.

**Acceptance:** Pipeline logs show Stage 8 completing before Stage 7 starts.

---

### ARC-5 · Sector routing hardcoded to 17 tickers *(Medium impact)*

**What is wrong:** Stage 6 sector routing contains three hardcoded sets:
```
compute_tickers = {NVDA, AVGO, TSM, AMD, ANET}
power_tickers   = {CEG, VST, GEV, NLR}
infra_tickers   = {PWR, ETN, HUBB, APH, FIX, FCX, BHP, NXT}
```
Any ticker outside these 17 gets zero sector analysis. ASX tickers, banks, healthcare, consumer, or any new universe composition will silently produce empty sector outputs.

**Fix:** Move routing rules into `config/loader.py` as `SECTOR_ROUTING: dict[str, list[str]]`. Allow fallback to a `GenericSectorAnalystAgent` for unmapped tickers.

**Acceptance:** Running with `["CBA.AX", "BHP.AX", "APT", "GOOGL"]` produces sector outputs for all four tickers.

---

### ARC-6 · Red Team Agent missing macro + risk inputs *(High impact)*

**What is wrong:** The Red Team Agent (Stage 10) receives only sector and valuation outputs. It cannot challenge macro assumptions (e.g. "DCF assumes 3% growth — RBA hiking cycle invalidates this") without access to macro context or risk scenarios.

**Fix:** Add `"macro_context": _get_macro_context()` and `"risk_scenarios": stage_outputs[9].get("scenarios")` to Stage 10 `format_input`.

---

### ARC-7 · Reviewer Agent missing macro + risk inputs *(High impact)*

**What is wrong:** Stage 11 Reviewer receives sector, evidence ledger, valuation, and red team outputs — but not macro context or risk. Review quality is degraded; macro-driven arguments cannot be verified.

**Fix:** Same pattern as ARC-6 — add macro + risk to Stage 11 inputs.

---

### ARC-8 · PM Agent missing macro context *(High impact)*

**What is wrong:** Stage 12 PM Agent constructs the portfolio using sector outputs, valuation, risk, and review — but has no access to the macro regime. In a rate-rising regime the PM should skew away from duration-sensitive assets; this is impossible without macro input.

**Fix:** Add `"macro_context": _get_macro_context()` to Stage 12 `format_input`.

---

### ARC-9 · Macro Agent receives no market data *(Medium impact)*

**What is wrong:** Stage 8 Macro Agent is called with `{"universe": universe}` only. It has no access to Stage 2 ingestion data (price history, earnings, news sentiment) or Stage 3 reconciliation outputs. It is writing macro analysis in a data vacuum.

**Fix:** Add `"ingestion_summary": stage_outputs[2]` and `"reconciliation_flags": stage_outputs[3]` to Stage 8 inputs.

---

### ARC-10 · Fixed Income Agent receives hardcoded stub *(High impact)*

**What is wrong:** Stage 9 Fixed Income Agent inputs include:
```python
"macro_context": {
    "note": "Live yield/spread data not available in this run. Interpret using internal heuristics."
}
```
Stage 8 completed immediately before Stage 9 with real macro output — it is simply not wired.

**Fix:** Replace the stub dict with `stage_outputs[8].get("macro", {})`.

---

## Part B — Macro Economy Module (Session 12)

The platform currently scores **2 / 10 on macro economy coverage**. The `MacroStrategistAgent` only classifies the AI infrastructure investment regime — it has zero awareness of:

- Reserve Bank of Australia (RBA) cash rate decisions
- US Federal Reserve policy (Fed funds rate, dot plot)
- Australian CPI, core inflation, trimmed mean
- US CPI / PCE
- Australian housing market (dwelling prices, credit growth, auction clearance rates)
- Australian wage growth (WPI)
- Global supply chain / COGS inflation pressure
- ASX 200 vs S&P 500 macro divergence
- AUD/USD exchange rate and its impact on unhedged US equity returns

### New Services Required

#### `EconomicIndicatorService`

```
Sources:   FRED API (US) + RBA Statistical Tables (AU) + ABS data
Outputs:   EconomicIndicators(Pydantic) — rates, CPI, unemployment, housing,
           yield curves, credit spreads for both AU and US
Caching:   In-memory cache with 1-hour TTL
Fallback:  Synthetic heuristic values if APIs unavailable
```

#### `MacroScenarioService`

```
Inputs:    EconomicIndicators
Outputs:   MacroScenario — 3-scenario matrix (base / bull / bear) per axis:
             - AU rates (RBA hiking / on-hold / cutting)
             - US rates (Fed hiking / on-hold / cutting)
             - AU inflation (above / on-target / below)
             - AU housing (accelerating / stable / correcting)
             - AUD/USD direction (strengthening / stable / weakening)
```

### New / Extended Agents

#### `EconomyAnalystAgent` (new)

```
Inputs:    EconomicIndicators + MacroScenario
Outputs:   EconomyAnalysis(Pydantic) — 12 structured fields:
             rba_cash_rate_thesis, fed_funds_thesis,
             au_cpi_assessment, us_cpi_assessment,
             au_housing_assessment, au_wage_growth,
             aud_usd_outlook, cogs_inflation_impact,
             asx200_vs_sp500_divergence, global_credit_conditions,
             key_risks_au, key_risks_us
```

#### `MacroStrategistAgent` (extend)

```
Current:   AI infrastructure regime classification only
Extended:  Receives EconomyAnalysis output; produces GlobalMacroRegime with
           AU-specific and US-specific regime flags alongside existing AI infra regime
```

### Market Scope Configuration (`MarketConfig`)

Add `MarketConfig` to `PipelineConfig`:

| Market | Priority | Indices | AU Relevance |
|---|---|---|---|
| US Large Cap / AI Infrastructure | P0 — built | S&P 500, NDX | High — JPAM AU holds US tech heavily |
| ASX Equities | P0 — build S12 | ASX 200 (^AXJO), ASX 300 | Primary — AU base |
| AU Fixed Income | P1 | AU 10Y government bond, IG spreads | High — super fund allocation |
| US Broad Market | P1 | Russell 2000, S&P 500 EW | Moderate |
| Global Thematic | P1 | MSCI World Tech | Moderate |
| Asian Technology | P2 | Nikkei 225, KOSPI | Low |
| European | P3 | Euro Stoxx 50 | Low |

---

## Part C — Session 13: Depth & Quality

Making outputs institutionally publishable.

| Item | Current State | Target State |
|---|---|---|
| Agent prompts | Generic JSON schemas | Rate/inflation-aware prompts; JPAM-style research note format |
| Valuation models | DCF + EV/EBITDA | Sensitivity tables; EV/EBITDA vs P/E cross-validation with macro overlay |
| Factor model | Synthetic if no live data | Full OLS refit against real FRED Fama-French factors (Mkt-RF, SMB, HML, RMW, CMA) |
| Report assembly | Hardcoded section titles | LLM-generated paragraph narrative per section; no hardcoded strings |
| Sector data | Hardcoded 17 tickers | `SectorDataService` calling FMP earnings / revenue endpoints; GICS classification |
| Research memory | Run-level only | Cross-run trend memory — e.g. "NVDA DCF compressed vs session 9 by 12%" |

---

## Part D — Session 14: Australian Client Context

| Item | Description |
|---|---|
| `SuperannuationMandateService` | AU super fund mandate types: growth / balanced / conservative / lifecycle / direct investment option (DIO) |
| `AustralianTaxService` | CGT discount (50% for >12mo), franking credit imputation, dividend withholding on US equities, SMSF tax rate (15%) |
| `ClientProfileSchema` | Client type (super fund / SMSF / HNW / institutional), AU residency flag, target AU/US/FI allocation |
| Mandate checking extension | Stage 3 mandate gate extended — AU super fund mandates; APRA SPS 530 diversification requirements |
| Report disclosures | AU-format FSG reference; ASIC § 1013D Product Disclosure Statement notice; AFSL disclaimer |
| SMSF rebalancing | Tax-aware rebalancing logic — CGT trigger minimisation for SMSF clients |

---

## Part E — 10 New Additions to Bolster Gap Score

These 10 items are net-new capabilities not yet in any session plan. Each addresses a specific gap-score dimension.

### E-1 · Black-Litterman Portfolio Construction *(Quant Research — gap ↑1.0)*

Replace the current mean-variance / risk-parity optimiser with a **Black-Litterman** model that blends market equilibrium returns with analyst views produced by the sector agents.

- Market cap implied returns (CAPM equilibrium) from live price data
- Analyst views mapped from Stage 6 sector agent outputs (expected returns + confidence)
- B-L posterior used as input to `PortfolioOptimisationEngine`
- Gap closes: PM agent constructs with forward-looking views, not just historical covariance

**Files:** `src/research_pipeline/services/portfolio_optimisation.py`, new `BlackLittermanEngine`

---

### E-2 · GARCH Volatility Forecasting *(Quantitative Research — gap ↑0.8)*

Replace the constant-σ assumption in parametric VaR with a **GARCH(1,1)** conditional volatility forecast. Use `arch` library.

- Fit GARCH(1,1) on `live_factor_returns` per ticker
- Conditional σ forecast used in `parametric_var()` replacing fixed `0.02`
- VaR becomes time-varying, regime-sensitive
- Adds `garch_vol_forecast: dict[str, float]` to `RiskPacket`

**Files:** `src/research_pipeline/services/risk_engine.py`

---

### E-3 · Hidden Markov Model Regime Detection *(Macro — gap ↑1.0)*

Implement a 3-state **HMM** (bull / bear / sideways) fitted on factor return history to automatically detect the current market regime without relying on LLM classification alone.

- HMM fitted on `live_factor_returns` history using `hmmlearn`
- Regime label + posterior probabilities passed to `MacroStrategistAgent`
- Removes subjective LLM-only regime assessment
- Adds `regime: Literal["bull", "bear", "sideways"]` + `regime_probability: float` to pipeline outputs

**Files:** New `src/research_pipeline/services/regime_detector.py`

---

### E-4 · Real Benchmark Data for BHB Attribution *(Performance Attribution — gap ↑1.5)*

The current BHB implementation uses synthetic benchmark returns. Replace with:

- ASX 200 Total Return (^AXJO) via yfinance for AU benchmarks
- S&P 500 Total Return (^SP500TR or SPY as proxy) for US benchmarks
- `BenchmarkConfig` per run — user selects AU / US / blended benchmark
- Rolling 1Y / 3Y / 5Y attribution periods (currently only trailing)
- GICS-sector contribution to active return

**Files:** `src/research_pipeline/services/benchmark_module.py`, `src/research_pipeline/config/loader.py`

---

### E-5 · Currency Attribution (AUD/USD) *(Performance Attribution — gap ↑0.8)*

AU-based investors in US equities face currency P&L that is separate from equity return.

- Fetch AUD/USD daily rates from FRED (`DEXUSAL`) or yfinance (`AUDUSD=X`)
- Decompose US equity return = local return + currency return + interaction term (standard BHB currency extension)
- Add `currency_attribution: CurrencyAttributionResult` to `AttributionPacket`
- Wire into Streamlit performance tab — show "Hedged" vs "Unhedged" return toggle

**Files:** `src/research_pipeline/services/benchmark_module.py`, new `CurrencyAttributionEngine`

---

### E-6 · Portfolio Carbon Intensity Score *(ESG — gap ↑1.0)*

Add Scope 1+2 carbon intensity (tCO2e / $M revenue) to the ESG assessment, driven by public disclosures + MSCI approximations.

- Source: `ESGService` extended with `carbon_intensity: float` per ticker
- Portfolio-level carbon intensity = weighted average × portfolio weights
- Add `portfolio_carbon_tco2e_per_m_revenue: float` to `EsgAnalystAgent` output
- AU super funds increasingly report this to members under TCFD / APRA CPS 230

**Files:** `src/research_pipeline/services/esg_service.py`, `src/research_pipeline/agents/esg_analyst.py`

---

### E-7 · Interactive HTML Research Report *(Client Solutions — gap ↑0.8)*

Replace the static `fpdf2` PDF with an **interactive HTML report** powered by Jinja2 + Plotly.

- Jinja2 template with embedded Plotly charts (price chart, attribution waterfall, ESG radar, sector weights)
- HTML is self-contained (all JS inline) — can be emailed or opened offline
- "Download HTML" button alongside existing PDF button in Streamlit
- Charts generated from pipeline outputs (no extra API calls)

**Files:** New `src/research_pipeline/services/report_html_service.py`, `src/frontend/app.py`

---

### E-8 · Multi-Provider LLM Fallback Chain *(Operations — gap ↑0.5)*

Extend the existing single-provider LLM fallback to a full **provider chain**: Anthropic Claude → OpenAI GPT-4o → Azure OpenAI GPT-4o → local stub.

- `BaseAgent.run()` iterates provider chain on `APIError` or timeout
- Provider config driven by `LLMConfig` in `PipelineConfig` (`preferred_provider`, `fallback_chain: list[str]`)
- `SelfAuditPacket.llm_provider_used` records which provider actually responded
- Reduces single-provider outage risk in production

**Files:** `src/research_pipeline/agents/base_agent.py`, `src/research_pipeline/config/loader.py`

---

### E-9 · Cross-Run Research Memory & Trend Alerts *(Global Research — gap ↑0.7)*

The current `ResearchMemoryService` stores run-level outputs but does not compare across runs. Add:

- Cross-run trend detection: flag when DCF fair value, VaR, or ESG score changes >10% vs previous run
- `ResearchTrend` schema: `ticker`, `metric`, `current_value`, `prior_value`, `delta_pct`, `alert_level`
- Trends included in `SelfAuditPacket.research_trends`
- Surfaced in Streamlit Observability tab as "Significant Changes Since Last Run"

**Files:** `src/research_pipeline/services/research_memory.py`, `src/research_pipeline/schemas/governance.py`

---

### E-10 · Earnings Transcript / News Sentiment NLP *(Global Research — gap ↑0.8)*

Wire a real qualitative data pipeline — turning earnings calls and news into structured sentiment signals for sector agents.

- **News:** ScraperAPI / NewsAPI / Finnhub news endpoint → headline list per ticker
- **Sentiment:** `transformers` FinBERT pipeline scores each headline (positive / neutral / negative + confidence)
- **Aggregation:** `QualitativeDataService.get_sentiment(ticker)` returns `SentimentPacket(score: float, headlines: list[str], signal: Literal["bullish","neutral","bearish"])`
- **Wiring:** `SentimentPacket` injected into Stage 2 ingestion output and passed to sector agents in Stage 6
- Currently Stage 2 has a qualitative schema but it is never populated with real signals

**Files:** `src/research_pipeline/services/qualitative_data_service.py`, `src/research_pipeline/schemas/qualitative.py`

---

### E-11 · FastAPI Event-Streaming API Layer *(Frontend — gap ↑0.8)*

Decouple the pipeline engine from any specific UI client by introducing a first-class HTTP API layer. This is the prerequisite for the premium Next.js frontend and also improves testability of the backend service contract.

- New `src/api/` FastAPI application
- Endpoints: `POST /runs` (start run), `GET /runs/{id}/events` (SSE live stream), `GET /runs/{id}/result`, `GET /runs/{id}/report`, `GET /runs/{id}/artifacts`, `GET /runs`, `DELETE /runs/{id}`
- `RunRequest` Pydantic schema as the API request body — includes universe, `ClientProfile`, mandate, model config, temperature
- SSE stream forwards all `PipelineEvent` objects emitted by the engine callback contract
- API key auth middleware on all routes

**Files:** `src/api/main.py`, `src/api/routes/`, `src/api/services/run_manager.py`, `src/research_pipeline/schemas/run_request.py`

---

### E-12 · Next.js + React Premium Product UI *(Frontend — gap ↑1.2)*

Replace the Streamlit monolith with a custom Next.js 14 (App Router) + React 18 frontend for the premium product surface. Streamlit is retained as the internal operator console.

- Full App Router page structure: Dashboard, `runs/new`, `runs/[id]` (live), `runs/[id]/report`, `runs/[id]/quant`, compare, settings
- Core components: `<PipelineTracker />` (real-time 15-stage with timers), `<LiveEventFeed />` (streaming event log), `<ReportViewer />` (TOC + jump links), `<QuantPanel />` (tabbed analytics with charts)
- Design system: TailwindCSS + shadcn/ui — institutional dark theme consistent with current Streamlit branding
- Data layer: TanStack Query (server state) + Zustand (client state) + typed API client in `lib/api.ts`

**Files:** `frontend/` — new Next.js project directory

---

### E-13 · Real-Time Stage and Agent Event Stream *(Frontend — gap ↑0.7)*

Make pipeline execution truly observable end-to-end, not just at stage completion. Users can follow the exact agent being called, the model being used, and token progress in real time.

- Engine event callback contract: `stage_started`, `stage_completed`, `stage_failed`, `agent_started`, `agent_completed`, `llm_call_started`, `llm_call_completed`, `artifact_written`
- SSE event channel forwards each event to the Next.js `<LiveEventFeed />` and `<PipelineTracker />` as it fires
- Stage statuses become: `pending` / `running` / `completed` / `failed` / `blocked` / `skipped`
- Token progress and elapsed time shown per active stage

**Files:** `src/research_pipeline/pipeline/engine.py`, `src/api/routes/events.py`, `frontend/components/pipeline/LiveEventFeed.tsx`

---

### E-14 · Compare-Runs Mode *(Frontend — gap ↑0.5)*

Allow users to select two completed runs and diff them side by side: different universes, models, portfolio weights, risk metrics, and key conclusions.

- `GET /runs/compare?run_a={id}&run_b={id}` endpoint returns normalised diffs
- `frontend/app/compare/page.tsx` — side-by-side layout with diff highlights
- Key diff dimensions: stage outputs, portfolio weights, VaR/CVaR, factor exposures, attribution, report narrative differences

**Files:** `src/api/routes/runs.py` (compare endpoint), `frontend/app/compare/page.tsx`, `frontend/components/shared/CompareView.tsx`

---

### E-15 · Report Section Provenance Traces *(Frontend — gap ↑0.6)*

Every section of the final report should be traceable back to the pipeline stage and artifact that produced it. This is the traceability and explainability layer that makes the product genuinely auditable.

- Engine emits `artifact_written` events with stage number and artifact path
- Report assembly (Stage 13) tags each section with `source_stage` and `artifact_ref`
- `<ReportViewer />` renders `<ProvenanceBadge />` on each section showing source stage + confidence flag
- Clicking a badge navigates to the `runs/[id]/stages/[n]` drilldown page
- Failed stage explainability: `<FailureExplainer />` component shows failing subsystem, last good stage, probable cause, recovery hint

**Files:** `src/research_pipeline/pipeline/engine.py` (artifact events), Stage 13 report assembly, `frontend/components/report/ProvenanceBadge.tsx`, `frontend/components/pipeline/StageDetail.tsx`

---

## Part F — Full Polish Checklist

Below is every polish item that separates "working prototype" from "institutional-grade platform". Grouped by area.

### Pipeline Integrity
- [ ] All 10 ARC bugs fixed (see Part A)
- [ ] Every `stage_outputs[N]` write has at least one `stage_outputs[N]` read downstream
- [ ] Stage execution order is semantically correct (S8 Macro → S7 Valuation → S9 Risk)
- [ ] Every agent's `format_input` includes macro context where relevant
- [ ] Report assembly uses real agent outputs — no hardcoded strings anywhere
- [ ] `_get_returns()` always used for VaR; `np.random.normal` removed from production path

### Data Quality
- [ ] `EconomicIndicatorService` live for FRED + RBA
- [ ] ASX tickers (`*.AX`) supported across all services (yfinance, ESG, sector routing)
- [ ] AUD/USD rate fetched and used in currency attribution
- [ ] GARCH(1,1) conditional volatility used for VaR
- [ ] Real BHB benchmark (ASX 200 TR or S&P 500 TR) — not synthetic returns
- [ ] News/sentiment NLP pipeline live for at least top-10 tickers (E-10)
- [ ] ESG CSV fixture has 50+ tickers including ASX-listed names
- [ ] FRED Fama-French factors (daily) fetched + cached for factor model refit

### Agent Quality
- [ ] All 14 agent prompts include macro regime context (rates, inflation, AU/US)
- [ ] `EconomyAnalystAgent` live with 12-field output
- [ ] `MacroStrategistAgent` extended for AU/US specific regime flags
- [ ] `EsgAnalystAgent` includes carbon intensity field
- [ ] `QuantResearchAnalystAgent` uses GARCH volatility in its commentary
- [ ] Black-Litterman views wired from sector agent outputs to PM optimiser
- [ ] All agent outputs validated by Pydantic — no raw `dict` returns bubbling up

### Portfolio & Risk
- [ ] Black-Litterman optimiser live (E-1)
- [ ] GARCH VaR live (E-2)
- [ ] HMM regime detector live (E-3)
- [ ] VaR stress scenarios include AU macro scenarios (RBA hike, AU housing correction)
- [ ] `SuperannuationMandateService` live — mandate gate covers super fund requirements
- [ ] SMSF CGT-aware rebalancing trigger logic implemented
- [ ] `rebalance_proposal` in Stage 12 uses macro regime weighting

### Performance Attribution
- [ ] Real ASX 200 TR benchmark used for AU portfolios
- [ ] Real S&P 500 TR benchmark used for US portfolios
- [ ] GICS sector contribution to active return
- [ ] AUD/USD currency attribution decomposition (E-5)
- [ ] Rolling 1Y / 3Y / 5Y periods
- [ ] Cross-run trend alerts (E-9) surface in Observability tab

### ESG
- [ ] Carbon intensity per ticker in `ESGService`
- [ ] Portfolio-level carbon intensity in `EsgAnalystAgent` output
- [ ] APRA CPS 230 / TCFD alignment flag
- [ ] MSCI ESG approximation dataset (50+ AU + US tickers)
- [ ] ESG controversy score sourced from news sentiment (E-10 integration)

### Client Solutions & Reporting
- [ ] Interactive HTML report (E-7) — downloadable from Streamlit
- [ ] Report sections use real PM `investor_document` + real stock cards
- [ ] AU-format disclosures (FSG, AFSL, ASIC § 1013D) in report footer
- [ ] Client profile schema with AU residency and super type (Session 14)
- [ ] Report narrative generated per-section by LLM (no hardcoded strings)

### Governance & Compliance
- [ ] `SelfAuditPacket.research_trends` populated with cross-run deltas (E-9)
- [ ] `SelfAuditPacket.llm_provider_used` populated (E-8)
- [ ] Prompt regression CI gate covering all 14 agent prompts
- [ ] Mandate gate covers AU super fund mandates (Session 14)
- [ ] Every run persists full `SelfAuditPacket` to disk (currently working — verify)
- [ ] IC vote requires PASS from all three signal sources (currently working — verify)

### Operations
- [ ] Multi-provider LLM fallback chain (E-8)
- [ ] Weekly CI job runs against live FRED + yfinance + FMP
- [x] `SECTOR_ROUTING` config externalised (ARC-5 fix) ✅ Session 11
- [ ] `docker-compose.yml` for local production deployment
- [ ] Grafana / Prometheus metrics stub for observability export
- [ ] Blue/green pipeline deployment with canary comparison

### Frontend & Product UI (Migration)
- [x] Phase 1: adapter fixes — report_path → markdown loaded, token_log populated, audit_packet surfaced, temperature wired (Session 11)
- [x] Phase 1: all three provider key paths (Anthropic / OpenAI / Google) cleanly handled in adapter
- [x] Phase 1: `st.session_state["run_result"]` key fixed (ISS-20)
- [ ] Phase 2: engine event callback contract implemented (`stage_started`, `agent_started`, `llm_call_*`, `artifact_written`)
- [ ] Phase 3: `RunRequest` Pydantic schema defined; `run_full_pipeline(request)` signature adopted
- [ ] Phase 3: `ClientProfile` + mandate threaded into Stages 9, 12, 13
- [ ] Phase 3: unified artifact layout under `reports/{run_id}/`; `storage.py` indexes engine run dir
- [ ] Phase 4: FastAPI `src/api/` layer built; `POST /runs`, SSE `/runs/{id}/events`, artifact endpoints all tested (E-11)
- [ ] Phase 5: Next.js `frontend/` project scaffolded with TailwindCSS + shadcn/ui (E-12)
- [ ] Phase 5: `<PipelineTracker />` shows `running` state with elapsed timer (E-13)
- [ ] Phase 5: `<LiveEventFeed />` streams agent + token events as they happen (E-13)
- [ ] Phase 5: `<ReportViewer />` renders full report from `report_path` with floating TOC
- [ ] Phase 5: `<QuantPanel />` serves all analytics tabs with charts (VaR, factor, attribution, ESG, rebalance)
- [ ] Phase 6: all 10 visual analytics charts implemented
- [ ] Phase 6: compare-runs view built (E-14)
- [ ] Phase 7: every report section has `<ProvenanceBadge />` linking to source stage (E-15)
- [ ] Phase 7: failed run explainability component renders probable cause and recovery hint
- [ ] Phase 7: `<StageDetail />` panel shows inputs, outputs, gate result, key assumptions for every stage
- [ ] Streamlit `src/frontend/app.py` retained and functional as internal operator console throughout all phases

---

## Part G — Division Gap Score Targets

Current weighted scores post-sessions 1–10. Projected scores after each session block.

| Division | S10 Score | After S11 | After S12 | After S13 | After S14 | After E-1–10 | After S15–17 (UI) | JPAM Target |
|---|---|---|---|---|---|---|---|---|
| Global Research | 8.0 | 8.3 | 8.8 | **9.2** | 9.2 | **9.5** | 9.5 | 9.0 |
| Quantitative Research | 8.5 | 8.7 | 9.0 | 9.2 | 9.2 | **9.7** | 9.7 | 9.0 |
| Portfolio Management | 8.0 | 8.3 | 8.7 | 9.0 | **9.3** | **9.5** | 9.5 | 8.5 |
| Investment Governance | 8.8 | 9.0 | 9.0 | 9.1 | **9.4** | 9.4 | 9.6 | 9.5 |
| Performance Attribution | 7.5 | 7.5 | 8.0 | 8.5 | 8.5 | **9.3** | 9.3 | 8.5 |
| ESG / Sustainable Investing | 6.5 | 6.5 | 6.8 | 7.0 | 7.0 | **8.0** | 8.0 | 7.5 |
| Operations & Technology | 8.8 | 9.0 | 9.0 | 9.1 | 9.1 | **9.4** | 9.4 | 9.0 |
| Client Solutions / Reporting | 8.5 | 8.5 | 8.7 | **9.0** | 9.2 | **9.5** | 9.6 | 8.5 |
| **Macro Economy** | **2.0** | 2.0 | **7.5** | 8.0 | 8.0 | **8.5** | 8.5 | 8.0 |
| **Frontend / Product UI** | **6.5** | 7.0 | 7.5 | 7.8 | 7.8 | 7.8 | **9.3** | 8.5 |
| **Weighted Overall** | **8.1** | 8.4 | 8.7 | 8.9 | 9.0 | **9.3** | **9.4** | 9.0 |

> Note: Macro Economy is a new division added to the scoring matrix. Frontend / Product UI is also now tracked as a division based on the March 28 assessment (current: 6.5/10). The frontend migration (Sessions 15–17) is the largest single score uplift left on the roadmap.


---

## Part H — Prioritised Backlog (All Items in Sequence)

| Priority | ID | Item | Session | Effort |
|---|---|---|---|---|
| 1 | ARC-4 | Fix Stage 7/8 execution order | ✅ S11 | Trivial |
| 2 | ARC-1 | Wire Stage 8 macro to S9/S10/S11/S12 | ✅ S11 | Low |
| 3 | ARC-10 | Fix FI Agent hardcoded stub | ✅ S11 | Trivial |
| 4 | ARC-6 | Red Team macro + risk inputs | ✅ S11 | Low |
| 5 | ARC-7 | Reviewer macro + risk inputs | ✅ S11 | Low |
| 6 | ARC-8 | PM Agent macro context | ✅ S11 | Low |
| 7 | ARC-9 | Macro Agent receives market data | ✅ S11 | Low |
| 8 | ARC-3 | VaR uses live returns (not random) | ✅ S11 | Low |
| 9 | ARC-5 | SECTOR_ROUTING config | ✅ S11 | Medium |
| 10 | ARC-2 | Real report assembly (stock cards + PM doc) | ✅ S11 | Medium |
| 11 | — | `EconomicIndicatorService` (FRED + RBA) | S12 | Medium |
| 12 | — | `MacroScenarioService` | S12 | Medium |
| 13 | — | `EconomyAnalystAgent` (12-field AU/US) | S12 | Medium |
| 14 | — | `MarketConfig` + ASX universe support | S12 | Low |
| 15 | — | Wire macro scenarios into VaR stress tests | S12 | Low |
| 16 | — | Agent prompt upgrades (macro-aware) | S13 | Medium |
| 17 | — | DCF sensitivity tables with macro overlay | S13 | Medium |
| 18 | — | Fama-French 5-factor live refit (FRED) | S13 | High |
| 19 | E-2 | GARCH(1,1) VaR | S13/E | Medium |
| 20 | E-3 | HMM regime detection | S13/E | Medium |
| 21 | E-1 | Black-Litterman optimiser | E | High |
| 22 | E-4 | Real benchmark data (ASX 200 TR + S&P 500 TR) | E | Medium |
| 23 | E-5 | AUD/USD currency attribution | E | Medium |
| 24 | E-9 | Cross-run research trend alerts | E | Medium |
| 25 | — | `SuperannuationMandateService` | S14 | Medium |
| 26 | — | `AustralianTaxService` (CGT, franking) | S14 | Medium |
| 27 | E-7 | Interactive HTML report | E | Medium |
| 28 | E-6 | Portfolio carbon intensity (ESG) | E | Low |
| 29 | E-8 | Multi-provider LLM fallback chain | E | Medium |
| 30 | E-10 | Earnings/news sentiment NLP pipeline | E | High |
| 31 | — | ASIC / AFSL report disclosures | S14 | Low |
| 32 | — | Docker-compose production deployment | E | Low |

---

## Summary Statistics

| Category | Count |
|---|---|
| Architecture repair items (ARC) | 10 |
| Planned session items (S11–S14) | 22 |
| Net-new additions (E-1–E-10) | 10 |
| Residual issues from `PROJECT_ISSUES_ASSESSMENT.md` | 41 |
| Full polish checklist items | 47 |
| **Total tracked improvements / watch-outs** | **130** |

Current test count: **667**  
Projected after S12–S14 + E items: **667 + 35 + 30 + 30 + 50 ≈ 812 tests**

---

## Part I — External PR Intake Decisions (March 28, 2026)

### PR #1 — `Core system improvements`

**Decision:** do **not** merge as-is.

Why:

| Evidence | Result |
|---|---|
| Isolated PR branch test run | **14 failed, 18 errors, 575 passed** |
| Immediate runtime break | `_route_sector_tickers()` missing in `PipelineEngine` |
| Secondary runtime break | `_build_metric_snapshot()` missing in `PipelineEngine` |
| Scope quality | Too many unrelated features landed in one PR without clean staging |

**Use it for:** idea harvesting only. Good concepts to salvage later:
- `EconomyAnalystAgent`
- AU tax and super overlays
- LLM provider telemetry
- HTML report service
- cross-run research trend alerts

### PR #2 — `PROJECT_ISSUES_ASSESSMENT.md`

**Decision:** merged. The document is useful and has now been accepted into `main`.

What it adds:
- a post-roadmap audit of **41 residual issues**
- a severity-ranked list of architectural gaps still not captured in the base roadmap
- several prerequisite fixes that need to be folded into Sessions 11–13

---

## Part J — Residual Issues Added from `PROJECT_ISSUES_ASSESSMENT.md`

These are issues not previously covered by Parts A–H.

### Severity summary

| Severity | Count |
|---|---|
| Critical | 1 |
| High | 15 |
| Medium | 19 |
| Low | 6 |

### New immediate-priority additions

| ID | New issue | Why it changes the plan | Status |
|---|---|---|---|
| ISS-1 | `MacroContextPacket` schema missing | ARC-1 needs typed validation, not raw dict threading | ✅ `2b6a360` |
| ISS-3 | No `GenericSectorAnalystAgent` fallback | ARC-5 remains incomplete otherwise | ✅ `2b6a360` |
| ISS-4 | `ValuationCard` → `StockCard` mapper unspecified | ARC-2 can still produce malformed report cards | ✅ `2b6a360` |
| ISS-9 | Agent quality checks are non-fatal | Missing required keys still pass through the system | ✅ `2b6a360` |
| ISS-10 | Gemini package/import mismatch | E-8 fallback chain can break on first use | ✅ `2b6a360` |
| ISS-12 | Macro agents lack required key contracts | Session 12 needs unified Stage 8 packet design | 🔲 S12 |
| ISS-13 | No ASX prompt coverage | AU market support remains shallow even with AU data | 🔲 S12 |
| ISS-16 | BHB benchmark still synthetic | E-4 needs deeper scope than currently written | 🔲 S13 |
| ISS-20 | Streamlit `result` / `run_result` mismatch | Frontend observability can fail despite backend success | ✅ `2b6a360` |
| ISS-27 | No live API E2E pipeline test | Production-readiness score remains overstated | 🔲 S13 |

### Session remapping after the assessment

| Session | Existing scope | Newly added residual issues |
|---|---|---|
| Session 11 | ARC-1 through ARC-10 | ISS-1, ISS-3, ISS-4, ISS-9, ISS-10, ISS-20 — ✅ **`2b6a360` complete** |
| Session 12 | Macro economy + AU/US markets | ISS-12, ISS-13, ISS-14, ISS-22 |
| Session 13 | Depth & quality | ISS-16, ISS-23, ISS-27, ISS-28 |
| Session 14 | AU client context | ISS-29, ISS-30 |
| Future Ops / Session 15+ | Production hardening | ISS-34, ISS-35, ISS-36, ISS-37, ISS-38, ISS-39, ISS-40, ISS-41 |

### Extra watch-outs added to the polish checklist

- Do not mark ARC-1 done until macro payload validation is typed and default-safe.
- Do not mark ARC-2 done until report cards are produced through an explicit adapter.
- Do not mark ARC-5 done until unmapped tickers still receive a sector view.
- Do not count E-8 complete until Gemini import/runtime path is proven in tests.
- Do not count E-4 complete until benchmark **return series** are real, not just benchmark weights.
- Do not call the platform production-ready until a live-key full pipeline integration test exists.

---

## Part K — Frontend Architecture Migration (Streamlit → Next.js + FastAPI)

**Decision:** Move away from Streamlit for the premium product surface. Keep Streamlit as an internal operator console only. Build a new high-end custom frontend using Next.js (React) backed by a FastAPI event-streaming API layer.

This decision is driven by an independent frontend assessment that scored the current app at **6.5/10 overall** and **5.5/10 for backend fidelity**. The assessment identified structural limits in Streamlit that cannot be resolved through iterative patching.

---

### K.1 — Assessment Findings Summary (Current Streamlit State)

| Capability | High-end expectation | Current state | Score |
|---|---|---|---|
| Visual polish | Strong identity, clean layout | Good | 7.5/10 |
| Backend fidelity | UI reflects actual backend state | Partial | 5.5/10 |
| Real-time observability | True stage/substage live updates | Weak | 4.5/10 |
| Drill-down depth | Multi-level linked navigation | Moderate | 7/10 |
| Navigation | Fast, filterable, searchable | Moderate | 6/10 |
| Analytical richness | Deep risk/portfolio/evidence tools | Good | 7.5/10 |
| Explainability | Easy to understand system reasoning | Partial | 6/10 |
| Saved workflows | History, compare, reload, artifacts | Moderate | 6.5/10 |
| User friendliness | Intuitive for non-operator users | Moderate | 6.5/10 |
| **Overall** | | | **6.5/10** |

**Top 5 highest-impact current gaps (ordered by impact):**

1. Report markdown missing — Stage 13 stores `report_path`, not inline markdown; Report tab can be blank on successful runs
2. Token/cost/audit/timing panels dormant — adapter never populates `token_log`, `audit_packet` not surfaced to UI state
3. Sidebar controls not fully wired — `temperature`, `stage_models`, `ClientProfile` collected but not passed to engine
4. Only stage completion events exist — no stage-start, agent-start, or substage events; users cannot follow execution in progress
5. Storage split — backend artifacts under `PIPELINE_STORAGE_DIR`, frontend saved runs under `reports/`; inconsistent reload

---

### K.2 — Migration Decision

| Factor | Streamlit | Next.js + FastAPI |
|---|---|---|
| Real-time observability | Simulated, constrained | True WebSocket/SSE streams |
| Navigation depth | Scripted vertical scroll | Pages, routes, deep-links |
| Custom interaction | Limited | Full React component freedom |
| Visual analytics | Constrained | Recharts, D3, AG Grid |
| Backend fidelity | Hard to wire cleanly | First-class API contract |
| Compare-runs mode | Very hard | Standard multi-view routing |
| Traceability + provenance | Very hard | First-class component design |
| Time to premium UX | Months of workarounds | Clean build from solid base |

**Architecture decision:**
- Keep `src/research_pipeline/` entirely — the Python backend is sound
- Add `src/api/` — FastAPI application as the bridge between pipeline and any frontend
- Keep `src/frontend/app.py` as internal operator console only (ISS fixes still apply there)
- Build `frontend/` — Next.js 14 + React 18 premium product UI

**Realistic score ceiling after migration:** 9.0–9.4/10

---

### K.3 — Phase Plan (Layered with Existing Sessions)

Each phase maps to an existing session block or a new session.

#### Phase 1 — Fix adapter truthfulness (fold into Session 11)

Fixes the five highest-impact current gaps on the existing Streamlit app. This work is required regardless of migration — it validates the API contract.

- Load actual report markdown from `report_path` when inline markdown is absent (`pipeline_adapter.py:202-205`, `engine.py:1242-1244`)
- Wire `llm_temperature` into Settings object (adapter `137-148`)
- Populate `token_log` and `audit_packet` in adapter result mapping (`pipeline_adapter.py:209-219`)
- Surface `stage_timings` from engine run record
- Fix all three provider key paths (Anthropic, OpenAI, Google) consistently
- Acceptance: Report tab always has content after a successful run; cost panel populated; `st.session_state["run_result"]` resolved (ISS-20)

#### Phase 2 — Engine event stream (fold into Session 12)

Add a lightweight structured event callback contract to `PipelineEngine`. This is required by both the Streamlit UI improvements and the new frontend.

Events to emit:
- `stage_started(stage_num, stage_name)`
- `stage_completed(stage_num, duration_ms, summary)`
- `stage_failed(stage_num, error)`
- `agent_started(stage_num, agent_name)`
- `agent_completed(stage_num, agent_name, token_count)`
- `artifact_written(stage_num, artifact_path)`
- `llm_call_started(stage_num, provider, model)`
- `llm_call_completed(stage_num, tokens_in, tokens_out, cost_usd)`

Acceptance: stage status in Streamlit shows `running` (not just `done`); telemetry panel populated; stage events in order during integration tests.

#### Phase 3 — Unified storage and RunRequest schema (fold into Session 12–13)

- Define `RunRequest` Pydantic schema in `src/research_pipeline/schemas/` containing: universe, provider/model config, `ClientProfile`, mandate constraints, benchmark, report options, execution options
- Change `run_full_pipeline(universe)` signature to `run_full_pipeline(request: RunRequest)`
- Thread `ClientProfile` and mandate into Stages 9, 12, 13
- Unify artifact layout under: `reports/{run_id}/report.md`, `/report.pdf`, `/summary.json`, `/audit_packet.json`, `/telemetry.json`, `/stages/{00..14}.json`
- Update `storage.py` to index canonical engine run directory rather than write a parallel copy
- Acceptance: reload of any saved run always produces complete report content; all artifacts accessible from one directory; portfolio section cites mandate constraints

#### Phase 4 — FastAPI event-streaming API layer (new Session 15)

New work: build `src/api/` as the formal backend-to-frontend bridge.

Key endpoints:
- `POST /runs` — create a run from `RunRequest`; returns `run_id`
- `GET /runs/{run_id}/events` — SSE stream of structured pipeline events
- `GET /runs/{run_id}/result` — full result JSON on completion
- `GET /runs/{run_id}/stages/{stage_num}` — per-stage artifact
- `GET /runs/{run_id}/report` — report markdown or HTML
- `GET /runs/{run_id}/artifacts` — artifact manifest
- `GET /runs` — saved run list
- `DELETE /runs/{run_id}` — delete run
- WebSocket `/runs/{run_id}/live` — alternative real-time channel

Security scope: API key auth on all endpoints; CORS locked to localhost or configured origin.

Acceptance: Next.js frontend can start a run and receive live stage events; report content always loads; all quant analytics endpoints return structured data.

#### Phase 5 — Next.js premium UI (new Session 16)

Build `frontend/` using:
- **Next.js 14** (App Router)
- **React 18** with server + client components
- **TailwindCSS** + shadcn/ui design system for consistent institutional look
- **Recharts** or **Tremor** for charts
- **AG Grid Community** for data tables
- **React Query (TanStack Query)** for server state management
- **Zustand** for client-side state

Page / route structure:
```
/                      — Dashboard: last run summary, quick start
/runs/new              — Configure and launch a new pipeline run
/runs/[id]             — Live run view: stage tracker + event feed + live analytics
/runs/[id]/report      — Full report with TOC, section jump, stage provenance links
/runs/[id]/stages/[n]  — Per-stage artifact drilldown
/runs/[id]/quant       — Quant analytics: VaR, factor, attribution, ESG, rebalance
/runs/[id]/artifacts   — Raw artifact browser
/runs                  — Saved runs list with compare mode
/compare               — Side-by-side run comparison
/settings              — Provider keys, default model, preferences
```

Core UI components to build:
- `<PipelineTracker />` — real-time 15-stage progress with start/running/done/failed states per stage, elapsed timers
- `<LiveEventFeed />` — streaming event log with agent, token, artifact entries
- `<StageDetail />` — drawerside panel: inputs received, outputs produced, gate result, key assumptions
- `<ReportViewer />` — report with floating TOC, jump links, section-level provenance badges
- `<QuantPanel />` — tabbed analytics with charts: VaR/CVaR, drawdown, factor radar, attribution waterfall, ETF overlap heatmap
- `<ArtifactBrowser />` — tree view of all run artifacts, open/download per file
- `<CompareView />` — diff two runs by stage outputs, portfolio weights, risk metrics
- `<TokenCostPanel />` — cost breakdown by stage/provider/model with totals

Acceptance: all backend data surfaces in meaningful UI; users can follow execution in real time; any section of a report can be traced back to its source stage; ESG, risk, attribution, rebalance all have charts not just tables.

#### Phase 6 — Visual analytics upgrade (fold into Session 16)

Charts to implement alongside the Next.js UI:
- Stage duration bar chart (post-run timeline)
- Run event timeline (Gantt-style)
- Portfolio allocation donut/treemap
- Factor exposure radar + bar chart
- Drawdown chart (cumulative return line)
- Attribution waterfall (contribution by security)
- ETF overlap heatmap
- Scenario outcome table + bar chart
- ESG score heatmap by sector
- Token usage breakdown (stacked bar by stage)

#### Phase 7 — Traceability and explainability (new Session 17)

- Every major report section displays: source stage(s), underlying artifacts, confidence flags, gate result
- Per-stage provenance cards: inputs received, outputs generated, gate result, key assumptions, downstream dependencies
- Failed run explainability: failing subsystem highlighted, last successful stage, probable cause, recovery hint
- Audit trail: complete JSON audit packet browsable from the UI
- Evidence citation: agent evidence links back to the stage that produced them

---

### K.4 — New E-Items (E-11 through E-15)

These extend the original E-1–E-10 list with frontend-specific additions made possible by the migration.

| ID | Item | What it adds | Target session |
|---|---|---|---|
| E-11 | FastAPI event-streaming layer | Decouples frontend from Python script model; enables any UI client | Session 15 |
| E-12 | Next.js + React premium UI | Premium product surface vs dashboard page; full routing and navigation | Session 16 |
| E-13 | Real-time stage + agent event stream | Users can follow execution at stage AND agent level as it runs | Session 15–16 |
| E-14 | Compare-runs mode | Side-by-side diff of universe/portfolio/risk across separate pipeline runs | Session 16 |
| E-15 | Report section provenance traces | Every report claim linked to originating stage and artifact | Session 17 |

---

### K.5 — Score Progression

| After phase | Expected product score |
|---|---|
| Phase 1 (adapter truthfulness) | 7.0/10 |
| Phase 2 (engine event stream) | 7.5/10 |
| Phase 3 (storage + RunRequest) | 7.8/10 |
| Phase 4 (FastAPI layer) | 8.2/10 |
| Phase 5 (Next.js UI) | 8.8/10 |
| Phase 6 (visual analytics) | 9.0/10 |
| Phase 7 (traceability) | 9.3/10 |

---

### K.6 — Watch-outs for the Migration

- Do not remove `src/frontend/app.py` until Phase 5 is fully tested and the new UI covers all operator use cases
- The FastAPI layer must honour the `RunRequest` schema before the Next.js UI builds against it — API-first design is mandatory
- Keep Streamlit adapter fixes (Phase 1) even after Phase 5 — the operator console stays
- All new E-items (E-11–E-15) depend on the Phase 4 API layer being stable
- Visual analytics (Phase 6) should use the same data as the Streamlit quant panels — do not invent new data models for charts
- Traceability (Phase 7) requires engine event stream to include artifact paths — this contract must be set in Phase 2 or it will require a later engine change

---

## Summary Statistics (updated)

| Category | Count |
|---|---|
| Architecture repair items (ARC-1–10) | 10 |
| Session 11–14 scoped work items | ~40 |
| New E-items (E-1–E-15) | 15 |
| Residual issues (ISS-1–41) | 41 |
| Frontend migration phases (Phase 1–7) | 7 |
| PR #2 issues ingested | 41 |
| **Total tracked improvements / watch-outs** | **~154** |

---

*This document supersedes the brainstorm sections in ARCHITECTURE.md §13.9 and TRACKER.md §12 for the purposes of implementation planning. Those sections remain as quick-reference summaries. It now also incorporates the merged `PROJECT_ISSUES_ASSESSMENT.md` residual-issue audit, the explicit decision not to merge PR #1 as-is, and the full frontend architecture migration plan (Parts K) layering the new Next.js + FastAPI UI with the existing implementation sessions.*
