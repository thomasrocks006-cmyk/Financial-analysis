# AI Infrastructure Research & Portfolio Platform

> **Version 8** — A 15-stage, gate-controlled investment research pipeline combining deterministic computation with LLM-powered expert reasoning.

---

## Overview

This platform automates the production of institutional-quality equity research focused on the **AI infrastructure investment theme** — encompassing compute/silicon, power/energy, and infrastructure/materials.

### Architecture

The system operates across three layers:

| Layer | Purpose | Components |
|-------|---------|------------|
| **Deterministic Services** | Repeatable computation — no LLM | 10 services (market data, reconciliation, DCF, risk, scenarios, etc.) |
| **Expert Reasoning Agents** | Judgment-intensive analysis via LLM | 11 agents (orchestrator, analysts, red team, reviewer, portfolio manager) |
| **Governance & Control** | Quality gates, audit trail, self-monitoring | Pipeline gates, run registry, golden tests, self-audit |

### Pipeline Stages

| Stage | Name | Type |
|-------|------|------|
| 0 | Configuration & Bootstrap | Control |
| 1 | Universe Definition | Control |
| 2 | Data Ingestion (FMP + Finnhub) | Deterministic |
| 3 | Consensus Reconciliation | Deterministic |
| 4 | Data QA & Lineage | Deterministic |
| 5 | Evidence & Claim Registration | LLM Agent |
| 6 | Sector Analysis (3 parallel analysts) | LLM Agent |
| 7 | Valuation & Modelling | LLM + Deterministic |
| 8 | Macro & Political Overlay | LLM Agent |
| 9 | Quantitative Risk & Scenarios | Deterministic |
| 10 | Red Team Analysis | LLM Agent |
| 11 | Associate Review & Publish Gate | LLM Agent |
| 12 | Portfolio Construction | LLM Agent |
| 13 | Report Assembly | Deterministic |
| 14 | Monitoring & Logging | Mixed |

Every stage must pass its quality gate before the next stage begins.

---

## Research Universe

| Subtheme | Tickers |
|----------|---------|
| Compute & Silicon | NVDA, AVGO, TSM |
| Power & Energy | CEG, VST, GEV, NLR |
| Infrastructure | PWR, ETN, HUBB, APH, FIX |
| Materials | FCX, BHP |
| Data Centres | NXT |

---

## Project Structure

```
src/
├── research_pipeline/
│   ├── config/          # Settings, YAML loader
│   ├── schemas/         # Pydantic models (claims, market data, portfolio, registry, reports)
│   ├── services/        # 10 deterministic services
│   ├── agents/          # 11 LLM agent modules
│   └── pipeline/        # Engine, gates, stage orchestration
├── cli/                 # Typer CLI entry point
configs/                 # YAML configuration (pipeline, thresholds, universe)
prompts/                 # Agent system prompts (Markdown)
tests/                   # pytest test suite
```

---

## Installation

```bash
# Clone and install
cd Financial-analysis
pip install -e .

# Or install dependencies directly
pip install -r requirements.txt
```

### Environment Variables

```bash
export FMP_API_KEY="your-fmp-api-key"
export FINNHUB_API_KEY="your-finnhub-api-key"
export OPENAI_API_KEY="your-openai-api-key"
```

---

## Usage

### CLI Commands

```bash
# Run the full 15-stage pipeline
research-pipeline run

# Run with custom tickers
research-pipeline run --tickers NVDA,AVGO,TSM,CEG

# Validate configuration without running
research-pipeline run --dry-run

# Validate config files
research-pipeline validate

# Run golden regression tests
research-pipeline test

# View pipeline run history
research-pipeline history --limit 5

# Show default universe
research-pipeline universe
```

### Programmatic Usage

```python
import asyncio
from research_pipeline.config.settings import Settings
from research_pipeline.config.loader import load_pipeline_config
from research_pipeline.pipeline.engine import PipelineEngine

settings = Settings()
config = load_pipeline_config("configs/pipeline.yaml")
engine = PipelineEngine(settings, config)

result = asyncio.run(engine.run_full_pipeline(["NVDA", "AVGO", "TSM"]))
print(result["status"])
```

---

## Key Design Principles

1. **Deterministic work in code, judgment in LLM agents** — DCF calculations, reconciliation, and risk math are pure code. Thesis construction, valuation interpretation, and editorial decisions use GPT-4o.

2. **Every claim is traceable** — The Evidence Librarian registers every factual assertion with source, tier, confidence, and provenance. Nothing enters the final report unnamed.

3. **Publication is gated** — The Associate Reviewer enforces hard-fail rules. No report publishes with untraced data, missing methodology tags, or unaddressed red flags.

4. **Adversarial by design** — The Red Team Analyst must attack every thesis with 7 mandatory falsification tests before publication.

5. **Epistemic honesty** — Every report carries an institutional ceiling disclosure acknowledging the limitations of automated research.

---

## Configuration

### Pipeline Config (`configs/pipeline.yaml`)
Complete pipeline definition: stages, services, agents, thresholds, portfolio constraints.

### Thresholds (`configs/thresholds.yaml`)
Reconciliation tolerances, publication gate rules, red team thresholds, portfolio constraints.

### Universe (`configs/universe.yaml`)
Full coverage universe with subtheme classifications and analyst assignments.

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test module
pytest tests/test_schemas.py -v

# Run golden regression tests via CLI
research-pipeline test
```

### Golden Tests (Built-in)
| Test ID | Category | Description |
|---------|----------|-------------|
| GT-CLAIM-001 | Claim Classification | Tier-1 metric → confidence ≥ 0.85 |
| GT-CLAIM-002 | Claim Classification | Tier-4 source → requires caveat |
| GT-CLAIM-003 | Claim Classification | Derived claim → needs supporting refs |
| GT-GATE-001 | Gating | Failed claim → blocks publication |
| GT-GATE-002 | Gating | Red reconciliation → blocks without override |
| GT-RECON-001 | Reconciliation | >2% price divergence → red flag |

---

## Output

Each pipeline run produces:
- **Research Report** (Markdown) — executive summary, stock cards, portfolio variants, appendices
- **Run Record** (JSON) — full audit trail with agent versions, prompt hashes, timestamps
- **Claim Ledger** (JSON) — every factual claim with provenance
- **Self-Audit** — institutional ceiling statement, override log, version tracking

Reports are saved to `reports/` with the run ID as filename prefix.

---

## Data Sources

| Provider | Role | Required |
|----------|------|----------|
| **FMP (Financial Modeling Prep)** | Market data, consensus, ratios, DCF inputs | Yes |
| **Finnhub** | Cross-check, recommendations, earnings calendar | Yes |
| **Estimize** | Alternative consensus | Optional |

---

## License

Private — internal research use only.
