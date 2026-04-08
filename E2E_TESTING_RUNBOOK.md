# E2E Testing Runbook

## Purpose

This file records how end-to-end testing was performed on the FastAPI pipeline in April 2026, what was fixed, what providers were called, and what blocked or enabled a fully publishable run.

## Active backend under test

Backend entrypoint:
- [src/api/main.py](src/api/main.py)

Pipeline engine under test:
- [src/research_pipeline/pipeline/engine.py](src/research_pipeline/pipeline/engine.py)

Frontend/API runtime path under test:
- [frontend/src/lib/runtime-settings.ts](frontend/src/lib/runtime-settings.ts)
- [frontend/src/app/runs/new/page.tsx](frontend/src/app/runs/new/page.tsx)

## How the tests were run

### Standard backend startup

The backend was started with:
- `python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000`

### Health verification

Before each run, the backend was verified with:
- `GET /health`
- `GET /health/details`

`/health/details` was used to confirm:
- `.env` was loaded
- provider credentials were present as booleans only
- the active backend model
- the current `LLM_MAX_TOKENS`

### Run creation path

Live E2E tests were performed against:
- `POST /api/v1/runs`
- `GET /api/v1/runs/{run_id}`
- `GET /api/v1/runs/{run_id}/result`
- `GET /api/v1/runs/{run_id}/stages`

### Artifact inspection

After failures, stage artifacts were inspected in:
- [storage/artifacts](storage/artifacts)
- [storage/audits](storage/audits)

## Models used during testing

### Current FastAPI backend path

For the live tests documented here, the active backend model was:
- `claude-sonnet-4-6`

