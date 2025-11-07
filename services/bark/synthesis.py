"""Bark TTS synthesis implementation.

This module provides the core text-to-speech functionality including:
- Bark TTS generation with multiple voice presets
- Voice selection and configuration
- Performance monitoring
"""

from __future__ import annotations

import io
import os
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

import numpy as np
import torch

# Import Bark with strict fail-fast
try:
    from bark import SAMPLE_RATE, generate_audio, preload_models
except ImportError as exc:
    raise ImportError(
        f"Required TTS library not available: {exc}. "
        "Bark service requires bark library. Use python-ml base image or "
        "explicitly install bark."
    ) from exc
from scipy.io.wavfile import write as write_wav

from services.common.model_loader import BackgroundModelLoader
from services.common.model_utils import force_download_bark
from services.common.structured_logging import get_logger
from services.common.permissions import check_directory_permissions
from services.common.gpu_utils import get_full_device_info, log_device_info

logger = get_logger(__name__)


@contextmanager
def _bark_environment_context() -> Generator[None, None, None]:
    """Context manager for Bark environment variable patching.

    Sets HOME and XDG_CACHE_HOME to /app and /app/models respectively,
    then restores original values on exit (even on exceptions).

    Yields:
        None - context manager for environment variable patching
    """
    original_home = os.environ.get("HOME")
    original_xdg_cache = os.environ.get("XDG_CACHE_HOME")

    # Set HOME to /app so bark can write to /app/.cache (within mounted volume)
    # Bark uses ~/.cache/suno/bark_v0 which requires HOME to be writable
    os.environ["HOME"] = "/app"

    # Also set XDG_CACHE_HOME as fallback (XDG spec)
    os.environ["XDG_CACHE_HOME"] = "/app/models"

    try:
        yield
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


def _check_force_download(logger: Any) -> bool:
    """Check if force download is enabled for Bark models.

    Args:
        logger: Structured logger instance

    Returns:
        True if force download is enabled, False otherwise
    """
    force_val = os.getenv("FORCE_MODEL_DOWNLOAD_BARK_MODELS", "").lower()
    global_val = os.getenv("FORCE_MODEL_DOWNLOAD", "false").lower()
    force_download = force_val in ("true", "1", "yes") or global_val in (
        "true",
        "1",
        "yes",
    )

    logger.info(
        "bark.force_download_check",
        force_download=force_download,
        phase="force_download_check",
    )

    return force_download


def _patch_pytorch_safe_globals(logger: Any) -> None:
    """Patch PyTorch 2.6+ compatibility: Allow numpy objects in torch.load.

    PyTorch 2.6+ defaults to weights_only=True, which restricts unpickling to safe types.
    Bark's checkpoints contain numpy objects that need explicit allowlisting.
    This patch adds numpy types to PyTorch's safe globals before model loading.

    Args:
        logger: Structured logger instance
    """
    import inspect

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
                    if attr_name.endswith("DType") and not attr_name.startswith("_"):
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
            import torch.serialization

            torch.serialization.add_safe_globals(safe_globals)
            logger.info(
                "bark.pytorch_safe_globals_patched",
                phase="pytorch_compatibility_patch",
                base_types=base_types,
                dtype_classes=dtype_type_names[:10],  # Log first 10 for brevity
                total_dtype_classes=len(dtype_type_names),
                total_types=len(safe_globals),
                message="PyTorch safe globals configured for numpy compatibility",
            )
        else:
            logger.warning(
                "bark.pytorch_safe_globals_empty",
                phase="pytorch_compatibility_patch",
                message="No numpy types discovered for safe globals",
            )

    except (ImportError, AttributeError) as patch_exc:
        logger.warning(
            "bark.pytorch_safe_globals_patch_failed",
            error=str(patch_exc),
            error_type=type(patch_exc).__name__,
            phase="pytorch_compatibility_patch_failed",
            exc_info=True,
        )
        # Continue anyway - might work with older PyTorch or different error handling


