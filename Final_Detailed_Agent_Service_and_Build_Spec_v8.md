# Final Detailed Agent, Service, and Build Spec v8

## 1. Build philosophy
This system should be built as a research-and-risk platform, not a prompt chain.

### Golden rules
1. Deterministic work stays in code.
2. Judgment work goes to LLM agents.
3. Every stage emits typed outputs.
4. Every run is logged.
5. Every publish action is gated.
6. Every material claim must be traceable.

## 2. Recommended implementation approach
### Orchestration
Use plain Python orchestration first.
- no LangChain required for MVP
- each LLM agent is a callable module with:
  - system prompt
  - input schema
  - output schema
  - retry / validation wrapper

### Storage
Recommended:
- SQLite or Postgres for metadata and registry
- parquet for snapshots and large tables
- local artifact folder for generated reports

### Scheduling
Recommended:
- cron or GitHub Actions for monitoring jobs
- manual CLI trigger for full report builds in MVP

## 3. Services vs agents

## A. Deterministic services

### A1. Market Data Ingestor
Purpose:
- ingest FMP and Finnhub data into canonical raw tables
Functions:
- fetch_quotes()
- fetch_ratios()
- fetch_analyst_estimates()
- fetch_price_targets()
- fetch_recommendation_trends()
- fetch_earnings_calendar()
Outputs:
- raw_fmp_snapshot
- raw_finnhub_snapshot
Controls:
- request budget handling
- retry logic
- stale data detection

### A2. Consensus & Reconciliation Service
Purpose:
- compare FMP and Finnhub and classify divergence
This should be code, not an LLM.
Required config:
- price_drift_amber_pct
- price_drift_red_pct
- target_divergence_amber_pct
- target_divergence_red_pct
- estimate_divergence_amber_pct
- estimate_divergence_red_pct
- stale_data_hours
Output example:
- field_name
- source_a
- source_b
- preferred_source
- status = green|amber|red
- reviewer_required Y/N

### A3. Data QA & Lineage Service
Purpose:
- prevent garbage-in errors
Checks:
- field completeness
- duplicate rows
- malformed dates
- currency/unit mismatches
- outlier values
- lineage key existence
Output:
- data_quality_report
- lineage_report

### A4. DCF / Model Engine
Purpose:
- deterministic valuation math
Features:
- scenario assumptions input
- WACC sensitivity
- terminal growth sensitivity
- margin path sensitivity
- capex/FCF scenarios
Outputs:
- DCF table
- sensitivity tables
- reverse DCF values
Rules:
- engine computes; agent interprets

### A5. Risk Engine
Purpose:
- compute quantitative portfolio risk
Functions:
- rolling correlation matrix
- covariance matrix
- ETF overlap matrix
- contribution to variance
- single-name / subtheme concentration
- benchmark beta estimates if available
Outputs:
- risk packet
- concentration report
- correlation heatmap data

### A6. Scenario & Stress Engine
Purpose:
- deterministic scenario propagation
Scenarios to include:
- AI capex slowdown
- higher rates
- power permitting delays
- export-control escalation
- recession / industrial slowdown
- energy-price shock
Outputs:
- per-name scenario impacts
- portfolio scenario summary

### A7. Run Registry Service
Purpose:
- log every run and replay context
Fields:
- run_id
- timestamp
- universe
- config hash
- agent versions
- prompt versions
- dataset versions
- status
- outputs generated
- final gate outcome

### A8. Report Assembly Service
Purpose:
- compile final report from approved sections only
Rules:
- no unpublished content from failed stages
- auto-append self-audit
- auto-append claim register

### A9. Scheduler / Monitoring Service
Purpose:
- recurring diff checks
Cadence:
- daily data refresh
- weekly watchlist refresh
- report-day full refresh
Outputs:
- alert log
- diff summary
- revalidation flags

### A10. Golden Test Harness
Purpose:
- regression testing
Test categories:
- claim classification tests
- gating tests
- reconciliation tests
- portfolio output stability tests
- known-case report tests

## B. LLM agents

### B1. Research Pipeline Orchestrator
Purpose:
- manage stage sequencing and pass structured inputs
Must not:
- invent evidence
- override deterministic red flags
Inputs:
- universe
- config
- stage outputs
Outputs:
- stage plan
- run summary
- escalation notes

### B2. Evidence Librarian
Purpose:
- build claim ledger before narrative
Required output per claim:
- claim_id
- ticker
- claim_text
- evidence_class
- source_url
- source_date
- corroborated Y/N
- confidence
Hard rule:
- must distinguish fact, guidance, consensus, and house inference

### B3. Sector Analyst – Compute
Purpose:
- analyze semis, custom silicon, networking, packaging
Output structure:
- verified facts
- management guidance
- market expectations
- what market may miss
- key disconfirming risks

### B4. Sector Analyst – Power & Energy
Purpose:
- analyze utilities, power generation, nuclear, electrical demand chain

