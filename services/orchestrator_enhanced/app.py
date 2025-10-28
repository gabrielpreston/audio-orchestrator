"""
Enhanced Orchestrator Service with LangChain Integration

This service replaces the existing orchestrator with LangChain-based orchestration,
providing more sophisticated agent management and tool integration.
"""

import os
import time
from typing import Any

from fastapi import FastAPI, HTTPException

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

# Import new REST API models
from .models import (
    TranscriptProcessRequest,
    TranscriptProcessResponse,
    CapabilitiesResponse,
    CapabilityInfo,
    StatusResponse,
    ConnectionInfo,
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


@app.post("/api/v1/transcripts", response_model=TranscriptProcessResponse)  # type: ignore[misc]
async def process_transcript(
    request: TranscriptProcessRequest,
) -> TranscriptProcessResponse:
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

                    return TranscriptProcessResponse(
                        success=False,
                        response_text="I'm sorry, but I can't process that request.",
                        correlation_id=request.correlation_id,
                        error="Input blocked by guardrails",
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
            sanitized_transcript, request.user_id, _langchain_executor
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

        return TranscriptProcessResponse(
            success=True,
            response_text=response,
            correlation_id=request.correlation_id,
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


@app.get("/api/v1/capabilities", response_model=CapabilitiesResponse)  # type: ignore[misc]
async def list_capabilities() -> CapabilitiesResponse:
    """List available orchestrator capabilities."""
    return CapabilitiesResponse(
        service="orchestrator_enhanced",
        version="1.0.0",
        capabilities=[
            CapabilityInfo(
                name="transcript_processing",
                description="Process voice transcripts using LangChain orchestration",
                parameters={
                    "type": "object",
                    "properties": {
                        "transcript": {
                            "type": "string",
                            "description": "Transcript text to process",
                        },
                        "user_id": {"type": "string", "description": "User identifier"},
                        "channel_id": {
                            "type": "string",
                            "description": "Channel identifier",
                        },
                        "correlation_id": {
                            "type": "string",
                            "description": "Correlation ID for tracing",
                        },
                        "metadata": {
                            "type": "object",
                            "description": "Additional metadata",
                        },
                    },
                    "required": ["transcript", "user_id", "channel_id"],
                },
            ),
            CapabilityInfo(
                name="discord_message_sending",
                description="Send messages to Discord channels",
                parameters={
                    "type": "object",
                    "properties": {
                        "channel_id": {
                            "type": "string",
                            "description": "Discord channel ID",
                        },
                        "content": {"type": "string", "description": "Message content"},
                        "correlation_id": {
                            "type": "string",
                            "description": "Correlation ID for tracing",
                        },
                    },
                    "required": ["channel_id", "content"],
                },
            ),
        ],
    )


@app.get("/api/v1/status", response_model=StatusResponse)  # type: ignore[misc]
async def get_status() -> StatusResponse:
    """Get orchestrator service status and connections."""
    return StatusResponse(
        service="orchestrator_enhanced",
        status="healthy",
        version="1.0.0",
        connections=[
            ConnectionInfo(
                service="discord",
                status="connected",
                url="http://discord:8001",
            ),
            ConnectionInfo(
                service="llm_flan",
                status="connected",
                url="http://llm_flan:8200",
            ),
            ConnectionInfo(
                service="guardrails",
                status="available",
                url="http://guardrails:9300",
            ),
        ],
    )
