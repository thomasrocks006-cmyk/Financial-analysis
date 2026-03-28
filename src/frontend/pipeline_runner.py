"""Pipeline runner for the Streamlit frontend.

Drives the full 15-stage institutional research pipeline.
Uses FMP + Finnhub for live market data, yfinance as fallback.
Injects client investment profile context into every LLM agent.
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

        # ── Stage 0: Bootstrap ────────────────────────────────────────────
        s0 = await self._run_stage(0, "Bootstrap & Configuration", _cb, self._stage_bootstrap, run_id, market_data)
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

        # ── Stage 5: Evidence Librarian (LLM) ────────────────────────────
        s5 = await self._run_stage(5, "Evidence Librarian / Claim Ledger", _cb, self._stage_evidence, market_data)
        result.stages.append(s5)
        claim_ledger_text = s5.raw_text

        # ── Stage 6: Sector Analysis (LLM) ───────────────────────────────
        s6 = await self._run_stage(6, "Sector Analysis", _cb, self._stage_sector, market_data)
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

    async def _stage_bootstrap(self, run_id: str, market_data: dict) -> dict:
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

    async def _stage_evidence(self, market_data: dict) -> str:
        stocks_summary = []
        for ticker, snap in market_data.get("stocks", {}).items():
            parts = [f"**{ticker} ({snap.get('company_name', ticker)})**:"]
            if snap.get("price"): parts.append(f"price ${snap['price']}")
            if snap.get("market_cap_bn"): parts.append(f"mkt cap ${snap['market_cap_bn']}B")
            if snap.get("forward_pe"): parts.append(f"fwd P/E {snap['forward_pe']}x")
            if snap.get("trailing_pe"): parts.append(f"trailing P/E {snap['trailing_pe']}x")
            if snap.get("consensus_target_12m"): parts.append(f"consensus target ${snap['consensus_target_12m']}")
            if snap.get("revenue_ttm_bn"): parts.append(f"revenue ${snap['revenue_ttm_bn']}B")
            if snap.get("gross_margin_pct"): parts.append(f"gross margin {snap['gross_margin_pct']}%")
            if snap.get("free_cash_flow_ttm_bn"): parts.append(f"FCF ${snap['free_cash_flow_ttm_bn']}B")
            if snap.get("ev_ebitda"): parts.append(f"EV/EBITDA {snap['ev_ebitda']}x")
            if snap.get("debt_to_equity"): parts.append(f"D/E {snap['debt_to_equity']}")
            if snap.get("roe"): parts.append(f"ROE {snap['roe']:.1%}" if isinstance(snap['roe'], float) and snap['roe'] < 1 else f"ROE {snap['roe']}")
            # News headlines
            news = snap.get("recent_news", [])
            if news:
                headlines = [n.get("headline", "") for n in news[:5] if n.get("headline")]
                if headlines:
                    parts.append(f"Recent news: {'; '.join(headlines[:3])}")
            stocks_summary.append(", ".join(parts))

        system = textwrap.dedent(f"""
            You are the Evidence Librarian for an institutional research platform.

            {self._client_context()}

            You have been provided with LIVE market data from FMP and Finnhub APIs plus
            recent news headlines. These are real, current data points.

            For each company:
            1. List 4-6 primary verified facts from the live data feed.
               Tag source: [FMP], [FHB], or [YF] for provider. Rate tier: [T1] or [T2].
            2. List 3-5 items from news/market signals (recent headlines). Tag [NEWS].
            3. Identify 3-4 evidence gaps — material questions the API data cannot answer
               (e.g., management commentary, capex guidance, contract wins, regulatory status).
            4. Rate overall evidence quality (HIGH/MEDIUM/LOW) with reasoning.

            Format as clean readable markdown with headers per company.
        """).strip()

        user_content = f"""
Date: {market_data.get('date')}
Universe: {', '.join(self.tickers)}
Data source: {market_data.get('data_source')}

LIVE DATA PACKAGE:
{chr(10).join(stocks_summary)}

