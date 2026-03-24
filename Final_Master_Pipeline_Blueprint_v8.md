# Final Master Pipeline Blueprint v8
**Purpose:** Build a public-source, institutional-style AI infrastructure research and portfolio platform in Codespaces.

## What changed vs prior handoff
This v8 package explicitly embeds the previously missing control layers as part of the build:
- Quant risk module
- Scenario / stress-testing module
- Run registry
- Agent / prompt version registry
- Golden regression tests
- Human override / approval logging
- Data QA / lineage checks
- Performance attribution framework (Phase 2 but specified now)

## Design principle
Separate the system into three layers:

### 1) Deterministic platform services
Pure code. No LLM.
- market data ingestion
- consensus ingestion
- reconciliation
- freshness checks
- data QA / lineage
- risk math
- scenario engine math
- DCF engine math
- report assembly templates
- registry logging
- schedulers

### 2) Expert reasoning agents
LLM-powered.
- Research Pipeline Orchestrator
- Evidence Librarian
- Sector Analyst – Compute
- Sector Analyst – Power & Energy
- Sector Analyst – Infrastructure
- Valuation Analyst
- Red Team Analyst
- Associate Reviewer
- Portfolio Manager
- Macro & Regime Strategist
- Political & Geopolitical Risk Analyst

### 3) Governance and control layer
Mixed code + policy.
- self-audit scorecard
- publish gate
- human override log
- prompt / agent versioning
- golden tests
- run registry
- reproducibility and replay

## Core external data
### Mandatory
- FMP API
- Finnhub API

### Optional later
- Estimize API
- internal price/holdings data
- benchmark factor feeds

## MVP target
A system that:
1. ingests and reconciles market/consensus data,
2. builds a claim ledger from primary sources,
3. runs the research agents with structured inputs,
4. runs valuation + risk + red team,
5. audits the entire package,
6. requires explicit pass / caveat / fail outputs,
7. logs the run and publishes only on pass.

## End-state target
A repeatable asset-management research platform with:
- stored run history
- versioned prompts
- repeatable portfolio construction
- risk decomposition
- scenario testing
- performance attribution
- governance trail

## Team / role map

### Platform services
1. Market Data Ingestor
2. Consensus & Reconciliation Service
3. Data QA & Lineage Service
4. Risk Engine
5. Scenario & Stress Engine
6. DCF / Model Engine
7. Report Assembly Service
8. Run Registry Service
9. Scheduler / Monitoring Service
10. Golden Test Harness

### Research agents
1. Research Pipeline Orchestrator
2. Evidence Librarian
3. Sector Analyst – Compute
4. Sector Analyst – Power & Energy
5. Sector Analyst – Infrastructure
6. Valuation Analyst
7. Red Team Analyst
8. Associate Reviewer
9. Portfolio Manager
10. Macro & Regime Strategist
11. Political & Geopolitical Risk Analyst

## Final stage map

### Stage 0 — Configuration & run bootstrap
Owner: Orchestrator + Run Registry Service
Outputs:
- run_id
- active config snapshot
- agent/version snapshot
- dataset credential checks
- date/time context
Gate:
- fail if required secrets, schemas, or thresholds missing

### Stage 1 — Universe definition
Owner: Orchestrator
Outputs:
- approved ticker universe
- subtheme tags
- benchmark set
- exclusion list
Gate:
- fail if universe lacks source coverage or liquidity metadata

### Stage 2 — Data ingestion
Owner: Market Data Ingestor
Inputs:
- FMP
- Finnhub
Outputs:
- raw market snapshots
- raw consensus snapshots
- earnings calendar
- ratings/recommendation snapshots
Gate:
- fail if stale or incomplete feed coverage breaches thresholds

### Stage 3 — Reconciliation
Owner: Consensus & Reconciliation Service
Outputs:
- reconciled snapshot
- field-level green / amber / red flags
- preferred-source resolution
Gate:
- red fields on mandatory data block downstream stages

