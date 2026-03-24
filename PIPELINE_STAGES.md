# Pipeline Stage Documentation
## AI Infrastructure Research Pipeline — v8.0

This document describes every stage of the 14-stage research pipeline: its purpose,
layer type, inputs, process, outputs, and the design rationale behind it.

---

## Architecture overview

The pipeline is divided into three distinct layers. Every stage belongs to exactly one:

| Layer | Type | Description |
|-------|------|-------------|
| **Deterministic Platform** | Code only | Math, schema validation, data reconciliation — no LLM |
| **Expert Reasoning Agents** | LLM (Claude) | Judgment, interpretation, structured prose analysis |
| **Governance & Control** | Mixed | Quality gates, publication decisions, self-audit |

The golden rule: *deterministic work stays in code; judgment work goes to the LLM.*

---

## Stage flow diagram

```
[0] Bootstrap & Configuration
        ↓
[1] Universe Definition
        ↓
[2] Data Ingestion          ← Deterministic
[3] Reconciliation          ← Deterministic
[4] Data QA & Lineage       ← Deterministic
        ↓
[5] Evidence Librarian / Claim Ledger   ← LLM ★
        ↓
[6] Sector Analysis                     ← LLM ★
        ↓
[7] Valuation & Modelling               ← LLM ★
        ↓
[8] Macro & Political Overlay           ← LLM ★
        ↓
[9] Quant Risk & Scenario Testing       ← LLM ★ (metrics deterministic, narrative LLM)
        ↓
[10] Red Team Analysis                  ← LLM ★
        ↓
[11] Associate Review / Publish Gate    ← LLM ★ + Governance gate
        ↓
[12] Portfolio Construction             ← LLM ★
        ↓
[13] Report Assembly                    ← Deterministic template + all stage outputs
```

---

## Stage 0 — Bootstrap & Configuration

**Layer:** Deterministic  
**Agent / Service:** None — pure configuration  
**Dependencies:** None

### Purpose
Initialise the run environment before any data or LLM work begins. Every downstream
stage reads from the bootstrap output to ensure all components use the same settings,
model, run ID, and timestamp.

### Process
1. Generate a unique `run_id` (format: `DEMO-XXXXXXXX`) using `uuid4`.
2. Record the model name, ticker list, temperature, and data source mode.
3. Set `ANTHROPIC_API_KEY` in the environment so all downstream LLM calls can resolve it.
4. Stamp the run start time in UTC ISO-8601 format.
5. Validate that mandatory configuration is present (API key, at least one ticker).
6. Return a configuration manifest that is attached to the final report appendix.

### Inputs
- API key (from UI sidebar)
- Model selection (`claude-opus-4-5` / `claude-sonnet-4-5` / `claude-haiku-4-5`)
- Ticker list (from universe selection)
- Temperature setting

### Outputs
```json
{
  "run_id": "DEMO-A1B2C3D4",
  "model": "claude-opus-4-5",
  "tickers": ["NVDA", "CEG", "PWR"],
  "data_source": "Demo mode — illustrative data",
  "config_valid": true,
  "timestamp": "2026-03-24T10:00:00Z"
}
```

### Design rationale
Separating bootstrap from data work means any configuration error is caught immediately,
before costly LLM API calls are made. The run_id enables full reproducibility — every
artifact can be traced back to a specific run with known configuration.

---

## Stage 1 — Universe Definition

**Layer:** Deterministic  
**Agent / Service:** Universe Registry  
**Dependencies:** Stage 0 (run config), mock_data / live market data

### Purpose
Formally define the approved research universe for this run. Every subsequent agent
works only from the approved universe list — this acts as the authorisation gate
for which securities can appear in the final report.

### Process
1. Receive the ticker list from Stage 0.
2. For each ticker, look up the canonical company record from `MARKET_SNAPSHOTS`
   (demo) or the live data registry (production).
3. Assign each ticker to its sub-theme: `compute`, `power_energy`, or `infrastructure`.
4. Stamp each entry as `approved: true` (in production, this would require a registry
   check against the approved ticker whitelist).
5. Return the structured universe manifest that all agents will reference.

