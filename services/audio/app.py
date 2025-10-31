"""FastAPI application for the unified audio processing service.

This service provides HTTP API endpoints for audio processing including:
- Frame processing with VAD
- Audio enhancement with MetricGAN+
- Quality metrics calculation
- Performance monitoring
"""

from __future__ import annotations

import base64
import time
from typing import Any

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel
import uvicorn

from services.common.audio_metrics import create_audio_metrics, create_http_metrics
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

# Import local audio types
from services.common.surfaces.types import AudioSegment, PCMFrame

from services.audio.enhancement import AudioEnhancer
from services.audio.processor import AudioProcessor


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
        _audio_metrics = create_audio_metrics(_observability_manager)
        _http_metrics = create_http_metrics(_observability_manager)

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


@app.post("/process/frame", response_model=ProcessingResponse)  # type: ignore[misc]
async def process_frame(request: PCMFrameRequest) -> ProcessingResponse:
    """Process a single PCM frame with VAD and basic processing.

    Args:
        request: PCM frame processing request

    Returns:
        Processed frame with quality metrics
    """
    start_time = time.perf_counter()

    try:
        if not _audio:
            raise HTTPException(
                status_code=503, detail="Audio processor not initialized"
            )

        # Decode PCM data
        pcm_data = base64.b64decode(request.pcm)

        # Create PCMFrame object
        frame = PCMFrame(
            pcm=pcm_data,
            timestamp=request.timestamp,
            rms=request.rms,
            duration=request.duration,
            sequence=request.sequence,
            sample_rate=request.sample_rate,
        )

        # Process frame
        processed_frame = await _audio.process_frame(frame)

        # Calculate quality metrics
        quality_metrics = await _audio.calculate_quality_metrics(processed_frame)

        processing_time = (time.perf_counter() - start_time) * 1000

        # Record metrics
        if _audio_metrics:
            if "audio_processing_duration" in _audio_metrics:
                _audio_metrics["audio_processing_duration"].record(
                    processing_time / 1000,
                    attributes={"stage": "frame_processing", "status": "success"},
                )
            if "audio_chunks_processed" in _audio_metrics:
                _audio_metrics["audio_chunks_processed"].add(
                    1, attributes={"type": "frame"}
                )

        # Encode processed PCM data
        processed_pcm = base64.b64encode(processed_frame.pcm).decode()

        _logger.debug(
            "audio.frame_processed",
            sequence=request.sequence,
            processing_time_ms=processing_time,
            quality_metrics=quality_metrics,
        )

        return ProcessingResponse(
            success=True,
            pcm=processed_pcm,
            processing_time_ms=processing_time,
            quality_metrics=quality_metrics,
        )

    except Exception as exc:
        processing_time = (time.perf_counter() - start_time) * 1000

        # Record error metrics
        if _audio_metrics and "audio_processing_duration" in _audio_metrics:
            _audio_metrics["audio_processing_duration"].record(
                processing_time / 1000,
                attributes={"stage": "frame_processing", "status": "error"},
            )

        _logger.error(
            "audio.frame_processing_failed",
            sequence=request.sequence,
            error=str(exc),
            processing_time_ms=processing_time,
        )

        return ProcessingResponse(
            success=False,
            pcm=request.pcm,  # Return original data
            processing_time_ms=processing_time,
            error=str(exc),
        )


@app.post("/process/segment", response_model=ProcessingResponse)  # type: ignore[misc]
async def process_segment(request: AudioSegmentRequest) -> ProcessingResponse:
    """Process an audio segment with full enhancement pipeline.

    Args:
        request: Audio segment processing request

    Returns:
        Processed segment with quality metrics
    """
    start_time = time.perf_counter()

    try:
        if not _audio:
            raise HTTPException(
                status_code=503, detail="Audio processor not initialized"
            )

        # Decode PCM data
        pcm_data = base64.b64decode(request.pcm)

        # Create AudioSegment object
        segment = AudioSegment(
            user_id=str(request.user_id),
            pcm=pcm_data,
            start_timestamp=request.start_timestamp,
            end_timestamp=request.end_timestamp,
            correlation_id=request.correlation_id,
            frame_count=request.frame_count,
            sample_rate=request.sample_rate,
        )

        # Process segment
        processed_segment = await _audio.process_segment(segment)

        # Calculate quality metrics
        quality_metrics = await _audio.calculate_quality_metrics(processed_segment)

        processing_time = (time.perf_counter() - start_time) * 1000

        # Record metrics
        if _audio_metrics:
            if "audio_processing_duration" in _audio_metrics:
                _audio_metrics["audio_processing_duration"].record(
                    processing_time / 1000,
                    attributes={"stage": "segment_processing", "status": "success"},
                )
            if "audio_chunks_processed" in _audio_metrics:
                _audio_metrics["audio_chunks_processed"].add(
                    1, attributes={"type": "segment"}
                )
            if "audio_quality_score" in _audio_metrics and quality_metrics:
                quality_score = quality_metrics.get("overall_score", 0.0)
                _audio_metrics["audio_quality_score"].record(quality_score)

        # Encode processed PCM data
        processed_pcm = base64.b64encode(processed_segment.pcm).decode()

        _logger.info(
            "audio.segment_processed",
            correlation_id=request.correlation_id,
            user_id=request.user_id,
            processing_time_ms=processing_time,
            quality_metrics=quality_metrics,
        )

        return ProcessingResponse(
            success=True,
            pcm=processed_pcm,
            processing_time_ms=processing_time,
            quality_metrics=quality_metrics,
        )

    except Exception as exc:
        processing_time = (time.perf_counter() - start_time) * 1000

        # Record error metrics
        if _audio_metrics and "audio_processing_duration" in _audio_metrics:
            _audio_metrics["audio_processing_duration"].record(
                processing_time / 1000,
                attributes={"stage": "segment_processing", "status": "error"},
            )

        _logger.error(
            "audio.segment_processing_failed",
            correlation_id=request.correlation_id,
            user_id=request.user_id,
            error=str(exc),
            processing_time_ms=processing_time,
        )

        return ProcessingResponse(
            success=False,
            pcm=request.pcm,  # Return original data
            processing_time_ms=processing_time,
            error=str(exc),
        )


