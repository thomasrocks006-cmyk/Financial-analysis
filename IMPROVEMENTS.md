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

## Part B — Macro Economy Module (Session 12) ✅ COMPLETE — `12c7086`

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

## Part C — Session 13: Depth & Quality ✅ COMPLETE — `34d7949`

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

## Part D — Session 14: Australian Client Context ✅ COMPLETE — `29272dd`

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

### E-11 · FastAPI Event-Streaming API Layer *(Frontend — gap ↑0.8)* ✅ **COMPLETE — `7a62757`**

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
- [x] `EconomyAnalystAgent` live with 12-field output
- [x] `MacroStrategistAgent` extended for AU/US specific regime flags
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
- [x] Phase 4: FastAPI `src/api/` layer built; `POST /runs`, SSE `/runs/{id}/events`, artifact endpoints all tested (E-11) — ✅ `7a62757`
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
| 11 | — | `EconomicIndicatorService` (FRED + RBA) | ✅ S12 `12c7086` | Medium |
| 12 | — | `MacroScenarioService` | ✅ S12 `12c7086` | Medium |
| 13 | — | `EconomyAnalystAgent` (12-field AU/US) | ✅ S12 `12c7086` | Medium |
| 14 | — | `MarketConfig` + ASX universe support | ✅ S12 `12c7086` | Low |
| 15 | — | Wire macro scenarios into VaR stress tests | ✅ S12 `12c7086` | Low |
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
| ISS-12 | Macro agents lack required key contracts | Session 12 needs unified Stage 8 packet design | ✅ `12c7086` |
| ISS-13 | No ASX prompt coverage | AU market support remains shallow even with AU data | ✅ `12c7086` |
| ISS-16 | BHB benchmark still synthetic | E-4 needs deeper scope than currently written | 🔲 S13 |
| ISS-20 | Streamlit `result` / `run_result` mismatch | Frontend observability can fail despite backend success | ✅ `2b6a360` |
| ISS-27 | No live API E2E pipeline test | Production-readiness score remains overstated | 🔲 S13 |

### Session remapping after the assessment

| Session | Existing scope | Newly added residual issues |
|---|---|---|
| Session 11 | ARC-1 through ARC-10 | ISS-1, ISS-3, ISS-4, ISS-9, ISS-10, ISS-20 — ✅ **`2b6a360` complete** |
| Session 12 | Macro economy + AU/US markets | ISS-12, ISS-13, ISS-14, ISS-22 — ✅ **`12c7086` complete** |
| Session 13 | Depth & quality | ISS-16, ISS-23, ISS-27, ISS-28 — ✅ **`34d7949` complete** |
| Session 14 | AU client context | ISS-29, ISS-30 — ✅ **`29272dd` complete** |
| Session 15 | FastAPI API layer + engine event stream | E-11, Phase 2–4 — ✅ **`7a62757` complete** |
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

---

## Part L — Backend Contract Hardening & Architecture Evolution

> **Source:** Cross-analysis from `BACKEND_ARCHITECTURE_ASSESSMENT.md` (March 2026)  
> **Priority basis:** Items ranked by impact/effort ratio — contract discipline first, topology additions second  
> **Current backend score:** 7.9/10 → **Target: 9.0/10**  
> **Philosophy:** Most of the quality ceiling is a *contract discipline problem*, not a *topology problem*. Fix the handoffs between existing stages before adding new interaction paths.

---

### L.1 — Claim Ledger as a Live Contract (BCH-1)

**Priority:** CRITICAL — Highest ROI improvement available  
**Current state:** Stage 5 produces a richly structured `ClaimLedger` (four-tier source tiering, per-claim PASS/CAVEAT/FAIL, corroboration tracking) that is largely ignored by downstream stages. Agents read prose summaries; they do not cite claim IDs or formally address CAVEAT/FAIL status.  
**Impact:** Every downstream stage that ignores the ledger is operating on ungrounded inference. Fixing this raises traceability, reduces hallucination risk, and gives Stage 11 (Reviewer) and Stage 10 (Red Team) dramatically better adversarial coverage.

#### What needs to change

**Step 1 — Extend downstream output schemas to require claim citations**

`FourBoxOutput` (sector), `ValuationCard` (valuation), `RedTeamAssessment` (red team) must cite which claims they rely on:

```python
# schemas/portfolio.py additions

class FourBoxOutput(BaseModel):
    # ... existing fields ...
    cited_claim_ids: list[str] = Field(
        default_factory=list,
        description="Claim IDs from ClaimLedger that support this analysis"
    )
    unresolved_caveats: list[str] = Field(
        default_factory=list,
        description="Claim IDs with CAVEAT status that this analysis explicitly acknowledges"
    )
    contested_claims: list[str] = Field(
        default_factory=list,
        description="Claim IDs this analysis disputes with rationale"
    )

class ValuationCard(BaseModel):
    # ... existing fields ...
    cited_claim_ids: list[str] = Field(default_factory=list)
    unresolved_caveats: list[str] = Field(default_factory=list)
    claim_ledger_coverage: float = Field(
        default=0.0,
        description="Fraction of relevant claims explicitly addressed (0.0–1.0)"
    )

class RedTeamAssessment(BaseModel):
    # ... existing fields ...
    challenged_claim_ids: list[str] = Field(
        default_factory=list,
        description="Claim IDs this red team assessment directly challenges"
    )
    unchallenged_high_confidence_claims: list[str] = Field(
        default_factory=list,
        description="HIGH-confidence PASS claims not challenged — must be justified"
    )
```

**Step 2 — Inject claim ledger as a typed structured input, not prose**

In `engine.py`, all Stage 6/7/10/11 prompt inputs must receive:

```python
# In stage_6_sector_analysis, stage_7_valuation, stage_10_red_team, stage_11_review:
"claim_ledger_summary": {
    "total_claims": len(ledger.claims),
    "pass_count": ledger.pass_count,
    "caveat_count": ledger.caveat_count,
    "fail_count": ledger.fail_count,
    "tier_1_claims": [c.model_dump() for c in ledger.claims if c.source_id and c.status == ClaimStatus.PASS],
    "caveat_claims": [c.model_dump() for c in ledger.claims if c.status == ClaimStatus.CAVEAT],
    "fail_claims": [c.model_dump() for c in ledger.claims if c.status == ClaimStatus.FAIL],
}
```

**Step 3 — Enforce citation in gates**

```python
# gates.py — gate_6_sector_analysis
@staticmethod
def gate_6_sector_analysis(
    four_box_count: int,
    expected_count: int,
    unsupported_claims: int = 0,
    min_claim_citation_rate: float = 0.0,  # NEW
    actual_citation_rate: float = 0.0,     # NEW
) -> GateResult:
    blockers = []
    # ... existing checks ...
    if actual_citation_rate < min_claim_citation_rate:
        blockers.append(
            f"Sector analysis cites only {actual_citation_rate:.0%} of available claims "
            f"(minimum required: {min_claim_citation_rate:.0%})"
        )
    return GateResult(...)
```

**Step 4 — FAIL claims must be explicitly disposed of before Stage 11**

Gate 11 (Associate Review) should receive a `ClaimDispositionReport`:

```python
class ClaimDispositionReport(BaseModel):
    """Tracks whether every FAIL/CAVEAT claim was addressed downstream."""
    run_id: str
    total_fail_claims: int
    disposed_fail_claims: int  # Claims where a downstream agent explicitly addressed them
    undisposed_fail_claims: list[str]  # Claim IDs not addressed by any downstream stage
    total_caveat_claims: int
    disposed_caveat_claims: int
    undisposed_caveat_claims: list[str]

    @property
    def all_fails_disposed(self) -> bool:
        return len(self.undisposed_fail_claims) == 0
```

Gate 11 blocks if `undisposed_fail_claims` is non-empty.

**Acceptance criteria:**
- Every `FourBoxOutput` contains at least one `cited_claim_id`
- Every `ValuationCard` references the claims underpinning its thesis
- Gate 11 rejects runs where FAIL claims have not been explicitly addressed
- `claim_ledger_coverage` field is populated and measured in telemetry

**Estimated score uplift:** +0.3 overall (traceability, auditability, hallucination resistance)

---

### L.2 — Cross-Sector Disagreement Typed Schema (BCH-2)

**Priority:** HIGH  
**Current state:** Three sector analysts run in parallel (Stage 6). Their outputs are stored independently in `stage_outputs[6]`. No stage reconciles them. Conflicting sector views (e.g. Compute says power is the primary growth constraint; Infrastructure says it is permitting timelines) coexist silently. Portfolio construction in Stage 12 consumes both views without knowing they conflict.  
**Impact:** Portfolio coherence, reviewer quality, and thesis integrity all benefit from explicit disagreement tracking.

#### New schema: `CrossSectorSynthesis`

```python
# schemas/portfolio.py — new model

class SectorDisagreement(BaseModel):
    """A specific point of disagreement between two sector analysts."""
    disagreement_id: str
    topic: str  # e.g. "primary_growth_constraint", "power_demand_timeline"
    sector_a: str
    sector_a_position: str
    sector_a_confidence: ConfidenceLevel
    sector_b: str
    sector_b_position: str
    sector_b_confidence: ConfidenceLevel
    portfolio_impact: str  # How this disagreement affects position sizing or thesis
    resolution: str = ""  # Populated by downstream review or PM

class SharedBottleneck(BaseModel):
    """A constraint or risk factor that affects multiple sectors simultaneously."""
    bottleneck_id: str
    description: str  # e.g. "US grid interconnection queue delays"
    affected_sectors: list[str]
    affected_tickers: list[str]
    severity: str  # "critical", "significant", "moderate"
    evidence_claim_ids: list[str]  # Links to ClaimLedger

class CrossSectorSynthesis(BaseModel):
    """Structured synthesis of parallel sector analyst outputs."""
    run_id: str
    sectors_analysed: list[str]
    tickers_covered: int
    disagreements: list[SectorDisagreement]
    shared_bottlenecks: list[SharedBottleneck]
    corroborating_themes: list[str]  # Themes all sectors agree on
    ai_demand_correlation_estimate: str  # Cross-sector AI demand sensitivity
    synthesis_confidence: ConfidenceLevel
    produced_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

#### New service: `CrossSectorSynthesisService`

This is **deterministic** — it does not require an LLM call. It takes the three `FourBoxOutput` objects and computes disagreements by comparing their `primary_risks`, `key_assumptions`, and thesis positions:

```python
# services/cross_sector_synthesis.py

class CrossSectorSynthesisService:
    """Deterministic aggregation of parallel sector outputs.
    
    No LLM call. Identifies conflicts and shared bottlenecks
    through structured comparison of FourBoxOutput fields.
    """

    def synthesise(
        self,
        sector_outputs: dict[str, list[FourBoxOutput]],
        claim_ledger: ClaimLedger,
    ) -> CrossSectorSynthesis:
        ...
```

#### Engine integration

In `stage_6_sector_analysis`, after all three parallel sector calls complete:

```python
# After parallel gather in stage_6_sector_analysis:
cross_sector = self.cross_sector_svc.synthesise(
    sector_outputs={"compute": compute_outputs, "power": power_outputs, "infra": infra_outputs},
    claim_ledger=stage_5_ledger,
)
self.stage_outputs[6]["cross_sector_synthesis"] = cross_sector.model_dump()
```

This synthesis object is then threaded into Stage 7 (valuation), Stage 9 (risk scenarios), Stage 11 (review), and Stage 12 (portfolio):

```python
# In stage_7_valuation format_input:
"cross_sector_disagreements": cross_sector.disagreements,
"shared_bottlenecks": cross_sector.shared_bottlenecks,

# In stage_9_risk format_input:
"shared_bottlenecks": cross_sector.shared_bottlenecks,  # Informs correlated-crash scenarios

# In stage_12_portfolio format_input:
"cross_sector_synthesis": cross_sector.model_dump(),  # PM must account for disagreements
```

**Gate addition for Stage 6:**
```python
# gate_6 addition:
if cross_sector.disagreements and not any(
    d.portfolio_impact for d in cross_sector.disagreements
):
    blockers.append("Cross-sector disagreements detected with no portfolio impact assessment")
```

**Acceptance criteria:**
- `CrossSectorSynthesis` is produced on every Stage 6 run with ≥2 sector analysts
- Portfolio Manager prompt explicitly receives cross-sector disagreement objects
- Stage 9 scenario stress severity accounts for shared bottleneck severity ratings
- Telemetry tracks disagreement count per run

**Estimated score uplift:** +0.2 to Stage 6, +0.2 to Stage 12, +0.1 to Stage 11

---

### L.3 — Valuation Must Explicitly Acknowledge Macro Regime Assumptions (BCH-3)

**Priority:** HIGH  
**Current state:** `MacroContextPacket` is injected into Stage 7's prompt (ARC-4 fix confirmed). However, `ValuationCard` has no mandatory field requiring the agent to declare which macro assumptions drive its DCF. A valuation can be produced without stating whether it assumes rates are flat, rising, or falling. This means the valuation and macro work run in parallel conceptually and only share context — they do not formally integrate.  
**Impact:** Regime-inconsistent valuations (e.g. bullish DCF despite hawkish macro memo) go undetected. The Reviewer and Red Team cannot flag a specific disagreement because no agreement was ever formalised.

#### Schema changes to `ValuationCard`

```python
# schemas/portfolio.py — ValuationCard extension

class MacroAssumptionAcknowledgement(BaseModel):
    """Formal declaration of macro assumptions embedded in a valuation."""
    
    # Rate regime assumption
    rate_regime: str  # "rising", "flat", "falling", "uncertain"
    rate_impact_on_wacc: str  # e.g. "WACC increased by 50bps vs neutral scenario"
    
    # Macro regime alignment
    macro_regime_used: str  # Must match MacroContextPacket.regime_label
    regime_consistent: bool  # Does this valuation's assumptions align with macro memo?
    regime_divergence_note: str = ""  # If not consistent, explain the deliberate divergence
    
    # Specific macro inputs used
    terminal_growth_rate_justification: str  # Must reference macro context
    discount_rate_basis: str  # e.g. "WACC 10.2% using current 10Y UST + equity risk premium"
    
    # Sensitivity to macro regime
    bull_macro_impact: str  # e.g. "Rate cuts → WACC -80bps → fair value +18%"
    bear_macro_impact: str  # e.g. "Prolonged hikes → WACC +120bps → fair value -24%"

class ValuationCard(BaseModel):
    # ... all existing fields ...
    macro_assumptions: MacroAssumptionAcknowledgement  # MANDATORY — no default
    dcf_assumptions_explicit: bool = False  # True only if all DCF inputs are stated
    cross_sector_alignment: str = ""  # Reference to CrossSectorSynthesis if material
```

#### Prompt engineering requirement

The `ValuationAnalystAgent` system prompt must be extended with:

```
MANDATORY: Every valuation must include a MacroAssumptionAcknowledgement block declaring:
1. The rate regime assumed (rising/flat/falling/uncertain)
2. Whether your DCF assumptions are consistent with the Macro Strategist's regime assessment
3. If inconsistent, you must explicitly justify the divergence
4. The impact on fair value of bull vs bear macro scenarios
5. Your terminal growth rate must reference the macro context provided

DO NOT produce a valuation without completing all five of the above fields.
```

#### Gate enforcement

```python
# gates.py — gate_7_valuation extension
@staticmethod
def gate_7_valuation(
    valuation_cards_count: int,
    expected_count: int,
    missing_methodology_tags: int = 0,
    cards_missing_macro_acknowledgement: int = 0,  # NEW
    regime_inconsistent_without_justification: int = 0,  # NEW
) -> GateResult:
    blockers = []
    # ... existing checks ...
    if cards_missing_macro_acknowledgement > 0:
        blockers.append(
            f"{cards_missing_macro_acknowledgement} valuation cards missing "
            f"MacroAssumptionAcknowledgement — cannot proceed without explicit rate/regime assumptions"
        )
    if regime_inconsistent_without_justification > 0:
        blockers.append(
            f"{regime_inconsistent_without_justification} valuations conflict with macro memo "
            f"without documented justification"
        )
    return GateResult(...)
```

#### What the Reviewer gains

Stage 11 (Associate Review) now receives structured `macro_assumptions` per ticker. It can explicitly flag:
- Valuations inconsistent with the macro memo
- DCF terminal growth rates incompatible with the stated rate regime
- Bull/bear macro sensitivities that contradict Stage 9's scenario stress results

**Acceptance criteria:**
- Every `ValuationCard` contains a populated `MacroAssumptionAcknowledgement`
- Gate 7 rejects runs with missing macro acknowledgements
- Stage 11 prompt explicitly receives macro assumption declarations alongside review context
- `regime_consistent: False` cases generate a specific flag in the audit packet

**Estimated score uplift:** +0.3 to Stage 7, +0.2 to Stage 11 quality, +0.2 to overall consistency

---

### L.4 — Red Team → Controlled Thesis Repair Loop (BCH-4)

**Priority:** HIGH  
**Current state:** Stage 10 (Red Team) identifies material contradictions in the thesis. Stage 11 (Review) can block on them. If blocked, the entire run fails — there is no middle path. This means a single contested name can veto the entire research output, even if 14 other names are clean.  
**Impact:** A controlled repair loop makes the architecture more resilient. It is not about making approval easier — it is about making adversarial challenge productive rather than purely destructive.

#### New typed schemas

```python
# schemas/portfolio.py — new models

class ThesisRepairRequest(BaseModel):
    """Issued by the engine when Stage 10 flags material RED findings."""
    repair_id: str
    run_id: str
    ticker: str
    stage_10_findings: list[str]  # Specific red team challenges requiring response
    challenged_claim_ids: list[str]  # Claims directly challenged
    original_sector_output_key: str  # Reference to stage_outputs[6] entry
    original_valuation_output_key: str  # Reference to stage_outputs[7] entry
    severity: str  # "material" — only material findings trigger repair
    issued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ThesisRepairResponse(BaseModel):
    """Structured response from the repair agent."""
    repair_id: str
    ticker: str
    revision_type: str  # "thesis_maintained", "thesis_qualified", "thesis_retracted"
    
    # If thesis_maintained: must rebut each red team finding explicitly
    rebuttals: dict[str, str] = {}  # {finding_id: rebuttal_text}
    
    # If thesis_qualified: state what changed
    qualification_summary: str = ""
    revised_confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    revised_sector_notes: str = ""  # Override for the specific challenged sections
    
    # If thesis_retracted: explain and remove from portfolio
    retraction_rationale: str = ""
    
    # Mandatory: cite which claims now support (or no longer support) the thesis
    supporting_claim_ids: list[str] = []
    withdrawn_claim_ids: list[str] = []
    
    repair_version: str = "REV-1"  # Stamped in artifact registry
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

#### Engine flow

```python
# In run_full_pipeline, after stage_10_red_team:

red_team_output = self.stage_outputs.get(10, {})
repair_requests = self._identify_repair_candidates(red_team_output)

if repair_requests:
    # Only trigger for material RED findings — not every yellow flag
    for request in repair_requests:
        logger.info(f"Thesis repair triggered for {request.ticker}: {request.severity}")
        repair_response = await self._run_thesis_repair(request)
        self.stage_outputs.setdefault("repairs", {})[request.ticker] = repair_response.model_dump()
        # Patch stage_outputs[7] for this ticker with revision notes
        # Stamp repair_version = "REV-1" in artifact registry

# stage_11_review now receives both original outputs AND repair responses
```

#### Trigger criteria (strict — not a soft-pass mechanism)

The repair loop triggers ONLY when:
1. Red team flags a finding as `severity = "material"` (not just "significant")
2. The finding directly challenges a core thesis claim (not a peripheral risk)
3. The ticker has a PASS valuation in Stage 7 (no point repairing an already-flagged name)

It does NOT trigger to make approval easier. It triggers to convert a binary BLOCK → REVISE → APPROVE flow into a more institutionally realistic one.

#### Safeguards

- Maximum one revision per ticker per run (`REV-1` only — no circular repairs)
- Repair responses are permanently stamped in the artifact registry alongside the originals
- Gate 11 receives both original and revised outputs; reviewer sees the full revision chain
- If `revision_type = "thesis_retracted"`, the ticker is automatically removed from portfolio candidates in Stage 12

**Acceptance criteria:**
- Repair loop triggers only for `severity = "material"` findings
- `ThesisRepairResponse` is stored as a named artifact (`repairs/{ticker}/rev1.json`)
- Gate 11 receives repair chain in full
- Retracted tickers are automatically excluded from Stage 12
- Run audit log records whether repair was invoked, for which tickers, and the outcome

**Estimated score uplift:** +0.3 to Stage 10 effectiveness, +0.2 to Stage 11 quality, +0.2 to overall resilience

---

### L.5 — PipelineEngine Decomposition (BCH-5)

**Priority:** MEDIUM-HIGH (architecture quality, not immediate feature quality)  
**Current state:** `engine.py` is 1,961 lines, managing 15 stages, ~80 imports, ~40 instantiated services, and all cross-stage state in a single class. It is the highest-risk file in the codebase — changes to any stage risk breaking others.  
**Impact:** Decomposing it improves testability, reduces merge conflicts, isolates stage regressions, and makes the engine intelligible to new contributors.

#### Target architecture

Each stage becomes a self-contained `StageExecutor`:

```python
# research_pipeline/pipeline/stages/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

@dataclass
class StageContext:
    """Shared context passed to every stage executor."""
    run_id: str
    universe: list[str]
    config: PipelineConfig
    stage_outputs: dict[int, Any]
    gates: PipelineGates

class StageResult:
    def __init__(self, stage_num: int, passed: bool, output: Any, gate_result: GateResult):
        self.stage_num = stage_num
        self.passed = passed
        self.output = output
        self.gate_result = gate_result

class BaseStageExecutor(ABC):
    stage_number: int
    stage_name: str

    @abstractmethod
    async def execute(self, ctx: StageContext) -> StageResult:
        ...

    def get_gate(self, ctx: StageContext) -> GateResult:
        ...
```

```python
# research_pipeline/pipeline/stages/stage_05_evidence.py

class Stage5Evidence(BaseStageExecutor):
    stage_number = 5
    stage_name = "Evidence Librarian / Claim Ledger"

    def __init__(self, evidence_agent: EvidenceLibrarianAgent):
        self.evidence_agent = evidence_agent

    async def execute(self, ctx: StageContext) -> StageResult:
        # All current stage_5_evidence logic moves here
        ...
```

`PipelineEngine` becomes a thin orchestrator:

```python
class PipelineEngine:
    def __init__(self, ...):
        self._stages: dict[int, BaseStageExecutor] = {
            0: Stage0Bootstrap(...),
            1: Stage1Universe(...),
            # ...
            14: Stage14Monitoring(...),
        }

    async def run_full_pipeline(self, request: RunRequest) -> FinalReport:
        ctx = StageContext(run_id=..., universe=request.universe, ...)
        execution_order = [0, 1, 2, 3, 4, 5, 6, 8, 7, 9, 10, 11, 12, 13, 14]
        for stage_num in execution_order:
            result = await self._stages[stage_num].execute(ctx)
            if not result.passed:
                await self._stages[14].execute(ctx)  # always run monitoring
                return self._build_failed_report(result)
        return self._build_final_report(ctx)
```

#### Migration approach

- Extract stages **one at a time**, starting with the simplest (Stage 0, Stage 1, Stage 14)
- Keep `engine.py` as the canonical file; move stage logic into `pipeline/stage_executors/` directory
- Each extraction is a separate PR with no functional changes — pure refactor
- Full test suite must pass after every extraction

**Acceptance criteria:**
- `engine.py` is <400 lines after extraction (down from 1,961)
- Each `StageNExecutor` has its own unit test file
- All existing tests continue to pass
- New stages can be added by creating a new `StageNExecutor` class without touching `engine.py`

**Estimated score uplift:** +0.3 to scalability, +0.2 to implementation quality score, +0.2 to testability

---

### L.6 — Schema Versioning & Artifact Reproducibility (BCH-6)

**Priority:** MEDIUM  
**Current state:** Pydantic models have no version field. When schemas evolve between pipeline versions, artifacts written by an older run cannot be safely loaded by a newer engine. There is no explicit versioning strategy.  
**Impact:** Production operational risk. Different engine versions produce subtly different artifacts with no way to detect or manage the difference.

#### Implementation

**Step 1 — Versioned schema mixin**

```python
# schemas/_base.py — new file

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"  # Bump this when any schema adds/removes required fields

class VersionedSchema(BaseModel):
    """Base for all stage output schemas that are persisted to disk."""
    schema_version: str = Field(default=SCHEMA_VERSION, frozen=True)
    pipeline_version: str = Field(default="v8.0", frozen=True)
```

Apply to all persisted stage output models:

```python
class ClaimLedger(VersionedSchema):  # was BaseModel
    ...

class FourBoxOutput(VersionedSchema):
    ...

class ValuationCard(VersionedSchema):
    ...

class CrossSectorSynthesis(VersionedSchema):  # new — already versioned
    ...
```

**Step 2 — Version check on artifact load**

```python
# services/run_registry.py — add to load_stage_output():
def load_stage_output(self, run_id: str, stage: int) -> dict:
    data = json.loads(path.read_text())
    if "schema_version" in data:
        loaded_version = data["schema_version"]
        if loaded_version != SCHEMA_VERSION:
            logger.warning(
                f"Schema version mismatch loading Stage {stage} from run {run_id}: "
                f"artifact is {loaded_version}, engine expects {SCHEMA_VERSION}. "
                f"Field compatibility not guaranteed."
            )
    return data
```

**Step 3 — Compatibility matrix in docs**

A `SCHEMA_CHANGELOG.md` must be maintained:

```markdown
## v1.1 → v1.2 (Stage 7)
Added: ValuationCard.macro_assumptions (required)
Migration: Existing v1.1 artifacts missing this field will fail Gate 7 on reload.
Mitigation: Set macro_assumptions to MacroAssumptionAcknowledgement.default() for legacy loads.
```

**Acceptance criteria:**
- Every persisted schema model inherits `VersionedSchema`
- `run_registry.py` warnings on version mismatch
- `SCHEMA_CHANGELOG.md` exists and is updated with every breaking schema change
- Golden test suite includes a backward-compatibility test loading a v1.0 artifact with v1.1 engine

---

### L.7 — Macro Grounding Verification & Completion (BCH-7)

**Priority:** HIGH (closes the single largest accuracy gap)  
**Current state:** Session 12 added `EconomyAnalystAgent`, `EconomicIndicatorService`, and `MacroScenarioService`. These exist in the codebase but the depth of their wiring into Stage 8's prompt context is unverified. Review B scored external macro grounding at 5/10, calling it "the biggest real PM office gap." If Session 12 is fully wired, the score rises to 7.5+. If partially wired, the gap remains.

#### Verification required

Run `grep -n "EconomicIndicatorService\|EconomyAnalystAgent\|MacroScenarioService\|economic_indicators\|economy_analysis"` against `engine.py` Stage 8 implementation and confirm each of the following:

| Check | Required Evidence | Status |
|---|---|---|
| `EconomicIndicatorService.fetch()` called in Stage 8 | Line reference in `stage_8_macro` | ⬜ Verify |
| `EconomicIndicators` object passed to `MacroStrategistAgent.format_input()` | Prompt dict entry | ⬜ Verify |
| `EconomyAnalystAgent.run()` called with live indicators | Not just `{"universe": universe}` | ⬜ Verify |
| `MacroScenario` (3-scenario matrix) passed to Stage 9 scenario engine | `stage_outputs[8]` consumption in `stage_9_risk` | ⬜ Verify |
| RBA cash rate in Stage 8 prompt when AU tickers in universe | Field present in `economic_indicators` | ⬜ Verify |
| Fed funds rate in Stage 8 prompt when US tickers in universe | Field present in `economic_indicators` | ⬜ Verify |

#### Completion work (if any checks fail)

```python
# stage_8_macro — required input structure:
format_input = {
    "universe": universe,
    "ingestion_summary": self.stage_outputs.get(2, {}),          # ARC-9
    "reconciliation_flags": self.stage_outputs.get(3, {}),       # ARC-9
    "economic_indicators": economic_indicators.model_dump(),      # NEW — must be present
    "economy_analysis": economy_analysis.model_dump(),            # NEW — must be present
    "macro_scenarios": macro_scenarios.model_dump(),              # NEW — must be present
    "sector_context": self.stage_outputs.get(6, {}),             # Cross-sector synthesis
}
```

#### Macro propagation completeness audit

After Stage 8 wiring is confirmed, audit every downstream stage that consumes `_get_macro_context()` and verify it passes **all** relevant macro fields:

