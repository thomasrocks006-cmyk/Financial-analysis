"""Qualitative intelligence schemas — typed models for all 8 qualitative data sources.

These schemas establish the backend data contract for qualitative data collected
from FMP and Finnhub. Each model corresponds to one source category. All models
are Pydantic v2 for runtime validation and serialisation integrity.

Source hierarchy (for evidence tier classification):
  Tier 1 — SEC filings (8-K, 10-K, 10-Q)
  Tier 2 — Earnings transcripts (direct management commentary)
  Tier 3 — Analyst actions, press releases, insider filings
  Tier 4 — News aggregation, social sentiment
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Tier classification ──────────────────────────────────────────────────

class QualSourceTier(int, Enum):
    SEC_FILING = 1          # Primary regulatory document
    EARNINGS_TRANSCRIPT = 2 # Direct management commentary
    ANALYST_ACTION = 3      # Third-party analyst commentary
    PRESS_RELEASE = 3       # Company-issued comms (not SEC)
    NEWS_AGGREGATED = 4     # Aggregated news / sentiment


class InsiderDirection(str, Enum):
    BUY = "buy"
    SELL = "sell"
    OTHER = "other"


class SentimentLabel(str, Enum):
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"


# ── E-10: FinBERT / NLP Sentiment Packet ─────────────────────────────────

class SentimentPacket(BaseModel):
    """E-10: Aggregated NLP sentiment for a single ticker.

    Produced by QualitativeDataService.get_sentiment() from news headlines
    scored by FinBERT or a keyword fallback.
    """
    ticker: str
    score: float = 0.0            # [-1.0 (bearish) to +1.0 (bullish)]
    signal: SentimentLabel = SentimentLabel.NEUTRAL
    headlines: list[str] = Field(default_factory=list)
    headline_scores: list[float] = Field(default_factory=list)
    n_headlines: int = 0
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    method: str = "keyword_fallback"   # "finbert" or "keyword_fallback"
    data_source: str = ""              # e.g. "finnhub", "newsapi", "synthetic"


class CoverageDepth(str, Enum):
    DEEP = "deep"       # ≥15 signals, ≤1 gap
    MODERATE = "moderate"  # ≥8 signals, ≤3 gaps
    THIN = "thin"       # ≥3 signals
    MINIMAL = "minimal" # <3 signals


# ── Source 1 & 2: News and Press Releases ────────────────────────────────

class NewsItem(BaseModel):
    """A single news item from FMP or Finnhub (deduplicated by headline hash)."""
    ticker: str
    headline: str
    summary: str = ""
    published_at: Optional[datetime] = None
    source: str = ""                  # e.g. "FMP", "Finnhub"
    url: str = ""
    sentiment_label: Optional[SentimentLabel] = None
    sentiment_score: Optional[float] = None  # [-1.0, 1.0]
    source_tier: int = QualSourceTier.NEWS_AGGREGATED.value

    @property
    def is_recent(self) -> bool:
        """True if published within the last 30 days."""
        if not self.published_at:
            return False
        now = datetime.now(timezone.utc)
        delta = now - (self.published_at if self.published_at.tzinfo else
                       self.published_at.replace(tzinfo=timezone.utc))
        return delta.days <= 30


class PressRelease(BaseModel):
    """Official company press release (not an SEC regulatory filing)."""
    ticker: str
    title: str
    date: Optional[datetime] = None
    text: str = ""
    source_url: str = ""
    source_tier: int = QualSourceTier.PRESS_RELEASE.value


# ── Source 3: Earnings Transcripts ────────────────────────────────────────

class EarningsTranscript(BaseModel):
    """Most recent earnings call transcript — highest value qualitative source."""
    ticker: str
    quarter: str = ""    # e.g. "Q3"
    year: int = 0
    date: Optional[datetime] = None
    content: str = ""                         # Full or partial transcript text
    management_commentary: str = ""           # Extracted guidance/commentary
    key_guidance_phrases: list[str] = Field(default_factory=list)
    source_tier: int = QualSourceTier.EARNINGS_TRANSCRIPT.value

    @property
    def has_content(self) -> bool:
        return bool(self.content or self.management_commentary)


# ── Source 4: SEC Filings ────────────────────────────────────────────────

class SECFiling(BaseModel):
    """SEC filing entry (8-K, 10-K, 10-Q, 4, SC 13G etc.)."""
    ticker: str
    filing_type: str          # "8-K", "10-K", "10-Q", "4"
    filed_date: Optional[datetime] = None
    period_of_report: str = ""
    filing_url: str = ""
    description: str = ""
    is_material: bool = False  # True if 8-K or other market-moving type
    source_tier: int = QualSourceTier.SEC_FILING.value

    @property
    def is_primary_document(self) -> bool:
        return self.filing_type in ("10-K", "10-Q", "8-K")


# ── Source 5: Analyst Actions ────────────────────────────────────────────

class AnalystAction(BaseModel):
    """Single analyst upgrade/downgrade or initiation."""
    ticker: str
    firm: str
    action: str = ""         # "upgrade", "downgrade", "initiation", "reiteration"
    previous_grade: str = ""
    new_grade: str = ""
    action_date: Optional[datetime] = None
    price_target: Optional[float] = None
    source_tier: int = QualSourceTier.ANALYST_ACTION.value

    @property
    def is_positive_action(self) -> bool:
        return self.action.lower() in ("upgrade", "initiation")

    @property
    def is_negative_action(self) -> bool:
        return self.action.lower() == "downgrade"


# ── Source 6: Insider Transactions ───────────────────────────────────────

class InsiderTransaction(BaseModel):
    """Single insider buy or sell transaction (SEC Form 4)."""
    ticker: str
    reporter_name: str = ""
    role: str = ""              # CEO, CFO, Director, 10% Owner etc.
    direction: InsiderDirection = InsiderDirection.OTHER
    shares: float = 0.0
    price_per_share: float = 0.0
    total_value: float = 0.0
    transaction_date: Optional[datetime] = None
    filing_date: Optional[datetime] = None
    source_tier: int = QualSourceTier.SEC_FILING.value  # Form 4 is a regulatory filing


class InsiderActivitySummary(BaseModel):
    """Aggregated insider activity summary for a ticker."""
    ticker: str
    transactions: list[InsiderTransaction] = Field(default_factory=list)
    total_bought_usd: float = 0.0
    total_sold_usd: float = 0.0

    @property
    def net_usd(self) -> float:
        return self.total_bought_usd - self.total_sold_usd

    @property
    def net_direction(self) -> InsiderDirection:
        if self.net_usd > 0:
            return InsiderDirection.BUY
        if self.net_usd < 0:
            return InsiderDirection.SELL
        return InsiderDirection.OTHER


# ── Source 7: Analyst Estimates ──────────────────────────────────────────

class EstimatePeriod(BaseModel):
    """Forward consensus estimates for a single forecast period."""
    period_label: str          # "current_quarter", "current_year", "next_year"
    fiscal_period: str = ""    # e.g. "2026Q1"
    estimated_revenue_avg: Optional[float] = None
    estimated_revenue_low: Optional[float] = None
    estimated_revenue_high: Optional[float] = None
    estimated_eps_avg: Optional[float] = None
    estimated_eps_low: Optional[float] = None
    estimated_eps_high: Optional[float] = None
    num_analysts_revenue: int = 0
    num_analysts_eps: int = 0

    @property
    def revenue_spread_pct(self) -> Optional[float]:
        if (self.estimated_revenue_low and self.estimated_revenue_high
                and self.estimated_revenue_low > 0):
            return (self.estimated_revenue_high - self.estimated_revenue_low) / self.estimated_revenue_low * 100
        return None


class AnalystEstimates(BaseModel):
    """All forward consensus estimates for a ticker."""
    ticker: str
    current_quarter: Optional[EstimatePeriod] = None
    current_year: Optional[EstimatePeriod] = None
    next_year: Optional[EstimatePeriod] = None

    @property
    def has_estimates(self) -> bool:
        return any([self.current_quarter, self.current_year, self.next_year])


# ── Source 8: Sentiment Signals ──────────────────────────────────────────

class SentimentSignals(BaseModel):
    """Aggregated social and news sentiment for a ticker."""
    ticker: str
    news_sentiment_score: Optional[float] = None   # [-1.0, 1.0]
    stocktwits_sentiment_score: Optional[float] = None
    stocktwits_posts: int = 0
    reddit_sentiment_score: Optional[float] = None
    reddit_mentions: int = 0

    @property
    def composite_sentiment_label(self) -> SentimentLabel:
        scores = [s for s in [
            self.news_sentiment_score,
            self.stocktwits_sentiment_score,
            self.reddit_sentiment_score,
        ] if s is not None]
        if not scores:
            return SentimentLabel.NEUTRAL
        avg = sum(scores) / len(scores)
        if avg > 0.15:
            return SentimentLabel.BULLISH
        if avg < -0.15:
            return SentimentLabel.BEARISH
        return SentimentLabel.NEUTRAL


# ── Full Qualitative Package ─────────────────────────────────────────────

class QualitativePackage(BaseModel):
    """Complete qualitative intelligence package for a single ticker.

    This is the canonical backend data contract — analogous to MarketSnapshot
    in market_data.py. All downstream agents receive this type.
    """
    ticker: str
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    news_items: list[NewsItem] = Field(default_factory=list)
    press_releases: list[PressRelease] = Field(default_factory=list)
    earnings_transcript: Optional[EarningsTranscript] = None
    sec_filings: list[SECFiling] = Field(default_factory=list)
    analyst_actions: list[AnalystAction] = Field(default_factory=list)
    insider_activity: InsiderActivitySummary = Field(
        default_factory=lambda: InsiderActivitySummary(ticker="")
    )
    analyst_estimates: Optional[AnalystEstimates] = None
    sentiment: Optional[SentimentSignals] = None
    coverage_gaps: list[str] = Field(default_factory=list)   # names of sources that failed

    @property
    def signal_count(self) -> int:
        return (
            len(self.news_items)
            + len(self.press_releases)
            + (1 if self.earnings_transcript and self.earnings_transcript.has_content else 0)
            + len(self.sec_filings)
            + len(self.analyst_actions)
            + len(self.insider_activity.transactions)
            + (1 if self.analyst_estimates and self.analyst_estimates.has_estimates else 0)
            + (1 if self.sentiment else 0)
        )

    @property
    def coverage_depth(self) -> CoverageDepth:
        count = self.signal_count
        gaps = len(self.coverage_gaps)
        if count >= 15 and gaps <= 1:
            return CoverageDepth.DEEP
        if count >= 8 and gaps <= 3:
            return CoverageDepth.MODERATE
        if count >= 3:
            return CoverageDepth.THIN
        return CoverageDepth.MINIMAL

    @property
    def tier1_sources_present(self) -> bool:
        """True if at least one Tier 1 source (SEC filing) is available."""
        return bool(self.sec_filings)

    @property
    def tier2_sources_present(self) -> bool:
        """True if earnings transcript is available with content."""
        return self.earnings_transcript is not None and self.earnings_transcript.has_content

    def to_prompt_block(self) -> str:
        """Render qualitative package as a structured text block for LLM ingestion."""
        sections: list[str] = [f"═══ QUALITATIVE INTELLIGENCE: {self.ticker} ═══"]
        sections.append(f"Coverage depth: {self.coverage_depth.value.upper()} "
                        f"| Signal count: {self.signal_count} "
                        f"| Tier 1 (SEC): {'YES' if self.tier1_sources_present else 'NO'} "
                        f"| Tier 2 (transcript): {'YES' if self.tier2_sources_present else 'NO'}")

        # SEC filings (highest tier)
        if self.sec_filings:
            material = [f for f in self.sec_filings if f.is_primary_document]
            sections.append(f"\n### SEC Filings ({len(self.sec_filings)} total, {len(material)} primary)")
            for f in self.sec_filings[:6]:
                date_str = f.filed_date.strftime("%Y-%m-%d") if f.filed_date else "N/A"
                sections.append(f"  - {f.filing_type} filed {date_str}: {f.description or f.filing_url}")
        else:
            sections.append("\n### SEC Filings: NONE — coverage gap (Tier 1)")

        # Earnings transcript
        if self.earnings_transcript and self.earnings_transcript.has_content:
            et = self.earnings_transcript
            date_str = et.date.strftime("%Y-%m-%d") if et.date else "N/A"
            sections.append(f"\n### Earnings Transcript — {et.quarter} {et.year} ({date_str})")
            if et.management_commentary:
                sections.append(f"Management commentary:\n{et.management_commentary[:2000]}")
            elif et.content:
                sections.append(f"Transcript excerpt:\n{et.content[:2000]}")
        else:
            sections.append("\n### Earnings Transcript: NOT AVAILABLE — coverage gap (Tier 2)")

        # News
        if self.news_items:
            sections.append(f"\n### Recent News ({len(self.news_items)} items)")
            for item in self.news_items[:10]:
                date_str = item.published_at.strftime("%Y-%m-%d") if item.published_at else "N/A"
                sent = f" [{item.sentiment_label.value}]" if item.sentiment_label else ""
                sections.append(f"  - [{date_str}]{sent} {item.headline} — {item.summary[:200]}")
        else:
            sections.append("\n### News: NONE AVAILABLE")

        # Analyst actions
        if self.analyst_actions:
            sections.append(f"\n### Analyst Actions ({len(self.analyst_actions)} actions)")
            for a in self.analyst_actions[:8]:
                date_str = a.action_date.strftime("%Y-%m-%d") if a.action_date else "N/A"
                pt_str = f" PT: ${a.price_target:.0f}" if a.price_target else ""
                sections.append(
                    f"  - {a.firm}: {a.action} {a.previous_grade} → {a.new_grade}"
                    f"{pt_str} ({date_str})"
                )

        # Insider activity
        if self.insider_activity.transactions:
            ia = self.insider_activity
            net_dir = ia.net_direction.value.upper()
            sections.append(
                f"\n### Insider Activity ({len(ia.transactions)} transactions, "
                f"net {net_dir}: ${ia.net_usd:+,.0f})"
            )
            for tx in ia.transactions[:8]:
                date_str = tx.transaction_date.strftime("%Y-%m-%d") if tx.transaction_date else "N/A"
                sections.append(
                    f"  - {tx.direction.value.upper()}: {tx.reporter_name} ({tx.role}) "
                    f"{tx.shares:,.0f} shares @ ${tx.price_per_share:.2f} ({date_str})"
                )

        # Estimates
        if self.analyst_estimates and self.analyst_estimates.has_estimates:
            sections.append("\n### Forward Analyst Estimates")
            for period in [
                self.analyst_estimates.current_quarter,
                self.analyst_estimates.current_year,
                self.analyst_estimates.next_year,
            ]:
                if period:
                    rev = f"${period.estimated_revenue_avg/1e9:.2f}B" if period.estimated_revenue_avg else "N/A"
                    eps = f"${period.estimated_eps_avg:.2f}" if period.estimated_eps_avg else "N/A"
                    sections.append(f"  - {period.period_label}: Rev {rev}, EPS {eps} "
                                    f"({period.num_analysts_revenue} analysts)")

        # Sentiment
        if self.sentiment:
            s = self.sentiment
            label = s.composite_sentiment_label.value.upper()
            sections.append(f"\n### Sentiment: {label}")
            if s.news_sentiment_score is not None:
                sections.append(f"  - News score: {s.news_sentiment_score:+.2f}")
            if s.stocktwits_sentiment_score is not None:
                sections.append(f"  - StockTwits: {s.stocktwits_sentiment_score:+.2f} "
                                 f"({s.stocktwits_posts} posts)")

        # Coverage gaps
        if self.coverage_gaps:
            sections.append(f"\n⚠ Coverage gaps: {', '.join(self.coverage_gaps)}")

        return "\n".join(sections)
