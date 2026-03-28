# Project Issues Assessment — Post-Improvement Target State

> **Document type:** Engineering gap analysis  
> **Date:** March 28, 2026  
> **Scope:** Issues that will **still exist** after the completion of all planned work in  
> TRACKER.md (Sessions 11–14), IMPROVEMENTS.md (ARC-1–10, Parts B–H, E-1–E-10), and  
> ARCHITECTURE.md (§13 session plans).  
> **Method:** Full system index + code audit of `engine.py`, `base_agent.py`, `app.py`,  
> all schemas, all services, all tests, and all planning documents cross-referenced against  
> the target state those plans describe.

---

## How to Read This Document

Each issue is classed by area, given a severity rating, and has a concrete pointer to where
the problem lives in code. Only issues that are **not addressed** by any item in the current
backlog are included. Issues that are explicitly scheduled (e.g. ARC-1 in Session 11) are
**not** listed here.

Severity scale:
- **Critical** — breaks correctness or institutional-grade output claims
- **High** — degrades a JPAM-division score or creates production risk
- **Medium** — technical debt with measurable quality impact
- **Low** — polish / consistency item

---

## SECTION 1 — Pipeline Engine & Data-Flow Issues

### ISS-1 · `_get_macro_context()` has no schema contract (Critical)

**Location:** `src/research_pipeline/pipeline/engine.py` — planned helper added by ARC-1

**Problem:** ARC-1 schedules a helper `_get_macro_context()` that extracts `stage_outputs[8]`.
The current Session 11 plan wires this raw dict into Stages 9, 10, 11, and 12. However
`stage_outputs[8]` is itself an untyped `dict` assembled from two separate agent results
(`macro_agent` + `political_agent`). There is no `MacroContextPacket` Pydantic schema that
defines what keys must be present, their types, or their defaults when a field is absent.

**Impact:** Every downstream stage silently receives partial or structurally inconsistent macro
context if either agent fails or returns incomplete JSON. The Red Team, Reviewer, and PM agents
will have no way to distinguish "rate regime = None because agent failed" from "rate regime
= None because it is genuinely unknown".

**Fix required:** Define `MacroContextPacket(BaseModel)` in `schemas/portfolio.py` or a new
`schemas/macro.py`. The helper `_get_macro_context()` must validate against this schema and
return a default-filled instance on failure, not a raw dict.

---

### ISS-2 · Stage ordering change (ARC-4) breaks existing `stage_outputs` index assumptions (High)

**Location:** `engine.py` — `run_full_pipeline()` execution order

**Problem:** ARC-4 swaps Stage 7 (Valuation) and Stage 8 (Macro). The rest of the engine
references these by their numeric index: `stage_outputs[7]` and `stage_outputs[8]`. After the
swap, the semantic contents of these indices remain unchanged, which is correct. However the
`SelfAuditPacket.stage_latencies_ms` field uses the integer stage number as a key. Any
downstream code (Streamlit UI panels, observability service, reporting) that reads latency by
stage number and assumes "Stage 7 = valuation" will correctly display them — **but the
execution order in the `audit_packet` will now say Stage 8 finished first**. The UI stage
progress cards in `app.py` paint status badges using sequential stage indices and the current
hardcoded sequence table. If the displayed order does not match the new execution order, the
operator will see Stage 7 as "running" after Stage 8 is already "complete" — which is
confusing.

**Fix required:** Update the Streamlit stage progress card order in `app.py` to reflect the
new 8→7 execution sequence, or make the display order dynamic from engine metadata.

---

### ISS-3 · `SECTOR_ROUTING` config (ARC-5) has no fallback agent implementation (High)

**Location:** `engine.py` stage_6 + `config/loader.py`

**Problem:** ARC-5 externalises the routing dict into `config/loader.py`. IMPROVEMENTS.md
specifies "Allow fallback to a `GenericSectorAnalystAgent` for unmapped tickers." No such
agent is planned in any session. The plan in Session 13 adds `SectorDataService` for FMP
earnings data and per-ticker four-box output, but this is a different concern. Without the
fallback agent, ASX tickers and any custom universe ticker not in the three hardcoded sectors
will still get zero sector analysis — the bug is fixed for the 17 known tickers but the root
cause (single-universe assumption) persists for new tickers.

**Fix required:** Implement `GenericSectorAnalystAgent` or extend one of the three existing
sector agents to accept arbitrary tickers. This does not require a new session — it is the
completion condition for ARC-5.

---

### ISS-4 · Stage 13 report assembly: `StockCard` population logic depends on untyped valuation output (High)

**Location:** `engine.py` stage_13 + `services/report_assembly.py`

**Problem:** ARC-2 builds `stock_cards` by iterating `stage_outputs[7]` (valuation outputs).
The `ValuationAnalystAgent` returns a raw `dict` from `parse_output()`. The `StockCard` schema
in `schemas/reports.py` expects specific typed fields. There is no code in any session plan
that adds a `ValuationAnalystAgent` → `StockCard` adapter or enforces that `stage_outputs[7]`
returns something that matches `StockCard`'s fields. The ARC-2 fix will produce stock_cards but
they will be ad-hoc dicts coerced to `StockCard`, almost certainly with missing/wrong fields
the first time live LLM output is used.

**Fix required:** Add `ValuationCard → StockCard` mapping logic with explicit field extraction
and defaults. Add a test that round-trips a real-shaped valuation output through this mapping.

---

### ISS-5 · `SelfAuditPacket.llm_provider_used` is planned but no agent produces it (Medium)

**Location:** `base_agent.py` + `schemas/governance.py`

