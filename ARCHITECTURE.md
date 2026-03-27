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
10. [Directory Map](#10-directory-map)

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

## 10. Directory Map

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

*Document auto-generated from codebase analysis — March 27, 2026*
