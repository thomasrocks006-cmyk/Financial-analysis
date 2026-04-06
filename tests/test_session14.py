"""
tests/test_session14.py
-----------------------
Session 14 — Australian Client Context

Covers:
  1. ClientProfile schema — construction, derived properties, convenience helpers
  2. SuperannuationMandateService — mandate library, compliance checks
  3. AustralianTaxService — tax settings, CGT, franking, US withholding, drag
  4. build_au_disclosures() — report AU disclosure text
  5. PipelineConfig client_profile field
  6. PipelineEngine Session 14 wiring
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# 1. ClientProfile — schema construction
# ---------------------------------------------------------------------------


class TestClientProfileConstruction:
    def test_default_client(self):
        from research_pipeline.schemas.client_profile import ClientProfile

        cp = ClientProfile(client_id="test-01")
        assert cp.client_type == "institutional"
        assert cp.au_resident is True

    def test_super_fund_type(self):
        from research_pipeline.schemas.client_profile import ClientProfile

        cp = ClientProfile(client_id="sf-01", client_type="super_fund", super_fund_type="balanced")
        assert cp.super_fund_type == "balanced"

    def test_smsf_type(self):
        from research_pipeline.schemas.client_profile import ClientProfile

        cp = ClientProfile(client_id="smsf-01", client_type="smsf")
        assert cp.is_smsf is True

    def test_hnw_type(self):
        from research_pipeline.schemas.client_profile import ClientProfile

        cp = ClientProfile(client_id="hnw-01", client_type="hnw")
        assert cp.client_type == "hnw"

    def test_target_allocations_stored(self):
        from research_pipeline.schemas.client_profile import ClientProfile

        cp = ClientProfile(
            client_id="alloc",
            target_au_pct=55.0,
            target_us_pct=35.0,
            target_fi_pct=10.0,
        )
        assert cp.target_au_pct == 55.0
        assert cp.target_us_pct == 35.0
        assert cp.target_fi_pct == 10.0


# ---------------------------------------------------------------------------
# 2. ClientProfile — derived properties
# ---------------------------------------------------------------------------


class TestClientProfileDerivedProperties:
    def test_is_super_true_for_super_fund(self):
        from research_pipeline.schemas.client_profile import ClientProfile

        cp = ClientProfile(client_type="super_fund")
        assert cp.is_super is True

    def test_is_super_true_for_smsf(self):
        from research_pipeline.schemas.client_profile import ClientProfile

        cp = ClientProfile(client_type="smsf")
        assert cp.is_super is True

    def test_is_super_false_for_institutional(self):
        from research_pipeline.schemas.client_profile import ClientProfile

        cp = ClientProfile(client_type="institutional")
        assert cp.is_super is False

    def test_super_fund_tax_rate(self):
        from research_pipeline.schemas.client_profile import ClientProfile

        cp = ClientProfile(client_type="super_fund")
        assert cp.effective_marginal_tax_rate == pytest.approx(0.15)

    def test_smsf_pension_phase_zero_tax(self):
        from research_pipeline.schemas.client_profile import ClientProfile

        cp = ClientProfile(client_type="smsf", smsf_pension_phase=True)
        assert cp.effective_marginal_tax_rate == pytest.approx(0.0)

    def test_smsf_accumulation_tax_rate(self):
        from research_pipeline.schemas.client_profile import ClientProfile

        cp = ClientProfile(client_type="smsf", smsf_pension_phase=False)
        assert cp.effective_marginal_tax_rate == pytest.approx(0.15)

    def test_hnw_tax_rate(self):
        from research_pipeline.schemas.client_profile import ClientProfile

        cp = ClientProfile(client_type="hnw")
        assert cp.effective_marginal_tax_rate == pytest.approx(0.47)

    def test_smsf_pension_cgt_fully_exempt(self):
        from research_pipeline.schemas.client_profile import ClientProfile

        cp = ClientProfile(client_type="smsf", smsf_pension_phase=True)
        assert cp.effective_cgt_discount == pytest.approx(1.0)

    def test_individual_cgt_discount(self):
        from research_pipeline.schemas.client_profile import ClientProfile

        cp = ClientProfile(client_type="hnw")
        assert cp.effective_cgt_discount == pytest.approx(0.50)


# ---------------------------------------------------------------------------
# 3. Convenience constructors
# ---------------------------------------------------------------------------


class TestClientProfileConvenienceConstructors:
    def test_default_super_fund_profile(self):
        from research_pipeline.schemas.client_profile import default_super_fund_profile

        cp = default_super_fund_profile(fund_type="growth")
        assert cp.client_type == "super_fund"
        assert cp.super_fund_type == "growth"
        assert cp.apra_regulated is True

    def test_default_smsf_profile_pension(self):
        from research_pipeline.schemas.client_profile import default_smsf_profile

        cp = default_smsf_profile(pension_phase=True)
        assert cp.smsf_pension_phase is True
        assert cp.is_smsf is True

    def test_default_hnw_profile(self):
        from research_pipeline.schemas.client_profile import default_hnw_profile

        cp = default_hnw_profile()
        assert cp.client_type == "hnw"
        assert cp.au_resident is True


# ---------------------------------------------------------------------------
# 4. SuperannuationMandateService — mandate library
# ---------------------------------------------------------------------------


class TestSuperannuationMandateLibrary:
    @pytest.fixture
    def svc(self):
        from research_pipeline.services.superannuation_mandate import SuperannuationMandateService

        return SuperannuationMandateService()

    def test_get_growth_mandate(self, svc):
        m = svc.get_mandate("growth")
        assert m.mandate_type == "growth"
        assert m.max_growth_assets_pct == 85.0

    def test_get_conservative_has_lower_single_name(self, svc):
        m = svc.get_mandate("conservative")
        assert m.max_single_name_pct == 3.0

    def test_get_balanced_mandate(self, svc):
        m = svc.get_mandate("balanced")
        assert m.max_international_pct == 50.0

    def test_unknown_type_falls_back_to_balanced(self, svc):
        m = svc.get_mandate("unknown_xyz")
        assert m.mandate_type == "balanced"

    def test_dio_has_relaxed_single_name(self, svc):
        m = svc.get_mandate("dio")
        assert m.max_single_name_pct == 20.0

    def test_describe_mandate_non_empty(self, svc):
        desc = svc.describe_mandate("balanced")
        assert "Balanced" in desc or "balanced" in desc
        assert "single-name" in desc


# ---------------------------------------------------------------------------
# 5. SuperannuationMandateService — compliance checks
# ---------------------------------------------------------------------------


class TestSuperannuationMandateCompliance:
    @pytest.fixture
    def svc(self):
        from research_pipeline.services.superannuation_mandate import SuperannuationMandateService

        return SuperannuationMandateService()

    def _equal_weights(self, tickers):
        w = 100.0 / len(tickers)
        return {t: w for t in tickers}

    def test_compliant_portfolio(self, svc):
        # 20 equally-weighted stocks — each 5%, all US
        tickers = [f"TICK{i}" for i in range(20)]
        weights = self._equal_weights(tickers)
        result = svc.check_compliance(
            run_id="test",
            mandate_type="growth",
            weights=weights,
            asx_tickers=[],
        )
        # International 100% > 65% → violation
        assert not result.is_compliant

    def test_compliant_au_portfolio_growth(self, svc):
        # 20 equally-weighted .AX stocks — 5% each, all AU domestic
        tickers = [f"TICK{i}.AX" for i in range(20)]
        weights = self._equal_weights(tickers)
        result = svc.check_compliance(
            run_id="test",
            mandate_type="growth",
            weights=weights,
        )
        assert result.is_compliant
        assert result.violations == []

    def test_single_name_violation(self, svc):
        weights = {f"TICK{i}.AX": 4.0 for i in range(24)}
        weights["BIG.AX"] = 4.0  # still 4% — within balanced 5% limit
        weights["HUGE.AX"] = 8.0  # 8% > 5% balanced limit → violation
        result = svc.check_compliance(
            run_id="test",
            mandate_type="balanced",
            weights=weights,
        )
        assert not result.is_compliant
        assert any("HUGE.AX" in v.description for v in result.violations)

    def test_international_cap_violation(self, svc):
        # 80% international, 20% AU — balanced cap is 50%
        us_weights = {f"US{i}": 4.0 for i in range(20)}  # 80%
        au_weights = {"CBA.AX": 10.0, "BHP.AX": 10.0}
        weights = {**us_weights, **au_weights}
        result = svc.check_compliance(
            run_id="test",
            mandate_type="balanced",
            weights=weights,
        )
        assert not result.is_compliant
        assert any("International" in v.description for v in result.violations)

    def test_au_minimum_warning(self, svc):
        # 28 AU stocks × 2.5% = 70% AU; 12 US stocks × 2.5% = 30% intl
        # Each position 2.5% < 5% single-name limit; intl 30% < 65% growth cap;
        # AU 70% > 20% minimum → fully compliant, zero violations.
        au_weights = {f"AX{i}.AX": 2.5 for i in range(28)}  # 70% AU
        us_weights = {f"US{i}": 2.5 for i in range(12)}  # 30% intl
        weights = {**au_weights, **us_weights}
        result = svc.check_compliance(
            run_id="test",
            mandate_type="growth",
            weights=weights,
        )
        assert result.is_compliant
        assert result.violations == []

    def test_mandate_id_format(self, svc):
        weights = {"CBA.AX": 5.0 for _ in range(20)}
        weights = {f"T{i}.AX": 5.0 for i in range(20)}
        result = svc.check_compliance(run_id="run-123", mandate_type="balanced", weights=weights)
        assert "AU_SUPER_BALANCED" in result.mandate_id

    def test_conservative_lower_single_name_limit(self, svc):
        # 4% is fine for growth but violates conservative (3% limit)
        weights = {f"T{i}.AX": 3.5 for i in range(28)}  # 28 × 3.5% = 98%
        weights["T0.AX"] = 5.0  # bump first one to 5%
        result = svc.check_compliance(run_id="test", mandate_type="conservative", weights=weights)
        assert not result.is_compliant
        assert any("SPS530_NAME" in v.rule.rule_id for v in result.violations)


# ---------------------------------------------------------------------------
# 6. AustralianTaxService — tax settings
# ---------------------------------------------------------------------------


class TestAustralianTaxServiceSettings:
    @pytest.fixture
    def svc(self):
        from research_pipeline.services.australian_tax_service import AustralianTaxService

        return AustralianTaxService()

    def test_super_fund_tax_settings(self, svc):
        from research_pipeline.schemas.client_profile import ClientProfile

        cp = ClientProfile(client_type="super_fund")
        ts = svc.get_tax_settings(cp)
        assert ts.income_tax_rate == pytest.approx(0.15)
        assert ts.cgt_discount_rate == pytest.approx(0.333)

    def test_smsf_accumulation_tax_settings(self, svc):
        from research_pipeline.schemas.client_profile import ClientProfile

        cp = ClientProfile(client_type="smsf", smsf_pension_phase=False)
        ts = svc.get_tax_settings(cp)
        assert ts.income_tax_rate == pytest.approx(0.15)
        assert ts.smsf_pension_phase is False

    def test_smsf_pension_tax_settings(self, svc):
        from research_pipeline.schemas.client_profile import ClientProfile

        cp = ClientProfile(client_type="smsf", smsf_pension_phase=True)
        ts = svc.get_tax_settings(cp)
        assert ts.income_tax_rate == pytest.approx(0.0)
        assert ts.smsf_pension_phase is True

    def test_hnw_tax_settings(self, svc):
        from research_pipeline.schemas.client_profile import ClientProfile

        cp = ClientProfile(client_type="hnw")
        ts = svc.get_tax_settings(cp)
        assert ts.income_tax_rate == pytest.approx(0.47)
        assert ts.cgt_discount_rate == pytest.approx(0.50)

    def test_institutional_default_settings(self, svc):
        from research_pipeline.schemas.client_profile import ClientProfile

        cp = ClientProfile(client_type="institutional")
        ts = svc.get_tax_settings(cp)
        assert ts.income_tax_rate == pytest.approx(0.30)
        assert ts.cgt_discount_rate == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 7. AustralianTaxService — CGT calculations
# ---------------------------------------------------------------------------


class TestAustralianTaxCGT:
    @pytest.fixture
    def svc(self):
        from research_pipeline.services.australian_tax_service import AustralianTaxService

        return AustralianTaxService()

    @pytest.fixture
    def hnw_ts(self):
        from research_pipeline.services.australian_tax_service import TAX_HNW

        return TAX_HNW

    @pytest.fixture
    def super_ts(self):
        from research_pipeline.services.australian_tax_service import TAX_SUPER_FUND

        return TAX_SUPER_FUND

    def test_short_term_gain_no_discount(self, svc, hnw_ts):
        tax = svc.apply_cgt(1000.0, held_days=100, tax_settings=hnw_ts)
        # 100 days < 365: no discount → 1000 × 47% = 470
        assert tax == pytest.approx(470.0)

    def test_long_term_gain_with_discount(self, svc, hnw_ts):
        tax = svc.apply_cgt(1000.0, held_days=400, tax_settings=hnw_ts)
        # 400 days ≥ 365: 50% discount → taxable = 500, tax = 500 × 47% = 235
        assert tax == pytest.approx(235.0)

    def test_super_fund_long_term_cgt(self, svc, super_ts):
        tax = svc.apply_cgt(1000.0, held_days=400, tax_settings=super_ts)
        # 1/3 discount → taxable = 667, tax = 667 × 15% ≈ 100
        assert tax == pytest.approx(1000 * (1 - 0.333) * 0.15, abs=0.01)

    def test_zero_gain_returns_zero(self, svc, hnw_ts):
        assert svc.apply_cgt(0.0, held_days=500, tax_settings=hnw_ts) == pytest.approx(0.0)

    def test_negative_gain_returns_zero(self, svc, hnw_ts):
        assert svc.apply_cgt(-500.0, held_days=500, tax_settings=hnw_ts) == pytest.approx(0.0)

    def test_after_tax_gain_less_than_gross(self, svc, hnw_ts):
        after = svc.after_tax_gain(1000.0, held_days=400, tax_settings=hnw_ts)
        assert after < 1000.0
        assert after > 0.0


# ---------------------------------------------------------------------------
# 8. AustralianTaxService — franking credits
# ---------------------------------------------------------------------------


class TestAustralianTaxFranking:
    @pytest.fixture
    def svc(self):
        from research_pipeline.services.australian_tax_service import AustralianTaxService

        return AustralianTaxService()

    def test_fully_franked_credit(self, svc):
        # Cash div $0.70; corp tax 30%; credit = 0.70 × 30/70 = 0.30
        credit = svc.compute_franking_credit(0.70, franking_pct=1.0, corporate_tax_rate=0.30)
        assert credit == pytest.approx(0.30, abs=0.0001)

    def test_partially_franked_credit(self, svc):
        # 50% franked: credit = 0.70 × 0.5 × (0.30/0.70) = 0.15
        credit = svc.compute_franking_credit(0.70, franking_pct=0.5, corporate_tax_rate=0.30)
        assert credit == pytest.approx(0.15, abs=0.0001)

    def test_grossed_up_is_cash_plus_credit(self, svc):
        grossed = svc.grossed_up_dividend(0.70, franking_pct=1.0)
        assert grossed == pytest.approx(1.00, abs=0.0001)


# ---------------------------------------------------------------------------
# 9. AustralianTaxService — US dividend withholding
# ---------------------------------------------------------------------------


class TestAustralianTaxUSWithholding:
    @pytest.fixture
    def svc(self):
        from research_pipeline.services.australian_tax_service import AustralianTaxService

        return AustralianTaxService()

    def test_super_fund_net_us_dividend(self, svc):
        from research_pipeline.services.australian_tax_service import TAX_SUPER_FUND

        # $1.00 gross: after 15% withholding = $0.85; after 15% income tax on $0.85 ≈ $0.7225
        net = svc.compute_net_us_dividend(1.0, TAX_SUPER_FUND)
        assert net == pytest.approx(0.85 * (1 - 0.15), abs=0.001)

    def test_smsf_pension_zero_income_tax(self, svc):
        from research_pipeline.services.australian_tax_service import TAX_SMSF_PENSION

        # Pension phase: 0% income tax, still 15% US withholding → net = 0.85
        net = svc.compute_net_us_dividend(1.0, TAX_SMSF_PENSION)
        assert net == pytest.approx(0.85, abs=0.001)


# ---------------------------------------------------------------------------
# 10. AustralianTaxService — tax drag
# ---------------------------------------------------------------------------


class TestAustralianTaxDrag:
    @pytest.fixture
    def svc(self):
        from research_pipeline.services.australian_tax_service import AustralianTaxService

        return AustralianTaxService()

    def test_super_fund_drag(self, svc):
        from research_pipeline.services.australian_tax_service import TAX_SUPER_FUND

        # 3% yield, 15% rate → drag = 300 bps × 0.15 = 45 bps
        drag = svc.compute_tax_drag_bps(3.0, TAX_SUPER_FUND)
        assert drag == pytest.approx(45.0)

    def test_smsf_pension_zero_drag(self, svc):
        from research_pipeline.services.australian_tax_service import TAX_SMSF_PENSION

        drag = svc.compute_tax_drag_bps(3.0, TAX_SMSF_PENSION)
        assert drag == pytest.approx(0.0)

    def test_hnw_drag_higher_than_super(self, svc):
        from research_pipeline.services.australian_tax_service import TAX_HNW, TAX_SUPER_FUND

        hnw_drag = svc.compute_tax_drag_bps(3.0, TAX_HNW)
        super_drag = svc.compute_tax_drag_bps(3.0, TAX_SUPER_FUND)
        assert hnw_drag > super_drag

    def test_portfolio_tax_summary_keys(self, svc):
        from research_pipeline.schemas.client_profile import ClientProfile

        cp = ClientProfile(client_type="super_fund")
        summary = svc.portfolio_tax_summary(cp)
        for key in [
            "income_tax_rate_pct",
            "after_tax_yield_pct",
            "estimated_tax_drag_bps",
            "cgt_discount_rate_pct",
        ]:
            assert key in summary


# ---------------------------------------------------------------------------
# 11. build_au_disclosures
# ---------------------------------------------------------------------------


class TestBuildAuDisclosures:
    def test_returns_non_empty_string(self):
        from research_pipeline.services.report_assembly import build_au_disclosures

        result = build_au_disclosures()
        assert isinstance(result, str)
        assert len(result) > 100

    def test_contains_fsg_notice(self):
        from research_pipeline.services.report_assembly import build_au_disclosures

        result = build_au_disclosures()
        assert "Financial Services Guide" in result

    def test_contains_asic_notice(self):
        from research_pipeline.services.report_assembly import build_au_disclosures

        result = build_au_disclosures()
        assert "ASIC" in result

    def test_super_fund_client_adds_super_disclosure(self):
        from research_pipeline.services.report_assembly import build_au_disclosures
        from research_pipeline.schemas.client_profile import ClientProfile

        cp = ClientProfile(client_type="super_fund", super_fund_type="balanced")
        result = build_au_disclosures(client_profile=cp)
        assert "APRA" in result
        assert "SPS 530" in result
        assert "Balanced" in result or "balanced" in result

    def test_tax_summary_included_when_provided(self):
        from research_pipeline.services.report_assembly import build_au_disclosures

        tax = {
            "estimated_tax_drag_bps": 45.0,
            "after_tax_yield_pct": 2.55,
            "income_tax_rate_pct": 15.0,
        }
        result = build_au_disclosures(tax_summary=tax)
        assert "45" in result
        assert "tax drag" in result.lower()

    def test_afsl_number_included(self):
        from research_pipeline.services.report_assembly import build_au_disclosures

        result = build_au_disclosures(afsl_number="000123456")
        assert "000123456" in result


# ---------------------------------------------------------------------------
# 12. PipelineConfig — client_profile field
# ---------------------------------------------------------------------------


class TestPipelineConfigClientProfile:
    def test_default_config_has_no_profile(self):
        from research_pipeline.config.loader import PipelineConfig

        cfg = PipelineConfig()
        assert cfg.client_profile is None

    def test_config_accepts_client_profile(self):
        from research_pipeline.config.loader import PipelineConfig
        from research_pipeline.schemas.client_profile import ClientProfile

        cp = ClientProfile(client_type="super_fund", super_fund_type="balanced")
        cfg = PipelineConfig(client_profile=cp)
        assert cfg.client_profile is not None
        assert cfg.client_profile.client_type == "super_fund"


# ---------------------------------------------------------------------------
# 13. PipelineEngine — Session 14 wiring
# ---------------------------------------------------------------------------


class TestEngineSession14Init:
    @pytest.fixture(scope="class")
    def engine(self, tmp_path_factory):
        from research_pipeline.pipeline.engine import PipelineEngine
        from research_pipeline.config.settings import Settings
        from research_pipeline.config.loader import load_pipeline_config

        tmp = tmp_path_factory.mktemp("engine_s14")
        (tmp / "prompts").mkdir()
        s = Settings(
            storage_dir=tmp,
            prompts_dir=tmp / "prompts",
            llm_model="gemini-1.5-flash",
        )
        return PipelineEngine(s, load_pipeline_config())

    def test_has_super_mandate_svc(self, engine):
        from research_pipeline.services.superannuation_mandate import SuperannuationMandateService

        assert isinstance(engine.super_mandate_svc, SuperannuationMandateService)

    def test_has_tax_svc(self, engine):
        from research_pipeline.services.australian_tax_service import AustralianTaxService

        assert isinstance(engine.tax_svc, AustralianTaxService)
