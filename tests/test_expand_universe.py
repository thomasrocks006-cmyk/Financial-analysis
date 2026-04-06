"""Tests for the expanded universe configuration and updated RunRequest schema."""

from __future__ import annotations

import pytest

from research_pipeline.config.universe_config import (
    BROAD_MARKET_UNIVERSE,
    AI_INFRASTRUCTURE_UNIVERSE,
    GLOBAL_TECH_UNIVERSE,
    HEALTHCARE_UNIVERSE,
    FINANCIALS_UNIVERSE,
    CONSUMER_UNIVERSE,
    ENERGY_MATERIALS_UNIVERSE,
    REAL_ESTATE_UNIVERSE,
    FIXED_INCOME_UNIVERSE,
    COMMODITY_UNIVERSE,
    ALTERNATIVES_UNIVERSE,
    ETF_BENCHMARK_UNIVERSE,
    get_universe,
    list_universes,
    list_universe_details,
    get_universe_metadata,
    get_subtheme_map,
    get_subtheme,
    ticker_to_subtheme,
)
from research_pipeline.schemas.run_request import RunRequest


# ── Universe Config tests ──────────────────────────────────────────────────────

class TestUniverseSizes:
    """Verify expanded universe has sufficient coverage across asset classes."""

    def test_broad_market_universe_is_large(self):
        assert len(BROAD_MARKET_UNIVERSE) >= 80, "Broad market should have at least 80 tickers"

    def test_ai_infrastructure_expanded(self):
        assert len(AI_INFRASTRUCTURE_UNIVERSE) >= 20, "AI infra should have at least 20 tickers"

    def test_ai_infra_has_more_than_legacy_15(self):
        legacy = ["NVDA", "AMD", "INTC", "AVGO", "MRVL", "MSFT", "GOOGL", "AMZN", "META",
                  "PLTR", "AI", "SNOW", "MDB", "VST"]
        assert len(AI_INFRASTRUCTURE_UNIVERSE) > len(legacy)

    def test_healthcare_universe_present(self):
        assert len(HEALTHCARE_UNIVERSE) >= 15

    def test_financials_universe_present(self):
        assert len(FINANCIALS_UNIVERSE) >= 10

    def test_fixed_income_expanded(self):
        assert len(FIXED_INCOME_UNIVERSE) >= 20, "Fixed income should cover short/long/IG/HY/tips/intl"

    def test_commodities_present(self):
        assert len(COMMODITY_UNIVERSE) >= 10

    def test_alternatives_present(self):
        assert len(ALTERNATIVES_UNIVERSE) >= 10

    def test_etf_benchmarks_expanded(self):
        assert len(ETF_BENCHMARK_UNIVERSE) >= 25

    def test_real_estate_universe_present(self):
        assert len(REAL_ESTATE_UNIVERSE) >= 10


class TestUniverseContents:
    """Check that key tickers are present in the right universes."""

    def test_broad_market_includes_equities(self):
        for ticker in ["AAPL", "MSFT", "NVDA", "JPM", "JNJ", "XOM"]:
            assert ticker in BROAD_MARKET_UNIVERSE, f"{ticker} missing from broad market"

    def test_broad_market_includes_fixed_income(self):
        for ticker in ["TLT", "IEF", "LQD", "HYG"]:
            assert ticker in BROAD_MARKET_UNIVERSE, f"{ticker} (FI ETF) missing from broad market"

    def test_broad_market_includes_commodities(self):
        for ticker in ["GLD", "USO"]:
            assert ticker in BROAD_MARKET_UNIVERSE, f"{ticker} missing from broad market"

    def test_broad_market_includes_alternatives(self):
        assert "IBIT" in BROAD_MARKET_UNIVERSE, "Bitcoin ETF should be in broad market"

    def test_ai_infra_includes_networking(self):
        assert "ANET" in AI_INFRASTRUCTURE_UNIVERSE

    def test_ai_infra_includes_data_centres(self):
        for ticker in ["EQIX", "DLR", "AMT"]:
            assert ticker in AI_INFRASTRUCTURE_UNIVERSE, f"{ticker} (data centre REIT) missing"

    def test_fixed_income_has_full_duration_curve(self):
        assert "SHV" in FIXED_INCOME_UNIVERSE, "Short-end treasury missing"
        assert "TLT" in FIXED_INCOME_UNIVERSE, "Long-end treasury missing"

    def test_fixed_income_has_credit(self):
        assert "LQD" in FIXED_INCOME_UNIVERSE, "IG credit missing"
        assert "HYG" in FIXED_INCOME_UNIVERSE, "HY credit missing"

    def test_fixed_income_has_inflation_linked(self):
        assert "TIP" in FIXED_INCOME_UNIVERSE

    def test_fixed_income_has_international(self):
        assert "BNDX" in FIXED_INCOME_UNIVERSE
        assert "EMB" in FIXED_INCOME_UNIVERSE


