"""
Session 20 tests — new services, schema extensions, and engine wiring.
"""
import asyncio
import pytest

# ── Service tests ─────────────────────────────────────────────────────────────


class TestArticleExtractionService:
    def test_clean_text_strips_html(self):
        from research_pipeline.services.article_extraction_service import _clean_text
        result = _clean_text("<p>Hello <b>world</b></p>")
        assert "<" not in result
        assert "Hello" in result

    def test_extract_from_text(self):
        from research_pipeline.services.article_extraction_service import ArticleExtractionService
        svc = ArticleExtractionService()
        art = svc.extract_from_text("https://example.com/news", "Title", "Some body text here that is long enough to pass filter checks")
        assert art.url == "https://example.com/news"
        assert len(art.url_hash) == 16
        assert art.word_count > 0

    def test_truncate_for_prompt(self):
        from research_pipeline.services.article_extraction_service import ExtractedArticle
        art = ExtractedArticle.from_url(
            "https://example.com", "t", " ".join(["word"] * 500)
        )
        truncated = art.truncate_for_prompt(max_words=10)
        assert "[truncated]" in truncated
        assert len(truncated.split()) <= 12

    def test_deduplicate(self):
        from research_pipeline.services.article_extraction_service import ArticleExtractionService, ExtractedArticle
        svc = ArticleExtractionService()
        art1 = ExtractedArticle.from_url("https://example.com/a", "T1", "text here")
        art2 = ExtractedArticle.from_url("https://example.com/a", "T2", "text here")
        art3 = ExtractedArticle.from_url("https://example.com/b", "T3", "text here")
        result = svc.deduplicate([art1, art2, art3])
        assert len(result) == 2


class TestNewsApiService:
    def test_no_key_returns_empty(self):
        from research_pipeline.services.news_api_service import NewsApiService
        svc = NewsApiService(api_key="")
        assert not svc._is_key_available()
        result = asyncio.run(svc.get_policy_news())
        assert result == []

    def test_is_allowed_source(self):
        from research_pipeline.services.news_api_service import NewsApiService
        svc = NewsApiService(api_key="dummy")
        assert svc._is_allowed_source("https://reuters.com/article", "Reuters")
        assert not svc._is_allowed_source("https://yahoo.com/article", "Yahoo Finance")

    def test_format_for_prompt_empty(self):
        from research_pipeline.services.news_api_service import NewsApiService
        svc = NewsApiService(api_key="")
        assert "No macro" in svc.format_for_prompt([])

    def test_format_for_prompt(self):
        from research_pipeline.services.news_api_service import NewsApiService, NewsArticle
        svc = NewsApiService(api_key="")
        articles = [
            NewsArticle(
                title="Chip export controls tighten",
                source="Reuters",
                url="https://reuters.com/1",
                url_hash="abc123",
                published_at="2025-01-15T10:00:00Z",
                is_allowlisted=True,
            )
        ]
        text = svc.format_for_prompt(articles)
        assert "Reuters" in text
        assert "Chip export" in text


class TestDataFreshnessService:
    def test_register_and_retrieve(self):
        from research_pipeline.services.data_freshness_service import DataFreshnessCatalog, FreshnessTier
        catalog = DataFreshnessCatalog(run_id="test-run")
        ff = catalog.register("eps_fwd", "NVDA", "fmp")
        assert ff.ticker == "NVDA"
        assert ff.source_service == "fmp"
        assert ff.freshness_tier == FreshnessTier.LIVE
        assert "eps_fwd" in catalog.fields

    def test_stale_summary_empty(self):
        from research_pipeline.services.data_freshness_service import DataFreshnessCatalog
        catalog = DataFreshnessCatalog(run_id="test-run")
        assert "fresh" in catalog.get_stale_summary().lower()

    def test_stale_summary_with_stale(self):
        from research_pipeline.services.data_freshness_service import DataFreshnessCatalog
        catalog = DataFreshnessCatalog(run_id="test-run", stale_fields=["eps_fwd"])
        summary = catalog.get_stale_summary()
        assert "STALE" in summary

    def test_to_audit_list(self):
        from research_pipeline.services.data_freshness_service import DataFreshnessCatalog
        catalog = DataFreshnessCatalog(
            run_id="r", stale_fields=["a"], expired_fields=["b"]
        )
        lst = catalog.to_audit_list()
        assert "a" in lst and "b" in lst


