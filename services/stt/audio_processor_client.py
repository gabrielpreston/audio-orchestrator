"""HTTP client for the audio processor service (STT service version).

This module provides a client for the STT service to communicate with the
unified audio processor service for audio enhancement.
"""

from __future__ import annotations

import time

from services.common.resilient_http import ServiceUnavailableError
from services.common.structured_logging import get_logger

logger = get_logger(__name__)


class STTAudioProcessorClient:
    """HTTP client for the audio processor service (STT service version)."""

    def __init__(
        self,
        base_url: str = "http://audio:9100",
        timeout: float = 50.0,  # 50 second timeout for enhancement
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        """Initialize audio processor client for STT service.

        Args:
            base_url: Base URL for the audio processor service
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts (used by ResilientHTTPClient)
            retry_delay: Delay between retries in seconds (not used - ResilientHTTPClient handles retries)
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._logger = get_logger(__name__)

        # Create resilient HTTP client with circuit breaker and connection pooling
        # Pass timeout explicitly to ensure the client uses the correct timeout
        from services.common.circuit_breaker import CircuitBreakerConfig
        from services.common.resilient_http import ResilientHTTPClient

        self._client = ResilientHTTPClient(
            service_name="audio",
            base_url=base_url,
            circuit_config=CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=2,
                timeout_seconds=timeout,
            ),
            timeout=timeout,  # Pass the timeout to the client
        )

        self._logger.info(
            "stt_audio_processor_client.initialized", base_url=base_url, timeout=timeout
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.close()
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
            # Make request to audio processor using resilient client
            headers = {}
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id

            # Log request initiation with decision context
            self._logger.info(
                "stt_audio_processor_client.request_initiated",
                correlation_id=correlation_id,
                url=f"{self.base_url}/enhance/audio",
                input_size=len(audio_data),
                timeout_seconds=self.timeout,
                max_retries=self.max_retries,
                decision="attempting_enhancement",
            )

            try:
                response = await self._client.post_with_retry(
                    "/enhance/audio",
                    content=audio_data,
                    headers=headers if headers else None,
                    timeout=self.timeout,
                    max_retries=self.max_retries,
                )
            except ServiceUnavailableError as exc:
                enhancement_duration = (time.time() - start_time) * 1000
                self._logger.error(
                    "stt_audio_processor_client.service_unavailable",
                    correlation_id=correlation_id,
                    error=str(exc),
                    enhancement_duration_ms=enhancement_duration,
                    decision="service_unavailable_returning_original",
                )
                return audio_data  # Return original data on failure

            if response.status_code == 200:
                enhancement_duration = (time.time() - start_time) * 1000

                self._logger.info(
                    "stt_audio_processor_client.audio_enhanced",
                    correlation_id=correlation_id,
                    input_size=len(audio_data),
                    output_size=len(response.content),
                    enhancement_duration_ms=enhancement_duration,
                    decision="enhancement_successful",
                )
                return bytes(response.content)
            else:
                self._logger.warning(
                    "stt_audio_processor_client.enhancement_failed",
                    correlation_id=correlation_id,
                    status_code=response.status_code,
                    decision="enhancement_failed_returning_original",
                )
                return audio_data  # Return original data on failure

        except Exception as exc:
            enhancement_duration = (time.time() - start_time) * 1000
            self._logger.error(
                "stt_audio_processor_client.enhancement_error",
                correlation_id=correlation_id,
                error=str(exc),
                error_type=type(exc).__name__,
                enhancement_duration_ms=enhancement_duration,
                decision="enhancement_error_returning_original",
            )
            return audio_data  # Return original data on failure

    async def health_check(self) -> bool:
        """Check if the audio processor service is healthy.

        Returns:
            True if service is healthy, False otherwise
        """
        return await self._client.check_health()
