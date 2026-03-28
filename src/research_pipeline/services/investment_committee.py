"""Investment Committee Service — simulate IC voting, record keeping, governance."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from research_pipeline.schemas.governance import (
    AuditEntry,
    AuditTrail,
    CommitteeMember,
    CommitteeRecord,
    CommitteeVote,
    CommitteeVoteRecord,
    MandateCheckResult,
)

logger = logging.getLogger(__name__)


# ── Default Committee Members ──────────────────────────────────────────────

DEFAULT_COMMITTEE = [
    CommitteeMember(member_id="IC-CHAIR", role="chair", name="IC Chair (System)"),
    CommitteeMember(member_id="IC-PM", role="pm", name="Portfolio Manager (System)"),
    CommitteeMember(member_id="IC-RISK", role="risk_officer", name="Risk Officer (System)"),
    CommitteeMember(member_id="IC-ANALYST", role="analyst", name="Lead Analyst (System)"),
    CommitteeMember(member_id="IC-COMPLIANCE", role="compliance", name="Compliance Officer (System)"),
]


class InvestmentCommitteeService:
    """Simulate investment committee approval workflow — no LLM.

    Evaluates pipeline outputs (gate results, mandate compliance, risk metrics)
    and generates committee voting records. Designed for human override injection.
    """

    def __init__(
        self,
        members: list[CommitteeMember] | None = None,
        required_votes: int = 3,
    ):
        self.members = members or DEFAULT_COMMITTEE
        self.required_votes = required_votes

    def evaluate_and_vote(
        self,
        run_id: str,
        gate_results: dict[str, Any],
        mandate_check: MandateCheckResult | None = None,
        risk_summary: dict[str, Any] | None = None,
        review_result: dict[str, Any] | None = None,
    ) -> CommitteeRecord:
        """Evaluate pipeline outputs and generate committee votes.

        Each committee member votes based on their role and the relevant data:
        - Chair: overall process completeness
        - PM: portfolio quality / conviction
        - Risk Officer: risk limit compliance
        - Analyst: research quality / evidence strength
        - Compliance: mandate compliance
        """
        record_id = f"IC-{run_id}-{uuid.uuid4().hex[:6]}"
        votes: list[CommitteeVoteRecord] = []
        agenda_items: list[str] = [
            f"Review and approval of research pipeline run {run_id}",
            "Gate compliance assessment",
            "Mandate compliance review",
            "Risk limit evaluation",
        ]

        for member in self.members:
            vote, rationale, conditions = self._member_vote(
                member=member,
                gate_results=gate_results,
                mandate_check=mandate_check,
                risk_summary=risk_summary,
                review_result=review_result,
            )
            votes.append(CommitteeVoteRecord(
                member=member,
                vote=vote,
                rationale=rationale,
                conditions=conditions,
            ))

        # Determine outcome
        approve_count = sum(
            1 for v in votes
            if v.vote in (CommitteeVote.APPROVE, CommitteeVote.APPROVE_WITH_CONDITIONS)
        )
        reject_count = sum(1 for v in votes if v.vote == CommitteeVote.REJECT)
        quorum_met = len(votes) >= self.required_votes

        # Outcome logic
        if not quorum_met:
            outcome = CommitteeVote.REJECT
            minutes = "Quorum not met — decision deferred."
        elif reject_count >= 2:
            outcome = CommitteeVote.REJECT
            minutes = f"Rejected by committee ({reject_count} reject votes)."
        elif approve_count >= self.required_votes:
            has_conditions = any(
                v.vote == CommitteeVote.APPROVE_WITH_CONDITIONS for v in votes
            )
            outcome = CommitteeVote.APPROVE_WITH_CONDITIONS if has_conditions else CommitteeVote.APPROVE
            all_conditions = []
            for v in votes:
                all_conditions.extend(v.conditions)
            cond_text = (" Conditions: " + "; ".join(all_conditions)) if all_conditions else ""
            minutes = f"Approved by committee ({approve_count}/{len(votes)} votes).{cond_text}"
        else:
            outcome = CommitteeVote.REJECT
            minutes = f"Insufficient approvals ({approve_count}/{self.required_votes} required)."

        record = CommitteeRecord(
            record_id=record_id,
            run_id=run_id,
            agenda_items=agenda_items,
            votes=votes,
            outcome=outcome,
            conditions=[c for v in votes for c in v.conditions],
            minutes=minutes,
            quorum_met=quorum_met,
            required_votes=self.required_votes,
        )

        logger.info(
            "IC decision for %s: %s (%d approve, %d reject, quorum=%s)",
            run_id, outcome.value, approve_count, reject_count, quorum_met,
        )
        return record

    def _member_vote(
        self,
        member: CommitteeMember,
        gate_results: dict[str, Any],
        mandate_check: MandateCheckResult | None,
        risk_summary: dict[str, Any] | None,
        review_result: dict[str, Any] | None,
    ) -> tuple[CommitteeVote, str, list[str]]:
        """Generate a vote for a specific committee member based on role."""
        conditions: list[str] = []

        if member.role == "chair":
            return self._chair_vote(gate_results, conditions)
        elif member.role == "pm":
            return self._pm_vote(gate_results, review_result, conditions)
        elif member.role == "risk_officer":
            return self._risk_vote(risk_summary, conditions)
        elif member.role == "analyst":
            return self._analyst_vote(gate_results, review_result, conditions)
        elif member.role == "compliance":
            return self._compliance_vote(mandate_check, conditions)
        else:
            return CommitteeVote.ABSTAIN, f"Unknown role: {member.role}", []

    def _chair_vote(
        self, gate_results: dict[str, Any], conditions: list[str]
    ) -> tuple[CommitteeVote, str, list[str]]:
        """Chair evaluates overall process completeness."""
        # Count completed stages
        total_stages = gate_results.get("total_stages", 15)
        completed = gate_results.get("completed_stages", 0)
        failed_gates = gate_results.get("failed_gates", [])

        if failed_gates:
            return (
                CommitteeVote.REJECT,
                f"Pipeline has {len(failed_gates)} failed gates: {failed_gates}",
                [],
            )
        if completed < total_stages:
            conditions.append(f"Only {completed}/{total_stages} stages completed")
            return (
                CommitteeVote.APPROVE_WITH_CONDITIONS,
                f"{completed}/{total_stages} stages completed",
                conditions,
            )
        return CommitteeVote.APPROVE, "All stages completed successfully", []

    def _pm_vote(
        self,
        gate_results: dict[str, Any],
        review_result: dict[str, Any] | None,
        conditions: list[str],
    ) -> tuple[CommitteeVote, str, list[str]]:
        """PM evaluates portfolio quality."""
        if review_result and review_result.get("status") == "fail":
            return CommitteeVote.REJECT, "Associate reviewer rejected", []

        if review_result and review_result.get("status") == "pass_with_disclosure":
            conditions.append("Reviewer passed with disclosure — address disclosures")
            return CommitteeVote.APPROVE_WITH_CONDITIONS, "Approved with disclosure conditions", conditions

        return CommitteeVote.APPROVE, "Portfolio quality satisfactory", []

    def _risk_vote(
        self,
        risk_summary: dict[str, Any] | None,
        conditions: list[str],
    ) -> tuple[CommitteeVote, str, list[str]]:
        """Risk officer evaluates risk metrics."""
        if not risk_summary:
            conditions.append("No risk assessment available — request risk engine output")
            return CommitteeVote.APPROVE_WITH_CONDITIONS, "Risk data unavailable", conditions

        hhi = risk_summary.get("concentration_hhi", 0)
        max_weight = risk_summary.get("max_single_position_weight", 0)

        if hhi > 2500:
            return CommitteeVote.REJECT, f"Concentration HHI={hhi} exceeds 2500 limit", []
        if max_weight > 20:
            return CommitteeVote.REJECT, f"Max single position {max_weight}% exceeds 20% limit", []

        if hhi > 1800:
            conditions.append(f"HHI={hhi} approaching limit — monitor concentration")
        if max_weight > 15:
            conditions.append(f"Max weight {max_weight}% — consider trimming")

        if conditions:
            return CommitteeVote.APPROVE_WITH_CONDITIONS, "Risk within limits but elevated", conditions
        return CommitteeVote.APPROVE, "Risk metrics within acceptable limits", []

    def _analyst_vote(
        self,
        gate_results: dict[str, Any],
        review_result: dict[str, Any] | None,
        conditions: list[str],
    ) -> tuple[CommitteeVote, str, list[str]]:
        """Analyst evaluates research quality."""
        evidence_gate = gate_results.get("stage_5_gate", "unknown")
        if evidence_gate == "fail":
            return CommitteeVote.REJECT, "Evidence gate (Stage 5) failed — insufficient sourcing", []

        if review_result and review_result.get("issues"):
            issue_count = len(review_result["issues"])
            if issue_count > 3:
                return CommitteeVote.REJECT, f"Review raised {issue_count} issues — too many", []
            conditions.append(f"Address {issue_count} reviewer issues before publication")
            return CommitteeVote.APPROVE_WITH_CONDITIONS, "Research quality acceptable with issues", conditions

        return CommitteeVote.APPROVE, "Research quality satisfactory", []

    def _compliance_vote(
        self,
        mandate_check: MandateCheckResult | None,
        conditions: list[str],
    ) -> tuple[CommitteeVote, str, list[str]]:
        """Compliance evaluates mandate adherence."""
        if not mandate_check:
            conditions.append("No mandate compliance check performed — require pre-publication check")
            return CommitteeVote.APPROVE_WITH_CONDITIONS, "Mandate check not available", conditions

        if not mandate_check.is_compliant:
            violations = [v.description for v in mandate_check.violations]
            return (
                CommitteeVote.REJECT,
                f"Mandate violations: {'; '.join(violations)}",
                [],
            )

        if mandate_check.warnings:
            conditions.extend(mandate_check.warnings)
            return CommitteeVote.APPROVE_WITH_CONDITIONS, "Compliant with warnings", conditions

        return CommitteeVote.APPROVE, "Portfolio is mandate-compliant", []

    # ── Audit Trail ────────────────────────────────────────────────────
    def create_audit_trail(self, run_id: str) -> AuditTrail:
        """Create a new audit trail for a run."""
        return AuditTrail(run_id=run_id)

    def record_committee_decision(
        self, audit_trail: AuditTrail, committee_record: CommitteeRecord
    ) -> None:
        """Add committee decision to audit trail."""
        audit_trail.add_entry(
            action="committee_vote",
            actor=committee_record.record_id,
            details={
                "outcome": committee_record.outcome.value,
                "approve_count": committee_record.approve_count,
                "reject_count": committee_record.reject_count,
                "quorum_met": committee_record.quorum_met,
                "conditions": committee_record.conditions,
            },
            outcome=committee_record.outcome.value,
        )

    def record_human_override(
        self,
        audit_trail: AuditTrail,
        stage: int,
        original_status: str,
        override_status: str,
        approver: str,
        reason: str,
    ) -> AuditEntry:
        """Record a human override in the audit trail."""
        audit_trail.add_entry(
            action="override",
            stage=stage,
            actor=approver,
            details={
                "original_status": original_status,
                "override_status": override_status,
                "reason": reason,
            },
            outcome=override_status,
        )
        return audit_trail.entries[-1]
