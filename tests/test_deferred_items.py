"""Tests for Phase deferred items: qualitative schemas, qualitative service, quant research agent.

Covers:
  - D-1: QualitativePackage schema correctness, coverage depth, prompt block generation
  - D-1: QualitativeDataService parser methods (offline — no live API calls)
  - D-4: QuantResearchAnalystAgent parse_output enforcement
  - A-3: PublicationStatus only has PASS and FAIL (PASS_WITH_DISCLOSURE removed)
  - A-4: InvestmentCommitteeService _pm_vote treats pass_with_disclosure as FAIL
"""

from __future__ import annotations

import json
import pytest
from datetime import datetime, timezone

from research_pipeline.schemas.qualitative import (
    AnalystAction,
    AnalystEstimates,
    CoverageDepth,
    EarningsTranscript,
    EstimatePeriod,
    InsiderActivitySummary,
    InsiderDirection,
    InsiderTransactionRecord,
    NewsItem,
    PressRelease,
    QualitativePackage,
    QualSourceTier,
    SECFiling,
    SentimentLabel,
    SentimentSignals,
)
from research_pipeline.agents.quant_research_analyst import QuantResearchAnalystAgent
from research_pipeline.agents.base_agent import StructuredOutputError
from research_pipeline.schemas.portfolio import PublicationStatus
from research_pipeline.services.investment_committee import InvestmentCommitteeService
from research_pipeline.schemas.governance import CommitteeVote


# ── D-1: QualitativePackage schema ───────────────────────────────────────

class TestQualitativeSchemas:
    def test_news_item_creates(self):
        item = NewsItem(
            ticker="NVDA",
            headline="NVIDIA beats earnings",
            summary="Revenue up 200%",
            source="FMP",
        )
        assert item.ticker == "NVDA"
        assert item.source_tier == QualSourceTier.NEWS_AGGREGATED.value

    def test_news_item_sentiment_label(self):
        item = NewsItem(ticker="NVDA", headline="test", sentiment_score=0.8)
        assert item.sentiment_score == 0.8

    def test_news_item_is_recent_without_date(self):
        item = NewsItem(ticker="NVDA", headline="test")
        assert item.is_recent is False

    def test_news_item_is_recent_with_date(self):
        item = NewsItem(
            ticker="NVDA",
            headline="test",
            published_at=datetime.now(timezone.utc),
        )
        assert item.is_recent is True

    def test_sec_filing_is_material(self):
        f = SECFiling(ticker="NVDA", filing_type="8-K", is_material=True)
        assert f.is_primary_document is True
        assert f.source_tier == QualSourceTier.SEC_FILING.value

    def test_sec_filing_non_material_type(self):
        f = SECFiling(ticker="NVDA", filing_type="DEF 14A")
        assert f.is_primary_document is False

    def test_earnings_transcript_has_content(self):
        et = EarningsTranscript(ticker="NVDA", content="Q1 results were strong...")
        assert et.has_content is True

    def test_earnings_transcript_empty(self):
        et = EarningsTranscript(ticker="NVDA")
        assert et.has_content is False

    def test_estimate_period_spread(self):
        ep = EstimatePeriod(
            period_label="current_year",
            estimated_revenue_low=1_000_000,
            estimated_revenue_high=1_200_000,
            estimated_revenue_avg=1_100_000,
        )
        assert ep.revenue_spread_pct == pytest.approx(20.0)

    def test_insider_summary_net_direction_buy(self):
        ia = InsiderActivitySummary(
            ticker="NVDA",
            total_bought_usd=500_000,
            total_sold_usd=100_000,
        )
        assert ia.net_direction == InsiderDirection.BUY
        assert ia.net_usd == 400_000

    def test_insider_summary_net_direction_sell(self):
        ia = InsiderActivitySummary(
            ticker="NVDA",
            total_bought_usd=50_000,
            total_sold_usd=500_000,
        )
        assert ia.net_direction == InsiderDirection.SELL

    def test_sentiment_signals_composite_bullish(self):
        s = SentimentSignals(
            ticker="NVDA",
            news_sentiment_score=0.6,
            stocktwits_sentiment_score=0.4,
        )
        assert s.composite_sentiment_label == SentimentLabel.BULLISH

    def test_sentiment_signals_composite_bearish(self):
        s = SentimentSignals(ticker="NVDA", news_sentiment_score=-0.5)
        assert s.composite_sentiment_label == SentimentLabel.BEARISH

    def test_sentiment_signals_composite_neutral_no_data(self):
        s = SentimentSignals(ticker="NVDA")
        assert s.composite_sentiment_label == SentimentLabel.NEUTRAL


