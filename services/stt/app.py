from collections.abc import Iterable
import io
import os
import time
from typing import Any, cast
import wave

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile
from starlette.requests import ClientDisconnect

from services.common.config import (
    ServiceConfig,
    get_service_preset,
    load_config_from_env,
)
from services.common.app_factory import create_service_app
from services.common.gpu_utils import (
    get_pytorch_cuda_info,
    validate_cuda_runtime as validate_cuda_runtime_common,
)
from services.common.health import HealthManager
from services.common.health_endpoints import HealthEndpoints
from services.common.model_loader import BackgroundModelLoader
from services.common.model_utils import force_download_faster_whisper
from services.common.structured_logging import configure_logging, get_logger
from services.common.tracing import get_observability_manager
from services.common.permissions import ensure_model_directory

from .audio_processor_client import STTAudioProcessorClient


# Configuration classes are now handled by the new config system


# Centralized configuration
_cfg: ServiceConfig = load_config_from_env(ServiceConfig, **get_service_preset("stt"))

MODEL_NAME = _cfg.faster_whisper.model
MODEL_PATH = _cfg.faster_whisper.model_path or "/app/models"
# Module-level cached model to avoid repeated loads
_model: Any = None
# Model loader for background loading
_model_loader: BackgroundModelLoader | None = None
# Transcript result cache for caching identical audio requests
_transcript_cache: Any | None = None  # ResultCache[dict[str, Any]] | None
# Audio processor client for remote enhancement
_audio_processor_client: STTAudioProcessorClient | None = None
# Health manager for service resilience
_health_manager = HealthManager("stt")
# Observability manager for metrics and tracing
_observability_manager = None
_stt_metrics: dict[str, Any] = {}
_http_metrics: dict[str, Any] = {}


configure_logging(
    _cfg.logging.level,
    json_logs=_cfg.logging.json_logs,
    service_name="stt",
)
logger = get_logger(__name__, service_name="stt")


def _check_cudnn_library() -> bool:
    """Check if required CUDNN libraries (especially libcudnn_ops) are available.

    Returns:
        True if CUDNN ops library appears to be available, False otherwise
    """
    import ctypes.util
    import os
    import sysconfig

    # Strategy 1: Check file system paths first (most reliable)
    # This checks where the Dockerfile actually installs the libraries
    # Also check PyTorch's bundled CUDNN location (PyTorch includes CUDNN)
    site_packages_paths = [
        sysconfig.get_path("purelib"),
        sysconfig.get_path("platlib"),
    ]
    pytorch_cudnn_paths = [
        os.path.join(sp, "nvidia", "cudnn", "lib")
        for sp in site_packages_paths
        if os.path.exists(os.path.join(sp, "nvidia", "cudnn", "lib"))
    ]

    library_paths = [
        "/usr/local/cuda/lib64",
        "/usr/lib/x86_64-linux-gnu",
        "/usr/lib",
        "/lib/x86_64-linux-gnu",
        "/lib",
        *pytorch_cudnn_paths,
    ]

    # Add LD_LIBRARY_PATH paths
    ld_path = os.environ.get("LD_LIBRARY_PATH", "")
    if ld_path:
        for path in ld_path.split(":"):
            if path and path not in library_paths:
                library_paths.append(path)

    # Check each path for cudnn_ops library files
    for lib_path in library_paths:
        if not lib_path or not os.path.exists(lib_path):
            continue
        try:
            files = os.listdir(lib_path)
            for f in files:
                if "cudnn_ops" in f.lower() and (f.endswith(".so") or ".so." in f):
                    logger.debug(
                        "stt.cudnn_ops_found",
                        library_path=lib_path,
                        library_file=f,
                        phase="cudnn_detection",
                    )
                    return True
        except (OSError, PermissionError, Exception) as e:
            logger.debug(
                "stt.cudnn_path_check_failed",
                library_path=lib_path,
                error=str(e),
                phase="cudnn_detection",
            )
            continue

    # Strategy 2: Try ctypes.util.find_library (uses system library cache)
    # This searches standard system library paths and ldconfig cache
    try:
        found_lib_path: str | None = ctypes.util.find_library("cudnn_ops")
        if found_lib_path:
            logger.debug(
                "stt.cudnn_ops_found_via_ctypes",
                library_path=found_lib_path,
                phase="cudnn_detection",
            )
            return True
    except Exception as e:
        logger.debug(
            "stt.ctypes_find_library_failed",
            error=str(e),
            phase="cudnn_detection",
        )

    # Strategy 3: Try direct loading from known paths with specific version names
    # CTranslate2 looks for version 9.x, but we check both version 9 and 8 for compatibility
    cudnn_ops_names = [
        "libcudnn_ops.so.9",
        "libcudnn_ops.so.9.1",
        "libcudnn_ops.so.9.1.0",
        "libcudnn_ops.so.8",
        "libcudnn_ops.so.8.9",
        "libcudnn_ops.so.8.9.0",
        "libcudnn_ops.so",
    ]

    for lib_name in cudnn_ops_names:
        # Try loading from each library path
        for lib_path in library_paths:
            if not lib_path or not os.path.exists(lib_path):
                continue
            try:
                full_path = os.path.join(lib_path, lib_name)
                if os.path.exists(full_path):
                    # Try to actually load the library to verify it's valid
                    try:
                        ctypes.CDLL(full_path)
                        logger.debug(
                            "stt.cudnn_ops_loaded",
                            library_path=full_path,
                            phase="cudnn_detection",
                        )
                        return True
                    except (OSError, AttributeError) as e:
                        logger.debug(
                            "stt.cudnn_ops_load_failed",
                            library_path=full_path,
                            error=str(e),
                            phase="cudnn_detection",
                        )
                        continue
            except Exception as e:
                logger.debug(
                    "stt.cudnn_ops_check_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    phase="cudnn_detection",
                    message="Failed to check CUDA ops library, continuing",
                )
                continue

    logger.debug(
        "stt.cudnn_ops_not_found",
        checked_paths=library_paths,
        phase="cudnn_detection",
    )
    return False


