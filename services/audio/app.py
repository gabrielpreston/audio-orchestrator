"""FastAPI application for the unified audio processing service.

This service provides HTTP API endpoints for audio processing including:
- Frame processing with VAD
- Audio enhancement with MetricGAN+
- Quality metrics calculation
- Performance monitoring
"""

from __future__ import annotations

import time
from typing import Any, cast

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel
import uvicorn

from services.audio.enhancement import AudioEnhancer
from services.audio.processor import AudioProcessor
from services.common.app_factory import create_service_app
from services.common.audio_processing import process_audio_request
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
from services.common.permissions import ensure_model_directory
from services.common.structured_logging import configure_logging, get_logger

# Import local audio types
from services.common.surfaces.types import AudioSegment, PCMFrame
from services.common.tracing import get_observability_manager


# Global variables
_audio: AudioProcessor | None = None
_audio_enhancer: AudioEnhancer | None = None
_health_manager = HealthManager("audio")
_observability_manager = None
_audio_metrics = {}
_http_metrics = {}
_logger = get_logger(__name__, service_name="audio")

# Load configuration
_config_preset = get_service_preset("audio")
_logging_config = LoggingConfig(**_config_preset["logging"])
_http_config = HttpConfig(**_config_preset["http"])
_audio_config = AudioConfig(**_config_preset["audio"])
_service_config = ServiceConfig(**_config_preset["service"])
_telemetry_config = TelemetryConfig(**_config_preset["telemetry"])

# Configure logging
configure_logging(
    _logging_config.level,
    json_logs=_logging_config.json_logs,
    service_name="audio",
)


class PCMFrameRequest(BaseModel):
    """Request model for PCM frame processing."""

    pcm: str  # Base64 encoded PCM data
    timestamp: float
    rms: float
    duration: float
    sequence: int
    sample_rate: int


class AudioSegmentRequest(BaseModel):
    """Request model for audio segment processing."""

    user_id: int
    pcm: str  # Base64 encoded PCM data
    start_timestamp: float
    end_timestamp: float
    correlation_id: str
    frame_count: int
    sample_rate: int


class ProcessingResponse(BaseModel):
    """Response model for audio processing."""

    success: bool
    pcm: str  # Base64 encoded processed PCM data
    processing_time_ms: float
    quality_metrics: dict[str, Any] | None = None
    error: str | None = None


async def _startup() -> None:
    """Initialize audio processor and enhancer on startup."""
    global \
        _audio, \
        _audio_enhancer, \
        _observability_manager, \
        _audio_metrics, \
        _http_metrics

    try:
        _logger.info("audio.startup_started")

        # Get observability manager (factory already setup observability)
        _observability_manager = get_observability_manager("audio")

        # Create service-specific metrics
        from services.common.audio_metrics import (
            create_audio_metrics,
            create_http_metrics,
            create_system_metrics,
        )

        _audio_metrics = create_audio_metrics(_observability_manager)
        _http_metrics = create_http_metrics(_observability_manager)
        _system_metrics = create_system_metrics(_observability_manager)

        # Set observability manager in health manager
        _health_manager.set_observability_manager(_observability_manager)

        # Register dependencies
        _health_manager.register_dependency("audio", _check_audio_health)
        _health_manager.register_dependency(
            "audio_enhancer", _check_audio_enhancer_health
        )

        # Initialize audio processor
        _audio = AudioProcessor(_audio_config)
        await _audio.initialize()

        # Initialize audio enhancer
        # Get model savedir from environment or use default
        import os

        model_savedir = os.getenv(
            "METRICGAN_MODEL_SAVEDIR", "/app/models/metricgan-plus"
        )
        model_source = os.getenv(
            "METRICGAN_MODEL_SOURCE", "speechbrain/metricgan-plus-voicebank"
        )

        # Ensure model directory is writable
        from pathlib import Path

        model_path = Path(model_savedir)
        parent = model_path.parent
        # If parent is root or current dir, use default
        model_dir = str(parent) if str(parent) not in (".", "/") else "/app/models"
        if not ensure_model_directory(model_dir):
            _logger.warning(
                "audio.model_directory_not_writable",
                model_dir=model_dir,
                message="MetricGAN model downloads may fail",
            )

        _audio_enhancer = AudioEnhancer(
            enable_metricgan=_audio_config.enable_enhancement,
            device="cpu",
            model_source=model_source,
            model_savedir=model_savedir,
        )

        # Mark startup complete
        _health_manager.mark_startup_complete()

        _logger.info("audio.startup_completed")

    except Exception as exc:
        _logger.error("audio.startup_failed", error=str(exc))
        # Continue without crashing - service will report not_ready


async def _shutdown() -> None:
    """Cleanup on shutdown."""
    try:
        if _audio:
            await _audio.cleanup()
        _logger.info("audio.shutdown_completed")
    except Exception as exc:
        _logger.error("audio.shutdown_failed", error=str(exc))