**Problem:** IMPROVEMENTS.md E-8 adds `SelfAuditPacket.llm_provider_used`. The existing
`BaseAgent.call_llm()` already logs which fallback model was used via `logger.warning()` but
returns nothing beyond the text string. The `AgentResult` schema has no `provider_used` or
`model_used` field. E-8 schedules adding this to `SelfAuditPacket` and a `LLMConfig` in
`PipelineConfig`, but it does **not** schedule modifying `AgentResult` to carry the
model-actually-used field back from `call_llm()`. Without that, the engine cannot know which
provider each agent used; it can only log it.

**Fix required:** Add `model_used: str` and `provider_used: str` to `AgentResult`. Propagate
from `call_llm()` return value. Collect in engine and store in `SelfAuditPacket`.

---

### ISS-6 · `GoldenTestHarness` categories `portfolio_output_stability` and `report_generation` remain with zero real assertions (High)

**Location:** `src/research_pipeline/services/golden_tests.py` lines 147–151

**Problem:** The architectural note in `ARCHITECTURE.md §12.3` flagged `passed = True #
placeholder` at line 148. The current code now fails unknown categories (`passed = False`
with a warning). However the two categories `portfolio_output_stability` and
`report_generation` are registered in `PipelineConfig.test_categories` but have:
1. No registered test fixtures in `_register_builtin_tests()`
2. No corresponding `run_*_test()` method on `GoldenTestHarness`

So Stage 14 golden tests will silently skip these two categories entirely — they never
appear in `results["details"]` because no `GoldenTest` instances with those categories
exist. No session plan adds them.

**Fix required:** Add at least one `GoldenTest` fixture per category and implement
`run_portfolio_output_stability_test()` and `run_report_generation_test()`.

---

### ISS-7 · `FinnhubAPIKey` absent from `.env.example` (Medium)

**Location:** `.env.example`

**Problem:** `engine.py` and `market_data_ingestor.py` require `FINNHUB_API_KEY`. The
`.env.example` file documents `FMP_API_KEY` but omits `FINNHUB_API_KEY`. Any developer
cloning the repo will hit a silent failure in Stage 2 data ingestion without knowing what
environment variable they are missing.

**Fix required:** Add `FINNHUB_API_KEY=` to `.env.example` with a comment linking to
`finnhub.io`.

---

### ISS-8 · `qualitative.py` schema not exported from `schemas/__init__.py` (Medium)

**Location:** `src/research_pipeline/schemas/__init__.py`

**Problem:** `qualitative.py` contains Pydantic models used by `QualitativeDataService`
and referenced in tests, but it is absent from the `__init__.py` re-exports. Any code doing
`from research_pipeline.schemas import QualitativePackage` will raise `ImportError`. This
is a current bug; no session plan fixes it.

**Fix required:** Add `from research_pipeline.schemas.qualitative import *  # noqa: F403`
to `schemas/__init__.py`.

---

## SECTION 2 — Agent Layer Issues

### ISS-9 · `BaseAgent._validate_output_quality()` is non-fatal — missing required keys never fail the pipeline (High)

**Location:** `src/research_pipeline/agents/base_agent.py` lines 387–402

**Problem:** `_validate_output_quality()` logs warnings but always returns a list — it
never raises. The `_REQUIRED_OUTPUT_KEYS` mechanism (ACT-S10-3) is therefore cosmetic: an
agent that omits `"valuation_thesis"` from its output will pass `parse_output()`, return
`success=True`, and propagate `None` for that key downstream. IMPROVEMENTS.md Part F
checklist item states "All agent outputs validated by Pydantic — no raw `dict` returns
bubbling up." The scheduled session work adds more keys to `_REQUIRED_OUTPUT_KEYS` for
additional agents, but it never changes the non-fatal behaviour. The downstream stages that
consume these dicts do so with `.get()` calls that silently return `None`.

**Fix required:** Make quality validation failures either (a) raise `StructuredOutputError`
to trigger the retry loop, or (b) count toward a stage gate condition. At minimum, gate
failure should block the pipeline when required keys are absent from critical agents
(ValuationAnalyst, AssociateReviewer, PortfolioManager).

---

### ISS-10 · Gemini import mismatch — `google.generativeai` vs `google-genai` package (High)

**Location:** `src/research_pipeline/agents/base_agent.py` line 266

**Problem:** `requirements.txt` pins `google-genai>=1.0` which installs the new `google.genai`
module. `base_agent.py` imports `import google.generativeai as genai` which is the **old**
`google-generativeai` package. These are two different PyPI distributions:

- `google-generativeai` → `import google.generativeai`
- `google-genai` → `import google.genai`

The import at line 266 will therefore always fail, causing Gemini to silently fall through to
the REST fallback (`_call_gemini_rest`). The REST fallback itself uses `asyncio.get_event_loop()`
which is deprecated in Python 3.10+ and will emit a `DeprecationWarning` or fail in
Python 3.12+.

**Fix required:** Either change `requirements.txt` to `google-generativeai>=0.5` and keep the
existing import, or rewrite `_call_gemini()` to use `import google.genai` and the new SDK
interface. Either way `_call_gemini_rest` should replace `asyncio.get_event_loop()` with
`asyncio.get_running_loop()`.

---

### ISS-11 · `OrchestratorAgent` has no place in the engine's execution — it is never called (Medium)

**Location:** `src/research_pipeline/agents/orchestrator.py` + `engine.py`

**Problem:** `OrchestratorAgent` is instantiated in `engine.py` and documented in
`ARCHITECTURE.md §5.2` as "Manages stage sequencing". In practice `engine.py` does all
stage sequencing itself in `run_full_pipeline()`. The orchestrator agent is never invoked in
any pipeline stage. It exists only as a registered entity for prompt registry scanning. The
session plans do not schedule connecting it to any stage — the `EconomyAnalystAgent` (Session
12) and other new agents all bypass the orchestrator.

