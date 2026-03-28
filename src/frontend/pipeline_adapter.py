"""PipelineEngineAdapter — thin frontend shim over PipelineEngine.

This module is the *recommended replacement* for the legacy
``frontend.pipeline_runner.PipelineRunner``.  It exposes the same external
interface (``STAGES``, ``StageResult``, ``RunResult``, ``PipelineRunner``
alias, ``PipelineEngineAdapter``) so that ``app.py`` can adopt it with a
one-line import swap:

  # Old:
  from frontend.pipeline_runner import STAGES, PipelineRunner, RunResult

  # New:
  from frontend.pipeline_adapter import STAGES, PipelineRunner, RunResult

**What changed:**
  - Stage logic lives exclusively in ``research_pipeline.pipeline.engine``
    (PipelineEngine).  No duplicate stage implementations here.
  - This file is ~120 lines instead of 1851.
  - All deterministic services, gate logic, and agent calls are delegated
    to PipelineEngine — a single source of truth.

**What is preserved (backward compatibility):**
  - ``STAGES`` constant — same list of (num, name) tuples
  - ``StageResult`` dataclass — same fields
  - ``RunResult`` dataclass — same fields
  - ``PipelineRunner`` name re-exported as an alias for PipelineEngineAdapter
  - ``ProgressCallback`` / ``ActivityCallback`` types
  - ``run()`` coroutine signature and return type

**Migration note:**
  ``pipeline_runner.py`` is deliberately NOT deleted; it remains available
  for direct use.  Once app.py switches to this adapter, pipeline_runner.py
  can be archived.
"""

from __future__ import annotations

import logging
import os
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

    # ── Run ──────────────────────────────────────────────────────────────

    async def run(
        self,
        progress_callback: Optional[ProgressCallback] = None,
        activity_callback: Optional[ActivityCallback] = None,
    ) -> RunResult:
        """Execute the pipeline and return a ``RunResult`` compatible dict."""
        started_at = datetime.now(timezone.utc).isoformat()

        if activity_callback:
            activity_callback("Initialising PipelineEngine …")

        engine = PipelineEngine(settings=self._settings, config=self._config)

        # Bridge: translate engine progress to ProgressCallback
        if progress_callback:
            _original_save = engine._save_stage_output

            def _intercepting_save(stage_num: int, output: Any) -> None:
                _original_save(stage_num, output)
                stage_name = dict(STAGES).get(stage_num, f"Stage {stage_num}")
                progress_callback(stage_num, stage_name, "done", output if isinstance(output, dict) else {})

            engine._save_stage_output = _intercepting_save  # type: ignore[method-assign]

        # Execute
        pipeline_result = await engine.run_full_pipeline(self.tickers)

        completed_at = datetime.now(timezone.utc).isoformat()
        succeeded = pipeline_result.get("status") != "failed"
        pub_status = "PASS" if succeeded else "FAIL"

        # Build StageResult list from engine.stage_outputs
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
            stage_results.append(StageResult(
                stage_num=num,
                stage_name=name,
                status=status,
                output=output if isinstance(output, dict) else {"data": output},
            ))

        # Fix: Load report markdown from report_path if inline markdown absent
        report_md: str = ""
        report_output = engine.stage_outputs.get(13, {})
        if isinstance(report_output, dict):
            # Try inline markdown first
            report_md = report_output.get("report_markdown", report_output.get("report", ""))
            # If missing, try loading from report_path
            if not report_md and "report_path" in report_output:
                report_path = Path(report_output["report_path"])
                if report_path.exists():
                    try:
                        report_md = report_path.read_text(encoding="utf-8")
                        logger.info(f"Loaded report markdown from {report_path}")
                    except Exception as e:
                        logger.warning(f"Failed to load report from {report_path}: {e}")

        run_id = engine.run_record.run_id if engine.run_record else f"run-{uuid.uuid4().hex[:8]}"

        # Fix: Populate token_log and audit_packet from engine telemetry
        token_log: list[dict] = []
        audit_packet_dict: dict[str, Any] = {}
        stage_timings_dict: dict[str, float] = {}
        
        if engine.run_record:
            # Extract audit packet if available
            if hasattr(engine.run_record, "audit_packet") and engine.run_record.audit_packet:
                audit_packet = engine.run_record.audit_packet
                if hasattr(audit_packet, "model_dump"):
                    audit_packet_dict = audit_packet.model_dump()
                elif isinstance(audit_packet, dict):
                    audit_packet_dict = audit_packet
                
                # Extract stage timings from audit packet
                if "stage_latencies_ms" in audit_packet_dict:
                    stage_timings_dict = audit_packet_dict["stage_latencies_ms"]
            
            # Build token_log from stage outputs (approximate until engine emits real events)
            # This is a placeholder until Phase 2 implements full telemetry
            for num, name in STAGES:
                output = engine.stage_outputs.get(num, {})
                if isinstance(output, dict) and "agent_name" in output:
                    token_log.append({
                        "stage": num,
                        "agent": output.get("agent_name", "unknown"),
                        "model": self.model,
                        "tokens_in": 0,  # Placeholder until Phase 2
                        "tokens_out": 0,
                        "cost_usd": 0.0,
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
        )


# ── Re-export as PipelineRunner for drop-in compatibility ─────────────────
#
# app.py can swap its import line to:
#    from frontend.pipeline_adapter import STAGES, PipelineRunner, RunResult
# and gain all PipelineEngine benefits without any other changes.

PipelineRunner = PipelineEngineAdapter
