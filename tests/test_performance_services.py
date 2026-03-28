"""Tests for performance, monitoring, rebalancing, position sizing, and support services."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from research_pipeline.services.performance_tracker import PerformanceTracker
from research_pipeline.services.monitoring_engine import (
    AlertSeverity,
    AlertType,
    MonitoringEngine,
)
from research_pipeline.services.rebalancing_engine import RebalancingEngine
from research_pipeline.services.position_sizing import PositionSizingEngine
from research_pipeline.services.cache_layer import CacheLayer, QuotaManager
from research_pipeline.services.prompt_registry import PromptRegistry
from research_pipeline.schemas.performance import ThesisStatus


# ── Performance Tracker ────────────────────────────────────────────────────


class TestPerformanceTracker:
    def setup_method(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.tracker = PerformanceTracker(storage_dir=self.tmpdir)

    def test_bhb_attribution(self):
        now = datetime.now(timezone.utc)
        sector_map = {"NVDA": "compute", "AVGO": "compute", "CEG": "power", "EQIX": "infra"}
        attr = self.tracker.compute_bhb_attribution(
            run_id="RUN-001",
            portfolio_weights={"NVDA": 30, "AVGO": 20, "CEG": 25, "EQIX": 25},
            portfolio_returns={"NVDA": 0.10, "AVGO": 0.05, "CEG": 0.08, "EQIX": 0.03},
            benchmark_weights={"NVDA": 20, "AVGO": 15, "CEG": 30, "EQIX": 35},
            benchmark_returns={"NVDA": 0.10, "AVGO": 0.05, "CEG": 0.08, "EQIX": 0.03},
            sector_map=sector_map,
        )
        assert attr.run_id == "RUN-001"
        assert isinstance(attr.allocation_effect_pct, float)
        assert isinstance(attr.selection_effect_pct, float)

    def test_liquidity_profile(self):
        profile = self.tracker.compute_liquidity_profile(
            ticker="NVDA",
            avg_daily_volume=50_000_000,
            price=125.0,
            position_weight_pct=10.0,
            portfolio_value=1_000_000_000,  # 1B portfolio so position is meaningful vs ADV
        )
        assert profile.ticker == "NVDA"
        assert profile.days_to_liquidate > 0
        assert profile.liquidity_score >= 1.0

    def test_liquidity_profile_illiquid(self):
        profile = self.tracker.compute_liquidity_profile(
            ticker="SMALL_CAP",
            avg_daily_volume=10_000,
            price=50.0,
            position_weight_pct=10.0,
            portfolio_value=10_000_000,  # 10M portfolio, position = 1M vs low ADV
        )
        assert profile.days_to_liquidate > 1
        assert profile.liquidity_score < 10.0

    def test_thesis_create_and_retrieve(self):
        thesis = self.tracker.create_thesis(
            thesis_id="TH-001",
            run_id="RUN-001",
            ticker="NVDA",
            thesis_text="NVIDIA data center thesis",
            price_at_creation=125.0,
        )
        assert thesis.status == ThesisStatus.ACTIVE

        active = self.tracker.get_active_theses(ticker="NVDA")
        assert len(active) == 1
        assert active[0].thesis_id == "TH-001"

    def test_thesis_update_status(self):
        self.tracker.create_thesis(
            thesis_id="TH-002",
            run_id="RUN-001",
            ticker="AVGO",
            thesis_text="AVGO AI networking thesis",
            price_at_creation=180.0,
        )
        updated = self.tracker.update_thesis_status(
            thesis_id="TH-002",
            status=ThesisStatus.CHALLENGED,
            current_price=170.0,
            notes="Revenue miss in Q3",
        )
        assert updated is not None
        assert updated.status == ThesisStatus.CHALLENGED
        assert updated.return_since_pct is not None

    def test_snapshot_save_and_load(self):
        from research_pipeline.schemas.performance import PortfolioSnapshot
        snap = PortfolioSnapshot(
            run_id="RUN-001",
            variant_name="balanced",
            positions={"NVDA": 12.0, "AVGO": 10.0},
            prices={"NVDA": 125.0, "AVGO": 180.0},
        )
        self.tracker.save_snapshot(snap)
        loaded = self.tracker.get_snapshots(variant_name="balanced")
        assert len(loaded) == 1
        assert loaded[0].run_id == "RUN-001"


# ── Monitoring Engine ──────────────────────────────────────────────────────


class TestMonitoringEngine:
    def setup_method(self):
        # Use relaxed concentration limits for general tests
        self.engine = MonitoringEngine(
            price_move_threshold_pct=5.0,
            weight_drift_threshold_pct=2.0,
            concentration_hhi_limit=5000,
            max_single_name_pct=50.0,
        )

    def test_no_alerts_stable_portfolio(self):
        target = {"NVDA": 30.0, "AVGO": 30.0, "TSM": 40.0}
        ref_prices = {"NVDA": 100.0, "AVGO": 100.0, "TSM": 100.0}
        cur_prices = {"NVDA": 101.0, "AVGO": 99.5, "TSM": 100.5}

        report = self.engine.run_monitoring(
            run_id="RUN-001",
            target_weights=target,
            current_prices=cur_prices,
            reference_prices=ref_prices,
        )
        assert len(report.alerts) == 0

    def test_price_move_alert(self):
        target = {"NVDA": 50.0, "AVGO": 50.0}
        ref_prices = {"NVDA": 100.0, "AVGO": 100.0}
        cur_prices = {"NVDA": 110.0, "AVGO": 100.0}  # 10% move

        report = self.engine.run_monitoring(
            run_id="RUN-001",
            target_weights=target,
            current_prices=cur_prices,
            reference_prices=ref_prices,
        )
        price_alerts = [a for a in report.alerts if a.alert_type == AlertType.PRICE_MOVE]
        assert len(price_alerts) >= 1
        assert price_alerts[0].ticker == "NVDA"

    def test_concentration_breach(self):
        # Use strict concentration engine for this test
        strict_engine = MonitoringEngine(
            price_move_threshold_pct=5.0,
            weight_drift_threshold_pct=2.0,
            concentration_hhi_limit=2500,
            max_single_name_pct=15.0,
        )
        target = {"NVDA": 85.0, "AVGO": 15.0}
        ref_prices = {"NVDA": 100.0, "AVGO": 100.0}
        cur_prices = {"NVDA": 100.0, "AVGO": 100.0}

        report = strict_engine.run_monitoring(
            run_id="RUN-001",
            target_weights=target,
            current_prices=cur_prices,
            reference_prices=ref_prices,
        )
        conc_alerts = [a for a in report.alerts if a.alert_type == AlertType.CONCENTRATION_BREACH]
        assert len(conc_alerts) >= 1

    def test_needs_reanalysis(self):
        # Use strict engine for this test — big moves + concentration should trigger critical alerts
        strict_engine = MonitoringEngine(
            price_move_threshold_pct=5.0,
            weight_drift_threshold_pct=2.0,
            concentration_hhi_limit=2500,
            max_single_name_pct=15.0,
        )
        target = {"NVDA": 85.0, "AVGO": 15.0}
        ref_prices = {"NVDA": 100.0, "AVGO": 100.0}
        cur_prices = {"NVDA": 120.0, "AVGO": 80.0}  # big moves + concentration

        report = strict_engine.run_monitoring(
            run_id="RUN-001",
            target_weights=target,
            current_prices=cur_prices,
            reference_prices=ref_prices,
        )
        assert report.needs_reanalysis is True


# ── Rebalancing Engine ─────────────────────────────────────────────────────


class TestRebalancingEngine:
    def setup_method(self):
        self.engine = RebalancingEngine(
            drift_threshold_pct=2.0,
            min_trade_pct=0.5,
        )

    def test_no_drift(self):
        target = {"NVDA": 30.0, "AVGO": 30.0, "TSM": 40.0}
        current = {"NVDA": 30.5, "AVGO": 29.8, "TSM": 39.7}
        assert self.engine.needs_rebalance(target, current) is False

    def test_drift_detected(self):
        target = {"NVDA": 30.0, "AVGO": 30.0, "TSM": 40.0}
        current = {"NVDA": 35.0, "AVGO": 28.0, "TSM": 37.0}
        assert self.engine.needs_rebalance(target, current) is True

    def test_generate_rebalance_trades(self):
        target = {"NVDA": 30.0, "AVGO": 30.0, "TSM": 40.0}
        current = {"NVDA": 40.0, "AVGO": 25.0, "TSM": 35.0}

        proposal = self.engine.generate_rebalance(
            run_id="RUN-001",
            target_weights=target,
            current_weights=current,
        )
        assert proposal.trade_count > 0
        assert proposal.total_turnover_pct > 0

        # NVDA should be a sell (currently overweight)
        nvda_trades = [t for t in proposal.trades if t.ticker == "NVDA"]
        assert len(nvda_trades) == 1
        assert nvda_trades[0].direction == "sell"

    def test_compute_current_weights(self):
        target = {"NVDA": 50.0, "AVGO": 50.0}
        ref = {"NVDA": 100.0, "AVGO": 100.0}
        cur = {"NVDA": 120.0, "AVGO": 100.0}  # NVDA up 20%

        current_weights = self.engine.compute_current_weights(target, ref, cur)
        assert current_weights["NVDA"] > 50.0  # NVDA should drift higher
        assert abs(sum(current_weights.values()) - 100.0) < 0.1


# ── Position Sizing ────────────────────────────────────────────────────────


class TestPositionSizing:
    def setup_method(self):
        self.engine = PositionSizingEngine(
            max_position_pct=15.0,
            min_position_pct=1.0,
        )

    def test_equal_weight(self):
        tickers = ["NVDA", "AVGO", "TSM", "EQIX", "CEG"]
        weights = self.engine.equal_weight(tickers)
        assert len(weights) == 5
        assert abs(sum(weights.values()) - 100.0) < 0.01

    def test_conviction_weighted(self):
        scores = {"NVDA": 9.0, "AVGO": 7.0, "TSM": 5.0, "EQIX": 6.0, "CEG": 8.0}
        weights = self.engine.conviction_weighted(scores)
        assert abs(sum(weights.values()) - 100.0) < 0.1
        # NVDA should have highest weight
        assert weights["NVDA"] >= weights["TSM"]

    def test_conviction_weighted_max_constraint(self):
        # Use enough tickers (>=7) so max 15% constraint is satisfiable (7*15=105>100)
        scores = {
            "NVDA": 10.0, "AVGO": 5.0, "TSM": 4.0,
            "EQIX": 3.0, "CEG": 2.0, "VST": 2.0, "PWR": 1.0,
        }
        weights = self.engine.conviction_weighted(scores)
        assert abs(sum(weights.values()) - 100.0) < 0.5
        # After constraint application, NVDA (highest conviction) should be capped
        assert weights["NVDA"] <= 15.0 + 0.5

    def test_inverse_volatility(self):
        vols = {"NVDA": 0.40, "AVGO": 0.30, "TSM": 0.25, "EQIX": 0.15}
        weights = self.engine.inverse_volatility(vols)
        assert abs(sum(weights.values()) - 100.0) < 0.1
        # EQIX has lowest vol → should have highest weight
        assert weights["EQIX"] >= weights["NVDA"]

    def test_risk_budget_weighted(self):
        scores = {"NVDA": 9.0, "AVGO": 7.0, "TSM": 5.0}
        vols = {"NVDA": 0.40, "AVGO": 0.25, "TSM": 0.20}
        weights = self.engine.risk_budget_weighted(scores, vols)
        assert abs(sum(weights.values()) - 100.0) < 0.1

    def test_size_portfolio_dispatch(self):
        tickers = ["NVDA", "AVGO", "TSM"]
        weights = self.engine.size_portfolio(tickers, method="equal")
        assert len(weights) == 3
        assert abs(sum(weights.values()) - 100.0) < 0.1

    def test_empty_input(self):
        assert self.engine.equal_weight([]) == {}
        assert self.engine.conviction_weighted({}) == {}


# ── Cache Layer ────────────────────────────────────────────────────────────


class TestCacheLayer:
    def setup_method(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.cache = CacheLayer(cache_dir=self.tmpdir, default_ttl_seconds=3600)

    def test_set_and_get(self):
        self.cache.set("market_data", "NVDA_price", 125.50)
        result = self.cache.get("market_data", "NVDA_price")
        assert result == 125.50

    def test_cache_miss(self):
        result = self.cache.get("market_data", "nonexistent")
        assert result is None

    def test_cache_stats(self):
        self.cache.get("ns", "miss1")
        self.cache.set("ns", "key1", "value1")
        self.cache.get("ns", "key1")
        stats = self.cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["sets"] == 1

    def test_invalidate(self):
        self.cache.set("ns", "key1", "value1")
        assert self.cache.get("ns", "key1") == "value1"
        self.cache.invalidate("ns", "key1")
        assert self.cache.get("ns", "key1") is None

    def test_clear_all(self):
        self.cache.set("ns", "k1", "v1")
        self.cache.set("ns", "k2", "v2")
        assert self.cache.size == 2
        cleared = self.cache.clear_all()
        assert cleared == 2
        assert self.cache.size == 0

    def test_complex_values(self):
        data = {"tickers": ["NVDA", "AVGO"], "prices": [125.0, 180.0]}
        self.cache.set("market_data", "portfolio", data)
        result = self.cache.get("market_data", "portfolio")
        assert result == data

    def test_expired_entry(self):
        self.cache.set("ns", "key1", "value1", ttl_seconds=0)  # immediate expiry
        import time
        time.sleep(0.01)
        assert self.cache.get("ns", "key1") is None


# ── Quota Manager ──────────────────────────────────────────────────────────


class TestQuotaManager:
    def setup_method(self):
        self.mgr = QuotaManager(quotas={"fmp_api": 10, "anthropic_tokens": 1000})

    def test_track_and_check(self):
        self.mgr.track_usage("RUN-001", "fmp_api", 3)
        ok, remaining = self.mgr.check_quota("RUN-001", "fmp_api")
        assert ok is True
        assert remaining == 7

    def test_quota_exceeded(self):
        self.mgr.track_usage("RUN-001", "fmp_api", 10)
        ok, remaining = self.mgr.check_quota("RUN-001", "fmp_api")
        assert ok is False
        assert remaining == 0

    def test_usage_report(self):
        self.mgr.track_usage("RUN-001", "fmp_api", 5)
        self.mgr.track_usage("RUN-001", "anthropic_tokens", 500)
        usage = self.mgr.get_usage("RUN-001")
        assert usage["fmp_api"]["used"] == 5
        assert usage["fmp_api"]["utilization_pct"] == 50.0

    def test_reset_run(self):
        self.mgr.track_usage("RUN-001", "fmp_api", 5)
        self.mgr.reset_run("RUN-001")
        ok, remaining = self.mgr.check_quota("RUN-001", "fmp_api")
        assert ok is True
        assert remaining == 10


# ── Prompt Registry ────────────────────────────────────────────────────────


class TestPromptRegistry:
    def setup_method(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.registry = PromptRegistry(storage_dir=self.tmpdir)

    def test_register_new_prompt(self):
        version = self.registry.register_prompt(
            "sector_analyst_compute",
            "You are a semiconductor sector analyst...",
        )
        assert version.version == 1
        assert version.prompt_id == "sector_analyst_compute"

    def test_same_prompt_no_new_version(self):
        self.registry.register_prompt("test", "prompt text here")
        v2 = self.registry.register_prompt("test", "prompt text here")
        assert v2.version == 1  # same content, no new version

    def test_changed_prompt_new_version(self):
        self.registry.register_prompt("test", "version 1 text")
        v2 = self.registry.register_prompt("test", "version 2 text with changes")
        assert v2.version == 2

    def test_drift_detection_no_drift(self):
        self.registry.register_prompt("test", "stable prompt")
        report = self.registry.check_drift("test", "stable prompt")
        assert report.changed is False
        assert report.regression_required is False

    def test_drift_detection_with_drift(self):
        self.registry.register_prompt("test", "original prompt")
        report = self.registry.check_drift("test", "modified prompt")
        assert report.changed is True
        assert report.regression_required is True

    def test_regression_marking(self):
        self.registry.register_prompt("test", "prompt v1")
        self.registry.mark_regression_passed("test", "RUN-REGRESSION-001")
        latest = self.registry.get_latest_version("test")
        assert latest is not None
        assert latest.regression_status == "passed"

    def test_stats(self):
        self.registry.register_prompt("p1", "text1")
        self.registry.register_prompt("p2", "text2")
        self.registry.register_prompt("p1", "text1 v2")
        stats = self.registry.stats
        assert stats["total_prompts"] == 2
        assert stats["total_versions"] == 3
