# Project Tracker — AI Research & Portfolio Platform

> **Last updated:** March 29, 2026  
> **Test suite:** 941 / 941 passing (+ 6 pre-existing errors in session 7/8)  
> **Commit:** see below — sessions 16 + 17 complete

---

## Status Summary

| Area | Status |
|---|---|
| ROADMAP Phases 0–7 | All **COMPLETE** |
| Session 2 debt-clearing (10 items) | All **COMPLETE** |
| Session 3 (P-5, P-6, ACT-6) | All **COMPLETE** |
| Session 4 (P-4, P-7, P-8) | All **COMPLETE** |
| Session 5 (ACT-S5-1, ACT-S5-2) | All **COMPLETE** |
| Session 6 (ACT-S6-1 through ACT-S6-5) | All **COMPLETE** |
| Session 7 (ACT-S7-1 through ACT-S7-5) | All **COMPLETE** |
| Session 8 (ACT-S8-1 through ACT-S8-5) | All **COMPLETE** |
| Session 9 (ACT-S9-1 through ACT-S9-5) | All **COMPLETE** |
| Session 10 (ACT-S10-1 through ACT-S10-5) | All **COMPLETE** |
| **Architecture Repair (ARC-1 through ARC-10)** | ✅ **COMPLETE — `2b6a360`** |
| **Session 11 (revised)** | ✅ **COMPLETE — `2b6a360`** |
| **Session 12 — Macro Economy & Australia/US Markets** | ✅ **COMPLETE — `12c7086`** |
| **Session 13 — Depth & Quality** | ✅ **COMPLETE — `34d7949`** |
| **Session 14 — Superannuation & AU Client Context** | ✅ **COMPLETE — `29272dd`** |
| **PROJECT_ISSUES_ASSESSMENT.md (PR #2)** | ✅ **MERGED — March 28, 2026** |
| **Residual issues (ISS-1, ISS-3, ISS-4, ISS-9, ISS-10, ISS-20)** | ✅ **COMPLETE — `2b6a360`** |
| **PR #1 Core system improvements** | ⛔ **Do not merge as-is** |
| **Frontend migration decision (Streamlit → Next.js + FastAPI)** | ✅ **DECIDED — March 28, 2026** |
| **Phase 1 — adapter truthfulness** | ✅ **COMPLETE — `2b6a360`** |
| **Phase 2 — engine event stream** | ✅ **COMPLETE — `7a62757`** |
| **Phase 3 — unified storage + RunRequest** | ✅ **COMPLETE — `7a62757`** |
| **Phase 4 — FastAPI layer (Session 15)** | ✅ **COMPLETE — `7a62757`** |
| **Phase 5 + 6 — Next.js UI + charts (Session 16)** | ✅ **COMPLETE** |
| **Phase 7 — traceability (Session 17)** | ✅ **COMPLETE** |
| **Session 15 — FastAPI Event-Streaming API** | ✅ **COMPLETE — `7a62757`** |
| **Session 16 — Premium Next.js Frontend** | ✅ **COMPLETE** |
| **Session 17 — Traceability & Provenance** | ✅ **COMPLETE** |

---

## 1. Completed Items (Sessions 1 & 2)

| ID | Task | Done |
|---|---|---|
| D-1 | Qualitative data pipeline — Pydantic v2 schemas + async 8-source service | ✅ |
| D-2 | Prompts audit | ⏭ deferred (human judgment) |
| D-3 | Golden test suite — real assertions in `golden_tests.py` | ✅ |
| D-4 | Quant Research Analyst Agent — LLM over factor/VaR/ETF outputs | ✅ |
| A-1 | `pipeline_runner.py` → thin adapter (`pipeline_adapter.py`) | ✅ |
| A-2 | `storage.py` unified with `RunRegistryService` | ✅ |
| A-3 | Binary `PASS`/`FAIL` only — `PASS_WITH_DISCLOSURE` removed | ✅ |
| A-4 | IC `_pm_vote` no longer auto-approves unexpected statuses | ✅ |
| P-1 | `ARCHITECTURE.md` scorecard updated (overall 6.6 → 7.8) | ✅ |
| P-2 | E2E smoke tests — 19 tests, full 15-stage pipeline mocked | ✅ |

---

## 2. Current Work Queue

| ID | Area | Task | Priority | Effort | Status |
|---|---|---|---|---|---|
| P-5 | **Data** | yfinance as third data source fallback | Medium | Low | ✅ `86f5c1c` |
| ACT-6 | **Quant** | Drawdown analysis + CVaR in `RiskEngine` + `RiskPacket` | High | Medium | ✅ `86f5c1c` |
| ACT-5 | **Governance** | `SelfAuditPacket` schema attached to every run | High | Low | ✅ (prior session) |
| P-6 | **Services** | DCF extension — EV/EBITDA and P/E relative valuation | Medium | Medium | ✅ `86f5c1c` |
| ACT-7 | **Quant** | Benchmark-relative analytics module (`benchmark_module.py`) | Medium | Medium | ✅ (prior session) |
| P-4 | **Frontend** | Wire ETF overlap + BHB + benchmark analytics into Streamlit | Medium | Medium | ✅ session 4 |
| P-7 | **Agents** | Fixed-income thesis agent | Medium | High | ✅ session 4 |
| P-8 | **CI** | Weekly live-data validation run as CI job | Low | Low | ✅ session 4 |
| ACT-S5-1 | **Engine** | Fix engine.py gate logic — gates 9/12/13 no longer hardcoded True | High | Low | ✅ session 5 |
| ACT-S5-2 | **Agents** | Fix base_agent.parse_output — 3-strategy JSON extraction incl. preamble | High | Low | ✅ session 5 |

### Session 6 — Completed Work

| ID | Area | Task | JPAM Division | Priority | Status |
|---|---|---|---|---|---|
| ACT-S6-1 | **Governance** | Wire `SelfAuditPacket` into every engine run — `_build_self_audit_packet()`, persisted to disk, on `RunRecord` | Investment Governance | High | ✅ `608c286` |
| ACT-S6-2 | **Agents** | `EsgAnalystAgent` — E/S/G scoring per ticker [0-100], exclusion trigger, score clamping; wired into Stage 6 (non-blocking) | ESG / Sustainable Investing | High | ✅ `608c286` |
| ACT-S6-3 | **Frontend** | PDF export button in Report tab — `fpdf2` cover page + body; `_generate_report_pdf()` helper | Client Solutions | Medium | ✅ `608c286` |
| ACT-S6-4 | **Schemas** | Close A-1 debt — `pipeline_runner.py` `DeprecationWarning` on import; `app.py` switched to `pipeline_adapter` | Operations | Medium | ✅ `608c286` |
| ACT-S6-5 | **Testing** | `tests/test_session6.py` — 27 new tests covering SelfAuditPacket wiring, ESG agent, PDF export, deprecation | Operations | Medium | ✅ `608c286` |

### Session 7 — Completed Work

| ID | Area | Task | JPAM Division | Priority | Status |
|---|---|---|---|---|---|
| ACT-S7-1 | **Attribution** | BHB Performance Attribution with synthetic returns (`_generate_synthetic_returns`, `_compute_bhb_attribution`) wired into Stage 14 | Performance Attribution | High | ✅ `2530399` |
| ACT-S7-2 | **ESG** | `ESGService` baseline profiles enriching `EsgAnalystAgent` prompts — per-ticker E/S/G baselines, controversy flags, heuristic profiles | ESG / Sustainable Investing | High | ✅ `2530399` |
| ACT-S7-3 | **Audit** | `SelfAuditPacket` per-stage latency (`stage_latencies_ms`) + `total_pipeline_duration_s`; `_emit_audit_packet` called on ALL exits (success + every early gate failure) | Investment Governance | Medium | ✅ `2530399` |
| ACT-S7-4 | **Portfolio** | `PortfolioOptimisationEngine` — risk parity, min-variance, max-Sharpe; wired into Stage 12 `optimisation_results` | Portfolio Management | High | ✅ `2530399` |
| ACT-S7-5 | **Testing** | `tests/test_session7.py` — 23 new tests covering attribution, ESG enrichment, optimiser, latency fields | Operations | Low | ✅ `2530399` |

### Session 8 — Completed Work

| ID | Area | Task | JPAM Division | Priority | Status |
|---|---|---|---|---|---|
| ACT-S8-1 | **Data** | `LiveReturnStore` — yfinance-backed daily return fetcher with in-memory cache; `_get_returns()` engine helper tries live first, falls back to synthetic | Performance Attribution | High | ✅ `a7e520e` |
| ACT-S8-2 | **Portfolio** | Rebalancing signals wired into Stage 12 output (`rebalance_proposal`); Streamlit Rebalancing Signals panel with trade-level detail | Portfolio Management | High | ✅ `a7e520e` |
| ACT-S8-3 | **ESG** | `ESGService.load_from_csv()` — ingest external ESG scores (ticker, E/S/G, controversy) from CSV; validates enum, invalidates cache | ESG / Sustainable Investing | Medium | ✅ `a7e520e` |
| ACT-S8-4 | **Governance** | `PromptRegistry` wired into engine `_scan_prompt_registry()`; `SelfAuditPacket.prompt_drift_reports` populated on every run | Investment Governance | Medium | ✅ `a7e520e` |
| ACT-S8-5 | **Testing** | `tests/test_session8.py` — 26 new tests covering LiveReturnStore, rebalancing wiring, ESG CSV ingest, PromptRegistry wiring | Operations | Low | ✅ `a7e520e` |

### Session 9 — Completed Work

| ID | Area | Task | JPAM Division | Priority | Status |
|---|---|---|---|---|---|
| ACT-S9-1 | **ESG** | `tests/fixtures/esg_sample.csv` — 20-row MSCI-style fixture; `load_from_csv()` round-trip verified; new tickers (INTC, QCOM, etc.) added | ESG / Sustainable Investing | High | ✅ `93f5ba5` |
| ACT-S9-2 | **Governance** | `tests/test_prompt_regression.py` — 50 regression tests; CI gate detects accidental prompt edits; `mark_regression_passed/failed` lifecycle tested | Operations | Medium | ✅ `93f5ba5` |
| ACT-S9-3 | **Governance** | `SelfAuditPacket.rebalancing_summary` — trade count, turnover%, impact bps, trigger; populated in `_emit_audit_packet`; surfaced in Observability UI | Investment Governance | Medium | ✅ `93f5ba5` |
| ACT-S9-4 | **Data** | `LiveReturnStore._download_individual()` — ticker-by-ticker fallback when batch fails; `_get_returns()` blends partial live + synthetic per ticker | Performance Attribution | Medium | ✅ `93f5ba5` |
| ACT-S9-5 | **Testing** | `tests/test_session9.py` — 26 new tests covering ESG fixture, LiveReturnStore hardening, rebalancing_summary schema, prompt registry integration | Operations | Low | ✅ `93f5ba5` |

---

## 3. Post-Roadmap Build Candidates (original)

| ID | Area | Task | JPAM Division | Priority | Effort |
|---|---|---|---|---|---|
| P-3 | **Agent** | Quant Research Agent | Quant Research | High | Medium | ✅ done as D-4 |
| P-4 | **Frontend** | Wire ETF overlap, observability, BHB attribution into Streamlit | Client Solutions | Medium | Medium | 🔲 |
| P-5 | **Data** | yfinance fallback when FMP/Finnhub quotas exhausted | Operations | Medium | Low | 🔲 |
| P-6 | **Services** | DCF extension — EV/EBITDA and P/E methods | Quant Research | Medium | Medium | 🔲 |
| P-7 | **Agents** | Fixed-income thesis agent | Research | Medium | High | 🔲 |
| P-8 | **Operations** | Live run validation — weekly CI job against real APIs | Operations | Low | Low | 🔲 |

---

## 4. Division-Level Maturity

*Scores updated through session 10.*

| Division | Session 10 Score | JPAM Target | Gap | Primary Remaining Gap |
|---|---|---|---|---|
| Global Research | **8.0 / 10** ↑ | 9.0 / 10 | 1.0 | Agent output quality gate ✅; still no live news integration |
| Quantitative Research | **8.5 / 10** ↑ | 9.0 / 10 | 0.5 | Live returns → OLS factor refit ✅; no live factor model refit from external data |
| Portfolio Management | **8.0 / 10** | 8.5 / 10 | 0.5 | Rebalancing signals live in UI ✅; no execution integration |
| Investment Governance | **8.8 / 10** | 9.5 / 10 | 0.7 | Prompt CI regression gate ✅; `rebalancing_summary` in audit ✅ |
| Performance Attribution | **7.5 / 10** ↑ | 8.5 / 10 | 1.0 | `data_source` tracking ✅; full live BHB pipeline still needs real market data |
| ESG / Sustainable Investing | **6.5 / 10** | 7.5 / 10 | 1.0 | CSV export ✅; real MSCI dataset still outstanding |
| Operations & Technology | **8.8 / 10** | 9.0 / 10 | 0.2 | 607 tests; all passing |
| Client Solutions / Reporting | **8.5 / 10** ↑ | 8.5 / 10 | 0.0 | ESG CSV download button ✅ — target met |
| **Weighted platform score** | **8.8 / 10** ↑ | **9.0 / 10** | **0.2** | Live live factor data ✅; real ESG dataset remaining main gap |

---

## 5. Test Coverage

| File | Tests | Area |
|---|---|---|
| `test_deferred_items.py` | 56 | D-1 schemas/parsers, D-4 agent, A-3/A-4 governance |
| `test_gates.py` | ~30 | Gate enforcement |
| `test_governance.py` | ~25 | Governance schemas + IC |
| `test_memory_audit.py` | ~20 | Research memory + audit |
| `test_new_schemas.py` | ~20 | New Pydantic models |
| `test_performance_services.py` | ~25 | BHB attribution, performance tracker |
| `test_phase1_hardening.py` | 24 | Agent parse_output + LLM fallback |
| `test_phase6_7.py` | 52 | Memory injection, observability, universe config, report formats |
| `test_pipeline.py` | ~30 | Pipeline engine + stages |
| `test_quant_engines.py` | ~30 | Factor engine, VaR, optimisation |
| `test_schemas.py` | ~30 | Schema validation |
| `test_services.py` | ~20 | Deterministic services |
| `test_smoke_pipeline.py` | 19 | E2E pipeline + adapter |
| `test_next_section.py` | 49 | P-5 yfinance fallback, P-6 relative valuation, ACT-6 RiskPacket, P-7 FI agent, P-4 panel |
| `test_session5.py` | 26 | ACT-S5-1 gate logic hardening (gates 9/12/13), ACT-S5-2 base_agent parse_output strategies |
| `test_session6.py` | 27 | ACT-S6-1 SelfAuditPacket wiring, ACT-S6-2 ESG agent, ACT-S6-3 PDF export, ACT-S6-4 deprecation |
| `test_session7.py` | 23 | ACT-S7-1 BHB attribution, ACT-S7-2 ESG enrichment, ACT-S7-3 latency fields, ACT-S7-4 optimiser |
| `test_session8.py` | 26 | ACT-S8-1 LiveReturnStore, ACT-S8-2 rebalancing wiring, ACT-S8-3 ESG CSV ingest, ACT-S8-4 PromptRegistry |
| `test_prompt_regression.py` | 24 | ACT-S9-2 prompt CI gate — hash stability, drift detection, regression marking, CI simulation |
| `test_session9.py` | 26 | ACT-S9-1 ESG fixture, ACT-S9-4 live return hardening, ACT-S9-3 rebalancing_summary, ACT-S9-2 integration |
| `test_session10.py` | 28 | ACT-S10-1 BHB data_source, ACT-S10-2 ESG CSV export, ACT-S10-3 agent quality gate, ACT-S10-4 factor live data |
| `test_session11.py` | 60 | ARC-1–10 pipeline wiring, ISS-1 MacroContextPacket, ISS-3 GenericSectorAnalystAgent, ISS-4 StockCard adapter, ISS-9 _VALIDATION_FATAL, ISS-10 Gemini fallback, ISS-20 adapter key fix |
| **Total** | **667** | All passing |

---

## 6. Quick Reference — Key Files

| Purpose | Path |
|---|---|
| Main pipeline orchestrator | `src/research_pipeline/pipeline/engine.py` |
| All 14 LLM agents | `src/research_pipeline/agents/` |
| Generic sector analyst agent (new S11) | `src/research_pipeline/agents/generic_sector_analyst.py` |
| MacroContextPacket schema (new S11) | `src/research_pipeline/schemas/macro.py` |
| ESG analyst agent (new S6) | `src/research_pipeline/agents/esg_analyst.py` |
| ESG baseline service (new S7) | `src/research_pipeline/services/esg_service.py` |
| Portfolio optimisation engine (new S7) | `src/research_pipeline/services/portfolio_optimisation.py` |
| Live return store (new S8) | `src/research_pipeline/services/live_return_store.py` |
| Rebalancing engine (new S7, wired S8) | `src/research_pipeline/services/rebalancing_engine.py` |
| Prompt registry (new S7, wired S8) | `src/research_pipeline/services/prompt_registry.py` |
| ESG fixture (new S9) | `tests/fixtures/esg_sample.csv` |
| Deterministic services | `src/research_pipeline/services/` |
| Qualitative schemas (new) | `src/research_pipeline/schemas/qualitative.py` |
| Quant Research Agent (new) | `src/research_pipeline/agents/quant_research_analyst.py` |
| Pipeline adapter (new) | `src/frontend/pipeline_adapter.py` |
| Governance schemas | `src/research_pipeline/schemas/governance.py` |
| Universe configs | `src/research_pipeline/config/universe_config.py` |
| Market data ingestor | `src/research_pipeline/services/market_data_ingestor.py` |
| Risk engine | `src/research_pipeline/services/risk_engine.py` |
| DCF engine | `src/research_pipeline/services/dcf_engine.py` |
| ETF overlap engine | `src/research_pipeline/services/etf_overlap_engine.py` |
| Run registry | `src/research_pipeline/services/run_registry.py` |


---

## Status Summary

| Area | Status |
|---|---|
| ROADMAP Phases 0–7 | All **COMPLETE** |
| Deferred ROADMAP items | 4 items outstanding |
| Architectural debt | 4 open items |
| Post-roadmap build candidates | 8 items |

---

## 1. ROADMAP Deferred Items

These were explicitly marked ⬜ Deferred within completed phases. They are real gaps, not future aspirations.

| ID | Task | Phase | Why Deferred | Effort |
|---|---|---|---|---|
| D-1 | **Qualitative data pipeline** — formalise news / earnings transcript / SEC filing ingestion into typed schemas | 1.7 | Frontend has partial implementation; backend schema contract not defined | Medium |
| D-2 | **Prompts audit** — review all 11 agent prompts against JPAM research standards; assign version tags | 1.8 | Requires human judgment + prompt engineering; not pure code | Low |
| D-3 | **Golden test suite** — implement real assertion logic for all 10 test categories in `golden_tests.py` | 1.9 | `golden_tests.py` line 148 still has `passed = True # placeholder` | Low |
| D-4 | **Quant Research Agent** — LLM agent that interprets factor exposures and risk decomposition outputs | 2.10 | No LLM agent written yet; deterministic quant services exist but no analyst layer | Medium |

---

## 2. Architectural Debt

Live code issues that remain from the architecture review.

| ID | File | Issue | Severity | Status |
|---|---|---|---|---|
| A-1 | `src/frontend/pipeline_runner.py` | 1,851-line duplicate orchestration engine — fixes to `engine.py` not reflected here | **Critical** | 🔲 open |
| A-2 | `src/frontend/storage.py` | Two separate persistence systems (frontend JSON vs backend registry) | High | ✅ **DONE** session 2 (storage mirrors to registry) |
| A-3 | `src/research_pipeline/schemas/portfolio.py` | `PublicationStatus.PASS_WITH_DISCLOSURE` still in enum | Medium | ✅ **DONE** session 2 (enum value removed) |
| A-4 | `src/research_pipeline/services/investment_committee.py` | `pass_with_disclosure` branch in `_pm_vote` | Medium | ✅ **DONE** session 2 (branch removed; treated as FAIL) |

---

## 3. Post-Roadmap Build Candidates

| ID | Area | Task | JPAM Division | Priority | Status |
|---|---|---|---|---|---|
| P-1 | **Documentation** | Update `ARCHITECTURE.md` scorecard | — | High | ✅ Done (sessions 2–5) |
| P-2 | **Testing** | E2E pipeline smoke tests | Operations | High | ✅ Done session 2 (19 tests) |
| P-3 | **Agent** | Quant Research Agent | Quant Research | High | ✅ Done as D-4 (session 2) |
| P-4 | **Frontend** | Quant Analytics panel in Streamlit | Client Solutions | Medium | ✅ Done session 4 |
| P-5 | **Data** | yfinance fallback data source | Operations | Medium | ✅ Done session 3 |
| P-6 | **Services** | DCF extension — EV/EBITDA + P/E | Quant Research | Medium | ✅ Done session 3 |
| P-7 | **Agents** | Fixed-income thesis agent | Research | Medium | ✅ Done session 4 |
| P-8 | **Operations** | Weekly live-data CI job | Operations | Low | ✅ Done session 4 |

---

## 4. Division-Level Maturity

*Stale pre-build baseline. See live scores in §4 of the primary tracker section above.*

| Division | Pre-build Score | Session 5 Score | JPAM Target | Remaining Gap |
|---|---|---|---|---|
| Global Research | 6.5 | **7.5** | 9.0 | 1.5 |
| Quantitative Research | 5.5 | **7.5** | 9.0 | 1.5 |
| Portfolio Management | 6.0 | **6.5** | 8.5 | 2.0 |
| Investment Governance | 4.5 | **8.0** ↑ | 9.5 | 1.5 |
| Performance Attribution | 0.0 | **0** | 8.5 | 8.5 |
| ESG / Sustainable Investing | 0.0 | **0** | 7.5 | 7.5 |
| Operations & Technology | 6.5 | **8.3** ↑ | 9.0 | 0.7 |
| Client Solutions / Reporting | 6.5 | **7.5** | 8.5 | 1.0 |
| **Weighted platform score** | **4.4** | **7.1** ↑ | **9.0** | **1.9** |

---

## 5. Test Coverage

*This lower section is a legacy view; the live test table is in §5 of the primary tracker section.*

| File | Tests | Area |
|---|---|---|
| `test_gates.py` | ~30 | Gate enforcement |
| `test_governance.py` | ~25 | Governance schemas + IC |
| `test_memory_audit.py` | ~20 | Research memory + audit |
| `test_new_schemas.py` | ~20 | New Pydantic models |
| `test_performance_services.py` | ~25 | BHB attribution, performance tracker |
| `test_phase1_hardening.py` | 24 | Agent parse_output + LLM fallback |
| `test_phase6_7.py` | 52 | Memory injection, observability, universe config, report formats |
| `test_pipeline.py` | ~30 | Pipeline engine + stages |
| `test_quant_engines.py` | ~30 | Factor engine, VaR, optimisation |
| `test_schemas.py` | ~30 | Schema validation |
| `test_services.py` | ~20 | Deterministic services |
| `test_smoke_pipeline.py` | 19 | E2E pipeline smoke tests + adapter |
| `test_deferred_items.py` | 56 | D-1/D-4/A-3/A-4 debt items |
| `test_next_section.py` | 49 | Sessions 3–4 features |
| `test_session5.py` | 26 | Sessions 5 gate hardening + parse_output |
| **Total** | **453** | All passing |

---

## 6. Quick Reference — Key Files

| Purpose | Path |
|---|---|
| Main pipeline orchestrator | `src/research_pipeline/pipeline/engine.py` |
| All 13 LLM agents | `src/research_pipeline/agents/` |
| 30+ deterministic services | `src/research_pipeline/services/` |
| Governance schemas (incl. SelfAuditPacket) | `src/research_pipeline/schemas/governance.py` |
| Fixed-income analyst agent | `src/research_pipeline/agents/fixed_income_analyst.py` |
| Quant Research Agent | `src/research_pipeline/agents/quant_research_analyst.py` |
| Pipeline adapter | `src/frontend/pipeline_adapter.py` |
| Universe configs | `src/research_pipeline/config/universe_config.py` |
| LLM fallback + parse_output | `src/research_pipeline/agents/base_agent.py` |
| Observability | `src/research_pipeline/services/observability.py` |
| ETF overlap engine | `src/research_pipeline/services/etf_overlap_engine.py` |
| Risk engine + VaR | `src/research_pipeline/services/risk_engine.py` |
| BHB benchmark module | `src/research_pipeline/services/benchmark_module.py` |
| Run registry | `src/research_pipeline/services/run_registry.py` |
| CI weekly live-data | `.github/workflows/weekly_live_data.yml` |

---

## 7. Architecture Repair Backlog (ARC-1 through ARC-10)

All bugs located in `src/research_pipeline/pipeline/engine.py`. Scheduled for **Session 11**.

| ID | Bug | Impact | File / Location | Status |
|---|---|---|---|---|
| ARC-1 | Stage 8 macro outputs (`stage_outputs[8]`) never read by Stages 9, 10, 11, or 12 — macro context silently discarded | **Very High** | `engine.py` stages 9–12 `format_input` calls | ✅ `2b6a360` |
| ARC-2 | Stage 13 final report is a stub — `stock_cards=[]`, section text hardcoded strings; PM agent `investor_document` and valuation cards never flow into the report | **High** | `engine.py` ~L1231–1248 | ✅ `2b6a360` |
| ARC-3 | VaR uses `np.random.normal(0.001, 0.02, 252)` despite `live_factor_returns` (dict[str, list[float]]) already computed in same stage | **Medium** | `engine.py` ~L856 | ✅ `2b6a360` |
| ARC-4 | Execution order wrong — Stage 7 (Valuation) runs **before** Stage 8 (Macro); valuation models lack macro regime context | **Medium** | `engine.py` `run_full_pipeline()` ~L1462–1468 | ✅ `2b6a360` |
| ARC-5 | Sector routing hardcoded to 17 specific tickers — any ticker outside `{NVDA, AVGO, TSM, AMD, ANET, CEG, VST, GEV, NLR, PWR, ETN, HUBB, APH, FIX, FCX, BHP, NXT}` gets zero sector analysis | **Medium** | `engine.py` ~L724–726 | ✅ `2b6a360` |
| ARC-6 | Red Team Agent (Stage 10) receives no macro or risk-scenario inputs — cannot challenge macro assumptions | **High** | `engine.py` ~L980–990 | ✅ `2b6a360` |
| ARC-7 | Reviewer Agent (Stage 11) receives no macro or risk inputs — review quality degraded | **High** | `engine.py` ~L1000–1010 | ✅ `2b6a360` |
| ARC-8 | PM Agent (Stage 12) receives no macro regime context — portfolio construction ignores rate/inflation environment | **High** | `engine.py` ~L1144–1165 | ✅ `2b6a360` |
| ARC-9 | Macro Agent (Stage 8) receives only `{"universe": [...]}` — no market data from Stage 2 ingestion or Stage 3 reconciliation | **Medium** | `engine.py` ~L805 | ✅ `2b6a360` |
| ARC-10 | Fixed Income Agent (Stage 9) receives hardcoded stub `"note": "Live yield/spread data not available..."` instead of Stage 8 macro output | **High** | `engine.py` ~L930–937 | ✅ `2b6a360` |

---

## 8. Session 11 — Architecture Repair (✅ Complete — `2b6a360`)

**Goal:** Fix all 10 ARC bugs; bring pipeline data-flow integrity to production standard.  
**Result:** 667 / 667 tests passing (+60 new tests in `test_session11.py`).  
**Commit:** `2b6a360`

| Step | ID | Task | Effort |
|---|---|---|---|
| 1 | ARC-4 | Swap Stage 7 and Stage 8 execution order in `run_full_pipeline()` — 2-line change | Trivial | ✅ |
| 2 | ARC-1 | Add `_get_macro_context()` helper; thread `stage_outputs[8]` into Stages 9, 10, 11, 12 | Low | ✅ |
| 3 | ARC-10 | Replace hardcoded FI stub with `stage_outputs[8]["macro"]` | Trivial | ✅ |
| 4 | ARC-6 | Add macro + risk context to Red Team Agent inputs | Low | ✅ |
| 5 | ARC-7 | Add macro + risk context to Reviewer Agent inputs | Low | ✅ |
| 6 | ARC-8 | Add macro context to PM Agent inputs | Low | ✅ |
| 7 | ARC-9 | Pass Stage 2/3 market data into Macro Agent inputs | Low | ✅ |
| 8 | ARC-3 | Replace `np.random.normal()` VaR with aggregate of `live_factor_returns` | Low | ✅ |
| 9 | ARC-5 | Add `SECTOR_ROUTING` config dict to `config/loader.py`; replace hardcoded ticker sets | Medium | ✅ |
| 10 | ARC-2 | Build `stock_cards` from `stage_outputs[7]`; use PM `investor_document` for report sections | Medium | ✅ |
| 11 | — | Write `tests/test_session11.py` — 32 tests covering all 10 ARC fixes | Medium | ✅ |
| 12 | — | Run full test suite; target 639+/639 passing | Low | ✅ |
| 13 | — | Update TRACKER.md + ARCHITECTURE.md; git commit | Trivial | ✅ |

---

## 9. Session 12 — Macro Economy & Australia / US Markets

**Goal:** Build real macroeconomic analysis capability — rates, inflation, housing, COGS, AU/US market divergence.  
This fills the current **2/10 macro economy gap** (see ARCHITECTURE.md §13.2).

### New Services

| Service | Data Sources | Purpose |
|---|---|---|
| `EconomicIndicatorService` | FRED API, RBA Statistical Tables, ABS data | Fetch live rates, CPI, unemployment, housing, yield curves for AU + US |
| `MacroScenarioService` | Internal + FRED | Generate rate/inflation/growth scenario matrices (base / bull / bear) |

### New / Extended Agents

| Agent | Extension | Outputs |
|---|---|---|
| `EconomyAnalystAgent` (new) | Full AU + US macro analysis | RBA cash rate thesis, Fed funds thesis, AU CPI, US CPI, AU housing, S&P 500 vs ASX 200 macro divergence, COGS inflation impact |
| `MacroStrategistAgent` (extend) | Receives `EconomyAnalystAgent` output | Global regime classification + AU / US specific regime flags |

### Market Scope Configuration (`MarketConfig` in `PipelineConfig`)

| Market | Priority | Key Indices | Data Required |
|---|---|---|---|
| US Large Cap / AI Infrastructure | P0 — current | S&P 500, NDX | Already built |
| ASX (Australian) | P0 — build | ASX 200, ASX 300, XJO | yfinance `^AXJO`; RBA cash rate |
| US Broad Market | P1 | Russell 2000, S&P 500 EW | FRED + FMP |
| Global Thematic / Tech | P1 | MSCI World Tech | FRED + FMP |
| Fixed Income (AU + US) | P1 | AU 10Y, US 10Y, IG spreads | FRED + RBA |
| Asian Technology | P2 | Nikkei 225, KOSPI, TSMC | yfinance |

### Session 12 Steps

| Step | Task | Effort |
|---|---|---|
| 1 | `EconomicIndicatorService` — FRED + RBA + ABS fetch, async, typed Pydantic output | Medium | ✅ `12c7086` |
| 2 | `MacroScenarioService` — scenario matrix builder; base/bull/bear for AU + US | Medium | ✅ `12c7086` |
| 3 | `EconomyAnalystAgent` — full LLM agent; ~10 output fields AU/US specific | Medium | ✅ `12c7086` |
| 4 | `MarketConfig` added to `PipelineConfig`; universe detection logic | Low | ✅ `12c7086` |
| 5 | Wire `EconomyAnalystAgent` → `MacroStrategistAgent` | Low | ✅ `12c7086` |
| 6 | Wire macro scenarios into VaR stress tests (Stage 9) | Low | ✅ `12c7086` |
| 7 | Wire AU/US macro divergence into PM allocation (Stage 12) | Low | ✅ `12c7086` |
| 8 | Write `tests/test_session12.py` — 100 tests (749 passing total) | Medium | ✅ `12c7086` |
| 9 | Run full suite; 749 passing (18 pre-existing errors in S7/S8 async) | Low | ✅ `12c7086` |
| 10 | Update TRACKER.md + IMPROVEMENTS.md; git commit | Trivial | ✅ `12c7086` |

---

## 10. Session 13 — Depth & Quality Improvements

**Goal:** Elevate output quality from "structurally correct" to "institutionally publishable".

| Step | Task | Division | Effort | Status |
|---|---|---|---|---|
| 1 | Agent prompt upgrades — rate/macro context injected into all 14 agent prompts | Global Research | Medium | ✅ `34d7949` |
| 2 | Valuation model depth — DCF sensitivity tables; EV/EBITDA vs P/E cross-validation | Quant Research | Medium | ✅ `34d7949` |
| 3 | Factor model live refit — OLS against real FRED factor data (Mkt-RF, SMB, HML) | Quant Research | High | ✅ `34d7949` |
| 4 | Report assembly — narrative paragraph generation for each section; no hardcoded strings | Client Solutions | Medium | ✅ `34d7949` |
| 5 | Live sector data routing — `SectorDataService`; real earnings/revenue from FMP | Global Research | High | ✅ `34d7949` |
| 6 | `tests/test_session13.py` — 48 tests | Operations | Medium | ✅ `34d7949` |
| 7 | Full suite + commit | Operations | Low | ✅ `34d7949` — 797 passing |

---

## 11. Session 14 — Superannuation & Australian Client Context

**Goal:** Model the JP Morgan Australia client base — superannuation funds, SMSF, retail AU investors.

| Step | Task | Division | Effort | Status |
|---|---|---|---|---|
| 1 | `SuperannuationMandateService` — AU super fund mandate types (growth, balanced, conservative, lifecycle) | Portfolio Management | Medium | ✅ `29272dd` |
| 2 | `AustralianTaxService` — CGT discount, franking credits, div withholding for foreign equities | Client Solutions | Medium | ✅ `29272dd` |
| 3 | `ClientProfileSchema` — client type (super fund / SMSF / HNW / institutional), AU residency flag, AUS/US allocation target | Client Solutions | Low | ✅ `29272dd` |
| 4 | Mandate checking (Stage 12) extended — APRA SPS 530 single-name, intl cap, AU minimum checks | Investment Governance | Medium | ✅ `29272dd` |
| 5 | Report assembly — AU-format disclosures, FSG reference, ASIC compliance notices, `build_au_disclosures()` | Client Solutions | Medium | ✅ `29272dd` |
| 6 | `tests/test_session14.py` — 60 tests | Operations | Medium | ✅ `29272dd` |
| 7 | Full suite + commit | Operations | Low | ✅ `29272dd` — 857 passing |

---

## 12. Session 15 — FastAPI Event-Streaming API Layer

**Goal:** Decouple the pipeline engine from any specific UI client by introducing a first-class HTTP API layer — prerequisite for the Next.js premium frontend.

| Phase | Task | Status |
|---|---|---|
| Phase 2 | `PipelineEvent` schema (11 event types) + engine `_emit()` + `_timed_stage` events | ✅ `7a62757` |
| Phase 3 | `RunRequest` Pydantic schema (universe, model, client_profile, market, fields) | ✅ `7a62757` |
| Phase 4 | `src/api/main.py` FastAPI app + lifespan + CORS + auth middleware | ✅ `7a62757` |
| Phase 4 | `src/api/routes/runs.py` — POST/GET/DELETE /api/v1/runs + SSE /events | ✅ `7a62757` |
| Phase 4 | `src/api/services/run_manager.py` — RunManager, ManagedRun, async event queues | ✅ `7a62757` |
| Tests | `tests/test_session15.py` — 47 tests | ✅ `7a62757` — 904 passing |

---

## 13. Brainstorm Backlog (Future Sessions 16+)

Items identified during Session 11 planning audit. Not yet scheduled.

### Global Research Division
- Live news ingestion — Reuters / Bloomberg headline sentiment per ticker (currently no real-time news)
- Earnings transcript parsing — NLP over SEC 8-K / ASX announcements
- Analyst consensus integration — FactSet / LSEG consensus EPS + price targets
- Sector deep-dive agents for AU-listed companies (banks, miners, REITs, energy)

### Quantitative Research Division
- Black-Litterman portfolio construction from analyst views
- GARCH-based volatility forecasting (replace constant σ in VaR)
- Regime detection model — HMM over factor data for bull/bear/sideways
- Fama-French 5-factor model extension (adding RMW + CMA)

### Portfolio Management Division
- Multi-asset allocation — AU equities + US equities + fixed income + cash
- SMSF tax-aware rebalancing (CGT trigger minimisation)
- Drawdown recovery scenarios — time-to-recovery estimates per portfolio type
- Execution integration — order generation API stub

### Performance Attribution Division
- Real benchmark data — ASX 200 TR (^AXJO) + S&P 500 TR daily returns from yfinance
- Sector contribution to active return (GICS-level BHB)
- Currency attribution — AUD/USD hedging impact on US equity returns
- Rolling 1Y / 3Y / 5Y attribution periods

### ESG / Sustainable Investing Division
- MSCI ESG dataset integration (licensed or approximated)
- AU ESG regulatory requirements — APRA SPS 530, TCFD alignment
- Greenwashing red-flag detection in agent prompts
- Portfolio carbon intensity score (Scope 1+2 per $M revenue)

### Client Solutions / Reporting Division
- Interactive HTML report with Plotly charts (replace static PDF)
- Client portal — per-client report generation with mandate-specific commentary
- ASIC-compliant Financial Services Guide (FSG) generation
- Regulatory filing extracts — APRA, ASIC format outputs

### Operations Division
- Multi-provider LLM fallback — Anthropic → OpenAI → Azure OpenAI
- Prompt versioning with semantic diff alerts
- Full observability dashboard — Grafana/Prometheus metrics export
- Blue/green pipeline deployment with canary run comparison

---

## 13. External PR Review — Core system improvements (#1)

**Verdict:** useful ideas, **not mergeable as-is**. Build the work on `main` ourselves and selectively port concepts only.

### Why PR #1 should not be merged directly

| Evidence | Finding |
|---|---|
| PR branch test run | **14 failed, 18 errors, 575 passed** |
| Runtime failure 1 | `PipelineEngine` missing `_route_sector_tickers()` — breaks Stage 6 immediately |
| Runtime failure 2 | `PipelineEngine` missing `_build_metric_snapshot()` — breaks Stage 14 monitoring |
| Delivery risk | Large feature bundle mixes ARC fixes, Session 12/14 work, HTML reports, tax overlays, fallback chains, and trend logic in one untested PR |
| Architectural quality | Several changes introduce useful ideas but without the missing adapters, schemas, or test coverage identified in `PROJECT_ISSUES_ASSESSMENT.md` |

### Reusable ideas worth salvaging later

- `EconomyAnalystAgent` as a dedicated AU/US macro agent
- LLM fallback telemetry fields on `AgentResult`
- `MarketConfig`, `LLMConfig`, and AU client config model direction
- `ReportHtmlService` concept for interactive reports
- `AustralianTaxService` and `SuperannuationMandateService` as future deterministic overlays
- `ResearchTrend` / cross-run change alert concept

**Decision:** keep PR #1 open only as a reference branch; do not squash or merge it.

---

## 14. Residual Issues from PROJECT_ISSUES_ASSESSMENT.md

`PROJECT_ISSUES_ASSESSMENT.md` was merged from PR #2 and adds **41 residual issues** not yet covered by the existing roadmap.

### Severity summary

| Severity | Count |
|---|---|
| Critical | 1 |
| High | 15 |
| Medium | 19 |
| Low | 6 |

### Highest-priority residual issues to fold into upcoming work

| ID | Issue | Why it matters | Fold into |
|---|---|---|---|
| ISS-1 | `MacroContextPacket` schema contract missing | ARC-1 is unsafe without typed macro packet validation | ✅ `2b6a360` |
| ISS-3 | No `GenericSectorAnalystAgent` fallback | ARC-5 incomplete without coverage for unmapped tickers | ✅ `2b6a360` |
| ISS-4 | `ValuationCard` → `StockCard` mapping unspecified | ARC-2 report fix can still produce malformed report cards | ✅ `2b6a360` |
| ISS-9 | Agent output quality validation is non-fatal | Missing required keys still propagate through the pipeline | ✅ `2b6a360` |
| ISS-10 | Gemini SDK import mismatch | Planned fallback chain can be broken on day one | ✅ `2b6a360` |
| ISS-12 | Macro agents lack required key contracts | Stage 8 remains structurally weak even after Session 12 | ✅ `12c7086` |
| ISS-13 | No ASX-specific prompts | Australian market support will remain shallow | ✅ `12c7086` |
| ISS-16 | BHB benchmark still synthetic | Performance Attribution target can still be overstated | E-4 / Session 13 |
| ISS-20 | Streamlit session key bug (`result` vs `run_result`) | Observability UI can break despite backend success | ✅ `2b6a360` |
| ISS-27 | No live API full-pipeline integration test | Production-readiness remains unverified | Session 13 |
| ISS-34 | No database persistence | Run history and observability remain flat-file only | Future Session 15+ |
| ISS-36 | `llm_cost_usd` never populated | Ops / governance cost tracking remains incomplete | Future Session 15+ |

### Watch-outs for every implementation session

- Keep `PROJECT_ISSUES_ASSESSMENT.md` open while building Sessions 11–14.
- Treat ISS-1, ISS-3, ISS-4, ISS-9, ISS-10, and ISS-20 as **preconditions**, not optional polish.
- Do not merge large Cursor-generated feature bundles without running the full suite first.
- Any new macro/reporting/ops work should be checked against ISS-12 through ISS-41 before commit.

---

## 15. Frontend Architecture Migration Plan

**Decision (March 28, 2026):** Move from Streamlit to a custom Next.js + FastAPI frontend for the premium product surface. Keep Streamlit as the internal operator console only.

### Frontend assessment verdict

An independent review of the current Streamlit frontend scored:

| Dimension | Score |
|---|---|
| Overall | 6.5/10 |
| Backend fidelity | 5.5/10 |
| Real-time observability | 4.5/10 |
| Navigation | 6/10 |
| Visual polish | 7.5/10 |
| Analytical richness | 7.5/10 |

**Core finding:** the frontend implies capabilities that are only partially wired. It looks like a premium deeply-observable research platform; in practice, some of that depth is real and some is presentation ahead of plumbing.

### Why Streamlit is the ceiling

| Capability | Streamlit limit | Next.js + FastAPI solution |
|---|---|---|
| Real-time stage/substage events | Simulated; no true streaming | WebSocket / SSE from FastAPI |
| Navigation depth | Scripted vertical scroll | Full App Router with pages + deep-links |
| Custom interaction | Constrained widget set | Full React component freedom |
| Compare-runs mode | Very hard | Standard multi-view routing |
| Traceability / provenance | Very hard without re-architecting | First-class React components |
| Visual analytics | Limited chart options | Recharts, D3, AG Grid available |
| Product polish trajectory | 7–7.5/10 ceiling | 9.0–9.3/10 target |

### Target tech stack

| Layer | Tool |
|---|---|
| Premium frontend | Next.js 14 (App Router) + React 18 |
| Design system | TailwindCSS + shadcn/ui |
| Charts | Recharts / Tremor |
| Data tables | AG Grid Community |
| State management | TanStack Query (server) + Zustand (client) |
| Backend API | FastAPI (new `src/api/`) |
| Real-time events | Server-Sent Events (SSE) or WebSocket |
| Internal console | Keep `src/frontend/app.py` (Streamlit) |

### New session blocks introduced by this plan

| Session | Scope | Test target |
|---|---|---|
| Session 15 | FastAPI event-streaming API layer | API contract tests ~+25 | ✅ `7a62757` — 47 tests, 904 total |
| Session 16 | Next.js premium UI build | Component + integration tests ~+20 | ✅ 39 tests, 941 total |
| Session 17 | Traceability, provenance, explainability | E2E + traceability tests ~+15 | ✅ 29 tests, 941 total |

### Phase map layered with existing sessions

| Phase | Scope | Layered into |
|---|---|---|
| Phase 1 | Adapter truthfulness fixes (report_path → markdown, token_log, audit_packet, temperature, provider keys) | **Session 11** |
| Phase 2 | Engine event stream contract (stage_started, agent_started, llm_call events) | **Session 12** |
| Phase 3 | Unified storage + `RunRequest` schema + `ClientProfile` wiring | **Sessions 12–13** |
| Phase 4 | FastAPI API layer (`POST /runs`, SSE `/runs/{id}/events`, artifact endpoints) | **Session 15** |
| Phase 5 | Next.js premium UI (all pages, live tracker, report viewer, quant panel) | **Session 16** |
| Phase 6 | Visual analytics (charts per dimension) | **Session 16** |
| Phase 7 | Traceability + explainability + audit trail | **Session 17** |

### Score progression expected

| After | Score |
|---|---|
| Phase 1 (adapter fixes) | 7.0/10 |
| Phase 2 (event stream) | 7.5/10 |
| Phase 3 (storage + RunRequest) | 7.8/10 |
| Phase 4 (FastAPI) | 8.2/10 |
| Phase 5 + 6 (Next.js + charts) | 9.0/10 |
| Phase 7 (traceability) | 9.3/10 |

### New E-items added

| ID | Item | Session |
|---|---|---|
| E-11 | FastAPI event-streaming layer | Session 15 |
| E-12 | Next.js + React premium UI | Session 16 |
| E-13 | Real-time stage + agent event stream | Session 15–16 |
| E-14 | Compare-runs mode | Session 16 |
| E-15 | Report section provenance traces | Session 17 |

### Critical acceptance gates

- Phase 1 must be done before Phase 4 — the API contract should reflect the fixed data model, not the broken one
- Phase 4 (FastAPI) must be stable before Session 16 commences — Next.js builds against the API contract
- `src/frontend/app.py` must remain functional throughout migration — it is the operator fallback until Session 16 is complete
- Do not build visual analytics (Phase 6) on new data models — reuse the same data structures as Streamlit quant panels
- Traceability (Phase 7) requires artifact paths in the event stream — this contract must be set in Phase 2

### Status

| Phase | Status |
|---|---|
| Phase 2 — adapter fixes | ✅ |
| Phase 2 — engine event stream | ✅ `7a62757` |
| Phase 3 — storage + RunRequest | ✅ `7a62757` |
| Phase 4 — FastAPI layer | ✅ `7a62757` |
| Phase 5 — Next.js UI | ✅ |
| Phase 6 — Visual analytics | ✅ |
| Phase 7 — Traceability | ✅ |

---

## Session 16 — Premium Next.js Frontend + Backend Expansion

### Deliverables
1. **Pipeline adapter truthfulness** — `src/frontend/pipeline_adapter.py` rewritten with truthful `elapsed_secs`, `raw_text`, `token_log`, `audit_packet`; fires `running` + `done` callbacks
2. **FastAPI API expansion** — 6 → 15 endpoints: `/report`, `/stages`, `/stages/{n}`, `/audit`, `/timings`, `/artifacts`, `/provenance`, `/saved-runs`, `/saved-runs/{id}`
3. **RunManager** — 4 new methods: `get_stages()`, `get_audit_packet()`, `get_timings()`, `get_provenance()`
4. **Storage fixes** — `token_log` + `audit_packet` persisted; `_mirror_to_registry()` run_id overwrite; `delete_run()` cascades to registry
5. **Next.js 16** frontend scaffolded at `frontend/` — TypeScript, TailwindCSS 4, Zustand 5, React Query 5, Recharts 2, Lucide icons
6. **7 pages**: Dashboard, New Run (theme quick-select), Runs List, Run Detail (5-tab view: Live Tracker, Report, Audit & Quality, Provenance, Stage Detail), Saved Runs, Settings
7. **8 components**: Sidebar, TopBar, PipelineTracker (animated 15-stage vertical timeline), LiveEventFeed (auto-scroll SSE), MetricCard, TimingChart, 3 Provenance components
8. **Complete API client** (typed, 15 functions) + SSE `createEventStream` + Zustand store processing all 11 event types

### Files created
- `frontend/` — Full Next.js project (package.json, tsconfig, next.config, postcss, .env.local)
- `frontend/src/lib/` — types.ts, api.ts, utils.ts, store.ts
- `frontend/src/components/` — providers, sidebar, top-bar, pipeline-tracker, live-event-feed, metric-card, timing-chart
- `frontend/src/app/` — layout, globals.css, 7 page routes

### Tests
- `tests/test_session16.py`: 39 tests — route validation, RunManager methods, SSE helper, event schema, frontend structure

---

## Session 17 — Traceability & Provenance

### Deliverables
1. **ProvenanceCard schema** — per-stage lineage: inputs consumed, outputs produced, gate outcome, assumptions, agent/model, timing
2. **ReportSectionProvenance schema** — maps report sections to source stages, agents, data sources, confidence levels, methodology tags
3. **ProvenancePacket schema** — aggregates all cards + report sections with completeness % tracking
4. **ProvenanceService** — builds stage cards from engine state (STAGE_INPUTS, STAGE_OUTPUTS, STAGE_ASSUMPTIONS for all 15 stages), parses report sections, saves to disk
5. **Engine integration** — `_save_stage_output()` auto-builds provenance cards; `run_full_pipeline()` builds + persists full provenance packet
6. **API endpoint** — `GET /runs/{run_id}/provenance` returns the complete provenance packet
7. **Frontend** — 3 provenance components: ProvenanceCard (expandable with inputs/outputs/gate/assumptions), ReportProvenancePanel (section-level traceability), ProvenancePanel (full page with completeness bar)
8. **Run detail Provenance tab** — 5th tab in the run detail page, loads provenance via React Query

### Files created
- `src/research_pipeline/schemas/provenance.py` — DataSource, StageOutput, ProvenanceCard, ReportSectionProvenance, ProvenancePacket
- `src/research_pipeline/services/provenance_service.py` — ProvenanceService with STAGE_INPUTS/OUTPUTS/ASSUMPTIONS
- `frontend/src/components/provenance/` — provenance-card.tsx, report-provenance.tsx, provenance-panel.tsx

### Tests
- `tests/test_session17.py`: 29 tests — schema validation, service logic, stage metadata coverage, engine integration, confidence assessment, section mapping
| Phase 6 — visual analytics | 🔲 |
| Phase 7 — traceability | 🔲 |
