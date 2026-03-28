"""Rebalancing Framework — detect portfolio drift and generate rebalance trades."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class RebalanceTrade(BaseModel):
    """A single rebalance trade."""

    ticker: str
    direction: str  # "buy" or "sell"
    current_weight_pct: float
    target_weight_pct: float
    delta_weight_pct: float
    estimated_shares: float = 0.0
    estimated_value: float = 0.0
    market_impact_bps: float = 0.0
    priority: str = "normal"  # "high", "normal", "low"


class RebalanceProposal(BaseModel):
    """Full rebalance proposal with trade list and impact estimates."""

    run_id: str
    proposal_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    trigger: str = "manual"  # "drift", "mandate_breach", "scheduled", "manual"
    trades: list[RebalanceTrade] = []
    total_turnover_pct: float = 0.0
    estimated_total_impact_bps: float = 0.0
    summary: str = ""

    @property
    def trade_count(self) -> int:
        return len(self.trades)


class RebalancingEngine:
    """Portfolio rebalancing framework — no LLM.

    Detects drift from target weights, generates rebalance trades,
    and estimates transaction costs / market impact.
    """

    def __init__(
        self,
        drift_threshold_pct: float = 2.0,
        min_trade_pct: float = 0.5,
        portfolio_value: float = 1_000_000.0,
        participation_rate: float = 0.20,
    ):
        self.drift_threshold = drift_threshold_pct
        self.min_trade = min_trade_pct
        self.portfolio_value = portfolio_value
        self.participation_rate = participation_rate

    def check_drift(
        self,
        target_weights: dict[str, float],
        current_weights: dict[str, float],
    ) -> dict[str, float]:
        """Compute drift per position.

        Returns {ticker: drift_pct} for positions exceeding drift threshold.
        """
        drifts: dict[str, float] = {}
        all_tickers = set(target_weights.keys()) | set(current_weights.keys())

        for ticker in all_tickers:
            target = target_weights.get(ticker, 0)
            current = current_weights.get(ticker, 0)
            drift = current - target
            if abs(drift) >= self.drift_threshold:
                drifts[ticker] = round(drift, 4)

        return drifts

    def compute_current_weights(
        self,
        target_weights: dict[str, float],
        reference_prices: dict[str, float],
        current_prices: dict[str, float],
    ) -> dict[str, float]:
        """Compute current weights from price changes since construction."""
        position_values: dict[str, float] = {}

        for ticker, weight_pct in target_weights.items():
            ref_price = reference_prices.get(ticker, 1)
            cur_price = current_prices.get(ticker, ref_price)
            ratio = cur_price / ref_price if ref_price > 0 else 1.0
            position_values[ticker] = weight_pct * ratio

        total = sum(position_values.values())
        if total <= 0:
            return dict(target_weights)

        return {t: round(v / total * 100, 4) for t, v in position_values.items()}

    def generate_rebalance(
        self,
        run_id: str,
        target_weights: dict[str, float],
        current_weights: dict[str, float],
        current_prices: dict[str, float] | None = None,
        volume_data: dict[str, float] | None = None,
        trigger: str = "drift",
    ) -> RebalanceProposal:
        """Generate a full rebalance proposal.

        Args:
            run_id: Pipeline run identifier
            target_weights: Target portfolio weights (ticker -> pct)
            current_weights: Current portfolio weights (ticker -> pct)
            current_prices: Current prices (optional, for share calculation)
            volume_data: Average daily volume (optional, for impact estimation)
            trigger: What triggered the rebalance
        """
        trades: list[RebalanceTrade] = []
        total_turnover = 0.0
        total_impact = 0.0

        all_tickers = set(target_weights.keys()) | set(current_weights.keys())

        for ticker in sorted(all_tickers):
            target = target_weights.get(ticker, 0)
            current = current_weights.get(ticker, 0)
            delta = target - current

            if abs(delta) < self.min_trade:
                continue

            direction = "buy" if delta > 0 else "sell"
            est_value = abs(delta) / 100 * self.portfolio_value

            # Estimate shares
            est_shares = 0.0
            if current_prices and ticker in current_prices and current_prices[ticker] > 0:
                est_shares = est_value / current_prices[ticker]

            # Market impact estimate (square root model)
            impact_bps = 0.0
            if (
                volume_data
                and ticker in volume_data
                and current_prices
                and ticker in current_prices
            ):
                adv_value = volume_data[ticker] * current_prices[ticker]
                if adv_value > 0:
                    import numpy as np

                    participation = est_value / (adv_value * self.participation_rate)
                    impact_bps = float(10 * np.sqrt(participation) * 100)

            # Priority based on delta magnitude
            priority = "high" if abs(delta) > 5 else ("normal" if abs(delta) > 2 else "low")

            trades.append(
                RebalanceTrade(
                    ticker=ticker,
                    direction=direction,
                    current_weight_pct=round(current, 2),
                    target_weight_pct=round(target, 2),
                    delta_weight_pct=round(delta, 2),
                    estimated_shares=round(est_shares, 0),
                    estimated_value=round(est_value, 2),
                    market_impact_bps=round(impact_bps, 2),
                    priority=priority,
                )
            )

            total_turnover += abs(delta)
            total_impact += impact_bps * est_value

        # Weighted average impact
        total_trade_value = sum(t.estimated_value for t in trades)
        avg_impact = total_impact / total_trade_value if total_trade_value > 0 else 0

        # Sort by priority (high first) then by absolute delta
        priority_order = {"high": 0, "normal": 1, "low": 2}
        trades.sort(key=lambda t: (priority_order.get(t.priority, 1), -abs(t.delta_weight_pct)))

        # Summary text
        buys = [t for t in trades if t.direction == "buy"]
        sells = [t for t in trades if t.direction == "sell"]
        summary = (
            f"Rebalance proposal: {len(buys)} buys, {len(sells)} sells, "
            f"turnover={total_turnover:.1f}%, avg impact={avg_impact:.1f}bps"
        )

        proposal = RebalanceProposal(
            run_id=run_id,
            trigger=trigger,
            trades=trades,
            total_turnover_pct=round(total_turnover, 2),
            estimated_total_impact_bps=round(avg_impact, 2),
            summary=summary,
        )

        logger.info("Rebalance: %s", summary)
        return proposal

    def needs_rebalance(
        self,
        target_weights: dict[str, float],
        current_weights: dict[str, float],
    ) -> bool:
        """Quick check: does the portfolio need rebalancing?"""
        drifts = self.check_drift(target_weights, current_weights)
        return len(drifts) > 0