### Inputs
- Ticker list from Stage 0
- Market snapshot registry (company names, sub-themes)

### Outputs
```json
{
  "universe": [
    {"ticker": "NVDA", "company": "NVIDIA Corporation", "subtheme": "compute", "approved": true},
    {"ticker": "CEG", "company": "Constellation Energy", "subtheme": "power_energy", "approved": true},
    {"ticker": "PWR", "company": "Quanta Services", "subtheme": "infrastructure", "approved": true}
  ],
  "total": 3
}
```

### Design rationale
Explicit universe approval prevents ad-hoc ticker expansion mid-pipeline. In production,
this gate would enforce compliance rules (e.g., no restricted securities, approved analyst
coverage only). The sub-theme classification drives which sector analyst receives each
security in Stage 6.

---

## Stage 2 — Data Ingestion

**Layer:** Deterministic  
**Agent / Service:** Market Data Ingestor (A1)  
**Dependencies:** Stage 1 (approved universe)

### Purpose
Load all market and consensus data for the approved universe into a single canonical
data package that all subsequent stages consume. In demo mode this reads from
`mock_data.py`; in production it calls FMP API and Finnhub API.

### Process

**Demo mode (current):**
1. Load pre-built illustrative market snapshots from `MARKET_SNAPSHOTS` dict.
2. Filter to approved tickers only.
3. Package into a normalised `market_data` dict with `stocks`, `date`, and `data_source` keys.

**Production mode (target):**
1. Call FMP API: `fetch_quotes()`, `fetch_ratios()`, `fetch_analyst_estimates()`,
   `fetch_price_targets()`, `fetch_recommendation_trends()`, `fetch_earnings_calendar()`.
2. Call Finnhub API for cross-validation data (second source for reconciliation).
3. Store raw responses as `raw_fmp_snapshot` and `raw_finnhub_snapshot` artifacts.
4. Apply request budget controls and retry logic.
5. Flag any stale data (configurable `stale_data_hours` threshold).

### Data fields per stock
| Field | Source | Type |
|-------|--------|------|
| price | FMP / demo | float |
| market_cap_bn | FMP / demo | float |
| forward_pe | FMP / demo | float |
| ev_ebitda | FMP / demo | float |
| revenue_ttm_bn | FMP / demo | float |
| revenue_next_yr_consensus_bn | FMP / demo | float |
| free_cash_flow_ttm_bn | FMP / demo | float |
| gross_margin_pct | FMP / demo | float |
| consensus_target_12m | FMP / demo | float |
| analyst_ratings | FMP / Finnhub | dict |
| recent_catalysts | Demo / research | list |
| key_risks | Demo / research | list |

### Outputs
```json
{
  "status": "complete",
  "tickers_loaded": 3,
  "data_source": "Demo / illustrative",
  "date": "2026-03-24"
}
```

### Design rationale
All data flows through a single ingestor so every downstream stage reads from the same
canonical snapshot. This prevents drift between stages (e.g., Stage 6 and Stage 7 using
different prices). The raw / canonical separation gives an audit trail.

---

## Stage 3 — Reconciliation

**Layer:** Deterministic  
**Agent / Service:** Consensus & Reconciliation Service (A2)  
**Dependencies:** Stage 2 (ingested data)

### Purpose
Compare data across sources (FMP vs Finnhub in production) and classify any divergences
as GREEN / AMBER / RED. Human review is required before publication when RED fields exist.
This is one of the most important governance controls in the pipeline.

### Process

**Demo mode:**
1. Iterate over each ticker's market snapshot.
2. Since only one source exists in demo mode, classify all fields as GREEN with a note
   explaining that cross-source reconciliation is not applicable.

**Production mode:**
1. For each field in each ticker, compare `source_a` (FMP) vs `source_b` (Finnhub).
2. Apply configurable drift thresholds:
   - `price_drift_amber_pct` (default: 0.5%) — flag for monitoring
   - `price_drift_red_pct` (default: 2.0%) — require human review
   - `target_divergence_amber_pct` (default: 5%) — flag analyst target disagreement
   - `estimate_divergence_amber_pct` (default: 10%) — flag estimate spread
