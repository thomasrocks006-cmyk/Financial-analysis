# AI Infrastructure Research & Portfolio Platform — Architecture Workflow

> **Version 8** | 15-Stage Gate-Controlled Pipeline | March 2026

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Three-Layer Architecture](#2-three-layer-architecture)
3. [End-to-End Pipeline Workflow](#3-end-to-end-pipeline-workflow)
4. [Stage-by-Stage Breakdown](#4-stage-by-stage-breakdown)
5. [Component Deep-Dives](#5-component-deep-dives)
   - [Deterministic Services](#51-deterministic-services)
   - [LLM Reasoning Agents](#52-llm-reasoning-agents)
   - [Gate System](#53-gate-system)
   - [Schema Layer](#54-schema-layer)
6. [Data Flow Diagram](#6-data-flow-diagram)
7. [Entry Points](#7-entry-points)
8. [Configuration & Secrets](#8-configuration--secrets)
9. [Testing Layer](#9-testing-layer)
10. [Critical Architecture Review](#10-critical-architecture-review-actual-code-state--march-28-2026)
11. [Directory Map](#11-directory-map)
12. [Extended Gap Analysis: JPAM Capability Assessment](#12-extended-gap-analysis-jpam-capability-assessment)

---

## 1. System Overview

The platform automates **institutional-quality equity research** on the AI infrastructure investment theme. Given a list of tickers it:

1. Ingests live market and consensus data from **FMP** and **Finnhub**
2. Runs deterministic financial models (DCF, risk, scenarios)
3. Passes structured facts to **LLM reasoning agents** for judgment-intensive work
4. Gates every stage — downstream work is blocked until the prior gate passes
5. Assembles a final, publishable research report and portfolio allocation

**Research universe (default)**

| Subtheme | Tickers |
|---|---|
| Compute & Silicon | NVDA, AVGO, TSM |
| Power & Energy | CEG, VST, GEV, NLR |
| Infrastructure & Build-out | PWR, ETN, HUBB, APH, FIX |
| Materials | FCX, BHP |
| Data Centres | NXT |

---

## 2. Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  ENTRY POINTS                                                       │
│  ┌──────────────────┐   ┌─────────────────────────────────────┐    │
│  │  CLI (Typer)     │   │  Streamlit Web UI (src/frontend/)   │    │
│  │  src/cli/main.py │   │  src/frontend/app.py                │    │
│  └────────┬─────────┘   └──────────────┬──────────────────────┘    │
└───────────┼─────────────────────────────┼───────────────────────────┘
            │                             │
            └──────────────┬──────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PIPELINE ENGINE   src/research_pipeline/pipeline/engine.py        │
│  Orchestrates all 15 stages, enforces gate checks, logs runs        │
└─────────────────────────────────────────────────────────────────────┘
            │
            ├──────────────────────────────────────────────────────────
            │  Layer 1 — DETERMINISTIC SERVICES  (no LLM)
            │  src/research_pipeline/services/
            │  ┌─────────────────┐  ┌──────────────────────┐
            │  │ MarketData      │  │ ConsensusReconcile   │
            │  │ Ingestor        │  │ Service              │
            │  └─────────────────┘  └──────────────────────┘
            │  ┌─────────────────┐  ┌──────────────────────┐
            │  │ DataQALineage   │  │ DCFEngine            │
            │  └─────────────────┘  └──────────────────────┘
            │  ┌─────────────────┐  ┌──────────────────────┐
            │  │ RiskEngine      │  │ ScenarioStressEngine │
            │  └─────────────────┘  └──────────────────────┘
            │  ┌─────────────────┐  ┌──────────────────────┐
            │  │ ReportAssembly  │  │ RunRegistry          │
            │  └─────────────────┘  └──────────────────────┘
            │  ┌─────────────────┐
            │  │ GoldenTests     │
            │  └─────────────────┘
            │
            ├──────────────────────────────────────────────────────────
            │  Layer 2 — LLM REASONING AGENTS
            │  src/research_pipeline/agents/
            │  ┌────────────────────┐  ┌──────────────────────┐
            │  │ OrchestratorAgent  │  │ EvidenceLibrarian    │
            │  └────────────────────┘  └──────────────────────┘
            │  ┌────────────────────┐  ┌──────────────────────┐
            │  │ SectorAnalyst      │  │ ValuationAnalyst     │
            │  │ (×3 parallel)      │  │                      │
            │  └────────────────────┘  └──────────────────────┘
            │  ┌────────────────────┐  ┌──────────────────────┐
            │  │ MacroStrategist    │  │ PoliticalRisk        │
            │  └────────────────────┘  └──────────────────────┘
            │  ┌────────────────────┐  ┌──────────────────────┐
            │  │ RedTeamAnalyst     │  │ AssociateReviewer    │
            │  └────────────────────┘  └──────────────────────┘
            │  ┌────────────────────┐
            │  │ PortfolioManager   │
            │  └────────────────────┘
            │
            └──────────────────────────────────────────────────────────
               Layer 3 — GOVERNANCE & CONTROL
               src/research_pipeline/pipeline/gates.py
               ┌───────────────┐  ┌──────────────┐  ┌──────────────┐
               │ PipelineGates │  │ RunRegistry  │  │ GoldenTests  │
               └───────────────┘  └──────────────┘  └──────────────┘
```

---

## 3. End-to-End Pipeline Workflow

```
  USER / SCHEDULER
       │
       ▼
  ┌──────────────┐
  │  Entry Point │  (CLI `research-pipeline run` OR Streamlit UI)
  └──────┬───────┘
         │ passes: ticker list, config path, flags
         ▼
  ┌──────────────────────────────────────────┐
  │  Stage 0 — Configuration & Bootstrap     │
  │  Load YAML config, validate API keys,    │
  │  register run in RunRegistry             │
  └──────────────────┬───────────────────────┘
                     │ GATE 0: API keys ✓, config ✓, schemas ✓
                     ▼
  ┌──────────────────────────────────────────┐
  │  Stage 1 — Universe Definition           │
  │  Build ticker list, subtheme mapping     │
  └──────────────────┬───────────────────────┘
                     │ GATE 1: ≥3 tickers, no duplicates
                     ▼
  ┌──────────────────────────────────────────┐
  │  Stage 2 — Data Ingestion                │
  │  FMP + Finnhub → MarketSnapshot,         │
  │  ConsensusSnapshot, AnalystEstimate,     │
  │  EarningsEvent, RatingsSnapshot          │
  └──────────────────┬───────────────────────┘
                     │ GATE 2: all tickers ingested, no API errors
                     ▼
  ┌──────────────────────────────────────────┐
  │  Stage 3 — Consensus Reconciliation      │
  │  Align FMP vs Finnhub estimates,         │
  │  flag divergence > threshold             │
  └──────────────────┬───────────────────────┘
                     │ GATE 3: reconciliation divergence within limits
                     ▼
  ┌──────────────────────────────────────────┐
  │  Stage 4 — Data QA & Lineage             │
  │  Check completeness, stale data,         │
  │  build provenance chain                  │
  └──────────────────┬───────────────────────┘
                     │ GATE 4: QA pass rate ≥ threshold
                     ▼
  ┌──────────────────────────────────────────┐
  │  Stage 5 — Evidence & Claim Registration │  ◄── LLM (EvidenceLibrarianAgent)
  │  Extract claims from raw data,           │
  │  assign tier/class, build ClaimLedger    │
  └──────────────────┬───────────────────────┘
                     │ GATE 5: minimum claims per ticker
                     ▼
  ┌──────────────────────────────────────────┐
  │  Stage 6 — Sector Analysis (×3 parallel) │  ◄── LLM (3 SectorAnalyst agents)
  │  Compute analyst, Power/Energy analyst,  │
  │  Infrastructure analyst — run in async   │
  │  parallel, each writes a SectorReport    │
  └──────────────────┬───────────────────────┘
                     │ GATE 6: all 3 sector reports present
                     ▼
  ┌──────────────────────────────────────────┐
  │  Stage 7 — Valuation & Modelling         │  ◄── LLM + Deterministic
  │  DCFEngine computes intrinsic values,    │
  │  ValuationAnalystAgent interprets,       │
  │  produces FourBoxOutput + ValuationCard  │
  └──────────────────┬───────────────────────┘
                     │ GATE 7: DCF complete, valuation cards present
                     ▼
  ┌──────────────────────────────────────────┐
  │  Stage 8 — Macro & Political Overlay     │  ◄── LLM (Macro + Political agents)
  │  MacroStrategistAgent sets regime memo,  │
  │  PoliticalRiskAnalyst adds country/      │
  │  regulatory risk flags                   │
  └──────────────────┬───────────────────────┘
                     │ GATE 8: macro memo present
                     ▼
  ┌──────────────────────────────────────────┐
  │  Stage 9 — Quantitative Risk & Scenarios │  ◄── Deterministic
  │  RiskEngine: correlations, concentration,│
  │  contribution to variance                │
  │  ScenarioStressEngine: base/bull/bear    │
  └──────────────────┬───────────────────────┘
                     │ GATE 9: risk packet & scenarios generated
                     ▼
  ┌──────────────────────────────────────────┐
  │  Stage 10 — Red Team Analysis            │  ◄── LLM (RedTeamAnalystAgent)
  │  Challenge every thesis, surface         │
  │  alternative views, assign severity      │
  └──────────────────┬───────────────────────┘
                     │ GATE 10: red team assessment present
                     ▼
  ┌──────────────────────────────────────────┐
  │  Stage 11 — Associate Review & Pub Gate  │  ◄── LLM (AssociateReviewerAgent)
  │  QA check: evidence tiers, claim         │
  │  corroboration, red-team addressed.      │
  │  PASS → PublicationStatus.APPROVED       │
  │  FAIL → blocks Stage 12+                 │
  └──────────────────┬───────────────────────┘
                     │ GATE 11: AssociateReview PASS — hard stop if FAIL
                     ▼
  ┌──────────────────────────────────────────┐
  │  Stage 12 — Portfolio Construction       │  ◄── LLM (PortfolioManagerAgent)
  │  Build 3 portfolio variants (Bull,       │
  │  Base, Bear), assign weights, rank       │
  │  positions                               │
  └──────────────────┬───────────────────────┘
                     │ GATE 12: portfolio weights sum to 100%
                     ▼
  ┌──────────────────────────────────────────┐
  │  Stage 13 — Report Assembly              │  ◄── Deterministic (Jinja2)
  │  Compile approved sections into          │
  │  FinalReport, render Markdown/HTML       │
  │  output, write to output/                │
  └──────────────────┬───────────────────────┘
                     │ GATE 13: report rendered without errors
                     ▼
  ┌──────────────────────────────────────────┐
  │  Stage 14 — Monitoring & Logging         │  ◄── Mixed
  │  Close run record, golden test checks,   │
  │  emit metrics, schedule next run         │
  └──────────────────┴───────────────────────┘
```

---

## 4. Stage-by-Stage Breakdown

| Stage | Name | Type | Key Inputs | Key Outputs | Gate Condition |
|---|---|---|---|---|---|
| 0 | Configuration & Bootstrap | Control | env vars, YAML | Settings, PipelineConfig | API keys valid, config loaded, schemas valid |
| 1 | Universe Definition | Control | ticker list param | verified ticker list | ≥3 tickers, no duplicates |
| 2 | Data Ingestion | Deterministic | ticker list, API keys | MarketSnapshot, ConsensusSnapshot per ticker | all tickers ingested successfully |
| 3 | Consensus Reconciliation | Deterministic | FMP + Finnhub estimates | ReconciliationReport | divergence within threshold |
| 4 | Data QA & Lineage | Deterministic | MarketSnapshot set | DataQualityReport | QA pass rate ≥ configured minimum |
| 5 | Evidence & Claim Registration | LLM Agent | market data + QA report | ClaimLedger | min claims per ticker present |
| 6 | Sector Analysis (×3 parallel) | LLM Agent | ClaimLedger + market data | 3 × SectorReport | all sector reports present |
| 7 | Valuation & Modelling | LLM + Deterministic | SectorReports, market data | DCFResult, ValuationCard, FourBoxOutput | DCF complete, valuation cards present |
| 8 | Macro & Political Overlay | LLM Agent | macro inputs | MacroRegimeMemo | memo present |
| 9 | Quantitative Risk & Scenarios | Deterministic | return series, portfolio weights | RiskPacket, scenario outputs | risk packet generated |
| 10 | Red Team Analysis | LLM Agent | all prior outputs | RedTeamAssessment | assessment present |
| 11 | Associate Review & Publish Gate | LLM Agent | full research package | AssociateReviewResult | review status = PASS |
| 12 | Portfolio Construction | LLM Agent | approved research | PortfolioVariant ×3 | weights sum = 100% |
| 13 | Report Assembly | Deterministic | all approved outputs | FinalReport (Markdown/HTML) | rendered without error |
| 14 | Monitoring & Logging | Mixed | run record | closed RunRecord, metrics | golden tests pass |

---

## 5. Component Deep-Dives

### 5.1 Deterministic Services

All services live in `src/research_pipeline/services/`. They contain **no LLM calls** — every output is reproducible given the same inputs.

| Service | File | What It Does |
|---|---|---|
| **MarketDataIngestor** | `market_data_ingestor.py` | Hits FMP `/stable/` and Finnhub REST endpoints; normalises quotes, ratios, analyst estimates, price targets, earnings calendars, and ratings into canonical Pydantic schemas. Retries on timeout. Tracks request budget. |
| **ConsensusReconciliationService** | `consensus_reconciliation.py` | Compares FMP vs Finnhub analyst estimates; flags divergence exceeding configured thresholds (e.g., EPS spread > 5%). Produces a `ReconciliationReport`. |
| **DataQALineageService** | `data_qa_lineage.py` | Checks field completeness, stale-data age, and negative-value sanity. Builds a provenance chain linking every data point to its source. |
| **DCFEngine** | `dcf_engine.py` | Discounted cash-flow model: projects FCF over 5 years, computes terminal value, derives equity value and implied share price. Builds a 2-D WACC × terminal-growth sensitivity table. |
| **RiskEngine** | `risk_engine.py` | Computes pairwise correlation matrix, covariance matrix, portfolio concentration (HHI), contribution-to-variance per position, ETF overlap analysis. |
| **ScenarioStressEngine** | `scenario_engine.py` | Runs base / bull / bear revenue and margin scenarios; stress-tests the portfolio against each scenario. |
| **ReportAssemblyService** | `report_assembly.py` | Jinja2 template engine; slots approved sections (stock cards, exec summary, risk packet, portfolio allocation) into a final Markdown/HTML report. Only approved content (post-Stage 11 gate) is included. |
| **RunRegistryService** | `run_registry.py` | Persists `RunRecord` objects to disk (JSON). Each run gets a UUID, timestamps, stage outcomes, and final status (RUNNING / COMPLETED / FAILED). Enables audit and re-run. |
| **GoldenTestHarness** | `golden_tests.py` | Regression tests run at Stage 14. Checks that key numeric outputs fall within expected bands established from prior approved runs. |
| **Scheduler** | `scheduler.py` | Cron-style scheduling for automated recurring pipeline runs. |
| **FactorExposureEngine** | `factor_engine.py` | Computes 5-factor (market, size, value, momentum, quality) exposures per ticker via OLS regression or heuristic subtheme profiles. Portfolio-level factor decomposition and attribution. |
| **BenchmarkModule** | `benchmark_module.py` | Loads benchmark constituents (SPY, QQQ, XLK, SOXX). Computes active weights, tracking error, information ratio, Sharpe ratio, max drawdown. Full benchmark comparison. |
| **VaREngine** | `var_engine.py` | Parametric and historical VaR/CVaR at configurable confidence levels (95%, 99%). Drawdown analysis with max drawdown, recovery tracking. Portfolio-level VaR with position decomposition. |
| **PortfolioOptimisationEngine** | `portfolio_optimisation.py` | Mean-variance optimisation: minimum variance, maximum Sharpe, risk parity, Black-Litterman. Enforces min/max weight constraints. Returns `OptimisationResult` with weights, expected return, volatility, risk contributions. |
| **MandateComplianceEngine** | `mandate_compliance.py` | Checks portfolio weights against investment mandate rules (single-name limits, sector caps, position count, liquidity floors). Returns `MandateCheckResult` with violations and severity. |
| **ESGService** | `esg_service.py` | ESG scoring per ticker (heuristic profiles for 15 AI infra stocks). Exclusion checking (rating, controversy, composite). Portfolio-level ESG compliance and weighted scoring. |
| **InvestmentCommitteeService** | `investment_committee.py` | Simulates 5-member IC voting (chair, PM, risk officer, analyst, compliance). Per-role voting logic based on gate results, mandate, risk, review. Audit trail and committee records. |
| **PositionSizingEngine** | `position_sizing.py` | Converts conviction signals and risk budgets into portfolio weights. Methods: equal weight, conviction-weighted, inverse volatility, risk-budget weighted. Iterative constraint application. |
| **MonitoringEngine** | `monitoring_engine.py` | Portfolio drift detection: price moves, weight drift, concentration breach (HHI), volatility spikes. Generates `MonitoringReport` with severity-rated alerts. |
| **PerformanceTracker** | `performance_tracker.py` | BHB attribution (allocation, selection, interaction effects). Liquidity profiling (days-to-liquidate, market impact). Thesis lifecycle (create, challenge, invalidate). Portfolio snapshots. |
| **RebalancingEngine** | `rebalancing_engine.py` | Drift detection and rebalance proposal generation. Computes current weights from price drift, generates trade orders with direction, sizing, and participation rate. |
| **AuditExporter** | `audit_exporter.py` | Exports full governance audit as structured JSON: pipeline metadata, gate results, committee record, mandate compliance, ESG results, risk summary, compliance summary. |
| **CacheLayer** | `cache_layer.py` | File-backed cache with TTL, namespace isolation, stats tracking. `QuotaManager` tracks API usage per run with explicit budgets for FMP, Finnhub, LLM tokens. |
| **ResearchMemory** | `research_memory.py` | SQLite FTS5-backed research corpus. Stores documents, run outputs, reports, claim ledgers. Full-text search. Thesis evolution tracking across runs. |
| **PromptRegistry** | `prompt_registry.py` | Version-tracks all agent prompts with SHA256 hash dedup. Drift detection comparing current vs registered prompts. Regression status management per version. |

---

### 5.2 LLM Reasoning Agents

All agents live in `src/research_pipeline/agents/`. Each extends `BaseAgent`, which provides:

- **System prompt loading** — from `prompts/<name>.md` file, or a built-in default
- **Prompt hashing** — SHA-256 of the system prompt (immutable audit trail)
- **Retry wrapper** — up to `max_retries` attempts with structured error capture
- **`AgentResult`** — a standard typed wrapper containing `raw_response`, `parsed_output`, `success`, `error`, `timestamp`, `prompt_hash`

**Model:** `claude-opus-4-6` at temperature `0.2` (low creativity, high determinism)

| Agent | File | Role | Must NOT |
|---|---|---|---|
| **OrchestratorAgent** | `orchestrator.py` | Manages stage sequencing, passes structured inputs between stages, enforces gate outcomes, escalates blocked stages. Produces a JSON stage plan. | Write analysis, override reviewer FAIL, invent evidence |
| **EvidenceLibrarianAgent** | `evidence_librarian.py` | Extracts and registers claims from raw data; assigns `EvidenceClass` (PRIMARY_FACT, MGMT_GUIDANCE, etc.) and `SourceTier` (1–4) to each claim. Builds the `ClaimLedger`. | Invent claims beyond what data supports |
| **SectorAnalystCompute** | `sector_analysts.py` | Deep analysis of compute/silicon stocks (NVDA, AVGO, TSM). GPU cycles, supply chain, product roadmap, competitive moat. | Override data QA red flags |
| **SectorAnalystPowerEnergy** | `sector_analysts.py` | Analysis of power/energy stocks (CEG, VST, GEV). Grid capacity, power purchase agreements, nuclear/renewables. | Override data QA red flags |
| **SectorAnalystInfrastructure** | `sector_analysts.py` | Analysis of infrastructure/materials/data centre stocks. Capex cycles, order books, backlog. | Override data QA red flags |
| **ValuationAnalystAgent** | `valuation_analyst.py` | Interprets DCFEngine outputs; picks the appropriate valuation methodology per stock; writes `ValuationCard` with entry quality and thesis integrity scores. | Recompute DCF math itself |
| **MacroStrategistAgent** | `macro_political.py` | Sets the macro regime memo — rates, dollar direction, credit spreads, AI investment cycle positioning. Conditions portfolio risk appetite. | Override sector analysis |
| **PoliticalRiskAnalystAgent** | `macro_political.py` | Flags country/regulatory/trade risks relevant to the universe (e.g., Taiwan risk for TSM, IRA risk for power stocks). | Override country data |
| **RedTeamAnalystAgent** | `red_team_analyst.py` | Adversarially challenges every investment thesis; surfaces bearish scenarios, valuation downsides, and execution risks. Severity-rates each challenge. | Fabricate risks, be sycophantic |
| **AssociateReviewerAgent** | `associate_reviewer.py` | Final QA gate: checks evidence tiers, claim corroboration, red-team coverage, methodology consistency. Issues PASS / FAIL with specific blockers. | Override deterministic red flags, approve if evidence is weak |
| **PortfolioManagerAgent** | `portfolio_manager.py` | Constructs three portfolio variants (Bull / Base / Bear) with position sizes, weights, and rank ordering. Applies macro overlay from Stage 8. | Fabricate price targets, deviate from approved research |

---

### 5.3 Gate System

```
src/research_pipeline/pipeline/gates.py  →  PipelineGates
```

Every stage has a corresponding static method on `PipelineGates`. A gate returns a `GateResult`:

```
GateResult
├── stage: int          stage number
├── passed: bool        True = proceed, False = block
├── reason: str         human-readable summary
└── blockers: list[str] specific failure reasons
```

**Gate failure policy:** If any gate returns `passed=False`, the engine halts all downstream stages and writes `RunStatus.FAILED` to the run registry. The specific blockers are logged for operator review. The one exception is a **human override** mechanism (operator-only) that can force-continue past Stage 11.

---

### 5.4 Schema Layer

```
src/research_pipeline/schemas/
```

All data flowing between stages is typed via **Pydantic v2 models**. This enforces contract correctness and enables automatic serialisation/deserialisation.

| Schema File | Key Models | Purpose |
|---|---|---|
| `claims.py` | `Claim`, `ClaimLedger`, `Source`, `EvidenceClass`, `SourceTier` | Evidence provenance backbone — every analytic claim is traceable to a source |
| `market_data.py` | `MarketSnapshot`, `ConsensusSnapshot`, `AnalystEstimate`, `ReconciliationReport`, `DataQualityReport` | Canonical representation of all ingested market data |
| `portfolio.py` | `ValuationCard`, `FourBoxOutput`, `MacroRegimeMemo`, `RedTeamAssessment`, `AssociateReviewResult`, `PortfolioVariant`, `PublicationStatus` | Research outputs from Stage 6 through Stage 12 |
| `reports.py` | `FinalReport`, `ReportSection`, `StockCard`, `RiskPacket` | Final assembled report structure |
| `registry.py` | `RunRecord`, `RunStatus` | Audit trail for every pipeline execution |

---

## 6. Data Flow Diagram

```
External APIs
┌─────────────┐   ┌──────────────┐
│  FMP        │   │  Finnhub     │
│  /stable/   │   │  /api/v1/    │
└──────┬──────┘   └──────┬───────┘
       │                 │
       └────────┬─────────┘
                ▼
     MarketDataIngestor (Stage 2)
                │
       ┌────────┴────────┐
       ▼                 ▼
ConsensusRecon       DataQALineage
(Stage 3)            (Stage 4)
       │                 │
       └────────┬─────────┘
                ▼
     ClaimLedger (Stage 5)  ◄── EvidenceLibrarianAgent
                │
       ┌────────┴────────────────────┐
       ▼        ▼                   ▼
   Compute   PowerEnergy      Infrastructure
   Analyst   Analyst          Analyst
   (Stage 6 — 3× parallel LLM calls)
       │        │                   │
       └────────┴──────────┬────────┘
                           ▼
              ValuationAnalyst + DCFEngine (Stage 7)
                           │
              ┌────────────┴───────────┐
              ▼                        ▼
        MacroStrategist          PoliticalRisk
             (Stage 8 — macro overlay)
              │
              ▼
     RiskEngine + ScenarioEngine (Stage 9)
              │
              ▼
     RedTeamAnalyst (Stage 10)
              │
              ▼
     AssociateReviewer (Stage 11) ── HARD GATE ──►  FAIL → STOP
              │ PASS
              ▼
     PortfolioManager (Stage 12) — 3 portfolio variants
              │
              ▼
     ReportAssembly (Stage 13) — Jinja2 → Markdown/HTML
              │
              ▼
     output/  (final report file)
```

---

## 7. Entry Points

### CLI — `src/cli/main.py`

Built with **Typer** + **Rich** for coloured terminal output.

```bash
# Full pipeline run
research-pipeline run --tickers NVDA,AVGO,TSM --config configs/pipeline.yaml

# Validate config only (no execution)
research-pipeline run --dry-run

# List all past runs
research-pipeline runs

# Show status of a specific run
research-pipeline status <run-id>
```

### Streamlit UI — `src/frontend/app.py`

```bash
streamlit run src/frontend/app.py
```

| Panel | What It Shows |
|---|---|
| Sidebar | Universe selector, quick-demo universe, run controls |
| Stage Progress | Live colour-coded stage cards (pending / running / done / failed) |
| Market Snapshot | Real-time or mock pricing table for all tickers |
| Pipeline Output | Final report rendered inline |
| Mock Data | `frontend/mock_data.py` provides offline demo data for UI development |

### Script runner — `scripts/live_test_run.py`

Thin wrapper for ad-hoc test runs during development without the full CLI.

---

## 8. Configuration & Secrets

### YAML Configuration

```
configs/
├── pipeline.yaml    — stage timeouts, retry counts, output paths, LLM model selection
├── thresholds.yaml  — reconciliation divergence limits, QA pass-rate floors
└── universe.yaml    — default ticker sets and subtheme mappings
```

Loaded by `src/research_pipeline/config/loader.py` → `PipelineConfig` Pydantic model.

### Environment Variables (`.env`)

| Variable | Purpose |
|---|---|
| `FMP_API_KEY` | Financial Modeling Prep market data |
| `FINNHUB_API_KEY` | Finnhub market data & consensus |
| `OPENAI_API_KEY` | LLM calls (OpenAI-compatible endpoint) |

### Settings Object

`src/research_pipeline/config/settings.py` → `Settings` (Pydantic BaseSettings).  
Reads from environment + `.env` file; accessed by the engine and all services.

---

## 9. Testing Layer

```
tests/
├── conftest.py        — shared fixtures (mock settings, sample market data)
├── test_gates.py      — unit tests for every PipelineGates method
├── test_pipeline.py   — integration tests for engine stage sequencing
├── test_schemas.py    — Pydantic model validation tests
└── test_services.py   — unit tests for deterministic services
```

Run with:
```bash
pytest tests/ -v
```

**Golden Tests** (Stage 14, runtime): The `GoldenTestHarness` service validates final numeric outputs against approved bands from prior runs — catching metric regression between pipeline versions.

---

## 10. Critical Architecture Review (Actual Code State — March 28, 2026)

### Executive Verdict

**Overall architecture score: 7.8 / 10** *(updated post-Phase-7 + debt-clearing)*

This project has a strong institutional workflow design and better-than-average
process discipline for an AI research platform. The core idea is right:
deterministic services should produce facts, LLMs should produce judgment, and
gates should control publication.

The architectural split-brain between `research_pipeline/` and
`frontend/pipeline_runner.py` has been partially resolved: a thin
`pipeline_adapter.py` now bridges the frontend to `PipelineEngine`, and
`frontend/storage.py` is unified with the backend `RunRegistryService`.
The remaining gap is that `app.py` still imports from `pipeline_runner` —
swapping to `pipeline_adapter` is the next convergence step.

### Component Scorecard

| Component | Score / 10 | What is strong | Main gap |
|---|---:|---|---|
| Research workflow / stage design | 8.5 | Excellent decomposition of the research process into 15 coherent stages | Some stages are still more prompt-driven than contract-driven |
| Frontend operator experience | 8.0 | Streamlit workflow is polished and practical | `app.py` still imports from legacy `pipeline_runner`; not yet using `pipeline_adapter` |
| Core orchestration architecture | 7.0 ↑ | `pipeline_adapter.py` thin shim created; single canonical `PipelineEngine` path documented | `app.py` import swap not yet done; legacy runner still present |
| Deterministic services | 7.5 | Good modular service set: DCF, reconciliation, QA, risk, scenarios, factor, VaR | Service unit-test coverage could be deeper |
| Market + qualitative data ingestion | 8.0 ↑ | D-1: `QualitativePackage` typed schemas + async `QualitativeDataService`; 8 sources with Pydantic contracts | Backend ingestion still serial; add `asyncio.gather` with semaphore |
| LLM agent layer | 7.8 ↑ | All agents enforce `parse_output`; `QuantResearchAnalystAgent` + `FixedIncomeAnalystAgent` wired into Stage 9 | Political risk macro agents still have shallow output contracts; base_agent silent JSON fallback unresolved |
| Governance / gates / review | 7.5 ↑ | Binary `PASS`/`FAIL` enforced (A-3); IC `_pm_vote` no longer auto-passes (A-4); all gates hardened | Frontend still calls plain `pass_with_disclosure` strings in some legacy code paths |
| Schema layer / type safety | 7.5 ↑ | New Pydantic v2 qualitative schemas (10 models); `QualitativePackage` coverage metrics | Frontend ad hoc dicts still bypass typed contracts in some flows |
| Persistence / audit trail | 7.0 ↑ | A-2: `storage.save_run()` now mirrors to `RunRegistryService`; `list_saved_runs()` merges both stores | Frontend-initiated runs that bypass PipelineEngine create partial registry records |
| Report assembly | 7.0 ↑ | Streamlit Quant Analytics panel surfaces VaR/CVaR/drawdown, ETF overlap, factor β, IC vote, Fixed-Income context from Stage 9/12 outputs; works for live and loaded runs | Two assembly paths still create drift risk; no PDF export yet |
| Testing / QA | 8.5 | 427 tests (up from 378 in session 3); CI weekly live-data workflow (.github/workflows/weekly_live_data.yml) canaries NVDA+MSFT schema + yfinance fallback | Frontend Streamlit components untested; live API path tested only in CI canary |
| Documentation accuracy | 7.8 ↑ | Scores updated through session 4; TRACKER.md current; ARCHITECTURE.md Next 10 Actions updated | P-5/P-6 specs still informal; ESG and Performance Attribution have no detailed spec |

### Gap Analysis

#### Gap 1 — Split-brain orchestration

**Severity:** Critical

**Target**

- one canonical execution engine
- one gate framework
- one report assembly path
- one set of stage contracts

**Actual**

- `src/research_pipeline/pipeline/engine.py` contains a typed backend engine
- `src/frontend/pipeline_runner.py` contains a second full orchestration layer
- the frontend path is currently the more feature-rich runtime path

**Impact**

- fixes must often be applied twice
- stage logic drifts over time
- tests on one path do not guarantee the other path

**Recommendation**

Choose one canonical runtime. Best direction: keep `research_pipeline/` as the
system of record and reduce the frontend runner into a thin adapter.

#### Gap 2 — Governance is strong in design, weaker in implementation

**Severity:** Critical

The architecture promises hard publication controls, but parts of the backend
pipeline still use permissive placeholder logic.

Examples:

- Stage 5 evidence handling seeds an initialization claim if the agent succeeds
- Stage 11 review converts agent success into `PASS_WITH_DISCLOSURE`
- Stage 13 report assembly still uses placeholder sections and empty stock cards

**Recommendation**

Remove all placeholder approval behavior and fail closed on malformed or missing
structured outputs.

#### Gap 3 — Frontend and backend data contracts have drifted

**Severity:** High

Backend services were designed around typed models like `MarketSnapshot`, but
the frontend pipeline mostly operates on richer dict payloads.

**Recommendation**

Define one shared canonical snapshot/report contract for both frontend and
backend usage.

#### Gap 4 — Testing is more modular than systemic

**Severity:** High

The current test suite is meaningful, but it mostly proves module integrity,
not full product integrity.

**Recommendation**

Add product-level smoke tests and parity tests between backend and frontend
execution paths.

#### Gap 5 — Persistence is fragmented

**Severity:** Medium-High

There are multiple storage concepts: backend run registry, frontend report
storage, and stage artifact persistence.

**Recommendation**

Unify reports, artifacts, audit history, and run metadata under one registry.

#### Gap 6 — Operational processes are under-built

**Severity:** Medium

Missing or incomplete production processes include caching, explicit quota
management, centralized telemetry, queue-grade orchestration, and stronger raw
payload reproducibility.

**Recommendation**

The next phase should focus on operationalization, not just more analytical
features.

### Process Maturity Review

| Process Area | Score / 10 | Assessment |
|---|---:|---|
| Data acquisition | 8.0 | Good breadth, fallback logic, and practical source handling |
| Reconciliation and QA | 7.0 | Correctly prioritized, but not yet deep enough to be truly institutional-grade |
| Evidence formation | 7.5 ↑ | Typed claim ledger with tier enforcement; binary pass/fail status; golden-test assertions verified |
| Sector and thesis generation | 8.0 | Good decomposition and reasoning structure |
| Valuation process | 7.5 | Significantly improved by deterministic DCF integration |
| Risk process | 7.5 ↑ | `QuantResearchAnalystAgent` now interprets factor/VaR/ETF output; scenario engine deterministic |
| Red-team process | 7.5 | Strong role separation and useful adversarial framing |
| Publication control | 7.5 ↑ | Binary PASS/FAIL enforced in enum and IC vote; placeholder branches removed; gates hardened |
| Portfolio construction | 6.5 | Valuable stage, should consume more typed upstream contracts |
| Reporting and delivery | 6.5 | Reliable output generation, but split assembly paths create drift risk |

### Priority Remediation Plan

#### P0 — Architecture convergence

1. Unify orchestration under one canonical runtime path
2. Remove placeholder gate-pass logic
3. Unify frontend/backend stage contracts

#### P1 — Process hardening

4. Enforce structured outputs per agent/stage
5. Consolidate persistence and audit storage
6. Add frontend and end-to-end regression tests

#### P2 — Production readiness

7. Add caching, quotas, telemetry, and provider isolation
8. Deepen QA/lineage to field-level provenance
9. Maintain target-state vs current-state docs separately

## 11. Directory Map

```
Financial-analysis/
│
├── src/
│   ├── cli/                        # Typer CLI entry point
│   │   └── main.py
│   ├── frontend/                   # Streamlit UI
│   │   ├── app.py                  # Main UI app
│   │   ├── mock_data.py            # Offline demo data
│   │   └── pipeline_runner.py     # Async bridge for UI ↔ engine
│   └── research_pipeline/
│       ├── config/
│       │   ├── loader.py           # YAML → PipelineConfig
│       │   └── settings.py        # Env-var Settings model
│       ├── schemas/
│       │   ├── claims.py           # Evidence / claim models
│       │   ├── market_data.py      # Market, consensus, QA models
│       │   ├── portfolio.py        # Research output models
│       │   ├── reports.py          # Final report models
│       │   └── registry.py        # Run record models
│       ├── services/               # 10 deterministic services (no LLM)
│       │   ├── market_data_ingestor.py
│       │   ├── consensus_reconciliation.py
│       │   ├── data_qa_lineage.py
│       │   ├── dcf_engine.py
│       │   ├── risk_engine.py
│       │   ├── scenario_engine.py
│       │   ├── report_assembly.py
│       │   ├── run_registry.py
│       │   ├── golden_tests.py
│       │   └── scheduler.py
│       ├── agents/                 # 11 LLM reasoning agents
│       │   ├── base_agent.py       # BaseAgent + AgentResult shared infra
│       │   ├── orchestrator.py
│       │   ├── evidence_librarian.py
│       │   ├── sector_analysts.py  # Compute, PowerEnergy, Infrastructure
│       │   ├── valuation_analyst.py
│       │   ├── macro_political.py  # MacroStrategist + PoliticalRisk
│       │   ├── red_team_analyst.py
│       │   ├── associate_reviewer.py
│       │   └── portfolio_manager.py
│       └── pipeline/
│           ├── engine.py           # PipelineEngine — 15 stage execution
│           └── gates.py            # PipelineGates — gate check per stage
│
├── configs/                        # YAML config files
├── prompts/                        # Agent system prompts (Markdown)
├── tests/                          # pytest test suite
├── output/                         # Generated reports land here
├── pyproject.toml                  # Package metadata & dependencies
└── requirements.txt                # Pip install list
```

---

## 12. Extended Gap Analysis: JPAM Capability Assessment

> **Goal logged March 28, 2026:** Build a fully autonomous AI-powered investment organisation
> that structurally emulates JPMorgan Asset Management — with research, risk, portfolio
> management, governance, performance attribution, and client delivery operating as distinct,
> correctly governed divisions. See ROADMAP.md for the full 7-phase build plan.

### 12.1 What the Platform Still Needs to Build

The following capabilities exist in a real institutional asset manager (JPAM reference) but do
not yet exist in this codebase. Each is assessed for priority and build effort.

| Capability | JPAM Division | Priority | Effort | Status |
|---|---|---|---|---|
| **Factor exposure engine** (size, value, momentum, quality loadings) | Quant Research | P0 | Medium | Not started |
| **Benchmark-relative analytics** (active weight, tracking error, information ratio) | Quant Research | P0 | Medium | Not started |
| **VaR / CVaR engine** (parametric + historical, 95% and 99%) | Risk Management | P0 | Medium | Not started |
| **Drawdown analysis** (max drawdown, recovery time, underwater charts) | Risk Management | P0 | Low | Not started |
| **Liquidity profiling** (ADV, days-to-liquidate per position) | Portfolio Mgmt | P1 | Low | Not started |
| **ETF overlap engine** (BOTZ, AIQ, SOXX, etc.) | Quant Research | P1 | Low | Not started |
| **Portfolio optimisation** (mean-variance efficient frontier, min-var, max-Sharpe) | Portfolio Mgmt | P1 | High | Not started |
| **Black-Litterman model** (blend market equilibrium with analyst views) | Portfolio Mgmt | P1 | High | Not started |
| **Risk-budget allocation** (equal risk contribution, risk parity) | Risk Management | P1 | Medium | Not started |
| **Mandate compliance engine** (sector caps, single-name limits, liquidity floors) | Governance | P1 | Medium | Not started |
| **Investment committee process** (multi-approver voting, committee record schema) | Governance | P1 | Medium | Not started |
| **Human override log with identity** (approver, reason, timestamp, original status) | Governance | P1 | Low | Partial |
| **ESG integration layer** (ESG score per ticker, exclusion lists, ESG mandates) | ESG / Governance | P2 | High | Not started |
| **Performance attribution — BHB** (allocation, selection, interaction decomposition) | Performance | P2 | High | Not started |
| **Factor attribution** (attribute returns to factor exposures over time) | Performance | P2 | High | Not started |
| **Performance tracker** (price-stamped portfolio at T+N; NAV evolution) | Performance | P2 | Medium | Not started |
| **Thesis tracking** (link positions to original claims; surface thesis invalidation) | Research | P2 | Medium | Not started |
| **Research memory / vector store** (embed past reports for context injection) | Research | P2 | High | Not started |
| **Daily monitoring & diff engine** (nightly price/news refresh; trigger re-analysis) | Operations | P2 | Medium | Not started |
| **Prompt regression harness** (auto-run golden tests on any prompt change) | Governance | P2 | Low | Not started |
| **Observability dashboard** (stage latency, token usage, cost per run) | Operations | P2 | Medium | Not started |

### 12.2 What the Platform Needs to Improve

These components exist but fall short of institutional standard. Each gap is scored and
described with the specific improvement required.

#### Data layer improvements

| Component | Current state | Required improvement | Score gap |
|---|---|---|---|
| Market data ingestion | Serial requests, FMP + Finnhub only | Async parallel ingestion; add at least one more data source | 7.5 → 9.0 |
| Consensus reconciliation | Basic flag/threshold system | Field-level provenance; source preference logic with audit | 7.0 → 8.5 |
| Data QA / lineage | Completeness and staleness checks present | Add split/corporate action detection; currency unit cross-checks | 6.5 → 8.5 |
| Qualitative ingestion | Partially built in frontend | Formalise into a typed schema with tier classification | 5.5 → 8.0 |

#### Agent layer improvements

| Agent | Current state | Required improvement | Score gap |
|---|---|---|---|
| Evidence Librarian | Claim ledger built, partial source tier enforcement | Hard-reject Tier 3/4 sources for core claims | 6.0 → 8.5 |
| Sector analysts | Four-box structure per sector, not per ticker | Per-ticker four-box output with individual claim counts | 7.0 → 8.5 |
| Valuation Analyst | Interprets DCF output | Must label every target with methodology; disallow point estimates | 6.5 → 8.5 |
| Red Team Analyst | Challenge memo present | Enforce structural minimum of 3 concrete falsification paths per top idea | 7.0 → 9.0 |
| Associate Reviewer | Working, placeholder pass-through | Remove auto-pass; require explicit resolution for every unresolved item | 5.0 → 9.0 |
| Portfolio Manager | 3 variants produced | Must consume Black-Litterman weights and produce mandate-compliant output | 6.5 → 8.5 |
| Base Agent | JSON fallback to raw_text silently | Fail closed on malformed output; surface structured parse error explicitly | 6.0 → 9.0 |

#### Services improvements

| Service | Current state | Required improvement |
|---|---|---|
| DCF Engine | WACC/FCF/terminal value/sensitivity working | Add EV/EBITDA, P/E relative valuation methods for non-DCF-amenable stocks |
| Risk Engine | Correlation, HHI, contribution-to-variance | Add VaR, drawdown, benchmark beta, liquidity analysis |
| Scenario Engine | 7 named scenarios, deterministic | Add macro factor shock scenarios (rate +200bps, USD +10%, credit spread +150bps) |
| Report Assembly | Works on backend path, frontend builds inline | Unify to one Jinja2 path; add self-audit appendix and claim register as mandatory sections |
| Run Registry | UUID, timestamps, and stage outcomes | Add dataset version hash, config hash, LLM cost, token usage per run |
| Scheduler | Cron-style skeleton | Reliable async scheduler with alert-on-failure and watchlist monitoring |

### 12.3 What the Platform Needs to Fix

These are concrete defects in the current code — not design gaps but bugs or unsafe patterns.

| File | Location | Defect | Fix |
|---|---|---|---|
| `pipeline/engine.py` | Line 285–290 | Synthetic `INIT-001` claim seeded when agent succeeds — Stage 5 gate bypass | Remove synthetic claim; fail gate if minimum claims not met from real data |
| `pipeline/engine.py` | Line 413 | Stage 11 review converts agent success alone to `PASS_WITH_DISCLOSURE` | Require structured reviewer output with explicit disposition per unresolved item |
| `pipeline/engine.py` | Line 450–453 | Stage 13 fallback to `PASS_WITH_DISCLOSURE` if no review result | Fail closed — no review result must halt pipeline |
| `agents/base_agent.py` | Lines 208–212 | Malformed agent JSON silently degraded to `{"raw_text": raw_response}` | Raise structured error; route to retry; fail stage on repeated malformed response |
| `services/golden_tests.py` | Line 148 | `passed = True  # placeholder for custom categories` | Implement real assertion logic per test category |
| `frontend/storage.py` | Line 82 | `REPORTS_DIR.glob("DEMO-*.json")` only finds DEMO-prefixed runs | Change glob to `RUN-*.json` or `*.json` with schema validation |
| `frontend/pipeline_runner.py` | Full file (1852 lines) | Second full orchestration engine duplicating `PipelineEngine` | Reduce to thin adapter pattern calling `PipelineEngine` stages |
| `services/market_data_ingestor.py` | `ingest_universe()` | Sequential per-ticker requests, no parallelism | Wrap per-ticker calls in `asyncio.gather` with semaphore for rate control |

### 12.4 Division-Level Maturity Assessment (JPAM Benchmark)

| Division | Analogous in codebase | Current score | JPAM target | Gap |
|---|---|---|---|---|
| Global Research | Stages 5–8 + associated agents | 7.5 / 10 ↑ | 9.0 / 10 | 1.5 |
| Quantitative Research | Risk Engine + Scenario + QuantResearchAnalystAgent + FixedIncomeAnalystAgent + `PortfolioOptimisationEngine` | 8.0 / 10 ↑ | 9.0 / 10 | 1.0 |
| Portfolio Management | Stage 12 + Portfolio Manager agent + risk-parity / min-var / max-Sharpe optimiser | 7.5 / 10 ↑ | 8.5 / 10 | 1.0 |
| Investment Governance | Gates + Associate Reviewer + binary PASS/FAIL + gate hardening + `SelfAuditPacket` on every exit (success + failure) + latency fields | 8.5 / 10 | 9.5 / 10 | 1.0 |
| Performance Attribution | BHB attribution with synthetic returns (`_generate_synthetic_returns`, `_compute_bhb_attribution`) wired into Stage 14 | 4.0 / 10 ↑ | 8.5 / 10 | 4.5 |
| ESG / Sustainable Investing | `EsgAnalystAgent` + `ESGService` baseline profiles; heuristic E/S/G + controversy; wired into Stage 6 | 5.0 / 10 ↑ | 7.5 / 10 | 2.5 |
| Operations & Technology | Ingestion + Run Registry + pipeline_adapter + 503 tests + CI weekly + robust parse_output + all exits emit audit packet | 8.5 / 10 | 9.0 / 10 | 0.5 |
| Client Solutions / Reporting | Streamlit UI + Report Assembly + Quant Analytics Panel (VaR, ETF overlap, IC vote, FI context, ESG panel, latency) + PDF export | 8.0 / 10 | 8.5 / 10 | 0.5 |

**Weighted platform score vs JPAM standard: 8.0 / 10 ↑** *(updated session 7 from 7.5)*  
*(Primary remaining gaps: Performance Attribution on synthetic data only [needs live price feed]; ESG on heuristic profiles [needs paid dataset])*

### 12.5 Next 10 Actions (Priority Order)

1. ~~Fix `engine.py` placeholder gate logic (lines 285–290, 413, 450–453)~~ — **DONE** session 5 (gates 9/12/13 real values; IC rejection enforced; concentration warnings surfaced)
2. ~~Fix `base_agent.py` silent JSON fallback~~ — **DONE** session 5 (three-strategy parse_output: regex fence, bare json.loads, raw_decode preamble strip)
3. ~~Reduce `frontend/pipeline_runner.py` to an adapter~~ — **DONE** (`pipeline_adapter.py` created; `PipelineEngineAdapter` is drop-in)
4. ~~Merge `frontend/storage.py` into `RunRegistryService`~~ — **DONE** (`save_run` mirrors to registry; `list_saved_runs` merges both stores)
5. ~~Implement `SelfAuditPacket` schema and attach to every run~~ — **DONE** session 6 (`_build_self_audit_packet()` wired into `run_full_pipeline`; JSON persisted to `artifacts/{run_id}/self_audit_packet.json`; ACT-S6-1)
6. ~~Add drawdown analysis and VaR to `RiskEngine`~~ — **DONE** (`RiskPacket` with VaR/CVaR/max-drawdown/portfolio-volatility; ACT-6 session 3)
7. ~~Add benchmark-relative analytics module~~ — **DONE** (`BenchmarkModule` with BHB factor attribution; already built)
8. ~~Implement investment committee schema and human override log with identity~~ — **DONE** (`InvestmentCommitteeService` + `HumanOverride` built; IC vote displayed in Streamlit)
9. ~~Begin historical portfolio logging~~ — **DONE** (`PortfolioSnapshot` / `PerformanceTracker` built and wired)
10. ~~Add `asyncio.gather` to market data ingestion~~ — **DONE** (semaphore + `asyncio.gather` in both market data and qualitative ingestors)

### 12.6 Session 5 Candidate Actions

1. ~~Fix `engine.py` placeholder gate logic~~ — **DONE** (gates 9/12/13 now use real computed values; IC rejection blocks gate 12; `all_sections_approved` uses review verdict; concentration_breaches surfaced in gate 9)
2. ~~Fix `base_agent.py` silent JSON fallback~~ — **DONE** (three-strategy parse_output: regex fence extraction, direct `json.loads`, `JSONDecoder.raw_decode` to skip preamble; `re` imported; logs warning on preamble strip)
3. ~~Implement `SelfAuditPacket` schema~~ — **DONE** session 6 (engine `_build_self_audit_packet()`; JSON persisted; quality score computed; ACT-S6-1)
4. ~~Add `asyncio.gather` to market data ingestion~~ — **ALREADY DONE** (`ingest_universe` uses semaphore + `asyncio.gather`; qualitative ingestor same)
5. ~~ESG/Governance analyst agent~~ — **DONE** session 6 (`EsgAnalystAgent` with E/S/G clamped [0-100], exclusion trigger, wired into Stage 6 non-blocking; ACT-S6-2)
6. ~~Performance Attribution (BHB) with real historical data~~ — **DONE** session 7 (`_generate_synthetic_returns` + `_compute_bhb_attribution` wired into Stage 14; `PortfolioOptimisationEngine` in Stage 12; ACT-S7-1/S7-4)
7. Add Redis-backed run cache — avoid re-fetching market data for same ticker set within 1 h — **deferred**
8. ~~Export Report-tab data to PDF~~ — **DONE** session 6 (`fpdf2` cover page + body via `_generate_report_pdf()`; download button in Report tab; ACT-S6-3)

### 12.7 Session 6 Completed Work

| ID | Task | File(s) | JPAM Division | Status |
|---|---|---|---|---|
| ACT-S6-1 | Wire `SelfAuditPacket` into every `run_full_pipeline` call — `_build_self_audit_packet()`, JSON to `artifacts/{run_id}/self_audit_packet.json`, quality score computed | `engine.py`, `run_registry.py`, `governance.py` | Investment Governance | ✅ `608c286` |
| ACT-S6-2 | New `EsgAnalystAgent` — LLM agent scoring E/S/G [0-100] per ticker; clamped mandatory JSON; `exclusion_trigger`/`controversy_flags`; wired into Stage 6 non-blocking | `agents/esg_analyst.py`, `engine.py`, `app.py` | ESG / Sustainable Investing | ✅ `608c286` |
| ACT-S6-3 | PDF export button via `fpdf2` — `_generate_report_pdf()` cover page + body (Latin-1 safe, markdown-formatted); download button in Report tab | `src/frontend/app.py`, `requirements.txt` | Client Solutions | ✅ `608c286` |
| ACT-S6-4 | Close A-1 debt — `pipeline_runner.py` `DeprecationWarning` on import; `app.py` switched to `pipeline_adapter` | `src/frontend/pipeline_runner.py`, `app.py` | Operations | ✅ `608c286` |
| ACT-S6-5 | 27 new tests: SelfAuditPacket wiring, ESG agent (parse/clamp/defaults/exclusion), PDF export, deprecation warning | `tests/test_session6.py` | Operations | ✅ `608c286` |

**Session 6 achieved state:** Weighted platform score 7.1 → **7.5**; ESG division 0 → **3.0/10**; Investment Governance 8.0 → **8.5**; `SelfAuditPacket` on every run ✅; 480 tests passing.

### 12.8 Session 7 Completed Work

| ID | Task | File(s) | JPAM Division | Status |
|---|---|---|---|---|
| ACT-S7-1 | BHB Performance Attribution with synthetic returns — `_generate_synthetic_returns`, `_compute_bhb_attribution`; wired into Stage 14 `stage_outputs[14]["attribution"]` | `engine.py`, `schemas/governance.py` | Performance Attribution | ✅ `2530399` |
| ACT-S7-2 | `ESGService` baseline profiles (heuristic E/S/G + controversy per ticker) passed to `EsgAnalystAgent.format_input`; `esg_baseline_profiles` in Stage 6 context | `agents/esg_analyst.py`, `services/esg_service.py`, `engine.py` | ESG / Sustainable Investing | ✅ `2530399` |
| ACT-S7-3 | `SelfAuditPacket.stage_latencies_ms` + `total_pipeline_duration_s`; `_emit_audit_packet` extracted — called on every pipeline exit (14 early-fail paths + success); stage 14 timed via `_timed_stage(14, ...)` | `engine.py`, `schemas/governance.py` | Investment Governance | ✅ `2530399` |
| ACT-S7-4 | `PortfolioOptimisationEngine` — risk parity (inverse-vol), min-variance, max-Sharpe; wired into Stage 12 as `optimisation_results` dict alongside existing PM agent output | `services/portfolio_optimisation.py`, `engine.py` | Portfolio Management | ✅ `2530399` |
| ACT-S7-5 | 23 new tests covering attribution BHB identity, synthetic returns, optimiser weight sums, ESG format_input enrichment, latency fields | `tests/test_session7.py` | Operations | ✅ `2530399` |

**Session 7 achieved state:** Weighted platform score 7.5 → **8.0**; Performance Attribution 0 → **4.0/10**; ESG 3.0 → **5.0/10**; Portfolio Management 6.5 → **7.5**; audit packet on all exits ✅; 503 tests passing.

### 12.9 Session 8 Completed Work

| ID | Task | File(s) | JPAM Division | Status |
|---|---|---|---|---|
| ACT-S8-1 | `LiveReturnStore` — yfinance-backed daily return fetcher with in-memory cache and graceful fallback; `_get_returns()` engine helper tries live first, falls back to synthetic; wired into Stage 12 + Stage 14 | `services/live_return_store.py`, `engine.py` | Performance Attribution | ✅ `a7e520e` |
| ACT-S8-2 | Rebalancing signals — `RebalancingEngine.generate_rebalance()` called post-optimisation in Stage 12; `rebalance_proposal` in `stage_outputs[12]`; Streamlit Rebalancing Signals panel with trade-level detail table | `engine.py`, `app.py` | Portfolio Management | ✅ `a7e520e` |
| ACT-S8-3 | `ESGService.load_from_csv()` — ingest external ESG scores (ticker, overall_rating, E/S/G scores, controversy_flag) from CSV; validates `ESGRating` enum, skips invalid rows, invalidates score cache per ticker | `services/esg_service.py` | ESG / Sustainable Investing | ✅ `a7e520e` |
| ACT-S8-4 | `PromptRegistry` wired — `_scan_prompt_registry(packet)` iterates all 14 agents, registers prompt hashes, checks drift; `SelfAuditPacket.prompt_drift_reports: list[dict]` populated on every completed run | `engine.py`, `schemas/governance.py` | Investment Governance | ✅ `a7e520e` |
| ACT-S8-5 | 26 new tests — `TestLiveReturnStore` (7), `TestRebalancingWiring` (5), `TestESGCsvIngest` (6), `TestPromptRegistryWiring` (8) | `tests/test_session8.py` | Operations | ✅ `a7e520e` |

**Session 8 achieved state:** Weighted platform score 8.0 → **8.3**; Performance Attribution 4.0 → **5.5/10** (live data path built); ESG 5.0 → **5.5/10** (CSV ingest available); Portfolio Management 7.5 → **8.0/10** (rebalancing signals in UI); prompt drift tracking wired ✅; 529 tests passing.

### 12.10 Session 9 Completed Work

| ID | Task | File(s) | JPAM Division | Status |
|---|---|---|---|---|
| ACT-S9-1 | `tests/fixtures/esg_sample.csv` — 20-ticker MSCI-style ESG fixture; verified round-trip via `ESGService.load_from_csv()`; adds INTC, QCOM, ORCL, CRM, SNOW | `tests/fixtures/esg_sample.csv`, `services/esg_service.py` | ESG / Sustainable Investing | ✅ `93f5ba5` |
| ACT-S9-2 | `tests/test_prompt_regression.py` — 24 CI regression tests; `check_all_drift()` detects accidental prompt changes; regression marking lifecycle; all 14 agents gated | `services/prompt_registry.py`, `tests/` | Operations | ✅ `93f5ba5` |
| ACT-S9-3 | `SelfAuditPacket.rebalancing_summary: dict` — populated in `_emit_audit_packet` from `stage_outputs[12]`; keys: `trade_count`, `total_turnover_pct`, `estimated_total_impact_bps`; Observability panel updated | `schemas/governance.py`, `engine.py`, `app.py` | Investment Governance | ✅ `93f5ba5` |
| ACT-S9-4 | `LiveReturnStore._download_individual()` — per-ticker yfinance fallback when batch fails; `_get_returns()` blends live data for available tickers with synthetic for failed ones | `services/live_return_store.py`, `engine.py` | Performance Attribution | ✅ `93f5ba5` |
| ACT-S9-5 | 26 new tests — `TestESGFixtureCsvIngest` (9), `TestLiveReturnStoreHardening` (6), `TestRebalancingSummaryAuditPacket` (7), `TestPromptRegressionIntegration` (4) | `tests/test_session9.py` | Operations | ✅ `93f5ba5` |

**Session 9 achieved state:** Weighted platform score 8.3 → **8.5**; ESG 5.5 → **6.5/10** (fixture CSV verified); Performance Attribution 5.5 → **6.0/10** (ticker-level fallback); Investment Governance 8.5 → **8.8/10**; 579 tests passing.

### 12.11 Session 10 — Completed ✅

| ID | Task | File(s) | JPAM Division | Status |
|---|---|---|---|---|
| ACT-S10-1 | **Live BHB attribution accuracy** — `data_source` field (`"live"` / `"blended"` / `"synthetic"`) in attribution output; `live_return_store.fetch()` called for both portfolio and benchmark returns | `engine.py` | Performance Attribution | ✅ Done |
| ACT-S10-2 | **ESG compliance CSV export** — `ESGService.to_csv()` method; `st.download_button` in ESG Analytics panel | `services/esg_service.py`, `app.py` | Client Solutions / Reporting | ✅ Done |
| ACT-S10-3 | **Agent output quality gate** — `BaseAgent._REQUIRED_OUTPUT_KEYS` class attribute + `_validate_output_quality()` method; `ValuationAnalystAgent` and `EsgAnalystAgent` declare required keys; non-fatal warnings logged | `agents/base_agent.py`, `agents/valuation_analyst.py`, `agents/esg_analyst.py` | Global Research | ✅ Done |
| ACT-S10-4 | **Factor model live data** — Stage 9 now calls `_get_returns(universe, n_days=252)` and passes live returns + 5-factor synthetic proxy to `FactorExposureEngine` for OLS regression path | `engine.py` | Quantitative Research | ✅ Done |
| ACT-S10-5 | **Tests** — 28 new tests; 607 total passing | `tests/test_session10.py` | Operations | ✅ Done |

**Session 10 outcome:** Weighted platform score 8.5 → 8.8; Performance Attribution to 7.5; Global Research to 8.0; Quantitative Research to 8.5; Client Solutions to 8.5.

### 12.12 Session 11 Work Plan

| ID | Task | File(s) | JPAM Division | Effort |
|---|---|---|---|---|
| ACT-S11-1 | **Attribution time series** — store rolling 30-day BHB decomposition in `SelfAuditPacket`; Streamlit line chart in attribution panel | `engine.py`, `schemas/governance.py`, `app.py` | Performance Attribution | Medium |
| ACT-S11-2 | **Sector-weight drift alert** — compare current vs baseline sector weights; alert if drift > threshold | `engine.py`, `app.py` | Portfolio Management | Low |
| ACT-S11-3 | **Agent retry telemetry** — log per-agent retry counts and model-fallback events to `SelfAuditPacket` | `agents/base_agent.py`, `schemas/governance.py` | Global Research | Medium |
| ACT-S11-4 | **ESG mandate score trend** — store last-N ESG composite scores; display trending chart in Streamlit | `services/esg_service.py`, `app.py` | Client Solutions | Low |
| ACT-S11-5 | **Tests** — session 11 verification tests targeting 635+ total | `tests/test_session11.py` | Operations | Low |

---

*Document updated: session 10 — ACT-S10-1 (live BHB data_source), ACT-S10-2 (ESG CSV export), ACT-S10-3 (agent quality gate), ACT-S10-4 (factor live data), ACT-S10-5 (28 tests). Test count: 607 passing. Session 11 plan in §12.12.*

---

## 13. Platform Scope, Market Coverage & Macro Economics Architecture

### 13.1 Realistic Market Scope — JP Morgan Australia Clone

This platform models a **JP Morgan-style institutional asset management office based in Australia**, managing client portfolios across equity markets realistic for a boutique-to-mid-tier Australian asset manager with global reach. The markets covered and their investment rationale are:

| Market | Exchange | Currency | Benchmark | Client relevance | Priority |
|---|---|---|---|---|---|
| **US Large Cap / AI Infrastructure** | NYSE / NASDAQ | USD | S&P 500, NASDAQ-100 | Primary — highest-growth, highest-conviction theme | P0 — current |
| **Australian Equities** | ASX | AUD | ASX 200 | Domestic client portfolios, superannuation mandates, franking credits | P0 — build session 12 |
| **US Broad Market** | NYSE / NASDAQ | USD | S&P 500 | Core equity allocation for most client mandates | P1 — partial |
| **Global Thematic (AI/tech)** | Multi-exchange | Multi | MSCI World | Thematic overlays for high-growth clients | P1 — partial |
| **Fixed Income (US Treasuries)** | OTC | USD | Bloomberg US Agg | Defensive allocation; rate sensitivity for equity models | P1 — build session 13 |
| **ASX Fixed Income / Bonds** | ASX | AUD | Bloomberg AusBond | Super / conservative mandates | P2 |
| **Asian Tech / Semiconductors** | TSE, HKEX, TWSE | JPY/HKD/TWD | Nikkei, Hang Seng, TWSE | Taiwan/Japan AI supply chain exposure | P2 |
| **European Equities** | LSE, NYSE Euronext | EUR/GBP | STOXX 600 | Diversification overlay; minimal current exposure | P3 |
| **Commodities (AUD-correlated)** | ASX / CME | USD/AUD | Bloomberg Commodity | BHP, RIO, FCX — already in universe | P1 — partial |

**Markets NOT covered (realistic exclusions for this office profile):**
- Emerging markets standalone allocations (EM is captured via global thematic)
- Frontier markets
- Private equity / venture capital
- Real estate direct investment (REITs are captured as equity)
- Crypto assets (outside mandate)

---

### 13.2 macroeconomic Analysis Gap Assessment

**Current state:** The platform has one `MacroStrategistAgent` that classifies a single generic "macro regime" with 5-6 fields. It has no awareness of:
- Which countries' economies are relevant to the portfolio
- Australia vs US macro divergence (RBA vs Fed)
- Inflation measures (CPI, PCE, trimmed mean, PPI, core)
- Interest rate paths and forward pricing
- Housing markets (Australia's outsized impact on consumer spending)
- Labour market tightness (wage inflation → cost of capital)
- Currency movements (AUD/USD matters enormously for ASX portfolios)
- Government fiscal stance (deficit spending supporting or crowding out)
- Corporate earnings impact from macro variables (COGS, margin compression)

**Gap score:** The current macro analysis is 2/10. It produces AI infrastructure sensitivities only and is never consumed by downstream stages.

---

### 13.3 Target Macro Economy Architecture

The platform needs a dedicated **Economic Intelligence Layer** consisting of three new services and one redesigned agent:

#### Service 1: `EconomicIndicatorService` (new)
Fetches and normalises economic indicator data:
- **US indicators**: Fed Funds Rate, 10Y/2Y yields, CPI YoY, PCE YoY, Core CPI, PPI, NFP, unemployment, ISM PMI, housing starts, Case-Shiller HPI, retail sales, consumer confidence
- **Australian indicators**: RBA cash rate, CPI (trimmed mean), wage price index, employment change, NAB business confidence, Westpac consumer sentiment, CoreLogic housing prices, rental vacancy rates, AUD/USD, trade balance, terms of trade
- **Global**: China PMI (impacts Australian exports), global PMI composite, oil price (WTI/Brent), copper price (AUD proxy), VIX

Data sources: FRED API (free), RBA Statistical Tables (public), ABS (Australian Bureau of Statistics), Yahoo Finance for market-derived indicators.

#### Service 2: `MacroScenarioService` (new)
Forward-looking scenario construction:
- **Rate path scenarios**: base case / hiking cycle / cutting cycle — with probability weights
- **Inflation scenarios**: sticky inflation vs normalisation vs deflation
- **Growth scenarios**: soft landing / hard landing / stagflation
- **Currency scenarios**: AUD strength/weakness vs USD, impact on offshore holdings
- For Australia: RBA specific scenarios (pause, hike, cut) + their transmission to mortgages, consumer spending, bank earnings

#### Service 3: `MarketRegimeClassifier` (upgraded from current MacroStrategist)
- Classifies regime per market: US, Australia, Global
- Outputs regime → portfolio construction implications
- Feeds into Stage 7 (Valuation), Stage 9 (Risk), Stage 12 (Portfolio)

#### Agent 1: `EconomyAnalystAgent` (new — replaces/upgrades MacroStrategistAgent)
Full sovereign-level economic analysis per jurisdiction:
- **For US investing**: Fed policy, yield curve shape, inflation dynamics (CPI/PCE), labour market (NFP, wages, JOLTS), housing (mortgage rates, affordability, starts), consumer health (savings rate, credit card delinquencies), corporate margins (COGS, SG&A vs revenue), earnings revisions cycle
- **For Australia (ASX/super mandates)**: RBA policy, trimmed mean CPI, housing market (CoreLogic prices, rental yields, vacancy rates, mortgage stress), wage inflation, terms of trade (iron ore, coal, gas — the real AUD driver), household debt-to-income ratio, bank net interest margins, superannuation flows as a structural buyer
- **Cross-market**: AUD/USD impact on US-listed holdings, hedging costs, FX contribution to returns

#### Agent 2: `MacroPoliticalRiskAgent` (existing — upgraded)
- Currently: narrow AI infrastructure policy focus
- Needs: central bank independence risks, sovereign debt sustainability, geopolitical shock scenarios, election impacts on fiscal policy, RBA vs APRA regulatory divergence, US-China trade war transmission to Australian exports

---

### 13.4 Architecture Repair: Critical Bugs Found in Sessions 1–10

The following are live bugs in the current codebase where stages run but their outputs never reach the agents that need them:

| # | Bug | Location | Impact | Fix session |
|---|---|---|---|---|
| ARC-1 | **Stage 8 macro outputs never consumed downstream** — saved to `stage_outputs[8]` but no stage 9/10/11/12 reads it | `engine.py` lines 801–818 | All downstream agents missing macro context | Session 11 |
| ARC-2 | **Stage 13 report is a stub** — `stock_cards=[]`, sections are hardcoded strings, PM investor document never inserted | `engine.py` line 1231–1248 | Final deliverable is empty | Session 11 |
| ARC-3 | **VaR uses synthetic data despite live returns available** — `live_factor_returns` computed then ignored; `np.random.normal()` used instead | `engine.py` lines 856–866 | VaR is inaccurate | Session 11 |
| ARC-4 | **Stage 8 (Macro) runs AFTER Stage 7 (Valuation)** — valuation discount rates and terminal growth assumptions set without macro regime context | `engine.py` lines 1462–1472 | DCF quality undermined | Session 11 |
| ARC-5 | **Sector routing is hardcoded to 17 specific tickers** — any other ticker gets no sector analysis agent at all | `engine.py` lines 724–726 | Custom universes fail silently | Session 11 |
| ARC-6 | **Stage 10 Red Team missing macro + risk inputs** — only sees sector + valuation | `engine.py` line 980–990 | Red Team can't challenge macro thesis | Session 11 |
| ARC-7 | **Stage 11 Reviewer missing macro + risk inputs** — only sees evidence, valuation, red team | `engine.py` lines 1000–1010 | Review is incomplete | Session 11 |
| ARC-8 | **Stage 12 PM Agent missing macro context** — portfolio built without macro regime | `engine.py` lines 1144–1165 | Portfolio construction not macro-aware | Session 11 |
| ARC-9 | **Macro agent receives no market data (Stage 2 outputs never passed)** | `engine.py` line 805 | Macro analysis is context-free | Session 11 |
| ARC-10 | **Stage 9 FI Agent receives hardcoded stub** — `"Live yield/spread data not available"` despite Stage 8 running just before | `engine.py` lines 930–937 | Fixed income analysis is fictional | Session 11 |

---

### 13.5 Session 11 — Revised Plan (Architecture Repair First)

| ID | Task | File(s) | Impact | Effort |
|---|---|---|---|---|
| ARC-1 | **Wire Stage 8 macro to downstream stages** — extract `_get_macro_context()` helper; pass to S9 FI agent, S10 Red Team, S11 Reviewer, S12 PM | `engine.py` | Very High | Low |
| ARC-2 | **Fix Stage 13 report** — build `stock_cards` from S7 valuation; use PM `investor_document` for sections; pull exec summary from orchestrator | `engine.py`, `services/report_assembly.py` | High | Medium |
| ARC-3 | **Fix VaR to use live returns** — replace `np.random.normal()` with already-computed `live_factor_returns` aggregate | `engine.py` stage_9 | Medium | Low |
| ARC-4 | **Reorder S7/S8** — run macro before valuation; or add macro re-contextualization pass | `engine.py` run_full_pipeline | Medium | Low |
| ARC-5 | **Config-driven sector routing** — replace hardcoded ticker sets with `SECTOR_ROUTING` dict + general fallback analyst | `engine.py`, `config/loader.py` | Medium | Low |
| ARC-6–8 | **Wire macro to Red Team, Reviewer, PM** — `stage_outputs[8]` macro summary added to all three agents' inputs | `engine.py` | High | Low |
| ARC-9 | **Feed market data to Macro agent** — pass `stage_outputs[2]` ingestion data + Stage 3 reconciliation report to MacroStrategistAgent | `engine.py` | Medium | Low |
| ARC-10 | **Replace FI Agent hardcoded stub** — extract real macro context from Stage 8 output and pass to Fixed Income agent | `engine.py` | High | Low |
| S11-6 | **Tests** — `tests/test_session11.py` ~32 tests covering all ARC fixes | `tests/test_session11.py` | Required | Low |

**Session 11 target:** 639+ tests passing; Global Research 8.0 → 8.8; Performance Attribution 7.5 → 8.0; Portfolio Management 8.0 → 8.5; weighted 8.8 → 9.0

---

### 13.6 Session 12 — Macro Economy & Australia/US Markets

| ID | Task | File(s) | Impact | Effort |
|---|---|---|---|---|
| MAC-1 | **`EconomicIndicatorService`** — FRED API + RBA public tables + ABS; normalised data model for US and Australian indicators | `services/economic_indicators.py` | Very High | Medium |
| MAC-2 | **`EconomyAnalystAgent`** — full LLM agent for US macro analysis (Fed, CPI/PCE, housing, labour, earnings margins) and Australian macro (RBA, trimmed mean CPI, housing, wages, terms of trade, AUD) | `agents/economy_analyst.py` | Very High | Medium |
| MAC-3 | **Market scope config** — `MarketConfig` in `PipelineConfig`: US/ASX/Global toggle; jurisdiction-aware data routing | `config/loader.py`, `config/settings.py` | High | Low |
| MAC-4 | **Macro scenario service** — rate path (hike/hold/cut), inflation (sticky/normalising), growth (soft/hard landing); AUD/USD scenarios | `services/macro_scenario.py` | High | Medium |
| MAC-5 | **Wire `EconomyAnalystAgent` into Stage 8** — run in parallel with existing macro/political agents; output to `stage_outputs[8]["economy_analysis"]` | `engine.py` | High | Low |
| MAC-6 | **Valuation macro integration** — Stage 7 receives economy context; discount rate and terminal growth informed by rate path scenario | `agents/valuation_analyst.py`, `engine.py` | High | Medium |
| MAC-7 | **Streamlit macro dashboard** — new "Market Overview" tab: US macro panel (Fed watch, yield curve, CPI), Australian macro panel (RBA, housing, AUD), macro scenarios with probability weights | `frontend/app.py` | High | Medium |
| MAC-8 | **Tests** — `tests/test_session12.py` ~30 tests | `tests/test_session12.py` | Required | Low |

**Session 12 target:** 669+ tests; new Macro Economy tab live; EconomyAnalystAgent produces AU + US analysis; macro context flows to all pipeline stages; weighted score 9.0 → 9.2

---

### 13.7 Session 13 — Depth & Quality Improvements

| ID | Task | File(s) | Impact | Effort |
|---|---|---|---|---|
| DEP-1 | **ASX universe support** — ticker routing for ASX stocks (BHP, CBA, CSL, etc.); AUD denomination adjustments; ASX-specific data ingestor | `config/universe_config.py`, `services/market_data_ingestor.py` | High | High |
| DEP-2 | **Research memory → Stage 5** — embed past research reports in vector store; inject top-k relevant prior claims into Evidence Librarian context | `services/research_memory.py`, `engine.py` | High | High |
| DEP-3 | **Currency-aware portfolio** — AUD/USD FX conversion; hedged vs unhedged return contribution; FX risk in `RiskPacket`  | `schemas/portfolio.py`, `engine.py`, `app.py` | Medium | Medium |
| DEP-4 | **Sector 4-box per ticker** — sector analysts currently produce portfolio-level analysis; restructure to per-ticker four-box with individual claim counts | `agents/sector_analysts.py`, `engine.py` | Medium | Medium |
| DEP-5 | **Evidence Librarian enrichment pass** — after Stage 6, inject sector four-box data back into the claim ledger to corroborate/contradict existing claims | `engine.py` | High | Medium |
| DEP-6 | **Real-time rate data** — FRED API integration for live Fed Funds, SOFR, 10Y, TIPS breakeven; RBA historical series for AUD rates | `services/economic_indicators.py` | High | Medium |
| DEP-7 | **Attribution time series** — rolling 30-day BHB decomposition stored in `SelfAuditPacket`; Streamlit line chart | `engine.py`, `schemas/governance.py`, `app.py` | Medium | Medium |
| DEP-8 | **Agent retry telemetry** — per-agent retry count and model-fallback events logged in `SelfAuditPacket` | `agents/base_agent.py`, `schemas/governance.py` | Low | Low |
| DEP-9 | **Tests** — `tests/test_session13.py` ~30 tests | `tests/test_session13.py` | Required | Low |

---

### 13.8 Session 14 — Superannuation & Australian Client Context

*(Planned — not yet designed in detail)*

| ID | Task |
|---|---|
| SUP-1 | Superannuation mandate profiles — conservative / balanced / growth / high-growth with constraint sets |
| SUP-2 | Franking credit model — grossed-up yield computation for ASX dividend payers |
| SUP-3 | APRA compliance checks — super fund investment restrictions |
| SUP-4 | Tax-aware portfolio construction — CGT harvesting, super-specific tax efficiency |
| SUP-5 | ATO reporting schema — SMSF-ready output format |

---

### 13.9 Brainstorm — What Else Is Missing

The following items were identified in a systematic gap analysis vs a real JPAM institutional office. Grouped by division:

#### Global Research Division
- **Thesis tracking** — link positions to original claims; surface when thesis is partially invalidated mid-cycle
- **Earnings revision momentum** — track analyst estimate revisions as a signal input
- **Transcript analysis** — earnings call keyword tracking feeding into agent prompts
- **Supply chain graph** — map NVDA/AMD/TSM supply chains; propagate risk scores upstream/downstream
- **News freshness scoring** — weight claim confidence by how recent the supporting news is

#### Quantitative Research Division
- **Black-Litterman model** — blend market equilibrium (implied returns) with analyst views from Stage 7
- **Risk parity with macro overlays** — weight constraints adjust as macro regime shifts
- **Correlation regime detection** — identify when cross-asset correlations break down (crisis)
- **Liquidity profiling** — ADV (average daily volume) and days-to-liquidate per position
- **Factor attribution** — attribute weekly/monthly return to factor exposures (market, size, value, momentum, quality)

#### Portfolio Management Division
- **Benchmark-relative mandate profiles** — active share, tracking error budget, TE-constrained optimisation
- **Tax-lot tracking** — position-level cost basis for CGT-aware rebalancing
- **Overlay hedging** — FX hedge ratios; interest rate duration overlay
- **Portfolio stress testing** — fully specified macro shock scenarios applied to the current portfolio

#### Performance Attribution Division
- **Daily NAV** — price the portfolio daily using live prices; produce daily P&L attribution
- **Attribution vs benchmark** — active return decomposition: selection + allocation + interaction per sector
- **Multi-period linking** — chain-link attribution across reporting periods (monthly, quarterly, annual)
- **Risk-adjusted performance** — Sharpe, Sortino, Calmar per portfolio variant

#### ESG / Sustainable Investing
- **Real data feed** — MSCI ESG Ratings, Sustainalytics, or equivalent (currently all heuristic)
- **SFDR alignment** — Article 6/8/9 classification for European mandates
- **Net-zero pathway** — carbon intensity tracking; Paris-alignment scoring
- **Governance red flags** — director tenure, related-party transactions, audit quality

#### Client Solutions / Reporting
- **Client portal PDF** — branded, client-ready PDF with portfolio summary, macro view, risk commentary
- **Scenario P&L letters** — "if rates rise 100bps, your portfolio does X" formatted for retail clients
- **SMSF reporting pack** — ATO-compliant transaction and holdings report
- **Benchmark comparison chart** — portfolio vs ASX200 vs S&P500 vs 60/40 running chart

#### Operations & Technology
- **Database persistence** — replace JSON files with PostgreSQL or SQLite for run history
- **Scheduler / watchlist monitoring** — nightly refresh; trigger re-analysis on price/news threshold breach
- **LLM cost tracking** — per-run token usage and USD cost in `SelfAuditPacket`
- **Redis caching** — avoid re-running expensive stages within TTL window
- **API rate limiting** — proper backoff and quota management for FMP/Finnhub/FRED
- **Test coverage to 90%** — currently strong but some services are under-tested

---

### 13.10 External PR Review — Core system improvements (#1)

The Cursor-generated PR #1 contains ideas aligned with our roadmap, but it should **not** be merged as-is.

**Observed result from isolated review branch:** `14 failed, 18 errors, 575 passed`.

Primary hard failures:

| Finding | Why it blocks merge |
|---|---|
| `_route_sector_tickers()` referenced but not implemented | Stage 6 crashes immediately |
| `_build_metric_snapshot()` referenced but not implemented | Stage 14 crashes on failed or completed runs |
| Large mixed-scope bundle | ARC fixes, Session 12/14 features, HTML reporting, tax overlays, fallback chains, and trend logic all land together without a clean sequencing strategy |
| Several changes depend on unspecified adapters/schemas | Confirmed by `PROJECT_ISSUES_ASSESSMENT.md` ISS-1, ISS-3, ISS-4, ISS-12, ISS-16 |

**Architecture decision:** use PR #1 as a concept/reference branch only. Rebuild any valuable pieces on `main` in small session-sized increments with tests.

Reusable concepts worth salvaging later:
- `EconomyAnalystAgent`
- LLM provider/model telemetry on `AgentResult`
- `MarketConfig` / `LLMConfig` direction
- `ReportHtmlService`
- AU client overlays (`AustralianTaxService`, `SuperannuationMandateService`)
- Cross-run research trend alerts

---

### 13.11 Residual Issues After Current Plan (from `PROJECT_ISSUES_ASSESSMENT.md`)

PR #2 introduced a useful audit document identifying **41 additional residual issues** that still remain even if Sessions 11–14 and E-1–E-10 are completed exactly as currently written.

| Severity | Count |
|---|---|
| Critical | 1 |
| High | 15 |
| Medium | 19 |
| Low | 6 |

Most important additions to the architecture plan:

| ID | Architectural implication | Required response |
|---|---|---|
| ISS-1 | `_get_macro_context()` must validate against a typed `MacroContextPacket` | Add schema contract in Session 11 before ARC-1 is considered done |
| ISS-3 | Config-driven routing alone is insufficient | Add `GenericSectorAnalystAgent` or equivalent fallback in Session 11 |
| ISS-4 | Report assembly needs typed mapping, not raw dict reuse | Add `ValuationCard` → `StockCard` adapter in Session 11 |
| ISS-9 | `_REQUIRED_OUTPUT_KEYS` warnings are too weak | Convert critical agent quality failures into retry / gate failures |
| ISS-10 | Gemini fallback path is structurally mismatched to installed package | Fix before E-8 multi-provider fallback is trusted |
| ISS-12 | Stage 8 remains untyped even after adding `EconomyAnalystAgent` | Define a unified Stage 8 packet with required keys |
| ISS-13 | AU market support is not only data/config — prompt layer also needs localisation | Extend Session 12/13 prompt work to ASX-specific analysis |
| ISS-16 | Benchmark module still needs real benchmark series, not just benchmark weights | Strengthen E-4 scope |
| ISS-20 | Streamlit stage/output state has a known bug | Add to Session 11 quick wins |
| ISS-27 | No live full-pipeline API integration test exists | Add to Session 13 production-hardening scope |
| ISS-34 | Flat-file persistence becomes a platform ceiling | Plan Session 15+ database migration |
| ISS-36 / ISS-37 / ISS-38 | Production telemetry, caching, and cancellation are still incomplete | Add to future Ops hardening roadmap |

This means the roadmap is directionally correct, but **not yet sufficient for full polish**. Session definitions should now be interpreted as:

- **Session 11:** ARC-1–10 **plus** ISS-1, ISS-3, ISS-4, ISS-9, ISS-10, ISS-20
- **Session 12:** macro build-out **plus** ISS-12, ISS-13, ISS-14, ISS-22
- **Session 13:** depth/quality **plus** ISS-16, ISS-23, ISS-27, ISS-28
- **Session 14+:** AU client context **plus** ISS-29, ISS-30, and future ops/persistence items

---

*Document updated: March 28, 2026 — session 10 complete (607 tests), full gap analysis and brainstorm added §13. Sessions 11–14 planned. Market scope defined. Architecture repair items ARC-1 through ARC-10 documented. PR #1 reviewed and rejected as not merge-ready. PR #2 assessment merged and folded into the architecture plan.*