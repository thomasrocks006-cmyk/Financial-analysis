"""Portfolio Optimisation Engine — mean-variance, Black-Litterman, risk parity."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class OptimisationResult:
    """Output from a portfolio optimisation."""
    method: str  # "min_variance", "max_sharpe", "risk_parity", "black_litterman"
    weights: dict[str, float]
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    risk_contributions: dict[str, float] = field(default_factory=dict)


@dataclass
class BlackLittermanInputs:
    """Inputs for Black-Litterman model."""
    market_cap_weights: dict[str, float]  # equilibrium weights
    views: dict[str, float]  # ticker -> expected excess return
    view_confidences: dict[str, float]  # ticker -> confidence (0-1)
    risk_aversion: float = 2.5
    tau: float = 0.05


class PortfolioOptimisationEngine:
    """Deterministic portfolio optimisation — no LLM.

    Supports:
    - Minimum variance portfolio
    - Maximum Sharpe ratio portfolio
    - Risk parity (equal risk contribution)
    - Black-Litterman combined weights
    """

    def compute_minimum_variance(
        self,
        tickers: list[str],
        returns: dict[str, list[float]],
        max_weight: float = 0.15,
        min_weight: float = 0.02,
    ) -> OptimisationResult:
        """Find the minimum variance portfolio using analytical solution."""
        n = len(tickers)
        if n == 0:
            return OptimisationResult(method="min_variance", weights={})

        min_len = min(len(returns.get(t, [])) for t in tickers)
        if min_len < 10:
            # Fallback to equal weight
            w = 1.0 / n
            return OptimisationResult(
                method="min_variance",
                weights={t: round(w * 100, 2) for t in tickers},
            )

        data = np.array([returns[t][:min_len] for t in tickers])
        cov = np.cov(data)

        # Analytical minimum variance: w = Σ^-1 * 1 / (1' Σ^-1 1)
        try:
            cov_inv = np.linalg.inv(cov)
        except np.linalg.LinAlgError:
            cov_inv = np.linalg.pinv(cov)

        ones = np.ones(n)
        raw_weights = cov_inv @ ones
        raw_weights = raw_weights / raw_weights.sum()

        # Apply constraints
        weights = np.clip(raw_weights, min_weight, max_weight)
        weights = weights / weights.sum()

        # Compute portfolio stats
        port_var = float(weights @ cov @ weights)
        port_vol = float(np.sqrt(port_var)) * np.sqrt(252)
        mean_returns = np.mean(data, axis=1)
        port_ret = float(weights @ mean_returns) * 252

        sharpe = port_ret / port_vol if port_vol > 0 else 0

        # Risk contributions
        marginal = cov @ weights
        risk_contrib = {}
        for i, t in enumerate(tickers):
            rc = float(weights[i] * marginal[i]) / port_var if port_var > 0 else 0
            risk_contrib[t] = round(rc * 100, 2)

        return OptimisationResult(
            method="min_variance",
            weights={t: round(float(weights[i]) * 100, 2) for i, t in enumerate(tickers)},
            expected_return=round(port_ret * 100, 2),
            expected_volatility=round(port_vol * 100, 2),
            sharpe_ratio=round(sharpe, 4),
            risk_contributions=risk_contrib,
        )

    def compute_max_sharpe(
        self,
        tickers: list[str],
        returns: dict[str, list[float]],
        risk_free_rate: float = 0.045,
        max_weight: float = 0.15,
        min_weight: float = 0.02,
    ) -> OptimisationResult:
        """Find the maximum Sharpe ratio portfolio."""
        n = len(tickers)
        if n == 0:
            return OptimisationResult(method="max_sharpe", weights={})

        min_len = min(len(returns.get(t, [])) for t in tickers)
        if min_len < 10:
            w = 1.0 / n
            return OptimisationResult(
                method="max_sharpe",
                weights={t: round(w * 100, 2) for t in tickers},
            )

        data = np.array([returns[t][:min_len] for t in tickers])
        cov = np.cov(data)
        mu = np.mean(data, axis=1) * 252
        rf_daily = risk_free_rate
        excess = mu - rf_daily

        try:
            cov_inv = np.linalg.inv(cov * 252)
        except np.linalg.LinAlgError:
            cov_inv = np.linalg.pinv(cov * 252)

        raw_weights = cov_inv @ excess
        if raw_weights.sum() != 0:
            raw_weights = raw_weights / raw_weights.sum()
        else:
            raw_weights = np.ones(n) / n

        # Clip negative weights to minimum
        weights = np.clip(raw_weights, min_weight, max_weight)
        weights = weights / weights.sum()

        port_ret = float(weights @ mu)
        port_vol = float(np.sqrt(weights @ (cov * 252) @ weights))
        sharpe = (port_ret - risk_free_rate) / port_vol if port_vol > 0 else 0

        return OptimisationResult(
            method="max_sharpe",
            weights={t: round(float(weights[i]) * 100, 2) for i, t in enumerate(tickers)},
            expected_return=round(port_ret * 100, 2),
            expected_volatility=round(port_vol * 100, 2),
            sharpe_ratio=round(sharpe, 4),
        )

    def compute_risk_parity(
        self,
        tickers: list[str],
        returns: dict[str, list[float]],
        max_iterations: int = 1000,
        tolerance: float = 1e-8,
    ) -> OptimisationResult:
        """Compute equal risk contribution (risk parity) weights."""
        n = len(tickers)
        if n == 0:
            return OptimisationResult(method="risk_parity", weights={})

        min_len = min(len(returns.get(t, [])) for t in tickers)
        if min_len < 10:
            w = 1.0 / n
            return OptimisationResult(
                method="risk_parity",
                weights={t: round(w * 100, 2) for t in tickers},
            )

        data = np.array([returns[t][:min_len] for t in tickers])
        cov = np.cov(data)

        # Iterative risk parity via inverse vol as starting point
        vols = np.sqrt(np.diag(cov))
        weights = (1.0 / vols) / np.sum(1.0 / vols)

        target_rc = 1.0 / n

        for _ in range(max_iterations):
            port_var = float(weights @ cov @ weights)
            if port_var == 0:
                break
            marginal = cov @ weights
            rc = weights * marginal / port_var

            # Adjust weights to equalize risk contribution
            adjustment = target_rc / (rc + 1e-12)
            weights = weights * adjustment
            weights = weights / weights.sum()

            if np.max(np.abs(rc - target_rc)) < tolerance:
                break

        port_var = float(weights @ cov @ weights)
        port_vol = float(np.sqrt(port_var)) * np.sqrt(252)
        port_ret = float(weights @ np.mean(data, axis=1)) * 252

        risk_contrib = {}
        marginal = cov @ weights
        for i, t in enumerate(tickers):
            rc = float(weights[i] * marginal[i]) / port_var if port_var > 0 else 0
            risk_contrib[t] = round(rc * 100, 2)

        return OptimisationResult(
            method="risk_parity",
            weights={t: round(float(weights[i]) * 100, 2) for i, t in enumerate(tickers)},
            expected_return=round(port_ret * 100, 2),
            expected_volatility=round(port_vol * 100, 2),
            risk_contributions=risk_contrib,
        )

    def compute_black_litterman(
        self,
        tickers: list[str],
        returns: dict[str, list[float]],
        bl_inputs: BlackLittermanInputs,
    ) -> OptimisationResult:
        """Compute Black-Litterman combined weights.

        Blends market equilibrium with analyst views.
        """
        n = len(tickers)
        if n == 0:
            return OptimisationResult(method="black_litterman", weights={})

        min_len = min(len(returns.get(t, [])) for t in tickers)
        if min_len < 10:
            return OptimisationResult(
                method="black_litterman",
                weights={t: round(bl_inputs.market_cap_weights.get(t, 100 / n), 2) for t in tickers},
            )

        data = np.array([returns[t][:min_len] for t in tickers])
        cov = np.cov(data) * 252  # annualized

        # Equilibrium excess returns: π = δΣw_mkt
        w_mkt = np.array([bl_inputs.market_cap_weights.get(t, 1.0 / n) / 100 for t in tickers])
        w_mkt = w_mkt / w_mkt.sum()
        pi = bl_inputs.risk_aversion * cov @ w_mkt

        # Build views matrix P and view vector Q
        view_tickers = [t for t in tickers if t in bl_inputs.views]
        if not view_tickers:
            # No views — return equilibrium weights
            return OptimisationResult(
                method="black_litterman",
                weights={t: round(float(w_mkt[i]) * 100, 2) for i, t in enumerate(tickers)},
            )

        k = len(view_tickers)
        P = np.zeros((k, n))
        Q = np.zeros(k)
        omega_diag = np.zeros(k)

        for j, vt in enumerate(view_tickers):
            idx = tickers.index(vt)
            P[j, idx] = 1.0
            Q[j] = bl_inputs.views[vt]
            conf = bl_inputs.view_confidences.get(vt, 0.5)
            omega_diag[j] = (1 - conf) / conf * bl_inputs.tau * cov[idx, idx]

        Omega = np.diag(omega_diag)
        tau_cov = bl_inputs.tau * cov

        # BL posterior: μ_BL = [(τΣ)^-1 + P'Ω^-1P]^-1 [(τΣ)^-1π + P'Ω^-1Q]
        try:
            tau_cov_inv = np.linalg.inv(tau_cov)
            omega_inv = np.linalg.inv(Omega)
        except np.linalg.LinAlgError:
            tau_cov_inv = np.linalg.pinv(tau_cov)
            omega_inv = np.linalg.pinv(Omega)

        M = tau_cov_inv + P.T @ omega_inv @ P
        try:
            M_inv = np.linalg.inv(M)
        except np.linalg.LinAlgError:
            M_inv = np.linalg.pinv(M)

        mu_bl = M_inv @ (tau_cov_inv @ pi + P.T @ omega_inv @ Q)

        # Optimal weights from BL expected returns
        try:
            cov_inv = np.linalg.inv(cov)
        except np.linalg.LinAlgError:
            cov_inv = np.linalg.pinv(cov)

        raw_weights = (1 / bl_inputs.risk_aversion) * cov_inv @ mu_bl
        raw_weights = np.clip(raw_weights, 0.02, 0.15)
        raw_weights = raw_weights / raw_weights.sum()

        port_ret = float(raw_weights @ mu_bl * 100)
        port_vol = float(np.sqrt(raw_weights @ cov @ raw_weights) * 100)
        sharpe = (port_ret / 100) / (port_vol / 100) if port_vol > 0 else 0

        return OptimisationResult(
            method="black_litterman",
            weights={t: round(float(raw_weights[i]) * 100, 2) for i, t in enumerate(tickers)},
            expected_return=round(port_ret, 2),
            expected_volatility=round(port_vol, 2),
            sharpe_ratio=round(sharpe, 4),
        )