3. For each RED or AMBER field, emit: `{field_name, source_a, source_b, preferred_source, status, reviewer_required}`.
4. Count totals: `red_fields`, `amber_fields`, `green_fields`.
5. If `red_fields > 0`, escalate to human review queue before proceeding.

### Outputs
```json
{
  "reconciliation": {
    "NVDA": {"price": 875.0, "reconciliation_status": "GREEN"},
    "CEG": {"price": 287.5, "reconciliation_status": "GREEN"}
  },
  "red_fields": 0,
  "amber_fields": 0,
  "green_fields": 3
}
```

### Design rationale
Data quality failures are the most common cause of institutional research errors.
Making reconciliation a hard-coded deterministic gate (not an LLM judgment) ensures
it cannot be bypassed or rationalised away. RED fields creating a mandatory human
review queue is a direct production risk control.

---

## Stage 4 — Data QA & Lineage

**Layer:** Deterministic  
**Agent / Service:** Data QA & Lineage Service (A3)  
**Dependencies:** Stage 3 (reconciled data)

### Purpose
Run automated schema validation, outlier detection, freshness checks, and lineage
tagging on the reconciled data package before any LLM agent is permitted to read it.
This is the last deterministic gate before expensive LLM work begins.

### QA checks performed
| Check | Method | Fail condition |
|-------|--------|----------------|
| Schema validation | Pydantic v2 field types | Any field type mismatch |
| Timestamp freshness | Compare data date vs run date | Stale by > N hours |
| Duplicate detection | Hash-based row deduplication | Any duplicates found |
| Null field scan | Check required fields present | Nulls in price/PE/cap |
| Outlier detection | Z-score vs sector peers | Z-score > 4σ for price/PE |
| Lineage tagging | Trace each field to source | Any untagged field |

### Lineage tier system
Every claim and data point carries a tier tag throughout the pipeline:

| Tier | Label | Meaning | Example |
|------|-------|---------|---------|
| T1 | `[T1]` | Exchange data, regulatory filings | Price, shares outstanding, 10-K revenue |
| T2 | `[T2]` | Management statements, earnings calls | Guidance, investor day targets |
| T3 | `[T3]` | Sell-side estimates, consensus | Analyst targets, Estimize estimates |

### Outputs
```json
{
  "schema_valid": true,
  "timestamps_valid": true,
  "duplicates_found": 0,
  "lineage_complete": true,
  "data_quality_score": 7.5,
  "notes": "Demo data treated as Tier 3 — no source chain available"
}
```

### Design rationale
The `data_quality_score` (0-10) is used in the Stage 11 self-audit scorecard. A score
below 6.0 should trigger a FAIL at the publish gate. The tier system flowing from this
stage is critical — it ensures every claim in the final report can be traced to its
evidence quality level, enabling readers to weight claims appropriately.

---

## Stage 5 — Evidence Librarian / Claim Ledger

**Layer:** LLM Reasoning Agent  
**Agent / Service:** Evidence Librarian  
**Model:** Claude (temperature: user-configured)  
**Dependencies:** Stages 2–4 (reconciled, QA-passed data)

### Purpose
The Evidence Librarian is the first LLM agent in the pipeline. Its job is to review
the raw market data and build a structured **claim ledger** — a traceable, tiered
inventory of every material factual claim that will appear in the research report.
This is the epistemic foundation of the entire report.

### Process
1. Receive the canonical market data package and a preliminary claim list from Stage 4.
2. For each stock, identify and tier:
   - **Tier 1 / T1 facts**: Exchange data, SEC filings — incontrovertible
   - **Tier 2 / T2 guidance**: Management statements, earnings calls — directional
   - **Tier 3 / T3 estimates**: Sell-side consensus — illustrative only
3. Flag **evidence gaps** — claims the analysis would like to make but cannot yet
   support with T1/T2 sources.
4. Rate overall evidence quality per stock: HIGH / MEDIUM / LOW.
5. Output the structured claim ledger in markdown, with every claim tagged `[T1]`,
   `[T2]`, or `[T3]`.

### System prompt framing
The agent is instructed to be the "last line of defence before bad data reaches the
analysts." It must explicitly flag anything that could be a sell-side estimate
masquerading as hard data.

