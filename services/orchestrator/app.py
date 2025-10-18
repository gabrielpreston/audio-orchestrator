from __future__ import annotations

from typing import Any

import httpx
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator

from services.common.config import ConfigBuilder, Environment, ServiceConfig
from services.common.health import HealthManager
from services.common.logging import configure_logging, get_logger
from services.common.service_configs import (
    HttpConfig,
    LLMClientConfig,
    LoggingConfig,
    OrchestratorConfig,
    PortConfig,
    TelemetryConfig,
    TestRecorderConfig,
    TTSClientConfig,
)

from .mcp_manager import MCPManager
from .orchestrator import Orchestrator
from .test_recorder import TestRecorderManager

# Prometheus metrics
try:
    from prometheus_client import make_asgi_app

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

app = FastAPI(title="Voice Assistant Orchestrator")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

_cfg: ServiceConfig = (
    ConfigBuilder.for_service("orchestrator", Environment.DOCKER)
    .add_config("logging", LoggingConfig)
    .add_config("http", HttpConfig)
    .add_config("port", PortConfig)
    .add_config("llm_client", LLMClientConfig)
    .add_config("tts_client", TTSClientConfig)
    .add_config("orchestrator", OrchestratorConfig)
    .add_config("test_recorder", TestRecorderConfig)
    .add_config("telemetry", TelemetryConfig)
    .load()
)

configure_logging(
    _cfg.logging.level,  # type: ignore[attr-defined]
    json_logs=_cfg.logging.json_logs,  # type: ignore[attr-defined]
    service_name="orchestrator",
)
logger = get_logger(__name__, service_name="orchestrator")

_ORCHESTRATOR: Orchestrator | None = None
_MCP_MANAGER: MCPManager | None = None
_LLM_CLIENT: httpx.AsyncClient | None = None
_TEST_RECORDER: TestRecorderManager | None = None
_health_manager = HealthManager("orchestrator")

_LLM_BASE_URL = _cfg.llm_client.base_url or "http://llm:8000"  # type: ignore[attr-defined]
_LLM_AUTH_TOKEN = _cfg.llm_client.auth_token  # type: ignore[attr-defined]
_TTS_BASE_URL = _cfg.tts_client.base_url  # type: ignore[attr-defined]
_TTS_AUTH_TOKEN = _cfg.tts_client.auth_token  # type: ignore[attr-defined]
_MCP_CONFIG_PATH = _cfg.orchestrator.mcp_config_path  # type: ignore[attr-defined]

# Deprecated helper retained for backward compat; prefer config values


async def _ensure_llm_client() -> httpx.AsyncClient | None:
    global _LLM_CLIENT
    if not _LLM_BASE_URL:
        return None
    if _LLM_CLIENT is None:
        timeout = httpx.Timeout(connect=5.0, read=60.0, write=60.0, pool=60.0)
        _LLM_CLIENT = httpx.AsyncClient(base_url=_LLM_BASE_URL, timeout=timeout)
    return _LLM_CLIENT


@app.on_event("startup")  # type: ignore[misc]
async def _startup_event() -> None:
    """Initialize MCP manager, orchestrator, and test recorder on startup."""
    global _MCP_MANAGER, _ORCHESTRATOR, _TEST_RECORDER

    try:
        # Initialize MCP manager
        _MCP_MANAGER = MCPManager(_MCP_CONFIG_PATH)
        await _MCP_MANAGER.initialize()

        # Initialize orchestrator
        _ORCHESTRATOR = Orchestrator(_MCP_MANAGER, _cfg.llm_client, _cfg.tts_client)  # type: ignore[arg-type]
        await _ORCHESTRATOR.initialize()
        logger.info("orchestrator.initialized")

        # Initialize test recorder
        _TEST_RECORDER = TestRecorderManager(
            recordings_dir=_cfg.test_recorder.recordings_dir,  # type: ignore[attr-defined]
            max_file_size=_cfg.test_recorder.max_file_size_bytes,  # type: ignore[attr-defined]
        )
        logger.info("test_recorder.initialized")

    except Exception as exc:
        logger.error("orchestrator.startup_failed", error=str(exc))
        # Continue without MCP integration for compatibility


@app.on_event("shutdown")  # type: ignore[misc]
async def _shutdown_event() -> None:
    """Shutdown MCP manager, orchestrator, and test recorder."""
    global _LLM_CLIENT, _MCP_MANAGER, _ORCHESTRATOR, _TEST_RECORDER

    if _LLM_CLIENT is not None:
        await _LLM_CLIENT.aclose()
        _LLM_CLIENT = None

    if _ORCHESTRATOR is not None:
        await _ORCHESTRATOR.shutdown()
        _ORCHESTRATOR = None

    if _MCP_MANAGER is not None:
        await _MCP_MANAGER.shutdown()
        _MCP_MANAGER = None

    if _TEST_RECORDER is not None:
        _TEST_RECORDER = None


