# Multi-Agent Parallel Build Plan
*AI Infrastructure Research Platform — JPAM Emulator*
*Generated from: IMPROVEMENTS.md (5109 lines), TRACKER.md, ARCHITECTURE.md deep-dive analysis*
*Baseline: Sessions 1–19 complete · 1072/1072 tests passing · async event loop bug fixed*

> **⚠️ Audit note (post-generation correction):** The original baseline claimed Sessions 1–18 with 1004 tests. 
> A deep codebase audit revealed Session 19 (DSQ-1–8, DSQ-12/13/15) was already fully implemented 
> in `engine.py`. `gemini_deep_research.py` (Stage 4.5) also existed but was unwired — it has since 
> been wired in (GDR-1). `AnalystRatingChange`/`AdverseSignal` schemas have been added. 
> Test count corrected: 1072 passing (31 previously—failing async tests now fixed). 
> DSQ-9/10/11/14/16 remain as deferred items for Session 20.

---

## Contents

1. [Platform Status — What Exists](#1-platform-status--what-exists)
2. [What Needs To Be Built — Master Gap List](#2-what-needs-to-be-built--master-gap-list)
3. [Agent Cluster Allocations](#3-agent-cluster-allocations)
4. [Interface Contracts Between Clusters](#4-interface-contracts-between-clusters)
5. [Sequencing & Dependency Rules](#5-sequencing--dependency-rules)
6. [Session-by-Session Roadmap](#6-session-by-session-roadmap)
7. [Shared File Edit Registry](#7-shared-file-edit-registry)
8. [Acceptance Criteria Summary](#8-acceptance-criteria-summary)

---

## 1. Platform Status — What Exists

### 1.1 Confirmed Existing Services (`src/research_pipeline/services/`)
| File | Purpose |
|---|---|
| `audit_exporter.py` | Audit trail export |
| `australian_tax_service.py` | AU tax wrapper (Session 14) |
| `benchmark_module.py` | BHB attribution |
| `benzinga_service.py` | Benzinga analyst ratings API *(verify completeness)* |
| `cache_layer.py` | Response caching |
| `consensus_reconciliation.py` | Cross-provider consensus |
| `data_qa_lineage.py` | Data quality lineage |
| `dcf_engine.py` | Discounted cash flow |
| `economic_indicator_service.py` | FRED/RBA macro indicators (Session 12) |
| `esg_service.py` | ESG scoring |
| `etf_overlap_engine.py` | ETF overlap detection |
| `factor_engine.py` | Fama-French / factor model |
| `gemini_deep_research.py` | Gemini Deep Research Stage 4.5 (GDR-1) — ✅ wired |
| `golden_tests.py` | Golden test fixtures |
| `investment_committee.py` | IC gate logic |
| `live_return_store.py` | Daily NAV / return storage |
| `macro_scenario_service.py` | Macro scenario runner (Session 12) |
| `mandate_compliance.py` | Mandate constraint checks |
| `market_data_ingestor.py` | FMP / yfinance / FRED data ingestion |
| `memory_injection.py` | Memory injection into prompts |
| `monitoring_engine.py` | Pipeline observability |
| `observability.py` | Ops metrics |
| `performance_tracker.py` | Performance attribution |
| `portfolio_optimisation.py` | MVO portfolio optimisation |
| `position_sizing.py` | Kelly / risk-based sizing |
| `prompt_registry.py` | Versioned prompt storage |
| `provenance_service.py` | Evidence provenance (Session 17) |
| `qualitative_data_service.py` | News / transcript qualitative data |
| `rebalancing_engine.py` | Portfolio rebalancing |
| `report_assembly.py` | Report section assembly |
| `report_formats.py` | PDF / Markdown output |
| `research_memory.py` | SQLite FTS5 memory layer |
| `risk_engine.py` | VaR / risk calculations |
| `run_registry.py` | Run state persistence |
| `scenario_engine.py` | Scenario analysis |
| `scheduler.py` | Background task scheduling |
| `sec_api_service.py` | SEC EDGAR API *(verify completeness)* |
| `sector_data_service.py` | Sector-level data (Session 13) |
| `superannuation_mandate.py` | APRA SPS 530 mandate (Session 14) |
| `var_engine.py` | Value-at-Risk engine |

### 1.2 Confirmed Existing Agents (`src/research_pipeline/agents/`)
| File | Purpose |
|---|---|
| `associate_reviewer.py` | Associate review stage |
| `base_agent.py` | Base class — all agents inherit |
| `economy_analyst.py` | Macro economy analyst (Session 12) |
| `esg_analyst.py` | ESG analyst |
| `evidence_librarian.py` | Stage 5 evidence gathering |
| `fixed_income_analyst.py` | FI thesis agent (**NOTE:** not full bond analyst — that is MAC-4) |
| `generic_sector_analyst.py` | Reusable sector analyst (Session 11) |
| `macro_political.py` | Macro / political risk (Stage 8) |
| `orchestrator.py` | Stage 1 orchestrator |
| `portfolio_manager.py` | Stage 12 PM |
| `quant_research_analyst.py` | Stage 9 quant analyst |
| `red_team_analyst.py` | Stage 10 red team |
| `report_narrative_agent.py` | Stage 13 narrative |
| `sector_analyst_asx.py` | ASX-specific sector analysis |
| `sector_analysts.py` | Sector analyst routing |
| `valuation_analyst.py` | Stage 7 valuation |

### 1.3 Confirmed Existing Schemas (`src/research_pipeline/schemas/`)
Key existing schema files: `base.py`, `events.py`, `governance.py`, `macro.py`, `market_data.py`, `pipeline.py`, `portfolio.py`, `qualitative.py`, `reports.py`

### 1.4 Confirmed Existing API / Frontend
- FastAPI: `src/api/` (Session 15) — `/runs`, `/events` SSE, `/provenance`, quant endpoints
- Next.js: `frontend/src/` (Session 16) — 7 pages, 8+ components, Zustand store
- Streamlit: `src/frontend/app.py` — internal dev/demo console

---

## 2. What Needs To Be Built — Master Gap List

### 2.1 Critical Single-Line Fix (✅ COMPLETE)
> **DSQ-1** has been fixed. `QualitativeDataService` is fully wired into Stage 5.
> SEC API (Stage 2 + Stage 5), Benzinga (Stage 2 + Stage 5 + Stage 10 adverse signals), and
> Gemini Deep Research (Stage 4.5) are all wired.
> Test suite: **1072/1072 passing**, 0 errors.

---

### 2.2 Part L — Backend Contract Hardening (BCH items)

| ID | What to Build | New Files | Touches Existing |
|---|---|---|---|
| BCH-1 | Claim Ledger as Live Contract — `ClaimDispositionReport` schema; Gate 11 blocks on undisposed FAIL claims | `schemas/` extension | `schemas/portfolio.py`, `gates.py` |
| BCH-2 | `CrossSectorSynthesis` service + schemas: `SectorDisagreement`, `SharedBottleneck` | `services/cross_sector_synthesis.py` | `schemas/portfolio.py`, `engine.py` Stages 7/9/11/12 |
| BCH-3 | `MacroAssumptionAcknowledgement` mandatory on `ValuationCard`; Gate 7 enforcement | schema extension | `schemas/portfolio.py`, `gates.py`, agent prompt |
| BCH-4 | Red Team → Thesis Repair Loop: `ThesisRepairRequest`/`ThesisRepairResponse`; engine repair path for `severity="material"` | schema new models | `engine.py` |
| BCH-5 | PipelineEngine decomposition → `BaseStageExecutor`, `StageContext`, each stage in own file | `pipeline/stages/` directory (15 files) | `engine.py` MAJOR REFACTOR |
| BCH-6 | Schema Versioning mixin; version checks in `run_registry.py`; `SCHEMA_CHANGELOG.md` | `schemas/_base.py` | `run_registry.py` |
| BCH-7 | Macro wiring verification — confirm all 6 checks on `EconomicIndicatorService` in Stage 8; `PoliticalContextPacket` | `schemas/macro.py` extension | `engine.py` Stage 8 |
| BCH-8 | Documentation fidelity — `PIPELINE_STAGES.md`, `ARCHITECTURE.md`, `configs/thresholds.yaml` header | doc files only | — |
| BCH-9 | `run_full_pipeline(request: RunRequest)` canonical signature everywhere | — | `engine.py`, callers |
| BCH-10 | Cancellation/backpressure — `cancel_token`, per-stage timeouts, `/runs/{id}/partial` endpoint | — | `engine.py`, `api/routes/runs.py` |
| BCH-QW-1–10 | 10 quick wins: concentration disclosure, IC all-paths, memory store at Stage 14, memory injection Stage 5, validation audit, scheduler alerting, Gate 1 strength, Gate 10 deterministic, `PoliticalContextPacket` threading | scattered small changes | Various |

---

### 2.3 Part M — Session 19: Data Sourcing Quality (DSQ-1–16)

> **✅ STATUS: Sessions 19 DSQ-1 through DSQ-8 are COMPLETE. DSQ-12/13/15 also COMPLETE.**
> **GDR-1 (Gemini Deep Research Stage 4.5) also COMPLETE.**
> Remaining deferred items: DSQ-9/10/11 (NewsAPI) and DSQ-14/16 — now part of Session 20.

| ID | Task | New Files | Existing Files Changed | Status |
|---|---|---|---|---|
| DSQ-1 | Wire `QualitativeDataService` into Stage 5 | — | `engine.py` | ✅ DONE |
| DSQ-2 | Verify/complete `SECApiService` — filings, insider, XBRL | `sec_api_service.py` (verify) | — | ✅ DONE |
| DSQ-3 | Wire SEC into Stage 2 data ingestion | — | `engine.py` | ✅ DONE |
| DSQ-4 | Wire SEC into Stage 5 (10-K MD&A, Form 4, XBRL) | — | `engine.py` | ✅ DONE |
| DSQ-5 | Verify/complete `BenzingaService` — analyst ratings, price target history | `benzinga_service.py` (verify) | — | ✅ DONE |
| DSQ-6 | Wire Benzinga into Stage 2 (primary analyst rating source) | — | `engine.py` | ✅ DONE |
| DSQ-7 | Wire Benzinga into Stage 5 evidence | — | `engine.py` | ✅ DONE |
| DSQ-8 | Wire Benzinga adverse signals into Stage 10 Red Team | — | `engine.py` | ✅ DONE |
| DSQ-9 | `ArticleExtractionService` — URL → clean article body | `services/article_extraction_service.py` | — | 🔲 Deferred → Session 20 |
| DSQ-10 | `NewsApiService` with publisher allowlist | `services/news_api_service.py` | — | 🔲 Deferred → Session 20 |
| DSQ-11 | Wire NewsAPI into Stage 8 Macro/Political | — | `engine.py` | 🔲 Deferred → Session 20 |
| DSQ-12 | Stage 3 XBRL vs FMP cross-check in reconciliation | — | `consensus_reconciliation.py` | ✅ DONE (partial) |
| DSQ-13 | Wire `fetch_fmp_ratios` into `ingest_ticker()` | — | `market_data_ingestor.py` | ✅ DONE |
| DSQ-14 | Synthetic data contamination tagging in `RiskPacket` + `SelfAuditPacket` | — | `risk_engine.py`, `governance.py` | 🔲 Deferred → Session 20 |
| DSQ-15 | `tests/test_session19.py` — 50 tests | `tests/test_session19.py` | — | ✅ DONE (50 tests pass) |
| DSQ-16 | API keys wired into `PipelineConfig` + `configs/pipeline.yaml` allowlist | — | `config/loader.py`, `configs/pipeline.yaml` | ⚠️ PARTIAL (SEC/Benzinga keys done; `NEWS_API_KEY` deferred) |
| GDR-1 | Gemini Deep Research Stage 4.5 — wire `GeminiDeepResearchService` into engine | — | `engine.py`, `config/loader.py`, `config/settings.py` | ✅ DONE |

**Schema status for Session 19 (in `schemas/qualitative.py`):**
- `FilingMetadata` — ✅ already existed before this session
- `MaterialEvent` — ✅ already existed before this session
- `InsiderTransaction` — ✅ already existed before this session
- `FilingSection` — ✅ already existed before this session
- `AnalystRatingChange` — ✅ added in post-generation audit fix
- `AdverseSignal` — ✅ added in post-generation audit fix
**Schema extension:** `SelfAuditPacket.synthetic_data_fields` in `schemas/governance.py` — 🔲 deferred to Session 20 (DSQ-14)

---

### 2.4 Part N — Session 20: Sector Intelligence & Platform Hardening (DSQ-17–32)

| ID | Task | New Files |
|---|---|---|
| DSQ-17 | `DataFreshnessCatalog` — field-level freshness tracking | `services/data_freshness_service.py` |
| DSQ-18 | `RateLimitBudgetManager` — centralised multi-API quota tracking | `services/rate_limit_manager.py` |
| DSQ-19 | `SourceRankingService` — publisher trust scores, URL-hash dedup | `services/source_ranking_service.py` |
| DSQ-20 | `EIAService` — US Energy Information Administration API (free) | `services/eia_service.py` |
| DSQ-21 | `FERCService` — FERC interconnection queue data (free) | `services/ferc_service.py` |
| DSQ-22 | Wire EIA + FERC into Stage 8 | `engine.py` |
| DSQ-23 | `ASXAnnouncementService` — ASX public announcements (free, no auth) | `services/asx_announcement_service.py` |
| DSQ-24 | Wire ASX announcements into Stage 2 + Stage 5 for AU tickers | `engine.py` |
| DSQ-25 | `TranscriptParserService` — structured guidance/capex/margin extraction | `services/transcript_parser_service.py` |
| DSQ-26 | Wire structured transcripts into Stage 5 | `engine.py` |
| DSQ-27 | Political risk overhaul — `RegulatoryEventPacket`; wire into Stage 8 | `schemas/macro.py`, `engine.py` |
| DSQ-28 | `WSTSService` — semiconductor shipment data (WSTS/SEMI public) | `services/wsts_service.py` |
| DSQ-29 | `HyperscalerCapexTracker` — capex from hyperscaler XBRL + transcripts | `services/hyperscaler_capex_tracker.py` |
| DSQ-30 | `.env.example` completeness fix | `.env.example`, `README.md` |
| DSQ-31 | `IRScraperService` — IR RSS feeds, robots.txt-respecting | `services/ir_scraper_service.py` |
| DSQ-32 | `tests/test_session20.py` — 50+ tests | `tests/test_session20.py` |

**New schemas:** `ASXAnnouncement`, `ParsedTranscript`, `GuidanceStatement`, `ManagementToneSignal`, `GuidanceRevisionDelta`, `SemiconductorShipmentSnapshot`, `HyperscalerCapexData` in `qualitative.py`; `RegulatoryEvent`, `RegulatoryEventPacket`, `MacroPowerGridPacket` in `macro.py`

---

### 2.5 Part O — Session 21: Multi-Asset Class Expansion (MAC-1–15)

| ID | Task | New Files |
|---|---|---|
| MAC-1 | `AssetClassRouter` — classify equity/bond/REIT/infra per ticker | `services/asset_class_router.py` |
| MAC-2 | `FixedIncomeDataService` — RBA F-series, AOFM, FRED credit spreads | `services/fixed_income_data_service.py` |
| MAC-3 | `BondMarketPacket` schema — yield curves, spreads, rate paths | `schemas/fixed_income.py` |
| MAC-4 | `FixedIncomeAnalystAgent` — bond analysis producing `BondAnalysisCard` | `agents/fixed_income_analyst_agent.py` |
| MAC-5 | `CreditRiskAnalystAgent` — issuer credit producing `CreditAssessmentCard` | `agents/credit_risk_analyst_agent.py` |
| MAC-6 | Wire FI path into Stages 6 and 7 | `engine.py` |
| MAC-7 | `REITAnalystAgent` — NTA, FFO, WALE, cap rate analysis | `agents/reit_analyst_agent.py` |
| MAC-8 | `ListedInfrastructureAnalystAgent` — RAB multiple, regulated WACC | `agents/listed_infrastructure_analyst_agent.py` |
| MAC-9 | GICS sector routing in Stage 6 — 11 sectors mapped to agents | `services/gics_router.py`, `engine.py` |
| MAC-10 | `MultiAssetPortfolioOptimiser` — blended equity + FI + REIT + infra | `services/multi_asset_portfolio_optimiser.py` |
| MAC-11 | `FXHedgingAnalystService` — hedged vs unhedged expected return | `services/fx_hedging_analyst_service.py` |
| MAC-12 | Expand `MandateConfig` — insurance (GPS 320), endowment, wholesale, SMA | `schemas/mandate.py` extension |
| MAC-13 | `AOFMService` — AU sovereign bond data (AOFM API, free) | `services/aofm_service.py` |
| MAC-14 | Wire `BondMarketPacket` into Stage 8 macro context | `engine.py`, `schemas/macro.py` |
| MAC-15 | `tests/test_session21.py` — 50+ tests | `tests/test_session21.py` |

**New config directories:** `configs/universes/` (6 YAML files), `configs/mandates/` (preset mandate YAMLs)

---

### 2.6 Part P — Session 22: JPAM Immersive Experience Layer (EXP-1–12)

| ID | Task | New Files |
|---|---|---|
| EXP-1 | `StageNarrative` schema + emission from all 15 stage methods | `schemas/events.py` extension, `engine.py` |
| EXP-2 | `AgentPersona` registry + `AGENT_PERSONAS` dict; `persona` field on `StageEvent` | `schemas/personas.py`, `schemas/events.py` |
| EXP-3 | `MorningBriefPacket` schema + `MorningBriefService` + `/api/morning-brief` endpoint | `schemas/morning_brief.py`, `services/morning_brief_service.py`, `api/routes/morning_brief.py` |
| EXP-4 | `RunNarrative` + `StageContribution` + `ICDecisionSummary` schemas + `RunNarrativeService` | `schemas/run_narrative.py`, `services/run_narrative_service.py` |
| EXP-5 | `ResearchFloorPanel` — pipeline tracker redesigned as analyst desk grid | `components/floor/research-floor-panel.tsx`, `components/floor/desk-card.tsx` |
| EXP-6 | `MorningBriefPanel` — market moves, regime flags, sector focus on dashboard home | `components/morning-brief/morning-brief-panel.tsx` |
| EXP-7 | `ICMeetingRoom` — full-width IC view with animated sequential vote reveal | `components/governance/ic-meeting-room.tsx` |
| EXP-8 | "How This Was Made" tab on run detail page | `app/runs/[run_id]/page.tsx` extension |
| EXP-9 | `TeamReferencePanel` — "The Team" sidebar page | `components/team/team-reference-panel.tsx`, `app/team/page.tsx` |
| EXP-10 | Streamlit frontend narrative parity | `src/frontend/app.py` |
| EXP-11 | `StageNarrative` content quality — each agent produces ticker-specific concrete narrative | All `agents/*.py` files |
| EXP-12 | `tests/test_session22.py` — 40+ tests | `tests/test_session22.py` |

---

### 2.7 Part Q — Session 23: Daily Rhythms (RHY-1–8)

| ID | Task | New Files |
|---|---|---|
| RHY-1 | `CalendarEvent` schema + `ResearchCalendarService` (Benzinga earnings, FOMC, FRED) | `schemas/calendar.py`, `services/research_calendar_service.py` |
| RHY-1b | `ResearchCalendarPanel` + `/calendar` page | `components/calendar/research-calendar-panel.tsx`, `app/calendar/page.tsx` |
| RHY-2 | `CoverageRecord` schema + `CoverageBookService` (SQLite); auto-update on run completion | `schemas/coverage.py`, `services/coverage_book_service.py` |
| RHY-2b | `/coverage` page — sortable coverage table | `app/coverage/page.tsx`, `components/coverage/coverage-table.tsx` |
| RHY-3 | `PortfolioBlotterService` — live positions vs target; drift alert detection | `services/portfolio_blotter_service.py` |
| RHY-3b | `/portfolio` page — blotter table with drift alerts | `app/portfolio/page.tsx`, `components/portfolio/blotter-table.tsx` |
| RHY-4 | `StandupBriefService` + `/api/standup` endpoint | `schemas/standup.py`, `services/standup_brief_service.py`, `api/routes/standup.py` |
| RHY-4b | `StandupBriefPanel` on dashboard | `components/standup/standup-brief-panel.tsx` |
| RHY-5 | `NewsWireItem` schema + `NewsWireService` (Benzinga + NewsAPI + 8-K events) | `schemas/news_wire.py`, `services/news_wire_service.py` |
| RHY-5b | `NewsWirePanel` — right-rail SSE-streamed news feed | `components/news-wire/news-wire-panel.tsx` |
| RHY-6 | `RecommendationRecord` schema + `TrackRecordService` — log every IC-approved rec | `schemas/track_record.py`, `services/track_record_service.py` |
| RHY-6b | `/track-record` page — performance table, win rate, post-mortem links | `app/track-record/page.tsx`, `components/track-record/track-record-table.tsx` |
| RHY-7 | `ScenarioDefinition` schema + `ScenarioRunner` (partial pipeline re-run, Stages 8/9/12) | `schemas/scenario.py`, `services/scenario_runner.py`, `api/routes/scenario.py` |
| RHY-7b | `/scenario` page — pre-built templates, custom sliders, result diff | `app/scenario/page.tsx`, `components/scenario/scenario-sandbox.tsx` |
| RHY-8 | `ComplianceBoardPacket` schema + `ComplianceBoardService` | `schemas/compliance.py`, `services/compliance_board_service.py` |
| RHY-8b | Compliance badge in top bar + `/compliance` page | `components/layout/top-bar.tsx`, `app/compliance/page.tsx` |
| RHY-SN | Update sidebar nav — 14 items across 4 groups | `components/layout/sidebar.tsx` |
| RHY-TEST | `tests/test_session23.py` — 50+ tests | `tests/test_session23.py` |

---

### 2.8 Part R — Session 24: Institutional Depth Layer (INS-1–10)

| ID | Task | New Files |
|---|---|---|
| INS-1 | `MarketTile` + `MarketMonitorPacket` schemas; `MarketMonitorService`; `/api/market-monitor` | `schemas/market_monitor.py`, `services/market_monitor_service.py`, `api/routes/market_monitor.py` |
| INS-1b | `MarketMonitorPanel` — live tile grid on `/market` page | `components/market/market-monitor-panel.tsx`, `app/market/page.tsx` |
| INS-2 | `FundFactSheet` + `ClientLetter` schemas; `ClientReportingService` (PDF + JSON) | `schemas/client_report.py`, `services/client_reporting_service.py` |
| INS-2b | `/reports` client document page | `app/reports/page.tsx`, `components/reports/report-generator.tsx` |
| INS-3 | `/workbench/[ticker]` — 6-panel single-stock view over existing services | `app/workbench/[ticker]/page.tsx`, `components/workbench/` |
| INS-4 | `FactorExposure` + `RiskDashboardPacket` schemas; `RiskDashboardService` | `schemas/risk_dashboard.py`, `services/risk_dashboard_service.py` |
| INS-4b | `/risk` page — factor exposures, VaR, mandate compliance | `app/risk/page.tsx`, `components/risk/risk-dashboard.tsx` |
| INS-5 | `EarningsSeason` + `EarningsReporter` schemas; `EarningsSeasonService`; rapid run profile | `schemas/earnings_season.py`, `services/earnings_season_service.py` |
| INS-5b | `/earnings-season` page — queue, countdown, surprise tracker | `app/earnings-season/page.tsx` |
| INS-6 | `WatchlistItem` schema + `WatchlistService` (SQLite); auto-suggest from NewsWire | `schemas/watchlist.py`, `services/watchlist_service.py` |
| INS-6b | `/watchlist` Kanban page — 4-column drag-and-drop board | `app/watchlist/page.tsx`, `components/watchlist/kanban-board.tsx` |
| INS-7 | `RegimeDimension` + `MacroRegimePacket` schemas; `MacroRegimeService` (5 dimensions) | `schemas/macro_regime.py`, `services/macro_regime_service.py` |
| INS-7b | `/macro-regime` page — heatmap grid, trend arrows, cycle phase | `app/macro-regime/page.tsx`, `components/macro/regime-heatmap.tsx` |
| INS-8 | `KnowledgeLibraryService` — wraps `ResearchMemory` FTS5; name history, claim ancestry | `services/knowledge_library_service.py`, `api/routes/library.py` |
| INS-8b | `/library` page — full-text search across claims + run narratives | `app/library/page.tsx`, `components/library/search-results.tsx` |
| INS-9 | `StreetVsHouse` schema + `ConsensusComparisonService` — divergence calc | `schemas/street_vs_house.py`, `services/consensus_comparison_service.py` |
| INS-9b | `/street-vs-house` page — divergence table, alpha flags | `app/street-vs-house/page.tsx` |
| INS-10 | `StressScenario` (10 standard); `StressTestRunner` applying shocks to quant output | `schemas/stress_test.py`, `services/stress_test_runner.py` |
| INS-10b | `/stress-test` page — scenario table, portfolio vs benchmark, APRA flags | `app/stress-test/page.tsx`, `components/risk/stress-test-table.tsx` |
| INS-TEST | `tests/test_session24.py` — 60+ tests | `tests/test_session24.py` |

---

### 2.9 E-items — Original Gap Closers (E-1–10)

| ID | What | Status | New Files |
|---|---|---|---|
| E-1 | Black-Litterman Portfolio Construction | 🔲 NOT BUILT | Extension to `portfolio_optimisation.py` |
| E-2 | GARCH(1,1) VaR | 🔲 NOT BUILT | Extension to `var_engine.py` (needs `arch` library) |
| E-3 | HMM Regime Detection | 🔲 NOT BUILT | `services/regime_detector.py` |
| E-4 | Real Benchmark Data for BHB (ASX 200 TR + S&P 500 TR) | 🔲 NOT BUILT (still synthetic) | Extension to `benchmark_module.py` |
| E-5 | AUD/USD Currency Attribution | 🔲 NOT BUILT | `services/currency_attribution_engine.py` |
| E-6 | Portfolio Carbon Intensity Score | 🔲 NOT BUILT | Extension to `esg_service.py` |
| E-7 | Interactive HTML Research Report | 🔲 NOT BUILT | `services/report_html_service.py` |
| E-8 | Multi-Provider LLM Fallback Chain | 🔲 NOT BUILT | Extension to `base_agent.py` |
| E-9 | Cross-Run Research Memory & Trend Alerts | 🔲 NOT BUILT | Extension to `research_memory.py` |
| E-10 | Earnings Transcript / News Sentiment NLP (FinBERT) | 🔲 NOT BUILT | `services/sentiment_nlp_service.py` |

---

## 3. Agent Cluster Allocations

Each cluster is designed to be **buildable in parallel** with minimal merge conflicts. Shared file edits are tracked in Section 7.

---

### CLUSTER A — Data Sourcing Core (Session 19)
**Session:** 19 | **Agent count:** 1–2 | **Tests:** `tests/test_session19.py` (40+ tests)

**Scope:** Wire the already-built qualitative data services into the pipeline engine. This is the highest-ROI work in the codebase.

**Tasks:**
- DSQ-1: Wire `QualitativeDataService` into Stage 5 (**DO THIS FIRST**)
- DSQ-2/3/4: SEC API verify + wire into Stages 2 and 5
- DSQ-5/6/7/8: Benzinga verify + wire into Stages 2, 5, 10
- DSQ-9: `ArticleExtractionService` (new service)
- DSQ-10: `NewsApiService` (new service)
- DSQ-11: Wire NewsAPI into Stage 8
- DSQ-12: XBRL vs FMP cross-check in `consensus_reconciliation.py`
- DSQ-13: Wire `fetch_fmp_ratios` into `ingest_ticker()`
- DSQ-14: Synthetic data contamination tagging
- DSQ-16: API keys into `PipelineConfig`

**New files:**
```
src/research_pipeline/services/article_extraction_service.py
src/research_pipeline/services/news_api_service.py
tests/test_session19.py
```

**Schema additions (append-only to existing files):**
- `schemas/qualitative.py`: add `FilingMetadata`, `MaterialEvent`, `InsiderTransaction`, `FilingSection`, `AnalystRatingChange`, `AdverseSignal`
- `schemas/governance.py`: add `synthetic_data_fields` to `SelfAuditPacket`

**Primary shared file:** `engine.py` (all wiring changes here, Stages 2/5/8/10)

**Interface contract output:** All stage results written to existing `stage_outputs` dict keys; no new keys required. `QualitativeDataService` results injected as `stage_outputs["qualitative"]`.

---

### CLUSTER B — Backend Contract Hardening (Part L)
**Session:** Parallel to 19/20 | **Agent count:** 2 | **Tests:** additions to existing test files

**Scope:** Strengthen the contracts of the existing pipeline — schemas, gates, and engine behaviour — without adding new data sources.

**Sub-cluster B1 (Schema & Gates):** BCH-1, BCH-2, BCH-3, BCH-6, BCH-7, BCH-8, BCH-QW-1 through BCH-QW-10
- New schemas: `ClaimDispositionReport`, `CrossSectorSynthesis`, `SectorDisagreement`, `SharedBottleneck`, `MacroAssumptionAcknowledgement`, `PoliticalContextPacket`, `VersionedSchema`
- Gate changes: BCH-1 (Gate 11), BCH-3 (Gate 7)
- New service: `cross_sector_synthesis.py`
- Schema versioning: `schemas/_base.py` (new)

**Sub-cluster B2 (Engine Behaviour):** BCH-4, BCH-9, BCH-10
- BCH-4: Thesis repair loop — new repair path in `engine.py` after Stage 10
- BCH-9: Canonical `run_full_pipeline(request: RunRequest)` signature
- BCH-10: Cancel token, per-stage timeouts, `/runs/{id}/partial` endpoint

> ⚠️ **BCH-5 (PipelineEngine Decomposition) is excluded from this cluster** — it is a major refactor that must be the **last thing done** (Cluster G). B2 should not pre-stage any of the decomposition work.

**New files:**
```
src/research_pipeline/services/cross_sector_synthesis.py
src/research_pipeline/schemas/_base.py
SCHEMA_CHANGELOG.md
```

**Primary shared files:** `schemas/portfolio.py`, `gates.py`, `engine.py` (additive changes only)

---

### CLUSTER C — Multi-Asset Class Expansion (Session 21)
**Session:** 21 | **Agent count:** 2 | **Tests:** `tests/test_session21.py` (50+ tests)

**Scope:** Entirely new asset classes: fixed income, REITs, listed infrastructure. All new files — only `engine.py` routing is additive.

**Tasks:** MAC-1 through MAC-15

**New files (backend):**
```
src/research_pipeline/services/asset_class_router.py
src/research_pipeline/services/fixed_income_data_service.py
src/research_pipeline/services/aofm_service.py
src/research_pipeline/services/gics_router.py
src/research_pipeline/services/multi_asset_portfolio_optimiser.py
src/research_pipeline/services/fx_hedging_analyst_service.py
src/research_pipeline/agents/fixed_income_analyst_agent.py
src/research_pipeline/agents/credit_risk_analyst_agent.py
src/research_pipeline/agents/reit_analyst_agent.py
src/research_pipeline/agents/listed_infrastructure_analyst_agent.py
src/research_pipeline/schemas/fixed_income.py
configs/universes/ai_infra_thematic.yaml
configs/universes/asx200_core.yaml
configs/universes/us_large_cap_diversified.yaml
configs/universes/au_fixed_income.yaml
configs/universes/balanced_multi_asset.yaml
configs/universes/income_alternatives.yaml
configs/mandates/  (preset mandate YAMLs)
tests/test_session21.py
```

**Existing files changed (additive only):**
- `schemas/macro.py`: add `BondMarketPacket` reference
- `schemas/mandate.py`: extend `MandateConfig` for insurance / endowment types
- `engine.py`: routing conditions based on `AssetClassRouter` output — new `if` branches only

**IMPORTANT:** `agents/fixed_income_analyst_agent.py` is a NEW file. The existing `agents/fixed_income_analyst.py` is a thesis agent and must **not** be renamed or replaced.

---

### CLUSTER D — Data Intelligence Layer (Session 20)
**Session:** 20 | **Agent count:** 1–2 | **Tests:** `tests/test_session20.py` (50+ tests)

**Scope:** Advanced data services — intelligence, freshness tracking, rate limiting, specialist data APIs. All new service files.

**Tasks:** DSQ-17 through DSQ-32

**New files:**
```
src/research_pipeline/services/data_freshness_service.py
src/research_pipeline/services/rate_limit_manager.py
src/research_pipeline/services/source_ranking_service.py
src/research_pipeline/services/eia_service.py
src/research_pipeline/services/ferc_service.py
src/research_pipeline/services/asx_announcement_service.py
src/research_pipeline/services/transcript_parser_service.py
src/research_pipeline/services/wsts_service.py
src/research_pipeline/services/hyperscaler_capex_tracker.py
src/research_pipeline/services/ir_scraper_service.py
tests/test_session20.py
.env.example (update)
```

**Schema additions:**
- `schemas/qualitative.py`: `ASXAnnouncement`, `ParsedTranscript`, `GuidanceStatement`, `ManagementToneSignal`, `GuidanceRevisionDelta`, `SemiconductorShipmentSnapshot`, `HyperscalerCapexData`
- `schemas/macro.py`: `RegulatoryEvent`, `RegulatoryEventPacket`, `MacroPowerGridPacket`

**Shared file coordination with Cluster A:**
- Both clusters append to `schemas/qualitative.py` — **Cluster A defines first** (Session 19), Cluster D appends new models. No field overlap.
- `engine.py` receives wiring changes for DSQ-22 (EIA/FERC Stage 8), DSQ-24 (ASX Stage 2/5), DSQ-26 (transcripts Stage 5), DSQ-27 (regulatory Stage 8) — all additive `if`-branches after Cluster A's changes are merged.

---

### CLUSTER E — Immersive Experience Layer (Session 22)
**Session:** 22 | **Agent count:** 2 (backend + frontend) | **Tests:** `tests/test_session22.py` (40+ tests)

**Scope:** Institutional identity layer — personas, stage narratives, IC meeting room, morning brief, run narrative. Backend changes are purely additive.

**Backend tasks (EXP-1 to EXP-4):**
**New files:**
```
src/research_pipeline/schemas/personas.py
src/research_pipeline/schemas/morning_brief.py
src/research_pipeline/schemas/run_narrative.py
src/research_pipeline/services/morning_brief_service.py
src/research_pipeline/services/run_narrative_service.py
src/api/routes/morning_brief.py
```
**Existing files (additive only):**
- `schemas/events.py`: add `StageNarrative` model + `persona` field on `StageEvent`
- `engine.py`: emit `StageNarrative` events; call `RunNarrativeService` on completion
- All `agents/*.py`: add `StageNarrative` emission with ticker-specific content (EXP-11)

**Frontend tasks (EXP-5 to EXP-10):**
**New files:**
```
frontend/src/components/floor/research-floor-panel.tsx
frontend/src/components/floor/desk-card.tsx
frontend/src/components/morning-brief/morning-brief-panel.tsx
frontend/src/components/governance/ic-meeting-room.tsx
frontend/src/components/team/team-reference-panel.tsx
frontend/src/app/team/page.tsx
```
**Existing frontend files (additive):**
- `frontend/src/app/runs/[run_id]/page.tsx`: add "How This Was Made" tab
- `frontend/src/app/page.tsx`: add `MorningBriefPanel` at top

---

### CLUSTER F — E-item Gap Closers (Quant & Analytics)
**Session:** Parallel to any session | **Agent count:** 2 | **Tests:** additions to appropriate test files

**Scope:** Close the original 10 gap items from the E-list. Mostly contained enhancement tasks within existing service files.

**Sub-cluster F1 (Quant):** E-1, E-2, E-3, E-4, E-5
- E-1: `BlackLittermanEngine` class in `portfolio_optimisation.py`
- E-2: `GARCHVaR` class in `var_engine.py` (add `arch` to `requirements.txt`)
- E-3: `services/regime_detector.py` (new) — HMM regime detection
- E-4: Real benchmark fetch in `benchmark_module.py` (FMP ASX 200 TR + S&P 500 TR)
- E-5: `services/currency_attribution_engine.py` (new)

**Sub-cluster F2 (Intelligence):** E-6, E-7, E-8, E-9, E-10
- E-6: `portfolio_carbon_intensity_score()` in `esg_service.py`
- E-7: `services/report_html_service.py` (new) — interactive HTML report
- E-8: Multi-provider LLM fallback in `base_agent.py` — **COORDINATE WITH CLUSTER E** (both touch `base_agent.py`)
- E-9: `cross_run_trend_alerts()` in `research_memory.py`
- E-10: `services/sentiment_nlp_service.py` (new) — FinBERT

**⚠️ Coordination required:** E-8 modifies `base_agent.py`. Cluster E (EXP-11) also modifies all agent files but does NOT modify `base_agent.py` directly. These can proceed in parallel but the `base_agent.py` change from E-8 must be merged before EXP-11 is applied to individual agent files to ensure the fallback chain is available.

---

### CLUSTER G — Daily Rhythm Layer (Session 23)
**Session:** 23 | **Agent count:** 2 (backend + frontend) | **Tests:** `tests/test_session23.py` (50+ tests)

**Scope:** The operational cadence layer — calendar, coverage book, portfolio blotter, standup brief, news wire, track record, scenario sandbox, compliance board. Mostly new files.

**All tasks:** RHY-1 through RHY-8 + RHY-SN + RHY-TEST

**New backend files:**
```
src/research_pipeline/schemas/calendar.py
src/research_pipeline/schemas/coverage.py
src/research_pipeline/schemas/standup.py
src/research_pipeline/schemas/news_wire.py
src/research_pipeline/schemas/track_record.py
src/research_pipeline/schemas/scenario.py
src/research_pipeline/schemas/compliance.py
src/research_pipeline/services/research_calendar_service.py
src/research_pipeline/services/coverage_book_service.py
src/research_pipeline/services/portfolio_blotter_service.py
src/research_pipeline/services/standup_brief_service.py
src/research_pipeline/services/news_wire_service.py
src/research_pipeline/services/track_record_service.py
src/research_pipeline/services/scenario_runner.py
src/research_pipeline/services/compliance_board_service.py
src/api/routes/standup.py
src/api/routes/scenario.py
```

**Note:** `ScenarioRunner` calls Stages 8, 9, 12 of `engine.py` directly. It depends on the engine's `run_stage(n)` interface — if BCH-5 (engine decomposition, Cluster H) has been merged before this, the `ScenarioRunner` must use the new decomposed interface.

**New frontend files:**
```
frontend/src/components/calendar/research-calendar-panel.tsx
frontend/src/components/coverage/coverage-table.tsx
frontend/src/components/portfolio/blotter-table.tsx
frontend/src/components/standup/standup-brief-panel.tsx
frontend/src/components/news-wire/news-wire-panel.tsx
frontend/src/components/track-record/track-record-table.tsx
frontend/src/components/scenario/scenario-sandbox.tsx
frontend/src/components/layout/top-bar.tsx (extend)
frontend/src/app/calendar/page.tsx
frontend/src/app/coverage/page.tsx
frontend/src/app/portfolio/page.tsx
frontend/src/app/track-record/page.tsx
frontend/src/app/scenario/page.tsx
frontend/src/app/compliance/page.tsx
frontend/src/components/layout/sidebar.tsx (update nav)
```

---

### CLUSTER H — Institutional Depth Layer (Session 24)
**Session:** 24 | **Agent count:** 3 (data services + frontend A + frontend B) | **Tests:** `tests/test_session24.py` (60+ tests)

**Scope:** The full institutional surface — market monitor, client reports, stock workbench, risk dashboard, earnings season, watchlist, macro regime, knowledge library, street vs house, stress tests.

**All tasks:** INS-1 through INS-10 + INS-TEST

**New backend files:**
```
src/research_pipeline/schemas/market_monitor.py
src/research_pipeline/schemas/client_report.py
src/research_pipeline/schemas/risk_dashboard.py
src/research_pipeline/schemas/earnings_season.py
src/research_pipeline/schemas/watchlist.py
src/research_pipeline/schemas/macro_regime.py
src/research_pipeline/schemas/street_vs_house.py
src/research_pipeline/schemas/stress_test.py
src/research_pipeline/services/market_monitor_service.py
src/research_pipeline/services/client_reporting_service.py
src/research_pipeline/services/risk_dashboard_service.py
src/research_pipeline/services/earnings_season_service.py
src/research_pipeline/services/watchlist_service.py
src/research_pipeline/services/macro_regime_service.py
src/research_pipeline/services/knowledge_library_service.py
src/research_pipeline/services/consensus_comparison_service.py
src/research_pipeline/services/stress_test_runner.py
src/api/routes/market_monitor.py
src/api/routes/library.py
```

**New frontend files:** (all new pages under `frontend/src/app/` — no existing page modifications)
```
frontend/src/app/market/page.tsx
frontend/src/app/reports/page.tsx
frontend/src/app/workbench/[ticker]/page.tsx
frontend/src/app/risk/page.tsx
frontend/src/app/earnings-season/page.tsx
frontend/src/app/watchlist/page.tsx
frontend/src/app/macro-regime/page.tsx
frontend/src/app/library/page.tsx
frontend/src/app/street-vs-house/page.tsx
frontend/src/app/stress-test/page.tsx
+ corresponding components/ directories
```

---

### CLUSTER I — Engine Decomposition (BCH-5 — LAST)
**Session:** After all others | **Agent count:** 1 | **Tests:** all existing tests must still pass

**Scope:** Restructure `pipeline/engine.py` into a `BaseStageExecutor` pattern with each stage in its own file. This is a pure refactor — zero behaviour changes.

**New files:**
```
src/research_pipeline/pipeline/stages/__init__.py
src/research_pipeline/pipeline/stages/stage_01_orchestration.py
src/research_pipeline/pipeline/stages/stage_02_data_ingestion.py
... (15 stage files)
src/research_pipeline/pipeline/stages/base_executor.py
src/research_pipeline/pipeline/stages/stage_context.py
src/research_pipeline/pipeline/stages/stage_result.py
```

> ⚠️ **This MUST be built last.** All other clusters that modify `engine.py` must be merged and tested before Cluster I begins. The decomposition requires a complete, stable `engine.py` as its source.

---

## 4. Interface Contracts Between Clusters

### 4.1 Engine Stage Output Keys (Shared State)
All clusters that wire new data into `engine.py` must write to agreed `stage_outputs` dict keys:

| Key | Producer Cluster | Consumer Stages |
|---|---|---|
| `"qualitative"` | A (DSQ-1) | Stage 5, 8, 10 |
| `"sec_filings"` | A (DSQ-4) | Stage 5 |
| `"benzinga_signals"` | A (DSQ-8) | Stage 10 |
| `"news_articles"` | A (DSQ-11) | Stage 8 |
| `"eia_data"` | D (DSQ-22) | Stage 8 |
| `"asx_announcements"` | D (DSQ-24) | Stages 2, 5 |
| `"parsed_transcripts"` | D (DSQ-26) | Stage 5 |
| `"regulatory_events"` | D (DSQ-27) | Stage 8 |
| `"bond_market_packet"` | C (MAC-14) | Stage 8 |
| `"stage_narrative"` | E (EXP-1) | SSE event stream |
| `"run_narrative"` | E (EXP-4) | Saved per run |

### 4.2 Schema Ownership (Who Creates, Who Extends)
| Schema File | Owner Cluster | Extensions Allowed By |
|---|---|---|
| `schemas/qualitative.py` | A (Session 19) | D (Session 20) — append only |
| `schemas/macro.py` | B (BCH-7) | C (MAC-14), D (DSQ-27) — append only |
| `schemas/portfolio.py` | B (BCH-1/2/3) | No other cluster |
| `schemas/governance.py` | A (DSQ-14) | B (BCH quick wins) — coordinate |
| `schemas/events.py` | E (EXP-1/2) | No other cluster |
| `schemas/fixed_income.py` | C (MAC-3) | No other cluster |
| `schemas/mandate.py` | C (MAC-12) | No other cluster |
| `schemas/personas.py` | E (EXP-2) | No other cluster |
| `schemas/morning_brief.py` | E (EXP-3) | G (RHY-4 standup — read only) |
| `schemas/run_narrative.py` | E (EXP-4) | No other cluster |
| All RHY schemas | G | No other cluster |
| All INS schemas | H | No other cluster |

### 4.3 Shared Mutable Files — Edit Protocol

The following files are edited by multiple clusters. Each cluster's changes must be **additive (append-only)** — no modification of existing methods:

| File | Clusters That Touch It | Protocol |
|---|---|---|
| `engine.py` | A, B, C, D, E, G, I | One agent owns per session; changes are `if`/`elif` additions and new method calls only. Cluster I (decomposition) runs last. |
| `base_agent.py` | E (EXP-11 narrative), F2 (E-8 LLM fallback) | F2 merges first; E then adds `emit_narrative()` call pattern |
| `schemas/qualitative.py` | A, D | A defines Session 19 models first. D appends Session 20 models after merge. |
| `schemas/macro.py` | B, C, D | B (BCH-7) adds `PoliticalContextPacket`. C (MAC-14) adds `BondMarketPacket` reference. D (DSQ-27) adds `RegulatoryEvent*`. All append-only |
| `frontend/src/components/layout/sidebar.tsx` | E (EXP-9), G (RHY-SN), H (final nav) | G defines canonical 14-item nav. H extends to 26-item nav with sections. |
| `frontend/src/app/page.tsx` (dashboard) | E (MorningBriefPanel), G (StandupBriefPanel) | E adds MorningBriefPanel first. G adds StandupBrief below it. |

---

## 5. Sequencing & Dependency Rules

### 5.1 Hard Dependencies (must happen in order)

```
DSQ-1 (wire QualitativeDataService)     — FIRST ACTION, no dependencies
          ↓
DSQ-2–16 (Session 19 completion)        — after DSQ-1 merged
          ↓
DSQ-17–32 (Session 20) = Cluster D      — can start in parallel with Sessions 21/22
MAC-1–15  (Session 21) = Cluster C      — fully independent, can run in parallel
EXP-1–12  (Session 22) = Cluster E      — backend independent; frontend after E-8 base_agent merged
          ↓
RHY-1–8   (Session 23) = Cluster G      — ScenarioRunner requires stable engine.py
INS-1–10  (Session 24) = Cluster H      — StressTestRunner requires Cluster C (AssetClassRouter)
          ↓
BCH-5     (Session ?) = Cluster I       — ABSOLUTE LAST: engine decomposition
```

### 5.2 Parallel-Safe Groups
These clusters can be built at the same time without conflict:

| Parallel Group | Clusters | Reason |
|---|---|---|
| Group 1 | A + B (sub-cluster B1) | A touches engine.py Stages 2/5/8/10; B1 touches schemas and gates only |
| Group 2 | C + D | C is all new files; D is all new files |
| Group 3 | E (backend) + F (sub-cluster F1) | E is new schemas/services; F1 is isolated quant service extensions |
| Group 4 | E (frontend) + G (frontend) | Different page/component files; sidebar coordinated by G |
| Group 5 | H frontend pages | All new pages — zero shared files |

### 5.3 Critical Ordering for `schemas/qualitative.py`

1. Cluster A agent writes Session 19 models: `FilingMetadata`, `MaterialEvent`, `InsiderTransaction`, `FilingSection`, `AnalystRatingChange`, `AdverseSignal`
2. **MERGE and test** Cluster A
3. Cluster D agent appends Session 20 models: `ASXAnnouncement`, `ParsedTranscript`, `GuidanceStatement`, `ManagementToneSignal`, `GuidanceRevisionDelta`, `SemiconductorShipmentSnapshot`, `HyperscalerCapexData`

---

## 6. Session-by-Session Roadmap

| Session | Cluster | Primary Deliverables | Test File | Pass Target |
|---|---|---|---|---|
| **19** | A | DSQ-1–16 complete; QualitativeDataService wired; SEC + Benzinga + NewsAPI wired | `test_session19.py` | 40+ tests |
| **20** | D | DSQ-17–32 complete; 8 new specialist data services | `test_session20.py` | 50+ tests |
| **21** | C | MAC-1–15; 4 new agents; fixed income + REIT + infra schemas | `test_session21.py` | 50+ tests |
| **22** | E | EXP-1–12; personas, morning brief, run narrative, research floor frontend | `test_session22.py` | 40+ tests |
| **23** | G | RHY-1–8; coverage book, calendar, blotter, news wire, track record, compliance | `test_session23.py` | 50+ tests |
| **24** | H | INS-1–10; market monitor, client reports, workbench, risk dashboard, stress tests | `test_session24.py` | 60+ tests |
| **25** | B | BCH-1–10, BCH-QW-1–10; contract hardening; schema versioning | existing test files | all pass |
| **26** | F | E-1–10 gap closers; Black-Litterman, GARCH VaR, HMM, LLM fallback | existing test files | all pass |
| **27** | I | Engine decomposition; BCH-5 refactor | ALL existing tests | all still pass |

> **Sessions 20–26 can be partially parallelised** — see Section 5.2 for safe parallel groups.

---

## 7. Shared File Edit Registry

Files that are touched by **more than one cluster** — the single most likely source of merge conflicts.

| File | Cluster A | Cluster B | Cluster C | Cluster D | Cluster E | Cluster F | Cluster G | Cluster H | Cluster I |
|---|---|---|---|---|---|---|---|---|---|
| `engine.py` | ✅ Stages 2/5/8/10 | ✅ repair loop; BCH-9/10 | ✅ asset routing | ✅ EIA/ASX/transcripts | ✅ narrative emit | — | ✅ ScenarioRunner calls | — | ✅ REFACTOR |
| `base_agent.py` | — | — | — | — | ✅ narrative emit | ✅ LLM fallback | — | — | — |
| `schemas/qualitative.py` | ✅ S19 models | — | — | ✅ S20 models (after A) | — | — | — | — | — |
| `schemas/macro.py` | — | ✅ PoliticalContextPacket | ✅ BondMarketPacket ref | ✅ RegulatoryEvent* | — | — | — | ✅ MacroRegimePacket | — |
| `schemas/portfolio.py` | — | ✅ BCH-1/2/3 | — | — | — | — | — | — | — |
| `schemas/governance.py` | ✅ synthetic_data_fields | ✅ QW items | — | — | — | — | — | — | — |
| `schemas/events.py` | — | — | — | — | ✅ StageNarrative | — | — | — | — |
| `schemas/mandate.py` | — | — | ✅ MAC-12 | — | — | — | — | — | — |
| `gates.py` | — | ✅ BCH-1/3 | — | — | — | — | — | — | — |
| `api/routes/runs.py` | — | ✅ BCH-10 /partial | — | — | — | — | — | — | — |
| `frontend/.../sidebar.tsx` | — | — | — | — | ✅ add team | — | ✅ 14 nav items | ✅ 26 nav items | — |
| `frontend/.../page.tsx` (dashboard) | — | — | — | — | ✅ MorningBrief | — | ✅ StandupBrief | — | — |
| `src/frontend/app.py` | — | — | — | — | ✅ EXP-10 | — | — | — | — |

---

## 8. Acceptance Criteria Summary

### Session 19 Gate (Cluster A)
- [ ] `QualitativeDataService` called in Stage 5 of `run_full_pipeline()`
- [ ] At least one `FilingSection` returned for a US ticker in Stage 5 output
- [ ] At least one `AnalystRatingChange` returned for a covered ticker
- [ ] `SelfAuditPacket.synthetic_data_fields` populated on synthetic runs
- [ ] All test_session19.py tests pass

### Session 20 Gate (Cluster D)
- [ ] `DataFreshnessCatalog.check_freshness()` returns staleness status per field
- [ ] `RateLimitBudgetManager` tracks quota across at minimum 3 APIs
- [ ] `ASXAnnouncementService.fetch()` returns announcements for an AU ticker
- [ ] All test_session20.py tests pass

### Session 21 Gate (Cluster C)
- [ ] `AssetClassRouter` correctly classifies NVDA=equity, BND=fixed_income, VNQ=REIT
- [ ] `FixedIncomeAnalystAgent` produces a `BondAnalysisCard` without LLM error
- [ ] `MultiAssetPortfolioOptimiser` runs without error on blended universe
- [ ] All test_session21.py tests pass

### Session 22 Gate (Cluster E)
- [ ] `StageNarrative` emitted by ≥8 stages in a live run; all contain ticker-specific content
- [ ] `AGENT_PERSONAS` registry complete for all 15 stages
- [ ] `MorningBriefPacket` returned from `/api/morning-brief` with yield curve + regime flags
- [ ] `RunNarrative` written to `run_narrative.json` for every completed run
- [ ] `ResearchFloorPanel` renders live during a run with persona cards
- [ ] "How This Was Made" tab present on run detail page
- [ ] All test_session22.py tests pass

### Session 23 Gate (Cluster G)
- [ ] `CoverageBookService` auto-updates on IC-approved run completion
- [ ] `ResearchCalendarService` returns FOMC + RBA dates for 90 days
- [ ] `TrackRecordService` logs recommendation for every IC-approved run
- [ ] Compliance badge visible in top bar; reflects open breaches
- [ ] All test_session23.py tests pass

### Session 24 Gate (Cluster H)
- [ ] `MarketMonitorPacket` populated with ≥12 tiles from FRED + FMP
- [ ] `FundFactSheet` PDF generated from completed run without error
- [ ] `/workbench/NVDA` renders all 6 panels with real data
- [ ] `StressTestRunner` produces estimates for all 10 standard scenarios
- [ ] All test_session24.py tests pass

### Full Platform Gate (after all clusters)
- [ ] All tests from Sessions 1–24 pass (target: 1004 + ~330 new = ~1334 tests)
- [ ] `engine.py` decomposition (Cluster I) completes with all pre-existing tests passing
- [ ] Full run from Morning Brief → IC Decision → Published Report navigable end-to-end in Next.js frontend
- [ ] Compliance badge status correctly reflects live gate outcomes

---

## Appendix A — New File Count by Cluster

| Cluster | New Backend Files | New Frontend Files | New Test Files | Total |
|---|---|---|---|---|
| A (Session 19) | 2 services | — | 1 | 3 |
| B (Part L) | 2 services, 1 schema | — | — | 3 |
| C (Session 21) | 6 services, 4 agents, 1 schema | — | 1 | 12 |
| D (Session 20) | 10 services | — | 1 | 11 |
| E (Session 22) | 2 services, 3 schemas | 7 components/pages | 1 | 13 |
| F (E-items) | 4 services (new) | — | — | 4 |
| G (Session 23) | 8 services, 7 schemas, 3 API routes | 13 components/pages | 1 | 32 |
| H (Session 24) | 9 services, 8 schemas, 2 API routes | 15+ components/pages | 1 | 35+ |
| I (BCH-5) | 18 stage files + 3 base files | — | — | 21 |
| **Total** | **~62** | **~35** | **7** | **~134 new files** |

---

## Appendix B — Required New Python Dependencies

| Library | Used By | Cluster |
|---|---|---|
| `arch` | GARCH VaR (E-2) | F1 |
| `hmmlearn` | HMM regime detection (E-3) | F1 |
| `transformers` + `torch` | FinBERT sentiment (E-10) | F2 |
| `newspaper3k` or `trafilatura` | Article extraction (DSQ-9) | A |
| `fpdf2` | Already present — client reports (INS-2) | H |
| `requests-cache` | Rate limit manager (DSQ-18) | D |

All dependencies must be added to `requirements.txt` and `pyproject.toml`.

---

*Document created from full analysis of IMPROVEMENTS.md (5109 lines), TRACKER.md (804 lines), ARCHITECTURE.md (1472 lines), and live `list_dir` of `src/research_pipeline/services/` and `src/research_pipeline/agents/`.*
*Sessions 1–18 baseline: 1004 tests passing · commit f021327*
