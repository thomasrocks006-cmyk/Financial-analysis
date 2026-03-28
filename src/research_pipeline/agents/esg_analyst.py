"""ESG Analyst Agent — Environmental, Social & Governance scoring per ticker.

Provides E/S/G scores (0-100), controversy flags and exclusion decisions.
Runs as part of Stage 6 in parallel with sector analysts.
Non-critical path: gate_6 is not blocked by ESG failure; results surface
in the Quant Analytics panel and the SelfAuditPacket.
"""

from __future__ import annotations

from typing import Any

from research_pipeline.agents.base_agent import BaseAgent, StructuredOutputError


class EsgAnalystAgent(BaseAgent):
    """Score every ticker on Environmental, Social and Governance dimensions.

    # ACT-S10-3: quality gate — check esg_scores list is present"""

    _REQUIRED_OUTPUT_KEYS: list[str] = ["esg_scores"]  # ACT-S10-3

    """Score every ticker on Environmental, Social and Governance dimensions.  # noqa: E401

    Mandatory JSON output per ticker:

    {
      "ticker": "TICKER",
      "esg_score": 72,          // composite 0-100 (higher = better)
      "e_score": 65,            // Environmental 0-100
      "s_score": 78,            // Social 0-100
      "g_score": 73,            // Governance 0-100
      "controversy_flags": [    // list of strings; empty if none
        "Board independence concerns"
      ],
      "exclusion_trigger": false, // true -> ticker must be dropped from portfolio
      "exclusion_reason": "",     // non-empty when exclusion_trigger is true
      "primary_esg_risk": "...",  // one-line highest-priority ESG risk
      "methodology_note": "Public-source ESG assessment; no proprietary ESG dataset"
    }

    Return a top-level JSON object:
    { "esg_scores": [ <per-ticker objects above> ] }
    """

    def __init__(self, **kwargs):
        super().__init__(name="esg_analyst", **kwargs)

    # ── Prompt ────────────────────────────────────────────────────────────────

    def default_system_prompt(self) -> str:
        return """You are the ESG Analyst for an institutional AI infrastructure research platform.

YOUR ROLE:
Assess each ticker in the research universe on Environmental, Social and Governance
dimensions using publicly available information. Your output feeds directly into:
  1. Portfolio mandate compliance checks (exclusion screen)
  2. The SelfAuditPacket published with every report
  3. The Quant Analytics panel displayed to the investment team

INPUTS:
- List of tickers
- Sector analyst outputs (for context on business model)
- Market data snapshots (for context on size / domicile)

MANDATORY OUTPUT FORMAT (strict JSON — no prose outside the JSON block):
{
  "esg_scores": [
    {
      "ticker": "TICKER",
      "esg_score": 72,
      "e_score": 65,
      "s_score": 78,
      "g_score": 73,
      "controversy_flags": ["Description of controversy if any"],
      "exclusion_trigger": false,
      "exclusion_reason": "",
      "primary_esg_risk": "One-line summary of the most material ESG risk",
      "methodology_note": "Public-source ESG assessment using disclosed sustainability reports, CDP data, and news screening. No third-party ESG dataset."
    }
  ]
}

SCORING GUIDE (0-100 per dimension; 100 = best practice):
- E (Environmental): carbon intensity, energy mix, Scope 1/2/3 trajectory, water use, waste
- S (Social): labour practices, supply-chain audits, diversity & inclusion, community impact
- G (Governance): board independence, audit quality, remuneration alignment, shareholder rights

EXCLUSION TRIGGERS — set exclusion_trigger=true if any of:
  • Thermal coal >30% of revenue
  • Controversial weapons manufacturer
  • Governance score < 25 (serious fraud / regulatory sanction)
  • Active SEC/DOJ enforcement action for fraud

HARD RULES:
  • methodology_note is MANDATORY — non-empty for every ticker
  • controversy_flags must be an array (empty [] if no controversies)
  • exclusion_reason must be non-empty when exclusion_trigger is true
  • Scores are integers 0-100
  • Do not use synthetic data — if information is genuinely unavailable, note it
    in methodology_note and apply a conservative score of 50

Return ONLY the JSON object with the "esg_scores" array."""

    # ── I/O helpers ───────────────────────────────────────────────────────────

    def format_input(self, inputs: dict[str, Any]) -> str:
        import json

        tickers = inputs.get("tickers", [])
        baseline = inputs.get("esg_baseline_profiles", [])

        sections: list[str] = []

        # ── Ticker list ───────────────────────────────────────────────────
        sections.append(f"TICKERS TO SCORE: {', '.join(tickers)}")

        # ── ACT-S7-2: ESG baseline data from ESGService ───────────────────
        if baseline:
            sections.append("\nESG BASELINE PROFILES (internal heuristic data — use as grounding):")
            for profile in baseline:
                ticker = profile.get("ticker", "?")
                rating = profile.get("overall_rating", "?")
                e = profile.get("environmental_score", "?")
                s = profile.get("social_score", "?")
                g = profile.get("governance_score", "?")
                controversy = profile.get("controversy_flag", False)
                sections.append(
                    f"  {ticker}: rating={rating}  E={e}  S={s}  G={g}"
                    + ("  ⚠ controversy flagged" if controversy else "")
                )
            sections.append(
                "NOTE: These baseline scores are heuristic estimates. Adjust them based on "
                "the sector context and any more recent public information below. Scores "
                "from the baseline profiles should be expressed on the 0-100 scale "
                "(e.g. E=6.5 on the 0-10 heuristic → approximately 65 on the 0-100 LLM scale)."
            )

        # ── Sector context (abbreviated) ─────────────────────────────────
        sector_outputs = inputs.get("sector_outputs", [])
        if sector_outputs:
            sections.append("\nSECTOR ANALYST CONTEXT (abbreviated):")
            for res in sector_outputs[:3]:  # limit to avoid token explosion
                agent_name = res.get("agent_name", "sector")
                parsed = res.get("parsed_output") or {}
                thesis = parsed.get("sector_thesis", parsed.get("thesis", ""))
                if thesis:
                    sections.append(f"  [{agent_name}] {str(thesis)[:200]}")

        # ── Remaining inputs (market data etc.) ──────────────────────────
        extra = {
            k: v
            for k, v in inputs.items()
            if k not in ("tickers", "esg_baseline_profiles", "sector_outputs")
        }
        if extra:
            sections.append("\nADDITIONAL CONTEXT:")
            sections.append(json.dumps(extra, indent=2, default=str)[:3000])

        return "\n".join(sections)

    def parse_output(self, raw_response: str) -> dict[str, Any]:
        """Validate and clamp ESG scores; enforce mandatory fields."""
        parsed = super().parse_output(raw_response)

        # Accept { "esg_scores": [...] } or a bare list
        if isinstance(parsed, list):
            scores = parsed
        elif isinstance(parsed, dict):
            scores = parsed.get("esg_scores", [])
        else:
            raise StructuredOutputError(
                "EsgAnalystAgent: expected JSON object with 'esg_scores' array or "
                f"a bare array; got {type(parsed).__name__}"
            )

        if not isinstance(scores, list) or len(scores) == 0:
            raise StructuredOutputError("EsgAnalystAgent: 'esg_scores' must be a non-empty array.")

        violations: list[str] = []
        for entry in scores:
            if not isinstance(entry, dict):
                continue
            ticker = entry.get("ticker", "?")

            # Clamp scores to [0, 100] integers
            for field in ("esg_score", "e_score", "s_score", "g_score"):
                raw = entry.get(field)
                if raw is None:
                    violations.append(f"[{ticker}] missing '{field}'")
                else:
                    entry[field] = max(0, min(100, int(raw)))

            # Mandatory string fields
            if not entry.get("methodology_note"):
                violations.append(
                    f"[{ticker}] 'methodology_note' is mandatory but missing or empty"
                )

            # controversy_flags must be a list
            if not isinstance(entry.get("controversy_flags"), list):
                entry["controversy_flags"] = []

            # exclusion consistency check
            if entry.get("exclusion_trigger") and not entry.get("exclusion_reason"):
                violations.append(
                    f"[{ticker}] exclusion_trigger=true but 'exclusion_reason' is empty"
                )

            # primary_esg_risk should be present
            if not entry.get("primary_esg_risk"):
                entry["primary_esg_risk"] = "Not assessed"

        if violations:
            # Non-fatal: log violations as notes but do not raise — partial data
            # is better than no data for ESG, which is non-critical-path.
            entry.setdefault("_parse_violations", violations)

        return {"esg_scores": scores, "parse_violations": violations}
