"""Wake phrase detection helpers leveraging openwakeword when available.

This module provides a backward-compatible wrapper around the common library
wake detection implementation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from services.common.wake_detection import (
    WakeDetectionResult,
    WakeDetector as CommonWakeDetector,
)

if TYPE_CHECKING:
    from .audio import AudioSegment
    from .config import WakeConfig


class WakeDetector(CommonWakeDetector):
    """Detect wake phrases from transcripts and raw audio.

    This is a Discord-specific wrapper that extends the common library
    WakeDetector to add Discord-specific logging and backward compatibility
    for the AudioSegment-based detect() method.
    """

    def __init__(self, config: WakeConfig) -> None:
        """Initialize wake detector for Discord service."""
        super().__init__(config, service_name="discord")

    def detect(  # type: ignore[override]
        self,
        segment: AudioSegment,
        transcript: str | None,
    ) -> WakeDetectionResult | None:
        """Detect a wake phrase from audio first, then fall back to transcripts.

        This method maintains backward compatibility with the existing
        Discord codebase that passes AudioSegment objects.

        Args:
            segment: AudioSegment object with pcm and sample_rate attributes
            transcript: Transcribed text (optional)

        Returns:
            WakeDetectionResult if wake phrase detected, None otherwise
        """
        from services.common.structured_logging import bind_correlation_id

        logger = bind_correlation_id(self._logger, segment.correlation_id)

        # Log wake detection attempt
        logger.debug(
            "wake.detection_attempt",
            correlation_id=segment.correlation_id,
            user_id=segment.user_id,
            transcript_preview=transcript[:120] if transcript else None,
            wake_phrases=self._phrases,
            enabled=self._config.enabled,
        )

        if not self._config.enabled:
            testing_result = WakeDetectionResult(
                phrase="testing_mode",
                confidence=1.0,
                source="transcript",
            )
            logger.info(
                "wake.detection_result",
                correlation_id=segment.correlation_id,
                user_id=segment.user_id,
                detected=True,
                phrase=testing_result.phrase,
                confidence=testing_result.confidence,
                source=testing_result.source,
            )
            return testing_result

        # Use parent class detect() method with backward compatibility
        # Pass segment as first arg, let it extract pcm and sample_rate
        result: WakeDetectionResult | None = super().detect(segment, None, transcript)

        if result:
            logger.info(
                "wake.detection_result",
                correlation_id=segment.correlation_id,
                user_id=segment.user_id,
                detected=True,
                phrase=result.phrase,
                confidence=result.confidence,
                source=result.source,
            )
        else:
            # Log no detection at DEBUG (too verbose for non-events)
            # Only detected wake phrases are logged at INFO level
            logger.debug(
                "wake.detection_result",
                correlation_id=segment.correlation_id,
                user_id=segment.user_id,
                detected=False,
                phrase=None,
                confidence=None,
                source=None,
            )

        return result


__all__ = ["WakeDetectionResult", "WakeDetector"]