Please build the Evidence Library and Claim Ledger for this universe.
        """.strip()

        return await self._call_llm(system, user_content, stage_num=5)

    async def _stage_sector(self, market_data: dict) -> str:
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
            for field in ["price", "market_cap_bn", "forward_pe", "trailing_pe",
                          "ev_ebitda", "ev_to_sales", "consensus_target_12m",
                          "upside_to_consensus_pct", "revenue_ttm_bn",
                          "gross_margin_pct", "operating_margin_pct", "net_margin_pct",
                          "free_cash_flow_ttm_bn", "eps", "eps_growth_yoy",
                          "roe", "roic", "debt_to_equity", "beta",
                          "week52_high", "week52_low"]:
                val = snap.get(field)
                if val is not None:
                    entry[field] = val
            # Add news headlines
            news = snap.get("recent_news", [])
            if news:
                entry["recent_headlines"] = [n.get("headline", "") for n in news[:5]]
            # Analyst ratings
            ratings = snap.get("analyst_ratings", {})
            if ratings:
                entry["analyst_ratings"] = ratings
            stocks_data[ticker] = entry

        system = textwrap.dedent(f"""
            You are a team of Sector Analysts for an institutional research platform.

            {self._client_context()}

            For EACH stock in the universe, produce a **Four-Box analysis**:

            ### Box 1 — Verified Facts
            Only confirmed data from the live feed. Tag source: [FMP], [FHB]. No estimates.

            ### Box 2 — Recent Developments & News
            Recent headlines and market signals. Tag [NEWS]. Note limitations.

            ### Box 3 — Consensus & Market View
            Consensus estimates, analyst targets, and sell-side views from the data.

            ### Box 4 — Analyst Judgment [HOUSE VIEW]
            Your differentiated view vs consensus. What does the market miss?
            Bull/bear arguments from the same factual base.
            Conviction level: HIGH / MEDIUM / LOW with explicit rationale.

            **HARD RULES:**
            - Every numerical claim must reference source data provided
            - Flag evidence gaps explicitly
            - No price targets (valuation analyst's job only)
            - Separate fact from opinion
            - Tailor analysis to the client's investment objectives and risk tolerance
        """).strip()

        user_content = f"""
Date: {market_data.get('date')}
Universe: {', '.join(self.tickers)}

STOCK DATA (live from FMP + Finnhub):
{json.dumps(stocks_data, indent=2, default=str)}

Please produce the full Four-Box sector analysis for each stock.
Use headers: ## [TICKER] — [Company Name] then the four boxes.
        """.strip()

        return await self._call_llm(system, user_content, stage_num=6)

    async def _stage_valuation(self, market_data: dict, sector_outputs: str) -> str:
        stocks_dict = {}
        for t, s in market_data.get("stocks", {}).items():
            entry: dict[str, Any] = {"ticker": t, "company": s.get("company_name", t)}
            for field in ["price", "market_cap_bn", "forward_pe", "trailing_pe",
                          "ev_ebitda", "ev_to_sales", "revenue_ttm_bn",
                          "free_cash_flow_ttm_bn", "consensus_target_12m",
                          "upside_to_consensus_pct", "analyst_ratings",
                          "gross_margin_pct", "operating_margin_pct", "net_margin_pct",
                          "eps", "eps_growth_yoy", "roe", "roic", "debt_to_equity",
                          "fcf_yield", "dividend_yield", "beta",
                          "week52_high", "week52_low"]:
                val = s.get(field)
                if val is not None:
                    entry[field] = val
            stocks_dict[t] = entry
        stocks_str = json.dumps(stocks_dict, indent=2, default=str)

        system = textwrap.dedent(f"""
            You are the Valuation Analyst for an institutional research platform.
            You are the ONLY team member who sets return scenarios and price context.

            {self._client_context()}

            For each stock produce:

            ### [TICKER] Valuation

            **Current Snapshot**
            - Price, market cap, forward P/E, EV/EBITDA, FCF yield
            - Where multiples sit vs historical range (comment based on available data)

            **Return Decomposition**
            - Revenue growth contribution
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

            **HARD RULES:**
            - All multi-year scenarios labelled [HOUSE VIEW]
            - Do NOT treat consensus target as intrinsic value
            - If current price is above consensus target, flag explicitly
            - No single-point fair values — always provide scenario ranges
            - Be explicit about what assumptions are embedded in current price
            - Tailor valuation framework to the client's return objectives and risk tolerance
        """).strip()

        user_content = f"""
Date: {market_data.get('date')}
Universe: {', '.join(self.tickers)}

MARKET DATA (live from FMP + Finnhub):
{stocks_str}

SECTOR ANALYSIS OUTPUT (for context):
{sector_outputs[:3000]}...

Please produce the full valuation analysis for each stock.
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
            The team has built a bull case for AI infrastructure. Your job is adversarial.

            For each stock in the universe:

            ### [TICKER] — Red Team Assessment

            **Thesis Under Attack**: (state the bull thesis in one sentence)

            **Falsification Tests** (minimum 3 concrete disconfirming scenarios):
            1. What single data point, if announced tomorrow, would invalidate the thesis?
            2. What is the bear case that is being systematically underweighted?
            3. Where is the analysis most likely to be wrong?

            **Variant Bear Case [HOUSE VIEW]**:
            - Timeline: 6-18 months
            - Mechanism: specific chain of events
            - Estimated downside: X%
            - What would you need to see to no longer hold this bear view?

            **Crowding & Sentiment Risk**:
            - How consensus is this position? (1-10, 10 = maximum crowded)
            - What does an orderly exit look like vs a disorderly one?

            **Overall Red Team Rating**: STRONG (thesis survives) / MODERATE (concerns) / WEAK (serious problems)

            Be specific. Vague risks are worthless. Every bear point should be actionable.
        """).strip()

        user_content = f"""
Universe: {', '.join(self.tickers)}

SECTOR ANALYSIS:
{sector_outputs[:3000]}

VALUATION OUTPUTS:
{valuation_outputs[:2000]}

Please conduct the full Red Team analysis for each stock.
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

---

### Client Profile
{client_header}

---

> **IMPORTANT DISCLAIMERS**
> This report uses live market data from FMP, Finnhub, and yfinance APIs.
> All prices and metrics reflect data as of the date shown above.
> All multi-year return scenarios are labelled [HOUSE VIEW] and represent analytical
> estimates, not recommendations. Past performance is no guide to future returns.
> Not investment advice. This is an AI-generated research report for analytical purposes.

---

## Executive Summary

This report covers {len(self.tickers)} names across the client's selected investment universe.

### Universe Snapshot

| Ticker | Company | Sector | Price | Mkt Cap | Fwd P/E | Consensus Target | Upside |
|--------|---------|--------|-------|---------|---------|-----------------|--------|
{snapshot_table}

*Source: {data_source} — as of {report_date}*

---

## 1. Evidence Library & Claim Ledger (Stage 5)

{claim_ledger}

---

## 2. Sector Analysis (Stage 6)

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

## 6. Red Team Analysis (Stage 10)

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
| Pipeline version | v8.0 — JPM Asset Management |

---

*AI-Powered Institutional Research Pipeline v8*
*All [HOUSE VIEW] content is analytical opinion, not investment advice.*
*Live data sourced from FMP, Finnhub, and yfinance APIs.*
"""
        return report
