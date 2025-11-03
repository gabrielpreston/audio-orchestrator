import io
import os
import time
from typing import Any
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
    log_device_info,
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


def _resolve_device_and_compute_type() -> tuple[str, str | None]:
    """Resolve and validate device/compute_type settings.

    Consolidates device validation and compute_type compatibility checking
    that was duplicated across cache and download loader paths.

    Returns:
        Validated (device, compute_type) tuple.
    """
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
            phase="config_validation",
        )

    return device, compute_type


def _initialize_whisper_model(
    model_path_or_name: str,
    device: str,
    compute_type: str | None,
) -> Any:
    """Initialize WhisperModel with CUDA fallback.

    Handles the nested try/except CUDA fallback pattern that was duplicated
    across cache and download loader paths.

    Args:
        model_path_or_name: Model path or name for WhisperModel
        device: Target device ("cuda" or "cpu")
        compute_type: Compute type or None for default

    Returns:
        Loaded WhisperModel instance

    Raises:
        Exception if model initialization fails (non-CUDA errors are re-raised)
    """
    from faster_whisper import WhisperModel

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

    return model


def _resolve_model_path(model_name: str) -> tuple[str, bool]:
    """Resolve model path considering force download and local cache.

    Consolidates force download logic that was duplicated in download loader.

    Args:
        model_name: Model name to load

    Returns:
        Tuple of (model_path_or_name, force_download_used)
    """
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
        return model_path_or_name, True

    # Check local cache
    local_model_path = os.path.join(MODEL_PATH, model_name)
    if os.path.exists(local_model_path):
        logger.debug(
            "stt.using_local_model",
            model_name=model_name,
            model_path=local_model_path,
            phase="download_local_found",
        )
        return local_model_path, False

    logger.info(
        "stt.downloading_model",
        model_name=model_name,
        download_root=MODEL_PATH,
        phase="download_required",
    )
    return model_name, False


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
        from faster_whisper import WhisperModel  # noqa: F401
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

    # Resolve device and compute_type using shared utility
    device, compute_type = _resolve_device_and_compute_type()

    load_start = time.time()
    try:
        # Initialize model with CUDA fallback using shared utility
        model = _initialize_whisper_model(local_model_path, device, compute_type)

        load_duration = time.time() - load_start
        total_duration = time.time() - cache_start

        # Get device information (STT-specific for CTranslate2, then merge with PyTorch CUDA info)
        config_device = _cfg.faster_whisper.device if _cfg else "unknown"
        model_device_info = _get_model_device_info(model)
        cuda_info = get_pytorch_cuda_info()
        device_info = {
            "intended_device": config_device,
            **cuda_info,
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

        # Log device info using standardized utility
        log_device_info(
            logger,
            "stt.model_loaded_from_cache",
            device_info,
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
        from faster_whisper import WhisperModel  # noqa: F401
    except Exception as e:
        logger.error(
            "stt.model_import_failed",
            error=str(e),
            error_type=type(e).__name__,
            phase="import_check",
        )
        raise RuntimeError(f"faster-whisper import error: {e}") from e

    # Resolve device and compute_type using shared utility
    device, compute_type = _resolve_device_and_compute_type()

    # Resolve model path using shared utility (handles force download)
    model_path_or_name, force_download = _resolve_model_path(model_name)

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

        # Initialize model with CUDA fallback using shared utility
        model = _initialize_whisper_model(model_path_or_name, device, compute_type)

        model_init_duration = time.time() - model_init_start
        total_duration = time.time() - download_start

        # Get device information (STT-specific for CTranslate2, then merge with PyTorch CUDA info)
        config_device = _cfg.faster_whisper.device if _cfg else "unknown"
        model_device_info = _get_model_device_info(model)
        cuda_info = get_pytorch_cuda_info()
        device_info = {
            "intended_device": config_device,
            **cuda_info,
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

        # Log device info using standardized utility
        log_device_info(
            logger,
            "stt.model_loaded",
            device_info,
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
        _stt_metrics

    try:
        # Get observability manager (factory already setup observability)
        _observability_manager = get_observability_manager("stt")
        _health_manager.set_observability_manager(_observability_manager)

        # Register service-specific metrics using centralized helper
        from services.common.audio_metrics import MetricKind, register_service_metrics

        metrics = register_service_metrics(
            _observability_manager, kinds=[MetricKind.STT, MetricKind.SYSTEM]
        )
        _stt_metrics = metrics["stt"]
        _system_metrics = metrics["system"]

        # HTTP metrics already available from app_factory via app.state.http_metrics

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

            # Create temporary file for model warmup
            # File is automatically deleted when context manager exits (even on exceptions)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
                tmp.write(wav_data)
                tmp_path = tmp.name

                default_beam_size = getattr(_cfg.faster_whisper, "beam_size", 5) or 5
                _ = model.transcribe(tmp_path, beam_size=default_beam_size)

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
    from services.stt.transcription import (
        build_transcription_response,
        cache_transcription_result,
        check_cache,
        ensure_model_ready,
        execute_inference,
        parse_transcription_params,
        prepare_audio_for_transcription,
        record_transcription_metrics,
        resolve_correlation_id,
        validate_request,
    )

    # Resolve correlation ID
    correlation_id = resolve_correlation_id(request, correlation_id)

    # Prepare audio (enhancement + cache key generation)
    wav_bytes, cache_key = await prepare_audio_for_transcription(
        wav_bytes,
        correlation_id,
        _audio_processor_client,
        _enhance_audio_if_enabled,
    )

    # Check cache before transcription
    cached_result = check_cache(_transcript_cache, cache_key, correlation_id)
    if cached_result:
        return JSONResponse(cached_result)

    # Top-level timing for the request (includes validation, file I/O, model work)
    req_start = time.time()

    with correlation_context(correlation_id) as request_logger:
        # Validate request and extract audio metadata
        channels, _sampwidth, framerate = validate_request(
            wav_bytes, _extract_audio_metadata
        )

        # Ensure model is ready
        model = await ensure_model_ready(_model_loader)

        # Cache in global for backward compatibility
        global _model
        _model = model

        device = _cfg.faster_whisper.device

        # Parse transcription parameters
        params = parse_transcription_params(request, _cfg, _parse_bool)

        # Write incoming WAV bytes to a temp file and let the model handle I/O
        import tempfile

        input_bytes = len(wav_bytes)

        processing_ms: int | None = None
        info: Any = None
        segments_list: list[Any] = []

        try:
            request_logger.info(
                "stt.request_received",
                correlation_id=correlation_id,
                input_bytes=input_bytes,
                task=params["task"],
                beam_size=params["beam_size"],
                language=params["language"],
                filename=filename,
                channels=channels,
                sample_rate=framerate,
                decision="processing_transcription_request",
            )

            # Create temporary file for faster-whisper
            # File is automatically deleted when context manager exits (even on exceptions)
            # This ensures no orphaned files are left behind on errors
            # Measure server-side processing time (model inference portion)
            proc_start = time.time()

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
                tmp.write(wav_bytes)
                tmp_path = tmp.name

                # Execute inference
                (
                    segments_list,
                    info,
                    device_info,
                    inference_duration,
                ) = await execute_inference(
                    model,
                    tmp_path,
                    params,
                    device,
                    correlation_id,
                    MODEL_NAME,
                    _validate_cuda_runtime,
                    _get_model_device_info,
                    request_logger,
                    input_bytes=input_bytes,
                )

            proc_end = time.time()
            processing_ms = int((proc_end - proc_start) * 1000)
            processing_seconds = processing_ms / 1000.0

            # Record STT metrics for success
            record_transcription_metrics(_stt_metrics, "success", processing_seconds)

            request_logger.info(
                "stt.request_processed",
                correlation_id=correlation_id,
                processing_ms=processing_ms,
                segments=len(segments_list),
            )
        except Exception as e:
            # Record error metrics
            elapsed = time.time() - req_start
            record_transcription_metrics(_stt_metrics, "error", elapsed)

            logger.exception(
                "stt.transcription_error",
                correlation_id=correlation_id,
                error=str(e),
            )
            raise HTTPException(
                status_code=500, detail=f"transcription error: {e}"
            ) from e

        # Build response (only if no exception was raised)
        req_end = time.time()
        total_ms = int((req_end - req_start) * 1000)

        resp = build_transcription_response(
            segments_list,
            info,
            params,
            processing_ms or 0,
            total_ms,
            input_bytes,
            correlation_id,
            MODEL_NAME,
            device,
        )

        # Cache result after successful transcription
        cache_transcription_result(_transcript_cache, cache_key, resp)

        # Log response ready with correlation context
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

        # Build response headers
        headers = {}
        if "processing_ms" in resp:
            headers["X-Processing-Time-ms"] = str(resp["processing_ms"])
        if "total_ms" in resp:
            headers["X-Total-Time-ms"] = str(resp["total_ms"])
        if "input_bytes" in resp:
            headers["X-Input-Bytes"] = str(resp["input_bytes"])

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
