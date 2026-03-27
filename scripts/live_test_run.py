"""Live test run: FMP + Finnhub data fetch, then one LLM stage on real data.

Usage:
    python scripts/live_test_run.py

Reads keys from .env (or environment). Runs against NVDA, CEG, PWR.
Costs ~$0.02-0.04 (one Sonnet 4.6 call on ~3k tokens).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import textwrap
import time
from pathlib import Path

# ── Load .env ──────────────────────────────────────────────────────────────
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

# ── Ensure src/ is on path ─────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import httpx
import anthropic


TICKERS = ["NVDA", "CEG", "PWR"]
FMP_KEY     = os.environ.get("FMP_API_KEY", "")
FINNHUB_KEY = os.environ.get("FINNHUB_API_KEY", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-6"


# ─────────────────────────────────────────────────────────────────────────────
# DATA FETCH
# ─────────────────────────────────────────────────────────────────────────────

async def fmp_get(client: httpx.AsyncClient, path: str, extra: dict = {}) -> dict | list:
    url = f"https://financialmodelingprep.com/stable{path}"
    r = await client.get(url, params={"apikey": FMP_KEY, **extra})
    r.raise_for_status()
    return r.json()


async def finnhub_get(client: httpx.AsyncClient, path: str, extra: dict = {}) -> dict | list:
    url = f"https://finnhub.io/api/v1{path}"
    r = await client.get(url, params={"token": FINNHUB_KEY, **extra})
    r.raise_for_status()
    return r.json()


async def fetch_all_data(ticker: str, client: httpx.AsyncClient) -> dict:
    print(f"  → Fetching {ticker} from FMP + Finnhub...")
    results = {}

    # FMP: quote  (stable endpoint uses symbol= param, returns list)
    try:
        data = await fmp_get(client, f"/quote", {"symbol": ticker})
        q = data[0] if isinstance(data, list) and data else (data or {})
        if not q or "Error Message" in str(q):
            raise ValueError(f"FMP returned no data: {q}")
        results["fmp_quote"] = {
            "price":          q.get("price"),
            "market_cap_bn":  round((q.get("marketCap") or 0) / 1e9, 1),
            "pe":             q.get("pe"),
            "forward_pe":     q.get("forwardPE"),
            "52w_high":       q.get("yearHigh"),
            "52w_low":        q.get("yearLow"),
            "avg_volume":     q.get("volume"),
            "change_pct":     q.get("changePercentage"),
            "name":           q.get("name"),
            "day_high":       q.get("dayHigh"),
            "day_low":        q.get("dayLow"),
            "prev_close":     q.get("previousClose"),
        }
        print(f"    ✓ FMP quote: ${q.get('price')}")
    except Exception as e:
        results["fmp_quote"] = {"error": str(e)}
        code = "402" if "402" in str(e) else "ERR"
        print(f"    ✗ FMP quote [{code}] — free tier limit for {ticker}")

    # FMP: price target consensus
    try:
        data = await fmp_get(client, f"/price-target-consensus", {"symbol": ticker})
        r = data[0] if isinstance(data, list) and data else (data or {})
        if not r or "Error Message" in str(r):
            raise ValueError(str(r))
        results["fmp_price_targets"] = {
            "target_low":    r.get("targetLow"),
            "target_median": r.get("targetMedian"),
            "target_high":   r.get("targetHigh"),
            "target_mean":   r.get("targetConsensus"),
        }
        print(f"    ✓ FMP price targets: median ${r.get('targetMedian')}")
    except Exception as e:
        results["fmp_price_targets"] = {"error": str(e)}
        code = "402" if "402" in str(e) else "ERR"
        print(f"    ✗ FMP targets [{code}] — free tier limit for {ticker}")

    # FMP: analyst estimates (forward revenue/EPS) — premium endpoint, may 400/402
    try:
        data = await fmp_get(client, f"/analyst-estimates", {"symbol": ticker, "limit": 4})
        if not data or isinstance(data, dict):
            raise ValueError(str(data))
        results["fmp_estimates"] = [
            {
                "period":          d.get("date"),
                "rev_est_avg_bn":  round((d.get("estimatedRevenueAvg") or 0) / 1e9, 2),
                "eps_est_avg":     d.get("estimatedEpsAvg"),
                "num_analysts":    d.get("numberAnalystEstimatedRevenue"),
            }
            for d in (data or [])[:4]
        ]
        print(f"    ✓ FMP estimates: {len(results['fmp_estimates'])} periods")
    except Exception as e:
        results["fmp_estimates"] = []
        code = "402" if "402" in str(e) else "400" if "400" in str(e) else "ERR"
        print(f"    ✗ FMP estimates [{code}] — premium endpoint")

    # FMP: key metrics (EV/EBITDA, FCF yield, etc.)
    try:
        data = await fmp_get(client, f"/key-metrics", {"symbol": ticker, "limit": 1})
        km = data[0] if isinstance(data, list) and data else {}
        if not km or "Error Message" in str(km):
            raise ValueError(str(km))
        results["fmp_key_metrics"] = {
            "ev_to_ebitda":       km.get("evToEbitda") or km.get("enterpriseValueOverEBITDA"),
            "fcf_yield":          km.get("freeCashFlowYield"),
            "revenue_per_share":  km.get("revenuePerShare"),
            "net_income_margin":  km.get("netIncomePerShare"),
            "debt_to_equity":     km.get("debtToEquity"),
            "roe":                km.get("roe"),
            "roic":               km.get("roic"),
        }
        print(f"    ✓ FMP key metrics: EV/EBITDA={results['fmp_key_metrics']['ev_to_ebitda']}")
    except Exception as e:
        results["fmp_key_metrics"] = {}
        code = "402" if "402" in str(e) else "ERR"
        print(f"    ✗ FMP key metrics [{code}] — free tier limit for {ticker}")

    # Finnhub: analyst recommendations
    try:
        data = await finnhub_get(client, "/stock/recommendation", {"symbol": ticker})
        row = data[0] if data else {}
        total = sum([
            row.get("strongBuy", 0), row.get("buy", 0),
            row.get("hold", 0), row.get("sell", 0), row.get("strongSell", 0)
        ]) or 1
        results["finnhub_recommendations"] = {
            "period":      row.get("period"),
            "strong_buy":  row.get("strongBuy"),
            "buy":         row.get("buy"),
            "hold":        row.get("hold"),
            "sell":        row.get("sell"),
            "strong_sell": row.get("strongSell"),
            "buy_pct":     round((row.get("strongBuy", 0) + row.get("buy", 0)) / total * 100, 1),
            "hold_pct":    round(row.get("hold", 0) / total * 100, 1),
            "sell_pct":    round((row.get("sell", 0) + row.get("strongSell", 0)) / total * 100, 1),
        }
        print(f"    ✓ Finnhub recs: {results['finnhub_recommendations']['buy_pct']}% buy")
    except Exception as e:
        results["finnhub_recommendations"] = {"error": str(e)}
        print(f"    ✗ Finnhub recs failed: {e}")

    # Finnhub: basic financials (revenue in millions in Finnhub, not billions)
    try:
        data = await finnhub_get(client, "/stock/metric", {"symbol": ticker, "metric": "all"})
        m = (data or {}).get("metric", {})
        # Finnhub reports revenue in millions (revenuePerShareTTM * shares)
        # Use revenuePerShareTTM * sharesOutstanding approximation, or just report per-share
        rev_ps = m.get("revenuePerShareTTM") or 0
        results["finnhub_metrics"] = {
            "52w_high":              m.get("52WeekHigh"),
            "52w_low":               m.get("52WeekLow"),
            "52w_high_date":         m.get("52WeekHighDate"),
            "52w_low_date":          m.get("52WeekLowDate"),
            "beta":                  m.get("beta"),
            "pe_ttm":                m.get("peTTM"),
            "pe_annual":             m.get("peAnnual"),
            "pb_annual":             m.get("pbAnnual"),
            "ps_ttm":                m.get("psTTM"),
            "revenue_per_share_ttm": rev_ps,
            "gross_margin_ttm":      m.get("grossMarginTTM"),
            "net_margin_ttm":        m.get("netProfitMarginTTM"),
            "eps_ttm":               m.get("epsTTM"),
            "eps_growth_ttm":        m.get("epsGrowthTTMYoy"),
            "roa_ttm":               m.get("roaTTM"),
            "roe_ttm":               m.get("roeTTM"),
            "current_ratio":         m.get("currentRatioAnnual"),
            "debt_equity_annual":    m.get("totalDebt/totalEquityAnnual"),
            "div_yield_ttm":         m.get("dividendYieldIndicatedAnnual"),
            "10d_avg_vol":           m.get("10DayAverageTradingVolume"),
        }
        print(f"    ✓ Finnhub metrics: beta={m.get('beta')}, PE(ttm)={m.get('peTTM')}, EPS={m.get('epsTTM')}")
    except Exception as e:
        results["finnhub_metrics"] = {}
        print(f"    ✗ Finnhub metrics failed: {e}")

    return results


# ─────────────────────────────────────────────────────────────────────────────
# LLM STAGE — Evidence Librarian on real data
# ─────────────────────────────────────────────────────────────────────────────

async def run_evidence_stage(live_data: dict) -> tuple[str, int, int]:
    """Run Stage 5 Evidence Librarian on live FMP/Finnhub data. Returns (text, in_tokens, out_tokens)."""

    data_block = json.dumps(live_data, indent=2)

    system = textwrap.dedent("""
        You are the Evidence Librarian for an institutional AI infrastructure research platform.
        You have been provided with LIVE market data from FMP (Financial Modeling Prep) and
        Finnhub APIs — these are real, current data points as of today.

        For each company in the universe, produce a structured Evidence Library entry:

        ## [TICKER] — [Company Name]

        ### A. Live Data Confirmed [T1/T2]
        List every numerical fact from the live feed with its source tag:
        - [FMP-Q] = FMP Quote API (real-time price data)
        - [FMP-PT] = FMP Price Target Consensus
        - [FMP-EST] = FMP Analyst Estimates
        - [FMP-KM] = FMP Key Metrics (fundamental ratios)
        - [FHB-REC] = Finnhub Analyst Recommendations
        - [FHB-MET] = Finnhub Fundamental Metrics

        For each figure: state the value, note what it means in context, and flag any anomaly.

        ### B. FMP vs Finnhub Cross-Validation
        Compare any overlapping fields (PE ratio, 52w range, revenue, etc.).
        Flag divergences >5% as AMBER, >15% as RED with explanation.

        ### C. Evidence Gaps (what live data cannot tell us)
        What material questions remain unanswered by the API data?
        These are the inputs that would require earnings transcripts, SEC filings, or management calls.

        ### D. Data Quality Assessment
        - Freshness: how recent is this data?
        - Completeness score: out of 10
        - Key limitations for downstream analysis

        Be precise and cite specific numbers. This feeds directly into valuation and sector analysis.
    """).strip()

    user_content = f"""