def _validate_and_adjust_cuda_device(
    device: str, compute_type: str | None
) -> tuple[str, str | None]:
    """Validate CUDA availability and adjust device/compute_type if needed.

    Args:
        device: Requested device ("cuda" or "cpu")
        compute_type: Requested compute type

    Returns:
        Tuple of (adjusted_device, adjusted_compute_type)
    """
    original_device = device
    original_compute_type = compute_type

    if device != "cuda":
        logger.debug(
            "stt.device_validation_skipped",
            device=device,
            reason="not_cuda",
            phase="device_validation",
        )
        return device, compute_type

    logger.info(
        "stt.cuda_validation_starting",
        requested_device=device,
        requested_compute_type=compute_type,
        phase="device_validation",
    )

    # CRITICAL: Check for CUDNN ops library first (required by CTranslate2)
    # This prevents segfaults during inference
    cudnn_available = _check_cudnn_library()
    if not cudnn_available:
        logger.error(
            "stt.cudnn_ops_library_missing",
            reason="libcudnn_ops.so not found",
            fallback="cpu",
            fallback_reason="cudnn_ops_library_missing",
            note="CTranslate2 (used by faster-whisper) requires CUDNN ops library for CUDA inference",
            phase="device_validation",
        )
        return "cpu", "int8"

    # Check if CUDA is available via PyTorch
    try:
        import torch

        cuda_available = torch.cuda.is_available()

        if not cuda_available:
            logger.warning(
                "stt.cuda_not_available",
                reason="torch.cuda.is_available() returned False",
                fallback="cpu",
                phase="device_validation",
            )
            return "cpu", "int8"  # CPU-compatible compute type

        # Additional check: verify CUDA runtime actually works
        try:
            test_tensor = torch.zeros(1).cuda()
            del test_tensor
            torch.cuda.empty_cache()
            logger.info("stt.cuda_runtime_validated", phase="device_validation")
            # CUDA appears to work via PyTorch, but faster-whisper uses CTranslate2
            # which may have different CUDA requirements. We'll proceed with CUDA
            # but log a warning that CTranslate2 might still fail.
            logger.warning(
                "stt.cuda_pytorch_works_but_ctranslate2_may_fail",
                note="faster-whisper uses CTranslate2 which may have different CUDA requirements",
                phase="device_validation",
            )
            return device, compute_type  # CUDA is working
        except RuntimeError as e:
            error_str = str(e).lower()
            # Check for specific CUDA library errors
            if (
                "cudnn" in error_str
                or "invalid handle" in error_str
                or "cuda error" in error_str
            ):
                logger.error(
                    "stt.cuda_library_error_detected",
                    error=str(e),
                    fallback="cpu",
                    phase="device_validation",
                )
                return "cpu", "int8"
            logger.warning(
                "stt.cuda_runtime_test_failed",
                error=str(e),
                fallback="cpu",
                phase="device_validation",
            )
            return "cpu", "int8"
        except Exception as e:
            # Other CUDA-related errors (e.g., out of memory, initialization issues)
            error_str = str(e).lower()
            if "cudnn" in error_str or "invalid handle" in error_str:
                logger.error(
                    "stt.cuda_library_error_during_validation",
                    error=str(e),
                    error_type=type(e).__name__,
                    fallback="cpu",
                    phase="device_validation",
                )
            else:
                logger.warning(
                    "stt.cuda_error_during_validation",
                    error=str(e),
                    error_type=type(e).__name__,
                    fallback="cpu",
                    phase="device_validation",
                )
            return "cpu", "int8"
    except ImportError:
        logger.warning(
            "stt.torch_not_available", fallback="cpu", phase="device_validation"
        )
        return "cpu", "int8"
    except Exception as e:
        # Unexpected error during CUDA check
        logger.error(
            "stt.cuda_validation_error",
            error=str(e),
            error_type=type(e).__name__,
            fallback="cpu",
            phase="device_validation",
        )
        return "cpu", "int8"
    finally:
        # Log the final decision with more detail
        if device != original_device or compute_type != original_compute_type:
            logger.warning(
                "stt.device_adjusted",
                original_device=original_device,
                adjusted_device=device,
                original_compute_type=original_compute_type,
                adjusted_compute_type=compute_type,
                phase="device_validation",
            )
        elif device == "cuda":
            # Log successful CUDA validation
            # Get additional CUDA info for successful validation
            try:
                import torch

                if torch.cuda.is_available():
                    logger.info(
                        "stt.cuda_validation_successful",
                        device=device,
                        compute_type=compute_type,
                        cuda_device_count=torch.cuda.device_count(),
                        cuda_device_name=torch.cuda.get_device_name(0)
                        if torch.cuda.device_count() > 0
                        else None,
                        phase="device_validation",
                    )
                else:
                    logger.warning(
                        "stt.cuda_validation_uncertain",
                        device=device,
                        note="Device set to CUDA but torch.cuda.is_available() is False",
                        phase="device_validation",
                    )
            except ImportError:
                logger.warning(
                    "stt.cuda_validation_without_torch",
                    device=device,
                    note="PyTorch not available for CUDA validation",
                    phase="device_validation",
                )
            except RuntimeError:
                logger.debug(
                    "stt.cuda_info_unavailable",
                    device=device,
                    compute_type=compute_type,
                    phase="device_validation",
                )


def _validate_cuda_runtime() -> bool:
    """Validate CUDA runtime is actually usable for inference.

    Uses common utility but kept here for backward compatibility.

    Returns:
        True if CUDA is available and working, False otherwise
    """
    return validate_cuda_runtime_common()


def _get_model_device_info(model: Any) -> dict[str, Any]:
    """Get device information from the loaded faster-whisper/CTranslate2 model.

    This is STT-specific because faster-whisper uses CTranslate2 which has different
    device access patterns than standard PyTorch models.

    Args:
        model: WhisperModel instance (from faster-whisper)

    Returns:
        Dict with device information compatible with get_full_device_info format
    """
    # Start with PyTorch CUDA info from common utility
    cuda_info = get_pytorch_cuda_info()
    device_info = {
        "actual_device": "unknown",
        "device_verified": False,
        "model_on_device": None,
        **cuda_info,
    }

    # Try to get device from faster-whisper/CTranslate2 model
    # faster-whisper uses CTranslate2 which may expose device info
    try:
        # Check if model has a device attribute (some versions do)
        if hasattr(model, "device"):
            device_value = model.device
            if device_value:
                device_str = str(device_value).lower()
                device_info["model_on_device"] = device_str
                # Extract "cuda" or "cpu" from "cuda:0" or "cpu"
                base_device = device_str.split(":")[0]
                device_info["actual_device"] = base_device
                device_info["device_verified"] = True
    except Exception as e:
        logger.debug(
            "stt.device_info_check_failed",
            error=str(e),
            error_type=type(e).__name__,
            phase="device_info",
            message="Failed to check model device, continuing",
        )

    # Try to access underlying CTranslate2 model
    try:
        if hasattr(model, "model") and hasattr(model.model, "device"):
            device_value = model.model.device
            if device_value:
                device_str = str(device_value).lower()
                device_info["model_on_device"] = device_str
                base_device = device_str.split(":")[0]
                device_info["actual_device"] = base_device
                device_info["device_verified"] = True
    except Exception as e:
        logger.debug(
            "stt.device_info_ctranslate2_check_failed",
            error=str(e),
            error_type=type(e).__name__,
            phase="device_info",
            message="Failed to check CTranslate2 model device, continuing",
        )

    # Try to check CTranslate2 translator device
    try:
        if hasattr(model, "model") and hasattr(model.model, "translator"):
            translator = model.model.translator
            if hasattr(translator, "device"):
                device_value = translator.device
                if device_value:
                    device_str = str(device_value).lower()
                    device_info["model_on_device"] = device_str
                    base_device = device_str.split(":")[0]
                    device_info["actual_device"] = base_device
                    device_info["device_verified"] = True
    except Exception as e:
        logger.debug(
            "stt.device_info_translator_check_failed",
            error=str(e),
            error_type=type(e).__name__,
            phase="device_info",
            message="Failed to check translator device, continuing",
        )

    return device_info