**Impact:** Conceptual inconsistency — the architecture claims the orchestrator manages stage
sequencing but `engine.py` hard-codes it. Any new agent is integrated directly into
`run_full_pipeline()`. If the codebase is ever read by a new engineer, the `orchestrator.py`
file implies a dispatch model that does not exist.

**Fix required:** Either (a) remove the `OrchestratorAgent` from `engine.py` instantiation
and label it clearly as a conceptual placeholder, or (b) wire it into at least one real
coordination step (e.g. Stage 0 bootstrap validation or Stage 14 run summary production).

---

### ISS-12 · `MacroStrategistAgent` and `PoliticalRiskAnalystAgent` have shallow Pydantic output contracts (High)

**Location:** `src/research_pipeline/agents/macro_political.py`

**Problem:** Neither `MacroStrategistAgent` nor `PoliticalRiskAnalystAgent` declare
`_REQUIRED_OUTPUT_KEYS`. Their outputs flow into `stage_outputs[8]` and from there (after
ARC-1) into every downstream stage. The `MacroRegimeMemo` schema in `schemas/portfolio.py`
exists but is not enforced — the agents return raw dicts from `parse_output()`. Session 12
adds `EconomyAnalystAgent` with a 12-field schema, but it does not fix the structural weakness
in the existing macro agents. After Session 12, there will be three macro-related agents
(`EconomyAnalystAgent`, `MacroStrategistAgent`, `PoliticalRiskAnalystAgent`) all contributing
to `stage_outputs[8]` with no unified typed packet.

**Fix required:** Add `_REQUIRED_OUTPUT_KEYS` to `MacroStrategistAgent` and
`PoliticalRiskAnalystAgent`. Define a unified `Stage8MacroPacket` that combines outputs from
all three agents, validated before being passed downstream.

---

### ISS-13 · No agent prompt covers ASX-listed stock analysis (High)

**Location:** `prompts/` directory — all 12 prompt templates

**Problem:** All sector agent prompts (`sector_compute.md`, `sector_power_energy.md`,
`sector_infrastructure.md`) reference US-listed equities by name (NVDA, TSM, CEG, etc.),
US-specific valuation conventions (USD reporting, S&P 500 context), and US regulatory
frameworks. Session 12 adds ASX universe support at the config/routing level, but no session
plan updates the agent prompts to handle ASX-listed stocks. An ASX-listed company (e.g.
`BHP.AX`, `CSL.AX`) requires AUD reporting, ASX continuous disclosure rules, ASIC oversight,
franking credit valuation, and comparison to the ASX 200 benchmark. A sector agent running
with the current prompts against an ASX stock will produce structurally inappropriate analysis
(USD price targets, S&P context, US regulatory framing).

**Fix required:** Either (a) add jurisdiction-detection to `format_input()` and inject
ASX-specific prompt sections when `.AX` tickers are in the universe, or (b) create
ASX-specific prompt variants (`sector_compute_asx.md`, etc.) loaded based on `MarketConfig`.

---

## SECTION 3 — Services & Data Layer Issues

### ISS-14 · `EconomicIndicatorService` (Session 12) has no tested fallback for FRED API being unavailable (Medium)

**Location:** Planned `src/research_pipeline/services/economic_indicators.py`

**Problem:** IMPROVEMENTS.md Part B specifies "Fallback: Synthetic heuristic values if APIs
unavailable." No session plan defines what those heuristic values are, how they are
structured, or how the service signals to downstream consumers that the data is synthetic
vs live. A hardcoded stub returning stale mid-2025 US/AU rates would be materially worse
than nothing for a live production run, but the pipeline would silently treat it as real.

**Fix required:** Define a `MacroDataQuality` enum (`LIVE`, `CACHED`, `SYNTHETIC`) on
`EconomicIndicators`. Include this in `stage_outputs[8]` so the `MacroStrategistAgent`
prompt can explicitly acknowledge data quality. Gate Stage 8 on data quality — `SYNTHETIC`
data should produce a warning in `SelfAuditPacket`, not a silent pass.

---

### ISS-15 · `LiveReturnStore` has no max cache size or staleness eviction (Medium)

**Location:** `src/research_pipeline/services/live_return_store.py`

**Problem:** `LiveReturnStore` uses an in-memory dict cache keyed by `(ticker, n_days)`.
The cache TTL is either missing or not documented. In a Streamlit session that runs many
pipeline iterations, or in a long-running CLI session, the cache grows unboundedly. For a
252-day return series per ticker with 17 tickers, each entry is small, but the lack of any
eviction policy is a maintenance trap. None of the session plans add TTL eviction.

**Fix required:** Add a `max_age_seconds` parameter (default 3600) and check
`cache_time + max_age > now()` on every cache read. Alternatively, wire through the existing
`CacheLayer` service which already implements TTL.

---

### ISS-16 · BHB Attribution still uses `_generate_synthetic_returns` as the benchmark series (High)

**Location:** `src/research_pipeline/pipeline/engine.py` — Stage 14

**Problem:** ACT-S7-1 introduced `_compute_bhb_attribution()` wired into Stage 14. E-4 in
IMPROVEMENTS.md schedules replacing the synthetic benchmark with real ASX 200 TR / S&P 500 TR
data from yfinance. However E-4 targets the `benchmark_module.py` service, not the BHB
attribution call in Stage 14. Even after E-4, if the engine's Stage 14 path still calls
`_generate_synthetic_returns` for the benchmark leg of BHB (as it does now), attribution will
remain synthetic. Session plans do not include modifying the Stage 14 BHB call site to use the
new real benchmark from E-4.

