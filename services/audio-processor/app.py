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

from fastapi import FastAPI, HTTPException, Request
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
from services.common.health import HealthManager, HealthStatus
from services.common.logging import configure_logging, get_logger

# Import Discord types for standardization
from services.discord.audio import AudioSegment, PCMFrame

from .enhancement import AudioEnhancer
from .processor import AudioProcessor


app = FastAPI(
    title="Audio Processor Service",
    description="Unified audio processing service for audio-orchestrator",
    version="1.0.0",
)

# Global variables
_audio_processor: AudioProcessor | None = None
_audio_enhancer: AudioEnhancer | None = None
_health_manager = HealthManager("audio-processor")
_logger = get_logger(__name__, service_name="audio-processor")

# Load configuration
_config_preset = get_service_preset("audio-processor")
_logging_config = LoggingConfig(**_config_preset["logging"])
_http_config = HttpConfig(**_config_preset["http"])
_audio_config = AudioConfig(**_config_preset["audio"])
_service_config = ServiceConfig(**_config_preset["service"])
_telemetry_config = TelemetryConfig(**_config_preset["telemetry"])

# Configure logging
configure_logging(
    _logging_config.level,
    json_logs=_logging_config.json_logs,
    service_name="audio-processor",
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


@app.on_event("startup")
async def startup_event() -> None:
    """Initialize audio processor and enhancer on startup."""
    global _audio_processor, _audio_enhancer

    try:
        _logger.info("audio_processor.startup_started")

        # Register dependencies
        _health_manager.register_dependency(
            "audio_processor", _check_audio_processor_health
        )
        _health_manager.register_dependency(
            "audio_enhancer", _check_audio_enhancer_health
        )

        # Initialize audio processor
        _audio_processor = AudioProcessor(_audio_config)
        await _audio_processor.initialize()

        # Initialize audio enhancer
        _audio_enhancer = AudioEnhancer(
            enable_metricgan=_audio_config.enable_enhancement, device="cpu"
        )

        # Mark startup complete
        _health_manager.mark_startup_complete()

        _logger.info("audio_processor.startup_completed")

    except Exception as exc:
        _logger.error("audio_processor.startup_failed", error=str(exc))
        # Continue without crashing - service will report not_ready


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Cleanup on shutdown."""
    try:
        if _audio_processor:
            await _audio_processor.cleanup()
        _logger.info("audio_processor.shutdown_completed")
    except Exception as exc:
        _logger.error("audio_processor.shutdown_failed", error=str(exc))


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    """Liveness check - always returns 200 if process is alive."""
    return {"status": "alive", "service": "audio-processor"}


@app.get("/health/ready")
async def health_ready() -> dict[str, Any]:
    """Readiness check with component status."""
    health_status = await _health_manager.get_health_status()

    # Determine status string
    if not health_status.ready:
        status_str = (
            "degraded" if health_status.status == HealthStatus.DEGRADED else "not_ready"
        )
    else:
        status_str = "ready"

    return {
        "status": status_str,
        "service": "audio-processor",
        "components": {
            "processor_loaded": _audio_processor is not None,
            "enhancer_loaded": _audio_enhancer is not None,
            "enhancer_enabled": _audio_enhancer.is_enhancement_enabled
            if _audio_enhancer
            else False,
            "startup_complete": _health_manager._startup_complete,
        },
        "dependencies": health_status.details.get("dependencies", {}),
        "health_details": health_status.details,
        "performance": {
            "max_concurrent_requests": 10,
            "frame_processing_timeout_ms": 20,
            "enhancement_timeout_ms": 50,
        },
    }


@app.post("/process/frame", response_model=ProcessingResponse)
async def process_frame(request: PCMFrameRequest) -> ProcessingResponse:
    """Process a single PCM frame with VAD and basic processing.

    Args:
        request: PCM frame processing request

    Returns:
        Processed frame with quality metrics
    """
    start_time = time.perf_counter()

    try:
        if not _audio_processor:
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
        processed_frame = await _audio_processor.process_frame(frame)

        # Calculate quality metrics
        quality_metrics = await _audio_processor.calculate_quality_metrics(
            processed_frame
        )

        processing_time = (time.perf_counter() - start_time) * 1000

        # Encode processed PCM data
        processed_pcm = base64.b64encode(processed_frame.pcm).decode()

        _logger.debug(
            "audio_processor.frame_processed",
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
        _logger.error(
            "audio_processor.frame_processing_failed",
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


@app.post("/process/segment", response_model=ProcessingResponse)
async def process_segment(request: AudioSegmentRequest) -> ProcessingResponse:
    """Process an audio segment with full enhancement pipeline.

    Args:
        request: Audio segment processing request

    Returns:
        Processed segment with quality metrics
    """
    start_time = time.perf_counter()

    try:
        if not _audio_processor:
            raise HTTPException(
                status_code=503, detail="Audio processor not initialized"
            )

        # Decode PCM data
        pcm_data = base64.b64decode(request.pcm)

        # Create AudioSegment object
        segment = AudioSegment(
            user_id=request.user_id,
            pcm=pcm_data,
            start_timestamp=request.start_timestamp,
            end_timestamp=request.end_timestamp,
            correlation_id=request.correlation_id,
            frame_count=request.frame_count,
            sample_rate=request.sample_rate,
        )

        # Process segment
        processed_segment = await _audio_processor.process_segment(segment)

        # Calculate quality metrics
        quality_metrics = await _audio_processor.calculate_quality_metrics(
            processed_segment
        )

        processing_time = (time.perf_counter() - start_time) * 1000

        # Encode processed PCM data
        processed_pcm = base64.b64encode(processed_segment.pcm).decode()

        _logger.info(
            "audio_processor.segment_processed",
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
        _logger.error(
            "audio_processor.segment_processing_failed",
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


@app.post("/enhance/audio")
async def enhance_audio(request: Request) -> bytes:
    """Apply audio enhancement to WAV data.

    Args:
        request: HTTP request with audio file

    Returns:
        Enhanced audio data
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
        enhanced_data = await _audio_enhancer.enhance_audio(audio_data)

        processing_time = (time.perf_counter() - start_time) * 1000

        _logger.info(
            "audio_processor.audio_enhanced",
            input_size=len(audio_data),
            output_size=len(enhanced_data),
            processing_time_ms=processing_time,
        )

        return enhanced_data

    except Exception as exc:
        processing_time = (time.perf_counter() - start_time) * 1000
        _logger.error(
            "audio_processor.enhancement_failed",
            error=str(exc),
            processing_time_ms=processing_time,
        )

        # Return original data on failure
        return await request.body()


@app.get("/metrics")
async def get_metrics() -> dict[str, Any]:
    """Get service metrics."""
    return {
        "service": "audio-processor",
        "uptime_seconds": time.time() - _health_manager._startup_time,
        "status": "ready" if _health_manager._startup_complete else "starting",
        "components": {
            "processor_loaded": _audio_processor is not None,
            "enhancer_loaded": _audio_enhancer is not None,
        },
    }


async def _check_audio_processor_health() -> bool:
    """Check audio processor health."""
    return _audio_processor is not None


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