def _load_from_cache() -> Any | None:
    """Try loading model from local cache."""
    import time

    cache_start = time.time()
    logger.debug(
        "stt.cache_load_start",
        model_name=MODEL_NAME,
        model_path=MODEL_PATH,
        phase="cache_check",
    )

    try:
        from faster_whisper import WhisperModel
    except Exception as e:
        logger.error(
            "stt.model_import_failed",
            error=str(e),
            error_type=type(e).__name__,
            phase="import_check",
        )
        return None

    # Check if we have a local model directory
    local_model_path = os.path.join(MODEL_PATH, MODEL_NAME)
    if not os.path.exists(local_model_path):
        logger.debug(
            "stt.cache_directory_not_found",
            model_path=local_model_path,
            phase="cache_check",
        )
        return None

    logger.debug(
        "stt.cache_directory_found",
        model_path=local_model_path,
        phase="cache_found",
    )

    # Try loading from local path
    device = _cfg.faster_whisper.device
    compute_type = _cfg.faster_whisper.compute_type

    # Validate CUDA availability and adjust if needed
    device, compute_type = _validate_and_adjust_cuda_device(device, compute_type)

    # Validate device/compute_type compatibility
    if device == "cpu" and compute_type == "float16":
        compute_type = "int8"
        logger.debug(
            "stt.compute_type_adjusted",
            original="float16",
            adjusted="int8",
            reason="CPU does not support float16",
        )

    load_start = time.time()
    try:
        # Try to create model with the validated device
        # If CUDA fails during initialization, catch and fallback
        try:
            if compute_type:
                model = WhisperModel(
                    local_model_path, device=device, compute_type=compute_type
                )
            else:
                model = WhisperModel(local_model_path, device=device)
        except (RuntimeError, OSError, Exception) as model_init_error:
            error_str = str(model_init_error).lower()
            # Check for CUDA-related errors during model initialization
            if device == "cuda" and (
                "cuda" in error_str
                or "cudnn" in error_str
                or "gpu" in error_str
                or "invalid handle" in error_str
                or "cuda error" in error_str
            ):
                logger.error(
                    "stt.cuda_model_init_failed",
                    error=str(model_init_error),
                    error_type=type(model_init_error).__name__,
                    original_device=device,
                    original_compute_type=compute_type,
                    fallback="cpu",
                    phase="model_initialization",
                )
                # Fallback to CPU
                device = "cpu"
                compute_type = "int8"
                # Retry with CPU
                if compute_type:
                    model = WhisperModel(
                        local_model_path, device=device, compute_type=compute_type
                    )
                else:
                    model = WhisperModel(local_model_path, device=device)
                logger.warning(
                    "stt.model_reloaded_with_cpu",
                    original_device="cuda",
                    reason="cuda_init_failed",
                    phase="model_initialization",
                )
            else:
                # Not a CUDA error, re-raise
                raise

        load_duration = time.time() - load_start
        total_duration = time.time() - cache_start

        # Get actual device information from the loaded model (STT-specific for CTranslate2)
        model_device_info = _get_model_device_info(model)
        # Merge with intended device to match common format
        device_info = {
            "intended_device": device,
            **model_device_info,
        }

        logger.info(
            "stt.model_loaded_from_cache",
            model_name=MODEL_NAME,
            model_path=local_model_path,
            device=device,  # Intended device
            compute_type=compute_type or "default",  # Intended compute_type
            load_duration_ms=round(load_duration * 1000, 2),
            total_duration_ms=round(total_duration * 1000, 2),
            phase="cache_load_complete",
        )

        # Log device info using common utility pattern (matches FLAN)
        # Get config device to compare with actual
        config_device = _cfg.faster_whisper.device if _cfg else "unknown"
        if config_device == "cuda" and device_info.get("actual_device") != "cuda":
            logger.warning(
                "stt.device_mismatch_detected",
                intended_device=config_device,
                actual_device=device_info.get("actual_device", "unknown"),
                model_on_device=device_info.get("model_on_device"),
                note="Model may have fallen back to CPU despite CUDA request",
                phase="cache_load_complete",
            )
        elif config_device == "cuda" and device_info.get("actual_device") == "cuda":
            logger.info(
                "stt.gpu_usage_confirmed",
                device=device_info.get("actual_device"),
                gpu_name=device_info.get("pytorch_cuda_device_name"),
                phase="cache_load_complete",
            )

        # Log comprehensive device info in structured format
        logger.info(
            "stt.model_loaded_from_cache.device_info",
            intended_device=config_device,
            actual_device=device_info.get("actual_device", "unknown"),
            device_verified=device_info.get("device_verified", False),
            model_on_device=device_info.get("model_on_device"),
            pytorch_cuda_available=device_info.get("pytorch_cuda_available", False),
            pytorch_cuda_device_count=device_info.get("pytorch_cuda_device_count", 0),
            pytorch_cuda_device_name=device_info.get("pytorch_cuda_device_name"),
            phase="cache_load_complete",
        )

        return model
    except Exception as e:
        load_duration = time.time() - load_start
        logger.warning(
            "stt.cache_load_failed",
            error=str(e),
            error_type=type(e).__name__,
            model_path=local_model_path,
            load_duration_ms=round(load_duration * 1000, 2),
            phase="cache_load_failed",
        )
        return None


