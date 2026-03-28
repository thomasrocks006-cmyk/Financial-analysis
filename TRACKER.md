# Project Tracker — AI Research & Portfolio Platform

> **Last updated:** March 28, 2026  
> **Test suite:** 453 / 453 passing  
> **Commit:** `2c08376` — session 5 complete

---

## Status Summary

| Area | Status |
|---|---|
| ROADMAP Phases 0–7 | All **COMPLETE** |
| Session 2 debt-clearing (10 items) | All **COMPLETE** |
| Session 3 (P-5, P-6, ACT-6) | All **COMPLETE** |
| Session 4 (P-4, P-7, P-8) | All **COMPLETE** |
| Session 5 (ACT-S5-1, ACT-S5-2) | All **COMPLETE** |
| Session 6 | **PLANNED** — see §2 below |

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

### Session 6 — Planned Work Queue

| ID | Area | Task | JPAM Division | Priority | Effort |
|---|---|---|---|---|---|
| ACT-S6-1 | **Governance** | Wire `SelfAuditPacket` into every engine run — attach per-stage latency, token counts, confidence flags to `RunRecord` | Investment Governance | High | Low |
| ACT-S6-2 | **Agents** | ESG analyst agent — new `EsgAnalystAgent` scoring environmental/social/governance factors per ticker; wired into Stage 6 | ESG / Sustainable Investing | High | High |
| ACT-S6-3 | **Frontend** | PDF export of Quant Analytics Report tab — `pdfkit` / `weasyprint` rendering triggered from Streamlit | Client Solutions | Medium | Medium |
| ACT-S6-4 | **Schemas** | Remove legacy `PublicationStatus.PASS_WITH_DISCLOSURE` — confirmed still referenced in old test fixtures | Governance | Medium | Low |
| ACT-S6-5 | **Testing** | Expand smoke test to assert `SelfAuditPacket` presence and ESG fields after session 6 additions | Operations | Medium | Low |

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

*Scores updated through session 5. Session 5 improved Investment Governance (gate hardening) and Operations & Technology (base_agent reliability).*

| Division | Session 5 Score | JPAM Target | Gap | Primary Remaining Gap |
|---|---|---|---|---|
| Global Research | **7.5 / 10** | 9.0 / 10 | 1.5 | Agent outputs still partially shallow (political risk, macro) |
| Quantitative Research | **7.5 / 10** | 9.0 / 10 | 1.5 | SelfAuditPacket not wired; no live historical return data |
| Portfolio Management | **6.5 / 10** | 8.5 / 10 | 2.0 | IC vote blocks on mandate violations (good), but no weights optimiser |
| Investment Governance | **8.0 / 10** ↑ | 9.5 / 10 | 1.5 | SelfAuditPacket not wired; PASS_WITH_DISCLOSURE in test fixtures |
| Performance Attribution | **0 / 10** | 8.5 / 10 | 8.5 | Not built — requires time-series price store |
| ESG / Sustainable Investing | **0 / 10** | 7.5 / 10 | 7.5 | Not built — ACT-S6-2 target |
| Operations & Technology | **8.3 / 10** ↑ | 9.0 / 10 | 0.7 | base_agent fixed; asyncio.gather done; CI weekly workflow live |
| Client Solutions / Reporting | **7.5 / 10** | 8.5 / 10 | 1.0 | No PDF export yet; Quant Analytics panel complete |
| **Weighted platform score** | **7.1 / 10** ↑ | **9.0 / 10** | **1.9** | ESG and Performance Attribution are the main platform-score anchors |

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
| **Total** | **453** | All passing |

---

## 6. Quick Reference — Key Files

| Purpose | Path |
|---|---|
| Main pipeline orchestrator | `src/research_pipeline/pipeline/engine.py` |
| All 12 LLM agents | `src/research_pipeline/agents/` |
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