class TestRateLimitManager:
    def test_check_quota_allows_unknown(self):
        from research_pipeline.services.rate_limit_manager import RateLimitBudgetManager
        mgr = RateLimitBudgetManager()
        assert mgr.check_quota("unknown_service") is True

    def test_check_quota_exhaustion(self):
        from research_pipeline.services.rate_limit_manager import RateLimitBudgetManager
        mgr = RateLimitBudgetManager()
        mgr._services["news_api"].current_day_usage = 100
        assert mgr.check_quota("news_api") is False

    def test_record_usage(self):
        from research_pipeline.services.rate_limit_manager import RateLimitBudgetManager
        mgr = RateLimitBudgetManager()
        mgr.record_usage("fmp", 5)
        assert mgr._services["fmp"].current_day_usage == 5

    def test_get_fallback(self):
        from research_pipeline.services.rate_limit_manager import RateLimitBudgetManager
        mgr = RateLimitBudgetManager()
        assert mgr.get_fallback("fmp") == "finnhub"
        assert mgr.get_fallback("news_api") is None

    def test_reset_daily(self):
        from research_pipeline.services.rate_limit_manager import RateLimitBudgetManager
        mgr = RateLimitBudgetManager()
        mgr.record_usage("fmp", 100)
        mgr.reset_daily()
        assert mgr._services["fmp"].current_day_usage == 0
        assert not mgr._services["fmp"].exhausted

    def test_budget_summary(self):
        from research_pipeline.services.rate_limit_manager import RateLimitBudgetManager
        mgr = RateLimitBudgetManager()
        summary = mgr.get_budget_summary()
        assert "fmp" in summary
        assert "news_api" in summary


class TestSourceRankingService:
    def test_trust_score_known(self):
        from research_pipeline.services.source_ranking_service import SourceRankingService
        svc = SourceRankingService()
        assert svc.get_trust_score("reuters.com") == 0.95
        assert svc.get_trust_score("yahoo.com") == 0.30

    def test_trust_score_unknown(self):
        from research_pipeline.services.source_ranking_service import SourceRankingService
        svc = SourceRankingService()
        assert svc.get_trust_score("unknown-blog.xyz") == 0.5

    def test_hash_url(self):
        from research_pipeline.services.source_ranking_service import SourceRankingService
        svc = SourceRankingService()
        h = svc.hash_url("https://reuters.com/article")
        assert len(h) == 16
        # Normalisation: same URL different case
        assert svc.hash_url("https://Reuters.com/article") == h

    def test_rank_and_deduplicate(self):
        from research_pipeline.services.source_ranking_service import SourceRankingService
        svc = SourceRankingService()
        sources = [
            {"url": "https://yahoo.com/a", "source": "yahoo.com", "title": "T1"},
            {"url": "https://reuters.com/a", "source": "reuters.com", "title": "T2"},
            {"url": "https://ft.com/a", "source": "ft.com", "title": "T3"},
        ]
        ranked = svc.rank_and_deduplicate(sources)
        # reuters should rank first
        assert ranked[0].source_domain == "reuters.com"

    def test_dedup_filters_seen(self):
        from research_pipeline.services.source_ranking_service import SourceRankingService
        svc = SourceRankingService()
        sources = [
            {"url": "https://reuters.com/same", "source": "reuters.com", "title": "T1"},
            {"url": "https://reuters.com/same", "source": "reuters.com", "title": "T2"},
        ]
        ranked = svc.rank_and_deduplicate(sources)
        assert len(ranked) == 1


