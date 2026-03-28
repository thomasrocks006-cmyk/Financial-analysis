# Platform Improvements & Full-Polish Roadmap

> **Document type:** Living engineering + product roadmap  
> **Last updated:** March 28, 2026  
> **Current state:** Sessions 1–10 complete · 607 / 607 tests passing · commit `0642dfe`  
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

## Part A — Architecture Repair (Session 11)

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
- [ ] `SECTOR_ROUTING` config externalised (ARC-5 fix)
- [ ] `docker-compose.yml` for local production deployment
- [ ] Grafana / Prometheus metrics stub for observability export
- [ ] Blue/green pipeline deployment with canary comparison

---

## Part G — Division Gap Score Targets

Current weighted scores post-sessions 1–10. Projected scores after each session block.

| Division | S10 Score | After S11 | After S12 | After S13 | After S14 | After E-1–10 | JPAM Target |
|---|---|---|---|---|---|---|---|
| Global Research | 8.0 | 8.3 | 8.8 | **9.2** | 9.2 | **9.5** | 9.0 |
| Quantitative Research | 8.5 | 8.7 | 9.0 | 9.2 | 9.2 | **9.7** | 9.0 |
| Portfolio Management | 8.0 | 8.3 | 8.7 | 9.0 | **9.3** | **9.5** | 8.5 |
| Investment Governance | 8.8 | 9.0 | 9.0 | 9.1 | **9.4** | 9.4 | 9.5 |
| Performance Attribution | 7.5 | 7.5 | 8.0 | 8.5 | 8.5 | **9.3** | 8.5 |
| ESG / Sustainable Investing | 6.5 | 6.5 | 6.8 | 7.0 | 7.0 | **8.0** | 7.5 |
| Operations & Technology | 8.8 | 9.0 | 9.0 | 9.1 | 9.1 | **9.4** | 9.0 |
| Client Solutions / Reporting | 8.5 | 8.5 | 8.7 | **9.0** | 9.2 | **9.5** | 8.5 |
| **Macro Economy** | **2.0** | 2.0 | **7.5** | 8.0 | 8.0 | **8.5** | 8.0 |
| **Weighted Overall** | **8.3** | 8.5 | 8.8 | 9.0 | 9.1 | **9.4** | 9.0 |

> Note: Macro Economy is a new division added to the scoring matrix. It drags the overall average significantly — fixing it in Session 12 lifts the platform from ~8.3 to ~8.8 overall.

---

## Part H — Prioritised Backlog (All Items in Sequence)

| Priority | ID | Item | Session | Effort |
|---|---|---|---|---|
| 1 | ARC-4 | Fix Stage 7/8 execution order | S11 | Trivial |
| 2 | ARC-1 | Wire Stage 8 macro to S9/S10/S11/S12 | S11 | Low |
| 3 | ARC-10 | Fix FI Agent hardcoded stub | S11 | Trivial |
| 4 | ARC-6 | Red Team macro + risk inputs | S11 | Low |
| 5 | ARC-7 | Reviewer macro + risk inputs | S11 | Low |
| 6 | ARC-8 | PM Agent macro context | S11 | Low |
| 7 | ARC-9 | Macro Agent receives market data | S11 | Low |
| 8 | ARC-3 | VaR uses live returns (not random) | S11 | Low |
| 9 | ARC-5 | SECTOR_ROUTING config | S11 | Medium |
| 10 | ARC-2 | Real report assembly (stock cards + PM doc) | S11 | Medium |
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

Current test count: **607**  
Projected after S11–S14 + E items: **607 + 32 + 35 + 30 + 30 + 50 ≈ 784 tests**

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

| ID | New issue | Why it changes the plan |
|---|---|---|
| ISS-1 | `MacroContextPacket` schema missing | ARC-1 needs typed validation, not raw dict threading |
| ISS-3 | No `GenericSectorAnalystAgent` fallback | ARC-5 remains incomplete otherwise |
| ISS-4 | `ValuationCard` → `StockCard` mapper unspecified | ARC-2 can still produce malformed report cards |
| ISS-9 | Agent quality checks are non-fatal | Missing required keys still pass through the system |
| ISS-10 | Gemini package/import mismatch | E-8 fallback chain can break on first use |
| ISS-12 | Macro agents lack required key contracts | Session 12 needs unified Stage 8 packet design |
| ISS-13 | No ASX prompt coverage | AU market support remains shallow even with AU data |
| ISS-16 | BHB benchmark still synthetic | E-4 needs deeper scope than currently written |
| ISS-20 | Streamlit `result` / `run_result` mismatch | Frontend observability can fail despite backend success |
| ISS-27 | No live API E2E pipeline test | Production-readiness score remains overstated |

### Session remapping after the assessment

| Session | Existing scope | Newly added residual issues |
|---|---|---|
| Session 11 | ARC-1 through ARC-10 | ISS-1, ISS-3, ISS-4, ISS-9, ISS-10, ISS-20 |
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

*This document supersedes the brainstorm sections in ARCHITECTURE.md §13.9 and TRACKER.md §12 for the purposes of implementation planning. Those sections remain as quick-reference summaries. It now also incorporates the merged `PROJECT_ISSUES_ASSESSMENT.md` residual-issue audit and the explicit decision not to merge PR #1 as-is.*
