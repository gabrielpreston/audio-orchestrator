"""HTTP client for the audio processor service.

This module provides a client for communicating with the unified audio processor service.
"""

from __future__ import annotations

import base64

from services.common.http_client_factory import create_resilient_client
from services.common.resilient_http import ServiceUnavailableError
from services.common.structured_logging import get_logger
from services.discord.audio import AudioSegment, PCMFrame

logger = get_logger(__name__)


class AudioProcessorClient:
    """HTTP client for the audio processor service."""

    def __init__(
        self,
        base_url: str = "http://audio:9100",
        timeout: float = 20.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        """Initialize audio processor client.

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
        self._client = create_resilient_client(
            service_name="audio",
            base_url=base_url,
            env_prefix="AUDIO_PROCESSOR",
        )

        self._logger.info(
            "audio_processor_client.initialized", base_url=base_url, timeout=timeout
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.close()
        self._logger.info("audio_processor_client.closed")

    async def process_frame(self, frame: PCMFrame) -> PCMFrame | None:
        """Process a single PCM frame with the audio processor service.

        Args:
            frame: PCM frame to process

        Returns:
            Processed PCM frame or None if processing failed
        """
        try:
            # Encode PCM data as base64
            pcm_b64 = base64.b64encode(frame.pcm).decode()

            # Prepare request data
            request_data = {
                "pcm": pcm_b64,
                "timestamp": frame.timestamp,
                "rms": frame.rms,
                "duration": frame.duration,
                "sequence": frame.sequence,
                "sample_rate": frame.sample_rate,
            }

            # Make request to audio processor using resilient client
            try:
                response = await self._client.post_with_retry(
                    "/process/frame",
                    json=request_data,
                    timeout=self.timeout,
                    max_retries=self.max_retries,
                )
            except ServiceUnavailableError as exc:
                self._logger.error(
                    "audio_processor_client.service_unavailable",
                    sequence=frame.sequence,
                    error=str(exc),
                )
                return None

            if response.status_code == 200:
                result = response.json()
                if result.get("success", False):
                    # Decode processed PCM data
                    processed_pcm = base64.b64decode(result["pcm"])

                    # Create processed frame
                    processed_frame = PCMFrame(
                        pcm=processed_pcm,
                        timestamp=frame.timestamp,
                        rms=frame.rms,
                        duration=frame.duration,
                        sequence=frame.sequence,
                        sample_rate=frame.sample_rate,
                    )

                    self._logger.debug(
                        "audio_processor_client.frame_processed",
                        sequence=frame.sequence,
                        processing_time_ms=result.get("processing_time_ms", 0),
                    )

                    return processed_frame
                else:
                    self._logger.warning(
                        "audio_processor_client.frame_processing_failed",
                        sequence=frame.sequence,
                        error=result.get("error", "Unknown error"),
                    )
                    return None
            else:
                self._logger.error(
                    "audio_processor_client.frame_request_failed",
                    sequence=frame.sequence,
                    status_code=response.status_code,
                )
                return None

        except Exception as exc:
            self._logger.error(
                "audio_processor_client.frame_processing_error",
                sequence=frame.sequence,
                error=str(exc),
            )
            return None

    async def process_segment(self, segment: AudioSegment) -> AudioSegment | None:
        """Process an audio segment with the audio processor service.

        Args:
            segment: Audio segment to process

        Returns:
            Processed audio segment or None if processing failed
        """
        try:
            # Encode PCM data as base64
            pcm_b64 = base64.b64encode(segment.pcm).decode()

            # Prepare request data
            request_data = {
                "user_id": segment.user_id,
                "pcm": pcm_b64,
                "start_timestamp": segment.start_timestamp,
                "end_timestamp": segment.end_timestamp,
                "correlation_id": segment.correlation_id,
                "frame_count": segment.frame_count,
                "sample_rate": segment.sample_rate,
            }

            # Make request to audio processor using resilient client
            try:
                response = await self._client.post_with_retry(
                    "/process/segment",
                    json=request_data,
                    timeout=self.timeout,
                    max_retries=self.max_retries,
                )
            except ServiceUnavailableError as exc:
                self._logger.error(
                    "audio_processor_client.service_unavailable",
                    correlation_id=segment.correlation_id,
                    user_id=segment.user_id,
                    error=str(exc),
                )
                return None

            if response.status_code == 200:
                result = response.json()
                if result.get("success", False):
                    # Decode processed PCM data
                    processed_pcm = base64.b64decode(result["pcm"])

                    # Create processed segment
                    processed_segment = AudioSegment(
                        user_id=segment.user_id,
                        pcm=processed_pcm,
                        start_timestamp=segment.start_timestamp,
                        end_timestamp=segment.end_timestamp,
                        correlation_id=segment.correlation_id,
                        frame_count=segment.frame_count,
                        sample_rate=segment.sample_rate,
                    )

                    self._logger.info(
                        "audio_processor_client.segment_processed",
                        correlation_id=segment.correlation_id,
                        user_id=segment.user_id,
                        processing_time_ms=result.get("processing_time_ms", 0),
                    )

                    return processed_segment
                else:
                    self._logger.warning(
                        "audio_processor_client.segment_processing_failed",
                        correlation_id=segment.correlation_id,
                        user_id=segment.user_id,
                        error=result.get("error", "Unknown error"),
                    )
                    return None
            else:
                self._logger.error(
                    "audio_processor_client.segment_request_failed",
                    correlation_id=segment.correlation_id,
                    user_id=segment.user_id,
                    status_code=response.status_code,
                )
                return None

        except Exception as exc:
            self._logger.error(
                "audio_processor_client.segment_processing_error",
                correlation_id=segment.correlation_id,
                user_id=segment.user_id,
                error=str(exc),
            )
            return None

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
        try:
            # Make request to audio processor using resilient client
            headers = {}
            if correlation_id:
                headers["X-Correlation-ID"] = correlation_id

            try:
                response = await self._client.post_with_retry(
                    "/enhance/audio",
                    content=audio_data,
                    headers=headers if headers else None,
                    timeout=self.timeout,
                    max_retries=self.max_retries,
                )
            except ServiceUnavailableError as exc:
                self._logger.error(
                    "audio_processor_client.service_unavailable",
                    correlation_id=correlation_id,
                    error=str(exc),
                )
                return audio_data  # Return original data on failure

            if response.status_code == 200:
                self._logger.debug(
                    "audio_processor_client.audio_enhanced",
                    correlation_id=correlation_id,
                    input_size=len(audio_data),
                    output_size=len(response.content),
                )
                return bytes(response.content)
            else:
                self._logger.warning(
                    "audio_processor_client.enhancement_failed",
                    correlation_id=correlation_id,
                    status_code=response.status_code,
                )
                return audio_data  # Return original data on failure

        except Exception as exc:
            self._logger.error(
                "audio_processor_client.enhancement_error",
                correlation_id=correlation_id,
                error=str(exc),
            )
            return audio_data  # Return original data on failure

    async def health_check(self) -> bool:
        """Check if the audio processor service is healthy.

        Returns:
            True if service is healthy, False otherwise
        """
        return await self._client.check_health()
