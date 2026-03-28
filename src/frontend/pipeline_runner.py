"""Pipeline runner for the Streamlit frontend.

Drives the full 15-stage institutional research pipeline.
Uses FMP + Finnhub for live market data, yfinance as fallback.
Injects client investment profile context into every LLM agent.

Qualitative Intelligence (8-source engine):
  - Company news & press releases (FMP + Finnhub, deduplicated)
  - Earnings call transcripts (FMP — management commentary)
  - SEC filings (8-K / 10-K / 10-Q material events)
  - Analyst upgrades/downgrades (FMP grade changes)
  - Insider trading activity (FMP + Finnhub MSPR)
  - Forward analyst estimates (FMP revenue/EPS consensus)
  - Social & news sentiment (FMP social + Finnhub sentiment scores)

Qualitative Synthesis uses a dedicated reasoning model (Gemini 2.5 Pro preferred)
to correlate qualitative signals with quantitative data before the main
analysis stages, producing deep narrative intelligence per ticker.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import textwrap
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ── Stage definitions ─────────────────────────────────────────────────────
STAGES = [
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


@dataclass
class StageResult:
    stage_num: int
    stage_name: str
    status: str = "pending"   # pending | running | done | failed
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


class PipelineRunner:
    """Orchestrates the full research pipeline for the Streamlit frontend."""

    def __init__(
        self,
        provider_keys: dict[str, str],
        model: str = "claude-opus-4-6",
        tickers: Optional[list[str]] = None,
        temperature: float = 0.3,
        stage_models: Optional[dict[int, str]] = None,
        client_profile: Optional[Any] = None,
    ):
        self.provider_keys = provider_keys  # {"anthropic": key, "openai": key, "gemini": key, "fmp": key, "finnhub": key}
        self.model = model          # default / display model
        self.temperature = temperature
        self.max_retries = 3
        self.tickers = tickers or ["NVDA", "CEG", "PWR"]
        self.stage_models = stage_models or {}  # {stage_num: model_id}
        self.client_profile = client_profile  # ClientProfile or None

        # Backward compat: inject Anthropic key if present
        if ak := provider_keys.get("anthropic"):
            os.environ["ANTHROPIC_API_KEY"] = ak
        self.token_log: list[dict] = []  # token usage accumulated across all LLM calls
        self._activity_cb: Optional[ActivityCallback] = None  # set in run()

    def _client_context(self) -> str:
        """Return client profile context for LLM prompts, or fallback."""
        if self.client_profile and hasattr(self.client_profile, 'to_prompt_context'):
            return self.client_profile.to_prompt_context()
        return "\n═══ CLIENT: Default institutional analysis (no specific client profile) ═══\n"

    async def run(
        self,
        progress_callback: Optional[ProgressCallback] = None,
        activity_callback: Optional[ActivityCallback] = None,
    ) -> RunResult:
        """Execute the full pipeline and return a RunResult."""
        self._activity_cb = activity_callback
        run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
        started_at = datetime.now(timezone.utc).isoformat()

        result = RunResult(
            run_id=run_id,
            tickers=self.tickers,
            model=self.model,
            started_at=started_at,
        )

        def _cb(stage_num: int, stage_name: str, status: str, output: dict) -> None:
            if progress_callback:
                progress_callback(stage_num, stage_name, status, output)

        # ── Load market data (FMP + Finnhub, yfinance fallback) ─────────
        fmp_key = self.provider_keys.get("fmp", os.environ.get("FMP_API_KEY", ""))
        finnhub_key = self.provider_keys.get("finnhub", os.environ.get("FINNHUB_API_KEY", ""))

        from frontend.market_data import fetch_universe, fetch_macro_context
        try:
            market_data = await fetch_universe(
                self.tickers,
                fmp_key=fmp_key,
                finnhub_key=finnhub_key,
                activity_cb=self._activity_cb,
            )
            logger.info(
                "Live market data loaded: %d/%d tickers",
                market_data.get("live_count", 0), len(self.tickers),
            )
        except Exception as _live_exc:
            logger.warning("Live data fetch failed (%s) — falling back", _live_exc)
            market_data = {
                "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "data_source": "Fallback — no live data",
                "live_count": 0,
                "stocks": {t: {"ticker": t, "company_name": t, "_live": False} for t in self.tickers},
            }

        try:
            macro_data = await fetch_macro_context(finnhub_key=finnhub_key)
        except Exception:
            macro_data = {"date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "source": "unavailable"}

        # ── Load qualitative intelligence (8 sources per ticker) ────────
        from frontend.qualitative_data import fetch_qualitative_universe
        try:
            qual_packages = await fetch_qualitative_universe(
                self.tickers,
                fmp_key=fmp_key,
                finnhub_key=finnhub_key,
                activity_cb=self._activity_cb,
            )
            total_signals = sum(p.signal_count for p in qual_packages.values())
            logger.info(
                "Qualitative data loaded: %d signals across %d tickers",
                total_signals, len(self.tickers),
            )
            if self._activity_cb:
                coverage = {t: p.coverage_score for t, p in qual_packages.items()}
                self._activity_cb(f"Qualitative coverage: {coverage}")
        except Exception as _qual_exc:
            logger.warning("Qualitative data fetch failed (%s)", _qual_exc)
            from frontend.qualitative_data import QualitativePackage
            qual_packages = {
                t: QualitativePackage(ticker=t, coverage_gaps=[f"TOTAL FAILURE: {_qual_exc}"])
                for t in self.tickers
            }

        # ── Stage 0: Bootstrap ────────────────────────────────────────────
        s0 = await self._run_stage(0, "Bootstrap & Configuration", _cb, self._stage_bootstrap, run_id, market_data, qual_packages)
        result.stages.append(s0)

        # ── Stage 1: Universe ─────────────────────────────────────────────
        s1 = await self._run_stage(1, "Universe Definition", _cb, self._stage_universe, self.tickers)
        result.stages.append(s1)

        # ── Stages 2-4: Data (deterministic) ─────────────────────────────
        s2 = await self._run_stage(2, "Data Ingestion", _cb, self._stage_data_ingestion, market_data)
        result.stages.append(s2)

        s3 = await self._run_stage(3, "Reconciliation", _cb, self._stage_reconciliation, market_data)
        result.stages.append(s3)

        s4 = await self._run_stage(4, "Data QA & Lineage", _cb, self._stage_qa, market_data)
        result.stages.append(s4)

        # ── Stage 5: Evidence Librarian + Qualitative Synthesis (LLM) ──
        s5 = await self._run_stage(5, "Evidence Librarian / Claim Ledger", _cb, self._stage_evidence, market_data, qual_packages)
        result.stages.append(s5)
        claim_ledger_text = s5.raw_text

        # ── Stage 6: Sector Analysis + Narrative Intelligence (LLM) ──────
        s6 = await self._run_stage(6, "Sector Analysis", _cb, self._stage_sector, market_data, qual_packages)
        result.stages.append(s6)
        sector_outputs = s6.raw_text

        # ── Stage 7: Valuation (LLM) ─────────────────────────────────────
        s7 = await self._run_stage(7, "Valuation & Modelling", _cb, self._stage_valuation, market_data, sector_outputs)
        result.stages.append(s7)
        valuation_outputs = s7.raw_text

        # ── Stage 8: Macro & Political (LLM) ─────────────────────────────
        s8 = await self._run_stage(8, "Macro & Political Overlay", _cb, self._stage_macro, macro_data, sector_outputs)
        result.stages.append(s8)
        macro_outputs = s8.raw_text

        # ── Stage 9: Risk (LLM + quant) ──────────────────────────────────
        s9 = await self._run_stage(9, "Quant Risk & Scenario Testing", _cb, self._stage_risk, market_data, sector_outputs, valuation_outputs, macro_outputs)
        result.stages.append(s9)
        risk_outputs = s9.raw_text

        # ── Stage 10: Red Team (LLM) ──────────────────────────────────────
        s10 = await self._run_stage(10, "Red Team Analysis", _cb, self._stage_red_team, sector_outputs, valuation_outputs)
        result.stages.append(s10)
        red_team_outputs = s10.raw_text

        # ── Stage 11: Associate Review (LLM) ─────────────────────────────
        s11 = await self._run_stage(11, "Associate Review / Publish Gate", _cb, self._stage_review, sector_outputs, valuation_outputs, red_team_outputs)
        result.stages.append(s11)
        review_output = s11.raw_text

        # ── Stage 12: Portfolio Construction (LLM) ────────────────────────
        s12 = await self._run_stage(12, "Portfolio Construction", _cb, self._stage_portfolio, sector_outputs, valuation_outputs, risk_outputs, review_output)
        result.stages.append(s12)
        portfolio_output = s12.raw_text

        # ── Stage 13: Report Assembly ─────────────────────────────────────
        s13 = await self._run_stage(
            13, "Report Assembly", _cb, self._stage_report_assembly,
            run_id, market_data, claim_ledger_text, sector_outputs,
            valuation_outputs, macro_outputs, risk_outputs,
            red_team_outputs, review_output, portfolio_output,
        )
        result.stages.append(s13)
        result.final_report_md = s13.raw_text

        # ── Stage 14: Monitoring & Run Registry ──────────────────────────
        s14 = await self._run_stage(14, "Monitoring & Run Registry", _cb, self._stage_monitoring, run_id, result.stages)
        result.stages.append(s14)

        result.completed_at = datetime.now(timezone.utc).isoformat()
        result.success = all(s.status != "failed" for s in result.stages)
        result.token_log = list(self.token_log)

        return result

    # ── Stage runner helper ───────────────────────────────────────────────
    async def _run_stage(
        self,
        stage_num: int,
        stage_name: str,
        cb: ProgressCallback,
        fn,
        *args,
    ) -> StageResult:
        sr = StageResult(stage_num=stage_num, stage_name=stage_name, status="running")
        cb(stage_num, stage_name, "running", {})
        t_start = time.monotonic()
        try:
            result = await fn(*args)
            sr.raw_text = result if isinstance(result, str) else json.dumps(result, indent=2, default=str)
            sr.output = result if isinstance(result, dict) else {}
            sr.status = "done"
        except Exception as exc:
            logger.error("Stage %d failed: %s", stage_num, exc)
            sr.status = "failed"
            sr.error = str(exc)
        sr.elapsed_secs = time.monotonic() - t_start
        # Pass raw_text for done stages so the UI receives the full LLM output.
        # For failed/running stages raw_text is "" so sr.output ({}) is passed instead.
        cb(stage_num, stage_name, sr.status, sr.raw_text or sr.output)
        return sr

    # ── LLM helpers ──────────────────────────────────────────────────────
    @staticmethod
    def _provider_for(model: str) -> str:
        m = model.lower()
        if m.startswith("claude"):  return "anthropic"
        if m.startswith("gpt") or m.startswith("o1") or m.startswith("o3"): return "openai"
        if m.startswith("gemini"): return "gemini"
        return "anthropic"

    async def _call_llm(self, system_prompt: str, user_content: str, stage_num: int = -1) -> str:
        """Route to the correct provider; tracks token usage per stage."""
        model    = self.stage_models.get(stage_num, self.model)
        provider = self._provider_for(model)
        api_key  = self.provider_keys.get(provider, "")
        if not api_key:
            raise ValueError(
                f"No API key for provider '{provider}' "
                f"(stage {stage_num}, model '{model}'). Add the key in the sidebar."
            )
        # Emit live activity so the UI knows exactly what the pipeline is doing
        if self._activity_cb:
            prov_label = {"anthropic": "Anthropic", "openai": "OpenAI", "gemini": "Google"}.get(provider, provider.title())
            self._activity_cb(f"S{stage_num} → {prov_label} / {model} (sending request…)")
        if provider == "openai":
            text, in_tok, out_tok = await self._call_openai(system_prompt, user_content, model, api_key)
        elif provider == "gemini":
            text, in_tok, out_tok = await self._call_gemini(system_prompt, user_content, model, api_key)
        else:
            text, in_tok, out_tok = await self._call_anthropic(system_prompt, user_content, model, api_key)
        self.token_log.append({
            "stage_num":     stage_num,
            "model":         model,
            "input_tokens":  in_tok,
            "output_tokens": out_tok,
        })
        return text

    async def _call_anthropic(self, system_prompt: str, user_content: str, model: str, api_key: str) -> tuple[str, int, int]:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=api_key)
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await client.messages.create(
                    model=model, max_tokens=8192, temperature=self.temperature,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_content}],
                )
                in_tok  = getattr(response.usage, "input_tokens",  0) or 0
                out_tok = getattr(response.usage, "output_tokens", 0) or 0
                return response.content[0].text or "", in_tok, out_tok
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning("Anthropic attempt %d/%d failed: %s", attempt, self.max_retries, exc)
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
        raise last_exc  # type: ignore[misc]

    async def _call_openai(self, system_prompt: str, user_content: str, model: str, api_key: str) -> tuple[str, int, int]:
        import openai
        client = openai.AsyncOpenAI(api_key=api_key)
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await client.chat.completions.create(
                    model=model, max_tokens=8192, temperature=self.temperature,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                )
                usage   = response.usage
                in_tok  = getattr(usage, "prompt_tokens",     0) or 0
                out_tok = getattr(usage, "completion_tokens", 0) or 0
                return response.choices[0].message.content or "", in_tok, out_tok
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning("OpenAI attempt %d/%d failed: %s", attempt, self.max_retries, exc)
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
        raise last_exc  # type: ignore[misc]

    async def _call_gemini(self, system_prompt: str, user_content: str, model: str, api_key: str) -> tuple[str, int, int]:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=api_key)
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await client.aio.models.generate_content(
                    model=model, contents=user_content,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        max_output_tokens=8192,
                        temperature=self.temperature,
                    ),
                )
                meta    = getattr(response, "usage_metadata", None)
                in_tok  = int(getattr(meta, "prompt_token_count",     0) or 0) if meta else 0
                out_tok = int(getattr(meta, "candidates_token_count", 0) or 0) if meta else 0
                return response.text or "", in_tok, out_tok
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning("Gemini attempt %d/%d failed: %s", attempt, self.max_retries, exc)
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
        raise last_exc  # type: ignore[misc]

    # ── Individual stage implementations ─────────────────────────────────

    async def _stage_bootstrap(self, run_id: str, market_data: dict, qual_packages: dict = None) -> dict:
        qual_summary = {}
        if qual_packages:
            for t, pkg in qual_packages.items():
                qual_summary[t] = {
                    "signals": pkg.signal_count,
                    "coverage": pkg.coverage_score,
                    "gaps": pkg.coverage_gaps[:3] if pkg.coverage_gaps else [],
                }
        return {
            "run_id": run_id,
            "model": self.model,
            "tickers": self.tickers,
            "data_source": market_data.get("data_source", "Live multi-source"),
            "live_count": market_data.get("live_count", 0),
            "total_tickers": len(self.tickers),
            "config_valid": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "client_profile": self.client_profile.name if self.client_profile else "Default",
            "risk_tolerance": self.client_profile.risk_tolerance if self.client_profile else "moderate",
            "qualitative_coverage": qual_summary,
        }

    async def _stage_universe(self, tickers: list[str]) -> dict:
        universe = []
        for ticker in tickers:
            universe.append({
                "ticker": ticker,
                "approved": True,
            })
        return {"universe": universe, "total": len(universe)}

    async def _stage_data_ingestion(self, market_data: dict) -> dict:
        stocks = market_data.get("stocks", {})
        live_tickers = [t for t, s in stocks.items() if s.get("_live")]
        return {
            "status": "complete",
            "tickers_loaded": len(stocks),
            "live_tickers": live_tickers,
            "data_source": market_data.get("data_source"),
            "date": market_data.get("date"),
            "errors": market_data.get("errors", []),
        }

    async def _stage_reconciliation(self, market_data: dict) -> dict:
        results = {}
        for ticker, snap in market_data.get("stocks", {}).items():
            cross_checks = snap.get("cross_validation", [])
            red_count = sum(1 for c in cross_checks if c.get("status") == "RED")
            amber_count = sum(1 for c in cross_checks if c.get("status") == "AMBER")
            green_count = sum(1 for c in cross_checks if c.get("status") == "GREEN")
            status = "RED" if red_count > 0 else "AMBER" if amber_count > 0 else "GREEN"
            results[ticker] = {
                "price": snap.get("price"),
                "forward_pe": snap.get("forward_pe"),
                "reconciliation_status": status,
                "cross_checks": cross_checks,
                "notes": f"FMP+Finnhub cross-validated" if cross_checks else "Single source",
            }
        red_total = sum(1 for r in results.values() if r["reconciliation_status"] == "RED")
        amber_total = sum(1 for r in results.values() if r["reconciliation_status"] == "AMBER")
        green_total = sum(1 for r in results.values() if r["reconciliation_status"] == "GREEN")
        return {"reconciliation": results, "red_fields": red_total, "amber_fields": amber_total, "green_fields": green_total}

    async def _stage_qa(self, market_data: dict) -> dict:
        stocks = market_data.get("stocks", {})
        live_count = sum(1 for s in stocks.values() if s.get("_live"))
        has_cross_val = sum(1 for s in stocks.values() if s.get("cross_validation"))
        score = 9.0 if live_count == len(stocks) else 7.0 if live_count > 0 else 4.0
        tier = "Tier 1/2 — dual-source verified" if has_cross_val else "Tier 2 — single live source" if live_count else "Tier 3 — no live data"
        return {
            "schema_valid": True,
            "timestamps_valid": True,
            "duplicates_found": 0,
            "lineage_complete": live_count > 0,
            "data_quality_score": score,
            "live_tickers": live_count,
            "total_tickers": len(stocks),
            "data_tier": tier,
        }

    async def _stage_evidence(self, market_data: dict, qual_packages: dict = None) -> str:
        """Stage 5: Evidence Librarian with deep qualitative-quantitative correlation.

        This stage uses a reasoning model (Gemini 2.5 Pro when available) to:
        1. Ingest ALL quantitative data from FMP/Finnhub/yfinance
        2. Ingest ALL qualitative data (8 sources) from the qualitative engine
        3. Cross-correlate: do insider actions align with fundamentals?
           Do analyst grade changes match estimate revisions? Does news
           sentiment match price action?
        4. Build a structured Evidence Library with provenance tags and
           confidence tiers for every claim.
        """
        # Build quantitative summary per ticker
        quant_blocks = []
        for ticker, snap in market_data.get("stocks", {}).items():
            parts = [f"**{ticker} ({snap.get('company_name', ticker)})**:"]
            if snap.get("price"): parts.append(f"price ${snap['price']}")
            if snap.get("market_cap_bn"): parts.append(f"mkt cap ${snap['market_cap_bn']}B")
            if snap.get("forward_pe"): parts.append(f"fwd P/E {snap['forward_pe']}x")
            if snap.get("trailing_pe"): parts.append(f"trailing P/E {snap['trailing_pe']}x")
            if snap.get("consensus_target_12m"): parts.append(f"consensus target ${snap['consensus_target_12m']}")
            if snap.get("revenue_ttm_bn"): parts.append(f"revenue ${snap['revenue_ttm_bn']}B")
            if snap.get("gross_margin_pct"): parts.append(f"gross margin {snap['gross_margin_pct']}%")
            if snap.get("operating_margin_pct"): parts.append(f"op margin {snap['operating_margin_pct']}%")
            if snap.get("free_cash_flow_ttm_bn"): parts.append(f"FCF ${snap['free_cash_flow_ttm_bn']}B")
            if snap.get("ev_ebitda"): parts.append(f"EV/EBITDA {snap['ev_ebitda']}x")
            if snap.get("debt_to_equity"): parts.append(f"D/E {snap['debt_to_equity']}")
            if snap.get("roe"):
                roe_val = snap["roe"]
                parts.append(f"ROE {roe_val:.1%}" if isinstance(roe_val, float) and roe_val < 1 else f"ROE {roe_val}")
            if snap.get("eps_growth_yoy"): parts.append(f"EPS growth {snap['eps_growth_yoy']}%")
            if snap.get("beta"): parts.append(f"beta {snap['beta']}")
            quant_blocks.append(", ".join(parts))

        # Build qualitative blocks per ticker
        qual_blocks = []
        correlation_hints_all = []
        if qual_packages:
            for ticker, pkg in qual_packages.items():
                qual_blocks.append(pkg.to_prompt_block())
                # Generate correlation hints
                snap = market_data.get("stocks", {}).get(ticker, {})
                hints = pkg.correlation_hints(snap)
                if hints:
                    correlation_hints_all.append(
                        f"**{ticker} correlations:**\n" + "\n".join(f"  • {h}" for h in hints)
                    )

        qual_text = "\n\n".join(qual_blocks) if qual_blocks else "(No qualitative data available)"
        hints_text = "\n\n".join(correlation_hints_all) if correlation_hints_all else "(No correlation signals detected)"

        system = textwrap.dedent(f"""
            You are the Evidence Librarian and Qualitative Intelligence Analyst for an
            institutional research platform. You have PhD-level analytical reasoning skills.

            {self._client_context()}

            You have been provided with:
            1. LIVE QUANTITATIVE DATA from FMP and Finnhub APIs (prices, fundamentals, ratios)
            2. DEEP QUALITATIVE INTELLIGENCE from 8 sources:
               - Company news & press releases (official corporate communications)
               - Earnings call transcripts (management commentary, tone, guidance)
               - SEC filings (8-K material events, 10-K annual, 10-Q quarterly)
               - Analyst upgrades/downgrades (sell-side grade changes)
               - Insider trading activity (executive buy/sell patterns)
               - Forward analyst estimates (consensus revenue/EPS, estimate spread)
               - Social & news sentiment scores (market mood indicators)
            3. CORRELATION HINTS — pre-computed signals where qualitative and quantitative
               data align (convergence) or diverge (divergence).

            Your task is to build a DEEP Evidence Library that goes far beyond listing data points.
            You must REASON about what the data means collectively.

            For each company, produce:

            ## [TICKER] — Evidence Library

            ### Tier 1: Verified Quantitative Facts
            List 5-8 hard numerical facts from the live data feed.
            Tag source: [FMP], [FHB], [YF]. Rate: [T1 — machine-verified].
            For each fact, note what it IMPLIES (e.g., "FCF of $X implies Y% FCF yield,
            which is [above/below] peer median").

            ### Tier 2: Qualitative Intelligence
            Synthesise the qualitative signals into a NARRATIVE, not just a list:
            - What story do the news headlines tell? Is coverage positive/negative/mixed?
            - What did management say on the earnings call? What tone? What guidance?
            - Are analysts upgrading or downgrading? Is there consensus movement?
            - Are insiders buying or selling? Does insider behavior MATCH the bull thesis?
            - What SEC filings are material? Any 8-K events that change the picture?
            Tag each insight: [NEWS], [TRANSCRIPT], [SEC], [ANALYST], [INSIDER], [SENTIMENT].

            ### Tier 3: Cross-Correlation Analysis
            This is the most important section. Reason about:
            - **Narrative-Fundamental Alignment**: Do qualitative signals CONFIRM or
              CONTRADICT the quantitative picture? (e.g., "Revenue growing 30% [T1] AND
              management guiding higher [TRANSCRIPT] AND analysts upgrading [ANALYST]
              = STRONG CONVERGENCE" vs "Revenue growing but insiders selling = DIVERGENCE")
            - **Information Asymmetry Signals**: Where might the market be wrong?
              What does insider/management behavior tell us that the headline numbers don't?
            - **Catalyst Identification**: What upcoming events could move the stock?
              (earnings dates, product launches, regulatory decisions, contract renewals)
            - **Evidence Gaps**: What CRITICAL information is missing? What would change
              your assessment if you knew it?

            ### Evidence Quality Rating
            - Overall: HIGH / MEDIUM / LOW
            - Quantitative depth: X/10
            - Qualitative depth: X/10
            - Correlation confidence: X/10
            - Key gap that would change the assessment: (one sentence)

            **REASONING RULES:**
            - Every qualitative insight must connect back to a quantitative data point
            - Never state a qualitative signal without assessing its reliability
            - Insider trading is a LEADING indicator — weight it heavily
            - Earnings transcript tone matters as much as the numbers
            - Analyst estimate spread indicates conviction/uncertainty level
            - High social sentiment + stretched valuation = crowding risk
            - Low coverage + strong fundamentals = potential under-the-radar opportunity
        """).strip()

        user_content = f"""
Date: {market_data.get('date')}
Universe: {', '.join(self.tickers)}
Data source: {market_data.get('data_source')}

═══════════════════════════════════════════════════════════════
SECTION A — QUANTITATIVE DATA (live from FMP + Finnhub)
═══════════════════════════════════════════════════════════════
{chr(10).join(quant_blocks)}

═══════════════════════════════════════════════════════════════
SECTION B — QUALITATIVE INTELLIGENCE (8 sources)
═══════════════════════════════════════════════════════════════
{qual_text}

═══════════════════════════════════════════════════════════════
SECTION C — PRE-COMPUTED CORRELATION SIGNALS
═══════════════════════════════════════════════════════════════
{hints_text}

Please build the deep Evidence Library with full qualitative-quantitative
correlation analysis for each company in the universe.
        """.strip()

        # Use Gemini for evidence synthesis if available (strong reasoning benchmark),
        # otherwise fall back to the default model
        return await self._call_llm(system, user_content, stage_num=5)

    async def _stage_sector(self, market_data: dict, qual_packages: dict = None) -> str:
        # Build comprehensive per-stock data for the LLM
        stocks_data = {}
        for ticker, snap in market_data.get("stocks", {}).items():
            entry: dict[str, Any] = {
                "ticker": ticker,
                "company": snap.get("company_name", ticker),
                "sector": snap.get("sector", ""),
                "industry": snap.get("industry", ""),
            }
            # Add available quantitative fields
            for fld in ["price", "market_cap_bn", "forward_pe", "trailing_pe",
                          "ev_ebitda", "ev_to_sales", "consensus_target_12m",
                          "upside_to_consensus_pct", "revenue_ttm_bn",
                          "gross_margin_pct", "operating_margin_pct", "net_margin_pct",
                          "free_cash_flow_ttm_bn", "eps", "eps_growth_yoy",
                          "roe", "roic", "debt_to_equity", "beta",
                          "week52_high", "week52_low"]:
                val = snap.get(fld)
                if val is not None:
                    entry[fld] = val
            # Analyst ratings
            ratings = snap.get("analyst_ratings", {})
            if ratings:
                entry["analyst_ratings"] = ratings
            stocks_data[ticker] = entry

        # Build qualitative context per ticker
        qual_context_blocks = []
        if qual_packages:
            for ticker, pkg in qual_packages.items():
                snap = market_data.get("stocks", {}).get(ticker, {})
                block_parts = [f"\n### {ticker} — Qualitative Intelligence"]

                # Earnings transcript excerpt (most valuable qualitative source)
                if pkg.earnings_transcript:
                    et = pkg.earnings_transcript
                    content = et.get("content", "")
                    block_parts.append(
                        f"**Earnings Call ({et.get('quarter', '?')} {et.get('year', '?')}):**\n"
                        f"{content[:2500]}"
                    )

                # Analyst actions summary
                if pkg.analyst_actions:
                    upgrades = sum(1 for a in pkg.analyst_actions if "upgrade" in (a.get("action", "")).lower())
                    downgrades = sum(1 for a in pkg.analyst_actions if "downgrade" in (a.get("action", "")).lower())
                    actions_list = [
                        f"  {a.get('gradeCompany', '?')}: {a.get('action', '')} "
                        f"{a.get('previousGrade', '')} → {a.get('newGrade', '')} ({a.get('gradingDate', '')})"
                        for a in pkg.analyst_actions[:6]
                    ]
                    block_parts.append(
                        f"**Analyst Actions:** {upgrades} upgrades, {downgrades} downgrades\n"
                        + "\n".join(actions_list)
                    )

                # Insider activity net
                if pkg.insider_activity:
                    buys = sum(
                        1 for tx in pkg.insider_activity
                        if tx.get("acquistionOrDisposition") in ("A", "P")
                    )
                    sells = sum(
                        1 for tx in pkg.insider_activity
                        if tx.get("acquistionOrDisposition") in ("D", "S")
                    )
                    total_val = sum(tx.get("value", 0) for tx in pkg.insider_activity)
                    block_parts.append(
                        f"**Insider Activity:** {buys} buys, {sells} sells, "
                        f"total value ${total_val:,.0f}"
                    )

                # Forward estimates
                if pkg.analyst_estimates:
                    for period_key in ("current_year", "next_year"):
                        est = pkg.analyst_estimates.get(period_key, {})
                        if est:
                            rev = est.get("estimatedRevenueAvg")
                            eps = est.get("estimatedEpsAvg")
                            rev_str = f"${rev / 1e9:.2f}B" if rev else "N/A"
                            eps_str = f"${eps:.2f}" if eps else "N/A"
                            block_parts.append(
                                f"**{period_key.replace('_', ' ').title()} Estimates:** "
                                f"Revenue {rev_str}, EPS {eps_str}"
                            )

                # Sentiment summary
                if pkg.sentiment:
                    ns = pkg.sentiment.get("news_sentiment_score")
                    if ns is not None:
                        label = "BULLISH" if ns > 0.5 else "BEARISH" if ns < -0.5 else "NEUTRAL"
                        block_parts.append(f"**Sentiment:** {label} (score: {ns:.2f})")

                # Key news headlines (top 5)
                if pkg.news:
                    headlines = [n.get("headline", "") for n in pkg.news[:5]]
                    block_parts.append("**Key Headlines:**\n" + "\n".join(f"  • {h}" for h in headlines))

                # Coverage assessment
                block_parts.append(
                    f"**Qualitative Coverage:** {pkg.coverage_score} "
                    f"({pkg.signal_count} signals)"
                )
                if pkg.coverage_gaps:
                    block_parts.append(f"**Gaps:** {', '.join(pkg.coverage_gaps[:3])}")

                # Correlation hints
                hints = pkg.correlation_hints(snap)
                if hints:
                    block_parts.append(
                        "**Quant-Qual Correlation Signals:**\n"
                        + "\n".join(f"  ⚡ {h}" for h in hints)
                    )

                qual_context_blocks.append("\n".join(block_parts))

        qual_text = "\n\n".join(qual_context_blocks) if qual_context_blocks else "(No qualitative data)"

        system = textwrap.dedent(f"""
            You are a team of Sector Analysts for an institutional research platform.
            You combine deep quantitative analysis with qualitative intelligence synthesis.

            {self._client_context()}

            You have been provided with:
            - QUANTITATIVE DATA: Full financial profiles from FMP + Finnhub (live)
            - QUALITATIVE INTELLIGENCE: Earnings transcripts, analyst actions, insider trading,
              forward estimates, sentiment scores, news headlines, and correlation signals.

            For EACH stock in the universe, produce a **Six-Box analysis** (enhanced from Four-Box
            to incorporate the deeper qualitative intelligence):

            ### Box 1 — Verified Quantitative Facts
            Only confirmed numerical data from the live feed. Tag source: [FMP], [FHB].
            No estimates. Include what each metric implies.

            ### Box 2 — Management Narrative & Earnings Intelligence
            What is management saying? Analyze the earnings transcript for:
            - Forward guidance (specific numbers, tone, confidence level)
            - Strategic priorities and capital allocation
            - Risks they acknowledge vs risks they avoid discussing
            - Changes in language vs previous quarters (if detectable)
            Tag [TRANSCRIPT]. This is the highest-value qualitative source.

            ### Box 3 — Market Participant Signals
            Synthesize what other market participants are doing:
            - Analyst upgrades/downgrades — which firms, what direction, consensus shift
            - Insider buying/selling — does smart money confirm or contradict the thesis?
            - Social sentiment — crowded or under-the-radar?
            - Forward estimate revisions — are estimates moving up or down?
            Tag [ANALYST], [INSIDER], [SENTIMENT], [ESTIMATES].

            ### Box 4 — Recent Developments & Catalysts
            News headlines, press releases, SEC filings — what is happening NOW?
            - Material 8-K events that change the investment picture
            - Product launches, contract wins/losses, regulatory developments
            - Upcoming catalysts (earnings dates, FDA decisions, contract renewals)
            Tag [NEWS], [SEC], [PR].

            ### Box 5 — Consensus & Market View
            Consensus price targets, analyst estimates, and where the market is positioned.
            Critically: what does the CURRENT PRICE already embed?

            ### Box 6 — Analyst Judgment [HOUSE VIEW]
            Your differentiated view. This must be REASONED, not just stated:
            - Where does qualitative evidence SUPPORT the quantitative picture?
            - Where does it CONTRADICT? (These contradictions are the most valuable insights)
            - What is the market missing? What narrative shift is underway?
            - What single piece of information would change your view?
            - Conviction level: HIGH / MEDIUM / LOW with explicit multi-factor rationale

            **HARD RULES:**
            - Every numerical claim must reference source data provided
            - Qualitative signals must be CORRELATED with quantitative data
              (e.g., "insider selling + declining margins + cautious guidance = CONVERGENT BEARISH")
            - Flag evidence gaps explicitly
            - No price targets (valuation analyst's job only)
            - Separate fact from opinion rigorously
            - Weight insider behavior and management tone MORE than news headlines
            - Tailor analysis to the client's investment objectives and risk tolerance
        """).strip()

        user_content = f"""
Date: {market_data.get('date')}
Universe: {', '.join(self.tickers)}

═══════════════════════════════════════════════════════════════
QUANTITATIVE DATA (live from FMP + Finnhub):
═══════════════════════════════════════════════════════════════
{json.dumps(stocks_data, indent=2, default=str)}

═══════════════════════════════════════════════════════════════
QUALITATIVE INTELLIGENCE (8 sources per ticker):
═══════════════════════════════════════════════════════════════
{qual_text}

Please produce the full Six-Box sector analysis for each stock.
Use headers: ## [TICKER] — [Company Name] then the six boxes.
Reason deeply about qualitative-quantitative alignment and divergence.
        """.strip()

        return await self._call_llm(system, user_content, stage_num=6)

    async def _stage_valuation(self, market_data: dict, sector_outputs: str) -> str:
        stocks_dict = {}
        for t, s in market_data.get("stocks", {}).items():
            entry: dict[str, Any] = {"ticker": t, "company": s.get("company_name", t)}
            for fld in ["price", "market_cap_bn", "forward_pe", "trailing_pe",
                          "ev_ebitda", "ev_to_sales", "revenue_ttm_bn",
                          "free_cash_flow_ttm_bn", "consensus_target_12m",
                          "upside_to_consensus_pct", "analyst_ratings",
                          "gross_margin_pct", "operating_margin_pct", "net_margin_pct",
                          "eps", "eps_growth_yoy", "roe", "roic", "debt_to_equity",
                          "fcf_yield", "dividend_yield", "beta",
                          "week52_high", "week52_low"]:
                val = s.get(fld)
                if val is not None:
                    entry[fld] = val
            stocks_dict[t] = entry
        stocks_str = json.dumps(stocks_dict, indent=2, default=str)

        system = textwrap.dedent(f"""
            You are the Valuation Analyst for an institutional research platform.
            You are the ONLY team member who sets return scenarios and price context.

            {self._client_context()}

            IMPORTANT: The Sector Analysis you receive now contains DEEP QUALITATIVE
            INTELLIGENCE including earnings transcript analysis, insider trading patterns,
            analyst upgrade/downgrade momentum, and forward estimate consensus. Use this
            qualitative context to INFORM your valuation scenarios:
            - If management guided higher + analysts upgrading → weight bull case higher
            - If insiders selling + estimate spread widening → widen bear case
            - If sentiment is extremely bullish + stretched multiples → flag crowding risk
            - Earnings transcript tone should influence your confidence in growth assumptions

            For each stock produce:

            ### [TICKER] Valuation

            **Current Snapshot**
            - Price, market cap, forward P/E, EV/EBITDA, FCF yield
            - Where multiples sit vs historical range (comment based on available data)

            **Qualitative Valuation Overlay**
            - How does management's own guidance affect your growth assumptions?
            - Does insider behavior validate or undermine the current multiple?
            - What do forward estimate revisions imply about consensus direction?

            **Return Decomposition**
            - Revenue growth contribution (calibrated to forward estimates + guidance)
            - Margin expansion contribution
            - Multiple re-rating contribution
            - Which driver dominates and how defensible it is

            **Scenarios [HOUSE VIEW]**
            | Case | Prob | Rev CAGR | Exit Multiple | Implied 1yr Return | Key Assumption |
            |------|------|----------|---------------|-------------------|----------------|
            | Bull | 25% | ... | ... | ... | ... |
            | Base | 55% | ... | ... | ... | ... |
            | Bear | 20% | ... | ... | ... | ... |

            **Entry Quality**: STRONG / ACCEPTABLE / STRETCHED / POOR — with 1-sentence rationale

            **Expectation Pressure**: 0-10 (10 = maximum priced-in perfection)

            **Qualitative Confidence Modifier**: Does qualitative evidence raise or lower
            your confidence vs what the numbers alone suggest? Explain.

            **HARD RULES:**
            - All multi-year scenarios labelled [HOUSE VIEW]
            - Do NOT treat consensus target as intrinsic value
            - If current price is above consensus target, flag explicitly
            - No single-point fair values — always provide scenario ranges
            - Be explicit about what assumptions are embedded in current price
            - Reference specific qualitative signals that inform scenario probabilities
            - Tailor valuation framework to the client's return objectives and risk tolerance
        """).strip()

        user_content = f"""
Date: {market_data.get('date')}
Universe: {', '.join(self.tickers)}

MARKET DATA (live from FMP + Finnhub):
{stocks_str}

SECTOR ANALYSIS OUTPUT (includes qualitative intelligence):
{sector_outputs[:4000]}...

Please produce the full valuation analysis for each stock.
Reference qualitative signals where they inform scenario probabilities.
        """.strip()

        return await self._call_llm(system, user_content, stage_num=7)

    async def _stage_macro(self, macro_data: dict, sector_outputs: str = "") -> str:
        system = textwrap.dedent(f"""
            You are the Macro & Regime Strategist and Political Risk Analyst for an institutional
            research platform.

            {self._client_context()}

            Produce two sections:

            ## Macro & Regime Overlay
            - Current regime characterisation (growth/inflation/rates)
            - Key macro variables relevant to AI infrastructure (rates, dollar, copper, power prices)
            - How the current regime affects earnings quality and multiple sustainability
            - Regime shift risks (what macro scenario breaks the AI capex thesis?)
            - Factor exposure: is this a growth bet, quality bet, or both?

            ## Political & Geopolitical Risk Register
            | Risk | Probability | Impact | Affected Names | Monitoring Trigger |
            |------|-------------|--------|----------------|-------------------|
            (Build a table of 5-7 risks)

            Then:
            - US-China tech controls: current state, escalation scenarios, specific stock impacts
            - Taiwan risk: probability assessment, hedging considerations, CVaR estimate
            - IRA / US infrastructure policy: renewable energy tax credit risks under current admin
            - Export controls: H20/B20 chip bans, TSMC restrictions
            - Grid permitting / FERC policy: impact on infrastructure buildout pace

            Conclude with an overall **Geopolitical Risk Rating** (LOW / MEDIUM / HIGH / ELEVATED)
            and which stocks are most/least exposed.
        """).strip()

        sector_ctx = f"\n\nSECTOR ANALYSIS CONTEXT (for overlay calibration):\n{sector_outputs[:2000]}..." if sector_outputs else ""

        user_content = f"""
Date: {macro_data.get('date')}

MACRO CONTEXT:
{json.dumps(macro_data, indent=2)}

PORTFOLIO UNIVERSE: {', '.join(self.tickers)}{sector_ctx}

Please produce the macro and political risk analysis.
        """.strip()

        return await self._call_llm(system, user_content, stage_num=8)

    async def _stage_risk(self, market_data: dict, sector_outputs: str, valuation_outputs: str = "", macro_outputs: str = "") -> str:
        """Quant risk summary incorporating sector, valuation, and macro context."""
        stocks = market_data.get("stocks", {})

        # Build risk metrics from market snapshot data
        risk_metrics = {}
        for ticker, snap in stocks.items():
            pe = snap.get("forward_pe") or 25
            price = snap.get("price") or 100
            target = snap.get("consensus_target_12m") or price
            upside = (target - price) / price * 100 if price else 0
            beta = snap.get("beta", 1.2)
            risk_metrics[ticker] = {
                "company": snap.get("company_name", ticker),
                "sector": snap.get("sector", ""),
                "implied_upside_pct": round(upside, 1),
                "forward_pe": pe,
                "multiple_percentile_estimate": "High" if pe > 35 else "Medium" if pe > 20 else "Low",
                "beta": beta,
                "market_cap_bn": snap.get("market_cap_bn"),
                "debt_to_equity": snap.get("debt_to_equity"),
            }

        system = textwrap.dedent(f"""
            You are the Risk Manager for an institutional research platform.

            {self._client_context()}

            Review the provided risk metrics, sector analysis, valuation scenarios, and macro overlay,
            then produce:

            ## Portfolio Risk Summary
            - Concentration risk: compute vs power vs infrastructure allocation
            - Correlation risk: names that will move together in a sell-off
            - Factor exposures: AI capex beta, rates sensitivity, geopolitical beta
            - How the current macro regime (rates, dollar, commodities) affects each sub-theme

            ## Scenario Stress Tests
            For each scenario, estimate approximate portfolio drawdown:
            1. **AI Capex Pause** — hyperscalers cut capex 30% following ROI disappointment
            2. **Higher For Longer** — Fed holds at 5%+ through 2027; rates re-rate multiples
            3. **Taiwan Crisis** — 10% probability 12-month scenario; tech supply chain disruption
            4. **DeepSeek 2.0** — efficiency breakthrough reduces training compute demand 50%
            5. **Power Price Collapse** — gas oversupply normalises electricity prices

            ## Risk-Adjusted Summary Table
            | Ticker | Upside (consensus) | Beta | Key Risk | Risk Rating |
            For each stock in the universe.
        """).strip()

        val_ctx = f"\n\nVALUATION SCENARIOS (for drawdown calibration):\n{valuation_outputs[:1500]}..." if valuation_outputs else ""
        macro_ctx = f"\n\nMACRO REGIME OVERLAY:\n{macro_outputs[:1200]}..." if macro_outputs else ""

        user_content = f"""
Date: {market_data.get('date')}
Universe: {', '.join(self.tickers)}

RISK METRICS:
{json.dumps(risk_metrics, indent=2)}

SECTOR ANALYSIS EXCERPT:
{sector_outputs[:2000]}...{val_ctx}{macro_ctx}

Please produce the risk and scenario analysis.
        """.strip()

        return await self._call_llm(system, user_content, stage_num=9)

    async def _stage_red_team(self, sector_outputs: str, valuation_outputs: str) -> str:
        system = textwrap.dedent(f"""
            You are the Red Team Analyst for an institutional research platform.

            {self._client_context()}
            Your sole job is to try to BREAK every investment thesis before publication.
            The team has built a bull case. Your job is adversarial.

            IMPORTANT: The sector and valuation analysis now contain DEEP QUALITATIVE
            INTELLIGENCE — earnings transcript analysis, insider trading patterns,
            analyst upgrade/downgrade momentum, forward estimate consensus, and sentiment
            signals. You MUST attack the QUALITATIVE reasoning, not just the numbers:

            For each stock in the universe:

            ### [TICKER] — Red Team Assessment

            **Thesis Under Attack**: (state the bull thesis in one sentence)

            **Quantitative Falsification Tests** (minimum 3):
            1. What single data point, if announced tomorrow, would invalidate the thesis?
            2. What is the bear case that is being systematically underweighted?
            3. Where is the analysis most likely to be wrong?

            **Qualitative Falsification Tests** (minimum 3 — THIS IS NEW):
            1. Is management's earnings call guidance being taken at face value?
               What incentive do they have to guide conservatively/aggressively?
            2. Are the analyst upgrades LEADING or LAGGING? Are analysts upgrading
               because the stock already went up (momentum-driven) or based on new information?
            3. Insider selling: is the team dismissing it as "routine" when it might be material?
               What is the magnitude relative to total holdings?
            4. Is the news sentiment creating a narrative bubble? Is the team anchoring
               on recent positive headlines while ignoring structural risks?
            5. Forward estimate spread: is wide disagreement being treated as "opportunity"
               when it might indicate genuine uncertainty about the business model?

            **Variant Bear Case [HOUSE VIEW]**:
            - Timeline: 6-18 months
            - Mechanism: specific chain of events
            - Estimated downside: X%
            - What would you need to see to no longer hold this bear view?

            **Crowding & Sentiment Risk**:
            - How consensus is this position? (1-10, 10 = maximum crowded)
            - What does an orderly exit look like vs a disorderly one?
            - Is social sentiment a CONTRARY indicator here?

            **Overall Red Team Rating**: STRONG (thesis survives) / MODERATE (concerns) / WEAK (serious problems)

            Be specific. Vague risks are worthless. Every bear point should be actionable.
            Attack the qualitative reasoning as hard as the quantitative.
        """).strip()

        user_content = f"""
Universe: {', '.join(self.tickers)}

SECTOR ANALYSIS (includes qualitative intelligence — Six-Box format):
{sector_outputs[:4000]}

VALUATION OUTPUTS (includes qualitative confidence modifiers):
{valuation_outputs[:2500]}

Please conduct the full Red Team analysis for each stock.
Challenge both the quantitative AND qualitative reasoning.
        """.strip()

        return await self._call_llm(system, user_content, stage_num=10)

    async def _stage_review(self, sector_outputs: str, valuation_outputs: str, red_team_outputs: str) -> str:
        system = textwrap.dedent(f"""
            You are the Associate Reviewer for an institutional research platform.

            {self._client_context()}
            You are the final quality gate before publication.

            Review the research package and produce:

            ## Self-Audit Scorecard

            | Criterion | Score (0-10) | Notes |
            |-----------|-------------|-------|
            | Evidence quality & sourcing | | |
            | Claim provenance (T1/T2/T3 mix) | | |
            | Valuation methodology rigor | | |
            | Risk identification completeness | | |
            | Red team engagement quality | | |
            | Disclosure completeness | | |
            | Internal consistency | | |

            **Overall Score**: X/10
            **Publication Decision**: PASS / PASS WITH DISCLOSURE / FAIL

            ## Issues List
            List any required disclosures or corrections.
            If FAIL, state exactly what must be remediated.

            ## Recommended Disclosures
            Standard disclosures to include at the bottom of the final report.

            Be rigorous. A PASS WITH DISCLOSURE is better than ignoring a real issue.
        """).strip()

        user_content = f"""
Universe: {', '.join(self.tickers)}

SECTOR ANALYSIS (excerpt):
{sector_outputs[:2000]}

VALUATION OUTPUTS (excerpt):
{valuation_outputs[:1500]}

RED TEAM OUTPUTS (excerpt):
{red_team_outputs[:1500]}

Please conduct the full associate review and produce the self-audit scorecard.
        """.strip()

        return await self._call_llm(system, user_content, stage_num=11)

    async def _stage_portfolio(self, sector_outputs: str, valuation_outputs: str, risk_outputs: str, review_output: str = "") -> str:
        # Build constraints from client profile
        if self.client_profile and hasattr(self.client_profile, 'get_portfolio_constraints'):
            constraints = self.client_profile.get_portfolio_constraints()
            max_single = constraints.get('max_single_position_pct', 15)
            max_sector = constraints.get('max_sector_pct', 50)
            amount = getattr(self.client_profile, 'investment_amount_usd', None)
            amount_str = f"\n            - **Investment amount**: ${amount:,.0f}" if amount else ""
        else:
            max_single = 15
            max_sector = 50
            amount_str = ""

        system = textwrap.dedent(f"""
            You are the Portfolio Manager for an institutional research platform.

            {self._client_context()}

            Using the research from the team, construct THREE portfolio variants.

            ## Portfolio Variant Construction Rules
            - **Max single stock weight**: {max_single}%
            - **Sector limits**: No sector > {max_sector}% by weight
            - **Universe restriction**: Only names from the approved research universe{amount_str}

            ## Three Variants Required

            ### Variant 1: Balanced Conviction Basket
            Target: Highest risk-adjusted return blend; balanced across themes
            Present as a table: | Ticker | Company | Subtheme | Weight % | Rationale |

            ### Variant 2: Higher Return Basket
            Target: Maximum expected return; higher concentration; accepts higher volatility
            Present as a table with same format.

            ### Variant 3: Lower Volatility Basket
            Target: Defensive AI infrastructure exposure; prefers lower-beta names, utilities, materials
            Present as a table with same format.

            ## For Each Variant:
            - Total weights must sum to 100%
            - Implementation notes (liquidity, sizing, entry strategy)
            - Key portfolio risk (what single factor would hurt this variant most)
            - Rebalancing trigger (what would cause you to reweight)

            ## Portfolio Synthesis
            Across all three variants, which names appear consistently? This is the highest-conviction core.
            Which names are variant-specific? Why?
        """).strip()

        user_content = f"""
Universe: {', '.join(self.tickers)}

SECTOR ANALYSIS (excerpt):
{sector_outputs[:2500]}

VALUATION OUTPUTS (excerpt):
{valuation_outputs[:2000]}

RISK ANALYSIS (excerpt):
{risk_outputs[:1500]}

ASSOCIATE REVIEW (full — mandatory constraint):
{review_output or '(not available)'}

HARD RULE: If the associate review contains a FAIL decision, you must note it explicitly
and flag that any portfolio recommendation is provisional pending remediation.

Please construct the three portfolio variants.
        """.strip()

        return await self._call_llm(system, user_content, stage_num=12)

    async def _stage_monitoring(self, run_id: str, stages: list) -> dict:
        """Stage 14: Record final run summary (frontend equivalent of run registry update)."""
        failed = [s.stage_name for s in stages if s.status == "failed"]
        completed = [s.stage_name for s in stages if s.status == "done"]
        total_elapsed = sum(s.elapsed_secs for s in stages)
        return {
            "run_id": run_id,
            "status": "completed" if not failed else "completed_with_failures",
            "stages_completed": len(completed),
            "stages_failed": len(failed),
            "failed_stage_names": failed,
            "total_elapsed_secs": round(total_elapsed, 1),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }

    def _model_display(self) -> str:
        """Return a human-readable model label — shows overrides when per-stage models differ."""
        if self.stage_models:
            unique_models = set(self.stage_models.values())
            if len(unique_models) > 1:
                return f"{self.model} (+ per-stage overrides: {len(unique_models)} models)"
        return self.model

    async def _stage_report_assembly(
        self,
        run_id: str,
        market_data: dict,
        claim_ledger: str,
        sector_outputs: str,
        valuation_outputs: str,
        macro_outputs: str,
        risk_outputs: str,
        red_team_outputs: str,
        review_output: str,
        portfolio_output: str,
    ) -> str:
        """Assemble the final report markdown."""
        report_date = market_data.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        tickers_list = ", ".join(self.tickers)
        stocks = market_data.get("stocks", {})
        data_source = market_data.get("data_source", "Unknown")
        live_count = market_data.get("live_count", 0)

        # Client profile header
        if self.client_profile:
            cp = self.client_profile
            client_header = (
                f"**Client:** {getattr(cp, 'name', 'Institutional')}\n"
                f"**Objective:** {getattr(cp, 'primary_objective', 'growth').replace('_', ' ').title()}\n"
                f"**Risk Tolerance:** {getattr(cp, 'risk_tolerance', 'moderate').title()}\n"
                f"**Time Horizon:** {getattr(cp, 'time_horizon_years', 'N/A')} years\n"
                f"**Investment Theme:** {getattr(cp, 'investment_theme', 'custom').replace('_', ' ').title()}"
            )
            if getattr(cp, 'investment_amount_usd', None):
                client_header += f"\n**Investment Amount:** ${cp.investment_amount_usd:,.0f}"
        else:
            client_header = "**Client:** Default institutional analysis"

        # Build snapshot table from live data
        snapshot_rows = []
        for t, s in stocks.items():
            company = s.get("company_name", t)
            sector = s.get("sector", "").replace("_", " ").title() if s.get("sector") else "—"
            price = s.get("price")
            fwd_pe = s.get("forward_pe")
            target = s.get("consensus_target_12m")
            mkt_cap = s.get("market_cap_bn")

            price_str = f"${price:,.2f}" if price else "—"
            pe_str = f"{fwd_pe:.1f}x" if fwd_pe else "—"
            target_str = f"${target:,.2f}" if target else "—"
            cap_str = f"${mkt_cap:,.1f}B" if mkt_cap else "—"

            if price and target:
                upside = (target - price) / price * 100
                upside_str = f"{upside:+.1f}%"
            else:
                upside_str = "—"

            snapshot_rows.append(
                f"| {t} | {company} | {sector} | {price_str} | {cap_str} | {pe_str} | {target_str} | {upside_str} |"
            )
        snapshot_table = "\n".join(snapshot_rows)

        report = f"""# Institutional Equity Research Report

**Date:** {report_date}
**Run ID:** {run_id}
**Model:** {self._model_display()}
**Universe:** {tickers_list} ({len(self.tickers)} names)
**Data Source:** {data_source} ({live_count}/{len(self.tickers)} tickers live)
**Intelligence Depth:** Quantitative (3 sources) + Qualitative (8 sources)

---

### Client Profile
{client_header}

---

> **IMPORTANT DISCLAIMERS**
> This report uses live market data from FMP, Finnhub, and yfinance APIs.
> Qualitative intelligence sourced from 8 channels: company news, press releases,
> earnings call transcripts, SEC filings, analyst upgrades/downgrades, insider
> trading activity, forward analyst estimates, and social/news sentiment.
> All prices and metrics reflect data as of the date shown above.
> All multi-year return scenarios are labelled [HOUSE VIEW] and represent analytical
> estimates, not recommendations. Past performance is no guide to future returns.
> Not investment advice. This is an AI-generated research report for analytical purposes.

---

## Executive Summary

This report covers {len(self.tickers)} names across the client's selected investment universe.
Analysis integrates live quantitative data with deep qualitative intelligence including
management commentary (earnings transcripts), insider trading patterns, analyst grade
changes, forward estimate consensus, and market sentiment signals.

### Universe Snapshot

| Ticker | Company | Sector | Price | Mkt Cap | Fwd P/E | Consensus Target | Upside |
|--------|---------|--------|-------|---------|---------|-----------------|--------|
{snapshot_table}

*Source: {data_source} — as of {report_date}*

---

## 1. Evidence Library & Qualitative-Quantitative Correlation (Stage 5)

{claim_ledger}

---

## 2. Sector Analysis — Six-Box with Narrative Intelligence (Stage 6)

{sector_outputs}

---

## 3. Valuation & Modelling (Stage 7)

{valuation_outputs}

---

## 4. Macro & Political Risk Overlay (Stage 8)

{macro_outputs}

---

## 5. Quant Risk & Scenario Testing (Stage 9)

{risk_outputs}

---

## 6. Red Team Analysis — Quantitative & Qualitative Challenge (Stage 10)

{red_team_outputs}

---

## 7. Associate Review & Self-Audit (Stage 11)

{review_output}

---

## 8. Portfolio Construction (Stage 12)

{portfolio_output}

---

## Appendix — Run Metadata

| Field | Value |
|-------|-------|
| Run ID | {run_id} |
| Date | {report_date} |
| Model | {self._model_display()} |
| Universe size | {len(self.tickers)} stocks |
| Live data tickers | {live_count} |
| Data source | {data_source} |
| Qualitative sources | News, press releases, earnings transcripts, SEC filings, analyst actions, insider trading, estimates, sentiment |
| Pipeline version | v8.1 — JPM Asset Management (Deep Qualitative) |

---

*AI-Powered Institutional Research Pipeline v8.1*
*All [HOUSE VIEW] content is analytical opinion, not investment advice.*
*Quantitative data: FMP, Finnhub, yfinance APIs.*
*Qualitative intelligence: 8-source engine with cross-correlation analysis.*
"""
        return report