### Key outputs per stock
- 4–6 primary verified facts `[T1]`
- 3–5 management guidance items `[T2]`
- 2–3 consensus estimates `[T3]`
- 2–3 identified evidence gaps
- Evidence quality rating with reasoning

### Why this stage exists before sector analysis
If the sector analysts in Stage 6 were given raw data without a claim ledger, they
would mix T1 facts and T3 estimates without distinguishing them. This stage forces
epistemic hygiene upstream so analysts only reason from tiered, labelled inputs.

---

## Stage 6 — Sector Analysis

**Layer:** LLM Reasoning Agent  
**Agent / Service:** Sector Analyst × 3 (Compute, Power & Energy, Infrastructure)  
**Model:** Claude  
**Dependencies:** Stage 5 (claim ledger), Stages 2–4 (market data)

### Purpose
Produce the core differentiated fundamental analysis for every stock in the universe.
Each stock receives a structured **Four-Box analysis** that separates facts from
judgment, and differentiates the house view from consensus.

### Three analyst personas
| Analyst | Coverage | Focus |
|---------|---------|-------|
| Compute & Silicon | NVDA, AVGO, TSM | GPU monopoly dynamics, custom ASIC threat, TSMC foundry capacity |
| Power & Energy | CEG, VST, GEV | Nuclear relicensing, gas peaker economics, grid equipment backlog |
| Infrastructure & Materials | PWR, ETN, APH, FIX, FCX, NXT | Grid construction, data centre cooling, copper supply, solar trackers |

### The Four-Box framework (per stock)

**Box 1 — Verified Facts** `[T1]` / `[T2]` only  
Hard data: price, market cap, revenue, margins, filed guidance. No estimates.
Every number references the source data package. Purpose: establish the incontrovertible baseline.

**Box 2 — Management Guidance** `[GUIDANCE]`  
Forward-looking statements made by management on earnings calls or investor days.
Dated and sourced. Explicit about the difference between committed guidance and aspirational targets.

**Box 3 — Consensus & Market View** `[T3]`  
Sell-side consensus estimates and analyst sentiment. Data limitations stated explicitly.
Not treated as truth — treated as the market's embedded assumption.

**Box 4 — Analyst Judgment** `[HOUSE VIEW]`  
The differentiated view. What does the market miss? What is already priced in?
Bull and bear arguments derived from the same factual base (not cherry-picked).
Conviction level: HIGH / MEDIUM / LOW with explicit rationale.

### Hard rules enforced in the system prompt
- Every numerical claim must reference the source data provided
- Evidence gaps must be flagged, not glossed over
- No price targets — that is the valuation analyst's exclusive role
- The AI efficiency shock (DeepSeek-style rapid inference improvement) must appear
  as a mandatory bear scenario for all compute names
- Opinions are clearly separated from facts at all times

---

## Stage 7 — Valuation & Modelling

**Layer:** LLM Reasoning Agent  
**Agent / Service:** Valuation Analyst  
**Model:** Claude  
**Dependencies:** Stage 6 (sector analysis), Stages 2–4 (market data with financials)

### Purpose
The Valuation Analyst is the **only** team member who sets return scenarios and
contextualises current prices. Stage 6 analysts are prohibited from giving price targets;
all valuation judgment is centralised here to ensure consistency.

### Process per stock
1. **Current snapshot** — where the stock sits today on key multiples (P/E, EV/EBITDA,
   FCF yield) relative to its own history (where data permits).
2. **Return decomposition** — break the expected return into its three components:
   revenue growth, margin expansion, and multiple re-rating. Identify which driver
   dominates and how defensible it is.
3. **Three scenarios** — Bull / Base / Bear with explicit probability weights,
   revenue CAGR assumptions, exit multiples, implied 12-month returns, and the
   single key assumption that drives each case.
4. **Entry quality rating** — STRONG / ACCEPTABLE / STRETCHED / POOR with a
   one-sentence rationale.
5. **Expectation pressure** — 0 to 10 score (10 = maximum priced-in perfection).
   A score above 8 means the stock needs to execute perfectly to justify current price.

