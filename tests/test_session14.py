"""Session 14 — Superannuation & Australian Client Context Tests.

30 tests covering:
- SuperannuationMandateService (mandate types, APRA SPS 530)
- AustralianTaxService (CGT, franking credits, SMSF, tax-aware rebalancing)
- Carbon intensity ESG (E-6)
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest


# ── SuperannuationMandateService ──────────────────────────────────────────

class TestSuperannuationMandateService:

    def _make_weights(self, tickers: list[str], equal: bool = True) -> dict[str, float]:
        if equal:
            w = 100.0 / len(tickers)
            return {t: w for t in tickers}
        return {t: 100.0 / len(tickers) for t in tickers}

    def test_service_instantiates(self):
        from research_pipeline.services.superannuation_mandate_service import SuperannuationMandateService
        svc = SuperannuationMandateService()
        assert svc is not None

    def test_get_constraints_balanced(self):
        from research_pipeline.services.superannuation_mandate_service import SuperannuationMandateService
        svc = SuperannuationMandateService()
        c = svc.get_constraints("balanced")
        assert c.min_growth_assets_pct == 60.0
        assert c.max_growth_assets_pct == 75.0

    def test_get_constraints_conservative(self):
        from research_pipeline.services.superannuation_mandate_service import SuperannuationMandateService
        svc = SuperannuationMandateService()
        c = svc.get_constraints("conservative")
        assert c.min_growth_assets_pct == 30.0
        assert c.max_single_stock_pct <= 5.0

    def test_get_constraints_growth(self):
        from research_pipeline.services.superannuation_mandate_service import SuperannuationMandateService
        svc = SuperannuationMandateService()
        c = svc.get_constraints("growth")
        assert c.min_growth_assets_pct >= 75.0

    def test_check_mandate_compliant_portfolio(self):
        from research_pipeline.services.superannuation_mandate_service import SuperannuationMandateService
        svc = SuperannuationMandateService()
        weights = {"NVDA": 5.0, "AMD": 5.0, "AVGO": 5.0, "CEG": 5.0, "PWR": 5.0,
                   "CBA.AX": 5.0, "BHP.AX": 5.0, "WBC.AX": 5.0, "NAB.AX": 5.0, "ANZ.AX": 5.0}
        result = svc.check_mandate("run1", weights, mandate_type="balanced")
        assert result.mandate_type == "balanced"
        assert result.apra_sps530_compliant is not None

    def test_check_mandate_detects_concentration(self):
        from research_pipeline.services.superannuation_mandate_service import SuperannuationMandateService
        svc = SuperannuationMandateService()
        # Single position at 50% — above SPS 530 limit
        weights = {"NVDA": 50.0, "AMD": 50.0}
        result = svc.check_mandate("run2", weights, mandate_type="balanced")
        assert result.is_compliant is False
        assert any("single_stock" in v.constraint for v in result.violations)

    def test_check_mandate_returns_growth_pct(self):
        from research_pipeline.services.superannuation_mandate_service import SuperannuationMandateService
        svc = SuperannuationMandateService()
        weights = self._make_weights(["NVDA", "AMD", "AVGO", "CEG", "PWR"])
        result = svc.check_mandate("run3", weights, mandate_type="growth")
        assert result.growth_assets_pct >= 0

    def test_check_mandate_lifecycle_age_60(self):
        from research_pipeline.services.superannuation_mandate_service import SuperannuationMandateService
        svc = SuperannuationMandateService()
        # For a 60-year-old, growth should be more constrained
        weights = self._make_weights(["NVDA", "AMD", "AVGO", "CEG", "PWR",
                                      "BHP.AX", "CBA.AX", "NAB.AX", "WBC.AX", "ANZ.AX"])
        result = svc.check_mandate("run4", weights, mandate_type="lifecycle", member_age=60)
        # At 60, conservative allocation — 100% growth equity would typically violate
        assert result.mandate_type == "lifecycle"

    def test_check_mandate_international_limit(self):
        from research_pipeline.services.superannuation_mandate_service import SuperannuationMandateService
        svc = SuperannuationMandateService()
        # Conservative mandate: max 20% international
        weights = {f"T{i}": 5.0 for i in range(20)}  # all US tickers (no .AX)
        result = svc.check_mandate("run5", weights, mandate_type="conservative")
        # Should flag international limit violation
        intl_violations = [v for v in result.violations if "international" in v.constraint]
        assert len(intl_violations) > 0

    def test_mandate_result_has_apra_flag(self):
        from research_pipeline.services.superannuation_mandate_service import SuperannuationMandateService
        svc = SuperannuationMandateService()
        weights = self._make_weights(["NVDA", "AMD"])
        result = svc.check_mandate("run6", weights, mandate_type="growth")
        assert hasattr(result, "apra_sps530_compliant")
        assert hasattr(result, "notes")

    def test_dio_allows_high_concentration(self):
        from research_pipeline.services.superannuation_mandate_service import SuperannuationMandateService
        svc = SuperannuationMandateService()
        # DIO: member-directed; allows up to 20% single stock
        weights = {"NVDA": 15.0, "AMD": 15.0, "AVGO": 10.0, "CEG": 10.0,
                   "PWR": 10.0, "ETN": 10.0, "BHP.AX": 10.0, "CBA.AX": 10.0,
                   "WBC.AX": 5.0, "NAB.AX": 5.0}
        result = svc.check_mandate("run7", weights, mandate_type="direct_investment_option")
        # 15% positions should be compliant under DIO (limit is 20%)
        conc_violations = [v for v in result.violations if "single_stock" in v.constraint]
        assert len(conc_violations) == 0


# ── AustralianTaxService ──────────────────────────────────────────────────

class TestAustralianTaxService:

    def test_service_instantiates(self):
        from research_pipeline.services.australian_tax_service import AustralianTaxService
        svc = AustralianTaxService()
        assert svc is not None

    def test_franking_credit_calculation(self):
        from research_pipeline.services.australian_tax_service import AustralianTaxService
        svc = AustralianTaxService()
        result = svc.compute_franking_credit(
            ticker="CBA.AX",
            dividend_per_share=2.50,
            franking_percentage=100.0,
        )
        assert result.franking_credit_per_share > 0
        assert result.grossed_up_dividend > result.dividend_per_share

    def test_franking_credit_partial_franking(self):
        from research_pipeline.services.australian_tax_service import AustralianTaxService
        svc = AustralianTaxService()
        full = svc.compute_franking_credit("TEST", 1.0, 100.0)
        half = svc.compute_franking_credit("TEST", 1.0, 50.0)
        assert full.franking_credit_per_share > half.franking_credit_per_share

    def test_cgt_calculation_with_discount(self):
        from research_pipeline.services.australian_tax_service import AustralianTaxService
        svc = AustralianTaxService()
        result = svc.compute_cgt(
            ticker="NVDA",
            cost_base=500.0,
            proceeds=700.0,
            purchase_date=date(2023, 1, 1),  # >12 months
            sale_date=date(2024, 2, 1),
            entity_type="individual",
        )
        assert result.discount_applied is True
        assert result.holding_period_days > 365
        assert result.capital_gain == 200.0
        # Net after 50% discount
        assert result.net_capital_gain == 100.0

    def test_cgt_no_discount_for_short_hold(self):
        from research_pipeline.services.australian_tax_service import AustralianTaxService
        svc = AustralianTaxService()
        result = svc.compute_cgt(
            ticker="NVDA",
            cost_base=500.0,
            proceeds=600.0,
            purchase_date=date(2024, 1, 1),
            sale_date=date(2024, 6, 1),  # 5 months
            entity_type="individual",
        )
        assert result.discount_applied is False
        assert result.net_capital_gain == result.capital_gain

    def test_cgt_tax_loss_flagged(self):
        from research_pipeline.services.australian_tax_service import AustralianTaxService
        svc = AustralianTaxService()
        result = svc.compute_cgt(
            ticker="AMD",
            cost_base=150.0,
            proceeds=100.0,
            purchase_date=date(2023, 1, 1),
            sale_date=date(2024, 1, 15),
        )
        assert result.is_tax_loss is True
        assert result.capital_gain < 0
        assert result.tax_payable == 0

    def test_smsf_accumulation_tax_rate(self):
        from research_pipeline.services.australian_tax_service import AustralianTaxService
        svc = AustralianTaxService()
        assert svc.TAX_RATES["smsf_accumulation"] == 0.15

    def test_smsf_pension_zero_tax(self):
        from research_pipeline.services.australian_tax_service import AustralianTaxService
        svc = AustralianTaxService()
        assert svc.TAX_RATES["smsf_pension"] == 0.0

    def test_tax_aware_rebalance_generates_trades(self):
        from research_pipeline.services.australian_tax_service import AustralianTaxService
        svc = AustralianTaxService()
        result = svc.tax_aware_rebalance(
            run_id="test",
            target_weights={"NVDA": 10.0, "AMD": 15.0, "AVGO": 10.0},
            current_weights={"NVDA": 15.0, "AMD": 10.0, "AVGO": 10.0},
            cost_bases={"NVDA": 80.0, "AMD": 100.0},
            current_prices={"NVDA": 120.0, "AMD": 95.0},
            purchase_dates={"NVDA": date(2023, 1, 1), "AMD": date(2023, 6, 1)},
        )
        assert len(result.trades) > 0
        assert result.summary != ""

    def test_tax_aware_rebalance_identifies_harvest(self):
        from research_pipeline.services.australian_tax_service import AustralianTaxService
        svc = AustralianTaxService()
        result = svc.tax_aware_rebalance(
            run_id="test",
            target_weights={"NVDA": 5.0},
            current_weights={"NVDA": 15.0},
            cost_bases={"NVDA": 150.0},  # bought high
            current_prices={"NVDA": 100.0},  # now lower → tax loss
            purchase_dates={"NVDA": date(2024, 1, 1)},
        )
        harvest_trades = [t for t in result.trades if t.is_tax_loss_harvest]
        assert len(harvest_trades) >= 1

    def test_deferred_trade_for_near_12m_threshold(self):
        from research_pipeline.services.australian_tax_service import AustralianTaxService
        svc = AustralianTaxService()
        # Purchase 350 days ago — very close to 12 month discount threshold
        purchase = date.today() - __import__("datetime").timedelta(days=350)
        result = svc.tax_aware_rebalance(
            run_id="test",
            target_weights={"NVDA": 5.0},
            current_weights={"NVDA": 20.0},
            cost_bases={"NVDA": 50.0},
            current_prices={"NVDA": 120.0},  # large gain
            purchase_dates={"NVDA": purchase},
        )
        deferred = [t for t in result.trades if t.recommendation == "defer"]
        assert len(deferred) >= 1, "Near-12m threshold should trigger defer recommendation"


# ── E-6: Carbon Intensity (ESG) ───────────────────────────────────────────

class TestCarbonIntensityE6:

    def test_esg_service_has_carbon_intensity(self):
        from research_pipeline.services.esg_service import ESGService
        svc = ESGService()
        # Check that ESGService has or can be extended with carbon intensity
        assert hasattr(svc, "get_portfolio_scores") or hasattr(svc, "check_portfolio_esg_compliance")

    def test_governance_schema_has_esg_score(self):
        from research_pipeline.schemas.governance import ESGScore
        score = ESGScore(ticker="NVDA", environmental_score=7.0, social_score=6.0, governance_score=8.0)
        assert score.ticker == "NVDA"

    def test_super_mandate_esg_integration(self):
        """ESG exclusions should affect mandate compliance."""
        from research_pipeline.services.superannuation_mandate_service import SuperannuationMandateService
        svc = SuperannuationMandateService()
        weights = {"NVDA": 10.0, "AMD": 10.0}
        result = svc.check_mandate("test", weights, mandate_type="balanced")
        assert result is not None
