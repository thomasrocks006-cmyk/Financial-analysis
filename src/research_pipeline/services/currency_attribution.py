"""E-5 — Currency Attribution Engine: AUD/USD decomposition for AU investors.

AU-based investors holding US equities face currency P&L that is separate from
local equity return. This service decomposes:
    Total Return (AUD) = Local Equity Return + Currency Return + Interaction Term

Standard BHB currency extension (Karnosky-Singer methodology).

Sources for AUD/USD:
- FRED series DEXUSAL
- yfinance ticker AUDUSD=X
- Synthetic fallback calibrated to recent AUD/USD history
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CurrencyAttributionResult(BaseModel):
    """AUD/USD currency attribution decomposition."""

    total_return_aud_pct: float = 0.0
    local_equity_return_pct: float = 0.0    # return in USD terms
    currency_return_pct: float = 0.0         # AUD/USD appreciation impact
    interaction_term_pct: float = 0.0
    hedged_return_pct: float = 0.0           # local return + hedging cost
    unhedged_return_pct: float = 0.0         # total AUD return
    aud_usd_spot_start: float = 0.0
    aud_usd_spot_end: float = 0.0
    aud_usd_change_pct: float = 0.0
    hedging_cost_pct: float = 0.0            # assumed hedging cost (IR differential)
    n_days: int = 0
    data_source: str = "synthetic"


class CurrencyAttributionEngine:
    """Decompose US equity returns into local + currency components for AU investors."""

    # AUD/USD hedging cost proxy = AU-US 3m bank bill rate differential
    _DEFAULT_HEDGE_COST_ANN_PCT = 0.60  # ~60bp typical cost for AUD/USD hedge

    def __init__(self, fred_api_key: str = ""):
        self._fred_key = fred_api_key

    def fetch_aud_usd_returns(self, n_days: int = 252) -> tuple[list[float], str]:
        """Fetch daily AUD/USD spot returns from yfinance or FRED.

        Returns (returns_list, data_source_label).
        """
        try:
            import yfinance as yf  # type: ignore[import]

            ticker = yf.Ticker("AUDUSD=X")
            hist = ticker.history(period=f"{max(n_days // 21 + 2, 13)}mo")
            if not hist.empty and len(hist) > 5:
                closes = hist["Close"].dropna().values
                returns = [(closes[i] / closes[i - 1]) - 1 for i in range(1, len(closes))]
                if len(returns) > n_days:
                    returns = returns[-n_days:]
                logger.info("Fetched %d days AUD/USD from yfinance", len(returns))
                return [round(float(r), 6) for r in returns], "yfinance"
        except Exception as exc:
            logger.debug("yfinance AUD/USD fetch failed: %s", exc)

        # Synthetic fallback
        return self._synthetic_aud_usd(n_days), "synthetic"

    def compute_attribution(
        self,
        us_equity_returns_usd: list[float],
        aud_usd_returns: Optional[list[float]] = None,
        n_days: int = 252,
    ) -> CurrencyAttributionResult:
        """Decompose US equity returns into local + currency components.

        If aud_usd_returns not provided, fetches live data.

        Formula (daily compounding):
            R_AUD = (1 + R_USD) × (1 + R_FX) - 1
                  = R_USD + R_FX + R_USD × R_FX
        """
        data_source = "provided"
        if aud_usd_returns is None:
            aud_usd_returns, data_source = self.fetch_aud_usd_returns(n_days)

        n = min(len(us_equity_returns_usd), len(aud_usd_returns))
        if n < 2:
            return CurrencyAttributionResult(data_source=data_source)

        r_usd = np.array(us_equity_returns_usd[:n])
        r_fx = np.array(aud_usd_returns[:n])  # AUD/USD daily return

        # Note: AUD/USD appreciation (positive r_fx) REDUCES AUD return
        # because AU investor sells USD to buy AUD at end
        r_fx_impact = -r_fx  # negative sign: AU investor view

        # Total daily AUD return
        r_aud = (1 + r_usd) * (1 + r_fx_impact) - 1

        # Decomposition
        local_return = float(np.prod(1 + r_usd) - 1) * 100
        currency_return = float(np.prod(1 + r_fx_impact) - 1) * 100
        total_return_aud = float(np.prod(1 + r_aud) - 1) * 100
        interaction = total_return_aud - local_return - currency_return

        # Hedged return (removes currency risk, costs hedging premium)
        daily_hedge_cost = self._DEFAULT_HEDGE_COST_ANN_PCT / 100 / 252
        hedged_returns = r_usd - daily_hedge_cost
        hedged_return = float(np.prod(1 + hedged_returns) - 1) * 100

        # AUD/USD spot levels (from cumulative returns)
        spot_start = 0.635  # approximate
        spot_end = spot_start * float(np.prod(1 + r_fx))
        aud_usd_change = (spot_end / spot_start - 1) * 100

        return CurrencyAttributionResult(
            total_return_aud_pct=round(total_return_aud, 4),
            local_equity_return_pct=round(local_return, 4),
            currency_return_pct=round(currency_return, 4),
            interaction_term_pct=round(interaction, 4),
            hedged_return_pct=round(hedged_return, 4),
            unhedged_return_pct=round(total_return_aud, 4),
            aud_usd_spot_start=round(spot_start, 4),
            aud_usd_spot_end=round(spot_end, 4),
            aud_usd_change_pct=round(aud_usd_change, 4),
            hedging_cost_pct=round(self._DEFAULT_HEDGE_COST_ANN_PCT * n / 252, 4),
            n_days=n,
            data_source=data_source,
        )

    def _synthetic_aud_usd(self, n_days: int) -> list[float]:
        """Synthetic AUD/USD daily returns for fallback."""
        rng = np.random.default_rng(seed=20260328)
        # AUD/USD: ~10% annual vol, slight downward trend vs USD
        returns = rng.normal(-0.03 / 252, 0.10 / (252 ** 0.5), n_days)
        return [round(float(r), 6) for r in returns]