### Scenario table format (required)
| Case | Prob | Rev CAGR | Exit Multiple | Implied 1yr Return | Key Assumption |
|------|------|----------|---------------|--------------------|----------------|
| Bull | 25%  | ...      | ...           | ...                | ...            |
| Base | 55%  | ...      | ...           | ...                | ...            |
| Bear | 20%  | ...      | ...           | ...                | ...            |

### Hard rules
- All multi-year scenarios labelled `[HOUSE VIEW]`
- Consensus target is NOT treated as intrinsic value — it is one data point
- If current price is above the consensus target, this must be flagged explicitly
- No single-point fair values — always scenario ranges
- The assumptions embedded in the current price must be made explicit

### Design rationale
Centralising price context in a single agent prevents scenario inflation (different
analysts independently producing inconsistent return estimates for the same stock).
The "expectation pressure" construct is specifically designed to combat the institutional
bias toward recommending stocks that have already performed well.

---

## Stage 8 — Macro & Political Overlay

**Layer:** LLM Reasoning Agent  
**Agent / Service:** Macro & Regime Strategist + Political Risk Analyst  
**Model:** Claude  
**Dependencies:** `macro_data` (rates, growth, inflation variables), universe list

### Purpose
Overlay the bottom-up stock analysis with the macro and geopolitical regime.
AI infrastructure stocks are highly sensitive to rates, geopolitics, and policy —
this stage makes those sensitivities explicit and ensures they feed into the final
portfolio construction.

### Two sections produced

**Part 1: Macro & Regime Overlay**
- Current regime characterisation: growth/inflation/rates environment
- Key macro variables relevant to AI infrastructure:
  - Interest rates (affects long-duration growth multiples)
  - US dollar (affects international earnings translation)
  - Copper and steel prices (input costs for infrastructure build)
  - Power prices (affects nuclear/generation economics)
- Regime shift risks: what macro scenario breaks the AI capex thesis?
- Factor exposure classification: growth bet vs quality bet vs both

**Part 2: Political & Geopolitical Risk Register**

Structured risk table covering:
| Risk | Probability | Impact | Affected Names | Monitoring Trigger |

Five to seven risks including:
- **US-China tech export controls** — current state, escalation scenarios, H20/B20 chip bans
- **Taiwan risk** — probability assessment, CVaR estimate, hedging considerations
- **IRA / US infrastructure policy** — renewable energy tax credit risk under current administration
- **TSMC restrictions** — foundry access risk for US chip customers
- **Grid permitting / FERC policy** — impact on data centre power buildout pace

Concludes with an overall **Geopolitical Risk Rating**: LOW / MEDIUM / HIGH / ELEVATED,
and which specific stocks in the universe are most and least exposed.

### Design rationale
Bottom-up fundamental analysis systematically underweights macro and political risk
because individual analysts focus on company-level data. Requiring a separate macro
overlay stage forces the team to confront regime-level risks that could invalidate the
thesis regardless of company fundamentals.

---

## Stage 9 — Quant Risk & Scenario Testing

**Layer:** Hybrid (deterministic metrics + LLM narrative)  
**Agent / Service:** Risk Manager  
**Dependencies:** Stages 6–7 (sector and valuation outputs), market data

### Purpose
Quantify portfolio-level risk, compute basic risk metrics for each stock, and stress-test
the portfolio against five defined macro/sector shock scenarios.

### Deterministic metrics computed (code)
For each stock:
- **Implied upside %** — `(consensus_target - price) / price × 100`
- **Multiple percentile estimate** — HIGH / MEDIUM / LOW based on forward P/E ranges
- **Concentration flag** — YES for names exceeding single-stock weight limits (NVDA, TSM)
- **Beta estimate** — 1.8 for compute names, 1.1 for infrastructure/utilities

### LLM narrative analysis (Claude)
With those deterministic inputs, the LLM produces:

**Portfolio Risk Summary**
- Concentration risk across sub-themes
- Correlation risk: which names will move together in a sell-off
- Factor exposures: AI capex beta, rates sensitivity, geopolitical beta