def _load_with_fallback(model_name: str = MODEL_NAME) -> Any:
    """Load model with fallback logic (try primary, then tiny.en)."""
    import time

    download_start = time.time()
    logger.info(
        "stt.download_load_start",
        model_name=model_name,
        model_path=MODEL_PATH,
        phase="download_start",
    )

    try:
        from faster_whisper import WhisperModel
    except Exception as e:
        logger.error(
            "stt.model_import_failed",
            error=str(e),
            error_type=type(e).__name__,
            phase="import_check",
        )
        raise RuntimeError(f"faster-whisper import error: {e}") from e

    device = _cfg.faster_whisper.device
    compute_type = _cfg.faster_whisper.compute_type

    # Validate CUDA availability and adjust if needed
    device, compute_type = _validate_and_adjust_cuda_device(device, compute_type)

    # Validate device/compute_type compatibility
    if device == "cpu" and compute_type == "float16":
        logger.warning(
            "stt.compute_type_corrected",
            device=device,
            original_compute_type=compute_type,
            corrected_compute_type="int8",
            reason="float16 not supported on CPU",
            phase="config_validation",
        )
        compute_type = "int8"

    # Check if force download is enabled (check env var directly as fallback)
    force_download = False
    if _model_loader is not None:
        force_download = _model_loader.is_force_download()
    else:
        # Fallback: check environment variable directly
        force_val = os.getenv("FORCE_MODEL_DOWNLOAD_WHISPER_MODEL", "").lower()
        global_val = os.getenv("FORCE_MODEL_DOWNLOAD", "false").lower()
        force_download = force_val in ("true", "1", "yes") or global_val in (
            "true",
            "1",
            "yes",
        )

    # Use force download helper if enabled
    if force_download:
        logger.info(
            "stt.force_download_clearing_cache",
            model_name=model_name,
            model_path=MODEL_PATH,
            phase="force_download_prep",
        )
        model_path_or_name = force_download_faster_whisper(
            model_name=model_name,
            download_root=MODEL_PATH,
            force=True,
        )
        logger.info(
            "stt.force_download_cache_cleared",
            model_name=model_name,
            model_path_or_name=model_path_or_name,
            phase="force_download_ready",
        )
    else:
        # Check if we have a local model directory for the specified model
        local_model_path = os.path.join(MODEL_PATH, model_name)
        model_path_or_name = (
            local_model_path if os.path.exists(local_model_path) else model_name
        )
        if os.path.exists(local_model_path):
            logger.debug(
                "stt.using_local_model",
                model_name=model_name,
                model_path=local_model_path,
                phase="download_local_found",
            )
        else:
            logger.info(
                "stt.downloading_model",
                model_name=model_name,
                download_root=MODEL_PATH,
                phase="download_required",
            )

    model_init_start = time.time()
    try:
        # Log exact parameters that will be passed to WhisperModel
        whisper_params = {
            "model_path_or_name": model_path_or_name,
            "device": device,
        }
        if compute_type:
            whisper_params["compute_type"] = compute_type

        logger.info(
            "stt.model_initialization_start",
            model_name=model_name,
            model_path_or_name=model_path_or_name,
            device=device,
            compute_type=compute_type or "default",
            force_download=force_download,
            whisper_model_parameters=whisper_params,
            phase="model_init",
        )

        # Try to create model with the validated device
        # If CUDA fails during initialization, catch and fallback
        try:
            if compute_type:
                model = WhisperModel(
                    model_path_or_name, device=device, compute_type=compute_type
                )
            else:
                model = WhisperModel(model_path_or_name, device=device)
        except (RuntimeError, OSError, Exception) as model_init_error:
            error_str = str(model_init_error).lower()
            # Check for CUDA-related errors during model initialization
            if device == "cuda" and (
                "cuda" in error_str
                or "cudnn" in error_str
                or "gpu" in error_str
                or "invalid handle" in error_str
                or "cuda error" in error_str
            ):
                logger.error(
                    "stt.cuda_model_init_failed",
                    error=str(model_init_error),
                    error_type=type(model_init_error).__name__,
                    original_device=device,
                    original_compute_type=compute_type,
                    fallback="cpu",
                    phase="model_initialization",
                )
                # Fallback to CPU
                device = "cpu"
                compute_type = "int8"
                # Retry with CPU
                if compute_type:
                    model = WhisperModel(
                        model_path_or_name, device=device, compute_type=compute_type
                    )
                else:
                    model = WhisperModel(model_path_or_name, device=device)
                logger.warning(
                    "stt.model_reloaded_with_cpu",
                    original_device="cuda",
                    reason="cuda_init_failed",
                    phase="model_initialization",
                )
            else:
                # Not a CUDA error, re-raise
                raise

        model_init_duration = time.time() - model_init_start
        total_duration = time.time() - download_start

        # Get actual device information from the loaded model (STT-specific for CTranslate2)
        model_device_info = _get_model_device_info(model)
        # Merge with intended device to match common format
        device_info = {
            "intended_device": device,
            **model_device_info,
        }

        logger.info(
            "stt.model_loaded",
            model_name=model_name,
            model_path=model_path_or_name,
            is_local=os.path.exists(os.path.join(MODEL_PATH, model_name)),
            device=device,  # Intended device
            compute_type=compute_type or "default",  # Intended compute_type
            init_duration_ms=round(model_init_duration * 1000, 2),
            total_duration_ms=round(total_duration * 1000, 2),
            phase="download_complete",
        )

        # Log device mismatch warnings and confirmations
        config_device = _cfg.faster_whisper.device if _cfg else "unknown"
        if config_device == "cuda" and device_info.get("actual_device") != "cuda":
            logger.warning(
                "stt.device_mismatch_detected",
                intended_device=config_device,
                actual_device=device_info.get("actual_device", "unknown"),
                model_on_device=device_info.get("model_on_device"),
                note="Model may have fallen back to CPU despite CUDA request",
                phase="download_complete",
            )
        elif config_device == "cuda" and device_info.get("actual_device") == "cuda":
            logger.info(
                "stt.gpu_usage_confirmed",
                device=device_info.get("actual_device"),
                gpu_name=device_info.get("pytorch_cuda_device_name"),
                phase="download_complete",
            )

        # Log comprehensive device info in structured format
        logger.info(
            "stt.model_loaded.device_info",
            intended_device=config_device,
            actual_device=device_info.get("actual_device", "unknown"),
            device_verified=device_info.get("device_verified", False),
            model_on_device=device_info.get("model_on_device"),
            pytorch_cuda_available=device_info.get("pytorch_cuda_available", False),
            pytorch_cuda_device_count=device_info.get("pytorch_cuda_device_count", 0),
            pytorch_cuda_device_name=device_info.get("pytorch_cuda_device_name"),
            phase="download_complete",
        )

        return model
    except Exception as e:
        model_init_duration = time.time() - model_init_start
        total_duration = time.time() - download_start

        logger.exception(
            "stt.model_load_error",
            model_name=model_name,
            device=device,
            compute_type=compute_type,
            error=str(e),
            error_type=type(e).__name__,
            init_duration_ms=round(model_init_duration * 1000, 2),
            total_duration_ms=round(total_duration * 1000, 2),
            phase="download_failed",
        )
        # If primary model fails and not already trying fallback, try tiny.en
        if model_name != "tiny.en":
            logger.warning(
                "stt.primary_model_failed",
                trying_fallback="tiny.en",
                primary_model=model_name,
                phase="fallback_triggered",
            )
            return _load_with_fallback("tiny.en")
        # If fallback also fails, raise
        raise RuntimeError(f"model load error: {e}") from e