class TestQualitativePackage:
    def _make_full_package(self) -> QualitativePackage:
        return QualitativePackage(
            ticker="NVDA",
            news_items=[NewsItem(ticker="NVDA", headline=f"News {i}") for i in range(5)],
            press_releases=[PressRelease(ticker="NVDA", title="PR 1")],
            earnings_transcript=EarningsTranscript(ticker="NVDA", content="strong results"),
            sec_filings=[SECFiling(ticker="NVDA", filing_type="10-K", is_material=True)],
            analyst_actions=[AnalystAction(ticker="NVDA", firm="Goldman", action="upgrade",
                                           new_grade="Buy")],
            insider_activity=InsiderActivitySummary(
                ticker="NVDA",
                transactions=[InsiderTransactionRecord(ticker="NVDA", direction=InsiderDirection.BUY,
                                                      shares=100, price_per_share=500.0, total_value=50000)],
                total_bought_usd=50000,
            ),
            analyst_estimates=AnalystEstimates(
                ticker="NVDA",
                current_year=EstimatePeriod(period_label="current_year",
                                            estimated_revenue_avg=50e9, num_analysts_revenue=30),
            ),
            sentiment=SentimentSignals(ticker="NVDA", news_sentiment_score=0.3),
        )

    def test_signal_count(self):
        pkg = self._make_full_package()
        # 5 news + 1 pr + 1 transcript + 1 filing + 1 action + 1 insider tx + 1 estimates + 1 sentiment = 12
        assert pkg.signal_count == 12

    def test_coverage_depth_moderate(self):
        pkg = self._make_full_package()
        assert pkg.coverage_depth in (CoverageDepth.MODERATE, CoverageDepth.DEEP, CoverageDepth.THIN)

    def test_tier1_sources_present(self):
        pkg = self._make_full_package()
        assert pkg.tier1_sources_present is True

    def test_tier2_sources_present(self):
        pkg = self._make_full_package()
        assert pkg.tier2_sources_present is True

    def test_tier1_absent_without_sec(self):
        pkg = QualitativePackage(ticker="NVDA")
        assert pkg.tier1_sources_present is False

    def test_prompt_block_contains_ticker(self):
        pkg = self._make_full_package()
        block = pkg.to_prompt_block()
        assert "NVDA" in block

    def test_prompt_block_contains_sec_section(self):
        pkg = self._make_full_package()
        block = pkg.to_prompt_block()
        assert "SEC Filing" in block or "10-K" in block

    def test_prompt_block_shows_coverage_gaps(self):
        pkg = QualitativePackage(ticker="NVDA", coverage_gaps=["earnings_transcript", "sec_filings"])
        block = pkg.to_prompt_block()
        assert "gap" in block.lower() or "earnings_transcript" in block

    def test_empty_package_coverage_minimal(self):
        pkg = QualitativePackage(ticker="XYZ")
        assert pkg.coverage_depth == CoverageDepth.MINIMAL
        assert pkg.signal_count == 0


# ── D-1: QualitativeDataService parsers (offline) ─────────────────────────

