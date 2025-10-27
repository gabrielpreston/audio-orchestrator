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

from fastapi import FastAPI, HTTPException
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
from services.common.structured_logging import configure_logging, get_logger

from .synthesis import BarkSynthesizer


app = FastAPI(
    title="Bark TTS Service",
    description="Text-to-speech service using Bark with Piper fallback for audio-orchestrator",
    version="1.0.0",
)

# Global variables
_bark_synthesizer: BarkSynthesizer | None = None
_health_manager = HealthManager("tts-bark")
_logger = get_logger(__name__, service_name="tts_bark")

# Load configuration
_config_preset = get_service_preset("tts")
_logging_config = LoggingConfig(**_config_preset["logging"])
_http_config = HttpConfig(**_config_preset["http"])
_audio_config = AudioConfig(**_config_preset["audio"])
_service_config = ServiceConfig(**_config_preset["service"])
_telemetry_config = TelemetryConfig(**_config_preset["telemetry"])

# Configure logging
configure_logging(
    _logging_config.level,
    json_logs=_logging_config.json_logs,
    service_name="tts_bark",
)

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

    audio: bytes
    engine: str
    processing_time_ms: float
    voice_used: str


@app.on_event("startup")  # type: ignore[misc]
async def _startup() -> None:
    """Initialize the Bark TTS service."""
    try:
        # Initialize Bark synthesizer
        _bark_synthesizer = BarkSynthesizer(_audio_config)
        await _bark_synthesizer.initialize()

        # Register dependencies
        _health_manager.register_dependency(
            "bark_synthesizer", _check_synthesizer_health
        )

        # Mark startup complete
        _health_manager.mark_startup_complete()

        _logger.info("service.startup_complete", service="tts_bark")
    except Exception as exc:
        _logger.error("service.startup_failed", error=str(exc))
        # Continue without crashing - service will report not_ready


@app.on_event("shutdown")  # type: ignore[misc]
async def _shutdown() -> None:
    """Cleanup resources on shutdown."""
    try:
        if _bark_synthesizer:
            await _bark_synthesizer.cleanup()
        _logger.info("service.shutdown_complete", service="tts_bark")
    except Exception as exc:
        _logger.error("service.shutdown_failed", error=str(exc))


@app.get("/health/live")  # type: ignore[misc]
async def health_live() -> dict[str, str]:
    """Liveness check - always returns 200 if process is alive."""
    return {"status": "alive", "service": "tts_bark"}


@app.get("/health/ready")  # type: ignore[misc]
async def health_ready() -> dict[str, Any]:
    """Readiness check with component status."""
    if _bark_synthesizer is None:
        raise HTTPException(status_code=503, detail="Bark synthesizer not loaded")

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
        "service": "tts_bark",
        "components": {
            "bark_synthesizer_loaded": _bark_synthesizer is not None,
            "startup_complete": _health_manager._startup_complete,
        },
        "dependencies": health_status.details.get("dependencies", {}),
        "health_details": health_status.details,
    }


@app.post("/synthesize")  # type: ignore[misc]
async def synthesize(request: SynthesisRequest) -> SynthesisResponse:
    """Synthesize text to speech using Bark with Piper fallback."""
    if _bark_synthesizer is None:
        raise HTTPException(status_code=503, detail="Bark synthesizer not available")

    try:
        start_time = time.time()

        # Try Bark first
        try:
            audio_data, engine = await _bark_synthesizer.synthesize(
                text=request.text, voice=request.voice, speed=request.speed
            )
        except Exception as bark_exc:
            _logger.error("bark.synthesis_failed", error=str(bark_exc))
            raise HTTPException(
                status_code=500, detail=f"Bark synthesis failed: {str(bark_exc)}"
            )

        processing_time = (time.time() - start_time) * 1000

        _logger.info(
            "tts.synthesis_completed",
            engine=engine,
            processing_time_ms=processing_time,
            text_length=len(request.text),
            voice=request.voice,
        )

        return SynthesisResponse(
            audio=audio_data,
            engine=engine,
            processing_time_ms=processing_time,
            voice_used=request.voice,
        )

    except Exception as exc:
        _logger.error("tts.synthesis_failed", error=str(exc))
        raise HTTPException(
            status_code=500, detail=f"Text synthesis failed: {str(exc)}"
        )


@app.get("/voices")  # type: ignore[misc]
async def list_voices() -> dict[str, list[str]]:
    """List available voice presets."""
    return {"bark": VOICE_PRESETS, "piper": ["default"]}


async def _check_synthesizer_health() -> bool:
    """Check if Bark synthesizer is healthy."""
    return _bark_synthesizer is not None and await _bark_synthesizer.is_healthy()


if __name__ == "__main__":
    uvicorn.run(
        "services.tts_bark.app:app",
        host="0.0.0.0",
        port=7100,
        reload=False,
    )