```
Stage 7  — rate_regime, terminal_growth_assumption, wacc_delta  ← BCH-3 addresses this
Stage 9  — macro_scenarios (3-scenario severity), bear_case_rate_shock
Stage 10 — regime_label, rate_direction (for macroeconomically-challenged theses)
Stage 11 — full MacroContextPacket + EconomyAnalysis summary
Stage 12 — regime_conditional_weights, rate_sensitivity_by_sector
```

**PoliticalContextPacket gap:** Political risk analysis has no equivalent typed packet downstream. Add:

```python
# schemas/macro.py — new model
class PoliticalContextPacket(BaseModel):
    """Typed political risk context for downstream stage consumption."""
    run_id: str
    key_risk_countries: list[str]
    tariff_risk_level: str  # "elevated", "moderate", "low"
    geopolitical_regime: str  # "stable", "volatile", "crisis"
    supply_chain_risk_score: float  # 0.0 – 1.0
    specific_ticker_risks: dict[str, str] = {}  # ticker → risk description
    produced_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

**Acceptance criteria:**
- All six verification checks above pass
- `EconomicIndicators` fields are present in Stage 8 prompt (verifiable from telemetry logs)
- Stage 9 macro-scenario severity is driven by `MacroScenario` data, not synthetic defaults
- `PoliticalContextPacket` produced and consumed by Stage 10 and Stage 11

**Estimated score uplift:** +0.4 to macro grounding (5/10 → 7.5+), +0.2 to Stage 9, +0.2 overall accuracy

---

### L.8 — Documentation & Configuration Fidelity (BCH-8)

**Priority:** MEDIUM (trust and operational discipline rather than runtime quality)  
**Current state:** Both independent reviews and the cross-analysis independently identified documentation fidelity as a persistent ceiling (6.5/10). Three specific types of drift exist:
1. Stage ordering — `PIPELINE_STAGES.md` still shows Stage 7 before Stage 8 in its flow diagram
2. Session 13 additions — `ReportNarrativeAgent` is undocumented in `ARCHITECTURE.md`
3. Australian institutional layer — `sector_analyst_asx.py`, `superannuation_mandate.py`, `australian_tax_service.py` are not mentioned in any architecture document
4. `configs/thresholds.yaml` — reconciliation thresholds that drive `gate_3_reconciliation` must be documented alongside the gate logic

#### Specific changes required

**PIPELINE_STAGES.md — fix stage flow diagram:**

```markdown
## Stage flow diagram (actual execution order)

[0] Bootstrap & Configuration
        ↓
[1] Universe Definition
        ↓
[2] Data Ingestion          ← Deterministic
[3] Reconciliation          ← Deterministic
[4] Data QA & Lineage       ← Deterministic
        ↓
[5] Evidence Librarian / Claim Ledger   ← LLM ★
        ↓
[6] Sector Analysis                     ← LLM ★ (3× parallel + cross-sector synthesis)
        ↓
[8] Macro & Political Overlay           ← LLM ★ (runs BEFORE Stage 7 — ARC-4)
        ↓
[7] Valuation & Modelling               ← LLM ★ + Deterministic DCF (macro-aware)
        ↓
[9] Quant Risk & Scenario Testing       ← Deterministic + LLM ★
        ↓
[10] Red Team Analysis                  ← LLM ★
        ↓
    [10a] Thesis Repair (conditional)   ← LLM ★ (material RED findings only)
        ↓
[11] Associate Review / Publish Gate    ← LLM ★ + Governance gate
        ↓
[12] Portfolio Construction             ← LLM ★ + Deterministic optimiser
        ↓
[13] Report Assembly                    ← Deterministic template + ReportNarrativeAgent LLM ★
        ↓
[14] Monitoring & Audit                 ← Deterministic (always executes)
```

**ARCHITECTURE.md — add Session 13 section:**

Document `ReportNarrativeAgent`: its role, the five sections it generates, and its non-blocking `_VALIDATION_FATAL = False` pattern.

**ARCHITECTURE.md — add Australian institutional layer section:**

Document the three ASX/AU files and explain their role in the multi-mandate framework.

**configs/thresholds.yaml — add documentation header:**

```yaml
# configs/thresholds.yaml
# 
# CRITICAL: These thresholds directly govern gate_3_reconciliation() in gates.py.
# Changing them affects what data divergences are considered "blocking RED" vs "amber".
# 
# red_threshold: Divergence % at which gate_3 BLOCKS the pipeline
# amber_threshold: Divergence % that generates a warning but allows continuation
#
# Review gate_3 logic in src/research_pipeline/pipeline/gates.py before modifying.
```

**Acceptance criteria:**
- `PIPELINE_STAGES.md` stage flow diagram shows Stage 8 before Stage 7
- `ARCHITECTURE.md` documents `ReportNarrativeAgent` and the Australian layer
- `configs/thresholds.yaml` has header comments explaining gate connection
- A documentation review is part of the PR checklist for all future engine changes

---

### L.9 — First-Class RunRequest Multi-Tenancy (BCH-9)

**Priority:** MEDIUM  
**Current state:** `RunRequest` schema and `ClientProfile` exist in `schemas/run_request.py` and `schemas/client_profile.py`. The architecture can conceptually support multiple client types. However, `run_full_pipeline()` still takes `universe: list[str]` in several code paths rather than a `RunRequest`, and mandate constraints are not uniformly passed through all stages.  
**Impact:** Commercial viability for multiple fund types (retail, institutional, superannuation, family office) depends on this working end-to-end.

#### Engine signature change

```python
# Before:
async def run_full_pipeline(self, universe: list[str]) -> FinalReport:

# After:
async def run_full_pipeline(self, request: RunRequest) -> FinalReport:
    universe = request.universe
    client_profile = request.client_profile  # ClientProfile or None → default mandate
    mandate = request.mandate_config         # MandateConfig or None → permissive defaults
```

#### Per-stage mandate threading

Every stage that applies portfolio constraints must receive the mandate:

```python
# Stage 9 (Risk) — mandate determines concentration thresholds
"mandate_max_single_name_pct": mandate.max_single_name_pct,

# Stage 12 (Portfolio) — hard limits from mandate
"mandate_rules": [r.model_dump() for r in mandate.rules],
"mandate_esg_exclusions": mandate.esg_exclusion_list,

# Stage 13 (Report) — report format from client_profile
"report_format": client_profile.preferred_report_format,
"benchmark": client_profile.benchmark,
```

#### Supporting schemas already in place

`MandateRule.hard_limit: bool` already distinguishes blocking from warning violations.
`MandateComplianceEngine` already enforces rules from `MandateConfig`.
`superannuation_mandate.py` already implements AU super-specific rules.

The work here is **threading**, not schema design — the schema architecture is correct.

**Acceptance criteria:**
- `run_full_pipeline(request: RunRequest)` signature is canonical across all call paths
- Running with a superannuation `ClientProfile` produces a mandate-compliant portfolio automatically
- Running with US institutional vs AU retail profiles produces different ESG exclusions and concentration limits
- `CLIand Streamlit UI both pass `RunRequest` to the engine

---

### L.10 — Cancellation, Backpressure & Partial Results (BCH-10)

**Priority:** MEDIUM  
**Current state:** Both reviews scored this at 5.2–5.5/10. Long-running pipeline executions cannot be cancelled mid-stage; there is no graceful degradation path for partial failures; partial results from failed runs are not surfaced usefully.

#### Required additions

**Cancellation token pattern:**

```python
# In run_full_pipeline:
import asyncio

async def run_full_pipeline(self, request: RunRequest, cancel_token: asyncio.Event | None = None) -> FinalReport:
    for stage_num in execution_order:
        if cancel_token and cancel_token.is_set():
            logger.info(f"Pipeline cancelled before Stage {stage_num}")
            await self._stages[14].execute(ctx)  # always write audit on cancel
            return self._build_cancelled_report(ctx, cancelled_at_stage=stage_num)
        result = await self._stages[stage_num].execute(ctx)
        ...
```

**Per-stage timeout:**

```python
# In BaseStageExecutor:
DEFAULT_STAGE_TIMEOUT_SECONDS = 300  # 5 minutes per stage

async def execute_with_timeout(self, ctx: StageContext) -> StageResult:
    try:
        return await asyncio.wait_for(self.execute(ctx), timeout=self.timeout_seconds)
    except asyncio.TimeoutError:
        return StageResult(
            stage_num=self.stage_number,
            passed=False,
            output={},
            gate_result=GateResult(self.stage_number, False, f"Stage {self.stage_number} timed out after {self.timeout_seconds}s")
        )
```

**Partial results API endpoint:**

```python
# api/routes/runs.py — new endpoint:
@router.get("/runs/{run_id}/partial")
async def get_partial_results(run_id: str):
    """Return whatever stage outputs are available for an in-progress or failed run."""
    ...
```

**Acceptance criteria:**
- `cancel_token` parameter accepted by `run_full_pipeline`
- Cancelled runs write a `cancellation_record` to the audit packet
- Each stage has a configurable timeout (default 300s)
- Stage 14 (monitoring) always executes on cancel, timeout, or failure
- `/runs/{run_id}/partial` endpoint returns available stage outputs

---

### L.11 — 10 Priority-Ordered Quick Wins (BCH-QW)

These are smaller improvements identified in the assessment that each take < 1 session to implement:

| ID | Item | Location | Effort | Impact |
|---|---|---|---|---|
| QW-1 | Add `concentration_breach_disclosure` field to `RiskPacket` — `gate_9` warns but disclosure obligation is not formally tracked | `schemas/reports.py`, `gate_9` | 1h | Medium |
| QW-2 | `CommitteeRecord.is_approved` — verify IC service is called in all publication paths, not only specific mandate configs | `services/investment_committee.py` | 2h | High |
| QW-3 | ResearchMemory population — add explicit `memory.store_run()` call at Stage 14 for every successful run | `engine.py` Stage 14 | 1h | Medium |
| QW-4 | Memory injection in Stage 5 — evidence librarian should query prior claim ledgers for the same tickers before generating new claims | `agents/evidence_librarian.py` | 2h | High |
| QW-5 | Add `SchemaVersionMixin` to all persisted schemas and bump checks in `run_registry.py` | `schemas/_base.py`, `services/run_registry.py` | 3h | Medium |
| QW-6 | `_VALIDATION_FATAL = False` audit — review all agent classes; any agent where failure should be blocking must have `True` explicitly set | All agents in `agents/` | 2h | High |
| QW-7 | `scheduler.py` — add failure alerting: if a scheduled run fails, emit an alert event to `ObservabilityService` | `services/scheduler.py` | 1h | Medium |
| QW-8 | Stage 1 gate strength — add minimum market cap and liquidity floor checks to `gate_1_universe` | `gates.py`, `schemas/market_data.py` | 3h | Medium |
| QW-9 | `gate_10_red_team` — `all_have_min_falsifications` is currently agent-self-reported; add deterministic verification by counting `falsification_paths` in `RedTeamAssessment` | `gates.py`, `schemas/portfolio.py` | 2h | High |
| QW-10 | Thread `PoliticalContextPacket` (BCH-7 new schema) through Stages 10 and 11 once schema is defined | `engine.py` Stages 10, 11 | 2h | Medium |

---

### L.12 — Score Progression Targets

| After completing | Expected backend score |
|---|---|
| Current baseline (Sessions 1–18 complete) | 7.9/10 |
| BCH-7 (macro wiring verified + completed) | 8.2/10 |
| BCH-1 (claim ledger as live contract) | 8.5/10 |
| BCH-3 (valuation macro acknowledgement) | 8.7/10 |
| BCH-2 (cross-sector synthesis schema) | 8.8/10 |
| BCH-4 (thesis repair loop) + BCH-8 (doc fidelity) | 9.0/10 |
| BCH-5 (engine decomposition) + BCH-6 (schema versioning) | 9.2/10 |
| BCH-9 (multi-tenancy) + BCH-10 (cancellation) + BCH-QW all | **9.4/10** |

---

### L.13 — Implementation Sequencing

```
PHASE L-A — Contract Foundations (Sessions 19–20)
│
├── BCH-7  Verify + complete macro wiring (session 19, first)
├── BCH-1  Claim ledger as live contract — schema changes + gate changes
├── BCH-3  ValuationCard macro acknowledgement — schema + prompt + gate
└── BCH-8  Documentation fidelity — PIPELINE_STAGES.md, ARCHITECTURE.md, thresholds comment

PHASE L-B — Cross-Stage Intelligence (Sessions 21–22)
│
├── BCH-2  CrossSectorSynthesis schema + CrossSectorSynthesisService
├── BCH-4  ThesisRepairRequest/Response schemas + engine flow
└── BCH-QW Quick wins QW-1 through QW-10

PHASE L-C — Architecture Evolution (Sessions 23–25)
│
├── BCH-5  PipelineEngine decomposition (multiple PRs — one stage per PR)
├── BCH-6  Schema versioning + SCHEMA_CHANGELOG.md
├── BCH-9  RunRequest multi-tenancy threading
└── BCH-10 Cancellation + backpressure + partial results API
```

Each phase is independently deployable. Phase L-A improves contract quality without changing any topology. Phase L-B adds two new typed data structures and one new engine path. Phase L-C is architectural refactoring with no runtime behaviour change.

---

### L.14 — Summary Statistics (Part L)

| Category | Count |
|---|---|
| Critical contract hardening items (BCH-1 to BCH-4) | 4 |
| Architecture evolution items (BCH-5 to BCH-6) | 2 |
| Data grounding + documentation items (BCH-7 to BCH-8) | 2 |
| Operational maturity items (BCH-9 to BCH-10) | 2 |
| Quick wins (BCH-QW-1 to BCH-QW-10) | 10 |
| New schemas required | 8 |
| Schema modifications to existing models | 6 |
| New services required | 2 |
| Gate changes required | 5 |
| **Total Part L tracked improvements** | **20 items + schemas** |

**Combined total (all parts):** ~174 tracked improvements

---

*Part L added March 2026 based on `BACKEND_ARCHITECTURE_ASSESSMENT.md` cross-analysis. Sequencing targets Sessions 19–25. Each BCH item has explicit acceptance criteria and can be verified independently.*

---

## Part M — Data Sourcing Quality & New API Integration (Session 19)

> **Source:** Dual independent sourcing analysis cross-compared in `BACKEND_ARCHITECTURE_ASSESSMENT.md` §9  
> **Date added:** March 29, 2026  
> **Current data quality ceiling:** Usable for structured quantitative overview; not suitable for high-conviction institutional decisions without manual primary-source verification at the investment stage  
> **Target after Session 19:** Primary-source grounded evidence, live qualitative evidence in the headless engine path, three new APIs integrated with proper tiering  
> **New API keys available in `.env`:** `SEC_API_KEY`, `BENZINGA_API_KEY`, `NEWS_API_KEY`

---

### Context: The Evidence Gap

Two independent analyses converged on the same core finding, code-verified: the platform's biggest bottleneck is not LLM reasoning quality — it is source quality and the wiring of existing qualitative services into the live engine path.

**The confirmed live-engine sourcing state (March 2026):**

| Path | Gets qualitative data | Notes |
|---|---|---|
| Streamlit `pipeline_runner.py` | Yes — full `QualitativeDataService` package | Rich: transcripts, news, filings metadata, insider, sentiment |
| **Headless CLI / API `ResearchPipelineEngine`** | **No** | Only `tickers` + Stage 2 `market_data` passed to Stage 5 |

Every run through the API (which is what the Next.js frontend calls) is running a qualitatively hollow evidence stage. This single code gap has more impact on output quality than any prompt change.

**Source tier reality vs aspiration:**

| Tier | Aspiration (Evidence Librarian prompt) | Reality (live engine) |
|---|---|---|
| Tier 1 | SEC filings, 10-K/Q/8-K | FMP filing metadata links only — no text content |
| Tier 2 | Reuters, Bloomberg, FT, WSJ | Not retrieved — no news feed wired at all |
| Tier 3 | Analyst consensus, Yahoo Finance | FMP + Finnhub aggregator snapshots |
| Tier 4 | House research | Prior run claim ledger (when wired) |

The Evidence Librarian prompt aspires to Tier 1 sourcing; the live retrieval layer delivers Tier 3 maximum. This is a grounding mismatch — the Claims it generates look well-sourced while the underlying evidence layer does not support that standard.

---

### New API Evaluation Summary

| API | Role | Tier | Priority | Where it wires |
|---|---|---|---|---|
| **SEC API (sec-api.io)** — `SEC_API_KEY` | Primary US filings: 10-K/Q/8-K section extraction, XBRL financials, Form 4 insider, real-time 8-K events | Tier 1 | **Must add — highest impact** | Stages 2, 3, 5, 7, 10 |
| **Benzinga** — `BENZINGA_API_KEY` | Finance-native news, analyst rating changes, earnings catalysts, transcript enrichment | Tier 2 | **Strong yes — second priority** | Stages 2, 5, 10 |
| **NewsAPI** — `NEWS_API_KEY` | Broad news for macro/regulatory/geopolitical scanning | Tier 4 | **Conditional — prerequisites required first** | Stage 8 only |

---

### Session 19 Steps

| Step | ID | Task | Division | Effort | Files |
|---|---|---|---|---|---|
| 1 | DSQ-1 | Wire `QualitativeDataService` into `ResearchPipelineEngine` Stage 5 — no new API needed; closes the biggest live gap immediately | Global Research | Low | `engine.py`, `qualitative_data_service.py` |
| 2 | DSQ-2 | `SECApiService` — new service wrapping sec-api.io; filing index per ticker, latest 10-K/Q/8-K metadata, 8-K real-time events | Global Research | Medium | `src/research_pipeline/services/sec_api_service.py` |
| 3 | DSQ-3 | Wire SEC API into Stage 2 data ingestion — per-ticker latest filings index, 8-K material events; add to ingestion bundle | Data Infrastructure | Medium | `engine.py`, `sec_api_service.py` |
| 4 | DSQ-4 | Wire SEC API into Stage 5 Evidence Librarian — 10-K MD&A and Risk Factors section extraction; Form 4 insider data; XBRL key facts | Global Research | High | `engine.py`, `sec_api_service.py` |
| 5 | DSQ-5 | `BenzingaService` — new service wrapping Benzinga API; analyst rating changes, earnings catalysts, finance-native company news | Global Research | Medium | `src/research_pipeline/services/benzinga_service.py` |
| 6 | DSQ-6 | Wire Benzinga into Stage 2 — analyst rating changes and earnings events; demote FMP/Finnhub news to backfill role | Data Infrastructure | Medium | `engine.py`, `benzinga_service.py` |
| 7 | DSQ-7 | Wire Benzinga into Stage 5 — finance-native qualitative evidence alongside SEC API sections | Global Research | Medium | `engine.py`, `benzinga_service.py` |
| 8 | DSQ-8 | Wire Benzinga adverse signals (downgrades, negative catalysts) into Stage 10 Red Team inputs | Global Research | Low | `engine.py` |
| 9 | DSQ-9 | `ArticleExtractionService` — fetch full article text from URL, clean body, strip nav/ads, chunk for prompt injection. Prerequisite for NewsAPI. | Data Infrastructure | Medium | `src/research_pipeline/services/article_extraction_service.py` |
| 10 | DSQ-10 | `NewsApiService` with publisher allowlist — allowlisted publishers only (Reuters, AP, FT, WSJ, Bloomberg, Ars Technica, The Information); topic/entity filtering; `ArticleExtractionService` pipeline | Data Infrastructure | Medium | `src/research_pipeline/services/news_api_service.py` |
| 11 | DSQ-11 | Wire NewsAPI into Stage 8 Macro/Political — macro/regulatory/geopolitical news: export controls, AI regulation, grid policy, chip sanctions | Global Research | Low | `engine.py`, `news_api_service.py` |
| 12 | DSQ-12 | Expand Stage 3 reconciliation — add XBRL-derived fundamentals cross-check against FMP for key metrics (revenue, operating income, EPS); flag discrepancies | Data Infrastructure | Medium | `consensus_reconciliation.py`, `sec_api_service.py` |
| 13 | DSQ-13 | Wire `fetch_fmp_ratios` into `ingest_ticker` — this method exists in `market_data_ingestor.py` but is not called in the default Stage 2 bundle; adds ROE, ROIC, FCF yield, debt/equity | Data Infrastructure | Low | `market_data_ingestor.py` |
| 14 | DSQ-14 | Synthetic data contamination tagging — wherever `LiveReturnStore` falls back to synthetic returns, explicitly tag outputs with `data_source: "synthetic"` in `RiskPacket`, `AttributionPacket`, and `SelfAuditPacket.synthetic_fields` | Investment Governance | Medium | `risk_engine.py`, `live_return_store.py`, `governance.py` |
| 15 | DSQ-15 | `tests/test_session19.py` — 40+ tests covering all DSQ items; mock API responses; verify engine wiring; verify synthetic tagging | Operations | Medium | `tests/test_session19.py` |
| 16 | DSQ-16 | Update `configs/settings.py` (or equivalent) to read `SEC_API_KEY`, `BENZINGA_API_KEY`, `NEWS_API_KEY` from environment; add to `PipelineConfig` API keys model | Operations | Low | `src/research_pipeline/config/loader.py`, `settings.py` |

---

### DSQ-1: Wire QualitativeDataService into Engine (Detail)

This is the highest-impact, lowest-effort item on this list. It requires zero new external APIs.

**What the code already has:**
- `QualitativeDataService` exists at `src/research_pipeline/services/qualitative_data_service.py`
- It fetches: company news + press releases (FMP + Finnhub), earnings transcripts (FMP), SEC filing metadata (FMP), analyst recommendations (FMP), insider trading (FMP), analyst estimates (FMP), social sentiment (FMP + Finnhub)
- It is fully wired and tested in the Streamlit `pipeline_runner.py` path
- It is NOT called anywhere in `ResearchPipelineEngine.run_full_pipeline()`

**The required change in `engine.py`:**

```python
# In stage_5_evidence_librarian (or before calling evidence_agent.run):

# Call qualitative service for all universe tickers
qualitative_data = {}
if self.settings.qualitative_enabled:  # Feature flag — default True
    for ticker in universe:
        qual = await self.qualitative_svc.fetch_qualitative(ticker)
        qualitative_data[ticker] = qual.model_dump()

# Pass to evidence agent
result = await self.evidence_agent.run(
    self.run_record.run_id,
    {
        "tickers": universe,
        "market_data": self.stage_outputs.get(2, []),
        "qualitative_data": qualitative_data,  # NEW — closes the gap
        "sec_filing_sections": sec_sections,   # DSQ-4 (later)
        "benzinga_events": benzinga_events,    # DSQ-7 (later)
    },
)
```

**Acceptance:** A run where all APIs return valid data results in the Evidence Librarian prompt containing transcript excerpts, news headlines, and insider activity — not just price/consensus data.

---

### DSQ-2 / DSQ-3 / DSQ-4: SEC API Integration (Detail)

**What `SECApiService` should expose:**

```python
# src/research_pipeline/services/sec_api_service.py

class SECApiService:
    """
    Wraps sec-api.io endpoints for primary-source US filing access.
    Rate limit: depends on plan (free tier: 100 req/day).
    US-listed companies only — ASX tickers not covered.
    """

    async def get_latest_filings_index(
        self, ticker: str, form_types: list[str] = ["10-K", "10-Q", "8-K"]
    ) -> list[FilingMetadata]:
        """Stage 2: filing index per ticker — metadata only, no content."""
        ...

    async def get_section_text(
        self, accession_number: str, section: str
    ) -> str:
        """Stage 5: extract specific section from a 10-K or 10-Q.
        sections: '1A' (Risk Factors), '7' (MD&A), '7A' (Quant Disclosures)
        Chunked to <4000 tokens for prompt safety.
        """
        ...

    async def get_recent_8k_events(
        self, ticker: str, days_back: int = 30
    ) -> list[MaterialEvent]:
        """Stage 2 + Stage 10: material 8-K events — earnings, guidance changes,
        M&A, restatements, management changes."""
        ...

    async def get_insider_transactions(
        self, ticker: str, days_back: int = 90
    ) -> list[InsiderTransaction]:
        """Stage 5 + Stage 10: Form 3/4 insider transactions.
        Replaces FMP insider aggregation with primary SEC source."""
        ...

    async def get_xbrl_facts(
        self, ticker: str, concepts: list[str]
    ) -> dict[str, Any]:
        """Stage 3: XBRL-structured financial facts for cross-validation.
        Key concepts: us-gaap/Revenues, us-gaap/NetIncomeLoss,
        us-gaap/EarningsPerShareBasic, us-gaap/OperatingIncomeLoss
        """
        ...
```

**Pydantic models to add:**

```python
# src/research_pipeline/schemas/qualitative.py — additions

class FilingMetadata(BaseModel):
    ticker: str
    form_type: str  # "10-K", "10-Q", "8-K"
    accession_number: str
    filed_at: datetime
    period_of_report: str
    is_material_event: bool = False

class MaterialEvent(BaseModel):
    ticker: str
    accession_number: str
    event_type: str  # "earnings", "guidance_change", "restatement", etc.
    filed_at: datetime
    summary: str
    full_text_url: str
    is_adverse: bool = False  # Set True for restatements, going-concern, etc.

class InsiderTransaction(BaseModel):
    ticker: str
    insider_name: str
    title: str
    transaction_type: str  # "buy", "sell", "gift", etc.
    shares: int
    price_per_share: float
    transaction_date: datetime
    form_type: str  # "Form 3", "Form 4", "Form 5"
    is_cluster_signal: bool = False  # True if multiple insiders transacting same direction

class FilingSection(BaseModel):
    ticker: str
    form_type: str
    accession_number: str
    section_code: str  # "1A", "7", "7A"
    section_title: str
    content_chunks: list[str]  # <4000 tokens each
    total_tokens: int
    source_tier: str = "TIER_1_PRIMARY"  # Always Tier 1 for SEC filings
```

**Critical ASX limitation note:** SEC API covers EDGAR only. For ASX-listed names in the universe, fall back to `QualitativeDataService` FMP/Finnhub paths. Log a warning. ASX primary-source parity (via `data.asx.com.au` announcement API) is a future item.

---

### DSQ-5 / DSQ-6 / DSQ-7 / DSQ-8: Benzinga Integration (Detail)

**What `BenzingaService` should expose:**

```python
# src/research_pipeline/services/benzinga_service.py

class BenzingaService:
    """
    Wraps Benzinga API endpoints for finance-native qualitative intelligence.
    Better than FMP/Finnhub for: analyst rating changes, earnings catalysts,
    event-driven news. Demotes FMP/Finnhub to backfill role for news.
    """

    async def get_analyst_ratings(
        self, ticker: str, days_back: int = 30
    ) -> list[AnalystRatingChange]:
        """Stage 2 + Stage 5: analyst rating changes with price targets.
        Replaces FMP upgrades-downgrades as primary rating-change source."""
        ...

    async def get_news(
        self, ticker: str, days_back: int = 14
    ) -> list[FinanceNewsItem]:
        """Stage 5: finance-native news. Higher signal than FMP/Finnhub
        aggregations. Deduped against FMP/Finnhub news by URL hash."""
        ...

    async def get_earnings_calendar(
        self, ticker: str
    ) -> EarningsEvent | None:
        """Stage 2: earnings date, expected EPS, expected revenue.
        Cross-check against Finnhub calendar."""
        ...

    async def get_adverse_signals(
        self, ticker: str, days_back: int = 30
    ) -> list[AdverseSignal]:
        """Stage 10 Red Team: downgrade clusters, negative catalyst events,
        miss-and-lower patterns. Structured for adversarial use."""
        ...
```

**Source demotions after Benzinga integration:**

| Area | Before | After |
|---|---|---|
| Primary news source | FMP `stock_news` + Finnhub `company-news` | **Benzinga** (primary); FMP + Finnhub (backfill/dedup) |
| Analyst rating changes | FMP `analyst-stock-recommendations` | **Benzinga** (primary); FMP (backfill) |
| Earnings calendar | Finnhub `calendar/earnings` | **Benzinga** + Finnhub cross-check |
| Adverse signals for Red Team | None (currently no adverse signal feed) | **Benzinga** adverse events |

---

### DSQ-9 / DSQ-10 / DSQ-11: NewsAPI Integration (Detail — prerequisites mandatory)

**Prerequisites before wiring NewsAPI into any stage:**

1. `ArticleExtractionService` must be built and tested (DSQ-9)
2. Publisher allowlist must be configured in `configs/pipeline.yaml`
3. Entity/topic filter must be applied before storing articles
4. Do NOT wire into Stage 5 evidence — Tier 4 sources do not belong in the primary claim ledger

