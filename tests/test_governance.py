"""Tests for governance services — mandate, ESG, investment committee, audit."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from research_pipeline.schemas.governance import (
    CommitteeVote,
    ESGConfig,
    ESGRating,
    MandateCheckResult,
    MandateConfig,
)
from research_pipeline.services.mandate_compliance import (
    MandateComplianceEngine,
    default_mandate,
)
from research_pipeline.services.esg_service import ESGService
from research_pipeline.services.investment_committee import InvestmentCommitteeService


# ── Mandate Compliance ─────────────────────────────────────────────────────


class TestMandateCompliance:
    def setup_method(self):
        self.engine = MandateComplianceEngine()

    def test_default_mandate_exists(self):
        mandate = default_mandate()
        assert mandate.mandate_id == "AI_INFRA_DEFAULT"
        assert mandate.max_single_name_pct == 15.0

    def test_compliant_portfolio(self):
        tickers = ["NVDA", "AVGO", "TSM", "EQIX", "CEG", "VST", "GEV", "PWR", "ETN"]
        weights = {t: 100 / len(tickers) for t in tickers}  # equal weight ~11.1%
        result = self.engine.check_compliance(
            run_id="RUN-001",
            weights=weights,
        )
        assert result.is_compliant is True
        assert len(result.violations) == 0

    def test_single_name_violation(self):
        weights = {"NVDA": 20.0, "AVGO": 10.0, "TSM": 70.0}
        result = self.engine.check_compliance(
            run_id="RUN-001",
            weights=weights,
        )
        assert result.is_compliant is False
        # TSM at 70% should violate single name limit
        violation_tickers = [v.description for v in result.violations]
        assert any("TSM" in d for d in violation_tickers) or any("NVDA" in d for d in violation_tickers)

    def test_too_few_positions(self):
        weights = {"NVDA": 35.0, "AVGO": 35.0, "TSM": 30.0}
        # Only 3 positions — below minimum of 8
        result = self.engine.check_compliance(
            run_id="RUN-001",
            weights=weights,
        )
        assert result.is_compliant is False

    def test_custom_mandate(self):
        mandate = MandateConfig(
            mandate_id="CUSTOM",
            max_single_name_pct=25.0,
            min_positions=3,
            max_positions=10,
        )
        engine = MandateComplianceEngine(mandate=mandate)
        weights = {"NVDA": 20.0, "AVGO": 30.0, "TSM": 50.0}
        result = engine.check_compliance(run_id="RUN-001", weights=weights)
        # AVGO at 30% exceeds 25%, TSM at 50% exceeds 25%
        assert result.is_compliant is False


# ── ESG Service ────────────────────────────────────────────────────────────


class TestESGService:
    def setup_method(self):
        self.svc = ESGService()

    def test_known_ticker_score(self):
        score = self.svc.get_score("NVDA")
        assert score.ticker == "NVDA"
        assert score.overall_rating == ESGRating.AA

    def test_unknown_ticker_defaults(self):
        score = self.svc.get_score("UNKNOWN_XYZ")
        assert score.overall_rating == ESGRating.BBB
        assert score.source == "default_unknown"

    def test_portfolio_scores(self):
        scores = self.svc.get_portfolio_scores(["NVDA", "MSFT", "META"])
        assert len(scores) == 3

    def test_exclusion_check_clean(self):
        excluded, reason = self.svc.check_exclusion("NVDA")
        assert excluded is False

    def test_exclusion_check_controversial(self):
        # META has controversy flag
        excluded, reason = self.svc.check_exclusion("META")
        assert excluded is True
        assert "controversy" in reason.lower()

    def test_exclusion_check_explicit_list(self):
        config = ESGConfig(exclusion_list=["BAD_CORP"])
        svc = ESGService(config=config)
        excluded, reason = svc.check_exclusion("BAD_CORP")
        assert excluded is True
        assert "exclusion list" in reason.lower()

    def test_portfolio_compliance_clean(self):
        result = self.svc.check_portfolio_esg_compliance(
            tickers=["NVDA", "MSFT", "GOOGL"]
        )
        assert result["compliant"] is True

    def test_portfolio_compliance_with_excluded(self):
        result = self.svc.check_portfolio_esg_compliance(
            tickers=["NVDA", "META"]
        )
        assert result["compliant"] is False
        assert len(result["excluded_tickers"]) > 0

    def test_weighted_esg_scores(self):
        weights = {"NVDA": 50.0, "MSFT": 50.0}
        result = self.svc.check_portfolio_esg_compliance(
            tickers=["NVDA", "MSFT"], weights=weights
        )
        assert "portfolio_weighted_esg" in result
        assert result["portfolio_weighted_esg"]["composite"] > 0

    def test_esg_summary_text(self):
        summary = self.svc.portfolio_esg_summary(["NVDA", "MSFT"])
        assert "NVDA" in summary
        assert "MSFT" in summary


# ── Investment Committee ───────────────────────────────────────────────────


class TestInvestmentCommittee:
    def setup_method(self):
        self.svc = InvestmentCommitteeService()

    def test_approve_clean_run(self):
        """All gates pass, mandate compliant, no risk issues → approve."""
        gate_results = {
            "total_stages": 15,
            "completed_stages": 15,
            "failed_gates": [],
        }
        mandate = MandateCheckResult(
            run_id="RUN-001", mandate_id="M-001", is_compliant=True
        )
        risk_summary = {"concentration_hhi": 1000, "max_single_position_weight": 12}
        review_result = {"status": "pass", "issues": []}

        record = self.svc.evaluate_and_vote(
            run_id="RUN-001",
            gate_results=gate_results,
            mandate_check=mandate,
            risk_summary=risk_summary,
            review_result=review_result,
        )

        assert record.is_approved is True
        assert record.quorum_met is True
        assert record.approve_count >= 3

    def test_reject_failed_gates(self):
        """Failed gates should cause chair rejection."""
        gate_results = {
            "total_stages": 15,
            "completed_stages": 10,
            "failed_gates": ["stage_5"],
        }
        record = self.svc.evaluate_and_vote(
            run_id="RUN-002",
            gate_results=gate_results,
        )
        # Chair should vote reject for failed gates
        chair_votes = [v for v in record.votes if v.member.role == "chair"]
        assert len(chair_votes) == 1
        assert chair_votes[0].vote == CommitteeVote.REJECT

    def test_reject_high_concentration(self):
        """Excessive concentration should cause risk officer rejection."""
        gate_results = {"total_stages": 15, "completed_stages": 15, "failed_gates": []}
        risk_summary = {"concentration_hhi": 3000, "max_single_position_weight": 10}

        record = self.svc.evaluate_and_vote(
            run_id="RUN-003",
            gate_results=gate_results,
            risk_summary=risk_summary,
        )
        # Risk officer should reject
        risk_votes = [v for v in record.votes if v.member.role == "risk_officer"]
        assert len(risk_votes) == 1
        assert risk_votes[0].vote == CommitteeVote.REJECT

    def test_reject_mandate_violation(self):
        """Mandate violations should cause compliance rejection."""
        from research_pipeline.schemas.governance import MandateRule, MandateViolation
        gate_results = {"total_stages": 15, "completed_stages": 15, "failed_gates": []}
        rule = MandateRule(rule_id="R-001", rule_type="max_weight", threshold=15.0)
        mandate = MandateCheckResult(
            run_id="RUN-004",
            mandate_id="M-001",
            is_compliant=False,
            violations=[MandateViolation(rule=rule, actual_value=20.0, description="NVDA exceeds 15%")],
        )

        record = self.svc.evaluate_and_vote(
            run_id="RUN-004",
            gate_results=gate_results,
            mandate_check=mandate,
        )
        compliance_votes = [v for v in record.votes if v.member.role == "compliance"]
        assert compliance_votes[0].vote == CommitteeVote.REJECT

    def test_approve_with_conditions(self):
        """Partial data should produce conditional approval."""
        gate_results = {"total_stages": 15, "completed_stages": 15, "failed_gates": []}
        # No risk summary — risk officer should approve with conditions
        record = self.svc.evaluate_and_vote(
            run_id="RUN-005",
            gate_results=gate_results,
        )
        has_conditions = any(
            v.vote == CommitteeVote.APPROVE_WITH_CONDITIONS for v in record.votes
        )
        assert has_conditions is True

    def test_audit_trail_creation(self):
        trail = self.svc.create_audit_trail("RUN-006")
        assert trail.run_id == "RUN-006"
        assert len(trail.entries) == 0

    def test_record_human_override(self):
        trail = self.svc.create_audit_trail("RUN-007")
        entry = self.svc.record_human_override(
            audit_trail=trail,
            stage=11,
            original_status="fail",
            override_status="pass",
            approver="john.smith",
            reason="Manual review confirms quality",
        )
        assert len(trail.entries) == 1
        assert trail.entries[0].action == "override"
        assert trail.entries[0].actor == "john.smith"