async def _startup() -> None:
    """Ensure the Whisper model is loaded before serving traffic."""
    global \
        _model_loader, \
        _transcript_cache, \
        _audio_processor_client, \
        _observability_manager, \
        _stt_metrics, \
        _http_metrics

    try:
        # Get observability manager (factory already setup observability)
        _observability_manager = get_observability_manager("stt")
        _health_manager.set_observability_manager(_observability_manager)

        # Create service-specific metrics
        from services.common.audio_metrics import (
            create_stt_metrics,
            create_http_metrics,
            create_system_metrics,
        )

        _stt_metrics = create_stt_metrics(_observability_manager)
        _http_metrics = create_http_metrics(_observability_manager)
        _system_metrics = create_system_metrics(_observability_manager)

        # Ensure model directory is writable
        if not ensure_model_directory(MODEL_PATH):
            logger.warning(
                "stt.model_directory_not_writable",
                model_path=MODEL_PATH,
                message="Model downloads may fail if directory is not writable",
            )

        # Initialize model loader with cache-first + download fallback
        _model_loader = BackgroundModelLoader(
            cache_loader_func=_load_from_cache,
            download_loader_func=lambda: _load_with_fallback(MODEL_NAME),
            logger=logger,
            loader_name="whisper_model",
        )

        # Start background loading (non-blocking)
        await _model_loader.initialize()
        logger.info("stt.model_loader_initialized", model_name=MODEL_NAME)

        # Register model loader as dependency for health checks
        # Models must be loaded AND not currently loading for service to be ready
        _health_manager.register_dependency(
            "whisper_model",
            lambda: (
                _model_loader.is_loaded() and not _model_loader.is_loading()
                if _model_loader
                else False
            ),
        )

        # Initialize audio processor client with fallback
        try:
            _audio_processor_client = STTAudioProcessorClient(
                base_url=_cfg.faster_whisper.audio_service_url or "http://audio:9100",
                timeout=_cfg.faster_whisper.audio_service_timeout or 50.0,
            )
            logger.info("stt.audio_processor_client_initialized")
        except Exception as exc:
            logger.warning("stt.audio_processor_client_init_failed", error=str(exc))
            _audio_processor_client = None

        # Initialize result cache if enabled
        global _transcript_cache
        from services.common.result_cache import ResultCache

        _transcript_cache = None
        enable_cache = os.getenv("STT_ENABLE_CACHE", "true").lower() in (
            "true",
            "1",
            "yes",
        )
        if enable_cache:
            max_entries = int(os.getenv("STT_CACHE_MAX_ENTRIES", "200"))
            max_size_mb = int(os.getenv("STT_CACHE_MAX_SIZE_MB", "1000"))
            _transcript_cache = ResultCache(
                max_entries=max_entries,
                max_size_mb=max_size_mb,
                service_name="stt",
            )
            logger.info(
                "stt.cache_initialized",
                max_entries=max_entries,
                max_size_mb=max_size_mb,
            )

        # Always mark startup complete (graceful degradation)
        _health_manager.mark_startup_complete()

        # Pre-warm models using unified pattern (replaces telemetry-specific warmup)
        from services.common.prewarm import prewarm_if_enabled
        from services.common.audio import AudioProcessor
        import tempfile
        import numpy as np

        async def _prewarm_stt() -> None:
            """Pre-warm STT model by performing a transcription."""
            if not _model_loader.is_loaded():
                return

            model = _model_loader.get_model()
            if model is None:
                return

            # Generate ~300ms silence at 16kHz mono int16 (matches existing pattern)
            samples = int(16000 * 0.3)
            pcm = (np.zeros(samples, dtype=np.int16)).tobytes()

            # Encode to WAV using AudioProcessor to match runtime path
            processor = AudioProcessor("stt")
            wav_data = processor.pcm_to_wav(pcm, 16000, 1, 2)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(wav_data)
                tmp_path = tmp.name

            try:
                default_beam_size = getattr(_cfg.faster_whisper, "beam_size", 5) or 5
                _ = model.transcribe(tmp_path, beam_size=default_beam_size)
            finally:
                from contextlib import suppress
                import os

                with suppress(Exception):
                    os.unlink(tmp_path)

        await prewarm_if_enabled(
            _prewarm_stt,
            "stt",
            logger,
            model_loader=_model_loader,
            health_manager=_health_manager,
        )

    except Exception as exc:
        logger.error("stt.startup_failed", error=str(exc))
        # Still mark startup complete to avoid infinite startup loop
        _health_manager.mark_startup_complete()


# Create app using factory pattern
app = create_service_app(
    "stt",
    "1.0.0",
    title="audio-orchestrator STT (faster-whisper)",
    startup_callback=_startup,
)


def _get_stt_device_info() -> dict[str, Any]:
    """Get current STT service device information for health checks."""
    intended_device = _cfg.faster_whisper.device if _cfg else "unknown"

    # Get actual device from loaded model (STT-specific for CTranslate2)
    import contextlib

    model_device_info = {}
    if _model is not None:
        with contextlib.suppress(Exception):
            model_device_info = _get_model_device_info(_model)

    # Merge to match common format
    return {
        "intended_device": intended_device,
        **model_device_info,
    }


# Initialize health endpoints
health_endpoints = HealthEndpoints(
    service_name="stt",
    health_manager=_health_manager,
    custom_components={
        "model_loaded": lambda: _model_loader.is_loaded() if _model_loader else False,
        "model_name": lambda: MODEL_NAME,
        "audio_processor_client_loaded": lambda: _audio_processor_client is not None,
        "device_info": _get_stt_device_info,  # Add device info component
    },
    custom_dependencies={
        "audio_processor": lambda: _audio_processor_client is not None,
    },
)

# Include the health endpoints router
app.include_router(health_endpoints.get_router())


def _parse_bool(value: str | None) -> bool:
    if value is None:
        return False
    return str(value).lower() in {"1", "true", "yes", "on"}


def _lazy_load_model() -> Any:
    """Get model from loader (maintains backward compatibility)."""
    global _model
    if _model_loader is None:
        raise HTTPException(status_code=503, detail="Model loader not initialized")
    # Get model from loader (may trigger lazy load)
    model = _model_loader.get_model()
    if model is None:
        raise HTTPException(status_code=503, detail="Model not available")
    # Cache in global for backward compatibility
    _model = model
    return _model


def _extract_audio_metadata(wav_bytes: bytes) -> tuple[int, int, int]:
    """Extract audio metadata using standardized audio processing."""
    from services.common.audio import AudioProcessor

    processor = AudioProcessor("stt")

    try:
        metadata = processor.extract_metadata(wav_bytes, "wav")

        # Validate sample width (only 16-bit supported)
        if metadata.sample_width != 2:
            raise HTTPException(
                status_code=400, detail="only 16-bit PCM WAV is supported"
            )

        return metadata.channels, metadata.sample_width, metadata.sample_rate

    except Exception as exc:
        # Fallback to original implementation - log the failure for debugging
        logger.debug(
            "stt.metadata_extraction_fallback",
            error=str(exc),
            error_type=type(exc).__name__,
            fallback="wave_module",
        )
        try:
            with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
                wf.getnframes()  # consume to ensure header validity
        except wave.Error as e:
            raise HTTPException(status_code=400, detail=f"invalid WAV: {e}") from e

        if sampwidth != 2:
            raise HTTPException(
                status_code=400, detail="only 16-bit PCM WAV is supported"
            )
        return channels, sampwidth, framerate


