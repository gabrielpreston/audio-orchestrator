"""FastAPI application for the audio preprocessing service.

This service provides HTTP API endpoints for audio preprocessing including:
- MetricGAN+ denoising for noise reduction
- Real-time frame processing
- Audio quality enhancement
- Performance monitoring
"""

from __future__ import annotations

import time
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile
from pydantic import BaseModel

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

from .enhancement import AudioPreprocessor

app = FastAPI(
    title="Audio Preprocessor Service",
    description="Audio preprocessing service with MetricGAN+ denoising for audio-orchestrator",
    version="1.0.0",
)

# Global variables
_audio_preprocessor: AudioPreprocessor | None = None
_health_manager = HealthManager("audio-preprocessor")
_logger = get_logger(__name__, service_name="audio_preprocessor")

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
    service_name="audio_preprocessor",
)


class DenoiseRequest(BaseModel):
    """Request model for audio denoising."""

    audio_data: bytes


class DenoiseResponse(BaseModel):
    """Response model for audio denoising."""

    enhanced_audio: bytes
    processing_time_ms: float
    quality_improvement: float | None = None


@app.on_event("startup")  # type: ignore[misc]
async def _startup() -> None:
    """Initialize the audio preprocessor service."""
    try:
        # Initialize audio preprocessor
        _audio_preprocessor = AudioPreprocessor(_audio_config)
        await _audio_preprocessor.initialize()

        # Register dependencies
        _health_manager.register_dependency(
            "audio_preprocessor", _check_preprocessor_health
        )

        # Mark startup complete
        _health_manager.mark_startup_complete()

        _logger.info("service.startup_complete", service="audio_preprocessor")
    except Exception as exc:
        _logger.error("service.startup_failed", error=str(exc))
        # Continue without crashing - service will report not_ready


@app.on_event("shutdown")  # type: ignore[misc]
async def _shutdown() -> None:
    """Cleanup resources on shutdown."""
    try:
        if _audio_preprocessor:
            await _audio_preprocessor.cleanup()
        _logger.info("service.shutdown_complete", service="audio_preprocessor")
    except Exception as exc:
        _logger.error("service.shutdown_failed", error=str(exc))


@app.get("/health/live")  # type: ignore[misc]
async def health_live() -> dict[str, str]:
    """Liveness check - always returns 200 if process is alive."""
    return {"status": "alive", "service": "audio_preprocessor"}


@app.get("/health/ready")  # type: ignore[misc]
async def health_ready() -> dict[str, Any]:
    """Readiness check with component status."""
    if _audio_preprocessor is None:
        raise HTTPException(status_code=503, detail="Audio preprocessor not loaded")

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
        "service": "audio_preprocessor",
        "components": {
            "preprocessor_loaded": _audio_preprocessor is not None,
            "startup_complete": _health_manager._startup_complete,
        },
        "dependencies": health_status.details.get("dependencies", {}),
        "health_details": health_status.details,
    }


@app.post("/denoise")  # type: ignore[misc]
async def denoise_audio(audio: UploadFile) -> DenoiseResponse:
    """Denoise audio using MetricGAN+ preprocessing."""
    if _audio_preprocessor is None:
        raise HTTPException(status_code=503, detail="Audio preprocessor not available")

    try:
        start_time = time.time()

        # Read audio data
        audio_data = await audio.read()

        # Process audio
        enhanced_audio = await _audio_preprocessor.denoise_audio(audio_data)

        processing_time = (time.time() - start_time) * 1000

        # Calculate quality improvement (placeholder for now)
        quality_improvement = None

        _logger.info(
            "audio.denoising_completed",
            processing_time_ms=processing_time,
            input_size_bytes=len(audio_data),
            output_size_bytes=len(enhanced_audio),
        )

        return DenoiseResponse(
            enhanced_audio=enhanced_audio,
            processing_time_ms=processing_time,
            quality_improvement=quality_improvement,
        )

    except Exception as exc:
        _logger.error("audio.denoising_failed", error=str(exc))
        raise HTTPException(
            status_code=500, detail=f"Audio denoising failed: {str(exc)}"
        )


@app.post("/denoise/streaming")  # type: ignore[misc]
async def denoise_streaming(frame_data: bytes) -> bytes:
    """Real-time frame processing for streaming audio."""
    if _audio_preprocessor is None:
        raise HTTPException(status_code=503, detail="Audio preprocessor not available")

    try:
        # Process frame
        enhanced_frame = await _audio_preprocessor.denoise_frame(frame_data)

        _logger.debug("audio.frame_processed", frame_size=len(frame_data))

        return bytes(enhanced_frame)

    except Exception as exc:
        _logger.error("audio.frame_processing_failed", error=str(exc))
        raise HTTPException(
            status_code=500, detail=f"Frame processing failed: {str(exc)}"
        )


@app.get("/metrics")  # type: ignore[misc]
async def get_metrics() -> dict[str, Any]:
    """Get service metrics."""
    if _audio_preprocessor is None:
        return {"error": "Audio preprocessor not available"}

    return dict(await _audio_preprocessor.get_metrics())


async def _check_preprocessor_health() -> bool:
    """Check if audio preprocessor is healthy."""
    return _audio_preprocessor is not None and await _audio_preprocessor.is_healthy()


if __name__ == "__main__":
    uvicorn.run(
        "services.audio_preprocessor.app:app",
        host="0.0.0.0",
        port=9200,
        reload=False,
    )
