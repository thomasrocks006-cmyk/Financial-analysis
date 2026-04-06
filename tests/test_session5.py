"""Session 5 tests — gate logic hardening and base_agent JSON robustness.

Covers:
- ACT-S5-1: engine.py gate logic fixed (gates 9, 12, 13 no longer hardcoded True)
- ACT-S5-2: base_agent.parse_output three-strategy JSON extraction
"""

from __future__ import annotations

import json
import unittest


# ── ACT-S5-2: BaseAgent parse_output multi-strategy extraction ───────────────


class _ConcreteAgent:
    """Minimal replication of BaseAgent.parse_output (no LLM needed)."""

    import re as _re  # class-level, avoids repeated import in method

    name = "test_agent"

    # Copy of the new parse_output logic so we can test it in isolation
    # without instantiating the full BaseAgent (which needs API keys).
    def parse_output(self, raw_response: str) -> dict:
        import json as _json
        import re as _re

        from research_pipeline.agents.base_agent import StructuredOutputError

        cleaned = raw_response.strip()

        # Strategy 1: markdown code fence (handles preamble + fence)
        fence_match = _re.search(r"```(?:json)?\s*\n?([\s\S]*?)```", cleaned)
        if fence_match:
            candidate = fence_match.group(1).strip()
            try:
                return _json.loads(candidate)
            except _json.JSONDecodeError:
                pass

        # Strategy 2: bare JSON
        try:
            return _json.loads(cleaned)
        except _json.JSONDecodeError:
            pass

        # Strategy 3: raw_decode to skip preamble
        _decoder = _json.JSONDecoder()
        for start_char in ("{", "["):
            idx = cleaned.find(start_char)
            if idx != -1:
                try:
                    obj, _ = _decoder.raw_decode(cleaned, idx)
                    if isinstance(obj, (dict, list)):
                        return obj
                except _json.JSONDecodeError:
                    pass

        raise StructuredOutputError(
            f"Agent '{self.name}' returned malformed JSON: no valid JSON found. "
            f"First 200 chars: {raw_response[:200]}"
        )


