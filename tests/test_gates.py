"""Tests for pipeline gates — matching actual PipelineGates API."""

from __future__ import annotations


from research_pipeline.pipeline.gates import GateResult, PipelineGates
from research_pipeline.schemas.market_data import (
    ReconciliationField,
    ReconciliationReport,
    ReconciliationStatus,
)
from research_pipeline.schemas.claims import ClaimLedger, Claim, ClaimStatus, EvidenceClass
from research_pipeline.schemas.portfolio import (
    AssociateReviewResult,
    PublicationStatus,
    ReviewIssue,
)


class TestGateResult:
    def test_gate_result_pass(self):
        r = GateResult(stage=0, passed=True, reason="OK")
        assert r.passed is True
        assert "PASS" in repr(r)

    def test_gate_result_fail(self):
        r = GateResult(stage=1, passed=False, reason="Bad", blockers=["missing data"])
        assert r.passed is False
        assert r.blockers == ["missing data"]
        assert "FAIL" in repr(r)


class TestGate0Configuration:
    def test_all_valid(self):
        result = PipelineGates.gate_0_configuration(
            api_keys_valid=True,
            config_loaded=True,
            schemas_valid=True,
        )
        assert result.passed is True
        assert result.stage == 0

    def test_missing_api_keys(self):
        result = PipelineGates.gate_0_configuration(
            api_keys_valid=False,
            config_loaded=True,
            schemas_valid=True,
        )
        assert result.passed is False
        assert any("API keys" in b for b in result.blockers)

    def test_missing_config(self):
        result = PipelineGates.gate_0_configuration(
            api_keys_valid=True,
            config_loaded=False,
            schemas_valid=True,
        )
        assert result.passed is False

    def test_all_missing(self):
        result = PipelineGates.gate_0_configuration(
            api_keys_valid=False,
            config_loaded=False,
            schemas_valid=False,
        )
        assert result.passed is False
        assert len(result.blockers) == 3


class TestGate1Universe:
    def test_valid_universe(self):
        result = PipelineGates.gate_1_universe(universe=["NVDA", "AVGO", "TSM"])
        assert result.passed is True
        assert result.stage == 1

    def test_single_ticker_custom_style_universe(self):
        result = PipelineGates.gate_1_universe(universe=["AAPL"])
        assert result.passed is True
        assert result.stage == 1

    def test_empty_universe(self):
        result = PipelineGates.gate_1_universe(universe=[])
        assert result.passed is False

    def test_below_minimum(self):
        result = PipelineGates.gate_1_universe(universe=["NVDA"], min_tickers=3)
        assert result.passed is False

    def test_duplicates_blocked(self):
        result = PipelineGates.gate_1_universe(universe=["NVDA", "NVDA", "AVGO"])
        assert result.passed is False
        assert any("Duplicate" in b for b in result.blockers)


class TestGate2Ingestion:
    def test_all_ingested(self):
        ingest_results = [
            {"ticker": "NVDA", "price": 125.0},
            {"ticker": "AVGO", "price": 180.0},
        ]
        result = PipelineGates.gate_2_ingestion(
            ingest_results=ingest_results,
            universe=["NVDA", "AVGO"],
        )
        assert result.passed is True
        assert result.stage == 2

    def test_missing_ticker(self):
        ingest_results = [{"ticker": "NVDA", "price": 125.0}]
        result = PipelineGates.gate_2_ingestion(
            ingest_results=ingest_results,
            universe=["NVDA", "AVGO"],
        )
        assert result.passed is False
        assert any("AVGO" in b for b in result.blockers)

    def test_error_in_result(self):
        ingest_results = [
            {"ticker": "NVDA", "error": "API timeout"},
            {"ticker": "AVGO", "price": 180.0},
        ]
        result = PipelineGates.gate_2_ingestion(
            ingest_results=ingest_results,
            universe=["NVDA", "AVGO"],
        )
        assert result.passed is False