**Five mandatory stress scenarios with estimated drawdown:**
1. **AI Capex Pause** — hyperscalers cut capex 30% following ROI disappointment
2. **Higher For Longer** — Fed holds rates at 5%+ through 2027, re-rates growth multiples
3. **Taiwan Crisis** — 10% probability over 12 months, tech supply chain disruption
4. **DeepSeek 2.0** — efficiency breakthrough cuts training compute demand 50%
5. **Power Price Collapse** — gas oversupply normalises electricity prices, squeezing utilities

**Risk-Adjusted Summary Table**
| Ticker | Upside (consensus) | Beta | Key Risk | Risk Rating |

### Design rationale
Keeping the risk metrics deterministic ensures they are objective and reproducible.
The LLM's role is interpretation and scenario narrative — not the math. The five
mandatory scenarios are fixed rather than LLM-chosen, preventing the model from
only generating scenarios it finds easy to discuss.

---

## Stage 10 — Red Team Analysis

**Layer:** LLM Reasoning Agent  
**Agent / Service:** Red Team Analyst  
**Model:** Claude  
**Dependencies:** Stage 6 (sector analysis), Stage 7 (valuation outputs)

### Purpose
The Red Team Analyst's sole job is adversarial: try to break every investment thesis
before publication. This stage exists specifically to counter model and analyst
optimism bias. The agent must produce arguments against the bull case, regardless
of conviction.

### Process per stock

**Thesis identification** — state the bull thesis in one sentence before attacking it.

**Falsification tests (minimum 3):**
1. What single data point, announced tomorrow, would invalidate the thesis?
2. What is the bear case that is systematically underweighted by the bull thesis?
3. Where is this analysis most likely to be wrong?

**Variant Bear Case `[HOUSE VIEW]`:**
- Timeline: specific horizon (6–18 months)
- Mechanism: specific chain of events (not "things could go wrong")
- Estimated downside: percentage range
- Exit condition: what would make you abandon the bear view?

**Crowding & Sentiment Risk:**
- Consensus crowding score (1–10, 10 = maximum consensus positioning)
- Orderly vs disorderly exit scenario

**Overall Red Team Rating per stock:**
- **STRONG** — thesis survives adversarial scrutiny
- **MODERATE** — material concerns that must be disclosed
- **WEAK** — serious structural problems; consider excluding from report

### Hard rules
- Vague risks ("competition could increase") are explicitly banned — every bear point
  must be concrete and falsifiable
- Each falsification test must be actionable (you must be able to monitor for it)
- The agent must engage with the specific bull thesis from Stage 6, not generic sector risks

### Design rationale
Institutional research has a documented bullish bias because analysts are incentivised
to generate interest in covered names. A dedicated adversarial stage with an explicit
mandate to find flaws provides an independent check. The WEAK rating gives the
publication gate in Stage 11 a hard signal to act on.

---

## Stage 11 — Associate Review / Publish Gate

**Layer:** LLM Agent + Governance Gate  
**Agent / Service:** Associate Reviewer  
**Model:** Claude  
**Dependencies:** Stages 5–10 (all analyst outputs)

### Purpose
The final quality gate before publication. The Associate Reviewer reads the entire
research package and produces a self-audit scorecard, a publication decision, and any
required disclosures. Nothing is published without an explicit PASS decision.

### Self-Audit Scorecard (0–10 per criterion)

| Criterion | Description |
|-----------|-------------|
| Evidence quality & sourcing | Are T1/T2 claims properly sourced? |
| Claim provenance (T1/T2/T3 mix) | Is the T3 proportion disclosed? |
| Valuation methodology rigor | Are scenarios properly uncertainty-bounded? |
| Risk identification completeness | Were all material risks surfaced? |
| Red team engagement quality | Did red team address the actual bull thesis? |
| Disclosure completeness | Are required regulatory disclosures present? |
| Internal consistency | Do stages agree with each other? |

**Overall Score: X / 10**

### Three possible publication decisions

| Decision | Meaning | Action |
|----------|---------|--------|
| **PASS** | All criteria met; proceed to assembly | Continue to Stage 13 |
| **PASS WITH DISCLOSURE** | Material limitations exist but are disclosed | Add required disclosures; proceed |
| **FAIL** | Serious quality problems that must be remediated | Block publication; return to affected stage |

