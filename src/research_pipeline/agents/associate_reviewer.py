"""B10 — Associate Reviewer: enforce publication standards."""

from __future__ import annotations

from typing import Any

from research_pipeline.agents.base_agent import BaseAgent


class AssociateReviewerAgent(BaseAgent):
    """Senior associate gatekeeper — binary pass/fail before anything reaches the PM.

    Nothing reaches the Portfolio Manager without passing here.
    PASS_WITH_DISCLOSURE is NOT a valid outcome — there is no soft pass.
    """

    # ISS-9: reviewer gate is critical — publication_status field must be present
    _REQUIRED_OUTPUT_KEYS: list[str] = ["publication_status"]
    _VALIDATION_FATAL: bool = True

    def __init__(self, **kwargs):
        super().__init__(name="associate_reviewer", **kwargs)

    def default_system_prompt(self) -> str:
        return """You are the Associate Reviewer — the senior quality gate between analysts and the Portfolio Manager.

EVERY piece of analyst output passes through you. You integrate, quality-control, and gate.

INPUTS YOU RECEIVE SIMULTANEOUSLY:
1. Sector analyst four-box outputs (Compute, Power/Energy, Infrastructure)
2. Evidence Librarian claim ledger (with PASS/CAVEAT/FAIL statuses)
3. Valuation Analyst output (price targets, entry quality, scenarios)
4. Red Team Analyst assessment (thesis integrity, falsification results)

Do NOT begin review until ALL FOUR inputs are present.

PUBLICATION GATE — HARD RULES:
The gate FAILS if ANY of the following are true:
- Any claim has FAIL status in the evidence ledger
- Any field in a stock block is undefined, blank, or placeholder text
- Any management guidance presented as PRIMARY FACT without [GUIDANCE] label
- Any price target has no methodology tag (HOUSE VIEW vs consensus)
- Any return scenario lacks explicit driver decomposition
- Any company described as "specified" or "exclusive" partner when source says "contributor"
- Any stock's audit status field is undefined/null/empty
- Red Team assessment not completed for all names
- Red Team has fewer than 3 falsification tests for any name
- CAVEAT claims not explicitly labelled in body text

GATE PASSES when: All FAIL claims resolved, all CAVEAT claims labelled, all fields populated, all methodology tags present, all four analysts submitted, red team has ≥3 tests per name.

CROSS-ANALYST CONSISTENCY CHECKS:
After gate passes, verify:
- Compute analyst's AI revenue view aligns with Power analyst's demand view
- Infrastructure analyst's entry quality aligns with Valuation analyst's rating
- Red Team's worst-case scenarios are reflected in PM's risk discussion

YOUR OUTPUT:
{
  "publication_status": "PASS | FAIL",
  "gate_checks": [
    {"check": "description", "status": "pass|fail", "note": "issue if fail"}
  ],
  "cross_analyst_issues": ["consistency issues found"],
  "required_corrections": ["specific items to fix before next attempt — MUST be empty for PASS"],
  "integration_notes": "summary of how analyst outputs connect",
  "self_audit_packet": {
    "total_claims": 0,
    "pass_claims": 0,
    "caveat_claims": 0,
    "fail_claims": 0,
    "methodology_tags_present": true/false,
    "dates_complete": true/false,
    "source_hygiene_score": "0-10"
  },
  "ready_for_pm": true/false
}

HARD RULE: Gate status is BINARY — PASS or FAIL only. There is no PASS_WITH_DISCLOSURE.
PASS requires: required_corrections is empty AND ready_for_pm is true AND no FAIL gate checks.

JPAM MACRO REGIME AWARENESS (Session 13):
A MACRO REGIME CONTEXT block is prepended to each input.
Additional gate checks triggered by macro context:
- If macro_scenario is "bear" and portfolio has >40% rate-sensitive names: flag as required_correction
- If economy_analysis includes high AU risks and no AU-specific notes in sector outputs: flag
- Reference macro scenario label in any macro-related required_corrections messages"""

    def format_input(self, inputs: dict[str, Any]) -> str:
        import json
        return json.dumps(inputs, indent=2, default=str)

    def parse_output(self, raw_response: str) -> dict[str, Any]:
        """Enforce binary PASS/FAIL. Convert any PASS_WITH_DISCLOSURE to FAIL."""
        from research_pipeline.agents.base_agent import StructuredOutputError

        parsed = super().parse_output(raw_response)
        if not isinstance(parsed, dict):
            raise StructuredOutputError(
                "AssociateReviewer: expected a JSON object, got array."
            )

        status = str(parsed.get("publication_status", "fail")).lower().strip()

        # Normalise: reject any soft-pass variant
        if status in ("pass_with_disclosure", "conditional_pass", "pass with disclosure"):
            # Force fail — soft pass is not permitted
            parsed["publication_status"] = "FAIL"
            parsed.setdefault("required_corrections", []).append(
                "publication_status was 'PASS_WITH_DISCLOSURE' — not a valid outcome. "
                "All items must be explicitly resolved before PASS is granted."
            )
            parsed["ready_for_pm"] = False

        # Validate that a PASS has no required corrections outstanding
        if parsed.get("publication_status", "").upper() == "PASS":
            corrections = parsed.get("required_corrections", [])
            if corrections:
                parsed["publication_status"] = "FAIL"
                parsed.setdefault("required_corrections", []).append(
                    "Status changed to FAIL: PASS cannot coexist with required_corrections."
                )
                parsed["ready_for_pm"] = False

        if "publication_status" not in parsed:
            raise StructuredOutputError(
                "AssociateReviewer: 'publication_status' field missing from output."
            )

        return parsed