"""Pipeline runner for the Streamlit frontend.

Drives all 14 stages using demo or live data and the LLM agents.
Designed to be called from the Streamlit app with progress callbacks.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import textwrap
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


ProgressCallback = Callable[[int, str, str, dict], None]


class PipelineRunner:
    """Orchestrates the full research pipeline for the Streamlit frontend."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-opus-4-6",
        tickers: Optional[list[str]] = None,
        temperature: float = 0.3,
    ):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.tickers = tickers or ["NVDA", "CEG", "PWR"]

        # Inject API key into environment for agents
        os.environ["ANTHROPIC_API_KEY"] = api_key

    async def run(
        self,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> RunResult:
        """Execute the full pipeline and return a RunResult."""
        run_id = f"DEMO-{uuid.uuid4().hex[:8].upper()}"
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

        # ── Load demo market data ─────────────────────────────────────────
        from frontend.mock_data import (
            get_sector_snapshot, get_macro_context, get_claim_ledger
        )
        market_data = get_sector_snapshot("all", self.tickers)
        macro_data = get_macro_context()
        claims = get_claim_ledger(self.tickers)

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
        s5 = await self._run_stage(5, "Evidence Librarian / Claim Ledger", _cb, self._stage_evidence, market_data, claims)
        result.stages.append(s5)
        claim_ledger_text = s5.raw_text

        # ── Stage 6: Sector Analysis (LLM) ───────────────────────────────
        s6 = await self._run_stage(6, "Sector Analysis", _cb, self._stage_sector, market_data, claims)
        result.stages.append(s6)
        sector_outputs = s6.raw_text

        # ── Stage 7: Valuation (LLM) ─────────────────────────────────────
        s7 = await self._run_stage(7, "Valuation & Modelling", _cb, self._stage_valuation, market_data, sector_outputs)
        result.stages.append(s7)
        valuation_outputs = s7.raw_text

        # ── Stage 8: Macro & Political (LLM) ─────────────────────────────
        s8 = await self._run_stage(8, "Macro & Political Overlay", _cb, self._stage_macro, macro_data)
        result.stages.append(s8)
        macro_outputs = s8.raw_text

        # ── Stage 9: Risk (deterministic) ────────────────────────────────
        s9 = await self._run_stage(9, "Quant Risk & Scenario Testing", _cb, self._stage_risk, market_data, sector_outputs)
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
        s12 = await self._run_stage(12, "Portfolio Construction", _cb, self._stage_portfolio, sector_outputs, valuation_outputs, risk_outputs)
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
        result.completed_at = datetime.now(timezone.utc).isoformat()
        result.success = all(s.status != "failed" for s in result.stages)

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
        t_start = asyncio.get_event_loop().time()
        try:
            result = await fn(*args)
            sr.raw_text = result if isinstance(result, str) else json.dumps(result, indent=2, default=str)
            sr.output = result if isinstance(result, dict) else {}
            sr.status = "done"
        except Exception as exc:
            logger.error("Stage %d failed: %s", stage_num, exc)
            sr.status = "failed"
            sr.error = str(exc)
        sr.elapsed_secs = asyncio.get_event_loop().time() - t_start
        cb(stage_num, stage_name, sr.status, sr.output)
        return sr

    # ── LLM helpers ──────────────────────────────────────────────────────
    def _detect_provider(self) -> str:
        """Detect provider from model name prefix."""
        m = self.model.lower()
        if m.startswith("claude"):
            return "anthropic"
        if m.startswith("gpt") or m.startswith("o1") or m.startswith("o3"):
            return "openai"
        if m.startswith("gemini"):
            return "gemini"
        return "anthropic"

    async def _call_llm(self, system_prompt: str, user_content: str) -> str:
        """Route to the correct LLM provider based on model name."""
        provider = self._detect_provider()
        if provider == "openai":
            return await self._call_openai(system_prompt, user_content)
        if provider == "gemini":
            return await self._call_gemini(system_prompt, user_content)
        return await self._call_anthropic(system_prompt, user_content)

    async def _call_anthropic(self, system_prompt: str, user_content: str) -> str:
        """Call Claude via the anthropic SDK."""
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=self.api_key)
        response = await client.messages.create(
            model=self.model,
            max_tokens=8192,
            temperature=self.temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        return response.content[0].text

    async def _call_openai(self, system_prompt: str, user_content: str) -> str:
        """Call GPT via the openai SDK."""
        import openai
        client = openai.AsyncOpenAI(api_key=self.api_key)
        response = await client.chat.completions.create(
            model=self.model,
            max_tokens=8192,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
        return response.choices[0].message.content

    async def _call_gemini(self, system_prompt: str, user_content: str) -> str:
        """Call Gemini via the google-genai SDK."""
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=self.api_key)
        response = await client.aio.models.generate_content(
            model=self.model,
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=8192,
                temperature=self.temperature,
            ),
        )
        return response.text

    # ── Individual stage implementations ─────────────────────────────────

    async def _stage_bootstrap(self, run_id: str, market_data: dict) -> dict:
        return {
            "run_id": run_id,
            "model": self.model,
            "tickers": self.tickers,
            "data_source": "Demo mode — illustrative data",
            "config_valid": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _stage_universe(self, tickers: list[str]) -> dict:
        from frontend.mock_data import MARKET_SNAPSHOTS, FULL_UNIVERSE
        universe = []
        for ticker in tickers:
            snap = MARKET_SNAPSHOTS.get(ticker, {})
            universe.append({
                "ticker": ticker,
                "company": snap.get("company_name", ticker),
                "subtheme": snap.get("subtheme", "unknown"),
                "approved": True,
            })
        return {"universe": universe, "total": len(universe)}

    async def _stage_data_ingestion(self, market_data: dict) -> dict:
        return {
            "status": "complete",
            "tickers_loaded": len(market_data.get("stocks", {})),
            "data_source": market_data.get("data_source"),
            "date": market_data.get("date"),
            "note": "Demo mode: using illustrative market snapshots (not live FMP/Finnhub data)",
        }

    async def _stage_reconciliation(self, market_data: dict) -> dict:
        results = {}
        for ticker, snap in market_data.get("stocks", {}).items():
            results[ticker] = {
                "price": snap.get("price"),
                "forward_pe": snap.get("forward_pe"),
                "reconciliation_status": "GREEN",
                "notes": "Single source (demo) — no cross-source reconciliation needed",
            }
        return {"reconciliation": results, "red_fields": 0, "amber_fields": 0, "green_fields": len(results)}

    async def _stage_qa(self, market_data: dict) -> dict:
        return {
            "schema_valid": True,
            "timestamps_valid": True,
            "duplicates_found": 0,
            "lineage_complete": True,
            "data_quality_score": 7.5,
            "notes": "Demo data: no lineage chain — treating as Tier 3. Live mode would require FMP/Finnhub source tags.",
        }

    async def _stage_evidence(self, market_data: dict, claims: list[dict]) -> str:
        stocks_summary = []
        for ticker, snap in market_data.get("stocks", {}).items():
            stocks_summary.append(
                f"**{ticker} ({snap['company_name']})**: price ${snap['price']}, "
                f"mkt cap ${snap['market_cap_bn']}B, fwd P/E {snap['forward_pe']}x, "
                f"consensus target ${snap['consensus_target_12m']}. "
                f"Recent catalysts: {'; '.join(snap.get('recent_catalysts', [])[:3])}"
            )

        system = textwrap.dedent("""
            You are the Evidence Librarian for an institutional AI infrastructure research platform.
            Your role is to review incoming market data and build a structured claim ledger.
            For each company:
            1. List 4-6 primary verified facts (Tier 1/2: earnings reported, filed guidance, exchange data)
            2. List 3-5 management guidance items (Tier 2: stated on earnings calls, investor days)
            3. Identify 2-3 evidence gaps (data not yet confirmed from primary sources)
            4. Rate overall evidence quality (HIGH/MEDIUM/LOW) with reasoning

            Format as clean, readable markdown with headers per company.
            Be precise — flag anything that could be sell-side estimate vs hard data.
            Use [T1], [T2], [T3] tags for evidence tiers.
        """).strip()

        user_content = f"""
Date: {market_data.get('date')}
Universe: {', '.join(self.tickers)}
Data source note: {market_data.get('data_source')}

MARKET DATA PACKAGE:
{chr(10).join(stocks_summary)}

PRELIMINARY CLAIMS FROM DATA SYSTEM ({len(claims)} claims):
{json.dumps(claims[:15], indent=2)}

Please build the Evidence Library and Claim Ledger for this universe.
        """.strip()

        return await self._call_llm(system, user_content)

    async def _stage_sector(self, market_data: dict, claims: list[dict]) -> str:
        stocks_by_sector: dict[str, list] = {"compute": [], "power_energy": [], "infrastructure": []}
        for ticker, snap in market_data.get("stocks", {}).items():
            sector = snap.get("subtheme", "infrastructure")
            stocks_by_sector.get(sector, stocks_by_sector["infrastructure"]).append(snap)

        system = textwrap.dedent("""
            You are a team of three Sector Analysts for an institutional AI infrastructure research platform:
            — **Compute & Silicon Analyst** covers NVDA, AVGO, TSM and semiconductor/foundry names
            — **Power & Energy Analyst** covers CEG, VST, GEV and utility/generation names
            — **Infrastructure Analyst** covers PWR, ETN, APH, FIX, FCX, NXT and materials/construction names

            For EACH stock in the universe, produce a **Four-Box analysis**:

            ### Box 1 — Verified Facts
            Only Tier 1/2 confirmed data. Tag each claim [T1] or [T2]. No guidance or estimates here.

            ### Box 2 — Management Guidance
            Forward-looking statements from management. Tag [GUIDANCE] with source/date. Be explicit about limitations.

            ### Box 3 — Consensus & Market View
            Tier 3 consensus estimates and sell-side views. State data limitations clearly.

            ### Box 4 — Analyst Judgment [HOUSE VIEW]
            Your differentiated view vs consensus. What does the market miss? What's priced in?
            Bull/bear arguments from the same factual base.
            Conviction level: HIGH / MEDIUM / LOW with explicit rationale.

            **HARD RULES:**
            - Every numerical claim must reference source data provided
            - Flag evidence gaps explicitly
            - No price targets (valuation analyst's job only)
            - Separate what is fact from what is your view
            - Consider AI efficiency shock (DeepSeek-style) as a mandatory bear scenario
        """).strip()

        sector_data_str = json.dumps(
            {s: [{"ticker": x["ticker"], "company": x["company_name"],
                  "price": x["price"], "fwd_pe": x["forward_pe"],
                  "catalysts": x["recent_catalysts"], "risks": x["key_risks"],
                  "consensus_target": x["consensus_target_12m"]}
                 for x in stocks]
             for s, stocks in stocks_by_sector.items()},
            indent=2
        )

        user_content = f"""
Date: {market_data.get('date')}
Universe: {', '.join(self.tickers)}

SECTOR DATA:
{sector_data_str}

CLAIM LEDGER SAMPLE:
{json.dumps(claims[:10], indent=2)}

Please produce the full Four-Box sector analysis for each stock.
Use headers: ## [TICKER] — [Company Name] then the four boxes.
        """.strip()

        return await self._call_llm(system, user_content)

    async def _stage_valuation(self, market_data: dict, sector_outputs: str) -> str:
        stocks_str = json.dumps(
            {t: {
                "price": s["price"],
                "mkt_cap_bn": s["market_cap_bn"],
                "forward_pe": s["forward_pe"],
                "ev_ebitda": s["ev_ebitda"],
                "rev_next_yr_bn": s["revenue_next_yr_consensus_bn"],
                "rev_ttm_bn": s["revenue_ttm_bn"],
                "fcf_ttm_bn": s["free_cash_flow_ttm_bn"],
                "consensus_target": s["consensus_target_12m"],
                "ratings": s["analyst_ratings"],
                "gross_margin_pct": s["gross_margin_pct"],
            }
             for t, s in market_data.get("stocks", {}).items()},
            indent=2
        )

        system = textwrap.dedent("""
            You are the Valuation Analyst for an institutional AI infrastructure research platform.
            You are the ONLY team member who sets return scenarios and price context.

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
        """).strip()

        user_content = f"""
Date: {market_data.get('date')}
Universe: {', '.join(self.tickers)}

MARKET DATA:
{stocks_str}

SECTOR ANALYSIS OUTPUT (for context):
{sector_outputs[:3000]}...

Please produce the full valuation analysis for each stock.
        """.strip()

        return await self._call_llm(system, user_content)

    async def _stage_macro(self, macro_data: dict) -> str:
        system = textwrap.dedent("""
            You are the Macro & Regime Strategist and Political Risk Analyst for an institutional
            AI infrastructure research platform.

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

        user_content = f"""
Date: {macro_data.get('date')}

MACRO CONTEXT:
{json.dumps(macro_data, indent=2)}

PORTFOLIO UNIVERSE: {', '.join(self.tickers)}

Please produce the macro and political risk analysis.
        """.strip()

        return await self._call_llm(system, user_content)

    async def _stage_risk(self, market_data: dict, sector_outputs: str) -> str:
        """Simplified quant risk summary (deterministic + LLM narrative)."""
        stocks = market_data.get("stocks", {})

        # Simple mock risk metrics
        risk_metrics = {}
        for ticker, snap in stocks.items():
            pe = snap.get("forward_pe", 25)
            price = snap.get("price", 100)
            target = snap.get("consensus_target_12m", price)
            upside = (target - price) / price * 100 if price else 0
            risk_metrics[ticker] = {
                "implied_upside_pct": round(upside, 1),
                "multiple_percentile_estimate": "High" if pe > 35 else "Medium" if pe > 20 else "Low",
                "concentration_flag": "YES" if ticker in ["NVDA", "TSM"] else "NO",
                "beta_estimate": 1.8 if snap.get("subtheme") == "compute" else 1.1,
            }

        system = textwrap.dedent("""
            You are the Risk Manager for an institutional AI infrastructure research platform.
            Review the provided risk metrics and sector analysis, then produce:

            ## Portfolio Risk Summary
            - Concentration risk: compute vs power vs infrastructure allocation
            - Correlation risk: names that will move together in a sell-off
            - Factor exposures: AI capex beta, rates sensitivity, geopolitical beta

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

        user_content = f"""
Date: {market_data.get('date')}
Universe: {', '.join(self.tickers)}

RISK METRICS:
{json.dumps(risk_metrics, indent=2)}

SECTOR ANALYSIS EXCERPT:
{sector_outputs[:2000]}...

Please produce the risk and scenario analysis.
        """.strip()

        return await self._call_llm(system, user_content)

    async def _stage_red_team(self, sector_outputs: str, valuation_outputs: str) -> str:
        system = textwrap.dedent("""
            You are the Red Team Analyst for an institutional AI infrastructure research platform.
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

        return await self._call_llm(system, user_content)

    async def _stage_review(self, sector_outputs: str, valuation_outputs: str, red_team_outputs: str) -> str:
        system = textwrap.dedent("""
            You are the Associate Reviewer for an institutional AI infrastructure research platform.
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

        return await self._call_llm(system, user_content)

    async def _stage_portfolio(self, sector_outputs: str, valuation_outputs: str, risk_outputs: str) -> str:
        system = textwrap.dedent("""
            You are the Portfolio Manager for an institutional AI infrastructure research platform.
            Using the research from the team, construct THREE portfolio variants.

            ## Portfolio Variant Construction Rules
            - **Max single stock weight**: 15%
            - **Subtheme requirements**: Each variant must hold at least one compute, one power/energy, one infrastructure name
            - **Sector limits**: No sector > 50% by weight
            - **Universe restriction**: Only names from the approved research universe

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

Please construct the three portfolio variants.
        """.strip()

        return await self._call_llm(system, user_content)

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
        from frontend.mock_data import DEMO_DATE

        tickers_list = ", ".join(self.tickers)
        stocks = market_data.get("stocks", {})

        # Build a brief snapshot table
        snapshot_rows = []
        for t, s in stocks.items():
            upside = (s["consensus_target_12m"] - s["price"]) / s["price"] * 100
            snapshot_rows.append(
                f"| {t} | {s['company_name']} | {s['subtheme'].replace('_', ' ').title()} "
                f"| ${s['price']:.2f} | {s['forward_pe']:.1f}x | ${s['consensus_target_12m']:.2f} | {upside:+.1f}% |"
            )
        snapshot_table = "\n".join(snapshot_rows)

        report = f"""# AI Infrastructure Research Report
## Institutional-Grade Equity Research — AI Infrastructure Theme

**Date:** {DEMO_DATE}
**Run ID:** {run_id}
**Model:** {self.model}
**Universe:** {tickers_list}
**Publication Status:** PASS (demo run)

> **IMPORTANT DISCLAIMERS**
> This report uses illustrative demo data only. All prices, targets, and figures are
> estimates for demonstration purposes. This is NOT live market data.
> All multi-year return scenarios are labelled [HOUSE VIEW] and represent analytical
> estimates, not recommendations. Past performance is no guide to future returns.
> Not investment advice.

---

## Executive Summary

This report covers {len(self.tickers)} names across three AI infrastructure sub-themes:
**Compute & Silicon**, **Power & Energy**, and **Infrastructure & Materials**.

### Universe Snapshot

| Ticker | Company | Sub-theme | Price | Fwd P/E | Consensus 12M Target | Implied Upside |
|--------|---------|-----------|-------|---------|---------------------|----------------|
{snapshot_table}

*Source: Illustrative demo data — not live prices*

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

## 7. Portfolio Construction (Stage 12)

{portfolio_output}

---

## 8. Associate Review & Self-Audit (Stage 11)

{review_output}

---

## Appendix — Run Metadata

| Field | Value |
|-------|-------|
| Run ID | {run_id} |
| Date | {DEMO_DATE} |
| Model | {self.model} |
| Universe size | {len(self.tickers)} stocks |
| Data source | Demo/illustrative |
| Pipeline version | v8.0 |

---

*AI Infrastructure Research Pipeline v8 — Demo Run*
*All [HOUSE VIEW] content is analytical opinion, not investment advice.*
*Data limitations: illustrative only. Live production requires FMP + Finnhub API keys.*
"""
        return report