### Additional outputs
- **Issues list** — specific corrections or disclosures required
- **Recommended disclosures** — standard compliance language to appear at report bottom

### Design rationale
The publish gate is the central governance control of the pipeline. Making it a
separate LLM stage ensures it reads the entire package with fresh context rather
than inheriting the authors' framing. A PASS WITH DISCLOSURE is designed to be
clearly better than ignoring a real limitation — incentivising honesty over gaming
the gate. In production, the FAIL path would return a flag to the orchestrator to
re-run affected stages.

---

## Stage 12 — Portfolio Construction

**Layer:** LLM Reasoning Agent  
**Agent / Service:** Portfolio Manager  
**Model:** Claude  
**Dependencies:** Stages 6–9 (sector, valuation, risk outputs)

### Purpose
Synthesise all research into three practical portfolio variants. The Portfolio Manager
acts as an independent voice — reading the research and constructing portfolios that
are appropriately diversified, risk-constrained, and actionable.

### Mandatory hard constraints (all variants)
- Maximum single-stock weight: **15%**
- Each variant must hold at least one name from each sub-theme:
  compute, power/energy, infrastructure
- No sector can exceed **50%** of a variant's weight
- Only names from the approved research universe may be included
- Weights must sum to exactly 100%

### Three portfolio variants

**Variant 1: Balanced Conviction Basket**  
Target: Highest risk-adjusted return blend across the full theme  
Construction logic: Select names with the best balance of upside, evidence quality,
and entry quality across all three sub-themes. No aggressive concentration.

**Variant 2: Higher Return Basket**  
Target: Maximum expected return; higher concentration acceptable; higher volatility accepted  
Construction logic: Overweight the highest-conviction names from Stage 6/7 with
STRONG red team ratings. May concentrate in compute if that sub-theme has highest
return potential. Accepts the tail risk that comes with concentration.

**Variant 3: Lower Volatility Basket**  
Target: Defensive AI infrastructure exposure  
Construction logic: Prefer lower-beta names — utilities, materials, infrastructure
construction. Underweight high-multiple semiconductor names. Seeks participation
in the AI capex theme without the valuation risk.

### For each variant, the agent must produce
- Weights table: `| Ticker | Company | Subtheme | Weight % | Rationale |`
- Implementation notes (liquidity, sizing, entry strategy)
- Key portfolio risk: the single factor that would most hurt this variant
- Rebalancing trigger: what specific conditions would cause reweighting

### Portfolio Synthesis
Across all three variants, the agent must identify:
- **Core names** — appear in all three variants (highest-conviction holdings)
- **Variant-specific names** — only in one variant and why

### Design rationale
Three variants serve different client mandates without the Portfolio Manager having to
make a single universal recommendation. The core/variant-specific analysis in the
synthesis section is the most actionable output — it reveals where all three
construction approaches converge.

---

## Stage 13 — Report Assembly

**Layer:** Deterministic (templated assembly)  
**Agent / Service:** Report Assembly Service  
**Dependencies:** All stages 0–12

### Purpose
Assemble every stage output into a single, consistently formatted research report
in markdown. This is pure template work — no LLM, no new analysis. The goal is
to produce a document that reads as a coherent whole rather than a concatenation
of individual stage outputs.

### Assembly structure (report sections)

| Section | Source | Description |
|---------|--------|-------------|
| Cover & metadata | Stage 0 | Run ID, model, date, universe, publication status |
| Disclaimers | Fixed template | Demo/production data limitations, not investment advice |
| Executive Summary | Stages 1–4 | Universe snapshot table with prices, P/E, consensus targets, upside |
| 1. Evidence Library | Stage 5 output | Full claim ledger with T1/T2/T3 tags |
| 2. Sector Analysis | Stage 6 output | Four-Box per stock, all sub-themes |
| 3. Valuation & Modelling | Stage 7 output | Scenario tables, entry quality, expectation pressure |
| 4. Macro & Political Overlay | Stage 8 output | Regime analysis and risk register |
| 5. Quant Risk & Scenarios | Stage 9 output | Stress scenarios, risk table |
| 6. Red Team Analysis | Stage 10 output | Falsification tests, bear cases, ratings |
| 7. Portfolio Construction | Stage 12 output | Three variants with weights |
| 8. Associate Review | Stage 11 output | Self-audit scorecard, disclosures |
| Appendix | Stage 0 output | Run metadata table |

