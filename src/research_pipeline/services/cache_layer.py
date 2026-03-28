"""Cache Layer — API response caching with TTL for market data and LLM calls."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class CacheLayer:
    """Simple file-backed cache with TTL.

    Caches API responses (market data, LLM outputs) to avoid redundant calls
    within a session or across short time windows.
    """

    def __init__(
        self,
        cache_dir: Path | str = ".cache/pipeline",
        default_ttl_seconds: int = 3600,
        max_entries: int = 10_000,
    ):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_ttl = default_ttl_seconds
        self.max_entries = max_entries
        self._stats = {"hits": 0, "misses": 0, "sets": 0, "evictions": 0}

    @staticmethod
    def _make_key(namespace: str, identifier: str) -> str:
        """Generate a deterministic cache key."""
        raw = f"{namespace}:{identifier}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, namespace: str, identifier: str) -> Optional[Any]:
        """Retrieve a cached value if it exists and hasn't expired."""
        key = self._make_key(namespace, identifier)
        path = self._cache_path(key)

        if not path.exists():
            self._stats["misses"] += 1
            return None

        try:
            data = json.loads(path.read_text())
            expires_at = data.get("expires_at", 0)
            if time.time() > expires_at:
                path.unlink(missing_ok=True)
                self._stats["misses"] += 1
                logger.debug("Cache expired: %s:%s", namespace, identifier)
                return None

            self._stats["hits"] += 1
            logger.debug("Cache hit: %s:%s", namespace, identifier)
            return data.get("value")
        except (json.JSONDecodeError, KeyError):
            path.unlink(missing_ok=True)
            self._stats["misses"] += 1
            return None

    def set(
        self, namespace: str, identifier: str, value: Any, ttl_seconds: int | None = None
    ) -> None:
        """Store a value in the cache with TTL."""
        key = self._make_key(namespace, identifier)
        path = self._cache_path(key)
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl

        data = {
            "namespace": namespace,
            "identifier": identifier,
            "value": value,
            "created_at": time.time(),
            "expires_at": time.time() + ttl,
        }

        try:
            path.write_text(json.dumps(data, indent=2, default=str))
            self._stats["sets"] += 1
            logger.debug("Cache set: %s:%s (TTL=%ds)", namespace, identifier, ttl)
        except (OSError, TypeError) as e:
            logger.warning("Cache write failed for %s:%s — %s", namespace, identifier, e)

    def invalidate(self, namespace: str, identifier: str) -> bool:
        """Remove a specific cache entry."""
        key = self._make_key(namespace, identifier)
        path = self._cache_path(key)
        if path.exists():
            path.unlink()
            return True
        return False

    def clear_namespace(self, namespace: str) -> int:
        """Clear all entries in a namespace."""
        count = 0
        for path in self.cache_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                if data.get("namespace") == namespace:
                    path.unlink()
                    count += 1
            except (json.JSONDecodeError, KeyError):
                continue
        logger.info("Cleared %d entries from namespace %s", count, namespace)
        return count

    def clear_expired(self) -> int:
        """Remove all expired entries."""
        now = time.time()
        count = 0
        for path in self.cache_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                if now > data.get("expires_at", 0):
                    path.unlink()
                    count += 1
                    self._stats["evictions"] += 1
            except (json.JSONDecodeError, KeyError):
                path.unlink(missing_ok=True)
                count += 1
        logger.info("Cleared %d expired cache entries", count)
        return count

    def clear_all(self) -> int:
        """Clear entire cache."""
        count = 0
        for path in self.cache_dir.glob("*.json"):
            path.unlink()
            count += 1
        self._stats = {"hits": 0, "misses": 0, "sets": 0, "evictions": 0}
        return count

    @property
    def stats(self) -> dict[str, int]:
        """Cache hit/miss statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        return {
            **self._stats,
            "total_requests": total,
            "hit_rate_pct": round(self._stats["hits"] / total * 100, 1) if total > 0 else 0,
        }

    @property
    def size(self) -> int:
        """Number of entries currently in cache."""
        return len(list(self.cache_dir.glob("*.json")))


class QuotaManager:
    """API quota tracking per run and globally.

    Tracks API calls (FMP, Finnhub, Anthropic, OpenAI) and enforces
    per-run budgets to prevent runaway costs.
    """

    # Default quotas per run
    DEFAULT_QUOTAS: dict[str, int] = {
        "fmp_api": 500,
        "finnhub_api": 300,
        "anthropic_tokens": 500_000,
        "openai_tokens": 200_000,
    }

    def __init__(self, quotas: dict[str, int] | None = None):
        self.quotas = quotas or dict(self.DEFAULT_QUOTAS)
        self._usage: dict[str, dict[str, int]] = {}  # run_id -> {provider -> count}

    def track_usage(self, run_id: str, provider: str, count: int = 1) -> None:
        """Record API usage for a provider."""
        if run_id not in self._usage:
            self._usage[run_id] = {}
        current = self._usage[run_id].get(provider, 0)
        self._usage[run_id][provider] = current + count

    def check_quota(self, run_id: str, provider: str) -> tuple[bool, int]:
        """Check if a provider is within quota.

        Returns (is_within_quota, remaining).
        """
        limit = self.quotas.get(provider, float("inf"))
        used = self._usage.get(run_id, {}).get(provider, 0)
        remaining = max(0, limit - used)
        return remaining > 0, remaining

    def get_usage(self, run_id: str) -> dict[str, Any]:
        """Get usage summary for a run."""
        usage = self._usage.get(run_id, {})
        result: dict[str, Any] = {}
        for provider in self.quotas:
            used = usage.get(provider, 0)
            limit = self.quotas[provider]
            result[provider] = {
                "used": used,
                "limit": limit,
                "remaining": max(0, limit - used),
                "utilization_pct": round(used / limit * 100, 1) if limit > 0 else 0,
            }
        return result

    def reset_run(self, run_id: str) -> None:
        """Reset usage counters for a specific run."""
        self._usage.pop(run_id, None)