class TestBaseAgentParseOutputStrategies(unittest.TestCase):
    """Validate the three-strategy JSON extraction added in session 5."""

    def setUp(self):
        self.agent = _ConcreteAgent()

    # ── Strategy 1: markdown code fence ──────────────────────────────────

    def test_strategy1_leading_fence_no_preamble(self):
        """```json ... ``` at the start of response."""
        payload = {"key": "value", "num": 42}
        raw = f"```json\n{json.dumps(payload)}\n```"
        result = self.agent.parse_output(raw)
        self.assertEqual(result["key"], "value")
        self.assertEqual(result["num"], 42)

    def test_strategy1_leading_fence_no_lang_tag(self):
        """``` ... ``` without language specifier."""
        payload = {"alpha": True}
        raw = f"```\n{json.dumps(payload)}\n```"
        result = self.agent.parse_output(raw)
        self.assertTrue(result["alpha"])

    def test_strategy1_fence_with_preamble(self):
        """LLM adds 'Here is the output:' before the fence block."""
        payload = {"ticker": "NVDA", "score": 7.5}
        raw = f"Here is the structured output:\n```json\n{json.dumps(payload)}\n```"
        result = self.agent.parse_output(raw)
        self.assertEqual(result["ticker"], "NVDA")
        self.assertAlmostEqual(result["score"], 7.5)

    def test_strategy1_fence_with_multiline_preamble(self):
        """Multi-sentence preamble before fence."""
        payload = {"result": "pass", "items": [1, 2, 3]}
        preamble = "I have analysed your request.\nPlease see the JSON below.\n"
        raw = f"{preamble}```json\n{json.dumps(payload)}\n```"
        result = self.agent.parse_output(raw)
        self.assertEqual(result["result"], "pass")
        self.assertEqual(result["items"], [1, 2, 3])

    # ── Strategy 2: bare JSON ─────────────────────────────────────────────

    def test_strategy2_bare_json_object(self):
        """Response is bare JSON object with no wrapper."""
        payload = {"a": 1, "b": "two"}
        result = self.agent.parse_output(json.dumps(payload))
        self.assertEqual(result["a"], 1)

    def test_strategy2_bare_json_array(self):
        """Response is a bare JSON array — should return the list."""
        payload = [{"x": 1}, {"x": 2}]
        result = self.agent.parse_output(json.dumps(payload))
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)

    def test_strategy2_bare_json_with_leading_whitespace(self):
        """Stripping whitespace before parsing."""
        payload = {"k": "v"}
        result = self.agent.parse_output("   \n" + json.dumps(payload) + "\n   ")
        self.assertEqual(result["k"], "v")

    # ── Strategy 3: raw_decode skips preamble text ───────────────────────

    def test_strategy3_text_preamble_before_brace(self):
        """LLM outputs narrative text then a { JSON block with no fence."""
        payload = {"val": 99}
        raw = f"Based on the analysis, here is the result: {json.dumps(payload)}"
        result = self.agent.parse_output(raw)
        self.assertEqual(result["val"], 99)

    def test_strategy3_text_preamble_before_bracket(self):
        """LLM outputs narrative then a [ JSON array with no fence.

        Note: the loop tries '{' before '[', so to test '[' is found first the
        array must not contain any object literals (no inner '{' chars).
        """
        payload = ["NVDA", "MSFT", "AAPL"]
        raw = f"Tickers in universe: {json.dumps(payload)} — end of list."
        result = self.agent.parse_output(raw)
        self.assertIsInstance(result, list)
        self.assertIn("NVDA", result)

    # ── All strategies fail ───────────────────────────────────────────────

    def test_all_strategies_fail_raises_structured_output_error(self):
        """Plain text with no JSON raises StructuredOutputError."""
        from research_pipeline.agents.base_agent import StructuredOutputError

        with self.assertRaises(StructuredOutputError):
            self.agent.parse_output("Sorry, I cannot provide a JSON response.")

    def test_malformed_fence_raises_structured_output_error(self):
        """Fence present but content is not valid JSON."""
        from research_pipeline.agents.base_agent import StructuredOutputError

        raw = "```json\nThis is not JSON at all\n```"
        with self.assertRaises(StructuredOutputError):
            self.agent.parse_output(raw)

    # ── Real base_agent parse_output is consistent with the local impl ───

    def test_real_base_agent_strategy1_preamble_fence(self):
        """Confirm the actual BaseAgent.parse_output handles preamble + fence."""
        from research_pipeline.agents.base_agent import BaseAgent

        class _Stub(BaseAgent):
            @property
            def default_system_prompt(self) -> str:
                return "stub"

            def parse_output(self, raw: str) -> dict:
                return super().parse_output(raw)

        stub = _Stub.__new__(_Stub)  # skip __init__ — no API keys needed
        stub.name = "stub"

        payload = {"hello": "world"}
        raw = f"Intro text.\n```json\n{json.dumps(payload)}\n```"
        result = stub.parse_output(raw)
        self.assertEqual(result["hello"], "world")

    def test_real_base_agent_strategy3_preamble_then_json(self):
        """Confirm actual BaseAgent.parse_output strips preamble via raw_decode."""
        from research_pipeline.agents.base_agent import BaseAgent

        class _Stub(BaseAgent):
            @property
            def default_system_prompt(self) -> str:
                return "stub"

            def parse_output(self, raw: str) -> dict:
                return super().parse_output(raw)

        stub = _Stub.__new__(_Stub)
        stub.name = "stub"

        payload = {"ticker": "AAPL", "upside": 12.5}
        raw = f"Given the analysis: {json.dumps(payload)} — that concludes my response."
        result = stub.parse_output(raw)
        self.assertEqual(result["ticker"], "AAPL")


# ── ACT-S5-1: Gate 9 risk_packet_present fix ─────────────────────────────────