class TestEIAService:
    def test_no_key_returns_defaults(self):
        from research_pipeline.services.eia_service import EIAService
        svc = EIAService(api_key="")
        result = asyncio.run(svc.get_power_prices())
        assert len(result) == 1
        assert result[0].price_cents_kwh == 12.5

    def test_generation_capacity_defaults(self):
        from research_pipeline.services.eia_service import EIAService
        svc = EIAService(api_key="")
        result = asyncio.run(svc.get_generation_capacity())
        assert result.total_gw == 1200.0
        assert result.data_source == "eia_api"

    def test_datacenter_forecast(self):
        from research_pipeline.services.eia_service import EIAService
        svc = EIAService(api_key="")
        result = asyncio.run(svc.get_datacenter_power_demand_forecast())
        assert result.forecast_year == 2030
        assert result.datacenter_share_pct > 0


class TestFERCService:
    def test_queue_summary_defaults(self):
        from research_pipeline.services.ferc_service import FERCService
        svc = FERCService()
        # _get_synthetic_defaults always returns valid data
        defaults = svc._get_synthetic_defaults()
        assert defaults.total_pending_gw == 2600.0
        assert "PJM" in defaults.by_region

    def test_load_queue_by_region(self):
        from research_pipeline.services.ferc_service import FERCService
        svc = FERCService()
        # Use synthetic defaults directly
        summary = svc._get_synthetic_defaults()
        assert len(summary.by_region) >= 4
        assert summary.by_region["MISO"].load_mw_requested > 0


class TestASXAnnouncementService:
    def test_normalize_ticker(self):
        from research_pipeline.services.asx_announcement_service import ASXAnnouncementService
        svc = ASXAnnouncementService()
        assert svc._normalize_ticker("BHP.AX") == "BHP"
        assert svc._normalize_ticker("CBA") == "CBA"

    def test_is_asx_ticker(self):
        from research_pipeline.services.asx_announcement_service import _is_asx_ticker
        assert _is_asx_ticker("BHP.AX")
        assert _is_asx_ticker("CBA")
        assert not _is_asx_ticker("NVDA")

    def test_parse_empty_data(self):
        from research_pipeline.services.asx_announcement_service import ASXAnnouncementService
        svc = ASXAnnouncementService()
        result = svc._parse_announcements("BHP", {"data": []}, 30)
        assert result == []

    def test_announcement_to_prompt_line(self):
        from research_pipeline.services.asx_announcement_service import ASXAnnouncement
        ann = ASXAnnouncement(
            ticker="BHP", document_date="2025-01-15T00:00:00", headline="Annual Report",
            category="Annual Report to shareholders", is_periodic=True,
        )
        line = ann.to_prompt_line()
        assert "PERIODIC" in line
        assert "BHP" in line


class TestWSTSService:
    def test_latest_shipment_data(self):
        from research_pipeline.services.wsts_service import WSTSService
        svc = WSTSService()
        result = asyncio.run(svc.get_latest_shipment_data())
        assert result.total_market_usd_billions > 0
        assert result.memory_yoy_growth_pct > 0

    def test_book_to_bill(self):
        from research_pipeline.services.wsts_service import WSTSService
        svc = WSTSService()
        result = asyncio.run(svc.get_equipment_book_to_bill())
        assert result.ratio > 1.0
        assert result.signal == "expanding"

    def test_format_for_prompt(self):
        from research_pipeline.services.wsts_service import WSTSService
        svc = WSTSService()
        snapshot = asyncio.run(svc.get_latest_shipment_data())
        btb = asyncio.run(svc.get_equipment_book_to_bill())
        text = svc.format_for_prompt(snapshot, btb)
        assert "Semiconductor" in text
        assert "EXPANDING" in text