Date: 2026-03-27 (live run)
Universe: {', '.join(TICKERS)}
Data source: Live FMP + Finnhub API pull (just fetched)

LIVE DATA PACKAGE:
{data_block}

Please produce the full Evidence Library for all three names.
Flag any anomalies, cross-source divergences, and evidence gaps clearly.
    """.strip()

    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    print(f"\n  → Calling {MODEL} for Stage 5 Evidence Librarian...")
    t0 = time.time()

    response = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        temperature=0.2,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )

    elapsed = time.time() - t0
    text = response.content[0].text
    in_tok = response.usage.input_tokens
    out_tok = response.usage.output_tokens

    # Cost calculation (Sonnet 4.6: $3/MTok input, $15/MTok output)
    cost_usd = (in_tok / 1_000_000 * 3.0) + (out_tok / 1_000_000 * 15.0)

    print(f"  ✓ Stage 5 complete in {elapsed:.1f}s")
    print(f"  ✓ Tokens: {in_tok:,} in / {out_tok:,} out → ${cost_usd:.4f}")
    print(f"  ✓ Output length: {len(text)} chars / ~{len(text)//4} words")

    return text, in_tok, out_tok, cost_usd, elapsed


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    print("\n" + "="*70)
    print("  AI INFRASTRUCTURE PIPELINE — LIVE TEST RUN")
    print(f"  Universe: {', '.join(TICKERS)}  |  {MODEL}")
    print("="*70)

    # Validate keys
    missing = []
    if not FMP_KEY:     missing.append("FMP_API_KEY")
    if not FINNHUB_KEY: missing.append("FINNHUB_API_KEY")
    if not ANTHROPIC_KEY: missing.append("ANTHROPIC_API_KEY")
    if missing:
        print(f"\n❌ Missing keys: {', '.join(missing)}")
        print("   Make sure .env is populated and run from the workspace root.")
        return

    print(f"\n✓ FMP key:      {FMP_KEY[:8]}...")
    print(f"✓ Finnhub key:  {FINNHUB_KEY[:8]}...")
    print(f"✓ Anthropic:    {ANTHROPIC_KEY[:12]}...")

    # ── Stage 2: Fetch live data ──────────────────────────────────────────
    print("\n[STAGE 2/3] DATA INGESTION — FMP + Finnhub")
    print("-"*50)

    t_data_start = time.time()
    live_data: dict[str, dict] = {}

    async with httpx.AsyncClient(timeout=30) as client:
        for ticker in TICKERS:
            live_data[ticker] = await fetch_all_data(ticker, client)

    data_elapsed = time.time() - t_data_start
    print(f"\n✓ Data ingestion complete in {data_elapsed:.1f}s")

    # ── Show raw data table ───────────────────────────────────────────────
    print("\n" + "="*70)
    print("  RAW DATA SNAPSHOT")
    print("="*70)
    def _f(v, fmt="", prefix="", suffix="", decimals=2):
        """Format a value safely — returns 'N/A' if None/missing."""
        if v is None: return "N/A"
        try:
            if isinstance(v, float): v = round(v, decimals)
            return f"{prefix}{v:{fmt}}{suffix}"
        except Exception:
            return str(v)

    print(f"\n{'Ticker':<6} {'Price':>8} {'MktCap':>9} {'FwdPE':>7} "
          f"{'Target':>8} {'Buy%':>6} {'Beta':>6} {'PE(ttm)':>8} {'EPS':>7}")
    print("-"*70)
    for t in TICKERS:
        d = live_data[t]
        q   = d.get("fmp_quote", {})
        pt  = d.get("fmp_price_targets", {})
        rec = d.get("finnhub_recommendations", {})
        met = d.get("finnhub_metrics", {})
        print(
            f"{t:<6} "
            f"{_f(q.get('price'), prefix='$'):>8} "
            f"{_f(q.get('market_cap_bn'), suffix='B'):>9} "
            f"{_f(q.get('forward_pe')):>7} "
            f"{_f(pt.get('target_median'), prefix='$'):>8} "
            f"{_f(rec.get('buy_pct'), suffix='%'):>6} "
            f"{_f(met.get('beta')):>6} "
            f"{_f(met.get('pe_ttm')):>8} "
            f"{_f(met.get('eps_ttm')):>7}"
        )

    # ── FMP vs Finnhub cross-check ────────────────────────────────────────
    print("\n[RECONCILIATION] FMP vs Finnhub cross-validation:")
    for t in TICKERS:
        d = live_data[t]
        fmp_price    = d.get("fmp_quote", {}).get("price")
        fmp_52h      = d.get("fmp_quote", {}).get("52w_high")
        fhb_52h      = d.get("finnhub_metrics", {}).get("52w_high")
        fhb_pe_ttm   = d.get("finnhub_metrics", {}).get("pe_ttm")
        fhb_beta     = d.get("finnhub_metrics", {}).get("beta")
        fhb_eps      = d.get("finnhub_metrics", {}).get("eps_ttm")
        fmp_target   = d.get("fmp_price_targets", {}).get("target_median")
        fhb_buy      = d.get("finnhub_recommendations", {}).get("buy_pct")
        # Cross-validate 52w high if both sources have it
        if fmp_52h and fhb_52h:
            drift = abs(fmp_52h - fhb_52h) / max(fmp_52h, fhb_52h) * 100
            flag = "✓" if drift < 2 else "⚠️ AMBER" if drift < 10 else "🔴 RED"
            print(f"  {t}: 52wH FMP=${fmp_52h} vs FHB=${fhb_52h} ({drift:.1f}% drift) {flag}")
        else:
            print(f"  {t}: FMP price=${fmp_price} | 52wH={fhb_52h} | PE(ttm)={fhb_pe_ttm} "
                  f"| beta={fhb_beta} | EPS={fhb_eps} | target={fmp_target} | buy%={fhb_buy}")

    # ── Stage 5: LLM — Evidence Librarian ────────────────────────────────
    print("\n[STAGE 5] LLM — EVIDENCE LIBRARIAN (claude-sonnet-4-6)")
    print("-"*50)

    llm_output, in_tok, out_tok, cost, elapsed = await run_evidence_stage(live_data)

    # ── Output to file ────────────────────────────────────────────────────
    out_dir = Path(__file__).parent.parent / "output"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "live_test_run_output.md"

    report = f"""# Live Test Run — AI Infrastructure Pipeline
