"""Audio enhancement module for the unified audio processor service.

This module provides audio enhancement functionality including:
- MetricGAN+ integration
- High-pass filtering
- Audio quality improvement
- Performance optimization
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from scipy import signal

from services.common.logging import get_logger


logger = get_logger(__name__)


class AudioEnhancer:
    """Audio enhancement using MetricGAN+ and preprocessing techniques."""

    def __init__(
        self,
        enable_metricgan: bool = True,
        device: str = "cpu",
        model_source: str = "speechbrain/metricgan-plus-voicebank",
        model_savedir: str = "pretrained_models/metricgan-plus",
        enhancement_class: Any | None = None,  # Dependency injection for testing
    ) -> None:
        """Initialize audio enhancer.

        Args:
            enable_metricgan: Whether to enable MetricGAN+ enhancement
            device: Device to run enhancement on (cpu/cuda)
            model_source: Source for MetricGAN+ model
            model_savedir: Directory to save model
            enhancement_class: Optional enhancement class for dependency injection (testing)
        """
        self.enable_metricgan = enable_metricgan
        self.device = device
        self.model_source = model_source
        self.model_savedir = model_savedir
        self._enhancement_class = enhancement_class  # Store injected class

        self._metricgan_model: Any | None = None
        self._is_enhancement_enabled = False

        if self.enable_metricgan:
            self._load_metricgan_model()

    def _load_metricgan_model(self) -> None:
        """Load MetricGAN+ model."""
        try:
            if self._enhancement_class is not None:
                # Use injected class (for testing)
                self._metricgan_model = self._enhancement_class.from_hparams(
                    source=self.model_source, savedir=self.model_savedir
                )
            else:
                # Use real speechbrain import (production)
                from speechbrain.inference.enhancement import SpectralMaskEnhancement

                self._metricgan_model = SpectralMaskEnhancement.from_hparams(
                    source=self.model_source, savedir=self.model_savedir
                )
            self._is_enhancement_enabled = True
            logger.info("audio_enhancer.metricgan_loaded")

        except (ImportError, OSError, RuntimeError) as exc:
            logger.warning("audio_enhancer.metricgan_load_failed", error=str(exc))
            self._metricgan_model = None
            self._is_enhancement_enabled = False

    @property
    def is_enhancement_enabled(self) -> bool:
        """Check if enhancement is available."""
        return self._is_enhancement_enabled

    def apply_high_pass_filter(
        self,
        audio: np.ndarray[Any, np.dtype[np.float32]],
        sample_rate: int = 16000,
        cutoff_freq: float = 80.0,
    ) -> np.ndarray[Any, np.dtype[np.float32]]:
        """Apply high-pass filter to remove low-frequency noise.

        Args:
            audio: Input audio array
            sample_rate: Sample rate of audio
            cutoff_freq: Cutoff frequency for high-pass filter

        Returns:
            Filtered audio array
        """
        try:
            # Design high-pass Butterworth filter
            nyquist = sample_rate / 2
            normalized_cutoff = cutoff_freq / nyquist

            # Ensure cutoff is valid
            if normalized_cutoff >= 1.0:
                logger.warning("audio_enhancer.invalid_cutoff", cutoff=cutoff_freq)
                return audio

            b, a = signal.butter(4, normalized_cutoff, btype="high", analog=False)
            filtered_audio = signal.filtfilt(b, a, audio)

            logger.debug("audio_enhancer.high_pass_applied", cutoff=cutoff_freq)
            return filtered_audio

        except (ValueError, RuntimeError) as exc:
            logger.error("audio_enhancer.high_pass_failed", error=str(exc))
            return audio

    def enhance_audio(
        self,
        audio: np.ndarray[Any, np.dtype[np.float32]],
        sample_rate: int = 16000,
    ) -> np.ndarray[Any, np.dtype[np.float32]]:
        """Apply MetricGAN+ enhancement to audio.

        Args:
            audio: Input audio array (float32, shape: [samples])
            sample_rate: Sample rate of audio

        Returns:
            Enhanced audio array
        """
        if not self._is_enhancement_enabled or self._metricgan_model is None:
            logger.debug("audio_enhancer.enhancement_disabled")
            return audio

        try:
            import torch

            # Convert to torch tensor
            audio_tensor = (
                torch.from_numpy(audio).float().unsqueeze(0)
            )  # Add batch dimension

            # Apply MetricGAN+ enhancement
            enhanced_tensor = self._metricgan_model.enhance_batch(
                audio_tensor, lengths=torch.tensor([len(audio) / sample_rate])
            )

            # Convert back to numpy
            enhanced_audio = enhanced_tensor.squeeze(0).detach().cpu().numpy()

            logger.debug("audio_enhancer.enhancement_applied")
            return enhanced_audio

        except (ImportError, RuntimeError, OSError, MemoryError) as exc:
            logger.error("audio_enhancer.enhancement_failed", error=str(exc))
            # Return original audio on failure
            return audio

    def enhance_audio_pipeline(
        self,
        audio: np.ndarray[Any, np.dtype[np.float32]],
        sample_rate: int = 16000,
        apply_high_pass: bool = True,
        high_pass_cutoff: float = 80.0,
    ) -> np.ndarray[Any, np.dtype[np.float32]]:
        """Complete audio enhancement pipeline.

        Args:
            audio: Input audio array
            sample_rate: Sample rate of audio
            apply_high_pass: Whether to apply high-pass filter
            high_pass_cutoff: Cutoff frequency for high-pass filter

        Returns:
            Enhanced audio array
        """
        enhanced_audio = audio.copy()

        # Apply high-pass filter if requested
        if apply_high_pass:
            enhanced_audio = self.apply_high_pass_filter(
                enhanced_audio,
                sample_rate=sample_rate,
                cutoff_freq=high_pass_cutoff,
            )

        # Apply MetricGAN+ enhancement
        enhanced_audio = self.enhance_audio(
            enhanced_audio,
            sample_rate=sample_rate,
        )

        return enhanced_audio

    async def enhance_audio_bytes(self, audio_data: bytes) -> bytes:
        """Enhance audio data (async wrapper for HTTP endpoint).

        Args:
            audio_data: Raw audio data

        Returns:
            Enhanced audio data
        """
        start_time = time.time()

        try:
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
            audio_array = audio_array / 32768.0  # Normalize to [-1, 1]

            # Apply enhancement pipeline
            enhanced_array = self.enhance_audio_pipeline(
                audio_array,
                sample_rate=16000,
                apply_high_pass=True,
                high_pass_cutoff=80.0,
            )

            # Convert back to int16 and bytes
            enhanced_int16 = (enhanced_array * 32768.0).astype(np.int16)
            enhanced_bytes = enhanced_int16.tobytes()

            processing_time = (time.time() - start_time) * 1000

            logger.info(
                "audio_enhancer.enhancement_completed",
                input_size=len(audio_data),
                output_size=len(enhanced_bytes),
                processing_time_ms=processing_time,
            )

            return enhanced_bytes

        except Exception as exc:
            processing_time = (time.time() - start_time) * 1000
            logger.error(
                "audio_enhancer.enhancement_failed",
                error=str(exc),
                processing_time_ms=processing_time,
            )
            # Return original data on failure
            return audio_data

    def get_enhancement_info(self) -> dict[str, Any]:
        """Get information about enhancement capabilities.

        Returns:
            Dictionary with enhancement information
        """
        return {
            "enhancement_enabled": self._is_enhancement_enabled,
            "metricgan_available": self._metricgan_model is not None,
            "device": self.device,
            "model_source": self.model_source,
        }