**Fix required:** After E-4 is implemented, ensure `stage_14_monitoring()` calls
`live_return_store.fetch()` for benchmark tickers (`^AXJO`, `SPY`) with the same method used
for portfolio return fetching, and passes those to `_compute_bhb_attribution()`. Add a test
that asserts `data_source != "synthetic"` when live prices are available.

---

### ISS-17 · `ESGService` heuristic profiles cover only 15–20 US tickers — ASX not covered (High)

**Location:** `src/research_pipeline/services/esg_service.py`

**Problem:** `ESGService` has baseline heuristic profiles for the AI infrastructure universe
(NVDA, AVGO, TSM, CEG, VST, etc.). Session 12 adds ASX tickers to the universe. No session
plan extends the ESG profiles to cover ASX-listed companies. When `EsgAnalystAgent` runs for
an ASX ticker it will receive empty ESG baseline context, producing lower-quality ESG scores.
E-6 adds carbon intensity but does not add ASX coverage. IMPROVEMENTS.md Part F checklist
item states "ESG CSV fixture has 50+ tickers including ASX-listed names" — but this refers to
the test fixture, not the production `ESGService` profiles.

**Fix required:** Add a second-pass data source for ASX ESG heuristics (at minimum,
approximate scores from public MSCI methodology for ASX 200 constituents, or use the CSV
ingest path for production). The test fixture extension alone does not close this gap.

---

### ISS-18 · `ResearchMemoryService` SQLite FTS5 requires a compiled SQLite with FTS5 support (Medium)

**Location:** `src/research_pipeline/services/research_memory.py`

**Problem:** The service uses SQLite FTS5 for full-text search. Python's bundled SQLite on
many Linux distributions (including Ubuntu 20.04) and some macOS builds is compiled without
FTS5. The cloud agent environment (Linux 6.1) may not have this. If FTS5 is unavailable,
the `CREATE VIRTUAL TABLE ... USING fts5` call will raise `OperationalError`. There is no
graceful fallback to a non-FTS search. No session plan addresses this.

**Fix required:** Add a capability check at init time. If FTS5 is unavailable, fall back to
a standard `LIKE`-based search with an explicit log warning. Alternatively, add `pysqlite-binary`
or use `chromadb` / `sqlmodel` which bundles its own SQLite.

---

### ISS-19 · `report_assembly.py` Jinja2 templates are not version-controlled alongside prompts (Medium)

**Location:** `src/research_pipeline/services/report_assembly.py`

**Problem:** Agent prompts are version-tracked by `PromptRegistry` via SHA256 hashing. The
Jinja2 report templates (used in `ReportAssemblyService`) are not registered in
`PromptRegistry`. If a template changes, `SelfAuditPacket.prompt_drift_reports` will not
detect it. For an institutional-grade platform claiming full audit trail, a report that
changes silently due to a template edit is a governance gap. No session plan adds template
hashing to the registry.

**Fix required:** Extend `PromptRegistry` to also track Jinja2 templates. Or, at minimum,
include a `template_hash` in `FinalReport` and `SelfAuditPacket`.

---

## SECTION 4 — Frontend / Streamlit Issues

### ISS-20 · `app.py` session state key `"result"` is inconsistent with `"run_result"` used elsewhere (High)

**Location:** `src/frontend/app.py` line 1187–1190

**Problem:** The audit packet is read from `st.session_state.get("result")` in the latency
display section. The rest of `app.py` uses `st.session_state.get("run_result")`. This means
the latency/rebalancing summary panel in the Observability expander silently shows nothing
after every real pipeline run — the `_ap` dict is always `{}`. No session plan fixes this key
inconsistency.

**Fix required:** Replace `st.session_state.get("result")` with
`st.session_state.get("run_result")` at line 1187 and audit the full file for any other
`"result"` vs `"run_result"` mismatches.

---

### ISS-21 · `pipeline_runner.py` deprecation warning does not prevent it from being imported (Medium)

**Location:** `src/frontend/pipeline_runner.py`

**Problem:** ACT-S6-4 added a `DeprecationWarning` on import but left the full 1,851-line
file intact. Any code — including test files, scripts, or accidental IDE imports — that
imports from `pipeline_runner.py` will silently use the old orchestration path. The warning
is easy to suppress. TRACKER.md §2 still lists A-1 as "Critical / open" in the lower
duplicate section. No session plan schedules removing the file or reducing it to a true stub
that only delegates to `pipeline_adapter`.

**Fix required:** Replace the full `pipeline_runner.py` body with a minimal stub that imports
`PipelineEngineAdapter` from `pipeline_adapter` and re-exports any symbols callers expect.
This eliminates the dual-engine risk without breaking existing import paths.

---

### ISS-22 · Streamlit "Market Overview" macro tab (Session 12 MAC-7) has no defined data refresh mechanism (Medium)

**Location:** Planned `src/frontend/app.py` — new "Market Overview" tab

**Problem:** MAC-7 adds a Macro Dashboard tab to Streamlit with live FRED and RBA data. The
`EconomicIndicatorService` has a 1-hour in-memory TTL cache. Streamlit reruns the entire
script on any widget interaction. A user toggling between tabs will trigger multiple
`EconomicIndicatorService` calls, all of which may race against the 1-hour TTL. Streamlit's
session state and caching decorators (`@st.cache_data`) need to be used correctly, or the
macro tab will make live FRED API calls on every interaction, burning through the FRED free
tier (120 requests/minute) in seconds for multi-user deployments.