class TestHyperscalerCapexTracker:
    def test_get_latest_snapshot(self):
        from research_pipeline.services.hyperscaler_capex_tracker import HyperscalerCapexTracker
        tracker = HyperscalerCapexTracker()
        result = asyncio.run(tracker.get_latest_capex_snapshot())
        assert "MSFT" in result
        assert "AMZN" in result
        assert result["MSFT"].capex_reported_usd_billions > 0

    def test_format_for_prompt(self):
        from research_pipeline.services.hyperscaler_capex_tracker import HyperscalerCapexTracker
        tracker = HyperscalerCapexTracker()
        data = asyncio.run(tracker.get_latest_capex_snapshot())
        text = tracker.format_for_prompt(data)
        assert "MSFT" in text
        assert "annualized" in text

    def test_to_prompt_line(self):
        from research_pipeline.services.hyperscaler_capex_tracker import HyperscalerCapexData
        item = HyperscalerCapexData(
            hyperscaler="META", quarter="2024-Q4",
            capex_reported_usd_billions=14.8, capex_yoy_growth_pct=66.0,
            capex_guidance_next_q="$60-65B FY2025",
        )
        line = item.to_prompt_line()
        assert "META" in line
        assert "Guidance" in line


class TestIRScraperService:
    def test_hash_url(self):
        from research_pipeline.services.ir_scraper_service import IRScraperService
        svc = IRScraperService()
        h = svc._hash_url("https://example.com/news")
        assert len(h) == 16

    def test_is_material(self):
        from research_pipeline.services.ir_scraper_service import IRScraperService
        svc = IRScraperService()
        assert svc._is_material("NVIDIA Reports Q4 Earnings Beat")
        assert svc._is_material("Company Announces CEO Change")
        assert not svc._is_material("Random Company Update About Nothing Special")

    def test_no_feed_returns_empty(self):
        from research_pipeline.services.ir_scraper_service import IRScraperService
        svc = IRScraperService()
        result = asyncio.run(svc.get_latest_announcements("UNKNOWN_TICKER_XYZ"))
        assert result == []

    def test_parse_rss_empty(self):
        from research_pipeline.services.ir_scraper_service import IRScraperService
        svc = IRScraperService()
        result = svc._parse_rss("NVDA", "<rss></rss>", 7)
        assert result == []


class TestTranscriptParserService:
    def test_parse_empty(self):
        from research_pipeline.services.transcript_parser_service import TranscriptParserService
        svc = TranscriptParserService()
        result = asyncio.run(svc.parse("NVDA", "Q4-2024", ""))
        assert result.ticker == "NVDA"
        assert result.parse_confidence == 0.0
        assert result.guidance_statements == []

    def test_parse_with_guidance(self):
        from research_pipeline.services.transcript_parser_service import TranscriptParserService
        svc = TranscriptParserService()
        text = "We expect revenue growth of 20% next quarter. Guidance for EPS remains strong. Strong demand pipeline and robust backlog."
        result = asyncio.run(svc.parse("NVDA", "Q4-2024", text))
        assert result.ticker == "NVDA"
        assert result.raw_word_count > 0
        assert result.parse_confidence > 0

    def test_tone_detection_positive(self):
        from research_pipeline.services.transcript_parser_service import TranscriptParserService
        svc = TranscriptParserService()
        text = "strong strong strong growing accelerating robust beat outperform exceeding results this quarter"
        result = asyncio.run(svc.parse("AMD", "Q1-2025", text))
        tone_topics = {s.topic: s.tone for s in result.tone_signals}
        assert tone_topics.get("overall") == "positive"

    def test_cache_hit(self):
        from research_pipeline.services.transcript_parser_service import TranscriptParserService
        svc = TranscriptParserService()
        text = "We expect revenue to grow significantly this year driven by strong demand."
        r1 = asyncio.run(svc.parse("MSFT", "Q3-2025", text))
        r2 = asyncio.run(svc.parse("MSFT", "Q3-2025", text))
        assert r1 is r2  # same object from cache


# ── Schema tests ──────────────────────────────────────────────────────────────


