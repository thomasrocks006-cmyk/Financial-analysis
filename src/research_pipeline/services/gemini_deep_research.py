"""Gemini Deep Research Service — Stage 4.5 (pre-Evidence Librarian enrichment).

Fires one Gemini Deep Research call per active theme between Stage 4 (Data QA)
and Stage 5 (Evidence Librarian). Results are injected as Tier-3 qualitative
claims into the ClaimLedger before LLM sector analysts run, giving every
downstream agent richer qualitative context without touching the deterministic
quantitative data layer.

Architecture insertion point:
    Stage 4 (Data QA) → [GeminiDeepResearchService] → Stage 5 (Evidence Librarian)

Claim injection:
    - output_claim_tier:  3  (reputable journalism/research synthesis)
    - output_claim_class: qualitative
    - confidence_floor:   0.55
    - status:             unverified  (Evidence Librarian upgrades to verified)

Non-blocking: if Gemini is unavailable or times out, the pipeline logs a
WARNING and continues to Stage 5 without deep-research enrichment.

Usage:
    service = GeminiDeepResearchService(config)
    result = await service.run(active_themes, run_id)
    claim_ledger.merge(result.claims)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dependency guard — google-generativeai is optional; pipeline degrades
# gracefully if not installed.
# ---------------------------------------------------------------------------
try:
    import google.generativeai as genai  # type: ignore

    _GEMINI_AVAILABLE = True
except ImportError:
    genai = None  # type: ignore
    _GEMINI_AVAILABLE = False


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class DeepResearchClaim:
    """A single qualitative claim extracted from Gemini Deep Research output.

    Maps onto the ClaimLedger schema:
        evidence_class → qualitative
        source_tier    → 3
        status         → unverified (Evidence Librarian upgrades)
    """

    claim_id: str
    ticker: str  # primary ticker the claim relates to; "_MACRO" for cross-sector
    theme_key: str  # e.g. "ai_infrastructure", "us_financials"
    claim_text: str
    evidence_class: str = "qualitative"
    source_tier: int = 3
    source_ref: str = ""  # Gemini citation if available
    date_sourced: str = ""  # ISO 8601
    confidence: float = 0.55
    status: str = "unverified"
    supporting_claims: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class DeepResearchThemeResult:
    """Result of a single Gemini Deep Research call for one theme."""

    theme_key: str
    theme_label: str
    query: str
    raw_response: str
    claims: list[DeepResearchClaim]
    success: bool
    error: Optional[str] = None
    latency_seconds: float = 0.0
    model_used: str = ""


@dataclass
class DeepResearchRunResult:
    """Aggregated result across all themes for a pipeline run."""

    run_id: str
    timestamp: str
    themes_attempted: list[str]
    themes_succeeded: list[str]
    themes_failed: list[str]
    all_claims: list[DeepResearchClaim]
    theme_results: list[DeepResearchThemeResult]
    total_claims_injected: int = 0
    skipped_reason: Optional[str] = None  # set when deep_research.enabled = False


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class GeminiDeepResearchService:
    """Orchestrates Gemini Deep Research calls for all active themes.

    Instantiated once per pipeline run. Call ``run()`` after Stage 4 completes.
    """

    # Prompt scaffold for claim extraction — Gemini returns structured JSON
    _EXTRACTION_SUFFIX = """

──────────────────────────────────────────────────────────────────────────────
EXTRACTION INSTRUCTIONS
──────────────────────────────────────────────────────────────────────────────
After your research synthesis, extract the 10–20 most important qualitative
claims as a JSON array. Each claim object must follow this schema exactly:

{
  "ticker": "<PRIMARY_TICKER or '_MACRO' for cross-sector>",
  "claim_text": "<single factual assertion, one sentence>",
  "source_ref": "<URL or publication name where this was sourced>",
  "date_sourced": "<ISO 8601 date of source publication, e.g. 2026-04-01>",
  "confidence": <float 0.55–0.85>,
  "notes": "<any caveats, conflicts, or methodology notes>"
}