**Fix required:** Wrap `EconomicIndicatorService.fetch()` calls in `@st.cache_data(ttl=3600)`
or store results in `st.session_state` with an explicit timestamp check. The session plans do
not specify this caching strategy.

---

### ISS-23 · No Streamlit component tests exist or are planned (Medium)

**Location:** `tests/` — entire directory

**Problem:** ARCHITECTURE.md §9 testing layer and TRACKER.md §5 both note that "Frontend
Streamlit components [are] untested". The 607-test suite covers backend services, agents,
schemas, and engine integration. All planned session tests (S11–S14, E items) add backend
unit and integration tests. No session plan schedules Streamlit UI component tests. Any
regression in `app.py` — broken download buttons, wrong session state key, broken PDF
generation, broken chart rendering — will be undetected by CI.

**Fix required:** Add at minimum a `test_app_smoke.py` using `streamlit.testing.v1.AppTest`
to verify: (a) the app loads without exception, (b) key session state initialisation works,
(c) PDF download helper functions produce non-empty output, (d) the pipeline runner adapter
is correctly imported.

---

## SECTION 5 — Dependency & Infrastructure Issues

### ISS-24 · `arch` library not in `requirements.txt` but required by E-2 GARCH (Medium)

**Location:** `requirements.txt` + planned `services/risk_engine.py` (E-2)

**Problem:** IMPROVEMENTS.md E-2 implements GARCH(1,1) using the `arch` library. This package
is not in `requirements.txt`. The `hmmlearn` library (required by E-3 HMM regime detection) is
also absent. Neither will install automatically. Production deployments and CI will fail with
`ModuleNotFoundError` when these features are called.

**Fix required:** Add `arch>=5.0` and `hmmlearn>=0.3` to `requirements.txt` when E-2 and E-3
are implemented. Also add `scipy>=1.10` which `arch` depends on and `transformers>=4.30` for
FinBERT (E-10). None of these are currently listed.

---

### ISS-25 · `docker-compose.yml` is on the backlog but no `Dockerfile` exists (Medium)

**Location:** Root directory — planned by IMPROVEMENTS.md Operations checklist

**Problem:** IMPROVEMENTS.md Part F Operations checklist includes
`docker-compose.yml for local production deployment`. No `Dockerfile` exists. Without a base
image definition there is nothing for `docker-compose.yml` to reference. The environment
variables, PYTHONPATH setup, Streamlit port exposure, and volume mounts for `reports/`,
`artifacts/`, and `data/` must all be specified. No session plan schedules writing the
`Dockerfile`.

**Fix required:** Write `Dockerfile` (Python 3.11-slim base, copy src/, pip install -r
requirements.txt, EXPOSE 8501, CMD streamlit run). Then write `docker-compose.yml` referencing
it. These are prerequisites for any production deployment.

---

### ISS-26 · `pyproject.toml` and `requirements.txt` are not synchronised (Low)

**Location:** `pyproject.toml` + `requirements.txt`

**Problem:** Both files define dependencies independently. No tooling enforces that they
stay in sync. `requirements.txt` pins 18 packages. `pyproject.toml` likely has a different
or overlapping set. Any new dependency added to one (e.g. `arch`, `hmmlearn`) must be
manually added to both. This is a standard engineering hygiene issue but will cause subtle
"works in dev, fails in CI" bugs as sessions add packages.

**Fix required:** Make `requirements.txt` the single source of truth and configure
`pyproject.toml` to reference it (`dependencies = []` with a note to run `pip install -r
requirements.txt`), or move to a proper lock-file tool (`pip-tools` generating
`requirements.txt` from `pyproject.toml`).

---

## SECTION 6 — Testing Coverage Gaps

### ISS-27 · No integration test covers a full pipeline run with live API keys (High)

**Location:** `tests/test_smoke_pipeline.py` and CI workflows

**Problem:** `test_smoke_pipeline.py` runs 19 tests against a fully mocked engine. The
weekly CI job (`weekly_live_data.yml`) validates `NVDA` and `MSFT` yfinance schema only —
it does not run a full 15-stage pipeline end-to-end with live FMP, Finnhub, and LLM calls.
After Sessions 11–14 add `EconomicIndicatorService` (FRED), `EconomyAnalystAgent`,
`MacroScenarioService`, and ASX data routing, there is no CI path that validates these live
integrations. A silent FRED API change, a Finnhub schema change, or a new LLM model version
could break production without any CI signal.

**Fix required:** Extend `weekly_live_data.yml` to run a minimal 2-ticker pipeline end-to-end
with live APIs and assert `run_status == COMPLETED`. Gate on this in a separate `nightly_e2e`
workflow that requires all API secrets to be present.

---

### ISS-28 · Agent prompt regression CI covers current 12 prompts but not new Session 12+ prompts (Medium)

**Location:** `tests/test_prompt_regression.py` + `src/research_pipeline/services/prompt_registry.py`

**Problem:** ACT-S9-2 wired `PromptRegistry` to detect drift across "all 14 agents". Currently
there are 12 `.md` prompt files in `prompts/`. Session 12 adds `EconomyAnalystAgent` with a
new prompt. The prompt regression test in `test_prompt_regression.py` calls
`check_all_drift()` over agents registered at runtime. If `EconomyAnalystAgent` is not
instantiated in the test fixture (it currently does not exist), its prompt will never be
baseline-registered and drift will go undetected.

**Fix required:** When adding `EconomyAnalystAgent` (and any other Session 12+ agents),
explicitly add them to the registry scan in `test_prompt_regression.py` and in
`engine._scan_prompt_registry()`.

---

### ISS-29 · No tests for ASIC/AFSL report disclosures (Session 14 target) (Low)

