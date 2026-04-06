# Session 19 — Data Sourcing Quality: SEC API, Benzinga, Gemini Deep Research

**Date:** April 2026  
**Branch:** `main`  
**Tests:** 1072 passing, 0 errors (↑ from 1004/1004 + 18 pre-existing errors)

---

## Objective

Session 19 targeted **DSQ-1 through DSQ-16** — the full data sourcing quality uplift plan
described in `IMPROVEMENTS.md` Part M. The goal: close the gap between the platform's
qualitative evidence quality (7.5/10) and institutional grade (9.0+/10) by wiring three
new primary data sources into the pipeline.

A post-generation audit also revealed an unwired service (`gemini_deep_research.py`),
two missing schemas (`AnalystRatingChange`, `AdverseSignal`), and 31 test failures
caused by deprecated async patterns. All were fixed in this session.

---

## Completed Work

### DSQ-1: QualitativeDataService wired into Stage 5 ✅

`QualitativeDataService` was already built in Session 18 but never called.
Wired in `engine.py` Stage 5 — all news, transcripts, filings, insider activity,
analyst actions, and sentiment now feed into the Evidence Librarian's claim ledger.

### DSQ-2 / DSQ-3 / DSQ-4: SEC API Integration ✅

`SECApiService` (`src/research_pipeline/services/sec_api_service.py`) provides:
- Per-ticker filing index (10-K/10-Q/8-K metadata) — wired into Stage 2
- 8-K material event extraction — wired into Stage 2
- 10-K MD&A and Risk Factors section extraction — wired into Stage 5
- Form 4 insider transaction data — wired into Stage 5
- XBRL key facts — wired into Stage 5

Gracefully no-ops when `SEC_API_KEY` is absent. Added to `APIKeys` in `settings.py`.

### DSQ-5 / DSQ-6 / DSQ-7 / DSQ-8: Benzinga Integration ✅

`BenzingaService` (`src/research_pipeline/services/benzinga_service.py`) provides:
- Analyst rating changes (upgrades, downgrades, initiations, price target changes) — Stage 2 + Stage 5
- Finance-native company news (demotes FMP/Finnhub to backfill role) — Stage 5
- Earnings calendar cross-check — Stage 2
- Adverse signals (downgrade clusters, negative catalysts) — Stage 10 Red Team

Gracefully no-ops when `BENZINGA_API_KEY` is absent.

### DSQ-12 / DSQ-13: Reconciliation + FMP Ratios ✅

- `consensus_reconciliation.py` exists and handles Stage 3 cross-provider checks
- `fetch_fmp_ratios()` is called in `market_data_ingestor.py` within the ingestion bundle
  (adds ROE, ROIC, FCF yield, debt/equity per ticker)

### DSQ-15: test_session19.py ✅

`tests/test_session19.py` — 50 tests covering:
- `SECApiService` with and without API keys
- `BenzingaService` with and without API keys
- Engine Stage 2 and Stage 5 enrichment wiring
- Graceful degradation on service exceptions

All 50 tests pass in isolation and in the full suite.

---

## New: GDR-1 — Gemini Deep Research Stage 4.5 ✅

`gemini_deep_research.py` (509 lines) existed in the services directory but was
**not wired into the engine**. This session completes the wiring.

| Component | Change |
|---|---|
| `engine.py` | Added `stage_4_5_deep_research()` method + `_get_active_themes()` helper |
| `engine.py` | Stage 4.5 called in `run_full_pipeline()` between Stage 4 and Stage 5 |
| `engine.py` | `GeminiDeepResearchService` instantiated in `__init__` with defensive mock-safe config |
| `config/loader.py` | Added `DeepResearchConfig` Pydantic model to `PipelineConfig` |
| `config/settings.py` | Added `gemini_api_key` reading from `GEMINI_API_KEY` env var |

**Stage 4.5 behaviour:**
- Fires between Stage 4 (Data QA) and Stage 5 (Evidence Librarian)
- Loads theme definitions from `configs/universe.yaml` (filters to active universe tickers)
- Each theme fires one Gemini Deep Research call; extracts 10–20 qualitative claims
- Claims injected as Tier-3 `DeepResearchClaim` objects via `stage_outputs[45]`
- **Non-blocking**: any failure (no API key, `google-generativeai` not installed, timeout) is absorbed and logged; pipeline always continues to Stage 5
- Config controlled by `deep_research:` key in `pipeline.yaml` (or defaults)

---

## New Schemas Added

### `AnalystRatingChange` (in `schemas/qualitative.py`) ✅

Pydantic schema representing a single analyst rating change event from Benzinga:
- Fields: `ticker`, `analyst_firm`, `action_type`, `rating_current`, `rating_prior`,
  `price_target_current`, `price_target_prior`, `published_at`, `is_adverse`, `source_tier`
- `pt_delta` property: price-target change (current − prior)
- `to_prompt_line()`: single-line summary for prompt injection