### Universe snapshot table (generated in code)
The cover section includes a dynamically generated table:
```
| Ticker | Company | Sub-theme | Price | Fwd P/E | Consensus 12M Target | Implied Upside |
```
This is computed programmatically from market data rather than relying on LLM output,
ensuring the numbers are always traceable to the original data package.

### Output
A single `.md` file available for download from the frontend. In production, this
would also be written to a dated artifact store and registered in the run registry.

### Design rationale
Keeping assembly deterministic (no LLM) means the report content is exactly the
sum of the stage outputs with no additional editorialising. This is critical for
auditability — a reader can trace any claim in the report directly to the stage
that generated it and the data that fed that stage.

---

## Data flow summary

```
MARKET DATA (demo: mock_data.py | production: FMP + Finnhub)
    │
    ├─[Stage 2]─► canonical market_data dict
    │                     │
    ├─[Stage 3]─► reconciled, GREEN/AMBER/RED fields
    │                     │
    ├─[Stage 4]─► QA-passed, lineage-tagged, data_quality_score
    │                     │
    ├─[Stage 5]─► claim_ledger_text (T1/T2/T3 tags)
    │                     │
    ├─[Stage 6]─► sector_outputs (Four-Box per stock)
    │                     │
    ├─[Stage 7]─► valuation_outputs (scenarios, entry quality)
    │                     │
    ├─[Stage 8]─► macro_outputs (regime, risk register)
    │                     │
    ├─[Stage 9]─► risk_outputs (stress scenarios, risk table)
    │                     │
    ├─[Stage 10]─► red_team_outputs (falsification, bear cases)
    │                     │
    ├─[Stage 11]─► review_output (scorecard, PASS/FAIL)
    │                     │
    ├─[Stage 12]─► portfolio_output (3 variants, weights)
    │                     │
    └─[Stage 13]─► final_report_md (complete markdown document)
```

---

## LLM context budget per stage

Each LLM stage is given a bounded context window to prevent token overflow:

| Stage | System prompt | User context passed |
|-------|---------------|---------------------|
| 5 — Evidence | ~500 tokens | Full market data + 15 preliminary claims |
| 6 — Sector | ~700 tokens | Full market data per sector + 10 claims |
| 7 — Valuation | ~600 tokens | Financial metrics + first 3,000 chars of Stage 6 |
| 8 — Macro | ~500 tokens | Full macro_data dict |
| 9 — Risk | ~550 tokens | Risk metrics + first 2,000 chars of Stage 6 |
| 10 — Red Team | ~550 tokens | First 3,000 chars of Stage 6 + 2,000 of Stage 7 |
| 11 — Review | ~450 tokens | First 2,000 chars each of Stages 6, 7, 10 |
| 12 — Portfolio | ~600 tokens | First 2,500 chars of Stage 6 + 2,000 of Stage 7 + 1,500 of Stage 9 |

Max output tokens per call: **8,192** (set in `_call_claude`).

---

## Evidence tier reference

All claims throughout the pipeline carry one of these tags:

| Tag | Name | Source examples | Trust level |
|-----|------|-----------------|-------------|
| `[T1]` | Primary / Exchange | SEC filings, exchange prices, reported earnings | High — verifiable |
| `[T2]` | Management / Official | Earnings calls, investor days, press releases | Medium — official but forward-looking |
| `[T3]` | Consensus / Derived | Analyst targets, Estimize, calculated ratios | Low — estimate only |
| `[GUIDANCE]` | Forward guidance | Management guidance statements | Medium — stated but uncertain |
| `[HOUSE VIEW]` | Analyst judgment | All scenarios, opinions, differentiated views | Label as opinion |

---

*Pipeline v8.0 — Documentation generated 2026-03-24*
