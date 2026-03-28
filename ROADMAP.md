# Platform Roadmap — From Research Pipeline to JPMorgan Asset Management Equivalent

> **North Star Goal:** Build a fully autonomous AI-powered investment organisation that
> structurally emulates JPMorgan Asset Management — with research, risk, portfolio management,
> governance, performance attribution, and client delivery all operating as distinct, correctly
> governed divisions.
>
> **Date logged:** March 28, 2026
> **Current version:** v8.0 (15-stage research pipeline, partially converged)

---

## Table of Contents

1. [North Star: The JPMorgan AM Model](#1-north-star-the-jpmorgan-am-model)
2. [Current State Summary](#2-current-state-summary)
3. [Capability Gap Map](#3-capability-gap-map)
4. [7-Phase Build Roadmap](#4-7-phase-build-roadmap)
5. [Target Architecture When Complete](#5-target-architecture-when-complete)
6. [Division-Level Design Spec](#6-division-level-design-spec)
7. [Success Metrics](#7-success-metrics)
8. [Risk Register for the Build Itself](#8-risk-register-for-the-build-itself)

---

## 1. North Star: The JPMorgan AM Model

JPMorgan Asset Management operates as a set of distinct, governed divisions that each perform
a specialist function with formal handoffs between them. The key structural insight is that no
single function both creates and approves its own work. Evidence is separated from judgment.
Judgment is separated from governance. Portfolio management is separated from risk oversight.

### JPAM Division Map

| Division | JPAM Function | Our Equivalent |
|---|---|---|
| **Global Research** | Sector analysts, thematic analysts, deep fundamental coverage | Sector agents + Evidence Librarian |
| **Investment Management** | PMs building and managing portfolios | Portfolio Manager agent |
| **Quantitative Research** | Factor models, risk decomposition, systematic strategies | Risk Engine + Scenario Engine |
| **Macro & Investment Strategy** | Global market outlook, regime assessment, asset allocation | Macro Strategist + Political Risk agents |
| **Risk Management** | Independent risk monitoring, limit management, stress testing | Risk Engine + Gate system |
| **Investment Governance** | Investment committees, compliance, mandate management | Gate system + Associate Reviewer |
| **Performance & Analytics** | Attribution, benchmarking, portfolio analytics | **NOT YET BUILT** |
| **ESG & Sustainable Investing** | ESG scoring, exclusion lists, engagement | **NOT YET BUILT** |
| **Client Solutions** | Custom mandates, portfolio construction advice, client reporting | Partial (Streamlit UI, basic reports) |
| **Operations & Technology** | Data infrastructure, trade operations, technology platform | Partial (pipeline engine, run registry) |

### JPAM Process Principles (What We Must Emulate)

1. **Separation of creation and approval** — research is created by analysts; approved by reviewers; never self-approved
2. **Structured investment process** — formal stage-gate workflow, not ad hoc
3. **Reproducibility** — every output can be replicated from logged inputs
4. **Independent risk oversight** — risk is not managed by the PM; it is reported to a separate function
5. **Evidence hierarchy** — primary filings > management guidance > sell-side consensus > inference
6. **Performance accountability** — portfolios are tracked vs benchmark; attribution is explained
7. **Mandate governance** — portfolios comply with explicit investment guidelines
8. **Governance trail** — every decision is logged with reason, approver, and timestamp

---

## 2. Current State Summary

### What We Have (Operational or Near-Operational)

| Capability | Status | Score |
|---|---|---|
| 15-stage gate-controlled pipeline | Working (frontend path complete, backend converging) | 6.5/10 |
| Market data ingestion (FMP + Finnhub) | Working, serial | 7.5/10 |
| Consensus reconciliation | Working | 7.0/10 |
| Data QA & lineage | Working | 6.5/10 |
| Evidence librarian / claim ledger | Working, partial enforcement | 6.0/10 |
| 3× sector analyst agents (Compute / Power / Infrastructure) | Working | 7.0/10 |
| DCF valuation engine | Working (WACC, FCF projection, sensitivity table) | 7.5/10 |
| Valuation analyst agent | Working | 6.5/10 |
| Red team analyst agent | Working | 7.0/10 |
| Associate reviewer / publish gate | Working, placeholder enforcement | 5.0/10 |
| Portfolio manager (3 variants) | Working | 6.5/10 |
| Macro strategist + political risk agents | Working | 6.5/10 |
| Scenario & stress engine (7 scenarios) | Working | 7.0/10 |
| Risk engine (correlation, HHI, contribution to variance) | Working | 6.5/10 |
| Report assembly | Working (dual path, drift risk) | 6.0/10 |
| Run registry | Working | 6.5/10 |
| Streamlit UI | Working | 7.5/10 |
| CLI | Working | 7.0/10 |
| Test suite (103 tests) | Passing | 6.0/10 |

### What We Do Not Have Yet

| JPAM Capability | Status |
|---|---|
| Performance attribution (Brinson-Hood-Beebower) | Not built |
| Benchmark-relative analytics (alpha, tracking error, IR) | Not built |
| Factor exposure model (size, value, momentum, quality) | Not built |
| Investment committee process (multi-approver voting) | Not built |
| ESG integration | Not built |
| Mandate compliance engine | Not built |
| Position-level liquidity analysis | Not built |
| Portfolio optimisation (mean-variance / Black-Litterman) | Not built |
| Research memory / historical corpus | Not built |
| Thesis evolution tracking | Not built |
| Ongoing portfolio monitoring (trigger-based re-analysis) | Not built |
| Client report customisation (format variants, mandates) | Not built |
| Drawdown & VaR/CVaR | Not built |
| Daily monitoring with diff engine | Not built |
| Human override log with identity | Partial |
| Prompt/agent version registry with drift detection | Partial |
| Multi-asset capability (beyond equity) | Not built |

---

## 3. Capability Gap Map

### Tier 1 — Architecture Debt (Must Fix First)

These block everything else. No JPAM-equivalent is achievable until these are resolved.

| Gap | Current State | What is Needed |
|---|---|---|
| Dual orchestration engines | `PipelineEngine` + `PipelineRunner` running in parallel | One canonical runtime; frontend becomes thin adapter |
| Placeholder governance | Engine passes gates on agent success alone | Fail-closed enforcement on all gates; real structured output parsing |
| Data contract drift | Frontend uses dicts; backend uses Pydantic models | Single canonical data contract used everywhere |
| Fragmented persistence | Two separate storage systems | One registry for runs, artifacts, audit, and history |

### Tier 2 — Missing JPAM Divisions (Build Next)

| Division | Core Missings | Priority |
|---|---|---|
| **Performance Attribution** | No BHB attribution, no benchmark comparison, no alpha calculation | High |
| **Quantitative Research** | No factor model, no VaR/CVaR, no benchmark beta | High |
| **Investment Committee** | No voting mechanism, no committee record | High |
| **Risk Oversight** | Risk not independent from PM — combined in pipeline | Medium |
| **ESG** | No ESG scoring, no exclusion list management | Medium |
| **Mandate Governance** | No investment guidelines enforcement | Medium |
| **Research Memory** | No historical corpus, no thesis evolution, no learning loop | Medium |

### Tier 3 — Operational Maturity (Later Phase)

| Operational Gap | Description |
|---|---|
| Caching & API quota management | No cache, no explicit request budget per run |
| Async parallel ingestion | Backend ingestion is serial; FMP + Finnhub calls should be concurrent |
| Centralized telemetry | No observability dashboard, no latency tracking |
| Retry/circuit breaker for LLM | Rate limit handling not systematic |
| Prompt drift / regression detection | No automated test that catches prompt changes affecting output |

---

## 4. 7-Phase Build Roadmap

### Phase 0 — Architecture Convergence  *(COMPLETED)*

**Goal:** Fix the structural debt that prevents secure build-out.

| Task | Description | Status |
|---|---|---|
| 0.2 | Remove placeholder gate-pass logic in Stage 5, 11, 13 | ✅ Done |
| 0.3 | Enforce structured outputs — fail closed on malformed agent JSON | ✅ Done |
| 0.5 | Fix storage glob — `DEMO-*.json` → `*.json` | ✅ Done |
| 0.6 | Define unified canonical data contracts (governance.py, performance.py) | ✅ Done |

**Exit criteria:** ✅ Zero placeholder passes, 227 tests green.

---

### Phase 1 — Research Division Hardening  *(4 → 10 weeks)*

**Goal:** Raise the existing research pipeline to institutional grade.

| Task | Description |
|---|---|
| 1.1 | Evidence librarian — enforce source tier on every claim (reject Tier 3/4 for core facts) |
| 1.2 | Sector analysts — enforce structured four-box output per ticker (not just per sector) |
| 1.3 | Valuation analyst — enforce methodology tag on every target; disallow single-point fair values |
| 1.4 | Red team analyst — enforce minimum 3 falsification paths per top idea (hard gate) |
| 1.5 | Associate reviewer — remove `PASS_WITH_DISCLOSURE` fallback; require explicit resolution list |
| 1.6 | Parallel data ingestion — run FMP + Finnhub concurrently via `asyncio.gather` |
| 1.7 | Qualitative data pipeline — formalise news / earnings transcript / SEC filing ingestion into typed schemas |
| 1.8 | Prompts audit — review all 11 agent prompts against JPAM research standards; version them |
| 1.9 | Golden tests — cover all 10 test categories (not just pass-through placeholders) |
| 1.10 | `SelfAuditPacket` schema — build and attach to every run output |

**Exit criteria:** Every claim has a source tier. Every valuation has a methodology label. Red team always has ≥3 risks. Associate reviewer never auto-passes.

---

### Phase 2 — Quantitative Research Division  *(COMPLETED)*

**Goal:** Build a proper quant research division — factor model, VaR, benchmark analytics.

| Task | Description | Status |
|---|---|---|
| 2.1 | **Factor Exposure Engine** — compute size, value, momentum, quality factor loadings per ticker | ✅ `factor_engine.py` |
| 2.2 | **Benchmark module** — load index constituent weights (S&P 500, NDX, XLK, XLU) for comparison | ✅ `benchmark_module.py` |
| 2.3 | **Active exposure analysis** — calculate active weight, active risk, tracking error vs benchmark | ✅ `benchmark_module.py` |
| 2.4 | **VaR/CVaR engine** — parametric and historical VaR at 95% and 99% confidence | ✅ `var_engine.py` |
| 2.5 | **Drawdown analysis** — maximum drawdown, recovery time, underwater period | ✅ `var_engine.py` |
| 2.6 | **Liquidity profiling** — average daily volume, days-to-liquidate per position | ✅ `performance_tracker.py` |
| 2.7 | **ETF overlap engine** — holdings overlap vs major AI/tech ETFs (BOTZ, AIQ, SOXX, etc.) |
| 2.8 | **Portfolio optimisation** — mean-variance efficient frontier; minimum variance and maximum Sharpe variants | ✅ `portfolio_optimisation.py` |
| 2.9 | **Risk-budget allocation** — equal risk contribution and risk-parity weighting | ✅ `portfolio_optimisation.py` |
| 2.10 | **Quant Research Agent** — LLM agent to interpret factor exposures and risk decomposition | ⬜ Deferred |

**Exit criteria:** ✅ Every portfolio run includes factor exposures, VaR, tracking error vs benchmark. Integrated into Stage 9.

---

### Phase 3 — Portfolio Management Division  *(COMPLETED)*

**Goal:** Upgrade portfolio construction from 3 static variants to a full PM workflow.

| Task | Description | Status |
|---|---|---|
| 3.1 | **Black-Litterman model** — blend market equilibrium weights with analyst views | ✅ `portfolio_optimisation.py` |
| 3.2 | **Position sizing engine** — convert conviction signals + risk budget into explicit weights | ✅ `position_sizing.py` |
| 3.3 | **Rebalancing framework** — track drift vs target weights; generate rebalance triggers | ✅ `rebalancing_engine.py` |
| 3.6 | **Mandate compliance engine** — investment guidelines enforcement; check portfolio | ✅ `mandate_compliance.py` |
| 3.7 | **Concentration risk alerts** — auto-trigger when HHI or single-name weight crosses threshold | ✅ `monitoring_engine.py` |

**Exit criteria:** ✅ Portfolios mandate-compliant, risk-budgeted, Black-Litterman-informed. Integrated into Stage 12.

---

### Phase 4 — Investment Committee & Governance Division  *(COMPLETED)*

**Goal:** Simulate a proper investment committee — multi-approval, voting, override log.

| Task | Description | Status |
|---|---|---|
| 4.1 | **Investment Committee schema** — `CommitteeRecord`: vote, rationale, approver identity, outcome | ✅ `governance.py` |
| 4.2 | **Multi-stage approval workflow** — Stage 12 requires IC voting before publish | ✅ `investment_committee.py` integrated in `engine.py` |
| 4.3 | **Human override log** — full `HumanOverride` schema with approver, stage, reason, timestamp | ✅ `investment_committee.py` |
| 4.4 | **Compliance rules engine** — rule set for what can be published; auto-check against mandate | ✅ `mandate_compliance.py` |
| 4.5 | **ESG integration layer** — ESG score per ticker; exclusion list; ESG mandate variant | ✅ `esg_service.py` |
| 4.6 | **Prompt/agent version registry** — log prompt hash, detect changes, re-run regression on change | ✅ `prompt_registry.py` |
| 4.7 | **Audit trail exporter** — export full run audit as standalone governance JSON | ✅ `audit_exporter.py` |

**Exit criteria:** ✅ Every published run has a committee record. ESG exclusions enforced. Integrated into Stage 12/14.

---

### Phase 5 — Performance Attribution & Monitoring Division  *(COMPLETED)*

**Goal:** Track portfolio performance over time; attribute returns to decisions.

| Task | Description | Status |
|---|---|---|
| 5.1 | **Historical run store** — persist every portfolio variant from every run with price-stamped weights | ✅ `performance_tracker.py` |
| 5.2 | **Performance tracker** — compute portfolio NAV evolution | ✅ `performance_tracker.py` |
| 5.3 | **Brinson-Hood-Beebower attribution** — decompose excess return into allocation, selection, interaction | ✅ `performance_tracker.py` |
| 5.4 | **Factor attribution** — attribute returns to factor exposures | ✅ `factor_engine.py` |
| 5.7 | **Thesis tracking** — link position to research claim; surface when thesis invalidated | ✅ `performance_tracker.py` |
| 5.9 | **Daily monitoring job** — price + news refresh; flag positions with moves > N× ATR | ✅ `monitoring_engine.py` |
| 5.11 | **Research memory store** — SQLite FTS5 corpus of past reports; queryable for context | ✅ `research_memory.py` |

**Exit criteria:** ✅ Attribution available. Monitoring generates alerts. Research memory searchable. Integrated into Stage 14.

---

### Phase 6 — Research Memory & Learning Loop  *(PARTIALLY COMPLETE)*

**Goal:** The system learns from prior research — retaining institutional memory.

| Task | Description | Status |
|---|---|---|
| 6.1 | **Research corpus store** — embed all past reports and claim ledgers in searchable store | ✅ `research_memory.py` (SQLite FTS5) |
| 6.3 | **Thesis evolution log** — track how the house view on each ticker has changed across runs | ✅ `research_memory.py` |
| 6.5 | **Prompt regression harness** — on any prompt change, re-run golden test suite automatically | ✅ `prompt_registry.py` |
| 6.2 | **Memory injection** — inject relevant prior research context into each new agent run |
| 6.3 | **Thesis evolution log** — track how the house view on each ticker has changed across runs |
| 6.4 | **Model drift detector** — flag when agent outputs show systematic regime change |
| 6.5 | **Prompt regression harness** — on any prompt change, re-run golden test suite automatically |
| 6.6 | **Error pattern library** — collect past red-team falsifications; inject into future red-team prompts |
| 6.7 | **Performance feedback loop** — when attribution data is available, weight prior successful thesis patterns |

**Exit criteria:** New runs reference prior research automatically. The system has a growing institutional memory corpus.

---

### Phase 7 — Production Readiness & Scaling  *(PARTIALLY COMPLETE)*

**Goal:** Harden for reliable production operation; expand universe coverage.

| Task | Description | Status |
|---|---|---|
| 7.2 | **API quota management** — explicit per-run budgets for FMP, Finnhub, and LLM tokens | ✅ `cache_layer.py` QuotaManager |
| 7.3 | **Caching layer** — market data cache with TTL; avoids redundant API calls | ✅ `cache_layer.py` CacheLayer |

| Task | Description |
|---|---|
| 7.1 | **Async pipeline execution** — full asyncio-native pipeline with concurrent stage execution where safe |
| 7.2 | **API quota management** — explicit per-run budgets for FMP, Finnhub, and LLM tokens |
| 7.3 | **Caching layer** — market data cache with TTL; avoids redundant API calls within a session |
| 7.4 | **LLM provider fallback** — auto-fallback from Anthropic → OpenAI → Gemini on rate limit |
| 7.5 | **Observability dashboard** — stage latency, error rates, token usage, cost per run |
| 7.6 | **Expanded universe coverage** — extend beyond AI infrastructure to global equities |
| 7.7 | **Multi-asset support** — extend schemas and agents to support fixed income, macro ETFs |
| 7.8 | **CI/CD pipeline** — automated test + lint on every commit; auto-deploy on merge to main |
| 7.9 | **Client report customisation** — multiple output formats (institutional PDF, exec summary, factsheet) |
| 7.10 | **Scheduler hardening** — reliable daily/weekly automated runs with alert on failure |

**Exit criteria:** System runs reliably on a schedule without human intervention. Coverage is expanded beyond the initial 15-stock universe.

---

## 5. Target Architecture When Complete

```
┌─────────────────────────────────────────────────────────────────────────┐
│  CLIENT DELIVERY LAYER                                                  │
│  Streamlit UI  ·  CLI  ·  PDF/HTML Reports  ·  API                     │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────┐
│  CANONICAL PIPELINE ENGINE  (one orchestrator, one gate framework)      │
│  PipelineEngine  ·  PipelineGates  ·  RunRegistry                      │
└───┬───────────────┬───────────────┬───────────────┬──────────────────┬──┘
    │               │               │               │                  │
    ▼               ▼               ▼               ▼                  ▼
┌────────┐   ┌────────────┐  ┌──────────┐  ┌─────────────┐  ┌──────────────┐
│RESEARCH│   │QUANT RISK  │  │PORTFOLIO │  │GOVERNANCE   │  │PERFORMANCE   │
│DIVISION│   │DIVISION    │  │MGMT DIV  │  │& COMPLIANCE │  │ATTRIBUTION   │
│        │   │            │  │          │  │             │  │DIVISION      │
│Evidence│   │Factor Model│  │BL Optim  │  │Committee    │  │BHB Attr.     │
│Sector  │   │VaR/CVaR    │  │Mandate   │  │ESG Layer    │  │Factor Attr.  │
│Analysts│   │Benchmark   │  │Risk Bdgt │  │Compliance   │  │Perf Tracking │
│Valuation   │Analytics   │  │Portfolio │  │Override Log │  │Thesis Health │
│RedTeam │   │Correlation │  │Variants  │  │Audit Trail  │  │Memory Store  │
│Macro   │   │Liquidity   │  │Rebalance │  │Publishing   │  │Learning Loop │
└────────┘   └────────────┘  └──────────┘  └─────────────┘  └──────────────┘
    │               │               │               │                  │
    └───────────────┴───────────────┴───────┬───────┴──────────────────┘
                                            │
                              ┌─────────────▼─────────────┐
                              │  DETERMINISTIC SERVICES   │
                              │  Data · Models · Registry │
                              └───────────────────────────┘
```

---

## 6. Division-Level Design Spec

### Division A: Global Research

**Purpose:** Produce evidence-grounded, rigorous equity research on the AI infrastructure theme.

**Agents:** Evidence Librarian, Sector Analyst ×3, Valuation Analyst, Red Team Analyst  
**Services:** Market Data Ingestor, Consensus Reconciliation, DCF Engine, Data QA  
**Governance rules:**
- No analyst may use unsourced claims
- Every valuation target requires a methodology label
- Red team must falsify every top idea

**Maturity target:** 9.0/10

---

### Division B: Quantitative Research

**Purpose:** Provide mathematically rigorous risk decomposition, factor exposure analysis, and portfolio construction inputs.

**Agents:** Quant Research Agent (to be built)  
**Services:** Risk Engine, Scenario Engine, Factor Exposure Engine (to be built), VaR Engine (to be built), Benchmark Module (to be built)  
**Governance rules:**
- Risk reports are independent of portfolio management
- Concentration breaches always trigger automatic flagging

**Maturity target:** 8.5/10

---

### Division C: Portfolio Management

**Purpose:** Translate approved research into investable portfolios within mandates and risk budgets.

**Agents:** Portfolio Manager Agent  
**Services:** Portfolio Optimisation Engine (to be built), Mandate Compliance Engine (to be built), Rebalancing Framework (to be built)  
**Governance rules:**
- PM cannot publish without Associate Reviewer PASS and Committee record
- Mandate constraints are non-overridable by PM

**Maturity target:** 8.5/10

---

### Division D: Investment Governance

**Purpose:** Ensure every published output meets process and evidentiary standards.

**Agents:** Associate Reviewer  
**Services:** Investment Committee Process (to be built), Human Override Log, Prompt Registry, Audit Exporter  
**Governance rules:**
- Reviewer must be structurally independent (cannot be the same agent that wrote the analysis)
- FAIL verdict always blocks publication regardless of any override without logged approver identity

**Maturity target:** 9.0/10

---

### Division E: Performance & Analytics

**Purpose:** Track portfolio outcomes, attribute returns, and feed results back into future research.

**Agents:** Performance Attribution Agent (to be built)  
**Services:** Performance Tracker (to be built), Attribution Engine (to be built), Research Memory Store (to be built)  
**Governance rules:**
- Attribution results are published alongside research for all runs >30 days old
- Thesis health is tracked continuously and flags when thesis breach conditions are met

**Maturity target:** 8.0/10

---

## 7. Success Metrics

### Research Quality Metrics

| Metric | Current Target | JPAM-Equivalent Target |
|---|---|---|
| Claims with Tier 1/2 sources | No enforcement | ≥ 80% of core claims |
| Valuations with explicit methodology | No enforcement | 100% |
| Red team risks per top idea | No minimum | ≥ 3 per idea |
| Publications blocked by reviewer | Not tracked | Tracked; target <15% auto-pass rate |

### Risk & Portfolio Metrics

| Metric | Current | Target |
|---|---|---|
| Factor exposure reported | No | Yes — all 4 factors per run |
| VaR calculated | No | Yes — 95% parametric VaR |
| Mandate compliance checked | No | Yes — hard block on breach |
| Tracking error vs benchmark | No | Yes — mandatory output |

### Governance Metrics

| Metric | Current | Target |
|---|---|---|
| Every run logged | Yes | Yes |
| Every override logged with approver | Partial | Yes — mandatory |
| Prompt version on every run | Yes (hash) | Yes + regression status |
| Committee record per publication | No | Yes |

### Operational Metrics

| Metric | Current | Target |
|---|---|---|
| Pipeline completion rate | Not tracked | ≥ 95% of scheduled runs complete |
| Mean time per full run | Not tracked | < 8 minutes for 15-stock universe |
| Test coverage (unit + product) | 103 unit tests | ≥ 200 tests including product-level |
| LLM cost per run | Not tracked | < $8 per full 15-stock run |

---

## 8. Risk Register for the Build Itself

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Architecture convergence takes longer than expected due to frontend/backend coupling | High | High | Start with adapter pattern — thin wrapper first, full unification second |
| Factor exposure model requires paid data sources not currently available | Medium | Medium | Use publicly available beta estimates from yfinance as Phase 2 proxy |
| Performance attribution requires 30–90 days of live data to be meaningful | High | Medium | Start logging portfolios now so data accrues — attribution becomes meaningful from run 30+ |
| Investment committee simulation is artificial without real human approvers | High | Low | Log system-generated committee records; design for real human injection later |
| LLM structured output enforcement breaks existing working agents | Medium | High | Implement in Phase 0.3 behind a feature flag; shadow-compare structured vs raw output first |
| Research memory vector database introduces infrastructure complexity | Medium | Medium | Start with SQLite FTS as simple memory store; upgrade to pgvector later |
| Expanded universe coverage hits FMP/Finnhub API budget limits | Medium | Medium | Implement caching and quota management in Phase 7 before expanding coverage |

---

*Roadmap logged: March 28, 2026 — aligned with critical architecture review in ARCHITECTURE.md Section 10*
