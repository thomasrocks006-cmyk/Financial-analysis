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

# New Quantitative & Governance Services
from research_pipeline.services.factor_engine import FactorExposureEngine
from research_pipeline.services.benchmark_module import BenchmarkModule
from research_pipeline.services.var_engine import VaREngine
from research_pipeline.services.portfolio_optimisation import PortfolioOptimisationEngine
from research_pipeline.services.mandate_compliance import MandateComplianceEngine
from research_pipeline.services.esg_service import ESGService
from research_pipeline.services.investment_committee import InvestmentCommitteeService
from research_pipeline.services.position_sizing import PositionSizingEngine
from research_pipeline.services.monitoring_engine import MonitoringEngine
from research_pipeline.services.performance_tracker import PerformanceTracker
from research_pipeline.services.audit_exporter import AuditExporter
from research_pipeline.services.cache_layer import CacheLayer, QuotaManager
from research_pipeline.services.rebalancing_engine import RebalancingEngine

# Governance schemas
from research_pipeline.schemas.governance import SelfAuditPacket

# New Phase 7 Services
from research_pipeline.services.etf_overlap_engine import ETFOverlapEngine
from research_pipeline.services.observability import ObservabilityService
from research_pipeline.services.report_formats import ReportFormatService

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
from research_pipeline.agents.quant_research_analyst import QuantResearchAnalystAgent
from research_pipeline.agents.fixed_income_analyst import FixedIncomeAnalystAgent
from research_pipeline.agents.esg_analyst import EsgAnalystAgent

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

        # New services — Quantitative Research Division
        self.factor_engine = FactorExposureEngine()
        self.benchmark_module = BenchmarkModule()
        self.var_engine = VaREngine()
        self.portfolio_optimisation = PortfolioOptimisationEngine()
        self.position_sizing = PositionSizingEngine()

        # New services — Governance & Compliance Division
        self.mandate_engine = MandateComplianceEngine()
        self.esg_service = ESGService()
        self.investment_committee = InvestmentCommitteeService()
        self.audit_exporter = AuditExporter(output_dir=settings.storage_dir / "audits")

        # New services — Performance & Monitoring Division
        self.performance_tracker = PerformanceTracker(storage_dir=settings.storage_dir)
        self.monitoring_engine = MonitoringEngine()
        self.rebalancing_engine = RebalancingEngine()
        self.cache = CacheLayer(cache_dir=settings.storage_dir / "cache")
        self.quota_manager = QuotaManager(quotas={"fmp_api": 250, "finnhub_api": 250, "llm_tokens": 500_000})

        # New Phase 7 Services — ETF Overlap, Observability, Report Formats
        self.etf_overlap_engine = ETFOverlapEngine()
        self.observability = ObservabilityService(
            output_dir=settings.storage_dir / "telemetry"
        )
        self.report_format_service = ReportFormatService(
            output_dir=settings.storage_dir / "reports"
        )

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
        self.quant_analyst_agent = QuantResearchAnalystAgent(**agent_kwargs)
        self.fixed_income_agent = FixedIncomeAnalystAgent(**agent_kwargs)
        self.esg_analyst_agent = EsgAnalystAgent(**agent_kwargs)

        # Run state
        self.run_record: Optional[RunRecord] = None
        self.gate_results: dict[int, GateResult] = {}
        self.stage_outputs: dict[int, Any] = {}
        self._review_result: Optional[AssociateReviewResult] = None  # set by stage_11, read by stage_13

    # ── helpers ─────────────────────────────────────────────────────────
    def _build_self_audit_packet(self, universe: list[str]) -> SelfAuditPacket:
        """Build a SelfAuditPacket from accumulated run state after Stage 14.

        Uses gate_results, stage_outputs, and _review_result — all fully
        populated by the time run_full_pipeline reaches the final return.
        """
        run_id = self.run_record.run_id if self.run_record else "unknown"
        packet = SelfAuditPacket(run_id=run_id)

        # ── Gate outcomes ───────────────────────────────────────────────
        packet.gates_passed = sorted(
            s for s, gr in self.gate_results.items() if gr.passed
        )
        packet.gates_failed = sorted(
            s for s, gr in self.gate_results.items() if not gr.passed
        )
        packet.blockers = [
            gr.reason
            for s, gr in sorted(self.gate_results.items())
            if not gr.passed and gr.reason
        ]

        # ── Agent outcomes — scan single-agent stage outputs ────────────
        # Stages that store a single AgentResult.model_dump()
        single_agent_stages = [5, 7, 9, 10, 11]
        for stage_num in single_agent_stages:
            result = self.stage_outputs.get(stage_num)
            if isinstance(result, dict):
                name = result.get("agent_name", f"stage_{stage_num}")
                if result.get("success"):
                    packet.agents_succeeded.append(name)
                else:
                    packet.agents_failed.append(name)

        # Stage 6 stores {sector_outputs: [...], esg_output: {...|None}}
        sector_results = self._get_sector_outputs()
        if isinstance(sector_results, list):
            for res in sector_results:
                if isinstance(res, dict):
                    name = res.get("agent_name", "sector_analyst")
                    (packet.agents_succeeded if res.get("success") else packet.agents_failed).append(name)

        # Stage 8 may store [macro_result, political_result] or a single dict
        stage8 = self.stage_outputs.get(8)
        if isinstance(stage8, list):
            for res in stage8:
                if isinstance(res, dict):
                    name = res.get("agent_name", "macro_agent")
                    (packet.agents_succeeded if res.get("success") else packet.agents_failed).append(name)
        elif isinstance(stage8, dict):
            name = stage8.get("agent_name", "macro_agent")
            (packet.agents_succeeded if stage8.get("success") else packet.agents_failed).append(name)

        # ── Evidence / claim metrics from Stage 5 parsed output ─────────
        stage5 = self.stage_outputs.get(5, {})
        if isinstance(stage5, dict):
            parsed5 = stage5.get("parsed_output") or {}
            claims = parsed5.get("claims", [])
            sources = parsed5.get("sources", [])

            packet.total_claims = len(claims)
            for claim in claims:
                status = str(claim.get("status", "")).lower()
                if status == "pass":
                    packet.pass_claims += 1
                elif status == "caveat":
                    packet.caveat_claims += 1
                elif status == "fail":
                    packet.fail_claims += 1

            for src in sources:
                tier = int(src.get("tier", 4))
                if tier == 1:
                    packet.tier1_claims += 1
                elif tier == 2:
                    packet.tier2_claims += 1
                elif tier == 3:
                    packet.tier3_claims += 1
                else:
                    packet.tier4_claims += 1

        # ── Methodology compliance from Stage 11 review result ───────────
        if self._review_result is not None:
            packet.methodology_tags_present = bool(
                getattr(self._review_result, "methodology_tags_complete", False)
            )
            packet.dates_complete = bool(
                getattr(self._review_result, "dates_complete", False)
            )

        # ── Red team coverage from Stage 10 ─────────────────────────────
        stage10 = self.stage_outputs.get(10, {})
        if isinstance(stage10, dict):
            parsed10 = stage10.get("parsed_output") or {}
            # Accept either a list under "falsification_tests" or a numeric count
            ft = parsed10.get("falsification_tests", [])
            if isinstance(ft, list):
                packet.min_falsification_tests = len(ft)
            elif isinstance(ft, (int, float)):
                packet.min_falsification_tests = int(ft)

        # All tickers are covered by a single red-team agent call
        if self.gate_results.get(10) and self.gate_results[10].passed:
            packet.tickers_with_red_team = list(universe)

        # ── IC outcome from Stage 12 ─────────────────────────────────────
        stage12 = self.stage_outputs.get(12, {})
        if isinstance(stage12, dict):
            packet.ic_approved = stage12.get("ic_approved")
            ic_rec = stage12.get("ic_record") or {}
            raw_votes = ic_rec.get("votes", {})
            if isinstance(raw_votes, dict):
                packet.ic_vote_breakdown = {k: str(v) for k, v in raw_votes.items()}

        # ── Mandate & ESG from Stage 12 ──────────────────────────────────
            mandate = stage12.get("mandate_compliance") or {}
            packet.mandate_compliant = mandate.get("is_compliant")
            esg_excl = stage12.get("esg_exclusions") or []
            if isinstance(esg_excl, list):
                packet.esg_exclusions = [
                    e.get("ticker", str(e)) if isinstance(e, dict) else str(e)
                    for e in esg_excl
                ]

        # ── Compute quality score ────────────────────────────────────────
        packet.compute_quality_score()

        return packet

    def _get_sector_outputs(self) -> list:
        """Return sector agent results from stage_outputs[6].

        Handles both the legacy format (plain list) and the current dict format
        introduced in session 6: {sector_outputs: [...], esg_output: {...}}.
        """
        raw = self.stage_outputs.get(6)
        if isinstance(raw, dict):
            return raw.get("sector_outputs", [])
        if isinstance(raw, list):
            return raw
        return []

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

        # ── ESG analysis — non-critical-path, runs after sector agents ──
        esg_result_dump: dict | None = None
        try:
            esg_result = await self.esg_analyst_agent.run(
                self.run_record.run_id,
                {
                    "tickers": universe,
                    "sector_outputs": [r.model_dump() for r in results],
                    "market_data": mkt_data,
                },
            )
            esg_result_dump = esg_result.model_dump()
            logger.info(
                "ESG analysis complete — success=%s tickers=%d",
                esg_result.success,
                len((esg_result.parsed_output or {}).get("esg_scores", [])),
            )
        except Exception as exc:
            logger.warning("ESG analyst failed (non-blocking): %s", exc)

        self._save_stage_output(6, {
            "sector_outputs": [r.model_dump() for r in results],
            "esg_output": esg_result_dump,
        })
        gate = self.gates.gate_6_sector_analysis(four_box_count, expected_count=expected_count)
        return self._check_gate(gate)

    async def stage_7_valuation(self, universe: list[str]) -> bool:
        """Stage 7: Valuation & Modelling."""
        logger.info("═══ STAGE 7: Valuation & Modelling ═══")
        result = await self.valuation_agent.run(
            self.run_record.run_id,
            {
                "tickers": universe,
                "sector_outputs": self._get_sector_outputs(),
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
        """Stage 9: Quant Risk & Scenario Testing — enhanced with factor, VaR, benchmark analytics."""
        logger.info("═══ STAGE 9: Quant Risk & Scenario Testing ═══")

        # Run scenario stress engine
        scenario_results = self.scenario_engine.run_all_scenarios(universe)

        # Factor exposure analysis
        factor_exposures = self.factor_engine.compute_factor_exposures(universe)
        factor_data = [fe.model_dump() for fe in factor_exposures]

        # Portfolio factor exposure (if weights provided)
        portfolio_factor_exp = None
        if weights:
            portfolio_factor_exp = self.factor_engine.portfolio_factor_exposure(factor_exposures, weights)

        # VaR analysis (using synthetic returns if no market data available)
        var_result = None
        drawdown_result = None
        try:
            import numpy as np
            np.random.seed(42)
            # Generate synthetic returns based on factor betas for demonstration
            synthetic_returns = np.random.normal(0.001, 0.02, 252).tolist()
            var_result = self.var_engine.parametric_var(
                run_id=self.run_record.run_id,
                portfolio_returns=synthetic_returns,
                confidence_level=0.95,
            )
            drawdown_result = self.var_engine.compute_drawdown_analysis(
                self.run_record.run_id, synthetic_returns
            )
        except Exception as exc:
            logger.warning("VaR computation failed: %s", exc)

        risk_packet = self.risk_engine.build_risk_packet(
            run_id=self.run_record.run_id,
            weights={t: 1.0 / len(universe) for t in universe},
            returns={t: [] for t in universe},   # synthetic returns present in var_result
            subthemes={t: "compute" for t in universe},
            var_result=var_result,
            drawdown=drawdown_result,
        )
        risk_packet.scenario_results = scenario_results

        # Build enhanced risk output — start from the typed packet
        risk_output = risk_packet.model_dump()
        risk_output["factor_exposures"] = factor_data
        if portfolio_factor_exp:
            risk_output["portfolio_factor_exposure"] = portfolio_factor_exp
        # Keep var_95 alias so quant agent and legacy code still find it
        if var_result:
            risk_output["var_95"] = var_result.model_dump()

        # Phase 2.7 / 7.4: ETF overlap analysis
        try:
            etf_overlaps = self.etf_overlap_engine.analyse_portfolio(
                run_id=self.run_record.run_id,
                portfolio_weights={t: 1.0 / len(universe) for t in universe},
            )
            risk_output["etf_overlap"] = etf_overlaps.to_dict()
            risk_output["etf_differentiation_score"] = etf_overlaps.differentiation_score
            if self.etf_overlap_engine.flag_etf_replication(etf_overlaps):
                logger.warning(
                    "ETF OVERLAP WARNING: portfolio exceeds replication threshold — "
                    "differentiation_score=%.1f", etf_overlaps.differentiation_score
                )
        except Exception as exc:
            logger.warning("ETF overlap analysis failed: %s", exc)

        # Quant Research Analyst — LLM interpretation of all deterministic quant outputs
        try:
            quant_agent_result = await self.quant_analyst_agent.run(
                self.run_record.run_id,
                {
                    "factor_exposures": factor_data,
                    "var_metrics": risk_output.get("var_95"),
                    "benchmark_analytics": risk_output.get("portfolio_factor_exposure"),
                    "etf_overlap": risk_output.get("etf_overlap"),
                    "risk_engine": {
                        "scenario_count": len(scenario_results),
                        "drawdown_analysis": risk_output.get("drawdown_analysis"),
                    },
                    "scenario_results": [s.model_dump() if hasattr(s, "model_dump") else s for s in scenario_results],
                },
            )
            if quant_agent_result.success and quant_agent_result.parsed_output:
                risk_output["quant_research_commentary"] = quant_agent_result.parsed_output
            else:
                logger.warning("Quant Research Analyst agent did not produce output — continuing")
        except Exception as exc:
            logger.warning("Quant Research Analyst agent failed: %s", exc)

        # P-7: Fixed Income Analyst — macro rate/credit context for equity thesis
        try:
            # Assemble fixed-income context packet
            fi_inputs = {
                "universe": universe,
                "macro_context": {
                    "note": (
                        "Live yield/spread data not available in this run. "
                        "Interpret using internal heuristics."
                    ),
                },
                "leverage_data": {
                    # Pull ND/EBITDA from DCF assumptions where available
                    t: self.stage_outputs.get(7, {}).get(t, {}).get("net_debt")
                    for t in universe
                },
                "var_metrics": risk_output.get("var_95", {}),
                "scenario_results": [
                    (s.model_dump() if hasattr(s, "model_dump") else s)
                    for s in scenario_results
                ],
            }
            fi_result = await self.fixed_income_agent.run(
                self.run_record.run_id, fi_inputs
            )
            if fi_result.success and fi_result.parsed_output:
                risk_output["fixed_income_context"] = fi_result.parsed_output
                logger.info(
                    "Fixed Income Analyst: rate_sensitivity_score=%.1f  "
                    "yield_curve_regime=%s",
                    fi_result.parsed_output.get("rate_sensitivity_score", 0),
                    fi_result.parsed_output.get("yield_curve_regime", "?"),
                )
            else:
                logger.warning("Fixed Income Analyst agent did not produce output — continuing")
        except Exception as exc:
            logger.warning("Fixed Income Analyst agent failed: %s", exc)

        self._save_stage_output(9, risk_output)
        gate = self.gates.gate_9_risk(
            risk_packet_present=risk_packet is not None,
            scenario_results_count=len(scenario_results),
            concentration_breaches=[
                f"{t}: weight={(1.0/len(universe)):.2%}"
                for t in universe
                if (1.0 / len(universe)) > 0.40  # flag single names >40% weight
            ] if universe else [],
        )
        return self._check_gate(gate)

    async def stage_10_red_team(self, universe: list[str]) -> bool:
        """Stage 10: Red Team."""
        logger.info("═══ STAGE 10: Red Team ═══")
        result = await self.red_team_agent.run(
            self.run_record.run_id,
            {
                "tickers": universe,
                "sector_outputs": self._get_sector_outputs(),
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
                "sector_outputs": self._get_sector_outputs(),
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
            # Agent must return explicit {"status": "pass"|"fail", ...}
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
        """Stage 12: Portfolio Construction — enhanced with mandate, ESG, optimisation, IC."""
        logger.info("═══ STAGE 12: Portfolio Construction ═══")
        # Check that review passed
        review_gate = self.gate_results.get(11)
        if not review_gate or not review_gate.passed:
            gate = self.gates.gate_12_portfolio(0, review_passed=False)
            return self._check_gate(gate)

        # ESG compliance check
        esg_result = self.esg_service.check_portfolio_esg_compliance(tickers=universe)
        esg_excluded = esg_result.get("excluded_tickers", [])
        esg_clean_universe = [t for t in universe if t not in [e["ticker"] for e in esg_excluded]]

        if esg_excluded:
            logger.warning("ESG exclusions: %s", [e["ticker"] for e in esg_excluded])

        # Position sizing (equal weight as baseline)
        baseline_weights = self.position_sizing.equal_weight(esg_clean_universe)

        # Mandate compliance check on baseline weights
        mandate_check = self.mandate_engine.check_compliance(
            run_id=self.run_record.run_id,
            weights=baseline_weights,
        )

        if not mandate_check.is_compliant:
            logger.warning("Mandate violations on baseline: %s", [v.description for v in mandate_check.violations])

        # Run PM agent for variant construction
        result = await self.pm_agent.run(
            self.run_record.run_id,
            {
                "universe": esg_clean_universe,
                "sector_outputs": self._get_sector_outputs(),
                "valuation_outputs": self.stage_outputs.get(7, {}),
                "red_team_outputs": self.stage_outputs.get(10, {}),
                "risk_outputs": self.stage_outputs.get(9, {}),
                "review_outputs": self.stage_outputs.get(11, {}),
                "esg_result": esg_result,
                "mandate_check": mandate_check.model_dump(),
                "baseline_weights": baseline_weights,
            },
        )

        # Investment Committee voting
        gate_summary = {
            "total_stages": 15,
            "completed_stages": sum(1 for g in self.gate_results.values() if g.passed),
            "failed_gates": [str(s) for s, g in self.gate_results.items() if not g.passed],
        }
        risk_summary = {}
        risk_output = self.stage_outputs.get(9, {})
        if risk_output:
            var_data = risk_output.get("var_95", {})
            risk_summary = {
                "concentration_hhi": sum(w ** 2 for w in baseline_weights.values()),
                "max_single_position_weight": max(baseline_weights.values()) if baseline_weights else 0,
                "var_95_pct": var_data.get("var_pct") if var_data else None,
            }

        review_for_ic = None
        if self._review_result:
            review_for_ic = {
                "status": self._review_result.status.value,
                "issues": [{"description": i.description, "severity": i.severity} for i in self._review_result.issues],
            }

        ic_record = self.investment_committee.evaluate_and_vote(
            run_id=self.run_record.run_id,
            gate_results=gate_summary,
            mandate_check=mandate_check,
            risk_summary=risk_summary,
            review_result=review_for_ic,
        )

        # Create audit trail
        audit_trail = self.investment_committee.create_audit_trail(self.run_record.run_id)
        self.investment_committee.record_committee_decision(audit_trail, ic_record)

        self._save_stage_output(12, {
            "pm_result": result.model_dump(),
            "esg_compliance": esg_result,
            "mandate_compliance": mandate_check.model_dump(),
            "baseline_weights": baseline_weights,
            "ic_record": ic_record.model_dump(),
            "ic_approved": ic_record.is_approved,
            "audit_trail": audit_trail.model_dump(),
        })

        # Check mandate compliance violations for gate
        mandate_violations = [
            v.description for v in mandate_check.violations
        ] if not mandate_check.is_compliant else []

        gate = self.gates.gate_12_portfolio(
            variants_count=3 if result.success else 0,
            review_passed=ic_record.is_approved,  # IC vote must approve; hard False blocks downstream
            constraint_violations=mandate_violations or None,
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
        gate = self.gates.gate_13_report(
            report_generated=True,
            all_sections_approved=review_result.is_publishable,  # use reviewer verdict, not hardcoded True
        )
        return self._check_gate(gate)

    async def stage_14_monitoring(self) -> None:
        """Stage 14: Monitoring, Registry, Governance Audit, and Post-Run Logging."""
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

        # Export governance audit
        stage_12_output = self.stage_outputs.get(12, {})
        audit_trail_data = stage_12_output.get("audit_trail")
        ic_record_data = stage_12_output.get("ic_record")
        mandate_data = stage_12_output.get("mandate_compliance")
        esg_data = stage_12_output.get("esg_compliance")

        try:
            gate_results_for_audit = {
                str(s): {"passed": g.passed, "reason": g.reason}
                for s, g in self.gate_results.items()
            }
            risk_output = self.stage_outputs.get(9, {})

            audit_path = self.audit_exporter.export_full_audit(
                run_id=self.run_record.run_id,
                audit_trail=audit_trail_data,
                committee_record=ic_record_data,
                mandate_check=mandate_data,
                gate_results=gate_results_for_audit,
                pipeline_metadata={
                    "stages_completed": [s for s, g in self.gate_results.items() if g.passed],
                    "stages_failed": failed_stages,
                    "final_status": final_status.value,
                },
                esg_results=esg_data,
                risk_summary=risk_output,
            )
            logger.info("Governance audit exported to %s", audit_path)
        except Exception as exc:
            logger.warning("Audit export failed: %s", exc)

        # Save performance snapshot if stage 12 produced weights
        baseline_weights = stage_12_output.get("baseline_weights", {})
        if baseline_weights:
            try:
                from research_pipeline.schemas.performance import PortfolioSnapshot
                snapshot = PortfolioSnapshot(
                    run_id=self.run_record.run_id,
                    variant_name="baseline",
                    positions=baseline_weights,
                )
                self.performance_tracker.save_snapshot(snapshot)
                logger.info("Portfolio snapshot saved for run %s", self.run_record.run_id)
            except Exception as exc:
                logger.warning("Snapshot save failed: %s", exc)

        self._save_stage_output(14, {
            "final_status": final_status.value,
            "stages_completed": [s for s, g in self.gate_results.items() if g.passed],
            "stages_failed": failed_stages,
            "gate_summary": {s: g.reason for s, g in self.gate_results.items()},
            "cache_stats": self.cache.stats,
        })
        logger.info("Pipeline run %s finished with status: %s", self.run_record.run_id, final_status.value)

    # ── Full pipeline execution ────────────────────────────────────────
    async def run_full_pipeline(self, universe: list[str]) -> dict[str, Any]:
        """Execute the full 15-stage pipeline end-to-end."""
        logger.info("╔══════════════════════════════════════════════╗")
        logger.info("║  AI Infrastructure Research Pipeline v8      ║")
        logger.info("║  Starting full pipeline run                  ║")
        logger.info("╚══════════════════════════════════════════════╝")

        # Phase 7.5: Start observability tracking
        if self.run_record:
            self.observability.start_run(self.run_record.run_id)

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

        # Phase 7.5: End observability tracking and save telemetry
        if self.run_record:
            try:
                run_obs = self.observability.end_run(self.run_record.run_id)
                telemetry_path = self.observability.save(self.run_record.run_id)
                logger.info(
                    "Observability saved to %s | total_cost=$%.4f | duration=%.1fs",
                    telemetry_path, run_obs.total_llm_cost_usd, run_obs.total_duration_seconds,
                )
            except Exception as exc:
                logger.warning("Observability save failed: %s", exc)

            # Phase 7.9: Render client reports
            try:
                pipeline_output_for_reports = {
                    "final_report": self.stage_outputs.get(13, {}),
                    "portfolio": self.stage_outputs.get(12, {}),
                    "risk_package": self.stage_outputs.get(9, {}),
                    "ic_outcome": self.stage_outputs.get(12, {}).get("ic_record", {}),
                    "mandate_result": self.stage_outputs.get(12, {}).get("mandate", {}),
                    "sector_outputs": self._get_sector_outputs(),
                    "valuations": self.stage_outputs.get(7, {}),
                    "red_team": self.stage_outputs.get(10, {}),
                }
                report_paths = self.report_format_service.save_all(
                    self.run_record.run_id, pipeline_output_for_reports
                )
                logger.info("Reports saved: %s", [str(p) for p in report_paths])
            except Exception as exc:
                logger.warning("Report format rendering failed: %s", exc)

        # ── ACT-S6-1: Build and attach SelfAuditPacket ────────────────────
        audit_packet: Optional[SelfAuditPacket] = None
        try:
            audit_packet = self._build_self_audit_packet(universe)
            if self.run_record:
                self.run_record.self_audit_packet = audit_packet.model_dump(mode="json")
                self.registry.update_run(self.run_record)
            # Persist as a named artifact alongside other stage outputs
            if self.run_record:
                audit_dir = self.settings.storage_dir / "artifacts" / self.run_record.run_id
                audit_dir.mkdir(parents=True, exist_ok=True)
                (audit_dir / "self_audit_packet.json").write_text(
                    audit_packet.model_dump_json(indent=2)
                )
            logger.info(
                "SelfAuditPacket built — quality_score=%.1f gates_passed=%d agents_succeeded=%d",
                audit_packet.publication_quality_score,
                len(audit_packet.gates_passed),
                len(audit_packet.agents_succeeded),
            )
        except Exception as exc:
            logger.warning("SelfAuditPacket build failed (non-blocking): %s", exc)

        return {
            "status": "completed",
            "run_id": self.run_record.run_id,
            "stages_completed": sorted(self.gate_results.keys()),
            "report_path": self.stage_outputs.get(13, {}).get("report_path"),
            "audit_packet": audit_packet.model_dump(mode="json") if audit_packet else None,
        }
