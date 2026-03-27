"""Cost estimation for pipeline runs.

Provides pre-run estimates and post-run actuals based on token usage.
All prices are per 1M tokens (input / output).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ── Model pricing table (USD per 1M tokens: input, output) ───────────────
MODEL_PRICES: dict[str, tuple[float, float]] = {
    # Anthropic
    "claude-opus-4-6":         (15.00, 75.00),
    "claude-sonnet-4-6":       (3.00,  15.00),
    "claude-haiku-4-5":        (0.80,   4.00),
    # OpenAI
    "gpt-5.4":                 (2.50,  10.00),
    "gpt-5.4-mini":            (0.40,   1.60),
    "gpt-5.4-nano":            (0.15,   0.60),
    "gpt-4o":                  (2.50,  10.00),
    "gpt-4o-mini":             (0.15,   0.60),
    # Google
    "gemini-3.1-pro-preview":  (2.00,   8.00),
    "gemini-2.5-pro":          (1.25,  10.00),
    "gemini-2.5-flash":        (0.30,   2.50),
    "gemini-2.5-flash-lite":   (0.10,   0.40),
}

# ── Per-stage estimated token usage (mean tokens, 3-stock run) ──────────
#   (input_tokens, output_tokens)  — scale linearly with ticker count
STAGE_TOKEN_ESTIMATES: dict[int, tuple[int, int]] = {
    5:  (4_000,  3_000),   # Evidence librarian
    6:  (5_000,  7_000),   # Sector analysis (largest)
    7:  (4_500,  5_500),   # Valuation
    8:  (2_500,  3_500),   # Macro & political
    9:  (3_500,  4_000),   # Risk & scenarios
    10: (5_000,  6_000),   # Red team
    11: (4_500,  3_000),   # Associate review
    12: (5_500,  4_500),   # Portfolio construction
}

# LLM stages (non-LLM stages cost nothing)
LLM_STAGE_NUMS = set(STAGE_TOKEN_ESTIMATES.keys())


@dataclass
class StageCostEstimate:
    stage_num: int
    stage_name: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float


@dataclass
class RunCostEstimate:
    total_cost_usd: float
    low_usd: float       # 0.7× (shorter outputs on quick runs)
    high_usd: float      # 1.5× (verbose responses, full universe)
    stages: list[StageCostEstimate] = field(default_factory=list)
    ticker_count: int = 0
    model_breakdown: dict[str, float] = field(default_factory=dict)


@dataclass
class RunCostActual:
    """Actual cost calculated from recorded token counts post-run."""
    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    stage_costs: list[dict] = field(default_factory=list)


def _price_for(model: str) -> tuple[float, float]:
    """Return (input_price, output_price) per 1M tokens. Falls back to Sonnet."""
    for key, prices in MODEL_PRICES.items():
        if model.lower().startswith(key.lower()):
            return prices
    # Default fallback
    return MODEL_PRICES["claude-sonnet-4-6"]


def estimate_run_cost(
    tickers: list[str],
    stage_models: dict[int, str],
    default_model: str = "claude-sonnet-4-6",
) -> RunCostEstimate:
    """
    Estimate the cost of a pipeline run before execution.

    Token counts scale with ticker_count / 3 (base estimate is 3 tickers).
    """
    n = len(tickers)
    scale = max(n / 3.0, 0.5)  # minimum 0.5× even for 1 ticker (overhead)

    stage_estimates: list[StageCostEstimate] = []
    model_totals: dict[str, float] = {}
    total = 0.0

    stage_names = {
        5:  "Evidence Librarian",
        6:  "Sector Analysis",
        7:  "Valuation",
        8:  "Macro & Political",
        9:  "Quant Risk",
        10: "Red Team",
        11: "Associate Review",
        12: "Portfolio Construction",
    }

    for stage_num, (base_in, base_out) in STAGE_TOKEN_ESTIMATES.items():
        model = stage_models.get(stage_num, default_model)
        in_price, out_price = _price_for(model)

        in_tok  = int(base_in  * scale)
        out_tok = int(base_out * scale)

        cost = (in_tok * in_price + out_tok * out_price) / 1_000_000

        stage_estimates.append(StageCostEstimate(
            stage_num=stage_num,
            stage_name=stage_names.get(stage_num, f"Stage {stage_num}"),
            model=model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=cost,
        ))
        total += cost
        model_totals[model] = model_totals.get(model, 0.0) + cost

    return RunCostEstimate(
        total_cost_usd=total,
        low_usd=total * 0.7,
        high_usd=total * 1.5,
        stages=stage_estimates,
        ticker_count=n,
        model_breakdown=model_totals,
    )


def calculate_actual_cost(token_log: list[dict]) -> RunCostActual:
    """
    Calculate actual cost from a list of stage token records.

    Each record: {"stage_num": int, "model": str,
                  "input_tokens": int, "output_tokens": int}
    """
    total_cost = 0.0
    total_in   = 0
    total_out  = 0
    stage_costs = []

    for entry in token_log:
        model   = entry.get("model", "claude-sonnet-4-6")
        in_tok  = entry.get("input_tokens", 0)
        out_tok = entry.get("output_tokens", 0)
        in_p, out_p = _price_for(model)
        cost = (in_tok * in_p + out_tok * out_p) / 1_000_000

        total_cost += cost
        total_in   += in_tok
        total_out  += out_tok
        stage_costs.append({**entry, "cost_usd": round(cost, 4)})

    return RunCostActual(
        total_cost_usd=total_cost,
        total_input_tokens=total_in,
        total_output_tokens=total_out,
        stage_costs=stage_costs,
    )


def format_cost(usd: float) -> str:
    """Human-friendly cost string."""
    if usd < 0.01:
        return f"< $0.01"
    elif usd < 1.0:
        return f"${usd:.3f}"
    else:
        return f"${usd:.2f}"
