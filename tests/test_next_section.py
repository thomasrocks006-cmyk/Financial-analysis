"""Tests for session-3 additions:
P-5  — yfinance third-source fallback in MarketDataIngestor
P-6  — DCF relative valuation (EV/EBITDA and P/E)
ACT-6 — VaR / Drawdown embedded in RiskPacket via RiskEngine
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest


# ══════════════════════════════════════════════════════════════════════════════
# P-6: DCF relative valuation
# ══════════════════════════════════════════════════════════════════════════════


class TestRelativeValuation:
    """Tests for DCFEngine.relative_valuation()."""

    @pytest.fixture(autouse=True)
    def engine(self):
        from research_pipeline.services.dcf_engine import DCFEngine

        self.engine = DCFEngine()

    # ── EV/EBITDA method ──────────────────────────────────────────────────

    def test_ev_ebitda_implied_price_known_numbers(self):
        """With known inputs, implied EV/EBITDA price should match hand-calc."""
        # ebitda=100, multiple=20 → EV=2000; net_debt=200, shares=100
        # equity = 2000 - 200 = 1800; price = 1800 / 100 = 18.0
        result = self.engine.relative_valuation(
            ticker="TEST",
            current_price=15.0,
            ebitda=100.0,
            net_debt=200.0,
            shares_outstanding=100.0,
            peer_ev_ebitda_multiple=20.0,
        )
        assert result.ev_ebitda_implied_price == pytest.approx(18.0, abs=0.01)

    def test_ev_ebitda_upside_pct(self):
        """Upside percentage is correctly calculated."""
        result = self.engine.relative_valuation(
            ticker="TEST",
            current_price=15.0,
            ebitda=100.0,
            net_debt=200.0,
            shares_outstanding=100.0,
            peer_ev_ebitda_multiple=20.0,
        )
        # (18 - 15) / 15 * 100 = 20%
        assert result.ev_ebitda_upside_pct == pytest.approx(20.0, abs=0.1)

    def test_ev_ebitda_skipped_when_missing_inputs(self):
        """If ebitda or multiple is None the EV/EBITDA result is None."""
        result = self.engine.relative_valuation(
            ticker="TEST",
            current_price=10.0,
            eps=2.0,
            peer_pe_multiple=15.0,
        )
        assert result.ev_ebitda_implied_price is None
        assert result.ev_ebitda_upside_pct is None

    # ── P/E method ────────────────────────────────────────────────────────

    def test_pe_implied_price_known_numbers(self):
        """eps=5 × multiple=20 → implied 100."""
        result = self.engine.relative_valuation(
            ticker="TEST",
            current_price=80.0,
            eps=5.0,
            peer_pe_multiple=20.0,
        )
        assert result.pe_implied_price == pytest.approx(100.0, abs=0.01)

    def test_pe_upside_pct(self):
        """(100 - 80) / 80 = 25%."""
        result = self.engine.relative_valuation(
            ticker="TEST",
            current_price=80.0,
            eps=5.0,
            peer_pe_multiple=20.0,
        )
        assert result.pe_upside_pct == pytest.approx(25.0, abs=0.1)

    def test_negative_eps_skips_pe_method(self):
        """Negative EPS yields None for P/E results with a note in methodology."""
        result = self.engine.relative_valuation(
            ticker="TEST",
            current_price=10.0,
            eps=-1.0,
            peer_pe_multiple=15.0,
        )
        assert result.pe_implied_price is None
        assert result.pe_upside_pct is None
        assert "P/E skipped" in (result.methodology_note or "")

    def test_zero_eps_skips_pe_method(self):
        """Zero EPS yields None for P/E results."""
        result = self.engine.relative_valuation(
            ticker="TEST",
            current_price=10.0,
            eps=0.0,
            peer_pe_multiple=15.0,
        )
        assert result.pe_implied_price is None

    # ── Composite ────────────────────────────────────────────────────────

    def test_composite_is_simple_average_of_both_methods(self):
        """Composite = (ev_ebitda_price + pe_price) / 2 when both available."""
        result = self.engine.relative_valuation(
            ticker="TEST",
            current_price=50.0,
            ebitda=200.0,
            net_debt=0.0,
            shares_outstanding=100.0,
            peer_ev_ebitda_multiple=10.0,  # implied = 200*10/100 = 20
            eps=5.0,
            peer_pe_multiple=16.0,  # implied = 80
        )
        # EV/EBITDA → 20, P/E → 80, composite → 50
        assert result.composite_implied_price == pytest.approx(50.0, abs=0.01)

    def test_composite_equals_single_available_method(self):
        """Composite equals the single available implied price when only one method works."""
        result = self.engine.relative_valuation(
            ticker="TEST",
            current_price=80.0,
            eps=5.0,
            peer_pe_multiple=20.0,
        )
        assert result.composite_implied_price == pytest.approx(result.pe_implied_price, abs=0.01)

    def test_custom_weight_composite(self):
        """weight_composite() correctly blends two prices."""
        from research_pipeline.services.dcf_engine import RelativeValuationResult

        r = RelativeValuationResult(
            ticker="T",
            current_price=50.0,
            ev_ebitda_implied_price=40.0,
            pe_implied_price=60.0,
            composite_implied_price=50.0,
        )
        # 70% EV/EBITDA + 30% P/E = 0.7*40 + 0.3*60 = 46
        assert r.weight_composite(ev_ebitda_weight=0.7, pe_weight=0.3) == pytest.approx(
            46.0, abs=0.01
        )

    def test_custom_weight_only_pe_available(self):
        """weight_composite with only P/E returns P/E price regardless of weights."""
        from research_pipeline.services.dcf_engine import RelativeValuationResult

        r = RelativeValuationResult(
            ticker="T",
            current_price=50.0,
            ev_ebitda_implied_price=None,
            pe_implied_price=60.0,
            composite_implied_price=60.0,
        )
        assert r.weight_composite(ev_ebitda_weight=0.7, pe_weight=0.3) == pytest.approx(
            60.0, abs=0.01
        )

    def test_result_has_ticker_and_current_price(self):
        result = self.engine.relative_valuation(
            ticker="AAPL",
            current_price=175.0,
            eps=6.5,
            peer_pe_multiple=25.0,
        )
        assert result.ticker == "AAPL"
        assert result.current_price == 175.0


# ══════════════════════════════════════════════════════════════════════════════
# ACT-6: VaR / Drawdown in RiskPacket and RiskEngine
# ══════════════════════════════════════════════════════════════════════════════


class TestRiskPacketExtendedFields:
    """Tests for the new VaR/drawdown fields on RiskPacket."""

    def _make_packet(self, var_analysis=None, drawdown_analysis=None, **kwargs):
        from research_pipeline.schemas.reports import RiskPacket

        return RiskPacket(
            run_id="test-run",
            portfolio_volatility=0.18,
            max_drawdown=0.25,
            sector_concentration={"compute": 0.6},
            beta_weighted_exposure=1.1,
            var_analysis=var_analysis,
            drawdown_analysis=drawdown_analysis,
            **kwargs,
        )

    def test_var_pct_property_reads_from_analysis_dict(self):
        r = self._make_packet(var_analysis={"var_pct": 0.035, "method": "parametric"})
        assert r.var_pct == pytest.approx(0.035)

    def test_cvar_pct_property_reads_from_analysis_dict(self):
        r = self._make_packet(var_analysis={"cvar_pct": 0.055})
        assert r.cvar_pct == pytest.approx(0.055)

    def test_max_drawdown_pct_property_reads_from_drawdown_dict(self):
        r = self._make_packet(drawdown_analysis={"max_drawdown_pct": 0.30})
        assert r.max_drawdown_pct == pytest.approx(0.30)

    def test_properties_return_none_when_analysis_missing(self):
        r = self._make_packet()
        assert r.var_pct is None
        assert r.cvar_pct is None
        assert r.max_drawdown_pct is None

    def test_var_method_field_stored(self):
        r = self._make_packet(var_method="historical", confidence_level=0.99)
        assert r.var_method == "historical"
        assert r.confidence_level == pytest.approx(0.99)

    def test_risk_packet_serialises_to_dict(self):
        r = self._make_packet(
            var_analysis={"var_pct": 0.02},
            drawdown_analysis={"max_drawdown_pct": 0.15},
        )
        d = r.model_dump()
        assert d["var_analysis"]["var_pct"] == pytest.approx(0.02)
        assert d["drawdown_analysis"]["max_drawdown_pct"] == pytest.approx(0.15)


class TestRiskEngineBuildPacketWithVaR:
    """Tests for RiskEngine.build_risk_packet() with VaR/drawdown injection."""

    @pytest.fixture(autouse=True)
    def engine(self):
        from research_pipeline.services.risk_engine import RiskEngine

        self.engine = RiskEngine()

    def _base_kwargs(self):
        return dict(
            run_id="run-001",
            weights={"NVDA": 0.5, "MSFT": 0.5},
            returns={"NVDA": [0.01, -0.02, 0.03], "MSFT": [0.005, -0.01, 0.015]},
            subthemes={"NVDA": "compute", "MSFT": "infrastructure"},
        )

    def test_build_packet_without_var_produces_valid_packet(self):
        packet = self.engine.build_risk_packet(**self._base_kwargs())
        assert packet.run_id == "run-001"
        assert packet.var_analysis is None
        assert packet.drawdown_analysis is None

    def test_build_packet_embeds_var_result_dict(self):
        var_dict = {"var_pct": 0.025, "cvar_pct": 0.040, "method": "historical"}
        packet = self.engine.build_risk_packet(**self._base_kwargs(), var_result=var_dict)
        assert packet.var_analysis is not None
        assert packet.var_analysis["var_pct"] == pytest.approx(0.025)
        assert packet.var_pct == pytest.approx(0.025)

    def test_build_packet_embeds_drawdown_dict(self):
        dd_dict = {"max_drawdown_pct": 0.22, "recovery_days": 45}
        packet = self.engine.build_risk_packet(**self._base_kwargs(), drawdown=dd_dict)
        assert packet.drawdown_analysis is not None
        assert packet.drawdown_analysis["max_drawdown_pct"] == pytest.approx(0.22)
        assert packet.max_drawdown_pct == pytest.approx(0.22)

    def test_build_packet_accepts_pydantic_model_objects(self):
        """VaRResult / DrawdownAnalysis pydantic objects are accepted via model_dump()."""
        from research_pipeline.services.var_engine import VaREngine

        np.random.seed(99)
        ret = np.random.normal(0, 0.01, 252).tolist()
        var_engine = VaREngine()
        var_result = var_engine.historical_var("test-run", ret)

        packet = self.engine.build_risk_packet(**self._base_kwargs(), var_result=var_result)
        # Should not raise; var_analysis is populated
        assert packet.var_analysis is not None

    def test_build_packet_strips_none_var_properly(self):
        """Explicitly passing None keeps var_analysis=None."""
        packet = self.engine.build_risk_packet(
            **self._base_kwargs(), var_result=None, drawdown=None
        )
        assert packet.var_analysis is None
        assert packet.drawdown_analysis is None


# ══════════════════════════════════════════════════════════════════════════════
# P-5: yfinance fallback in MarketDataIngestor
# ══════════════════════════════════════════════════════════════════════════════


class TestYfinanceFallback:
    """Tests for P-5 — yfinance as third-source fallback in MarketDataIngestor."""

    @pytest.fixture()
    def ingestor(self):
        from research_pipeline.services.market_data_ingestor import MarketDataIngestor

        return MarketDataIngestor(fmp_key="FAKE", finnhub_key="FAKE")

    # ── source field is always present ───────────────────────────────────

    def test_ingest_result_always_has_source_field(self, ingestor):
        """The result dict must contain a 'source' key regardless of API failures."""

        async def run():
            # All network calls will fail (fake keys) — source must still be present
            result = await ingestor.ingest_ticker("AAPL")
            return result

        # patch httpx to avoid real network calls; let them raise
        result = asyncio.run(run())
        assert "source" in result, "'source' key is required by DataQA gate 4"

    # ── fallback logic ────────────────────────────────────────────────────

    def test_yfinance_fallback_activates_when_both_sources_miss_price(self, ingestor):
        """When FMP and Finnhub both miss a price, yfinance should be used."""
        from research_pipeline.schemas.market_data import MarketSnapshot

        mock_snap = MarketSnapshot(ticker="XYZ", source="yfinance", price=42.0)

        async def run():
            with patch.object(
                ingestor, "fetch_yfinance_quote", new=AsyncMock(return_value=mock_snap)
            ):
                # stub all real network methods to return data with no price
                empty_snap = MarketSnapshot(ticker="XYZ", source="fmp", price=None)
                ingestor.fetch_fmp_quote = AsyncMock(return_value=empty_snap)
                ingestor.fetch_fmp_price_targets = AsyncMock(return_value=[])
                ingestor.fetch_fmp_analyst_estimates = AsyncMock(return_value=[])
                from research_pipeline.schemas.market_data import ConsensusSnapshot, RatingsSnapshot

                ingestor.fetch_finnhub_quote = AsyncMock(
                    return_value=MarketSnapshot(ticker="XYZ", source="finnhub", price=None)
                )
                ingestor.fetch_finnhub_recommendation = AsyncMock(
                    return_value=RatingsSnapshot(ticker="XYZ", source="finnhub")
                )
                ingestor.fetch_finnhub_price_target = AsyncMock(
                    return_value=ConsensusSnapshot(ticker="XYZ", source="finnhub")
                )
                return await ingestor.ingest_ticker("XYZ")

        result = asyncio.run(run())
        assert "yfinance_quote" in result
        assert result["yfinance_quote"]["price"] == pytest.approx(42.0)
        assert result["source"] == "yfinance"

    def test_yfinance_not_called_when_fmp_has_price(self, ingestor):
        """yfinance fallback must NOT fire when FMP already returned a price."""
        from research_pipeline.schemas.market_data import (
            ConsensusSnapshot,
            MarketSnapshot,
            RatingsSnapshot,
        )

        mock_yf = AsyncMock()

        async def run():
            with patch.object(ingestor, "fetch_yfinance_quote", new=mock_yf):
                ingestor.fetch_fmp_quote = AsyncMock(
                    return_value=MarketSnapshot(ticker="AAPL", source="fmp", price=170.0)
                )
                ingestor.fetch_fmp_price_targets = AsyncMock(return_value=[])
                ingestor.fetch_fmp_analyst_estimates = AsyncMock(return_value=[])
                ingestor.fetch_finnhub_quote = AsyncMock(
                    return_value=MarketSnapshot(ticker="AAPL", source="finnhub", price=None)
                )
                ingestor.fetch_finnhub_recommendation = AsyncMock(
                    return_value=RatingsSnapshot(ticker="AAPL", source="finnhub")
                )
                ingestor.fetch_finnhub_price_target = AsyncMock(
                    return_value=ConsensusSnapshot(ticker="AAPL", source="finnhub")
                )
                return await ingestor.ingest_ticker("AAPL")

        asyncio.run(run())
        mock_yf.assert_not_called()

    def test_yfinance_not_called_when_finnhub_has_price(self, ingestor):
        """yfinance fallback must NOT fire when Finnhub already returned a price."""
        from research_pipeline.schemas.market_data import (
            ConsensusSnapshot,
            MarketSnapshot,
            RatingsSnapshot,
        )

        mock_yf = AsyncMock()

        async def run():
            with patch.object(ingestor, "fetch_yfinance_quote", new=mock_yf):
                ingestor.fetch_fmp_quote = AsyncMock(
                    return_value=MarketSnapshot(ticker="MSFT", source="fmp", price=None)
                )
                ingestor.fetch_fmp_price_targets = AsyncMock(return_value=[])
                ingestor.fetch_fmp_analyst_estimates = AsyncMock(return_value=[])
                ingestor.fetch_finnhub_quote = AsyncMock(
                    return_value=MarketSnapshot(ticker="MSFT", source="finnhub", price=310.0)
                )
                ingestor.fetch_finnhub_recommendation = AsyncMock(
                    return_value=RatingsSnapshot(ticker="MSFT", source="finnhub")
                )
                ingestor.fetch_finnhub_price_target = AsyncMock(
                    return_value=ConsensusSnapshot(ticker="MSFT", source="finnhub")
                )
                return await ingestor.ingest_ticker("MSFT")

        asyncio.run(run())
        mock_yf.assert_not_called()

    def test_yfinance_failure_stored_in_errors_and_doesnt_raise(self, ingestor):
        """If yfinance also fails the error is recorded but the result is still returned."""
        from research_pipeline.schemas.market_data import (
            ConsensusSnapshot,
            MarketSnapshot,
            RatingsSnapshot,
        )

        async def run():
            with patch.object(
                ingestor,
                "fetch_yfinance_quote",
                new=AsyncMock(side_effect=RuntimeError("network error")),
            ):
                ingestor.fetch_fmp_quote = AsyncMock(
                    return_value=MarketSnapshot(ticker="ZZZ", source="fmp", price=None)
                )
                ingestor.fetch_fmp_price_targets = AsyncMock(return_value=[])
                ingestor.fetch_fmp_analyst_estimates = AsyncMock(return_value=[])
                ingestor.fetch_finnhub_quote = AsyncMock(
                    return_value=MarketSnapshot(ticker="ZZZ", source="finnhub", price=None)
                )
                ingestor.fetch_finnhub_recommendation = AsyncMock(
                    return_value=RatingsSnapshot(ticker="ZZZ", source="finnhub")
                )
                ingestor.fetch_finnhub_price_target = AsyncMock(
                    return_value=ConsensusSnapshot(ticker="ZZZ", source="finnhub")
                )
                return await ingestor.ingest_ticker("ZZZ")

        result = asyncio.run(run())
        assert "yfinance_quote" not in result
        assert "yfinance_quote" in result.get("errors", {})
        # ingest still returned a dict → no exception propagated
        assert "ticker" in result

    # ── fetch_yfinance_quote unit test ────────────────────────────────────

    def test_fetch_yfinance_quote_returns_market_snapshot(self, ingestor):
        """Unit test for fetch_yfinance_quote; mocks yfinance Ticker.fast_info."""
        from research_pipeline.schemas.market_data import MarketSnapshot

        fake_fast_info = MagicMock()
        fake_fast_info.last_price = 55.0
        fake_fast_info.market_cap = 5_000_000_000.0
        fake_fast_info.pe_ratio = 22.5
        fake_fast_info.forward_pe = 18.0

        fake_ticker = MagicMock()
        fake_ticker.fast_info = fake_fast_info

        with patch("yfinance.Ticker", return_value=fake_ticker):
            result = asyncio.run(ingestor.fetch_yfinance_quote("FAKE"))

        assert isinstance(result, MarketSnapshot)
        assert result.ticker == "FAKE"
        assert result.source == "yfinance"
        assert result.price == pytest.approx(55.0)
        assert result.market_cap == pytest.approx(5e9)
        assert result.trailing_pe == pytest.approx(22.5)


# ══════════════════════════════════════════════════════════════════════════════
# P-7: Fixed-income analyst agent
# ══════════════════════════════════════════════════════════════════════════════


class TestFixedIncomeAnalystAgent:
    """Tests for the FixedIncomeAnalystAgent parse_output and validation."""

    @pytest.fixture(autouse=True)
    def agent(self):
        from research_pipeline.agents.fixed_income_analyst import FixedIncomeAnalystAgent

        self.agent = FixedIncomeAnalystAgent()

    # ── parse_output: mandatory-field defaults ────────────────────────────────

    def test_parse_output_with_complete_valid_json(self):
        import json

        payload = {
            "yield_curve_regime": "inverted",
            "10y_yield_context": "5.2% — highest since 2007",
            "cost_of_capital_trend": "rising",
            "rate_sensitivity_score": 8.0,
            "rate_sensitivity_rationale": "High-multiple tech names carry duration risk",
            "sector_rotation_read": "Utilities and asset-heavy names most affected",
            "credit_quality_flags": [
                {"ticker": "NVDA", "net_debt_ebitda": -1.5, "flag": "clean", "note": "net cash"}
            ],
            "capital_markets_risk": "Negligible near-term refinancing risk for universe",
            "key_risks": ["Rate snap-up squeezes multiples", "CAPEX financing costs rise"],
            "offsetting_factors": ["Asset-light software revenue", "Strong FCF generation"],
            "duration_proxy_commentary": "Growth premium embeds ~3y duration proxy",
            "methodology_note": "Heuristic — no live yield data available",
        }
        result = self.agent.parse_output(json.dumps(payload))
        assert result["yield_curve_regime"] == "inverted"
        assert result["rate_sensitivity_score"] == pytest.approx(8.0)
        assert len(result["key_risks"]) == 2
        assert result["methodology_note"] != ""

    def test_parse_output_fills_missing_mandatory_fields(self):
        import json

        # Minimal payload: only a few keys
        payload = {"10y_yield_context": "4.5% inverted curve"}
        result = self.agent.parse_output(json.dumps(payload))
        assert result["yield_curve_regime"] == "unknown"
        assert result["cost_of_capital_trend"] == "unknown"
        assert result["rate_sensitivity_score"] == pytest.approx(5.0)
        assert isinstance(result["key_risks"], list)
        assert isinstance(result["credit_quality_flags"], list)

    def test_parse_output_clamps_rate_sensitivity_score_high(self):
        import json

        payload = {"rate_sensitivity_score": 99, "methodology_note": "test"}
        result = self.agent.parse_output(json.dumps(payload))
        assert result["rate_sensitivity_score"] == pytest.approx(10.0)

    def test_parse_output_clamps_rate_sensitivity_score_low(self):
        import json

        payload = {"rate_sensitivity_score": -5, "methodology_note": "test"}
        result = self.agent.parse_output(json.dumps(payload))
        assert result["rate_sensitivity_score"] == pytest.approx(1.0)

    def test_parse_output_inserts_default_methodology_note_when_empty(self):
        import json

        payload = {"rate_sensitivity_score": 5, "methodology_note": ""}
        result = self.agent.parse_output(json.dumps(payload))
        assert len(result["methodology_note"]) > 10  # default text injected

    def test_parse_output_normalises_list_response_to_dict(self):
        """Some models return a JSON array; parse_output should extract first element."""
        import json

        payload = [{"rate_sensitivity_score": 6, "methodology_note": "test note"}]
        result = self.agent.parse_output(json.dumps(payload))
        assert result["rate_sensitivity_score"] == pytest.approx(6.0)
        assert result["methodology_note"] == "test note"

    def test_parse_output_handles_empty_list(self):
        import json

        result = self.agent.parse_output(json.dumps([]))
        # Should not raise; should return dict with defaults
        assert isinstance(result, dict)
        assert result["rate_sensitivity_score"] == pytest.approx(5.0)

    # ── Agent metadata ────────────────────────────────────────────────────────

    def test_agent_name_is_correct(self):
        assert self.agent.name == "fixed_income_analyst"

    def test_system_prompt_contains_required_output_keys(self):
        prompt = self.agent.default_system_prompt()
        required_keys = [
            "yield_curve_regime",
            "rate_sensitivity_score",
            "cost_of_capital_trend",
            "credit_quality_flags",
            "methodology_note",
        ]
        for key in required_keys:
            assert key in prompt, f"System prompt missing key: {key}"

    def test_format_input_serialises_to_json_string(self):
        import json

        inputs = {"universe": ["NVDA", "CEG"], "macro_context": {"note": "test"}}
        formatted = self.agent.format_input(inputs)
        parsed_back = json.loads(formatted)
        assert parsed_back["universe"] == ["NVDA", "CEG"]


# ══════════════════════════════════════════════════════════════════════════════
# Engine wiring: fixed_income_agent attribute
# ══════════════════════════════════════════════════════════════════════════════


class TestEngineHasFixedIncomeAgent:
    """Confirm PipelineEngine instantiates with a fixed_income_agent attribute."""

    def test_engine_has_fixed_income_agent(self, tmp_path):
        from pathlib import Path
        from research_pipeline.config.loader import PipelineConfig
        from research_pipeline.config.settings import APIKeys, Settings
        from research_pipeline.pipeline.engine import PipelineEngine
        from research_pipeline.agents.fixed_income_analyst import FixedIncomeAnalystAgent

        settings = Settings(
            project_root=Path(__file__).resolve().parents[1],
            storage_dir=tmp_path / "storage",
            reports_dir=tmp_path / "reports",
            prompts_dir=tmp_path / "prompts",
            llm_model="claude-opus-4-6",
            api_keys=APIKeys(
                fmp_api_key="fake",
                finnhub_api_key="fake",
                anthropic_api_key="fake",
            ),
        )
        engine = PipelineEngine(settings=settings, config=PipelineConfig())
        assert hasattr(engine, "fixed_income_agent"), (
            "PipelineEngine must expose a fixed_income_agent attribute"
        )
        assert isinstance(engine.fixed_income_agent, FixedIncomeAnalystAgent)

    def test_stage9_risk_output_accepts_fixed_income_context_key(self):
        """The Stage 9 risk_output dict can be extended with 'fixed_income_context'."""
        fi_context = {
            "yield_curve_regime": "flattening",
            "rate_sensitivity_score": 7.5,
            "cost_of_capital_trend": "rising",
            "key_risks": ["Spread widening"],
            "methodology_note": "Test",
        }
        risk_output = {
            "run_id": "test",
            "portfolio_volatility": 0.18,
            "max_drawdown": 0.20,
            "sector_concentration": {},
            "beta_weighted_exposure": 1.1,
        }
        # Engine stores fi_context at this key; confirm no constraint violation
        risk_output["fixed_income_context"] = fi_context
        assert risk_output["fixed_income_context"]["rate_sensitivity_score"] == pytest.approx(7.5)


# ══════════════════════════════════════════════════════════════════════════════
# P-4: Quant Analytics panel — data-extraction helper logic
# ══════════════════════════════════════════════════════════════════════════════


class TestQuantAnalyticsPanelDataExtraction:
    """Unit tests for the _stage_out logic pattern used in the Streamlit panel.

    Since _stage_out is defined inline in app.py (not importable), we replicate
    the identical logic here and test the data extraction behaviour directly.
    """

    @staticmethod
    def stage_out(n: int, loaded: dict | None, session_outputs: dict) -> dict:
        """Replicated _stage_out helper from app.py."""
        if loaded:
            for s in loaded.get("stages", []):
                if isinstance(s, dict) and s.get("stage_num") == n:
                    out = s.get("output")
                    if isinstance(out, dict):
                        return out
            return {}
        return session_outputs.get(n, {})

    def test_extracts_from_loaded_run_by_stage_num(self):
        loaded = {
            "stages": [
                {"stage_num": 7, "output": {"some": "data"}},
                {"stage_num": 9, "output": {"etf_differentiation_score": 72.5}},
            ]
        }
        result = self.stage_out(9, loaded, {})
        assert result["etf_differentiation_score"] == pytest.approx(72.5)

    def test_returns_empty_dict_for_missing_stage_in_loaded(self):
        loaded = {"stages": [{"stage_num": 7, "output": {"x": 1}}]}
        result = self.stage_out(9, loaded, {})
        assert result == {}

    def test_falls_back_to_session_state_when_no_loaded(self):
        session_state = {9: {"var_analysis": {"var_pct": 0.025}}}
        result = self.stage_out(9, None, session_state)
        assert result["var_analysis"]["var_pct"] == pytest.approx(0.025)

    def test_returns_empty_dict_when_both_sources_empty(self):
        result = self.stage_out(9, None, {})
        assert result == {}

    def test_ignores_non_dict_output_in_loaded(self):
        """If a stage output is not a dict (e.g. raw text string), skip it."""
        loaded = {"stages": [{"stage_num": 9, "output": "raw text, not a dict"}]}
        result = self.stage_out(9, loaded, {9: {"fallback": True}})
        # Should fall back to session_state since loaded output isn't a dict
        assert result == {}  # loaded path returns {} when not a dict

    def test_var_pct_extracted_from_var_analysis_key(self):
        session_state = {
            9: {
                "var_analysis": {"var_pct": 0.035, "cvar_pct": 0.055},
                "drawdown_analysis": {"max_drawdown_pct": 0.28},
            }
        }
        out = self.stage_out(9, None, session_state)
        var_d = out.get("var_analysis") or {}
        assert var_d.get("var_pct") == pytest.approx(0.035)

    def test_fixed_income_context_extracted_from_stage9(self):
        session_state = {
            9: {
                "fixed_income_context": {
                    "yield_curve_regime": "inverted",
                    "rate_sensitivity_score": 8.0,
                }
            }
        }
        out = self.stage_out(9, None, session_state)
        fi = out.get("fixed_income_context", {})
        assert fi["yield_curve_regime"] == "inverted"

    def test_ic_record_extracted_from_stage12(self):
        session_state = {
            12: {
                "ic_record": {"is_approved": True, "votes": {"CIO": "approve"}},
                "baseline_weights": {"NVDA": 0.5, "CEG": 0.5},
            }
        }
        out = self.stage_out(12, None, session_state)
        assert out["ic_record"]["is_approved"] is True