async def _transcribe_request(
    request: Request,
    wav_bytes: bytes,
    *,
    correlation_id: str | None,
    filename: str | None,
) -> JSONResponse:
    from services.common.structured_logging import correlation_context

    # Extract and resolve correlation_id first
    headers_correlation = request.headers.get("X-Correlation-ID")
    query_correlation = request.query_params.get("correlation_id")
    correlation_id = correlation_id or headers_correlation or query_correlation

    # Validate correlation ID if provided
    if correlation_id:
        from services.common.correlation import validate_correlation_id

        is_valid, error_msg = validate_correlation_id(correlation_id)
        if not is_valid:
            raise HTTPException(
                status_code=400, detail=f"Invalid correlation ID: {error_msg}"
            )

    # Generate STT correlation ID if none provided
    if not correlation_id:
        from services.common.correlation import generate_stt_correlation_id

        correlation_id = generate_stt_correlation_id()

    # Generate cache key before correlation_context (needed for cache.put at end)
    # Apply audio enhancement if enabled (before cache check)
    wav_bytes = await _enhance_audio_if_enabled(wav_bytes, correlation_id)
    # Generate cache key from audio bytes (convert to hex string for hashing)
    import hashlib

    cache_key = hashlib.sha256(wav_bytes).hexdigest()

    # Check cache before transcription
    if _transcript_cache:
        cached_result = _transcript_cache.get(cache_key)
        if cached_result:
            # Add correlation_id to cached response if not present
            if correlation_id and "correlation_id" not in cached_result:
                cached_result["correlation_id"] = correlation_id
            cache_stats = _transcript_cache.get_stats()
            # Log cache hit with correlation context
            with correlation_context(correlation_id) as request_logger:
                request_logger.info(
                    "stt.cache_hit",
                    cache_key=cache_key[:16],
                    correlation_id=correlation_id,
                    cache_hit_rate=round(cache_stats["hit_rate"], 3),
                )
            return JSONResponse(cached_result)

    with correlation_context(correlation_id) as request_logger:
        # Top-level timing for the request (includes validation, file I/O, model work)
        req_start = time.time()

        if not wav_bytes:
            raise HTTPException(status_code=400, detail="empty request body")

        channels, _sampwidth, framerate = _extract_audio_metadata(wav_bytes)

    # Check model status before processing (non-blocking)
    if _model_loader is None:
        raise HTTPException(status_code=503, detail="Model loader not initialized")

    if _model_loader.is_loading():
        raise HTTPException(
            status_code=503,
            detail="Model is currently loading. Please try again shortly.",
        )

    if not _model_loader.is_loaded():
        status = _model_loader.get_status()
        error_msg = status.get("error", "Model not available")
        raise HTTPException(status_code=503, detail=f"Model not available: {error_msg}")

    # Ensure model is loaded (may trigger lazy load if background failed)
    if not await _model_loader.ensure_loaded():
        status = _model_loader.get_status()
        error_msg = status.get("error", "Model not available")
        raise HTTPException(status_code=503, detail=f"Model not available: {error_msg}")

    model = _model_loader.get_model()
    if model is None:
        raise HTTPException(status_code=503, detail="Model not available")

    # Cache in global for backward compatibility
    global _model
    _model = model

    device = _cfg.faster_whisper.device
    # Write incoming WAV bytes to a temp file and let the model handle I/O
    import tempfile

    # Allow clients to optionally request a translation task by passing
    # the `task=translate` query parameter. We also accept `beam_size` and
    # `language` query params to tune faster-whisper behavior at runtime.
    task = request.query_params.get("task")
    beam_size_q = request.query_params.get("beam_size")
    lang_q = request.query_params.get("language")
    word_ts_q = request.query_params.get("word_timestamps")
    vad_filter_q = request.query_params.get("vad_filter")
    initial_prompt = request.query_params.get("initial_prompt")
    language = lang_q
    include_word_ts = _parse_bool(word_ts_q)
    # Use configured beam_size as default (optimized to 5 for quality/latency balance)
    beam_size = getattr(_cfg.faster_whisper, "beam_size", 5) or 5
    if beam_size_q:
        try:
            beam_size = int(beam_size_q)
            if beam_size < 1:
                beam_size = getattr(_cfg.faster_whisper, "beam_size", 5) or 5
        except (ValueError, TypeError) as exc:
            logger.warning(
                "stt.invalid_beam_size",
                beam_size=beam_size_q,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise HTTPException(
                status_code=400, detail="invalid beam_size query param"
            ) from exc

    tmp_path = None
    # metadata for response payload
    input_bytes = len(wav_bytes)

    processing_ms: int | None = None
    info: Any = None
    segments_list: list[Any] = []
    text = ""
    segments_out: list[dict[str, Any]] = []

    # Calculate audio duration for metrics (disabled for now)
    # audio_duration = len(wav_bytes) / (channels * sampwidth * framerate) if channels and sampwidth and framerate else 0

    try:
        request_logger.info(
            "stt.request_received",
            correlation_id=correlation_id,
            input_bytes=input_bytes,
            task=task,
            beam_size=beam_size,
            language=language,
            filename=filename,
            channels=channels,
            sample_rate=framerate,
            decision="processing_transcription_request",
        )
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name
        # faster-whisper's transcribe signature accepts beam_size and optional
        # task/language parameters. If language is not provided we pass None
        # to allow automatic language detection.
        # Some faster-whisper variants support word-level timestamps; request it
        # only when asked via the query param.
        # Determine whether caller requested word-level timestamps and pass
        # that flag into the model.transcribe call (some faster-whisper
        # implementations accept a word_timestamps=True parameter).
        # measure server-side processing time (model inference portion)
        proc_start = time.time()

        # Get device info for logging (STT-specific for CTranslate2)
        device_info = {}
        if model:
            try:
                model_device_info = _get_model_device_info(model)
                device_info = {
                    "intended_device": device,
                    **model_device_info,
                }
            except Exception:
                device_info = {
                    "intended_device": device,
                    "actual_device": "unknown",
                }

        request_logger.info(
            "stt.processing_started",
            correlation_id=correlation_id,
            model=MODEL_NAME,
            input_bytes=input_bytes,
            beam_size=beam_size,
            language=language,
            task=task,
            include_word_timestamps=include_word_ts,
            decision="starting_transcription_inference",
        )

        # Log device info
        request_logger.info(
            "stt.processing_started.device_info",
            correlation_id=correlation_id,
            intended_device=device_info.get("intended_device"),
            actual_device=device_info.get("actual_device", "unknown"),
            device_verified=device_info.get("device_verified", False),
            model_on_device=device_info.get("model_on_device"),
            pytorch_cuda_available=device_info.get("pytorch_cuda_available", False),
            pytorch_cuda_device_name=device_info.get("pytorch_cuda_device_name"),
            phase="inference_start",
        )
        transcribe_kwargs: dict[str, object] = {"beam_size": beam_size}
        if task == "translate":
            transcribe_kwargs.update({"task": "translate", "language": language})
        elif language is not None:
            transcribe_kwargs["language"] = language
        if include_word_ts:
            transcribe_kwargs["word_timestamps"] = True
        if vad_filter_q and _parse_bool(vad_filter_q):
            transcribe_kwargs["vad_filter"] = True
        if initial_prompt:
            transcribe_kwargs["initial_prompt"] = initial_prompt

        # Validate CUDA runtime before inference if using CUDA
        if device == "cuda" and not _validate_cuda_runtime():
            request_logger.error(
                "stt.cuda_runtime_unavailable_at_inference",
                correlation_id=correlation_id,
                actual_device=device_info.get("actual_device", "unknown"),
                decision="cuda_validation_failed",
            )
            raise HTTPException(
                status_code=503,
                detail="CUDA runtime unavailable. Model may need to be reloaded with CPU device.",
            )

        inference_start = time.time()
        try:
            raw_segments, info = model.transcribe(tmp_path, **transcribe_kwargs)
            inference_duration = time.time() - inference_start

            # Log successful inference with device confirmation
            request_logger.info(
                "stt.inference_completed",
                correlation_id=correlation_id,
                inference_duration_ms=round(inference_duration * 1000, 2),
                decision="inference_success",
            )

            # Log device info
            request_logger.info(
                "stt.inference_completed.device_info",
                correlation_id=correlation_id,
                intended_device=device_info.get("intended_device"),
                actual_device=device_info.get("actual_device", "unknown"),
                model_on_device=device_info.get("model_on_device"),
                phase="inference_complete",
            )
        except (RuntimeError, OSError) as e:
            inference_duration = time.time() - inference_start
            error_str = str(e).lower()
            # Check if this is a CUDA-related error
            if any(
                keyword in error_str
                for keyword in ["cuda", "cudnn", "gpu", "cuda error", "invalid handle"]
            ):
                request_logger.error(
                    "stt.cuda_inference_error",
                    correlation_id=correlation_id,
                    error=str(e),
                    error_type=type(e).__name__,
                    intended_device=device_info.get("intended_device"),
                    actual_device=device_info.get("actual_device", "unknown"),
                    model_on_device=device_info.get("model_on_device"),
                    inference_duration_ms=round(inference_duration * 1000, 2),
                    decision="cuda_inference_failed",
                )
                raise HTTPException(
                    status_code=503,
                    detail=f"CUDA inference failed: {str(e)}. Service may need CPU device configuration.",
                ) from e
            # Re-raise non-CUDA errors
            raise
        except Exception as e:
            inference_duration = time.time() - inference_start
            # Log other errors but don't assume they're CUDA-related
            request_logger.error(
                "stt.inference_error",
                correlation_id=correlation_id,
                error=str(e),
                error_type=type(e).__name__,
                intended_device=device_info.get("intended_device"),
                actual_device=device_info.get("actual_device", "unknown"),
                model_on_device=device_info.get("model_on_device"),
                inference_duration_ms=round(inference_duration * 1000, 2),
            )
            raise
        # faster-whisper may return a generator/iterator for segments; convert
        # to a list so we can iterate it multiple times (build text and
        # optionally include word-level timestamps).
        if isinstance(raw_segments, list):
            segments_list = raw_segments
        else:
            try:
                segments_list = list(cast("Iterable[Any]", raw_segments))
            except TypeError:
                segments_list = [raw_segments]
        proc_end = time.time()
        processing_ms = int((proc_end - proc_start) * 1000)
        processing_seconds = processing_ms / 1000.0

        # Record STT metrics
        if _stt_metrics:
            if "stt_requests" in _stt_metrics:
                _stt_metrics["stt_requests"].add(1, attributes={"status": "success"})
            if "stt_latency" in _stt_metrics:
                _stt_metrics["stt_latency"].record(
                    processing_seconds, attributes={"status": "success"}
                )

        request_logger.info(
            "stt.request_processed",
            correlation_id=correlation_id,
            processing_ms=processing_ms,
            segments=len(segments_list),
        )
        # Build a combined text and (optionally) include timestamped segments/words
        text = " ".join(getattr(seg, "text", "") for seg in segments_list).strip()
        if include_word_ts:
            for seg in segments_list:
                segment_entry: dict[str, Any] = {
                    "start": getattr(seg, "start", None),
                    "end": getattr(seg, "end", None),
                    "text": getattr(seg, "text", ""),
                }
                # some faster-whisper variants expose `words` on segments when
                # word timestamps are requested; include them if present.
                words = getattr(seg, "words", None)
                word_entries: list[dict[str, Any]] = []
                if isinstance(words, list):
                    for w in words:
                        word_entries.append(
                            {
                                "word": getattr(w, "word", None)
                                or getattr(w, "text", None),
                                "start": getattr(w, "start", None),
                                "end": getattr(w, "end", None),
                            }
                        )
                elif words is not None:
                    word_entries.append(
                        {
                            "word": getattr(words, "word", None)
                            or getattr(words, "text", None),
                            "start": getattr(words, "start", None),
                            "end": getattr(words, "end", None),
                        }
                    )
                if word_entries:
                    segment_entry["words"] = word_entries
                segments_out.append(segment_entry)
    except Exception as e:
        # Record error metrics
        if _stt_metrics:
            if "stt_requests" in _stt_metrics:
                _stt_metrics["stt_requests"].add(1, attributes={"status": "error"})
            if "stt_latency" in _stt_metrics:
                # Record latency even for errors (if we have timing info)
                elapsed = time.time() - req_start if "req_start" in locals() else 0
                _stt_metrics["stt_latency"].record(
                    elapsed, attributes={"status": "error"}
                )

        logger.exception(
            "stt.transcription_error", correlation_id=correlation_id, error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"transcription error: {e}") from e
    finally:
        if tmp_path:
            from contextlib import suppress

            with suppress(Exception):
                os.unlink(tmp_path)

    req_end = time.time()
    total_ms = int((req_end - req_start) * 1000)

    resp: dict[str, Any] = {
        "text": text,
        "duration": getattr(info, "duration", None),
        "language": getattr(info, "language", None),
        "confidence": getattr(info, "language_probability", None),
    }
    if task:
        resp["task"] = task
    # include correlation id if provided by client
    if correlation_id:
        resp["correlation_id"] = correlation_id
    # include server-side processing time (ms)
    try:
        resp["processing_ms"] = processing_ms
        resp["total_ms"] = total_ms
        resp["input_bytes"] = input_bytes
        resp["model"] = MODEL_NAME
        resp["device"] = device
    except NameError:
        # if for some reason processing_ms isn't set, ignore
        pass
    if include_word_ts and segments_out:
        resp["segments"] = segments_out
    # include header with processing time for callers that prefer headers
    headers = {}
    if "processing_ms" in resp:
        headers["X-Processing-Time-ms"] = str(resp["processing_ms"])
    if "total_ms" in resp:
        headers["X-Total-Time-ms"] = str(resp["total_ms"])
    if "input_bytes" in resp:
        headers["X-Input-Bytes"] = str(resp["input_bytes"])

    # Cache result after successful transcription
    if _transcript_cache:
        _transcript_cache.put(cache_key, resp)

    # Log response ready with correlation context
    with correlation_context(correlation_id) as request_logger:
        request_logger.info(
            "stt.response_ready",
            correlation_id=correlation_id,
            text_length=len(resp.get("text", "")),
            processing_ms=resp.get("processing_ms"),
            total_ms=resp.get("total_ms"),
        )
        if resp.get("text"):
            request_logger.debug(
                "stt.transcription_text",
                correlation_id=correlation_id,
                text=resp["text"],
            )
    return JSONResponse(resp, headers=headers)


@app.post("/asr")  # type: ignore[misc]
async def asr(request: Request) -> JSONResponse:
    # Expect raw WAV bytes in the request body
    body = await request.body()
    logger.info(
        "stt.asr_request",
        content_length=len(body),
        correlation_id=request.headers.get("X-Correlation-ID"),
    )
    return await _transcribe_request(
        request,
        body,
        correlation_id=request.headers.get("X-Correlation-ID")
        or request.query_params.get("correlation_id"),
        filename=None,
    )


async def _enhance_audio_if_enabled(
    wav_bytes: bytes, correlation_id: str | None = None
) -> bytes:
    """Apply audio enhancement via remote audio processor service if available.

    This function attempts to enhance audio using MetricGAN+ (GPU-accelerated ML model)
    from the audio processor service. Enhancement is optional and gracefully degrades
    if the service is unavailable.

    Enhancement improves transcription accuracy by:
    - Noise reduction (MetricGAN+ ML model)
    - High-pass filtering (80Hz cutoff)
    - Volume normalization

    Architecture Note:
    - Frame-level processing (Discord): Lightweight VAD + normalization only
    - Segment-level enhancement (STT): Heavy MetricGAN+ ML processing
    - GPU isolation: Audio processor has separate GPU for MetricGAN+

    Args:
        wav_bytes: WAV format audio (16kHz, mono, 16-bit PCM expected)
        correlation_id: Optional correlation ID for request tracking

    Returns:
        Enhanced WAV audio if enhancement succeeded, original audio otherwise
    """
    from services.common.structured_logging import get_logger

    enhance_logger = get_logger(
        __name__, correlation_id=correlation_id, service_name="stt"
    )

    # Only attempt enhancement if audio processor client is available
    if _audio_processor_client is None:
        enhance_logger.debug(
            "stt.enhancement_skipped",
            correlation_id=correlation_id,
            reason="audio_processor_client_not_available",
            decision="skip_enhancement_use_original",
        )
        return wav_bytes

    # Attempt remote enhancement via audio processor service
    enhance_logger.info(
        "stt.enhancement_attempting",
        correlation_id=correlation_id,
        input_size=len(wav_bytes),
        enhancement_method="remote_metricgan_plus",
        decision="attempting_remote_enhancement",
    )

    try:
        enhanced_wav: bytes = await _audio_processor_client.enhance_audio(
            wav_bytes, correlation_id
        )

        # Check if enhancement was actually applied
        if enhanced_wav != wav_bytes:
            enhance_logger.info(
                "stt.enhancement_successful",
                correlation_id=correlation_id,
                input_size=len(wav_bytes),
                output_size=len(enhanced_wav),
                decision="enhancement_applied",
            )
            return enhanced_wav
        else:
            # Audio processor returned original (enhancement not applied or disabled)
            enhance_logger.info(
                "stt.enhancement_not_applied",
                correlation_id=correlation_id,
                reason="audio_processor_returned_original",
                decision="using_original_audio",
            )
            return wav_bytes

    except Exception as exc:
        # Enhancement failed - gracefully degrade to original audio
        enhance_logger.warning(
            "stt.enhancement_failed",
            correlation_id=correlation_id,
            error=str(exc),
            error_type=type(exc).__name__,
            decision="enhancement_failed_using_original",
            fallback="original_audio",
        )
        return wav_bytes


@app.post("/transcribe")  # type: ignore[misc]
async def transcribe(request: Request) -> JSONResponse:
    try:
        form = await request.form()
    except ClientDisconnect:
        correlation_id = request.headers.get(
            "X-Correlation-ID"
        ) or request.query_params.get("correlation_id")
        logger.info(
            "stt.client_disconnect",
            correlation_id=correlation_id,
            detail="client closed connection during multipart parse",
        )
        return JSONResponse({"detail": "client disconnected"}, status_code=499)
    upload = form.get("file")
    if upload is None:
        logger.warning(
            "stt.transcribe_missing_file",
            fields=list(form.keys()),
        )
        raise HTTPException(status_code=400, detail="missing 'file' form field")

    metadata_value = form.get("metadata")

    filename: str | None = None
    wav_bytes: bytes
    if isinstance(upload, UploadFile):
        filename = upload.filename
        wav_bytes = await upload.read()
        await upload.close()
    elif isinstance(upload, (bytes, bytearray)):
        wav_bytes = bytes(upload)
    else:
        logger.warning(
            "stt.transcribe_unsupported_payload",
            payload_type=type(upload).__name__,
        )
        raise HTTPException(status_code=400, detail="unsupported file payload")

    # Sample noisy request logs to reduce verbosity in production
    try:
        sample_n = _cfg.telemetry.log_sample_stt_request_n or 25
    except (AttributeError, KeyError) as exc:
        # Fallback if telemetry config not available
        logger.debug(
            "stt.config_fallback",
            error=str(exc),
            error_type=type(exc).__name__,
            fallback_value=25,
        )
        sample_n = 25
    from services.common.structured_logging import should_sample

    if should_sample("stt.transcribe_request", sample_n):
        logger.info(
            "stt.transcribe_request",
            filename=filename,
            input_bytes=len(wav_bytes),
            correlation_id=metadata_value,
        )

    return await _transcribe_request(
        request,
        wav_bytes,
        correlation_id=metadata_value,
        filename=filename,
    )


# Test change
