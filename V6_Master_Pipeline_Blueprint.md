# Version 6 Research Pipeline Blueprint

## Purpose
Build a public-source, institutional-style research system for AI infrastructure investing that is credible enough to present to sophisticated clients, while being honest that it is **not** Bloomberg / FactSet / LSEG grade. The system should maximize factual reliability, valuation discipline, repeatability, and auditability.

This blueprint merges:
- the stronger **role separation** and writing structure from the V5 document
- the stronger **system architecture, data layer, reconciliation logic, and monitoring design** from the earlier Version 4 work

## Target standard
### What this system should achieve
- Strong public-source factual reliability
- Clear separation of facts, management guidance, consensus, and house view
- Explicit claim-level provenance
- Repeatable portfolio construction
- Machine-readable data ingest and history storage
- A hard publication gate that blocks weak outputs

### What it will not honestly achieve without licensed terminal data
- Broker-by-broker estimate history
- Full consensus revision history across all sell-side shops
- True Bloomberg / FactSet / LSEG historical comps and event workflows
- Institutional messaging/network effects

## Team model
Treat the system as an 11-agent team:

### Core research committee (9 agents)
1. Research Pipeline Orchestrator
2. Evidence Librarian
3. Sector Analyst - Compute
4. Sector Analyst - Power & Energy
5. Sector Analyst - Infrastructure & Build-out
6. Valuation Analyst
7. Red Team Analyst
8. Associate Reviewer
9. Portfolio Manager

### Platform support agents (2 new agents)
10. Market Data Ingestor
11. Consensus & Reconciliation Analyst

The 9 research agents produce the investment view. The 2 platform agents supply and validate the machine-readable quantitative layer.

## Operating principles
1. **No single agent can both assert a fact and approve its own fact.**
2. **No core business claim can rely only on a retail aggregator.**
3. **No management statement can be silently upgraded into fact.**
4. **No final report can publish with unresolved placeholders, missing audit fields, or unlabeled house views.**
5. **All prices, targets, and valuation fields must carry an as-of date.**
6. **Consensus indicators are context, not truth.**
7. **Three-year and five-year targets are always house view unless explicitly stated otherwise.**

## Source hierarchy
### Tier 1 - Primary
Use for core business facts only.
- 10-K / 10-Q / annual report
- earnings release
- investor deck
- official transcript / webcast
- exchange filing
- official company IR release
- official counterparty release

### Tier 2 - Independent confirmation
Use to corroborate major catalysts and disputed claims.
- Reuters
- government or regulator sources
- DOE / EIA / IEA / FERC / ISO / RTO style sources
- exchange-hosted notices
- major high-quality business press when clearly reporting a primary event

### Tier 3 - Structured market data
Use for market context, not proof of business facts.
- FMP API
- Finnhub API
- Estimize optional overlay

### Tier 4 - House outputs
Use only for internal modeling and final portfolio judgment.
- scenario analysis
- expected return bands
- multi-year price targets
- ranking logic
- final weights

## Data stack
### Required APIs
#### FMP
Use as the primary machine-readable market and estimates feed.
- quotes
- ratios
- analyst estimates
- price targets
- ratings and ratings history
- fundamentals

#### Finnhub
Use as the secondary quant feed.
- recommendation trends
- price targets
- EPS surprises
- earnings calendar
- estimate-related metadata

### Optional later overlay
#### Estimize
Use only if you want an alternative-consensus signal.
Do not make it a core dependency for Version 6.

## Core system outputs
- claim ledger
- source registry
- market snapshots
- consensus snapshots
- ratings snapshots
- reconciliation report
- stock scorecards
- red-team memos
- portfolio run artifacts
- final report package
- self-audit scorecard

## Stage map
### Stage 0 - Universe definition
Owner: Orchestrator
Output: approved research universe with theme buckets and peer groups
Gate: all names must have adequate primary-source coverage and liquidity

### Stage 1 - Evidence capture
Owner: Evidence Librarian
Support: Market Data Ingestor
Output: claim ledger and source registry
Gate: every material claim classified and tagged

### Stage 2 - Quant ingest
Owner: Market Data Ingestor
Output: prices, multiples, estimates, target summaries, ratings trends, event calendar
Gate: successful pull and timestamping from FMP and Finnhub

### Stage 3 - Quant reconciliation
Owner: Consensus & Reconciliation Analyst
Output: reconciled market snapshot, source disagreement flags, preferred-field rules
Gate: all red flags either resolved or labeled for manual review

### Stage 4 - Sector analysis
Owners in parallel:
- Compute Analyst
- Power & Energy Analyst
- Infrastructure Analyst
Output: four-box stock notes
Gate: each name has verified facts, guidance, market view, and analyst judgment sections

### Stage 5 - Valuation
Owner: Valuation Analyst
Output: expectation score, valuation crowding score, 1/3/5-year house ranges, driver decomposition
Gate: each target must show what drives it and what could break it

### Stage 6 - Red team challenge
Owner: Red Team Analyst
Output: bear cases, invalidation criteria, scenario stress notes
Gate: every stock has at least three disconfirming paths

### Stage 7 - Review and publication gate
Owner: Associate Reviewer
Output: integration memo and pass/fail result
Gate: no FAIL claims, no unlabeled caveats, no undefined fields

### Stage 8 - Portfolio construction and report synthesis
Owner: Portfolio Manager
Output: balanced portfolio, higher-return portfolio, lower-volatility portfolio, plus final report
Gate: all statements must inherit evidence labels from prior stages

