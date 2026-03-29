# Comprehensive Backend Architecture Assessment
## AI Infrastructure Research & Portfolio Platform — v8.0
### Critical Cross-Analysis + Independent Code Review

> **Date:** March 2026 | **Scope:** Full backend — engine, agents, services, schemas, governance, tests
> **Method:** Synthesis of two independent analyses plus direct code inspection of `engine.py`, `gates.py`, `schemas/`, `agents/`, `services/`

---

## Table of Contents

1. [Meta-Analysis: What Each Review Got Right and Missed](#1-meta-analysis)
2. [Definitive Architecture Description](#2-definitive-architecture-description)
3. [Stage-by-Stage Consolidated Scorecard](#3-stage-by-stage-consolidated-scorecard)
4. [Architecture Dimension Assessment](#4-architecture-dimension-assessment)
5. [Cross-Stage Interaction Analysis](#5-cross-stage-interaction-analysis)
6. [Additional Findings from Code Inspection](#6-additional-findings-from-code-inspection)
7. [Master Scorecard](#7-master-scorecard)
8. [Upgrade Blueprint: 7.8 → 9.0](#8-upgrade-blueprint-78--90)

---

## 1. Meta-Analysis

### What both reviews agreed on

Both analyses independently converged on the same core conclusions, which gives them high confidence:

| Finding | Review A | Review B | Verdict |
|---|---|---|---|
| Overall score range | 7.8/10 | 7.8–8.2/10 | **Confirmed: ~7.9/10** |
| Stage 8 before Stage 7 in code is a good call | ✓ | ✓ | **Confirmed correct** |
| Doc/config/runtime drift is primary ceiling | ✓ | ✓ | **Confirmed — highest priority** |
| Data integrity architecture is a strength | 8.7 | ~8.5 | **Confirmed strong** |
| Governance/gates is a standout design | 8.8 | ~8.8 | **Confirmed strongest area** |
| DCF wiring vs docs is a gap | ✓ | ✓ | **Confirmed gap** |
| PipelineEngine is too monolithic | ✓ | Implied | **Confirmed** |
| Macro grounding vs narrative ambition is a gap | Implied | 5/10 explicit | **Confirmed largest gap** |
| Stage 11 (Publish Gate) is a best design decision | ✓ | ✓ | **Confirmed** |
| More structured cross-stage typed packets needed | ✓ | ✓ | **Confirmed** |

### What Review A did better than Review B

- **Richer qualitative analysis** — more narrative depth on each stage's conceptual design merit
- **Better stage inter-dependency reasoning** — explicitly worked through what should feed what and why
- **Identified Stage 5 (Evidence Ledger) as under-exploited downstream** — a critical observation
- **Named "revision loops" as a structural gap** — the architecture is one-pass; no repair after red-team or review failures
- **Better on the "best vs weakest stages" ranking** — concise, useful operational summary
- **Better discussion of symbiosis vs linearity** — important framing for future development

### What Review B did better than Review A

- **Grounded in specific code artifacts** — referenced `_get_macro_context()`, `MacroContextPacket`, `SECTOR_ROUTING` directly
- **Added `Contract` and `Observability` as explicit scoring dimensions** — more complete assessment framework
- **Explicitly scored multi-tenancy (5.5/10) and cancellation/backpressure (5.5/10)** — operational gaps Review A missed entirely
- **Explicitly scored external macro grounding at 5/10** — the single most important accuracy gap
- **Schema evolution / versioning gap (6/10)** — operational maturity point Review A missed
- **Better on reproducibility as a distinct concern** — noted LLM + vendor data weakens full replay
- **More honest about "accuracy" as a dimension** — Review A blended accuracy with other concerns

### What BOTH reviews missed (found by code inspection)

This is covered in full in Section 6. Key headlines:

| Finding | Impact |
|---|---|
| `ResearchMemory` SQLite FTS5 institutional memory layer | High — cross-run learning, not mentioned |
| `ReportNarrativeAgent` — Session 13 LLM narrative per section | High — fundamentally changes report assembly characterisation |
| ASX/Australian institutional layer (3 separate files) | Medium — market expansion not captured |
| `EconomyAnalystAgent` + `EconomicIndicatorService` + `MacroScenarioService` | High — directly addresses the macro grounding gap |
| `Provenance_service.py` as a dedicated service | Medium — both discussed provenance conceptually but missed the service |
| `_VALIDATION_FATAL: bool = False` on narrative agent | Medium — resilience pattern not discussed |
| `scheduler.py` for batch/scheduled execution | Low-medium — operational capability not noted |
| Formal `CommitteeRecord` with quorum logic in governance schemas | Medium — IC architecture richer than both described |
| Four-tier source tiering in `ClaimLedger` (Tier 1 Primary → Tier 4 House) | Medium — claim provenance more rigorous than both portrayed |

---

## 2. Definitive Architecture Description

### What this backend actually is

This backend is a **15-stage, gate-controlled, hybrid research pipeline** built on:

- A **single orchestrating engine** (`PipelineEngine`) that owns stage execution, gating, shared state, and artifact persistence
- A **deterministic services layer** that handles all computation: DCF, risk/VaR/factor engines, scenario stress, mandate compliance, optimisation, report assembly, and audit
- An **LLM agent layer** for all judgment-intensive work: evidence synthesis, sector reasoning, valuation interpretation, macro/political overlay, quant/FI commentary, adversarial red-teaming, associate review, portfolio management, narrative generation
- A **governance layer** with typed Pydantic schemas as contracts, formal gate checks at every stage, an IC voting schema with quorum requirements, and a `SelfAuditPacket` for explainability

### The precise execution model

```
PipelineEngine.run_full_pipeline()
│
├── Stage 0   Bootstrap           Deterministic — fail fast
├── Stage 1   Universe            Deterministic — scope gate
├── Stage 2   Data Ingestion      Deterministic — async gather + retries
├── Stage 3   Reconciliation      Deterministic — cross-provider consensus
├── Stage 4   Data QA & Lineage   Deterministic — provenance enforcement
├── Stage 5   Evidence Librarian  LLM — claim ledger (4-tier source tiering)
├── Stage 6   Sector Analysis     LLM — 3×parallel specialists + generic fallback
├── Stage 8   Macro & Political   LLM — runs BEFORE Stage 7 (ARC-4 ordering fix)
├── Stage 7   Valuation           LLM + Deterministic DCF — macro-aware
├── Stage 9   Quant Risk          Deterministic engines + LLM commentary
├── Stage 10  Red Team            LLM — adversarial falsification
├── Stage 11  Associate Review    LLM + Hard Gate — fail-closed publish gate
├── Stage 12  Portfolio           LLM + Deterministic optimiser
├── Stage 13  Report Assembly     Deterministic template + ReportNarrativeAgent
└── Stage 14  Monitoring/Audit    Deterministic — always runs
```

**Key architectural truth:** This is not a distributed multi-agent mesh. It is a **linear-gated pipeline with parallel pockets** (Stage 6 sector concurrency, macro-before-valuation reordering) and **engine-mediated context aggregation** rather than direct agent-to-agent dialogue.

That characterisation should be documented explicitly, because calling it a "multi-agent system" creates false performance expectations.

### The three golden rules (as actually implemented)

1. **Deterministic computation stays in code; judgment goes to the LLM** — Verified: DCF, VaR, factor exposure, scenario stress, report assembly are all deterministic services
2. **No stage can run without its upstream gate passing** — Verified: `gates.py` has explicit gate methods for all 15 stages with typed blocking logic
3. **Report assembly is deterministic and uses only approved artifacts** — Verified: `ReportAssemblyService` assembles from stage outputs, with `ReportNarrativeAgent` (Session 13) handling prose — critically, this agent is **non-blocking** (`_VALIDATION_FATAL = False`), meaning report generation cannot be held hostage by a narrative quality failure

---

## 3. Stage-by-Stage Consolidated Scorecard

> Scoring dimensions used: **Design Quality (D)**, **Depth (De)**, **Coverage (C)**, **Accuracy Potential (A)**, **Implementation Quality (I)**, **Importance (Imp)**, **Contract Discipline (Ct)**, **Observability (Ob)**

> Review A and Review B scores are averaged where both assessed; this review's code-informed score is added. Final Score = weighted reconciliation.

---

### Stage 0 — Bootstrap & Configuration

| Dimension | Review A | Review B | This Review | Final |
|---|---|---|---|---|
| Design Quality | 8.5 | 8/10 | 8.0 | **8.2** |
| Depth | 7.5 | 6 | 6.5 | **6.5** |
| Coverage | 8.0 | 8 | 8.0 | **8.0** |
| Accuracy Potential | 8.0 | 8 | 8.0 | **8.0** |
| Implementation Quality | 7.6 | 8 | 8.0 | **7.9** |
| Importance | 9.0 | 10 | 9.5 | **9.5** |
| Contract Discipline | — | 7 | 7.0 | **7.0** |
| Observability | — | 7 | 7.0 | **7.0** |

**Blended Stage Score: 7.8/10**

**Key observations:**
- Both reviews correctly note this is cheap to do right but catastrophic if wrong
- No LLM cost until this passes — good fail-fast discipline
- Config discipline across the repo is inconsistent (noted by both) — YAML is not always the single source of truth
- `run_id` (UUID-based) enables full artifact traceability across runs — underrated by both reviews
- **This review adds:** `PromptRegistry` is initialised here (confirmed in engine.py imports), making prompt versioning a bootstrap-time concern — excellent design not noted by either prior analysis

---

### Stage 1 — Universe Definition

| Dimension | Review A | Review B | This Review | Final |
|---|---|---|---|---|
| Design Quality | 7.8 | — | 7.5 | **7.5** |
| Depth | 6.8 | 5 | 5.5 | **5.5** |
| Coverage | 6.9 | 7 | 7.0 | **7.0** |
| Accuracy Potential | 7.5 | 7 | 7.0 | **7.0** |
| Implementation Quality | 7.2 | 7 | 7.0 | **7.0** |
| Importance | 7.8 | 8 | 8.0 | **8.0** |
| Contract Discipline | — | 6 | 6.0 | **6.0** |
| Observability | — | 6 | 6.0 | **6.0** |

**Blended Stage Score: 6.8/10**

**Key observations:**
- Both reviews agree this stage is functional but not sophisticated
- `SECTOR_ROUTING` externalised to `config/loader.py` (ARC-5) is a meaningful improvement — noted only by Review B
- **This review adds:** `sector_analyst_asx.py` exists as a dedicated ASX specialist, meaning the sector routing has at least one geography-aware extension path already in place. Neither prior analysis noted this.
- Gate 1 only checks minimum ticker count and deduplication — a weak gate for a "scope definition" stage
- Missing: portfolio coverage constraints, mandate-level universe restrictions, market cap/liquidity floors as hard gates

---

### Stage 2 — Data Ingestion

| Dimension | Review A | Review B | This Review | Final |
|---|---|---|---|---|
| Design Quality | 8.3 | — | 8.0 | **8.0** |
| Depth | 7.4 | 7 | 7.5 | **7.3** |
| Coverage | 7.7 | 8 | 7.5 | **7.7** |
| Accuracy Potential | 7.8 | 7 | 7.5 | **7.4** |
| Implementation Quality | 7.5 | 8 | 7.5 | **7.7** |
| Importance | 9.4 | 10 | 9.5 | **9.6** |
| Contract Discipline | — | 8 | 8.0 | **8.0** |
| Observability | — | 7 | 7.0 | **7.0** |

**Blended Stage Score: 7.8/10**

**Key observations:**
- Async gather + retries inside `MarketDataIngestor` correctly treat this as an inherently unreliable I/O operation
- Two providers (FMP + Finnhub) is a minimum, not a robust configuration — single-provider failure is survivable but the fallback logic quality matters more than the count
- **This review adds:** `qualitative_data_service.py` and `sector_data_service.py` exist as dedicated services — these extend ingestion beyond price/consensus into qualitative and sector-specific data layers. Neither prior analysis mentioned this capability, which matters for Stage 5 claim quality
- Central accuracy ceiling: this stage's output quality bounds everything downstream. API normalisation is not the same as institutional data validation

---

### Stage 3 — Reconciliation

| Dimension | Review A | Review B | This Review | Final |
|---|---|---|---|---|
| Design Quality | 9.0 | — | 9.0 | **9.0** |
| Depth | 8.0 | 6 | 7.0 | **7.0** |
| Coverage | 8.1 | 7 | 7.5 | **7.5** |
| Accuracy Potential | 8.8 | 7 | 8.0 | **8.0** |
| Implementation Quality | 8.4 | 7 | 7.5 | **7.6** |
| Importance | 9.2 | 9 | 9.0 | **9.1** |
| Contract Discipline | — | 8 | 8.0 | **8.0** |
| Observability | — | 6 | 6.0 | **6.0** |

**Blended Stage Score: 7.9/10**

**Key observations:**
- Both reviews call this one of the best architectural decisions: forcing data skepticism before any narrative work begins
- `ReconciliationReport.has_blocking_reds()` is a hard gate — no soft-fail on data divergence. This is correct.
- **This review adds:** `gate_3_reconciliation` in code only blocks on `has_blocking_reds()`. The field-level policy determining what constitutes a "red" lives in thresholds config (`configs/thresholds.yaml`). Config drift in that file could silently weaken the gate — a subtle operational risk neither prior analysis flagged
- Threshold-based reconciliation is appropriate now; context-aware reconciliation (using sector/macro context to adjust thresholds) would be the next level

---

### Stage 4 — Data QA & Lineage

| Dimension | Review A | Review B | This Review | Final |
|---|---|---|---|---|
| Design Quality | 9.1 | — | 8.5 | **8.7** |
| Depth | 8.3 | 6 | 7.0 | **7.0** |
| Coverage | 8.0 | 7 | 7.5 | **7.5** |
| Accuracy Potential | 8.9 | 6 | 7.5 | **7.5** |
| Implementation Quality | 8.2 | 7 | 7.0 | **7.4** |
| Importance | 9.4 | 9 | 9.0 | **9.1** |
| Contract Discipline | — | 7 | 7.0 | **7.0** |
| Observability | — | 6 | 6.0 | **6.0** |

**Blended Stage Score: 7.6/10**

**Key observations:**
- `gate_4_data_qa` in code is surprisingly thin: it calls `report.is_passing()` and iterates `report.issues`. The sophistication lives entirely inside `DataQALineageService.run()` — which makes the gate a passthrough rather than an independent check
- **This review adds:** `provenance_service.py` exists as a dedicated service separate from `data_qa_lineage.py`. This is an important design separation neither prior analysis noted: QA verifies data integrity, Provenance tracks data lineage. The conceptual distinction matters for auditability
- Corporate actions (splits, special dividends) and FX normalisation are institutional-grade requirements not currently visible in the gate logic
- Both reviews correctly flag that later stages sometimes receive dict dumps rather than fully typed provenance packets — lineage can break at handoff boundaries

---

### Stage 5 — Evidence Librarian / Claim Ledger

| Dimension | Review A | Review B | This Review | Final |
|---|---|---|---|---|
| Design Quality | 9.3 | — | 9.2 | **9.2** |
| Depth | 8.7 | 7 | 8.0 | **8.0** |
| Coverage | 8.1 | 8 | 8.0 | **8.0** |
| Accuracy Potential | 8.9 | 6 | 7.5 | **7.5** |
| Implementation Quality | 7.8 | 7 | 8.0 | **7.6** |
| Importance | 9.5 | 10 | 9.5 | **9.7** |
| Contract Discipline | — | 8 | 8.5 | **8.5** |
| Observability | — | 6 | 6.5 | **6.5** |

**Blended Stage Score: 8.1/10**

**Key observations:**
- The claim schema (`claims.py`) is more rigorous than either review described. Key design elements found in code:
  - **Four-tier source tiering**: `SourceTier.TIER_1_PRIMARY` → `TIER_4_HOUSE` — enforces epistemic provenance at schema level
  - **Five evidence classes**: PRIMARY_FACT, MGMT_GUIDANCE, INDEPENDENT_CONFIRMATION, CONSENSUS_DATAPOINT, HOUSE_INFERENCE — strong epistemic classification
  - **Corroboration tracking**: `corroborated: bool` and `corroboration_source` — specific cross-validation record
  - **Per-claim confidence**: HIGH/MEDIUM/LOW at the claim level
  - **Per-claim status**: PASS/CAVEAT/FAIL with `caveat_note` — fine-grained gatekeeping
- Gate 5 specifically blocks on FAIL claims AND on empty ledger — correct enforcement
- **Both reviews agreed:** downstream stages don't fully exploit this ledger. This remains the single highest-ROI architectural improvement available
- **This review adds:** `ResearchMemory` (see Section 6) can persist claim ledgers across runs — creating institutional memory of past claims. This is a major capability neither analysis noted

---

### Stage 6 — Sector Analysis

| Dimension | Review A | Review B | This Review | Final |
|---|---|---|---|---|
| Design Quality | 8.8 | — | 8.5 | **8.6** |
| Depth | 8.1 | 8 | 8.0 | **8.0** |
| Coverage | 8.3 | 8 | 8.0 | **8.1** |
| Accuracy Potential | 7.8 | 6 | 7.0 | **7.0** |
| Implementation Quality | 8.0 | 8 | 8.0 | **8.0** |
| Importance | 9.0 | 9 | 9.0 | **9.0** |
| Contract Discipline | — | 7 | 7.5 | **7.5** |
| Observability | — | 7 | 7.0 | **7.0** |

**Blended Stage Score: 8.0/10**

**Key observations:**
- Three specialist agents (Compute, Power/Energy, Infrastructure) + `GenericSectorAnalystAgent` as fallback — good design
- **This review adds:** `sector_analyst_asx.py` exists as a fourth specialist for Australian-listed names. Neither prior analysis noted this, implying geographic extensibility is already real, not just planned
- The `FourBoxOutput` schema is the typed output contract for sector work — good discipline
- The absence of a **cross-sector synthesis step** is the primary weakness here. Three parallel analysts produce parallel outputs; the engine aggregates them but does not synthesise disagreements or cross-sector bottleneck dependencies (e.g. power constraints shared between Compute and Infrastructure)
- Both reviews correctly note this architecture is parallel but not symbiotic

---

### Stage 8 — Macro & Political Overlay (runs before Stage 7)

| Dimension | Review A | Review B | This Review | Final |
|---|---|---|---|---|
| Design Quality | 8.7 | — | 8.5 | **8.5** |
| Depth | 7.9 | 6 | 7.5 | **7.1** |
| Coverage | 7.8 | 6 | 7.0 | **6.9** |
| Accuracy Potential | 7.8 | 5 | 6.0 | **6.3** |
| Implementation Quality | 8.0 | 7 | 7.5 | **7.5** |
| Importance | 8.7 | 8 | 9.0 | **8.9** |
| Contract Discipline | — | 6 | 7.0 | **6.5** |
| Observability | — | 6 | 6.5 | **6.5** |

**Blended Stage Score: 7.3/10**

**Key observations:**
- The correct execution order (Stage 8 before Stage 7) is verified in code at line 953: `# ARC-4: Stage 8 now runs before Stage 7, so macro context is available here`. This is a deliberate, documented engineering decision
- `MacroContextPacket` typed schema exists and is produced by `_get_macro_context()` — good typed cross-stage contract
- **Accuracy is the key concern** (Review B: 5/10; this review: 6/10): when the macro agent has no real-time rates, CPI, or yield curve data it is generating macro "judgment" from LLM priors. That is a major accuracy ceiling
- **This review adds:** Session 12 added `EconomyAnalystAgent`, `EconomicIndicatorService`, and `MacroScenarioService` (confirmed in engine.py imports at lines 93-100). This is a direct response to the macro grounding problem — but how deeply these are wired into Stage 8's prompt context vs being post-hoc additions needs explicit verification. If fully wired, the macro grounding score rises to 7+/10. If partially wired, that gap remains
- Political risk's propagation downstream remains conceptually weaker than macro — there is no `PoliticalContextPacket` equivalent with typed downstream consumption

---

### Stage 7 — Valuation & Modelling

| Dimension | Review A | Review B | This Review | Final |
|---|---|---|---|---|
| Design Quality | 8.9 | — | 9.0 | **9.0** |
| Depth | 8.4 | 8 | 8.0 | **8.1** |
| Coverage | 7.5 | 8 | 7.5 | **7.7** |
| Accuracy Potential | 8.0 | 6 | 7.0 | **7.0** |
| Implementation Quality | 6.8 | 8 | 7.0 | **7.3** |
| Importance | 9.3 | 10 | 9.5 | **9.6** |
| Contract Discipline | — | 8 | 8.0 | **8.0** |
| Observability | — | 7 | 7.0 | **7.0** |

**Blended Stage Score: 7.8/10**

**Key observations:**
- Both reviews identified the DCF wiring gap: `DCFEngine` is instantiated and the `ValuationCard` schema is well-defined, but whether a real DCF output is injected into the valuation agent's prompt context (rather than just informing a separate service call) requires explicit verification
- The design intent is excellent: deterministic DCF first, LLM interpretation second — this is the right architecture
- **Session 13:** economy analysis + sector data are now passed into Stage 7 for DCF context (confirmed at engine.py line 955: "Session 13: Pass economy_analysis + sector data to give valuation agent DCF context")
- `ValuationCard` schema with methodology tagging is a strong institutional pattern — forces analysts to declare their method
- The macro awareness (via `_get_macro_context()` running against Stage 8's prior execution) is now correctly wired — one of the best incremental improvements in the codebase history

---

### Stage 9 — Quant Risk & Scenario Testing

| Dimension | Review A | Review B | This Review | Final |
|---|---|---|---|---|
| Design Quality | 9.0 | — | 9.0 | **9.0** |
| Depth | 8.5 | 8 | 8.5 | **8.5** |
| Coverage | 8.1 | 9 | 8.5 | **8.5** |
| Accuracy Potential | 8.3 | 7 | 7.5 | **7.6** |
| Implementation Quality | 7.9 | 8 | 8.0 | **8.0** |
| Importance | 9.1 | 9 | 9.0 | **9.0** |
| Contract Discipline | — | 8 | 8.0 | **8.0** |
| Observability | — | 8 | 8.0 | **8.0** |

**Blended Stage Score: 8.3/10**

**Key observations:**
- Both reviews agree this is a backend strength: thick deterministic service layer with multiple quant engines (Factor, VaR, Scenario, Position Sizing, Portfolio Optimisation)
- `gate_9_risk` explicitly allows concentration breaches as **warnings rather than blockers** — a deliberate governance decision that forces disclosure without blocking publication. This is the correct institutional pattern and was not noted by either prior analysis
- `RiskPacket` schema structures the deterministic output → LLM commentary pipeline cleanly
- Both `QuantResearchAnalystAgent` and `FixedIncomeAnalystAgent` exist as separate agents — good specialisation
- The main weakness is that scenario severity inputs may be synthetic/fallback-heavy rather than driven by real macro regime data. This connects back to Stage 8's grounding problem

---

### Stage 10 — Red Team Analysis

| Dimension | Review A | Review B | This Review | Final |
|---|---|---|---|---|
| Design Quality | 9.2 | — | 9.0 | **9.1** |
| Depth | 8.0 | 7 | 7.5 | **7.5** |
| Coverage | 7.8 | 7 | 7.5 | **7.4** |
| Accuracy Potential | 8.5 | 6 | 7.5 | **7.5** |
| Implementation Quality | 7.6 | 7 | 7.5 | **7.4** |
| Importance | 9.0 | 9 | 8.5 | **8.8** |
| Contract Discipline | — | 7 | 7.5 | **7.3** |
| Observability | — | 6 | 6.5 | **6.5** |

**Blended Stage Score: 7.6/10**

**Key observations:**
- Both reviews identify the same gap: `gate_10_red_team` requires `all_have_min_falsifications` — the right structural requirement — but the depth of falsification is not independently verifiable from the gate alone (the agent self-reports)
- `RedTeamAssessment` schema exists in `schemas/portfolio.py` — typed, which is good
- The architecture is structurally correct: separate red-team from construction, run after quant risk so adversarial analysis can incorporate stress results
- **The revision loop problem:** both reviews noted the system is one-pass. Red team identifies holes; review either passes or blocks. There is no mechanism for a controlled "thesis repair" between red team and review. This limits the red team from being truly generative rather than just an approval-layer challenge
- **This review adds:** The quality of red team output scales directly with the quality of upstream structured inputs. The more typed packets (claims, sector cards, valuation cards, risk packet) the red team agent consumes, the better its falsification coverage. This creates a direct incentive to improve all upstream contracts

---

### Stage 11 — Associate Review / Publish Gate

| Dimension | Review A | Review B | This Review | Final |
|---|---|---|---|---|
| Design Quality | 9.4 | — | 9.5 | **9.5** |
| Depth | 8.8 | 7 | 8.0 | **8.0** |
| Coverage | 8.4 | 8 | 8.5 | **8.3** |
| Accuracy Potential | 8.7 | 6 | 7.5 | **7.4** |
| Implementation Quality | 8.5 | 7 | 8.0 | **7.8** |
| Importance | 9.8 | 10 | 9.8 | **9.9** |
| Contract Discipline | — | 7 | 8.0 | **7.5** |
| Observability | — | 7 | 7.5 | **7.5** |

**Blended Stage Score: 8.2/10**

**Key observations:**
- Both reviews agree unanimously: fail-closed publish gate is one of the best architectural decisions in the entire system. It is the correct institutional instinct
- `AssociateReviewResult.is_publishable` drives `gate_11_review` — typed, hard gate. Portfolio cannot be constructed if this fails
- `gate_12_portfolio` has `review_passed: bool = True` as a guard — the PM explicitly cannot override the reviewer's FAIL. This is an important governance separation of duties
- **This review adds:** The `CommitteeRecord` schema in `governance.py` with `quorum_met`, `required_votes` (3), and formal `CommitteeVoteRecord` entries suggests an IC layer above the associate review — a proper investment committee architecture. Neither prior analysis noted this depth. Whether this IC is called from the engine in all paths or only in specific mandate configurations needs verification
- The quality of review depends on how much structured context the reviewer receives. If the reviewer is consuming typed packets (claims, sector cards, risk packet, red team assessments) rather than prose summaries, quality is significantly higher

---

### Stage 12 — Portfolio Construction

| Dimension | Review A | Review B | This Review | Final |
|---|---|---|---|---|
| Design Quality | 8.8 | — | 8.5 | **8.6** |
| Depth | 8.6 | 7 | 8.0 | **7.9** |
| Coverage | 8.4 | 8 | 8.0 | **8.1** |
| Accuracy Potential | 8.0 | 5 | 6.5 | **6.5** |
| Implementation Quality | 8.1 | 8 | 8.0 | **8.0** |
| Importance | 9.1 | 9 | 9.0 | **9.0** |
| Contract Discipline | — | 7 | 7.5 | **7.5** |
| Observability | — | 8 | 8.0 | **8.0** |

**Blended Stage Score: 8.0/10**

**Key observations:**
- Multiple optimisation modes (risk parity, min-var, max-Sharpe), mandate compliance, ESG integration, and rebalancing logic make this one of the most service-rich stages
- `PortfolioVariant` schema (multiple variants required by gate_12 — minimum 3) is a strong design: forces scenario thinking at the portfolio level
- **This review adds:** `superannuation_mandate.py` and `australian_tax_service.py` suggest Australian-specific mandate constraints are a first-class concern. Neither prior analysis mentioned this — it implies the mandate framework is designed to handle diverse institutional constraints, not just a generic set
- The "accuracy" concern (5–6.5/10) is primarily path-dependent: portfolio outputs are only as good as the upstream narratives. This is a legitimate concern but framing it as a Stage 12 problem misattributes it; the portfolio manager is correctly consuming what it is given
- `MandateComplianceEngine` enforcing hard vs soft limits from `MandateRule.hard_limit` is a clean pattern

---

### Stage 13 — Report Assembly

| Dimension | Review A | Review B | This Review | Final |
|---|---|---|---|---|
| Design Quality | 9.0 | — | 9.0 | **9.0** |
| Depth | 7.5 | 6 | 8.0 | **7.8** |
| Coverage | 7.8 | 7 | 8.0 | **7.9** |
| Accuracy Potential | 8.8 | 7 | 8.5 | **8.1** |
| Implementation Quality | 8.0 | 7 | 8.5 | **8.2** |
| Importance | 8.7 | 8 | 8.5 | **8.4** |
| Contract Discipline | — | 7 | 8.0 | **7.5** |
| Observability | — | 7 | 7.5 | **7.5** |

**Blended Stage Score: 8.1/10**

**Key observations:**
- Both reviews called deterministic report assembly "the right call." This review agrees and upgrades the implementation score based on Session 13's addition
- **This review adds a significant upgrade:** `ReportNarrativeAgent` (Session 13) fundamentally changes the characterisation of this stage. It is no longer a "deterministic template filler" but a hybrid: deterministic structure with LLM-generated institutional prose. Critically, `_VALIDATION_FATAL = False` means narrative failures are non-blocking — the report can still publish with fallback prose. This is the correct resilience design for a report assembly stage
- The five narrative sections (`executive_summary`, `methodology`, `valuation_appendix`, `risk_appendix`, `self_audit_appendix`) are generated in a single LLM call — efficient and consistent
- Neither prior analysis mentioned this Session 13 addition, meaning their characterisation of report assembly as "simpler than upstream deserves" is now outdated

---

### Stage 14 — Monitoring & Logging

| Dimension | Review A | Review B | This Review | Final |
|---|---|---|---|---|
| Design Quality | 8.7 | — | 8.5 | **8.5** |
| Depth | 7.8 | 7 | 7.5 | **7.4** |
| Coverage | 8.0 | 8 | 8.0 | **8.0** |
| Accuracy Potential | 8.2 | 6 | 7.5 | **7.2** |
| Implementation Quality | 8.1 | 8 | 8.0 | **8.0** |
| Importance | 8.5 | 7 | 8.0 | **7.8** |
| Contract Discipline | — | 8 | 8.0 | **8.0** |
| Observability | — | 8 | 8.0 | **8.0** |

**Blended Stage Score: 7.9/10**

**Key observations:**
- Both reviews agree: correct to always execute, critical for failed runs where post-mortem data matters most
- `SelfAuditPacket` + `AuditExporter` + `RunRegistry` + `PerformanceTracker` + `MonitoringEngine` is a rich set of monitoring artifacts
- **This review adds:** `scheduler.py` suggests this stage connects to a broader operational framework for batch/scheduled runs — not just fire-and-forget. Neither prior analysis noted this
- Attribution paths noted by Review B are still partially proxy-based on synthetic or partial series — the honest score for accuracy potential

---

## 4. Architecture Dimension Assessment

### Consolidated dimension scores (reconciling both reviews + code inspection)

| Dimension | Review A | Review B | This Review | **Final Score** |
|---|---|---|---|---|
| Conceptual Architecture | 8.6 | — | 8.5 | **8.5** |
| Implementation Fidelity | 7.5 | — | 7.5 | **7.5** |
| Stage Design Quality | 8.5 | — | 8.5 | **8.5** |
| Data Integrity Architecture | 8.7 | ~8.5 | 8.5 | **8.6** |
| Governance & Controls | 8.8 | ~8.8 | 9.0 | **8.9** |
| Agent Architecture / Coordination | 7.4 | 7.5 | 7.5 | **7.5** |
| Service Layer Design | 8.0 | 8.5 | 8.5 | **8.3** |
| Schema Discipline | 8.2 | 7.0 | 8.0 | **7.8** |
| Testing Depth | 8.1 | 8.0 | 8.0 | **8.0** |
| Config/Documentation Fidelity | 6.7 | — | 6.5 | **6.5** |
| Operational Maturity | 7.1 | 7.5 | 7.5 | **7.4** |
| Multi-tenancy / Multi-mandate | — | 5.5 | 5.5 | **5.5** |
| Cancellation & Backpressure | — | 5.5 | 5.0 | **5.2** |
| Cross-run Institutional Memory | — | — | 7.5 | **7.5** |
| External Data Grounding | — | 5.0 | 6.0 | **6.0** |
| Schema Evolution / Versioning | — | 6.0 | 6.0 | **6.0** |
| Reproducibility | — | 7.0 | 7.0 | **7.0** |
| Auditability / Explainability | 8.6 | 7.5 | 8.0 | **8.1** |
| Scalability of Current Design | 7.4 | — | 7.0 | **7.1** |

### Architecture design assessment (commentary)

**Strongest areas (8.5+):**

1. **Governance & Controls (8.9)** — explicitly modelled, typed, fail-closed. The IC voting schema with quorum requirements is institutional-grade. This is a genuine differentiator.

2. **Conceptual Architecture (8.5)** — the research lifecycle model is sound: validate → ingest → reconcile → structure evidence → reason → challenge → approve → construct → assemble → audit. This is a recognisable and defensible institutional workflow.

3. **Stage Design Quality (8.5)** — the conceptual decomposition is strong. Most stage boundaries are intentional and meaningful, not arbitrary.

4. **Data Integrity Architecture (8.6)** — three dedicated stages (Reconciliation, QA/Lineage, Evidence) before any LLM work begins is excellent defensive design.

**Material gaps (below 7.0):**

1. **Multi-tenancy / Multi-mandate (5.5)** — `RunRequest` schema exists in `schemas/run_request.py` and `client_profile.py` schema exists, suggesting the intent is there. But first-class multi-tenant engine threading is not complete.

2. **Cancellation & Backpressure (5.2)** — a common gap for long-running async pipeline architectures. Partial results, run cancellation mid-stage, and graceful degradation are not fully addressed.

3. **External Data Grounding (6.0)** — this is the single largest gap between narrative ambition and implementation reality. Session 12's macro economy services improve this but the full wiring depth needs verification.

4. **Schema Evolution (6.0)** — Pydantic models are excellent for structure but there is no explicit schema versioning strategy. As the pipeline evolves, old artifacts and new schemas will drift.

5. **Config/Documentation Fidelity (6.5)** — the "as-described" vs "as-executed" gap. This is a maintenance and trust problem more than a functionality problem, but it matters for operators and auditors.

---

## 5. Cross-Stage Interaction Analysis

### Current interaction model

The pipeline today is **linear + engine-mediated**: agents don't talk to each other; they talk to the engine's accumulated `stage_outputs` dict. The only real-time symbiosis is Stage 6's parallel sector execution and Stage 8's pre-computation for Stage 7.

### Interaction map (what passes what to where)

```
Stage 5 claims ─────────────────────────────────────────► Stage 11 review (weak wiring)
                                                           Stage 10 red team (weak wiring)
                                                           Stage 6 sector (conceptual only)

Stage 6 sector outputs ──────────────────────────────────► Stage 7 valuation (wired)
                                                           Stage 9 risk (partial)
                                                           Stage 12 portfolio (wired)

Stage 8 macro packet ────────────────────────────────────► Stage 7 valuation (WIRED - ARC-4)
                                                           Stage 9 risk (partial)
                                                           Stage 11 review (partial)
                                                           Stage 12 portfolio (partial)

Stage 9 risk packet ─────────────────────────────────────► Stage 10 red team (partial)
                                                           Stage 11 review (wired)
                                                           Stage 12 portfolio (wired)

Stage 10 red team ───────────────────────────────────────► Stage 11 review (wired)
                                                           [NOTHING ELSE — one-pass gap]
```

### Where deeper interaction would deliver the most value

**1. Claim Ledger → Stages 6, 7, 10, 11 (HIGH PRIORITY)**

Both reviews independently identified this. The Stage 5 claim ledger with four-tier source tiering and per-claim confidence ratings is architecturally excellent but underexploited. Every downstream stage consuming claims should:
- Require specific claim IDs to be cited in reasoning outputs
- Force unresolved FAIL or CAVEAT claims to be explicitly addressed
- Reject sector or valuation narratives that contradict HIGH-confidence PASS claims

Estimated quality uplift: **+0.4 to stage scores across 4 stages**

**2. Cross-Sector Synthesis Step after Stage 6 (HIGH PRIORITY)**

A lightweight typed synthesis step (not a full agent) that identifies:
- Shared bottlenecks across sectors (power constraints, supply chain)
- Cross-sector confidence conflicts
- AI demand sensitivity correlation estimates

This improves portfolio coherence and reviewer context quality significantly.
Estimated quality uplift: **+0.3 to Stage 6, +0.2 to Stage 12**

**3. Red Team → Thesis Repair Loop (MEDIUM PRIORITY)**

After Stage 10 identifies material contradictions, a controlled "targeted re-run" of the affected sector or valuation stage (for specific tickers only) would improve final output quality. This should:
- Only trigger for RED or HIGH-severity red team findings
- Only revise the specific affected assertion
- Not be a free-form re-analysis

Estimated quality uplift: **+0.3 to Stage 10 effectiveness**

**4. Portfolio Optimiser ↔ PM Agent Constraint Feedback (MEDIUM PRIORITY)**

When mandate constraints make an optimisation infeasible, the PM agent should receive a structured `InfeasibilityReport` rather than a generic failure. This enables reasoned constraint relaxation rather than silent fallback.
Estimated quality uplift: **+0.2 to Stage 12**

**5. MacroContextPacket → All Economically Sensitive Stages (LOWER PRIORITY BUT EASY)**

Macro already flows into Stage 7. Explicit typing of macro consumption into Stage 9 scenario severity inputs, Stage 10 scenario selection, and Stage 12 regime-conditional weights would close the remaining macro propagation gaps. This is low-effort relative to benefit.
Estimated quality uplift: **+0.2 across stages**

### Risk assessment for deeper interaction

| Risk | Mitigation |
|---|---|
| Circular reasoning between agents | Keep all interactions engine-mediated, never direct agent-to-agent |
| Audit complexity from non-linear paths | Require all interaction edges to be typed contracts with stage attribution |
| Longer run times | Selective triggering only (e.g. RED findings only for repair loops) |
| Harder debugging | Keep repair loops as separate named sub-stages in engine logging |

---

## 6. Additional Findings from Code Inspection

> These are findings from direct code inspection not captured in either prior analysis.

### Finding 1: SQLite FTS5 Institutional Memory Layer (`research_memory.py`)

**Discovered:** `ResearchMemory` is a SQLite FTS5-backed institutional memory store. It persists past reports, claim ledgers, thesis records, and agent outputs across runs in a searchable corpus.

**Significance:** This is a high-impact capability. It means:
- Past claim validation can inform current run evidence assessment
- Historical thesis records can flag if a thesis is being repeated without new evidence
- Agent outputs from prior runs provide a calibration baseline
- `memory_injection.py` provides the mechanism for injecting this into agent prompts

**Assessment:** Neither prior analysis mentioned this layer. The architecture currently supports cross-run learning without requiring a vector database (FTS5 is deterministic and auditable). This is a thoughtful infrastructure choice.

**Gap:** It is unclear how consistently the memory layer is populated and queried across runs, and whether `memory_injection.py` is called in production paths or remains an optional enhancement.

**Score uplift for auditability:** +0.3 to institutional memory dimension

---

### Finding 2: `ReportNarrativeAgent` Changes Report Assembly Characterisation

**Discovered:** `ReportNarrativeAgent` (Session 13) generates institutional prose for all five major report sections in a single LLM call. It replaces hardcoded template strings in `ReportAssemblyService`.

**Significance:** Both prior analyses described Stage 13 as "deterministic template filling" — this was accurate before Session 13 but is no longer accurate. Stage 13 is now a **hybrid** stage: deterministic structure + LLM prose. The `_VALIDATION_FATAL = False` flag means narrative failure cannot block publication, which is the correct design.

**Gap:** The prompt content of `ReportNarrativeAgent` (not reviewed in depth here) determines whether the executive summary actually reflects the quantitative findings or hallucinated about them. The quality of the structured input packet passed to this agent is critical.

---

### Finding 3: Australian Institutional Layer (3 files, 0 mentions in prior analyses)

**Discovered:** `sector_analyst_asx.py`, `australian_tax_service.py`, `superannuation_mandate.py`

**Significance:** The backend has a real institutional mandate layer for Australian superannuation funds, complete with Australian tax rules and an ASX-specific sector specialist. This:
- Extends the mandate compliance framework to a real-world institutional client type
- Implies the `RunRequest` / `client_profile` schemas are being used for genuine client differentiation
- Demonstrates the multi-mandate architecture is not theoretical

**Assessment:** This is an underadvertised capability. The documentation (ARCHITECTURE.md, PIPELINE_STAGES.md) does not mention it.

---

### Finding 4: Session 12 Macro Economy Services Address Core Grounding Gap

**Discovered:** `EconomyAnalystAgent`, `EconomicIndicatorService`, `MacroScenarioService`, and `EconomicIndicators` / `EconomyAnalysis` / `MacroScenario` schemas (all confirmed in engine.py imports at lines 93-100).

**Significance:** Review B scored external macro grounding at 5/10 and called it "the biggest real PM office gap." Session 12 has directly addressed this with:
- A dedicated economy analyst agent
- An economic indicator service (rates, CPI, etc.)
- A macro scenario service for structured regime modelling

**Remaining question:** How deeply are these wired into Stage 8's prompt? Are the economic indicators injected as structured data or does the macro agent still rely primarily on LLM priors? If fully wired, the external grounding score rises from 6.0 to 7.5+. Verifying this wiring depth is the highest-priority architecture verification task.

---

### Finding 5: `gate_9` Concentration Breaches as Warnings, Not Blockers

**Discovered:** In `gates.py`, `gate_9_risk` explicitly notes: "Concentration breaches are flagged but don't necessarily block — They must be disclosed in the report."

**Significance:** This is a deliberate and correct institutional governance choice — concentration risk doesn't prevent publication, it mandates disclosure. This is more nuanced than either prior analysis described. It also creates a **disclosure obligation** that must propagate into Report Assembly — a cross-stage contract that should be explicitly verified.

---

### Finding 6: `scheduler.py` — Batch/Scheduled Execution Capability

**Discovered:** `scheduler.py` exists in the services layer.

**Significance:** Neither prior analysis noted this. It implies the pipeline can run on a schedule (e.g. post-market daily runs, quarterly rebalancing triggers) rather than only as an interactive session. This has operational maturity implications.

---

### Finding 7: Formal IC Voting Schema with Quorum Requirements

**Discovered:** `CommitteeRecord` in `governance.py`:
- `quorum_met: bool`
- `required_votes: int = 3`
- `CommitteeVoteRecord` with individual votes and rationale
- Vote options: APPROVE, APPROVE_WITH_CONDITIONS, REJECT, ABSTAIN

**Significance:** Both prior analyses mentioned IC at 7.5/10 for audit trail but described it generically. The actual schema has a proper voting record structure with quorum enforcements. Whether the current engine calls this IC layer in all publication paths or only in specific mandate configurations determines whether this is operational or aspirational.

---

### Finding 8: Four-Tier Source Tiering is More Rigorous Than Described

**Discovered:** `ClaimLedger` in `claims.py` with:
- Four-tier source classification (Primary → Independent → Consensus → House)
- Five evidence classes (PRIMARY_FACT → HOUSE_INFERENCE)
- Per-claim corroboration tracking (boolean + source record)
- Per-claim confidence (HIGH/MEDIUM/LOW)
- Per-claim status (PASS/CAVEAT/FAIL) with `caveat_note`

**Significance:** Both prior analyses described the claim ledger in general terms. The actual schema is considerably more rigorous — it is closer to a formal epistemic ledger than a simple fact store. The challenge is that this richness can only be realised if the `EvidenceLibrarianAgent` consistently populates all fields with quality data. The gate only enforces minimal conditions (non-empty, no FAIL claims).

---

### Finding 9: `provenance_service.py` Separate from `data_qa_lineage.py`

**Discovered:** Two separate data provenance services: `DataQALineageService` (QA validation) and `Provenance_service.py` (provenance tracking).

**Significance:** This separation is architecturally correct — QA checks correctness, Provenance tracks origin. Both prior analyses discussed provenance as a concept but treated it as part of Stage 4. Having a standalone service means provenance can be updated progressively as data flows through the pipeline, not just stamped at Stage 4.

---

## 7. Master Scorecard

### Final Overall Scores (Reconciled)

| Category | Review A | Review B | This Review | **Final** |
|---|---|---|---|---|
| Conceptual architecture | 8.6 | — | 8.5 | **8.5** |
| Implementation fidelity | 7.5 | 7.5 | 7.5 | **7.5** |
| Stage design quality | 8.5 | — | 8.5 | **8.5** |
| Data integrity architecture | 8.7 | ~8.5 | 8.5 | **8.6** |
| Governance / controls | 8.8 | ~8.8 | 9.0 | **8.9** |
| Agent coordination / symbiosis | 7.4 | 7.5 | 7.5 | **7.5** |
| Service layer design | 8.0 | 8.5 | 8.5 | **8.3** |
| Schema discipline | 8.2 | 7.0 | 8.0 | **7.8** |
| Testing depth | 8.1 | 8.0 | 8.0 | **8.0** |
| Config / documentation fidelity | 6.7 | — | 6.5 | **6.5** |
| Operational maturity | 7.1 | 7.5 | 7.5 | **7.4** |
| Cross-run institutional memory | — | — | 7.5 | **7.5** |
| External data grounding | — | 5.0 | 6.0 | **6.0** |
| Multi-tenancy / multi-mandate | — | 5.5 | 5.5 | **5.5** |
| Cancellation / backpressure | — | 5.5 | 5.2 | **5.2** |
| Schema evolution / versioning | — | 6.0 | 6.0 | **6.0** |
| Reproducibility | — | 7.0 | 7.0 | **7.0** |
| Auditability / explainability | 8.6 | 7.5 | 8.2 | **8.1** |
| Scalability of current design | 7.4 | — | 7.2 | **7.2** |
| Institutional / research professionalism | 8.5 | 8.5 | 8.5 | **8.5** |

### **Overall Backend Architecture Score: 7.9/10**

Both independent reviews landed at 7.8/10. This review agrees: 7.9/10 after factoring in Session 12 and Session 13 additions not captured in either prior assessment.

### Score justification

**Why not 9/10:**
- Macro grounding is real but underverified (Session 12 wiring depth unknown)
- Multi-tenancy and cancellation are structural gaps
- Doc/config/runtime fidelity remains a consistent -1.3 drag
- Some critical stage handoffs still use dict dumps rather than fully typed contracts
- The architecture is one-pass; revision loops do not exist

**Why not 6/10:**
- The governance architecture is genuinely institutional-grade
- The data integrity pipeline is correct and thoughtful
- The claim ledger schema is more rigorous than most comparable systems
- The service layer is real: DCF, VaR, factor, scenario, mandate, ESG, optimisation are not toy implementations
- Session 12+13 additions show active architectural improvement
- Cross-run memory architecture is a real capability

**Best single descriptor:** *High-ambition, institutionally-minded backend with genuine strengths in governance and data integrity, held back primarily by implementation-to-design fidelity and external data grounding depth.*

---

## 8. Upgrade Blueprint: 7.9 → 9.0

Ranked by: **Impact / Effort ratio** (highest first)

---

### Priority 1 — Verify and complete Session 12 macro wiring (Impact: HIGH, Effort: LOW-MED)

**What:** Confirm `EconomicIndicatorService` and `EconomyAnalystAgent` outputs are injected as structured data into Stage 8's prompt context — not just run as separate services.

**Specific action:** Stage 8 agent prompt should receive: real current rates, CPI, yield curve shape, credit spreads, and PMI data as typed fields — not free text.

**Impact:** Raises macro accuracy from 6.0 to 7.5+. Cascades into better scenario severity in Stage 9 and better review context in Stage 11.

**Score uplift:** +0.3 overall

---

### Priority 2 — Force Claim Ledger consumption into Stages 6, 7, 10, 11 (Impact: HIGH, Effort: MED)

**What:** Require sector analysts, valuation analyst, red team, and associate reviewer to:
1. Receive the claim ledger as a structured typed input (not optional)
2. Cite specific claim IDs in their reasoning outputs
3. Explicitly address all CAVEAT and FAIL claims for their covered names

**Specific action:** Add a `required_claims: list[str]` field to `FourBoxOutput`, `ValuationCard`, and `RedTeamAssessment` schemas. Enforce citation in gates 6, 7, and 10.

**Impact:** Dramatically improves traceability, reduces hallucination surface, makes red team and review more adversarially effective.

**Score uplift:** +0.3 overall

---

### Priority 3 — Add a cross-sector synthesis substage (Impact: HIGH, Effort: MED)

**What:** After Stage 6's three parallel analysts complete, add a lightweight synthesis step (not a new full agent — a structured merge) that produces:
- Shared bottlenecks identified across ≥2 sectors
- Cross-sector confidence conflicts
- AI demand correlation estimates across the universe

**Specific action:** Implement `CrossSectorSynthesisService` (deterministic aggregation of sector outputs). Feed its output to Stage 7, Stage 9, and Stage 12.

**Impact:** More coherent portfolio, better risk scenarios, stronger reviewer context.

**Score uplift:** +0.2 overall

---

### Priority 4 — Fix doc/config/runtime fidelity (Impact: MED, Effort: LOW)

**What:** Specifically:
1. Update `PIPELINE_STAGES.md` to reflect actual execution order (Stage 8 before Stage 7)
2. Document the `ReportNarrativeAgent` in architecture docs
3. Document Australian institutional layer (ASX analyst, superannuation mandate)
4. Align `configs/thresholds.yaml` with gate logic in `gates.py`

**Impact:** Auditors, new engineers, and operators trust what they read. Reduces "architecture drift" score from 6.5 to 8.0+.

**Score uplift:** +0.2 to documentation fidelity

---

### Priority 5 — Add controlled thesis repair loop after Stage 10 (Impact: MED, Effort: MED-HIGH)

**What:** After Stage 10 red team, for names flagged RED or with ≥3 high-severity falsifications, trigger a targeted `ThesisRepairAgent` call that:
- Receives: affected ticker, specific red team findings, original sector/valuation card
- Produces: a revised card with explicit responses to each falsification challenge
- Is stamped as "REV-1" in the artifact registry

**Specific action:** Gate 10 could produce a `repair_required: list[str]` field that engine checks before proceeding to Stage 11.

**Impact:** Significantly improves the quality and defensibility of final outputs for contested names.

**Score uplift:** +0.2 to Stage 10, Stage 11 quality

---

### Priority 6 — Add typed cross-stage output versioning (Impact: MED, Effort: MED)

**What:** Every stage output schema should carry a `schema_version: str` field. Artifacts written to disk and loaded in subsequent runs should be version-checked.

**Specific action:** Add a `SchemaVersionMixin` base model with `schema_version: str = "1.0"`. Require all stage output models to inherit it.

**Impact:** Prevents silent schema drift between pipeline versions. Makes artifact reproducibility testable.

**Score uplift:** +0.2 to schema evolution/reproducibility

---

### Priority 7 — Decompose PipelineEngine into stage modules (Impact: MED, Effort: HIGH)

**What:** `engine.py` is 1,961 lines managing 15 stages, ~80 imports, ~40 service instances, and all cross-stage state. This makes it the highest-risk file in the codebase.

**Specific action:** Extract each `stage_N_*` method into its own `StageN` class (or module) that takes `stage_outputs` as input and returns a typed `StageNResult`. PipelineEngine becomes an orchestrator that calls `StageN.execute()`.

**Impact:** Dramatically improves testability, reduces merge conflicts, and isolates stage regression.

**Score uplift:** +0.3 to scalability, +0.2 to implementation quality

---

### Priority 8 — First-class RunRequest multi-tenancy (Impact: MED, Effort: HIGH)

**What:** `RunRequest` and `client_profile` schemas exist but multi-tenant mandate threading through the engine is not fully first-class.

**Specific action:** Ensure `PipelineEngine.__init__` accepts a `ClientProfile` that sets: mandate rules, universe restrictions, ESG filters, and report format preferences. All stage logic reads from this profile rather than hardcoded defaults.

**Impact:** Commercial viability for multiple fund types (retail, institutional, superannuation, family office).

**Score uplift:** +0.5 to multi-tenancy dimension

---

### Projected score after top 4 priorities

| Priority | Score Uplift | Cumulative |
|---|---|---|
| Current baseline | — | 7.9 |
| P1: Macro wiring complete | +0.3 | 8.2 |
| P2: Claim ledger consumption | +0.3 | 8.5 |
| P3: Cross-sector synthesis | +0.2 | 8.7 |
| P4: Doc/config fidelity | +0.2 | 8.9 |
| P5–P8: Advanced improvements | +0.3 | **9.2** |

---

## Closing Verdict

### Bottom line (consolidated from both reviews + this assessment)

> *This is a serious, institutionally-minded research pipeline backend with genuine strengths in governance architecture, data integrity, and service layer design. It is not a toy demo — the claim ledger four-tier source tiering, fail-closed publish gates, IC voting schema, and deterministic-before-judgment pipeline design all reflect real institutional thinking.*

> *The primary ceilings are: external data grounding depth, implementation-to-design fidelity, the engine's monolithic scale, and the absence of controlled revision loops after adversarial challenge. These are all fixable with targeted incremental work — none require rearchitecting the foundation.*

> *The foundation is sound. The upgrade path is clear. The gap between 7.9/10 and 9.0/10 is achievable.*

**Best phrase:** Strong institutional spine, execution fidelity in progress.

**Recommended first action:** Verify and document Session 12 macro service wiring depth — highest ROI, lowest risk, and resolves the single largest gap identified independently by both prior analyses.

---

*Assessment conducted March 2026. Scores reflect institutional research + quantitative + governance expectations. Direct code inspection scope: `engine.py` (1,961 lines), `gates.py` (238 lines), `schemas/` (15 files), `agents/` (15 files), `services/` (35 files).*