class TranscriptRequest(BaseModel):
    guild_id: str
    channel_id: str
    user_id: str
    transcript: str
    correlation_id: str | None = None

    @field_validator("correlation_id")  # type: ignore[misc]
    @classmethod
    def validate_correlation_id_field(cls, v: str | None) -> str | None:
        if v is not None:
            from services.common.correlation import validate_correlation_id

            is_valid, error_msg = validate_correlation_id(v)
            if not is_valid:
                raise ValueError(error_msg)
        return v


@app.post("/mcp/transcript")  # type: ignore[misc]
async def handle_transcript(request: TranscriptRequest) -> dict[str, Any]:
    """Handle transcript from Discord service."""
    from services.common.logging import correlation_context

    with correlation_context(request.correlation_id) as request_logger:
        request_logger.info(
            "orchestrator.transcript_received",
            guild_id=request.guild_id,
            channel_id=request.channel_id,
            user_id=request.user_id,
            correlation_id=request.correlation_id,
            text_length=len(request.transcript or ""),
        )
        if not _ORCHESTRATOR:
            return {"error": "Orchestrator not initialized"}

        try:
            # Process the transcript through the orchestrator
            result = await _ORCHESTRATOR.process_transcript(
                guild_id=request.guild_id,
                channel_id=request.channel_id,
                user_id=request.user_id,
                transcript=request.transcript,
                correlation_id=request.correlation_id,
            )

            request_logger.info(
                "orchestrator.transcript_processed",
                guild_id=request.guild_id,
                channel_id=request.channel_id,
                user_id=request.user_id,
                transcript=request.transcript,
                correlation_id=request.correlation_id,
            )

            return result

        except Exception as exc:
            request_logger.error(
                "orchestrator.transcript_processing_failed",
                error=str(exc),
                guild_id=request.guild_id,
                channel_id=request.channel_id,
                user_id=request.user_id,
                transcript=request.transcript,
                correlation_id=request.correlation_id,
            )
            return {"error": str(exc)}


@app.get("/mcp/tools")  # type: ignore[misc]
async def list_mcp_tools() -> dict[str, Any]:
    """List available MCP tools."""
    if not _MCP_MANAGER:
        return {"error": "MCP manager not initialized"}

    try:
        tools = await _MCP_MANAGER.list_all_tools()
        return {"tools": tools}
    except Exception as exc:
        return {"error": str(exc)}


@app.get("/mcp/connections")  # type: ignore[misc]
async def list_mcp_connections() -> dict[str, Any]:
    """List MCP connection status."""
    if not _MCP_MANAGER:
        return {"error": "MCP manager not initialized"}

    return {"connections": _MCP_MANAGER.get_client_status()}


@app.get("/health/live")  # type: ignore[misc]
async def health_live() -> dict[str, str]:
    """Liveness check - is process running."""
    return {"status": "alive", "service": "orchestrator"}


@app.get("/health/ready")  # type: ignore[misc]
async def health_ready() -> dict[str, Any]:
    """Readiness check - can serve requests."""
    if _ORCHESTRATOR is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail="Orchestrator not initialized")

    mcp_status = {}
    if _MCP_MANAGER:
        mcp_status = _MCP_MANAGER.get_client_status()

    health_status = await _health_manager.get_health_status()
    return {
        "status": "ready",
        "service": "orchestrator",
        "llm_available": _LLM_BASE_URL is not None,
        "tts_available": _TTS_BASE_URL is not None,
        "mcp_clients": mcp_status,
        "orchestrator_active": _ORCHESTRATOR is not None,
        "health_details": health_status.details,
    }


@app.get("/test-recorder")  # type: ignore[misc]
async def test_recorder_ui():
    """Serve the test recorder web interface."""
    return FileResponse("static/test-recorder.html")


# =============================================================================
# TEST RECORDER ENDPOINTS
# =============================================================================


class PhraseRequest(BaseModel):
    text: str
    category: str

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        valid_categories = ["wake", "core", "edge", "noise"]
        if v not in valid_categories:
            raise ValueError(f"Category must be one of: {valid_categories}")
        return v


class AudioUploadRequest(BaseModel):
    phrase_id: str
    audio_data: str  # Base64 encoded audio data
    audio_format: str = "webm"


@app.post("/test-recorder/phrases")  # type: ignore[misc]
async def add_phrase(request: PhraseRequest) -> dict[str, Any]:
    """Add a new test phrase."""
    if not _TEST_RECORDER:
        return {"error": "Test recorder not initialized"}

    try:
        phrase = _TEST_RECORDER.add_phrase(request.text, request.category)
        return {"success": True, "phrase": phrase}
    except Exception as exc:
        logger.error("test_recorder.add_phrase_failed", error=str(exc))
        return {"error": str(exc)}


@app.get("/test-recorder/phrases")  # type: ignore[misc]
async def list_phrases(category: str | None = None) -> dict[str, Any]:
    """List all test phrases, optionally filtered by category."""
    if not _TEST_RECORDER:
        return {"error": "Test recorder not initialized"}

    try:
        phrases = _TEST_RECORDER.list_phrases(category)
        return {"success": True, "phrases": phrases}
    except Exception as exc:
        logger.error("test_recorder.list_phrases_failed", error=str(exc))
        return {"error": str(exc)}


