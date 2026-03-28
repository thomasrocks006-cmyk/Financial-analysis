"""E-3 — Hidden Markov Model Regime Detection.

Fits a 3-state HMM (bull / bear / sideways) on factor return history to
automatically detect the current market regime without relying solely on
LLM classification.

Uses `hmmlearn` if available; falls back to a deterministic volatility-based
classifier if hmmlearn is not installed (zero external-dep guarantee).
"""

from __future__ import annotations

import logging
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

RegimeLabel = Literal["bull", "bear", "sideways"]


class RegimeDetectionResult(BaseModel):
    """Output of the HMM regime detector."""

    regime: RegimeLabel = "sideways"
    regime_probability: float = 0.0
    state_probabilities: dict[str, float] = Field(default_factory=dict)
    n_observations: int = 0
    method: str = "hmmlearn"  # or "volatility_fallback"
    volatility_annualised_pct: float = 0.0
    trend_30d_pct: float = 0.0

    model_config = {"frozen": False}


class RegimeDetector:
    """Detect market regime from return history using HMM or volatility fallback."""

    def __init__(self, n_states: int = 3):
        self.n_states = n_states

    def detect(self, returns: list[float]) -> RegimeDetectionResult:
        """Fit HMM on return series and return current regime with probabilities."""
        if len(returns) < 30:
            return RegimeDetectionResult(
                regime="sideways",
                regime_probability=0.333,
                state_probabilities={"bull": 0.333, "bear": 0.333, "sideways": 0.333},
                n_observations=len(returns),
                method="insufficient_data",
            )

        arr = np.array(returns, dtype=float)

        try:
            return self._hmm_detect(arr)
        except Exception as exc:
            logger.debug("HMM fit failed (%s) — using volatility fallback", exc)
            return self._volatility_fallback(arr)

    def detect_from_portfolio(
        self,
        returns_dict: dict[str, list[float]],
        weights: dict[str, float] | None = None,
    ) -> RegimeDetectionResult:
        """Aggregate ticker returns into portfolio series, then detect regime."""
        if not returns_dict:
            return RegimeDetectionResult()

        tickers = list(returns_dict.keys())
        w: dict[str, float] = weights or {t: 1.0 / len(tickers) for t in tickers}

        n = min(len(v) for v in returns_dict.values())
        portfolio_returns = np.zeros(n)
        for t in tickers:
            wt = w.get(t, 1.0 / len(tickers))
            portfolio_returns += wt * np.array(returns_dict[t][:n])

        return self.detect(portfolio_returns.tolist())

    def _hmm_detect(self, arr: np.ndarray) -> RegimeDetectionResult:
        from hmmlearn import hmm  # type: ignore[import]

        obs = arr.reshape(-1, 1)
        model = hmm.GaussianHMM(
            n_components=self.n_states,
            covariance_type="full",
            n_iter=100,
            random_state=42,
        )
        model.fit(obs)

        # Predict the most likely state sequence
        _, states = model.decode(obs, algorithm="viterbi")
        current_state = int(states[-1])

        # Get posterior probabilities for the last observation
        posteriors = model.predict_proba(obs)
        last_posterior = posteriors[-1]

        # Classify states by mean return: bull=highest, bear=lowest, sideways=middle
        means = [float(model.means_[i][0]) for i in range(self.n_states)]
        sorted_idx = np.argsort(means)  # ascending
        # sorted_idx[0] = bear (lowest mean), [-1] = bull (highest)
        label_map: dict[int, RegimeLabel] = {
            int(sorted_idx[0]): "bear",
            int(sorted_idx[-1]): "bull",
        }
        if self.n_states >= 3:
            label_map[int(sorted_idx[1])] = "sideways"

        current_label: RegimeLabel = label_map.get(current_state, "sideways")
        current_prob = float(last_posterior[current_state])

        state_probs: dict[str, float] = {}
        for idx, label in label_map.items():
            state_probs[label] = float(last_posterior[idx])

        vol_ann = float(np.std(arr) * np.sqrt(252) * 100)
        trend_30d = float(np.mean(arr[-30:]) * 252 * 100) if len(arr) >= 30 else 0.0

        return RegimeDetectionResult(
            regime=current_label,
            regime_probability=round(current_prob, 4),
            state_probabilities={k: round(v, 4) for k, v in state_probs.items()},
            n_observations=len(arr),
            method="hmmlearn",
            volatility_annualised_pct=round(vol_ann, 2),
            trend_30d_pct=round(trend_30d, 2),
        )

    def _volatility_fallback(self, arr: np.ndarray) -> RegimeDetectionResult:
        """Simple volatility + momentum heuristic when HMM is unavailable."""
        vol_ann = float(np.std(arr) * np.sqrt(252) * 100)
        trend_30d = float(np.mean(arr[-30:]) * 252 * 100) if len(arr) >= 30 else 0.0
        trend_90d = float(np.mean(arr[-90:]) * 252 * 100) if len(arr) >= 90 else trend_30d

        # Regime classification thresholds
        HIGH_VOL = 30.0   # annualised % — above = bear/stress
        MED_VOL = 15.0
        BULL_THRESH = 5.0  # 30d trend > 5% annualised
        BEAR_THRESH = -5.0

        if vol_ann > HIGH_VOL or trend_30d < BEAR_THRESH:
            regime: RegimeLabel = "bear"
            prob = min(0.90, 0.5 + (vol_ann - HIGH_VOL) / 50)
        elif vol_ann < MED_VOL and trend_30d > BULL_THRESH:
            regime = "bull"
            prob = min(0.85, 0.5 + (trend_30d - BULL_THRESH) / 20)
        else:
            regime = "sideways"
            prob = 0.60

        return RegimeDetectionResult(
            regime=regime,
            regime_probability=round(prob, 4),
            state_probabilities={
                "bull": round(prob if regime == "bull" else (1 - prob) / 2, 4),
                "bear": round(prob if regime == "bear" else (1 - prob) / 2, 4),
                "sideways": round(prob if regime == "sideways" else (1 - prob) / 2, 4),
            },
            n_observations=len(arr),
            method="volatility_fallback",
            volatility_annualised_pct=round(vol_ann, 2),
            trend_30d_pct=round(trend_30d, 2),
        )
