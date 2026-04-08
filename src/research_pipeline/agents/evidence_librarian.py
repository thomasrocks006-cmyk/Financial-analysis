"""B2 — Evidence Librarian: build claim ledger before narrative."""

from __future__ import annotations

import json
from typing import Any

from research_pipeline.agents.base_agent import BaseAgent


class EvidenceLibrarianAgent(BaseAgent):
    """Builds the claim ledger. Nothing else.

    Does NOT generate investment opinion, price targets, or portfolio recommendations.
    """

    def __init__(self, **kwargs):
        super().__init__(name="evidence_librarian", **kwargs)

    def default_system_prompt(self) -> str:
        return """You are the Evidence Librarian for an institutional AI infrastructure research platform.

YOUR SOLE JOB: Build the claim ledger before any analyst writes a word.

You do NOT generate investment opinion, price targets, or portfolio recommendations.
You ensure every material claim has complete provenance.

CLAIM LEDGER ENTRY FORMAT (all 11 fields required):
{
  "claim_id": "[TICKER]-[NNN]",
  "ticker": "TICKER",
  "claim_text": "Exact text of the claim",
  "source_name": "Named publication or filing",
  "source_url": "URL or filing reference (or UNLOCATED)",
  "source_date": "DD-Mon-YYYY",
  "source_tier": 1-4,
  "claim_type": "PRIMARY_FACT | MGMT_GUIDANCE | CONSENSUS | HOUSE_VIEW",
  "corroborated": "YES (source) | NO | PARTIAL (source)",
  "confidence": "HIGH | MEDIUM | LOW",
  "gate_status": "PASS | CAVEAT | FAIL",
  "caveat_note": "exact issue if CAVEAT/FAIL, else 'none'"
}

SOURCE TIER DEFINITIONS:
- Tier 1 (Primary): 10-K, 10-Q, earnings releases, transcripts, SEC filings, IR pages, government agencies
- Tier 2 (Independent): Reuters, Bloomberg, FT, WSJ, named analyst research, government reports
- Tier 3 (Consensus): StockAnalysis, TipRanks, MarketBeat, Yahoo Finance — acceptable for price/target/rating ONLY
- Tier 4 (House): Our own modelling. Always labelled explicitly.

HARD RULES:
- Primary facts require Tier 1 or 2
- Management guidance requires Tier 1 transcript/release + [GUIDANCE] label
- A FAIL claim cannot appear in downstream prose
- Every claim must distinguish fact, guidance, consensus, and house inference

Return a JSON array of claim ledger entries."""

    def format_input(self, inputs: dict[str, Any]) -> str:
        import json

        context = {
            "tickers": inputs.get("tickers", []),
            "analyst_claims": inputs.get("analyst_claims", []),
            "market_data": inputs.get("market_data", {}),
            "existing_ledger": inputs.get("existing_ledger", []),
            "prior_context": inputs.get("prior_context", ""),
        }
        return f"Build/update the claim ledger for:\n{json.dumps(context, indent=2, default=str)}"

    def parse_output(self, raw_response: str) -> dict[str, Any]:
        """Enforce source tier rules on every claim.

        PRIMARY_FACT claims must use Tier 1 or 2 sources.
        FAIL-status claims are retained in the ledger (so Stage 5 gate can reject them)
        but a Tier 3/4 PRIMARY_FACT forces a StructuredOutputError so the agent retries.
        """
        from research_pipeline.agents.base_agent import StructuredOutputError

        parsed = super().parse_output(raw_response)

        if isinstance(parsed, dict) and not parsed.get("claims"):
            if {"claim_id", "ticker", "claim_text"}.issubset(parsed.keys()):
                salvaged = self._salvage_claims_from_array_text(raw_response)
                parsed = salvaged or {"claims": [parsed]}

        # Agent may return a list or {"claims": [...], "sources": [...]}
        if isinstance(parsed, list):
            claims_list = parsed
            parsed = {"claims": claims_list}
        else:
            claims_list = parsed.get("claims", [])

        if not claims_list:
            salvaged = self._salvage_claims_from_array_text(raw_response)
            if salvaged:
                parsed = salvaged
                claims_list = parsed.get("claims", [])

        violations: list[str] = []
        for claim in claims_list:
            if not isinstance(claim, dict):
                continue
            claim_type = (claim.get("claim_type") or claim.get("evidence_class") or "").upper()
            try:
                tier = int(claim.get("source_tier", 4))
            except (TypeError, ValueError):
                tier = 4
            if claim_type == "PRIMARY_FACT" and tier >= 3:
                violations.append(
                    f"Claim '{claim.get('claim_id', '?')}' is PRIMARY_FACT but uses "
                    f"Tier {tier} source — must be Tier 1 or 2."
                )

        if violations:
            raise StructuredOutputError(
                "Evidence tier violation(s) — agent must fix before ledger is accepted:\n"
                + "\n".join(violations)
            )

        return parsed

    @staticmethod
    def _salvage_claims_from_array_text(raw_response: str) -> dict[str, Any] | None:
        """Recover complete claim objects from a truncated top-level JSON array."""

        cleaned = raw_response.strip()
        fence_start = cleaned.find("```json")
        if fence_start != -1:
            cleaned = cleaned[fence_start + len("```json") :].strip()

        start_idx = cleaned.find("[")
        if start_idx == -1:
            return None

        decoder = json.JSONDecoder()
        idx = start_idx + 1
        claims: list[dict[str, Any]] = []

        while idx < len(cleaned):
            while idx < len(cleaned) and cleaned[idx] in " \r\n\t,":
                idx += 1
            if idx >= len(cleaned) or cleaned[idx] in "]`":
                break
            try:
                obj, end = decoder.raw_decode(cleaned, idx)
            except json.JSONDecodeError:
                break
            if isinstance(obj, dict) and {"claim_id", "ticker", "claim_text"}.issubset(obj.keys()):
                claims.append(obj)
            idx = end

        return {"claims": claims} if claims else None
