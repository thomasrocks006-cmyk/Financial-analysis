"""Tests for Pydantic schema models — matching actual implementations."""

from __future__ import annotations

from datetime import datetime

import pytest

from research_pipeline.schemas.claims import (
    Claim,
    ClaimLedger,
    ClaimStatus,
    ConfidenceLevel,
    EvidenceClass,
    Source,
    SourceTier,
)
from research_pipeline.schemas.market_data import (
    MarketSnapshot,
    ReconciliationField,
    ReconciliationReport,
    ReconciliationStatus,
    DataQualityReport,
)
from research_pipeline.schemas.portfolio import (
    EntryQuality,
    FourBoxOutput,
    PortfolioPosition,
    PortfolioVariant,
    ThesisIntegrity,
    ValuationCard,
    ValuationSnapshot,
    ReturnScenario,
    RedTeamAssessment,
    FalsificationTest,
    AssociateReviewResult,
    PublicationStatus,
)
from research_pipeline.schemas.registry import (
    RunRecord,
    RunStatus,
    SelfAudit,
    GoldenTest,
    HumanOverride,
)
from research_pipeline.schemas.reports import (
    FinalReport,
    ReportSection,
    StockCard,
    RiskPacket,
    ScenarioResult,
    DiffSummary,
)


class TestClaims:
    """Tests for claim schemas."""

    def test_claim_creation(self, sample_claim):
        claim = Claim(**sample_claim)
        assert claim.claim_id == "CLM-NVDA-001"
        assert claim.ticker == "NVDA"
        assert claim.evidence_class == EvidenceClass.PRIMARY_FACT
        assert claim.confidence == ConfidenceLevel.HIGH
        assert claim.status == ClaimStatus.PASS

    def test_claim_invalid_tier(self):
        """SourceTier only allows 1-4."""
        with pytest.raises(Exception):
            SourceTier(5)

    def test_claim_confidence_levels(self, sample_claim):
        # high
        sample_claim["confidence"] = "high"
        claim = Claim(**sample_claim)
        assert claim.confidence == ConfidenceLevel.HIGH

        # medium
        sample_claim["confidence"] = "medium"
        claim = Claim(**sample_claim)
        assert claim.confidence == ConfidenceLevel.MEDIUM

        # low
        sample_claim["confidence"] = "low"
        claim = Claim(**sample_claim)
        assert claim.confidence == ConfidenceLevel.LOW

    def test_claim_ledger(self, sample_claim):
        claims = [Claim(**sample_claim)]
        ledger = ClaimLedger(run_id="test", claims=claims)
        assert len(ledger.claims) == 1
        assert ledger.fail_count == 0
        assert ledger.pass_count == 1

    def test_claim_ledger_fail_count(self, sample_claim):
        sample_claim["status"] = "fail"
        claims = [Claim(**sample_claim)]
        ledger = ClaimLedger(run_id="test", claims=claims)
        assert ledger.fail_count == 1
        assert ledger.has_unresolved_fails() is True

    def test_claim_ledger_caveat_count(self, sample_claim):
        sample_claim["status"] = "caveat"
        claims = [Claim(**sample_claim)]
        ledger = ClaimLedger(run_id="test", claims=claims)
        assert ledger.caveat_count == 1

    def test_claim_ledger_get_claims_for_ticker(self, sample_claim):
        claims = [Claim(**sample_claim)]
        ledger = ClaimLedger(run_id="test", claims=claims)
        nvda_claims = ledger.get_claims_for_ticker("NVDA")
        assert len(nvda_claims) == 1
        assert ledger.get_claims_for_ticker("AAPL") == []

    def test_evidence_classes(self):
        expected = {"primary_fact", "mgmt_guidance", "independent_confirmation",
                    "consensus_datapoint", "house_inference"}
        actual = {e.value for e in EvidenceClass}
        assert actual == expected

    def test_source_tier_values(self):
        values = [t.value for t in SourceTier]
        assert values == [1, 2, 3, 4]

    def test_source_model(self):
        source = Source(
            source_id="SRC-001",
            url="https://sec.gov/nvda-10k",
            source_type="10-K",
            tier=SourceTier.TIER_1_PRIMARY,
        )
        assert source.tier == SourceTier.TIER_1_PRIMARY