**Location:** Planned `tests/test_session14.py`

**Problem:** Session 14 adds AU-format FSG reference, AFSL disclaimer, and ASIC § 1013D
disclosure to report output. IMPROVEMENTS.md Part F checklist item: "AU-format disclosures
(FSG, AFSL, ASIC § 1013D) in report footer." These are compliance-critical strings that
must appear verbatim in every client-facing report. No test is currently planned to assert
that these strings appear in the `FinalReport` output for AU-profile clients. A refactor of
`report_assembly.py` could silently drop them.

**Fix required:** `test_session14.py` must include assertions that verify AFSL disclaimer
text appears in the assembled report when `ClientProfileSchema.au_residency = True`. This
should be treated as a compliance regression test, not an optional unit test.

---

### ISS-30 · `SuperannuationMandateService` (Session 14) has no cross-run mandate breach history (Medium)

**Location:** Planned `src/research_pipeline/services/superannuation_mandate.py`

**Problem:** IMPROVEMENTS.md Part D specifies `SuperannuationMandateService` with APRA SPS 530
diversification checks. The mandate gate is added to Stage 3. However, super fund mandate
compliance under APRA requires not just point-in-time checks but **trend monitoring** —
e.g. a portfolio that is individually compliant today but has been drifting towards a
concentration breach over 3 consecutive runs should trigger an early warning. No session plan
includes cross-run mandate breach trending in `SelfAuditPacket` or in the Observability tab.

**Fix required:** Add `mandate_breach_history: list[MandateTrendPoint]` to `SelfAuditPacket`
and surface it in the Observability panel. This is consistent with the E-9 cross-run trend
alert pattern already planned for DCF/VaR/ESG metrics.

---

## SECTION 7 — Documentation & Consistency Issues

### ISS-31 · `ARCHITECTURE.md §10` still describes `app.py` importing from legacy `pipeline_runner` (Low)

**Location:** `ARCHITECTURE.md` lines 527–530

**Problem:** §10 states: *"The remaining gap is that `app.py` still imports from
`pipeline_runner` — swapping to `pipeline_adapter` is the next convergence step."* This was
fixed in ACT-S6-4. The architecture document has not been updated to reflect the completed
state. The scorecard still lists "Frontend operator experience: 8.0 — `app.py` still imports
from legacy `pipeline_runner`" as a gap. Similarly the directory map in §11 still shows
`pipeline_runner.py` as "Async bridge for UI ↔ engine" rather than a deprecated stub.

**Fix required:** Update `ARCHITECTURE.md §10` component scorecard and §11 directory map to
reflect the current actual state (adapter in use, pipeline_runner deprecated).

---

### ISS-32 · `TRACKER.md` has two contradictory "Status Summary" sections (Low)

**Location:** `TRACKER.md` lines 9–28 and lines 193–201

**Problem:** The file has two `## Status Summary` blocks. The first (current) correctly shows
sessions 1–10 complete and ARC/Sessions 11–14 as TODO. The second (stale, lines 193–201)
shows "4 open architectural debt items" including A-1 (`pipeline_runner.py`) as "Critical /
open" even though it was resolved in Session 6. This creates confusion when referencing the
tracker: a reader scanning for architectural debt items finds conflicting signals about the
A-1 status.

**Fix required:** Remove or clearly archive the second stale Status Summary section. Merge the
two sections into one authoritative status table.

---

### ISS-33 · `PIPELINE_STAGES.md` describes "14 stages" but engine has 15 (Stages 0–14) (Low)

**Location:** `PIPELINE_STAGES.md` — stage count references

**Problem:** `PIPELINE_STAGES.md` uses "14-stage pipeline" in its introduction while the
engine implements stages 0–14 (15 stages). `PROJECT_README.md` correctly documents "15
stages." `ARCHITECTURE.md §3` correctly shows stages 0–14. The mismatch in
`PIPELINE_STAGES.md` is a documentation consistency issue that would confuse any engineer
reading it alongside the code.

**Fix required:** Update `PIPELINE_STAGES.md` to consistently state "15 stages (0–14)".

---

## SECTION 8 — Production-Readiness Gaps Not Covered by Any Session

### ISS-34 · No database persistence — all run history is in flat JSON files (High)

**Location:** `src/research_pipeline/services/run_registry.py`

**Problem:** `RunRegistryService` persists `RunRecord` objects to individual JSON files.
ARCHITECTURE.md §13.9 Operations lists "Database persistence — replace JSON files with
PostgreSQL or SQLite for run history" as a brainstorm item. No session plan (S11–S14) or E
item addresses this. At institutional scale (daily runs, 17 tickers, 50+ runs/year), the
flat-file approach creates: (a) no query capability, (b) no atomic writes (partial write =
corrupt run record), (c) no concurrent access safety. `ResearchMemoryService` uses SQLite for
the FTS store, but run records remain in flat JSON.

**Fix required:** Migrate `RunRegistryService` to SQLite (already available via SQLAlchemy
which is in `requirements.txt`). The schema is already defined as Pydantic models that map
trivially to SQL tables.

---

### ISS-35 · No API rate-limit backoff in `MarketDataIngestor` for FMP/Finnhub quota exhaustion (Medium)

**Location:** `src/research_pipeline/services/market_data_ingestor.py`

**Problem:** `ingest_universe()` uses `asyncio.gather` with a semaphore for parallelism. The
semaphore controls concurrency but not rate. FMP free tier allows 250 requests/day; Finnhub
free tier allows 60 requests/minute. With 17 tickers making multiple endpoint calls each, a
single Stage 2 run can exhaust the daily FMP quota. When quota is exhausted, FMP returns HTTP
429. The current code has basic retry logic but no exponential backoff and no daily budget
tracking that would stop the run before hitting the limit. `QuotaManager` exists in
`cache_layer.py` but is not wired to `MarketDataIngestor`. No session plan wires this.