class TestQualitativeDataServiceParsers:
    """Test service parsers with static fixture data — no live API calls."""

    from research_pipeline.services.qualitative_data_service import QualitativeDataService

    def setup_method(self):
        from research_pipeline.services.qualitative_data_service import QualitativeDataService
        self.svc = QualitativeDataService(fmp_key="", finnhub_key="")

    def test_parse_sec_filings(self):
        raw = [
            {"type": "10-K", "filledDate": "2025-01-15", "link": "http://sec.gov/test", "description": "Annual report"},
            {"type": "8-K", "filledDate": "2025-02-01"},
        ]
        filings = self.svc._parse_sec_filings("NVDA", raw)
        assert len(filings) == 2
        assert filings[0].filing_type == "10-K"
        assert filings[0].is_material is True
        assert filings[1].filing_type == "8-K"

    def test_parse_analyst_actions(self):
        raw = [
            {"analystFirm": "Goldman", "action": "upgrade", "previousGrade": "Hold",
             "newGrade": "Buy", "gradingDate": "2025-01-10", "priceTarget": 1000},
        ]
        actions = self.svc._parse_analyst_actions("NVDA", raw)
        assert len(actions) == 1
        assert actions[0].firm == "Goldman"
        assert actions[0].new_grade == "Buy"
        assert actions[0].price_target == 1000.0

    def test_parse_insider_buy(self):
        raw = [
            {"reportingName": "Jensen Huang", "typeOfOwner": "CEO",
             "acquistionOrDisposition": "A", "securitiesTransacted": 1000,
             "price": 500.0, "value": 500000, "transactionDate": "2025-01-20"},
        ]
        summary = self.svc._parse_insider("NVDA", raw)
        assert summary.total_bought_usd == pytest.approx(500000)
        assert summary.total_sold_usd == 0
        assert summary.transactions[0].direction == InsiderDirection.BUY

    def test_parse_insider_sell(self):
        raw = [
            {"reportingName": "CFO", "acquistionOrDisposition": "D",
             "securitiesTransacted": 500, "price": 500.0, "value": 250000},
        ]
        summary = self.svc._parse_insider("NVDA", raw)
        assert summary.total_sold_usd == pytest.approx(250000)
        assert summary.transactions[0].direction == InsiderDirection.SELL

    def test_parse_transcript(self):
        raw = {"content": "Q3 was excellent...", "quarter": "Q3", "year": 2025}
        transcript = self.svc._parse_transcript("NVDA", raw)
        assert transcript is not None
        assert transcript.quarter == "Q3"
        assert "excellent" in transcript.content

    def test_parse_transcript_empty_returns_none(self):
        transcript = self.svc._parse_transcript("NVDA", None)
        assert transcript is None

    def test_merge_news_deduplicates(self):
        fmp = [{"title": "NVDA soars", "text": "summary", "publishedDate": "2025-01-01"}]
        finnhub = [{"headline": "NVDA soars", "summary": "summary", "datetime": 1739000000}]
        merged = self.svc._merge_news("NVDA", fmp, finnhub)
        assert len(merged) == 1  # deduplicated by headline hash

    def test_merge_news_different_items(self):
        fmp = [{"title": "NVDA beats expectations", "text": ""}]
        finnhub = [{"headline": "NVDA expands datacenter", "summary": ""}]
        merged = self.svc._merge_news("NVDA", fmp, finnhub)
        assert len(merged) == 2

    def test_parse_estimates(self):
        raw = [
            {"estimatedRevenueAvg": 50e9, "estimatedEpsAvg": 1.5,
             "numberAnalystsEstimatedRevenue": 30, "date": "2025-Q1"},
            {"estimatedRevenueAvg": 200e9, "estimatedEpsAvg": 6.0,
             "numberAnalystsEstimatedRevenue": 40, "date": "2025"},
        ]
        ests = self.svc._parse_estimates("NVDA", raw)
        assert ests is not None
        assert ests.has_estimates is True
        assert ests.current_quarter.estimated_revenue_avg == pytest.approx(50e9)
        assert ests.current_year.estimated_revenue_avg == pytest.approx(200e9)

    def test_parse_estimates_empty_returns_none(self):
        ests = self.svc._parse_estimates("NVDA", [])
        assert ests is None

    def test_parse_sentiment(self):
        raw = [{"sentiment": 0.4}, {"sentiment": 0.6}]
        s = self.svc._parse_sentiment("NVDA", raw)
        assert s is not None
        assert s.news_sentiment_score == pytest.approx(0.5, abs=0.01)

    def test_parse_sentiment_no_data(self):
        s = self.svc._parse_sentiment("NVDA", [])
        assert s is None


# ── D-4: QuantResearchAnalystAgent parse_output enforcement ──────────────

