"""Live Return Store — fetch historical daily returns via yfinance.

Falls back gracefully to an empty dict so callers can degrade to synthetic data
when the network is unavailable or a ticker is unlisted.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_PERIOD = "1y"  # 252 trading days typical


class LiveReturnStore:
    """Fetch and cache historical adjusted-close daily returns via yfinance.

    Usage::

        store = LiveReturnStore()
        returns = store.fetch(["NVDA", "AMD"], period="1y")
        # returns = {"NVDA": [0.012, -0.003, ...], "AMD": [...]}

    Returned lists contain daily *percentage* returns (not log returns).
    Results are cached in-memory for the lifetime of the instance.
    A failed ticker is silently absent from the returned dict; the caller is
    responsible for graceful fallback.
    """

    def __init__(self) -> None:
        self._cache: dict[str, list[float]] = {}
        self._fetch_timestamp: Optional[datetime] = None
        self._cached_period: Optional[str] = None

    # ── Public API ────────────────────────────────────────────────────────

    def fetch(
        self,
        tickers: list[str],
        period: str = _DEFAULT_PERIOD,
        force_refresh: bool = False,
    ) -> dict[str, list[float]]:
        """Return daily percentage returns for each ticker.

        Args:
            tickers:       List of ticker symbols (e.g. ["NVDA", "AMD"]).
            period:        yfinance period string ("1y", "2y", "6mo", etc.).
            force_refresh: Bypass the in-memory cache.

        Returns:
            Mapping of ticker → list of float daily returns (as percentage).
            Tickers that fail to fetch are absent from the dict.
        """
        missing = [t for t in tickers if t not in self._cache or force_refresh]
        if missing:
            fetched = self._download(missing, period)
            self._cache.update(fetched)
            if fetched:
                self._fetch_timestamp = datetime.now(timezone.utc)
                self._cached_period = period

        result = {t: self._cache[t] for t in tickers if t in self._cache}
        logger.info(
            "LiveReturnStore.fetch — requested=%d returned=%d period=%s",
            len(tickers),
            len(result),
            period,
        )
        return result

    def clear_cache(self) -> None:
        """Invalidate the in-memory cache."""
        self._cache.clear()
        self._fetch_timestamp = None
        self._cached_period = None

    @property
    def cache_size(self) -> int:
        return len(self._cache)

    @property
    def last_fetched_at(self) -> Optional[datetime]:
        return self._fetch_timestamp

    # ── Internal ──────────────────────────────────────────────────────────

    def _download(self, tickers: list[str], period: str) -> dict[str, list[float]]:
        """Download adjusted close prices and convert to daily returns."""
        try:
            import yfinance as yf  # optional dependency
        except ImportError:
            logger.warning(
                "yfinance not installed — LiveReturnStore unavailable; "
                "install with: pip install yfinance"
            )
            return {}

        result: dict[str, list[float]] = {}
        try:
            if len(tickers) == 1:
                data = yf.download(
                    tickers[0],
                    period=period,
                    auto_adjust=True,
                    progress=False,
                    threads=False,
                )
                closes = data.get("Close") if data is not None and not data.empty else None
                if closes is not None and len(closes) >= 2:
                    pct = closes.pct_change().dropna() * 100
                    result[tickers[0]] = [round(float(v), 6) for v in pct.tolist()]
            else:
                data = yf.download(
                    tickers,
                    period=period,
                    auto_adjust=True,
                    progress=False,
                    threads=True,
                )
                if data is None or data.empty:
                    return {}
                closes = data.get("Close")
                if closes is None:
                    return {}
                # Multi-ticker download has MultiIndex columns or flat columns
                for ticker in tickers:
                    try:
                        series = closes[ticker] if ticker in closes.columns else None
                        if series is None or len(series) < 2:
                            continue
                        pct = series.pct_change().dropna() * 100
                        result[ticker] = [round(float(v), 6) for v in pct.dropna().tolist()]
                    except Exception as exc:
                        logger.debug("Could not extract returns for %s: %s", ticker, exc)
        except Exception as exc:
            logger.warning("yfinance download failed: %s", exc)

        success = list(result.keys())
        failed = [t for t in tickers if t not in result]
        if success:
            logger.info("LiveReturnStore fetched %d tickers: %s", len(success), success)
        if failed:
            logger.warning("LiveReturnStore failed for %d tickers: %s", len(failed), failed)
        return result