### Stage 4 — Data QA & lineage
Owner: Data QA & Lineage Service
Checks:
- schema validity
- timestamp validity
- currency sanity
- split / corporate action anomalies
- duplicate records
- lineage completeness
Outputs:
- data quality report
Gate:
- fail if lineage missing or data corruption detected

### Stage 5 — Evidence librarian / claim ledger
Owner: Evidence Librarian
Inputs:
- primary filings
- investor releases
- transcripts
- Reuters / regulator / exchange evidence
- reconciled market data
Outputs:
- claim register
- source register
- evidence classes
Gate:
- no analyst can proceed without claim ledger

### Stage 6 — Sector analysis
Owners:
- Compute Analyst
- Power & Energy Analyst
- Infrastructure Analyst
Outputs:
- four-box stock notes:
  - verified facts
  - management guidance
  - market expectations
  - house view / what market may miss
Gate:
- unsupported claims rejected

### Stage 7 — Valuation & modelling
Owners:
- Valuation Analyst
- DCF / Model Engine
Outputs:
- valuation summary
- bull / base / bear ranges
- relative valuation view
- reverse DCF / implied expectations
- key sensitivities
Gate:
- every target/range must show methodology tag

### Stage 8 — Macro, political, and regime overlay
Owners:
- Macro & Regime Strategist
- Political & Geopolitical Risk Analyst
Outputs:
- macro regime memo
- political risk scoring
- geopolitical dependency map
- policy sensitivity matrix
Gate:
- material unresolved regime risk must be disclosed in final report

### Stage 9 — Quant risk & scenario testing
Owners:
- Risk Engine
- Scenario & Stress Engine
Outputs:
- correlation matrix
- factor concentration
- ETF overlap
- volatility contribution
- scenario stress results
- drawdown risk summary
Gate:
- concentration or stress breaches must be flagged to PM and reviewer

### Stage 10 — Red team
Owner: Red Team Analyst
Outputs:
- falsification memo
- key failure modes
- variant bear cases
Gate:
- minimum three concrete disconfirming risks per top idea

### Stage 11 — Associate review / publish gate
Owner: Associate Reviewer
Outputs:
- PASS / PASS WITH DISCLOSURE / FAIL
- self-audit scorecard
- unresolved issues list
Gate:
- FAIL blocks publication

### Stage 12 — Portfolio construction
Owner: Portfolio Manager
Outputs:
- balanced basket
- higher-return basket
- lower-volatility basket
- weights and rationale
- implementation notes
Gate:
- PM cannot override FAIL from reviewer

### Stage 13 — Report assembly
Owner: Report Assembly Service
Outputs:
- client report
- claim register appendix
- self-audit appendix
- run summary
Gate:
- only pass-approved content may be published

### Stage 14 — Monitoring, registry, and post-run logging
Owners:
- Scheduler / Monitoring Service
- Run Registry Service
Outputs:
- run record
- daily/weekly diffs
- approval history
- human override log
- model drift / prompt drift markers

## Minimum governance requirements
### Mandatory in MVP
- run registry
- prompt / agent version registry
- deterministic reconciliation
- self-audit schema
- golden test suite
- human override log
- data QA / lineage checks
- basic quant risk module

### Phase 2
- fuller factor model
- richer geopolitical scoring
- performance attribution
- benchmark-relative exposure engine
- async execution / scaling
- alternative consensus overlay

## Scoring target
### Current achievable with this design
- Research architecture: 9.2/10
- Evidence discipline: 9.0/10
- Valuation architecture: 8.9/10
- Risk architecture: 8.7/10
- Governance / reproducibility: 8.9/10
- Institutional realism overall: 9.0–9.2/10

## Implementation posture
- services are code-first
- reasoning roles are LLM-first
- everything is versioned
- every run is replayable
- every published claim is traceable
