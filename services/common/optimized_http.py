"""Optimized HTTP client with connection pooling and performance improvements.

This module provides an optimized HTTP client that implements connection pooling,
request batching, and performance monitoring.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
from services.common.structured_logging import get_logger
from services.common.performance import ConnectionPool, profile_function

logger = get_logger(__name__)


class OptimizedHTTPClient:
    """Optimized HTTP client with connection pooling and performance monitoring."""

    def __init__(
        self,
        base_url: str,
        pool_size: int = 5,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        """Initialize optimized HTTP client.

        Args:
            base_url: Base URL for the service
            pool_size: Maximum number of connections in pool
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
        """
        self.base_url = base_url
        self.pool_size = pool_size
        self.timeout = timeout
        self.max_retries = max_retries
        self._connection_pool = ConnectionPool(base_url, pool_size, timeout)
        self._logger = get_logger(__name__)

        # Performance tracking
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_time": 0.0,
            "avg_response_time": 0.0,
            "connection_pool_hits": 0,
            "connection_pool_misses": 0,
        }

    async def post(
        self,
        url: str,
        json: dict[str, Any] | None = None,
        data: bytes | None = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an optimized POST request.

        Args:
            url: Request URL
            json: JSON data to send
            data: Raw data to send
            headers: Request headers
            **kwargs: Additional request parameters

        Returns:
            HTTP response
        """
        return await self._make_request(
            "POST", url, json=json, data=data, headers=headers, **kwargs
        )

    async def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an optimized GET request.

        Args:
            url: Request URL
            headers: Request headers
            **kwargs: Additional request parameters

        Returns:
            HTTP response
        """
        return await self._make_request("GET", url, headers=headers, **kwargs)

    async def _make_request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an optimized HTTP request.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Request parameters

        Returns:
            HTTP response
        """
        start_time = time.perf_counter()
        self._stats["total_requests"] += 1

        try:
            async with self._connection_pool as client:
                # Profile the request
                response, request_time = await profile_function(
                    client.request, method, url, **kwargs
                )

                self._stats["successful_requests"] += 1
                self._stats["total_time"] += request_time
                self._stats["avg_response_time"] = (
                    self._stats["total_time"] / self._stats["successful_requests"]
                )

                self._logger.debug(
                    "optimized_http.request_completed",
                    method=method,
                    url=url,
                    status_code=response.status_code,
                    response_time=request_time,
                    avg_response_time=self._stats["avg_response_time"],
                )

                return response

        except Exception as e:
            self._stats["failed_requests"] += 1
            request_time = time.perf_counter() - start_time

            self._logger.error(
                "optimized_http.request_failed",
                method=method,
                url=url,
                error=str(e),
                request_time=request_time,
            )

            raise

    async def check_health(self) -> bool:
        """Check if the service is healthy.

        Returns:
            True if service is healthy
        """
        try:
            response = await self.get("/health/live")
            return bool(response.status_code == 200)
        except (httpx.HTTPError, httpx.RequestError) as e:
            self._logger.error("optimized_http.health_check_failed", error=str(e))
            return False

    async def get_stats(self) -> dict[str, Any]:
        """Get performance statistics.

        Returns:
            Performance statistics
        """
        return {
            "http_stats": self._stats.copy(),
            "connection_pool": {
                "base_url": self.base_url,
                "pool_size": self.pool_size,
                "timeout": self.timeout,
            },
        }


class OptimizedSTTClient:
    """Optimized STT client with connection pooling."""

    def __init__(self, stt_url: str):
        """Initialize optimized STT client.

        Args:
            stt_url: STT service URL
        """
        self.stt_url = stt_url
        self._http_client = OptimizedHTTPClient(stt_url)
        self._logger = get_logger(__name__)

    async def transcribe(self, audio_data: bytes, **kwargs: Any) -> dict[str, Any]:
        """Transcribe audio with optimization.

        Args:
            audio_data: Audio data to transcribe
            **kwargs: Additional parameters

        Returns:
            Transcription result
        """
        start_time = time.perf_counter()

        try:
            response = await self._http_client.post(
                "/transcribe",
                data=audio_data,
                headers={"Content-Type": "audio/wav"},
                **kwargs,
            )

            if response.status_code == 200:
                result: dict[str, Any] = response.json()
                processing_time = time.perf_counter() - start_time

                self._logger.info(
                    "optimized_stt.transcription_completed",
                    audio_size=len(audio_data),
                    processing_time=processing_time,
                    text_length=len(result.get("text", "")),
                )

                return result
            else:
                raise httpx.HTTPStatusError(
                    f"STT request failed with status {response.status_code}",
                    request=response.request,
                    response=response,
                )

        except Exception as e:
            processing_time = time.perf_counter() - start_time

            self._logger.error(
                "optimized_stt.transcription_failed",
                audio_size=len(audio_data),
                processing_time=processing_time,
                error=str(e),
            )

            raise

    async def check_health(self) -> bool:
        """Check STT service health.

        Returns:
            True if service is healthy
        """
        return await self._http_client.check_health()

    async def get_stats(self) -> dict[str, Any]:
        """Get STT client statistics.

        Returns:
            STT client statistics
        """
        http_stats = await self._http_client.get_stats()
        return {
            "stt_client": {
                "stt_url": self.stt_url,
                "optimization_enabled": True,
            },
            **http_stats,
        }


class OptimizedTTSClient:
    """Optimized TTS client with connection pooling."""

    def __init__(self, tts_url: str):
        """Initialize optimized TTS client.

        Args:
            tts_url: TTS service URL
        """
        self.tts_url = tts_url
        self._http_client = OptimizedHTTPClient(tts_url)
        self._logger = get_logger(__name__)

    async def synthesize(self, text: str, **kwargs: Any) -> bytes:
        """Synthesize speech with optimization.

        Args:
            text: Text to synthesize
            **kwargs: Additional parameters

        Returns:
            Audio data
        """
        start_time = time.perf_counter()

        try:
            response = await self._http_client.post(
                "/synthesize",
                json={"text": text, **kwargs},
            )

            if response.status_code == 200:
                audio_data: bytes = response.content
                processing_time = time.perf_counter() - start_time

                self._logger.info(
                    "optimized_tts.synthesis_completed",
                    text_length=len(text),
                    audio_size=len(audio_data),
                    processing_time=processing_time,
                )

                return audio_data
            else:
                raise httpx.HTTPStatusError(
                    f"TTS request failed with status {response.status_code}",
                    request=response.request,
                    response=response,
                )

        except Exception as e:
            processing_time = time.perf_counter() - start_time

            self._logger.error(
                "optimized_tts.synthesis_failed",
                text_length=len(text),
                processing_time=processing_time,
                error=str(e),
            )

            raise

    async def check_health(self) -> bool:
        """Check TTS service health.

        Returns:
            True if service is healthy
        """
        return await self._http_client.check_health()

    async def get_stats(self) -> dict[str, Any]:
        """Get TTS client statistics.

        Returns:
            TTS client statistics
        """
        http_stats = await self._http_client.get_stats()
        return {
            "tts_client": {
                "tts_url": self.tts_url,
                "optimization_enabled": True,
            },
            **http_stats,
        }
