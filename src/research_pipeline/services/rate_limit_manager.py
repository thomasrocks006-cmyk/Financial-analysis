"""
RateLimitBudgetManager — centralised multi-API quota tracking.
"""
import logging
from pydantic import BaseModel, Field
from typing import Optional

logger = logging.getLogger(__name__)

DEGRADATION_ORDER = [
    "sec_api", "benzinga", "news_api", "fmp", "finnhub", "yfinance",
    "eia", "ferc", "asx", "wsts",
]


class ServiceQuotaConfig(BaseModel):
    service_name: str
    daily_limit: Optional[int] = None
    per_minute_limit: Optional[int] = None
    current_day_usage: int = 0
    current_minute_usage: int = 0
    fallback_service: Optional[str] = None
    exhausted: bool = False


class RateLimitBudgetManager:
    """
    Centralised multi-API quota tracking and graceful degradation.
    All service wrappers call check_quota() before making API requests.
    """

    DEFAULT_CONFIGS: dict[str, dict] = {
        "sec_api":  {"daily_limit": 100,  "per_minute_limit": 10, "fallback_service": "fmp"},
        "benzinga": {"daily_limit": 500,  "per_minute_limit": 20, "fallback_service": "fmp"},
        "news_api": {"daily_limit": 100,  "per_minute_limit": 10, "fallback_service": None},
        "fmp":      {"daily_limit": 250,  "per_minute_limit": 30, "fallback_service": "finnhub"},
        "finnhub":  {"daily_limit": 60,   "per_minute_limit": 30, "fallback_service": "yfinance"},
        "yfinance": {"daily_limit": None, "per_minute_limit": None, "fallback_service": None},
        "eia":      {"daily_limit": None, "per_minute_limit": 5,  "fallback_service": None},
        "ferc":     {"daily_limit": None, "per_minute_limit": 5,  "fallback_service": None},
        "asx":      {"daily_limit": None, "per_minute_limit": 10, "fallback_service": None},
        "wsts":     {"daily_limit": None, "per_minute_limit": 2,  "fallback_service": None},
    }

    def __init__(self) -> None:
        self._services: dict[str, ServiceQuotaConfig] = {}
        for name, cfg in self.DEFAULT_CONFIGS.items():
            self._services[name] = ServiceQuotaConfig(service_name=name, **cfg)

    def check_quota(self, service_name: str) -> bool:
        """Return True if service can be called, False if quota exhausted."""
        svc = self._services.get(service_name)
        if svc is None:
            return True  # Unknown service — allow
        if svc.exhausted:
            logger.warning("RateLimitBudgetManager: %s quota exhausted", service_name)
            return False
        if svc.daily_limit and svc.current_day_usage >= svc.daily_limit:
            svc.exhausted = True
            logger.warning(
                "RateLimitBudgetManager: %s daily limit reached (%d)",
                service_name,
                svc.daily_limit,
            )
            return False
        return True

    def record_usage(self, service_name: str, count: int = 1) -> None:
        svc = self._services.get(service_name)
        if svc:
            svc.current_day_usage += count
            svc.current_minute_usage += count

    def get_fallback(self, service_name: str) -> Optional[str]:
        svc = self._services.get(service_name)
        return svc.fallback_service if svc else None

    def get_budget_summary(self) -> dict[str, dict]:
        return {
            name: {
                "usage": svc.current_day_usage,
                "limit": svc.daily_limit,
                "exhausted": svc.exhausted,
            }
            for name, svc in self._services.items()
        }

    def reset_daily(self) -> None:
        """Call at start of each day to reset counters."""
        for svc in self._services.values():
            svc.current_day_usage = 0
            svc.current_minute_usage = 0
            svc.exhausted = False