def _preload_bark_models(logger: Any) -> float:
    """Preload Bark models with configuration options.

    Args:
        logger: Structured logger instance

    Returns:
        Duration of preload operation in seconds
    """
    # Check if small models should be used (for memory-constrained environments)
    use_small_models = os.getenv("BARK_USE_SMALL_MODELS", "false").lower() in (
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

    logger.info(
        "bark.preload_models_starting",
        phase="preload_start",
        use_small_models=use_small_models,
        preload_parameters=preload_params,
        message="Loading Bark models (text, coarse, fine, codec)",
    )

    logger.debug(
        "bark.preload_models_parameters",
        phase="preload_params",
        text_use_small=use_small_models,
        coarse_use_small=use_small_models,
        fine_use_small=use_small_models,
        codec_use_gpu=torch.cuda.is_available(),
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

    return preload_duration


def _migrate_models_to_gpu(logger: Any) -> list[str]:
    """Migrate Bark models to GPU with FP16 quantization.

    Args:
        logger: Structured logger instance

    Returns:
        List of model names that were successfully moved to GPU
    """
    if not torch.cuda.is_available():
        return []

    try:
        # Access Bark's module-level model storage
        # NOTE: Bark stores models in bark.generation.models dictionary
        # Keys: "text", "coarse", "fine", "codec"
        # Text model is nested: models["text"]["model"], others are direct
        from bark.generation import models as bark_models

        device = torch.device("cuda")

        # Move models to GPU with FP16 quantization (matches FLAN pattern)
        models_moved = []

        # Text model is nested in a container
        if (
            "text" in bark_models
            and bark_models["text"] is not None
            and "model" in bark_models["text"]
            and bark_models["text"]["model"] is not None
        ):
            bark_models["text"]["model"] = (
                bark_models["text"]["model"].to(device).half()
            )
            models_moved.append("text")

        # Coarse and fine models are direct
        if "coarse" in bark_models and bark_models["coarse"] is not None:
            bark_models["coarse"] = bark_models["coarse"].to(device).half()
            models_moved.append("coarse")

        if "fine" in bark_models and bark_models["fine"] is not None:
            bark_models["fine"] = bark_models["fine"].to(device).half()
            models_moved.append("fine")

        if models_moved:
            logger.info(
                "bark.models_moved_to_gpu",
                models_moved=models_moved,
                device=str(device),
                phase="gpu_migration",
                message="Bark models successfully migrated to GPU with FP16 quantization",
            )

            # Log device info using common utilities
            try:
                # Get device info for one model (they should all be on same device)
                model_for_info = None
                if (
                    "text" in bark_models
                    and bark_models["text"] is not None
                    and "model" in bark_models["text"]
                    and bark_models["text"]["model"] is not None
                ):
                    model_for_info = bark_models["text"]["model"]
                elif "coarse" in bark_models and bark_models["coarse"] is not None:
                    model_for_info = bark_models["coarse"]
                elif "fine" in bark_models and bark_models["fine"] is not None:
                    model_for_info = bark_models["fine"]

                if model_for_info is not None:
                    device_info = get_full_device_info(
                        model=model_for_info, intended_device="cuda"
                    )
                    log_device_info(
                        logger,
                        "bark.models_loaded",
                        device_info,
                        phase="gpu_migration_complete",
                    )
            except Exception as device_info_exc:
                # Non-critical - device info logging failed, continue
                logger.debug(
                    "bark.device_info_logging_failed",
                    error=str(device_info_exc),
                    error_type=type(device_info_exc).__name__,
                    phase="gpu_migration_complete",
                    message="Failed to log device info, continuing",
                )
        else:
            logger.warning(
                "bark.no_models_found_for_gpu_migration",
                phase="gpu_migration",
                message="GPU available but no Bark models found to migrate",
            )

        return models_moved

    except (ImportError, AttributeError, KeyError) as e:
        # Graceful fallback - log warning, continue with CPU
        logger.warning(
            "bark.gpu_migration_failed",
            error=str(e),
            error_type=type(e).__name__,
            phase="gpu_migration",
            message="Failed to migrate Bark models to GPU, continuing with CPU",
        )
        return []
    except Exception as e:
        # Catch-all for other GPU migration errors
        logger.exception(
            "bark.gpu_migration_error",
            error=str(e),
            error_type=type(e).__name__,
            phase="gpu_migration_error",
            message="Unexpected error during GPU migration, continuing with CPU",
        )
        return []


def _compile_bark_models(logger: Any) -> tuple[list[str], str]:
    """Apply torch.compile() optimization to Bark models if enabled.

    Args:
        logger: Structured logger instance

    Returns:
        Tuple of (list of compiled model names, compile mode used)
    """
    # torch is imported at module level
    if not torch.cuda.is_available():  # noqa: F823
        return [], ""

    enable_compile = os.getenv("BARK_ENABLE_TORCH_COMPILE", "true").lower() in (
        "true",
        "1",
        "yes",
    )
    # Use "max-autotune-no-cudagraphs" mode for optimal performance without CUDA graphs
    # This mode performs extensive autotuning while explicitly avoiding CUDA graphs,
    # which are incompatible with Bark's in-place operations that overwrite tensors
    compile_mode = os.getenv("BARK_COMPILE_MODE", "max-autotune-no-cudagraphs")

    if not enable_compile or not hasattr(torch, "compile"):
        return [], compile_mode

    try:
        from bark.generation import models as bark_models

        # Configure torch._dynamo FIRST, before any compilation or model operations
        # This fixes getpwuid() errors in Docker containers without /etc/passwd entries
        # Must be set early to affect all subsequent torch.compile() calls
        # Use renamed import to avoid shadowing module-level torch variable
        try:
            from torch import _dynamo as torch_dynamo

            torch_dynamo.config.suppress_errors = True
            logger.info(
                "bark.torch_dynamo_configured",
                suppress_errors=True,
                phase="optimization_setup",
                message="torch._dynamo configured to suppress errors and fallback gracefully",
            )
        except (ImportError, AttributeError):
            # torch._dynamo not available, continue anyway
            logger.debug(
                "bark.torch_dynamo_unavailable",
                phase="optimization_setup",
                message="torch._dynamo not available, compilation may fail",
            )

        compile_start = time.time()
        compiled_models = []

        # Compile text model
        if (
            "text" in bark_models
            and bark_models["text"] is not None
            and "model" in bark_models["text"]
            and bark_models["text"]["model"] is not None
        ):
            try:
                bark_models["text"]["model"] = torch.compile(
                    bark_models["text"]["model"],
                    mode=compile_mode,
                )
                compiled_models.append("text")
            except Exception as e:
                logger.warning(
                    "bark.compile_failed",
                    model="text",
                    error=str(e),
                    error_type=type(e).__name__,
                )

        # Compile coarse model
        if "coarse" in bark_models and bark_models["coarse"] is not None:
            try:
                bark_models["coarse"] = torch.compile(
                    bark_models["coarse"],
                    mode=compile_mode,
                )
                compiled_models.append("coarse")
            except Exception as e:
                logger.warning(
                    "bark.compile_failed",
                    model="coarse",
                    error=str(e),
                    error_type=type(e).__name__,
                )

        # Compile fine model
        if "fine" in bark_models and bark_models["fine"] is not None:
            try:
                bark_models["fine"] = torch.compile(
                    bark_models["fine"],
                    mode=compile_mode,
                )
                compiled_models.append("fine")
            except Exception as e:
                logger.warning(
                    "bark.compile_failed",
                    model="fine",
                    error=str(e),
                    error_type=type(e).__name__,
                )

        compile_duration = (time.time() - compile_start) * 1000
        if compiled_models:
            logger.info(
                "bark.models_compiled",
                models=compiled_models,
                mode=compile_mode,
                duration_ms=round(compile_duration, 2),
                phase="optimization",
                message="torch.compile() optimization applied successfully",
            )
        else:
            logger.warning(
                "bark.compile_all_failed",
                mode=compile_mode,
                phase="optimization",
                message="torch.compile() failed for all models, continuing without compilation",
            )

        return compiled_models, compile_mode

    except (ImportError, AttributeError) as e:
        logger.warning(
            "bark.compile_setup_failed",
            error=str(e),
            error_type=type(e).__name__,
            phase="optimization",
            message="Failed to setup compilation, continuing without compilation",
        )
        return [], compile_mode


class BarkSynthesizer:
    """Bark TTS synthesizer with Piper fallback."""

    def __init__(self, config: Any) -> None:
        """Initialize Bark synthesizer.

        Args:
            config: Audio configuration
        """
        self.config = config
        self._logger = get_logger(__name__, service_name="bark")

        # Create wrapper function for preload_models that checks force download
        def _preload_models_with_force() -> None:
            """Wrapper for preload_models that orchestrates startup pipeline stages."""
            load_start = time.time()

            self._logger.info(
                "bark.model_load_start",
                phase="load_start",
            )

            # Use context manager for environment variable patching (automatic cleanup)
            with _bark_environment_context():
                try:
                    # Stage 1: Check force download flag
                    force_download = _check_force_download(self._logger)

                    # Stage 2: Handle force download if enabled
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

                    # Stage 3: Patch PyTorch safe globals for numpy compatibility
                    _patch_pytorch_safe_globals(self._logger)

                    # Stage 4: Preload Bark models
                    preload_duration = _preload_bark_models(self._logger)

                    # Stage 5: Migrate models to GPU (if available)
                    _migrate_models_to_gpu(self._logger)

                    # Stage 6: Compile models with torch.compile() if enabled
                    _compile_bark_models(self._logger)

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
                    # Calculate duration (load_start is guaranteed to exist)
                    duration: float = time.time() - load_start
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
                        duration_ms=round(duration * 1000, 2),
                        phase="preload_failed_permission",
                    )
                    raise
                except Exception as e:
                    # Calculate duration (load_start is guaranteed to exist)
                    error_duration: float = time.time() - load_start
                    self._logger.exception(
                        "bark.model_loading_failed",
                        error=str(e),
                        error_type=type(e).__name__,
                        duration_ms=round(error_duration * 1000, 2),
                        phase="preload_failed",
                    )
                    raise

        # Initialize model loader (side-effect function, no cache)
        # preload_models() doesn't return a model, it loads into memory via side effect
        self._model_loader = BackgroundModelLoader(
            cache_loader_func=None,  # Bark doesn't have cache, only download
            download_loader_func=_preload_models_with_force,
            logger=self._logger,
            loader_name="bark_models",
            is_side_effect=True,  # preload_models() doesn't return model
        )

        # Initialize result cache if enabled
        self._cache = None
        enable_cache = os.getenv("BARK_ENABLE_CACHE", "true").lower() in (
            "true",
            "1",
            "yes",
        )
        if enable_cache:
            try:
                from services.bark.cache import TTSCache

                max_entries = int(os.getenv("BARK_CACHE_MAX_ENTRIES", "100"))
                max_size_mb = int(os.getenv("BARK_CACHE_MAX_SIZE_MB", "500"))
                self._cache = TTSCache(max_entries=max_entries, max_size_mb=max_size_mb)
                self._logger.info(
                    "bark.cache_initialized",
                    max_entries=max_entries,
                    max_size_mb=max_size_mb,
                )
            except ImportError:
                self._logger.warning(
                    "bark.cache_unavailable",
                    message="TTSCache not available, continuing without caching",
                )
            except Exception as e:
                self._logger.warning(
                    "bark.cache_init_failed",
                    error=str(e),
                    message="Cache initialization failed, continuing without caching",
                )

        # Performance tracking
        self._synthesis_stats = {
            "total_syntheses": 0,
            "bark_syntheses": 0,
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

    async def cleanup(self) -> None:
        """Cleanup resources."""
        try:
            # Cleanup model loader
            await self._model_loader.cleanup()

            self._logger.info("bark_synthesizer.cleanup_completed")
        except Exception as exc:
            self._logger.error("bark_synthesizer.cleanup_failed", error=str(exc))

    def _generate_cache_key(self, text: str, voice: str, speed: float) -> str:
        """Generate SHA256 cache key from synthesis parameters.

        Args:
            text: Text to synthesize
            voice: Voice preset to use
            speed: Speech speed multiplier

        Returns:
            SHA256 hash as hexadecimal string
        """
        import hashlib

        key_data = f"{text}|{voice}|{speed}"
        return hashlib.sha256(key_data.encode("utf-8")).hexdigest()

    async def synthesize(
        self,
        text: str,
        voice: str = "v2/en_speaker_1",
        speed: float = 1.0,
        correlation_id: str | None = None,
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
        model_check_start = time.time()
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

        model_check_time = (time.time() - model_check_start) * 1000
        stage_timings: dict[str, float] = {"model_readiness_check_ms": model_check_time}

        self._logger.info(
            "bark.models_ready",
            check_duration_ms=model_check_time,
            correlation_id=correlation_id,
        )

        # Check cache before synthesis
        cache_key = self._generate_cache_key(text, voice, speed)
        if self._cache:
            cached_result = self._cache.get(cache_key)
            if cached_result:
                audio_bytes, engine = cached_result
                cache_stats = self._cache.get_stats()
                self._logger.info(
                    "bark.cache_hit",
                    cache_key=cache_key[:16],
                    audio_size_bytes=len(audio_bytes),
                    correlation_id=correlation_id,
                    cache_hit_rate=round(cache_stats["hit_rate"], 3),
                )
                return audio_bytes, engine

        try:
            start_time = time.time()

            # Verify device usage before synthesis
            device_check_start = time.time()
            if torch.cuda.is_available():
                try:
                    from bark.generation import models as bark_models

                    # Text model is nested, others are direct
                    model_to_check = None
                    if (
                        "text" in bark_models
                        and bark_models["text"] is not None
                        and "model" in bark_models["text"]
                        and bark_models["text"]["model"] is not None
                    ):
                        model_to_check = bark_models["text"]["model"]
                    elif "coarse" in bark_models and bark_models["coarse"] is not None:
                        model_to_check = bark_models["coarse"]
                    elif "fine" in bark_models and bark_models["fine"] is not None:
                        model_to_check = bark_models["fine"]

                    if model_to_check is not None:
                        device_info = get_full_device_info(
                            model=model_to_check, intended_device="cuda"
                        )
                        device_check_time = (time.time() - device_check_start) * 1000
                        stage_timings["device_check_ms"] = device_check_time
                        self._logger.info(
                            "bark.synthesis_device_check",
                            actual_device=device_info.get("actual_device", "unknown"),
                            model_on_device=device_info.get("model_on_device"),
                            check_duration_ms=device_check_time,
                            phase="pre_synthesis",
                            correlation_id=correlation_id,
                        )
                except Exception as device_check_exc:
                    # Non-critical verification - log at info level for troubleshooting
                    device_check_time = (time.time() - device_check_start) * 1000
                    stage_timings["device_check_ms"] = device_check_time
                    self._logger.info(
                        "bark.device_check_failed",
                        error=str(device_check_exc),
                        error_type=type(device_check_exc).__name__,
                        check_duration_ms=device_check_time,
                        phase="pre_synthesis",
                        message="Device verification failed, continuing with synthesis",
                        correlation_id=correlation_id,
                    )

            self._logger.info(
                "bark.synthesis_start",
                text_length=len(text),
                voice=voice,
                device_check_ms=stage_timings.get("device_check_ms", 0),
                correlation_id=correlation_id,
            )

            # Generate audio using Bark with inference mode for optimal performance
            # torch.inference_mode() disables autograd and version tracking, faster than torch.no_grad()

            # Use CUDA events for more accurate GPU timing if available
            use_cuda_timing = torch.cuda.is_available()
            if use_cuda_timing:
                try:
                    # Create CUDA events for precise GPU timing
                    start_event = torch.cuda.Event(enable_timing=True)
                    end_event = torch.cuda.Event(enable_timing=True)
                    start_event.record()
                except Exception:
                    use_cuda_timing = False

            generation_start = time.perf_counter()  # More precise than time.time()

            # Monitor GPU memory before generation (if available)
            gpu_memory_before = None
            if torch.cuda.is_available():
                try:
                    # Reset peak memory tracking for this generation
                    torch.cuda.reset_peak_memory_stats()
                    gpu_memory_before = torch.cuda.memory_allocated() / 1024**2  # MB
                except Exception as exc:
                    self._logger.debug(
                        "bark.cuda_memory_tracking_unavailable",
                        error=str(exc),
                        message="CUDA memory tracking not available, continuing without it",
                    )

            with torch.inference_mode():
                self._logger.debug(
                    "bark.using_inference_mode",
                    note="torch.inference_mode() enabled for optimal performance",
                )
                # Try to pass silent=True if supported (reduces overhead from progress bars)
                # Bark's generate_audio may not support all parameters, so we use try/except
                try:
                    audio_array = generate_audio(
                        text, history_prompt=voice, silent=True
                    )
                except TypeError:
                    # silent parameter not supported, use default call
                    audio_array = generate_audio(text, history_prompt=voice)

            # Synchronize CUDA operations for accurate timing
            if torch.cuda.is_available():
                torch.cuda.synchronize()

            generation_time_cpu = (time.perf_counter() - generation_start) * 1000

            # Get GPU timing if CUDA events were used
            generation_time_gpu = None
            if use_cuda_timing:
                try:
                    end_event.record()
                    torch.cuda.synchronize()
                    generation_time_gpu = start_event.elapsed_time(
                        end_event
                    )  # Already in ms
                except Exception as exc:
                    self._logger.debug(
                        "bark.cuda_timing_unavailable",
                        error=str(exc),
                        message="CUDA timing not available, using CPU timing",
                    )

            # Use GPU timing if available (more accurate), otherwise CPU timing
            generation_time = (
                generation_time_gpu
                if generation_time_gpu is not None
                else generation_time_cpu
            )

            # Monitor GPU memory after generation
            gpu_memory_after = None
            gpu_memory_used = None
            gpu_memory_peak = None
            if torch.cuda.is_available():
                try:
                    gpu_memory_after = torch.cuda.memory_allocated() / 1024**2  # MB
                    gpu_memory_peak = torch.cuda.max_memory_allocated() / 1024**2  # MB
                    if gpu_memory_before is not None:
                        gpu_memory_used = gpu_memory_after - gpu_memory_before
                except Exception as exc:
                    self._logger.debug(
                        "bark.cuda_memory_read_unavailable",
                        error=str(exc),
                        message="CUDA memory read not available, continuing without it",
                    )

            stage_timings["audio_generation_ms"] = generation_time

            self._logger.info(
                "bark.audio_generated",
                duration_ms=round(generation_time, 2),
                duration_cpu_ms=round(generation_time_cpu, 2)
                if generation_time_cpu
                else None,
                duration_gpu_ms=round(generation_time_gpu, 2)
                if generation_time_gpu
                else None,
                timing_method="cuda_events" if use_cuda_timing else "perf_counter",
                text_length=len(text),
                gpu_memory_before_mb=round(gpu_memory_before, 2)
                if gpu_memory_before
                else None,
                gpu_memory_after_mb=round(gpu_memory_after, 2)
                if gpu_memory_after
                else None,
                gpu_memory_peak_mb=round(gpu_memory_peak, 2)
                if gpu_memory_peak
                else None,
                gpu_memory_used_mb=round(gpu_memory_used, 2)
                if gpu_memory_used
                else None,
                correlation_id=correlation_id,
            )

            # Convert to WAV bytes
            conversion_start = time.time()
            audio_bytes = self._audio_to_bytes(audio_array, SAMPLE_RATE)
            conversion_time = (time.time() - conversion_start) * 1000
            stage_timings["audio_conversion_ms"] = conversion_time

            # Update stats
            processing_time = time.time() - start_time
            self._update_stats(processing_time, len(text), "bark")

            self._logger.info(
                "bark.synthesis_completed",
                total_duration_ms=processing_time * 1000,
                stage_timings=stage_timings,
                text_length=len(text),
                audio_size_bytes=len(audio_bytes),
                voice=voice,
                correlation_id=correlation_id,
            )

            # Cache result after successful synthesis
            if self._cache:
                self._cache.put(cache_key, audio_bytes, "bark")

            return audio_bytes, "bark"

        except Exception as exc:
            self._logger.error(
                "bark.synthesis_failed", error=str(exc), correlation_id=correlation_id
            )
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

        # Update averages
        self._synthesis_stats["avg_processing_time"] = (
            self._synthesis_stats["total_processing_time"]
            / self._synthesis_stats["total_syntheses"]
        )
        self._synthesis_stats["avg_text_length"] = (
            self._synthesis_stats["total_text_length"]
            / self._synthesis_stats["total_syntheses"]
        )