### `AdverseSignal` (in `schemas/qualitative.py`) ✅

Structured adverse signal for Stage 10 Red Team analysis:
- Signal types: `analyst_downgrade`, `price_target_cut`, `negative_catalyst`, `miss_and_lower`
- Severity levels: `low`, `moderate`, `high`, `critical`
- `from_rating_change(rc)` class method: promotes an adverse `AnalystRatingChange`
- `to_prompt_line()`: adversarial one-liner for Red Team prompt injection

Both schemas were listed in `MULTI_AGENT_BUILD_PLAN.md` as needing creation; confirmed
four other schemas (`FilingMetadata`, `MaterialEvent`, `InsiderTransaction`, `FilingSection`)
already existed in `schemas/qualitative.py` before this session.

---

## Bug Fix: Async Event Loop (13 failures + 18 errors → 0)

**Root cause:** `asyncio.get_event_loop().run_until_complete()` is deprecated in Python 3.12.
When pytest-asyncio with `asyncio_mode = "auto"` manages async tests earlier in the suite,
it closes the event loop — subsequent synchronous test methods using the deprecated pattern
see `RuntimeError: There is no current event loop in thread 'MainThread'`.

**Fix:** Replaced all occurrences with `asyncio.run()` in:
- `tests/test_session19.py` (13 occurrences → 0 failures)
- `tests/test_session7.py` (1 occurrence → 0 errors, was pre-existing)
- `tests/test_session8.py` (1 occurrence → 0 errors, was pre-existing)
- `tests/test_session9.py` (1 occurrence → preventive fix)
- `tests/test_next_section.py` (6 occurrences → preventive fix)

**Result:** 1041 → 1072 tests fully passing, 18 pre-existing errors eliminated.

---

## Deferred to Session 20

| Item | Reason for deferral |
|---|---|
| DSQ-9: `ArticleExtractionService` | Prerequisite for NewsAPI; requires URL → body scraping + chunking |
| DSQ-10: `NewsApiService` | Requires DSQ-9 complete first (publisher allowlist + article extraction) |
| DSQ-11: Wire NewsAPI into Stage 8 | Requires DSQ-9 + DSQ-10 |
| DSQ-14: Synthetic data contamination tagging | Risk engine changes + governance.py; medium-effort standalone |
| DSQ-16 (partial): `NEWS_API_KEY` config | Blocked on DSQ-9/10; `SEC_API_KEY`/`BENZINGA_API_KEY` already done |
| DSQ-17 through DSQ-32 | Full Part N items — field-level freshness, EIA/FERC, transcript parser, etc. |

---

## Test Count Summary

| Metric | Before Session 19 | After Session 19 |
|---|---|---|
| Tests passing | 1004 | **1072** |
| Test failures | 0 (+ 13 new) | **0** |
| Pre-existing errors | 18 | **0** (fixed) |
| Total clean tests | 1004 | **1072** |

---

## Files Changed / Added

| File | Change |
|---|---|
| `src/research_pipeline/pipeline/engine.py` | Stage 4.5 method, `_get_active_themes()`, `GeminiDeepResearchService` init, Stage 4.5 call in pipeline |
| `src/research_pipeline/config/loader.py` | `DeepResearchConfig` Pydantic model added; `PipelineConfig.deep_research` field; `load_pipeline_config` updated |
| `src/research_pipeline/config/settings.py` | `APIKeys.gemini_api_key` field; `GEMINI_API_KEY` env var |
| `src/research_pipeline/schemas/qualitative.py` | `AnalystRatingChange` and `AdverseSignal` schemas added (105 lines) |
| `tests/test_session19.py` | 13× `asyncio.get_event_loop().run_until_complete()` → `asyncio.run()` |
| `tests/test_session7.py` | 1× same fix (eliminates 18 pre-existing errors) |
| `tests/test_session8.py` | 1× same fix |
| `tests/test_session9.py` | 1× same preventive fix |
| `tests/test_next_section.py` | 6× same preventive fix |
| `TRACKER.md` | Updated: Session 19 ✅, test count 1072, GDR-1 complete |
| `MULTI_AGENT_BUILD_PLAN.md` | Corrected baseline, DSQ status table, schema status |

---

## Session 20 Starting Point

**Prerequisites confirmed met:**
- ✅ `SECApiService` wired and tested (DSQ-2/3/4)
- ✅ `BenzingaService` wired and tested (DSQ-5/6/7/8)
- ✅ `QualitativeDataService` wired (DSQ-1)
- ✅ `GeminiDeepResearchService` wired (GDR-1)
- ✅ 1072/1072 tests passing
- ✅ `AnalystRatingChange`/`AdverseSignal` schemas available

**Session 20 should begin with DSQ-9 (`ArticleExtractionService`) — the mandatory prerequisite
for NewsAPI integration, which is the highest remaining data quality gap.**

Refer to `IMPROVEMENTS.md` Part N (lines ~2360+) for the full DSQ-17 through DSQ-32 specs.
