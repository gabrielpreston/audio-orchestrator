"""HTTP client for the audio processor service (STT service version).

This module provides a client for the STT service to communicate with the
unified audio processor service for audio enhancement.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from services.common.logging import get_logger


logger = get_logger(__name__)


class STTAudioProcessorClient:
    """HTTP client for the audio processor service (STT service version)."""

    def __init__(
        self,
        base_url: str = "http://audio-processor:9100",
        timeout: float = 50.0,  # 50ms timeout for enhancement
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        """Initialize audio processor client for STT service.

        Args:
            base_url: Base URL for the audio processor service
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._logger = get_logger(__name__)

        # Create HTTP client with timeout
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
        )

        self._logger.info(
            "stt_audio_processor_client.initialized", base_url=base_url, timeout=timeout
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
        self._logger.info("stt_audio_processor_client.closed")

    async def enhance_audio(
        self, audio_data: bytes, correlation_id: str | None = None
    ) -> bytes:
        """Enhance audio data using the audio processor service.

        Args:
            audio_data: Raw audio data to enhance
            correlation_id: Optional correlation ID for logging

        Returns:
            Enhanced audio data or original data if enhancement failed
        """
        start_time = time.time()

        try:
            # Make request to audio processor
            response = await self._make_request_with_retry(
                "POST",
                f"{self.base_url}/enhance/audio",
                content=audio_data,
                headers={"X-Correlation-ID": correlation_id}
                if correlation_id
                else None,
            )

            if response.status_code == 200:
                enhancement_duration = (time.time() - start_time) * 1000

                self._logger.debug(
                    "stt_audio_processor_client.audio_enhanced",
                    correlation_id=correlation_id,
                    input_size=len(audio_data),
                    output_size=len(response.content),
                    enhancement_duration_ms=enhancement_duration,
                )
                return response.content
            else:
                self._logger.warning(
                    "stt_audio_processor_client.enhancement_failed",
                    correlation_id=correlation_id,
                    status_code=response.status_code,
                )
                return audio_data  # Return original data on failure

        except Exception as exc:
            enhancement_duration = (time.time() - start_time) * 1000
            self._logger.error(
                "stt_audio_processor_client.enhancement_error",
                correlation_id=correlation_id,
                error=str(exc),
                enhancement_duration_ms=enhancement_duration,
            )
            return audio_data  # Return original data on failure

    async def health_check(self) -> bool:
        """Check if the audio processor service is healthy.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            response = await self._client.get(f"{self.base_url}/health/ready")
            return response.status_code == 200
        except Exception as exc:
            self._logger.warning(
                "stt_audio_processor_client.health_check_failed", error=str(exc)
            )
            return False

    async def _make_request_with_retry(
        self, method: str, url: str, **kwargs: Any
    ) -> httpx.Response:
        """Make HTTP request with retry logic.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional request parameters

        Returns:
            HTTP response
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await self._client.request(method, url, **kwargs)
                return response
            except Exception as exc:
                last_exception = exc
                if attempt < self.max_retries:
                    self._logger.warning(
                        "stt_audio_processor_client.retry_attempt",
                        attempt=attempt + 1,
                        max_retries=self.max_retries,
                        error=str(exc),
                    )
                    await asyncio.sleep(
                        self.retry_delay * (2**attempt)
                    )  # Exponential backoff
                else:
                    self._logger.error(
                        "stt_audio_processor_client.max_retries_exceeded",
                        max_retries=self.max_retries,
                        error=str(exc),
                    )

        # If we get here, all retries failed
        raise last_exception or Exception("Request failed after all retries")
