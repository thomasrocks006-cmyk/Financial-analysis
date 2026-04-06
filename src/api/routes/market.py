"""
src/api/routes/market.py
------------------------
Live market data endpoints for the Bloomberg-style terminal dashboard.

Endpoints:
  GET /api/v1/market/quotes       — live quotes for a comma-separated list of tickers
  GET /api/v1/market/indices      — major global market indices performance
  GET /api/v1/universes           — available universe presets with metadata
  GET /api/v1/universes/{name}    — tickers for a specific universe preset
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query

from research_pipeline.config.universe_config import (
    get_universe,
    list_universe_details,
    list_universes,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["market"])

# ── Timeout / rate-limit guard ─────────────────────────────────────────────────
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)

# Tickers used for the "indices" board — ETF proxies where direct index tickers
# require premium FMP plans.  These are all tradeable and on the free tier.
_INDEX_BOARD: list[dict[str, str]] = [
    {"sym": "SPY",   "label": "S&P 500"},
    {"sym": "QQQ",   "label": "NASDAQ 100"},
    {"sym": "IWM",   "label": "Russell 2000"},
    {"sym": "DIA",   "label": "Dow Jones"},
    {"sym": "EFA",   "label": "Int'l Dev."},
    {"sym": "EEM",   "label": "Emerging Mkts"},
    {"sym": "^VIX",  "label": "VIX"},
    {"sym": "TLT",   "label": "20yr Treasury"},
    {"sym": "GLD",   "label": "Gold"},
    {"sym": "USO",   "label": "Crude Oil"},
    {"sym": "IBIT",  "label": "Bitcoin ETF"},
    {"sym": "DXY",   "label": "US Dollar"},
]


async def _fmp_batch_quote(tickers: list[str], api_key: str) -> list[dict[str, Any]]:
    """Fetch batch quotes from FMP /stable/quote endpoint.

    Returns a list of quote dicts.  Silently returns [] on error so the
    dashboard degrades gracefully rather than failing hard.
    """
    if not tickers or not api_key:
        return []
    symbols = ",".join(tickers[:50])  # FMP free tier: up to 50 symbols per call
    url = "https://financialmodelingprep.com/stable/quote"
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(
                url,
                params={"symbol": symbols, "apikey": api_key},
                timeout=_TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else []
    except Exception as exc:
        logger.warning("FMP batch quote failed for %s tickers: %s", len(tickers), exc)
        return []


def _format_quote(raw: dict[str, Any], label: str = "") -> dict[str, Any]:
    """Normalise a raw FMP quote into the shape the frontend expects."""
    price = raw.get("price") or raw.get("previousClose") or 0
    prev_close = raw.get("previousClose") or price
    change_pct = raw.get("changePercentage") or raw.get("changesPercentage") or 0
    if not change_pct and prev_close and price:
        change_pct = round((price - prev_close) / prev_close * 100, 2)

    return {
        "sym": raw.get("symbol", ""),
        "label": label or raw.get("name", raw.get("symbol", "")),
        "price": price,
        "change_pct": round(float(change_pct), 2),
        "change_pct_str": f"{'+' if float(change_pct) >= 0 else ''}{float(change_pct):.2f}%",
        "market_cap_bn": round((raw.get("marketCap") or 0) / 1e9, 1),
        "volume": raw.get("volume"),
        "day_high": raw.get("dayHigh"),
        "day_low": raw.get("dayLow"),
        "52w_high": raw.get("yearHigh"),
        "52w_low": raw.get("yearLow"),
        "exchange": raw.get("exchange", ""),
    }


# ── GET /market/quotes ────────────────────────────────────────────────────────


@router.get("/market/quotes", summary="Live quotes for a list of tickers")
async def get_market_quotes(
    tickers: str = Query(
        ...,
        description="Comma-separated ticker symbols, e.g. 'AAPL,MSFT,SPY'. Max 50.",
    ),
) -> dict[str, Any]:
    """Return live price, change %, and key stats for up to 50 tickers.

    Uses FMP's /stable/quote endpoint (free tier).  Falls back to an empty list
    if FMP_API_KEY is not configured or the request fails.
    """
    api_key = os.getenv("FMP_API_KEY", "")
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()][:50]
    if not ticker_list:
        raise HTTPException(status_code=400, detail="No valid tickers provided.")

    raw_quotes = await _fmp_batch_quote(ticker_list, api_key)
    quote_map = {q.get("symbol", ""): q for q in raw_quotes}

    results = []
    for sym in ticker_list:
        raw = quote_map.get(sym)
        if raw:
            results.append(_format_quote(raw))
        else:
            results.append(
                {
                    "sym": sym,
                    "label": sym,
                    "price": None,
                    "change_pct": None,
                    "change_pct_str": "—",
                    "error": "unavailable",
                }
            )

    return {
        "quotes": results,
        "count": len(results),
        "source": "fmp" if api_key else "unavailable",
    }


# ── GET /market/indices ───────────────────────────────────────────────────────


@router.get("/market/indices", summary="Major global market indices performance")
async def get_market_indices() -> dict[str, Any]:
    """Return live performance for the standard index board.

    Uses ETF proxies (SPY for S&P 500, QQQ for NDX, etc.) which are available
    on the FMP free tier.  The ``label`` field contains the friendly index name.
    """
    api_key = os.getenv("FMP_API_KEY", "")
    label_map = {item["sym"]: item["label"] for item in _INDEX_BOARD}
    syms = [item["sym"] for item in _INDEX_BOARD]

    # Exclude VIX / DXY from FMP batch (they may need special handling)
    fmp_syms = [s for s in syms if not s.startswith("^") and s != "DXY"]
    raw_quotes = await _fmp_batch_quote(fmp_syms, api_key)
    quote_map = {q.get("symbol", ""): q for q in raw_quotes}

    results = []
    for item in _INDEX_BOARD:
        sym = item["sym"]
        label = item["label"]
        raw = quote_map.get(sym)
        if raw:
            results.append(_format_quote(raw, label=label))
        else:
            results.append(
                {
                    "sym": sym,
                    "label": label,
                    "price": None,
                    "change_pct": None,
                    "change_pct_str": "—",
                    "error": "unavailable",
                }
            )

    return {
        "indices": results,
        "count": len(results),
        "source": "fmp" if api_key else "unavailable",
    }


# ── GET /universes ────────────────────────────────────────────────────────────


@router.get("/universes", summary="List all available universe presets")
async def list_universe_presets() -> dict[str, Any]:
    """Return metadata and ticker counts for every registered universe preset.

    The ``broad_market`` preset is the recommended default for discovery runs.
    """
    details = list_universe_details()
    return {"universes": details, "count": len(details), "default": "broad_market"}


# ── GET /universes/{name} ─────────────────────────────────────────────────────


@router.get("/universes/{name}", summary="Tickers for a named universe preset")
async def get_universe_preset(name: str) -> dict[str, Any]:
    """Return the ticker list for a named universe preset.

    Raises 404 if the name is not registered.
    """
    try:
        tickers = get_universe(name)
    except KeyError:
        raise HTTPException(
            status_code=404,
            detail=f"Universe '{name}' not found. Available: {list_universes()}",
        )
    return {"name": name, "tickers": tickers, "count": len(tickers)}