@app.post("/enhance/audio")  # type: ignore[misc]
async def enhance_audio(request: Request) -> Response:
    """Apply audio enhancement to WAV data.

    Args:
        request: HTTP request with audio file

    Returns:
        Enhanced audio data as binary response
    """
    start_time = time.perf_counter()

    try:
        if not _audio_enhancer:
            raise HTTPException(
                status_code=503, detail="Audio enhancer not initialized"
            )

        # Get audio data from request
        audio_data = await request.body()

        # Apply enhancement
        enhanced_data = _audio_enhancer.enhance_audio(audio_data)

        processing_time = (time.perf_counter() - start_time) * 1000

        _logger.info(
            "audio.audio_enhanced",
            input_size=len(audio_data),
            output_size=len(enhanced_data),
            processing_time_ms=processing_time,
        )

        return Response(
            content=bytes(enhanced_data),
            media_type="audio/wav",
            headers={"Content-Disposition": "attachment; filename=enhanced.wav"},
        )

    except Exception as exc:
        processing_time = (time.perf_counter() - start_time) * 1000
        _logger.error(
            "audio.enhancement_failed",
            error=str(exc),
            processing_time_ms=processing_time,
        )

        # Return original data on failure
        original_data = await request.body()
        return Response(
            content=bytes(original_data),
            media_type="audio/wav",
            headers={"Content-Disposition": "attachment; filename=original.wav"},
        )


@app.post("/denoise")  # type: ignore[misc]
async def denoise_audio(request: Request) -> Response:
    """Denoise full audio file using MetricGAN+."""
    start_time = time.perf_counter()

    try:
        if not _audio_enhancer:
            raise HTTPException(
                status_code=503, detail="Audio enhancer not initialized"
            )

        # Get audio data from request
        audio_data = await request.body()

        # Apply denoising enhancement
        denoised_data = _audio_enhancer.enhance_audio(audio_data)

        processing_time = (time.perf_counter() - start_time) * 1000

        _logger.info(
            "audio.audio_denoised",
            input_size=len(audio_data),
            output_size=len(denoised_data),
            processing_time_ms=processing_time,
        )

        return Response(
            content=bytes(denoised_data),
            media_type="audio/wav",
            headers={"Content-Disposition": "attachment; filename=denoised.wav"},
        )

    except Exception as exc:
        processing_time = (time.perf_counter() - start_time) * 1000
        _logger.error(
            "audio.denoising_failed",
            error=str(exc),
            processing_time_ms=processing_time,
        )

        # Return original data on failure
        original_data = await request.body()
        return Response(
            content=bytes(original_data),
            media_type="audio/wav",
            headers={"Content-Disposition": "attachment; filename=original.wav"},
        )


@app.post("/denoise/streaming")  # type: ignore[misc]
async def denoise_streaming(request: Request) -> Response:
    """Denoise streaming audio frames using MetricGAN+."""
    start_time = time.perf_counter()

    try:
        if not _audio_enhancer:
            raise HTTPException(
                status_code=503, detail="Audio enhancer not initialized"
            )

        # Get audio data from request
        audio_data = await request.body()

        # Apply streaming denoising enhancement
        denoised_data = _audio_enhancer.enhance_audio(audio_data)

        processing_time = (time.perf_counter() - start_time) * 1000

        _logger.info(
            "audio.streaming_denoised",
            input_size=len(audio_data),
            output_size=len(denoised_data),
            processing_time_ms=processing_time,
        )

        return Response(
            content=bytes(denoised_data),
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=denoised_streaming.wav"
            },
        )

    except Exception as exc:
        processing_time = (time.perf_counter() - start_time) * 1000
        _logger.error(
            "audio.streaming_denoising_failed",
            error=str(exc),
            processing_time_ms=processing_time,
        )

        # Return original data on failure
        original_data = await request.body()
        return Response(
            content=bytes(original_data),
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=original_streaming.wav"
            },
        )


async def _check_audio_health() -> bool:
    """Check audio processor health."""
    return _audio is not None


async def _check_audio_enhancer_health() -> bool:
    """Check audio enhancer health."""
    return _audio_enhancer is not None and _audio_enhancer.is_enhancement_enabled


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=_service_config.host,
        port=_service_config.port,
        workers=_service_config.workers,
        log_level=_logging_config.level.lower(),
    )
