# Version 6 Agent Specifications and Build Guide

## Purpose
This document defines each agent as if it were a specialist on a real institutional research desk. It is written so an engineering team can implement the pipeline in Codespaces with clear scope boundaries and handoffs.

## Agent roster
### Research agents (9)
1. Research Pipeline Orchestrator
2. Evidence Librarian
3. Sector Analyst - Compute
4. Sector Analyst - Power & Energy
5. Sector Analyst - Infrastructure & Build-out
6. Valuation Analyst
7. Red Team Analyst
8. Associate Reviewer
9. Portfolio Manager

### Platform agents (2)
10. Market Data Ingestor
11. Consensus & Reconciliation Analyst

---

## 1. Research Pipeline Orchestrator
### Mission
Control the workflow, assign coverage, enforce stage order, and prevent premature publication.

### Inputs
- universe list
- config rules
- stage outputs
- reviewer status

### Outputs
- run manifest
- job queue
- stage state transitions
- final publication permission

### Responsibilities
- create research run ID
- load universe and theme map
- dispatch stock coverage to sector agents
- ensure no stage starts before prerequisites are met
- trigger reruns when a gate fails
- own report-day workflow

### Not allowed
- write stock analysis
- set price targets
- override reviewer fail without explicit policy exception

### Success metrics
- zero stage-order violations
- zero publication events on failed runs
- reproducible run logs

---

## 2. Evidence Librarian
### Mission
Create the claim ledger that all downstream prose must map back to.

### Inputs
- company primary documents
- Reuters and regulator sources
- run manifest

### Outputs
- claim ledger
- source registry
- unresolved claims report

### Responsibilities
- enumerate every material claim expected in the report
- define required source tier for each claim
- mark each claim as pass, caveat, or fail
- assign unresolved items to owning analyst

### Claim schema
- claim_id
- ticker
- claim_text
- claim_type
- source_tier_required
- source_url
- source_title
- source_date
- corroborated
- status
- note

### Pass criteria
- every claim has a valid evidence class
- every critical claim has at least one source reference

### Fail criteria
- key business claim lacks source
- claim wording exceeds source language

---

## 3. Sector Analyst - Compute
### Coverage
NVDA, AVGO, TSM, ANET, networking, semis, packaging, compute-adjacent ETFs

### Mission
Translate the compute stack into investable stock notes using only approved claims.

### Required stock template
1. Verified facts
2. Management guidance
3. Market view
4. Analyst judgment
5. Risks and what to watch

### Responsibilities
- analyze competitive position
- map demand drivers to revenue pathways
- identify what the market may still be underpricing
- surface where the story may already be crowded

### Not allowed
- invent consensus
- produce price targets
- cite weak market-data sources for core facts

---

## 4. Sector Analyst - Power & Energy
### Coverage
CEG, VST, NLR, GEV, utilities, nuclear, gas generation, power ETFs

### Mission
Evaluate the generation and power-supply layer with heavy caution around contract language and regulatory claims.

### Special controls
- distinguish contracted PPA revenue from merchant power exposure
- separate official MW figures from inferred demand impact
- flag policy sensitivity, capacity constraints, and commodity exposure

### Not allowed
- compress complex multi-party agreements into misleading single-number soundbites

---

## 5. Sector Analyst - Infrastructure & Build-out
### Coverage
ETN, PWR, HUBB, APH, FIX, NXT, FCX, BHP, electrical, cooling, grid, contractors, materials

### Mission
Own the picks-and-shovels layer and translate physical bottlenecks into investable thesis notes.

### Special controls
- do not overstate ecosystem participation as exclusivity
- differentiate backlog, orders, contracts, and opportunity language
- identify labor, execution, permitting, and build-cycle risks

---

## 6. Valuation Analyst
### Mission
Convert the stock notes into valuation-aware investment cases.

### Inputs
- sector notes
- market snapshots
- consensus snapshots
- ratings trends

### Outputs
- valuation cards
- 1-year target context
- 3-year and 5-year house ranges
- driver decomposition tables
- crowding score

### Required method outputs
- current valuation metrics
- peer-relative assessment
- target source classification
- base / bull / bear logic
- revenue, margin, multiple, and dividend contribution notes

### Hard rules
- only this agent may issue multi-year target ranges
- all 3-year and 5-year targets must be labeled house view
- if 1-year target is consensus-derived, it must say so

### Not allowed
- treat consensus targets as truth
- ignore when current price is already above consensus

---

## 7. Red Team Analyst
### Mission
Try to break the thesis and identify where a correct story can still be a bad trade.

### Outputs
- bear memo per name
- invalidation triggers
- correlated-risk map
- crowding stress note

