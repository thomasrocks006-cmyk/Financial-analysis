"""Audit Exporter — export full governance audit trail as structured JSON."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_pipeline.schemas.governance import (
    AuditTrail,
    CommitteeRecord,
    MandateCheckResult,
)

logger = logging.getLogger(__name__)


class AuditExporter:
    """Export governance audit trails in structured formats — no LLM.

    Produces complete audit packages for compliance review, including:
    - Gate results across all 15 stages
    - Committee voting records
    - Mandate compliance results
    - Human override log
    - Full timeline of actions
    """

    def __init__(self, output_dir: Path | str = "reports/audit"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_full_audit(
        self,
        run_id: str,
        audit_trail: AuditTrail | None = None,
        committee_record: CommitteeRecord | None = None,
        mandate_check: MandateCheckResult | None = None,
        gate_results: dict[str, Any] | None = None,
        pipeline_metadata: dict[str, Any] | None = None,
        esg_results: dict[str, Any] | None = None,
        risk_summary: dict[str, Any] | None = None,
    ) -> Path:
        """Export a complete audit package for a run.

        Returns the path to the exported audit file.
        """
        now = datetime.now(timezone.utc)

        audit_package: dict[str, Any] = {
            "audit_version": "1.0",
            "run_id": run_id,
            "export_timestamp": now.isoformat(),
            "sections": {},
        }

        # Section 1: Pipeline Metadata
        audit_package["sections"]["pipeline_metadata"] = {
            "run_id": run_id,
            "exported_at": now.isoformat(),
            **(pipeline_metadata or {}),
        }

        # Section 2: Gate Results
        if gate_results:
            audit_package["sections"]["gate_results"] = gate_results

        # Section 3: Committee Record
        if committee_record:
            audit_package["sections"]["committee_record"] = {
                "record_id": committee_record.record_id,
                "outcome": committee_record.outcome.value,
                "quorum_met": committee_record.quorum_met,
                "approve_count": committee_record.approve_count,
                "reject_count": committee_record.reject_count,
                "minutes": committee_record.minutes,
                "conditions": committee_record.conditions,
                "votes": [
                    {
                        "member_id": v.member.member_id,
                        "role": v.member.role,
                        "vote": v.vote.value,
                        "rationale": v.rationale,
                        "conditions": v.conditions,
                        "timestamp": v.timestamp.isoformat(),
                    }
                    for v in committee_record.votes
                ],
            }

        # Section 4: Mandate Compliance
        if mandate_check:
            audit_package["sections"]["mandate_compliance"] = {
                "mandate_id": mandate_check.mandate_id,
                "is_compliant": mandate_check.is_compliant,
                "violations": [
                    {
                        "rule_id": v.rule.rule_id,
                        "rule_type": v.rule.rule_type,
                        "description": v.description,
                        "actual_value": v.actual_value,
                        "threshold": v.rule.threshold,
                        "severity": v.breach_severity,
                    }
                    for v in mandate_check.violations
                ],
                "warnings": mandate_check.warnings,
            }

        # Section 5: ESG Assessment
        if esg_results:
            audit_package["sections"]["esg_assessment"] = esg_results

        # Section 6: Risk Summary
        if risk_summary:
            audit_package["sections"]["risk_summary"] = risk_summary

        # Section 7: Audit Trail (timeline)
        if audit_trail:
            audit_package["sections"]["audit_trail"] = {
                "total_entries": len(audit_trail.entries),
                "entries": [
                    {
                        "entry_id": e.entry_id,
                        "timestamp": e.timestamp.isoformat(),
                        "action": e.action,
                        "stage": e.stage,
                        "actor": e.actor,
                        "details": e.details,
                        "outcome": e.outcome,
                    }
                    for e in audit_trail.entries
                ],
            }

        # Section 8: Compliance Summary
        audit_package["sections"]["compliance_summary"] = self._build_compliance_summary(
            committee_record=committee_record,
            mandate_check=mandate_check,
            gate_results=gate_results,
        )

        # Write to file
        filename = f"audit_{run_id}_{now.strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.output_dir / filename
        filepath.write_text(json.dumps(audit_package, indent=2, default=str))

        logger.info("Audit exported to %s", filepath)
        return filepath

    def _build_compliance_summary(
        self,
        committee_record: CommitteeRecord | None,
        mandate_check: MandateCheckResult | None,
        gate_results: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Build a high-level compliance summary."""
        summary: dict[str, Any] = {
            "overall_status": "unknown",
            "checks": {},
        }

        overall_pass = True

        # Committee check
        if committee_record:
            ic_pass = committee_record.is_approved
            summary["checks"]["investment_committee"] = {
                "passed": ic_pass,
                "outcome": committee_record.outcome.value,
            }
            if not ic_pass:
                overall_pass = False
        else:
            summary["checks"]["investment_committee"] = {
                "passed": False,
                "outcome": "not_performed",
            }
            overall_pass = False

        # Mandate check
        if mandate_check:
            summary["checks"]["mandate_compliance"] = {
                "passed": mandate_check.is_compliant,
                "violation_count": len(mandate_check.violations),
            }
            if not mandate_check.is_compliant:
                overall_pass = False
        else:
            summary["checks"]["mandate_compliance"] = {
                "passed": False,
                "outcome": "not_performed",
            }

        # Gate results
        if gate_results:
            failed = gate_results.get("failed_gates", [])
            summary["checks"]["pipeline_gates"] = {
                "passed": len(failed) == 0,
                "failed_gates": failed,
            }
            if failed:
                overall_pass = False

        summary["overall_status"] = "compliant" if overall_pass else "non_compliant"
        return summary

    def list_audits(self, run_id: str | None = None) -> list[Path]:
        """List all audit files, optionally filtered by run_id."""
        pattern = f"audit_{run_id}_*.json" if run_id else "audit_*.json"
        return sorted(self.output_dir.glob(pattern), reverse=True)
