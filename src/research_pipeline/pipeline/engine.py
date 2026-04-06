"""Pipeline execution engine — orchestrates all 15 stages."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

from research_pipeline.config.loader import PipelineConfig, load_pipeline_config  # noqa: F401 – re-exported for test patching
from research_pipeline.config.settings import Settings
from research_pipeline.pipeline.gates import GateResult, PipelineGates
from research_pipeline.schemas.claims import ClaimLedger
from research_pipeline.schemas.market_data import (
    MarketSnapshot,
)
from research_pipeline.schemas.portfolio import (
    AssociateReviewResult,
    PublicationStatus,
)
from research_pipeline.schemas.registry import RunRecord, RunStatus

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
from research_pipeline.services.live_return_store import LiveReturnStore  # ACT-S8-1
from research_pipeline.services.prompt_registry import PromptRegistry  # ACT-S8-4

# Governance schemas
from research_pipeline.schemas.governance import SelfAuditPacket

# New Phase 7 Services
from research_pipeline.services.etf_overlap_engine import ETFOverlapEngine
from research_pipeline.services.observability import ObservabilityService
from research_pipeline.services.report_formats import ReportFormatService

# Session 19 / DSQ-1: Qualitative data service — closes the biggest live evidence gap
from research_pipeline.services.qualitative_data_service import QualitativeDataService

# Session 19 / DSQ-2: SEC API service — Tier 1 primary US filing data
from research_pipeline.services.sec_api_service import SECApiService

# Session 19 / DSQ-3: Benzinga service — Tier 2 finance-native news + analyst ratings
from research_pipeline.services.benzinga_service import BenzingaService

# GDR-1: Gemini Deep Research Stage 4.5 — fires between Stage 4 (Data QA) and Stage 5
from research_pipeline.services.gemini_deep_research import (
    GeminiDeepResearchService,
    DeepResearchRunResult,
    deep_research_claim_to_ledger_dict,
)

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
from research_pipeline.agents.generic_sector_analyst import GenericSectorAnalystAgent

# ARC-1: Macro context packet for cross-stage wiring
from research_pipeline.schemas.macro import MacroContextPacket

# ARC-5: Externalised sector routing
from research_pipeline.config.loader import SECTOR_ROUTING

# Session 12: Macro Economy module
from research_pipeline.agents.economy_analyst import EconomyAnalystAgent
from research_pipeline.services.economic_indicator_service import EconomicIndicatorService
from research_pipeline.services.macro_scenario_service import MacroScenarioService
from research_pipeline.schemas.macro_economy import (
    EconomicIndicators,
    EconomyAnalysis,
    MacroScenario,
)

# Session 12 (ISS-13): ASX sector analyst
from research_pipeline.agents.sector_analyst_asx import SectorAnalystASX, is_asx_ticker

# Session 13: Depth & Quality — new services and agents
from research_pipeline.agents.report_narrative_agent import ReportNarrativeAgent
from research_pipeline.services.sector_data_service import SectorDataService
from research_pipeline.services.factor_engine import FREDFactorFetcher

# Session 14: Australian Client Context
from research_pipeline.services.superannuation_mandate import SuperannuationMandateService
from research_pipeline.services.australian_tax_service import AustralianTaxService

# Session 15: Event stream contract (Phase 2)
from typing import Awaitable, Callable
from research_pipeline.schemas.events import PipelineEvent, STAGE_LABELS

# Session 17: Traceability & Provenance
from research_pipeline.services.provenance_service import ProvenanceService

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
        self.live_return_store = LiveReturnStore()  # ACT-S8-1
        self.prompt_registry = PromptRegistry(  # ACT-S8-4
            storage_dir=settings.storage_dir / "prompt_registry"
        )
        self.cache = CacheLayer(cache_dir=settings.storage_dir / "cache")
        self.quota_manager = QuotaManager(
            quotas={"fmp_api": 250, "finnhub_api": 250, "llm_tokens": 500_000}
        )

        # New Phase 7 Services — ETF Overlap, Observability, Report Formats
        self.etf_overlap_engine = ETFOverlapEngine()
        self.observability = ObservabilityService(output_dir=settings.storage_dir / "telemetry")
        self.report_format_service = ReportFormatService(
            output_dir=settings.storage_dir / "reports"
        )

        # Initialize agents
        prompts_dir = settings.prompts_dir
        agent_kwargs = {
            "model": settings.llm_model,
            "temperature": settings.llm_temperature,
            "prompts_dir": prompts_dir,
        }
        self.orchestrator_agent = OrchestratorAgent(**agent_kwargs)
        self.evidence_agent = EvidenceLibrarianAgent(**agent_kwargs)
        self.compute_analyst = SectorAnalystCompute(**agent_kwargs)
        self.power_analyst = SectorAnalystPowerEnergy(**agent_kwargs)
        self.infra_analyst = SectorAnalystInfrastructure(**agent_kwargs)
        self.generic_analyst = GenericSectorAnalystAgent(
            **agent_kwargs
        )  # ARC-5: fallback for unmapped tickers
        self.asx_analyst = SectorAnalystASX(**agent_kwargs)  # ISS-13: ASX sector specialist
        self.valuation_agent = ValuationAnalystAgent(**agent_kwargs)
        self.macro_agent = MacroStrategistAgent(**agent_kwargs)
        self.political_agent = PoliticalRiskAnalystAgent(**agent_kwargs)
        self.red_team_agent = RedTeamAnalystAgent(**agent_kwargs)
        self.reviewer_agent = AssociateReviewerAgent(**agent_kwargs)
        self.pm_agent = PortfolioManagerAgent(**agent_kwargs)
        self.quant_analyst_agent = QuantResearchAnalystAgent(**agent_kwargs)
        self.fixed_income_agent = FixedIncomeAnalystAgent(**agent_kwargs)
        self.esg_analyst_agent = EsgAnalystAgent(**agent_kwargs)
        # Session 12: Economy Analyst Agent + data services
        self.economy_analyst = EconomyAnalystAgent(**agent_kwargs)
        self.economic_indicator_svc = EconomicIndicatorService(
            fred_api_key=config.market_config.fred_api_key
        )
        self.macro_scenario_svc = MacroScenarioService()
        # Session 13: Sector data service, narrative agent, FRED factor fetcher
        self.sector_data_svc = SectorDataService(
            fmp_api_key=settings.api_keys.fmp_api_key
            if hasattr(settings, "api_keys") and settings.api_keys
            else None
        )
        self.fred_factor_fetcher = FREDFactorFetcher(fred_api_key=config.market_config.fred_api_key)
        self.report_narrative_agent = ReportNarrativeAgent(**agent_kwargs)
        # Session 14: AU client context services
        self.super_mandate_svc = SuperannuationMandateService()
        self.tax_svc = AustralianTaxService()

        # Session 15: optional event callback — async (event) -> None
        # Set by the FastAPI RunManager before calling run_full_pipeline().
        self._event_callback: Optional[Callable[[PipelineEvent], Awaitable[None]]] = None

        # Session 17: Provenance service — builds per-stage lineage cards
        self._provenance: Optional[ProvenanceService] = None  # initialised in run_full_pipeline

        # Session 19 / DSQ-1: Qualitative data service (news, transcripts, filings,
        # insider activity, analyst actions, sentiment — 7 sources per ticker).
        self.qualitative_svc = QualitativeDataService(
            fmp_key=settings.api_keys.fmp_api_key,
            finnhub_key=settings.api_keys.finnhub_api_key,
        )

        # Session 19 / DSQ-2: SEC API service — Tier 1 primary US filing data.
        # Gracefully no-ops when SEC_API_KEY is absent.
        self.sec_api_svc = SECApiService(
            api_key=settings.api_keys.sec_api_key,
        )

        # Session 19 / DSQ-3: Benzinga service — Tier 2 finance-native news + ratings.
        # Gracefully no-ops when BENZINGA_API_KEY is absent.
        self.benzinga_svc = BenzingaService(
            api_key=settings.api_keys.benzinga_api_key,
        )

        # GDR-1: Gemini Deep Research service — Stage 4.5 (non-blocking).
        # Gracefully degrades when GEMINI_API_KEY is absent or google-generativeai
        # is not installed. Never blocks Stage 5.
        try:
            _gdr_cfg = config.deep_research.model_dump()
            if not isinstance(_gdr_cfg, dict):
                _gdr_cfg = {}
        except Exception:
            _gdr_cfg = {}
        self.gemini_deep_research_svc = GeminiDeepResearchService(config=_gdr_cfg)

        self.run_record: Optional[RunRecord] = None
        self.gate_results: dict[int, GateResult] = {}
        self.stage_outputs: dict[int, Any] = {}
        self._review_result: Optional[AssociateReviewResult] = (
            None  # set by stage_11, read by stage_13
        )
        # ACT-S7-3: per-stage timing
        self._stage_timings: dict[int, float] = {}  # stage_num -> elapsed_ms
        self._pipeline_start: float = 0.0

    # ── helpers ─────────────────────────────────────────────────────────
    def _build_self_audit_packet(self, universe: list[str]) -> SelfAuditPacket:
        """Build a SelfAuditPacket from accumulated run state after Stage 14.

        Uses gate_results, stage_outputs, and _review_result — all fully
        populated by the time run_full_pipeline reaches the final return.
        """
        run_id = self.run_record.run_id if self.run_record else "unknown"
        packet = SelfAuditPacket(run_id=run_id)

        # ── Gate outcomes ───────────────────────────────────────────────
        packet.gates_passed = sorted(s for s, gr in self.gate_results.items() if gr.passed)
        packet.gates_failed = sorted(s for s, gr in self.gate_results.items() if not gr.passed)
        packet.blockers = [
            gr.reason for s, gr in sorted(self.gate_results.items()) if not gr.passed and gr.reason
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
                    (
                        packet.agents_succeeded if res.get("success") else packet.agents_failed
                    ).append(name)

        # Stage 8 may store [macro_result, political_result] or a single dict
        stage8 = self.stage_outputs.get(8)
        if isinstance(stage8, list):
            for res in stage8:
                if isinstance(res, dict):
                    name = res.get("agent_name", "macro_agent")
                    (
                        packet.agents_succeeded if res.get("success") else packet.agents_failed
                    ).append(name)
        elif isinstance(stage8, dict):
            name = stage8.get("agent_name", "macro_agent")
            (packet.agents_succeeded if stage8.get("success") else packet.agents_failed).append(
                name
            )

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
            packet.dates_complete = bool(getattr(self._review_result, "dates_complete", False))

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
                    e.get("ticker", str(e)) if isinstance(e, dict) else str(e) for e in esg_excl
                ]

        # ── Compute quality score ────────────────────────────────────────
        packet.compute_quality_score()

        # ── ACT-S7-3: per-stage latencies ────────────────────────────────
        packet.stage_latencies_ms = {f"stage_{s}": ms for s, ms in self._stage_timings.items()}
        if self._pipeline_start > 0:
            packet.total_pipeline_duration_s = round(time.monotonic() - self._pipeline_start, 2)

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

    def _get_macro_context(self) -> MacroContextPacket:
        """ARC-1: Return typed MacroContextPacket from Stage 8 output.

        Returns an empty packet (default values) if Stage 8 has not yet run or
        failed.  Callers should check ``packet.regime_classification`` before
        relying on the content.
        """
        run_id = self.run_record.run_id if self.run_record else "unknown"
        stage8 = self.stage_outputs.get(8)
        if not stage8:
            return MacroContextPacket(run_id=run_id)
        # stage_8 stores {"macro": AgentResult.model_dump(), "political": ...}
        macro_agent_output = stage8.get("macro", {})
        parsed = macro_agent_output.get("parsed_output") or {}
        if not parsed:
            return MacroContextPacket(run_id=run_id)
        return MacroContextPacket.from_stage_8_output(parsed, run_id)

    def _emit_audit_packet(self, universe: list[str]) -> "Optional[SelfAuditPacket]":
        """Build, persist and attach the SelfAuditPacket for every pipeline exit.

        Called from both the success path and every early-exit (gate failure)
        so the audit packet is always available in the returned result dict.
        Non-fatal — returns None on any exception.
        """
        try:
            packet = self._build_self_audit_packet(universe)
            if self.run_record:
                self.run_record.self_audit_packet = packet.model_dump(mode="json")
                self.registry.update_run(self.run_record)
                audit_dir = self.settings.storage_dir / "artifacts" / self.run_record.run_id
                audit_dir.mkdir(parents=True, exist_ok=True)
                (audit_dir / "self_audit_packet.json").write_text(packet.model_dump_json(indent=2))
            # ACT-S9-3: populate rebalancing_summary from stage 12 output
            try:
                rp = self.stage_outputs.get(12, {}).get("rebalance_proposal") or {}
                if rp:
                    packet.rebalancing_summary = {
                        "trade_count": len(rp.get("trades", [])),
                        "total_turnover_pct": rp.get("total_turnover_pct", 0.0),
                        "estimated_total_impact_bps": rp.get("estimated_total_impact_bps", 0.0),
                        "trigger": rp.get("trigger", ""),
                        "summary": rp.get("summary", ""),
                    }
            except Exception:
                pass

            logger.info(
                "SelfAuditPacket — quality=%.1f gates_passed=%d agents_ok=%d duration=%.2fs",
                packet.publication_quality_score,
                len(packet.gates_passed),
                len(packet.agents_succeeded),
                packet.total_pipeline_duration_s,
            )
            # ACT-S8-4: prompt drift scan
            self._scan_prompt_registry(packet)
            return packet
        except Exception as exc:
            logger.warning("SelfAuditPacket build failed (non-blocking): %s", exc)
            return None

    def _scan_prompt_registry(self, packet: "SelfAuditPacket") -> None:  # ACT-S8-4
        """Register current agent prompt hashes and detect drift from previous runs.

        Populates ``packet.prompt_drift_reports`` with one entry per agent.
        Changed prompts are logged as warnings.
        """
        agents = [
            self.orchestrator_agent,
            self.evidence_agent,
            self.compute_analyst,
            self.power_analyst,
            self.infra_analyst,
            self.valuation_agent,
            self.macro_agent,
            self.political_agent,
            self.red_team_agent,
            self.reviewer_agent,
            self.pm_agent,
            self.quant_analyst_agent,
            self.fixed_income_agent,
            self.esg_analyst_agent,
        ]
        drift_reports: list[dict] = []
        for agent in agents:
            try:
                prompt_id = getattr(agent, "name", agent.__class__.__name__)
                prompt_hash = getattr(agent, "prompt_hash", "")
                if not prompt_hash:
                    continue
                # Use hash as a stable content stub — avoids storing raw prompt text
                stub = f"__HASH__{prompt_hash}"
                self.prompt_registry.register_prompt(
                    prompt_id=prompt_id,
                    prompt_text=stub,
                    metadata={
                        "agent_class": agent.__class__.__name__,
                        "version_tag": getattr(agent, "version_tag", ""),
                    },
                )
                report = self.prompt_registry.check_drift(prompt_id, stub)
                drift_reports.append(report.model_dump())
            except Exception as exc:
                logger.debug("Prompt registry scan skipped for %s: %s", type(agent).__name__, exc)

        packet.prompt_drift_reports = drift_reports
        changed = sum(1 for r in drift_reports if r.get("changed", False))
        if changed:
            logger.warning("Prompt drift scan: %d agent prompt(s) changed", changed)
        else:
            logger.info("Prompt drift scan: %d agents checked, 0 changed", len(drift_reports))

    async def _emit(self, event: PipelineEvent) -> None:
        """Deliver a PipelineEvent to the registered callback, if any."""
        if self._event_callback is not None:
            try:
                await self._event_callback(event)
            except Exception:  # never let event delivery crash the pipeline
                pass

    async def _timed_stage(self, stage_num: int, coro) -> bool:  # ACT-S7-3 + Session 15
        """Await a stage coroutine, record its wall-clock duration, and emit stage events."""
        run_id = self.run_record.run_id if self.run_record else "unknown"
        await self._emit(PipelineEvent.stage_started(run_id, stage_num))
        _t = time.monotonic()
        try:
            result = await coro
            duration_ms = round((time.monotonic() - _t) * 1000, 1)
            self._stage_timings[stage_num] = duration_ms
            if result:
                await self._emit(PipelineEvent.stage_completed(run_id, stage_num, duration_ms))
            else:
                await self._emit(PipelineEvent.stage_failed(run_id, stage_num))
            return result
        except Exception as exc:
            duration_ms = round((time.monotonic() - _t) * 1000, 1)
            self._stage_timings[stage_num] = duration_ms
            await self._emit(PipelineEvent.stage_failed(run_id, stage_num, reason=str(exc)))
            raise

    def _generate_synthetic_returns(
        self,
        tickers: list[str],
        n_days: int = 252,
        seed_offset: int = 0,
    ) -> dict[str, list[float]]:
        """Generate reproducible synthetic daily returns for optimisation and attribution.

        Returns are drawn from N(mu, sigma) using per-ticker seeds derived from
        the ticker symbol.  Parameters are intentionally conservative — this is a
        structural / demo implementation until a live price feed is available.
        The seed is deterministic so the same universe always produces the same
        synthetic history within a session.
        """
        import hashlib

        # Tier-1 volatility assumptions (annualised sigma) keyed by ticker
        _SIGMA = {
            "NVDA": 0.58,
            "AMD": 0.52,
            "AVGO": 0.38,
            "MRVL": 0.48,
            "ARM": 0.55,
            "TSM": 0.40,
            "MSFT": 0.28,
            "AMZN": 0.32,
            "GOOGL": 0.30,
            "META": 0.43,
            "EQIX": 0.22,
            "DLR": 0.22,
            "VRT": 0.44,
            "DELL": 0.40,
            "SMCI": 0.72,
        }
        _MU = 0.15  # conservative annual return assumption

        result: dict[str, list[float]] = {}
        for ticker in tickers:
            sigma_ann = _SIGMA.get(ticker, 0.40)
            sigma_daily = sigma_ann / (252**0.5)
            mu_daily = _MU / 252
            # Deterministic seed from ticker name
            raw_seed = int(hashlib.md5(ticker.encode()).hexdigest()[:8], 16)
            rng = __import__("numpy").random.default_rng(raw_seed + seed_offset)
            rets = rng.normal(mu_daily, sigma_daily, n_days).tolist()
            result[ticker] = rets
        return result

    def _get_returns(
        self,
        tickers: list[str],
        n_days: int = 252,
        seed_offset: int = 0,
    ) -> dict[str, list[float]]:
        """Get daily returns — live data (yfinance) preferred, synthetic fallback.

        ACT-S8-1: Tries ``LiveReturnStore`` first.  If every requested ticker
        succeeds, the live series is returned (variable length per ticker).
        If any ticker fails to fetch, falls back to the deterministic synthetic
        series so the optimiser / BHB attribution always have a complete set.
        """
        try:
            live = self.live_return_store.fetch(tickers)
            if live and len(live) == len(tickers):
                logger.info("_get_returns: live yfinance data for all %d tickers", len(tickers))
                return live
            if live:
                # ACT-S9-4: ticker-level fallback — blend live data with synthetic for missing
                missing = [t for t in tickers if t not in live]
                synth = self._generate_synthetic_returns(
                    missing, n_days=n_days, seed_offset=seed_offset
                )
                merged = {**synth, **live}  # live data overrides synthetic where available
                logger.info(
                    "_get_returns: blended %d live + %d synthetic (ticker-level fallback)",
                    len(live),
                    len(missing),
                )
                return merged
        except Exception as exc:
            logger.debug("_get_returns: live fetch error — %s", exc)
        return self._generate_synthetic_returns(tickers, n_days=n_days, seed_offset=seed_offset)

    def _save_stage_output(self, stage: int, data: Any) -> None:
        """Persist stage output to disk and build provenance card."""
        self.stage_outputs[stage] = data
        output_dir = self.settings.storage_dir / "artifacts" / self.run_record.run_id
        output_dir.mkdir(parents=True, exist_ok=True)
        filepath = output_dir / f"stage_{stage:02d}.json"
        filepath.write_text(json.dumps(data, indent=2, default=str))
        logger.info("Stage %d output saved to %s", stage, filepath)

        # Session 17: build provenance card for this stage
        if self._provenance is not None:
            try:
                gate_data = self.gate_results.get(stage)
                self._provenance.build_stage_card(
                    stage_num=stage,
                    stage_label=STAGE_LABELS.get(stage, f"Stage {stage}"),
                    stage_output=data,
                    gate_passed=gate_data.passed if gate_data else None,
                    gate_reason=gate_data.reason if gate_data else "",
                    gate_blockers=gate_data.blockers if gate_data else [],
                    duration_ms=self._stage_timings.get(stage, 0.0),
                    error=None,
                )
            except Exception as exc:
                logger.debug("Provenance card build failed for stage %d: %s", stage, exc)

    def _check_gate(self, gate_result: GateResult) -> bool:
        """Record gate result and return whether it passed."""
        self.gate_results[gate_result.stage] = gate_result
        if gate_result.passed:
            logger.info("Gate %d PASSED: %s", gate_result.stage, gate_result.reason)
            self.registry.mark_stage_complete(self.run_record.run_id, gate_result.stage)
        else:
            logger.error(
                "Gate %d FAILED: %s — %s",
                gate_result.stage,
                gate_result.reason,
                gate_result.blockers,
            )
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
            agent.name: agent.version
            for agent in [
                self.orchestrator_agent,
                self.evidence_agent,
                self.compute_analyst,
                self.power_analyst,
                self.infra_analyst,
                self.valuation_agent,
                self.macro_agent,
                self.political_agent,
                self.red_team_agent,
                self.reviewer_agent,
                self.pm_agent,
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
        self._save_stage_output(
            0,
            {
                "run_id": self.run_record.run_id,
                "universe": universe,
                "agent_versions": agent_versions,
                "golden_tests": test_results,
                "api_keys_status": "valid" if api_valid else f"missing: {missing_keys}",
            },
        )
        return self._check_gate(gate)

    async def stage_1_universe(self, universe: list[str]) -> bool:
        """Stage 1: Universe Definition."""
        logger.info("═══ STAGE 1: Universe Definition ═══")
        gate = self.gates.gate_1_universe(universe)
        self._save_stage_output(1, {"universe": universe, "count": len(universe)})
        return self._check_gate(gate)

    async def stage_2_ingestion(self, universe: list[str]) -> bool:
        """Stage 2: Data Ingestion from FMP + Finnhub + SEC API + Benzinga.

        DSQ-2 / DSQ-3 (Session 19): SEC API filing index and Benzinga rating
        changes are collected here so downstream stages (5, 10) can consume
        structured primary-source and finance-event data without re-fetching.
        Both services degrade gracefully when API keys are absent.
        """
        logger.info("═══ STAGE 2: Data Ingestion ═══")

        # Core quantitative ingestion (FMP + Finnhub + yfinance fallback)
        results = await self.ingestor.ingest_universe(universe)

        # DSQ-2: SEC API — filing index per ticker (10-K, 10-Q, 8-K, Form 4)
        # Runs concurrently after FMP/Finnhub; failures are contained per-ticker.
        try:
            sec_packages = await self.sec_api_svc.fetch_universe(universe)
            for ticker_data in results:
                if isinstance(ticker_data, dict):
                    ticker = ticker_data.get("ticker", "")
                    pkg = sec_packages.get(ticker)
                    if pkg:
                        ticker_data["sec_filings"] = [f.to_dict() for f in pkg.recent_filings]
                        ticker_data["sec_8k_events"] = pkg.eight_k_events
                        ticker_data["sec_insider_transactions"] = pkg.insider_transactions
                        if pkg.coverage_gaps:
                            ticker_data["sec_coverage_gaps"] = pkg.coverage_gaps
        except Exception as exc:
            logger.warning("SEC API stage_2 enrichment failed: %s", exc)

        # DSQ-3: Benzinga — analyst rating changes + earnings calendar
        # Adverse ratings (downgrades) are surfaced for Stage 10 Red Team use.
        try:
            benzinga_packages = await self.benzinga_svc.fetch_universe(universe)
            for ticker_data in results:
                if isinstance(ticker_data, dict):
                    ticker = ticker_data.get("ticker", "")
                    pkg = benzinga_packages.get(ticker)
                    if pkg:
                        ticker_data["benzinga_rating_changes"] = [
                            r.to_dict() for r in pkg.rating_changes
                        ]
                        ticker_data["benzinga_adverse_ratings"] = [
                            r.to_dict() for r in pkg.adverse_ratings
                        ]
                        ticker_data["benzinga_earnings_events"] = pkg.earnings_events
                        if pkg.coverage_gaps:
                            ticker_data["benzinga_coverage_gaps"] = pkg.coverage_gaps
        except Exception as exc:
            logger.warning("Benzinga stage_2 enrichment failed: %s", exc)

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
            finnhub_price: Optional[float] = (ticker_data.get("finnhub_quote") or {}).get("price")

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

    async def stage_4_5_deep_research(self, universe: list[str]) -> DeepResearchRunResult:
        """Stage 4.5: Gemini Deep Research enrichment (non-blocking).

        Fires between Stage 4 (Data QA) and Stage 5 (Evidence Librarian).
        Injects Tier-3 qualitative claims from Gemini Deep Research into
        stage_outputs[45] for Stage 5 to consume.

        GDR-1: This stage NEVER raises — all failures are absorbed and logged.
        The pipeline always proceeds to Stage 5 with or without deep-research
        enrichment. If GEMINI_API_KEY is absent the service returns gracefully.
        """
        logger.info("═══ STAGE 4.5: Gemini Deep Research ═══")
        run_id = self.run_record.run_id if self.run_record else "unknown"
        try:
            active_themes = self._get_active_themes(universe)
            result = await self.gemini_deep_research_svc.run(active_themes, run_id)
            self._save_stage_output(45, {
                "themes_succeeded": result.themes_succeeded,
                "themes_failed": result.themes_failed,
                "total_claims_injected": result.total_claims_injected,
                "skipped_reason": result.skipped_reason,
                "claims": [deep_research_claim_to_ledger_dict(c) for c in result.all_claims],
            })
            if result.all_claims:
                logger.info(
                    f"Stage 4.5: enriched with {len(result.all_claims)} deep-research claims "
                    f"from {len(result.themes_succeeded)} themes"
                )
            elif result.skipped_reason:
                logger.info(f"Stage 4.5: skipped — {result.skipped_reason}")
            return result
        except Exception as exc:
            logger.warning(f"Stage 4.5 (Gemini Deep Research) failed non-fatally: {exc}")
            return DeepResearchRunResult(
                run_id=run_id,
                timestamp="",
                themes_attempted=[],
                themes_succeeded=[],
                themes_failed=[],
                all_claims=[],
                theme_results=[],
                skipped_reason=f"unhandled_exception: {exc}",
            )

    def _get_active_themes(self, universe: list[str]) -> list[dict]:
        """Build the active_themes list for GeminiDeepResearchService.

        Loads theme definitions from configs/universe.yaml if available.
        Filters to themes whose coverage intersects the current universe.
        Falls back to a single synthetic theme covering all universe tickers.
        """
        import yaml

        deep_research_cfg = self.config.deep_research
        universe_path = deep_research_cfg.universe_config_path

        if universe_path is None:
            # Default resolution: configs/universe.yaml relative to project root
            candidate = Path(__file__).resolve().parent.parent.parent.parent / "configs" / "universe.yaml"
            if candidate.exists():
                universe_path = str(candidate)

        if universe_path and Path(universe_path).exists():
            try:
                with open(universe_path) as f:
                    raw = yaml.safe_load(f) or {}
                themes_raw = raw.get("themes", {})
                active_themes: list[dict] = []
                for key, theme_data in themes_raw.items():
                    if not isinstance(theme_data, dict):
                        continue
                    coverage = theme_data.get("coverage", [])
                    theme_tickers = [
                        c.get("ticker", "") for c in coverage if isinstance(c, dict)
                    ]
                    # Include only themes with at least one ticker in the current run
                    matching_coverage = [
                        c for c in coverage
                        if isinstance(c, dict) and c.get("ticker", "") in universe
                    ]
                    if matching_coverage:
                        active_themes.append({
                            "key": key,
                            "label": theme_data.get("label", key),
                            "deep_research_query": theme_data.get("deep_research_query", ""),
                            "coverage": matching_coverage,
                        })
                if active_themes:
                    logger.debug(
                        f"Engine._get_active_themes: loaded {len(active_themes)} themes "
                        f"from {universe_path}"
                    )
                    return active_themes
            except Exception as exc:
                logger.warning(f"Engine._get_active_themes: failed to load universe.yaml: {exc}")

        # Fallback: single synthetic theme covering entire universe
        logger.debug(
            "Engine._get_active_themes: universe.yaml not found — using synthetic fallback theme"
        )
        return [{
            "key": "run_universe",
            "label": "Research Universe",
            "deep_research_query": (
                "Synthesise the current investment outlook for {tickers} as of {date}. "
                "Assess capital position, recent earnings, regulatory risk, and competitive "
                "dynamics for each position."
            ),
            "coverage": [{"ticker": t} for t in universe],
        }]

    async def stage_5_evidence(self, universe: list[str]) -> bool:
        """Stage 5: Evidence Librarian builds claim ledger.

        Session 19 (DSQ-1/2/3): This stage now receives a rich multi-source
        evidence pack:
          - DSQ-1: QualitativeDataService — news, transcripts, FMP filing
                   metadata, insider activity, analyst actions, sentiment
          - DSQ-2: SECApiService — 10-K/Q section text (MD&A, Risk Factors,
                   Business description) as Tier 1 primary-source content
          - DSQ-3: BenzingaService — finance-native news + analyst rating
                   changes for additional qualitative grounding

        All three services degrade gracefully; failures are logged and recorded
        in coverage_gaps but never block the stage.
        """
        logger.info("═══ STAGE 5: Evidence Librarian ═══")

        # DSQ-1: Fetch qualitative data (news, transcripts, filings, insider,
        # analyst actions, sentiment) for all universe tickers concurrently.
        # Failures are absorbed inside QualitativeDataService — coverage_gaps
        # records what was unavailable so the agent can flag it.
        try:
            qual_packages_raw = await self.qualitative_svc.ingest_universe(universe)
            qualitative_data = {
                ticker: pkg.model_dump() for ticker, pkg in qual_packages_raw.items()
            }
            total_signals = sum(
                len(pkg.news_items or [])
                + len(pkg.sec_filings or [])
                + len(pkg.analyst_actions or [])
                + len(pkg.press_releases or [])
                for pkg in qual_packages_raw.values()
            )
            logger.info(
                "Qualitative data ingested: %d signal items across %d tickers",
                total_signals,
                len(universe),
            )
        except Exception as _qual_exc:
            logger.warning("Qualitative ingestion failed — continuing without it: %s", _qual_exc)
            qualitative_data = {
                t: {"ticker": t, "coverage_gaps": [f"ingest_error: {_qual_exc}"]} for t in universe
            }

        # DSQ-2: SEC API — fetch 10-K/Q section text (MD&A, Risk Factors, Business)
        # as Tier 1 primary-source content for the Evidence Librarian.
        # These are the most authoritative inputs available for US-listed names.
        sec_evidence: dict[str, Any] = {}
        try:
            sec_pkgs = await self.sec_api_svc.fetch_universe(universe)
            for ticker, pkg in sec_pkgs.items():
                if pkg.has_primary_content or pkg.eight_k_events or pkg.insider_transactions:
                    sec_evidence[ticker] = pkg.to_dict()
            if sec_evidence:
                logger.info(
                    "SEC API primary content fetched for %d/%d tickers",
                    len(sec_evidence),
                    len(universe),
                )
        except Exception as _sec_exc:
            logger.warning("SEC API evidence fetch failed — continuing without it: %s", _sec_exc)

        # DSQ-3: Benzinga — news + rating changes for evidence enrichment.
        # Adverse ratings (downgrades) from Stage 2 are already in stage_outputs[2];
        # here we fetch the full Benzinga news pack for evidence-layer consumption.
        benzinga_evidence: dict[str, Any] = {}
        try:
            benz_pkgs = await self.benzinga_svc.fetch_universe(universe)
            for ticker, pkg in benz_pkgs.items():
                if pkg.has_content:
                    benzinga_evidence[ticker] = pkg.to_dict()
            if benzinga_evidence:
                logger.info(
                    "Benzinga evidence fetched for %d/%d tickers",
                    len(benzinga_evidence),
                    len(universe),
                )
        except Exception as _benz_exc:
            logger.warning("Benzinga evidence fetch failed — continuing without it: %s", _benz_exc)

        result = await self.evidence_agent.run(
            self.run_record.run_id,
            {
                "tickers": universe,
                "market_data": self.stage_outputs.get(2, []),
                "qualitative_data": qualitative_data,  # DSQ-1: FMP/Finnhub qualitative
                "sec_primary_content": sec_evidence,  # DSQ-2: Tier 1 SEC filing sections
                "benzinga_evidence": benzinga_evidence,  # DSQ-3: Tier 2 finance-native news
            },
        )
        self._save_stage_output(5, result.model_dump())

        # Build a real ClaimLedger from structured agent output — no synthetic claims.
        from research_pipeline.schemas.claims import (
            Claim,
            ClaimStatus,
            EvidenceClass,
            ConfidenceLevel,
            SourceTier,
            Source,
        )

        ledger = ClaimLedger(run_id=self.run_record.run_id)

        if result.success and result.parsed_output:
            parsed = result.parsed_output
            # Agent may return {"claims": [...], "sources": [...]}
            raw_claims = parsed.get("claims", [])
            raw_sources = parsed.get("sources", [])

            for rc in raw_claims:
                if isinstance(rc, dict):
                    try:
                        ledger.claims.append(
                            Claim(
                                claim_id=rc.get("claim_id", f"CLM-{len(ledger.claims) + 1:03d}"),
                                run_id=self.run_record.run_id,
                                ticker=rc.get("ticker", "UNKNOWN"),
                                claim_text=rc.get("claim_text", ""),
                                evidence_class=EvidenceClass(
                                    rc.get("evidence_class", "house_inference")
                                ),
                                source_id=rc.get("source_id", "agent"),
                                source_url=rc.get("source_url"),
                                corroborated=rc.get("corroborated", False),
                                confidence=ConfidenceLevel(rc.get("confidence", "medium")),
                                status=ClaimStatus(rc.get("status", "caveat")),
                                owner_agent="evidence_librarian",
                            )
                        )
                    except (ValueError, KeyError) as exc:
                        logger.warning("Skipping malformed claim: %s", exc)

            for rs in raw_sources:
                if isinstance(rs, dict):
                    try:
                        ledger.sources.append(
                            Source(
                                source_id=rs.get("source_id", f"SRC-{len(ledger.sources) + 1:03d}"),
                                source_type=rs.get("source_type", "unknown"),
                                tier=SourceTier(rs.get("tier", 4)),
                                url=rs.get("url"),
                                notes=rs.get("notes", ""),
                            )
                        )
                    except (ValueError, KeyError) as exc:
                        logger.warning("Skipping malformed source: %s", exc)

        # Fail-closed: if agent failed or returned no structurally valid claims, the gate blocks.
        gate = self.gates.gate_5_evidence(ledger)
        return self._check_gate(gate)

    async def stage_6_sector_analysis(self, universe: list[str]) -> bool:
        """Stage 6: Three sector analysts run in parallel."""
        logger.info("═══ STAGE 6: Sector Analysis (parallel) ═══")

        # ARC-5: Route tickers using config-externalised SECTOR_ROUTING (instead of hardcoded sets)
        routing = (
            self.config.sector_routing if hasattr(self.config, "sector_routing") else SECTOR_ROUTING
        )
        compute_tickers = [t for t in universe if t in routing.get("compute", [])]
        power_tickers = [t for t in universe if t in routing.get("power_energy", [])]
        infra_tickers = [t for t in universe if t in routing.get("infrastructure", [])]
        # ISS-13: Route ASX-suffixed tickers (.AX / .ASX) to the specialised AU analyst
        asx_tickers = [t for t in universe if is_asx_ticker(t)]
        # Any ticker not in any bucket goes to the GenericSectorAnalystAgent
        all_routed = (
            set(compute_tickers) | set(power_tickers) | set(infra_tickers) | set(asx_tickers)
        )
        generic_tickers = [t for t in universe if t not in all_routed]

        agent_calls = []
        expected_count = 0
        mkt_data = self.stage_outputs.get(2, [])
        macro_ctx = self._get_macro_context()  # may be empty if stage 8 hasn't run yet

        # Session 13: Fetch live sector financials (revenue, earnings, GICS)
        sector_data_map: dict[str, dict] = {}
        try:
            sd_results = self.sector_data_svc.get_sector_data(universe)
            sector_data_map = {r.ticker: r.model_dump() for r in sd_results}
            logger.debug(
                "SectorDataService: fetched %d tickers (%s)",
                len(sd_results),
                "live" if any(r.is_live for r in sd_results) else "synthetic",
            )
        except Exception as _sd_exc:
            logger.debug("SectorDataService failed (non-blocking): %s", _sd_exc)

        for agent, tickers in [
            (self.compute_analyst, compute_tickers),
            (self.power_analyst, power_tickers),
            (self.infra_analyst, infra_tickers),
        ]:
            if tickers:  # skip agents with no relevant tickers in this universe
                agent_calls.append(
                    agent.run(
                        self.run_record.run_id,
                        {
                            "tickers": tickers,
                            "market_data": mkt_data,
                            "sector_financials": {
                                t: sector_data_map[t] for t in tickers if t in sector_data_map
                            },
                        },
                    )
                )
                expected_count += 1
            else:
                logger.info("Skipping %s — no tickers in universe", agent.name)

        # ISS-13: Run ASX analyst for AU-listed tickers
        if asx_tickers:
            logger.info(
                "Routing %d ASX tickers to SectorAnalystASX: %s", len(asx_tickers), asx_tickers
            )
            stage_8_data = self.stage_outputs.get(8, {})
            economy_ctx = stage_8_data.get("economy_analysis", {})
            agent_calls.append(
                self.asx_analyst.run(
                    self.run_record.run_id,
                    {
                        "tickers": asx_tickers,
                        "market_data": mkt_data,
                        "macro_context_summary": macro_ctx.summary_text(),
                        "economy_analysis": economy_ctx,
                    },
                )
            )
            expected_count += 1

        # ARC-5: run GenericSectorAnalystAgent for any tickers not in the routing table
        if generic_tickers:
            logger.info(
                "Routing %d unmapped tickers to GenericSectorAnalystAgent: %s",
                len(generic_tickers),
                generic_tickers,
            )
            agent_calls.append(
                self.generic_analyst.run(
                    self.run_record.run_id,
                    {
                        "tickers": generic_tickers,
                        "market_data": mkt_data,
                        "macro_context_summary": macro_ctx.summary_text(),
                    },
                )
            )
            expected_count += 1

        results = await asyncio.gather(*agent_calls)

        four_box_count = sum(1 for r in results if r.success)

        # ── ESG analysis — non-critical-path, runs after sector agents ──
        esg_result_dump: dict | None = None
        try:
            # ACT-S7-2: enrich ESG agent context with ESGService baseline profiles
            esg_baseline = []
            try:
                esg_baseline = [
                    s.model_dump() for s in self.esg_service.get_portfolio_scores(universe)
                ]
            except Exception:
                pass  # fallback to empty — non-blocking

            esg_result = await self.esg_analyst_agent.run(
                self.run_record.run_id,
                {
                    "tickers": universe,
                    "sector_outputs": [r.model_dump() for r in results],
                    "market_data": mkt_data,
                    "esg_baseline_profiles": esg_baseline,  # ACT-S7-2
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

        self._save_stage_output(
            6,
            {
                "sector_outputs": [r.model_dump() for r in results],
                "esg_output": esg_result_dump,
            },
        )
        gate = self.gates.gate_6_sector_analysis(four_box_count, expected_count=expected_count)
        return self._check_gate(gate)

    async def stage_7_valuation(self, universe: list[str]) -> bool:
        """Stage 7: Valuation & Modelling."""
        logger.info("═══ STAGE 7: Valuation & Modelling ═══")
        # ARC-4: Stage 8 now runs before Stage 7, so macro context is available here
        macro_ctx = self._get_macro_context()
        # Session 13: Pass economy_analysis + sector data to give valuation agent DCF context
        stage_8_data = self.stage_outputs.get(8, {})
        economy_ctx_v7 = stage_8_data.get("economy_analysis", {})
        macro_scenario_v7 = stage_8_data.get("macro_scenario", {})
        sector_data_v7: dict = {}
        try:
            sd_v7 = self.sector_data_svc.get_sector_data(universe)
            sector_data_v7 = {r.ticker: r.model_dump() for r in sd_v7}
        except Exception:
            pass
        result = await self.valuation_agent.run(
            self.run_record.run_id,
            {
                "tickers": universe,
                "sector_outputs": self._get_sector_outputs(),
                "market_data": self.stage_outputs.get(2, []),
                "macro_context": macro_ctx.model_dump(mode="json"),
                "economy_analysis": economy_ctx_v7,  # Session 13: macro-adjusted WACC context
                "macro_scenario": macro_scenario_v7,  # Session 13: scenario type for WACC adj
                "sector_financials": sector_data_v7,  # Session 13: revenue/earnings context
            },
        )
        self._save_stage_output(7, result.model_dump())
        gate = self.gates.gate_7_valuation(
            valuation_cards_count=1 if result.success else 0,
            expected_count=1,
        )
        return self._check_gate(gate)

    async def stage_8_macro(self, universe: list[str]) -> bool:
        """Stage 8: Macro & Political Overlay — extended with EconomyAnalystAgent (Session 12)."""
        logger.info("═══ STAGE 8: Macro & Political Overlay ═══")
        # ARC-9: Enrich macro agent with reconciled market data (stage 2) and
        # reconciliation flags (stage 3) so it can reference actual market conditions.
        ingested_data = self.stage_outputs.get(2, [])
        reconciliation_report = self.stage_outputs.get(3, {})

        # Session 12: Run EconomicIndicatorService + MacroScenarioService + EconomyAnalystAgent
        # These run before MacroStrategistAgent so the regime classification is enriched.
        economy_analysis: Optional[EconomyAnalysis] = None
        macro_scenario: Optional[MacroScenario] = None
        economic_indicators: Optional[EconomicIndicators] = None
        try:
            economic_indicators = self.economic_indicator_svc.get_indicators_sync(
                run_id=self.run_record.run_id
            )
            macro_scenario = self.macro_scenario_svc.build_scenario(economic_indicators)
            economy_analysis = await self.economy_analyst.run_economy_analysis(
                indicators=economic_indicators,
                scenario=macro_scenario,
                run_id=self.run_record.run_id,
            )
            logger.info(
                "EconomyAnalystAgent complete — rba_stance=%s fed_stance=%s",
                economy_analysis.rba_stance.value,
                economy_analysis.fed_stance.value,
            )
        except Exception as _exc:
            logger.warning("Session 12 economy pipeline failed (non-blocking): %s", _exc)

        # Build economy context dict for downstream agents
        economy_context: dict = {}
        if economy_analysis:
            economy_context = {
                "rba_cash_rate_thesis": economy_analysis.rba_cash_rate_thesis,
                "fed_funds_thesis": economy_analysis.fed_funds_thesis,
                "au_cpi_assessment": economy_analysis.au_cpi_assessment,
                "aud_usd_outlook": economy_analysis.aud_usd_outlook,
                "asx200_vs_sp500_divergence": economy_analysis.asx200_vs_sp500_divergence,
                "key_risks_au": economy_analysis.key_risks_au,
                "key_risks_us": economy_analysis.key_risks_us,
                "rba_stance": economy_analysis.rba_stance.value,
                "fed_stance": economy_analysis.fed_stance.value,
                "confidence": economy_analysis.confidence,
            }

        macro_result, political_result = await asyncio.gather(
            self.macro_agent.run(
                self.run_record.run_id,
                {
                    "universe": universe,
                    "market_data": ingested_data,
                    "reconciliation_summary": reconciliation_report,
                    "economy_analysis": economy_context,
                },
            ),
            self.political_agent.run(self.run_record.run_id, {"tickers": universe}),
        )
        self._save_stage_output(
            8,
            {
                "macro": macro_result.model_dump(),
                "political": political_result.model_dump(),
                "economy_analysis": economy_analysis.model_dump() if economy_analysis else {},
                "macro_scenario": macro_scenario.model_dump() if macro_scenario else {},
                "economic_indicators": economic_indicators.model_dump()
                if economic_indicators
                else {},
            },
        )
        gate = self.gates.gate_8_macro(
            regime_memo_present=macro_result.success,
            political_assessments_count=1 if political_result.success else 0,
            expected_count=1,
        )
        return self._check_gate(gate)

    async def stage_9_risk(
        self, universe: list[str], weights: dict[str, float] | None = None
    ) -> bool:
        """Stage 9: Quant Risk & Scenario Testing — enhanced with factor, VaR, benchmark analytics."""
        logger.info("═══ STAGE 9: Quant Risk & Scenario Testing ═══")

        # Run scenario stress engine
        scenario_results = self.scenario_engine.run_all_scenarios(universe)

        # Factor exposure analysis — ACT-S10-4: pass live returns for OLS regression
        live_factor_returns = self._get_returns(universe, n_days=252, seed_offset=9)
        # Synthetic market factor proxy (returns on "market" factor, seed=0)
        import numpy as _np

        _rng = _np.random.default_rng(seed=42)
        _n = max(len(v) for v in live_factor_returns.values()) if live_factor_returns else 252
        _factor_returns: dict[str, list[float]] = {
            "market": [round(float(x), 6) for x in (_rng.normal(0.04 / 252, 0.01, _n))],
            "size": [round(float(x), 6) for x in (_rng.normal(0.02 / 252, 0.008, _n))],
            "value": [round(float(x), 6) for x in (_rng.normal(0.01 / 252, 0.007, _n))],
            "momentum": [round(float(x), 6) for x in (_rng.normal(0.03 / 252, 0.009, _n))],
            "quality": [round(float(x), 6) for x in (_rng.normal(0.02 / 252, 0.006, _n))],
        }
        factor_exposures = self.factor_engine.compute_factor_exposures(
            universe,
            returns=live_factor_returns if live_factor_returns else None,
            factor_returns=_factor_returns,
        )
        factor_data = [fe.model_dump() for fe in factor_exposures]

        # Portfolio factor exposure (if weights provided)
        portfolio_factor_exp = None
        if weights:
            portfolio_factor_exp = self.factor_engine.portfolio_factor_exposure(
                factor_exposures, weights
            )

        # VaR analysis — ARC-3: use aggregate live_factor_returns instead of np.random.normal
        var_result = None
        drawdown_result = None
        try:
            import numpy as np

            # ARC-3: aggregate the per-ticker live returns into a single daily portfolio series
            if live_factor_returns:
                all_series = list(live_factor_returns.values())
                min_len = min(len(s) for s in all_series)
                portfolio_returns = np.mean([s[:min_len] for s in all_series], axis=0).tolist()
            else:
                # No live data available — fall back to factor-proxy series
                np.random.seed(42)
                portfolio_returns = np.random.normal(0.001, 0.02, 252).tolist()
            var_result = self.var_engine.parametric_var(
                run_id=self.run_record.run_id,
                portfolio_returns=portfolio_returns,
                confidence_level=0.95,
            )
            drawdown_result = self.var_engine.compute_drawdown_analysis(
                self.run_record.run_id, portfolio_returns
            )
        except Exception as exc:
            logger.warning("VaR computation failed: %s", exc)

        risk_packet = self.risk_engine.build_risk_packet(
            run_id=self.run_record.run_id,
            weights={t: 1.0 / len(universe) for t in universe},
            returns={t: [] for t in universe},  # synthetic returns present in var_result
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
                    "differentiation_score=%.1f",
                    etf_overlaps.differentiation_score,
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
                    "scenario_results": [
                        s.model_dump() if hasattr(s, "model_dump") else s for s in scenario_results
                    ],
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
            # ARC-10: use real Stage 8 macro output instead of hardcoded stub
            macro_ctx_fi = self._get_macro_context()
            macro_context_for_fi = (
                {
                    "regime_classification": macro_ctx_fi.regime_classification,
                    "rate_sensitivity": macro_ctx_fi.rate_sensitivity,
                    "key_macro_variables": macro_ctx_fi.key_macro_variables,
                    "regime_winners": macro_ctx_fi.regime_winners,
                    "regime_losers": macro_ctx_fi.regime_losers,
                }
                if macro_ctx_fi.regime_classification
                else {
                    "note": (
                        "Macro stage output not yet available. Interpret using internal heuristics."
                    ),
                }
            )
            # Session 12: Enrich FI inputs with AU/US economy analysis and macro scenario
            stage_8_fi = self.stage_outputs.get(8, {})
            economy_analysis_fi = stage_8_fi.get("economy_analysis", {})
            macro_scenario_fi = stage_8_fi.get("macro_scenario", {})
            # Assemble fixed-income context packet
            fi_inputs = {
                "universe": universe,
                "macro_context": macro_context_for_fi,
                "leverage_data": {
                    # Pull ND/EBITDA from DCF assumptions where available
                    t: self.stage_outputs.get(7, {}).get(t, {}).get("net_debt")
                    for t in universe
                },
                "var_metrics": risk_output.get("var_95", {}),
                "scenario_results": [
                    (s.model_dump() if hasattr(s, "model_dump") else s) for s in scenario_results
                ],
                "economy_analysis": economy_analysis_fi,
                "macro_scenario": {
                    "composite": macro_scenario_fi.get("composite_scenario", ""),
                    "au_rates_base": (macro_scenario_fi.get("au_rates") or {}).get("base", ""),
                    "us_rates_base": (macro_scenario_fi.get("us_rates") or {}).get("base", ""),
                    "au_fixed_income_impact": macro_scenario_fi.get("au_fixed_income_impact", ""),
                },
            }
            fi_result = await self.fixed_income_agent.run(self.run_record.run_id, fi_inputs)
            if fi_result.success and fi_result.parsed_output:
                risk_output["fixed_income_context"] = fi_result.parsed_output
                logger.info(
                    "Fixed Income Analyst: rate_sensitivity_score=%.1f  yield_curve_regime=%s",
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
                f"{t}: weight={(1.0 / len(universe)):.2%}"
                for t in universe
                if (1.0 / len(universe)) > 0.40  # flag single names >40% weight
            ]
            if universe
            else [],
        )
        return self._check_gate(gate)

    async def stage_10_red_team(self, universe: list[str]) -> bool:
        """Stage 10: Red Team."""
        logger.info("═══ STAGE 10: Red Team ═══")
        # ARC-6: Wire macro context and risk outputs to the red team agent
        macro_ctx = self._get_macro_context()
        result = await self.red_team_agent.run(
            self.run_record.run_id,
            {
                "tickers": universe,
                "sector_outputs": self._get_sector_outputs(),
                "valuation_outputs": self.stage_outputs.get(7, {}),
                "macro_context": macro_ctx.model_dump(mode="json"),
                "risk_outputs": self.stage_outputs.get(9, {}),
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
        # ARC-7: Wire macro context and risk outputs to the reviewer
        macro_ctx = self._get_macro_context()
        result = await self.reviewer_agent.run(
            self.run_record.run_id,
            {
                "sector_outputs": self._get_sector_outputs(),
                "evidence_ledger": self.stage_outputs.get(5, {}),
                "valuation_outputs": self.stage_outputs.get(7, {}),
                "red_team_outputs": self.stage_outputs.get(10, {}),
                "macro_context": macro_ctx.model_dump(mode="json"),
                "risk_outputs": self.stage_outputs.get(9, {}),
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
                    review_result.issues.append(
                        ReviewIssue(
                            severity=issue_data.get("severity", "major"),
                            description=issue_data.get("description", ""),
                            ticker=issue_data.get("ticker"),
                            stage=issue_data.get("stage"),
                            resolution=issue_data.get("resolution", ""),
                        )
                    )

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

        # ACT-S7-4: Portfolio optimisation — risk parity and min-variance
        optimisation_results: dict[str, Any] = {}
        try:
            synth_returns = self._get_returns(esg_clean_universe)  # ACT-S8-1
            risk_parity = self.portfolio_optimisation.compute_risk_parity(
                esg_clean_universe, synth_returns
            )
            min_var = self.portfolio_optimisation.compute_minimum_variance(
                esg_clean_universe, synth_returns
            )
            max_sharpe = self.portfolio_optimisation.compute_max_sharpe(
                esg_clean_universe, synth_returns
            )
            optimisation_results = {
                "risk_parity": {
                    "weights": risk_parity.weights,
                    "expected_return_pct": risk_parity.expected_return,
                    "expected_volatility_pct": risk_parity.expected_volatility,
                    "risk_contributions": risk_parity.risk_contributions,
                },
                "min_variance": {
                    "weights": min_var.weights,
                    "expected_return_pct": min_var.expected_return,
                    "expected_volatility_pct": min_var.expected_volatility,
                    "sharpe_ratio": min_var.sharpe_ratio,
                },
                "max_sharpe": {
                    "weights": max_sharpe.weights,
                    "expected_return_pct": max_sharpe.expected_return,
                    "expected_volatility_pct": max_sharpe.expected_volatility,
                    "sharpe_ratio": max_sharpe.sharpe_ratio,
                },
            }
            logger.info(
                "Portfolio optimisation complete — risk_parity vol=%.1f%% max_sharpe=%.2f",
                risk_parity.expected_volatility,
                max_sharpe.sharpe_ratio,
            )
        except Exception as _exc:
            logger.warning("Portfolio optimisation failed (non-blocking): %s", _exc)

        # ACT-S8-2: Rebalancing signals — compare risk-parity target vs equal-weight baseline
        rebalance_proposal: Optional[dict] = None
        try:
            if optimisation_results.get("risk_parity"):
                rp_weights = optimisation_results["risk_parity"]["weights"]
                proposal = self.rebalancing_engine.generate_rebalance(
                    run_id=self.run_record.run_id,
                    target_weights=rp_weights,
                    current_weights=baseline_weights,
                    trigger="optimiser",
                )
                rebalance_proposal = proposal.model_dump()
                logger.info(
                    "Rebalance proposal: %d trades, turnover=%.1f%%",
                    proposal.trade_count,
                    proposal.total_turnover_pct,
                )
        except Exception as _exc:
            logger.warning("Rebalance proposal failed (non-blocking): %s", _exc)

        # Mandate compliance check on baseline weights
        mandate_check = self.mandate_engine.check_compliance(
            run_id=self.run_record.run_id,
            weights=baseline_weights,
        )

        if not mandate_check.is_compliant:
            logger.warning(
                "Mandate violations on baseline: %s",
                [v.description for v in mandate_check.violations],
            )

        # Session 14: APRA SPS 530 super mandate check (non-blocking, parallel to existing mandate)
        super_mandate_result: dict | None = None
        try:
            client_profile = getattr(self.config, "client_profile", None)
            if client_profile is not None and getattr(client_profile, "is_super", False):
                fund_type = getattr(client_profile, "super_fund_type", None) or "balanced"
                asx_tickers = [t for t in universe if t.endswith(".AX") or t.endswith(".ASX")]
                super_check = self.super_mandate_svc.check_compliance(
                    run_id=self.run_record.run_id,
                    mandate_type=fund_type,
                    weights=baseline_weights,
                    asx_tickers=asx_tickers,
                )
                super_mandate_result = super_check.model_dump()
                if not super_check.is_compliant:
                    logger.warning(
                        "APRA SPS 530 super mandate violations: %s",
                        [v.description for v in super_check.violations],
                    )
                else:
                    logger.info("APRA SPS 530 super mandate: COMPLIANT (type=%s)", fund_type)
        except Exception as _super_exc:
            logger.warning("Super mandate check failed (non-blocking): %s", _super_exc)

        # ARC-8: Wire macro context into PM agent so it can factor regime into allocations
        # Session 12: Also pass economy analysis (AU/US macro) for regime-aware construction
        macro_ctx_pm = self._get_macro_context()
        stage_8_outputs = self.stage_outputs.get(8, {})
        economy_analysis_pm = stage_8_outputs.get("economy_analysis", {})
        macro_scenario_pm = stage_8_outputs.get("macro_scenario", {})
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
                "macro_context": macro_ctx_pm.model_dump(mode="json"),
                "economy_analysis": economy_analysis_pm,
                "macro_scenario": macro_scenario_pm,
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
                "concentration_hhi": sum(w**2 for w in baseline_weights.values()),
                "max_single_position_weight": max(baseline_weights.values())
                if baseline_weights
                else 0,
                "var_95_pct": var_data.get("var_pct") if var_data else None,
            }

        review_for_ic = None
        if self._review_result:
            review_for_ic = {
                "status": self._review_result.status.value,
                "issues": [
                    {"description": i.description, "severity": i.severity}
                    for i in self._review_result.issues
                ],
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

        self._save_stage_output(
            12,
            {
                "pm_result": result.model_dump(),
                "esg_compliance": esg_result,
                "mandate_compliance": mandate_check.model_dump(),
                "super_mandate_compliance": super_mandate_result,  # Session 14
                "baseline_weights": baseline_weights,
                "optimisation_results": optimisation_results,  # ACT-S7-4
                "rebalance_proposal": rebalance_proposal,  # ACT-S8-2
                "ic_record": ic_record.model_dump(),
                "ic_approved": ic_record.is_approved,
                "audit_trail": audit_trail.model_dump(),
            },
        )

        # Check mandate compliance violations for gate
        mandate_violations = (
            [v.description for v in mandate_check.violations]
            if not mandate_check.is_compliant
            else []
        )

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
        audit = self.registry.build_self_audit(
            self.run_record.run_id, ClaimLedger(run_id=self.run_record.run_id)
        )

        # ARC-2: Build real StockCard objects from accumulated stage outputs
        from research_pipeline.schemas.reports import build_stock_card_from_pipeline_outputs

        universe_for_report = self.stage_outputs.get(1, {}).get("universe", [])
        valuation_output = self.stage_outputs.get(7, {})
        valuation_parsed = valuation_output.get("parsed_output") or {}
        redteam_output = self.stage_outputs.get(10, {})
        redteam_parsed = redteam_output.get("parsed_output") or {}
        portfolio_weights = self.stage_outputs.get(12, {}).get("baseline_weights", {})
        # Build a ticker→four_box lookup from sector outputs
        sector_by_ticker: dict[str, dict] = {}
        for sector_res in self._get_sector_outputs():
            if isinstance(sector_res, dict):
                parsed_s = sector_res.get("parsed_output") or {}
                for box in parsed_s.get("sector_outputs", []):
                    if isinstance(box, dict) and "ticker" in box:
                        sector_by_ticker[box["ticker"]] = box
        stock_cards = []
        for ticker in universe_for_report:
            try:
                card = build_stock_card_from_pipeline_outputs(
                    ticker=ticker,
                    valuation_card=valuation_parsed.get(ticker) or valuation_parsed,
                    four_box=sector_by_ticker.get(ticker),
                    red_team=redteam_parsed.get(ticker)
                    or (
                        next(
                            (
                                r
                                for r in (redteam_parsed.get("assessments") or [])
                                if isinstance(r, dict) and r.get("ticker") == ticker
                            ),
                            None,
                        )
                    ),
                    weight_in_balanced=portfolio_weights.get(ticker),
                )
                stock_cards.append(card)
            except Exception as _exc:
                logger.warning("StockCard build failed for %s (non-blocking): %s", ticker, _exc)

        report_sections_input = {
            "executive_summary": "AI Infrastructure Investment Research — Executive Summary",
            "methodology": "Public-source institutional-style research methodology.",
        }

        # Session 13: Generate LLM narrative prose per section (non-blocking)
        narrative_sections: dict[str, str] | None = None
        try:
            narrative_inputs: dict = {
                "run_id": self.run_record.run_id,
                "tickers": universe_for_report,
                "publication_status": review_result.status.value,
                "economy_analysis": self.stage_outputs.get(8, {}).get("economy_analysis"),
                "macro_scenario": self.stage_outputs.get(8, {}).get("macro_scenario"),
                "regime_classification": self.stage_outputs.get(8, {}).get(
                    "regime_classification", ""
                ),
                "portfolios": (self.stage_outputs.get(12, {}).get("parsed_output") or {}).get(
                    "portfolios", []
                ),
                "valuations": (
                    valuation_parsed.get("valuations")
                    if isinstance(valuation_parsed, dict)
                    else None
                ),
            }
            narrative_sections = await self.report_narrative_agent.generate_narrative(
                run_id=self.run_record.run_id,
                pipeline_outputs=narrative_inputs,
            )
            logger.info(
                "ReportNarrativeAgent: narrative generated for %d sections", len(narrative_sections)
            )
        except Exception as _narr_exc:
            logger.warning("ReportNarrativeAgent failed (non-blocking): %s", _narr_exc)

        report = self.report_assembly.assemble_report(
            run_id=self.run_record.run_id,
            review_result=review_result,
            sections=report_sections_input,
            stock_cards=stock_cards,
            self_audit_text=json.dumps(audit.model_dump(), indent=2, default=str),
            narrative_sections=narrative_sections,  # Session 13
        )

        # Save report
        output_path = self.report_assembly.save_report(report, self.settings.reports_dir)
        self._save_stage_output(
            13, {"report_path": str(output_path), "status": report.publication_status}
        )
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
            outputs_generated=[str(k) for k in self.stage_outputs.keys()],
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

        # ACT-S7-1: Performance Attribution — BHB decomposition with live-preferred returns
        attribution_output: dict[str, Any] = {}
        if baseline_weights:
            try:
                from research_pipeline.services.benchmark_module import BENCHMARK_CONSTITUENTS

                tickers = list(baseline_weights.keys())
                # ACT-S10-1: track data source for attribution accuracy reporting
                live_raw = self.live_return_store.fetch(tickers)
                data_source_port = (
                    "live"
                    if live_raw and len(live_raw) == len(tickers)
                    else "blended"
                    if live_raw
                    else "synthetic"
                )
                synth_returns = self._get_returns(tickers, seed_offset=1)  # blends live + synthetic
                bench_tickers = list(BENCHMARK_CONSTITUENTS.get("SPY", {}).keys())
                live_bench = self.live_return_store.fetch(bench_tickers)
                data_source_bench = (
                    "live"
                    if live_bench and len(live_bench) == len(bench_tickers)
                    else "blended"
                    if live_bench
                    else "synthetic"
                )
                bench_returns = self._get_returns(bench_tickers, seed_offset=2)
                attribution_data_source = (
                    "live"
                    if data_source_port == "live" and data_source_bench == "live"
                    else "blended"
                    if (
                        data_source_port in ("live", "blended")
                        or data_source_bench in ("live", "blended")
                    )
                    else "synthetic"
                )

                # Normalised benchmark weights (SPY proxy)
                raw_bench_w = BENCHMARK_CONSTITUENTS.get("SPY", {})
                total_bw = sum(raw_bench_w.get(t, 0) for t in bench_tickers) or 100
                benchmark_weights_norm = {
                    t: raw_bench_w.get(t, 0) / total_bw for t in bench_tickers
                }

                # Per-ticker synthetic portfolio returns (annualised mean)
                port_returns_annualised = {
                    t: float(__import__("numpy").mean(synth_returns[t]) * 252) for t in tickers
                }
                bench_returns_annualised = {
                    t: float(__import__("numpy").mean(bench_returns[t]) * 252)
                    for t in bench_tickers
                }

                # Sector map from sector analyst outputs
                sector_results = self._get_sector_outputs()
                sector_map: dict[str, str] = {}
                for res in sector_results:
                    if isinstance(res, dict):
                        agent_name = res.get("agent_name", "")
                        # Map compute/power/infra to sector labels
                        if "compute" in agent_name:
                            sector = "Semiconductors"
                        elif "power" in agent_name:
                            sector = "Power & Energy"
                        else:
                            sector = "Infrastructure"
                        parsed = res.get("parsed_output") or {}
                        covered = parsed.get("covered_tickers", tickers)
                        for t in covered:
                            if t in tickers and t not in sector_map:
                                sector_map[t] = sector
                # Default sector for unmapped tickers
                for t in tickers:
                    sector_map.setdefault(t, "Semiconductors")
                # Benchmark sector map
                for t in bench_tickers:
                    sector_map.setdefault(t, "Semiconductors")

                bhb = self.performance_tracker.compute_bhb_attribution(
                    run_id=self.run_record.run_id,
                    portfolio_weights=baseline_weights,
                    portfolio_returns=port_returns_annualised,
                    benchmark_weights=benchmark_weights_norm,
                    benchmark_returns=bench_returns_annualised,
                    sector_map=sector_map,
                )
                attribution_output = bhb.model_dump(mode="json")
                attribution_output["data_source"] = attribution_data_source  # ACT-S10-1
                logger.info(
                    "BHB attribution (%s) — excess_return=%.2f%% allocation=%.2f%% selection=%.2f%%",
                    attribution_data_source,
                    bhb.excess_return_pct,
                    bhb.allocation_effect_pct,
                    bhb.selection_effect_pct,
                )
            except Exception as exc:
                logger.warning("BHB attribution failed (non-blocking): %s", exc)

        self._save_stage_output(
            14,
            {
                "final_status": final_status.value,
                "stages_completed": [s for s, g in self.gate_results.items() if g.passed],
                "stages_failed": failed_stages,
                "gate_summary": {s: g.reason for s, g in self.gate_results.items()},
                "cache_stats": self.cache.stats,
                "attribution": attribution_output,  # ACT-S7-1
            },
        )
        logger.info(
            "Pipeline run %s finished with status: %s", self.run_record.run_id, final_status.value
        )

    # ── Full pipeline execution ────────────────────────────────────────
    async def run_full_pipeline(
        self,
        universe: list[str],
        event_callback: Optional[Callable[[PipelineEvent], Awaitable[None]]] = None,
    ) -> dict[str, Any]:
        """Execute the full 15-stage pipeline end-to-end.

        Session 15 (Phase 2): ``event_callback`` is an async coroutine that
        receives every ``PipelineEvent`` as the run progresses.  Pass ``None``
        (default) for a no-op, fully backward-compatible execution.
        """
        if event_callback is not None:
            self._event_callback = event_callback
        run_start = time.monotonic()

        # Session 17: initialise provenance service
        _run_id = self.run_record.run_id if self.run_record else "unknown"
        self._provenance = ProvenanceService(
            run_id=_run_id,
            model=self.settings.llm_model,
            temperature=self.settings.llm_temperature,
        )

        logger.info("╔══════════════════════════════════════════════╗")
        logger.info("║  AI Infrastructure Research Pipeline v8      ║")
        logger.info("║  Starting full pipeline run                  ║")
        logger.info("╚══════════════════════════════════════════════╝")

        # Phase 7.5: Start observability tracking
        if self.run_record:
            self.observability.start_run(self.run_record.run_id)

        # ACT-S7-3: pipeline-level start time for total_pipeline_duration_s
        self._pipeline_start = time.monotonic()

        # Stage 0: Bootstrap
        if not await self._timed_stage(0, self.stage_0_bootstrap(universe)):
            await self._timed_stage(14, self.stage_14_monitoring())
            _ap = self._emit_audit_packet(universe)
            _run_id = self.run_record.run_id if self.run_record else "unknown"
            await self._emit(PipelineEvent.pipeline_failed(_run_id, blocked_at=0))
            return {
                "status": "failed",
                "blocked_at": 0,
                "run_id": self.run_record.run_id,
                "audit_packet": _ap.model_dump(mode="json") if _ap else None,
            }

        # Session 15 Phase 2: emit pipeline_started now that run_record is guaranteed set
        await self._emit(PipelineEvent.pipeline_started(self.run_record.run_id, universe))

        # Stage 1: Universe
        if not await self._timed_stage(1, self.stage_1_universe(universe)):
            await self._timed_stage(14, self.stage_14_monitoring())
            _ap = self._emit_audit_packet(universe)
            return {
                "status": "failed",
                "blocked_at": 1,
                "run_id": self.run_record.run_id,
                "audit_packet": _ap.model_dump(mode="json") if _ap else None,
            }

        # Stage 2: Data Ingestion
        if not await self._timed_stage(2, self.stage_2_ingestion(universe)):
            await self._timed_stage(14, self.stage_14_monitoring())
            _ap = self._emit_audit_packet(universe)
            return {
                "status": "failed",
                "blocked_at": 2,
                "run_id": self.run_record.run_id,
                "audit_packet": _ap.model_dump(mode="json") if _ap else None,
            }

        # Stage 3: Reconciliation
        if not await self._timed_stage(3, self.stage_3_reconciliation()):
            await self._timed_stage(14, self.stage_14_monitoring())
            _ap = self._emit_audit_packet(universe)
            return {
                "status": "failed",
                "blocked_at": 3,
                "run_id": self.run_record.run_id,
                "audit_packet": _ap.model_dump(mode="json") if _ap else None,
            }

        # Stage 4: Data QA
        if not await self._timed_stage(4, self.stage_4_data_qa()):
            await self._timed_stage(14, self.stage_14_monitoring())
            _ap = self._emit_audit_packet(universe)
            return {
                "status": "failed",
                "blocked_at": 4,
                "run_id": self.run_record.run_id,
                "audit_packet": _ap.model_dump(mode="json") if _ap else None,
            }

        # Stage 4.5: Gemini Deep Research (non-blocking — failure never halts pipeline)
        # GDR-1: fires between Data QA and Evidence Librarian; injects Tier-3 claims.
        await self.stage_4_5_deep_research(universe)

        # Stage 5: Evidence Librarian
        if not await self._timed_stage(5, self.stage_5_evidence(universe)):
            await self._timed_stage(14, self.stage_14_monitoring())
            _ap = self._emit_audit_packet(universe)
            return {
                "status": "failed",
                "blocked_at": 5,
                "run_id": self.run_record.run_id,
                "audit_packet": _ap.model_dump(mode="json") if _ap else None,
            }

        # Stage 6: Sector Analysis (parallel)
        if not await self._timed_stage(6, self.stage_6_sector_analysis(universe)):
            await self._timed_stage(14, self.stage_14_monitoring())
            _ap = self._emit_audit_packet(universe)
            return {
                "status": "failed",
                "blocked_at": 6,
                "run_id": self.run_record.run_id,
                "audit_packet": _ap.model_dump(mode="json") if _ap else None,
            }

        # Stage 8: Macro & Political (ARC-4: runs BEFORE Valuation so macro feeds valuation agent)
        if not await self._timed_stage(8, self.stage_8_macro(universe)):
            await self._timed_stage(14, self.stage_14_monitoring())
            _ap = self._emit_audit_packet(universe)
            return {
                "status": "failed",
                "blocked_at": 8,
                "run_id": self.run_record.run_id,
                "audit_packet": _ap.model_dump(mode="json") if _ap else None,
            }

        # Stage 7: Valuation (now has access to Stage 8 macro context)
        if not await self._timed_stage(7, self.stage_7_valuation(universe)):
            await self._timed_stage(14, self.stage_14_monitoring())
            _ap = self._emit_audit_packet(universe)
            return {
                "status": "failed",
                "blocked_at": 7,
                "run_id": self.run_record.run_id,
                "audit_packet": _ap.model_dump(mode="json") if _ap else None,
            }

        # Stage 9: Risk & Scenarios
        if not await self._timed_stage(9, self.stage_9_risk(universe)):
            await self._timed_stage(14, self.stage_14_monitoring())
            _ap = self._emit_audit_packet(universe)
            return {
                "status": "failed",
                "blocked_at": 9,
                "run_id": self.run_record.run_id,
                "audit_packet": _ap.model_dump(mode="json") if _ap else None,
            }

        # Stage 10: Red Team
        if not await self._timed_stage(10, self.stage_10_red_team(universe)):
            await self._timed_stage(14, self.stage_14_monitoring())
            _ap = self._emit_audit_packet(universe)
            return {
                "status": "failed",
                "blocked_at": 10,
                "run_id": self.run_record.run_id,
                "audit_packet": _ap.model_dump(mode="json") if _ap else None,
            }

        # Stage 11: Associate Review
        if not await self._timed_stage(11, self.stage_11_review()):
            await self._timed_stage(14, self.stage_14_monitoring())
            _ap = self._emit_audit_packet(universe)
            return {
                "status": "failed",
                "blocked_at": 11,
                "run_id": self.run_record.run_id,
                "audit_packet": _ap.model_dump(mode="json") if _ap else None,
            }

        # Stage 12: Portfolio Construction
        if not await self._timed_stage(12, self.stage_12_portfolio(universe)):
            await self._timed_stage(14, self.stage_14_monitoring())
            _ap = self._emit_audit_packet(universe)
            return {
                "status": "failed",
                "blocked_at": 12,
                "run_id": self.run_record.run_id,
                "audit_packet": _ap.model_dump(mode="json") if _ap else None,
            }

        # Stage 13: Report Assembly
        if not await self._timed_stage(13, self.stage_13_report()):
            await self._timed_stage(14, self.stage_14_monitoring())
            _ap = self._emit_audit_packet(universe)
            return {
                "status": "failed",
                "blocked_at": 13,
                "run_id": self.run_record.run_id,
                "audit_packet": _ap.model_dump(mode="json") if _ap else None,
            }

        # Stage 14: Monitoring & Logging
        await self._timed_stage(14, self.stage_14_monitoring())

        # Phase 7.5: End observability tracking and save telemetry
        if self.run_record:
            try:
                run_obs = self.observability.end_run(self.run_record.run_id)
                telemetry_path = self.observability.save(self.run_record.run_id)
                logger.info(
                    "Observability saved to %s | total_cost=$%.4f | duration=%.1fs",
                    telemetry_path,
                    run_obs.total_llm_cost_usd,
                    run_obs.total_duration_seconds,
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

        # ── ACT-S6-1 / ACT-S7-3: Build and attach SelfAuditPacket ─────────────
        audit_packet = self._emit_audit_packet(universe)

        # Session 17: Build and persist provenance packet
        provenance_packet = None
        if self._provenance is not None:
            try:
                report_md = ""
                s13 = self.stage_outputs.get(13, {})
                if isinstance(s13, dict) and "report_path" in s13:
                    rp = Path(s13["report_path"])
                    if rp.exists():
                        try:
                            report_md = rp.read_text(encoding="utf-8")
                        except Exception:
                            pass
                pkt = self._provenance.build_packet(report_md=report_md)
                self._provenance.save_packet(pkt, self.settings.storage_dir)
                provenance_packet = pkt.model_dump(mode="json")
                logger.info(
                    "Provenance packet built: %d/%d stages, %.1f%% complete",
                    pkt.stages_with_provenance,
                    pkt.total_stages,
                    pkt.completeness_pct,
                )
            except Exception as exc:
                logger.warning("Provenance packet build failed (non-blocking): %s", exc)

        # Session 15 Phase 2: emit pipeline_completed
        _pipeline_total_ms = round((time.monotonic() - run_start) * 1000, 1)
        await self._emit(
            PipelineEvent.pipeline_completed(self.run_record.run_id, _pipeline_total_ms)
        )

        return {
            "status": "completed",
            "run_id": self.run_record.run_id,
            "stages_completed": sorted(self.gate_results.keys()),
            "report_path": self.stage_outputs.get(13, {}).get("report_path"),
            "audit_packet": audit_packet.model_dump(mode="json") if audit_packet else None,
            "provenance_packet": provenance_packet,
        }
