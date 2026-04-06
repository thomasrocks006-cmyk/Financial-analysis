"""Position Sizing Engine — convert conviction signals and risk budgets into weights."""

from __future__ import annotations

import logging
from typing import Any


logger = logging.getLogger(__name__)


class PositionSizingEngine:
    """Translate conviction scores and risk budgets into portfolio weights — no LLM.

    Supports multiple sizing methods:
    - Equal weight
    - Conviction-weighted
    - Risk-budget weighted
    - Inverse volatility
    - Fixed max-position constraint
    """

    def __init__(
        self,
        max_position_pct: float = 15.0,
        min_position_pct: float = 1.0,
        target_position_count: int = 15,
    ):
        self.max_position = max_position_pct
        self.min_position = min_position_pct
        self.target_count = target_position_count

    def equal_weight(self, tickers: list[str]) -> dict[str, float]:
        """Simple equal weight across all positions."""
        n = len(tickers)
        if n == 0:
            return {}
        weight = round(100.0 / n, 4)
        return {t: weight for t in tickers}

    def conviction_weighted(
        self,
        conviction_scores: dict[str, float],
        scale_factor: float = 1.0,
    ) -> dict[str, float]:
        """Weight positions proportional to conviction scores.

        Args:
            conviction_scores: {ticker: score} where higher = more conviction
            scale_factor: amplify/dampen conviction signal (>1 = more concentrated)
        """
        if not conviction_scores:
            return {}

        # Ensure all scores are positive
        min_score = min(conviction_scores.values())
        shifted = {t: (s - min_score + 1) ** scale_factor for t, s in conviction_scores.items()}

        total = sum(shifted.values())
        if total <= 0:
            return self.equal_weight(list(conviction_scores.keys()))

        raw_weights = {t: (v / total) * 100 for t, v in shifted.items()}
        return self._apply_constraints(raw_weights)

    def inverse_volatility(
        self,
        volatilities: dict[str, float],
    ) -> dict[str, float]:
        """Weight inversely proportional to volatility (lower vol = higher weight)."""
        if not volatilities:
            return {}

        inv_vols = {}
        for ticker, vol in volatilities.items():
            if vol > 0:
                inv_vols[ticker] = 1.0 / vol
            else:
                inv_vols[ticker] = 1.0

        total = sum(inv_vols.values())
        raw_weights = {t: (v / total) * 100 for t, v in inv_vols.items()}
        return self._apply_constraints(raw_weights)

    def risk_budget_weighted(
        self,
        conviction_scores: dict[str, float],
        volatilities: dict[str, float],
        risk_budget_pct: float = 100.0,
    ) -> dict[str, float]:
        """Combine conviction with volatility to allocate risk budget.

        Higher conviction + lower volatility = larger position.
        """
        tickers = list(set(conviction_scores.keys()) & set(volatilities.keys()))
        if not tickers:
            return {}

        composite_scores: dict[str, float] = {}
        for ticker in tickers:
            conv = conviction_scores.get(ticker, 0)
            vol = volatilities.get(ticker, 1)
            # Composite: conviction / volatility (risk-adjusted conviction)
            composite_scores[ticker] = conv / vol if vol > 0 else conv

        # Normalize to risk budget
        min_score = min(composite_scores.values())
        shifted = {t: s - min_score + 0.1 for t, s in composite_scores.items()}
        total = sum(shifted.values())

        raw_weights = {t: (v / total) * risk_budget_pct for t, v in shifted.items()}
        return self._apply_constraints(raw_weights)

    def from_optimisation(
        self,
        optimal_weights: dict[str, float],
    ) -> dict[str, float]:
        """Apply position constraints to optimizer output weights."""
        return self._apply_constraints({t: w * 100 for t, w in optimal_weights.items()})

    def _apply_constraints(self, weights: dict[str, float]) -> dict[str, float]:
        """Apply min/max position constraints iteratively.

        Clips positions to [min_position, max_position] and redistributes
        the excess to remaining unconstrained positions.
        """
        if not weights:
            return {}

        result = dict(weights)
        max_iterations = 10

        for _ in range(max_iterations):
            changed = False
            excess = 0.0
            unconstrained = []

            for ticker in result:
                if result[ticker] > self.max_position:
                    excess += result[ticker] - self.max_position
                    result[ticker] = self.max_position
                    changed = True
                elif result[ticker] < self.min_position and result[ticker] > 0:
                    excess -= self.min_position - result[ticker]
                    result[ticker] = self.min_position
                    changed = True
                else:
                    unconstrained.append(ticker)

            # Redistribute excess to unconstrained positions
            if excess != 0 and unconstrained:
                per_position = excess / len(unconstrained)
                for ticker in unconstrained:
                    result[ticker] += per_position

            if not changed:
                break

        # Final normalization to 100%
        total = sum(result.values())
        if total > 0 and abs(total - 100) > 0.01:
            scale = 100.0 / total
            result = {t: round(w * scale, 4) for t, w in result.items()}
        else:
            result = {t: round(w, 4) for t, w in result.items()}

        return result

    def size_portfolio(
        self,
        tickers: list[str],
        method: str = "equal",
        conviction_scores: dict[str, float] | None = None,
        volatilities: dict[str, float] | None = None,
        **kwargs: Any,
    ) -> dict[str, float]:
        """Dispatch to the appropriate sizing method.

        Args:
            tickers: Universe of tickers to size
            method: "equal", "conviction", "inverse_vol", "risk_budget"
            conviction_scores: Required for conviction/risk_budget methods
            volatilities: Required for inverse_vol/risk_budget methods
        """
        if method == "equal":
            return self.equal_weight(tickers)
        elif method == "conviction" and conviction_scores:
            return self.conviction_weighted(conviction_scores, **kwargs)
        elif method == "inverse_vol" and volatilities:
            return self.inverse_volatility(volatilities)
        elif method == "risk_budget" and conviction_scores and volatilities:
            return self.risk_budget_weighted(conviction_scores, volatilities, **kwargs)
        else:
            logger.warning(
                "Unknown sizing method '%s' or missing data — falling back to equal weight", method
            )
            return self.equal_weight(tickers)