class TestDSQ25QualitativeSchemas:
    def test_guidance_statement(self):
        from research_pipeline.schemas.qualitative import GuidanceStatement
        gs = GuidanceStatement(raw_text="We expect EPS of $5.00 next quarter")
        assert gs.category == "other"
        assert gs.confidence == "implied"

    def test_management_tone_signal(self):
        from research_pipeline.schemas.qualitative import ManagementToneSignal
        sig = ManagementToneSignal(topic="demand", tone="positive", evidence_quote="strong demand")
        assert sig.tone == "positive"

    def test_guidance_revision_delta(self):
        from research_pipeline.schemas.qualitative import GuidanceRevisionDelta
        delta = GuidanceRevisionDelta(
            ticker="NVDA", current_quarter="Q4-2024", prior_quarter="Q3-2024",
            direction="raise", categories_revised=["revenue", "eps"],
        )
        assert delta.direction == "raise"
        assert "revenue" in delta.categories_revised

    def test_parsed_transcript(self):
        from research_pipeline.schemas.qualitative import ParsedTranscript, GuidanceStatement, ManagementToneSignal
        pt = ParsedTranscript(
            ticker="NVDA", quarter="Q4-2024",
            guidance_statements=[GuidanceStatement(raw_text="revenue guide up", confidence="explicit")],
            tone_signals=[ManagementToneSignal(topic="overall", tone="positive")],
            raw_word_count=500,
            parse_confidence=0.8,
        )
        assert pt.ticker == "NVDA"
        assert len(pt.guidance_statements) == 1
        assert pt.parse_confidence == 0.8


class TestDSQ27MacroSchemas:
    def test_regulatory_event(self):
        from research_pipeline.schemas.macro import RegulatoryEvent
        evt = RegulatoryEvent(
            event_type="export_control",
            jurisdiction="US",
            headline="New chip export restrictions announced",
            affected_tickers=["NVDA", "AMD"],
            is_adverse=True,
            severity="material",
        )
        line = evt.to_prompt_line()
        assert "EXPORT_CONTROL" in line
        assert "MATERIAL" in line
        assert "US" in line

    def test_regulatory_event_packet_build(self):
        from research_pipeline.schemas.macro import RegulatoryEvent, RegulatoryEventPacket
        events = [
            RegulatoryEvent(event_type="export_control", jurisdiction="US",
                            headline="Chip ban extended", affected_tickers=["NVDA"],
                            is_adverse=True, severity="critical"),
            RegulatoryEvent(event_type="ai_regulation", jurisdiction="EU",
                            headline="AI Act enforcement begins", affected_tickers=[],
                            is_adverse=False, severity="watch"),
        ]
        packet = RegulatoryEventPacket.build("run-1", events, ["NVDA", "AMD"])
        assert len(packet.events) == 2
        assert len(packet.most_adverse) >= 1
        assert packet.most_adverse[0].severity == "critical"
        assert "NVDA" in packet.affected_ticker_map

    def test_macro_power_grid_packet(self):
        from research_pipeline.schemas.macro import MacroPowerGridPacket
        pkt = MacroPowerGridPacket(
            run_id="run-1",
            commercial_electricity_price_cents_kwh=12.5,
            total_generation_capacity_gw=1200.0,
            datacenter_demand_forecast_twh_2030=324.0,
            top_congested_regions=["PJM", "MISO"],
        )
        summary = pkt.to_prompt_summary()
        assert "12.5" in summary
        assert "1200" in summary
        assert "324" in summary


