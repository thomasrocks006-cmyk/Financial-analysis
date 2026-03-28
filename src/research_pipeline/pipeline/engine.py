"""Pipeline execution engine — orchestrates all 15 stages."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from research_pipeline.config.loader import PipelineConfig, load_pipeline_config
from research_pipeline.config.settings import Settings
from research_pipeline.pipeline.gates import GateResult, PipelineGates
from research_pipeline.schemas.claims import ClaimLedger
from research_pipeline.schemas.market_data import (
    DataQualityReport,
    MarketSnapshot,
    ReconciliationReport,
)
from research_pipeline.schemas.portfolio import (
    AssociateReviewResult,
    FourBoxOutput,
    PortfolioVariant,
    PublicationStatus,
    RedTeamAssessment,
    ValuationCard,
    MacroRegimeMemo,
)
from research_pipeline.schemas.registry import RunRecord, RunStatus
from research_pipeline.schemas.reports import FinalReport, RiskPacket

# Services
from research_pipeline.services.market_data_ingestor import MarketDataIngestor
from research_pipeline.services.consensus_reconciliation import ConsensusReconciliationService
from research_pipeline.services.data_qa_lineage import DataQALineageService
from research_pipeline.services.dcf_engine import DCFEngine
from research_pipeline.services.risk_engine import RiskEngine
from research_pipeline.services.scenario_engine import ScenarioStressEngine
from research_pipeline.services.run_registry import RunRegistryService
from research_pipeline.services.report_assembly import ReportAssemblyService
from research_pipeline.services.golden_tests import GoldenTestHarness

# Agents
from research_pipeline.agents.orchestrator import OrchestratorAgent
from research_pipeline.agents.evidence_librarian import EvidenceLibrarianAgent
from research_pipeline.agents.sector_analysts import (
    SectorAnalystCompute,
    SectorAnalystPowerEnergy,
    SectorAnalystInfrastructure,
)
from research_pipeline.agents.valuation_analyst import ValuationAnalystAgent
from research_pipeline.agents.macro_political import MacroStrategistAgent, PoliticalRiskAnalystAgent
from research_pipeline.agents.red_team_analyst import RedTeamAnalystAgent
from research_pipeline.agents.associate_reviewer import AssociateReviewerAgent
from research_pipeline.agents.portfolio_manager import PortfolioManagerAgent

logger = logging.getLogger(__name__)


class PipelineEngine:
    """Main execution engine for the 15-stage research pipeline.

    Deterministic work stays in code. Judgment work goes to LLM agents.
    Every stage emits typed outputs. Every run is logged. Every publish is gated.
    """

    def __init__(self, settings: Settings, config: PipelineConfig):
        self.settings = settings
        self.config = config
        self.gates = PipelineGates()

        # Initialize services
        self.registry = RunRegistryService(settings.storage_dir)
        self.ingestor = MarketDataIngestor(
            fmp_key=settings.api_keys.fmp_api_key,
            finnhub_key=settings.api_keys.finnhub_api_key,
        )
        self.reconciliation = ConsensusReconciliationService(config.thresholds.reconciliation)
        self.data_qa = DataQALineageService(
            require_lineage=config.thresholds.data_quality.require_lineage_for_all_final_fields,
        )
        self.dcf_engine = DCFEngine()
        self.risk_engine = RiskEngine()
        self.scenario_engine = ScenarioStressEngine()
        self.report_assembly = ReportAssemblyService()
        self.golden_tests = GoldenTestHarness()

        # Initialize agents
        prompts_dir = settings.prompts_dir
        agent_kwargs = {"model": settings.llm_model, "temperature": settings.llm_temperature, "prompts_dir": prompts_dir}
        self.orchestrator_agent = OrchestratorAgent(**agent_kwargs)
        self.evidence_agent = EvidenceLibrarianAgent(**agent_kwargs)
        self.compute_analyst = SectorAnalystCompute(**agent_kwargs)
        self.power_analyst = SectorAnalystPowerEnergy(**agent_kwargs)
        self.infra_analyst = SectorAnalystInfrastructure(**agent_kwargs)
        self.valuation_agent = ValuationAnalystAgent(**agent_kwargs)
        self.macro_agent = MacroStrategistAgent(**agent_kwargs)
        self.political_agent = PoliticalRiskAnalystAgent(**agent_kwargs)
        self.red_team_agent = RedTeamAnalystAgent(**agent_kwargs)
        self.reviewer_agent = AssociateReviewerAgent(**agent_kwargs)
        self.pm_agent = PortfolioManagerAgent(**agent_kwargs)

        # Run state
        self.run_record: Optional[RunRecord] = None
        self.gate_results: dict[int, GateResult] = {}
        self.stage_outputs: dict[int, Any] = {}
        self._review_result: Optional[AssociateReviewResult] = None  # set by stage_11, read by stage_13

    # ── helpers ─────────────────────────────────────────────────────────
    def _save_stage_output(self, stage: int, data: Any) -> None:
        """Persist stage output to disk."""
        self.stage_outputs[stage] = data
        output_dir = self.settings.storage_dir / "artifacts" / self.run_record.run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / f"stage_{stage:02d}.json"
        filepath.write_text(json.dumps(data, indent=2, default=str))
        logger.info("Stage %d output saved to %s", stage, filepath)

    def _check_gate(self, gate_result: GateResult) -> bool:
        """Record gate result and return whether it passed."""
        self.gate_results[gate_result.stage] = gate_result
        if gate_result.passed:
            logger.info("Gate %d PASSED: %s", gate_result.stage, gate_result.reason)
            self.registry.mark_stage_complete(self.run_record.run_id, gate_result.stage)
        else:
            logger.error("Gate %d FAILED: %s — %s", gate_result.stage, gate_result.reason, gate_result.blockers)
            self.registry.mark_stage_failed(self.run_record.run_id, gate_result.stage)
        return gate_result.passed

    # ── Stage execution methods ────────────────────────────────────────
    async def stage_0_bootstrap(self, universe: list[str]) -> bool:
        """Stage 0: Configuration & Bootstrap."""
        logger.info("═══ STAGE 0: Configuration & Bootstrap ═══")

        # Run golden tests
        test_results = self.golden_tests.run_all()

        # Validate API keys
        missing_keys = self.settings.api_keys.validate()
        api_valid = len(missing_keys) == 0

        # Create run record
        config_dict = self.config.model_dump()
        agent_versions = {
            agent.name: agent.version for agent in [
                self.orchestrator_agent, self.evidence_agent, self.compute_analyst,
                self.power_analyst, self.infra_analyst, self.valuation_agent,
                self.macro_agent, self.political_agent, self.red_team_agent,
                self.reviewer_agent, self.pm_agent,
            ]
        }
        self.run_record = self.registry.create_run(
            universe=universe,
            config=config_dict,
            agent_versions=agent_versions,
        )

        gate = self.gates.gate_0_configuration(
            api_keys_valid=api_valid,
            config_loaded=True,
            schemas_valid=test_results.get("failed", 0) == 0,
        )
        self._save_stage_output(0, {
            "run_id": self.run_record.run_id,
            "universe": universe,
            "agent_versions": agent_versions,
            "golden_tests": test_results,
            "api_keys_status": "valid" if api_valid else f"missing: {missing_keys}",
        })
        return self._check_gate(gate)

    async def stage_1_universe(self, universe: list[str]) -> bool:
        """Stage 1: Universe Definition."""
        logger.info("═══ STAGE 1: Universe Definition ═══")
        gate = self.gates.gate_1_universe(universe)
        self._save_stage_output(1, {"universe": universe, "count": len(universe)})
        return self._check_gate(gate)

    async def stage_2_ingestion(self, universe: list[str]) -> bool:
        """Stage 2: Data Ingestion from FMP + Finnhub."""
        logger.info("═══ STAGE 2: Data Ingestion ═══")
        results = await self.ingestor.ingest_universe(universe)
        gate = self.gates.gate_2_ingestion(results, universe)
        self._save_stage_output(2, results)
        return self._check_gate(gate)

    async def stage_3_reconciliation(self) -> bool:
        """Stage 3: Reconciliation of FMP vs Finnhub."""
        logger.info("═══ STAGE 3: Reconciliation ═══")
        ingest_data = self.stage_outputs.get(2, [])
        all_fields = []

        from research_pipeline.schemas.market_data import ConsensusSnapshot
        for ticker_data in ingest_data:
            # Skip tickers that had a TOTAL ingestion failure (set by ingest_universe
            # outer try/except with singular "error" key).
            if "error" in ticker_data:
                continue
            ticker = ticker_data["ticker"]

            # Build FMP quote snapshot — fmp_quote may be absent if FMP returned 402
            fmp_quote_raw = ticker_data.get("fmp_quote") or {}
            if not fmp_quote_raw:
                # Minimal shell so reconcile_price can still classify as MISSING
                fmp_quote = MarketSnapshot(ticker=ticker, source="fmp")
            else:
                fmp_quote = MarketSnapshot(**fmp_quote_raw)

            # Extract Finnhub spot price for price cross-validation
            finnhub_price: Optional[float] = (
                (ticker_data.get("finnhub_quote") or {}).get("price")
            )

            # Build consensus snapshots
            fmp_targets_raw = ticker_data.get("fmp_targets") or {}
            finnhub_targets_raw = ticker_data.get("finnhub_targets") or {}
            fmp_consensus = (
                ConsensusSnapshot(**fmp_targets_raw)
                if fmp_targets_raw
                else ConsensusSnapshot(ticker=ticker, source="fmp")
            )
            finnhub_consensus = (
                ConsensusSnapshot(**finnhub_targets_raw)
                if finnhub_targets_raw
                else ConsensusSnapshot(ticker=ticker, source="finnhub")
            )

            fields = self.reconciliation.reconcile_ticker(
                ticker=ticker,
                fmp_quote=fmp_quote,
                fmp_consensus=fmp_consensus,
                finnhub_consensus=finnhub_consensus,
                finnhub_price=finnhub_price,  # was never passed — price rec was always MISSING
            )
            all_fields.extend(fields)

        report = self.reconciliation.build_report(self.run_record.run_id, all_fields)
        gate = self.gates.gate_3_reconciliation(report)
        self._save_stage_output(3, report.model_dump())
        return self._check_gate(gate)

    async def stage_4_data_qa(self) -> bool:
        """Stage 4: Data QA & Lineage."""
        logger.info("═══ STAGE 4: Data QA & Lineage ═══")
        ingest_data = self.stage_outputs.get(2, [])

        # Build parsed MarketSnapshot objects so outlier checks (negative price,
        # extreme P/E, etc.) are actually exercised — without this the check is
        # silently skipped because parsed_snapshots defaults to None.
        parsed_snapshots: list[MarketSnapshot] = []
        for td in ingest_data:
            if "error" in td:
                continue
            for key in ("fmp_quote", "finnhub_quote"):
                raw = td.get(key) or {}
                if raw:
                    try:
                        parsed_snapshots.append(MarketSnapshot(**raw))
                    except Exception:
                        pass  # skip malformed records; schema errors caught by check_schema_validity

        report = self.data_qa.run_full_check(
            run_id=self.run_record.run_id,
            raw_snapshots=ingest_data,
            parsed_snapshots=parsed_snapshots,
            max_age_hours=self.config.thresholds.reconciliation.stale_data_hours,
        )
        gate = self.gates.gate_4_data_qa(report)
        self._save_stage_output(4, report.model_dump())
        return self._check_gate(gate)

    async def stage_5_evidence(self, universe: list[str]) -> bool:
        """Stage 5: Evidence Librarian builds claim ledger."""
        logger.info("═══ STAGE 5: Evidence Librarian ═══")
        result = await self.evidence_agent.run(
            self.run_record.run_id,
            {"tickers": universe, "market_data": self.stage_outputs.get(2, [])},
        )
        self._save_stage_output(5, result.model_dump())

        # Build a real ClaimLedger from structured agent output — no synthetic claims.
        from research_pipeline.schemas.claims import Claim, ClaimStatus, EvidenceClass, ConfidenceLevel, SourceTier, Source
        ledger = ClaimLedger(run_id=self.run_record.run_id)

        if result.success and result.parsed_output:
            parsed = result.parsed_output
            # Agent may return {"claims": [...], "sources": [...]}
            raw_claims = parsed.get("claims", [])
            raw_sources = parsed.get("sources", [])

            for rc in raw_claims:
                if isinstance(rc, dict):
                    try:
                        ledger.claims.append(Claim(
                            claim_id=rc.get("claim_id", f"CLM-{len(ledger.claims)+1:03d}"),
                            run_id=self.run_record.run_id,
                            ticker=rc.get("ticker", "UNKNOWN"),
                            claim_text=rc.get("claim_text", ""),
                            evidence_class=EvidenceClass(rc.get("evidence_class", "house_inference")),
                            source_id=rc.get("source_id", "agent"),
                            source_url=rc.get("source_url"),
                            corroborated=rc.get("corroborated", False),
                            confidence=ConfidenceLevel(rc.get("confidence", "medium")),
                            status=ClaimStatus(rc.get("status", "caveat")),
                            owner_agent="evidence_librarian",
                        ))
                    except (ValueError, KeyError) as exc:
                        logger.warning("Skipping malformed claim: %s", exc)

            for rs in raw_sources:
                if isinstance(rs, dict):
                    try:
                        ledger.sources.append(Source(
                            source_id=rs.get("source_id", f"SRC-{len(ledger.sources)+1:03d}"),
                            source_type=rs.get("source_type", "unknown"),
                            tier=SourceTier(rs.get("tier", 4)),
                            url=rs.get("url"),
                            notes=rs.get("notes", ""),
                        ))
                    except (ValueError, KeyError) as exc:
                        logger.warning("Skipping malformed source: %s", exc)

        # Fail-closed: if agent failed or returned no structurally valid claims, the gate blocks.
        gate = self.gates.gate_5_evidence(ledger)
        return self._check_gate(gate)

    async def stage_6_sector_analysis(self, universe: list[str]) -> bool:
        """Stage 6: Three sector analysts run in parallel."""
        logger.info("═══ STAGE 6: Sector Analysis (parallel) ═══")

        # Route tickers to analysts; skip agents whose subtheme has no tickers in this universe
        compute_tickers = [t for t in universe if t in {"NVDA", "AVGO", "TSM", "AMD", "ANET"}]
        power_tickers = [t for t in universe if t in {"CEG", "VST", "GEV", "NLR"}]
        infra_tickers = [t for t in universe if t in {"PWR", "ETN", "HUBB", "APH", "FIX", "FCX", "BHP", "NXT"}]

        agent_calls = []
        expected_count = 0
        mkt_data = self.stage_outputs.get(2, [])
        for agent, tickers in [
            (self.compute_analyst, compute_tickers),
            (self.power_analyst, power_tickers),
            (self.infra_analyst, infra_tickers),
        ]:
            if tickers:  # skip agents with no relevant tickers in this universe
                agent_calls.append(agent.run(self.run_record.run_id, {"tickers": tickers, "market_data": mkt_data}))
                expected_count += 1
            else:
                logger.info("Skipping %s — no tickers in universe", agent.name)

        results = await asyncio.gather(*agent_calls)

        four_box_count = sum(1 for r in results if r.success)
        self._save_stage_output(6, [r.model_dump() for r in results])
        gate = self.gates.gate_6_sector_analysis(four_box_count, expected_count=expected_count)
        return self._check_gate(gate)

    async def stage_7_valuation(self, universe: list[str]) -> bool:
        """Stage 7: Valuation & Modelling."""
        logger.info("═══ STAGE 7: Valuation & Modelling ═══")
        result = await self.valuation_agent.run(
            self.run_record.run_id,
            {
                "tickers": universe,
                "sector_outputs": self.stage_outputs.get(6, []),
                "market_data": self.stage_outputs.get(2, []),
            },
        )
        self._save_stage_output(7, result.model_dump())
        gate = self.gates.gate_7_valuation(
            valuation_cards_count=1 if result.success else 0,
            expected_count=1,
        )
        return self._check_gate(gate)

    async def stage_8_macro(self, universe: list[str]) -> bool:
        """Stage 8: Macro & Political Overlay."""
        logger.info("═══ STAGE 8: Macro & Political Overlay ═══")
        macro_result, political_result = await asyncio.gather(
            self.macro_agent.run(self.run_record.run_id, {"universe": universe}),
            self.political_agent.run(self.run_record.run_id, {"tickers": universe}),
        )
        self._save_stage_output(8, {
            "macro": macro_result.model_dump(),
            "political": political_result.model_dump(),
        })
        gate = self.gates.gate_8_macro(
            regime_memo_present=macro_result.success,
            political_assessments_count=1 if political_result.success else 0,
            expected_count=1,
        )
        return self._check_gate(gate)

    async def stage_9_risk(self, universe: list[str], weights: dict[str, float] | None = None) -> bool:
        """Stage 9: Quant Risk & Scenario Testing."""
        logger.info("═══ STAGE 9: Quant Risk & Scenario Testing ═══")
        # Run scenarios
        scenario_results = self.scenario_engine.run_all_scenarios(universe)
        risk_packet = RiskPacket(
            run_id=self.run_record.run_id,
            scenario_results=scenario_results,
        )
        self._save_stage_output(9, risk_packet.model_dump())
        gate = self.gates.gate_9_risk(
            risk_packet_present=True,
            scenario_results_count=len(scenario_results),
        )
        return self._check_gate(gate)

    async def stage_10_red_team(self, universe: list[str]) -> bool:
        """Stage 10: Red Team."""
        logger.info("═══ STAGE 10: Red Team ═══")
        result = await self.red_team_agent.run(
            self.run_record.run_id,
            {
                "tickers": universe,
                "sector_outputs": self.stage_outputs.get(6, []),
                "valuation_outputs": self.stage_outputs.get(7, {}),
            },
        )
        self._save_stage_output(10, result.model_dump())
        gate = self.gates.gate_10_red_team(
            assessments_count=1 if result.success else 0,
            expected_count=1,
        )
        return self._check_gate(gate)

    async def stage_11_review(self) -> bool:
        """Stage 11: Associate Review / Publish Gate."""
        logger.info("═══ STAGE 11: Associate Review / Publish Gate ═══")
        result = await self.reviewer_agent.run(
            self.run_record.run_id,
            {
                "sector_outputs": self.stage_outputs.get(6, []),
                "evidence_ledger": self.stage_outputs.get(5, {}),
                "valuation_outputs": self.stage_outputs.get(7, {}),
                "red_team_outputs": self.stage_outputs.get(10, {}),
            },
        )
        self._save_stage_output(11, result.model_dump())

        # Build review result from structured agent output — fail closed on missing data.
        review_result = AssociateReviewResult(
            run_id=self.run_record.run_id,
            status=PublicationStatus.FAIL,  # default: fail closed
        )

        if result.success and result.parsed_output:
            parsed = result.parsed_output
            # Agent must return explicit {"status": "pass"|"pass_with_disclosure"|"fail", ...}
            raw_status = parsed.get("status", "fail").lower().replace(" ", "_")
            try:
                review_result.status = PublicationStatus(raw_status)
            except ValueError:
                logger.warning("Invalid review status '%s' — defaulting to FAIL", raw_status)
                review_result.status = PublicationStatus.FAIL

            # Parse issues list
            from research_pipeline.schemas.portfolio import ReviewIssue
            for issue_data in parsed.get("issues", []):
                if isinstance(issue_data, dict):
                    review_result.issues.append(ReviewIssue(
                        severity=issue_data.get("severity", "major"),
                        description=issue_data.get("description", ""),
                        ticker=issue_data.get("ticker"),
                        stage=issue_data.get("stage"),
                        resolution=issue_data.get("resolution", ""),
                    ))

            review_result.self_audit_score = parsed.get("self_audit_score")
            review_result.unresolved_count = parsed.get("unresolved_count", 0)
            review_result.methodology_tags_complete = parsed.get("methodology_tags_complete", False)
            review_result.dates_complete = parsed.get("dates_complete", False)
            review_result.claim_mapping_complete = parsed.get("claim_mapping_complete", False)
            review_result.notes = parsed.get("notes", "")
        else:
            # Agent failure = automatic FAIL. No fallback to PASS.
            review_result.status = PublicationStatus.FAIL
            review_result.notes = f"Agent error: {result.error or 'no structured output'}"

        self._review_result = review_result
        gate = self.gates.gate_11_review(review_result)
        return self._check_gate(gate)

    async def stage_12_portfolio(self, universe: list[str]) -> bool:
        """Stage 12: Portfolio Construction."""
        logger.info("═══ STAGE 12: Portfolio Construction ═══")
        # Check that review passed
        review_gate = self.gate_results.get(11)
        if not review_gate or not review_gate.passed:
            gate = self.gates.gate_12_portfolio(0, review_passed=False)
            return self._check_gate(gate)

        result = await self.pm_agent.run(
            self.run_record.run_id,
            {
                "universe": universe,
                "sector_outputs": self.stage_outputs.get(6, []),
                "valuation_outputs": self.stage_outputs.get(7, {}),
                "red_team_outputs": self.stage_outputs.get(10, {}),
                "risk_outputs": self.stage_outputs.get(9, {}),
                "review_outputs": self.stage_outputs.get(11, {}),
            },
        )
        self._save_stage_output(12, result.model_dump())
        gate = self.gates.gate_12_portfolio(
            variants_count=3 if result.success else 0,
            review_passed=True,
        )
        return self._check_gate(gate)

    async def stage_13_report(self) -> bool:
        """Stage 13: Report Assembly."""
        logger.info("═══ STAGE 13: Report Assembly ═══")
        # Use the review result from stage 11. Fail closed if missing — never assume approval.
        if self._review_result is None:
            logger.error("Stage 13: No review result from Stage 11 — cannot assemble report")
            gate = self.gates.gate_13_report(report_generated=False, all_sections_approved=False)
            return self._check_gate(gate)
        review_result = self._review_result

        # Build self-audit
        audit = self.registry.build_self_audit(self.run_record.run_id, ClaimLedger(run_id=self.run_record.run_id))

        report = self.report_assembly.assemble_report(
            run_id=self.run_record.run_id,
            review_result=review_result,
            sections={
                "executive_summary": "AI Infrastructure Investment Research — Executive Summary",
                "methodology": "Public-source institutional-style research methodology.",
            },
            stock_cards=[],
            self_audit_text=json.dumps(audit.model_dump(), indent=2, default=str),
        )

        # Save report
        output_path = self.report_assembly.save_report(report, self.settings.reports_dir)
        self._save_stage_output(13, {"report_path": str(output_path), "status": report.publication_status})
        gate = self.gates.gate_13_report(report_generated=True, all_sections_approved=True)
        return self._check_gate(gate)

    async def stage_14_monitoring(self) -> None:
        """Stage 14: Monitoring, Registry, and Post-Run Logging."""
        logger.info("═══ STAGE 14: Monitoring & Post-Run Logging ═══")
        # Final run status update
        failed_stages = [s for s, g in self.gate_results.items() if not g.passed]
        final_status = RunStatus.COMPLETED if not failed_stages else RunStatus.FAILED

        self.registry.update_run_status(
            self.run_record.run_id,
            status=final_status,
            outputs_generated=list(self.stage_outputs.keys()),
            final_gate_outcome="PASS" if final_status == RunStatus.COMPLETED else "FAIL",
        )

        self._save_stage_output(14, {
            "final_status": final_status.value,
            "stages_completed": [s for s, g in self.gate_results.items() if g.passed],
            "stages_failed": failed_stages,
            "gate_summary": {s: g.reason for s, g in self.gate_results.items()},
        })
        logger.info("Pipeline run %s finished with status: %s", self.run_record.run_id, final_status.value)

    # ── Full pipeline execution ────────────────────────────────────────
    async def run_full_pipeline(self, universe: list[str]) -> dict[str, Any]:
        """Execute the full 15-stage pipeline end-to-end."""
        logger.info("╔══════════════════════════════════════════════╗")
        logger.info("║  AI Infrastructure Research Pipeline v8      ║")
        logger.info("║  Starting full pipeline run                  ║")
        logger.info("╚══════════════════════════════════════════════╝")

        # Stage 0: Bootstrap
        if not await self.stage_0_bootstrap(universe):
            await self.stage_14_monitoring()
            return {"status": "failed", "blocked_at": 0, "run_id": self.run_record.run_id}

        # Stage 1: Universe
        if not await self.stage_1_universe(universe):
            await self.stage_14_monitoring()
            return {"status": "failed", "blocked_at": 1, "run_id": self.run_record.run_id}

        # Stage 2: Data Ingestion
        if not await self.stage_2_ingestion(universe):
            await self.stage_14_monitoring()
            return {"status": "failed", "blocked_at": 2, "run_id": self.run_record.run_id}

        # Stage 3: Reconciliation
        if not await self.stage_3_reconciliation():
            await self.stage_14_monitoring()
            return {"status": "failed", "blocked_at": 3, "run_id": self.run_record.run_id}

        # Stage 4: Data QA
        if not await self.stage_4_data_qa():
            await self.stage_14_monitoring()
            return {"status": "failed", "blocked_at": 4, "run_id": self.run_record.run_id}

        # Stage 5: Evidence Librarian
        if not await self.stage_5_evidence(universe):
            await self.stage_14_monitoring()
            return {"status": "failed", "blocked_at": 5, "run_id": self.run_record.run_id}

        # Stage 6: Sector Analysis (parallel)
        if not await self.stage_6_sector_analysis(universe):
            await self.stage_14_monitoring()
            return {"status": "failed", "blocked_at": 6, "run_id": self.run_record.run_id}

        # Stage 7: Valuation
        if not await self.stage_7_valuation(universe):
            await self.stage_14_monitoring()
            return {"status": "failed", "blocked_at": 7, "run_id": self.run_record.run_id}

        # Stage 8: Macro & Political
        if not await self.stage_8_macro(universe):
            await self.stage_14_monitoring()
            return {"status": "failed", "blocked_at": 8, "run_id": self.run_record.run_id}

        # Stage 9: Risk & Scenarios
        if not await self.stage_9_risk(universe):
            await self.stage_14_monitoring()
            return {"status": "failed", "blocked_at": 9, "run_id": self.run_record.run_id}

        # Stage 10: Red Team
        if not await self.stage_10_red_team(universe):
            await self.stage_14_monitoring()
            return {"status": "failed", "blocked_at": 10, "run_id": self.run_record.run_id}

        # Stage 11: Associate Review
        if not await self.stage_11_review():
            await self.stage_14_monitoring()
            return {"status": "failed", "blocked_at": 11, "run_id": self.run_record.run_id}

        # Stage 12: Portfolio Construction
        if not await self.stage_12_portfolio(universe):
            await self.stage_14_monitoring()
            return {"status": "failed", "blocked_at": 12, "run_id": self.run_record.run_id}

        # Stage 13: Report Assembly
        if not await self.stage_13_report():
            await self.stage_14_monitoring()
            return {"status": "failed", "blocked_at": 13, "run_id": self.run_record.run_id}

        # Stage 14: Monitoring & Logging
        await self.stage_14_monitoring()

        return {
            "status": "completed",
            "run_id": self.run_record.run_id,
            "stages_completed": sorted(self.gate_results.keys()),
            "report_path": self.stage_outputs.get(13, {}).get("report_path"),
        }
