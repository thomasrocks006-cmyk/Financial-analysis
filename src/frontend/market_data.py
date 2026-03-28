"""Institutional-grade market data provider.

Three-source architecture:
  1. FMP (Financial Modeling Prep) — primary: quotes, financials, key metrics,
     price targets, analyst estimates, income statements
  2. Finnhub — secondary: analyst recommendations, fundamental metrics,
     company news (qualitative), basic financials for cross-validation
  3. Yahoo Finance (yfinance) — tertiary fallback if both APIs fail

Cross-validation: Where FMP and Finnhub overlap (PE ratios, 52w range),
fields are reconciled and divergences flagged (AMBER >5%, RED >15%).

All fetches are async via httpx with per-ticker parallelism.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, timedelta
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# ── API Clients ──────────────────────────────────────────────────────────

_TIMEOUT = httpx.Timeout(15.0, connect=10.0)


async def _fmp_get(
    client: httpx.AsyncClient, path: str, api_key: str, extra: dict | None = None,
) -> dict | list:
    """Call FMP stable API endpoint."""
    url = f"https://financialmodelingprep.com/stable{path}"
    params = {"apikey": api_key, **(extra or {})}
    r = await client.get(url, params=params, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


async def _finnhub_get(
    client: httpx.AsyncClient, path: str, api_key: str, extra: dict | None = None,
) -> dict | list:
    """Call Finnhub API endpoint."""
    url = f"https://finnhub.io/api/v1{path}"
    params = {"token": api_key, **(extra or {})}
    r = await client.get(url, params=params, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


# ── Per-Ticker Fetch ─────────────────────────────────────────────────────

async def _fetch_fmp(ticker: str, client: httpx.AsyncClient, api_key: str) -> dict[str, Any]:
    """Fetch all FMP data for a single ticker."""
    result: dict[str, Any] = {}

    # Quote (real-time price, market cap)
    try:
        data = await _fmp_get(client, "/quote", api_key, {"symbol": ticker})
        q = data[0] if isinstance(data, list) and data else (data or {})
        if q and "Error" not in str(q):
            result["fmp_quote"] = {
                "price":         q.get("price"),
                "market_cap_bn": round((q.get("marketCap") or 0) / 1e9, 1),
                "pe":            q.get("pe"),
                "forward_pe":    q.get("forwardPE"),
                "eps":           q.get("eps"),
                "52w_high":      q.get("yearHigh"),
                "52w_low":       q.get("yearLow"),
                "volume":        q.get("volume"),
                "avg_volume":    q.get("avgVolume"),
                "change_pct":    q.get("changePercentage"),
                "company_name":  q.get("name"),
                "exchange":      q.get("exchange"),
                "day_high":      q.get("dayHigh"),
                "day_low":       q.get("dayLow"),
            }
    except Exception as e:
        logger.warning("FMP quote failed for %s: %s", ticker, e)

    # Profile (company description, sector, industry, CEO)
    try:
        data = await _fmp_get(client, "/profile", api_key, {"symbol": ticker})
        p = data[0] if isinstance(data, list) and data else {}
        if p and "Error" not in str(p):
            result["fmp_profile"] = {
                "company_name":  p.get("companyName"),
                "description":   p.get("description", "")[:800],
                "sector":        p.get("sector"),
                "industry":      p.get("industry"),
                "ceo":           p.get("ceo"),
                "country":       p.get("country"),
                "employees":     p.get("fullTimeEmployees"),
                "ipo_date":      p.get("ipoDate"),
                "beta":          p.get("beta"),
                "website":       p.get("website"),
            }
    except Exception as e:
        logger.warning("FMP profile failed for %s: %s", ticker, e)

    # Price target consensus
    try:
        data = await _fmp_get(client, "/price-target-consensus", api_key, {"symbol": ticker})
        r = data[0] if isinstance(data, list) and data else (data or {})
        if r and "Error" not in str(r):
            result["fmp_targets"] = {
                "target_low":    r.get("targetLow"),
                "target_median": r.get("targetMedian"),
                "target_high":   r.get("targetHigh"),
                "target_mean":   r.get("targetConsensus"),
            }
    except Exception as e:
        logger.debug("FMP targets failed for %s: %s", ticker, e)

    # Key metrics (EV/EBITDA, FCF yield, ROE, ROIC, etc.)
    try:
        data = await _fmp_get(client, "/key-metrics", api_key, {"symbol": ticker, "limit": "1"})
        km = data[0] if isinstance(data, list) and data else {}
        if km and "Error" not in str(km):
            result["fmp_key_metrics"] = {
                "ev_to_ebitda":         km.get("evToEbitda") or km.get("enterpriseValueOverEBITDA"),
                "ev_to_sales":          km.get("evToSales"),
                "ev_to_fcf":            km.get("evToFreeCashFlow"),
                "fcf_yield":            km.get("freeCashFlowYield"),
                "debt_to_equity":       km.get("debtToEquity") or km.get("netDebtToEBITDA"),
                "roe":                  km.get("returnOnEquity"),
                "roic":                 km.get("returnOnInvestedCapital"),
                "roa":                  km.get("returnOnAssets"),
                "current_ratio":        km.get("currentRatio"),
                "working_capital_bn":   round((km.get("workingCapital") or 0) / 1e9, 2),
                "income_quality":       km.get("incomeQuality"),
                "earnings_yield":       km.get("earningsYield"),
                "market_cap_bn":        round((km.get("marketCap") or 0) / 1e9, 1),
                "ev_bn":               round((km.get("enterpriseValue") or 0) / 1e9, 1),
                "fiscal_year":          km.get("fiscalYear"),
                "period":               km.get("period"),
            }
    except Exception as e:
        logger.debug("FMP key metrics failed for %s: %s", ticker, e)

    # Income statement (revenue, margins)
    try:
        data = await _fmp_get(client, "/income-statement", api_key, {"symbol": ticker, "limit": "1"})
        inc = data[0] if isinstance(data, list) and data else {}
        if inc and "Error" not in str(inc):
            rev = inc.get("revenue") or 0
            gp = inc.get("grossProfit") or 0
            oi = inc.get("operatingIncome") or 0
            ni = inc.get("netIncome") or 0
            result["fmp_income"] = {
                "fiscal_year":       inc.get("fiscalYear"),
                "period":            inc.get("period"),
                "revenue_bn":        round(rev / 1e9, 2),
                "gross_profit_bn":   round(gp / 1e9, 2),
                "operating_income_bn": round(oi / 1e9, 2),
                "net_income_bn":     round(ni / 1e9, 2),
                "ebitda_bn":         round((inc.get("ebitda") or 0) / 1e9, 2),
                "gross_margin_pct":  round(gp / rev * 100, 1) if rev else None,
                "operating_margin_pct": round(oi / rev * 100, 1) if rev else None,
                "net_margin_pct":    round(ni / rev * 100, 1) if rev else None,
                "eps":               inc.get("eps"),
                "eps_diluted":       inc.get("epsDiluted"),
                "r_and_d_bn":        round((inc.get("researchAndDevelopmentExpenses") or 0) / 1e9, 2),
            }
    except Exception as e:
        logger.debug("FMP income statement failed for %s: %s", ticker, e)

    # Cash flow statement
    try:
        data = await _fmp_get(client, "/cash-flow-statement", api_key, {"symbol": ticker, "limit": "1"})
        cf = data[0] if isinstance(data, list) and data else {}
        if cf and "Error" not in str(cf):
            result["fmp_cashflow"] = {
                "operating_cf_bn":  round((cf.get("operatingCashFlow") or 0) / 1e9, 2),
                "capex_bn":         round(abs(cf.get("capitalExpenditure") or 0) / 1e9, 2),
                "fcf_bn":           round((cf.get("freeCashFlow") or 0) / 1e9, 2),
                "dividends_bn":     round(abs(cf.get("dividendsPaid") or 0) / 1e9, 2),
                "buybacks_bn":      round(abs(cf.get("commonStockRepurchased") or 0) / 1e9, 2),
            }
    except Exception as e:
        logger.debug("FMP cash flow failed for %s: %s", ticker, e)

    return result


async def _fetch_finnhub(ticker: str, client: httpx.AsyncClient, api_key: str) -> dict[str, Any]:
    """Fetch all Finnhub data for a single ticker."""
    result: dict[str, Any] = {}

    # Quote
    try:
        data = await _finnhub_get(client, "/quote", api_key, {"symbol": ticker})
        if data and isinstance(data, dict) and data.get("c"):
            result["finnhub_quote"] = {
                "price":       data.get("c"),
                "change":      data.get("d"),
                "change_pct":  data.get("dp"),
                "day_high":    data.get("h"),
                "day_low":     data.get("l"),
                "open":        data.get("o"),
                "prev_close":  data.get("pc"),
            }
    except Exception as e:
        logger.warning("Finnhub quote failed for %s: %s", ticker, e)

    # Analyst recommendations
    try:
        data = await _finnhub_get(client, "/stock/recommendation", api_key, {"symbol": ticker})
        row = data[0] if data and isinstance(data, list) else {}
        if row:
            total = sum([
                row.get("strongBuy", 0), row.get("buy", 0),
                row.get("hold", 0), row.get("sell", 0), row.get("strongSell", 0),
            ]) or 1
            result["finnhub_recommendations"] = {
                "period":      row.get("period"),
                "strong_buy":  row.get("strongBuy"),
                "buy":         row.get("buy"),
                "hold":        row.get("hold"),
                "sell":        row.get("sell"),
                "strong_sell": row.get("strongSell"),
                "buy_pct":     round((row.get("strongBuy", 0) + row.get("buy", 0)) / total * 100, 1),
            }
    except Exception as e:
        logger.debug("Finnhub recommendations failed for %s: %s", ticker, e)

    # Basic financials (comprehensive metrics)
    try:
        data = await _finnhub_get(client, "/stock/metric", api_key, {"symbol": ticker, "metric": "all"})
        m = (data or {}).get("metric", {})
        if m:
            result["finnhub_metrics"] = {
                "52w_high":            m.get("52WeekHigh"),
                "52w_low":             m.get("52WeekLow"),
                "52w_high_date":       m.get("52WeekHighDate"),
                "52w_low_date":        m.get("52WeekLowDate"),
                "beta":                m.get("beta"),
                "pe_ttm":              m.get("peTTM"),
                "pe_annual":           m.get("peAnnual"),
                "pb_annual":           m.get("pbAnnual"),
                "ps_ttm":              m.get("psTTM"),
                "ev_ebitda_ttm":       m.get("currentEv/freeCashFlowTTM"),
                "gross_margin_ttm":    m.get("grossMarginTTM"),
                "net_margin_ttm":      m.get("netProfitMarginTTM"),
                "operating_margin_ttm": m.get("operatingMarginTTM"),
                "eps_ttm":             m.get("epsTTM"),
                "eps_growth_yoy":      m.get("epsGrowthTTMYoy"),
                "revenue_growth_3y":   m.get("revenueGrowth3Y"),
                "roa_ttm":             m.get("roaTTM"),
                "roe_ttm":             m.get("roeTTM"),
                "current_ratio":       m.get("currentRatioAnnual"),
                "debt_equity":         m.get("totalDebt/totalEquityAnnual"),
                "div_yield":           m.get("dividendYieldIndicatedAnnual"),
                "10d_avg_vol":         m.get("10DayAverageTradingVolume"),
                "3m_avg_vol":          m.get("3MonthAverageTradingVolume"),
                "market_cap_mn":       m.get("marketCapitalization"),
            }
    except Exception as e:
        logger.debug("Finnhub metrics failed for %s: %s", ticker, e)

    # Company news (last 7 days — qualitative data)
    try:
        today = date.today()
        week_ago = today - timedelta(days=7)
        data = await _finnhub_get(client, "/company-news", api_key, {
            "symbol": ticker,
            "from": week_ago.isoformat(),
            "to": today.isoformat(),
        })
        if data and isinstance(data, list):
            # Take top 8 most recent, deduplicate by headline
            seen: set[str] = set()
            news = []
            for item in data[:20]:
                headline = item.get("headline", "")
                if headline and headline not in seen:
                    seen.add(headline)
                    news.append({
                        "headline": headline,
                        "summary":  (item.get("summary") or "")[:200],
                        "source":   item.get("source"),
                        "datetime": item.get("datetime"),
                        "url":      item.get("url"),
                    })
                if len(news) >= 8:
                    break
            result["finnhub_news"] = news
    except Exception as e:
        logger.debug("Finnhub news failed for %s: %s", ticker, e)

    return result


async def _fetch_yfinance_fallback(ticker: str) -> dict[str, Any]:
    """Fallback to yfinance if both FMP and Finnhub fail or have gaps."""
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        if not info or ("currentPrice" not in info and "regularMarketPrice" not in info):
            return {}
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        return {
            "yf_quote": {
                "price":            price,
                "market_cap_bn":    round((info.get("marketCap") or 0) / 1e9, 1),
                "forward_pe":       info.get("forwardPE"),
                "trailing_pe":      info.get("trailingPE"),
                "target_mean":      info.get("targetMeanPrice"),
                "analyst_count":    info.get("numberOfAnalystOpinions"),
                "revenue_ttm_bn":   round((info.get("totalRevenue") or 0) / 1e9, 1),
                "fcf_bn":           round((info.get("freeCashflow") or 0) / 1e9, 1),
                "gross_margin_pct": round((info.get("grossMargins") or 0) * 100, 1),
                "debt_to_equity":   info.get("debtToEquity"),
                "beta":             info.get("beta"),
                "52w_high":         info.get("fiftyTwoWeekHigh"),
                "52w_low":          info.get("fiftyTwoWeekLow"),
                "sector":           info.get("sector"),
                "industry":         info.get("industry"),
                "company_name":     info.get("shortName"),
            }
        }
    except Exception as e:
        logger.warning("yfinance fallback failed for %s: %s", ticker, e)
        return {}


# ── Cross-Validation ─────────────────────────────────────────────────────

def _cross_validate(fmp: dict, finnhub: dict) -> list[dict]:
    """Compare overlapping fields between FMP and Finnhub.
    
    Returns a list of field comparisons with status: GREEN / AMBER / RED.
    """
    checks: list[dict] = []
    
    comparisons = [
        ("price",    fmp.get("fmp_quote", {}).get("price"),
                     finnhub.get("finnhub_quote", {}).get("price"),
                     "Real-time price", 0.5),
        ("52w_high", fmp.get("fmp_quote", {}).get("52w_high"),
                     finnhub.get("finnhub_metrics", {}).get("52w_high"),
                     "52-week high", 1.0),
        ("52w_low",  fmp.get("fmp_quote", {}).get("52w_low"),
                     finnhub.get("finnhub_metrics", {}).get("52w_low"),
                     "52-week low", 1.0),
        ("pe_ratio", fmp.get("fmp_quote", {}).get("pe"),
                     finnhub.get("finnhub_metrics", {}).get("pe_ttm"),
                     "P/E ratio (TTM)", 5.0),
    ]
    
    for field, val_a, val_b, label, amber_pct in comparisons:
        if val_a is not None and val_b is not None and val_a != 0:
            diff_pct = abs(val_a - val_b) / abs(val_a) * 100
            if diff_pct > 15:
                status = "RED"
            elif diff_pct > amber_pct:
                status = "AMBER"
            else:
                status = "GREEN"
            checks.append({
                "field": label,
                "fmp_value": val_a,
                "finnhub_value": val_b,
                "divergence_pct": round(diff_pct, 2),
                "status": status,
            })
    
    return checks


# ── Main Assembly ────────────────────────────────────────────────────────

async def _fetch_ticker_all(
    ticker: str,
    client: httpx.AsyncClient,
    fmp_key: str,
    finnhub_key: str,
) -> dict[str, Any]:
    """Fetch all data for a single ticker from all sources."""
    fmp_data: dict = {}
    finnhub_data: dict = {}
    yf_data: dict = {}
    
    # Parallel fetch from FMP + Finnhub
    fmp_task = _fetch_fmp(ticker, client, fmp_key) if fmp_key else asyncio.sleep(0)
    finnhub_task = _fetch_finnhub(ticker, client, finnhub_key) if finnhub_key else asyncio.sleep(0)
    
    results = await asyncio.gather(fmp_task, finnhub_task, return_exceptions=True)
    
    if isinstance(results[0], dict):
        fmp_data = results[0]
    elif isinstance(results[0], Exception):
        logger.warning("FMP fetch failed for %s: %s", ticker, results[0])
    
    if isinstance(results[1], dict):
        finnhub_data = results[1]
    elif isinstance(results[1], Exception):
        logger.warning("Finnhub fetch failed for %s: %s", ticker, results[1])
    
    # Determine if we need yfinance fallback
    has_price = (
        fmp_data.get("fmp_quote", {}).get("price") or
        finnhub_data.get("finnhub_quote", {}).get("price")
    )
    if not has_price:
        logger.info("No price from FMP/Finnhub for %s — trying yfinance", ticker)
        yf_data = await asyncio.to_thread(_fetch_yfinance_fallback_sync, ticker)
    
    # Cross-validate
    cross_checks = _cross_validate(fmp_data, finnhub_data) if fmp_data and finnhub_data else []
    
    return {
        **fmp_data,
        **finnhub_data,
        **yf_data,
        "cross_validation": cross_checks,
    }


def _fetch_yfinance_fallback_sync(ticker: str) -> dict:
    """Synchronous wrapper for yfinance (used with asyncio.to_thread)."""
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        if not info:
            return {}
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        return {
            "yf_quote": {
                "price":            price,
                "market_cap_bn":    round((info.get("marketCap") or 0) / 1e9, 1),
                "forward_pe":       info.get("forwardPE"),
                "trailing_pe":      info.get("trailingPE"),
                "target_mean":      info.get("targetMeanPrice"),
                "revenue_ttm_bn":   round((info.get("totalRevenue") or 0) / 1e9, 1),
                "gross_margin_pct": round((info.get("grossMargins") or 0) * 100, 1),
                "company_name":     info.get("shortName"),
                "sector":           info.get("sector"),
                "industry":         info.get("industry"),
            }
        }
    except Exception:
        return {}


# ── Unified Snapshot Builder ─────────────────────────────────────────────

def _build_unified_snapshot(ticker: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Transform raw multi-source API data into a unified stock snapshot.
    
    Priority: FMP > Finnhub > yfinance for quantitative fields.
    News and recommendations come from Finnhub (best coverage).
    """
    fq = raw.get("fmp_quote", {})
    fp = raw.get("fmp_profile", {})
    ft = raw.get("fmp_targets", {})
    fkm = raw.get("fmp_key_metrics", {})
    fi = raw.get("fmp_income", {})
    fcf = raw.get("fmp_cashflow", {})
    hq = raw.get("finnhub_quote", {})
    hr = raw.get("finnhub_recommendations", {})
    hm = raw.get("finnhub_metrics", {})
    hn = raw.get("finnhub_news", [])
    yq = raw.get("yf_quote", {})
    
    # Price: FMP > Finnhub > yfinance
    price = fq.get("price") or hq.get("price") or yq.get("price")
    
    snap: dict[str, Any] = {
        "ticker":           ticker,
        "company_name":     fp.get("company_name") or fq.get("company_name") or yq.get("company_name") or ticker,
        "sector":           fp.get("sector") or yq.get("sector", ""),
        "industry":         fp.get("industry") or yq.get("industry", ""),
        "description":      fp.get("description", ""),
        "_live":            True,
        "data_freshness":   f"Live — FMP + Finnhub ({date.today().isoformat()})",
        "data_tier":        "Tier 1/2 — dual-source verified",
        
        # Price and market data
        "price":            round(float(price), 2) if price else None,
        "market_cap_bn":    fq.get("market_cap_bn") or fkm.get("market_cap_bn") or yq.get("market_cap_bn"),
        "change_pct":       fq.get("change_pct") or hq.get("change_pct"),
        "day_high":         fq.get("day_high") or hq.get("day_high"),
        "day_low":          fq.get("day_low") or hq.get("day_low"),
        "volume":           fq.get("volume"),
        "avg_volume":       fq.get("avg_volume"),
        "beta":             fp.get("beta") or hm.get("beta"),
        
        # Valuation ratios
        "forward_pe":       fq.get("forward_pe") or yq.get("forward_pe"),
        "trailing_pe":      fq.get("pe") or hm.get("pe_ttm") or yq.get("trailing_pe"),
        "ev_ebitda":        fkm.get("ev_to_ebitda"),
        "ev_to_sales":      fkm.get("ev_to_sales"),
        "ev_to_fcf":        fkm.get("ev_to_fcf"),
        "pb_ratio":         hm.get("pb_annual"),
        "ps_ratio":         hm.get("ps_ttm"),
        "earnings_yield":   fkm.get("earnings_yield"),
        "fcf_yield":        fkm.get("fcf_yield"),
        
        # Consensus & targets
        "consensus_target_12m": ft.get("target_mean") or yq.get("target_mean"),
        "target_low":       ft.get("target_low"),
        "target_median":    ft.get("target_median"),
        "target_high":      ft.get("target_high"),
        
        # Analyst ratings (Finnhub — most granular)
        "analyst_ratings":  {
            "strong_buy": hr.get("strong_buy", 0),
            "buy":        hr.get("buy", 0),
            "hold":       hr.get("hold", 0),
            "sell":       hr.get("sell", 0),
            "strong_sell": hr.get("strong_sell", 0),
            "buy_pct":    hr.get("buy_pct", 0),
        } if hr else {},
        
        # Income / profitability
        "revenue_ttm_bn":       fi.get("revenue_bn") or yq.get("revenue_ttm_bn"),
        "gross_profit_bn":      fi.get("gross_profit_bn"),
        "operating_income_bn":  fi.get("operating_income_bn"),
        "net_income_bn":        fi.get("net_income_bn"),
        "ebitda_bn":            fi.get("ebitda_bn"),
        "eps":                  fi.get("eps_diluted") or fq.get("eps") or hm.get("eps_ttm"),
        "gross_margin_pct":     fi.get("gross_margin_pct") or (hm.get("gross_margin_ttm") and round(hm["gross_margin_ttm"] * 100, 1)),
        "operating_margin_pct": fi.get("operating_margin_pct"),
        "net_margin_pct":       fi.get("net_margin_pct") or hm.get("net_margin_ttm"),
        "r_and_d_bn":           fi.get("r_and_d_bn"),
        "eps_growth_yoy":       hm.get("eps_growth_yoy"),
        
        # Cash flow
        "operating_cf_bn":      fcf.get("operating_cf_bn"),
        "capex_bn":             fcf.get("capex_bn"),
        "free_cash_flow_ttm_bn": fcf.get("fcf_bn") or yq.get("fcf_bn"),
        "dividends_bn":         fcf.get("dividends_bn"),
        "buybacks_bn":          fcf.get("buybacks_bn"),
        
        # Returns & efficiency
        "roe":                  fkm.get("roe") or (hm.get("roe_ttm") and round(hm["roe_ttm"], 4)),
        "roic":                 fkm.get("roic"),
        "roa":                  fkm.get("roa") or (hm.get("roa_ttm") and round(hm["roa_ttm"], 4)),
        "income_quality":       fkm.get("income_quality"),
        
        # Balance sheet / risk
        "debt_to_equity":       fkm.get("debt_to_equity") or hm.get("debt_equity") or yq.get("debt_to_equity"),
        "current_ratio":        fkm.get("current_ratio") or hm.get("current_ratio"),
        "enterprise_value_bn":  fkm.get("ev_bn"),
        "working_capital_bn":   fkm.get("working_capital_bn"),
        
        # 52-week range
        "week52_high":          fq.get("52w_high") or hm.get("52w_high") or yq.get("52w_high"),
        "week52_low":           fq.get("52w_low") or hm.get("52w_low") or yq.get("52w_low"),
        
        # Qualitative — from Finnhub news feed
        "recent_news":          hn if hn else [],
        
        # Cross-validation results
        "cross_validation":     raw.get("cross_validation", []),
        
        # Corporate info
        "ceo":                  fp.get("ceo"),
        "employees":            fp.get("employees"),
        "ipo_date":             fp.get("ipo_date"),
    }
    
    # Compute upside to consensus
    tgt = snap.get("consensus_target_12m")
    if price and tgt:
        snap["upside_to_consensus_pct"] = round((tgt - price) / price * 100, 1)
    
    return snap


