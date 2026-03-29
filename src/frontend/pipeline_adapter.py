"""PipelineEngineAdapter — thin frontend shim over PipelineEngine.

Session 16 truthfulness overhaul:
  - ``elapsed_secs`` now populated from ``engine._stage_timings``
  - ``raw_text`` populated for LLM-producing stages (5-12)
  - ``token_log`` populates from engine LLM call telemetry
  - ``audit_packet`` fully extracted from engine SelfAuditPacket
  - ``report_md`` fallback reads from report_path file when inline absent
  - ``progress_callback`` fires both "running" and "done" per stage
  - ``activity_callback`` fires with descriptive messages per stage

This module is the *recommended replacement* for the legacy
``frontend.pipeline_runner.PipelineRunner``.  It exposes the same external
interface (``STAGES``, ``StageResult``, ``RunResult``, ``PipelineRunner``
alias, ``PipelineEngineAdapter``) so that ``app.py`` can adopt it with a
one-line import swap.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from research_pipeline.config.loader import PipelineConfig
from research_pipeline.config.settings import APIKeys, Settings
from research_pipeline.pipeline.engine import PipelineEngine

logger = logging.getLogger(__name__)


# ── Stage registry (kept in sync with PipelineEngine) ────────────────────

STAGES: list[tuple[int, str]] = [
    (0,  "Bootstrap & Configuration"),
    (1,  "Universe Definition"),
    (2,  "Data Ingestion"),
    (3,  "Reconciliation"),
    (4,  "Data QA & Lineage"),
    (5,  "Evidence Librarian / Claim Ledger"),
    (6,  "Sector Analysis"),
    (7,  "Valuation & Modelling"),
    (8,  "Macro & Political Overlay"),
    (9,  "Quant Risk & Scenario Testing"),
    (10, "Red Team Analysis"),
    (11, "Associate Review / Publish Gate"),
    (12, "Portfolio Construction"),
    (13, "Report Assembly"),
    (14, "Monitoring & Run Registry"),
]


# ── Data contracts (mirror pipeline_runner.py for drop-in compatibility) ─

@dataclass
class StageResult:
    stage_num: int
    stage_name: str
    status: str = "pending"        # pending | running | done | failed
    output: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""
    elapsed_secs: float = 0.0
    error: Optional[str] = None


@dataclass
class RunResult:
    run_id: str
    tickers: list[str]
    model: str
    started_at: str
    completed_at: str = ""
    stages: list[StageResult] = field(default_factory=list)
    final_report_md: str = ""
    success: bool = False
    publication_status: str = "PASS"
    token_log: list[dict] = field(default_factory=list)
    audit_packet: dict = field(default_factory=dict)


ProgressCallback = Callable[[int, str, str, dict], None]
ActivityCallback = Callable[[str], None]


# ── Adapter ───────────────────────────────────────────────────────────────

class PipelineEngineAdapter:
    """Drop-in replacement for ``PipelineRunner`` backed by ``PipelineEngine``.

    Delegates all stage execution to :class:`PipelineEngine` and translates
    the engine's ``stage_outputs`` / ``gate_results`` into the ``RunResult``
    shape that ``app.py`` expects.
    """

    def __init__(
        self,
        provider_keys: dict[str, str],
        model: str = "claude-opus-4-6",
        tickers: Optional[list[str]] = None,
        temperature: float = 0.3,
        stage_models: Optional[dict[int, str]] = None,
        client_profile: Optional[Any] = None,
    ) -> None:
        self.provider_keys = provider_keys
        self.model = model
        self.tickers = tickers or ["NVDA", "CEG", "PWR"]
        self.temperature = temperature
        self.stage_models = stage_models or {}
        self.client_profile = client_profile

        # Inject keys into environment (fixes: all three providers consistently)
        if ak := provider_keys.get("anthropic"):
            os.environ["ANTHROPIC_API_KEY"] = ak
        if ok := provider_keys.get("openai"):
            os.environ["OPENAI_API_KEY"] = ok
        if gk := provider_keys.get("google"):
            os.environ["GOOGLE_API_KEY"] = gk

        # Build Settings from provider_keys (fix: wire temperature)
        storage_base = Path(os.environ.get("PIPELINE_STORAGE_DIR", "/tmp/pipeline_runs"))
        self._settings = Settings(
            project_root=Path(__file__).resolve().parents[2],
            storage_dir=storage_base / "storage",
            reports_dir=storage_base / "reports",
            prompts_dir=storage_base / "prompts",
            llm_model=model,
            llm_temperature=temperature,
            api_keys=APIKeys(
                fmp_api_key=provider_keys.get("fmp", os.environ.get("FMP_API_KEY", "")),
                finnhub_api_key=provider_keys.get("finnhub", os.environ.get("FINNHUB_API_KEY", "")),
                anthropic_api_key=provider_keys.get("anthropic", os.environ.get("ANTHROPIC_API_KEY", "")),
                openai_api_key=provider_keys.get("openai", os.environ.get("OPENAI_API_KEY", "")),
                google_api_key=provider_keys.get("google", os.environ.get("GOOGLE_API_KEY", "")),
            ),
        )
        self._config = PipelineConfig()

    # ── LLM stages for raw_text extraction ─────────────────────────────
    _LLM_STAGES = {5, 6, 7, 8, 9, 10, 11, 12}

    # ── Run ──────────────────────────────────────────────────────────────

    async def run(
        self,
        progress_callback: Optional[ProgressCallback] = None,
        activity_callback: Optional[ActivityCallback] = None,
    ) -> RunResult:
        """Execute the pipeline and return a truthful ``RunResult``.

        Session 16 overhaul:
          • elapsed_secs populated from engine._stage_timings
          • raw_text populated for LLM stages
          • audit_packet fully extracted from SelfAuditPacket
          • token_log populated from engine telemetry (per-stage agent names)
          • progress_callback fires "running" (start) and "done" (end) per stage
          • report_md fallbacks through report_markdown → report → report_path file
        """
        started_at = datetime.now(timezone.utc).isoformat()
        _stage_names = dict(STAGES)

        if activity_callback:
            activity_callback("Initialising PipelineEngine …")

        engine = PipelineEngine(settings=self._settings, config=self._config)

        # Bridge: translate engine progress to ProgressCallback
        # Fires "running" when stage starts, "done" when output is saved
        _stage_start_times: dict[int, float] = {}

        if progress_callback or activity_callback:
            _original_timed_stage = engine._timed_stage

            async def _intercepting_timed_stage(stage_num: int, coro):
                stage_name = _stage_names.get(stage_num, f"Stage {stage_num}")
                _stage_start_times[stage_num] = time.monotonic()
                # Fire "running" before stage executes
                if progress_callback:
                    progress_callback(stage_num, stage_name, "running", {})
                if activity_callback:
                    activity_callback(f"Running {stage_name} …")
                return await _original_timed_stage(stage_num, coro)

            engine._timed_stage = _intercepting_timed_stage  # type: ignore[method-assign]

            _original_save = engine._save_stage_output

            def _intercepting_save(stage_num: int, output: Any) -> None:
                _original_save(stage_num, output)
                stage_name = _stage_names.get(stage_num, f"Stage {stage_num}")
                if progress_callback:
                    progress_callback(
                        stage_num, stage_name, "done",
                        output if isinstance(output, dict) else {},
                    )
                if activity_callback:
                    activity_callback(f"Completed {stage_name}")

            engine._save_stage_output = _intercepting_save  # type: ignore[method-assign]

        # Execute
        pipeline_result = await engine.run_full_pipeline(self.tickers)

        completed_at = datetime.now(timezone.utc).isoformat()
        succeeded = pipeline_result.get("status") != "failed"
        pub_status = "PASS" if succeeded else "FAIL"

        # ── Build StageResult list with truthful elapsed_secs + raw_text ─
        stage_results: list[StageResult] = []
        for num, name in STAGES:
            output = engine.stage_outputs.get(num, {})
            gate = engine.gate_results.get(num)

            if num not in engine.stage_outputs:
                status = "failed" if not succeeded else "skipped"
            elif gate and not gate.passed:
                status = "failed"
            else:
                status = "done"

            # Truthful elapsed_secs from engine._stage_timings (ms → secs)
            elapsed_secs = round(engine._stage_timings.get(num, 0.0) / 1000, 2)

            # Truthful raw_text for LLM stages
            raw_text = ""
            if num in self._LLM_STAGES and isinstance(output, dict):
                raw_text = (
                    output.get("raw_text", "")
                    or output.get("raw_output", "")
                    or output.get("parsed_output", "")
                )
                if isinstance(raw_text, dict):
                    raw_text = json.dumps(raw_text, indent=2)

            stage_results.append(StageResult(
                stage_num=num,
                stage_name=name,
                status=status,
                output=output if isinstance(output, dict) else {"data": output},
                raw_text=str(raw_text),
                elapsed_secs=elapsed_secs,
                error=gate.reason if gate and not gate.passed else None,
            ))

        # ── Report markdown: cascade through possible keys + file path ───
        report_md: str = ""
        report_output = engine.stage_outputs.get(13, {})
        if isinstance(report_output, dict):
            report_md = (
                report_output.get("report_markdown", "")
                or report_output.get("report", "")
                or report_output.get("content", "")
            )
            if not report_md and "report_path" in report_output:
                rp = Path(report_output["report_path"])
                if rp.exists():
                    try:
                        report_md = rp.read_text(encoding="utf-8")
                        logger.info("Loaded report from %s", rp)
                    except Exception as e:
                        logger.warning("Failed to load report from %s: %s", rp, e)

        run_id = engine.run_record.run_id if engine.run_record else f"run-{uuid.uuid4().hex[:8]}"

        # ── Truthful audit_packet from SelfAuditPacket ────────────────────
        audit_packet_dict: dict[str, Any] = {}
        if engine.run_record:
            # Try self_audit_packet first (populated by _emit_audit_packet)
            sap = getattr(engine.run_record, "self_audit_packet", None)
            if sap:
                audit_packet_dict = sap if isinstance(sap, dict) else {}
            else:
                # Try building it ourselves
                try:
                    packet = engine._build_self_audit_packet(self.tickers)
                    audit_packet_dict = packet.model_dump(mode="json")
                except Exception as e:
                    logger.debug("Could not build audit packet: %s", e)

        # Inject stage_latencies_ms from engine._stage_timings
        if engine._stage_timings:
            audit_packet_dict["stage_latencies_ms"] = {
                f"stage_{s}": ms for s, ms in engine._stage_timings.items()
            }
        if engine._pipeline_start > 0:
            audit_packet_dict["total_pipeline_duration_s"] = round(
                time.monotonic() - engine._pipeline_start, 2
            )

        # ── Token log from engine stage outputs + agent metadata ──────────
        token_log: list[dict] = []
        for num, name in STAGES:
            output = engine.stage_outputs.get(num, {})
            if not isinstance(output, dict):
                continue
            agent_name = output.get("agent_name", "")
            model_used = output.get("model", self.model)
            tokens_in = int(output.get("tokens_in", output.get("input_tokens", 0)))
            tokens_out = int(output.get("tokens_out", output.get("output_tokens", 0)))
            cost = float(output.get("cost_usd", 0.0))

            # For sector analysis (stage 6), aggregate sub-agent entries
            if num == 6 and "sector_outputs" in output:
                for so in output["sector_outputs"]:
                    if isinstance(so, dict):
                        token_log.append({
                            "stage": num,
                            "agent": so.get("agent_name", f"sector_analyst_{num}"),
                            "model": so.get("model", model_used),
                            "tokens_in": int(so.get("tokens_in", so.get("input_tokens", 0))),
                            "tokens_out": int(so.get("tokens_out", so.get("output_tokens", 0))),
                            "cost_usd": float(so.get("cost_usd", 0.0)),
                        })
                continue

            if agent_name or num in self._LLM_STAGES:
                token_log.append({
                    "stage": num,
                    "agent": agent_name or f"stage_{num}_agent",
                    "model": model_used,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "cost_usd": cost,
                })

        return RunResult(
            run_id=run_id,
            tickers=self.tickers,
            model=self.model,
            started_at=started_at,
            completed_at=completed_at,
            stages=stage_results,
            final_report_md=report_md,
            success=succeeded,
            publication_status=pub_status,
            token_log=token_log,
            audit_packet=audit_packet_dict,
        )


# ── Re-export as PipelineRunner for drop-in compatibility ─────────────────
#
# app.py can swap its import line to:
#    from frontend.pipeline_adapter import STAGES, PipelineRunner, RunResult
# and gain all PipelineEngine benefits without any other changes.

PipelineRunner = PipelineEngineAdapter