### B5. Sector Analyst – Infrastructure
Purpose:
- analyze cooling, electrical equipment, contractors, data centres, grid buildout

### B6. Valuation Analyst
Purpose:
- interpret model outputs, not generate raw arithmetic
Must use:
- DCF engine
- relative valuation tables
- reverse DCF outputs
Must label:
- methodology
- sensitivity
- confidence level
Cannot:
- present single-point fair value without ranges

### B7. Macro & Regime Strategist
Purpose:
- assign current regime and macro sensitivities
Outputs:
- regime classification
- key macro variables
- regime winners / losers
- rates and cyclical sensitivities

### B8. Political & Geopolitical Risk Analyst
Purpose:
- assess export controls, Taiwan risk, tariffs, permitting, nuclear policy, election effects
Outputs:
- policy dependency score
- geopolitical dependency score
- jurisdiction map
- key event triggers

### B9. Red Team Analyst
Purpose:
- break the thesis
Required:
- minimum 3 falsification paths per top idea
- identify story/valuation mismatch risk
- identify consensus crowding risk

### B10. Associate Reviewer
Purpose:
- enforce publication standards
Checks:
- source hygiene
- unresolved caveats
- stale data
- wording overreach
- methodology labeling
Outputs:
- PASS / PASS WITH DISCLOSURE / FAIL
- issues requiring revision
- self-audit packet

### B11. Portfolio Manager
Purpose:
- construct portfolios from approved research
Must produce:
- balanced basket
- higher-return basket
- lower-volatility basket
Must consider:
- concentration
- correlation
- risk budget
- implementation feasibility
Cannot:
- override FAIL status

## 4. Required schemas

### Claim register schema
- claim_id
- run_id
- ticker
- claim_text
- evidence_class
- source_id
- corroborated
- confidence_score
- status

### Source register schema
- source_id
- url
- source_type
- tier
- published_date
- accessed_at
- notes

### Self-audit schema
- run_id
- source_tier_mix
- claim_counts_pass
- claim_counts_caveat
- claim_counts_fail
- stale_data_summary
- unresolved_items_count
- publishability_score
- institutional_ceiling_statement

### Human override schema
- override_id
- run_id
- approver
- stage
- reason
- original_status
- override_status
- timestamp

### Prompt registry schema
- agent_name
- prompt_version
- prompt_hash
- changed_at
- owner
- regression_status

### Golden test schema
- test_id
- category
- input_fixture
- expected_output_rule
- last_run
- pass_fail

## 5. Recommended file/folder structure
project_root/
  configs/
    pipeline.yaml
    thresholds.yaml
  prompts/
    orchestrator/
    evidence_librarian/
    sector_compute/
    sector_power/
    sector_infrastructure/
    valuation/
    macro/
    geopolitical/
    red_team/
    reviewer/
    portfolio_manager/
  services/
    ingest/
    reconcile/
    data_qa/
    dcf/
    risk/
    scenario/
    registry/
    assembly/
    monitoring/
    tests/
  schemas/
  storage/
  reports/
  notebooks/
  scripts/
  cli/

## 6. Build order
### Phase 1 — Core runnable spine
1. config loader
2. FMP ingest
3. Finnhub ingest
4. reconciliation service
5. run registry
6. evidence librarian input/output schema
7. one sector analyst
8. reviewer gate
9. report assembly

### Phase 2 — Full research team
10. all three sector analysts
11. valuation analyst + DCF engine
12. red team
13. portfolio manager
14. self-audit appendix

### Phase 3 — Risk and governance
15. risk engine
16. scenario engine
17. macro strategist
18. geopolitical analyst
19. golden tests
20. human override log
21. scheduler/monitoring

### Phase 4 — Learning loop
22. performance attribution
23. research memory manager
24. benchmark-relative analysis
25. async scale improvements

## 7. Minimum threshold examples
- price_drift_amber_pct: 0.5
- price_drift_red_pct: 2.0
- target_divergence_amber_pct: 5.0
- target_divergence_red_pct: 15.0
- estimate_divergence_amber_pct: 5.0
- estimate_divergence_red_pct: 20.0
- stale_data_hours: 24
- mandatory_source_tier_for_core_facts: Tier1_or_Tier2
- max_unresolved_caveats_for_publish: 0 if FAIL-class, <=3 if DISCLOSURE-class

## 8. What the system can and cannot claim
### Can claim
- public-source institutional-style workflow
- repeatable research-and-risk platform
- stronger-than-single-LLM research process

### Cannot claim
- Bloomberg / FactSet equivalence
- personalized investment advice
- fully institutional consensus history
- broker-note-complete coverage

## 9. Success criteria
A successful v8 implementation should:
- run end-to-end from CLI
- persist every stage output
- block publication on failed evidence or data QA
- generate reproducible reports
- log run context and overrides
- produce risk-aware portfolios, not just idea lists
