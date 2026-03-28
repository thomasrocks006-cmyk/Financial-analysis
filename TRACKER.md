# Project Tracker — AI Research & Portfolio Platform

> **Last updated:** March 28, 2026  
> **Test suite:** 303 / 303 passing  
> **Commit:** `1374e5d`

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

Live code issues that remain from the architecture review. Not cosmetic — each causes real risk.

| ID | File | Issue | Severity | Fix Required |
|---|---|---|---|---|
| A-1 | `src/frontend/pipeline_runner.py` | 1,851-line duplicate orchestration engine. Still runs its own full pipeline logic independently of `PipelineEngine`. Fixes applied to `engine.py` are not reflected here. | **Critical** | Reduce to thin adapter: call `PipelineEngine` stages directly; remove all duplicate orchestration logic |
| A-2 | `src/frontend/storage.py` + `src/research_pipeline/services/run_registry.py` | Two separate persistence systems. Frontend writes its own JSON storage; backend maintains its own run registry. They do not share records. | High | Unify under `RunRegistryService`; frontend writes through the registry |
| A-3 | `src/research_pipeline/schemas/portfolio.py` line 27 | `PublicationStatus.PASS_WITH_DISCLOSURE` still exists as a valid enum value (and line 217 treats it as passing). `AssociateReviewer` now rejects it, but the schema still permits it. | Medium | Remove `PASS_WITH_DISCLOSURE` from `PublicationStatus` enum; update `is_publishable()` property |
| A-4 | `src/research_pipeline/services/investment_committee.py` line 195 | Still checks `review_result.get("status") == "pass_with_disclosure"` as a valid case, inconsistent with the binary PASS/FAIL mandate | Medium | Remove the `pass_with_disclosure` branch; treat it as FAIL |

---

## 3. Post-Roadmap Build Candidates

These are not in any current ROADMAP phase but represent the logical next layer of the platform.

| ID | Area | Task | JPAM Division | Priority | Effort |
|---|---|---|---|---|---|
| P-1 | **Documentation** | Update `ARCHITECTURE.md` component scorecard and gap tables to reflect post-Phase-7 reality. Many rows still say "Not started" for things that are now built. | — | High | Low |
| P-2 | **Testing** | Product-level smoke tests: run full `PipelineEngine` end-to-end with mocked API responses and assert on final report structure | Operations | High | Medium |
| P-3 | **Agent** | Quant Research Agent (see D-4 above) — LLM commentary layer over factor exposures, VaR output, ETF overlap results | Quant Research | High | Medium |
| P-4 | **Frontend** | Wire new services into Streamlit UI: show ETF overlap score, observability cost table, and BHB attribution panel | Client Solutions | Medium | Medium |
| P-5 | **Data** | Add a third market data source (e.g. Yahoo Finance via `yfinance`) as fallback when FMP or Finnhub quotas are exhausted | Operations | Medium | Low |
| P-6 | **Services** | DCF Engine extension — add EV/EBITDA and P/E relative valuation methods for stocks where DCF is less applicable (e.g. early-stage or asset-light) | Quant Research | Medium | Medium |
| P-7 | **Agents** | Multi-asset thesis agents — sector analysts currently assume equity. Need fixed-income thesis agent for the `FIXED_INCOME_UNIVERSE` tickers now in `universe_config.py` | Research | Medium | High |
| P-8 | **Operations** | Live run validation — wire real API keys into CI (as secrets), run one pipeline pass per week against live FMP/Finnhub data, assert report completeness | Operations | Low | Low |

---

## 4. Division-Level Maturity

Current best estimates post-Phase-7. Architecture doc scores are stale (pre-phase completion).

| Division | Pre-build Score | Post-Phase-7 Estimate | JPAM Target | Remaining Gap |
|---|---|---|---|---|
| Global Research | 6.5 | **8.0** | 9.0 | 1.0 |
| Quantitative Research | 5.5 | **8.0** | 9.0 | 1.0 |
| Portfolio Management | 6.0 | **8.0** | 8.5 | 0.5 |
| Investment Governance | 4.5 | **7.5** | 9.5 | 2.0 |
| Performance Attribution | 0.0 | **6.5** | 8.5 | 2.0 |
| ESG / Sustainable Investing | 0.0 | **6.0** | 7.5 | 1.5 |
| Operations & Technology | 6.5 | **8.0** | 9.0 | 1.0 |
| Client Solutions / Reporting | 6.5 | **7.0** | 8.5 | 1.5 |
| **Weighted platform score** | **4.4** | **~7.5** | **9.0** | **1.5** |

---

## 5. Test Coverage

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
| **Total** | **303** | All passing |

**Coverage gaps:**
- No end-to-end pipeline smoke test (P-2 above)
- `golden_tests.py` categories not tested with real assertions (D-3 above)
- `frontend/pipeline_runner.py` has zero dedicated tests

---

## 6. Quick Reference — Key Files

| Purpose | Path |
|---|---|
| Main pipeline orchestrator | `src/research_pipeline/pipeline/engine.py` |
| All 11 LLM agents | `src/research_pipeline/agents/` |
| 30 deterministic services | `src/research_pipeline/services/` |
| Governance schemas | `src/research_pipeline/schemas/governance.py` |
| Universe configs | `src/research_pipeline/config/universe_config.py` |
| LLM fallback chain | `src/research_pipeline/agents/base_agent.py` → `_FALLBACK_CHAIN` |
| Observability | `src/research_pipeline/services/observability.py` |
| Memory injection | `src/research_pipeline/services/memory_injection.py` |
| ETF overlap engine | `src/research_pipeline/services/etf_overlap_engine.py` |
| Report formats (3 variants) | `src/research_pipeline/services/report_formats.py` |
| CI/CD | `.github/workflows/ci.yml` |
| Frontend (warn: architectural debt A-1) | `src/frontend/pipeline_runner.py` |
