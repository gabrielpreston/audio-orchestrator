"""
Enhanced Orchestrator Service with LangChain Integration

This service replaces the existing orchestrator with LangChain-based orchestration,
providing more sophisticated agent management and tool integration.
"""

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from services.common.config.loader import load_config_from_env
from services.common.config.presets import OrchestratorConfig
from services.common.health import HealthManager, HealthStatus
from services.common.structured_logging import get_logger

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

logger = get_logger(__name__)
app = FastAPI(title="Enhanced Orchestrator", version="1.0.0")

# Health manager
_health_manager = HealthManager("orchestrator-enhanced")

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
    global _cfg, _langchain_executor

    try:
        # Load configuration
        _cfg = load_config_from_env(OrchestratorConfig)

        # Initialize LangChain executor
        _langchain_executor = create_langchain_executor()

        # Register dependencies
        _health_manager.register_dependency(
            "langchain", lambda: _langchain_executor is not None
        )
        _health_manager.register_dependency("config", lambda: _cfg is not None)

        # Mark startup complete
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

        return TranscriptResponse(
            response=response,
            session_id=request.session_id,
            correlation_id=request.correlation_id,
            engine="langchain" if _langchain_executor else "fallback",
        )

    except Exception as e:
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