class TestGate3Reconciliation:
    def test_no_reds(self):
        report = ReconciliationReport(
            run_id="test",
            fields=[
                ReconciliationField(
                    field_name="price",
                    ticker="NVDA",
                    source_a="fmp",
                    source_a_value=125.0,
                    source_b="finnhub",
                    source_b_value=125.3,
                    divergence_pct=0.24,
                    status=ReconciliationStatus.GREEN,
                ),
            ],
        )
        result = PipelineGates.gate_3_reconciliation(report=report)
        assert result.passed is True

    def test_with_reds(self):
        report = ReconciliationReport(
            run_id="test",
            fields=[
                ReconciliationField(
                    field_name="target_median",
                    ticker="NVDA",
                    source_a="fmp",
                    source_a_value=150.0,
                    source_b="finnhub",
                    source_b_value=180.0,
                    divergence_pct=20.0,
                    status=ReconciliationStatus.RED,
                ),
            ],
        )
        result = PipelineGates.gate_3_reconciliation(report=report)
        assert result.passed is False
        assert any("RED" in b for b in result.blockers)

    def test_with_red_and_none_divergence_pct(self):
        """RED field with divergence_pct=None must not crash the gate (shows 'N/A')."""
        report = ReconciliationReport(
            run_id="test",
            fields=[
                ReconciliationField(
                    field_name="price",
                    ticker="NVDA",
                    source_a="fmp",
                    source_a_value=None,
                    source_b="finnhub",
                    source_b_value=None,
                    divergence_pct=None,
                    status=ReconciliationStatus.RED,
                ),
            ],
        )
        result = PipelineGates.gate_3_reconciliation(report=report)
        assert result.passed is False
        assert any("N/A" in b for b in result.blockers)


class TestGate5Evidence:
    def test_valid_ledger(self):
        ledger = ClaimLedger(
            run_id="test",
            claims=[
                Claim(
                    claim_id="CLM-001",
                    run_id="test",
                    ticker="NVDA",
                    claim_text="Revenue grew",
                    evidence_class=EvidenceClass.PRIMARY_FACT,
                    source_id="SRC-001",
                    status=ClaimStatus.PASS,
                ),
            ],
        )
        result = PipelineGates.gate_5_evidence(ledger=ledger)
        assert result.passed is True

    def test_empty_ledger(self):
        ledger = ClaimLedger(run_id="test", claims=[])
        result = PipelineGates.gate_5_evidence(ledger=ledger)
        assert result.passed is False

    def test_fail_claims_block(self):
        ledger = ClaimLedger(
            run_id="test",
            claims=[
                Claim(
                    claim_id="CLM-001",
                    run_id="test",
                    ticker="NVDA",
                    claim_text="Bad claim",
                    evidence_class=EvidenceClass.PRIMARY_FACT,
                    source_id="SRC-001",
                    status=ClaimStatus.FAIL,
                ),
            ],
        )
        result = PipelineGates.gate_5_evidence(ledger=ledger)
        assert result.passed is False


class TestGate11Review:
    def test_review_pass(self):
        review = AssociateReviewResult(
            run_id="test",
            status=PublicationStatus.PASS,
            issues=[],
        )
        result = PipelineGates.gate_11_review(result=review)
        assert result.passed is True

    def test_review_fail_blocks_gate(self):
        """PASS_WITH_DISCLOSURE is no longer a valid status; any non-PASS review must block."""
        review = AssociateReviewResult(
            run_id="test",
            status=PublicationStatus.FAIL,
            issues=[ReviewIssue(severity="minor", description="Stale data note")],
        )
        result = PipelineGates.gate_11_review(result=review)
        assert result.passed is False
        assert len(result.blockers) >= 1

    def test_review_fail(self):
        review = AssociateReviewResult(
            run_id="test",
            status=PublicationStatus.FAIL,
            issues=[ReviewIssue(severity="critical", description="Missing methodology tag")],
        )
        result = PipelineGates.gate_11_review(result=review)
        assert result.passed is False
        assert len(result.blockers) >= 1


class TestGate12Portfolio:
    def test_valid_portfolio(self):
        result = PipelineGates.gate_12_portfolio(
            variants_count=3,
            constraint_violations=None,
            review_passed=True,
        )
        assert result.passed is True

    def test_too_few_variants(self):
        result = PipelineGates.gate_12_portfolio(
            variants_count=2,
            constraint_violations=None,
            review_passed=True,
        )
        assert result.passed is False

    def test_constraint_violations(self):
        result = PipelineGates.gate_12_portfolio(
            variants_count=3,
            constraint_violations=["NVDA: weight 20% exceeds 15% max"],
            review_passed=True,
        )
        assert result.passed is False
