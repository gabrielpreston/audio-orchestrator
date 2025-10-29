"""FastAPI application for the Bark TTS service.

This service provides HTTP API endpoints for text-to-speech synthesis including:
- Bark TTS generation with multiple voice presets
- Piper fallback for reliability
- Voice selection and configuration
- Performance monitoring
"""

from __future__ import annotations

import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

from services.common.audio_metrics import create_http_metrics, create_tts_metrics
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
from services.common.structured_logging import configure_logging, get_logger
from services.common.tracing import setup_service_observability

from .synthesis import BarkSynthesizer


app = FastAPI(
    title="Bark TTS Service",
    description="Text-to-speech service using Bark with Piper fallback for audio-orchestrator",
    version="1.0.0",
)

# Global variables
_bark_synthesizer: BarkSynthesizer | None = None
_health_manager = HealthManager("bark")
_observability_manager = None
_tts_metrics = {}
_http_metrics = {}
_logger = get_logger(__name__, service_name="bark")

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
    service_name="bark",
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
    global _bark_synthesizer, _observability_manager, _tts_metrics, _http_metrics

    try:
        # Setup observability (tracing + metrics)
        _observability_manager = setup_service_observability("bark", "1.0.0")
        _observability_manager.instrument_fastapi(app)

        # Create service-specific metrics
        _tts_metrics = create_tts_metrics(_observability_manager)
        _http_metrics = create_http_metrics(_observability_manager)

        # Set observability manager in health manager
        _health_manager.set_observability_manager(_observability_manager)

        # Initialize Bark synthesizer
        _bark_synthesizer = BarkSynthesizer(_audio_config)
        await _bark_synthesizer.initialize()

        # Register dependencies
        _health_manager.register_dependency(
            "bark_synthesizer", _check_synthesizer_health
        )

        # Mark startup complete
        _health_manager.mark_startup_complete()

        _logger.info("service.startup_complete", service="bark")
    except Exception as exc:
        _logger.error("service.startup_failed", error=str(exc))
        # Continue without crashing - service will report not_ready


@app.on_event("shutdown")  # type: ignore[misc]
async def _shutdown() -> None:
    """Cleanup resources on shutdown."""
    try:
        if _bark_synthesizer:
            await _bark_synthesizer.cleanup()
        _logger.info("service.shutdown_complete", service="bark")
    except Exception as exc:
        _logger.error("service.shutdown_failed", error=str(exc))


# Initialize health endpoints
health_endpoints = HealthEndpoints(
    service_name="bark",
    health_manager=_health_manager,
    custom_components={
        "bark_synthesizer_loaded": lambda: _bark_synthesizer is not None
    },
)

# Include the health endpoints router
app.include_router(health_endpoints.get_router())


@app.post("/synthesize")  # type: ignore[misc]
async def synthesize(request: SynthesisRequest) -> SynthesisResponse:
    """Synthesize text to speech using Bark with Piper fallback."""
    if _bark_synthesizer is None:
        raise HTTPException(status_code=503, detail="Bark synthesizer not available")

    start_time = time.time()

    try:
        # Try Bark first
        try:
            audio_data, engine = await _bark_synthesizer.synthesize(
                text=request.text, voice=request.voice, speed=request.speed
            )
        except Exception as bark_exc:
            _logger.error("bark.synthesis_failed", error=str(bark_exc))

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
        )

        return SynthesisResponse(
            audio=audio_data,
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
        "services.bark.app:app",
        host="0.0.0.0",
        port=7100,
        reload=False,
    )
