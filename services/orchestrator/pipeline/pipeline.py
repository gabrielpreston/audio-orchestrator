"""Main audio pipeline for end-to-end audio processing.

This module provides the main AudioPipeline class that orchestrates
the entire audio processing workflow from input to output.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from services.common.logging import get_logger

from services.orchestrator.adapters.types import AudioChunk
from .audio_processor import AudioProcessor
from .types import ProcessedSegment, ProcessingConfig
from .wake_detector import WakeDetector


logger = get_logger(__name__)


class AudioPipeline:
    """Main audio pipeline for end-to-end audio processing.

    This class orchestrates the entire audio processing workflow,
    including audio processing, wake detection, and quality assessment.
    """

    def __init__(
        self,
        audio_processor: AudioProcessor | None = None,
        wake_detector: WakeDetector | None = None,
        config: ProcessingConfig | None = None,
    ) -> None:
        """Initialize the audio pipeline.

        Args:
            audio_processor: Audio processor instance
            wake_detector: Wake detector instance
            config: Processing configuration
        """
        self.config = config or ProcessingConfig()
        self.audio_processor = audio_processor or AudioProcessor(self.config)
        self.wake_detector = wake_detector or WakeDetector(self.config)
        self._logger = get_logger(self.__class__.__name__)

        # Pipeline statistics
        self._processed_count = 0
        self._failed_count = 0
        self._wake_detected_count = 0

        self._logger.info(
            "Audio pipeline initialized",
            extra={
                "target_sample_rate": self.config.target_sample_rate,
                "target_channels": self.config.target_channels,
                "wake_detection_enabled": self.config.wake_detection_enabled,
                "wake_phrases": self.config.wake_phrases,
            },
        )

    async def process_audio_stream(
        self, audio_stream: AsyncIterator[AudioChunk], session_id: str
    ) -> AsyncIterator[ProcessedSegment]:
        """Process a stream of audio chunks.

        Args:
            audio_stream: Stream of audio chunks to process
            session_id: Session identifier

        Yields:
            Processed audio segments
        """
        self._logger.info(
            "Starting audio stream processing", extra={"session_id": session_id}
        )

        try:
            async for audio_chunk in audio_stream:
                try:
                    # Process the audio chunk
                    processed_segment = await self.audio_processor.process_audio_chunk(
                        audio_chunk, session_id
                    )

                    # Skip failed segments
                    if processed_segment.status.value == "failed":
                        self._failed_count += 1
                        self._logger.warning(
                            "Skipping failed audio segment",
                            extra={
                                "correlation_id": audio_chunk.correlation_id,
                                "session_id": session_id,
                            },
                        )
                        continue

                    # Detect wake phrases if enabled
                    if self.config.wake_detection_enabled:
                        processed_segment = await self.wake_detector.detect_wake_phrase(
                            processed_segment
                        )

                        if processed_segment.wake_detected:
                            self._wake_detected_count += 1
                            self._logger.info(
                                "Wake phrase detected",
                                extra={
                                    "correlation_id": audio_chunk.correlation_id,
                                    "session_id": session_id,
                                    "wake_phrase": processed_segment.wake_phrase,
                                    "confidence": processed_segment.wake_confidence,
                                },
                            )

                    self._processed_count += 1

                    # Log processing statistics
                    self._logger.debug(
                        "Audio segment processed",
                        extra={
                            "correlation_id": audio_chunk.correlation_id,
                            "session_id": session_id,
                            "processing_time": processed_segment.processing_time,
                            "wake_detected": processed_segment.wake_detected,
                            "volume_level": processed_segment.volume_level,
                            "clarity_score": processed_segment.clarity_score,
                        },
                    )

                    yield processed_segment

                except Exception as e:
                    self._failed_count += 1
                    self._logger.error(
                        "Error processing audio chunk",
                        extra={
                            "correlation_id": audio_chunk.correlation_id,
                            "session_id": session_id,
                            "error": str(e),
                        },
                    )
                    continue

        except Exception as e:
            self._logger.error(
                "Error in audio stream processing",
                extra={"session_id": session_id, "error": str(e)},
            )
            raise

        finally:
            self._logger.info(
                "Audio stream processing completed",
                extra={
                    "session_id": session_id,
                    "processed_count": self._processed_count,
                    "failed_count": self._failed_count,
                    "wake_detected_count": self._wake_detected_count,
                },
            )

    async def process_single_chunk(
        self, audio_chunk: AudioChunk, session_id: str
    ) -> ProcessedSegment:
        """Process a single audio chunk.

        Args:
            audio_chunk: Audio chunk to process
            session_id: Session identifier

        Returns:
            Processed audio segment
        """
        self._logger.debug(
            "Processing single audio chunk",
            extra={
                "correlation_id": audio_chunk.correlation_id,
                "session_id": session_id,
            },
        )

        # Process the audio chunk
        processed_segment = await self.audio_processor.process_audio_chunk(
            audio_chunk, session_id
        )

        # Detect wake phrases if enabled
        if self.config.wake_detection_enabled:
            processed_segment = await self.wake_detector.detect_wake_phrase(
                processed_segment
            )

        self._processed_count += 1

        return processed_segment

    async def get_statistics(self) -> dict[str, Any]:
        """Get pipeline processing statistics.

        Returns:
            Dictionary containing processing statistics
        """
        return {
            "processed_count": self._processed_count,
            "failed_count": self._failed_count,
            "wake_detected_count": self._wake_detected_count,
            "success_rate": (
                self._processed_count / (self._processed_count + self._failed_count)
                if (self._processed_count + self._failed_count) > 0
                else 0.0
            ),
            "wake_detection_rate": (
                self._wake_detected_count / self._processed_count
                if self._processed_count > 0
                else 0.0
            ),
        }

    async def reset_statistics(self) -> None:
        """Reset pipeline statistics."""
        self._processed_count = 0
        self._failed_count = 0
        self._wake_detected_count = 0

        self._logger.info("Pipeline statistics reset")

    async def get_capabilities(self) -> dict[str, Any]:
        """Get pipeline capabilities.

        Returns:
            Dictionary describing pipeline capabilities
        """
        processor_capabilities = await self.audio_processor.get_capabilities()
        wake_detector_capabilities = await self.wake_detector.get_capabilities()

        return {
            "pipeline_type": "AudioPipeline",
            "config": {
                "target_sample_rate": self.config.target_sample_rate,
                "target_channels": self.config.target_channels,
                "target_format": self.config.target_format.value,
                "wake_detection_enabled": self.config.wake_detection_enabled,
                "wake_phrases": self.config.wake_phrases,
                "confidence_threshold": self.config.wake_confidence_threshold,
            },
            "processor": processor_capabilities,
            "wake_detector": wake_detector_capabilities,
        }

    async def health_check(self) -> dict[str, Any]:
        """Perform health check for the pipeline.

        Returns:
            Health check results
        """
        processor_health = await self.audio_processor.health_check()
        wake_detector_health = await self.wake_detector.health_check()
        statistics = await self.get_statistics()

        return {
            "status": "healthy",
            "pipeline_type": "AudioPipeline",
            "statistics": statistics,
            "processor": processor_health,
            "wake_detector": wake_detector_health,
        }