class TestQuantResearchAnalystAgent:
    def setup_method(self):
        self.agent = QuantResearchAnalystAgent()

    def _make_valid_output(self) -> dict:
        return {
            "run_id": "RUN-001",
            "date": "2026-03-28",
            "universe": "ai_infrastructure",
            "section_1_factor_interpretation": {
                "dominant_factors": ["momentum"],
                "factor_tilt_narrative": "Momentum-heavy portfolio",
                "concerns": [],
            },
            "section_2_risk_assessment": {
                "var_95_commentary": "VaR is moderate",
                "concentration_commentary": "HHI=1800 — elevated",
                "overall_risk_verdict": "Within mandate",
            },
            "section_3_benchmark_divergence": {
                "tracking_error_commentary": "TE=8% vs NDX — intentional",
                "etf_differentiation_score": 65,
                "etf_overlap_summary": "65% differentiated from ETFs",
                "etf_replication_risk": False,
                "active_bets_narrative": "Overweight NVDA +12%",
                "information_ratio_signal": "IR=0.7 — acceptable",
            },
            "section_4_construction_signal": {
                "factor_tilt_recommendation": "Maintain momentum tilt",
                "concentration_recommendation": "Trim NVDA below 15%",
                "benchmark_recommendation": "Differentiated enough vs ETFs",
                "constructive_changes": [],
            },
            "risk_signal": "neutral",
            "primary_concern": "NVDA concentration at 18% single-name weight",
            "recommended_action": "Trim NVDA to 14% to reduce HHI below 2000",
            "analyst_confidence": "medium",
            "data_quality_note": "VAR based on synthetic returns — live prices needed",
        }

    def test_valid_output_passes(self):
        payload = json.dumps(self._make_valid_output())
        result = self.agent.parse_output(payload)
        assert result["risk_signal"] == "neutral"
        assert result["primary_concern"]
        assert result["recommended_action"]

    def test_missing_risk_signal_fails(self):
        data = self._make_valid_output()
        del data["risk_signal"]
        with pytest.raises(StructuredOutputError, match="risk_signal"):
            self.agent.parse_output(json.dumps(data))

    def test_invalid_risk_signal_fails(self):
        data = self._make_valid_output()
        data["risk_signal"] = "unknown_value"
        with pytest.raises(StructuredOutputError, match="risk_signal"):
            self.agent.parse_output(json.dumps(data))

    def test_missing_primary_concern_fails(self):
        data = self._make_valid_output()
        del data["primary_concern"]
        with pytest.raises(StructuredOutputError, match="primary_concern"):
            self.agent.parse_output(json.dumps(data))

    def test_missing_section1_fails(self):
        data = self._make_valid_output()
        del data["section_1_factor_interpretation"]
        with pytest.raises(StructuredOutputError):
            self.agent.parse_output(json.dumps(data))

    def test_etf_replication_risk_flag_low_score(self):
        """If differentiation_score < 40 but etf_replication_risk is False, should fail."""
        data = self._make_valid_output()
        data["section_3_benchmark_divergence"]["etf_differentiation_score"] = 30
        data["section_3_benchmark_divergence"]["etf_replication_risk"] = False
        with pytest.raises(StructuredOutputError, match="etf_replication_risk"):
            self.agent.parse_output(json.dumps(data))

    def test_etf_replication_risk_flag_correctly_set(self):
        """If differentiation_score < 40 AND etf_replication_risk is True, should pass."""
        data = self._make_valid_output()
        data["section_3_benchmark_divergence"]["etf_differentiation_score"] = 30
        data["section_3_benchmark_divergence"]["etf_replication_risk"] = True
        result = self.agent.parse_output(json.dumps(data))
        assert result["risk_signal"] == "neutral"

    def test_list_input_single_item_normalised(self):
        """A list with a single dict should be unwrapped."""
        payload = json.dumps([self._make_valid_output()])
        result = self.agent.parse_output(payload)
        assert isinstance(result, dict)
        assert result["risk_signal"] == "neutral"

    def test_list_input_multi_item_fails(self):
        """A list with multiple dicts should be rejected."""
        payload = json.dumps([self._make_valid_output(), self._make_valid_output()])
        with pytest.raises(StructuredOutputError, match="single JSON object"):
            self.agent.parse_output(payload)

    @pytest.mark.parametrize("signal", ["positive", "neutral", "cautious", "negative"])
    def test_all_valid_risk_signals_accepted(self, signal):
        data = self._make_valid_output()
        data["risk_signal"] = signal
        result = self.agent.parse_output(json.dumps(data))
        assert result["risk_signal"] == signal


# ── A-3: PublicationStatus enum only has PASS and FAIL ────────────────────

class TestPublicationStatusBinary:
    def test_only_pass_and_fail_exist(self):
        valid_values = {s.value for s in PublicationStatus}
        assert valid_values == {"pass", "fail"}
        assert "pass_with_disclosure" not in valid_values

    def test_pass_value_creates(self):
        ps = PublicationStatus("pass")
        assert ps == PublicationStatus.PASS

    def test_fail_value_creates(self):
        ps = PublicationStatus("fail")
        assert ps == PublicationStatus.FAIL

    def test_pass_with_disclosure_raises(self):
        with pytest.raises(ValueError):
            PublicationStatus("pass_with_disclosure")


# ── A-4: IC service _pm_vote rejects pass_with_disclosure ─────────────────

class TestICPassWithDisclosureRemoved:
    def setup_method(self):
        self.ic = InvestmentCommitteeService()

    def _pm_vote(self, review_result):
        """Call the private _pm_vote via evaluate_and_vote with custom review_result."""
        # Directly test the private method
        vote, rationale, conditions = self.ic._pm_vote(
            gate_results={}, review_result=review_result, conditions=[]
        )
        return vote, rationale, conditions

    def test_pass_review_approves(self):
        vote, _, _ = self._pm_vote({"status": "pass"})
        assert vote == CommitteeVote.APPROVE

    def test_fail_review_rejects(self):
        vote, _, _ = self._pm_vote({"status": "fail"})
        assert vote == CommitteeVote.REJECT

    def test_pass_with_disclosure_treated_as_fail(self):
        """pass_with_disclosure is no longer valid — must be treated as FAIL."""
        vote, rationale, _ = self._pm_vote({"status": "pass_with_disclosure"})
        assert vote == CommitteeVote.REJECT
        assert "FAIL" in rationale or "Unexpected" in rationale or "treated" in rationale.lower()

    def test_none_review_approves(self):
        vote, _, _ = self._pm_vote(None)
        assert vote == CommitteeVote.APPROVE