**Date:** 2026-03-27
**Universe:** {', '.join(TICKERS)}
**Model:** {MODEL}
**Data source:** Live FMP + Finnhub APIs

---

## Raw Data Package (Stages 2-4)

```json
{json.dumps(live_data, indent=2)}
```

---

## Stage 5 — Evidence Librarian Output

{llm_output}

---

## Run Metadata

| Field | Value |
|-------|-------|
| Tickers | {', '.join(TICKERS)} |
| Data fetch time | {data_elapsed:.1f}s |
| LLM stage time | {elapsed:.1f}s |
| Input tokens | {in_tok:,} |
| Output tokens | {out_tok:,} |
| Stage 5 cost | ${cost:.4f} |
| Model | {MODEL} |

### Cost Extrapolation to Full Pipeline

| Stage | Model | Est. tokens (in/out) | Est. cost |
|-------|-------|----------------------|-----------|
| S5 Evidence | Sonnet 4.6 | {in_tok:,} / {out_tok:,} | ${cost:.4f} |
| S6 Sector | Opus 4.6 | ~8,000 / ~3,500 | ~$0.04–$0.09 |
| S7 Valuation | Sonnet 4.6 | ~6,000 / ~3,000 | ~$0.025–$0.06 |
| S8 Macro | Gemini 2.5 Pro | ~3,000 / ~2,000 | ~$0.008 |
| S9 Risk | Flash | ~5,000 / ~2,500 | ~$0.004 |
| S10 Red Team | Opus 4.6 | ~7,000 / ~3,500 | ~$0.04–$0.09 |
| S11 Review | Sonnet 4.6 | ~8,000 / ~2,000 | ~$0.03–$0.05 |
| S12 Portfolio | GPT-5.4 | ~6,000 / ~2,000 | ~$0.015–$0.03 |
| **TOTAL (3 stocks)** | | | **~$0.15–$0.35** |

*Note: Lower than earlier estimates because live data is compact JSON vs verbose mock text.*
"""
    out_file.write_text(report)
    print(f"\n✓ Full output written to: {out_file}")

    # ── Print LLM output to terminal ──────────────────────────────────────
    print("\n" + "="*70)
    print("  STAGE 5 OUTPUT — EVIDENCE LIBRARIAN (live data)")
    print("="*70)
    print(llm_output)
    print("\n" + "="*70)
    print(f"  COST SUMMARY")
    print("="*70)
    print(f"  Stage 5 alone:          ${cost:.4f}")
    print(f"  Extrapolated full run:  ~$0.15–$0.35 (3 stocks, optimal model mix)")
    print(f"  Full run (all Opus):    ~$0.80–$1.20 (3 stocks)")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
