"""Live market data fetcher using Yahoo Finance (yfinance).

Replaces the static mock_data snapshots with real-time prices and
quantitative fundamentals.  Qualitative context (catalysts, risks,
sub-theme, company description) is still sourced from the enrichment
library in mock_data.py — in a production deployment these would come
from an earnings-transcript / news-NLP pipeline.

Fall-back strategy:
  - Any ticker for which yfinance returns no data silently falls back
    to the static snap so the pipeline always has something to work with.
  - A "_live" flag on each stock record lets downstream stages (and the
    LLM prompts) distinguish live vs static data.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Any

logger = logging.getLogger(__name__)

# ── yfinance field map ────────────────────────────────────────────────────
# Maps Yahoo Finance info-dict keys → our internal field names.
_YF_FIELDS: dict[str, str] = {
    "currentPrice":            "price",
    "marketCap":               "market_cap_raw",
    "forwardPE":               "forward_pe",
    "trailingPE":              "trailing_pe",
    "targetMeanPrice":         "consensus_target_12m",
    "numberOfAnalystOpinions": "analyst_count",
    "totalRevenue":            "revenue_ttm_raw",
    "freeCashflow":            "free_cash_flow_raw",
    "debtToEquity":            "debt_to_equity",
    "grossMargins":            "gross_margin_raw",
    "revenueGrowth":           "revenue_growth_yoy",
    "fiftyTwoWeekHigh":        "week52_high",
    "fiftyTwoWeekLow":         "week52_low",
    "recommendationMean":      "recommendation_mean",
    "recommendationKey":       "recommendation_key",
    "shortName":               "company_name_live",
    "sector":                  "sector_yf",
    "industry":                "industry_yf",
}

_REC_LABELS = {
    (1.0, 1.5): "Strong Buy",
    (1.5, 2.5): "Buy",
    (2.5, 3.5): "Hold",
    (3.5, 4.5): "Underperform",
    (4.5, 5.1): "Sell",
}


def _rec_label(mean: float | None) -> str:
    if mean is None:
        return "n/a"
    for (lo, hi), label in _REC_LABELS.items():
        if lo <= mean < hi:
            return label
    return "n/a"


def _fetch_one(ticker: str) -> dict[str, Any]:
    """Fetch live data for a single ticker via yfinance.

    Returns a dict of our internal fields, or an empty dict on failure.
    """
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        if not info or "regularMarketPrice" not in info and "currentPrice" not in info:
            logger.warning("yfinance returned empty info for %s", ticker)
            return {}
    except Exception as exc:
        logger.warning("yfinance fetch failed for %s: %s", ticker, exc)
        return {}

    raw: dict[str, Any] = {}
    for yf_key, our_key in _YF_FIELDS.items():
        val = info.get(yf_key)
        if val is not None:
            raw[our_key] = val

    # Scale to analyst-friendly units
    price = raw.get("price")
    result: dict[str, Any] = {
        "_live": True,
        "data_freshness": f"Live — Yahoo Finance ({date.today().isoformat()})",
        "data_tier":      "Tier 1 live — Yahoo Finance real-time",
    }

    if price:
        result["price"] = round(float(price), 2)

    if "market_cap_raw" in raw:
        result["market_cap_bn"] = round(raw["market_cap_raw"] / 1e9, 1)

    if "revenue_ttm_raw" in raw:
        result["revenue_ttm_bn"] = round(raw["revenue_ttm_raw"] / 1e9, 1)

    if "free_cash_flow_raw" in raw:
        result["free_cash_flow_ttm_bn"] = round(raw["free_cash_flow_raw"] / 1e9, 1)

    if "gross_margin_raw" in raw:
        result["gross_margin_pct"] = round(raw["gross_margin_raw"] * 100, 1)

    if "revenue_growth_yoy" in raw:
        result["revenue_growth_yoy_pct"] = round(raw["revenue_growth_yoy"] * 100, 1)

    # Pass-through fields (already in good units)
    for key in ("forward_pe", "trailing_pe", "consensus_target_12m",
                "debt_to_equity", "week52_high", "week52_low",
                "analyst_count", "company_name_live",
                "sector_yf", "industry_yf"):
        if key in raw:
            result[key] = round(raw[key], 2) if isinstance(raw[key], float) else raw[key]

    # Analyst consensus label
    result["analyst_consensus"] = _rec_label(raw.get("recommendation_mean"))
    if "recommendation_mean" in raw:
        result["recommendation_mean"] = round(raw["recommendation_mean"], 2)

    # Upside if we have both live price and consensus target
    tgt = result.get("consensus_target_12m")
    if price and tgt:
        result["upside_to_consensus_pct"] = round((tgt - price) / price * 100, 1)

    return result


def fetch_live_snapshots(
    tickers: list[str],
    max_workers: int = 6,
) -> dict[str, dict]:
    """Fetch live data for every ticker in parallel.

    Returns ``{ticker: live_fields_dict}`` — empty dict for any failure.
    """
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_fetch_one, t): t for t in tickers}
        for fut in as_completed(futures):
            ticker = futures[fut]
            try:
                results[ticker] = fut.result()
            except Exception as exc:
                logger.warning("Unexpected error fetching %s: %s", ticker, exc)
                results[ticker] = {}
    return results


def merge_snapshot(
    ticker: str,
    live_fields: dict[str, Any],
    static_context: dict[str, Any],
) -> dict[str, Any]:
    """Merge live quantitative data onto a static enrichment snapshot.

    Live fields *win* for every numerical/quantitative key.
    Static context supplies: recent_catalysts, key_risks, subtheme,
    company description, and analyst commentary.
    """
    merged = dict(static_context)

    for key, val in live_fields.items():
        if val is not None:
            merged[key] = val

    # Recompute upside if we refreshed the price
    price  = merged.get("price")
    target = merged.get("consensus_target_12m")
    if price and target:
        merged["upside_to_consensus_pct"] = round((tgt := target - price) / price * 100, 1)

    return merged


def get_live_sector_snapshot(tickers: list[str]) -> dict:
    """Build a market-data package backed by live Yahoo Finance prices.

    Falls back to the static enrichment library for any ticker that
    cannot be fetched.  Always returns a fully structured package so
    the pipeline never sees a missing key.
    """
    from frontend.mock_data import MARKET_SNAPSHOTS

    logger.info("Fetching live market data for tickers: %s", tickers)
    live_data = fetch_live_snapshots(tickers)

    stocks: dict[str, dict] = {}
    live_count = 0

    for ticker in tickers:
        static = MARKET_SNAPSHOTS.get(ticker, {
            "ticker":           ticker,
            "company_name":     ticker,
            "subtheme":         "compute",
            "recent_catalysts": [],
            "key_risks":        [],
            "data_freshness":   "no static context",
            "data_tier":        "Tier 3 — no static enrichment",
        })

        live = live_data.get(ticker, {})

        if live.get("_live"):
            live_count += 1
            merged = merge_snapshot(ticker, live, static)
            # Ensure ticker field is always set
            merged["ticker"] = ticker
            stocks[ticker] = merged
        else:
            logger.warning("No live data for %s — using static snapshot", ticker)
            fallback = dict(static)
            fallback["ticker"] = ticker
            fallback["_live"] = False
            stocks[ticker] = fallback

    live_tickers   = [t for t in tickers if stocks[t].get("_live")]
    static_tickers = [t for t in tickers if not stocks[t].get("_live")]

    source_note = "Live market data (Yahoo Finance)"
    if static_tickers:
        source_note += f"; static fallback for: {', '.join(static_tickers)}"

    return {
        "date":        date.today().isoformat(),
        "data_source": source_note,
        "live_count":  live_count,
        "stocks":      stocks,
    }