**Publisher allowlist (minimum viable):**

```yaml
# configs/pipeline.yaml — new section
news_api:
  allowed_publishers:
    - reuters.com
    - apnews.com
    - ft.com
    - wsj.com
    - bloomberg.com
    - theatlantic.com
    - technologyreview.mit.edu
    - theinformation.com
    - semafor.com
    - arstechnica.com
  blocked_publishers:
    - yahoo.com    # aggregator
    - msn.com      # aggregator
    - seeking-alpha.com  # community, not editorial
  max_articles_per_run: 30
  max_age_days: 7
  ai_infra_topics:
    - "semiconductor"
    - "data center"
    - "AI chip"
    - "export control"
    - "TSMC"
    - "NVIDIA"
    - "grid interconnection"
    - "AI regulation"
    - "chip sanctions"
    - "hyperscaler capex"
```

**Stage 8 integration (only):**

```python
# In stage_8_macro format_input:
"macro_news": news_api_svc.get_policy_news(
    topics=["AI export controls", "semiconductor regulation",
            "grid interconnection", "data center permitting",
            "Federal Reserve", "RBA", "inflation"],
    days_back=7,
    max_articles=20,
),
```

**What NewsAPI does NOT replace:** company-specific earnings, analyst ratings, or any fact that should have Tier 1 citation in the claim ledger. It is only for macro and regulatory backdrop.

---

### DSQ-13: Wire `fetch_fmp_ratios` into `ingest_ticker` (Detail)

A silent gap identified by code inspection: `fetch_fmp_ratios()` method exists in `market_data_ingestor.py` but is not called within `ingest_ticker()`. This means ratio-rich fundamentals are absent from the default Stage 2 bundle.

**Fields currently missed:**
- ROE (Return on Equity)
- ROIC (Return on Invested Capital)
- FCF yield
- Debt/equity
- Current ratio
- Gross margin, operating margin
- Revenue growth TTM

**Fix:** Add to `ingest_ticker()`:

```python
# In MarketDataIngestor.ingest_ticker():
for fetch_fn, key in [
    (self.fetch_fmp_quote,             "fmp_quote"),
    (self.fetch_fmp_price_targets,     "fmp_targets"),
    (self.fetch_fmp_analyst_estimates, "fmp_estimates"),
    (self.fetch_fmp_ratios,            "fmp_ratios"),  # ADD THIS
]:
    ...
```

Cost: one additional FMP API call per ticker per run. Value: sector agents and valuation agent receive ROE, ROIC, FCF yield without needing a separate service call path.

---

### DSQ-14: Synthetic Data Contamination Tagging (Detail)

When `LiveReturnStore` falls back to synthetic returns, the downstream VaR and attribution figures are partially fictitious. This is not currently disclosed to the user or to downstream agents.

**Required changes:**

```python
# src/research_pipeline/services/risk_engine.py — RiskPacket additions
class RiskPacket(BaseModel):
    # ... existing fields ...
    returns_data_source: Literal["live", "synthetic", "mixed"] = "synthetic"
    synthetic_tickers: list[str] = []  # Which tickers used synthetic returns
    data_quality_warning: str = ""  # Human-readable warning if synthetic

# src/research_pipeline/schemas/governance.py — SelfAuditPacket addition
class SelfAuditPacket(BaseModel):
    # ... existing fields ...
    synthetic_data_fields: list[str] = []  # e.g. ["var_returns_NVDA", "attribution_AVGO"]
    data_quality_flags: dict[str, str] = {}  # field → warning message
```

**In `_get_returns()` helper:** when a ticker falls back to synthetic, add it to `synthetic_tickers`. Surface this in Stage 9 telemetry and in the final report's audit appendix.

---

### Revised Source Hierarchy Post-Session 19

| Tier | Sources | Used in stages |
|---|---|---|
| **Tier 1 — Primary truth** | SEC API (10-K/Q sections, XBRL, Form 4, 8-K events) | 2, 3, 5, 7, 10 |
| **Tier 2 — Finance event/news** | Benzinga (ratings, catalysts, news), QualitativeDataService (transcripts, insider) | 2, 5, 10 |
| **Tier 3 — Structured market data** | FMP (quotes, fundamentals, estimates, ratios), Finnhub (price cross-check, consensus) | 2, 3, 6, 7 |
| **Tier 4 — Broad macro/discovery** | NewsAPI (allowlisted, Stage 8 only), FRED (macro indicators) | 8 |
| **Tier 5 — Fallback only** | yfinance (price fallback, historical returns), synthetic fills | 2, 9 (tagged) |

---

### Division Score Impact After Session 19

| Division | Current Score | After Session 19 | Delta | Primary Driver |
|---|---|---|---|---|
| Global Research | ~9.2 | **9.5** | +0.3 | SEC API + Benzinga in Evidence Librarian; QualitativeDataService wired to engine |
| Data Sourcing Quality (new) | ~4.5 | **7.5** | +3.0 | From aggregator-only to primary-source grounded |
| Investment Governance | ~9.4 | **9.5** | +0.1 | Synthetic data contamination tagging; audit trail honesty |
| Quantitative Research | ~9.2 | **9.3** | +0.1 | FMP ratios in Stage 2; XBRL cross-validation in reconciliation |
| Operations & Technology | ~9.1 | **9.2** | +0.1 | Three new services with proper API key management |

---

### Session 19 Acceptance Criteria

**P0 — gating (must all pass before session is complete):**
- [ ] `QualitativeDataService` called from `ResearchPipelineEngine.run_full_pipeline()` before Stage 5
- [ ] Stage 5 `format_input` dict contains `qualitative_data` key with real content in a live run
- [ ] `SEC_API_KEY`, `BENZINGA_API_KEY`, `NEWS_API_KEY` resolved from environment in `PipelineConfig`
- [ ] `SECApiService`, `BenzingaService`, `NewsApiService` all instantiable with live keys
- [ ] 40+ new tests in `tests/test_session19.py`; all passing

**P1 — quality (all should pass):**
- [ ] Stage 2 ingestion bundle includes `filing_index` and `8k_events` from SEC API for US tickers
- [ ] Stage 5 evidence prompt receives at least one SEC filing section excerpt for S&P 500 names
- [ ] Stage 2 uses Benzinga as primary analyst rating change source
- [ ] Stage 8 receives allowlisted NewsAPI macro/regulatory headlines
- [ ] Stage 10 Red Team receives Benzinga adverse signals
- [ ] Stage 3 reconciliation has at least one XBRL vs FMP consistency check
- [ ] `fetch_fmp_ratios` called in `ingest_ticker()`
- [ ] Synthetic returns flagged in `RiskPacket.returns_data_source`

**Residual gaps acknowledged (not in scope for Session 19):**
- ASX primary-source documents (requires ASX API or ASIC integration — future session)
- Full transcript parsing pipeline (guidance extraction, tagged capex/margin commentary — future session)
- EIA / FERC power grid data — valuable for AI infra thesis but outside this session
- ESG live data — remains heuristic until a proper ESG data source is added

---

### Session 19 Files Changed

| File | Change |
|---|---|
| `src/research_pipeline/services/sec_api_service.py` | **NEW** — full `SECApiService` |
| `src/research_pipeline/services/benzinga_service.py` | **NEW** — full `BenzingaService` |
| `src/research_pipeline/services/news_api_service.py` | **NEW** — `NewsApiService` with publisher allowlist |
| `src/research_pipeline/services/article_extraction_service.py` | **NEW** — URL → clean article text |
| `src/research_pipeline/schemas/qualitative.py` | Extended: `FilingMetadata`, `MaterialEvent`, `InsiderTransaction`, `FilingSection`, `AnalystRatingChange`, `AdverseSignal` |
| `src/research_pipeline/schemas/governance.py` | Extended: `SelfAuditPacket.synthetic_data_fields`, `data_quality_flags` |
| `src/research_pipeline/pipeline/engine.py` | Stage 2 (SEC + Benzinga ingest), Stage 3 (XBRL cross-check), Stage 5 (full qual wiring), Stage 8 (NewsAPI macro), Stage 10 (Benzinga adverse) |
| `src/research_pipeline/services/market_data_ingestor.py` | Add `fetch_fmp_ratios` call in `ingest_ticker()` |
| `src/research_pipeline/services/risk_engine.py` | `RiskPacket.returns_data_source`, `synthetic_tickers` fields |
| `src/research_pipeline/config/loader.py` | Add new API keys to `PipelineConfig.api_keys` |
| `configs/pipeline.yaml` | `news_api` publisher allowlist section |
| `tests/test_session19.py` | **NEW** — 40+ tests |

---

*Part M added March 29, 2026 based on dual independent sourcing analysis cross-compared in `BACKEND_ARCHITECTURE_ASSESSMENT.md` §9. Session 19 is the data sourcing quality uplift before Part L backend contract hardening resumes at Session 20.*

---

## Part N — Data Sourcing: Sector Intelligence & Platform Hardening (Session 20)

> **Source:** Gap analysis of `BACKEND_ARCHITECTURE_ASSESSMENT.md` §9.6–§9.9 against Part M coverage, March 2026  
> **Prerequisite:** Session 19 (Part M, DSQ-1 through DSQ-16) complete  
> **Scope:** Items confirmed missing from Part M that are needed for institutional-grade evidence quality — sector-native intelligence, AU market parity, freshness/provenance infrastructure, multi-API reliability, and political risk grounding  
> **Numbering:** DSQ-17 through DSQ-26, plus platform hardening quick wins

---

### Context: What Part M Left Scheduled But Unplanned

Part M's "Residual gaps acknowledged" section names four items out of scope for Session 19. Section 9.6 of `BACKEND_ARCHITECTURE_ASSESSMENT.md` identifies several additional gaps that never received specific DSQ items in Part M but are material to the platform's analytical ceiling. This section gives each one a concrete implementation specification.

**The five categories of gaps:**

| Category | Severity | Part M Coverage | Status |
|---|---|---|---|
| EIA/FERC/ISO-RTO public power data | High — free sources, AI infra thesis critical | Mentioned §9.8 as "third phase step 9" | **No DSQ item, no plan** |
| ASX announcement API (AU ticker parity) | High — AU names entirely ungrounded | Noted as "future item" | **No concrete plan** |
| Sector-native intelligence (WSTS, semiconductor, hyperscaler capex) | High — differentiated insight for the vertical | Listed as §9.6 gap | **No DSQ item** |
| Platform data integrity (freshness, rate-limits, deduplication) | Medium — will degrade at scale | Not addressed | **Not mentioned in Part M** |
| Political risk stage overhaul | Medium-High — currently training-data only | DSQ-11 adds headlines only | **Insufficient** |

---

### Session 20 Steps

