# Runbook

## What this is

A runbook is the practical operating guide for the system.

- Documentation explains what the platform is, how it is structured, and what features exist.
- A runbook explains how to start it, verify it, troubleshoot it, and run standard checks safely.

This file is the operator/developer quick guide for the FastAPI + Next.js stack.

For the detailed April 2026 live testing ledger, provider/model map, and latest
publish-path blocker analysis, see [E2E_TESTING_RUNBOOK.md](E2E_TESTING_RUNBOOK.md).

## Local startup

### Backend

Expected module:
- `python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000`

Health checks:
- `GET /health`
- `GET /health/details`

### Frontend

Expected command from `frontend/`:
- `npm run dev`

Default URL:
- `http://127.0.0.1:3000`

## Diagnostics

Use `GET /health/details` to confirm:
- `.env` file presence
- which credential classes are loaded (boolean only, never raw secrets)
- default LLM model
- current `LLM_MAX_TOKENS`
- storage/prompt directories
- whether API-key middleware is enabled

## Live following and operator feedback

The run detail page now follows live runs in two layers:

1. SSE live stream for real-time stage/event updates
2. snapshot polling of `/api/v1/runs/{run_id}` and `/api/v1/runs/{run_id}/stages` as a resilience fallback when the SSE stream drops

Operator-facing behavior:
- a live stream state badge shows whether the page is on live SSE, polling fallback, or a terminal closed state
- the run detail page explains what the current stage is doing, what success looks like, and what to inspect if it stalls
- blocker panels now surface clearer next-step guidance instead of only raw error text
- supported browsers receive light haptic/vibration cues on stage start, stage completion, and failures

If live following looks stale:
1. Check whether the page is in `LIVE`, `POLLING`, or `ISSUE` mode
2. Inspect `/health/details`
3. Inspect `/api/v1/runs/{run_id}`
4. Inspect `/api/v1/runs/{run_id}/stages`
5. Open the Stage Detail tab for the blocked stage and review its gate reason/output

## Economic smoke mode

For a low-cost pipeline smoke run, start the backend with:
- `LLM_MAX_TOKENS=10`

This is intended for lifecycle verification, not research quality.

Expected behavior in this mode:
- stage 0–4 deterministic plumbing can run normally
- the run should start, emit events, and reach a terminal state
- LLM-heavy stages may fail because 10 tokens is too small for full structured JSON outputs

Use this mode to verify:
- startup
- API connectivity
- run creation
- event updates
- failure handling
- final status retrieval

## Recommended verification order

1. Start backend
2. Check `/health`
3. Check `/health/details`
4. Start frontend
5. Open New Run
6. Launch a small custom run
7. Confirm the run progresses or fails with a clear blocker
8. Inspect `/runs`, `/runs/[run_id]`, `/audit`, and `/quant`

## Common failure patterns

### Backend unreachable
Usually caused by:
- backend not started
- stale frontend backend URL override
- remote preview using `localhost` instead of the built-in proxy

### Stage 0 blocked
Usually caused by:
- missing provider keys
- config not loaded correctly

### Custom basket launch blocked
Usually caused by:
- invalid ticker symbols
- unresolved live quote check

## Current note

The platform is feature-rich, but the main remaining gap is production hardening of true end-to-end workflows across frontend + backend, rather than core pipeline capability.