class TestMarketData:
    """Tests for market data schemas."""

    def test_market_snapshot(self, sample_market_snapshot):
        snap = MarketSnapshot(**sample_market_snapshot)
        assert snap.ticker == "NVDA"
        assert snap.price == 125.50
        assert snap.source == "fmp"

    def test_reconciliation_field(self):
        field = ReconciliationField(
            field_name="price",
            ticker="NVDA",
            source_a="fmp",
            source_a_value=125.50,
            source_b="finnhub",
            source_b_value=125.80,
            divergence_pct=0.24,
            status=ReconciliationStatus.GREEN,
        )
        assert field.status == ReconciliationStatus.GREEN
        assert field.divergence_pct == 0.24

    def test_reconciliation_report_counts(self):
        fields = [
            ReconciliationField(
                field_name="price", ticker="NVDA",
                source_a="fmp", source_a_value=125.50,
                source_b="finnhub", source_b_value=125.80,
                divergence_pct=0.24, status=ReconciliationStatus.GREEN,
            ),
            ReconciliationField(
                field_name="target", ticker="NVDA",
                source_a="fmp", source_a_value=150.0,
                source_b="finnhub", source_b_value=180.0,
                divergence_pct=20.0, status=ReconciliationStatus.RED,
            ),
            ReconciliationField(
                field_name="eps", ticker="NVDA",
                source_a="fmp", source_a_value=5.5,
                source_b="finnhub", source_b_value=5.8,
                divergence_pct=5.5, status=ReconciliationStatus.AMBER,
            ),
        ]
        report = ReconciliationReport(run_id="test", fields=fields)
        assert report.red_count == 1
        assert report.amber_count == 1
        assert report.has_blocking_reds() is True
        assert len(report.get_reds()) == 1

    def test_data_quality_report_passing(self):
        report = DataQualityReport(run_id="test")
        assert report.is_passing() is True

    def test_data_quality_report_failing(self):
        report = DataQualityReport(run_id="test", schema_valid=False)
        assert report.is_passing() is False


class TestPortfolio:
    """Tests for portfolio schemas."""

    def test_portfolio_position(self):
        pos = PortfolioPosition(
            ticker="NVDA",
            weight_pct=12.5,
            subtheme="compute",
            entry_quality=EntryQuality.STRONG,
            thesis_integrity=ThesisIntegrity.ROBUST,
        )
        assert pos.ticker == "NVDA"
        assert pos.weight_pct == 12.5

    def test_portfolio_variant_no_excess_single_stock(self):
        positions = [
            PortfolioPosition(
                ticker="NVDA", weight_pct=20.0, subtheme="compute",
                entry_quality=EntryQuality.STRONG, thesis_integrity=ThesisIntegrity.ROBUST,
            ),
            PortfolioPosition(
                ticker="CEG", weight_pct=10.0, subtheme="power",
                entry_quality=EntryQuality.STRONG, thesis_integrity=ThesisIntegrity.ROBUST,
            ),
        ]
        variant = PortfolioVariant(variant_name="test", run_id="test", positions=positions)
        issues = variant.validate_constraints()
        stock_issues = [i for i in issues if "15%" in i]
        assert len(stock_issues) > 0

    def test_portfolio_variant_subtheme_concentration(self):
        # Compute at 30% (under 40% limit) — should pass
        positions = [
            PortfolioPosition(
                ticker="NVDA", weight_pct=15.0, subtheme="compute",
                entry_quality=EntryQuality.STRONG, thesis_integrity=ThesisIntegrity.ROBUST,
            ),
            PortfolioPosition(
                ticker="AVGO", weight_pct=15.0, subtheme="compute",
                entry_quality=EntryQuality.STRONG, thesis_integrity=ThesisIntegrity.ROBUST,
            ),
        ]
        variant = PortfolioVariant(variant_name="test", run_id="test", positions=positions)
        issues = variant.validate_constraints()
        # Compute total 30% < 40% limit, so no subtheme violation
        subtheme_issues = [i for i in issues if "Subtheme" in i]
        assert len(subtheme_issues) == 0

    def test_portfolio_variant_subtheme_over_limit(self):
        # Compute at 45% (over 40% limit)
        positions = [
            PortfolioPosition(
                ticker="NVDA", weight_pct=15.0, subtheme="compute",
                entry_quality=EntryQuality.STRONG, thesis_integrity=ThesisIntegrity.ROBUST,
            ),
            PortfolioPosition(
                ticker="AVGO", weight_pct=15.0, subtheme="compute",
                entry_quality=EntryQuality.STRONG, thesis_integrity=ThesisIntegrity.ROBUST,
            ),
            PortfolioPosition(
                ticker="TSM", weight_pct=15.0, subtheme="compute",
                entry_quality=EntryQuality.ACCEPTABLE, thesis_integrity=ThesisIntegrity.MODERATE,
            ),
        ]
        variant = PortfolioVariant(variant_name="test", run_id="test", positions=positions)
        issues = variant.validate_constraints()
        subtheme_issues = [i for i in issues if "compute" in i.lower() and "Subtheme" in i]
        assert len(subtheme_issues) > 0

    def test_fragile_thesis_flagged(self):
        positions = [
            PortfolioPosition(
                ticker="NVDA", weight_pct=10.0, subtheme="compute",
                entry_quality=EntryQuality.STRONG, thesis_integrity=ThesisIntegrity.FRAGILE,
            ),
        ]
        variant = PortfolioVariant(variant_name="test", run_id="test", positions=positions)
        issues = variant.validate_constraints()
        assert any("FRAGILE" in i for i in issues)

    def test_valuation_snapshot(self):
        snap = ValuationSnapshot(
            ticker="NVDA", price=125.50, market_cap=3.08e12,
            trailing_pe=55.2, forward_pe=32.1,
        )
        assert snap.price == 125.50

    def test_return_scenario(self):
        scenario = ReturnScenario(
            label="bull", revenue_cagr_pct=0.40, exit_multiple=35.0,
            exit_multiple_rationale="AI dominance premium",
        )
        assert scenario.label == "bull"

    def test_four_box_output(self):
        fb = FourBoxOutput(
            ticker="NVDA", company_name="NVIDIA", analyst_role="compute",
            box1_verified_facts="Revenue grew 400%",
            box4_analyst_judgment="Strong conviction",
        )
        assert fb.ticker == "NVDA"
        assert fb.analyst_role == "compute"

    def test_red_team_assessment(self):
        rta = RedTeamAssessment(
            target="NVDA", run_id="test",
            what_is_priced_in="40% CAGR for 3 years",
            falsification_tests=[
                FalsificationTest(
                    test_name="Capex slowdown",
                    assumption_challenged="Hyperscaler spend continues",
                    outcome_if_wrong="breaks",
                ),
            ],
            thesis_integrity=ThesisIntegrity.ROBUST,
        )
        assert len(rta.falsification_tests) == 1
        assert rta.thesis_integrity == ThesisIntegrity.ROBUST

    def test_associate_review_result_publishable(self):
        review = AssociateReviewResult(run_id="test", status=PublicationStatus.PASS)
        assert review.is_publishable is True

    def test_associate_review_result_not_publishable(self):
        review = AssociateReviewResult(run_id="test", status=PublicationStatus.FAIL)
        assert review.is_publishable is False