**Fix required:** Wire `QuotaManager.request_budget("fmp", n_calls=17)` before calling
`ingest_universe()` and propagate quota-exceeded errors to gate Stage 2 with a clear message.

---

### ISS-36 · `SelfAuditPacket.llm_cost_usd` is not populated (Medium)

**Location:** `src/research_pipeline/schemas/governance.py` + `engine.py`

**Problem:** `SelfAuditPacket` has a `llm_cost_usd` field referenced in ARCHITECTURE.md §13.9
Operations ("LLM cost tracking — per-run token usage and USD cost in `SelfAuditPacket`"). The
field exists on the schema but is never populated in `_emit_audit_packet()`. Token counts are
not extracted from LLM responses. No session plan adds this. After all sessions, every audit
packet will have `llm_cost_usd = 0.0` or `None`.

**Fix required:** Extract `usage.input_tokens` and `usage.output_tokens` from Anthropic
response objects (available on `response.usage`) and OpenAI response objects (available on
`response.usage`). Accumulate across all agents and store in `SelfAuditPacket`. This is a
low-effort, high-governance-value addition.

---

### ISS-37 · `CacheLayer` is instantiated in `engine.py` but never used by any service (Medium)

**Location:** `src/research_pipeline/services/cache_layer.py` + `engine.py`

**Problem:** `engine.py` instantiates `CacheLayer` and `QuotaManager` in `__init__`. Neither
is passed to `MarketDataIngestor`, `DCFEngine`, `ESGService`, or any other service that would
benefit from caching. Repeated pipeline runs will re-fetch the same market data (same tickers,
same day) at full API cost. No session plan wires `CacheLayer` into any service.

**Fix required:** At minimum, pass `cache_layer` to `MarketDataIngestor.__init__()` and have
`ingest_universe()` check the cache before making API calls. This would directly reduce API
costs and run time for repeated runs.

---

### ISS-38 · No graceful shutdown / cancellation mechanism for async pipeline runs (Medium)

**Location:** `src/research_pipeline/pipeline/engine.py` + `src/frontend/pipeline_adapter.py`

**Problem:** The pipeline runs via `asyncio.gather()` for parallel stages and sequential
`await` calls for serial stages. If a Streamlit user clicks "Stop" or navigates away while
a pipeline run is in progress, the underlying `asyncio.Task` is not cancelled. LLM API calls
continue to run (and consume tokens and cost money) even with no consumer. There is no
`asyncio.Task` cancellation handler, no `CancelledError` catch that writes a CANCELLED
`RunStatus` to the registry, and no cleanup of partial stage outputs.

**Fix required:** Wrap `run_full_pipeline()` in a cancellable `asyncio.Task`. Register a
`CancelledError` handler that writes `RunStatus.CANCELLED` and calls `_emit_audit_packet()`.
Expose a `cancel()` method on `PipelineEngineAdapter`.

---

## SECTION 9 — Completeness of the E-Items (Net-New Additions)

The following E-items from IMPROVEMENTS.md are planned but have gaps in their own
specifications that will leave residual issues even after implementation.

### ISS-39 · E-9 Cross-run trend alerts: no alert threshold configuration (Medium)

**Problem:** E-9 alerts when DCF, VaR, or ESG changes >10% vs previous run. The 10% threshold
is hardcoded in the spec. No session plan adds this to `configs/thresholds.yaml` or
`PipelineConfig`. An institutional platform must allow clients to configure alert sensitivity.
A super fund with tighter drift tolerances and a HNW client with higher tolerance need
different thresholds.

**Fix required:** Add `research_trend_alert_threshold_pct: float = 10.0` to
`Thresholds` in `config/loader.py`. Read it in `ResearchMemoryService.check_trends()`.

---

### ISS-40 · E-7 Interactive HTML report: no plan for report versioning or archival (Medium)

**Problem:** E-7 adds an HTML download alongside the existing PDF. The session plan does not
address how HTML reports are stored relative to the existing `reports/` directory, whether
they appear in `RunRegistry`, or whether they are linked in `SelfAuditPacket`. Two parallel
download formats with no unified archival creates the same split-brain problem that existed
between `pipeline_runner.py` and `engine.py`.

**Fix required:** Extend `FinalReport` schema to include `html_path: Optional[str]` alongside
existing `markdown_path` and `pdf_path`. Store all three in the same `artifacts/{run_id}/`
directory. Register the HTML path in `RunRecord`.

---

### ISS-41 · E-10 FinBERT sentiment NLP: no batching or rate-limit strategy (Medium)

**Problem:** E-10 plans FinBERT scoring for each headline per ticker. With 17 tickers × 10
headlines each, that is 170 forward-passes through a transformer model per pipeline run.
FinBERT inference on CPU takes ~100–200ms per headline. Total: 17–34 seconds of blocking
compute in Stage 2 ingestion. No session plan addresses batching, GPU detection, or a minimum
headline count before sentiment is considered reliable. If news for a ticker is unavailable,
the plan returns a `SentimentPacket` with `score = None` — but the spec does not define what
the sector agent should do with a `None` sentiment.

**Fix required:** Define minimum headline count (e.g. n ≥ 3) below which `SentimentPacket`
returns `signal = "insufficient_data"`. Use `transformers.pipeline` with batched inference
(`batch_size=16`) to reduce latency. Add `sentiment_data_quality: Literal["live", "insufficient", "unavailable"]` to the packet.

---