# Create app using factory pattern
app = create_service_app(
    "audio",
    "1.0.0",
    title="Audio Processor Service",
    startup_callback=_startup,
    shutdown_callback=_shutdown,
)


# Initialize health endpoints
health_endpoints = HealthEndpoints(
    service_name="audio",
    health_manager=_health_manager,
    custom_components={
        "processor_loaded": lambda: _audio is not None,
        "enhancer_loaded": lambda: _audio_enhancer is not None,
        "enhancer_enabled": lambda: (
            _audio_enhancer.is_enhancement_enabled if _audio_enhancer else False
        ),
    },
)

# Include the health endpoints router
app.include_router(health_endpoints.get_router())


async def process_enhancement_request(
    request: Request,
    *,
    response_filename: str,
    log_event_prefix: str,
    correlation_id: str | None = None,
) -> Response:
    """Process audio enhancement request with consistent handling.

    This helper function centralizes request parsing, enhancement invocation,
    logging, metrics, and error handling for all audio enhancement endpoints.

    Args:
        request: HTTP request with audio file in body
        response_filename: Filename for Content-Disposition header
        log_event_prefix: Prefix for log event names (e.g., "enhancement", "denoising")
        correlation_id: Optional correlation ID (overrides header extraction)

    Returns:
        Response with enhanced audio data or original audio on error
    """
    start_time = time.perf_counter()

    # Extract correlation ID from headers if not provided
    if correlation_id is None:
        correlation_id = request.headers.get("X-Correlation-ID")

    # Log request received
    _logger.info(
        f"audio.{log_event_prefix}_request_received",
        correlation_id=correlation_id,
        content_length=request.headers.get("content-length", "unknown"),
        decision=f"processing_{log_event_prefix}_request",
    )

    # Read and cache request body once (fixes double body read bug)
    audio_data = await request.body()
    input_size = len(audio_data)

    try:
        # Validate enhancer is initialized
        if not _audio_enhancer:
            _logger.error(
                "audio.decision",
                correlation_id=correlation_id,
                decision=f"{log_event_prefix}_rejected",
                reason="enhancer_not_initialized",
            )
            raise HTTPException(
                status_code=503, detail="Audio enhancer not initialized"
            )

        # Log enhancement decision
        _logger.info(
            "audio.decision",
            correlation_id=correlation_id,
            input_size=input_size,
            decision=f"applying_{log_event_prefix}",
            enhancement_method="metricgan_plus",
        )

        # Apply enhancement using correct async method (fixes incorrect method call bug)
        enhanced_data = await _audio_enhancer.enhance_audio_bytes(audio_data)

        processing_time = (time.perf_counter() - start_time) * 1000
        output_size = len(enhanced_data)

        # Record audio metrics
        if _audio_metrics:
            if "audio_processing_duration" in _audio_metrics:
                _audio_metrics["audio_processing_duration"].record(
                    processing_time / 1000,
                    attributes={
                        "stage": log_event_prefix,
                        "status": "success",
                        "service": "audio",
                    },
                )
            if "audio_chunks_processed" in _audio_metrics:
                _audio_metrics["audio_chunks_processed"].add(
                    1, attributes={"type": "enhancement", "service": "audio"}
                )

        # Record HTTP metrics
        if _http_metrics:
            if "http_requests" in _http_metrics:
                _http_metrics["http_requests"].add(
                    1,
                    attributes={"method": "POST", "status": "200", "service": "audio"},
                )
            if "http_request_duration" in _http_metrics:
                _http_metrics["http_request_duration"].record(
                    processing_time / 1000,
                    attributes={"method": "POST", "service": "audio"},
                )

        # Log success
        _logger.info(
            f"audio.{log_event_prefix}_completed",
            correlation_id=correlation_id,
            input_size=input_size,
            output_size=output_size,
            processing_time_ms=processing_time,
            decision=f"{log_event_prefix}_completed",
        )

        return Response(
            content=enhanced_data,  # Already bytes, no need for bytes() conversion
            media_type="audio/wav",
            headers={
                "Content-Disposition": f"attachment; filename={response_filename}"
            },
        )

    except HTTPException:
        # Re-raise HTTP exceptions (e.g., 503 for not initialized)
        raise
    except Exception as exc:
        # Handle all other exceptions with fallback to original audio
        processing_time = (time.perf_counter() - start_time) * 1000

        # Record error metrics
        if _audio_metrics and "audio_processing_duration" in _audio_metrics:
            _audio_metrics["audio_processing_duration"].record(
                processing_time / 1000,
                attributes={
                    "stage": log_event_prefix,
                    "status": "error",
                    "service": "audio",
                },
            )

        if _http_metrics and "http_requests" in _http_metrics:
            _http_metrics["http_requests"].add(
                1, attributes={"method": "POST", "status": "500", "service": "audio"}
            )

        # Log error with full context
        _logger.error(
            f"audio.{log_event_prefix}_failed",
            correlation_id=correlation_id,
            error=str(exc),
            error_type=type(exc).__name__,
            processing_time_ms=processing_time,
            decision=f"{log_event_prefix}_failed_returning_original",
        )

        # Return original data on failure using cached bytes (fixes double body read)
        # Map response filenames to original filenames
        filename_map = {
            "enhanced.wav": "original.wav",
            "denoised.wav": "original.wav",
            "denoised_streaming.wav": "original_streaming.wav",
        }
        original_filename = filename_map.get(response_filename, "original.wav")

        return Response(
            content=audio_data,  # Use cached bytes, not re-read
            media_type="audio/wav",
            headers={
                "Content-Disposition": f"attachment; filename={original_filename}"
            },
        )


