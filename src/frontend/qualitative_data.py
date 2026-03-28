"""Qualitative Intelligence Engine.

Deep qualitative data collection from 8+ sources across FMP and Finnhub,
structured for LLM-driven synthesis and correlation with quantitative data.

Sources:
  1. Company News        — FMP stock-news + Finnhub company-news (deduplicated)
  2. Press Releases      — FMP press-releases (earnings, guidance, M&A)
  3. Earnings Transcripts — FMP earning-call-transcript (management commentary)
  4. SEC Filings         — FMP sec-filings (8-K material events, 10-K/10-Q)
  5. Analyst Actions     — FMP upgrades-downgrades (grade changes with context)
  6. Insider Activity    — FMP insider-trading (buy/sell patterns, MSPR)
  7. Analyst Estimates   — FMP analyst-estimates (forward revenue/EPS consensus)
  8. Sentiment Signals   — FMP social-sentiment (Reddit/StockTwits volume & score)

Each source is fetched independently with graceful degradation — if an endpoint
fails or the API plan doesn't include it, we skip and note it in coverage gaps.

The raw qualitative data is structured into a per-ticker QualitativePackage that
downstream stages use for deep reasoning and correlation with quantitative metrics.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(15.0, connect=10.0)


# ── API helpers (reuse same pattern as market_data.py) ───────────────────

async def _fmp_get(
    client: httpx.AsyncClient, path: str, api_key: str, extra: dict | None = None,
) -> dict | list:
    url = f"https://financialmodelingprep.com/stable{path}"
    params = {"apikey": api_key, **(extra or {})}
    r = await client.get(url, params=params, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


async def _finnhub_get(
    client: httpx.AsyncClient, path: str, api_key: str, extra: dict | None = None,
) -> dict | list:
    url = f"https://finnhub.io/api/v1{path}"
    params = {"token": api_key, **(extra or {})}
    r = await client.get(url, params=params, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


# ── Data classes ─────────────────────────────────────────────────────────

@dataclass
class QualitativePackage:
    """All qualitative intelligence for a single ticker."""
    ticker: str
    news: list[dict] = field(default_factory=list)          # deduplicated from FMP + Finnhub
    press_releases: list[dict] = field(default_factory=list)
    earnings_transcript: dict = field(default_factory=dict)  # most recent quarter
    sec_filings: list[dict] = field(default_factory=list)
    analyst_actions: list[dict] = field(default_factory=list) # upgrades / downgrades
    insider_activity: list[dict] = field(default_factory=list)
    analyst_estimates: dict = field(default_factory=dict)     # forward consensus
    sentiment: dict = field(default_factory=dict)             # social sentiment
    coverage_gaps: list[str] = field(default_factory=list)    # sources that failed

    def to_prompt_block(self) -> str:
        """Render all qualitative data as a structured text block for LLM ingestion."""
        sections: list[str] = [f"═══ QUALITATIVE INTELLIGENCE: {self.ticker} ═══"]

        # 1 — News & market signals
        if self.news:
            sections.append("\n### Recent News & Market Signals")
            for i, n in enumerate(self.news[:12], 1):
                src = n.get("source", "Unknown")
                headline = n.get("headline", "")
                summary = n.get("summary", "")
                sentiment_label = n.get("sentiment", "")
                sent_str = f" [{sentiment_label}]" if sentiment_label else ""
                sections.append(f"{i}. **{headline}**{sent_str}\n   Source: {src} | {summary[:250]}")
        else:
            sections.append("\n### Recent News: NONE AVAILABLE — evidence gap")

        # 2 — Press releases
        if self.press_releases:
            sections.append("\n### Press Releases (official company communications)")
            for pr in self.press_releases[:6]:
                title = pr.get("title", "")
                pr_date = pr.get("date", "")
                text = pr.get("text", "")[:300]
                sections.append(f"- **{title}** ({pr_date})\n  {text}")
        else:
            sections.append("\n### Press Releases: NONE AVAILABLE")

        # 3 — Earnings transcript
        if self.earnings_transcript:
            et = self.earnings_transcript
            sections.append(
                f"\n### Most Recent Earnings Call — {et.get('quarter', '?')} {et.get('year', '?')}"
            )
            sections.append(f"Date: {et.get('date', 'N/A')}")
            content = et.get("content", "")
            if content:
                # Send meaningful excerpt — management commentary is gold
                sections.append(f"**Transcript excerpt** (first ~3000 chars):\n{content[:3000]}")
            else:
                sections.append("(transcript text not available — check API plan)")
        else:
            sections.append(
                "\n### Earnings Transcript: NOT AVAILABLE — "
                "CRITICAL GAP (management commentary missing)"
            )

        # 4 — SEC filings
        if self.sec_filings:
            sections.append("\n### Recent SEC Filings")
            for f in self.sec_filings[:8]:
                ftype = f.get("type", "")
                fdate = f.get("filledDate", f.get("date", ""))
                link = f.get("link", "")
                sections.append(f"- **{ftype}** filed {fdate} — {link}")
        else:
            sections.append("\n### SEC Filings: NONE AVAILABLE")

        # 5 — Analyst actions (upgrades / downgrades)
        if self.analyst_actions:
            sections.append("\n### Recent Analyst Actions (upgrades/downgrades)")
            for a in self.analyst_actions[:10]:
                firm = a.get("gradeCompany", a.get("company", "Unknown"))
                action = a.get("action", "")
                old = a.get("previousGrade", "")
                new = a.get("newGrade", "")
                adate = a.get("gradingDate", a.get("date", ""))
                arrow = "→"
                sections.append(
                    f"- **{firm}**: {action} {old} {arrow} {new} ({adate})"
                )
        else:
            sections.append("\n### Analyst Actions: NONE AVAILABLE")

        # 6 — Insider activity
        if self.insider_activity:
            sections.append("\n### Insider Trading Activity")
            total_bought = 0
            total_sold = 0
            for tx in self.insider_activity[:15]:
                name = tx.get("reportingName", tx.get("name", "Unknown"))
                title = tx.get("typeOfOwner", tx.get("title", ""))
                txn_type = tx.get("acquistionOrDisposition", tx.get("transactionType", ""))
                shares = tx.get("securitiesTransacted", tx.get("shares", 0))
                price_per = tx.get("price", 0)
                value = tx.get("value", (shares or 0) * (price_per or 0))
                tx_date = tx.get("filingDate", tx.get("transactionDate", ""))

                if txn_type in ("A", "P", "Buy"):
                    total_bought += value or 0
                    direction = "BUY"
                elif txn_type in ("D", "S", "Sale"):
                    total_sold += value or 0
                    direction = "SELL"
                else:
                    direction = txn_type

                val_str = f"${value:,.0f}" if value else "N/A"
                sections.append(
                    f"- {direction}: {name} ({title}) — "
                    f"{shares:,.0f} shares @ ${price_per:.2f} = {val_str} ({tx_date})"
                )

            # Net insider sentiment
            net = total_bought - total_sold
            if total_bought + total_sold > 0:
                direction_label = "NET BUYING" if net > 0 else "NET SELLING"
                sections.append(
                    f"\n  **Insider Summary**: {direction_label} — "
                    f"bought ${total_bought:,.0f}, sold ${total_sold:,.0f}, "
                    f"net ${net:+,.0f}"
                )
        else:
            sections.append("\n### Insider Activity: NONE AVAILABLE")

        # 7 — Forward estimates
        if self.analyst_estimates:
            ae = self.analyst_estimates
            sections.append("\n### Forward Analyst Estimates (consensus)")
            for period_key in ("current_quarter", "current_year", "next_year"):
                period = ae.get(period_key, {})
                if period:
                    label = period_key.replace("_", " ").title()
                    rev = period.get("estimatedRevenueAvg")
                    rev_str = f"${rev / 1e9:.2f}B" if rev else "N/A"
                    eps = period.get("estimatedEpsAvg")
                    eps_str = f"${eps:.2f}" if eps else "N/A"
                    n_analysts = period.get("numberAnalystsEstimatedRevenue", "?")
                    sections.append(
                        f"- **{label}**: Revenue {rev_str}, EPS {eps_str} "
                        f"({n_analysts} analysts)"
                    )
                    # Estimate spread gives conviction signal
                    rev_lo = period.get("estimatedRevenueLow")
                    rev_hi = period.get("estimatedRevenueHigh")
                    if rev_lo and rev_hi and rev_lo > 0:
                        spread = (rev_hi - rev_lo) / rev_lo * 100
                        sections.append(f"  Revenue range: ${rev_lo/1e9:.2f}B — ${rev_hi/1e9:.2f}B (spread {spread:.1f}%)")
                    eps_lo = period.get("estimatedEpsLow")
                    eps_hi = period.get("estimatedEpsHigh")
                    if eps_lo is not None and eps_hi is not None and eps_lo != 0:
                        sections.append(f"  EPS range: ${eps_lo:.2f} — ${eps_hi:.2f}")

        # 8 — Sentiment
        if self.sentiment:
            sections.append("\n### Social & Market Sentiment")
            if self.sentiment.get("stocktwits_sentiment"):
                st = self.sentiment["stocktwits_sentiment"]
                sections.append(
                    f"- StockTwits: score {st.get('score', 'N/A')}, "
                    f"posts {st.get('posts', 'N/A')}"
                )
            if self.sentiment.get("reddit_sentiment"):
                rd = self.sentiment["reddit_sentiment"]
                sections.append(
                    f"- Reddit: score {rd.get('score', 'N/A')}, "
                    f"mentions {rd.get('mentions', 'N/A')}"
                )
            if self.sentiment.get("news_sentiment_score") is not None:
                score = self.sentiment["news_sentiment_score"]
                label = "BULLISH" if score > 0.5 else "BEARISH" if score < -0.5 else "NEUTRAL"
                sections.append(f"- News Sentiment Score: {score:.2f} ({label})")

        # Coverage gaps
        if self.coverage_gaps:
            sections.append(f"\n### ⚠ Coverage Gaps: {', '.join(self.coverage_gaps)}")

        return "\n".join(sections)

    @property
    def signal_count(self) -> int:
        """Total number of qualitative signals available."""
        return (
            len(self.news)
            + len(self.press_releases)
            + (1 if self.earnings_transcript else 0)
            + len(self.sec_filings)
            + len(self.analyst_actions)
            + len(self.insider_activity)
            + (1 if self.analyst_estimates else 0)
            + (1 if self.sentiment else 0)
        )

    @property
    def coverage_score(self) -> str:
        """Rate qualitative coverage depth."""
        count = self.signal_count
        gaps = len(self.coverage_gaps)
        if count >= 15 and gaps <= 1:
            return "DEEP"
        if count >= 8 and gaps <= 3:
            return "MODERATE"
        if count >= 3:
            return "THIN"
        return "MINIMAL"

    def correlation_hints(self, quant_snapshot: dict) -> list[str]:
        """Generate hints about qualitative-quantitative correlations.

        These hints help LLM agents reason about alignment or divergence
        between the qualitative narrative and the quantitative reality.
        """
        hints: list[str] = []
        price = quant_snapshot.get("price")
        target = quant_snapshot.get("consensus_target_12m")
        fwd_pe = quant_snapshot.get("forward_pe")

        # Insider activity vs price trajectory
        if self.insider_activity:
            buys = sum(
                1 for tx in self.insider_activity
                if tx.get("acquistionOrDisposition", tx.get("transactionType", "")) in ("A", "P", "Buy")
            )
            sells = sum(
                1 for tx in self.insider_activity
                if tx.get("acquistionOrDisposition", tx.get("transactionType", "")) in ("D", "S", "Sale")
            )
            if sells > buys * 2 and price and target and price > target:
                hints.append(
                    "DIVERGENCE: Heavy insider selling while price is above consensus target — "
                    "insiders may see downside not yet priced in"
                )
            elif buys > sells * 2 and price and target and price < target:
                hints.append(
                    "CONVERGENCE: Heavy insider buying while price is below target — "
                    "insiders are signaling conviction"
                )

        # Analyst actions vs consensus
        if self.analyst_actions:
            upgrades = sum(1 for a in self.analyst_actions if "upgrade" in (a.get("action", "")).lower())
            downgrades = sum(1 for a in self.analyst_actions if "downgrade" in (a.get("action", "")).lower())
            if upgrades > downgrades and fwd_pe and fwd_pe > 40:
                hints.append(
                    f"TENSION: Analysts upgrading but fwd P/E at {fwd_pe:.1f}x — "
                    "is the upgrade cycle already priced in?"
                )
            elif downgrades > upgrades:
                hints.append(
                    f"CAUTION: More downgrades ({downgrades}) than upgrades ({upgrades}) recently"
                )

        # Earnings estimate spread
        for period_key in ("current_year", "next_year"):
            est = self.analyst_estimates.get(period_key, {})
            rev_lo = est.get("estimatedRevenueLow")
            rev_hi = est.get("estimatedRevenueHigh")
            if rev_lo and rev_hi and rev_lo > 0:
                spread = (rev_hi - rev_lo) / rev_lo * 100
                if spread > 30:
                    hints.append(
                        f"HIGH UNCERTAINTY: {period_key.replace('_', ' ').title()} "
                        f"revenue estimate spread is {spread:.0f}% — "
                        "wide analyst disagreement, catalysts could move estimates sharply"
                    )

        # News volume as attention signal
        if len(self.news) >= 10:
            hints.append(
                f"HIGH ATTENTION: {len(self.news)} news items in recent window — "
                "elevated market/media attention, potential for sentiment-driven volatility"
            )
        elif len(self.news) <= 2:
            hints.append(
                "LOW COVERAGE: Very few recent news items — "
                "may indicate under-the-radar opportunity or lack of catalysts"
            )

        # Sentiment alignment
        ns = self.sentiment.get("news_sentiment_score")
        if ns is not None and price and target:
            upside = (target - price) / price * 100 if price else 0
            if ns < -0.3 and upside > 20:
                hints.append(
                    f"CONTRARIAN SIGNAL: News sentiment bearish ({ns:.2f}) but "
                    f"consensus target implies {upside:.0f}% upside — potential mean reversion"
                )
            elif ns > 0.5 and upside < 0:
                hints.append(
                    f"CROWDING RISK: News sentiment bullish ({ns:.2f}) but "
                    f"price already above consensus target — sentiment may be peaking"
                )

        return hints


# ── Per-Source Fetchers ──────────────────────────────────────────────────

async def _fetch_fmp_news(
    ticker: str, client: httpx.AsyncClient, api_key: str
) -> list[dict]:
    """Fetch company-specific news from FMP."""
    try:
        data = await _fmp_get(client, "/news/stock", api_key, {
            "symbol": ticker,
            "limit": "15",
        })
        if not isinstance(data, list):
            return []
        return [
            {
                "headline": item.get("title", ""),
                "summary":  (item.get("text") or "")[:400],
                "source":   item.get("site", item.get("source", "")),
                "datetime": item.get("publishedDate", ""),
                "url":      item.get("url", ""),
                "sentiment": item.get("sentiment", ""),
                "provider":  "FMP",
            }
            for item in data[:15] if item.get("title")
        ]
    except Exception as e:
        logger.debug("FMP news failed for %s: %s", ticker, e)
        return []


async def _fetch_fmp_press_releases(
    ticker: str, client: httpx.AsyncClient, api_key: str
) -> list[dict]:
    """Fetch official press releases from FMP."""
    try:
        data = await _fmp_get(client, "/press-releases", api_key, {
            "symbol": ticker,
            "limit": "8",
        })
        if not isinstance(data, list):
            return []
        return [
            {
                "title": item.get("title", ""),
                "date":  item.get("date", ""),
                "text":  (item.get("text") or "")[:500],
            }
            for item in data[:8] if item.get("title")
        ]
    except Exception as e:
        logger.debug("FMP press releases failed for %s: %s", ticker, e)
        return []


async def _fetch_fmp_earnings_transcript(
    ticker: str, client: httpx.AsyncClient, api_key: str
) -> dict:
    """Fetch the most recent earnings call transcript from FMP."""
    # Try current year quarters, then previous year
    today = date.today()
    year = today.year
    for y in (year, year - 1):
        for q in range(4, 0, -1):
            try:
                data = await _fmp_get(
                    client, "/earning-call-transcript", api_key,
                    {"symbol": ticker, "year": str(y), "quarter": str(q)},
                )
                if isinstance(data, list) and data:
                    item = data[0]
                    content = item.get("content", "")
                    if content:
                        return {
                            "quarter": f"Q{q}",
                            "year": str(y),
                            "date": item.get("date", ""),
                            "content": content,
                        }
                elif isinstance(data, dict) and data.get("content"):
                    return {
                        "quarter": f"Q{q}",
                        "year": str(y),
                        "date": data.get("date", ""),
                        "content": data["content"],
                    }
            except Exception:
                continue
    logger.debug("No earnings transcript found for %s", ticker)
    return {}


async def _fetch_fmp_sec_filings(
    ticker: str, client: httpx.AsyncClient, api_key: str
) -> list[dict]:
    """Fetch recent SEC filings from FMP."""
    try:
        data = await _fmp_get(client, "/sec-filings", api_key, {
            "symbol": ticker,
            "limit": "15",
        })
        if not isinstance(data, list):
            return []
        # Prioritise material filings
        priority_types = {"8-K", "10-K", "10-Q", "S-1", "DEF 14A", "13F"}
        filings = []
        for item in data:
            ftype = item.get("type", "")
            if ftype in priority_types:
                filings.append({
                    "type":       ftype,
                    "filledDate": item.get("fillingDate", item.get("filledDate", "")),
                    "link":       item.get("finalLink", item.get("link", "")),
                    "accepted":   item.get("acceptedDate", ""),
                })
            if len(filings) >= 10:
                break
        return filings
    except Exception as e:
        logger.debug("FMP SEC filings failed for %s: %s", ticker, e)
        return []


async def _fetch_fmp_analyst_actions(
    ticker: str, client: httpx.AsyncClient, api_key: str
) -> list[dict]:
    """Fetch recent analyst upgrades/downgrades from FMP."""
    try:
        data = await _fmp_get(client, "/upgrades-downgrades", api_key, {
            "symbol": ticker,
            "limit": "12",
        })
        if not isinstance(data, list):
            return []
        return [
            {
                "gradeCompany":  item.get("gradingCompany", item.get("company", "")),
                "action":        item.get("action", item.get("newGrade", "")),
                "previousGrade": item.get("previousGrade", ""),
                "newGrade":      item.get("newGrade", ""),
                "gradingDate":   item.get("publishedDate", item.get("gradingDate", "")),
            }
            for item in data[:12]
        ]
    except Exception as e:
        logger.debug("FMP analyst actions failed for %s: %s", ticker, e)
        return []


async def _fetch_fmp_insider_trading(
    ticker: str, client: httpx.AsyncClient, api_key: str
) -> list[dict]:
    """Fetch insider trading data from FMP."""
    try:
        data = await _fmp_get(client, "/insider-trading", api_key, {
            "symbol": ticker,
            "limit": "20",
        })
        if not isinstance(data, list):
            return []
        return [
            {
                "reportingName":           item.get("reportingName", ""),
                "typeOfOwner":             item.get("typeOfOwner", ""),
                "acquistionOrDisposition": item.get("acquistionOrDisposition", ""),
                "securitiesTransacted":    item.get("securitiesTransacted", 0),
                "price":                   item.get("price", 0),
                "value":                   item.get("securitiesTransacted", 0) * (item.get("price") or 0),
                "filingDate":              item.get("filingDate", ""),
                "transactionDate":         item.get("transactionDate", ""),
                "securityName":            item.get("securityName", ""),
            }
            for item in data[:20]
        ]
    except Exception as e:
        logger.debug("FMP insider trading failed for %s: %s", ticker, e)
        return []


async def _fetch_fmp_analyst_estimates(
    ticker: str, client: httpx.AsyncClient, api_key: str
) -> dict:
    """Fetch forward analyst estimates (revenue/EPS consensus) from FMP."""
    try:
        data = await _fmp_get(client, "/analyst-estimates", api_key, {
            "symbol": ticker,
            "limit": "4",
        })
        if not isinstance(data, list) or not data:
            return {}
        result = {}
        for i, item in enumerate(data[:3]):
            key = ["current_quarter", "current_year", "next_year"][i] if i < 3 else f"period_{i}"
            result[key] = {
                "date":                          item.get("date", ""),
                "estimatedRevenueAvg":           item.get("estimatedRevenueAvg"),
                "estimatedRevenueLow":           item.get("estimatedRevenueLow"),
                "estimatedRevenueHigh":          item.get("estimatedRevenueHigh"),
                "estimatedEpsAvg":               item.get("estimatedEpsAvg"),
                "estimatedEpsLow":               item.get("estimatedEpsLow"),
                "estimatedEpsHigh":              item.get("estimatedEpsHigh"),
                "numberAnalystsEstimatedRevenue": item.get("numberAnalystsEstimatedRevenue"),
                "numberAnalystsEstimatedEps":    item.get("numberAnalystsEstimatedEps"),
            }
        return result
    except Exception as e:
        logger.debug("FMP analyst estimates failed for %s: %s", ticker, e)
        return {}


async def _fetch_fmp_social_sentiment(
    ticker: str, client: httpx.AsyncClient, api_key: str
) -> dict:
    """Fetch social media sentiment from FMP."""
    try:
        data = await _fmp_get(client, "/social-sentiment", api_key, {
            "symbol": ticker,
            "limit": "5",
        })
        if not isinstance(data, list) or not data:
            return {}
        # Aggregate recent sentiment
        stocktwits_scores = []
        reddit_scores = []
        stocktwits_posts = 0
        reddit_mentions = 0
        for item in data:
            if item.get("stocktwitsSentiment") is not None:
                stocktwits_scores.append(item["stocktwitsSentiment"])
                stocktwits_posts += item.get("stocktwitsPostsCount", item.get("stocktwitsPosts", 0))
            if item.get("redditSentiment") is not None:
                reddit_scores.append(item["redditSentiment"])
                reddit_mentions += item.get("redditMentions", item.get("redditComments", 0))

        result: dict[str, Any] = {}
        if stocktwits_scores:
            result["stocktwits_sentiment"] = {
                "score": round(sum(stocktwits_scores) / len(stocktwits_scores), 3),
                "posts": stocktwits_posts,
            }
        if reddit_scores:
            result["reddit_sentiment"] = {
                "score": round(sum(reddit_scores) / len(reddit_scores), 3),
                "mentions": reddit_mentions,
            }
        return result
    except Exception as e:
        logger.debug("FMP social sentiment failed for %s: %s", ticker, e)
        return {}


async def _fetch_finnhub_news(
    ticker: str, client: httpx.AsyncClient, api_key: str
) -> list[dict]:
    """Fetch company news from Finnhub (wider window than market_data.py)."""
    try:
        today = date.today()
        two_weeks_ago = today - timedelta(days=14)
        data = await _finnhub_get(client, "/company-news", api_key, {
            "symbol": ticker,
            "from": two_weeks_ago.isoformat(),
            "to": today.isoformat(),
        })
        if not isinstance(data, list):
            return []
        seen: set[str] = set()
        news = []
        for item in data[:30]:
            headline = item.get("headline", "")
            if headline and headline not in seen:
                seen.add(headline)
                news.append({
                    "headline": headline,
                    "summary":  (item.get("summary") or "")[:300],
                    "source":   item.get("source"),
                    "datetime": item.get("datetime"),
                    "url":      item.get("url"),
                    "provider": "Finnhub",
                })
            if len(news) >= 15:
                break
        return news
    except Exception as e:
        logger.debug("Finnhub news failed for %s: %s", ticker, e)
        return []


async def _fetch_finnhub_sentiment(
    ticker: str, client: httpx.AsyncClient, api_key: str
) -> dict:
    """Fetch insider sentiment (MSPR) and news sentiment from Finnhub."""
    result: dict[str, Any] = {}

    # Insider sentiment (Monthly Share Purchase Ratio)
    try:
        data = await _finnhub_get(client, "/stock/insider-sentiment", api_key, {
            "symbol": ticker,
            "from": (date.today() - timedelta(days=90)).isoformat(),
        })
        if isinstance(data, dict) and data.get("data"):
            latest = data["data"][0] if data["data"] else {}
            if latest:
                result["mspr"] = latest.get("mspr")
                result["mspr_change"] = latest.get("change")
    except Exception as e:
        logger.debug("Finnhub insider sentiment failed for %s: %s", ticker, e)

    # News sentiment
    try:
        data = await _finnhub_get(client, "/news-sentiment", api_key, {"symbol": ticker})
        if isinstance(data, dict):
            sent = data.get("sentiment", {})
            if sent:
                result["news_sentiment_score"] = sent.get("bearishPercent", 0) * -1 + sent.get("bullishPercent", 0)
                result["buzz_score"] = data.get("buzz", {}).get("buzz")
                result["articles_in_period"] = data.get("buzz", {}).get("articlesInLastWeek")
    except Exception as e:
        logger.debug("Finnhub news sentiment failed for %s: %s", ticker, e)

    return result


# ── Main Fetch Orchestrator ──────────────────────────────────────────────

async def _fetch_ticker_qualitative(
    ticker: str,
    client: httpx.AsyncClient,
    fmp_key: str,
    finnhub_key: str,
) -> QualitativePackage:
    """Fetch all qualitative data for a single ticker from all sources."""
    pkg = QualitativePackage(ticker=ticker)

    # Launch all fetches in parallel
    tasks: dict[str, Any] = {}
    if fmp_key:
        tasks["fmp_news"] = _fetch_fmp_news(ticker, client, fmp_key)
        tasks["press_releases"] = _fetch_fmp_press_releases(ticker, client, fmp_key)
        tasks["earnings_transcript"] = _fetch_fmp_earnings_transcript(ticker, client, fmp_key)
        tasks["sec_filings"] = _fetch_fmp_sec_filings(ticker, client, fmp_key)
        tasks["analyst_actions"] = _fetch_fmp_analyst_actions(ticker, client, fmp_key)
        tasks["insider_trading"] = _fetch_fmp_insider_trading(ticker, client, fmp_key)
        tasks["analyst_estimates"] = _fetch_fmp_analyst_estimates(ticker, client, fmp_key)
        tasks["social_sentiment"] = _fetch_fmp_social_sentiment(ticker, client, fmp_key)
    else:
        pkg.coverage_gaps.extend([
            "FMP news", "press releases", "earnings transcripts",
            "SEC filings", "analyst actions", "insider trading",
            "analyst estimates", "social sentiment",
        ])

    if finnhub_key:
        tasks["finnhub_news"] = _fetch_finnhub_news(ticker, client, finnhub_key)
        tasks["finnhub_sentiment"] = _fetch_finnhub_sentiment(ticker, client, finnhub_key)
    else:
        pkg.coverage_gaps.extend(["Finnhub news", "Finnhub sentiment"])

    # Execute all tasks
    if tasks:
        task_names = list(tasks.keys())
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        fetched = dict(zip(task_names, results))

        # Assign results, noting gaps for failures
        # News — deduplicate FMP + Finnhub
        fmp_news = fetched.get("fmp_news", [])
        finnhub_news = fetched.get("finnhub_news", [])
        if isinstance(fmp_news, Exception):
            fmp_news = []
            pkg.coverage_gaps.append("FMP news")
        if isinstance(finnhub_news, Exception):
            finnhub_news = []
            pkg.coverage_gaps.append("Finnhub news")

        # Deduplicate by headline similarity
        seen_headlines: set[str] = set()
        merged_news: list[dict] = []
        for item in fmp_news + finnhub_news:
            headline = item.get("headline", "").lower().strip()
            # Simple dedup — exact match after lowering
            if headline and headline not in seen_headlines:
                seen_headlines.add(headline)
                merged_news.append(item)
        pkg.news = merged_news[:20]

        # Press releases
        pr = fetched.get("press_releases", [])
        if isinstance(pr, Exception):
            pkg.coverage_gaps.append("press releases")
        else:
            pkg.press_releases = pr

        # Earnings transcript
        et = fetched.get("earnings_transcript", {})
        if isinstance(et, Exception):
            pkg.coverage_gaps.append("earnings transcripts")
        else:
            pkg.earnings_transcript = et

        # SEC filings
        sf = fetched.get("sec_filings", [])
        if isinstance(sf, Exception):
            pkg.coverage_gaps.append("SEC filings")
        else:
            pkg.sec_filings = sf

        # Analyst actions
        aa = fetched.get("analyst_actions", [])
        if isinstance(aa, Exception):
            pkg.coverage_gaps.append("analyst actions")
        else:
            pkg.analyst_actions = aa

        # Insider trading
        it = fetched.get("insider_trading", [])
        if isinstance(it, Exception):
            pkg.coverage_gaps.append("insider trading")
        else:
            pkg.insider_activity = it

        # Analyst estimates
        ae = fetched.get("analyst_estimates", {})
        if isinstance(ae, Exception):
            pkg.coverage_gaps.append("analyst estimates")
        else:
            pkg.analyst_estimates = ae

        # Sentiment — merge FMP social + Finnhub sentiment
        fmp_sent = fetched.get("social_sentiment", {})
        fhb_sent = fetched.get("finnhub_sentiment", {})
        if isinstance(fmp_sent, Exception):
            fmp_sent = {}
            pkg.coverage_gaps.append("social sentiment")
        if isinstance(fhb_sent, Exception):
            fhb_sent = {}
            pkg.coverage_gaps.append("Finnhub sentiment")
        pkg.sentiment = {**fmp_sent, **fhb_sent}

    return pkg


async def fetch_qualitative_universe(
    tickers: list[str],
    fmp_key: str = "",
    finnhub_key: str = "",
    activity_cb: Any = None,
) -> dict[str, QualitativePackage]:
    """Fetch qualitative intelligence for all tickers in parallel.

    Returns a dict of ticker -> QualitativePackage.
    """
    import os
    fmp_key = fmp_key or os.environ.get("FMP_API_KEY", "")
    finnhub_key = finnhub_key or os.environ.get("FINNHUB_API_KEY", "")

    if activity_cb:
        activity_cb(
            f"Fetching qualitative intelligence for {len(tickers)} tickers "
            f"(8 sources × {len(tickers)} tickers = up to {8 * len(tickers)} API calls)…"
        )

    async with httpx.AsyncClient() as client:
        tasks = [
            _fetch_ticker_qualitative(ticker, client, fmp_key, finnhub_key)
            for ticker in tickers
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    packages: dict[str, QualitativePackage] = {}
    for ticker, result in zip(tickers, results):
        if isinstance(result, Exception):
            logger.error("Total qualitative fetch failure for %s: %s", ticker, result)
            pkg = QualitativePackage(ticker=ticker)
            pkg.coverage_gaps.append(f"TOTAL FAILURE: {result}")
            packages[ticker] = pkg
        else:
            packages[ticker] = result
            if activity_cb:
                activity_cb(
                    f"  {ticker}: {result.signal_count} signals, "
                    f"coverage {result.coverage_score}"
                )

    return packages
