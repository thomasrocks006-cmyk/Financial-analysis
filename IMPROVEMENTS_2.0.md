# Improvements 2.0 — April 2026 Repo Audit, Re-Score, and Upgrade Path

> **Date:** April 6, 2026  
> **Method:** direct repo inspection + architecture doc review + live validation of test/build state  
> **Purpose:** capture the actual repo state after the earlier roadmap phases, then define the shortest path to materially higher scores on both (a) purpose-fit and (b) financial-firm benchmark quality.

---

## 1. Current Audit Verdict

Two scores matter:

| Score lens | Current score | Meaning |
|---|---:|---|
| **Purpose-fit** | **8.7 / 10** | Strong institutional-style AI research pipeline with a green premium frontend, browser-smoke coverage, DB-backed registry, and better product truthfulness |
| **Financial-firm benchmark** | **7.9 / 10** | More credible after CI hardening, SQLite-backed persistence, initial engine decomposition, and now browser-level regression proof, but still short of full firm-grade operating maturity |

---

## 2. Why the Platform Still Scores Well

The repo has several genuinely strong qualities that are better than a typical prototype:

1. **Pipeline design is coherent.** The `PipelineEngine` + gate architecture remains the right core model: deterministic facts, LLM judgment, hard stage gates.
2. **Governance is a real strength.** Gate logic, review stages, audit packets, provenance, and claim-ledger thinking are materially above average for an AI-driven financial workflow.
3. **Backend breadth is real.** DCF, risk, scenario, optimisation, compliance, provenance, memory, API, and reporting services exist as actual modules — not just roadmap claims.
4. **Test discipline is excellent.** The repo currently passes **1,099 tests** locally, which is a serious positive signal for engineering maturity.
5. **Institutional-memory direction is differentiated.** `ResearchMemory` gives the repo a credible base for cross-run learning and research recall.

---

## 3. Why the Scores Are Not Higher Yet

The ceiling is no longer mainly “missing ideas.” It is now mostly a **truthfulness + production-hardness + convergence** problem.

### The most important current drags

| Drag | Why it matters | Score impact |
|---|---|---|
| **Browser-level regression depth is still thin** | Baseline smoke coverage now exists, but it is still only a first layer rather than full route and workflow coverage | Low-medium drag on both scores |
| **Doc/runtime drift** | Several docs describe a more complete state than the code currently proves | Heavy drag on benchmark credibility |
| **Persistence is improved but still fragmented** | The registry is now DB-backed, but adjacent report/artifact metadata still needs convergence | Medium-heavy drag on benchmark score |
| **Security / production defaults still soft** | Open CORS by default and optional API-key auth are not financial-firm defaults | Medium-heavy drag |
| **Monolithic hotspots remain** | `engine.py` and `app.py` are still large risk concentrations even after the first extraction step | Medium drag |
| **CI is better, but still not full release governance** | Frontend type/build and browser smoke checks are enforced, but broader release checks are still missing | Medium drag |

---

## 4. Evidence From the April 2026 Audit

### Confirmed strengths

- Python + backend test suite: **1,102 passing tests**
- Broad backend service inventory present under `src/research_pipeline/services/`
- API layer exists and is structured under `src/api/`
- Streamlit operator console remains runnable and locally reachable on port 8501
- Playwright smoke tests now pass locally across dashboard, new-run, saved-run delete, and command-bar routing flows

### Confirmed weaknesses

- `frontend/` production build is now green
- frontend typecheck is now part of the normal validation path
- CI now treats frontend type/build and browser smoke success as required gates
- `RunRegistryService` is now SQLite-backed with legacy JSON migration support
- API security defaults are tighter, but still not fully production-grade
- the main remaining structural hotspot is `pipeline/engine.py`

---

## 5. Re-Scored Dimensions

| Dimension | Score | Notes |
|---|---:|---|
| Research process design | 8.8 | Excellent stage decomposition and role separation |
| Backend architecture | 8.2 | Strong service breadth; still too monolithic in key areas |
| Governance / controls / audit | 8.7 | One of the repo’s best qualities |
| Testing discipline | 9.2 | Major strength; much stronger than the average comparable project |
| Frontend product readiness | 8.4 | Production build/type path is clean and core browser flows are now smoke-tested |
| Operations / security / persistence | 7.5 | SQLite-backed registry and tighter defaults help materially |
| Documentation fidelity | 7.2 | Better aligned after audit, though some historical docs remain intentionally stale |

---

## 6. What Would Raise the Purpose-Fit Score Fastest

These items most directly improve “is this good for its stated purpose?”

### P0 — Must-do