@app.get("/test-recorder/phrases/{phrase_id}")  # type: ignore[misc]
async def get_phrase(phrase_id: str) -> dict[str, Any]:
    """Get a specific test phrase by ID."""
    if not _TEST_RECORDER:
        return {"error": "Test recorder not initialized"}

    try:
        phrase = _TEST_RECORDER.get_phrase(phrase_id)
        if not phrase:
            return {"error": "Phrase not found"}
        return {"success": True, "phrase": phrase}
    except Exception as exc:
        logger.error(
            "test_recorder.get_phrase_failed", phrase_id=phrase_id, error=str(exc)
        )
        return {"error": str(exc)}


@app.post("/test-recorder/phrases/{phrase_id}/audio")  # type: ignore[misc]
async def upload_audio(phrase_id: str, request: AudioUploadRequest) -> dict[str, Any]:
    """Upload audio data for a test phrase."""
    if not _TEST_RECORDER:
        return {"error": "Test recorder not initialized"}

    try:
        import base64

        audio_data = base64.b64decode(request.audio_data)
        result = _TEST_RECORDER.save_audio(phrase_id, audio_data, request.audio_format)
        return {"success": True, "result": result}
    except Exception as exc:
        logger.error(
            "test_recorder.upload_audio_failed", phrase_id=phrase_id, error=str(exc)
        )
        return {"error": str(exc)}


@app.post("/test-recorder/phrases/{phrase_id}/convert")  # type: ignore[misc]
async def convert_audio(phrase_id: str, sample_rate: int = 48000) -> dict[str, Any]:
    """Convert phrase audio to WAV format."""
    if not _TEST_RECORDER:
        return {"error": "Test recorder not initialized"}

    try:
        result = _TEST_RECORDER.convert_to_wav(phrase_id, sample_rate)
        return {"success": True, "result": result}
    except Exception as exc:
        logger.error(
            "test_recorder.convert_audio_failed", phrase_id=phrase_id, error=str(exc)
        )
        return {"error": str(exc)}


@app.get("/test-recorder/phrases/{phrase_id}/audio")  # type: ignore[misc]
async def get_audio_file(phrase_id: str, converted: bool = False):
    """Get audio file for a test phrase."""
    if not _TEST_RECORDER:
        return {"error": "Test recorder not initialized"}

    try:
        from fastapi.responses import FileResponse

        audio_file = _TEST_RECORDER.get_audio_file(phrase_id, converted)
        if not audio_file:
            return {"error": "Audio file not found"}

        return FileResponse(
            path=str(audio_file),
            media_type="audio/wav" if converted else "audio/webm",
            filename=audio_file.name,
        )
    except Exception as exc:
        logger.error(
            "test_recorder.get_audio_failed", phrase_id=phrase_id, error=str(exc)
        )
        return {"error": str(exc)}


@app.delete("/test-recorder/phrases/{phrase_id}")  # type: ignore[misc]
async def delete_phrase(phrase_id: str) -> dict[str, Any]:
    """Delete a test phrase and its audio files."""
    if not _TEST_RECORDER:
        return {"error": "Test recorder not initialized"}

    try:
        success = _TEST_RECORDER.delete_phrase(phrase_id)
        if not success:
            return {"error": "Phrase not found"}
        return {"success": True}
    except Exception as exc:
        logger.error(
            "test_recorder.delete_phrase_failed", phrase_id=phrase_id, error=str(exc)
        )
        return {"error": str(exc)}


@app.get("/test-recorder/metadata")  # type: ignore[misc]
async def export_metadata() -> dict[str, Any]:
    """Export all recordings metadata."""
    if not _TEST_RECORDER:
        return {"error": "Test recorder not initialized"}

    try:
        metadata = _TEST_RECORDER.export_metadata()
        return {"success": True, "metadata": metadata}
    except Exception as exc:
        logger.error("test_recorder.export_metadata_failed", error=str(exc))
        return {"error": str(exc)}


@app.get("/test-recorder/stats")  # type: ignore[misc]
async def get_stats() -> dict[str, Any]:
    """Get statistics about the recordings."""
    if not _TEST_RECORDER:
        return {"error": "Test recorder not initialized"}

    try:
        stats = _TEST_RECORDER.get_stats()
        return {"success": True, "stats": stats}
    except Exception as exc:
        logger.error("test_recorder.get_stats_failed", error=str(exc))
        return {"error": str(exc)}


@app.delete("/test-recorder/phrases")  # type: ignore[misc]
async def clear_all_phrases() -> dict[str, Any]:
    """Clear all test phrases and their audio files."""
    if not _TEST_RECORDER:
        return {"error": "Test recorder not initialized"}

    try:
        count = _TEST_RECORDER.clear_all()
        return {"success": True, "cleared_count": count}
    except Exception as exc:
        logger.error("test_recorder.clear_all_failed", error=str(exc))
        return {"error": str(exc)}


# Add Prometheus metrics endpoint if available
if PROMETHEUS_AVAILABLE:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=_cfg.port.port)  # type: ignore[attr-defined]
