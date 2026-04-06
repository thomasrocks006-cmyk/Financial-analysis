"""Tests for new Pydantic schemas — governance and performance."""

from __future__ import annotations

from datetime import datetime, timezone


from research_pipeline.schemas.governance import (
    AuditEntry,
    AuditTrail,
    CommitteeMember,
    CommitteeRecord,
    CommitteeVote,
    CommitteeVoteRecord,
    ESGConfig,
    ESGRating,
    ESGScore,
    MandateCheckResult,
    MandateConfig,
    MandateRule,
    MandateViolation,
)
from research_pipeline.schemas.performance import (
    BHBAttribution,
    BenchmarkComparison,
    DrawdownAnalysis,
    FactorAttribution,
    FactorExposure,
    LiquidityProfile,
    PortfolioSnapshot,
    ThesisRecord,
    ThesisStatus,
    VaRResult,
)


# ── Governance Schemas ─────────────────────────────────────────────────────


class TestCommitteeSchemas:
    def test_committee_vote_enum(self):
        assert CommitteeVote.APPROVE.value == "approve"
        assert CommitteeVote.REJECT.value == "reject"
        assert CommitteeVote.ABSTAIN.value == "abstain"

    def test_committee_member_creation(self):
        member = CommitteeMember(member_id="IC-1", role="chair", name="Test Chair")
        assert member.member_id == "IC-1"
        assert member.role == "chair"

    def test_committee_vote_record(self):
        member = CommitteeMember(member_id="IC-1", role="pm", name="PM")
        record = CommitteeVoteRecord(
            member=member,
            vote=CommitteeVote.APPROVE,
            rationale="Good analysis",
        )
        assert record.vote == CommitteeVote.APPROVE
        assert record.rationale == "Good analysis"
        assert isinstance(record.timestamp, datetime)

    def test_committee_record_approve_count(self):
        members = [
            CommitteeMember(member_id=f"IC-{i}", role="analyst", name=f"A{i}") for i in range(3)
        ]
        votes = [
            CommitteeVoteRecord(member=members[0], vote=CommitteeVote.APPROVE),
            CommitteeVoteRecord(member=members[1], vote=CommitteeVote.APPROVE_WITH_CONDITIONS),
            CommitteeVoteRecord(member=members[2], vote=CommitteeVote.REJECT),
        ]
        record = CommitteeRecord(
            record_id="IC-TEST-001",
            run_id="RUN-001",
            votes=votes,
            outcome=CommitteeVote.APPROVE,
            quorum_met=True,
        )
        assert record.approve_count == 2
        assert record.reject_count == 1
        assert record.is_approved is True

    def test_committee_record_not_approved_without_quorum(self):
        record = CommitteeRecord(
            record_id="IC-TEST-002",
            run_id="RUN-002",
            votes=[],
            outcome=CommitteeVote.APPROVE,
            quorum_met=False,
        )
        assert record.is_approved is False

    def test_committee_record_rejected(self):
        record = CommitteeRecord(
            record_id="IC-TEST-003",
            run_id="RUN-003",
            outcome=CommitteeVote.REJECT,
            quorum_met=True,
        )
        assert record.is_approved is False


class TestMandateSchemas:
    def test_mandate_rule_creation(self):
        rule = MandateRule(
            rule_id="R-001",
            rule_type="max_weight",
            description="Max single name 15%",
            threshold=15.0,
        )
        assert rule.hard_limit is True
        assert rule.threshold == 15.0

    def test_mandate_config_defaults(self):
        config = MandateConfig(mandate_id="M-001")
        assert config.max_single_name_pct == 15.0
        assert config.max_sector_pct == 40.0
        assert config.min_positions == 8
        assert config.max_positions == 25

    def test_mandate_violation(self):
        rule = MandateRule(rule_id="R-001", rule_type="max_weight", threshold=15.0)
        violation = MandateViolation(
            rule=rule,
            actual_value=18.5,
            breach_severity="hard",
            description="NVDA weight 18.5% exceeds 15% limit",
        )
        assert violation.actual_value == 18.5

    def test_mandate_check_result_compliant(self):
        result = MandateCheckResult(run_id="RUN-001", mandate_id="M-001", is_compliant=True)
        assert result.is_compliant is True
        assert len(result.violations) == 0

    def test_mandate_check_result_non_compliant(self):
        rule = MandateRule(rule_id="R-001", rule_type="max_weight", threshold=15.0)
        result = MandateCheckResult(
            run_id="RUN-001",
            mandate_id="M-001",
            is_compliant=False,
            violations=[MandateViolation(rule=rule, actual_value=20.0)],
        )
        assert result.is_compliant is False
        assert len(result.violations) == 1


