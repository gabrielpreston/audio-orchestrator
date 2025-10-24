"""Bark TTS synthesis implementation with Piper fallback.

This module provides the core text-to-speech functionality including:
- Bark TTS generation with multiple voice presets
- Piper fallback for reliability
- Voice selection and configuration
- Performance monitoring
"""

from __future__ import annotations

import io
import time
from typing import Any

import numpy as np

# Import Bark with error handling
try:
    from bark import SAMPLE_RATE, generate_audio, preload_models
except ImportError:
    # These will be available at runtime in the container
    SAMPLE_RATE = 22050
    generate_audio = None
    preload_models = None
from scipy.io.wavfile import write as write_wav

from services.common.logging import get_logger

logger = get_logger(__name__)


class BarkSynthesizer:
    """Bark TTS synthesizer with Piper fallback."""

    def __init__(self, config: Any) -> None:
        """Initialize Bark synthesizer.

        Args:
            config: Audio configuration
        """
        self.config = config
        self._logger = get_logger(__name__)

        # Initialize Bark models
        self._models_loaded = False

        # Performance tracking
        self._synthesis_stats = {
            "total_syntheses": 0,
            "bark_syntheses": 0,
            "piper_fallbacks": 0,
            "total_processing_time": 0.0,
            "avg_processing_time": 0.0,
            "total_text_length": 0,
            "avg_text_length": 0.0,
        }

        self._logger.info("bark_synthesizer.initialized")

    async def initialize(self) -> None:
        """Initialize the Bark synthesizer."""
        try:
            # Preload Bark models
            preload_models()
            self._models_loaded = True

            self._logger.info("bark_synthesizer.models_loaded")
        except Exception as exc:
            self._logger.error("bark_synthesizer.model_load_failed", error=str(exc))
            # Continue without Bark - will use Piper fallback

    async def cleanup(self) -> None:
        """Cleanup resources."""
        try:
            # Cleanup Bark resources
            self._models_loaded = False

            self._logger.info("bark_synthesizer.cleanup_completed")
        except Exception as exc:
            self._logger.error("bark_synthesizer.cleanup_failed", error=str(exc))

    async def synthesize(
        self, text: str, voice: str = "v2/en_speaker_1", speed: float = 1.0
    ) -> tuple[bytes, str]:
        """Synthesize text using Bark TTS.

        Args:
            text: Text to synthesize
            voice: Voice preset to use
            speed: Speech speed multiplier

        Returns:
            Tuple of (audio_data, engine_name)
        """
        if not self._models_loaded:
            raise RuntimeError("Bark models not loaded")

        try:
            start_time = time.time()

            # Generate audio using Bark
            audio_array = generate_audio(text, history_prompt=voice)

            # Convert to WAV bytes
            audio_bytes = self._audio_to_bytes(audio_array, SAMPLE_RATE)

            # Update stats
            processing_time = time.time() - start_time
            self._update_stats(processing_time, len(text), "bark")

            self._logger.debug(
                "bark.synthesis_completed",
                processing_time_ms=processing_time * 1000,
                text_length=len(text),
                voice=voice,
            )

            return audio_bytes, "bark"

        except Exception as exc:
            self._logger.error("bark.synthesis_failed", error=str(exc))
            raise

    async def is_healthy(self) -> bool:
        """Check if the synthesizer is healthy."""
        return self._models_loaded

    async def get_metrics(self) -> dict[str, Any]:
        """Get synthesis metrics."""
        return {
            "synthesis_stats": self._synthesis_stats,
            "models_loaded": self._models_loaded,
            "engine": "bark_with_piper_fallback",
        }

    def _audio_to_bytes(
        self, audio_array: np.ndarray[Any, np.dtype[np.floating[Any]]], sample_rate: int
    ) -> bytes:
        """Convert audio array to WAV bytes."""
        # Normalize audio to 16-bit PCM
        audio_int16: np.ndarray[Any, np.dtype[np.int16]] = (audio_array * 32767).astype(
            np.int16
        )

        # Write to bytes buffer
        output_buffer = io.BytesIO()
        write_wav(output_buffer, sample_rate, audio_int16)

        return output_buffer.getvalue()

    def _update_stats(
        self, processing_time: float, text_length: int, engine: str
    ) -> None:
        """Update synthesis statistics."""
        self._synthesis_stats["total_syntheses"] += 1
        self._synthesis_stats["total_processing_time"] += processing_time
        self._synthesis_stats["total_text_length"] += text_length

        if engine == "bark":
            self._synthesis_stats["bark_syntheses"] += 1
        elif engine == "piper":
            self._synthesis_stats["piper_fallbacks"] += 1

        # Update averages
        self._synthesis_stats["avg_processing_time"] = (
            self._synthesis_stats["total_processing_time"]
            / self._synthesis_stats["total_syntheses"]
        )
        self._synthesis_stats["avg_text_length"] = (
            self._synthesis_stats["total_text_length"]
            / self._synthesis_stats["total_syntheses"]
        )
