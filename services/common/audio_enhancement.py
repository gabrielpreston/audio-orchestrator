"""Audio enhancement module for voice pipeline improvements.

This module provides audio enhancement functionality including:
- MetricGAN+ integration with lazy loading
- High-pass filtering
- Audio quality improvement
- Performance optimization

REQUIRES: Services using this module must use python-ml base image or explicitly
install scipy dependency.
"""

from __future__ import annotations

import os
import time
from typing import Any

import numpy as np

try:
    from scipy import signal
except ImportError as exc:
    raise ImportError(
        f"Required audio enhancement library not available: {exc}. "
        "Services using audio enhancement must use python-ml base image or "
        "explicitly install scipy."
    ) from exc

from services.common.model_loader import BackgroundModelLoader
from services.common.model_utils import force_download_speechbrain
from services.common.structured_logging import get_logger

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

        # Initialize model loader (truly lazy - only loads when used)
        # Create loader functions that capture instance variables
        def _load_from_cache() -> Any | None:
            """Try loading model from savedir if exists."""
            cache_start = time.time()
            logger.debug(
                "audio.cache_load_start",
                model_source=self.model_source,
                model_savedir=self.model_savedir,
                phase="cache_check",
            )

            if not os.path.exists(self.model_savedir):
                logger.debug(
                    "audio.cache_directory_not_found",
                    model_savedir=self.model_savedir,
                    phase="cache_check",
                )
                return None

            try:
                load_start = time.time()
                if self._enhancement_class is not None:
                    model = self._enhancement_class.from_hparams(
                        source=self.model_source, savedir=self.model_savedir
                    )
                else:
                    from speechbrain.inference.enhancement import (
                        SpectralMaskEnhancement,
                    )

                    model = SpectralMaskEnhancement.from_hparams(
                        source=self.model_source, savedir=self.model_savedir
                    )

                load_duration = time.time() - load_start
                total_duration = time.time() - cache_start

                logger.info(
                    "audio.model_loaded_from_cache",
                    model_source=self.model_source,
                    model_savedir=self.model_savedir,
                    load_duration_ms=round(load_duration * 1000, 2),
                    total_duration_ms=round(total_duration * 1000, 2),
                    phase="cache_load_complete",
                )
                return model
            except Exception as e:
                # Calculate duration if load_start exists, otherwise use None
                if "load_start" in locals():
                    load_duration = time.time() - load_start
                else:
                    load_duration = None
                logger.warning(
                    "audio.cache_load_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    model_savedir=self.model_savedir,
                    load_duration_ms=round(load_duration * 1000, 2)
                    if load_duration
                    else None,
                    phase="cache_load_failed",
                )
                return None

        def _load_with_download() -> Any:
            """Load model with download fallback."""
            download_start = time.time()

            # Check if force download is enabled via environment variable
            force_download = os.getenv(
                "FORCE_MODEL_DOWNLOAD_METRICGAN", ""
            ).lower() in (
                "true",
                "1",
                "yes",
            ) or os.getenv("FORCE_MODEL_DOWNLOAD", "false").lower() in (
                "true",
                "1",
                "yes",
            )

            logger.info(
                "audio.download_load_start",
                model_source=self.model_source,
                model_savedir=self.model_savedir,
                force_download=force_download,
                phase="download_start",
            )

            # Log exact parameters that will be passed to SpeechBrain model loader
            speechbrain_params: dict[str, Any] = {
                "source": self.model_source,
                "savedir": self.model_savedir,
            }
            if force_download:
                speechbrain_params["force"] = True

            logger.debug(
                "audio.speechbrain_load_parameters",
                phase="model_load_params",
                speechbrain_parameters=speechbrain_params,
                force_download=force_download,
                message="Parameters for SpectralMaskEnhancement.from_hparams",
            )

            # Use force download helper if enabled
            if force_download:
                logger.info(
                    "audio.force_download_enabled",
                    model_source=self.model_source,
                    phase="force_download_prep",
                )
                load_start = time.time()
                model = force_download_speechbrain(
                    model_source=self.model_source,
                    savedir=self.model_savedir,
                    force=True,
                    enhancement_class=self._enhancement_class,
                )
                load_duration = time.time() - load_start
            else:
                logger.debug(
                    "audio.downloading_model",
                    model_source=self.model_source,
                    phase="model_download",
                )
                load_start = time.time()
                if self._enhancement_class is not None:
                    model = self._enhancement_class.from_hparams(
                        source=self.model_source, savedir=self.model_savedir
                    )
                else:
                    from speechbrain.inference.enhancement import (
                        SpectralMaskEnhancement,
                    )

                    model = SpectralMaskEnhancement.from_hparams(
                        source=self.model_source, savedir=self.model_savedir
                    )
                load_duration = time.time() - load_start

            total_duration = time.time() - download_start

            logger.info(
                "audio.model_downloaded_and_loaded",
                model_source=self.model_source,
                model_savedir=self.model_savedir,
                force_download=force_download,
                load_duration_ms=round(load_duration * 1000, 2),
                total_duration_ms=round(total_duration * 1000, 2),
                phase="download_complete",
            )
            return model

        # Create model loader with background loading disabled (truly lazy)
        self._model_loader = BackgroundModelLoader(
            cache_loader_func=_load_from_cache if enable_metricgan else None,
            download_loader_func=_load_with_download
            if enable_metricgan
            else lambda: None,
            logger=logger,
            loader_name="metricgan",
            enable_background_load=False,  # Truly lazy - only load when used
        )

        if self.enable_metricgan:
            logger.info("audio_enhancer.metricgan_enabled_but_not_loaded")

    @property
    def is_enhancement_enabled(self) -> bool:
        """Check if enhancement is available."""
        return self._model_loader.is_loaded() if self.enable_metricgan else False

    def apply_high_pass_filter(
        self,
        audio: np.ndarray[Any, np.dtype[np.float32]],
        sample_rate: int = 16000,
        cutoff_freq: float = 80.0,
    ) -> Any:
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
            return np.asarray(filtered_audio, dtype=np.float32)

        except (ValueError, RuntimeError) as exc:
            logger.error("audio_enhancer.high_pass_failed", error=str(exc))
            return audio

    def enhance_audio(
        self,
        audio: np.ndarray[Any, np.dtype[np.float32]],
        sample_rate: int = 16000,
    ) -> Any:
        """Apply MetricGAN+ enhancement to audio.

        Args:
            audio: Input audio array (float32, shape: [samples])
            sample_rate: Sample rate of audio

        Returns:
            Enhanced audio array
        """
        # Graceful handling: If model not loaded and not loading, return original audio
        if not self.enable_metricgan:
            return audio

        # Try to load model if not loaded (lazy loading)
        # Note: This is sync because enhance_audio is sync, but loader is async
        # We handle this gracefully by returning original audio if not available
        if not self._model_loader.is_loaded():
            # Check if loading (don't block)
            if self._model_loader.is_loading():
                logger.debug("audio_enhancer.model_loading")
                return audio
            # Try lazy load - but this is async, so we can't wait here
            # For now, just return original audio if not loaded
            logger.debug("audio_enhancer.model_not_loaded")
            return audio

        # Get model from loader
        self._metricgan_model = self._model_loader.get_model()
        if self._metricgan_model is None:
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
            return np.asarray(enhanced_audio, dtype=np.float32)

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
            enhanced_bytes = bytes(enhanced_int16.tobytes())

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
            "enhancement_enabled": self.is_enhancement_enabled,
            "metricgan_available": self._metricgan_model is not None,
            "device": self.device,
            "model_source": self.model_source,
        }