class TestESGSchemas:
    def test_esg_rating_enum(self):
        assert ESGRating.AAA.value == "AAA"
        assert ESGRating.CCC.value == "CCC"
        ratings = list(ESGRating)
        assert len(ratings) == 7

    def test_esg_score_defaults(self):
        score = ESGScore(ticker="NVDA")
        assert score.overall_rating == ESGRating.BBB
        assert score.environmental_score == 5.0
        assert score.controversy_flag is False

    def test_esg_config_defaults(self):
        config = ESGConfig()
        assert config.exclude_below_rating == ESGRating.CCC
        assert config.exclude_controversial is True
        assert config.min_esg_score == 3.0


class TestAuditTrailSchema:
    def test_audit_entry_creation(self):
        entry = AuditEntry(
            entry_id="AUD-001",
            run_id="RUN-001",
            action="gate_check",
            stage=5,
        )
        assert entry.actor == "system"

    def test_audit_trail_add_entry(self):
        trail = AuditTrail(run_id="RUN-001")
        trail.add_entry(action="gate_check", stage=5, outcome="pass")
        assert len(trail.entries) == 1
        assert trail.entries[0].entry_id == "AUD-RUN-001-0001"
        assert trail.entries[0].action == "gate_check"

    def test_audit_trail_multiple_entries(self):
        trail = AuditTrail(run_id="RUN-001")
        trail.add_entry(action="gate_check", stage=5)
        trail.add_entry(action="committee_vote")
        trail.add_entry(action="publication", actor="human_approver")
        assert len(trail.entries) == 3
        assert trail.entries[2].actor == "human_approver"


# ── Performance Schemas ────────────────────────────────────────────────────


class TestPortfolioSnapshot:
    def test_snapshot_creation(self):
        snap = PortfolioSnapshot(
            run_id="RUN-001",
            variant_name="balanced",
            positions={"NVDA": 12.0, "AVGO": 10.0},
            prices={"NVDA": 125.50, "AVGO": 180.75},
        )
        assert snap.nav == 100.0
        assert len(snap.positions) == 2


class TestBHBAttribution:
    def test_bhb_creation(self):
        now = datetime.now(timezone.utc)
        attr = BHBAttribution(
            run_id="RUN-001",
            period_start=now,
            period_end=now,
            total_portfolio_return_pct=12.5,
            total_benchmark_return_pct=10.0,
            excess_return_pct=2.5,
            allocation_effect_pct=1.0,
            selection_effect_pct=1.2,
            interaction_effect_pct=0.3,
        )
        assert attr.excess_return_pct == 2.5


class TestFactorSchemas:
    def test_factor_exposure(self):
        fe = FactorExposure(ticker="NVDA", market_beta=1.3, momentum_loading=0.5)
        assert fe.market_beta == 1.3

    def test_factor_attribution(self):
        now = datetime.now(timezone.utc)
        fa = FactorAttribution(
            run_id="RUN-001",
            period_start=now,
            period_end=now,
            total_return_pct=15.0,
            market_contribution_pct=10.0,
            residual_alpha_pct=3.0,
        )
        assert fa.residual_alpha_pct == 3.0


class TestBenchmarkComparison:
    def test_benchmark_creation(self):
        bc = BenchmarkComparison(
            run_id="RUN-001",
            benchmark_name="SPY",
            tracking_error_pct=5.2,
            information_ratio=0.45,
        )
        assert bc.benchmark_name == "SPY"


class TestThesisSchemas:
    def test_thesis_status_enum(self):
        assert ThesisStatus.ACTIVE.value == "active"
        assert ThesisStatus.INVALIDATED.value == "invalidated"

    def test_thesis_record(self):
        tr = ThesisRecord(
            thesis_id="TH-001",
            run_id="RUN-001",
            ticker="NVDA",
            thesis_text="NVIDIA data center revenue growth thesis",
            price_at_creation=125.50,
        )
        assert tr.status == ThesisStatus.ACTIVE
        assert tr.claim_ids == []


class TestVaRSchemas:
    def test_var_result(self):
        vr = VaRResult(
            run_id="RUN-001",
            method="parametric",
            confidence_level=0.95,
            var_pct=2.5,
            cvar_pct=3.2,
        )
        assert vr.var_pct == 2.5

    def test_drawdown_analysis(self):
        da = DrawdownAnalysis(
            run_id="RUN-001",
            max_drawdown_pct=15.3,
            underwater_days=45,
        )
        assert da.max_drawdown_pct == 15.3


class TestLiquidityProfile:
    def test_liquidity_profile(self):
        lp = LiquidityProfile(
            ticker="NVDA",
            avg_daily_volume=50_000_000,
            days_to_liquidate=0.3,
            liquidity_score=10.0,
        )
        assert lp.liquidity_score == 10.0