class TestRegistry:
    """Tests for run registry schemas."""

    def test_run_record(self):
        record = RunRecord(
            run_id="RUN-2024-001",
            config_hash="abc123",
            universe=["NVDA", "AVGO"],
            status=RunStatus.RUNNING,
        )
        assert record.status == RunStatus.RUNNING
        assert len(record.universe) == 2

    def test_run_status_values(self):
        values = {s.value for s in RunStatus}
        assert "initialized" in values
        assert "running" in values
        assert "completed" in values
        assert "failed" in values
        assert "published" in values

    def test_self_audit(self):
        audit = SelfAudit(run_id="RUN-2024-001")
        assert "public-source data" in audit.institutional_ceiling_statement.lower()

    def test_golden_test_model(self):
        gt = GoldenTest(
            test_id="GT-001",
            category="claim_classification",
            input_fixture={"claim_text": "Revenue was $35.1B"},
            expected_output_rule="status == pass",
        )
        assert gt.test_id == "GT-001"
        assert gt.passed is None  # not yet run

    def test_human_override(self):
        override = HumanOverride(
            override_id="OVR-001",
            run_id="RUN-001",
            approver="thomas@jpam.com",
            stage="gate_3",
            reason="Manual review confirmed data is accurate",
            original_status="FAIL",
            override_status="PASS",
        )
        assert override.approver == "thomas@jpam.com"


class TestReports:
    """Tests for report schemas."""

    def test_report_section(self):
        section = ReportSection(
            section_name="executive_summary",
            content="This is a test.",
            approved=True,
            source_stage=13,
        )
        assert section.approved is True

    def test_final_report(self):
        sections = [
            ReportSection(section_name="executive_summary", content="Test.", approved=True),
            ReportSection(section_name="methodology", content="Test.", approved=True),
        ]
        report = FinalReport(
            run_id="RUN-2024-001",
            title="AI Infrastructure Research",
            sections=sections,
        )
        assert len(report.sections) == 2
        assert report.get_section("executive_summary") is not None
        assert report.get_section("nonexistent") is None

    def test_stock_card(self):
        card = StockCard(
            ticker="NVDA", company_name="NVIDIA Corporation", subtheme="compute",
            four_box_summary="Strong", valuation_summary="Fair",
            entry_quality="strong", thesis_integrity="robust",
        )
        assert card.ticker == "NVDA"

    def test_risk_packet(self):
        packet = RiskPacket(run_id="test")
        assert packet.correlation_matrix == {}
        assert packet.scenario_results == []

    def test_scenario_result(self):
        sr = ScenarioResult(
            ticker="NVDA", scenario_name="AI Capex Slowdown",
            estimated_impact_pct=-15.0, severity="high",
        )
        assert sr.severity == "high"

    def test_diff_summary(self):
        ds = DiffSummary(
            ticker="NVDA", field="price",
            previous_value=120.0, current_value=130.0,
            change_pct=8.33, flagged=True,
        )
        assert ds.flagged is True