Return ONLY a valid JSON array — no surrounding prose. Example:
[
  {
    "ticker": "NVDA",
    "claim_text": "NVIDIA's Blackwell GPU architecture achieved 4x inference throughput vs H100 in Microsoft internal benchmarks published February 2026.",
    "source_ref": "https://blogs.microsoft.com/ai/...",
    "date_sourced": "2026-02-15",
    "confidence": 0.72,
    "notes": "Internal benchmark; independent verification pending."
  }
]
"""

    def __init__(self, config: dict[str, Any]):
        """
        Args:
            config: The pipeline config dict (or just the ``deep_research`` sub-dict).
                    Accepts both forms.
        """
        # Accept either the full pipeline config or just the deep_research sub-dict
        if "deep_research" in config:
            self._cfg = config["deep_research"]
        else:
            self._cfg = config

        self._enabled: bool = self._cfg.get("enabled", True)
        self._model_name: str = self._cfg.get("model", "gemini-2.5-pro")
        self._max_themes: int = self._cfg.get("max_themes_per_run", 5)
        self._timeout: float = float(self._cfg.get("timeout_seconds", 300))
        self._claim_tier: int = int(self._cfg.get("output_claim_tier", 3))
        self._confidence_floor: float = float(self._cfg.get("confidence_floor", 0.55))
        self._api_key_env: str = self._cfg.get("api_key_env", "GEMINI_API_KEY")
        self._cache_ttl: float = float(self._cfg.get("cache_ttl_hours", 12)) * 3600

        self._api_key: Optional[str] = os.environ.get(self._api_key_env)
        self._client: Any = None  # initialised lazily

    # ── Public API ──────────────────────────────────────────────────────────

    async def run(
        self,
        active_themes: list[dict[str, Any]],
        run_id: str,
        run_date: Optional[date] = None,
    ) -> DeepResearchRunResult:
        """Run deep research for all active themes.

        Args:
            active_themes: List of theme dicts from universe.yaml (already filtered
                           to the active set). Each dict must have keys:
                           ``key``, ``label``, ``deep_research_query``, ``coverage``.
            run_id:        Pipeline run UUID (for audit trail).
            run_date:      Date string injected into query templates. Defaults to today.

        Returns:
            DeepResearchRunResult aggregating all theme results and extracted claims.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        date_str = (run_date or date.today()).strftime("%B %d, %Y")

        # Early-exit cases
        if not self._enabled:
            logger.info("GeminiDeepResearch: disabled in config — skipping Stage 4.5")
            return DeepResearchRunResult(
                run_id=run_id,
                timestamp=timestamp,
                themes_attempted=[],
                themes_succeeded=[],
                themes_failed=[],
                all_claims=[],
                theme_results=[],
                skipped_reason="deep_research.enabled = false",
            )

        if not _GEMINI_AVAILABLE:
            logger.warning(
                "GeminiDeepResearch: google-generativeai not installed. "
                "Install with: pip install google-generativeai  — skipping Stage 4.5"
            )
            return DeepResearchRunResult(
                run_id=run_id,
                timestamp=timestamp,
                themes_attempted=[t.get("key", "") for t in active_themes],
                themes_succeeded=[],
                themes_failed=[t.get("key", "") for t in active_themes],
                all_claims=[],
                theme_results=[],
                skipped_reason="google-generativeai not installed",
            )

        if not self._api_key:
            logger.warning(
                f"GeminiDeepResearch: {self._api_key_env} env var not set — skipping Stage 4.5"
            )
            return DeepResearchRunResult(
                run_id=run_id,
                timestamp=timestamp,
                themes_attempted=[t.get("key", "") for t in active_themes],
                themes_succeeded=[],
                themes_failed=[t.get("key", "") for t in active_themes],
                all_claims=[],
                theme_results=[],
                skipped_reason=f"{self._api_key_env} not set",
            )

        # Limit themes to cap
        capped_themes = active_themes[: self._max_themes]
        if len(active_themes) > self._max_themes:
            logger.info(
                f"GeminiDeepResearch: capping to {self._max_themes} themes "
                f"(got {len(active_themes)}). Remaining: "
                f"{[t.get('key') for t in active_themes[self._max_themes :]]}"
            )

        self._init_client()

        # Run all themes concurrently (but respect timeout per theme)
        tasks = [self._run_theme(theme, date_str, run_id) for theme in capped_themes]
        theme_results: list[DeepResearchThemeResult] = await asyncio.gather(
            *tasks, return_exceptions=False
        )

        succeeded = [r.theme_key for r in theme_results if r.success]
        failed = [r.theme_key for r in theme_results if not r.success]
        all_claims = [c for r in theme_results for c in r.claims]

        logger.info(
            f"GeminiDeepResearch: completed — {len(succeeded)} themes succeeded, "
            f"{len(failed)} failed, {len(all_claims)} claims extracted"
        )

        return DeepResearchRunResult(
            run_id=run_id,
            timestamp=timestamp,
            themes_attempted=[t.get("key", "") for t in capped_themes],
            themes_succeeded=succeeded,
            themes_failed=failed,
            all_claims=all_claims,
            theme_results=theme_results,
            total_claims_injected=len(all_claims),
        )

    # ── Internal helpers ────────────────────────────────────────────────────

    def _init_client(self) -> None:
        """Initialise the Gemini client (once per service instance)."""
        if self._client is not None:
            return
        genai.configure(api_key=self._api_key)
        self._client = genai.GenerativeModel(
            model_name=self._model_name,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,  # slight creativity for synthesis
                max_output_tokens=8192,
            ),
        )
        logger.debug(f"GeminiDeepResearch: client initialised with model={self._model_name}")

    async def _run_theme(
        self,
        theme: dict[str, Any],
        date_str: str,
        run_id: str,
    ) -> DeepResearchThemeResult:
        """Run deep research for a single theme."""
        theme_key = theme.get("key", "unknown")
        theme_label = theme.get("label", theme_key)
        tickers = [c.get("ticker", "") for c in theme.get("coverage", [])]
        ticker_str = ", ".join(tickers) if tickers else "see coverage list"

        # Build query from template
        query_template = theme.get(
            "deep_research_query",
            f"Synthesise the current investment outlook for {theme_label} as of {{date}}. "
            f"Focus on: {{tickers}}.",
        )
        query = query_template.format(date=date_str, tickers=ticker_str, instruments=ticker_str)
        full_prompt = query.strip() + self._EXTRACTION_SUFFIX

        start_time = time.monotonic()
        try:
            raw_response = await asyncio.wait_for(
                asyncio.to_thread(self._call_gemini, full_prompt),
                timeout=self._timeout,
            )
            latency = time.monotonic() - start_time
            claims = self._extract_claims(raw_response, theme_key, tickers, run_id)
            logger.info(
                f"GeminiDeepResearch: theme={theme_key} OK — {len(claims)} claims in {latency:.1f}s"
            )
            return DeepResearchThemeResult(
                theme_key=theme_key,
                theme_label=theme_label,
                query=query,
                raw_response=raw_response,
                claims=claims,
                success=True,
                latency_seconds=latency,
                model_used=self._model_name,
            )
        except asyncio.TimeoutError:
            latency = time.monotonic() - start_time
            msg = f"timeout after {self._timeout}s"
            logger.warning(f"GeminiDeepResearch: theme={theme_key} FAILED — {msg}")
            return DeepResearchThemeResult(
                theme_key=theme_key,
                theme_label=theme_label,
                query=query,
                raw_response="",
                claims=[],
                success=False,
                error=msg,
                latency_seconds=latency,
                model_used=self._model_name,
            )
        except Exception as exc:
            latency = time.monotonic() - start_time
            msg = str(exc)
            logger.warning(f"GeminiDeepResearch: theme={theme_key} FAILED — {msg}")
            return DeepResearchThemeResult(
                theme_key=theme_key,
                theme_label=theme_label,
                query=query,
                raw_response="",
                claims=[],
                success=False,
                error=msg,
                latency_seconds=latency,
                model_used=self._model_name,
            )

    def _call_gemini(self, prompt: str) -> str:
        """Synchronous Gemini API call (run in thread via asyncio.to_thread)."""
        response = self._client.generate_content(prompt)
        return response.text

    def _extract_claims(
        self,
        raw_response: str,
        theme_key: str,
        theme_tickers: list[str],
        run_id: str,
    ) -> list[DeepResearchClaim]:
        """Parse Gemini response and build DeepResearchClaim objects.

        Gemini is instructed to append a JSON array at the end of its response.
        We locate the last JSON array in the text (robust to preamble prose).
        """
        # Find the last JSON array in the response
        json_str = self._find_last_json_array(raw_response)
        if not json_str:
            logger.warning(
                f"GeminiDeepResearch: theme={theme_key} — no JSON array found in response; "
                "falling back to zero claims"
            )
            return []

        try:
            raw_claims: list[dict] = json.loads(json_str)
        except json.JSONDecodeError as exc:
            logger.warning(
                f"GeminiDeepResearch: theme={theme_key} — JSON parse error: {exc}; "
                "falling back to zero claims"
            )
            return []

        today_iso = date.today().isoformat()
        claims: list[DeepResearchClaim] = []

        for idx, raw in enumerate(raw_claims):
            if not isinstance(raw, dict):
                continue

            ticker = raw.get("ticker", "_MACRO").strip()
            claim_text = raw.get("claim_text", "").strip()
            if not claim_text:
                continue

            # Validate ticker is in expected set (or _MACRO / cross-theme)
            known_tickers = set(theme_tickers) | {"_MACRO"}
            if ticker not in known_tickers:
                # Accept it but flag in notes
                extra_note = f"[ticker '{ticker}' not in theme universe] "
            else:
                extra_note = ""

            # Build deterministic claim_id
            hash_input = f"{run_id}:{theme_key}:{idx}:{claim_text[:50]}"
            claim_id = "CLM-DR-" + hashlib.sha1(hash_input.encode()).hexdigest()[:8].upper()

            # Clamp confidence to tier floor
            confidence = float(raw.get("confidence", self._confidence_floor))
            confidence = max(self._confidence_floor, min(0.85, confidence))

            claims.append(
                DeepResearchClaim(
                    claim_id=claim_id,
                    ticker=ticker,
                    theme_key=theme_key,
                    claim_text=claim_text,
                    evidence_class="qualitative",
                    source_tier=self._claim_tier,
                    source_ref=raw.get("source_ref", "Gemini Deep Research synthesis"),
                    date_sourced=raw.get("date_sourced", today_iso),
                    confidence=confidence,
                    status="unverified",
                    supporting_claims=[],
                    notes=extra_note + raw.get("notes", ""),
                )
            )

        return claims

    @staticmethod
    def _find_last_json_array(text: str) -> Optional[str]:
        """Extract the last valid JSON array from a text block.

        Works by finding the last '[' and scanning forward to its matching ']'.
        Handles nested structures.
        """
        last_start = text.rfind("[")
        if last_start == -1:
            return None

        depth = 0
        in_string = False
        escape_next = False

        for i, ch in enumerate(text[last_start:], start=last_start):
            if escape_next:
                escape_next = False
                continue
            if ch == "\\" and in_string:
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return text[last_start : i + 1]
        return None


# ---------------------------------------------------------------------------
# Convenience: convert DeepResearchClaim → ClaimLedger dict format
# ---------------------------------------------------------------------------


def deep_research_claim_to_ledger_dict(claim: DeepResearchClaim) -> dict[str, Any]:
    """Convert a DeepResearchClaim into the ClaimLedger JSON schema.

    Suitable for direct insertion into EvidenceLibrarianAgent's ClaimLedger.
    """
    return {
        "claim_id": claim.claim_id,
        "ticker": claim.ticker,
        "claim_text": claim.claim_text,
        "evidence_class": claim.evidence_class,
        "source_tier": claim.source_tier,
        "source_ref": claim.source_ref,
        "date_sourced": claim.date_sourced,
        "confidence": claim.confidence,
        "status": claim.status,
        "supporting_claims": claim.supporting_claims,
        "notes": f"[Gemini Deep Research — theme: {claim.theme_key}] {claim.notes}".strip(),
    }
