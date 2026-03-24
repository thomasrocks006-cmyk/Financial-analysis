"""Gate logic for every pipeline stage."""

from __future__ import annotations

import logging
from typing import Any

from research_pipeline.schemas.claims import ClaimLedger
from research_pipeline.schemas.market_data import DataQualityReport, ReconciliationReport
from research_pipeline.schemas.portfolio import AssociateReviewResult, PublicationStatus

logger = logging.getLogger(__name__)


class GateResult:
    """Result of a stage gate check."""

    def __init__(self, stage: int, passed: bool, reason: str = "", blockers: list[str] | None = None):
        self.stage = stage
        self.passed = passed
        self.reason = reason
        self.blockers = blockers or []

    def __repr__(self):
        status = "PASS" if self.passed else "FAIL"
        return f"Gate(stage={self.stage}, {status}, reason='{self.reason}')"


class PipelineGates:
    """All gate checks for the 15-stage pipeline.

    Each gate returns a GateResult. A failed gate blocks downstream stages.
    """

    # ── Stage 0: Configuration & Bootstrap ─────────────────────────────
    @staticmethod
    def gate_0_configuration(
        api_keys_valid: bool,
        config_loaded: bool,
        schemas_valid: bool,
    ) -> GateResult:
        """Fail if required secrets, schemas, or thresholds missing."""
        blockers = []
        if not api_keys_valid:
            blockers.append("Missing required API keys")
        if not config_loaded:
            blockers.append("Pipeline config not loaded")
        if not schemas_valid:
            blockers.append("Schema validation failed")
        return GateResult(
            stage=0,
            passed=len(blockers) == 0,
            reason="Configuration check",
            blockers=blockers,
        )

    # ── Stage 1: Universe Definition ───────────────────────────────────
    @staticmethod
    def gate_1_universe(
        universe: list[str],
        min_tickers: int = 3,
    ) -> GateResult:
        blockers = []
        if len(universe) < min_tickers:
            blockers.append(f"Universe has {len(universe)} tickers, minimum {min_tickers}")
        if len(set(universe)) != len(universe):
            blockers.append("Duplicate tickers in universe")
        return GateResult(stage=1, passed=len(blockers) == 0, reason="Universe check", blockers=blockers)

    # ── Stage 2: Data Ingestion ────────────────────────────────────────
    @staticmethod
    def gate_2_ingestion(
        ingest_results: list[dict[str, Any]],
        universe: list[str],
    ) -> GateResult:
        blockers = []
        ingested = {r["ticker"] for r in ingest_results if "error" not in r}
        missing = set(universe) - ingested
        if missing:
            blockers.append(f"Failed to ingest: {', '.join(missing)}")
        # Check for stale data
        for r in ingest_results:
            if r.get("error"):
                blockers.append(f"{r['ticker']}: {r['error']}")
        return GateResult(stage=2, passed=len(blockers) == 0, reason="Ingestion check", blockers=blockers)

    # ── Stage 3: Reconciliation ────────────────────────────────────────
    @staticmethod
    def gate_3_reconciliation(report: ReconciliationReport) -> GateResult:
        """Red fields on mandatory data block downstream."""
        blockers = []
        if report.has_blocking_reds():
            reds = report.get_reds()
            for r in reds:
                blockers.append(f"RED: {r.ticker} {r.field_name} — divergence {r.divergence_pct:.1f}%")
        return GateResult(stage=3, passed=len(blockers) == 0, reason="Reconciliation check", blockers=blockers)

    # ── Stage 4: Data QA & Lineage ─────────────────────────────────────
    @staticmethod
    def gate_4_data_qa(report: DataQualityReport) -> GateResult:
        """Fail if lineage missing or data corruption detected."""
        blockers = []
        if not report.is_passing():
            for issue in report.issues:
                blockers.append(issue)
        return GateResult(stage=4, passed=len(blockers) == 0, reason="Data QA check", blockers=blockers)

    # ── Stage 5: Evidence Librarian ────────────────────────────────────
    @staticmethod
    def gate_5_evidence(ledger: ClaimLedger) -> GateResult:
        """No analyst can proceed without claim ledger. No FAIL claims allowed."""
        blockers = []
        if not ledger.claims:
            blockers.append("Claim ledger is empty")
        if ledger.has_unresolved_fails():
            blockers.append(f"{ledger.fail_count} FAIL claims must be resolved before proceeding")
        return GateResult(stage=5, passed=len(blockers) == 0, reason="Evidence check", blockers=blockers)

    # ── Stage 6: Sector Analysis ───────────────────────────────────────
    @staticmethod
    def gate_6_sector_analysis(
        four_box_count: int,
        expected_count: int,
        unsupported_claims: int = 0,
    ) -> GateResult:
        blockers = []
        if four_box_count < expected_count:
            blockers.append(f"Only {four_box_count}/{expected_count} four-box outputs received")
        if unsupported_claims > 0:
            blockers.append(f"{unsupported_claims} unsupported claims rejected")
        return GateResult(stage=6, passed=len(blockers) == 0, reason="Sector analysis check", blockers=blockers)

    # ── Stage 7: Valuation & Modelling ─────────────────────────────────
    @staticmethod
    def gate_7_valuation(
        valuation_cards_count: int,
        expected_count: int,
        missing_methodology_tags: int = 0,
    ) -> GateResult:
        blockers = []
        if valuation_cards_count < expected_count:
            blockers.append(f"Only {valuation_cards_count}/{expected_count} valuation cards")
        if missing_methodology_tags > 0:
            blockers.append(f"{missing_methodology_tags} targets missing methodology tag")
        return GateResult(stage=7, passed=len(blockers) == 0, reason="Valuation check", blockers=blockers)

    # ── Stage 8: Macro & Political ─────────────────────────────────────
    @staticmethod
    def gate_8_macro(
        regime_memo_present: bool,
        political_assessments_count: int,
        expected_count: int,
    ) -> GateResult:
        blockers = []
        if not regime_memo_present:
            blockers.append("Macro regime memo missing")
        if political_assessments_count < expected_count:
            blockers.append(f"Only {political_assessments_count}/{expected_count} political assessments")
        return GateResult(stage=8, passed=len(blockers) == 0, reason="Macro/political check", blockers=blockers)

    # ── Stage 9: Quant Risk & Scenario ─────────────────────────────────
    @staticmethod
    def gate_9_risk(
        risk_packet_present: bool,
        scenario_results_count: int,
        concentration_breaches: list[str] | None = None,
    ) -> GateResult:
        blockers = []
        if not risk_packet_present:
            blockers.append("Risk packet missing")
        if scenario_results_count == 0:
            blockers.append("No scenario results generated")
        # Concentration breaches are flagged but don't necessarily block
        # They must be disclosed in the report
        warnings = concentration_breaches or []
        return GateResult(
            stage=9,
            passed=len(blockers) == 0,
            reason="Risk check" + (f" (warnings: {len(warnings)})" if warnings else ""),
            blockers=blockers,
        )

    # ── Stage 10: Red Team ─────────────────────────────────────────────
    @staticmethod
    def gate_10_red_team(
        assessments_count: int,
        expected_count: int,
        all_have_min_falsifications: bool = True,
    ) -> GateResult:
        blockers = []
        if assessments_count < expected_count:
            blockers.append(f"Only {assessments_count}/{expected_count} red team assessments")
        if not all_have_min_falsifications:
            blockers.append("Not all names have minimum 3 falsification tests")
        return GateResult(stage=10, passed=len(blockers) == 0, reason="Red team check", blockers=blockers)

    # ── Stage 11: Associate Review / Publish Gate ──────────────────────
    @staticmethod
    def gate_11_review(result: AssociateReviewResult) -> GateResult:
        """FAIL blocks publication."""
        if result.is_publishable:
            return GateResult(stage=11, passed=True, reason=f"Review: {result.status.value}")
        blockers = [f"Review status: {result.status.value}"]
        for issue in result.issues:
            blockers.append(f"[{issue.severity}] {issue.description}")
        return GateResult(stage=11, passed=False, reason="Publish gate FAILED", blockers=blockers)

    # ── Stage 12: Portfolio Construction ───────────────────────────────
    @staticmethod
    def gate_12_portfolio(
        variants_count: int,
        constraint_violations: list[str] | None = None,
        review_passed: bool = True,
    ) -> GateResult:
        blockers = []
        if not review_passed:
            blockers.append("PM cannot override FAIL from reviewer")
        if variants_count < 3:
            blockers.append(f"Only {variants_count}/3 portfolio variants produced")
        if constraint_violations:
            for v in constraint_violations:
                blockers.append(f"Constraint violation: {v}")
        return GateResult(stage=12, passed=len(blockers) == 0, reason="Portfolio check", blockers=blockers)

    # ── Stage 13: Report Assembly ──────────────────────────────────────
    @staticmethod
    def gate_13_report(
        report_generated: bool,
        all_sections_approved: bool,
    ) -> GateResult:
        blockers = []
        if not report_generated:
            blockers.append("Report not generated")
        if not all_sections_approved:
            blockers.append("Not all report sections approved")
        return GateResult(stage=13, passed=len(blockers) == 0, reason="Report assembly check", blockers=blockers)
