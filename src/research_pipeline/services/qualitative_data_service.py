"""Qualitative Data Service — typed backend ingestion for 8 qualitative sources.

This service formalises qualitative data collection that previously existed
only in the frontend (src/frontend/qualitative_data.py). It uses the same
FMP + Finnhub endpoints but returns typed Pydantic schemas from
research_pipeline.schemas.qualitative, providing a contract-stable backend path.

Sources:
  1. Company News & Press Releases  — FMP + Finnhub (deduplicated)
  2. Earnings Transcripts           — FMP earning-call-transcript
  3. SEC Filings                    — FMP sec-filings
  4. Analyst Actions                — FMP upgrades-downgrades
  5. Insider Activity               — FMP insider-trading
  6. Analyst Estimates              — FMP analyst-estimates
  7. Sentiment Signals              — FMP social-sentiment + Finnhub sentiment

Failure handling: every source degrades gracefully — failures are recorded
in QualitativePackage.coverage_gaps, not raised to callers.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False
    logger.warning("httpx not available — QualitativeDataService will return empty packages")

from research_pipeline.schemas.qualitative import (
    AnalystAction,
    AnalystEstimates,
    CoverageDepth,
    EarningsTranscript,
    EstimatePeriod,
    InsiderActivitySummary,
    InsiderDirection,
    InsiderTransaction,
    NewsItem,
    PressRelease,
    QualitativePackage,
    SECFiling,
    SentimentLabel,
    SentimentSignals,
)

_TIMEOUT_SECS = 15.0
_MAX_CONCURRENT = 4   # max simultaneous ticker ingestions


def _parse_date(val: Any) -> Optional[datetime]:
    """Best-effort date parser for FMP/Finnhub string formats."""
    if not val:
        return None
    if isinstance(val, (int, float)):
        try:
            return datetime.fromtimestamp(val, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None
    val = str(val).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(val[:len(fmt)], fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _headline_hash(headline: str) -> str:
    return hashlib.md5(headline.strip().lower().encode()).hexdigest()


class QualitativeDataService:
    """Fetches and validates all qualitative data sources for a ticker universe.

    Usage:
        svc = QualitativeDataService(fmp_key="...", finnhub_key="...")
        packages = asyncio.run(svc.ingest_universe(["NVDA", "AVGO"]))
    """

    FMP_BASE = "https://financialmodelingprep.com/stable"
    FINNHUB_BASE = "https://finnhub.io/api/v1"

    def __init__(
        self,
        fmp_key: str = "",
        finnhub_key: str = "",
        max_concurrent: int = _MAX_CONCURRENT,
    ):
        self.fmp_key = fmp_key
        self.finnhub_key = finnhub_key
        self._sem = asyncio.Semaphore(max_concurrent)

    # ── Public API ────────────────────────────────────────────────────

    async def ingest_universe(
        self, tickers: list[str]
    ) -> dict[str, QualitativePackage]:
        """Ingest all qualitative data for a list of tickers concurrently.

        Returns dict mapping ticker → QualitativePackage.
        """
        if not _HTTPX_AVAILABLE:
            return {t: QualitativePackage(ticker=t, coverage_gaps=["httpx_unavailable"]) for t in tickers}

        async with httpx.AsyncClient(timeout=_TIMEOUT_SECS) as client:
            tasks = [self._ingest_one(client, t) for t in tickers]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        packages: dict[str, QualitativePackage] = {}
        for ticker, result in zip(tickers, results):
            if isinstance(result, Exception):
                logger.error("Qualitative ingestion failed for %s: %s", ticker, result)
                packages[ticker] = QualitativePackage(
                    ticker=ticker,
                    coverage_gaps=["ingest_error"],
                )
            else:
                packages[ticker] = result
        return packages

    async def ingest_ticker(self, ticker: str) -> QualitativePackage:
        """Ingest all qualitative data for a single ticker."""
        if not _HTTPX_AVAILABLE:
            return QualitativePackage(ticker=ticker, coverage_gaps=["httpx_unavailable"])
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECS) as client:
            return await self._ingest_one(client, ticker)

    # ── Internal orchestration ─────────────────────────────────────────

    async def _ingest_one(
        self, client: httpx.AsyncClient, ticker: str
    ) -> QualitativePackage:
        async with self._sem:
            gaps: list[str] = []

            # Fire all sources concurrently for this single ticker
            (
                news_raw,
                pr_raw,
                transcript_raw,
                sec_raw,
                actions_raw,
                insider_raw,
                estimates_raw,
                sentiment_raw,
                finnhub_news_raw,
            ) = await asyncio.gather(
                self._safe(self._fetch_news_fmp(client, ticker), "news_fmp", gaps),
                self._safe(self._fetch_press_releases(client, ticker), "press_releases", gaps),
                self._safe(self._fetch_transcript(client, ticker), "earnings_transcript", gaps),
                self._safe(self._fetch_sec_filings(client, ticker), "sec_filings", gaps),
                self._safe(self._fetch_analyst_actions(client, ticker), "analyst_actions", gaps),
                self._safe(self._fetch_insider(client, ticker), "insider_activity", gaps),
                self._safe(self._fetch_estimates(client, ticker), "analyst_estimates", gaps),
                self._safe(self._fetch_sentiment(client, ticker), "sentiment", gaps),
                self._safe(self._fetch_news_finnhub(client, ticker), "news_finnhub", gaps),
            )

            # Merge and deduplicate news from FMP + Finnhub
            merged_news = self._merge_news(ticker, news_raw or [], finnhub_news_raw or [])

            return QualitativePackage(
                ticker=ticker,
                news_items=merged_news,
                press_releases=self._parse_press_releases(ticker, pr_raw or []),
                earnings_transcript=self._parse_transcript(ticker, transcript_raw),
                sec_filings=self._parse_sec_filings(ticker, sec_raw or []),
                analyst_actions=self._parse_analyst_actions(ticker, actions_raw or []),
                insider_activity=self._parse_insider(ticker, insider_raw or []),
                analyst_estimates=self._parse_estimates(ticker, estimates_raw),
                sentiment=self._parse_sentiment(ticker, sentiment_raw),
                coverage_gaps=gaps,
            )

    @staticmethod
    async def _safe(coro, source_name: str, gaps: list[str]) -> Any:
        """Await a coroutine; on any exception record gap and return None."""
        try:
            return await coro
        except Exception as exc:
            gaps.append(source_name)
            logger.debug("Qualitative source '%s' failed: %s", source_name, exc)
            return None

    # ── FMP fetch helpers ──────────────────────────────────────────────

    async def _fetch_news_fmp(self, client: httpx.AsyncClient, ticker: str) -> list:
        r = await client.get(
            f"{self.FMP_BASE}/stock_news",
            params={"symbol": ticker, "limit": 20, "apikey": self.fmp_key},
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []

    async def _fetch_press_releases(self, client: httpx.AsyncClient, ticker: str) -> list:
        r = await client.get(
            f"{self.FMP_BASE}/press-releases/{ticker}",
            params={"limit": 10, "apikey": self.fmp_key},
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []

    async def _fetch_transcript(self, client: httpx.AsyncClient, ticker: str) -> Any:
        r = await client.get(
            f"{self.FMP_BASE}/earning_call_transcript/{ticker}",
            params={"limit": 1, "apikey": self.fmp_key},
        )
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list) and data:
            return data[0]
        return None

    async def _fetch_sec_filings(self, client: httpx.AsyncClient, ticker: str) -> list:
        r = await client.get(
            f"{self.FMP_BASE}/sec_filings/{ticker}",
            params={"limit": 15, "apikey": self.fmp_key},
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []

    async def _fetch_analyst_actions(self, client: httpx.AsyncClient, ticker: str) -> list:
        r = await client.get(
            f"{self.FMP_BASE}/analyst-stock-recommendations/{ticker}",
            params={"limit": 15, "apikey": self.fmp_key},
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []

    async def _fetch_insider(self, client: httpx.AsyncClient, ticker: str) -> list:
        r = await client.get(
            f"{self.FMP_BASE}/insider-trading/{ticker}",
            params={"limit": 20, "apikey": self.fmp_key},
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []

    async def _fetch_estimates(self, client: httpx.AsyncClient, ticker: str) -> Any:
        r = await client.get(
            f"{self.FMP_BASE}/analyst-estimates/{ticker}",
            params={"limit": 4, "apikey": self.fmp_key},
        )
        r.raise_for_status()
        return r.json()

    async def _fetch_sentiment(self, client: httpx.AsyncClient, ticker: str) -> Any:
        r = await client.get(
            f"{self.FMP_BASE}/stock_news_sentiments_rss_feed",
            params={"symbol": ticker, "limit": 10, "apikey": self.fmp_key},
        )
        r.raise_for_status()
        return r.json()

    # ── Finnhub fetch helpers ─────────────────────────────────────────

    async def _fetch_news_finnhub(self, client: httpx.AsyncClient, ticker: str) -> list:
        from datetime import date, timedelta
        today = date.today()
        from_date = (today - timedelta(days=30)).isoformat()
        r = await client.get(
            f"{self.FINNHUB_BASE}/company-news",
            params={"symbol": ticker, "from": from_date, "to": today.isoformat(), "token": self.finnhub_key},
        )
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []

    # ── Parsers ────────────────────────────────────────────────────────

    def _merge_news(
        self, ticker: str, fmp_items: list, finnhub_items: list
    ) -> list[NewsItem]:
        seen: set[str] = set()
        merged: list[NewsItem] = []

        def _add(headline: str, summary: str, source: str, pub_date: Any,
                 url: str = "", sentiment_score: Optional[float] = None) -> None:
            h = _headline_hash(headline)
            if h in seen:
                return
            seen.add(h)
            sl: Optional[SentimentLabel] = None
            if sentiment_score is not None:
                sl = (SentimentLabel.BULLISH if sentiment_score > 0.1
                      else SentimentLabel.BEARISH if sentiment_score < -0.1
                      else SentimentLabel.NEUTRAL)
            merged.append(NewsItem(
                ticker=ticker,
                headline=headline,
                summary=summary,
                published_at=_parse_date(pub_date),
                source=source,
                url=url,
                sentiment_label=sl,
                sentiment_score=sentiment_score,
            ))

        for item in (fmp_items or []):
            if isinstance(item, dict):
                _add(
                    headline=item.get("title", ""),
                    summary=item.get("text", item.get("summary", ""))[:500],
                    source="FMP",
                    pub_date=item.get("publishedDate", item.get("date")),
                    url=item.get("url", ""),
                    sentiment_score=item.get("sentiment"),
                )
        for item in (finnhub_items or []):
            if isinstance(item, dict):
                _add(
                    headline=item.get("headline", ""),
                    summary=item.get("summary", "")[:500],
                    source="Finnhub",
                    pub_date=item.get("datetime"),
                    url=item.get("url", ""),
                )
        return merged[:25]  # cap at 25 items for prompt budget

    def _parse_press_releases(self, ticker: str, raw: list) -> list[PressRelease]:
        items: list[PressRelease] = []
        for item in (raw or []):
            if not isinstance(item, dict):
                continue
            items.append(PressRelease(
                ticker=ticker,
                title=item.get("title", ""),
                date=_parse_date(item.get("date")),
                text=item.get("text", "")[:1000],
                source_url=item.get("url", ""),
            ))
        return items[:10]

    def _parse_transcript(self, ticker: str, raw: Any) -> Optional[EarningsTranscript]:
        if not raw or not isinstance(raw, dict):
            return None
        content = raw.get("content", "") or ""
        if not content:
            return None
        return EarningsTranscript(
            ticker=ticker,
            quarter=str(raw.get("quarter", "")),
            year=int(raw.get("year", 0) or 0),
            date=_parse_date(raw.get("date")),
            content=content[:8000],
            management_commentary=content[:3000],  # first 3k chars as commentary proxy
        )

    def _parse_sec_filings(self, ticker: str, raw: list) -> list[SECFiling]:
        filings: list[SECFiling] = []
        for item in (raw or []):
            if not isinstance(item, dict):
                continue
            filing_type = item.get("type", item.get("formType", ""))
            filings.append(SECFiling(
                ticker=ticker,
                filing_type=filing_type,
                filed_date=_parse_date(item.get("filledDate", item.get("filedAt", item.get("date")))),
                period_of_report=str(item.get("periodOfReport", "")),
                filing_url=item.get("link", item.get("linkToFilingDetails", "")),
                description=item.get("description", "")[:200],
                is_material=filing_type in ("8-K", "10-K", "10-Q"),
            ))
        return filings[:15]

    def _parse_analyst_actions(self, ticker: str, raw: list) -> list[AnalystAction]:
        actions: list[AnalystAction] = []
        for item in (raw or []):
            if not isinstance(item, dict):
                continue
            actions.append(AnalystAction(
                ticker=ticker,
                firm=item.get("analystFirm", item.get("gradeCompany", item.get("firm", ""))),
                action=item.get("action", item.get("analystChange", "")),
                previous_grade=item.get("previousGrade", item.get("previousRating", "")),
                new_grade=item.get("newGrade", item.get("currentRating", "")),
                action_date=_parse_date(item.get("gradingDate", item.get("date"))),
                price_target=float(item["priceTarget"]) if item.get("priceTarget") else None,
            ))
        return actions[:15]

    def _parse_insider(self, ticker: str, raw: list) -> InsiderActivitySummary:
        transactions: list[InsiderTransaction] = []
        total_bought = 0.0
        total_sold = 0.0

        for item in (raw or []):
            if not isinstance(item, dict):
                continue
            raw_dir = item.get("acquistionOrDisposition", item.get("transactionType", ""))
            if raw_dir in ("A", "P", "Buy"):
                direction = InsiderDirection.BUY
            elif raw_dir in ("D", "S", "Sale"):
                direction = InsiderDirection.SELL
            else:
                direction = InsiderDirection.OTHER

            shares = float(item.get("securitiesTransacted", item.get("shares", 0)) or 0)
            price = float(item.get("price", 0) or 0)
            value = float(item.get("value", shares * price) or 0)

            if direction == InsiderDirection.BUY:
                total_bought += value
            elif direction == InsiderDirection.SELL:
                total_sold += value

            transactions.append(InsiderTransaction(
                ticker=ticker,
                reporter_name=item.get("reportingName", item.get("name", "")),
                role=item.get("typeOfOwner", item.get("title", "")),
                direction=direction,
                shares=shares,
                price_per_share=price,
                total_value=value,
                transaction_date=_parse_date(item.get("transactionDate", item.get("date"))),
                filing_date=_parse_date(item.get("filingDate")),
            ))

        return InsiderActivitySummary(
            ticker=ticker,
            transactions=transactions[:20],
            total_bought_usd=total_bought,
            total_sold_usd=total_sold,
        )

    def _parse_estimates(self, ticker: str, raw: Any) -> Optional[AnalystEstimates]:
        if not raw:
            return None
        items = raw if isinstance(raw, list) else []
        if not items:
            return None

        def _period(label: str, item: dict) -> EstimatePeriod:
            return EstimatePeriod(
                period_label=label,
                fiscal_period=str(item.get("period", item.get("date", ""))),
                estimated_revenue_avg=float(item["estimatedRevenueAvg"]) if item.get("estimatedRevenueAvg") else None,
                estimated_revenue_low=float(item["estimatedRevenueLow"]) if item.get("estimatedRevenueLow") else None,
                estimated_revenue_high=float(item["estimatedRevenueHigh"]) if item.get("estimatedRevenueHigh") else None,
                estimated_eps_avg=float(item["estimatedEpsAvg"]) if item.get("estimatedEpsAvg") else None,
                estimated_eps_low=float(item["estimatedEpsLow"]) if item.get("estimatedEpsLow") else None,
                estimated_eps_high=float(item["estimatedEpsHigh"]) if item.get("estimatedEpsHigh") else None,
                num_analysts_revenue=int(item.get("numberAnalystsEstimatedRevenue", 0) or 0),
                num_analysts_eps=int(item.get("numberAnalystsEstimatedEps", 0) or 0),
            )

        ests = AnalystEstimates(ticker=ticker)
        if len(items) >= 1:
            ests.current_quarter = _period("current_quarter", items[0])
        if len(items) >= 2:
            ests.current_year = _period("current_year", items[1])
        if len(items) >= 3:
            ests.next_year = _period("next_year", items[2])
        return ests

    def _parse_sentiment(self, ticker: str, raw: Any) -> Optional[SentimentSignals]:
        if not raw:
            return None
        items = raw if isinstance(raw, list) else [raw]
        scores = [float(i["sentiment"]) for i in items
                  if isinstance(i, dict) and i.get("sentiment") is not None]
        if not scores:
            return None
        avg_score = sum(scores) / len(scores)
        return SentimentSignals(
            ticker=ticker,
            news_sentiment_score=round(avg_score, 4),
        )

    # ── E-10: FinBERT / NLP Sentiment ────────────────────────────────────

    def get_sentiment(self, ticker: str, headlines: list[str] | None = None) -> "SentimentPacket":  # type: ignore[name-defined]
        """E-10: Score headlines for a ticker using FinBERT or keyword fallback.

        Args:
            ticker: Company ticker
            headlines: List of news headlines to score. If None, uses any
                       cached news headlines from a prior ingest.

        Returns a SentimentPacket with aggregated signal.
        """
        from research_pipeline.schemas.qualitative import SentimentLabel, SentimentPacket

        if not headlines:
            headlines = []

        scores: list[float] = []
        method = "keyword_fallback"

        # Try FinBERT if transformers is installed
        try:
            from transformers import pipeline as _hf_pipeline  # type: ignore[import]
            finbert = _hf_pipeline(
                "text-classification",
                model="ProsusAI/finbert",
                tokenizer="ProsusAI/finbert",
                device=-1,  # CPU
                top_k=None,
            )
            for hl in headlines[:20]:  # limit for speed
                try:
                    res = finbert(hl[:512])
                    # res is list of [{'label': 'positive/negative/neutral', 'score': float}]
                    if res:
                        for item in (res[0] if isinstance(res[0], list) else res):
                            if isinstance(item, dict):
                                lbl = item.get("label", "").lower()
                                scr = float(item.get("score", 0))
                                if lbl == "positive":
                                    scores.append(scr)
                                elif lbl == "negative":
                                    scores.append(-scr)
                                break
                except Exception:
                    pass
            method = "finbert"
        except (ImportError, Exception):
            # Keyword fallback
            _POSITIVE = {
                "beat", "beats", "strong", "growth", "profit", "record", "raised",
                "upgrade", "buy", "outperform", "exceeded", "positive", "demand",
                "AI", "artificial intelligence", "revenue", "gain",
            }
            _NEGATIVE = {
                "miss", "misses", "weak", "loss", "cut", "downgrade", "sell",
                "underperform", "fell", "declined", "disappoints", "below", "risk",
                "recall", "lawsuit", "investigation",
            }
            for hl in headlines:
                hl_lower = hl.lower()
                pos_hits = sum(1 for w in _POSITIVE if w.lower() in hl_lower)
                neg_hits = sum(1 for w in _NEGATIVE if w.lower() in hl_lower)
                if pos_hits > neg_hits:
                    scores.append(0.6)
                elif neg_hits > pos_hits:
                    scores.append(-0.6)
                else:
                    scores.append(0.0)

        # Aggregate
        if scores:
            avg_score = sum(scores) / len(scores)
        else:
            avg_score = 0.0

        if avg_score >= 0.2:
            signal = SentimentLabel.BULLISH
        elif avg_score <= -0.2:
            signal = SentimentLabel.BEARISH
        else:
            signal = SentimentLabel.NEUTRAL

        pos_count = sum(1 for s in scores if s > 0.1)
        neg_count = sum(1 for s in scores if s < -0.1)
        neu_count = len(scores) - pos_count - neg_count

        return SentimentPacket(
            ticker=ticker,
            score=round(avg_score, 4),
            signal=signal,
            headlines=headlines[:20],
            headline_scores=[round(s, 4) for s in scores[:20]],
            n_headlines=len(headlines),
            positive_count=pos_count,
            negative_count=neg_count,
            neutral_count=neu_count,
            method=method,
            data_source="qualitative_data_service",
        )
