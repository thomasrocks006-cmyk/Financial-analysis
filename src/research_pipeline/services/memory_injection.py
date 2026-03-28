"""Phase 6.2/6.6 — Memory Injection & Error Pattern Library.

Provides context injection from the research memory corpus into agent runs,
and maintains a library of past red-team falsifications for reuse.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ErrorPattern:
    """A captured red-team falsification or error pattern for future injection."""
    pattern_id: str
    ticker: str
    run_id: str
    captured_at: datetime
    category: str          # "thesis_errors", "execution_risks", "valuation_gaps", "macro_risks"
    assumption_text: str   # the bullish assumption that was challenged
    falsification: str     # the specific disconfirmation path
    severity: str          # "HIGH", "MEDIUM", "LOW"
    was_realised: bool = False   # True if the risk materialised after the run
    notes: str = ""


@dataclass
class InjectedContext:
    """Context block assembled from memory + patterns for agent input."""
    ticker: str
    prior_thesis_summaries: list[str] = field(default_factory=list)
    prior_red_team_risks: list[str] = field(default_factory=list)
    prior_factor_exposures: list[str] = field(default_factory=list)
    prior_valuation_targets: list[str] = field(default_factory=list)
    relevant_errors: list[str] = field(default_factory=list)
    run_count: int = 0

    def to_prompt_block(self) -> str:
        """Format injected context as a prompt-ready block."""
        if not any([
            self.prior_thesis_summaries, self.prior_red_team_risks,
            self.prior_factor_exposures, self.prior_valuation_targets,
            self.relevant_errors,
        ]):
            return ""

        lines = [f"=== INSTITUTIONAL MEMORY: {self.ticker} (from {self.run_count} prior runs) ==="]

        if self.prior_thesis_summaries:
            lines.append("\nPRIOR THESIS EVOLUTION:")
            for t in self.prior_thesis_summaries[-3:]:    # last 3 only
                lines.append(f"  • {t}")

        if self.prior_red_team_risks:
            lines.append("\nPREVIOUSLY IDENTIFIED RISKS (must be addressed or refuted):")
            for r in self.prior_red_team_risks[-5:]:
                lines.append(f"  • {r}")

        if self.prior_valuation_targets:
            lines.append("\nPRIOR VALUATION SNAPSHOTS:")
            for v in self.prior_valuation_targets[-3:]:
                lines.append(f"  • {v}")

        if self.relevant_errors:
            lines.append("\nPAST FALSIFICATION PATTERNS (for red team awareness):")
            for e in self.relevant_errors[-3:]:
                lines.append(f"  ⚠ {e}")

        lines.append("=== END INSTITUTIONAL MEMORY ===\n")
        return "\n".join(lines)


class MemoryInjectionService:
    """Injects relevant prior research context into new agent runs.

    Phase 6.2: Context injection from ResearchMemory (SQLite FTS5 corpus).
    Phase 6.6: Error pattern library for red-team enrichment.

    Designed to be wired in to format_input() / build_messages() of any agent.
    """

    def __init__(
        self,
        memory_store_path: Path | None = None,
        patterns_path: Path | None = None,
    ):
        from research_pipeline.services.research_memory import ResearchMemory
        self._memory = ResearchMemory(
            db_path=memory_store_path or Path("output/research_memory.db")
        )
        self._patterns_path = patterns_path or Path("output/error_patterns.json")
        self._patterns: list[ErrorPattern] = self._load_patterns()

    # ── Pattern Library ──────────────────────────────────────────────────────

    def _load_patterns(self) -> list[ErrorPattern]:
        """Load error patterns from disk."""
        if not self._patterns_path.exists():
            return []
        try:
            raw = json.loads(self._patterns_path.read_text())
            return [
                ErrorPattern(
                    pattern_id=p["pattern_id"],
                    ticker=p["ticker"],
                    run_id=p["run_id"],
                    captured_at=datetime.fromisoformat(p["captured_at"]),
                    category=p["category"],
                    assumption_text=p["assumption_text"],
                    falsification=p["falsification"],
                    severity=p["severity"],
                    was_realised=p.get("was_realised", False),
                    notes=p.get("notes", ""),
                )
                for p in raw
            ]
        except Exception as exc:
            logger.warning("Could not load error patterns: %s", exc)
            return []

    def _save_patterns(self) -> None:
        """Persist patterns to disk."""
        self._patterns_path.parent.mkdir(parents=True, exist_ok=True)
        data = [
            {
                "pattern_id": p.pattern_id,
                "ticker": p.ticker,
                "run_id": p.run_id,
                "captured_at": p.captured_at.isoformat(),
                "category": p.category,
                "assumption_text": p.assumption_text,
                "falsification": p.falsification,
                "severity": p.severity,
                "was_realised": p.was_realised,
                "notes": p.notes,
            }
            for p in self._patterns
        ]
        self._patterns_path.write_text(json.dumps(data, indent=2))

    def capture_red_team_patterns(
        self, run_id: str, red_team_output: dict[str, Any]
    ) -> int:
        """Extract falsification paths from a red team output and save to library.

        Returns number of patterns captured.
        """
        assessments = red_team_output.get("assessments", [])
        if isinstance(red_team_output, list):
            assessments = red_team_output

        captured = 0
        for assessment in assessments:
            if not isinstance(assessment, dict):
                continue
            ticker = assessment.get("ticker", "UNKNOWN")
            for test in assessment.get("section_2_falsification_tests", []):
                if not isinstance(test, dict):
                    continue
                pattern_id = f"P-{run_id}-{ticker}-{len(self._patterns)+1:04d}"
                prob = test.get("current_probability", "MEDIUM").upper()
                severity = "HIGH" if prob == "HIGH" else "MEDIUM" if prob == "MEDIUM" else "LOW"
                self._patterns.append(ErrorPattern(
                    pattern_id=pattern_id,
                    ticker=ticker,
                    run_id=run_id,
                    captured_at=datetime.now(timezone.utc),
                    category="thesis_errors",
                    assumption_text=test.get("assumption", ""),
                    falsification=test.get("test", ""),
                    severity=severity,
                    notes=test.get("evidence_trigger", ""),
                ))
                captured += 1

        if captured > 0:
            self._save_patterns()
        logger.info("Captured %d error patterns from run %s", captured, run_id)
        return captured

    def get_patterns_for_ticker(
        self, ticker: str, max_patterns: int = 5
    ) -> list[ErrorPattern]:
        """Retrieve relevant error patterns for a ticker."""
        ticker_patterns = [p for p in self._patterns if p.ticker == ticker]
        # Prioritise high-severity and recently realised risks
        ticker_patterns.sort(key=lambda p: (p.was_realised, p.severity == "HIGH"), reverse=True)
        return ticker_patterns[:max_patterns]

    # ── Memory Injection ─────────────────────────────────────────────────────

    def build_injected_context(
        self,
        tickers: list[str],
        run_id: str,
        max_per_ticker: int = 3,
    ) -> dict[str, InjectedContext]:
        """Build InjectedContext for each ticker by querying research memory.

        Returns {ticker: InjectedContext} for all requested tickers.
        """
        contexts: dict[str, InjectedContext] = {}

        for ticker in tickers:
            ctx = InjectedContext(ticker=ticker)

            # Search for prior theses
            thesis_results = self._memory.get_thesis_evolution(ticker)
            for thesis in thesis_results[-max_per_ticker:]:
                status = thesis.get("status", "unknown")
                text = thesis.get("thesis_text", "")[:200]
                ctx.prior_thesis_summaries.append(f"[{status.upper()}] {text}")
            ctx.run_count = len(thesis_results)

            # Search FTS for red team risks
            risk_results = self._memory.search(
                query=f"{ticker} risk falsification",
                doc_type="red_team",
                ticker=ticker,
                limit=max_per_ticker,
            )
            for r in risk_results:
                ctx.prior_red_team_risks.append(r.get("content", "")[:150])

            # Search for valuation snapshots
            val_results = self._memory.search(
                query=f"{ticker} price target valuation",
                doc_type="valuation",
                ticker=ticker,
                limit=max_per_ticker,
            )
            for v in val_results:
                ctx.prior_valuation_targets.append(v.get("content", "")[:150])

            # Error patterns
            patterns = self.get_patterns_for_ticker(ticker, max_per_ticker)
            for p in patterns:
                severity_label = f"[{p.severity}]"
                ctx.relevant_errors.append(
                    f"{severity_label} Assumption: {p.assumption_text[:100]} → "
                    f"Risk: {p.falsification[:100]}"
                )

            contexts[ticker] = ctx

        return contexts

    def inject_into_inputs(
        self,
        inputs: dict[str, Any],
        run_id: str,
        max_per_ticker: int = 3,
    ) -> dict[str, Any]:
        """Add memory context to agent inputs dict.

        Enriches inputs["prior_context"] with assembled InjectedContext blocks.
        Returns updated inputs (does NOT mutate the original).
        """
        tickers = inputs.get("tickers", [])
        if not tickers:
            return inputs

        contexts = self.build_injected_context(tickers, run_id, max_per_ticker)

        combined_context = ""
        for ticker in tickers:
            ctx = contexts.get(ticker)
            if ctx:
                block = ctx.to_prompt_block()
                if block:
                    combined_context += block

        if combined_context:
            updated = dict(inputs)
            updated["prior_context"] = combined_context
            return updated

        return inputs

    # ── Phase 6.4: Model Drift Detection ────────────────────────────────────

    def detect_output_drift(
        self,
        run_id: str,
        agent_name: str,
        current_output: dict[str, Any],
        lookback_runs: int = 5,
    ) -> dict[str, Any]:
        """Compare current agent output structure vs prior runs for drift detection.

        Returns drift report:
        {
          "drift_detected": bool,
          "severity": "none|low|medium|high",
          "changes": [list of structural changes],
          "current_key_count": int,
          "historic_avg_key_count": float,
        }
        """
        # Query memory for prior outputs from the same agent
        prior = self._memory.search(
            query=agent_name,
            doc_type=agent_name,
            limit=lookback_runs,
        )

        if len(prior) < 2:
            return {"drift_detected": False, "severity": "none", "changes": [], "prior_runs": 0}

        current_keys = set(current_output.keys()) if isinstance(current_output, dict) else set()
        prior_key_sets = []
        for p in prior:
            try:
                raw = json.loads(p.get("content", "{}"))
                if isinstance(raw, dict):
                    prior_key_sets.append(set(raw.keys()))
            except json.JSONDecodeError:
                pass

        if not prior_key_sets:
            return {"drift_detected": False, "severity": "none", "changes": [], "prior_runs": 0}

        # Union of all prior keys (expected schema)
        expected_keys = prior_key_sets[0]
        for ks in prior_key_sets[1:]:
            expected_keys = expected_keys & ks  # intersection — keys present in ALL prior runs

        missing_keys = expected_keys - current_keys
        new_keys = current_keys - expected_keys

        changes = []
        for k in missing_keys:
            changes.append(f"Key removed: '{k}'")
        for k in new_keys:
            changes.append(f"Key added: '{k}'")

        drift_detected = bool(changes)
        severity = "none"
        if len(changes) >= 5:
            severity = "high"
        elif len(changes) >= 2:
            severity = "medium"
        elif changes:
            severity = "low"

        avg_prior_keys = sum(len(ks) for ks in prior_key_sets) / len(prior_key_sets)

        return {
            "drift_detected": drift_detected,
            "severity": severity,
            "changes": changes,
            "current_key_count": len(current_keys),
            "historic_avg_key_count": round(avg_prior_keys, 1),
            "prior_runs": len(prior_key_sets),
        }

    # ── Phase 6.7: Performance Feedback Loop ────────────────────────────────

    def compute_thesis_success_patterns(
        self, threshold_days: int = 90
    ) -> dict[str, Any]:
        """Analyse prior theses to identify patterns associated with success.

        Returns a summary of what thesis characteristics correlated with
        CONFIRMED vs INVALIDATED outcomes.
        """
        confirmed_patterns: list[str] = []
        invalidated_patterns: list[str] = []

        for ticker in self._get_covered_tickers():
            evolution = self._memory.get_thesis_evolution(ticker)
            for thesis in evolution:
                status = thesis.get("status", "").upper()
                text = thesis.get("thesis_text", "")
                if status == "CONFIRMED":
                    confirmed_patterns.append(text[:100])
                elif status == "INVALIDATED":
                    invalidated_patterns.append(text[:100])

        return {
            "confirmed_count": len(confirmed_patterns),
            "invalidated_count": len(invalidated_patterns),
            "confirmed_samples": confirmed_patterns[:5],
            "invalidated_samples": invalidated_patterns[:5],
            "coverage_note": f"Based on {len(self._patterns)} captured error patterns",
        }

    def _get_covered_tickers(self) -> list[str]:
        """Get list of tickers with any stored thesis history."""
        results = self._memory.search("thesis", limit=1000)
        return list({r.get("ticker", "") for r in results if r.get("ticker")})