1. **Expand the new browser-regression baseline**
   - keep the production build green
   - extend smoke tests into run-detail, report, audit, and provenance flows
   - validate critical user flows beyond compile-time safety

2. **Restore repo truthfulness**
   - reconcile `TRACKER.md`, `FRONTEND_COMPARISON.md`, `SESSION_18_SUMMARY.md`, and live code
   - every “done” claim must map to a working build or passing test

3. **Add full product-level regression coverage**
   - API integration tests for real route flows
   - frontend smoke/build verification
   - parity tests between Streamlit operator path and API / Next.js path where required

### P1 — High-value

4. **Decompose the orchestration hotspot**
   - split `pipeline/engine.py` into stage executors or equivalent modular units
   - reduce change-risk and improve reviewability

5. **Unify the report / output path**
   - one canonical report assembly route
   - one canonical saved-run / artifact persistence route

6. **Close contract drift across backend ↔ API ↔ frontend**
   - tighten typed schemas
   - eliminate fallback dict-shape ambiguity

---

## 7. What Would Raise the Financial-Firm Benchmark Score Fastest

These items most directly improve “would a serious institutional engineering / platform team respect this as firm-grade?”

### F0 — Core benchmark uplifts

1. **Build on the new database-backed persistence base**
   - run history
   - artifact metadata
   - audit packet indexing
   - saved reports / retrieval metadata

2. **Harden API security and deployment defaults**
   - restrictive CORS by default
   - non-optional auth in non-dev environments
   - clearer environment separation for dev / staging / production

3. **Make CI reflect institutional release discipline**
   - required frontend build
   - required frontend typecheck / lint
   - required API contract tests
   - required migration / persistence checks once DB is introduced

4. **Improve operational observability**
   - central event / latency / failure telemetry
   - provider failure metrics
   - run-level SLA views
   - alerting hooks for broken upstream data vendors

### F1 — Benchmark credibility uplifts

5. **Formalise runtime reproducibility**
   - config hash + dataset/source fingerprint + prompt version + model version captured per run
   - make replay and audit materially stronger

6. **Eliminate presentation ahead of plumbing**
   - no UI surface should imply institutional depth that the data path cannot prove
   - de-scope or hide any not-yet-real analytics until the backend path is canonical

7. **Deepen production data controls**
   - quota handling
   - retry policies
   - vendor degradation modes
   - stronger freshness / staleness / source-trust policies

---

## 8. Expected Score Lift by Workstream

| Workstream | Purpose-fit uplift | Benchmark uplift | Why |
|---|---:|---:|---|
| Browser-level frontend regression coverage | +0.1 to +0.2 | +0.1 to +0.2 | Baseline smoke coverage is now in place; the next lift comes from deeper flow coverage |
| Doc/runtime convergence | +0.2 to +0.3 | +0.4 to +0.6 | Improves credibility and decision usefulness |
| DB persistence expansion | +0.1 to +0.2 | +0.3 to +0.5 | The registry is upgraded; adjacent persistence layers still need convergence |
| API security hardening | +0.1 | +0.4 to +0.6 | Important mainly for benchmark quality |
| Engine decomposition | +0.2 to +0.3 | +0.2 to +0.4 | Improves maintainability and review safety |
| Full product regression coverage | +0.3 to +0.5 | +0.3 to +0.5 | Makes quality claims provable |

---

## 9. Practical Near-Term Score Targets

| Milestone | Purpose-fit target | Benchmark target | What must be true |
|---|---:|---:|---|
| **Current state after browser smoke hardening** | 8.7 | 7.9 | Build green, browser smoke tests green, docs closer to truth, frontend enforced in CI, registry moved to SQLite, first engine extraction completed |
| **After persistence + security hardening** | 8.6 | 8.1 | Artifact/report metadata unified, stricter auth/CORS, stronger release discipline |
| **After engine decomposition + full parity testing** | 8.9 | 8.5 | Product integrity and maintainability materially improved |
| **After observability + reproducibility hardening** | 9.1 | 8.9 | Approaching real institutional platform quality |

---

## 10. The Real Next Goal

The platform does **not** need another giant idea-bundle first. It needs a **credibility pass**:

- keep the premium surface compile-clean and browser-smoke validated
- make docs match reality
- make CI police what the product claims
- make persistence and security worthy of institutional use
- reduce monolithic risk concentration

That is the shortest path to meaningfully higher scores on both axes.

---

## Conclusion

The project has already won the architecture-vision argument. The next upgrade is not “more imagination”; it is **convergence, hardening, and proof**. Once the repo becomes fully truthful about its live state and the premium surface is made production-clean, the scores can move up quickly.