async def fetch_universe(
    tickers: list[str],
    fmp_key: str = "",
    finnhub_key: str = "",
    activity_cb: Any = None,
) -> dict:
    """Fetch live data for all tickers in the universe.
    
    Returns a fully structured market data package ready for the pipeline.
    """
    fmp_key = fmp_key or os.environ.get("FMP_API_KEY", "")
    finnhub_key = finnhub_key or os.environ.get("FINNHUB_API_KEY", "")
    
    if not fmp_key and not finnhub_key:
        logger.warning("No FMP or Finnhub API key — all data will come from yfinance fallback")
    
    if activity_cb:
        activity_cb(f"Fetching live data for {len(tickers)} tickers (FMP + Finnhub)…")
    
    async with httpx.AsyncClient() as client:
        tasks = [
            _fetch_ticker_all(ticker, client, fmp_key, finnhub_key)
            for ticker in tickers
        ]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    stocks: dict[str, dict] = {}
    live_count = 0
    errors: list[str] = []
    
    for ticker, raw in zip(tickers, raw_results):
        if isinstance(raw, Exception):
            logger.error("Total fetch failure for %s: %s", ticker, raw)
            errors.append(f"{ticker}: {raw}")
            # Attempt yfinance fallback as last resort
            yf_data = _fetch_yfinance_fallback_sync(ticker)
            if yf_data:
                snap = _build_unified_snapshot(ticker, yf_data)
                snap["data_tier"] = "Tier 3 — yfinance fallback"
                snap["data_freshness"] = f"Fallback — yfinance ({date.today().isoformat()})"
                stocks[ticker] = snap
                live_count += 1
            else:
                stocks[ticker] = {
                    "ticker": ticker,
                    "company_name": ticker,
                    "_live": False,
                    "data_tier": "No data — all sources failed",
                    "error": str(raw),
                }
        else:
            snap = _build_unified_snapshot(ticker, raw)
            stocks[ticker] = snap
            if snap.get("price"):
                live_count += 1
    
    sources = []
    if fmp_key:
        sources.append("FMP")
    if finnhub_key:
        sources.append("Finnhub")
    sources.append("yfinance fallback")
    
    return {
        "date":        date.today().isoformat(),
        "data_source": f"Live multi-source: {' + '.join(sources)}",
        "live_count":  live_count,
        "total_count": len(tickers),
        "stocks":      stocks,
        "errors":      errors,
    }