| Step | ID | Task | Division | Effort | Files |
|---|---|---|---|---|---|
| 1 | DSQ-17 | `DataFreshnessCatalog` — field-level freshness tracking for every fetched field; track source, fetch_time, staleness_minutes, freshness_tier per field per ticker | Data Infrastructure | Medium | `src/research_pipeline/services/data_freshness_service.py`, `schemas/provenance.py` |
| 2 | DSQ-18 | `RateLimitBudgetManager` — centralised multi-API quota tracking; per-service daily/minute budgets; graceful degradation order when quotas exhausted; emits warnings before hard limits | Operations | Medium | `src/research_pipeline/services/rate_limit_manager.py` |
| 3 | DSQ-19 | `SourceRankingService` — publisher trust scores (0.0–1.0), URL-hash deduplication across all news services, source diversity enforcement (no single publisher dominates a ticker's evidence pack) | Data Infrastructure | Medium | `src/research_pipeline/services/source_ranking_service.py` |
| 4 | DSQ-20 | `EIAService` — US Energy Information Administration public API; electricity generation capacity, power prices (LMP), generation by fuel type, data centre power demand projections | AI Infrastructure Research | Medium | `src/research_pipeline/services/eia_service.py` |
| 5 | DSQ-21 | `FERCService` — FERC EQIS and ISO-RTO interconnection queue data; pending/approved data centre interconnection requests by ISO region (PJM, ERCOT, CAISO, MISO); grid capacity headroom | AI Infrastructure Research | Medium | `src/research_pipeline/services/ferc_service.py` |
| 6 | DSQ-22 | Wire EIA + FERC into Stage 8 — alongside NewsAPI: US grid stress, generation capacity by region, interconnection queue length and wait times as quantitative macro inputs for AI infra thesis | Global Research | Low | `engine.py`, `eia_service.py`, `ferc_service.py` |
| 7 | DSQ-23 | `ASXAnnouncementService` — ASX public REST announcements API (`data.asx.com.au`); latest company announcements by ticker, category filtering (periodic reports, substantial holder notices, material events); parity with SEC API for AU-listed names | Global Research | Medium | `src/research_pipeline/services/asx_announcement_service.py` |
| 8 | DSQ-24 | Wire ASX announcements into Stage 2 and Stage 5 for AU-listed tickers — conditional: US tickers → SEC API path; AU tickers → ASX announcement path; flag non-US/non-AU tickers as primary-source dark | Data Infrastructure | Low | `engine.py`, `asx_announcement_service.py` |
| 9 | DSQ-25 | `TranscriptParserService` — given a raw transcript text (from QualitativeDataService/Benzinga), parse and tag: guidance statements (EPS/revenue), capex commentary, margin language, demand commentary, supply constraints, management tone; output structured `ParsedTranscript` schema | Global Research | High | `src/research_pipeline/services/transcript_parser_service.py`, `schemas/qualitative.py` |
| 10 | DSQ-26 | Wire `TranscriptParserService` into Stage 5 — replace raw transcript injection with structured `ParsedTranscript`; Evidence Librarian receives tagged guidance + capex + margin commentary as distinct evidence fields | Global Research | Medium | `engine.py`, `transcript_parser_service.py` |
| 11 | DSQ-27 | Political risk stage overhaul — Stage 8's `PoliticalRiskAnalystAgent` currently receives only `{"tickers": universe}` and has zero live data; wire in: (a) NewsAPI allowlisted regulatory/geopolitical headlines (DSQ-11), (b) EIA/FERC grid data (DSQ-22), (c) structured regulatory event schema; add `RegulatoryEventPacket` to Stage 8 output | Global Research | Medium | `engine.py`, `political_risk_analyst_agent.py`, `schemas/macro.py` |
| 12 | DSQ-28 | `WSSTService` facade for WSTS/SEMI public semiconductor data — WSTS publishes monthly semiconductor shipment data (free); SEMI publishes North America equipment book-to-bill (free); wire into Stage 6 sector analysis for compute names | AI Infrastructure Research | Medium | `src/research_pipeline/services/wsts_service.py` |
| 13 | DSQ-29 | Hyperscaler capex extraction — using `SECApiService` (DSQ-4) and `TranscriptParserService` (DSQ-25), extract capex figures and guidance from MSFT/AMZN/GOOG/META 10-K/10-Q XBRL facts and earnings transcripts; build `HyperscalerCapexTracker` for Stage 6 and Stage 8 | AI Infrastructure Research | High | `src/research_pipeline/services/hyperscaler_capex_tracker.py` |
| 14 | DSQ-30 | `.env.example` completeness fix — add `FINNHUB_API_KEY`, `SEC_API_KEY`, `BENZINGA_API_KEY`, `NEWS_API_KEY`, `EIA_API_KEY` to `.env.example` with inline comments describing what each covers; closes ISS-7 (blocks new developer onboarding cold) | Operations | Low | `.env.example`, `PROJECT_ISSUES_ASSESSMENT.md` |
| 15 | DSQ-31 | Direct company IR scraper — `IRScraperService` subscribing to IR RSS feeds for key universe companies; triggers when a material announcement is not yet in SEC API or ASX announcement feed; rate-limited, robots.txt-respecting; feeds Stage 5 and Stage 10 | Data Infrastructure | High | `src/research_pipeline/services/ir_scraper_service.py` |
| 16 | DSQ-32 | `tests/test_session20.py` — 50+ tests covering all DSQ-17 through DSQ-31 items; mock EIA/FERC/ASX API responses; verify freshness tracking, rate-limit budget enforcement, transcript parsing output schema | Operations | Medium | `tests/test_session20.py` |

---

### DSQ-17: Field-Level Data Freshness Tracking (Detail)

The QA service checks run-level timestamps but does not track freshness per data field. A PE ratio fetched 10 days ago and an earnings transcript from 6 months ago are treated with equal recency weight in the evidence pack — this is a silent quality failure.

**`DataFreshnessCatalog` design:**

```python
# src/research_pipeline/services/data_freshness_service.py

from enum import Enum

class FreshnessTier(str, Enum):
    LIVE      = "live"       # < 15 minutes (real-time APIs)
    INTRADAY  = "intraday"   # < 4 hours (same session)
    DAILY     = "daily"      # < 24 hours (EOD snapshots)
    RECENT    = "recent"     # < 7 days
    STALE     = "stale"      # 7–30 days
    EXPIRED   = "expired"    # > 30 days — flag in evidence

class FieldFreshness(BaseModel):
    field_key: str          # e.g. "NVDA.pe_ratio", "NVDA.transcript_2024Q4"
    ticker: str
    source_service: str     # "fmp", "sec_api", "benzinga", "qualitative_data_svc"
    fetch_time: datetime
    value_period: str       # What time period the value covers (e.g. "2024-Q3")
    freshness_tier: FreshnessTier
    staleness_minutes: int

class DataFreshnessCatalog(BaseModel):
    run_id: str
    fields: dict[str, FieldFreshness] = {}  # field_key → FieldFreshness
    stale_fields: list[str] = []    # keys where freshness_tier ∈ {STALE, EXPIRED}
    expired_fields: list[str] = []  # keys where > 30 days

    def register(self, field_key: str, freshness: FieldFreshness) -> None: ...
    def get_stale_summary(self) -> str: ...  # Human-readable staleness report
```

**Integration points:**
- All service calls (`fetch_fmp_quote`, `get_section_text`, `get_news`, etc.) should register their result into the run's `DataFreshnessCatalog`
- `SelfAuditPacket` should include a `stale_data_fields` list when any field is STALE or EXPIRED
- Stage 5 Evidence Librarian prompt should receive a staleness note when evidence is > 7 days old

**Acceptance:** A run produces a per-field freshness catalogue. The `SelfAuditPacket` flags any field older than 7 days with its source and fetch time.

---

### DSQ-18: Multi-API Rate-Limit Budget Manager (Detail)

Adding SEC API, Benzinga, NewsAPI, EIA, and FERC alongside existing FMP and Finnhub creates 6+ concurrent API services with distinct rate-limit regimes. Without coordination, the first production run to process a 20-ticker universe will hit hard limits on multiple services simultaneously with no graceful fallback.

**`RateLimitBudgetManager` design:**

```python
# src/research_pipeline/services/rate_limit_manager.py

class ServiceQuotaConfig(BaseModel):
    service_name: str
    daily_limit: int | None       # None = unlimited
    per_minute_limit: int | None
    per_second_limit: float | None
    current_day_usage: int = 0
    current_minute_usage: int = 0
    fallback_service: str | None  # What to use when this quota exhausted

class RateLimitBudgetManager:
    """
    Centralised multi-API quota tracking and graceful degradation.
    All service wrappers call check_quota() before making API requests.
    Degrades in a defined order; never silently drops data without logging.
    """

    degradation_order: list[str] = [
        # When a service is exhausted, fall back to the next available
        "sec_api",       # → fall back to FMP filing metadata
        "benzinga",      # → fall back to FMP/Finnhub news
        "news_api",      # → Stage 8 Macro runs without news feed (logs warning)
        "fmp",           # → fall back to Finnhub
        "finnhub",       # → fall back to yfinance
        "eia",           # → Stage 8 runs without power data (logs warning)
        "ferc",          # → Stage 8 runs without interconnection data (logs warning)
    ]

    def check_quota(self, service_name: str) -> bool: ...
    def record_usage(self, service_name: str, count: int = 1) -> None: ...
    def get_budget_summary(self) -> dict[str, ServiceQuotaConfig]: ...
    def get_fallback(self, service_name: str) -> str | None: ...
```

**Integration:** Each service wrapper's `__init__` takes an optional `rate_limit_manager`. If provided, all calls go through `check_quota()` before execution. The engine instantiates one `RateLimitBudgetManager` per run and passes it to all services at startup.

**Acceptance:** A simulated run that exhausts the FMP daily quota gracefully falls back to Finnhub; exhausting Finnhub falls back to yfinance. All quota events logged in `SelfAuditPacket.data_quality_flags`.

---

### DSQ-20 / DSQ-21 / DSQ-22: EIA + FERC + Stage 8 Integration (Detail)

These are **free, official US government data sources** that directly support the AI infrastructure thesis. No API subscription cost. Very high ROI.

**EIA API (api.eia.gov):**

```python
class EIAService:
    """
    US Energy Information Administration public REST API (free with API key).
    Provides electricity generation, capacity, prices, demand forecasts.
    Directly relevant to: data center power cost, grid availability,
    renewable energy transition speed for AI infra thesis.
    """

    async def get_power_prices(
        self, region: str = "US48"
    ) -> list[PowerPricePoint]:
        """Average retail electricity prices (commercial/industrial) by region."""
        ...

    async def get_generation_capacity(
        self, region: str | None = None
    ) -> GenerationCapacitySummary:
        """Total utility-scale generation capacity by fuel type, by region.
        Key for: 'can the grid support data center expansion?'"""
        ...

    async def get_datacenter_power_demand_forecast(self) -> PowerDemandForecast:
        """EIA published data center electricity demand projections through 2030.
        Direct quant input for AI infrastructure grid capacity thesis."""
        ...
```

**FERC EQIS (queues.ferc.gov — public REST API):**

```python
class FERCService:
    """
    FERC Electric Queues Information System — interconnection queue data.
    Free public REST API. Shows pending/approved power plant interconnection
    requests by ISO region (PJM, ERCOT, CAISO, MISO, SPP, NYISO, ISO-NE).
    Key thesis signal: how long does a new data center have to wait to
    get a grid connection? Current waits: 3-7 years in some regions.
    """

    async def get_queue_summary(
        self, iso: str = "ALL"
    ) -> InterconnectionQueueSummary:
        """Count of pending requests, MW requested, type (solar/wind/storage/load).
        'Load' requests are effectively data center interconnection requests."""
        ...

    async def get_load_queue_by_region(self) -> dict[str, LoadQueueStats]:
        """MW of large-load interconnection requests queued per ISO region.
        CAISO and PJM queues are the most relevant for US hyperscaler expansion."""
        ...
```

**Stage 8 macro input additions (alongside NewsAPI DSQ-11):**

```python
# In stage_8_macro format_input:
"power_grid_data": {
    "us_electricity_price_commercial_cents_kwh": eia_svc.get_power_prices(),
    "grid_generation_capacity_summary": eia_svc.get_generation_capacity(),
    "datacenter_power_demand_forecast": eia_svc.get_datacenter_power_demand_forecast(),
    "interconnection_queue_load_mw": ferc_svc.get_load_queue_by_region(),
},
```

**Acceptance:** Stage 8 `MacroContextPacket` contains a `power_grid_context` field populated from EIA/FERC data. `MacroPowerGridPacket` added to schemas. Political and macro agents can quantify grid capacity constraints in AI infra thesis.

---

### DSQ-23 / DSQ-24: ASX Announcement API (AU Ticker Parity) (Detail)

SEC API covers US (EDGAR) only. For ASX-listed names (XRO, WTC, ALU, PME, NXT, etc.) there is currently no primary-source filing path.

**ASX Public Announcements API:**

```python
class ASXAnnouncementService:
    """
    ASX public announcements API at data.asx.com.au.
    Free, no authentication required for public announcements.
    Covers all ASX-listed companies; announcements in PDF and structured metadata.
    Equivalent role to SEC API's 8-K + 10-K/Q filing index for AU tickers.
    """

    BASE_URL = "https://www.asx.com.au/asx/1/company/{ticker}/announcements"

    async def get_recent_announcements(
        self, asx_ticker: str, days_back: int = 30
    ) -> list[ASXAnnouncement]:
        """Recent company announcements — annual/half-year reports,
        appendix 4E/4D, material change notices, substantial holder forms.
        Maps to SEC filing categories: periodic = 10-K/Q equivalent;
        material change = 8-K equivalent."""
        ...

    async def get_periodic_reports(
        self, asx_ticker: str
    ) -> list[ASXAnnouncement]:
        """Filtered: annual reports, half-year results, quarterly cash flows.
        Primary financial statement documents."""
        ...

    async def get_material_events(
        self, asx_ticker: str, days_back: int = 30
    ) -> list[ASXAnnouncement]:
        """Filtered: change of activities, material contracts, market updates,
        strategic updates. Equivalent to 8-K material events."""
        ...
```

**Ticker routing logic in engine.py:**

```python
def _is_asx_ticker(ticker: str) -> bool:
    """ASX tickers: typically 3-char uppercase with optional .AX suffix."""
    return ticker.endswith(".AX") or (len(ticker) <= 3 and ticker.isupper())

# In stage_2_data_ingestion and stage_5_evidence_librarian:
for ticker in universe:
    if _is_asx_ticker(ticker):
        filing_data[ticker] = await asx_svc.get_recent_announcements(ticker)
        filing_source[ticker] = "asx_announcement_api"
    elif _is_us_ticker(ticker):
        filing_data[ticker] = await sec_api_svc.get_latest_filings_index(ticker)
        filing_source[ticker] = "sec_api"
    else:
        filing_data[ticker] = None
        filing_source[ticker] = "primary_source_dark"  # Logged warning
        log.warning(f"Ticker {ticker} has no primary-source filing path")
```

**Acceptance:** An ASX-listed ticker in the universe receives `ASXAnnouncement` evidence in Stage 5 equivalent to what US tickers receive from SEC API. `filing_source` field logged per ticker in `SelfAuditPacket`.

---

### DSQ-25 / DSQ-26: Transcript Parsing Pipeline (Detail)

Raw transcript injection is currently prompt-size limited and unstructured. A full transcript is 15,000–40,000 tokens; the evidence stage truncates aggressively. This wastes the highest-quality qualitative evidence source: management's own guidance words.

**`ParsedTranscript` schema and parser:**

```python
# src/research_pipeline/schemas/qualitative.py — additions

class GuidanceStatement(BaseModel):
    category: Literal["eps", "revenue", "capex", "margin", "volume", "timing", "other"]
    speaker_role: Literal["ceo", "cfo", "ir", "analyst"]
    raw_text: str           # Exact quote
    metric: str | None      # Structured: "EPS guidance FY25"
    direction: Literal["raise", "maintain", "lower", "initiate", "withdraw"] | None
    confidence: Literal["explicit", "implied"]
    quarter: str            # "2024-Q3"

class ManagementToneSignal(BaseModel):
    topic: str             # "AI demand", "data center supply", "margin"
    tone: Literal["positive", "neutral", "cautious", "negative"]
    evidence_quote: str

class ParsedTranscript(BaseModel):
    ticker: str
    quarter: str
    guidance_statements: list[GuidanceStatement] = []
    capex_commentary: list[str] = []          # Direct capex quotes
    demand_commentary: list[str] = []         # Demand/pipeline language
    supply_constraint_mentions: list[str] = []
    margin_commentary: list[str] = []
    tone_signals: list[ManagementToneSignal] = []
    revision_vs_prior: str | None = None      # If parseable vs prior quarter
    raw_word_count: int = 0
    parse_confidence: float = 0.0             # 0.0–1.0

# src/research_pipeline/services/transcript_parser_service.py
class TranscriptParserService:
    """
    LLM-assisted transcript parser. Takes raw transcript text, returns
    ParsedTranscript with structured guidance and tagged commentary.
    Uses a small targeted model call (not the full research pipeline LLM)
    to extract structured data. Results cached by (ticker, quarter) to
    avoid re-parsing on re-runs.
    """

    async def parse(
        self, ticker: str, quarter: str, raw_text: str
    ) -> ParsedTranscript:
        ...

    async def get_revision_delta(
        self, ticker: str, current: ParsedTranscript, prior: ParsedTranscript
    ) -> GuidanceRevisionDelta:
        """Q-o-Q guidance revision: raise/maintain/lower vs prior guidance."""
        ...
```

**What Stage 5 Evidence Librarian receives after DSQ-26:**
Instead of a raw truncated transcript blob, the evidence pack includes:
- Structured guidance statements tagged by category and direction
- Capex and demand commentary as discrete quoted items
- A revision delta vs prior quarter (if available in research memory)
- Management tone signals on key thesis topics

**Acceptance:** A run with QualitativeDataService transcript data produces `ParsedTranscript` in the evidence pack for at least one ticker. Evidence Librarian prompt contains structured commentary fields rather than raw text truncation.

---

### DSQ-27: Political Risk Stage Overhaul (Detail)

Stage 8's `PoliticalRiskAnalystAgent` currently has the most severe sourcing gap in the entire pipeline: it receives only `{"tickers": universe}` and has **zero live data input**. The agent is generating geopolitical and regulatory analysis entirely from LLM training-cutoff knowledge. In a universe with material exposure to:

- US chip export controls (BIS Entity List, October 2023 and 2024 rules, mirrors, country-by-country restrictions)
- EU AI Act implementation timelines
- Data centre permitting (FERC, local grid authorities, moratoriums in some regions)
- Grid interconnection policy changes
- TSMC/ASML-relevant trade and technology transfer restrictions

...this is a material analytical risk, not just a footnote.

**What DSQ-27 adds on top of DSQ-11 (NewsAPI headlines):**

```python
# New schema: src/research_pipeline/schemas/macro.py (additions)

class RegulatoryEvent(BaseModel):
    event_type: Literal[
        "export_control", "ai_regulation", "grid_policy",
        "chip_sanctions", "trade_restriction", "data_center_permitting",
        "antitrust", "tax_policy"
    ]
    jurisdiction: str
    headline: str
    source: str
    published_at: datetime
    affected_tickers: list[str] = []  # Universe members explicitly named
    is_adverse: bool = False
    severity: Literal["watch", "material", "critical"]

class RegulatoryEventPacket(BaseModel):
    run_id: str
    events: list[RegulatoryEvent] = []
    most_adverse: list[RegulatoryEvent] = []   # Top 3 by severity + recency
    affected_ticker_map: dict[str, list[str]] = {}  # ticker → event_ids

# Stage 8 format_input additions:
"regulatory_events": regulatory_event_packet.model_dump(),
"power_grid_context": eia_ferc_context.model_dump(),
"macro_news_headlines": news_api_svc.get_policy_news(...),  # DSQ-11
```

**Political risk agent prompt must receive all three, not just news headlines.** A dedicated `RegulatoryEventDetector` (lightweight LLM pass over the NewsAPI +  Benzinga feeds) should classify articles into `RegulatoryEvent` instances before they reach the Stage 8 prompt.

**Acceptance:** Stage 8 `MacroContextPacket` contains a non-empty `regulatory_events` list for any run where NewsAPI returns results touching the universe tickers' regulatory landscape. At least one `RegulatoryEvent` object classified from live news per run.

---

### DSQ-28: Semiconductor Vertical Data — WSTS/SEMI (Detail)

The platform analyses AI infrastructure names — NVDA, AMD, AVGO, AMAT, ASML, and others. Generic equity news and SEC filings cannot generate differentiated insight on:

- GPU shipment volumes and pricing trends
- Memory (HBM3/HBM3E) pricing and supply tightness
- Semiconductor equipment order book trends (AMAT, LRCX, KLAC thesis signals)
- Wafer start trends (TSMC, Samsung — supply constraint indicators)

**Free public sources:**

| Source | Covers | Access | Update frequency |
|---|---|---|---|
| WSTS (World Semiconductor Trade Statistics) | Global semiconductor shipments by category | Free public monthly reports (PDF/CSV) | Monthly |
| SEMI | North America equipment book-to-bill ratio | Free press releases | Monthly |
| SEMI | Fab equipment billings by region | Free public reports | Quarterly |

**`WSSTService` facade:**

```python
class WSTSService:
    """
    Parses WSTS monthly shipment data (public reports) and SEMI equipment
    book-to-bill releases for semiconductor market context.
    Primarily scraped/parsed from public press release pages.
    Updates: monthly. Cache aggressively (TTL=7 days).
    """

    async def get_latest_shipment_data(self) -> SemiconductorShipmentSnapshot:
        """Latest WSTS monthly report: total market, memory, logic, analog,
        discrete, sensors. Month-on-month and year-on-year change."""
        ...

    async def get_equipment_book_to_bill(self) -> EquipmentBookToBill:
        """SEMI NA equipment book-to-bill ratio.
        > 1.0 indicates expanding backlog (positive for AMAT/LRCX/KLAC).
        < 1.0 indicates contracting orders."""
        ...
```

**Wire into Stage 6:** Sector analysis agents for compute names receive `semiconductor_market_context` containing the latest WSTS snapshot and equipment B2B ratio as quant backdrop.

---

### DSQ-29: Hyperscaler Capex Extraction (Detail)

The highest-ROI specific data extraction task for the AI infrastructure thesis. Hyperscaler capex is the primary demand driver for GPU, HBM, networking, and data centre construction names.

**Sources:** MSFT, AMZN, GOOG, META quarterly 10-Q XBRL facts + earnings transcript capex commentary.

**`HyperscalerCapexTracker`:**

```python
class HyperscalerCapexData(BaseModel):
    hyperscaler: Literal["MSFT", "AMZN", "GOOG", "META"]
    quarter: str
    capex_reported_usd_billions: float | None
    capex_yoy_growth_pct: float | None
    capex_guidance_next_q: str | None      # From transcript parser
    ai_capex_proportion_commentary: str | None  # Direct quote if parseable
    data_center_specifics: list[str] = []  # Relevant data center capex quotes
    source_xbrl: bool = False
    source_transcript: bool = False

class HyperscalerCapexTracker:
    """
    Aggregates capex data from XBRL facts (SECApiService) and transcript
    commentary (TranscriptParserService) for the four major hyperscalers.
    Output feeds Stage 6 sector analysis and Stage 8 macro context.
    """

    async def get_latest_capex_snapshot(self) -> dict[str, HyperscalerCapexData]:
        """Returns {hyperscaler: data} for the most recent reported quarter."""
        ...

    async def get_capex_trend(
        self, hyperscaler: str, quarters: int = 4
    ) -> list[HyperscalerCapexData]:
        """Trailing-N-quarter capex trend for acceleration/deceleration detection."""
        ...
```

**Wire into Stage 8 macro context** as `hyperscaler_capex_context` — the macro prompt should use it to contextualise AI hardware demand.

---

### DSQ-30: `.env.example` / Developer Onboarding Fix (Detail)

ISS-7 (from `PROJECT_ISSUES_ASSESSMENT.md`) identified that `FINNHUB_API_KEY` is absent from `.env.example`. After Session 19 adds three more API keys, this needs a comprehensive fix.

**Required `.env.example` additions:**

```bash
# --- Market Data (Quantitative Layer) ---
FMP_API_KEY=your_financial_modeling_prep_key  # https://financialmodelingprep.com
FINNHUB_API_KEY=your_finnhub_key              # https://finnhub.io — Closes ISS-7

# --- Primary Source / Filing Layer ---
SEC_API_KEY=your_sec_api_key                  # https://sec-api.io — US SEC filings
                                               # Free tier: 100 req/day

# --- Finance News + Events Layer ---
BENZINGA_API_KEY=your_benzinga_key            # https://developer.benzinga.com
                                               # Analyst ratings, earnings catalysts

# --- Macro / Political Discovery Layer ---
NEWS_API_KEY=your_news_api_key                # https://newsapi.org
                                               # Restricted to Stage 8 macro only

# --- Public Infrastructure Data (Free) ---
EIA_API_KEY=your_eia_key                      # https://api.eia.gov/bulk/register.php
                                               # Free. US electricity/grid data.
# FERC EQIS — No API key required (public REST API)
# ASX Announcements — No API key required (public API)
# WSTS/SEMI — No API key required (public press releases)
```

**Also update** `README.md` developer setup section to list all API keys with tier descriptions (required vs optional) and free tier limitations.

**Acceptance:** `python -c "from src.research_pipeline.config.loader import PipelineConfig; PipelineConfig()"` does not raise `KeyError` or `ValidationError` when all keys are set per `.env.example`. New developer setup documented.

---

### Source Hierarchy After Sessions 19 + 20

| Tier | Sources | Used in stages |
|---|---|---|
| **Tier 1 — Primary truth** | SEC API (US — 10-K/Q/8-K/Form 4), ASX Announcement API (AU), direct IR RSS (DSQ-31) | 2, 3, 5, 7, 10 |
| **Tier 2 — Finance event** | Benzinga (ratings, catalysts, news), QualitativeDataService (transcripts, insider, FMP filings metadata) | 2, 5, 10 |
| **Tier 2.5 — Parsed insights** | TranscriptParserService (structured guidance), HyperscalerCapexTracker, WSTSService | 6, 7, 8 |
| **Tier 3 — Structured market data** | FMP (quotes, estimates, fundamentals), Finnhub (price cross-check, consensus) | 2, 3, 6, 7 |
| **Tier 4 — Macro/discovery** | NewsAPI (allowlisted Stage 8 only), FRED (macro indicators), EIA (power data), FERC (interconnection queues) | 8 |
| **Tier 5 — Fallback only** | yfinance (price history fallback), synthetic fills (always tagged) | 2 fallback, 9 (tagged per DSQ-14) |

---

### Session 20 Acceptance Criteria

**P0 — gating:**
- [ ] `DataFreshnessCatalog` records per-field freshness and surfaces stale fields in `SelfAuditPacket`
- [ ] `RateLimitBudgetManager` prevents any service from exceeding its daily quota without graceful fallback
- [ ] EIA public API call succeeds and `MacroContextPacket` contains `power_grid_context`
- [ ] FERC interconnection queue data present in Stage 8 inputs
- [ ] ASX-listed ticker in universe receives `ASXAnnouncement` evidence in Stage 5
- [ ] US ticker pipeline routes to SEC API; AU ticker routes to ASX API; others log `primary_source_dark`
- [ ] 50+ new tests in `tests/test_session20.py`; all passing
- [ ] `.env.example` contains all 6+ API key entries with documentation comments

**P1 — quality:**
- [ ] `TranscriptParserService` produces `ParsedTranscript` with non-empty `guidance_statements` for major US tickers
- [ ] Stage 5 receives structured transcript fields rather than raw text truncation
- [ ] Stage 8 `PoliticalRiskAnalystAgent` receives `RegulatoryEventPacket` in its format_input
- [ ] `WSTSService` produces `SemiconductorShipmentSnapshot` and it flows into Stage 6 for compute names
- [ ] `HyperscalerCapexTracker` populates Stage 8 macro context with latest hyperscaler capex data
- [ ] `SourceRankingService` deduplicates news URL hashes across Benzinga and NewsAPI
- [ ] `fetch_fmp_ratios` absent-ticker gap validated still closed (regression from DSQ-13)

**Residual gaps acknowledged (not in scope for Session 20):**
- ESG live data — remains heuristic until a proper ESG data provider is onboarded (BloombergESG/MSCI are institutional-tier; Sustainalytics has an API; Arabesque is free-tier)
- Quartr transcript API — verify coverage and pricing; may deprecate the need for direct IR scraping
- Non-US/non-AU international tickers — no primary-source filing path identified yet
- GPU/HBM spot pricing data — TrendForce and DRAMeXchange are subscription-only; no free equivalent identified

---

### Session 20 Files Changed

| File | Change |
|---|---|
| `src/research_pipeline/services/data_freshness_service.py` | **NEW** — `DataFreshnessCatalog`, `FieldFreshness`, `FreshnessTier` |
| `src/research_pipeline/services/rate_limit_manager.py` | **NEW** — `RateLimitBudgetManager`, `ServiceQuotaConfig` |
| `src/research_pipeline/services/source_ranking_service.py` | **NEW** — `SourceRankingService` with publisher trust scores and URL-hash deduplication |
| `src/research_pipeline/services/eia_service.py` | **NEW** — EIA REST API wrapper (free) |
| `src/research_pipeline/services/ferc_service.py` | **NEW** — FERC EQIS interconnection queue wrapper (free) |
| `src/research_pipeline/services/asx_announcement_service.py` | **NEW** — ASX announcement API wrapper (free) |
| `src/research_pipeline/services/transcript_parser_service.py` | **NEW** — `TranscriptParserService` with `ParsedTranscript` output |
| `src/research_pipeline/services/wsts_service.py` | **NEW** — WSTS/SEMI data facade |
| `src/research_pipeline/services/hyperscaler_capex_tracker.py` | **NEW** — `HyperscalerCapexTracker` using SEC API + TranscriptParserService |
| `src/research_pipeline/services/ir_scraper_service.py` | **NEW** — IR RSS scraper (robots.txt-respecting) |
| `src/research_pipeline/schemas/qualitative.py` | Extended: `ASXAnnouncement`, `ParsedTranscript`, `GuidanceStatement`, `ManagementToneSignal`, `GuidanceRevisionDelta`, `SemiconductorShipmentSnapshot`, `EquipmentBookToBill`, `HyperscalerCapexData` |
| `src/research_pipeline/schemas/macro.py` | Extended: `RegulatoryEvent`, `RegulatoryEventPacket`, `MacroPowerGridPacket`, `InterconnectionQueueSummary` |
| `src/research_pipeline/schemas/governance.py` | Extended: `SelfAuditPacket.stale_data_fields`, `primary_source_dark_tickers` |
| `src/research_pipeline/pipeline/engine.py` | Stage 2 (ASX routing), Stage 5 (structured transcripts, ASX), Stage 6 (WSTS, hyperscaler capex), Stage 8 (EIA/FERC/regulatory events), Stage 10 (regulatory adverse events) |
| `src/research_pipeline/agents/political_risk_analyst_agent.py` | `format_input` receives `RegulatoryEventPacket`; prompt updated |
| `.env.example` | All 6+ API keys with inline documentation comments |
| `README.md` | Developer setup section updated with API key tiers |
| `tests/test_session20.py` | **NEW** — 50+ tests |

---

### Division Score Impact After Sessions 19 + 20

| Division | After Session 19 | After Session 20 | Delta | Primary Driver |
|---|---|---|---|---|
| Global Research | 9.5 | **9.7** | +0.2 | Structured transcripts; ASX parity; political risk grounding |
| Data Sourcing Quality | 7.5 | **9.0** | +1.5 | EIA/FERC free sources; ASX filing parity; freshness tracking; rate-limit hardening |
| Sector & Theme Intelligence (new) | — | **8.0** | new | WSTS; hyperscaler capex tracker; interconnection queues; extensible to all sectors |
| Investment Governance | 9.5 | **9.6** | +0.1 | Freshness catalog in audit trail; primary_source_dark transparency |
| Operations & Technology | 9.2 | **9.4** | +0.2 | Rate-limit manager; source ranking; developer onboarding fixed |

---

*Part N added March 2026. Items DSQ-17 through DSQ-32 address the data sourcing gaps remaining after Session 19 (Part M) — specifically: field-level freshness, multi-API quota management, source trust/dedup infrastructure, free public data sources (EIA/FERC), ASX primary-source parity, sector-native intelligence (WSTS, hyperscaler capex), structured transcript parsing, and political risk grounding overhaul. These items collectively close the gap between the platform's current 7.5/10 data sourcing quality score (post-Session-19) and the 9.0+/10 target required for institutional-grade evidence.*

---

## Part O — Multi-Asset Class Expansion: Fixed Income, Alternatives & Sector Breadth (Session 21)

> **Scope Clarification (March 2026):** The platform emulates a **JP Morgan Asset Management Australia** institutional office covering the full investable universe used by a diversified Australian asset manager — not a single-theme AI infrastructure fund. AI infrastructure is the **default example universe** and a managed specialisation; the platform architecture must support all asset classes routinely deployed across JPAM-style mandates including fixed income, alternatives, and all major equity sectors.  
> **Prerequisite:** Sessions 19–20 (Parts M + N) data sourcing hardening complete  
> **Goal:** Platform can run a research pipeline against any investment universe regardless of asset class. The current AI infra configured universe is one instantiation of that capability; the system must not have any AI-infra-specific hard-coding at the engine or schema level.

---

### O.1 Scope Statement: What a JPAM-style Platform Must Cover

A JPAM Australia institutional team manages money across all major asset classes. The platform must be able to research, analyse, risk-assess, and generate investment committee-grade output for:

| Asset Class | Sub-types | Key Mandates |
|---|---|---|
| **Australian Equities** | ASX200, small/mid-cap, sector rotations | Super growth, balanced, DIO, APRA SPS 530 |
| **US Equities** | S&P 500, NASDAQ, sector ETFs, global large cap | Global equity sleeve, thematic (AI infra, healthcare, energy transition) |
| **Global / International Equities** | MSCI World ex-AU, EM, EAFE, single-country | Global diversified mandates |
| **AU Fixed Income** | AGBs (Commonwealth bonds), semi-government, IG corporate, structured (ABS, RMBS) | Capital stable, bond, conservative |
| **US / Global Fixed Income** | US Treasuries, US IG/HY credit, EM sovereign/quasi-sov, global aggregate | Global bond sleeve, IG credit, HY credit |
| **Alternatives — Listed** | A-REITs, global REITs, listed infrastructure, listed private equity, commodity ETFs | Diversified, income-focused |
| **Alternatives — Unlisted** | Unlisted property, infrastructure funds, PE fund-of-fund proxies | Pension/endowment-style, long-duration |
| **Multi-Asset / Balanced** | Blended equity + FI + alternatives in a single mandate framework | MySuper balanced, lifecycle, capital stable |
| **FX / Currency Overlay** | AUD/USD, forward hedging, currency attribution | AU-based investors in offshore assets |
| **Cash & Short-Duration** | AU BBSW/bank bills, overnight rates, short-dated credit | Liquidity management within portfolio |

The current `configs/universe.yaml` defines an AI infra themed equity portfolio. This is one example `RunRequest` — the engine itself must work correctly when given any of the above.

---

### O.2 What Needs to Change for Full Multi-Asset Coverage

**What the engine already handles well for equities:**
- 15-stage pipeline with universe → data ingestion → sector analysis → valuation → macro → risk → portfolio construction → report
- Claim ledger with source tiering
- IC voting governance
- AU super mandate logic and APRA SPS 530 diversification (`SuperannuationMandateService`)
- AUD/USD currency attribution architecture (E-5, partially implemented)

**What needs to be added or extended:**

| Gap | Severity | Description |
|---|---|---|
| Fixed income analysis stages | High | Current pipeline stages 6/7 (sector analysis + valuation) are equity-only — P/E, EV/EBITDA, DCF. No duration, spread, yield, convexity, or credit rating analysis. |
| Bond data sourcing | High | No AGB/semi-gov/IG data sources. FRED covers US Treasuries; AU bonds need AOFM API, RBA F-series statistical tables. |
| Credit analysis agent | High | No `CreditRiskAnalystAgent` — no spread analysis, issuer credit assessment, default probability, covenant review. |
| Alternatives analysis | High | No REIT, infrastructure, PE-proxy, or real-asset research stages. |
| Multi-asset portfolio construction | High | Stage 12 optimisation is equity-only. Blended mandates need FI + alternatives allocation with risk budgeting across classes. |
| Sector coverage breadth (equities) | Medium | Only 3 named sector analysts (compute, power/energy, infrastructure). GICS has 11 sectors + 25 industry groups. `GenericSectorAnalystAgent` exists but routing logic for GICS mapping is incomplete. |
| FX hedging analysis | Medium | Currency attribution is planned (E-5) but forward hedging cost/benefit and hedge ratio optimisation are absent. |
| Mandate type coverage | Medium | `SuperannuationMandateService` covers super mandates. Insurance (GPS 320), endowment, wholesale, and SMA mandates not modelled. |
| Unlisted asset valuation | Low-medium | Unlisted property and infrastructure use appraisal/DCF methodologies different from listed market approaches. |

---

### Session 21 Steps

| Step | ID | Task | Division | Effort | Files |
|---|---|---|---|---|---|
| 1 | MAC-1 | `AssetClassRouter` — detect asset class (equity / bond / REIT / infrastructure / alternative) for each ticker/ISIN in the universe; route to appropriate analysis path | Data Infrastructure | Medium | `src/research_pipeline/services/asset_class_router.py` |
| 2 | MAC-2 | `FixedIncomeDataService` — fetch AU sovereign bond yields (RBA F-series), AGB prices (AOFM API), AU semi-government yields, US Treasuries (FRED, already partially present), IG/HY credit spread indices (FRED BAMLC0A0CM, BAMLH0A0HYM2) | Data Infrastructure | Medium | `src/research_pipeline/services/fixed_income_data_service.py` |
| 3 | MAC-3 | `BondMarketPacket` schema — structured fixed income market data: yield curve (2Y/5Y/10Y/30Y AU + US), credit spreads (IG, HY, EM), ARBS (AU-US spread), implied inflation breakevens, RBA and Fed OIS-implied rate expectations | Global Research | Medium | `src/research_pipeline/schemas/fixed_income.py` |
| 4 | MAC-4 | `FixedIncomeAnalystAgent` — agent for bond/credit analysis; produces `BondAnalysisCard` per holding; covers: modified duration, DV01, Z-spread, OAS, credit rating, outlook, key risk factors (duration risk, credit risk, liquidity risk, call/prepay risk) | Global Research | High | `src/research_pipeline/agents/fixed_income_analyst_agent.py` |
| 5 | MAC-5 | `CreditRiskAnalystAgent` — for IG/HY corporate bonds; issuer-level credit assessment: leverage, interest coverage, free cash flow vs debt service, covenant headroom, refinancing risk, sector cyclicality; output `CreditAssessmentCard` | Global Research | High | `src/research_pipeline/agents/credit_risk_analyst_agent.py` |
| 6 | MAC-6 | Wire fixed income path into Stage 6 and Stage 7 — if `AssetClassRouter` identifies bond/credit instruments in universe, route Stage 6 to `FixedIncomeAnalystAgent` + `CreditRiskAnalystAgent` instead of (or alongside) equity sector analysts | Global Research | Medium | `engine.py` |
| 7 | MAC-7 | `REITAnalystAgent` — specialist listed REIT/A-REIT analysis; metrics: NTA discount/premium, cap rate, FFO, AFFO, gearing, weighted average lease expiry (WALE), occupancy, property sector (office/industrial/retail/residential), interest rate sensitivity | Global Research | High | `src/research_pipeline/agents/reit_analyst_agent.py` |
| 8 | MAC-8 | `ListedInfrastructureAnalystAgent` — regulated utility / user-pays infrastructure analysis; metrics: RAB multiple, regulated WACC vs actual WACC, contract duration, EBITDA/EV, dividend yield, regulatory reset risk | Global Research | High | `src/research_pipeline/agents/listed_infrastructure_analyst_agent.py` |
| 9 | MAC-9 | GICS sector routing in Stage 6 — map all 11 GICS sectors to an agent: named specialists where they exist (compute, power/energy, infrastructure, REIT, fixed income); `GenericSectorAnalystAgent` for all others. Configurable per-run override. | Data Infrastructure | Medium | `engine.py`, `src/research_pipeline/services/gics_router.py` |
| 10 | MAC-10 | `MultiAssetPortfolioOptimiser` — extend Stage 12 portfolio construction to handle blended universes; cross-asset correlation matrix (equity + FI + REIT + infra); risk-budgeting allocation; mandate-constrained weights per asset class sleeve | Quantitative Research | High | `src/research_pipeline/services/multi_asset_portfolio_optimiser.py` |
| 11 | MAC-11 | `FXHedgingAnalystService` — for AU-based investors in offshore assets; forward hedging cost/benefit (AUD/USD, AUD/EUR, AUD/JPY); compute hedged vs unhedged expected return; hedge ratio recommendation based on mandate and cost | Quantitative Research | Medium | `src/research_pipeline/services/fx_hedging_analyst_service.py` |
| 12 | MAC-12 | Expand `MandateConfig` — add mandate types: insurance general account (GPS 320 constraints), endowment (perpetuity horizon, real return target), wholesale institutional, SMA/individually-managed; mandate constraints per asset class (min/max FI%, alternatives %, cash %) | Investment Governance | Medium | `src/research_pipeline/schemas/mandate.py` |
| 13 | MAC-13 | `AOFMService` — Australian Office of Financial Management bond data; AGB issuance calendar, outstanding line amounts, tender results, yield at issuance; primary-source AU sovereign data equivalent to FRED for US | Data Infrastructure | Medium | `src/research_pipeline/services/aofm_service.py` |
| 14 | MAC-14 | Expand `MacroContextPacket` with fixed income market context — wire `BondMarketPacket` into Stage 8 alongside existing FRED/RBA data; Stage 8 macro agents receive yield curve shape, credit spread levels, implied rate paths as structured inputs | Global Research | Low | `engine.py`, `schemas/macro.py` |
| 15 | MAC-15 | `tests/test_session21.py` — 50+ tests; mock fixed income data services; test asset class routing; test `BondAnalysisCard` / `CreditAssessmentCard` schemas; test multi-asset optimiser with blended universe | Operations | Medium | `tests/test_session21.py` |

---

### MAC-1: Asset Class Router (Detail)

The `AssetClassRouter` is the gateway that makes the engine truly multi-asset. Without it, every ticker is routed through equity-only analysis agents regardless of what it actually is.

```python
# src/research_pipeline/services/asset_class_router.py

from enum import Enum

class AssetClass(str, Enum):
    EQUITY              = "equity"           # Listed stocks (AU / US / global)
    GOVERNMENT_BOND     = "government_bond"  # AGBs, US Treasuries, gilts, bunds
    IG_CORPORATE_BOND   = "ig_corporate"     # Investment-grade corporate debt
    HY_CORPORATE_BOND   = "hy_corporate"     # High-yield / sub-investment-grade credit
    EM_DEBT             = "em_debt"          # Emerging market sovereign or corporate
    ABS_RMBS            = "structured"       # Asset-backed / mortgage-backed securities
    LISTED_REIT         = "listed_reit"      # A-REITs, global REITs
    LISTED_INFRA        = "listed_infra"     # Regulated utilities, toll roads, airports
    LISTED_PE_PROXY     = "listed_pe"        # Listed PE vehicles (APO, BX, KKR, MQG PE)
    COMMODITY_ETV       = "commodity"        # Gold ETF, copper ETV, commodity index
    BALANCED_FUND       = "balanced_fund"    # Multi-asset fund-of-funds or ETF
    CASH_SHORT_RATE     = "cash"             # BBSW, overnight, T-bills
    UNKNOWN             = "unknown"          # Fallback — log and treat as equity

class AssetClassRouter:
    """
    Determines the asset class of each instrument in the universe.
    Order of resolution:
      1. Explicit override in universe YAML (asset_class field)
      2. Ticker/ISIN prefix rules (AU bond ISINs start AU3TB...)
      3. FMP instrument type API call
      4. Heuristic (ETF name contains "Bond", "Credit", "REIT" etc.)
      5. Default: equity
    """

    def classify(self, ticker: str, meta: dict | None = None) -> AssetClass: ...
    def classify_universe(self, universe: list[str]) -> dict[str, AssetClass]: ...
    def get_analysis_path(self, asset_class: AssetClass) -> str:
        """Returns the name of the analysis agent/path to use in Stage 6."""
        ...
```

**Universe YAML extension** — add optional `asset_class` field to any ticker entry:

```yaml
# Fixed income example (new entries in universe.yaml or a separate bond universe file)
fixed_income:
  analyst: fixed_income_analyst
  coverage:
    - ticker: "AU:TGB10Y"
      name: "Commonwealth 10-Year Bond (benchmark)"
      asset_class: government_bond
      subtheme: au_sovereign
      description: "AU 10Y AGB — duration benchmark, RBA rate sensitivity"

    - ticker: "AU:SEMIGOV5Y"
      name: "NSW Treasury 5-Year Semi-Government"
      asset_class: government_bond
      subtheme: au_semi_government
      description: "Semi-gov spread to AGBs — state fiscal risk proxy"

    - ticker: "LQD"
      name: "iShares iBoxx $ IG Corporate Bond ETF"
      asset_class: ig_corporate
      subtheme: us_credit
      description: "US IG credit index proxy — spread and duration"

    - ticker: "HYG"
      name: "iShares iBoxx $ High Yield Corporate Bond ETF"
      asset_class: hy_corporate
      subtheme: us_credit
      description: "US HY credit proxy — risk appetite indicator"
```

---

### MAC-2 / MAC-3: Fixed Income Data & BondMarketPacket (Detail)

**Data sources for AU fixed income:**

| Source | Data | Access | Cost |
|---|---|---|---|
| AOFM (aofm.gov.au) | AGB tender results, outstanding lines, issuance calendar | Public REST API | Free |
| RBA Statistical Tables — F-series | AU yield curve (F1, F2, F16), bank bill rates, swap rates, credit spreads | Public CSV download | Free |
| AFMA | Australian swap rates, bank bill swap (BBSW) | Public daily rates page | Free (scrape) |
| FRED | US Treasury yields (all tenors), US IG/HY spreads (BAMLC0A0CM, BAMLH0A0HYM2), US TIPS breakevens | Already integrated | Free |

**`BondMarketPacket` schema:**

```python
# src/research_pipeline/schemas/fixed_income.py

class YieldCurve(BaseModel):
    currency: str  # "AUD", "USD"
    tenors: dict[str, float]  # {"2Y": 4.25, "5Y": 4.40, "10Y": 4.55, "30Y": 4.70}
    as_of: datetime
    source: str  # "rba_f2", "fred", "aofm"
    curve_shape: Literal["normal", "flat", "inverted", "humped"]

class CreditSpreadEnvironment(BaseModel):
    us_ig_oas_bps: float | None        # FRED BAMLC0A0CM
    us_hy_oas_bps: float | None        # FRED BAMLH0A0HYM2
    au_semi_gov_spread_bps: float | None
    em_sovereign_spread_bps: float | None
    spread_regime: Literal["tight", "normal", "wide", "stressed"]

class BondMarketPacket(BaseModel):
    run_id: str
    as_of: datetime
    au_yield_curve: YieldCurve | None
    us_yield_curve: YieldCurve | None
    credit_spreads: CreditSpreadEnvironment
    rba_cash_rate: float | None
    fed_funds_rate: float | None
    au_us_10y_spread_bps: float | None  # Key for AUD/USD carry
    au_implied_rate_path: list[float] = []  # OIS-implied RBA cuts/hikes
    us_implied_rate_path: list[float] = []
    inflation_breakeven_us_10y: float | None
    inflation_breakeven_au_10y: float | None
```

---

### MAC-4: FixedIncomeAnalystAgent (Detail)

The fixed income analyst produces `BondAnalysisCard` — the bond equivalent of the equity `ValuationCard`.

**`BondAnalysisCard` schema:**

```python
class BondAnalysisCard(BaseModel):
    ticker: str
    instrument_name: str
    asset_class: AssetClass
    issuer: str
    currency: str

    # Duration / Rate Risk
    modified_duration: float | None
    dv01_per_100: float | None  # Dollar value of 1bp per $100 face
    convexity: float | None
    yield_to_maturity: float | None
    yield_to_worst: float | None

    # Spread Analysis
    z_spread_bps: float | None
    oas_bps: float | None           # Option-adjusted spread
    spread_vs_benchmark_bps: float | None
    spread_source: str | None

    # Credit (for corporate bonds)
    credit_rating_sp: str | None    # "AAA", "AA+", "BBB-", "BB+", etc.
    credit_rating_moodys: str | None
    credit_outlook: Literal["positive", "stable", "negative", "watch"] | None
    credit_upgrade_risk: str | None
    credit_downgrade_risk: str | None

    # Relative Value / Recommendation
    relative_value: Literal["rich", "fair", "cheap"] | None
    thesis: str
    key_risks: list[str] = []
    recommendation: Literal["overweight", "neutral", "underweight"] | None
    conviction: Literal["high", "medium", "low"] | None

    # Source / audit
    data_sources: list[str] = []
    source_tier: str = "TIER_3"
    as_of: datetime
```

**Agent prompt context:** The `FixedIncomeAnalystAgent` prompt must receive `BondMarketPacket` (yield curve + credit spreads), the instrument's own data (`BondAnalysisCard` data fields), and the macro context from Stage 8. It must produce a recommendation in the same PASS/CAVEAT/FAIL claim framework as equity agents — claims are citeable. See prompts/fixed_income_analyst.md (to be created).

---

### MAC-5: CreditRiskAnalystAgent (Detail)

For IG and HY corporate bonds the `FixedIncomeAnalystAgent` alone is insufficient — issuer-level credit fundamentals must be assessed separately.

**`CreditAssessmentCard` schema:**

```python
class CreditAssessmentCard(BaseModel):
    issuer_ticker: str         # Equity ticker of the issuing company
    bond_ticker: str           # The bond/ETF ticker in the portfolio
    assessment_date: datetime

    # Leverage and Coverage
    net_debt_ebitda: float | None
    interest_coverage_ratio: float | None
    fcf_to_debt_service_coverage: float | None

    # Refinancing Risk
    nearest_maturity_date: datetime | None
    refinancing_wall_description: str | None  # e.g. "$2B due 2026"
    refinancing_environment: Literal["benign", "challenging", "stressed"] | None

    # Covenant and Structural Risk
    covenant_headroom: str | None
    structural_subordination_risk: bool = False

    # Agency Ratings
    sp_rating: str | None
    moodys_rating: str | None
    fitch_rating: str | None
    rating_direction: Literal["stable", "on_review_upgrade", "on_review_downgrade", "positive", "negative"] | None

    # Assessment
    credit_view: Literal["investment_grade_solid", "investment_grade_stressed",
                         "crossover", "high_yield_performing", "distressed"] | None
    key_credit_risks: list[str] = []
    mitigants: list[str] = []
    issuer_equity_signals: str | None  # Cross-reference from equity valuation side

    source_tier: str = "TIER_2"
    data_sources: list[str] = []
```

---

### MAC-9: GICS Sector Routing (Detail)

The platform currently has three named specialist agents: `SectorAnalystCompute`, `SectorAnalystPowerEnergy`, `SectorAnalystInfrastructure`. All other sectors — which is most of the JPAM investable universe — fall through to `GenericSectorAnalystAgent` with no subject-matter routing.

**GICS sector-to-agent mapping:**

```python
# src/research_pipeline/services/gics_router.py

GICS_AGENT_MAP: dict[str, str] = {
    # GICS Sector → Agent name
    "Information Technology":       "sector_analyst_compute",      # existing
    "Communication Services":       "generic_sector_analyst",
    "Consumer Discretionary":       "generic_sector_analyst",
    "Consumer Staples":             "generic_sector_analyst",
    "Energy":                       "sector_analyst_power_energy",  # existing — partially
    "Utilities":                    "sector_analyst_power_energy",  # existing — partially
    "Industrials":                  "sector_analyst_infrastructure", # existing — partially
    "Materials":                    "generic_sector_analyst",
    "Health Care":                  "generic_sector_analyst",       # TODO: specialist
    "Financials":                   "generic_sector_analyst",       # TODO: specialist (banks, insurance)
    "Real Estate":                  "reit_analyst",                 # MAC-7
    # Non-equity asset classes
    "government_bond":              "fixed_income_analyst",         # MAC-4
    "ig_corporate":                 "fixed_income_analyst",
    "hy_corporate":                 "fixed_income_analyst",
    "listed_infra":                 "listed_infrastructure_analyst", # MAC-8
}
```

**Future priority specialists to add (out of scope Session 21 but recorded here):**
- `FinancialsAnalystAgent` — bank NIM analysis, capital ratios (CET1, Tier 1), LVR, arrears, insurance combined ratio
- `HealthcareAnalystAgent` — pipeline/trial risk, regulatory pathway, patent cliff, biosimilar pressure
- `ConsumerAnalystAgent` — same-store sales, traffic, ticket size, private label vs branded, consumer confidence link

---

### MAC-10: Multi-Asset Portfolio Optimiser (Detail)

The current Stage 12 optimiser (`portfolio_optimiser.py` or similar) is equity-only — covariance matrix, mean-variance or Black-Litterman, equity mandates. A multi-asset blended mandate requires:

**Extensions to Stage 12:**

```python
# src/research_pipeline/services/multi_asset_portfolio_optimiser.py

class AssetClassSleeve(BaseModel):
    """Weight constraints per asset class within a blended mandate."""
    asset_class: AssetClass
    min_weight: float = 0.0
    max_weight: float = 1.0
    strategic_weight: float  # SAA target
    tactical_range_bps: int = 500  # Tactical deviation allowed around SAA

class MultiAssetBlend(BaseModel):
    """Full blended mandate definition."""
    mandate_name: str  # "MySuper Balanced", "Capital Stable", "Growth"
    sleeves: list[AssetClassSleeve]
    total_must_sum_to_one: bool = True
    benchmark_blend: dict[str, float]  # asset_class → benchmark weight
    # e.g. {"equity_au": 0.25, "equity_us": 0.20, "fixed_income_au": 0.35,
    #        "alternatives": 0.10, "cash": 0.10}

class MultiAssetPortfolioOptimiser:
    """
    Extends the existing equity optimiser (Stage 12) to blended universes.
    Steps:
      1. Group holdings by asset class using AssetClassRouter
      2. Optimise within each sleeve (equity optimiser for equity sleeve;
         duration/spread optimiser for FI sleeve)
      3. Combine sleeves respecting MultiAssetBlend constraints
      4. Apply mandate gates (APRA SPS 530 for super; GPS 320 for insurance)
      5. Run cross-asset correlation check (equity + FI + REIT correlations
         during stress periods versus normal — use conditional correlation)
    """
    ...
```

**Mandate presets** to add to `configs/`:

```yaml
# configs/mandates/mysuper_balanced.yaml
mandate_name: "MySuper Balanced (APRA SPS 530)"
sleeves:
  - asset_class: equity_au       strategic_weight: 0.25  min: 0.15 max: 0.35
  - asset_class: equity_us       strategic_weight: 0.20  min: 0.10 max: 0.30
  - asset_class: equity_global   strategic_weight: 0.15  min: 0.05 max: 0.25
  - asset_class: fixed_income_au strategic_weight: 0.20  min: 0.10 max: 0.35
  - asset_class: fixed_income_us strategic_weight: 0.05  min: 0.00 max: 0.15
  - asset_class: listed_reit     strategic_weight: 0.05  min: 0.00 max: 0.10
  - asset_class: infrastructure  strategic_weight: 0.05  min: 0.00 max: 0.10
  - asset_class: cash            strategic_weight: 0.05  min: 0.03 max: 0.15
```

---

### MAC-11: FX Hedging Analysis (Detail)

AU-based JPAM funds investing in US and global equities face AUD/USD currency exposure. Whether to hedge, how much to hedge, and the cost of hedging is a material portfolio-level decision that the current engine ignores after the E-5 currency attribution work.

**`FXHedgingAnalysisPacket`:**

```python
class FXHedgingAnalysisPacket(BaseModel):
    run_id: str
    base_currency: str = "AUD"
    hedge_analysis: list[FXPairHedgeAnalysis] = []

class FXPairHedgeAnalysis(BaseModel):
    currency_pair: str          # "AUD/USD", "AUD/EUR", "AUD/JPY"
    spot_rate: float
    forward_rate_3m: float | None
    implied_hedge_cost_annualised_bps: float | None  # Cost of 3M rolling hedge
    carry_differential_bps: float | None            # AU vs foreign rate differential
    hedge_ratio_recommendation: float               # 0.0–1.0 (0 = unhedged, 1 = fully hedged)
    hedge_ratio_rationale: str
    mandate_required_hedge_ratio: float | None      # From MandateConfig
    historical_volatility_30d: float | None
    current_regime: Literal["aud_strong", "aud_neutral", "aud_weak"] | None
```

**Wire into Stage 12** portfolio construction (alongside MAC-10 multi-asset optimiser): FX hedging cost should be reflected as a drag on expected return for unhedged offshore positions, and the mandate's required hedge ratio should be enforced as a portfolio constraint.

**Data sources:** AUD/USD spot + forward rates already partially available via `market_data_ingestor`; forward rates can be derived from the interest rate differential using covered interest parity.

---

### Part O: Sector Universe Files

To make multi-asset instantiation concrete, add pre-built example universe YAML files alongside the existing AI infra one. These serve as templates for different mandate types:

**Files to create in `configs/universes/`:**

| File | Contents | Mandate |
|---|---|---|
| `ai_infra_thematic.yaml` | Existing universe.yaml — AI infra themed equity | Thematic / growth |
| `asx200_core.yaml` | Top 30 ASX names across all sectors (CBA, BHP, CSL, WES, WOW, TLS, MQG, ANZ, WBC, NAB, RIO, WDS, STO, QBE, IAG, TCL, SYD-proxy, GMG, SCG, GPT, MIN, FMG, NXT, XRO, WTC, ALU, TLX, PME, REH) | Australian equity core |
| `us_large_cap_diversified.yaml` | S&P 500 sector leaders — AAPL, MSFT, GOOGL, AMZN, META (tech), JPM, BAC (financials), LLY, UNH (healthcare), JNJ, PG, WMT (consumer staples), XOM, CVX (energy), CAT, GE (industrials) | Global equity / US sleeve |
| `au_fixed_income.yaml` | AU sovereign + semi-gov + major IG corporate issuers (CBA, ANZ, BHP, Telstra bonds); AGB benchmark 3Y/5Y/10Y | Fixed income / bond |
| `balanced_multi_asset.yaml` | Blended: top 10 AU equities + top 10 US equities + AU govt bond proxies + AU REIT (GMG, SCG, GPT) + listed infra (TCL, APA, AGL) | MySuper Balanced |
| `income_alternatives.yaml` | A-REITs (GMG, SCG, GPT, CLW, CIP) + listed infrastructure (TCL, APA, SKI) + high-yield credit ETF (HYG, IHY) + dividend-focused equities | Income / capital stable |

---

### Session 21 Acceptance Criteria

**P0 — gating:**
- [ ] `AssetClassRouter.classify_universe()` correctly classifies equity, government_bond, ig_corporate, listed_reit, listed_infra for a blended universe
- [ ] A run with `au_fixed_income.yaml` universe completes without error; Stage 6 routes to `FixedIncomeAnalystAgent`; `BondAnalysisCard` objects present in `stage_outputs[6]`
- [ ] `BondMarketPacket` populated from RBA F-series + FRED and wired into Stage 8 `MacroContextPacket`
- [ ] `MandateConfig` accepts insurance (GPS 320) and endowment mandate types without validation error
- [ ] 50+ new tests in `tests/test_session21.py`; all passing

**P1 — quality:**
- [ ] `FixedIncomeAnalystAgent` produces `BondAnalysisCard` with duration, spread, and recommendation for at least one AGB
- [ ] `CreditRiskAnalystAgent` produces `CreditAssessmentCard` for at least one IG corporate holding
- [ ] `MultiAssetPortfolioOptimiser` produces valid blended portfolio weights for `balanced_multi_asset.yaml` universe respecting sleeve constraints
- [ ] GICS router correctly routes at least 8 of 11 GICS sectors without error
- [ ] `FXHedgingAnalysisPacket` present in Stage 12 output for any universe containing USD-denominated assets
- [ ] All 6 example universe YAML files loadable by the engine without error

**Residual gaps acknowledged (not in scope for Session 21):**
- Unlisted asset valuation (appraisal-based; requires external property/infra valuation data feeds)
- EM sovereign debt analysis (requires dedicated EM data sourcing — not in current API stack)
- `FinancialsAnalystAgent` and `HealthcareAnalystAgent` specialist agents (out of scope; GenericSectorAnalystAgent covers adequately for now)
- Derivative / options overlay analysis (currency options, rate caps/floors — added complexity; future session)
- Private equity / unlisted fund proxy modelling (PME analysis; requires benchmark data)

---

### Division Score Impact After Session 21

| Division | After Sessions 19–20 | After Session 21 | Delta | Primary Driver |
|---|---|---|---|---|
| Global Research | 9.7 | **9.8** | +0.1 | Fixed income + credit analysis agents; REIT + listed infra agents |
| Data Sourcing Quality | 9.0 | **9.1** | +0.1 | AOFM + RBA F-series; AU bond primary sources |
| Quantitative Research | 9.3 | **9.6** | +0.3 | Multi-asset optimiser; FX hedging analysis; cross-asset correlation |
| Investment Governance | 9.6 | **9.7** | +0.1 | Expanded mandate types; multi-asset mandate gate enforcement |
| Operations & Technology | 9.4 | **9.5** | +0.1 | Asset class router; GICS routing; example universe library |
| **New: Fixed Income & Credit** | — | **8.5** | new | FixedIncomeAnalystAgent + CreditRiskAnalystAgent + BondMarketPacket |
| **New: Multi-Asset Construction** | — | **8.5** | new | MultiAssetPortfolioOptimiser + sleeve constraints + FX hedging |

---

### Session 21 Files Changed

| File | Change |
|---|---|
| `src/research_pipeline/services/asset_class_router.py` | **NEW** — `AssetClassRouter`, `AssetClass` enum |
| `src/research_pipeline/services/fixed_income_data_service.py` | **NEW** — AOFM, RBA F-series, FRED FI data |
| `src/research_pipeline/services/aofm_service.py` | **NEW** — AU sovereign bond data (AOFM API) |
| `src/research_pipeline/services/gics_router.py` | **NEW** — GICS sector → agent mapping |
| `src/research_pipeline/services/multi_asset_portfolio_optimiser.py` | **NEW** — blended mandate optimiser |
| `src/research_pipeline/services/fx_hedging_analyst_service.py` | **NEW** — FX hedge analysis and recommendation |
| `src/research_pipeline/agents/fixed_income_analyst_agent.py` | **NEW** — `FixedIncomeAnalystAgent` |
| `src/research_pipeline/agents/credit_risk_analyst_agent.py` | **NEW** — `CreditRiskAnalystAgent` |
| `src/research_pipeline/agents/reit_analyst_agent.py` | **NEW** — `REITAnalystAgent` |
| `src/research_pipeline/agents/listed_infrastructure_analyst_agent.py` | **NEW** — `ListedInfrastructureAnalystAgent` |
| `src/research_pipeline/schemas/fixed_income.py` | **NEW** — `BondMarketPacket`, `BondAnalysisCard`, `CreditAssessmentCard`, `YieldCurve`, `CreditSpreadEnvironment` |
| `src/research_pipeline/schemas/mandate.py` | Extended: insurance (GPS 320), endowment, wholesale mandate types; `AssetClassSleeve`, `MultiAssetBlend` |
| `src/research_pipeline/pipeline/engine.py` | Stage 2 (asset class classification), Stage 6/7 (asset-class-aware routing), Stage 8 (`BondMarketPacket` in macro context), Stage 12 (multi-asset optimiser) |
| `configs/universe.yaml` | Comment updated; `asset_class` field recognised per entry |
| `configs/universes/` | **NEW directory** — 6 example universe YAML files |
| `configs/mandates/` | **NEW directory** — MySuper balanced, capital stable, growth, insurance mandate presets |
| `prompts/fixed_income_analyst.md` | **NEW** — prompt template for fixed income analysis |
| `prompts/credit_risk_analyst.md` | **NEW** — prompt template for credit risk assessment |
| `tests/test_session21.py` | **NEW** — 50+ tests |

---

*Part O added March 29, 2026. This section corrects the inadvertent AI-infrastructure-only framing in Parts M and N and establishes the full JPAM-style multi-asset scope: the platform covers general equities (all GICS sectors, AU + US + global), fixed income (sovereign + credit), alternatives (listed REITs, listed infrastructure), multi-asset blended mandates, and FX overlay analysis. AI infrastructure remains the default example universe and a maintained specialisation. The platform architecture must be asset-class-agnostic at the engine level.*

---

## Part P — The JPAM Internal Environment: Immersive Experience Layer (Session 22)

> **Source:** User directive March 29, 2026 — "I want it to be like walking into JPMorgan as an associate and being in the middle of it. I want to get a feel for the process, see each section and what it does, what the roles are, how they are handled, and how the output is finally produced."  
> **Scope:** This part is entirely about the *experience* of using the platform, not just what it produces. The outputs must feel like walking onto a live research floor — seeing which analyst is working on what, what the market context is today, how the investment committee decides, and how all of it connects into a final recommendation. The backend emits richer narrative signal; the frontend presents it as a live institutional environment.  
> **Prerequisite:** Base pipeline running cleanly (Sessions 1–20 complete)

---

### P.1 The Vision: Walking onto the Research Floor

The current experience is mechanical — "S5: running... S6: completed." That tells you nothing about why, what was found, or what it means. The target experience is this:

> You open the platform. The **Morning Brief** is on screen — the macro environment as of today: RBA held yesterday, US 10Y widened 12bps, NVIDIA's 8-K filed this morning with updated data center revenue guidance. The model portfolio is flagged: the AI infra sleeve is overweight relative to mandate.
>
> You start a run. The left panel shows a **research floor view** — six desks, each labelled with a role: Evidence Librarian, Sector Analysts (Compute, Power), Valuation Analyst, Macro Strategist, Red Team. You watch each desk activate as its stage begins, showing a live status: *"Reviewing NVDA 10-K §7 MD&A — identified $8.7B data centre capex guidance revision upward"*.
>
> The run completes. The **IC Meeting Room** appears — you see the three committee members vote YES/NO/ABSTAIN on the investment recommendation, with a brief rationale for any dissent. Quorum reached: 3/3 YES. The report publishes.
>
> You open the report. The first page is the **Investment Thesis Summary** — one concise paragraph, institutionally written. Below it: the claim ledger (every factual assertion with its source and confidence), the risk register, the sector breakdowns, the valuation cards. At the bottom: **How this report was made** — a narrative audit trail of which analysts contributed what finding, what the red team challenged, and how the PM responded.

This is achievable with targeted additions to the backend (narrative emission, persona layer, morning brief endpoint) and the Next.js frontend (redesigned panels, IC room, run narrative tab).

---

### P.2 JPAM Role Mapping — The People in the Building

Each pipeline stage maps to a real institutional role. The platform should make this explicit everywhere — in the UI, in event emissions, and in the report itself.

| Stage | JPAM Role Title | Seniority | Mandate | Output Analogy |
|---|---|---|---|---|
| Stage 0 — Universe | **Portfolio Strategist** | MD level | Defines the investment universe and run parameters | Investment Brief / Mandate Card |
| Stage 1 — Universe Gate | **Compliance Officer** | VP level | Universe validation — mandate conformity, liquidity floors | Pre-run clearance memo |
| Stage 2 — Data Ingestion | **Research Associate** | Analyst / Associate | Pulls all market data, filings, news, consensus into the workstation | Data pack assembly |
| Stage 3 — Reconciliation | **Data Quality Analyst** | Associate | Cross-checks all quantitative inputs for consistency; flags discrepancies | Data validation sign-off |
| Stage 4 — Orchestration | **Research Director** | MD level | Reviews data completeness; decides if enough to proceed | Green-light memo |
| Stage 5 — Evidence Librarian | **Senior Research Associate** | VP level | Primary source evidence gathering — filings, transcripts, news; assembles the claim ledger | Evidence pack / source citations |
| Stage 6 — Sector Analysis | **Sector Analyst(s)** | VP / Director | Deep sector-specific analysis per group (Compute, Power/Energy, Infra, etc.) | Sector research note |
| Stage 7 — Valuation | **Valuation Analyst** | VP level | DCF, relative valuation, intrinsic value vs market price | Valuation model summary |
| Stage 8 — Macro / Political | **Macro Strategist + Political Risk Analyst** | Director level | Regime assessment — rates, inflation, geopolitics, regulatory environment | Macro briefing note |
| Stage 9 — Quant Research | **Quantitative Analyst** | VP level | Factor analysis, VaR, attribution, risk decomposition | Quant risk report |
| Stage 10 — Red Team | **Devil's Advocate / Red Team Analyst** | Senior VP | Adversarial challenge — what could go wrong, what's been missed, thesis falsification | Challenge memo |
| Stage 11 — Associate Review | **Associate Reviewer** | Associate | Final quality gate — completeness, internal consistency, claim grounding | Pre-IC checklist |
| Stage 12 — Portfolio Manager | **Portfolio Manager** | MD level | Portfolio construction, position sizing, mandate compliance, final portfolio | PM order memo |
| Stage 13 — Report Assembly | **Research Editor / Report Writer** | VP level | Composes institutional-grade investment note in JPAM house style | Research publication |
| Stage 14 — Governance Gate | **Investment Committee** | C-suite / Partners | IC vote — formal publish/reject decision with rationale | IC decision record |

---

### P.3 Backend Changes: Making the Machine Tell Its Story

The backend needs to emit richer, human-readable signal at every stage. Currently `StageEvent` has `type`, `label`, `duration_ms`. It needs a `narrative` field.

#### EXP-1: `StageNarrative` — live narrative emission from every stage

```python
# src/research_pipeline/schemas/events.py — extension

class StageNarrative(BaseModel):
    """
    Human-readable narrative emitted by each stage as it runs.
    Designed to read like a live status update from a named analyst.
    Surfaced in the frontend as the 'what this person is doing' status.
    """
    stage_num: int
    role_title: str           # "Senior Research Associate — Evidence Librarian"
    role_seniority: str       # "VP level"
    status_headline: str      # One-line: what is happening right now
    # e.g. "Reviewing NVDA 10-K §7 MD&A — identified data centre capex revision"
    key_findings: list[str] = []
    # e.g. ["NVDA capex guidance revised up $2.1B", "AMD data centre share flat QoQ"]
    flags_raised: list[str] = []
    # e.g. ["AVGO earnings transcript unavailable — falling back to FMP consensus"]
    next_stage_handoff: str = ""
    # e.g. "Handing evidence pack to Sector Analysts with 47 claims, 3 CAVEAT, 0 FAIL"
    elapsed_seconds: float = 0.0
```

Each agent's `run()` method should emit `StageNarrative` events at three points:
- **On start:** `status_headline` = "Commenced [task description]"
- **Mid-run (optional):** `status_headline` updated with live progress
- **On complete:** `key_findings` and `next_stage_handoff` populated

#### EXP-2: `AgentPersona` — each agent knows its role identity

```python
# src/research_pipeline/schemas/personas.py — new file

class AgentPersona(BaseModel):
    """
    The institutional identity of each pipeline agent.
    Used by the frontend to present each stage as a named role.
    """
    stage_num: int
    role_title: str
    role_short: str           # For compact UI display: "Evidence Librarian"
    seniority: str            # "Analyst", "Associate", "VP", "Director", "MD"
    department: str           # "Global Research", "Quantitative Research", etc.
    mandate_description: str  # What this role is responsible for
    desk_icon: str            # Lucide icon name for the frontend desk card
    reports_to: str           # Which role reviews their output

# Registry — one entry per stage
AGENT_PERSONAS: dict[int, AgentPersona] = {
    0:  AgentPersona(stage_num=0,  role_title="Portfolio Strategist",
                     role_short="Strategist", seniority="MD",
                     department="Portfolio Management",
                     mandate_description="Defines universe, mandate, and run parameters",
                     desk_icon="Target", reports_to="Investment Committee"),
    2:  AgentPersona(stage_num=2,  role_title="Research Associate",
                     role_short="Data Desk", seniority="Associate",
                     department="Global Research",
                     mandate_description="Assembles quantitative data pack from all market data sources",
                     desk_icon="Database", reports_to="Senior Research Associate"),
    5:  AgentPersona(stage_num=5,  role_title="Senior Research Associate",
                     role_short="Evidence Librarian", seniority="VP",
                     department="Global Research",
                     mandate_description="Primary-source evidence gathering; assembles claim ledger",
                     desk_icon="BookOpen", reports_to="Sector Analysts"),
    6:  AgentPersona(stage_num=6,  role_title="Sector Analyst",
                     role_short="Sector Research", seniority="VP / Director",
                     department="Global Research",
                     mandate_description="Sector-specific analysis and investment view per coverage group",
                     desk_icon="BarChart3", reports_to="Valuation Analyst"),
    7:  AgentPersona(stage_num=7,  role_title="Valuation Analyst",
                     role_short="Valuation", seniority="VP",
                     department="Global Research",
                     mandate_description="DCF, relative valuation, price target derivation",
                     desk_icon="Calculator", reports_to="Portfolio Manager"),
    8:  AgentPersona(stage_num=8,  role_title="Macro Strategist",
                     role_short="Macro / Political", seniority="Director",
                     department="Global Macro",
                     mandate_description="Regime assessment: rates, inflation, geopolitics, regulatory",
                     desk_icon="Globe", reports_to="Portfolio Manager"),
    9:  AgentPersona(stage_num=9,  role_title="Quantitative Analyst",
                     role_short="Quant Research", seniority="VP",
                     department="Quantitative Research",
                     mandate_description="Factor models, VaR, risk decomposition, attribution",
                     desk_icon="Activity", reports_to="Portfolio Manager"),
    10: AgentPersona(stage_num=10, role_title="Red Team Analyst",
                     role_short="Red Team", seniority="Senior VP",
                     department="Risk",
                     mandate_description="Adversarial challenge — thesis falsification, tail risk identification",
                     desk_icon="AlertTriangle", reports_to="Investment Committee"),
    12: AgentPersona(stage_num=12, role_title="Portfolio Manager",
                     role_short="Portfolio Manager", seniority="MD",
                     department="Portfolio Management",
                     mandate_description="Construction, position sizing, mandate compliance, final portfolio",
                     desk_icon="Briefcase", reports_to="Investment Committee"),
    14: AgentPersona(stage_num=14, role_title="Investment Committee",
                     role_short="IC", seniority="C-suite / Partners",
                     department="Investment Governance",
                     mandate_description="Formal IC vote: publish or reject; final risk sign-off",
                     desk_icon="Users", reports_to="—"),
}
```

#### EXP-3: `MorningBriefPacket` — the market environment as of right now

```python
# src/research_pipeline/schemas/morning_brief.py — new file

class MarketMovement(BaseModel):
    label: str              # "US 10Y Treasury"
    current_value: float
    change_1d: float        # Absolute change
    change_1d_pct: float    # % change
    direction: Literal["up", "down", "flat"]
    significance: Literal["watch", "material", "critical"]

class RegimeFlag(BaseModel):
    dimension: str          # "Rate Environment", "Credit Spreads", "Geopolitical Risk"
    current_regime: str     # e.g. "Easing Bias", "Tightening Spreads", "Elevated"
    trend: Literal["improving", "stable", "deteriorating"]
    brief_rationale: str    # 1 sentence

class MorningBriefPacket(BaseModel):
    """
    Synthesised market context for today — what every analyst on the floor
    would read before sitting down. Surfaced on the dashboard front page.
    Updated once per day (cached; refreshed at market open).
    """
    as_of: datetime
    headline: str           # 1-sentence market summary for today
    # e.g. "Risk-on: US equities up 0.8%, spreads tightening, RBA held rates"

    key_market_moves: list[MarketMovement] = []
    # AU cash rate, US Fed funds, AU 10Y, US 10Y, AUD/USD,
    # S&P 500, ASX 200, IG spreads, HY spreads

    regime_flags: list[RegimeFlag] = []
    # Rate environment, credit spreads, risk appetite,
    # geopolitical/regulatory risk, AU-specific

    sector_in_focus: list[str] = []
    # e.g. ["AI Infrastructure — NVDA 8-K filed this morning",
    #        "Utilities — FERC grid moratorium news"]

    portfolio_alerts: list[str] = []
    # e.g. ["AI infra sleeve 3.2% overweight vs mandate",
    #        "AVGO earnings 4 days away — position review recommended"]

    sourced_from: list[str] = []  # Which data services populated this
```

**`/api/morning-brief` endpoint** — GET, no auth, returns `MorningBriefPacket`. Pulls from `FixedIncomeDataService` (yield curves), `EIAService`, `BenzingaService` (sector catalysts), Stage 8 macro outputs from the most recent completed run. Cached 1 hour.

#### EXP-4: `RunNarrative` — the story of how the report was made

Currently the pipeline produces a report with no record of the reasoning chain that created it. The `RunNarrative` captures this as a human-readable story appended to every completed run.

```python
# src/research_pipeline/schemas/run_narrative.py — new file

class StageContribution(BaseModel):
    """What one analyst contributed to the final output."""
    stage_num: int
    role_title: str
    contribution_summary: str   # 2–4 sentences: what they did, what they found
    key_finding: str            # The single most important thing this stage produced
    handed_to: str              # Who received this work
    challenges_raised: list[str] = []  # If Red Team — what was challenged
    challenges_resolved: list[str] = []  # If PM — how challenges were addressed

class ICDecisionSummary(BaseModel):
    quorum_met: bool
    vote_breakdown: dict[str, str]  # "member_1": "YES", "member_2": "YES", etc.
    dissent_rationale: str | None
    final_decision: Literal["PUBLISH", "REJECT", "DEFER"]
    decision_rationale: str  # 2–3 sentences on why

class RunNarrative(BaseModel):
    """
    The story of how a research report was produced.
    Appended to every completed run; surfaced as a 'How this was made' tab.
    """
    run_id: str
    universe: list[str]
    started_at: datetime
    completed_at: datetime
    total_elapsed_seconds: float

    executive_narrative: str
    # 3–5 paragraph institutional prose: "This research cycle commenced on [date]
    # with a universe of [N] names covering [sectors/themes]. The Evidence
    # Librarian identified [N] primary-source claims including [key finding]..."

    stage_contributions: list[StageContribution] = []
    ic_decision: ICDecisionSummary | None = None

    thesis_evolution: list[str] = []
    # Chronological: how the investment view changed as stages ran
    # e.g. ["Initial data: NVDA consensus BUY, target $180",
    #        "Evidence stage: found regulatory risk in §1A Risk Factors",
    #        "Red Team challenged: export control downside not in consensus EPS",
    #        "PM response: position sized down; stop-loss tightened"]

    data_quality_summary: str   # Plain English summary of data quality for this run
    caveats: list[str] = []     # Residual uncertainties acknowledged
```

The `ReportNarrativeAgent` (Stage 13) should be extended to populate `RunNarrative` alongside the existing five narrative sections. Alternatively, a new lightweight `RunNarrativeService` assembles it from the structured stage outputs after the pipeline completes.

---

### P.4 Frontend Changes: The Research Floor

#### EXP-5: Research Floor View — the pipeline tracker redesigned

The current pipeline tracker is a list of stage rows with status icons. The redesign turns it into a **desk layout** — a grid of analyst cards, each representing one role, lighting up as their stage runs.

**New component: `ResearchFloorPanel`**

```tsx
// frontend/src/components/floor/research-floor-panel.tsx

// Layout: 3-column grid of DeskCard components
// Left column: Data Desk (S2), Evidence Librarian (S5)  
// Middle column: Sector Analyst(s) (S6), Valuation (S7), Macro (S8)
// Right column: Quant (S9), Red Team (S10), Portfolio Manager (S12)
// Bottom bar: IC Meeting Room (S14) — full width when active

interface DeskCardProps {
  persona: AgentPersona;
  status: "idle" | "running" | "completed" | "failed";
  narrative: StageNarrative | null;
  durationMs: number | null;
  onClick: () => void;
}
```

**Each `DeskCard` shows:**
- Role title + seniority badge (e.g. "VP")
- Department tag (e.g. "Global Research")
- Status: idle (grey) / running (blue pulse animation) / completed (green) / failed (red)
- When running: the live `status_headline` from `StageNarrative`, updating in real time
- When completed: `key_findings` — bullet-point summary of what this analyst found
- Click → expand to full stage output drawer

**Visual treatment:**
- Idle desks: dark, slightly dimmed, "waiting" state
- Active desk: elevated shadow, subtle blue glow, animated "typing" indicator
- Completed desk: green border tick, findings visible
- The research floor should feel like a Bloomberg Terminal meets a war room — dark background, dense but readable, professional

#### EXP-6: Morning Brief Panel — top of the dashboard

Replaces (or supplements) the current metric cards on the dashboard home page.

```tsx
// frontend/src/components/morning-brief/morning-brief-panel.tsx

// Layout: full-width panel at top of dashboard
// Left: Market Moves — compact table of key rates/spreads/indices
//        with up/down arrows and color coding (green/red)
// Centre: Regime Flags — pill badges per dimension
//         (RATE ENVIRONMENT · Easing Bias · ↓) 
// Right: Sector in Focus + Portfolio Alerts — live items from this morning
// Footer: "as of [time] · sources: FRED, RBA, Benzinga"
```

This panel answers: "What is the market environment as of right now, and what should I be paying attention to today?"

#### EXP-7: IC Meeting Room — full-width view for Stage 14

When Stage 14 runs, the pipeline tracker should expand the bottom IC area into a dedicated **IC Meeting Room** view:

```tsx
// frontend/src/components/governance/ic-meeting-room.tsx

// Layout:
// Header: "Investment Committee · [timestamp]" + quorum indicator (e.g. "⚫⚫⚫ 3 of 3 present")
// Centre: Three member cards side by side:
//   [Member 1: Portfolio Strategist · MD] → VOTE: YES ✓
//   [Member 2: Risk Officer · SVP]        → VOTE: YES ✓  
//   [Member 3: Compliance · VP]           → VOTE: REVIEWING...
// Bottom: IC rationale text — "Committee voted to publish based on..."
// Final: PUBLISH button animation when quorum reached

// Votes appear one by one with a brief delay — creating the feeling
// that real deliberation is happening, not instantaneous rubber-stamping
```

This transforms the governance gate from a hidden background check into the most visible, dramatic moment in the run — which is what it is in a real IC process.

#### EXP-8: Run Narrative Tab — "How this was made"

On the run detail page (`/runs/[run_id]`), add a fourth tab alongside the existing output tabs:

```
[Report]  [Evidence]  [Risk & Quant]  [How This Was Made]
```

The "How This Was Made" tab renders the `RunNarrative`:
- `executive_narrative` — displayed as prose paragraphs
- `thesis_evolution` — a timeline component showing how the view evolved through the pipeline
- `stage_contributions` — accordion: expand each analyst's contribution
- `ic_decision` — IC decision card with vote breakdown
- `data_quality_summary` + `caveats` — honest disclosure section at the bottom

This is the institutional transparency layer — a JP Morgan analyst team would produce an audit trail of their reasoning. This is the AI equivalent.

#### EXP-9: Role Reference Panel — "Who's in the building"

A persistent reference accessible from the sidebar: **"The Team"** — a one-page glossary of every role in the pipeline, what their mandate is, what they produce, and what standard their output is held to. This is the "onboarding card" for a new associate joining the team.

```tsx
// frontend/src/components/team/team-reference-panel.tsx
// Renders AGENT_PERSONAS registry as a styled role directory
// Format: role card grid — title, department, seniority badge,
//         mandate description, "produces → [output type]", "reports to → [role]"
```

---

### P.5 Streamlit Frontend Parity

The Streamlit frontend at `src/frontend/app.py` is used for local development and demos. It should receive equivalent narrative enhancements — lighter weight, but the same emotional experience:

- **Stage headers** should include persona title: not "Stage 5" but "Stage 5 · Evidence Librarian (VP · Global Research)"
- **Stage status** should show `StageNarrative.status_headline` in an `st.info()` box during run
- **Stage completion** should show `key_findings` as `st.success()` bullets
- **IC vote** should be rendered as an `st.metric()` row: "Member 1 · YES  Member 2 · YES  Member 3 · YES"
- **Report** should include a "How this was made" expander at the bottom

---

### Session 22 Steps

| Step | ID | Task | Division | Effort | Files |
|---|---|---|---|---|---|
| 1 | EXP-1 | `StageNarrative` schema + emission from all 15 stage methods in `engine.py`; each stage emits start/complete narrative through the existing events channel | Global Research / Ops | Medium | `schemas/events.py`, `engine.py` |
| 2 | EXP-2 | `AgentPersona` registry — `AGENT_PERSONAS` dict covering all 15 stages; add `persona` field to `StageEvent` | Ops | Low | `schemas/personas.py`, `schemas/events.py` |
| 3 | EXP-3 | `MorningBriefPacket` schema + `MorningBriefService` building it from live data services; `/api/morning-brief` GET endpoint | Data Infrastructure | Medium | `schemas/morning_brief.py`, `services/morning_brief_service.py`, `api/routes/morning_brief.py` |
| 4 | EXP-4 | `RunNarrative` schema + assembly after pipeline completes; extend `ReportNarrativeAgent` or add `RunNarrativeService`; stored as `run_narrative.json` per run | Global Research | High | `schemas/run_narrative.py`, `services/run_narrative_service.py` |
| 5 | EXP-5 | `ResearchFloorPanel` Next.js component — redesigned pipeline tracker as desk-grid layout with `DeskCard` per persona; `StageNarrative` live updates via WebSocket | Frontend | High | `components/floor/research-floor-panel.tsx`, `components/floor/desk-card.tsx` |
| 6 | EXP-6 | `MorningBriefPanel` Next.js component — market moves table, regime flags, sector focus, portfolio alerts; calls `/api/morning-brief`; on dashboard home page | Frontend | Medium | `components/morning-brief/morning-brief-panel.tsx` |
| 7 | EXP-7 | `ICMeetingRoom` Next.js component — full-width IC stage view; animated sequential vote reveal; quorum indicator; rationale text | Frontend | Medium | `components/governance/ic-meeting-room.tsx` |
| 8 | EXP-8 | "How This Was Made" tab on run detail page — `RunNarrative` rendered as prose + timeline + accordion + IC card | Frontend | Medium | `app/runs/[run_id]/page.tsx` |
| 9 | EXP-9 | `TeamReferencePanel` — "The Team" sidebar page rendering `AGENT_PERSONAS` as role directory; accessible from sidebar nav | Frontend | Low | `components/team/team-reference-panel.tsx`, `app/team/page.tsx` |
| 10 | EXP-10 | Streamlit frontend narrative parity — persona titles in stage headers, `StageNarrative.status_headline` in `st.info()`, `key_findings` as `st.success()` bullets, IC vote as `st.metric()` row | Frontend | Medium | `src/frontend/app.py` |
| 11 | EXP-11 | `StageNarrative` content quality — each agent's `run()` outputs concrete, specific narrative (not generic "stage started"). Narrative should name tickers finding-specific: "NVDA: found $2.1B capex revision in 10-Q MD&A" not "evidence gathered." | Global Research | High | All agent files in `src/research_pipeline/agents/` |
| 12 | EXP-12 | `tests/test_session22.py` — tests for `StageNarrative` emission, `AgentPersona` registry completeness, `MorningBriefPacket` schema validation, `RunNarrative` assembly | Operations | Medium | `tests/test_session22.py` |

---

### What the Experience Looks Like End-to-End

**Before a run — the Morning Brief:**
> "March 29, 2026 — RBA held cash rate at 4.10% (as expected). US 10Y at 4.42% (+8bps). AUD/USD 0.6312 (+0.4%). AI infrastructure: NVDA filed 8-K at 06:42 UTC — revised data centre revenue guidance upward. ASX 200 flat. IG spreads tightening. Geopolitical: no new material export control events overnight."

**During a run — the Research Floor:**
> Stage 5 desk glowing blue: *"Senior Research Associate reviewing NVDA Form 4 insider transactions — 3 purchases $1.2M aggregate last 30 days. Pulling 10-K §7 MD&A... identified revised data centre revenue $36.5B (+18% YoY). Evidence pack: 23 Tier 1 claims, 6 CAVEAT."*

> Stage 10 desk lighting up: *"Red Team challenging NVDA recommendation: EXPORT CONTROL RISK — October 2023 BIS H100 restrictions not fully reflected in consensus EPS. Scenarios modelled: -15% revenue impact if China restrictions tighten further. Challenge logged as OPEN."*

> Stage 12 desk: *"Portfolio Manager responding to Red Team challenge: sizing NVDA at 4.2% vs consensus 5.8% overweight. Stop-loss set at $145. Red Team challenge PARTIALLY RESOLVED — residual export control risk disclosed in report."*

**IC Meeting Room:**
> Quorum: 3 of 3 members present.  
> Portfolio Strategist (MD): **YES** — "Thesis is well-grounded; position sizing reflects risk."  
> Risk Officer (SVP): **YES** — "Red team challenge addressed; export control risk disclosed."  
> Compliance (VP): **YES** — "Mandate constraints met; APRA SPS 530 diversification preserved."  
> Decision: **PUBLISH**.

**In the report — "How This Was Made":**
> "This research cycle commenced on March 29, 2026 covering a universe of 15 names across AI infrastructure, power/energy, and materials. The Evidence Librarian identified 47 primary-source claims from SEC filings, company transcripts, and Benzinga analyst actions. The Sector Analyst covering Compute flagged NVDA's upward data centre guidance revision as the primary positive catalyst. The Valuation Analyst derived an intrinsic value of $198 vs current price $172 — a 15.1% upside. The Red Team raised one open challenge: export control risk in China operations not fully reflected in consensus EPS estimates. The Portfolio Manager responded by reducing position size and tightening the stop-loss. The Investment Committee voted 3/3 to publish."

---

### Session 22 Acceptance Criteria

**P0 — gating:**
- [ ] `StageNarrative` emitted by at minimum Stages 2, 5, 6, 7, 8, 10, 12, 14 during a live run
- [ ] `StageNarrative.status_headline` contains ticker-specific content (not just "stage running")
- [ ] `AGENT_PERSONAS` registry complete for all 15 stages
- [ ] `MorningBriefPacket` constructed and returned from `/api/morning-brief` with at least yield curve + regime flags populated
- [ ] `RunNarrative` assembled and written to `run_narrative.json` for every completed run
- [ ] `ResearchFloorPanel` renders all desk cards with live narrative updates during a run
- [ ] `MorningBriefPanel` visible on dashboard home page
- [ ] "How This Was Made" tab present on run detail page with `RunNarrative` content
- [ ] IC stage renders as `ICMeetingRoom` component (not just a regular stage row)

**P1 — quality:**
- [ ] `StageNarrative.key_findings` non-empty for at least 8 stages in a full run
- [ ] `thesis_evolution` in `RunNarrative` records at minimum 3 state changes for a typical run
- [ ] `ICMeetingRoom` vote animation: votes appear sequentially with 800ms delay between members
- [ ] Streamlit frontend shows persona titles and stage narrative headlines
- [ ] "The Team" page accessible from sidebar; all roles rendered

**Experience test (manual):**
- [ ] A person unfamiliar with the codebase can watch a full run from the dashboard and understand: (a) which role is working right now, (b) what they found, (c) what was challenged, (d) why the IC voted YES/NO — without reading any documentation

---

### Session 22 Files Changed

| File | Change |
|---|---|
| `src/research_pipeline/schemas/personas.py` | **NEW** — `AgentPersona`, `AGENT_PERSONAS` registry |
| `src/research_pipeline/schemas/morning_brief.py` | **NEW** — `MorningBriefPacket`, `MarketMovement`, `RegimeFlag` |
| `src/research_pipeline/schemas/run_narrative.py` | **NEW** — `RunNarrative`, `StageContribution`, `ICDecisionSummary` |
| `src/research_pipeline/schemas/events.py` | Extended: `StageNarrative`, `persona` field on `StageEvent` |
| `src/research_pipeline/services/morning_brief_service.py` | **NEW** — assembles `MorningBriefPacket` from live data services |
| `src/research_pipeline/services/run_narrative_service.py` | **NEW** — assembles `RunNarrative` from completed stage outputs |
| `src/research_pipeline/agents/*.py` | All agents: emit `StageNarrative` with ticker-specific findings |
| `src/research_pipeline/pipeline/engine.py` | Emit `StageNarrative` events; call `RunNarrativeService` on completion |
| `src/api/routes/morning_brief.py` | **NEW** — GET `/api/morning-brief` → `MorningBriefPacket` |
| `frontend/src/components/floor/research-floor-panel.tsx` | **NEW** — research floor desk grid |
| `frontend/src/components/floor/desk-card.tsx` | **NEW** — individual analyst desk card |
| `frontend/src/components/morning-brief/morning-brief-panel.tsx` | **NEW** — morning brief dashboard panel |
| `frontend/src/components/governance/ic-meeting-room.tsx` | **NEW** — IC meeting room with vote animation |
| `frontend/src/components/team/team-reference-panel.tsx` | **NEW** — role directory |
| `frontend/src/app/runs/[run_id]/page.tsx` | Extended: "How This Was Made" tab with `RunNarrative` |
| `frontend/src/app/team/page.tsx` | **NEW** — "The Team" page |
| `frontend/src/app/page.tsx` | Extended: `MorningBriefPanel` at top of dashboard |
| `src/frontend/app.py` | Extended: persona titles, narrative headlines, IC vote display |
| `tests/test_session22.py` | **NEW** — 40+ tests |

---

*Part P added March 29, 2026. This section gives the platform its institutional identity — not just a system that produces outputs, but an environment where you feel the machine working, understand who is doing what and why, and experience the full institutional research process from morning brief to IC decision. The technical outputs are unchanged; what changes is the experience of watching them being made.*

---

## Part Q — Daily Rhythms: The Living Office (Session 23)

> **Source:** User directive March 29, 2026 — "can you think of any other things to implement to give the JPMorgan feel and understand the daily comings and goings"  
> **Context:** Part P gave the platform its identity — roles, morning brief, IC room. Part Q gives it its rhythm. A JPAM office is not just a machine you run — it is a place where things happen on a calendar, analysts maintain a living book of coverage, PMs watch positions against benchmark every day, and compliance is always somewhere in the peripheral vision.  
> **Scope:** Eight additions focused on the *operational cadence* of an institutional research floor — what drives work each day, what is always visible, and what creates the sense that the platform is alive even when no pipeline run is in progress.

---

### Q.1 The Eight Daily-Rhythm Additions

| ID | Name | What it emulates | Where it lives |
|---|---|---|---|
| RHY-1 | Research Calendar | The desk calendar — upcoming earnings, central bank meetings, economic releases, and scheduled review runs | Dashboard sidebar + dedicated page |
| RHY-2 | Coverage Book | The active research book — every covered name, current recommendation, last review date, conviction level, next catalyst | `/coverage` page + dashboard widget |
| RHY-3 | Portfolio Blotter | The PM's screen — live model portfolio positions vs SAA benchmark, current weight vs target, drift alerts | `/portfolio` page |
| RHY-4 | Daily Standup Brief | Auto-generated morning note sent to the "team" — per-analyst status on each name with material overnight events | Dashboard + `/api/standup` endpoint |
| RHY-5 | News Wire | Right-rail live news feed filtered to coverage universe — each item tagged with the affected holding(s) and event type | Run detail page + dashboard sidebar |
| RHY-6 | Research Track Record | How the calls have performed — every published recommendation tracked against subsequent price action | `/track-record` page |
| RHY-7 | Scenario Sandbox | Quick macro scenario tool — "what if Fed cuts 50bps? What if NVDA misses EPS by 15%?" — without triggering a full 15-stage run | `/scenario` page |
| RHY-8 | Compliance Board | Mandate and compliance status at a glance — restricted names, open mandate breaches, pre-clearance pending | Dashboard header badge + `/compliance` page |

---

### RHY-1: Research Calendar

The single most powerful thing that makes a sell-side or buy-side desk feel *alive* is the calendar. Everything is event-driven: earnings → update run. FOMC → re-assess macro stage. Quarterly portfolio review due. This gives the platform a forward pulse.

**`ResearchCalendarService` + `CalendarEvent` schema:**

```python
# src/research_pipeline/schemas/calendar.py

class CalendarEventType(str, Enum):
    EARNINGS          = "earnings"          # Quarterly earnings release
    CENTRAL_BANK      = "central_bank"      # RBA / Fed / ECB meeting
    ECONOMIC_RELEASE  = "economic_release"  # CPI, NFP, GDP, etc.
    PORTFOLIO_REVIEW  = "portfolio_review"  # Scheduled quarterly PM review
    COVERAGE_UPDATE   = "coverage_update"   # Scheduled analyst update run
    FILING_DUE        = "filing_due"        # 10-K / 10-Q expected filing window
    DIVIDEND_DATE     = "dividend_date"     # Ex-div / record date

class CalendarEvent(BaseModel):
    event_id: str
    event_type: CalendarEventType
    title: str                      # e.g. "NVDA Q1 2026 Earnings"
    description: str                # 1-sentence context
    event_date: date
    days_until: int                 # Computed at query time
    affected_tickers: list[str] = []
    urgency: Literal["watch", "prepare", "action_required"]
    auto_trigger_run: bool = False  # If True: schedule a coverage update run
    triggered_run_id: str | None = None
```

**Frontend: `ResearchCalendarPanel`**

```
[ THIS WEEK ]                    [ NEXT 30 DAYS ]
─────────────────────────────    ─────────────────────────────
◉ Today   Mar 29  RBA Decision   4d   NVDA Earnings  ► Prepare
           (Past — held 4.10%)   8d   US CPI Release   Watch
◉ Apr 1   US ISM Manufacturing   12d  Fed FOMC Meeting ► Action
◉ Apr 3   AVGO Earnings          15d  Q2 Portfolio Review ► Action
           ► Alert: 4 days out   22d  TSM 20-A Filing window
```

Each item has a colour-coded urgency dot and, for earnings, a one-click **"Prepare Update Run"** button that pre-fills `/runs/new` with the affected tickers. Calendar data sourced from: Benzinga earnings calendar, FOMC published schedule, RBA decision dates (both public), economic releases (FRED release calendar, ABS release schedule).

---

### RHY-2: Coverage Book

In any real research desk there is a **coverage list** — a living document of every name under formal coverage, its current standing, and when it was last touched. This is the "book" the analyst carries. Between pipeline runs, this is the persistent state of the research office.

**`CoverageRecord` schema:**

```python
# src/research_pipeline/schemas/coverage.py

class ResearchRecommendation(str, Enum):
    STRONG_BUY     = "strong_buy"
    BUY            = "buy"
    NEUTRAL        = "neutral"
    UNDERPERFORM   = "underperform"
    SELL           = "sell"
    UNDER_REVIEW   = "under_review"    # Post-material-event, pre-update
    NOT_RATED      = "not_rated"       # In universe but no formal rec yet

class CoverageRecord(BaseModel):
    ticker: str
    company_name: str
    sector: str
    analyst_role: str           # "Sector Analyst — Compute"
    current_rec: ResearchRecommendation
    price_target: float | None
    current_price: float | None
    upside_pct: float | None    # Computed: (pt - price) / price
    conviction: Literal["high", "medium", "low"]
    last_run_id: str | None
    last_reviewed: date | None
    next_catalyst: str | None   # e.g. "Earnings Apr 3"
    days_to_catalyst: int | None
    thesis_one_liner: str       # e.g. "GPU monopoly; data centre beat rhythm intact"
    open_red_team_challenges: int = 0
    status: Literal["current", "stale", "under_review", "watch_only"]
    # Stale = last reviewed > 45 days ago
```

**`CoverageBookService`** persists `CoverageRecord` per ticker (SQLite via `research_memory`). Updated automatically when a run completes — the published recommendation, price target, and thesis from the latest IC-approved output become the current `CoverageRecord` entry. 

**Frontend: `/coverage` page — "The Book"**

```
[ COVERAGE BOOK ]  15 names · Last updated: March 29, 2026
───────────────────────────────────────────────────────────────────────
Ticker  Name        Sector      Rec       PT     Current  Upside  Status
NVDA    NVIDIA      Compute     BUY ●     $198   $172     +15.1%  Current  ↑
AVGO    Broadcom    Compute     BUY ●     $205   $191     +7.3%   Current
TSM     TSMC        Compute     NEUTRAL   $175   $168     +4.2%   Current
CEG     Constant.   Power       BUY ●     $270   $254     +6.3%   STALE ⚠  Last: 52d ago
NVDA    ...         ...         ...       ...    ...      ...     ⚠ 1 open challenge
```

Sortable by: upside, rec, days since review, days to catalyst. "Stale" items flash a warning — a JPAM compliance standard is that formal coverage must be re-affirmed at minimum quarterly.

---

### RHY-3: Portfolio Blotter

The PM's screen. At any moment, what does the model portfolio actually look like versus where it should be? Part of the daily rhythm of a PM is checking this first thing — are any positions drifted significantly from target? Any mandate breach that opened overnight?

**Frontend: `/portfolio` page — "The Blotter"**

```
[ MODEL PORTFOLIO — MySuper Balanced ]  As of March 29, 2026 09:14 AEST
Benchmark: ASX 300 / MSCI World Blended  |  AUM: $100M (model)

Position    Weight  Target  Drift   PT      Current  Unrealised  Status
NVDA        4.2%    4.0%   +0.2%   $198    $172     +14.8%      ✓
AVGO        3.8%    4.0%   -0.2%   $205    $191     +7.1%       ✓
TSM         2.1%    2.5%   -0.4%   $175    $168     +3.8%       ✓
CEG         3.1%    3.0%   +0.1%   $270    $254     +6.3%       ✓
─────────────
Cash        8.2%    5.0%   +3.2%              ← DRIFT ALERT  ⚠
AI Sleeve   14.2%   15.0%  -0.8%              Within tolerance
────────────────────────────────────────────────────────────────
Portfolio   8.4% return vs benchmark 6.1%     Active return: +2.3%
```

Data sourced from: latest PM output (Stage 12 `PortfolioResult`), live prices from Stage 2 ingestor (FMP quote), benchmark prices from FMP. **Drift alerts** fire when any position drifts > 0.5% from target weight or any sleeve drifts > 2% from SAA. These appear in the Morning Brief and as a badge on the blotter nav item.

---

### RHY-4: Daily Standup Brief

Every morning at ~0800 AEST, the desk would have a standup. Each analyst briefly reports: "NVDA — maintaining BUY, 4 days to earnings, watching export control headlines. No change to thesis." This is auto-generated from the Coverage Book + Calendar + News Wire.

**`StandupBrief` schema:**

```python
# src/research_pipeline/schemas/standup.py

class AnalystStandupNote(BaseModel):
    analyst_role: str               # "Sector Analyst — Compute"
    coverage_items: list[str]       # Tickers this analyst covers
    status_per_ticker: dict[str, str]  # ticker → 1-sentence status
    overnight_events: list[str]     # Material news/events since last close
    action_items: list[str]         # e.g. ["Schedule AVGO pre-earnings run"]
    risk_flags: list[str] = []      # Open red team challenges on any coverage name

class StandupBrief(BaseModel):
    as_of: datetime
    headline: str                   # Overall tone: "Quiet overnight; watchful pre-earnings"
    market_open_context: str        # 1-sentence: market conditions at open
    analyst_notes: list[AnalystStandupNote]
    calendar_today: list[CalendarEvent]   # Events happening today
    upcoming_3_days: list[CalendarEvent]  # Next 3 days of events
    portfolio_drift_alerts: list[str]     # Any positions that drifted overnight
    compliance_flags: list[str]           # Any new compliance items
```

**`/api/standup`** — GET endpoint, returns today's `StandupBrief`. Cached per calendar day; regenerated at first request after midnight AEST. Surfaced on the dashboard as a collapsible **"Today's Brief"** panel just below the Morning Brief — formatted as a readable briefing note, not a data dump.

---

### RHY-5: News Wire

The right-rail news feed. Every item tagged with which holdings it touches and a classification of event type (catalyst, risk, regulatory, macro). Not a raw news dump — only items relevant to the coverage universe make it through. Items that triggered a `CalendarEvent` or `CoverageRecord.status` change are marked.

**`NewsWireItem` schema:**

```python
class NewsWireItem(BaseModel):
    wire_id: str
    headline: str
    source: str               # "Reuters", "Benzinga", "8-K Filing", "RBA Statement"
    published_at: datetime
    affected_tickers: list[str]  # Coverage book names mentioned
    event_type: Literal[
        "earnings_catalyst", "analyst_action", "filing",
        "regulatory", "macro", "geopolitical", "management_change",
        "m_and_a", "general_sector"
    ]
    sentiment: Literal["positive", "negative", "neutral"]
    urgency: Literal["watch", "material", "breaking"]
    summary: str              # 1-2 sentences — not the full article
    action_suggested: str | None  # e.g. "Consider scheduling NVDA update run"
```

**Frontend: `NewsWirePanel`**
- Lives in the right rail on the run detail page and as a collapsible panel on the dashboard
- Items arrive via SSE stream (reuses existing event infrastructure)
- Breaking items (8-K filings, surprise earnings, central bank decisions) pulse red momentarily
- Each item has a "Run Update" button that pre-populates `/runs/new` with the affected tickers
- Filtering: All / Earnings / Regulatory / Macro / Analyst Actions

---

### RHY-6: Research Track Record

Real PM desks track their calls. Every published research recommendation (from a completed IC-approved run) is logged with the price at time of publication and tracked against subsequent price action. This is both accountability and learning — when a call is wrong, the Run Narrative from that run explains what the reasoning was.

**`RecommendationRecord` schema:**

```python
# src/research_pipeline/schemas/track_record.py

class RecommendationRecord(BaseModel):
    record_id: str
    ticker: str
    run_id: str                    # Which run produced this rec
    published_at: datetime
    recommendation: ResearchRecommendation
    price_at_publication: float
    price_target: float | None
    conviction: Literal["high", "medium", "low"]

    # Updated daily by a background job
    current_price: float | None
    return_since_publication_pct: float | None
    days_held: int = 0
    status: Literal["open", "closed_target_hit",
                    "closed_stop_hit", "closed_updated", "superseded"]
    outcome: Literal["correct", "incorrect", "pending"] | None
    # "correct" = BUY and price > publication + 5%, or SELL and price < publication - 5%
    # evaluated at close of each position or after 90 days
```

**`TrackRecordService`** — background service that updates `return_since_publication_pct` and `outcome` for all open records daily. Persisted in SQLite (via `research_memory`).

**Frontend: `/track-record` page**

```
[ RESEARCH TRACK RECORD ]  Since inception · 28 recommendations · Win rate: 71.4%

Period: All Time ▾   Asset Class: All ▾

Ticker  Pub Date   Rec    Pub Price  Target  Current  Return   Outcome
NVDA    Jan 15     BUY    $142       $180    $172     +21.1%   ✓ Correct  (open)
AVGO    Jan 15     BUY    $178       $205    $191     +7.3%    → Pending  (open)
TSM     Feb 3      NEUTRAL $162      $175    $168     +3.7%    → Pending  (open)
─────────────────────────────────────────────────────────────────────────────────
Average return (BUY recs):    +12.3%   vs benchmark:  +6.1%
Hit rate (target reached):    71.4%
Avg days to target/resolution: 38 days
```

The track record page is also the honest accountability mirror: closed calls that were wrong have a "Post-Mortem" link to the original Run Narrative, showing what the reasoning was and what was missed. This is the research equivalent of a trade blotter — and it is what separates a serious institutional tool from a demo.

---

### RHY-7: Scenario Sandbox

Between formal pipeline runs, analysts need to quickly assess the impact of a macro change or a company-specific event without running all 14 stages. The Scenario Sandbox is a lightweight tool that takes a scenario definition and runs only the affected downstream stages — Macro (Stage 8), Quant/Risk (Stage 9), Portfolio (Stage 12).

**`ScenarioDefinition` schema:**

```python
# src/research_pipeline/schemas/scenario.py

class MacroShock(BaseModel):
    variable: str           # "fed_funds_rate", "au_10y_yield", "aud_usd", "wti_oil"
    current_value: float
    shock_value: float
    shock_label: str        # e.g. "Fed emergency cut -50bps"

class CompanyShock(BaseModel):
    ticker: str
    variable: str           # "eps", "revenue", "price_target"
    current_value: float
    shock_value: float
    shock_label: str        # e.g. "NVDA EPS miss -15%"

class ScenarioDefinition(BaseModel):
    scenario_name: str
    description: str
    scenario_type: Literal["macro", "company", "combined"]
    macro_shocks: list[MacroShock] = []
    company_shocks: list[CompanyShock] = []
    base_run_id: str        # The completed run to apply the scenario against
    stages_to_re_run: list[int] = [8, 9, 12]  # Only downstream impact stages
```

**`/api/scenario`** — POST endpoint, takes a `ScenarioDefinition`, re-runs only stages 8, 9, 12 (or as specified) against the base run's Stages 1–7 outputs held constant. Returns a `ScenarioResult` with portfolio impact, VaR delta, and narrative delta.

**Frontend: `/scenario` page — "What-If Sandbox"**

Pre-built scenario templates:
- **Fed cuts 50bps** — with estimated portfolio impact
- **RBA surprise hike** — AUD/USD impact, AU equity valuation compression
- **NVDA EPS miss -15%** — AI infra sleeve impact
- **China export control tightening** — semiconductor supply chain impact
- **US recession (GDP -1.5%)** — full portfolio stress

Custom scenario: sliders for each macro variable; a table of coverage-universe names with shock inputs; one-click "Run Scenario" button.

---

### RHY-8: Compliance Board

In a real asset management office, compliance is never out of sight. It lives in the peripheral vision — a corner of the screen that shows whether anything needs attention. Not just a background check but a live status board.

**`ComplianceStatus` schema:**

```python
# src/research_pipeline/schemas/compliance.py

class RestrictedListEntry(BaseModel):
    ticker: str
    reason: str                 # "Earnings blackout", "M&A advisory", "Material NPI"
    restricted_since: date
    restricted_until: date | None
    restriction_type: Literal["full", "buy_only", "sell_only", "research_blackout"]

class MandateBreach(BaseModel):
    breach_id: str
    run_id: str
    breach_type: str            # "concentration_limit", "sector_cap", "liquidity_floor"
    severity: Literal["warning", "breach", "critical"]
    description: str
    detected_at: datetime
    resolved: bool = False
    resolution_note: str | None = None

class ComplianceBoardPacket(BaseModel):
    as_of: datetime
    restricted_tickers: list[RestrictedListEntry] = []
    # Tickers that must not appear in new research or position changes

    open_breaches: list[MandateBreach] = []
    # Active mandate constraint violations from any run

    pre_clearance_pending: list[str] = []
    # Tickers where research is underway and pre-clearance is required

    overall_status: Literal["clear", "watch", "action_required"]
    # Used to colour the compliance badge in the top bar

    last_gate_outcomes: dict[str, bool] = {}
    # run_id → gate_passed for the last 5 runs
```

**Frontend:** A **compliance badge** in the top bar header (green dot when clear, amber when "watch", red when "action required"). Clicking it expands a drawer showing `ComplianceBoardPacket`. Breaches from `gate_9_risk` (concentration warnings) and `gate_14_governance` (IC reject) are automatically surfaced here. The restricted list is manually maintained via a simple admin UI.

---

### Session 23 Steps

| Step | ID | Task | Division | Effort | Files |
|---|---|---|---|---|---|
| 1 | RHY-1 | `CalendarEvent` schema + `ResearchCalendarService` pulling earnings (Benzinga), central bank dates (hardcoded schedule + FRED), economic releases (FRED release calendar) | Data Infrastructure | Medium | `schemas/calendar.py`, `services/research_calendar_service.py` |
| 2 | RHY-1b | `ResearchCalendarPanel` + `/calendar` page; earnings countdown, one-click "Prepare Update Run" | Frontend | Medium | `components/calendar/research-calendar-panel.tsx`, `app/calendar/page.tsx` |
| 3 | RHY-2 | `CoverageRecord` schema + `CoverageBookService` (SQLite via research_memory); auto-update on run completion; stale detection | Global Research | Medium | `schemas/coverage.py`, `services/coverage_book_service.py` |
| 4 | RHY-2b | `/coverage` page — the book; sortable table with rec/PT/upside/status/open challenges | Frontend | Medium | `app/coverage/page.tsx`, `components/coverage/coverage-table.tsx` |
| 5 | RHY-3 | `PortfolioBlotterService` — live positions vs target from last PM output; real-time price refresh; drift alert detection | Quantitative Research | Medium | `services/portfolio_blotter_service.py` |
| 6 | RHY-3b | `/portfolio` page — blotter table with weight, target, drift, unrealised; drift alert badges | Frontend | Medium | `app/portfolio/page.tsx`, `components/portfolio/blotter-table.tsx` |
| 7 | RHY-4 | `StandupBriefService` + `/api/standup` endpoint; synthesises CoverageBook + Calendar + NewsWire overnight | Global Research | Medium | `schemas/standup.py`, `services/standup_brief_service.py`, `api/routes/standup.py` |
| 8 | RHY-4b | `StandupBriefPanel` on dashboard — "Today's Brief" collapsible section | Frontend | Low | `components/standup/standup-brief-panel.tsx` |
| 9 | RHY-5 | `NewsWireItem` schema + `NewsWireService` consuming Benzinga + NewsAPI + 8-K events; filter against coverage tickers; classify event type + sentiment | Data Infrastructure | Medium | `schemas/news_wire.py`, `services/news_wire_service.py` |
| 10 | RHY-5b | `NewsWirePanel` — right-rail filterable live feed with SSE streaming; "Run Update" one-click actions | Frontend | Medium | `components/news-wire/news-wire-panel.tsx` |
| 11 | RHY-6 | `RecommendationRecord` schema + `TrackRecordService` — log every IC-approved rec; daily price update background job; outcome classification | Investment Governance | Medium | `schemas/track_record.py`, `services/track_record_service.py` |
| 12 | RHY-6b | `/track-record` page — performance table; win rate; average return vs benchmark; post-mortem links | Frontend | Medium | `app/track-record/page.tsx`, `components/track-record/track-record-table.tsx` |
| 13 | RHY-7 | `ScenarioDefinition` schema + `ScenarioRunner` service — partial re-run of stages 8, 9, 12 against frozen base outputs | Quantitative Research | High | `schemas/scenario.py`, `services/scenario_runner.py`, `api/routes/scenario.py` |
| 14 | RHY-7b | `/scenario` page — pre-built templates, custom sliders, result diff view | Frontend | High | `app/scenario/page.tsx`, `components/scenario/scenario-sandbox.tsx` |
| 15 | RHY-8 | `ComplianceBoardPacket` schema + `ComplianceBoardService` — aggregates gate outcomes, mandate breaches, restricted list | Investment Governance | Medium | `schemas/compliance.py`, `services/compliance_board_service.py` |
| 16 | RHY-8b | Compliance badge in top bar + `/compliance` page drawer; auto-populated from gate outputs | Frontend | Medium | `components/layout/top-bar.tsx`, `app/compliance/page.tsx` |
| 17 | RHY-SN | Update sidebar navigation — add Coverage, Portfolio, Calendar, Track Record, Scenario, Compliance to nav items with appropriate icons | Frontend | Low | `components/layout/sidebar.tsx` |
| 18 | RHY-TEST | `tests/test_session23.py` — 50+ tests; coverage book persistence; track record outcome classification; scenario partial re-run; compliance breach detection | Operations | Medium | `tests/test_session23.py` |

---

### Updated Sidebar Navigation (After Session 23)

```tsx
// frontend/src/components/layout/sidebar.tsx — updated navItems

const navItems = [
  // ── Research ──────────────────────────────
  { href: "/",             label: "Dashboard",      icon: LayoutDashboard },
  { href: "/morning-brief",label: "Morning Brief",  icon: Sun },
  { href: "/coverage",     label: "Coverage Book",  icon: BookOpen },
  { href: "/calendar",     label: "Research Calendar", icon: CalendarDays },
  { href: "/news",         label: "News Wire",       icon: Rss },

  // ── Portfolio & Risk ──────────────────────
  { href: "/portfolio",    label: "Portfolio Blotter", icon: BarChart2 },
  { href: "/track-record", label: "Track Record",   icon: TrendingUp },
  { href: "/scenario",     label: "Scenario Sandbox", icon: FlaskConical },

  // ── Runs ─────────────────────────────────
  { href: "/runs/new",     label: "New Run",        icon: PlayCircle },
  { href: "/runs",         label: "Active Runs",    icon: Activity },
  { href: "/saved",        label: "Saved Reports",  icon: History },

  // ── Governance ───────────────────────────
  { href: "/compliance",   label: "Compliance",     icon: Shield, badge: complianceStatus },
  { href: "/team",         label: "The Team",       icon: Users },
  { href: "/settings",     label: "Settings",       icon: Settings },
];
```

This is 14 navigation items across 4 logical groups — Research | Portfolio & Risk | Runs | Governance. The sidebar becomes a map of the entire institutional operation.

---

### What the Platform Looks Like After Sessions 22 + 23

Opening the platform at 0830 AEST, before any run:

- **Dashboard** — Morning Brief (market moves, regime flags, RBA held yesterday), Standup Brief ("4 names quiet overnight; AVGO earnings in 3 days — prepare update run"), compliance badge: **CLEAR**
- **Coverage Book** — 15 names, 3 with STALE status (>45 days since last review), 1 with an open Red Team challenge
- **Research Calendar** — today: US ISM release. In 3 days: AVGO earnings (pulsing action indicator). In 12 days: FOMC meeting.
- **Portfolio Blotter** — cash position drifted +3.2% vs target, drift alert visible. All equity positions within tolerance.
- **News Wire** — 3 items overnight: Benzinga analyst downgrade on rival (neutral for coverage), NVIDIA 8-K filed (earnings guidance — triggers calendar update), RBA statement published.
- **Track Record** — 28 recommendations, 71.4% win rate, average +8.3% vs +6.1% benchmark.

Click "Prepare Update Run" on the AVGO earnings calendar item → `/runs/new` pre-filled with `["AVGO"]`, labelled "AVGO Pre-Earnings Update — Q1 2026". Run it. IC votes 3/3 YES. Coverage Book updates automatically. Track record logs the new recommendation.

This is the daily rhythm of the office. Not just a machine you run when you want an answer — a living research environment.

---

### Session 23 Acceptance Criteria

**P0 — gating:**
- [ ] `CoverageBookService` updates `CoverageRecord` automatically on any completed IC-approved run
- [ ] `ResearchCalendarService` returns at minimum all FOMC and RBA dates for the next 90 days
- [ ] `PortfolioBlotter` shows live positions from the last completed PM output with drift alerts
- [ ] `/api/standup` returns a non-empty `StandupBrief` with at least one analyst note
- [ ] `TrackRecordService` logs a `RecommendationRecord` for every IC-approved run
- [ ] `ComplianceBoardPacket.overall_status` reflects actual open breaches from gate outputs
- [ ] Sidebar has all 14 nav items; compliance badge visible in top bar
- [ ] 50+ tests in `tests/test_session23.py`, all passing

**P1 — quality:**
- [ ] Coverage Book correctly marks records as STALE after 45 days
- [ ] News Wire shows at minimum Benzinga items for coverage tickers, tagged by event type
- [ ] Scenario Sandbox partial re-run produces a narrative delta (Stage 8 output different from base run)
- [ ] Track Record win rate computed correctly against a synthetic set of known outcomes
- [ ] Calendar "Prepare Update Run" button correctly pre-fills `/runs/new`
- [ ] Compliance badge turns amber when any open mandate breach exists

---

*Part Q added March 29, 2026. Parts P and Q together transform the platform from a pipeline runner into a living institutional environment — Part P gave it identity (who is doing what), Part Q gives it rhythm (the daily heartbeat of an asset management office). After both sessions, the experience is: you open the platform every morning, know immediately what is happening in markets, what needs attention across the coverage book, and move through the day driven by real institutional cadence rather than ad-hoc pipeline invocations.*

---

## Part R — Ten More: The Full Institutional Depth Layer (Session 24)

> **Source:** User directive March 29, 2026 — "think of more areas again — give me another 10"  
> **Context:** Parts P and Q covered identity (who is doing what) and daily rhythm (calendar, coverage book, blotter, news wire). Part R goes deeper still — the layers that distinguish a serious institutional platform from a sophisticated research tool: the live market monitor, client reporting, single-stock workbench, risk dashboard, earnings season infrastructure, ideas funnel, macro regime heatmap, institutional memory, street consensus comparison, and systematic stress testing.  
> **10 additions:** INS-1 through INS-10

---

### The Ten

| ID | Name | The institutional analogue |
|---|---|---|
| INS-1 | Live Market Monitor | The wall of screens — rates, FX, indices, commodities, all moving in real time |
| INS-2 | Client Reporting Suite | Quarterly client reports, fund fact sheets, performance attribution in house style |
| INS-3 | Single-Stock Workbench | Bloomberg single-stock equiv — full financials, earnings history, guidance revisions, insider timeline |
| INS-4 | Portfolio Risk Dashboard | Active share, tracking error, factor exposures, CVaR — always visible, always current |
| INS-5 | Earnings Season Mode | Enhanced mode during earnings: queue, rapid re-run (sub-30-min), surprise tracker |
| INS-6 | Watchlist & Ideas Funnel | Pre-coverage tracking — from "idea" through "on watch" to "initiation" |
| INS-7 | Macro Regime Heatmap | Visual economic conditions matrix — the cycle positioning dashboard |
| INS-8 | Institutional Memory / Knowledge Library | Search all past research, claims, theses — the accumulated firm intelligence |
| INS-9 | Street vs House Tracker | Where our calls differ from consensus — the differentiated-view map |
| INS-10 | Portfolio Stress Test Suite | Systematic historical and hypothetical stress scenarios run against the model portfolio |

---

### INS-1: Live Market Monitor — The Wall of Screens

Every institutional trading floor has it: a wall of screens showing every major rate, FX pair, equity index, credit spread, and commodity ticking in real time. Not a static snapshot — a live feed where you feel the market. This is the ambient backdrop of a professional investment environment.

**`MarketMonitorPanel` — `/market` page + dashboard widget**

Layout: a full-screen grid of live tiles, grouped by category:

```
[ RATES & BONDS ]                        [ EQUITY INDICES ]
AU Cash Rate    4.10%   —                ASX 200     8,142   +0.3%  ↑
AU 10Y AGB      4.38%   +3bps  ↑         S&P 500     5,641   +0.8%  ↑
US Fed Funds    4.25%   —                NASDAQ      18,220  +1.1%  ↑
US 10Y          4.42%   +8bps  ↑         MSCI World  3,847   +0.6%  ↑
US 2Y           4.81%   +4bps  ↑
2s/10s Curve   -39bps            inverted  ↓
                                         [ CREDIT SPREADS ]
[ FX ]                                   US IG OAS     88bps  -2bps  ↓✓
AUD/USD         0.6312  +0.4%  ↑         US HY OAS    312bps  -5bps  ↓✓
USD/JPY         149.8   -0.2%  ↓         EM Spread    268bps  —
EUR/USD         1.0821  +0.1%  ↑
AUD/EUR         0.5834  +0.3%  ↑         [ COMMODITIES ]
                                         WTI Oil      $81.4   +0.6%  ↑
                                         Gold         $2,312  +0.2%  ↑
                                         Copper       $4.31   +1.2%  ↑
                                         LNG          $9.84   -0.4%  ↓
```

Colours: green = up/tightening (risk-on), red = down/widening, white = flat. Arrows animated on tick. Values refresh every 30 seconds via a dedicated `/api/market-monitor` endpoint pulling FRED + FMP + RBA.

**Additional feature — "Rate of Change" alerts:** If any monitored item moves more than a configurable threshold intraday (e.g. AU 10Y moves >10bps), it pulses orange and adds to the dashboard's morning brief alerts. This is the institutional equivalent of a Bloomberg alert blasting.

**Schemas:**

```python
class MarketTile(BaseModel):
    label: str
    category: Literal["rates", "fx", "equity", "credit", "commodity"]
    current_value: float
    change_1d_abs: float
    change_1d_pct: float
    direction: Literal["up", "down", "flat"]
    alert_threshold_pct: float = 0.5
    is_alerting: bool = False
    last_updated: datetime
    source: str  # "fred", "fmp", "rba", "calculated"

class MarketMonitorPacket(BaseModel):
    as_of: datetime
    tiles: list[MarketTile]
    overall_risk_tone: Literal["risk_on", "neutral", "risk_off"]
    # Derived from: equities up + spreads tight = risk_on; opposite = risk_off
    intraday_alerts: list[str] = []
```

---

### INS-2: Client Reporting Suite

Every JPAM relationship manager sends quarterly client reports and monthly fund fact sheets. These are a distinct output from research notes — they are client-facing, performance-focused, and written in a non-technical style. The platform should generate them automatically from completed run outputs and blotter data.

**Two document types:**

**A. Fund Fact Sheet (monthly)**

In the style of a real JPAM fund fact sheet — a 2-page PDF containing:
- Fund name, strategy, AUM, benchmark, inception date
- Performance table: 1M / 3M / 6M / 1Y / 3Y / Inception vs benchmark
- Top 10 holdings with weight, sector, return contribution
- Sector allocation pie (current vs benchmark)
- Geographic allocation
- Market commentary (2 paragraphs — drawn from the most recent `RunNarrative.executive_narrative`)
- Risk statistics: volatility, tracking error, Sharpe ratio, max drawdown
- Disclaimer footer

**B. Quarterly Client Letter (3 pages)**

- Cover page: client name, fund name, period, PM name
- Performance summary paragraph (written by `ReportNarrativeAgent` in client register)
- Portfolio review: what we owned, what we added/trimmed and why
- Outlook: macro view and positioning intentions
- Appendix: full holdings table

```python
# src/research_pipeline/schemas/client_report.py

class PerformanceTable(BaseModel):
    periods: dict[str, float]   # "1M": 2.3, "3M": 4.1, "6M": 7.8, "1Y": 14.2
    benchmark_periods: dict[str, float]
    active_return: dict[str, float]

class FundFactSheet(BaseModel):
    fund_name: str
    strategy_description: str
    aum_millions: float
    benchmark: str
    inception_date: date
    report_date: date
    performance: PerformanceTable
    top_10_holdings: list[dict]  # ticker, name, weight, sector, contribution
    sector_allocation: dict[str, float]  # sector → weight %
    geo_allocation: dict[str, float]    # "Australia", "United States", etc.
    market_commentary: str      # 2 paragraphs from RunNarrative
    risk_statistics: dict[str, float]   # vol, TE, Sharpe, max_dd
    generated_at: datetime

class ClientLetter(BaseModel):
    client_name: str
    fund_name: str
    period: str                 # "Q1 2026"
    pm_name: str
    performance_summary: str    # LLM-generated client-register prose
    portfolio_review: str
    outlook: str
    holdings_table: list[dict]
    generated_at: datetime
```

**`ClientReportingService`** — generates both document types as PDF (via existing `fpdf2` infrastructure in `app.py`) and as structured JSON for the frontend renderer. `/api/client-report/factsheet` and `/api/client-report/quarterly-letter` endpoints.

**Frontend: `/reports` page**

- List of generated client documents with date and type
- "Generate Fact Sheet" and "Generate Quarterly Letter" buttons
- Preview pane + download as PDF
- Client management: add/edit client profiles linked to the `ClientProfile` schema

---

### INS-3: Single-Stock Workbench

When an analyst sits down to prepare for an earnings call or initiate coverage on a new name, they pull up a Bloomberg single-stock view: all the financial history, guidance comparisons, analyst target history, insider transaction timeline, news history, and relative valuation in one place. This doesn't require running the full pipeline — it is a pre-run, pre-analysis tool for deep due diligence.

**`/workbench/[ticker]` page**

Layout: 6 panels in a dense grid — all pulling from the existing services with no LLM inference involved:

```
[ NVDA — NVIDIA Corporation | Compute | NASDAQ | $172.40 (+1.2%) ]

┌─────────────────────┐  ┌──────────────────────────┐  ┌─────────────────┐
│ FINANCIALS HISTORY  │  │ EARNINGS TRACKER          │  │ VALUATION COMPS │
│ Revenue (8Q TTM)    │  │ Q4'25: EPS $0.89 +12%    │  │ NTM P/E    28.4x│
│ ████░░░░           │  │ beat +8% / guide +2%      │  │ Sector avg 32.1x│
│ Gross Margin 74.2%  │  │ Q3'25: EPS $0.81 +24%    │  │ EV/EBITDA  22.1x│
│ FCF Yield   3.2%   │  │ beat +6% / guide flat     │  │ P/FCF      31.4x│
└─────────────────────┘  └──────────────────────────┘  └─────────────────┘

┌─────────────────────┐  ┌──────────────────────────┐  ┌─────────────────┐
│ ANALYST TARGETS     │  │ INSIDER ACTIVITY          │  │ NEWS & FILINGS  │
│ High   $240         │  │ ▲ Jensen buys 50K @ $151  │  │ 8-K Mar 29 →    │
│ Mean   $198         │  │ ▲ CFO buys 12K @ $159     │  │ 10-Q Feb 19 →   │
│ Low    $155         │  │ ▼ Board sell 8K @ $174    │  │ Benzinga: UPG   │
│ You    $198 ● House │  │ Net: cluster BUY signal   │  │ Reuters: capex  │
└─────────────────────┘  └──────────────────────────┘  └─────────────────┘
```

Each panel is click-expandable to a full history view. A "Run Deep Dive" button at the top launches a single-ticker full pipeline run. A "Add to Watchlist" button feeds INS-6.

**Data sourced from:** `SECApiService` (Form 4 insider, 8-K/10-Q), `BenzingaService` (analyst targets history, rating changes), `QualitativeDataService` (earnings transcripts), `MarketDataIngestor` (financials, ratios). All existing services — no new data sourcing required. Pure presentation layer over already-built sources.

---

### INS-4: Portfolio Risk Dashboard

The Risk division's screen. On a real PM desk, risk metrics are visible at all times — active share vs benchmark, factor exposures, tracking error, tail risk. Post-Sessions 9 and 20, the quant engine produces rich risk output. This gives it a permanent home.

**`/risk` page — always-current risk view**

```
[ PORTFOLIO RISK DASHBOARD ]  Model: MySuper Balanced  |  As of March 29, 2026

ACTIVE POSITIONING                  FACTOR EXPOSURES (vs benchmark)
Active Share          68.4%         Value           +0.32 ↑ overweight
Tracking Error         4.2% pa      Momentum        -0.18 ↓ underweight
Information Ratio      1.21         Quality         +0.41 ↑ overweight
Beta vs benchmark      1.08         Size            -0.05 ≈ neutral
                                    Low Volatility   -0.22 ↓ underweight

TAIL RISK                           TOP 5 RISK CONTRIBUTORS
VaR (1-day 95%)        -1.8%        1. NVDA        22% of total risk
CVaR (1-day 95%)       -2.6%        2. AVGO        18%
Max Drawdown (6M)      -11.2%       3. AI Sleeve   35% (sleeve level)
Stress VaR (2020 COVID) -18.4%      4. CEG          9%
                                    5. Concentration  7%
MANDATE COMPLIANCE
Concentration limit    ✓ PASS       Liquidity floor  ✓ PASS
Sector cap             ✓ PASS       Currency hedge   ⚠ REVIEW
```

**Auto-refresh:** Recalculates factor exposures daily using last completed quant stage output (Stage 9 `QuantPacket`). Price-dependent metrics (VaR, beta) refresh with live prices every 60 seconds. Any metric that breaches a warning threshold turns amber and propagates to the Compliance Board badge.

```python
class FactorExposure(BaseModel):
    factor: str         # "value", "momentum", "quality", "size", "low_vol"
    exposure: float     # Z-score vs benchmark
    direction: Literal["overweight", "neutral", "underweight"]
    benchmark_exposure: float

class RiskDashboardPacket(BaseModel):
    run_id: str
    as_of: datetime
    active_share: float
    tracking_error_pa: float
    information_ratio: float | None
    portfolio_beta: float
    factor_exposures: list[FactorExposure]
    var_1d_95: float
    cvar_1d_95: float
    max_drawdown_6m: float | None
    stress_scenarios: dict[str, float]  # scenario_name → portfolio loss %
    top_risk_contributors: list[dict]   # ticker/sleeve → % of total active risk
    mandate_compliance_flags: dict[str, bool]
```

---

### INS-5: Earnings Season Mode

Four times a year, the pace of the office changes. Earnings season — roughly January, April, July, October — means rapid-fire: 10 companies reporting in 5 days, positions needing rapid reassessment after a miss or beat. The platform needs an enhanced mode for this period with a dedicated queue, condensed run profile, and surprise tracker.

**Three components:**

**A. Earnings Queue**
A priority-ordered list of upcoming reporters in the coverage universe, sorted by days until release. Each entry shows: expected EPS, expected revenue (from `BenzingaService` / FMP estimates), prior quarter surprise history, and the recommendation-at-risk (current rec vs what the model implies for the post-earnings price).

**B. Rapid Earnings Update Run**
A condensed 8-stage run profile (skip Orchestration, Reconciliation is lightweight, skip full IC — auto-approve if no material red team challenge) targeting sub-20-minute turnaround. Triggered automatically after an earnings event is detected in the News Wire.

```python
class EarningsSeason(BaseModel):
    is_active: bool
    season_label: str           # "Q1 2026 Earnings Season"
    season_start: date
    season_end: date
    reporters_in_universe: list[EarningsReporter] = []

class EarningsReporter(BaseModel):
    ticker: str
    report_date: date
    days_until: int
    time_of_day: Literal["before_open", "after_close", "during_market", "unknown"]
    expected_eps: float | None
    expected_revenue_bn: float | None
    prior_4q_surprise_avg_pct: float | None  # How much this company typically beats/misses
    current_rec: str
    current_pt: float | None
    recommendation_at_risk: bool  # True if a miss of >10% would flip rec
    rapid_run_queued: bool = False
    rapid_run_id: str | None = None
```

**C. Earnings Surprise Tracker**
After a company reports, log the actual vs expected, the stock's intraday reaction, whether the guidance was raised/maintained/lowered, and what the recommendation update was. Kept permanently in the `TrackRecordService` earnings history.

**Frontend: `/earnings-season` page**
- Active during earnings season, accessible year-round as historical archive
- Queue tab: countdown table with recommendation-at-risk highlighting
- Surprise tracker tab: actual vs expected, reaction table
- "Season summary" after close: how many beats, misses, rec changes

---

### INS-6: Watchlist & Ideas Funnel

Before a name goes into formal coverage it goes through an ideas pipeline: something catches an analyst's eye (sector rotation, macro theme, M&A overhang, regulatory catalyst), it gets added to watch, monitored informally, and eventually either initiated or dropped. This is the front of the research pipeline — the "deal sourcing" equivalent.

**`WatchlistItem` schema and three-stage funnel:**

```python
class WatchlistStage(str, Enum):
    IDEA      = "idea"        # Just noticed — minimal monitoring
    WATCH     = "watch"       # Active informal tracking — news wire + price alerts
    ANALYSIS  = "analysis"    # Formal pre-initiation work underway
    INITIATED = "initiated"   # Moved to Coverage Book → full formal coverage
    DROPPED   = "dropped"     # Reviewed and decided not to initiate

class WatchlistItem(BaseModel):
    ticker: str
    company_name: str
    sector: str
    added_by: str               # Analyst role / "Portfolio Strategist" / "PM"
    added_date: date
    thesis_hypothesis: str      # The one-sentence original investment hypothesis
    stage: WatchlistStage
    catalyst_for_initiation: str | None  # "Earnings season" / "Sector dislocation" / etc.
    target_initiation_date: date | None
    priority: Literal["high", "medium", "low"]
    news_wire_monitoring: bool = True  # Auto-add to news wire filter
    price_alert_threshold_pct: float = 5.0  # Alert at ±5% move
    stage_history: list[dict] = []   # Audit trail of stage transitions
    notes: str | None = None
```

**Frontend: `/watchlist` page**

A Kanban-style board: four columns (Idea / Watch / Analysis / Initiated). Each card shows ticker, hypothesis, days in this stage, and next catalyst. Drag-and-drop to promote through stages. "Initiate Coverage" button on the Analysis column fires a pre-populated `/runs/new` with the ticker. "Drop" archives with a required reason note (institutional discipline — a JPAM desk documents why a name was dropped, not just what was added).

The Ideas column shows incoming suggestions from the News Wire (any coverage-adjacent company with a significant event gets auto-suggested as an idea). Price alerts for Watch-stage names surface in the Morning Brief.

---

### INS-7: Macro Regime Heatmap

Every institutional macro team runs a framework for reading the economic cycle — which combination of growth, inflation, policy stance, credit conditions, and risk appetite characterises the current environment. This determines sector rotation positioning, duration positioning, and credit positioning. The platform has macro analysis in Stage 8, but it surfaces only within individual runs. This makes it permanent and visual.

**The heatmap: a 5×4 matrix of current vs recent regime scores**

```
MACRO REGIME DASHBOARD  |  As of March 29, 2026  |  Regime: LATE CYCLE · EASING BIAS

                 Current   1M ago   3M ago   Direction
GROWTH           ●●●●○     ●●●○○    ●●●●○    ↓ Softening
INFLATION        ●●●○○     ●●●○○    ●●●●○    ↓ Moderating ✓
POLICY STANCE    ●●●○○     ●●○○○    ●○○○○    ↑ Moving to Neutral
CREDIT CONDITIONS●●●●○     ●●●○○    ●●○○○    ↑ Improving ✓
RISK APPETITE    ●●●●○     ●●●○○    ●●●○○    ↑ Improving ✓

Regime signal: Late Cycle / Easing Beginning
Sector implication: Prefer Quality, Duration, Utilities, Healthcare over Cyclicals
Portfolio positioning: Current portfolio is 68% aligned with regime signal
```

Each dimension (1–5 score) derived from real data already in the system: FRED indicators, RBA, EIA, credit spreads. A `MacroRegimeService` converts raw indicator readings into regime scores on each dimension. The heatmap is built from the most recent Stage 8 outputs plus daily indicator updates.

```python
class RegimeDimension(BaseModel):
    dimension: Literal["growth", "inflation", "policy_stance",
                        "credit_conditions", "risk_appetite"]
    current_score: int          # 1–5: 1=deeply negative → 5=strongly positive
    prior_month_score: int
    prior_quarter_score: int
    trend: Literal["improving", "stable", "deteriorating"]
    key_indicators: list[str]   # What drove this score

class MacroRegimePacket(BaseModel):
    as_of: datetime
    regime_label: str           # "Late Cycle — Easing Bias"
    regime_confidence: float    # 0.0–1.0
    dimensions: list[RegimeDimension]
    cycle_phase: Literal["early_cycle", "mid_cycle", "late_cycle", "recession"]
    sector_rotation_signal: dict[str, str]  # sector → "overweight/neutral/underweight"
    duration_signal: Literal["extend", "neutral", "shorten"]
    credit_signal: Literal["add_risk", "neutral", "reduce_risk"]
    portfolio_regime_alignment_pct: float   # How aligned current positions are
```

**Auto-updates daily.** Stage 8 macro output feeds into `MacroRegimeService`; it also runs independently at market open using fresh FRED + RBA data. The regime label and cycle phase propagate into the Morning Brief and the Portfolio Risk Dashboard.

---

### INS-8: Institutional Memory / Knowledge Library

The JPAM research team has been doing this for years. There is accumulated firm knowledge: past research notes, historical theses on covered names, how the team's view on a name evolved over time, which red team challenges proved correct. This is the institutional memory layer — and it already exists in the backend as `ResearchMemory` (SQLite FTS5). What is missing is a front door.

**`/library` page — the firm's accumulated intelligence**

```
[ KNOWLEDGE LIBRARY ]  Search across all research, claims, and theses
───────────────────────────────────────────────────────────────────────

[ 🔍 Search: "NVDA export control"             ]  [ Filter: Claims | Theses | Runs | All ]

Results (14):

▶ NVDA · Red Team Challenge · March 15, 2026
  "Export control downside not reflected in consensus EPS — modelled
   -15% FY26 revenue if China restrictions tighten"  [OPEN CHALLENGE]

▶ NVDA · Thesis Evolution · Jan 2026 → Mar 2026
  Recommendation upgraded BUY → STRONG BUY (Jan 28) · downgraded to BUY
  after export control challenge (Mar 15)

▶ NVDA · Claim · "Data centre revenue $36.5B FY26 — Source: 10-K SEC API §7 MD&A"
  Confidence: PASS · Source: TIER_1_PRIMARY · Run: r_202501_15

▶ Run r_202501_15 · Jan 15, 2026 · Universe: NVDA, AVGO, TSM  [full run →]
```

**Search capability** (already exists in `ResearchMemory.search()` using FTS5):
- Full-text search across all claim ledger text, thesis statements, run narratives
- Filter by: date range, ticker, run ID, claim status (PASS/CAVEAT/FAIL), source tier
- "Name history" view: timeline of all research produced on a specific ticker — how the view evolved
- "Claim ancestry" view: for any current claim, see if an equivalent claim appeared in prior runs and whether it was confirmed or contradicted

**`KnowledgeLibraryService`** — thin wrapper over existing `ResearchMemory`, adding structured search, filters, and the "name history" and "claim ancestry" queries. Most of the infrastructure already exists — this is primarily a frontend and query-layer task.

---

### INS-9: Street vs House Tracker

One of the things that makes institutional research valuable is when it differs from consensus. If every bank has NVDA at $198 buy, there is no alpha in agreeing. The value is when the house view is meaningfully different — higher conviction, lower target, different thesis — and that view proves correct. The Street vs House Tracker is the differentiation map.

**`ConsensusComparisonService`** — for every covered name, maintain the house view (from `CoverageBook`) alongside the current street consensus (from `BenzingaService` and FMP analyst estimates). Compute the divergence.

```python
class StreetVsHouse(BaseModel):
    ticker: str
    as_of: date

    # House view (from CoverageBook)
    house_rec: str              # "BUY", "NEUTRAL", etc.
    house_pt: float | None
    house_conviction: str
    house_last_updated: date

    # Street consensus (from Benzinga + FMP)
    street_consensus_rec: str   # "Overweight", "Buy", "Neutral" normalised
    street_mean_pt: float | None
    street_high_pt: float | None
    street_low_pt: float | None
    street_analyst_count: int
    street_buy_pct: float       # % of street with buy/overweight
    street_sell_pct: float

    # Divergence
    pt_divergence_pct: float    # (house_pt - street_mean_pt) / street_mean_pt
    rec_alignment: Literal["aligned", "more_bullish", "more_bearish", "contrarian"]
    # "contrarian" = house SELL vs street >70% buy, or vice versa
    alpha_opportunity: bool     # True when rec_alignment ∈ {more_bullish, contrarian}
                                # and conviction is "high"
    divergence_narrative: str   # 1 sentence: "House 8% above consensus PT; 
                                # differentiated by export control downside not in street EPS"
```

**Frontend: `/street-vs-house` page**

```
[ STREET vs HOUSE TRACKER ]  Coverage universe · 15 names · 6 differentiated

Ticker  House     House PT  Street Mean  Divergence  Alignment       Alpha?
NVDA    BUY ●     $198       $197         +0.5%      ≈ Aligned       —
AVGO    BUY ●     $205       $218         -6.0%      ↓ More bearish  ★ Yes
TSM     NEUTRAL   $175       $183         -4.4%      ↓ More bearish  —
CEG     BUY ●     $270       $245         +10.2%     ↑ More bullish  ★ Yes
VST     NEUTRAL   $112       $98          +14.3%     ↑↑ Contrarian  ★★ Yes
```

Stars indicate genuine differentiation — where the house view is not just where the street is. "Contrarian" positions (house SELL vs street consensus BUY, or vice versa) are flagged prominently and trigger a prompt in the Coverage Book: "High divergence — schedule conviction review".

---

### INS-10: Portfolio Stress Test Suite

Distinct from the Scenario Sandbox (which is forward-looking / hypothetical). The Stress Test Suite runs the current model portfolio through systematic historical stress events and standardised hypothetical shocks, producing a structured comparison of portfolio drawdown vs benchmark in each scenario. This is the Risk team's quarterly deliverable and an APRA SPS 530 requirement for superannuation funds.

**Pre-built stress scenarios:**

```python
class StressScenario(BaseModel):
    scenario_id: str
    name: str
    description: str
    scenario_type: Literal["historical", "hypothetical", "regulatory"]
    # Historical: replays actual market moves from a reference period
    # Hypothetical: applies defined shocks to current portfolio
    # Regulatory: APRA-specified stress scenarios

    # For historical scenarios
    reference_period_start: date | None   # e.g. 2020-02-20 (COVID crash)
    reference_period_end: date | None     # e.g. 2020-03-23

    # For hypothetical / regulatory scenarios
    equity_shock_pct: float = 0.0        # e.g. -25.0 (25% equity market fall)
    rate_shock_bps: float = 0.0          # e.g. +200 (rates +200bps)
    credit_spread_shock_bps: float = 0.0
    fx_shock_pct: float = 0.0            # AUD/USD change %
    vol_shock_multiplier: float = 1.0    # e.g. 2.0 = VIX doubles

STANDARD_SCENARIOS: list[StressScenario] = [
    # Historical
    StressScenario(id="covid_2020", name="COVID Crash (Feb–Mar 2020)",
                   type="historical", equity_shock=-34, ...),
    StressScenario(id="gfc_2008", name="GFC (Oct 2008 peak–trough)",
                   type="historical", equity_shock=-46, ...),
    StressScenario(id="dot_com_2000", name="Dot-com Bust (2000–2002)",
                   type="historical", equity_shock=-49, ...),
    StressScenario(id="rate_shock_2022", name="Rate Shock (2022 bond selloff)",
                   type="historical", rate_shock=+400, ...),
    # Hypothetical
    StressScenario(id="equity_25", name="Equity Bear (-25%)",
                   type="hypothetical", equity_shock=-25),
    StressScenario(id="rates_200", name="Rates +200bps",
                   type="hypothetical", rate_shock=+200),
    StressScenario(id="china_taiwan", name="China-Taiwan Escalation",
                   type="hypothetical", equity_shock=-18, fx_shock=-8, ...),
    StressScenario(id="ai_bust", name="AI Capex Collapse (-50% sector)",
                   type="hypothetical", equity_shock=-50, ...),  # sector-targeted
    # Regulatory (APRA SPS 530)
    StressScenario(id="apra_1", name="APRA Scenario A: Severe Global Recession",
                   type="regulatory", equity_shock=-35, rate_shock=+150, ...),
    StressScenario(id="apra_2", name="APRA Scenario B: Stagflation",
                   type="regulatory", equity_shock=-20, rate_shock=+300, ...),
]
```

**`StressTestRunner`** — applies each scenario to the current `PortfolioResult` (from Stage 12), computes estimated portfolio return under shock using factor exposures + sector weights + duration. Does not require a full pipeline re-run — uses the existing quant output.

**Frontend: `/stress-test` page**

```
[ STRESS TEST SUITE ]  Portfolio: MySuper Balanced  |  Run April 2026

                     Portfolio  Benchmark  Active   Status
COVID Crash 2020      -18.4%    -26.5%    +8.1%   ✓ Outperform
GFC 2008              -28.7%    -38.2%    +9.5%   ✓ Outperform
Rate Shock 2022        -9.2%    -11.1%    +1.9%   ✓ Outperform
Equity Bear -25%      -15.8%    -21.0%    +5.2%   ✓ Outperform
Rates +200bps         -11.3%     -9.8%    -1.5%   ⚠ Underperform
China-Taiwan          -16.1%    -19.4%    +3.3%   ✓ Outperform
AI Capex Collapse     -24.3%    -15.2%    -9.1%   ⚠ ALERT — sleeve concentration
APRA Scenario A       -20.1%    -26.2%    +6.1%   ✓ PASS
APRA Scenario B       -13.4%    -12.9%    -0.5%   ⚠ REVIEW
```

Any scenario where the portfolio underperforms the benchmark by more than 2% is flagged. The AI Capex Collapse scenario is automatically important given the current universe — and the system knows this because `AssetClassRouter` knows the AI infra sleeve weighting.

---

### Session 24 Steps

| Step | ID | Task | Division | Effort | Files |
|---|---|---|---|---|---|
| 1 | INS-1 | `MarketTile` + `MarketMonitorPacket` schemas; `MarketMonitorService` pulling FRED + FMP + RBA; `/api/market-monitor` endpoint | Data Infrastructure | Medium | `schemas/market_monitor.py`, `services/market_monitor_service.py` |
| 2 | INS-1b | `MarketMonitorPanel` — live tile grid with category grouping, direction coloring, intraday alerts | Frontend | Medium | `components/market/market-monitor-panel.tsx`, `app/market/page.tsx` |
| 3 | INS-2 | `FundFactSheet` + `ClientLetter` schemas; `ClientReportingService` generating both as PDF + JSON | Global Research | High | `schemas/client_report.py`, `services/client_reporting_service.py` |
| 4 | INS-2b | `/reports` page — document list, generate buttons, PDF preview + download | Frontend | Medium | `app/reports/page.tsx`, `components/reports/report-generator.tsx` |
| 5 | INS-3 | `SingleStockWorkbench` — `/workbench/[ticker]` page; 6-panel dense grid pulling from existing services; no new data sources | Frontend | High | `app/workbench/[ticker]/page.tsx`, `components/workbench/` |
| 6 | INS-4 | `FactorExposure` + `RiskDashboardPacket` schemas; `RiskDashboardService` aggregating Stage 9 quant output + live prices; auto-refresh | Quantitative Research | Medium | `schemas/risk_dashboard.py`, `services/risk_dashboard_service.py` |
| 7 | INS-4b | `/risk` page — risk metrics grid; factor exposure bars; mandate compliance table; auto-refresh every 60s | Frontend | Medium | `app/risk/page.tsx`, `components/risk/risk-dashboard.tsx` |
| 8 | INS-5 | `EarningsSeason` + `EarningsReporter` schemas; `EarningsSeasonService`; rapid run profile (condensed 8-stage); earnings surprise tracker log | Global Research | High | `schemas/earnings_season.py`, `services/earnings_season_service.py` |
| 9 | INS-5b | `/earnings-season` page — queue, countdown, surprise tracker, season summary | Frontend | Medium | `app/earnings-season/page.tsx` |
| 10 | INS-6 | `WatchlistItem` schema + `WatchlistService` (SQLite); auto-suggestions from News Wire; stage transition audit trail | Global Research | Medium | `schemas/watchlist.py`, `services/watchlist_service.py` |
| 11 | INS-6b | `/watchlist` Kanban page — 4-column board; drag-and-drop stages; "Initiate Coverage" action | Frontend | High | `app/watchlist/page.tsx`, `components/watchlist/kanban-board.tsx` |
| 12 | INS-7 | `RegimeDimension` + `MacroRegimePacket` schemas; `MacroRegimeService` scoring 5 dimensions from FRED + RBA + Stage 8; regime label + cycle phase derivation | Global Research | Medium | `schemas/macro_regime.py`, `services/macro_regime_service.py` |
| 13 | INS-7b | `/macro-regime` page — 5×4 heatmap grid; trend arrows; cycle phase indicator; portfolio alignment % | Frontend | Medium | `app/macro-regime/page.tsx`, `components/macro/regime-heatmap.tsx` |
| 14 | INS-8 | `KnowledgeLibraryService` — wraps existing `ResearchMemory` FTS5; adds structured filters, name history, claim ancestry queries | Global Research | Low | `services/knowledge_library_service.py`, `api/routes/library.py` |
| 15 | INS-8b | `/library` page — search bar, filter panel, result cards with deep links to runs/claims | Frontend | Medium | `app/library/page.tsx`, `components/library/search-results.tsx` |
| 16 | INS-9 | `StreetVsHouse` schema + `ConsensusComparisonService` — per-ticker divergence calc using CoverageBook + Benzinga/FMP consensus | Global Research | Medium | `schemas/street_vs_house.py`, `services/consensus_comparison_service.py` |
| 17 | INS-9b | `/street-vs-house` page — divergence table; alpha opportunity flags; contrarian position alerts | Frontend | Medium | `app/street-vs-house/page.tsx` |
| 18 | INS-10 | `StressScenario` + 10 standard scenarios; `StressTestRunner` applying shocks to quant output; benchmark comparison | Quantitative Research | High | `schemas/stress_test.py`, `services/stress_test_runner.py` |
| 19 | INS-10b | `/stress-test` page — scenario table with portfolio vs benchmark; underperformance alerts; APRA pass/fail | Frontend | Medium | `app/stress-test/page.tsx`, `components/risk/stress-test-table.tsx` |
| 20 | INS-TEST | `tests/test_session24.py` — 60+ tests covering all 10 INS items; regime scoring; stress test calculation; watchlist stage transitions; consensus divergence | Operations | Medium | `tests/test_session24.py` |

---

### Final Sidebar Navigation (After Session 24)

```tsx
const navSections = [
  {
    label: "MARKETS",
    items: [
      { href: "/",              label: "Dashboard",        icon: LayoutDashboard },
      { href: "/market",        label: "Market Monitor",   icon: Monitor },
      { href: "/macro-regime",  label: "Macro Regime",     icon: Globe },
      { href: "/news",          label: "News Wire",        icon: Rss },
    ]
  },
  {
    label: "RESEARCH",
    items: [
      { href: "/coverage",      label: "Coverage Book",    icon: BookOpen },
      { href: "/watchlist",     label: "Watchlist",        icon: Eye },
      { href: "/workbench",     label: "Stock Workbench",   icon: Microscope },
      { href: "/library",       label: "Knowledge Library", icon: Library },
      { href: "/street-vs-house",label: "Street vs House",  icon: GitCompare },
      { href: "/calendar",      label: "Research Calendar", icon: CalendarDays },
      { href: "/earnings-season",label: "Earnings Season",  icon: TrendingUp },
    ]
  },
  {
    label: "PORTFOLIO & RISK",
    items: [
      { href: "/portfolio",     label: "Portfolio Blotter", icon: BarChart2 },
      { href: "/risk",          label: "Risk Dashboard",    icon: ShieldAlert },
      { href: "/scenario",      label: "Scenario Sandbox",  icon: FlaskConical },
      { href: "/stress-test",   label: "Stress Test Suite", icon: Zap },
      { href: "/track-record",  label: "Track Record",      icon: Award },
    ]
  },
  {
    label: "RUNS",
    items: [
      { href: "/runs/new",      label: "New Run",           icon: PlayCircle },
      { href: "/runs",          label: "Active Runs",       icon: Activity },
      { href: "/saved",         label: "Saved Reports",     icon: History },
    ]
  },
  {
    label: "CLIENT & GOVERNANCE",
    items: [
      { href: "/reports",       label: "Client Reports",    icon: FileText },
      { href: "/compliance",    label: "Compliance",        icon: Shield, badge: true },
      { href: "/team",          label: "The Team",          icon: Users },
      { href: "/settings",      label: "Settings",          icon: Settings },
    ]
  }
];
```

26 navigation destinations across 5 logical sections. Every area of an institutional asset management operation is represented.

---

### What the Full Platform Covers (Sessions P + Q + R Combined)

| Layer | Sessions | What it adds |
|---|---|---|
| **Identity** | P (EXP-1–12) | The people — who is working, roles, IC room, run narrative, morning brief |
| **Daily Rhythm** | Q (RHY-1–8) | The calendar, coverage book, blotter, news wire, track record, compliance board, standup brief, scenario sandbox |
| **Depth** | R (INS-1–10) | The market monitor, client reports, stock workbench, risk dashboard, earnings season, ideas funnel, macro regime, knowledge library, street vs house, stress test suite |

The experience of the complete platform, from opening screen to published research:

1. **0830 AEST** — Morning Brief loads. RBA held. NVDA 8-K filed overnight. AI sleeve 0.8% below target. No compliance flags.
2. **Research Calendar** — AVGO earnings in 3 days. Pre-earnings run queued automatically.
3. **Macro Regime** — Late Cycle, Easing Bias. Sector signal: favour Quality, Duration. Portfolio 68% aligned.
4. **Market Monitor** — US 10Y +8bps, spread tightening, risk-on tone. AUD/USD +0.4%.
5. **News Wire** — NVDA 8-K: revised capex guidance upward. Benzinga: 4 analyst target upgrades. One click → Pre-populate NVDA workbench.
6. **Stock Workbench** — Pull NVDA single-stock view. Insider cluster buy signal. Street mean target $197, house $198.
7. **Street vs House** — AVGO: house $205 vs street $218 (more bearish by 6%). Pre-earnings review flagged.
8. **Run AVGO pre-earnings update** — Research floor activates. Evidence Librarian reviews 10-Q. Red Team challenges margin guidance. IC votes 3/3 PUBLISH.
9. **Coverage Book** — AVGO updated: BUY, PT $212 (revised up). Stale flag cleared.
10. **Track Record** — recommendation logged. Portfolio blotter updates. Drift alert cleared.
11. **Risk Dashboard** — factor exposures updated. APRA SPS 530 compliance: PASS.
12. **Client Reports** — "Generate Q1 2026 Fact Sheet" — 2-page PDF ready to send.

This is JPAM. Every cog visible, every role understood, every output grounded, every decision traceable.

---

### Session 24 Acceptance Criteria

**P0 — gating:**
- [ ] `MarketMonitorPacket` populates from FRED + FMP with at minimum 12 tiles (rates, FX, equity, credit)
- [ ] `FundFactSheet` PDF generated without error from a completed run output
- [ ] `/workbench/NVDA` renders all 6 panels with real data from existing services
- [ ] `RiskDashboardPacket` auto-refreshes from Stage 9 output + live prices
- [ ] `EarningsSeasonService` returns correct queue sorted by days-until for all coverage tickers
- [ ] `WatchlistService` persists `WatchlistItem` across restarts
- [ ] `MacroRegimePacket` scores all 5 dimensions from FRED + most recent Stage 8 output
- [ ] `KnowledgeLibraryService.search()` returns results across claim ledgers and run narratives
- [ ] `StreetVsHouse` divergence calculated for all covered names with Benzinga consensus
- [ ] `StressTestRunner` produces portfolio loss estimates for all 10 standard scenarios
- [ ] 60+ tests in `tests/test_session24.py`, all passing

**P1 — quality:**
- [ ] Market Monitor intraday alert fires correctly when a tile moves beyond threshold
- [ ] Watchlist Kanban drag-and-drop persists stage transition in audit trail
- [ ] Earnings surprise tracker logs actual vs expected after a real reporting event
- [ ] Knowledge Library returns claim-level results with source tier visible
- [ ] Stress Test Suite correctly identifies AI Capex Collapse as a portfolio-specific risk given AI sleeve weighting
- [ ] Client Letter generated with non-generic market commentary drawn from run narrative

---

*Part R added March 29, 2026. Ten additions completing the institutional depth layer: live market monitor, client reporting, single-stock workbench, portfolio risk dashboard, earnings season mode, watchlist/ideas funnel, macro regime heatmap, knowledge library, street-vs-house differentiation tracker, and systematic stress test suite. Together with Parts P and Q, the platform now covers the full operational surface of a JPAM-style institutional asset management office.*
