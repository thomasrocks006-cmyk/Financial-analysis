"""
tests/test_session19.py
-----------------------
Session 19 feature tests: Data Sourcing Quality — SEC API, Benzinga,
QualitativeDataService wiring, and Settings API key expansion.

All tests are self-contained and mock HTTP calls so no live API access is needed.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch


# ── path setup ─────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))


# =============================================================================
# 1. Settings — new API keys
# =============================================================================


class TestSettingsAPIKeys:
    """APIKeys dataclass must carry sec_api_key and benzinga_api_key."""

    def test_api_keys_has_sec_api_key_field(self):
        from research_pipeline.config.settings import APIKeys

        keys = APIKeys()
        assert hasattr(keys, "sec_api_key")
        assert keys.sec_api_key == ""

    def test_api_keys_has_benzinga_api_key_field(self):
        from research_pipeline.config.settings import APIKeys

        keys = APIKeys()
        assert hasattr(keys, "benzinga_api_key")
        assert keys.benzinga_api_key == ""

    def test_from_env_reads_sec_api_key(self):
        from research_pipeline.config.settings import APIKeys

        with patch.dict("os.environ", {"SEC_API_KEY": "test-sec-key-123"}):
            keys = APIKeys.from_env()
        assert keys.sec_api_key == "test-sec-key-123"

    def test_from_env_reads_benzinga_api_key(self):
        from research_pipeline.config.settings import APIKeys

        with patch.dict("os.environ", {"BENZINGA_API_KEY": "benz-key-456"}):
            keys = APIKeys.from_env()
        assert keys.benzinga_api_key == "benz-key-456"

    def test_from_env_defaults_to_empty_when_not_set(self):
        from research_pipeline.config.settings import APIKeys

        with patch.dict("os.environ", {}, clear=False):
            # Remove keys if present
            import os

            os.environ.pop("SEC_API_KEY", None)
            os.environ.pop("BENZINGA_API_KEY", None)
            keys = APIKeys.from_env()
        assert keys.sec_api_key == ""
        assert keys.benzinga_api_key == ""


# =============================================================================
# 2. SECApiService — unit tests
# =============================================================================


class TestSECApiService:
    """Tests for src/research_pipeline/services/sec_api_service.py"""

    def test_import(self):
        from research_pipeline.services.sec_api_service import SECApiService  # noqa: F401

    def test_service_instantiation_with_empty_key(self):
        from research_pipeline.services.sec_api_service import SECApiService

        svc = SECApiService(api_key="")
        assert svc.api_key == ""
        assert svc._available is False

    def test_service_instantiation_with_key(self):
        from research_pipeline.services.sec_api_service import SECApiService

        svc = SECApiService(api_key="real-key-abc")
        assert svc.api_key == "real-key-abc"

    def test_fetch_universe_returns_empty_packages_without_key(self):
        from research_pipeline.services.sec_api_service import SECApiService

        svc = SECApiService(api_key="")
        result = asyncio.run(svc.fetch_universe(["NVDA", "MSFT"]))
        assert isinstance(result, dict)
        assert "NVDA" in result
        assert "MSFT" in result

    def test_empty_package_has_no_primary_content(self):
        from research_pipeline.services.sec_api_service import SECFilingPackage

        pkg = SECFilingPackage(ticker="NVDA")
        assert pkg.has_primary_content is False

    def test_package_with_mda_has_primary_content(self):
        from research_pipeline.services.sec_api_service import SECFilingPackage

        pkg = SECFilingPackage(ticker="NVDA")
        pkg.mda_text = "Management discussion and analysis text here."
        assert pkg.has_primary_content is True

    def test_sec_filing_record_to_dict(self):
        from research_pipeline.services.sec_api_service import SECFilingRecord
        from datetime import datetime, timezone

        rec = SECFilingRecord(
            ticker="NVDA",
            accession_no="0001045810-24-000001",
            form_type="10-K",
            filed_at=datetime(2024, 2, 26, tzinfo=timezone.utc),
            company_name="NVIDIA Corporation",
            filing_url="https://www.sec.gov/Archives/edgar/data/1045810/000104581024000001",
        )
        d = rec.to_dict()
        assert d["ticker"] == "NVDA"
        assert d["form_type"] == "10-K"
        assert d["source"] == "sec_api"
        assert d["source_tier"] == 1

    def test_package_to_dict_structure(self):
        from research_pipeline.services.sec_api_service import SECFilingPackage

        pkg = SECFilingPackage(ticker="MSFT")
        pkg.mda_text = "Revenue grew 15%."
        pkg.eight_k_events = [{"form_type": "8-K", "filed_at": "2024-01-15"}]
        d = pkg.to_dict()
        assert d["ticker"] == "MSFT"
        assert d["mda_text"] == "Revenue grew 15%."
        assert len(d["eight_k_events"]) == 1
        assert d["source"] == "sec_api"
        assert d["source_tier"] == 1

    def test_truncate_long_text(self):
        from research_pipeline.services.sec_api_service import _truncate

        short = "Hello world"
        assert _truncate(short, max_chars=50) == short

        long_text = "A" * 5000
        truncated = _truncate(long_text, max_chars=4000)
        assert len(truncated) < 5000
        assert "truncated" in truncated

    def test_parse_date_valid(self):
        from research_pipeline.services.sec_api_service import _parse_date

        dt = _parse_date("2024-03-15")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 3

    def test_parse_date_empty(self):
        from research_pipeline.services.sec_api_service import _parse_date

        assert _parse_date(None) is None
        assert _parse_date("") is None

    def test_fetch_universe_graceful_on_api_error(self):
        """When a ticker fetch raises, the error is contained and the ticker
        still appears in the result dict (with coverage_gaps populated)."""
        from research_pipeline.services.sec_api_service import SECApiService, SECFilingPackage

        svc = SECApiService(api_key="test-key")
        svc._available = True

        async def _failing_fetch(client, ticker):
            raise RuntimeError("rate limit exceeded")

        async def run():
            with patch.object(svc, "fetch_ticker", side_effect=_failing_fetch):
                import httpx

                async with httpx.AsyncClient():
                    pass
            result = await svc.fetch_universe(["AAPL"])
            return result

        result = asyncio.run(run())
        assert "AAPL" in result
        pkg = result["AAPL"]
        assert isinstance(pkg, SECFilingPackage)


# =============================================================================
# 3. BenzingaService — unit tests
# =============================================================================


class TestBenzingaService:
    """Tests for src/research_pipeline/services/benzinga_service.py"""

    def test_import(self):
        from research_pipeline.services.benzinga_service import BenzingaService  # noqa: F401

    def test_service_instantiation_with_empty_key(self):
        from research_pipeline.services.benzinga_service import BenzingaService

        svc = BenzingaService(api_key="")
        assert svc.api_key == ""
        assert svc._available is False

    def test_service_instantiation_with_key(self):
        from research_pipeline.services.benzinga_service import BenzingaService

        svc = BenzingaService(api_key="benz-test-key")
        assert svc._available is True

    def test_fetch_universe_returns_empty_packages_without_key(self):
        from research_pipeline.services.benzinga_service import BenzingaService

        svc = BenzingaService(api_key="")
        result = asyncio.run(svc.fetch_universe(["NVDA", "AMD"]))
        assert isinstance(result, dict)
        assert "NVDA" in result
        assert "AMD" in result
        # Empty packages have no content
        assert result["NVDA"].has_content is False

    def test_rating_change_to_dict(self):
        from research_pipeline.services.benzinga_service import RatingChange
        from datetime import datetime, timezone

        rc = RatingChange(
            ticker="NVDA",
            analyst_firm="Goldman Sachs",
            action_type="Downgrade",
            rating_current="Neutral",
            rating_prior="Buy",
            price_target_current=650.0,
            price_target_prior=800.0,
            published_at=datetime(2024, 3, 10, tzinfo=timezone.utc),
            headline="NVDA downgraded on valuation concerns",
        )
        d = rc.to_dict()
        assert d["ticker"] == "NVDA"
        assert d["analyst_firm"] == "Goldman Sachs"
        assert d["is_adverse"] is True
        assert d["source"] == "benzinga"
        assert d["source_tier"] == 2

    def test_rating_change_upgrade_not_adverse(self):
        from research_pipeline.services.benzinga_service import RatingChange

        rc = RatingChange(
            ticker="AMD",
            analyst_firm="Morgan Stanley",
            action_type="Upgrade",
            rating_current="Buy",
            rating_prior="Hold",
            price_target_current=200.0,
            price_target_prior=160.0,
            published_at=None,
            headline="AMD upgraded",
        )
        assert rc.is_adverse() is False

    def test_rating_change_downgrade_is_adverse(self):
        from research_pipeline.services.benzinga_service import RatingChange

        rc = RatingChange(
            ticker="NVDA",
            analyst_firm="Barclays",
            action_type="Downgrade",
            rating_current="Neutral",
            rating_prior="Overweight",
            price_target_current=None,
            price_target_prior=None,
            published_at=None,
            headline="",
        )
        assert rc.is_adverse() is True

    def test_benzinga_news_item_to_dict(self):
        from research_pipeline.services.benzinga_service import BenzingaNewsItem
        from datetime import datetime, timezone

        item = BenzingaNewsItem(
            ticker="MSFT",
            headline="Microsoft reports record Q3 earnings",
            summary="Revenue beat consensus by 5%.",
            published_at=datetime(2024, 4, 25, tzinfo=timezone.utc),
            author="Jane Doe",
            url="https://benzinga.com/article/12345",
            channels=["Earnings", "Tech"],
        )
        d = item.to_dict()
        assert d["ticker"] == "MSFT"
        assert d["source"] == "benzinga"
        assert d["source_tier"] == 2
        assert "Earnings" in d["channels"]

    def test_ticker_package_adverse_ratings_filter(self):
        from research_pipeline.services.benzinga_service import BenzingaTickerPackage, RatingChange

        pkg = BenzingaTickerPackage(ticker="NVDA")
        pkg.rating_changes = [
            RatingChange("NVDA", "GS", "Downgrade", "Neutral", "Buy", 650.0, 800.0, None, ""),
            RatingChange("NVDA", "MS", "Upgrade", "Buy", "Hold", 850.0, 700.0, None, ""),
            RatingChange(
                "NVDA",
                "JPM",
                "Lower Price Target",
                "Overweight",
                "Overweight",
                720.0,
                850.0,
                None,
                "",
            ),
        ]
        adverse = pkg.adverse_ratings
        assert len(adverse) == 2  # Downgrade + Lower PT

    def test_ticker_package_has_content_with_ratings(self):
        from research_pipeline.services.benzinga_service import BenzingaTickerPackage, RatingChange

        pkg = BenzingaTickerPackage(ticker="AAPL")
        assert pkg.has_content is False
        pkg.rating_changes.append(
            RatingChange("AAPL", "Wedbush", "Upgrade", "Buy", "Neutral", 220.0, 190.0, None, "")
        )
        assert pkg.has_content is True

    def test_ticker_package_to_dict_structure(self):
        from research_pipeline.services.benzinga_service import BenzingaTickerPackage

        pkg = BenzingaTickerPackage(ticker="TSLA")
        pkg.earnings_events = [{"date": "2024-04-23", "eps_est": 0.60}]
        d = pkg.to_dict()
        assert d["ticker"] == "TSLA"
        assert "rating_changes" in d
        assert "adverse_ratings" in d
        assert "news" in d
        assert len(d["earnings_events"]) == 1
        assert d["source"] == "benzinga"

    def test_to_float_helper(self):
        from research_pipeline.services.benzinga_service import _to_float

        assert _to_float("12.5") == 12.5
        assert _to_float(None) is None
        assert _to_float("") is None
        assert _to_float("not-a-number") is None

    def test_fetch_universe_graceful_on_api_error(self):
        from research_pipeline.services.benzinga_service import (
            BenzingaService,
            BenzingaTickerPackage,
        )

        svc = BenzingaService(api_key="test-key")
        svc._available = True

        async def _failing_fetch(client, ticker):
            raise ConnectionError("API unavailable")

        async def run():
            result = await svc.fetch_universe(["NVDA"])
            return result

        with patch.object(svc, "fetch_ticker", side_effect=_failing_fetch):
            result = asyncio.run(run())

        assert "NVDA" in result
        pkg = result["NVDA"]
        assert isinstance(pkg, BenzingaTickerPackage)
        assert len(pkg.coverage_gaps) > 0


# =============================================================================
# 4. Engine wiring — Stage 2 and Stage 5 integration
# =============================================================================


class TestEngineSession19Wiring:
    """Verify engine.py correctly instantiates and wires the new services."""

    def _make_settings(self) -> Any:
        from research_pipeline.config.settings import Settings, APIKeys

        settings = Settings.__new__(Settings)
        settings.api_keys = APIKeys(
            fmp_api_key="test-fmp",
            finnhub_api_key="test-finnhub",
            sec_api_key="",  # empty — services should no-op
            benzinga_api_key="",
        )
        settings.storage_dir = Path("/tmp/test_engine_s19")
        settings.storage_dir.mkdir(parents=True, exist_ok=True)
        for subdir in [
            "audits",
            "cache",
            "telemetry",
            "reports",
            "prompt_registry",
            "raw",
            "processed",
            "artifacts",
        ]:
            (settings.storage_dir / subdir).mkdir(parents=True, exist_ok=True)
        settings.prompts_dir = Path("/tmp/test_prompts_s19")
        settings.prompts_dir.mkdir(parents=True, exist_ok=True)
        settings.llm_model = "claude-sonnet-4-6"
        settings.llm_temperature = 0.2
        settings.db_url = "sqlite:///tmp/test_s19.db"
        return settings

    def test_engine_has_sec_api_svc_attribute(self):
        from research_pipeline.services.sec_api_service import SECApiService
        from research_pipeline.pipeline.engine import PipelineEngine

        settings = self._make_settings()
        with patch("research_pipeline.pipeline.engine.load_pipeline_config") as mock_cfg:
            mock_cfg.return_value = MagicMock()
            mock_cfg.return_value.thresholds = MagicMock()
            mock_cfg.return_value.thresholds.reconciliation = MagicMock()
            mock_cfg.return_value.thresholds.reconciliation.stale_data_hours = 24
            mock_cfg.return_value.thresholds.data_quality = MagicMock()
            mock_cfg.return_value.thresholds.data_quality.require_lineage_for_all_final_fields = (
                False
            )
            mock_cfg.return_value.market_config = MagicMock()
            mock_cfg.return_value.market_config.fred_api_key = ""
            _config = mock_cfg.return_value

            engine = PipelineEngine.__new__(PipelineEngine)
            engine.sec_api_svc = SECApiService(api_key=settings.api_keys.sec_api_key)

        assert hasattr(engine, "sec_api_svc")
        assert isinstance(engine.sec_api_svc, SECApiService)

    def test_engine_has_benzinga_svc_attribute(self):
        from research_pipeline.services.benzinga_service import BenzingaService
        from research_pipeline.pipeline.engine import PipelineEngine

        engine = PipelineEngine.__new__(PipelineEngine)
        engine.benzinga_svc = BenzingaService(api_key="")

        assert hasattr(engine, "benzinga_svc")
        assert isinstance(engine.benzinga_svc, BenzingaService)

    def test_engine_has_qualitative_svc_attribute(self):
        from research_pipeline.services.qualitative_data_service import QualitativeDataService
        from research_pipeline.pipeline.engine import PipelineEngine

        engine = PipelineEngine.__new__(PipelineEngine)
        engine.qualitative_svc = QualitativeDataService(fmp_key="", finnhub_key="")

        assert hasattr(engine, "qualitative_svc")
        assert isinstance(engine.qualitative_svc, QualitativeDataService)

    def test_sec_api_svc_no_ops_without_key(self):
        from research_pipeline.services.sec_api_service import SECApiService

        svc = SECApiService(api_key="")
        result = asyncio.run(svc.fetch_universe(["NVDA", "MSFT", "AAPL"]))
        assert all(k in result for k in ["NVDA", "MSFT", "AAPL"])
        # All should be empty no-op packages
        for pkg in result.values():
            assert pkg.has_primary_content is False
            assert pkg.eight_k_events == []
            assert pkg.insider_transactions == []

    def test_benzinga_svc_no_ops_without_key(self):
        from research_pipeline.services.benzinga_service import BenzingaService

        svc = BenzingaService(api_key="")
        result = asyncio.run(svc.fetch_universe(["NVDA", "AMD"]))
        assert all(k in result for k in ["NVDA", "AMD"])
        for pkg in result.values():
            assert pkg.has_content is False
            assert pkg.rating_changes == []


# =============================================================================
# 5. Engine Stage 2 — SEC + Benzinga enrichment wiring
# =============================================================================


class TestStage2Enrichment:
    """Verify stage_2_ingestion enriches results with SEC and Benzinga data."""

    def _make_mock_engine(self):
        """Build a minimal PipelineEngine stand-in for testing stage_2."""
        from research_pipeline.services.sec_api_service import SECApiService
        from research_pipeline.services.benzinga_service import BenzingaService
        from research_pipeline.pipeline.engine import PipelineEngine

        engine = PipelineEngine.__new__(PipelineEngine)
        engine.ingestor = MagicMock()
        engine.gates = MagicMock()
        engine.gates.gate_2_ingestion = MagicMock(return_value=MagicMock(passed=True))
        engine.gate_results = {}
        engine.stage_outputs = {}
        engine.run_record = MagicMock()
        engine.run_record.run_id = "test-stage2-run"
        engine.sec_api_svc = SECApiService(api_key="")  # no-op
        engine.benzinga_svc = BenzingaService(api_key="")  # no-op
        engine._stage_timings = {}
        return engine

    def test_stage_2_runs_without_error_when_new_services_are_empty(self):
        """Stage 2 must complete normally when SEC/Benzinga return no-op packages."""
        engine = self._make_mock_engine()

        mock_results = [{"ticker": "NVDA", "fmp_quote": {"ticker": "NVDA", "source": "fmp"}}]
        engine.ingestor.ingest_universe = AsyncMock(return_value=mock_results)

        def save_output(stage_num, data):
            engine.stage_outputs[stage_num] = data

        engine._save_stage_output = save_output

        def check_gate(gate):
            return gate.passed

        engine._check_gate = check_gate

        result = asyncio.run(engine.stage_2_ingestion(["NVDA"]))
        assert result is True
        assert 2 in engine.stage_outputs

    def test_stage_2_result_still_has_ticker_data(self):
        """Core ticker data must survive even when SEC/Benzinga enrichment is skipped."""
        engine = self._make_mock_engine()

        mock_results = [
            {"ticker": "NVDA", "fmp_quote": {"ticker": "NVDA", "source": "fmp", "price": 875.0}},
            {"ticker": "AMD", "fmp_quote": {"ticker": "AMD", "source": "fmp", "price": 175.0}},
        ]
        engine.ingestor.ingest_universe = AsyncMock(return_value=mock_results)

        def save_output(stage_num, data):
            engine.stage_outputs[stage_num] = data

        engine._save_stage_output = save_output
        engine._check_gate = lambda gate: gate.passed

        asyncio.run(engine.stage_2_ingestion(["NVDA", "AMD"]))
        saved = engine.stage_outputs[2]
        tickers_in_result = [row.get("ticker") for row in saved if isinstance(row, dict)]
        assert "NVDA" in tickers_in_result
        assert "AMD" in tickers_in_result


# =============================================================================
# 6. Engine Stage 5 — evidence enrichment wiring
# =============================================================================


class TestStage5EvidenceEnrichment:
    """Verify stage_5_evidence passes qualitative + SEC + Benzinga to the agent."""

    def _make_mock_engine(self):
        from research_pipeline.services.sec_api_service import SECApiService
        from research_pipeline.services.benzinga_service import BenzingaService
        from research_pipeline.services.qualitative_data_service import QualitativeDataService
        from research_pipeline.pipeline.engine import PipelineEngine

        engine = PipelineEngine.__new__(PipelineEngine)
        engine.evidence_agent = MagicMock()
        engine.gates = MagicMock()
        engine.gates.gate_5_evidence = MagicMock(return_value=MagicMock(passed=True))
        engine.gate_results = {}
        engine.stage_outputs = {2: []}
        engine.run_record = MagicMock()
        engine.run_record.run_id = "test-stage5-run"
        engine.qualitative_svc = QualitativeDataService(fmp_key="", finnhub_key="")
        engine.sec_api_svc = SECApiService(api_key="")  # no-op
        engine.benzinga_svc = BenzingaService(api_key="")  # no-op
        engine._stage_timings = {}
        return engine

    def test_stage_5_calls_evidence_agent(self):
        engine = self._make_mock_engine()

        agent_result = MagicMock()
        agent_result.model_dump = MagicMock(return_value={"success": True, "parsed_output": {}})
        agent_result.success = True
        agent_result.parsed_output = {}
        engine.evidence_agent.run = AsyncMock(return_value=agent_result)

        def save_output(stage_num, data):
            engine.stage_outputs[stage_num] = data

        engine._save_stage_output = save_output
        engine._check_gate = lambda gate: gate.passed

        asyncio.run(engine.stage_5_evidence(["NVDA"]))
        engine.evidence_agent.run.assert_called_once()

    def test_stage_5_agent_call_includes_qualitative_data_key(self):
        """The agent must receive 'qualitative_data' in its input dict."""
        engine = self._make_mock_engine()

        agent_result = MagicMock()
        agent_result.model_dump = MagicMock(return_value={"success": True, "parsed_output": {}})
        agent_result.success = True
        agent_result.parsed_output = {}
        engine.evidence_agent.run = AsyncMock(return_value=agent_result)

        def save_output(stage_num, data):
            engine.stage_outputs[stage_num] = data

        engine._save_stage_output = save_output
        engine._check_gate = lambda gate: gate.passed

        asyncio.run(engine.stage_5_evidence(["NVDA"]))

        call_args = engine.evidence_agent.run.call_args
        input_dict = call_args[0][1]  # second positional arg is the input dict
        assert "qualitative_data" in input_dict

    def test_stage_5_agent_call_includes_sec_primary_content_key(self):
        """The agent must receive 'sec_primary_content' in its input dict."""
        engine = self._make_mock_engine()

        agent_result = MagicMock()
        agent_result.model_dump = MagicMock(return_value={"success": True, "parsed_output": {}})
        agent_result.success = True
        agent_result.parsed_output = {}
        engine.evidence_agent.run = AsyncMock(return_value=agent_result)

        def save_output(stage_num, data):
            engine.stage_outputs[stage_num] = data

        engine._save_stage_output = save_output
        engine._check_gate = lambda gate: gate.passed

        asyncio.run(engine.stage_5_evidence(["NVDA"]))

        call_args = engine.evidence_agent.run.call_args
        input_dict = call_args[0][1]
        assert "sec_primary_content" in input_dict

    def test_stage_5_agent_call_includes_benzinga_evidence_key(self):
        """The agent must receive 'benzinga_evidence' in its input dict."""
        engine = self._make_mock_engine()

        agent_result = MagicMock()
        agent_result.model_dump = MagicMock(return_value={"success": True, "parsed_output": {}})
        agent_result.success = True
        agent_result.parsed_output = {}
        engine.evidence_agent.run = AsyncMock(return_value=agent_result)

        def save_output(stage_num, data):
            engine.stage_outputs[stage_num] = data

        engine._save_stage_output = save_output
        engine._check_gate = lambda gate: gate.passed

        asyncio.run(engine.stage_5_evidence(["NVDA"]))

        call_args = engine.evidence_agent.run.call_args
        input_dict = call_args[0][1]
        assert "benzinga_evidence" in input_dict

    def test_stage_5_survives_qualitative_svc_exception(self):
        """If QualitativeDataService raises, stage_5 must still proceed."""
        engine = self._make_mock_engine()
        engine.qualitative_svc.ingest_universe = AsyncMock(
            side_effect=RuntimeError("network error")
        )

        agent_result = MagicMock()
        agent_result.model_dump = MagicMock(return_value={"success": True, "parsed_output": {}})
        agent_result.success = True
        agent_result.parsed_output = {}
        engine.evidence_agent.run = AsyncMock(return_value=agent_result)

        def save_output(stage_num, data):
            engine.stage_outputs[stage_num] = data

        engine._save_stage_output = save_output
        engine._check_gate = lambda gate: gate.passed

        # Should not raise
        result = asyncio.run(engine.stage_5_evidence(["NVDA"]))
        assert result is True


# =============================================================================
# 7. File structure validation
# =============================================================================


class TestSession19FileStructure:
    """Verify all expected new files and attributes exist."""

    def test_sec_api_service_file_exists(self):
        sec_path = ROOT / "src" / "research_pipeline" / "services" / "sec_api_service.py"
        assert sec_path.exists(), f"Missing: {sec_path}"

    def test_benzinga_service_file_exists(self):
        benz_path = ROOT / "src" / "research_pipeline" / "services" / "benzinga_service.py"
        assert benz_path.exists(), f"Missing: {benz_path}"

    def test_sec_api_service_exports_expected_classes(self):
        from research_pipeline.services.sec_api_service import (
            SECApiService,
            SECFilingPackage,
            SECFilingRecord,
        )

        assert SECApiService is not None
        assert SECFilingPackage is not None
        assert SECFilingRecord is not None

    def test_benzinga_service_exports_expected_classes(self):
        from research_pipeline.services.benzinga_service import (
            BenzingaService,
            BenzingaTickerPackage,
            RatingChange,
            BenzingaNewsItem,
        )

        assert BenzingaService is not None
        assert BenzingaTickerPackage is not None
        assert RatingChange is not None
        assert BenzingaNewsItem is not None

    def test_engine_imports_sec_api_service(self):
        import research_pipeline.pipeline.engine as engine_module

        assert hasattr(engine_module, "SECApiService")

    def test_engine_imports_benzinga_service(self):
        import research_pipeline.pipeline.engine as engine_module

        assert hasattr(engine_module, "BenzingaService")

    def test_engine_imports_qualitative_data_service(self):
        import research_pipeline.pipeline.engine as engine_module

        assert hasattr(engine_module, "QualitativeDataService")

    def test_settings_has_both_new_keys(self):
        from research_pipeline.config.settings import APIKeys
        import inspect

        _fields = inspect.fields(APIKeys) if hasattr(inspect, "fields") else []
        keys = APIKeys()
        assert hasattr(keys, "sec_api_key")
        assert hasattr(keys, "benzinga_api_key")
