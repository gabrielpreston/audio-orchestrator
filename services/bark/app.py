"""FastAPI application for the Bark TTS service.

This service provides HTTP API endpoints for text-to-speech synthesis including:
- Bark TTS generation with multiple voice presets
- Piper fallback for reliability
- Voice selection and configuration
- Performance monitoring
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import HTTPException, Request
from pydantic import BaseModel
import uvicorn

from services.common.config import (
    AudioConfig,
    HttpConfig,
    LoggingConfig,
    ServiceConfig,
    TelemetryConfig,
    get_service_preset,
)
from services.common.health import HealthManager
from services.common.health_endpoints import HealthEndpoints
from services.common.app_factory import create_service_app
from services.common.structured_logging import configure_logging, get_logger
from services.common.tracing import get_observability_manager
from services.common.permissions import ensure_model_directory

from .synthesis import BarkSynthesizer


# Load configuration first (before creating loggers)
_config_preset = get_service_preset("tts")
_logging_config = LoggingConfig(**_config_preset["logging"])
_http_config = HttpConfig(**_config_preset["http"])
_audio_config = AudioConfig(**_config_preset["audio"])
_service_config = ServiceConfig(**_config_preset["service"])
_telemetry_config = TelemetryConfig(**_config_preset["telemetry"])

# Configure logging BEFORE creating any loggers to ensure JSON format is applied
configure_logging(
    _logging_config.level,
    json_logs=_logging_config.json_logs,
    service_name="bark",
)

# Global variables (created after logging configuration)
_bark_synthesizer: BarkSynthesizer | None = None
_health_manager = HealthManager("bark")
_observability_manager = None
_tts_metrics = {}
_logger = get_logger(__name__, service_name="bark")
_prewarm_complete = False

# Voice presets
VOICE_PRESETS = [
    "v2/en_speaker_0",  # Male voice
    "v2/en_speaker_1",  # Female voice
    "v2/en_speaker_2",  # Male with accent
    "v2/en_speaker_3",  # Female expressive
    "v2/en_speaker_6",  # Male deep
]


class SynthesisRequest(BaseModel):
    """Request model for text synthesis."""

    text: str
    voice: str = "v2/en_speaker_1"
    speed: float = 1.0


class SynthesisResponse(BaseModel):
    """Response model for text synthesis."""

    audio: str  # Base64-encoded audio data (WAV format)
    engine: str
    processing_time_ms: float
    voice_used: str


async def _startup() -> None:
    """Initialize the Bark TTS service."""
    global _bark_synthesizer, _observability_manager, _tts_metrics

    try:
        # Get observability manager (factory already setup observability)
        _observability_manager = get_observability_manager("bark")

        # Register service-specific metrics using centralized helper
        from services.common.audio_metrics import MetricKind, register_service_metrics

        metrics = register_service_metrics(
            _observability_manager, kinds=[MetricKind.TTS, MetricKind.SYSTEM]
        )
        _tts_metrics = metrics["tts"]
        _system_metrics = metrics["system"]

        # HTTP metrics already available from app_factory via app.state.http_metrics

        # Set observability manager in health manager
        _health_manager.set_observability_manager(_observability_manager)

        # Ensure model directories are writable (bark uses /app/.cache/suno/bark_v0)
        import os

        cache_dir = os.getenv("HF_HOME", "/app/models")
        home_dir = os.getenv("HOME", "/app")
        cache_subdir = os.path.join(home_dir, ".cache", "suno")

        # Ensure both HF cache and HOME/.cache/suno are writable
        if not ensure_model_directory(cache_dir):
            _logger.warning(
                "bark.cache_directory_not_writable",
                cache_dir=cache_dir,
                message="Bark model downloads may fail",
            )

        # Bark uses ~/.cache/suno/bark_v0 - ensure this path exists and is writable
        if not ensure_model_directory(cache_subdir):
            _logger.warning(
                "bark.cache_subdirectory_not_writable",
                cache_subdir=cache_subdir,
                message="Bark may not be able to write to ~/.cache/suno",
            )
        else:
            _logger.debug(
                "bark.cache_subdirectory_ready",
                cache_subdir=cache_subdir,
                phase="startup_permissions_check",
            )

        # Initialize Bark synthesizer (critical component)
        try:
            _bark_synthesizer = BarkSynthesizer(_audio_config)
            await _bark_synthesizer.initialize()
        except Exception as exc:
            _health_manager.record_startup_failure(
                error=exc, component="bark_synthesizer", is_critical=True
            )
            raise  # Re-raise so app_factory also records it

        # Register dependencies - models check already ensures synthesizer exists
        # Only need bark_models dependency (redundant to check synthesizer separately)
        _health_manager.register_dependency("bark_models", _check_models_loaded)
        _health_manager.register_dependency("prewarm", _check_prewarm_complete)

        # Pre-warm models with a synthesis to trigger torch.compile() warmup
        # This prevents the first real request from timing out during compilation
        try:
            await _prewarm_models()
        except Exception as exc:
            # Pre-warm failure is non-critical - service can still function
            _health_manager.record_startup_failure(
                error=exc, component="prewarm", is_critical=False
            )
            _logger.warning("bark.prewarm_failed", error=str(exc))

        # Check Bark library version for optimization opportunities (non-critical)
        try:
            import bark

            bark_version = getattr(bark, "__version__", "unknown")
            _logger.info(
                "bark.library_version",
                version=bark_version,
                phase="startup_check",
                note="Check PyPI for newer versions if performance issues persist",
            )
        except Exception as version_check_exc:
            # Non-critical - version check failed, continue
            _logger.debug(
                "bark.version_check_failed",
                error=str(version_check_exc),
                error_type=type(version_check_exc).__name__,
                phase="startup_check",
                note="Version check failed, continuing without version info",
            )

        # Only mark startup complete if no critical failures occurred
        if not _health_manager.has_startup_failure():
            _health_manager.mark_startup_complete()
            _logger.info("service.startup_complete", service="bark")
        else:
            _logger.warning(
                "service.startup_not_completed",
                service="bark",
                reason="critical_failure_detected",
            )

    except Exception as exc:
        _logger.error("service.startup_failed", error=str(exc))
        # Failure already recorded above or will be recorded by app_factory
        # Re-raise so app_factory can also record it
        raise


async def _shutdown() -> None:
    """Cleanup resources on shutdown."""
    try:
        if _bark_synthesizer:
            await _bark_synthesizer.cleanup()
        _logger.info("service.shutdown_complete", service="bark")
    except Exception as exc:
        _logger.error("service.shutdown_failed", error=str(exc))


# Create app using factory pattern
app = create_service_app(
    "bark",
    "1.0.0",
    title="Bark TTS Service",
    startup_callback=_startup,
    shutdown_callback=_shutdown,
    health_manager=_health_manager,
)


def _get_bark_device_info() -> dict[str, Any]:
    """Get current Bark service device information for health checks."""
    import torch
    from services.common.gpu_utils import get_full_device_info

    # Detect intended device
    intended_device = "cuda" if torch.cuda.is_available() else "cpu"

    # Get actual device from loaded Bark models
    loaded_model = None
    try:
        from bark.generation import models as bark_models

        # Text model is nested: models["text"]["model"], others are direct
        if (
            "text" in bark_models
            and bark_models["text"] is not None
            and "model" in bark_models["text"]
            and bark_models["text"]["model"] is not None
        ):
            loaded_model = bark_models["text"]["model"]
        elif "coarse" in bark_models and bark_models["coarse"] is not None:
            loaded_model = bark_models["coarse"]
        elif "fine" in bark_models and bark_models["fine"] is not None:
            loaded_model = bark_models["fine"]
    except (ImportError, AttributeError, KeyError):
        pass

    # Use common utility to get full device info (mirrors FLAN pattern)
    return get_full_device_info(model=loaded_model, intended_device=intended_device)


# Initialize health endpoints
health_endpoints = HealthEndpoints(
    service_name="bark",
    health_manager=_health_manager,
    custom_components={
        "bark_synthesizer_loaded": lambda: _bark_synthesizer is not None,
        "device_info": _get_bark_device_info,
    },
)

# Include the health endpoints router
app.include_router(health_endpoints.get_router())


@app.post("/synthesize")  # type: ignore[misc]
async def synthesize(
    request: SynthesisRequest, http_request: Request
) -> SynthesisResponse:
    """Synthesize text to speech using Bark with Piper fallback."""
    # Extract correlation ID from headers or context
    correlation_id: str | None = None
    try:
        from services.common.middleware import get_correlation_id

        correlation_id = get_correlation_id()
    except ImportError:
        pass

    # Fallback to extracting from Request headers
    if not correlation_id:
        correlation_id = http_request.headers.get("X-Correlation-ID")

    if _bark_synthesizer is None:
        raise HTTPException(status_code=503, detail="Bark synthesizer not available")

    # Check if models are loading (non-blocking)
    if _bark_synthesizer._model_loader.is_loading():
        raise HTTPException(
            status_code=503,
            detail="Bark models are currently loading. Please try again shortly.",
        )

    # Check if models are loaded (non-blocking)
    if not _bark_synthesizer._model_loader.is_loaded():
        status = _bark_synthesizer._model_loader.get_status()
        error_msg = status.get("error", "Models not available")
        raise HTTPException(
            status_code=503,
            detail=f"Bark models not available: {error_msg}",
        )

    start_time = time.time()

    _logger.info(
        "bark.synthesis_start",
        text_length=len(request.text),
        voice=request.voice,
        speed=request.speed,
        correlation_id=correlation_id,
    )

    try:
        # Try Bark first
        try:
            audio_data, engine = await _bark_synthesizer.synthesize(
                text=request.text,
                voice=request.voice,
                speed=request.speed,
                correlation_id=correlation_id,
            )
        except Exception as bark_exc:
            _logger.error(
                "bark.synthesis_failed",
                error=str(bark_exc),
                correlation_id=correlation_id,
            )

            # Record error metrics
            processing_time = (time.time() - start_time) * 1000
            if _tts_metrics:
                if "tts_requests" in _tts_metrics:
                    _tts_metrics["tts_requests"].add(
                        1, attributes={"engine": "bark", "status": "error"}
                    )
                if "tts_synthesis_duration" in _tts_metrics:
                    _tts_metrics["tts_synthesis_duration"].record(
                        processing_time / 1000,
                        attributes={"engine": "bark", "status": "error"},
                    )

            raise HTTPException(
                status_code=500, detail=f"Bark synthesis failed: {str(bark_exc)}"
            )

        processing_time = (time.time() - start_time) * 1000

        # Record metrics
        if _tts_metrics:
            if "tts_requests" in _tts_metrics:
                _tts_metrics["tts_requests"].add(
                    1, attributes={"engine": engine, "status": "success"}
                )
            if "tts_synthesis_duration" in _tts_metrics:
                _tts_metrics["tts_synthesis_duration"].record(
                    processing_time / 1000, attributes={"engine": engine}
                )
            if "tts_text_length" in _tts_metrics:
                _tts_metrics["tts_text_length"].record(
                    len(request.text), attributes={"engine": engine}
                )

        _logger.info(
            "tts.synthesis_completed",
            engine=engine,
            processing_time_ms=processing_time,
            text_length=len(request.text),
            voice=request.voice,
            correlation_id=correlation_id,
        )

        # Encode audio bytes as base64 for JSON serialization
        import base64

        audio_base64 = base64.b64encode(audio_data).decode("utf-8")

        return SynthesisResponse(
            audio=audio_base64,
            engine=engine,
            processing_time_ms=processing_time,
            voice_used=request.voice,
        )

    except Exception as exc:
        # Record error metrics
        processing_time = (time.time() - start_time) * 1000
        if _tts_metrics:
            if "tts_requests" in _tts_metrics:
                _tts_metrics["tts_requests"].add(
                    1, attributes={"engine": "unknown", "status": "error"}
                )
            if "tts_synthesis_duration" in _tts_metrics:
                _tts_metrics["tts_synthesis_duration"].record(
                    processing_time / 1000,
                    attributes={"engine": "unknown", "status": "error"},
                )

        _logger.error(
            "tts.synthesis_failed",
            error=str(exc),
            correlation_id=correlation_id,
        )
        raise HTTPException(
            status_code=500, detail=f"Text synthesis failed: {str(exc)}"
        )


@app.get("/voices")  # type: ignore[misc]
async def list_voices() -> dict[str, list[str]]:
    """List available voice presets."""
    return {"bark": VOICE_PRESETS, "piper": ["default"]}


# Track last known state to only log on changes
_last_model_check_state: dict[str, Any] | None = None


async def _check_models_loaded() -> bool:
    """Check if Bark models are loaded and ready."""
    global _last_model_check_state

    if _bark_synthesizer is None:
        # Only log if state changed
        if (
            _last_model_check_state is None
            or _last_model_check_state.get("ready") is not False
        ):
            _logger.warning(
                "health.bark_models_check",
                synthesizer=None,
                ready=False,
                service="bark",
            )
        _last_model_check_state = {"ready": False, "reason": "synthesizer_none"}
        return False

    model_loader = _bark_synthesizer._model_loader
    # _model_loader is always initialized in BarkSynthesizer.__init__, so it's never None

    # Models must be loaded AND not currently loading
    is_loaded = model_loader.is_loaded()
    is_loading = model_loader.is_loading()
    loader_status = model_loader.get_status()
    phase = loader_status.get("phase", "unknown")

    # Service is ready only if models are loaded and not still loading
    ready = is_loaded and not is_loading

    # Only log if state changed (reduce log noise from frequent health checks)
    current_state = {
        "ready": ready,
        "is_loaded": is_loaded,
        "is_loading": is_loading,
        "phase": phase,
    }

    if _last_model_check_state != current_state:
        if ready:
            _logger.info(
                "health.bark_models_check",
                is_loaded=is_loaded,
                is_loading=is_loading,
                phase=phase,
                ready=ready,
                service="bark",
            )
        else:
            _logger.debug(
                "health.bark_models_check",
                is_loaded=is_loaded,
                is_loading=is_loading,
                phase=phase,
                ready=ready,
                service="bark",
            )
        _last_model_check_state = current_state

    return ready


async def _prewarm_models() -> None:
    """Pre-warm Bark models by performing a synthesis to trigger torch.compile() warmup.

    This ensures the first compilation run happens during startup rather than
    on the first real request, preventing timeouts.
    """
    global _prewarm_complete

    if _bark_synthesizer is None:
        _logger.warning(
            "bark.prewarm_skipped",
            reason="synthesizer_not_available",
            message="Skipping pre-warm: synthesizer not initialized",
        )
        return

    # Check if pre-warm is enabled via environment variable
    import os

    enable_prewarm = os.getenv("BARK_ENABLE_PREWARM", "true").lower() in (
        "true",
        "1",
        "yes",
    )
    if not enable_prewarm:
        _logger.info(
            "bark.prewarm_disabled",
            message="Pre-warm disabled via BARK_ENABLE_PREWARM environment variable",
        )
        _prewarm_complete = True  # Mark complete if disabled
        return

    _logger.info(
        "bark.prewarm_start",
        message="Starting model pre-warming to trigger torch.compile() warmup",
    )

    prewarm_start = time.time()

    try:
        # Wait for models to be loaded before pre-warming
        # This ensures models are ready before attempting synthesis
        model_loader = _bark_synthesizer._model_loader
        if model_loader.is_loading():
            _logger.info(
                "bark.prewarm_waiting",
                message="Waiting for models to finish loading before pre-warming",
            )
            # Poll until models are loaded (with timeout safety)
            import asyncio

            max_wait_seconds = 300  # 5 minutes max wait
            poll_interval = 0.5  # Check every 500ms
            elapsed = 0.0

            while model_loader.is_loading() and elapsed < max_wait_seconds:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

            if model_loader.is_loading():
                _logger.warning(
                    "bark.prewarm_timeout",
                    elapsed_seconds=elapsed,
                    message="Model loading timeout exceeded, skipping pre-warm",
                )
                _prewarm_complete = True
                return

        # Ensure models are loaded before proceeding
        if not await model_loader.ensure_loaded():
            status = model_loader.get_status()
            error_msg = status.get("error", "Unknown error")
            raise RuntimeError(f"Bark models not available: {error_msg}")

        if not model_loader.is_loaded():
            raise RuntimeError("Bark models not available")

        _logger.info(
            "bark.prewarm_models_ready",
            message="Models loaded, proceeding with pre-warm synthesis",
        )

        # Perform a small synthesis to trigger compilation warmup
        # Use a short text to minimize startup time while still warming up the pipeline
        prewarm_text = "Hello"
        prewarm_voice = "v2/en_speaker_1"

        await _bark_synthesizer.synthesize(
            text=prewarm_text,
            voice=prewarm_voice,
            speed=1.0,
            correlation_id="bark-prewarm",
        )

        prewarm_duration = (time.time() - prewarm_start) * 1000
        _prewarm_complete = True

        _logger.info(
            "bark.prewarm_complete",
            duration_ms=round(prewarm_duration, 2),
            message="Model pre-warming completed successfully",
        )
    except Exception as exc:
        # Log error but don't block startup - service can still work
        prewarm_duration = (time.time() - prewarm_start) * 1000
        _logger.error(
            "bark.prewarm_failed",
            error=str(exc),
            error_type=type(exc).__name__,
            duration_ms=round(prewarm_duration, 2),
            message="Pre-warm failed but continuing startup - first request may be slower",
        )
        # Mark complete anyway to allow service to start
        # The health check will still report ready, but first request might be slow
        _prewarm_complete = True


async def _check_prewarm_complete() -> bool:
    """Check if pre-warming is complete.

    Returns:
        True if pre-warming is complete or disabled, False otherwise
    """
    return _prewarm_complete


if __name__ == "__main__":
    uvicorn.run(
        "services.bark.app:app",
        host="0.0.0.0",
        port=7100,
        reload=False,
    )