Evidence:
- [src/research_pipeline/pipeline/engine.py](src/research_pipeline/pipeline/engine.py#L203-L209)
- [src/api/main.py](src/api/main.py)
- `/health/details` runtime output during testing

Important:
- The current FastAPI backend still wires most reasoning agents from one shared `settings.llm_model`.
- The legacy Streamlit path still contains per-stage defaults in [src/frontend/app.py](src/frontend/app.py#L653-L661), but that is not the active backend execution path used by these tests.

### Testing-only model experiments already performed

These were also tested earlier in the session:
- low-cost smoke with `gpt-4o-mini`
- DeepSeek compatibility with `deepseek-chat`
- token-budget passes at `10`, `512`, and `2048`

Those were testing modes, not the restored default runtime.

## External APIs/services exercised

### Data APIs

The live backend path calls:
- FMP
- Finnhub
- SEC API
- Benzinga
- yfinance fallback for price rescue when both FMP and Finnhub miss
- FRED-backed economic service path, with synthetic fallback when live macro data is unavailable

Relevant code:
- [src/research_pipeline/services/market_data_ingestor.py](src/research_pipeline/services/market_data_ingestor.py)
- [src/research_pipeline/services/sec_api_service.py](src/research_pipeline/services/sec_api_service.py)
- [src/research_pipeline/services/benzinga_service.py](src/research_pipeline/services/benzinga_service.py)
- [src/research_pipeline/services/economic_indicator_service.py](src/research_pipeline/services/economic_indicator_service.py)

### LLM providers available in code

The shared agent layer supports:
- Anthropic
- OpenAI
- Gemini
- OpenAI-compatible DeepSeek testing path

Relevant code:
- [src/research_pipeline/agents/base_agent.py](src/research_pipeline/agents/base_agent.py)

### What was actually called in the latest live runs

Across the latest live runs:
- primary reasoning model before provider exhaustion: `claude-sonnet-4-6`
- successful publish-path verification model: `gpt-4o`
- provider paths exercised: Anthropic and OpenAI
- macro economic service path also ran before Stage 8
- Google/Gemini Deep Research was not active in the normal path because `GOOGLE_API_KEY` was absent in diagnostics

## What was fixed during this E2E campaign

### 1. Remote frontend/backend routing

Problem:
- frontend was trying to call stale loopback URLs in remote preview sessions

Fix:
- [frontend/src/lib/runtime-settings.ts](frontend/src/lib/runtime-settings.ts)
- [frontend/src/app/settings/page.tsx](frontend/src/app/settings/page.tsx)

### 2. Backend `.env` loading

Problem:
- FastAPI backend was not loading the project `.env`

Fix:
- [src/api/main.py](src/api/main.py)

### 3. Single-ticker custom run support

Problem:
- frontend allowed single-name custom runs, but Stage 1 still required at least 3 tickers

Fix:
- [src/research_pipeline/pipeline/gates.py](src/research_pipeline/pipeline/gates.py)
- [tests/test_gates.py](tests/test_gates.py)

### 4. Stage 5 evidence normalization

Problem:
- Stage 5 dropped valid claims because agent-side aliases did not match canonical schema enums

Fix:
- [src/research_pipeline/pipeline/engine.py](src/research_pipeline/pipeline/engine.py#L678)
- [tests/test_session19.py](tests/test_session19.py#L699)

Outcome:
- live run advanced past Stage 5 after restart

### 5. Stage 8 macro fallback

Problem:
- `macro_strategist` sometimes failed structured output, blocking Stage 8

Fix:
- deterministic fallback added in [src/research_pipeline/pipeline/engine.py](src/research_pipeline/pipeline/engine.py)
- regression in [tests/test_session12.py](tests/test_session12.py)

Outcome:
- live run advanced past Stage 8

### 6. Stage 7 valuation fallback

Problem:
- `valuation_analyst` was returning narrative/non-JSON output

Fix:
- deterministic valuation fallback in [src/research_pipeline/pipeline/engine.py](src/research_pipeline/pipeline/engine.py)
- regression in [tests/test_session13.py](tests/test_session13.py)

Outcome:
- live run advanced past Stage 7

### 7. Stage 11 review fallback

Problem:
- reviewer model often failed to emit structured `publication_status`
- review parsing also needed compatibility with `publication_status` rather than only `status`
- live red-team output used `section_2_falsification_tests`

Fix:
- review fallback and schema compatibility in [src/research_pipeline/pipeline/engine.py](src/research_pipeline/pipeline/engine.py)
- regressions in [tests/test_session13.py](tests/test_session13.py)

Outcome:
- live run advanced past Stage 11

### 8. Stage 12 portfolio fallback

Problem:
- `portfolio_manager` returned non-JSON narrative

Fix:
- deterministic Stage 12 fallback in [src/research_pipeline/pipeline/engine.py](src/research_pipeline/pipeline/engine.py)
- regression in [tests/test_session13.py](tests/test_session13.py)

Outcome:
- Stage 12 now reaches governance evaluation with a valid fallback portfolio package

### 9. Provider exhaustion fallback hardening

Problem:
- Anthropic returned a billing/credit exhaustion error during a diversified live run, and the shared LLM retry logic did not classify that message as quota-like fallback noise

Fix:
- retry classification expanded in [src/research_pipeline/agents/base_agent.py](src/research_pipeline/agents/base_agent.py)
- regression added in [tests/test_phase1_hardening.py](tests/test_phase1_hardening.py)

Outcome:
- provider credit exhaustion is now treated like quota exhaustion, so the shared agent layer can continue to the next configured provider instead of hard-failing immediately

### 10. Completed-run Stage 14 summary normalization

Problem:
- a live run could finish successfully on disk while the API summary still showed stale `Stage 14 failed` noise from transient event ordering

Fix:
- completed-run summary handling corrected in [src/api/services/run_manager.py](src/api/services/run_manager.py)
- regression added in [tests/test_session16.py](tests/test_session16.py)

Outcome:
- completed runs now report Stage 14 as complete and clear stale failed-stage noise in API summaries

### 11. Frontend live-follow and operator feedback hardening

Problem:
- live following relied too heavily on SSE alone
- the run detail view showed raw stage status and event flow, but not enough operator guidance about what each stage was doing or what to inspect when the feed dropped or a stage blocked

Fix:
- run detail live-follow now hydrates from both SSE and polling snapshots of run summary + stage status
- stream state is surfaced explicitly in the UI as `LIVE`, `POLLING`, `ISSUE`, or `CLOSED`
- stage-specific operator guidance was added so the UI explains what the active stage is doing, what success looks like, and where to look if it stalls
- blocker messaging was expanded to show actionable next steps instead of only raw error text
- light browser haptic feedback was added for stage starts, completions, and failures where vibration is supported

Relevant code:
- [frontend/src/app/runs/[run_id]/page.tsx](frontend/src/app/runs/[run_id]/page.tsx)
- [frontend/src/components/pipeline/live-event-feed.tsx](frontend/src/components/pipeline/live-event-feed.tsx)
- [frontend/src/lib/store.ts](frontend/src/lib/store.ts)
- [frontend/src/lib/live-stage-feedback.ts](frontend/src/lib/live-stage-feedback.ts)

Outcome:
- live following is clearer for operators and more resilient when the event stream drops mid-run

## Latest live results

### Latest normal live single-name run

Run:
- `run_20260407_083629_33540781`

Observed stage progression:
- passed runtime through Stages 5, 6, 7, 8, 9, 10, 11
- reached Stage 12
- blocked at Stage 12

### Why Stage 12 still blocks

This is currently a governance/mandate outcome, not the earlier schema/runtime failures.

Observed committee rejection on the underlying artifact run:
- risk officer rejected concentration: `HHI=10000.0 exceeds 2500 limit`
- compliance rejected mandate violations:
  - `AAPL: 100.0% > 15.0% max`
  - `Sector 'other': 100.0% > 40.0% max`
  - `Only 1 positions, minimum is 8`

Relevant artifact:
- [storage/artifacts/run_20260407_083629_2ae1ca06/stage_12.json](storage/artifacts/run_20260407_083629_2ae1ca06/stage_12.json)

Interpretation:
- The pipeline can now reach the portfolio governance layer with a single-name custom run.
- A single-name run is not publishable under the current investment committee and mandate rules.
- To get a true end-to-end publish pass, the next live run should use a diversified custom universe with at least 8 names and no single-name weight above policy limits.

### Diversified publish-path verification run

Run:
- `run_20260407_234702_49af4092`

Universe used:
- `NVDA, AVGO, TSM, CEG, VST, PWR, ETN, FCX`

Model used:
- `gpt-4o`

Observed outcome:
- live run progressed through Stages 0–13
- Stage 12 passed committee/mandate checks
- report generation completed
- Stage 14 monitoring artifact recorded `final_status: completed`

Relevant artifacts:
- [storage/artifacts/run_20260407_234702_87350327/stage_14.json](storage/artifacts/run_20260407_234702_87350327/stage_14.json)
- [reports/report_run_20260407_234702_87350327_20260407.md](reports/report_run_20260407_234702_87350327_20260407.md)

Notes:
- the API summary initially showed stale `Stage 14 failed` noise for this run even though the final artifact completed successfully
- that summary mismatch was fixed in [src/api/services/run_manager.py](src/api/services/run_manager.py) after this verification run

### Diversified Anthropic failure immediately before the successful rerun

Run:
- `run_20260407_234241_3124995a`

Observed blocker:
- Stage 5 failed because Anthropic returned insufficient-credit / billing exhaustion

Relevant artifact:
- [storage/artifacts/run_20260407_234241_06a1196f/stage_05.json](storage/artifacts/run_20260407_234241_06a1196f/stage_05.json)

Interpretation:
- this was an external provider-account issue, not a new Stage 5 schema/runtime regression
- rerunning the same diversified publish-path test on OpenAI succeeded

## Practical guidance for future runs

### If the goal is lifecycle smoke only

Use:
- single-name custom run
- standard backend model or cheap test mode

Expected result:
- the run should now progress deep into the pipeline instead of dying at Stage 5/7/8/11 schema boundaries

### If the goal is full publishable completion

Use a diversified universe:
- at least 8 names
- avoid expected >15% single-name concentration
- prefer a basket where equal-weighting is committee-compliant

Suggested custom smoke basket for publish-path validation:
- `NVDA, AVGO, TSM, CEG, VST, PWR, ETN, FCX`

### What to inspect first when a run fails

1. `/health/details`
2. `/api/v1/runs/{run_id}`
3. `/api/v1/runs/{run_id}/result`
4. `storage/artifacts/run_*/stage_XX.json`
5. `storage/audits/audit_run_*.json`

## Current status summary

As of 2026-04-07:
- runtime/configuration blockers have been fixed
- Stage 5 schema blocker is fixed
- Stage 7 schema blocker is fixed with fallback
- Stage 8 schema blocker is fixed with fallback
- Stage 11 schema blocker is fixed with fallback
- Stage 12 now fails for governance reasons on a one-name run
- a diversified live run has now completed successfully through the publish path using `gpt-4o`
- Anthropic credit exhaustion remains an external operational risk, but the platform now handles that class of provider error more gracefully
