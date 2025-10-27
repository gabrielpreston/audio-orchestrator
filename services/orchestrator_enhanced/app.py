"""
Enhanced Orchestrator Service with LangChain Integration

This service replaces the existing orchestrator with LangChain-based orchestration,
providing more sophisticated agent management and tool integration.
"""

import os
import time
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from services.common.audio_metrics import create_http_metrics, create_llm_metrics
from services.common.config.loader import load_config_from_env
from services.common.config.presets import OrchestratorConfig
from services.common.health import HealthManager, HealthStatus
from services.common.structured_logging import configure_logging, get_logger
from services.common.tracing import setup_service_observability

# LangChain imports
from .langchain_integration import (
    LANGCHAIN_AVAILABLE,
    create_langchain_executor,
    process_with_langchain,
)


# Import AgentExecutor for type hints
try:
    from langchain.agents import AgentExecutor
except ImportError:
    AgentExecutor = Any

# Configure logging
configure_logging("info", json_logs=True, service_name="orchestrator_enhanced")
logger = get_logger(__name__, service_name="orchestrator_enhanced")
app = FastAPI(title="Enhanced Orchestrator", version="1.0.0")

# Health manager and observability
_health_manager = HealthManager("orchestrator-enhanced")
_observability_manager = None
_llm_metrics = {}
_http_metrics = {}

# Configuration
_cfg: OrchestratorConfig | None = None
_langchain_executor: AgentExecutor | None = None

# Prompt versioning
PROMPT_VERSION = "v1.0"


class TranscriptRequest(BaseModel):
    transcript: str = Field(..., description="The transcript to process")
    session_id: str = Field(..., description="Session identifier")
    correlation_id: str | None = Field(None, description="Correlation ID for tracking")


class TranscriptResponse(BaseModel):
    response: str = Field(..., description="The generated response")
    session_id: str = Field(..., description="Session identifier")
    correlation_id: str | None = Field(None, description="Correlation ID for tracking")
    engine: str = Field(default="langchain", description="Processing engine used")


@app.on_event("startup")  # type: ignore[misc]
async def startup() -> None:
    """Initialize the enhanced orchestrator service."""
    global \
        _cfg, \
        _langchain_executor, \
        _observability_manager, \
        _llm_metrics, \
        _http_metrics

    try:
        # Setup observability (tracing + metrics)
        _observability_manager = setup_service_observability(
            "orchestrator-enhanced", "1.0.0"
        )
        _observability_manager.instrument_fastapi(app)

        # Create service-specific metrics
        _llm_metrics = create_llm_metrics(_observability_manager)
        _http_metrics = create_http_metrics(_observability_manager)

        # Set observability manager in health manager
        _health_manager.set_observability_manager(_observability_manager)

        # Load configuration with fallback
        try:
            _cfg = load_config_from_env(OrchestratorConfig)
        except Exception as exc:
            logger.warning("orchestrator_enhanced.config_load_failed", error=str(exc))
            _cfg = None  # Continue without config

        # Initialize LangChain executor with fallback
        try:
            _langchain_executor = create_langchain_executor()
        except Exception as exc:
            logger.warning(
                "orchestrator_enhanced.langchain_init_failed", error=str(exc)
            )
            _langchain_executor = None  # Continue without LangChain

        # Register dependencies with null checks
        _health_manager.register_dependency("config", lambda: _cfg is not None)
        _health_manager.register_dependency(
            "langchain", lambda: _langchain_executor is not None
        )

        # Always mark startup complete (graceful degradation)
        _health_manager.mark_startup_complete()

        logger.info(
            "orchestrator_enhanced.startup_complete",
            langchain_available=LANGCHAIN_AVAILABLE,
            executor_ready=_langchain_executor is not None,
        )

    except Exception as exc:
        logger.error("orchestrator_enhanced.startup_failed", error=str(exc))
        # Continue without crashing - service will report not_ready


@app.on_event("shutdown")  # type: ignore[misc]
async def shutdown() -> None:
    """Cleanup on shutdown."""
    logger.info("orchestrator_enhanced.shutdown")


@app.get("/health/live")  # type: ignore[misc]
async def health_live() -> dict[str, str]:
    """Liveness check."""
    return {"status": "alive", "service": "orchestrator-enhanced"}


@app.get("/health/ready")  # type: ignore[misc]
async def health_ready() -> dict[str, Any]:
    """Readiness check with component status."""
    if _cfg is None:
        raise HTTPException(status_code=503, detail="Configuration not loaded")

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
        "service": "orchestrator-enhanced",
        "components": {
            "config_loaded": _cfg is not None,
            "langchain_available": LANGCHAIN_AVAILABLE,
            "executor_ready": _langchain_executor is not None,
            "startup_complete": _health_manager._startup_complete,
        },
        "dependencies": health_status.details.get("dependencies", {}),
        "health_details": health_status.details,
    }


