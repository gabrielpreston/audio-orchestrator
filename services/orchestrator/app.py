from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from services.common.logging import configure_logging, get_logger

from .mcp_manager import MCPManager
from .orchestrator import Orchestrator

app = FastAPI(title="Voice Assistant Orchestrator")

configure_logging(
    os.getenv("LOG_LEVEL", "INFO"),
    json_logs=os.getenv("LOG_JSON", "true").lower() in {"1", "true", "yes", "on"},
    service_name="orchestrator",
)
logger = get_logger(__name__, service_name="orchestrator")

_ORCHESTRATOR: Orchestrator | None = None
_MCP_MANAGER: MCPManager | None = None
_LLM_CLIENT: httpx.AsyncClient | None = None

_LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://llm:8000")
_LLM_AUTH_TOKEN = os.getenv("LLM_AUTH_TOKEN")
_TTS_BASE_URL = os.getenv("TTS_BASE_URL")
_TTS_AUTH_TOKEN = os.getenv("TTS_AUTH_TOKEN")
_MCP_CONFIG_PATH = os.getenv("MCP_CONFIG_PATH", "./mcp.json")


def _env_bool(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes", "on"}


async def _ensure_llm_client() -> httpx.AsyncClient | None:
    global _LLM_CLIENT
    if not _LLM_BASE_URL:
        return None
    if _LLM_CLIENT is None:
        timeout = httpx.Timeout(connect=5.0, read=60.0, write=60.0, pool=60.0)
        _LLM_CLIENT = httpx.AsyncClient(base_url=_LLM_BASE_URL, timeout=timeout)
    return _LLM_CLIENT


@app.on_event("startup")
async def _startup_event() -> None:
    """Initialize MCP manager and orchestrator on startup."""
    global _MCP_MANAGER, _ORCHESTRATOR

    try:
        # Initialize MCP manager
        _MCP_MANAGER = MCPManager(_MCP_CONFIG_PATH)
        await _MCP_MANAGER.initialize()

        # Initialize orchestrator
        _ORCHESTRATOR = Orchestrator(_MCP_MANAGER, _LLM_BASE_URL, _TTS_BASE_URL)
        await _ORCHESTRATOR.initialize()
        logger.info("orchestrator.initialized")

    except Exception as exc:
        logger.error("orchestrator.startup_failed", error=str(exc))
        # Continue without MCP integration for compatibility


@app.on_event("shutdown")
async def _shutdown_event() -> None:
    """Shutdown MCP manager and orchestrator."""
    global _LLM_CLIENT, _MCP_MANAGER, _ORCHESTRATOR

    if _LLM_CLIENT is not None:
        await _LLM_CLIENT.aclose()
        _LLM_CLIENT = None

    if _ORCHESTRATOR is not None:
        await _ORCHESTRATOR.shutdown()
        _ORCHESTRATOR = None

    if _MCP_MANAGER is not None:
        await _MCP_MANAGER.shutdown()
        _MCP_MANAGER = None


class TranscriptRequest(BaseModel):
    guild_id: str
    channel_id: str
    user_id: str
    transcript: str
    correlation_id: str | None = None


@app.post("/mcp/transcript")
async def handle_transcript(request: TranscriptRequest) -> dict[str, Any]:
    """Handle transcript from Discord service."""
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

        logger.info(
            "orchestrator.transcript_processed",
            guild_id=request.guild_id,
            channel_id=request.channel_id,
            user_id=request.user_id,
            transcript=request.transcript,
            correlation_id=request.correlation_id,
        )

        return result

    except Exception as exc:
        logger.error(
            "orchestrator.transcript_processing_failed",
            error=str(exc),
            guild_id=request.guild_id,
            channel_id=request.channel_id,
            user_id=request.user_id,
        )
        return {"error": str(exc)}


@app.get("/mcp/tools")
async def list_mcp_tools() -> dict[str, Any]:
    """List available MCP tools."""
    if not _MCP_MANAGER:
        return {"error": "MCP manager not initialized"}

    try:
        tools = await _MCP_MANAGER.list_all_tools()
        return {"tools": tools}
    except Exception as exc:
        return {"error": str(exc)}


@app.get("/mcp/connections")
async def list_mcp_connections() -> dict[str, Any]:
    """List MCP connection status."""
    if not _MCP_MANAGER:
        return {"error": "MCP manager not initialized"}

    return {"connections": _MCP_MANAGER.get_client_status()}


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint with MCP status."""
    mcp_status = {}
    if _MCP_MANAGER:
        mcp_status = _MCP_MANAGER.get_client_status()

    return {
        "status": "healthy",
        "llm_available": _LLM_BASE_URL is not None,
        "tts_available": _TTS_BASE_URL is not None,
        "mcp_clients": mcp_status,
        "orchestrator_active": _ORCHESTRATOR is not None,
    }


@app.get("/audio/{filename}")
async def serve_audio(filename: str) -> FileResponse:
    """Serve audio files for Discord playback."""
    try:
        import glob
        from pathlib import Path

        # Search for audio file in flattened correlation-based directory structure
        debug_dir = Path("/app/debug")
        audio_pattern = str(debug_dir / "*" / filename)
        matching_files = glob.glob(audio_pattern)

        if not matching_files:
            raise HTTPException(status_code=404, detail="Audio file not found")

        # Use the first matching file
        file_path = Path(matching_files[0])

        return FileResponse(
            path=str(file_path), media_type="audio/wav", filename=filename
        )
    except Exception as exc:
        logger.error(
            "orchestrator.audio_serve_failed", error=str(exc), filename=filename
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