class TestUniverseRegistry:
    """Verify the registry accessor API."""

    def test_list_universes_includes_broad_market(self):
        assert "broad_market" in list_universes()

    def test_list_universes_includes_all_asset_classes(self):
        universes = list_universes()
        for name in ["ai_infrastructure", "fixed_income", "commodities", "alternatives",
                     "healthcare", "financials", "etf_benchmarks"]:
            assert name in universes, f"Universe '{name}' not registered"

    def test_get_universe_returns_broad_market(self):
        tickers = get_universe("broad_market")
        assert len(tickers) >= 80

    def test_get_universe_raises_on_unknown(self):
        with pytest.raises(KeyError):
            get_universe("unknown_universe_xyz")

    def test_list_universe_details_has_metadata(self):
        details = list_universe_details()
        assert len(details) >= 10
        for d in details:
            assert "id" in d
            assert "label" in d
            assert "ticker_count" in d
            assert d["ticker_count"] > 0

    def test_broad_market_is_default_in_details(self):
        details = list_universe_details()
        ids = [d["id"] for d in details]
        assert ids[0] == "broad_market", "Broad market should be listed first"

    def test_get_universe_metadata_returns_dict(self):
        meta = get_universe_metadata("broad_market")
        assert "label" in meta
        assert "description" in meta
        assert "asset_classes" in meta

    def test_get_universe_metadata_unknown_returns_empty(self):
        meta = get_universe_metadata("does_not_exist")
        assert meta == {}


class TestSubthemes:
    """Verify subtheme maps are complete."""

    def test_ai_infrastructure_subthemes_exist(self):
        themes = get_subtheme_map("ai_infrastructure")
        assert "ai_chips" in themes
        assert "hyperscalers" in themes
        assert "ai_software" in themes
        assert "data_centres" in themes
        assert "networking" in themes
        assert "power_energy" in themes

    def test_broad_market_subthemes_exist(self):
        themes = get_subtheme_map("broad_market")
        assert "fixed_income" in themes
        assert "alternatives" in themes
        assert "commodities" in themes

    def test_ticker_to_subtheme_works(self):
        assert ticker_to_subtheme("NVDA", "ai_infrastructure") == "ai_chips"
        assert ticker_to_subtheme("MSFT", "ai_infrastructure") == "hyperscalers"
        assert ticker_to_subtheme("UNKNOWN_XYZ", "ai_infrastructure") is None

    def test_get_subtheme_raises_on_unknown(self):
        with pytest.raises(KeyError):
            get_subtheme("ai_infrastructure", "nonexistent_subtheme")


# ── RunRequest schema tests ────────────────────────────────────────────────────

class TestRunRequestDefaults:
    """Verify the new RunRequest defaults."""

    def test_default_universe_mode_is_discovery(self):
        req = RunRequest()
        assert req.universe_mode == "discovery"

    def test_default_universe_is_broad_market(self):
        req = RunRequest()
        assert len(req.universe) >= 80

    def test_is_discovery_mode_property(self):
        req = RunRequest()
        assert req.is_discovery_mode is True

    def test_preset_mode_not_discovery(self):
        req = RunRequest(universe_mode="preset", universe=["NVDA", "AMD"])
        assert req.is_discovery_mode is False

    def test_custom_mode_not_discovery(self):
        req = RunRequest(universe_mode="custom", universe=["AAPL"])
        assert req.is_discovery_mode is False


class TestRunRequestValidation:
    """Verify RunRequest validation still works correctly."""

    def test_valid_preset_mode(self):
        req = RunRequest(
            universe_mode="preset",
            universe=["NVDA", "AMD", "MSFT"],
        )
        assert req.universe == ["NVDA", "AMD", "MSFT"]
        assert req.universe_mode == "preset"

    def test_valid_custom_mode(self):
        req = RunRequest(
            universe_mode="custom",
            universe=["aapl", " msft ", "NVDA"],
        )
        # Tickers are normalised to uppercase
        assert "AAPL" in req.universe
        assert "MSFT" in req.universe

    def test_invalid_universe_mode_rejected(self):
        with pytest.raises(Exception):
            RunRequest(universe_mode="invalid_mode", universe=["AAPL"])

    def test_empty_universe_rejected(self):
        with pytest.raises(Exception):
            RunRequest(universe=[], universe_mode="custom")

    def test_large_universe_accepted(self):
        tickers = [f"T{i:04d}" for i in range(200)]
        req = RunRequest(universe=tickers, universe_mode="custom")
        assert len(req.universe) == 200

    def test_universe_count_exceeds_legacy_15(self):
        req = RunRequest()
        assert len(req.universe) > 15, "Default universe should exceed the legacy 15-stock preset"

    def test_to_settings_overrides_still_works(self):
        req = RunRequest(llm_model="gpt-4o", llm_temperature=0.5)
        overrides = req.to_settings_overrides()
        assert overrides["llm_model"] == "gpt-4o"
        assert overrides["llm_temperature"] == 0.5
