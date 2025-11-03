"""TTS result cache implementation for Bark service.

This module provides an LRU cache for TTS synthesis results to avoid
regenerating identical audio requests.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from services.common.structured_logging import get_logger

logger = get_logger(__name__)


class TTSCache:
    """LRU cache for TTS synthesis results."""

    def __init__(self, max_entries: int = 100, max_size_mb: int = 500) -> None:
        """Initialize TTS cache.

        Args:
            max_entries: Maximum number of cache entries
            max_size_mb: Maximum cache size in megabytes
        """
        self._cache: OrderedDict[str, tuple[bytes, str]] = OrderedDict()
        self.max_entries = max_entries
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.current_size_bytes = 0
        self.hits = 0
        self.misses = 0
        self._logger = get_logger(__name__, service_name="bark")

    def get(self, key: str) -> tuple[bytes, str] | None:
        """Get cached result, move to end (LRU).

        Args:
            key: Cache key (SHA256 hash)

        Returns:
            Tuple of (audio_bytes, engine_name) if found, None otherwise
        """
        if key in self._cache:
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self.hits += 1
            return self._cache[key]
        self.misses += 1
        return None

    def put(self, key: str, audio_bytes: bytes, engine: str) -> None:
        """Add to cache with LRU eviction.

        Args:
            key: Cache key (SHA256 hash)
            audio_bytes: Audio data to cache
            engine: Engine name (e.g., "bark")
        """
        # Evict if at capacity (by entry count or size)
        while (
            len(self._cache) >= self.max_entries
            or self.current_size_bytes + len(audio_bytes) > self.max_size_bytes
        ):
            if not self._cache:
                break
            oldest_key, (oldest_audio, _) = self._cache.popitem(last=False)
            self.current_size_bytes -= len(oldest_audio)
            self._logger.debug(
                "bark.cache_evicted",
                key=oldest_key[:16],
                size_bytes=len(oldest_audio),
            )

        # Add new entry
        self._cache[key] = (audio_bytes, engine)
        self.current_size_bytes += len(audio_bytes)

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
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
        self._logger.info("bark.cache_cleared")