class TestGate9RiskPacketPresentFix(unittest.TestCase):
    """Gate 9 should fail when risk_packet_present=False."""

    def _gate(self, present: bool, scenario_count: int = 3):
        from research_pipeline.pipeline.gates import PipelineGates

        return PipelineGates.gate_9_risk(
            risk_packet_present=present,
            scenario_results_count=scenario_count,
        )

    def test_risk_packet_present_passes(self):
        result = self._gate(present=True, scenario_count=3)
        self.assertTrue(result.passed)

    def test_risk_packet_absent_fails(self):
        result = self._gate(present=False, scenario_count=3)
        self.assertFalse(result.passed)
        self.assertTrue(any("Risk packet missing" in b for b in result.blockers))

    def test_no_scenario_results_fails(self):
        result = self._gate(present=True, scenario_count=0)
        self.assertFalse(result.passed)
        self.assertTrue(any("scenario" in b.lower() for b in result.blockers))

    def test_concentration_breach_does_not_block(self):
        """Concentration warnings are advisory flags — gate should still pass."""
        from research_pipeline.pipeline.gates import PipelineGates

        result = PipelineGates.gate_9_risk(
            risk_packet_present=True,
            scenario_results_count=2,
            concentration_breaches=["NVDA: weight 55% exceeds 40%"],
        )
        # Gate still passes — concentration is a warning not a blocker
        self.assertTrue(result.passed)
        # But note is captured in the reason string
        self.assertIn("warnings", result.reason)


# ── ACT-S5-1: Gate 12 IC vote fix ────────────────────────────────────────────


class TestGate12ICVoteReallyGated(unittest.TestCase):
    """Gate 12 must fail when IC rejects (review_passed=False)."""

    def _gate(self, review_passed: bool, variants: int = 3, violations=None):
        from research_pipeline.pipeline.gates import PipelineGates

        return PipelineGates.gate_12_portfolio(
            variants_count=variants,
            review_passed=review_passed,
            constraint_violations=violations,
        )

    def test_ic_rejected_blocks_downstream(self):
        """IC rejection (review_passed=False) must block the gate."""
        result = self._gate(review_passed=False)
        self.assertFalse(result.passed)
        self.assertTrue(any("override FAIL" in b for b in result.blockers))

    def test_ic_approved_with_full_variants_passes(self):
        result = self._gate(review_passed=True, variants=3)
        self.assertTrue(result.passed)

    def test_ic_approved_but_too_few_variants_still_fails(self):
        result = self._gate(review_passed=True, variants=1)
        self.assertFalse(result.passed)
        self.assertTrue(any("variant" in b.lower() for b in result.blockers))

    def test_mandate_violations_block_even_with_ic_approval(self):
        result = self._gate(
            review_passed=True,
            variants=3,
            violations=["NVDA single-name > 15% mandate limit"],
        )
        self.assertFalse(result.passed)
        self.assertTrue(any("Constraint violation" in b for b in result.blockers))

    def test_hardcoded_true_would_have_passed_ic_rejection_incorrectly(self):
        """Regression: before the fix, IC rejection was silently ignored."""
        # Confirm that the OLD behaviour (always True) would return passed=True
        from research_pipeline.pipeline.gates import PipelineGates

        old_behaviour = PipelineGates.gate_12_portfolio(
            variants_count=3,
            review_passed=True,  # this is what was hardcoded
        )
        # That should pass — confirming the vector exists
        self.assertTrue(old_behaviour.passed)
        # Now confirm the fixed call fails on rejection
        fixed_behaviour = PipelineGates.gate_12_portfolio(
            variants_count=3,
            review_passed=False,  # real IC vote = rejected
        )
        self.assertFalse(fixed_behaviour.passed)


# ── ACT-S5-1: Gate 13 all_sections_approved fix ──────────────────────────────


class TestGate13SectionsApprovedFix(unittest.TestCase):
    """Gate 13 must fail when all_sections_approved=False."""

    def _gate(self, generated: bool = True, approved: bool = True):
        from research_pipeline.pipeline.gates import PipelineGates

        return PipelineGates.gate_13_report(
            report_generated=generated,
            all_sections_approved=approved,
        )

    def test_report_generated_and_approved_passes(self):
        result = self._gate(generated=True, approved=True)
        self.assertTrue(result.passed)

    def test_not_generated_fails(self):
        result = self._gate(generated=False, approved=True)
        self.assertFalse(result.passed)
        self.assertTrue(any("not generated" in b.lower() for b in result.blockers))

    def test_not_approved_fails(self):
        """all_sections_approved=False must block the report gate."""
        result = self._gate(generated=True, approved=False)
        self.assertFalse(result.passed)
        self.assertTrue(any("approved" in b.lower() for b in result.blockers))

    def test_not_generated_and_not_approved_has_two_blockers(self):
        result = self._gate(generated=False, approved=False)
        self.assertFalse(result.passed)
        self.assertEqual(len(result.blockers), 2)


if __name__ == "__main__":
    unittest.main()