### Stage 9 - Post-publication monitoring
Owners: Orchestrator + Market Data Ingestor + Consensus & Reconciliation Analyst
Output: daily snapshot diffs, watchlist changes, target changes, rating changes, event calendar refresh
Gate: all stale fields refreshed before re-issue

## Stage detail
### Stage 0 - Universe definition
The Orchestrator defines:
- theme buckets: compute, foundry, networking, cooling, electrical, grid, generation, contractors, materials, data centers, ETFs
- regions and currencies
- liquidity threshold
- minimum disclosure quality
- exclusion rules for weakly disclosed names

Deliverables:
- `universe_master.csv`
- `theme_map.yaml`
- `peer_groups.yaml`

### Stage 1 - Evidence capture
The Evidence Librarian builds the claim ledger **before narrative writing**.

Each claim must include:
- claim ID
- ticker
- claim text
- evidence class: primary fact / management guidance / independent confirmation / consensus datapoint / house inference
- required tier
- source URL or citation reference
- source date
- confidence status: pass / caveat / fail
- corroborated yes/no
- owner agent

Hard rule:
A claim marked FAIL cannot appear in downstream prose.

### Stage 2 - Quant ingest
The Market Data Ingestor polls APIs and stores dated snapshots.

Minimum fields:
- ticker
- timestamp
- price
- market cap
- EV if available
- trailing P/E
- forward P/E if available
- EV/EBITDA if available
- analyst target low / median / high
- recommendation trend metrics
- earnings date
- surprise metrics

Hard rule:
All fields must retain feed origin and as-of time.

### Stage 3 - Quant reconciliation
The Consensus & Reconciliation Analyst compares FMP and Finnhub outputs.

Rules:
- quote drift above threshold -> amber or red flag
- target divergence above threshold -> disclose range or choose preferred source by rule
- ratings disagreement -> classify as disagreement, not fact
- missing fields -> fallback logic or manual review

Output classes:
- green: aligned
- amber: minor disagreement, safe to use with note
- red: manual resolution required

### Stage 4 - Sector analysis
Each sector analyst writes only within its coverage scope.

Required stock structure:
1. Verified facts
2. Management guidance
3. Market view
4. Analyst judgment
5. Key risks

Not allowed:
- target setting
- unlabeled price predictions
- vague TAM inflation
- overclaiming partner announcements as hard demand

### Stage 5 - Valuation
The Valuation Analyst is the **only** role allowed to set return bands and multi-year targets.

Required outputs per stock:
- current valuation snapshot
- peer-relative valuation
- own-history note if available
- expectation pressure score
- valuation crowding score
- base / bull / bear range
- driver decomposition
- explicit house-view label

### Stage 6 - Red team
The Red Team must try to break the thesis, not merely list generic risks.

Required outputs:
- what could make the thesis wrong
- what evidence in the next two quarters would prove the bear case
- key correlated risks across the portfolio
- names where the story is true but the entry may still be weak

### Stage 7 - Review and gate
The Associate Reviewer is a true publish controller.

Mandatory checks:
- every material sentence maps to a claim ID
- every number has a date
- every target has a method tag
- no unresolved FAIL claims
- no `undefined` or empty audit fields
- no retail-source-only core claim
- all caveats visible in body text

### Stage 8 - Portfolio construction
The Portfolio Manager builds three variants:
- balanced institutional basket
- higher expected return basket
- lower-volatility basket

Constraints:
- max single-stock weight
- max theme weight
- max crowding score
- required representation across compute, manufacturing, power, electrical, and ETFs
- optional currency/regional balance

### Stage 9 - Monitoring
This stage turns the system into an operating platform, not a one-off document.

Daily jobs:
- refresh FMP snapshot
- refresh Finnhub snapshot
- store diffs
- flag rating / target / earnings-date changes

Weekly jobs:
- rerun crowding and expectation scores
- review top risk deltas
- refresh watchlist

Report-day jobs:
- revalidate claim ledger for top names
- rerun reconciliation
- rerun reviewer gate
- regenerate report package

## Governance
### Publication status codes
- PASS
- PASS WITH DISCLOSURE
- FAIL

### Fail conditions
A final report must fail if any of the following occur:
- unresolved fail claims remain
- targets appear without [HOUSE VIEW] or equivalent tag
- consensus is presented as truth
- management guidance is presented as fact
- no as-of date on market data
- stale quote data beyond policy threshold
- placeholders remain in final body

## Recommended file structure for Codespaces
```text
research-pipeline/
  README.md
  config/
    pipeline.yaml
    source_hierarchy.yaml
    peer_groups.yaml
  data/
    raw/
    processed/
  docs/
    methodology/
    outputs/
  prompts/
    agents/
  src/
    orchestrator/
    ingestion/
    reconciliation/
    evidence/
    analysis/
    valuation/
    redteam/
    review/
    portfolio/
    reporting/
  tests/
```

## Recommended score target
### Current realistic ceiling without terminal data
- 8.6 to 8.9 / 10 if built well

### Why not 9.3+
Because clean broker consensus history, revision depth, and premium comp data remain structurally unavailable without licensed data.

## Final design decision
The strongest merged design is:
- **V5 role architecture and writing discipline**
- **Version 4 data layer, reconciliation logic, monitoring loop, and hard publish gates**
- **FMP + Finnhub as core APIs**
- **Estimize optional later**

That is the Version 6 standard this build should target.