### Required questions
- what proves the bull case wrong?
- what near-term data point would damage conviction?
- where is the thesis crowded?
- where is there genuine non-consensus upside?
- which positions fail together under a common shock?

### Hard rule
Each stock needs at least three real disconfirming risks, not generic boilerplate.

---

## 8. Associate Reviewer
### Mission
Act as the publication gatekeeper.

### Inputs
- all prior stage outputs
- claim ledger
- reconciliation report
- final draft text

### Outputs
- gate memo
- required corrections list
- final status: pass / pass with disclosure / fail

### Checklist
- each material sentence maps to claim ID
- each number has as-of date
- each target has source class or house-view label
- no undefined or empty audit fields
- all caveat items visible in body text
- no prohibited source use for key facts
- all API-derived fields have timestamps and source IDs

### Hard power
This agent can block publication.

---

## 9. Portfolio Manager
### Mission
Turn the approved research into investable baskets.

### Inputs
- approved stock notes
- valuation cards
- red-team memo
- reviewer gate

### Outputs
- balanced basket
- higher-return basket
- lower-volatility basket
- weights
- inclusion/exclusion memo
- final client-facing report

### Constraints
- max single name weight
- max correlated-theme weight
- required exposure across compute, foundry, power, electrical, and ETF sleeves
- limit highly crowded names if expectation pressure is too high

### Not allowed
- resurrect failed claims
- silently soften red-team conclusions

---

## 10. Market Data Ingestor
### Mission
Pull structured quant data from APIs, normalize it, and store point-in-time snapshots.

### APIs
#### FMP
Use for:
- quotes
- fundamentals
- analyst estimates
- price target summaries
- ratings data

#### Finnhub
Use for:
- recommendation trends
- price targets
- earnings calendar
- EPS surprises
- supplemental estimates metadata

### Outputs
- market snapshot table
- consensus snapshot table
- ratings snapshot table
- earnings event table
- ingest log

### Hard rules
- store raw payload plus normalized fields
- preserve source and timestamp
- never overwrite history without versioning

---

## 11. Consensus & Reconciliation Analyst
### Mission
Resolve or flag disagreements between datasets and protect the report from false precision.

### Inputs
- FMP snapshot
- Finnhub snapshot
- policy thresholds

### Outputs
- reconciliation report
- preferred-source field map
- unresolved disagreement queue

### Core logic
- compare price target medians and ranges
- compare recommendation signals
- compare event dates
- flag stale or obviously broken values
- downgrade confidence when feeds materially diverge

### Status levels
- green
- amber
- red

### Hard rules
- red fields cannot silently flow into final report
- materially divergent figures must be disclosed or manually resolved

---

## Data model
### Core tables
- `runs`
- `universe`
- `claims`
- `sources`
- `market_snapshots`
- `consensus_snapshots`
- `ratings_snapshots`
- `earnings_events`
- `reconciliation_flags`
- `stock_notes`
- `valuation_cards`
- `redteam_memos`
- `portfolio_outputs`
- `reviewer_gates`

## Suggested API field map
### FMP
- symbol
- date
- price
- marketCap
- pe
- evToEbitda
- analyst estimates fields
- price target fields
- ratings fields

### Finnhub
- symbol
- atTime
- recommendation trend counts
- targetHigh / targetLow / targetMean
- epsActual / epsEstimate / surprisePercent
- earnings date

## Workflow timing
### Daily
- ingest APIs
- run reconciliation
- refresh watchlist
- save diffs

### Weekly
- refresh crowding and expectation scores
- update thesis monitor
- rerank shortlist

### Report cycle
- lock universe
- refresh claim ledger
- run analysts
- run valuation
- run red team
- run reviewer gate
- publish only on pass

## Publication package
A final report package should contain:
- executive summary
- methodology note
- source hierarchy disclosure
- stock cards
- valuation table
- portfolio tables
- red-team summary
- self-audit appendix
- claim-register appendix

## Recommended tests for Codespaces build
### Unit tests
- claim schema validation
- source-tier enforcement
- timestamp presence
- house-view labeling
- fail-on-undefined

### Integration tests
- end-to-end run on 3 tickers
- API ingest and reconciliation
- reviewer gate blocks bad output
- final report generator only runs on pass

### Regression tests
- known bad claim gets blocked
- management guidance cannot be upgraded to fact
- target without method tag fails review

## Build order
1. Config and schema
2. FMP ingest
3. Finnhub ingest
4. Reconciliation layer
5. Claim ledger module
6. Analyst output schema
7. Valuation module
8. Red team module
9. Reviewer gate
10. Portfolio/report generator
11. Monitoring and diff engine

## Final implementation stance
The 9 research skills remain the visible expert team.
The 2 new data agents act as shared services beneath them.
That is the cleanest way to preserve the original skill concept while upgrading the pipeline to the standard you actually want.