class TestRiskPacketDSQ14:
    def test_new_fields_defaults(self):
        from research_pipeline.schemas.reports import RiskPacket
        pkt = RiskPacket(run_id="test-run")
        assert pkt.returns_data_source == "synthetic"
        assert pkt.synthetic_tickers == []
        assert pkt.data_quality_warning == ""

    def test_new_fields_set(self):
        from research_pipeline.schemas.reports import RiskPacket
        pkt = RiskPacket(
            run_id="test-run",
            returns_data_source="mixed",
            synthetic_tickers=["SMCI", "VRT"],
            data_quality_warning="2 tickers use synthetic returns",
        )
        assert pkt.returns_data_source == "mixed"
        assert "SMCI" in pkt.synthetic_tickers
        assert "synthetic" in pkt.data_quality_warning

    def test_serialisation(self):
        from research_pipeline.schemas.reports import RiskPacket
        pkt = RiskPacket(run_id="r", returns_data_source="live", synthetic_tickers=[])
        d = pkt.model_dump()
        assert d["returns_data_source"] == "live"
        assert d["synthetic_tickers"] == []


class TestSelfAuditPacketDSQ14:
    def test_new_fields_defaults(self):
        from research_pipeline.schemas.governance import SelfAuditPacket
        pkt = SelfAuditPacket(run_id="test-run")
        assert pkt.synthetic_data_fields == []
        assert pkt.data_quality_flags == {}

    def test_new_fields_set(self):
        from research_pipeline.schemas.governance import SelfAuditPacket
        pkt = SelfAuditPacket(
            run_id="test-run",
            synthetic_data_fields=["returns:SMCI", "returns:VRT"],
            data_quality_flags={"SMCI": "synthetic_returns", "VRT": "synthetic_returns"},
        )
        assert "returns:SMCI" in pkt.synthetic_data_fields
        assert pkt.data_quality_flags["SMCI"] == "synthetic_returns"


class TestSettingsNewsApiKey:
    def test_news_api_key_default(self):
        from research_pipeline.config.settings import APIKeys
        keys = APIKeys()
        assert hasattr(keys, "news_api_key")
        assert keys.news_api_key == ""

    def test_news_api_key_from_env(self, monkeypatch):
        import os
        monkeypatch.setenv("NEWS_API_KEY", "test-key-123")
        from research_pipeline.config.settings import APIKeys
        keys = APIKeys.from_env()
        assert keys.news_api_key == "test-key-123"


class TestGetReturnsWithMetadata:
    """Unit tests for the new _get_returns_with_metadata helper."""

    def _make_engine(self):
        """Build a minimal PipelineEngine for unit testing."""
        from research_pipeline.config.settings import Settings
        from research_pipeline.config.loader import load_pipeline_config
        settings = Settings()
        config = load_pipeline_config()
        from research_pipeline.pipeline.engine import PipelineEngine
        return PipelineEngine(settings=settings, config=config)

    def test_all_synthetic_when_no_live(self):
        engine = self._make_engine()
        # Patch live_return_store to return nothing
        class EmptyStore:
            def fetch(self, tickers):
                return {}
        engine.live_return_store = EmptyStore()
        tickers = ["NVDA", "AMD"]
        returns, synthetic = engine._get_returns_with_metadata(tickers)
        assert set(returns.keys()) == set(tickers)
        assert set(synthetic) == set(tickers)

    def test_all_live_when_available(self):
        engine = self._make_engine()
        fake_returns = {"NVDA": [0.01] * 10, "AMD": [0.02] * 10}
        class FullStore:
            def fetch(self, tickers):
                return {t: fake_returns[t] for t in tickers if t in fake_returns}
        engine.live_return_store = FullStore()
        tickers = ["NVDA", "AMD"]
        returns, synthetic = engine._get_returns_with_metadata(tickers)
        assert set(returns.keys()) == set(tickers)
        assert synthetic == []

    def test_mixed_returns(self):
        engine = self._make_engine()
        class PartialStore:
            def fetch(self, tickers):
                return {"NVDA": [0.01] * 10}
        engine.live_return_store = PartialStore()
        tickers = ["NVDA", "AMD"]
        returns, synthetic = engine._get_returns_with_metadata(tickers)
        assert set(returns.keys()) == set(tickers)
        assert "AMD" in synthetic
        assert "NVDA" not in synthetic