@app.post("/mcp/transcript")  # type: ignore[misc]
async def handle_transcript(request: TranscriptRequest) -> TranscriptResponse:
    """Process transcript using LangChain orchestration with guardrails."""
    start_time = time.time()

    try:
        # Input validation with guardrails
        guardrails_url = os.getenv("GUARDRAILS_URL", "http://guardrails:9300")
        try:
            import httpx

            async with httpx.AsyncClient() as client:
                # Validate input
                validation_response = await client.post(
                    f"{guardrails_url}/validate/input",
                    json={"text": request.transcript, "validation_type": "input"},
                    timeout=5.0,
                )
                validation_data = validation_response.json()

                if not validation_data.get("safe", True):
                    logger.warning(
                        "orchestrator_enhanced.input_blocked",
                        reason=validation_data.get("reason"),
                        transcript=request.transcript[:100],
                    )

                    # Record blocked request metrics
                    if _llm_metrics and "llm_requests" in _llm_metrics:
                        _llm_metrics["llm_requests"].add(
                            1, attributes={"model": "orchestrator", "status": "blocked"}
                        )

                    return TranscriptResponse(
                        response="I'm sorry, but I can't process that request.",
                        session_id=request.session_id,
                        correlation_id=request.correlation_id,
                        engine="guardrails_blocked",
                    )

                # Use sanitized input
                sanitized_transcript = validation_data.get(
                    "sanitized", request.transcript
                )

        except Exception as e:
            logger.warning("orchestrator_enhanced.guardrails_unavailable", error=str(e))
            sanitized_transcript = request.transcript

        # Process with LangChain
        response = await process_with_langchain(
            sanitized_transcript, request.session_id, _langchain_executor
        )

        # Output validation with guardrails
        try:
            async with httpx.AsyncClient() as client:
                # Validate output
                output_validation = await client.post(
                    f"{guardrails_url}/validate/output",
                    json={"text": response, "validation_type": "output"},
                    timeout=5.0,
                )
                output_data = output_validation.json()

                if not output_data.get("safe", True):
                    logger.warning(
                        "orchestrator_enhanced.output_blocked",
                        reason=output_data.get("reason"),
                    )
                    response = "I'm sorry, but I can't provide that response."
                else:
                    # Use filtered output
                    response = output_data.get("filtered", response)

        except Exception as e:
            logger.warning(
                "orchestrator_enhanced.output_validation_failed", error=str(e)
            )

        # Record metrics
        processing_time = time.time() - start_time
        if _llm_metrics:
            if "llm_requests" in _llm_metrics:
                _llm_metrics["llm_requests"].add(
                    1, attributes={"model": "orchestrator", "status": "success"}
                )
            if "llm_latency" in _llm_metrics:
                _llm_metrics["llm_latency"].record(
                    processing_time, attributes={"model": "orchestrator"}
                )

        return TranscriptResponse(
            response=response,
            session_id=request.session_id,
            correlation_id=request.correlation_id,
            engine="langchain" if _langchain_executor else "fallback",
        )

    except Exception as e:
        # Record error metrics
        processing_time = time.time() - start_time
        if _llm_metrics and "llm_requests" in _llm_metrics:
            _llm_metrics["llm_requests"].add(
                1, attributes={"model": "orchestrator", "status": "error"}
            )
        if _llm_metrics and "llm_latency" in _llm_metrics:
            _llm_metrics["llm_latency"].record(
                processing_time, attributes={"model": "orchestrator", "status": "error"}
            )

        logger.error(
            "orchestrator_enhanced.transcript_processing_failed",
            error=str(e),
            transcript=request.transcript[:100],
        )
        raise HTTPException(
            status_code=500, detail=f"Processing failed: {str(e)}"
        ) from e


@app.get("/mcp/tools")  # type: ignore[misc]
async def list_tools() -> dict[str, list[dict[str, str]]]:
    """List available MCP tools."""
    tools = [
        {
            "name": "SendDiscordMessage",
            "description": "Send a message to Discord channel",
            "type": "action",
        },
        {
            "name": "SearchWeb",
            "description": "Search the web for information",
            "type": "action",
        },
    ]

    return {"tools": tools}


@app.get("/mcp/connections")  # type: ignore[misc]
async def list_connections() -> dict[str, Any]:
    """List MCP connections."""
    return {
        "connections": [
            {"name": "discord", "status": "connected", "type": "mcp"},
            {"name": "web_search", "status": "available", "type": "tool"},
        ]
    }
