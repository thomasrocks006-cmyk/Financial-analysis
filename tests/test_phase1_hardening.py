"""Tests for Phase 1 — Agent output hardening (parse_output enforcement).

Each agent must reject structurally invalid or policy-violating LLM responses
by raising StructuredOutputError. These tests verify those enforcement rules.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from research_pipeline.agents.base_agent import StructuredOutputError


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_agent(agent_cls, **extra_kwargs):
    """Instantiate an agent with minimal required config."""
    return agent_cls(
        model="claude-opus-4-6",
        temperature=0.0,
        prompts_dir=Path("/tmp"),
        **extra_kwargs,
    )


# ── Evidence Librarian ────────────────────────────────────────────────────────

class TestEvidenceLibrarianParseOutput:
    """Evidence librarian must reject Tier 3/4 PRIMARY_FACT claims."""

    def setup_method(self):
        from research_pipeline.agents.evidence_librarian import EvidenceLibrarianAgent
        self.agent = _make_agent(EvidenceLibrarianAgent)

    def _make_claim(self, claim_type="PRIMARY_FACT", source_tier=1):
        return {
            "claim_id": "CL-001",
            "ticker": "NVDA",
            "claim_text": "NVDA leads AI chip market",
            "claim_type": claim_type,
            "source_tier": source_tier,
            "evidence_class": "QUANTITATIVE",
            "confidence_level": "HIGH",
        }

    def test_valid_tier1_primary_fact_passes(self):
        payload = json.dumps({"claims": [self._make_claim(source_tier=1)]})
        result = self.agent.parse_output(payload)
        assert "claims" in result
        assert len(result["claims"]) == 1

    def test_valid_tier2_primary_fact_passes(self):
        payload = json.dumps({"claims": [self._make_claim(source_tier=2)]})
        result = self.agent.parse_output(payload)
        assert len(result["claims"]) == 1

    def test_tier3_primary_fact_raises(self):
        payload = json.dumps({"claims": [self._make_claim(source_tier=3)]})
        with pytest.raises(StructuredOutputError, match="Tier 3"):
            self.agent.parse_output(payload)

    def test_tier4_primary_fact_raises(self):
        payload = json.dumps({"claims": [self._make_claim(source_tier=4)]})
        with pytest.raises(StructuredOutputError, match="Tier 4"):
            self.agent.parse_output(payload)

    def test_tier3_contextual_fact_allowed(self):
        """Tier 3/4 is OK for non-PRIMARY_FACT claim types."""
        claim = self._make_claim(claim_type="CONTEXTUAL_FACT", source_tier=3)
        payload = json.dumps({"claims": [claim]})
        result = self.agent.parse_output(payload)
        assert len(result["claims"]) == 1

    def test_bare_list_normalised_to_dict(self):
        claims = [self._make_claim(source_tier=1)]
        payload = json.dumps(claims)
        result = self.agent.parse_output(payload)
        assert isinstance(result, dict)
        assert "claims" in result

    def test_invalid_json_raises(self):
        with pytest.raises(StructuredOutputError, match="JSON"):
            self.agent.parse_output("not json")


# ── Sector Analysts ────────────────────────────────────────────────────────────

class TestSectorAnalystParseOutput:
    """Sector analysts must enforce the four-box fields on every ticker."""

    def setup_method(self):
        from research_pipeline.agents.sector_analysts import SectorAnalystCompute
        self.agent = _make_agent(SectorAnalystCompute)

    def _make_output(self, ticker="NVDA", **overrides):
        base = {
            "ticker": ticker,
            "company_name": "NVIDIA",
            "date": "2025-01-01",
            "box1_verified_facts": "Revenue beat, margins expanding",
            "box2_management_guidance": "CEO guides 30% YoY growth",
            "box3_consensus_market_view": "FactSet consensus $155 PT",
            "box4_analyst_judgment": "Outperform, AI cycle intact",
            "key_risks": ["competition"],
        }
        base.update(overrides)
        return base

    def test_valid_output_passes(self):
        payload = json.dumps({"sector_outputs": [self._make_output()]})
        result = self.agent.parse_output(payload)
        assert "sector_outputs" in result

    def test_missing_box1_raises(self):
        output = self._make_output()
        del output["box1_verified_facts"]
        payload = json.dumps({"sector_outputs": [output]})
        with pytest.raises(StructuredOutputError, match="box1_verified_facts"):
            self.agent.parse_output(payload)

    def test_missing_key_risks_raises(self):
        output = self._make_output()
        del output["key_risks"]
        payload = json.dumps({"sector_outputs": [output]})
        with pytest.raises(StructuredOutputError, match="key_risks"):
            self.agent.parse_output(payload)

    def test_bare_list_normalised(self):
        payload = json.dumps([self._make_output()])
        result = self.agent.parse_output(payload)
        assert "sector_outputs" in result

    def test_multiple_outputs_all_validated(self):
        good = self._make_output("NVDA")
        bad = self._make_output("AMD")
        del bad["box2_management_guidance"]
        payload = json.dumps({"sector_outputs": [good, bad]})
        with pytest.raises(StructuredOutputError, match="AMD"):
            self.agent.parse_output(payload)


# ── Valuation Analyst ─────────────────────────────────────────────────────────

class TestValuationAnalystParseOutput:
    """Valuation analyst must enforce methodology_tag and entry_quality."""

    def setup_method(self):
        from research_pipeline.agents.valuation_analyst import ValuationAnalystAgent
        self.agent = _make_agent(ValuationAnalystAgent)

    def _make_valuation(self, ticker="NVDA", **overrides):
        base = {
            "ticker": ticker,
            "date": "2025-01-01",
            "base_case_target": 150.0,
            "methodology_tag": "DCF",
            "entry_quality": "STRONG_BUY",
            "section_5_scenarios": [
                {"case": "base", "target": 150.0, "what_breaks_it": "margin compression"},
                {"case": "bear", "target": 90.0, "what_breaks_it": "demand collapse"},
                {"case": "bull", "target": 200.0, "what_breaks_it": "none"},
            ],
        }
        base.update(overrides)
        return base

    def test_valid_valuation_passes(self):
        payload = json.dumps({"valuations": [self._make_valuation()]})
        result = self.agent.parse_output(payload)
        assert "valuations" in result

    def test_missing_methodology_tag_raises(self):
        val = self._make_valuation()
        del val["methodology_tag"]
        payload = json.dumps({"valuations": [val]})
        with pytest.raises(StructuredOutputError, match="methodology_tag"):
            self.agent.parse_output(payload)

    def test_missing_entry_quality_raises(self):
        val = self._make_valuation()
        del val["entry_quality"]
        payload = json.dumps({"valuations": [val]})
        with pytest.raises(StructuredOutputError, match="entry_quality"):
            self.agent.parse_output(payload)

    def test_scenario_missing_what_breaks_it_raises(self):
        val = self._make_valuation()
        del val["section_5_scenarios"][0]["what_breaks_it"]
        payload = json.dumps({"valuations": [val]})
        with pytest.raises(StructuredOutputError, match="what_breaks_it"):
            self.agent.parse_output(payload)

    def test_bare_list_normalised(self):
        payload = json.dumps([self._make_valuation()])
        result = self.agent.parse_output(payload)
        assert "valuations" in result


# ── Red Team Analyst ──────────────────────────────────────────────────────────

class TestRedTeamAnalystParseOutput:
    """Red team analyst must enforce minimum 3 falsification tests per ticker."""

    def setup_method(self):
        from research_pipeline.agents.red_team_analyst import RedTeamAnalystAgent
        self.agent = _make_agent(RedTeamAnalystAgent)

    def _make_test(self, assumption="Assumption A", test="Test A"):
        return {
            "assumption": assumption,
            "test": test,
            "disconfirmation_signal": "price decline",
            "current_probability": "LOW",
        }

    def _make_assessment(self, ticker="NVDA", num_tests=3):
        tests = [self._make_test(f"Assumption {i}", f"Test {i}") for i in range(num_tests)]
        return {
            "ticker": ticker,
            "section_2_falsification_tests": tests,
            "required_tests": {
                "test_1": self._make_test("T1", "T1"),
                "test_2": self._make_test("T2", "T2"),
                "test_3": self._make_test("T3", "T3"),
            },
        }

    def test_three_tests_passes(self):
        payload = json.dumps({"assessments": [self._make_assessment(num_tests=3)]})
        result = self.agent.parse_output(payload)
        assert "assessments" in result

    def test_five_tests_passes(self):
        payload = json.dumps({"assessments": [self._make_assessment(num_tests=5)]})
        result = self.agent.parse_output(payload)
        assert "assessments" in result

    def test_two_tests_raises(self):
        payload = json.dumps({"assessments": [self._make_assessment(num_tests=2)]})
        with pytest.raises(StructuredOutputError, match="NVDA"):
            self.agent.parse_output(payload)

    def test_zero_tests_raises(self):
        payload = json.dumps({"assessments": [self._make_assessment(num_tests=0)]})
        with pytest.raises(StructuredOutputError):
            self.agent.parse_output(payload)

    def test_bare_list_normalised(self):
        payload = json.dumps([self._make_assessment(num_tests=3)])
        result = self.agent.parse_output(payload)
        assert "assessments" in result


# ── Associate Reviewer ────────────────────────────────────────────────────────

class TestAssociateReviewerParseOutput:
    """Associate reviewer must enforce binary PASS/FAIL and reject PASS_WITH_DISCLOSURE."""

    def setup_method(self):
        from research_pipeline.agents.associate_reviewer import AssociateReviewerAgent
        self.agent = _make_agent(AssociateReviewerAgent)

    def _make_review(self, status="PASS", corrections=None):
        payload = {
            "publication_status": status,
            "overall_assessment": "All checks passed",
        }
        if corrections:
            payload["required_corrections"] = corrections
        return payload

    def test_pass_without_corrections_accepted(self):
        payload = json.dumps(self._make_review("PASS"))
        result = self.agent.parse_output(payload)
        assert result["publication_status"].upper() == "PASS"

    def test_fail_accepted(self):
        payload = json.dumps(self._make_review("FAIL"))
        result = self.agent.parse_output(payload)
        assert result["publication_status"].upper() == "FAIL"

    def test_pass_with_disclosure_converted_to_fail(self):
        payload = json.dumps(self._make_review("PASS_WITH_DISCLOSURE"))
        result = self.agent.parse_output(payload)
        # Must be converted to FAIL, not passed through
        assert result["publication_status"].upper() == "FAIL"

    def test_pass_with_required_corrections_converted_to_fail(self):
        """PASS + required_corrections should be silently downgraded to FAIL."""
        payload = json.dumps(self._make_review("PASS", corrections=["Fix X", "Fix Y"]))
        result = self.agent.parse_output(payload)
        assert result["publication_status"].upper() == "FAIL"

    def test_missing_publication_status_raises(self):
        payload = json.dumps({"overall_assessment": "OK"})
        with pytest.raises(StructuredOutputError, match="publication_status"):
            self.agent.parse_output(payload)

    def test_non_dict_response_raises(self):
        payload = json.dumps(["PASS"])
        with pytest.raises(StructuredOutputError):
            self.agent.parse_output(payload)


# ── LLM Provider Fallback ─────────────────────────────────────────────────────

class TestLLMProviderFallback:
    """Phase 7.4: call_llm should try fallback providers on rate-limit errors."""

    def setup_method(self):
        from research_pipeline.agents.evidence_librarian import EvidenceLibrarianAgent
        self.agent = _make_agent(EvidenceLibrarianAgent)

    @pytest.mark.asyncio
    async def test_fallback_chain_triggered_on_rate_limit(self):
        """When primary provider raises rate_limit, fallback to OpenAI."""
        call_count = {"n": 0}

        async def mock_anthropic(messages, api_key, model_override=None):
            raise Exception("rate limit exceeded — 429")

        async def mock_openai(messages, api_key, response_format=None, model_override=None):
            return json.dumps({"claims": []})

        with patch.object(self.agent, "_call_anthropic", side_effect=mock_anthropic):
            with patch.object(self.agent, "_call_openai", side_effect=mock_openai):
                result = await self.agent.call_llm([{"role": "user", "content": "test"}])
        assert result == json.dumps({"claims": []})

    @pytest.mark.asyncio
    async def test_non_rate_limit_error_not_retried(self):
        """Permission errors etc. should propagate without fallback."""
        async def mock_anthropic(messages, api_key, model_override=None):
            raise PermissionError("invalid_api_key — authentication error")

        openai_called = []

        async def mock_openai(messages, api_key, response_format=None, model_override=None):
            openai_called.append(True)
            return "should not reach here"

        with patch.object(self.agent, "_call_anthropic", side_effect=mock_anthropic):
            with patch.object(self.agent, "_call_openai", side_effect=mock_openai):
                with pytest.raises(PermissionError):
                    await self.agent.call_llm([{"role": "user", "content": "test"}])

        assert not openai_called, "OpenAI fallback should NOT be triggered for non-rate-limit errors"