@app.post("/process/frame", response_model=ProcessingResponse)  # type: ignore[misc]
async def process_frame(request: PCMFrameRequest) -> ProcessingResponse:
    """Process a single PCM frame with VAD and basic processing.

    Args:
        request: PCM frame processing request

    Returns:
        Processed frame with quality metrics
    """
    if not _audio:
        raise HTTPException(status_code=503, detail="Audio processor not initialized")

    result = await process_audio_request(
        pcm_base64=request.pcm,
        build_domain_object=lambda pcm: PCMFrame(
            pcm=pcm,
            timestamp=request.timestamp,
            rms=request.rms,
            duration=request.duration,
            sequence=request.sequence,
            sample_rate=request.sample_rate,
        ),
        process_audio=lambda frame: _audio.process_frame(cast("PCMFrame", frame)),
        calculate_metrics=lambda frame: _audio.calculate_quality_metrics(
            cast("PCMFrame", frame)
        ),
        audio_metrics=_audio_metrics,
        logger=_logger,
        stage="frame_processing",
        chunk_type="frame",
        log_level="debug",
        log_attributes={"sequence": request.sequence},
        original_pcm_base64=request.pcm,
    )

    return ProcessingResponse(**result)


@app.post("/process/segment", response_model=ProcessingResponse)  # type: ignore[misc]
async def process_segment(request: AudioSegmentRequest) -> ProcessingResponse:
    """Process an audio segment with full enhancement pipeline.

    Args:
        request: Audio segment processing request

    Returns:
        Processed segment with quality metrics
    """
    if not _audio:
        raise HTTPException(status_code=503, detail="Audio processor not initialized")

    result = await process_audio_request(
        pcm_base64=request.pcm,
        build_domain_object=lambda pcm: AudioSegment(
            user_id=str(request.user_id),
            pcm=pcm,
            start_timestamp=request.start_timestamp,
            end_timestamp=request.end_timestamp,
            correlation_id=request.correlation_id,
            frame_count=request.frame_count,
            sample_rate=request.sample_rate,
        ),
        process_audio=lambda segment: _audio.process_segment(
            cast("AudioSegment", segment)
        ),
        calculate_metrics=lambda segment: _audio.calculate_quality_metrics(
            cast("AudioSegment", segment)
        ),
        audio_metrics=_audio_metrics,
        logger=_logger,
        stage="segment_processing",
        chunk_type="segment",
        log_level="info",
        log_attributes={
            "correlation_id": request.correlation_id,
            "user_id": request.user_id,
        },
        original_pcm_base64=request.pcm,
    )

    return ProcessingResponse(**result)


@app.post("/enhance/audio")  # type: ignore[misc]
async def enhance_audio(request: Request) -> Response:
    """Apply audio enhancement to WAV data.

    Args:
        request: HTTP request with audio file

    Returns:
        Enhanced audio data as binary response
    """
    return await process_enhancement_request(
        request,
        response_filename="enhanced.wav",
        log_event_prefix="enhancement",
    )


@app.post("/denoise")  # type: ignore[misc]
async def denoise_audio(request: Request) -> Response:
    """Denoise full audio file using MetricGAN+."""
    return await process_enhancement_request(
        request,
        response_filename="denoised.wav",
        log_event_prefix="denoising",
    )


@app.post("/denoise/streaming")  # type: ignore[misc]
async def denoise_streaming(request: Request) -> Response:
    """Denoise streaming audio frames using MetricGAN+."""
    return await process_enhancement_request(
        request,
        response_filename="denoised_streaming.wav",
        log_event_prefix="streaming_denoising",
    )


async def _check_audio_health() -> bool:
    """Check audio processor health."""
    return _audio is not None


async def _check_audio_enhancer_health() -> bool:
    """Check audio enhancer health - enhancement is optional, so don't block if disabled."""
    # Audio enhancer is optional - service is ready if it exists
    # Model loading happens lazily, so don't require is_enhancement_enabled
    return _audio_enhancer is not None


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=_service_config.host,
        port=_service_config.port,
        workers=_service_config.workers,
        log_level=_logging_config.level.lower(),
    )
