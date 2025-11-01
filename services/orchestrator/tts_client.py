"""HTTP client for the TTS service (Bark).

This module provides a client for the orchestrator service to communicate with the TTS service.
"""

from __future__ import annotations

import time

from services.common.http_client_factory import create_resilient_client
from services.common.resilient_http import ServiceUnavailableError
from services.common.structured_logging import get_logger

logger = get_logger(__name__, service_name="orchestrator")


class TTSClient:
    """HTTP client for the TTS service."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        """Initialize TTS client.

        Args:
            base_url: Base URL for the TTS service. If not provided, will use
                     environment variable or default to http://bark:7100
            timeout: Request timeout in seconds
        """
        # Default to bark service URL if not provided
        if base_url is None:
            import os

            base_url = os.getenv("TTS_URL", "http://bark:7100")

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._logger = logger

        # Create resilient HTTP client with circuit breaker and connection pooling
        self._client = create_resilient_client(
            service_name="bark",
            base_url=base_url,
            env_prefix="ORCHESTRATOR_TTS",
        )

        self._logger.info(
            "tts_client.initialized",
            base_url=self.base_url,
            timeout=timeout,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.close()
            self._logger.info("tts_client.closed")

    async def synthesize(
        self,
        text: str,
        voice: str = "v2/en_speaker_1",
        speed: float = 1.0,
        correlation_id: str | None = None,
    ) -> bytes | None:
        """Synthesize text to speech.

        Args:
            text: Text to synthesize
            voice: Voice preset to use
            speed: Speech speed multiplier
            correlation_id: Correlation ID for tracing

        Returns:
            Audio data as bytes, or None if synthesis failed

        Raises:
            ServiceUnavailableError: If TTS service is unavailable
        """
        start_time = time.time()

        try:
            # Prepare request payload
            payload = {
                "text": text,
                "voice": voice,
                "speed": speed,
            }

            # Add correlation ID to headers if provided
            headers = {}
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id

            self._logger.debug(
                "tts_client.synthesis_request",
                text_length=len(text),
                voice=voice,
                correlation_id=correlation_id,
            )

            # Call TTS service
            response = await self._client.post_with_retry(
                "/synthesize",
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )

            response.raise_for_status()

            # Parse response (Bark service returns JSON with audio as base64-encoded bytes)
            result = response.json()
            audio_data = result.get("audio")

            if not audio_data:
                self._logger.error(
                    "tts_client.synthesis_missing_audio",
                    response_keys=list(result.keys()),
                )
                return None

            # Pydantic serializes bytes as base64 strings in JSON responses
            import base64

            if isinstance(audio_data, str):
                # Decode base64 string
                try:
                    audio_bytes = base64.b64decode(audio_data)
                except Exception as decode_exc:
                    self._logger.error(
                        "tts_client.base64_decode_failed",
                        error=str(decode_exc),
                    )
                    return None
            elif isinstance(audio_data, bytes):
                # Direct bytes (unlikely but handle it)
                audio_bytes = audio_data
            else:
                self._logger.error(
                    "tts_client.synthesis_invalid_audio_format",
                    audio_type=type(audio_data).__name__,
                )
                return None

            processing_time = time.time() - start_time

            self._logger.info(
                "tts_client.synthesis_completed",
                text_length=len(text),
                audio_size=len(audio_bytes),
                processing_time_ms=processing_time * 1000,
                voice=voice,
                correlation_id=correlation_id,
            )

            return audio_bytes

        except ServiceUnavailableError as exc:
            processing_time = time.time() - start_time
            self._logger.error(
                "tts_client.service_unavailable",
                error=str(exc),
                processing_time_ms=processing_time * 1000,
                correlation_id=correlation_id,
            )
            raise

        except Exception as exc:
            processing_time = time.time() - start_time
            self._logger.error(
                "tts_client.synthesis_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                processing_time_ms=processing_time * 1000,
                correlation_id=correlation_id,
            )
            raise

    async def check_health(self) -> bool:
        """Check if the TTS service is healthy.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            return await self._client.check_health()
        except Exception as exc:
            self._logger.warning(
                "tts_client.health_check_failed",
                error=str(exc),
            )
            return False