async def fetch_macro_context(finnhub_key: str = "") -> dict:
    """Fetch live macro context from Finnhub economic indicators.
    
    Falls back to reasonable defaults if API fails.
    """
    finnhub_key = finnhub_key or os.environ.get("FINNHUB_API_KEY", "")
    
    macro: dict[str, Any] = {
        "date":   date.today().isoformat(),
        "source": "Live market data",
    }
    
    # Try to get basic market indices for context
    try:
        async with httpx.AsyncClient() as client:
            # Fetch VIX and major indices via Finnhub
            vix_data = await _finnhub_get(client, "/quote", finnhub_key, {"symbol": "VIX"})
            if vix_data and isinstance(vix_data, dict):
                macro["vix"] = vix_data.get("c")
            
            spy_data = await _finnhub_get(client, "/quote", finnhub_key, {"symbol": "SPY"})
            if spy_data and isinstance(spy_data, dict):
                macro["spy_price"] = spy_data.get("c")
                macro["spy_change_pct"] = spy_data.get("dp")
            
            qqq_data = await _finnhub_get(client, "/quote", finnhub_key, {"symbol": "QQQ"})
            if qqq_data and isinstance(qqq_data, dict):
                macro["qqq_price"] = qqq_data.get("c")
                macro["qqq_change_pct"] = qqq_data.get("dp")
    except Exception as e:
        logger.warning("Macro context fetch failed: %s", e)
    
    return macro