## Summary Table

| ID | Area | Severity | Session Plans Address It? |
|---|---|---|---|
| ISS-1 | Pipeline data-flow — macro context no schema | Critical | No |
| ISS-2 | Pipeline — stage swap breaks UI sequence display | High | No |
| ISS-3 | Pipeline — ARC-5 GenericSectorAnalyst not implemented | High | No |
| ISS-4 | Pipeline — ValuationCard → StockCard mapping unspecified | High | No |
| ISS-5 | Agent — `llm_provider_used` not in `AgentResult` | Medium | No |
| ISS-6 | Services — Golden tests 2 categories have no fixtures | High | No |
| ISS-7 | Infrastructure — FINNHUB_API_KEY missing from `.env.example` | Medium | No |
| ISS-8 | Schemas — `qualitative.py` not exported from `__init__` | Medium | No |
| ISS-9 | Agent — `_validate_output_quality` is non-fatal | High | No |
| ISS-10 | Agent — Gemini import mismatch `google-genai` vs `google.generativeai` | High | No |
| ISS-11 | Agent — `OrchestratorAgent` never called in pipeline | Medium | No |
| ISS-12 | Agent — Macro agents have no required output key contracts | High | No |
| ISS-13 | Agent — Prompts not adapted for ASX-listed stocks | High | No |
| ISS-14 | Services — `EconomicIndicatorService` fallback data quality not signalled | Medium | No |
| ISS-15 | Services — `LiveReturnStore` has no TTL eviction | Medium | No |
| ISS-16 | Services — BHB benchmark leg still synthetic after E-4 | High | No |
| ISS-17 | Services — ESG profiles have no ASX coverage | High | No |
| ISS-18 | Services — SQLite FTS5 may not be available on all platforms | Medium | No |
| ISS-19 | Services — Jinja2 templates not in `PromptRegistry` | Medium | No |
| ISS-20 | Frontend — session state key `"result"` vs `"run_result"` | High | No |
| ISS-21 | Frontend — `pipeline_runner.py` never truly reduced to stub | Medium | No |
| ISS-22 | Frontend — Macro tab has no Streamlit caching strategy | Medium | No |
| ISS-23 | Testing — no Streamlit component tests | Medium | No |
| ISS-24 | Dependencies — `arch`, `hmmlearn`, `transformers` missing from `requirements.txt` | Medium | Partial (will be added when E-2/E-3/E-10 implemented, but not pre-specified) |
| ISS-25 | Infrastructure — no `Dockerfile` for planned `docker-compose.yml` | Medium | No |
| ISS-26 | Infrastructure — `pyproject.toml` and `requirements.txt` unsynchronised | Low | No |
| ISS-27 | Testing — no live end-to-end CI pipeline test | High | No |
| ISS-28 | Testing — new Session 12 agents not added to prompt regression test | Medium | No |
| ISS-29 | Testing — no compliance test for AFSL/ASIC disclosure strings | Low | No |
| ISS-30 | Services — super mandate has no cross-run breach trend history | Medium | No |
| ISS-31 | Documentation — `ARCHITECTURE.md §10` describes resolved issues as open | Low | No |
| ISS-32 | Documentation — `TRACKER.md` has two contradictory Status Summary blocks | Low | No |
| ISS-33 | Documentation — `PIPELINE_STAGES.md` says "14 stages" not "15" | Low | No |
| ISS-34 | Production — run history in flat JSON, no database | High | No |
| ISS-35 | Production — no FMP/Finnhub rate-limit budget enforcement | Medium | No |
| ISS-36 | Production — `SelfAuditPacket.llm_cost_usd` never populated | Medium | No |
| ISS-37 | Production — `CacheLayer` instantiated but never passed to services | Medium | No |
| ISS-38 | Production — no async pipeline cancellation handler | Medium | No |
| ISS-39 | E-9 — trend alert threshold hardcoded, not in config | Medium | No |
| ISS-40 | E-7 — HTML report not wired into RunRegistry/FinalReport schema | Medium | No |
| ISS-41 | E-10 — FinBERT sentiment has no batching or data-quality signalling | Medium | No |

**Total issues identified: 41**  
**Critical: 1 · High: 15 · Medium: 19 · Low: 6**

---

## Prioritised Fix Order

Based on correctness impact and implementation risk:

1. **ISS-20** — session state key bug (`"result"` vs `"run_result"`) — 1-line fix; currently breaks the Observability UI for every run
2. **ISS-10** — Gemini import mismatch — 2-line fix; currently breaks the fallback chain
3. **ISS-8** — `qualitative.py` not exported — 1-line fix; currently breaks any `from research_pipeline.schemas import ...` call for qualitative types
4. **ISS-7** — `FINNHUB_API_KEY` missing from `.env.example` — 1-line fix; blocks new developers
5. **ISS-9** — non-fatal quality validation — design decision required; affects all agents
6. **ISS-1** — `MacroContextPacket` schema — required before ARC-1 wiring is safe
7. **ISS-4** — `ValuationCard → StockCard` mapping — required before ARC-2 produces correct reports
8. **ISS-3** — `GenericSectorAnalystAgent` — required for ARC-5 to fully close
9. **ISS-16** — BHB benchmark still synthetic — blocks Performance Attribution score target
10. **ISS-12** — Macro agents no required key contracts — required before `_get_macro_context()` is trusted

---

*Document generated: March 28, 2026. Cross-referenced against IMPROVEMENTS.md, TRACKER.md, ARCHITECTURE.md, and direct code audit of `engine.py`, `base_agent.py`, `app.py`, `schemas/__init__.py`, `golden_tests.py`, `requirements.txt`, and `.env.example`.*
