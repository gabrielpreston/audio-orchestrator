from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import FastAPI
from pydantic import BaseModel, field_validator

from services.common.health import HealthManager
from services.common.logging import configure_logging, get_logger

from .mcp_manager import MCPManager
from .orchestrator import Orchestrator

# Prometheus metrics
try:
    from prometheus_client import make_asgi_app

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

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
_health_manager = HealthManager("orchestrator")

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


@app.on_event("startup")  # type: ignore[misc]
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


@app.on_event("shutdown")  # type: ignore[misc]
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


# Add Prometheus metrics endpoint if available
if PROMETHEUS_AVAILABLE:
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
