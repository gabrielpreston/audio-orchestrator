"""Generic result cache implementation for service responses.

This module provides an LRU cache for service results (transcripts, generations,
classifications) to avoid re-computing identical requests.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from typing import Any, Generic, TypeVar

from services.common.structured_logging import get_logger

T = TypeVar("T")  # Generic type for cached results


def generate_cache_key(*args: str) -> str:
    """Generate SHA256 cache key from string arguments.

    Args:
        *args: String arguments to hash (e.g., text, voice, speed)

    Returns:
        SHA256 hash as hexadecimal string
    """
    key_data = "|".join(str(arg) for arg in args)
    return hashlib.sha256(key_data.encode("utf-8")).hexdigest()


class ResultCache(Generic[T]):
    """LRU cache for service results with size and entry limits.

    Supports any result type T (bytes, dict, str, etc.) and provides
    LRU eviction based on both entry count and memory size.
    """

    def __init__(
        self,
        max_entries: int = 100,
        max_size_mb: int = 500,
        service_name: str = "service",
    ) -> None:
        """Initialize result cache.

        Args:
            max_entries: Maximum number of cache entries
            max_size_mb: Maximum cache size in megabytes
            service_name: Service name for logging
        """
        self._cache: OrderedDict[str, T] = OrderedDict()
        self.max_entries = max_entries
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.current_size_bytes = 0
        self.hits = 0
        self.misses = 0
        self._logger = get_logger(__name__, service_name=service_name)

        self._logger.info(
            "result_cache.initialized",
            service=service_name,
            max_entries=max_entries,
            max_size_mb=max_size_mb,
            message="Result cache initialized",
        )

    def get(self, key: str) -> T | None:
        """Get cached result, move to end (LRU).

        Args:
            key: Cache key (typically SHA256 hash)

        Returns:
            Cached result if found, None otherwise
        """
        if key in self._cache:
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self.hits += 1
            return self._cache[key]
        self.misses += 1
        return None

    def put(self, key: str, result: T) -> None:
        """Add to cache with LRU eviction.

        Args:
            key: Cache key (typically SHA256 hash)
            result: Result to cache
        """
        # Calculate result size (approximate)
        result_size = self._estimate_size(result)

        # Evict if at capacity (by entry count or size)
        while (
            len(self._cache) >= self.max_entries
            or self.current_size_bytes + result_size > self.max_size_bytes
        ):
            if not self._cache:
                break
            oldest_key, oldest_result = self._cache.popitem(last=False)
            oldest_size = self._estimate_size(oldest_result)
            self.current_size_bytes -= oldest_size
            self._logger.debug(
                "result_cache.evicted",
                key=oldest_key[:16] if len(oldest_key) > 16 else oldest_key,
                size_bytes=oldest_size,
            )

        # Add new entry
        self._cache[key] = result
        self.current_size_bytes += result_size

    def _estimate_size(self, result: T) -> int:
        """Estimate memory size of result.

        Args:
            result: Result to estimate size for

        Returns:
            Estimated size in bytes
        """
        if isinstance(result, bytes):
            return len(result)
        elif isinstance(result, str):
            return len(result.encode("utf-8"))
        elif isinstance(result, dict):
            # Rough estimate: sum of string/bytes values
            size = 0
            for v in result.values():
                if isinstance(v, bytes):
                    size += len(v)
                elif isinstance(v, str):
                    size += len(v.encode("utf-8"))
                elif isinstance(v, (list, dict)):
                    # Recursive estimate would be expensive, use fixed overhead
                    size += 100
            return size
        elif isinstance(result, (list, tuple)):
            # Rough estimate
            return sum(self._estimate_size(item) for item in result) if result else 0
        else:
            # Unknown type, use fixed overhead
            return 100

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics:
            - hits: Number of cache hits
            - misses: Number of cache misses
            - hit_rate: Cache hit rate (0.0 to 1.0)
            - size: Current number of entries
            - memory_mb: Current memory usage in MB
            - max_entries: Maximum entry limit
            - max_size_mb: Maximum memory limit
        """
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0.0
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "size": len(self._cache),
            "memory_mb": self.current_size_bytes / (1024 * 1024),
            "max_entries": self.max_entries,
            "max_size_mb": self.max_size_bytes / (1024 * 1024),
        }

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()
        self.current_size_bytes = 0
        self.hits = 0
        self.misses = 0
        self._logger.info(
            "result_cache.cleared",
            message="Result cache cleared",
        )
