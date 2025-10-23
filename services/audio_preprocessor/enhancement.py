"""Audio preprocessing implementation using MetricGAN+.

This module provides the core audio preprocessing functionality including:
- MetricGAN+ denoising for noise reduction
- Real-time frame processing
- Audio quality enhancement
- Performance monitoring
"""

from __future__ import annotations

import io
import time
from typing import Any

# Import ML libraries with error handling
try:
    import numpy as np
    import torch
    import torchaudio
    from speechbrain.pretrained import SpectralMaskEnhancement
except ImportError:
    # These will be available at runtime in the container
    import types

    np = types.ModuleType("numpy")
    torch = types.ModuleType("torch")
    torchaudio = types.ModuleType("torchaudio")
    SpectralMaskEnhancement = None

from services.common.logging import get_logger

logger = get_logger(__name__)


class AudioPreprocessor:
    """Audio preprocessor using MetricGAN+ for denoising."""

    def __init__(self, config: Any) -> None:
        """Initialize audio preprocessor.

        Args:
            config: Audio configuration
        """
        self.config = config
        self._logger = get_logger(__name__)

        # Initialize MetricGAN+ model
        self._enhance_model: SpectralMaskEnhancement | None = None

        # Performance tracking
        self._processing_stats = {
            "total_audio_processed": 0,
            "total_processing_time": 0.0,
            "avg_processing_time": 0.0,
            "total_frames_processed": 0,
            "avg_frame_processing_time": 0.0,
        }

        self._logger.info("audio_preprocessor.initialized")

    async def initialize(self) -> None:
        """Initialize the audio preprocessor."""
        try:
            # Load MetricGAN+ model
            self._enhance_model = SpectralMaskEnhancement.from_hparams(
                source="speechbrain/metricgan-plus-voicebank",
                savedir="models/metricgan",
                run_opts={"device": "cpu"},  # Use CPU for now
            )

            self._logger.info("audio_preprocessor.model_loaded", model="metricgan-plus")
        except Exception as exc:
            self._logger.error("audio_preprocessor.model_load_failed", error=str(exc))
            raise

    async def cleanup(self) -> None:
        """Cleanup resources."""
        try:
            # Cleanup model resources
            if self._enhance_model:
                del self._enhance_model
                self._enhance_model = None

            self._logger.info("audio_preprocessor.cleanup_completed")
        except Exception as exc:
            self._logger.error("audio_preprocessor.cleanup_failed", error=str(exc))

    async def denoise_audio(self, audio_data: bytes) -> bytes:
        """Denoise audio using MetricGAN+.

        Args:
            audio_data: Raw audio data bytes

        Returns:
            Enhanced audio data bytes
        """
        if self._enhance_model is None:
            raise RuntimeError("Audio preprocessor not initialized")

        try:
            start_time = time.time()

            # Load audio from bytes
            audio_tensor, sample_rate = torchaudio.load(io.BytesIO(audio_data))

            # Ensure audio is in the right format (mono, float32)
            if audio_tensor.shape[0] > 1:
                audio_tensor = audio_tensor.mean(dim=0, keepdim=True)

            # Convert to numpy for processing
            audio_np = audio_tensor.squeeze(0).numpy()

            # Enhance audio using MetricGAN+
            enhanced_audio = self._enhance_model.enhance_batch(
                torch.from_numpy(audio_np).unsqueeze(0),
                lengths=torch.tensor([audio_np.shape[0] / sample_rate]),
            )

            # Convert back to bytes
            enhanced_np = enhanced_audio.squeeze(0).detach().cpu().numpy()

            # Convert to WAV bytes
            output_buffer = io.BytesIO()
            torchaudio.save(
                output_buffer,
                torch.from_numpy(enhanced_np).unsqueeze(0),
                sample_rate,
                format="wav",
            )
            enhanced_bytes = output_buffer.getvalue()

            # Update stats
            processing_time = time.time() - start_time
            self._update_stats(processing_time, len(audio_data))

            self._logger.debug(
                "audio.denoising_completed",
                processing_time_ms=processing_time * 1000,
                input_size=len(audio_data),
                output_size=len(enhanced_bytes),
            )

            return bytes(enhanced_bytes)

        except Exception as exc:
            self._logger.error("audio.denoising_failed", error=str(exc))
            raise

    async def denoise_frame(self, frame_data: bytes) -> bytes:
        """Process a single audio frame.

        Args:
            frame_data: Raw frame data bytes

        Returns:
            Enhanced frame data bytes
        """
        if self._enhance_model is None:
            raise RuntimeError("Audio preprocessor not initialized")

        try:
            start_time = time.time()

            # Convert frame to tensor
            frame_tensor = torch.frombuffer(frame_data, dtype=torch.float32)

            # Enhance frame
            enhanced_frame = self._enhance_model.enhance_batch(
                frame_tensor.unsqueeze(0),
                lengths=torch.tensor([frame_tensor.shape[0] / 16000]),  # Assume 16kHz
            )

            # Convert back to bytes
            enhanced_bytes = enhanced_frame.squeeze(0).detach().cpu().numpy().tobytes()

            # Update stats
            processing_time = time.time() - start_time
            self._update_frame_stats(processing_time)

            return bytes(enhanced_bytes)

        except Exception as exc:
            self._logger.error("audio.frame_processing_failed", error=str(exc))
            raise

    async def is_healthy(self) -> bool:
        """Check if the preprocessor is healthy."""
        return self._enhance_model is not None

    async def get_metrics(self) -> dict[str, Any]:
        """Get processing metrics."""
        return {
            "processing_stats": self._processing_stats,
            "model_loaded": self._enhance_model is not None,
            "model_name": "metricgan-plus-voicebank",
        }

    def _update_stats(self, processing_time: float, input_size: int) -> None:
        """Update processing statistics."""
        self._processing_stats["total_audio_processed"] += 1
        self._processing_stats["total_processing_time"] += processing_time
        self._processing_stats["avg_processing_time"] = (
            self._processing_stats["total_processing_time"]
            / self._processing_stats["total_audio_processed"]
        )

    def _update_frame_stats(self, processing_time: float) -> None:
        """Update frame processing statistics."""
        self._processing_stats["total_frames_processed"] += 1
        self._processing_stats["avg_frame_processing_time"] = (
            self._processing_stats["total_processing_time"]
            / self._processing_stats["total_frames_processed"]
        )
