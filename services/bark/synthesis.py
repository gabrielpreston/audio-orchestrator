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

from services.common.model_loader import BackgroundModelLoader
from services.common.model_utils import force_download_bark
from services.common.structured_logging import get_logger
from services.common.permissions import check_directory_permissions

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

        # Create wrapper function for preload_models that checks force download
        def _preload_models_with_force() -> None:
            """Wrapper for preload_models that checks force download."""
            import time

            if preload_models is None:
                return

            load_start = time.time()

            # Check environment variable directly (loader not yet created)
            import os

            force_val = os.getenv("FORCE_MODEL_DOWNLOAD_BARK_MODELS", "").lower()
            global_val = os.getenv("FORCE_MODEL_DOWNLOAD", "false").lower()
            force_download = force_val in ("true", "1", "yes") or global_val in (
                "true",
                "1",
                "yes",
            )

            self._logger.info(
                "bark.model_load_start",
                force_download=force_download,
                phase="load_start",
            )

            # Set HOME to /app so bark can write to /app/.cache (within mounted volume)
            # Bark uses ~/.cache/suno/bark_v0 which requires HOME to be writable
            original_home = os.environ.get("HOME")
            os.environ["HOME"] = "/app"

            # Also set XDG_CACHE_HOME as fallback (XDG spec)
            original_xdg_cache = os.environ.get("XDG_CACHE_HOME")
            os.environ["XDG_CACHE_HOME"] = "/app/models"

            try:
                if force_download:
                    force_download_start = time.time()
                    force_download_bark(force=True)
                    force_download_duration = time.time() - force_download_start
                    self._logger.info(
                        "bark.force_download_enabled",
                        force_download_duration_ms=round(
                            force_download_duration * 1000, 2
                        ),
                        phase="force_download_prep",
                    )

                # Patch PyTorch 2.6+ compatibility: Allow numpy objects in torch.load
                # PyTorch 2.6+ defaults to weights_only=True, which restricts unpickling to safe types.
                # Bark's checkpoints contain numpy objects that need explicit allowlisting.
                # This patch adds numpy types to PyTorch's safe globals before model loading.
                import inspect
                import torch.serialization

                try:
                    safe_globals: list[Any] = []
                    dtype_type_names: list[str] = []

                    # Add base numpy types (compatible with all numpy versions)
                    from numpy.core.multiarray import scalar as numpy_scalar

                    safe_globals.append(numpy_scalar)
                    safe_globals.append(np.dtype)
                    base_types = ["numpy.core.multiarray.scalar", "numpy.dtype"]

                    # Discover and add all concrete dtype classes from numpy.dtypes
                    # NumPy 1.24+ provides numpy.dtypes with concrete DType classes
                    if hasattr(np, "dtypes"):
                        try:
                            import numpy.dtypes as numpy_dtypes

                            for attr_name in dir(numpy_dtypes):
                                # Only consider DType classes (exclude private attributes)
                                if attr_name.endswith(
                                    "DType"
                                ) and not attr_name.startswith("_"):
                                    try:
                                        dtype_class = getattr(numpy_dtypes, attr_name)
                                        # Only add actual classes, not instances or other types
                                        if inspect.isclass(dtype_class):
                                            safe_globals.append(dtype_class)
                                            dtype_type_names.append(attr_name)
                                    except (AttributeError, TypeError):
                                        # Skip attributes that can't be accessed or aren't classes
                                        continue

                            # Sort for consistent logging
                            dtype_type_names.sort()
                        except (ImportError, AttributeError):
                            # numpy.dtypes module not available or not accessible
                            pass

                    # Register all discovered numpy types with PyTorch
                    if safe_globals:
                        torch.serialization.add_safe_globals(safe_globals)
                        self._logger.info(
                            "bark.pytorch_safe_globals_patched",
                            phase="pytorch_compatibility_patch",
                            base_types=base_types,
                            dtype_classes=dtype_type_names[
                                :10
                            ],  # Log first 10 for brevity
                            total_dtype_classes=len(dtype_type_names),
                            total_types=len(safe_globals),
                            message="PyTorch safe globals configured for numpy compatibility",
                        )
                    else:
                        self._logger.warning(
                            "bark.pytorch_safe_globals_empty",
                            phase="pytorch_compatibility_patch",
                            message="No numpy types discovered for safe globals",
                        )

                except (ImportError, AttributeError) as patch_exc:
                    self._logger.warning(
                        "bark.pytorch_safe_globals_patch_failed",
                        error=str(patch_exc),
                        error_type=type(patch_exc).__name__,
                        phase="pytorch_compatibility_patch_failed",
                        exc_info=True,
                    )
                    # Continue anyway - might work with older PyTorch or different error handling

                # Call preload_models (side-effect function)
                # Check if small models should be used (for memory-constrained environments)
                import os

                use_small_models = os.getenv(
                    "BARK_USE_SMALL_MODELS", "false"
                ).lower() in (
                    "true",
                    "1",
                    "yes",
                )

                preload_start = time.time()

                # Log the exact parameters that will be passed to preload_models
                preload_params = {
                    "text_use_small": use_small_models,
                    "coarse_use_small": use_small_models,
                    "fine_use_small": use_small_models,
                    "codec_use_gpu": torch.cuda.is_available(),
                }

                self._logger.info(
                    "bark.preload_models_starting",
                    phase="preload_start",
                    use_small_models=use_small_models,
                    preload_parameters=preload_params,
                    message="Loading Bark models (text, coarse, fine, codec)",
                )

                self._logger.debug(
                    "bark.preload_models_parameters",
                    phase="preload_params",
                    text_use_small=use_small_models,
                    coarse_use_small=use_small_models,
                    fine_use_small=use_small_models,
                    codec_use_gpu=False,
                    message="Calling preload_models with these exact parameters",
                )

                # Use small models if configured to reduce memory footprint
                # Small models use ~50% less memory but with reduced quality
                preload_models(
                    text_use_small=use_small_models,
                    coarse_use_small=use_small_models,
                    fine_use_small=use_small_models,
                    codec_use_gpu=torch.cuda.is_available(),  # Use GPU if available
                )
                preload_duration = time.time() - preload_start
                total_duration = time.time() - load_start

                self._logger.info(
                    "bark.models_preloaded",
                    preload_duration_ms=round(preload_duration * 1000, 2),
                    total_duration_ms=round(total_duration * 1000, 2),
                    phase="preload_complete",
                )

                # Reset force download env var if it was set
                if force_download:
                    force_download_bark(force=False)
            except PermissionError as e:
                import os
                import time

                # Calculate duration if load_start exists, otherwise use None
                if "load_start" in locals():
                    total_duration = time.time() - load_start
                else:
                    total_duration = None
                home_diagnostics = check_directory_permissions("/app")
                cache_diagnostics = check_directory_permissions("/app/models")
                self._logger.exception(
                    "bark.model_loading_permission_error",
                    error=str(e),
                    error_type=type(e).__name__,
                    home_dir="/app",
                    home_diagnostics=home_diagnostics,
                    cache_dir="/app/models",
                    cache_diagnostics=cache_diagnostics,
                    user_id=os.getuid(),
                    group_id=os.getgid(),
                    duration_ms=round(total_duration * 1000, 2)
                    if total_duration
                    else None,
                    phase="preload_failed_permission",
                )
                raise
            except Exception as e:
                import time

                # Calculate duration if load_start exists, otherwise use None
                if "load_start" in locals():
                    total_duration = time.time() - load_start
                else:
                    total_duration = None
                self._logger.exception(
                    "bark.model_loading_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    duration_ms=round(total_duration * 1000, 2)
                    if total_duration
                    else None,
                    phase="preload_failed",
                )
                raise
            finally:
                # Restore original environment variables
                if original_home:
                    os.environ["HOME"] = original_home
                elif "HOME" in os.environ:
                    del os.environ["HOME"]

                if original_xdg_cache:
                    os.environ["XDG_CACHE_HOME"] = original_xdg_cache
                elif "XDG_CACHE_HOME" in os.environ:
                    del os.environ["XDG_CACHE_HOME"]

        # Initialize model loader (side-effect function, no cache)
        # preload_models() doesn't return a model, it loads into memory via side effect
        self._model_loader = BackgroundModelLoader(
            cache_loader_func=None,  # Bark doesn't have cache, only download
            download_loader_func=_preload_models_with_force,
            logger=self._logger,
            loader_name="bark_models",
            is_side_effect=True,  # preload_models() doesn't return model
        )

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
            # Start background model loading (non-blocking)
            await self._model_loader.initialize()
            self._logger.info("bark_synthesizer.initialized")
        except Exception as exc:
            self._logger.error("bark_synthesizer.initialization_failed", error=str(exc))
            # Continue without Bark - will use Piper fallback

    async def cleanup(self) -> None:
        """Cleanup resources."""
        try:
            # Cleanup model loader
            await self._model_loader.cleanup()

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

        Raises:
            RuntimeError: If models are not available or loading failed
        """
        # Check if models are still loading (non-blocking check)
        if self._model_loader.is_loading():
            raise RuntimeError(
                "Bark models are currently loading. Please try again shortly."
            )

        # Ensure models are loaded (lazy load if needed)
        if not await self._model_loader.ensure_loaded():
            status = self._model_loader.get_status()
            error_msg = status.get("error", "Unknown error")
            raise RuntimeError(f"Bark models not available: {error_msg}")

        # Verify models are loaded before proceeding
        if not self._model_loader.is_loaded():
            raise RuntimeError("Bark models not available")

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
        return self._model_loader.is_loaded()

    async def get_metrics(self) -> dict[str, Any]:
        """Get synthesis metrics."""
        return {
            "synthesis_stats": self._synthesis_stats,
            "models_loaded": self._model_loader.is_loaded(),
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
