"""Performance optimization utilities for audio orchestrator.

This module provides performance optimization tools including connection pooling,
caching, and optimized buffer management.
"""

from __future__ import annotations

import asyncio
import functools
import time
from typing import Any, TypeVar

import httpx
from services.common.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

# Performance constants based on profiling
OPTIMAL_CHUNK_SIZE_MS = 20  # 20ms chunks for low latency
BUFFER_SIZE_CHUNKS = 5  # 5 chunks = 100ms buffer
MAX_CONCURRENT_REQUESTS = 10
CONNECTION_POOL_SIZE = 5
REQUEST_TIMEOUT = 30.0


class ConnectionPool:
    """Optimized HTTP connection pool for service communication."""

    def __init__(
        self,
        base_url: str,
        pool_size: int = CONNECTION_POOL_SIZE,
        timeout: float = REQUEST_TIMEOUT,
    ):
        """Initialize connection pool.

        Args:
            base_url: Base URL for the service
            pool_size: Maximum number of connections in pool
            timeout: Request timeout in seconds
        """
        self.base_url = base_url
        self.pool_size = pool_size
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._logger = get_logger(__name__)

    async def __aenter__(self) -> httpx.AsyncClient:
        """Enter async context manager."""
        if self._client is None:
            limits = httpx.Limits(
                max_keepalive_connections=self.pool_size,
                max_connections=self.pool_size,
            )
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                limits=limits,
                timeout=self.timeout,
            )
            self._logger.info(
                "connection_pool.created",
                base_url=self.base_url,
                pool_size=self.pool_size,
            )
        return self._client

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager."""
        if self._client:
            await self._client.aclose()
            self._client = None


class ModelCache:
    """LRU cache for model loading to avoid repeated initialization."""

    def __init__(self, max_size: int = 3):
        """Initialize model cache.

        Args:
            max_size: Maximum number of models to cache
        """
        self.max_size = max_size
        self._cache: dict[str, Any] = {}
        self._access_times: dict[str, float] = {}
        self._logger = get_logger(__name__)

    def get(self, key: str) -> Any | None:
        """Get model from cache.

        Args:
            key: Cache key

        Returns:
            Cached model or None
        """
        if key in self._cache:
            self._access_times[key] = time.time()
            self._logger.debug("model_cache.hit", key=key)
            return self._cache[key]

        self._logger.debug("model_cache.miss", key=key)
        return None

    def put(self, key: str, model: Any) -> None:
        """Put model in cache.

        Args:
            key: Cache key
            model: Model to cache
        """
        # Evict least recently used if cache is full
        if len(self._cache) >= self.max_size and key not in self._cache:
            oldest_key = min(
                self._access_times.keys(), key=lambda k: self._access_times[k]
            )
            del self._cache[oldest_key]
            del self._access_times[oldest_key]
            self._logger.debug("model_cache.evicted", key=oldest_key)

        self._cache[key] = model
        self._access_times[key] = time.time()
        self._logger.debug("model_cache.stored", key=key)

    def clear(self) -> None:
        """Clear the cache."""
        self._cache.clear()
        self._access_times.clear()
        self._logger.info("model_cache.cleared")


def cached_model_loading(max_size: int = 3) -> Any:
    """Decorator to cache model loading.

    Args:
        max_size: Maximum number of models to cache

    Returns:
        Decorated function
    """
    cache = ModelCache(max_size)

    def decorator(func: Any) -> Any:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Create cache key from function name and arguments
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"

            # Try to get from cache
            cached_model = cache.get(cache_key)
            if cached_model is not None:
                return cached_model

            # Load model and cache it
            model = await func(*args, **kwargs)
            cache.put(cache_key, model)
            return model

        return wrapper

    return decorator


class OptimizedBuffer:
    """Optimized audio buffer with minimal memory copies."""

    def __init__(self, chunk_size_ms: int = OPTIMAL_CHUNK_SIZE_MS):
        """Initialize optimized buffer.

        Args:
            chunk_size_ms: Chunk size in milliseconds
        """
        self.chunk_size_ms = chunk_size_ms
        self.buffer_size_chunks = BUFFER_SIZE_CHUNKS
        self._buffer: list[bytes] = []
        self._total_size = 0
        self._logger = get_logger(__name__)

    def add_chunk(self, chunk: bytes) -> None:
        """Add audio chunk to buffer.

        Args:
            chunk: Audio chunk to add
        """
        self._buffer.append(chunk)
        self._total_size += len(chunk)

        # Maintain buffer size
        while len(self._buffer) > self.buffer_size_chunks:
            removed = self._buffer.pop(0)
            self._total_size -= len(removed)

    def get_ready_data(self) -> bytes:
        """Get ready audio data from buffer.

        Returns:
            Concatenated audio data
        """
        if not self._buffer:
            return b""

        # Concatenate all chunks efficiently
        result = b"".join(self._buffer)
        self._buffer.clear()
        self._total_size = 0
        return result

    def get_size(self) -> int:
        """Get current buffer size in bytes.

        Returns:
            Buffer size in bytes
        """
        return self._total_size

    def is_ready(self) -> bool:
        """Check if buffer has enough data.

        Returns:
            True if buffer is ready for processing
        """
        return len(self._buffer) >= self.buffer_size_chunks


async def profile_function(func: Any, *args: Any, **kwargs: Any) -> tuple[Any, float]:
    """Profile a function and return result with execution time.

    Args:
        func: Function to profile
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        Tuple of (result, execution_time_seconds)
    """
    start_time = time.perf_counter()
    if asyncio.iscoroutinefunction(func):
        result = await func(*args, **kwargs)
    else:
        result = func(*args, **kwargs)
    execution_time = time.perf_counter() - start_time
    return result, execution_time


def optimize_audio_processing(func: Any) -> Any:
    """Decorator to optimize audio processing functions.

    Args:
        func: Function to optimize

    Returns:
        Optimized function
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Run in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, func, *args, **kwargs)

    return wrapper
