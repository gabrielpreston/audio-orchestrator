"""
Enhanced Orchestrator Service with LangChain Integration

This service replaces the existing orchestrator with LangChain-based orchestration,
providing more sophisticated agent management and tool integration.
"""

import time
from typing import Any

from fastapi import HTTPException

from services.common.app_factory import create_service_app
from services.common.config import (
    LoggingConfig,
    get_service_preset,
)
from services.common.config.loader import get_env_with_default, load_config_from_env
from services.common.config.presets import OrchestratorConfig
from services.common.health import HealthManager
from services.common.health_endpoints import HealthEndpoints
from services.common.http_client_factory import create_resilient_client
from services.common.resilient_http import ResilientHTTPClient, ServiceUnavailableError
from services.common.structured_logging import configure_logging, get_logger
from services.common.tracing import get_observability_manager

# LangChain imports
from .langchain_integration import (
    LANGCHAIN_AVAILABLE,
    create_langchain_executor,
    process_with_langchain,
)

# Import new REST API models
from .models import (
    CapabilitiesResponse,
    CapabilityInfo,
    ConnectionInfo,
    StatusResponse,
    TranscriptProcessRequest,
    TranscriptProcessResponse,
)

# TTS client
from .tts_client import TTSClient


# Import AgentExecutor for type hints
try:
    from langchain.agents import AgentExecutor
except ImportError:
    AgentExecutor = Any

# Load configuration using standard config classes
_config_preset = get_service_preset("orchestrator")
_logging_config = LoggingConfig(**_config_preset["logging"])

# Configure logging using config class
configure_logging(
    _logging_config.level,
    json_logs=_logging_config.json_logs,
    service_name="orchestrator",
)
logger = get_logger(__name__, service_name="orchestrator")

# Health manager and observability
_health_manager = HealthManager("orchestrator")
_observability_manager = None
_llm_metrics = {}
_http_metrics = {}

# Configuration
_cfg: OrchestratorConfig | None = None
_langchain_executor: AgentExecutor | None = None
_tts_client: TTSClient | None = None

# Resilient HTTP clients for health checks
_llm_health_client: ResilientHTTPClient | None = None
_tts_health_client: ResilientHTTPClient | None = None
_guardrails_health_client: ResilientHTTPClient | None = None

# Prompt versioning
PROMPT_VERSION = "v1.0"


async def _startup() -> None:
    """Service-specific startup logic."""
    global \
        _cfg, \
        _langchain_executor, \
        _tts_client, \
        _observability_manager, \
        _llm_metrics, \
        _http_metrics

    try:
        # Get observability manager (factory already setup observability)
        _observability_manager = get_observability_manager("orchestrator")

        # Create service-specific metrics
        from services.common.audio_metrics import (
            create_llm_metrics,
            create_http_metrics,
            create_system_metrics,
        )

        _llm_metrics = create_llm_metrics(_observability_manager)
        _http_metrics = create_http_metrics(_observability_manager)
        _system_metrics = create_system_metrics(_observability_manager)

        # Set observability manager in health manager
        _health_manager.set_observability_manager(_observability_manager)

        # Load configuration with fallback
        try:
            _cfg = load_config_from_env(OrchestratorConfig)
        except Exception as exc:
            logger.warning("orchestrator.config_load_failed", error=str(exc))
            _cfg = None  # Continue without config

        # Initialize LangChain executor with fallback
        try:
            _langchain_executor = create_langchain_executor()
        except Exception as exc:
            logger.warning("orchestrator.langchain_init_failed", error=str(exc))
            _langchain_executor = None  # Continue without LangChain

        # Initialize TTS client
        try:
            tts_url = get_env_with_default("TTS_BASE_URL", "http://bark:7100", str)
            _tts_client = TTSClient(base_url=tts_url)
            logger.info("orchestrator.tts_client_initialized", tts_url=tts_url)
        except Exception as exc:
            logger.warning("orchestrator.tts_client_init_failed", error=str(exc))
            _tts_client = None  # Continue without TTS (graceful degradation)

        # Initialize resilient HTTP clients for health checks
        # For dependency health checks, disable grace period to get accurate readiness
        global _llm_health_client, _tts_health_client, _guardrails_health_client
        try:
            llm_url = get_env_with_default("LLM_BASE_URL", "http://flan:8100", str)
            # Create client with grace period disabled for accurate dependency checking
            from services.common.circuit_breaker import CircuitBreakerConfig

            _llm_health_client = ResilientHTTPClient(
                service_name="llm",
                base_url=llm_url,
                circuit_config=CircuitBreakerConfig(),
                health_check_startup_grace_seconds=0.0,  # No grace period for dependency checks
            )
        except Exception as exc:
            logger.warning("orchestrator.llm_health_client_init_failed", error=str(exc))
            _llm_health_client = None

        try:
            tts_url = get_env_with_default("TTS_BASE_URL", "http://bark:7100", str)
            _tts_health_client = ResilientHTTPClient(
                service_name="tts",
                base_url=tts_url,
                circuit_config=CircuitBreakerConfig(),
                health_check_startup_grace_seconds=0.0,  # No grace period for dependency checks
            )
        except Exception as exc:
            logger.warning("orchestrator.tts_health_client_init_failed", error=str(exc))
            _tts_health_client = None

        try:
            guardrails_url = get_env_with_default(
                "GUARDRAILS_BASE_URL", "http://guardrails:9300", str
            )
            _guardrails_health_client = ResilientHTTPClient(
                service_name="guardrails",
                base_url=guardrails_url,
                circuit_config=CircuitBreakerConfig(),
                health_check_startup_grace_seconds=0.0,  # No grace period for dependency checks
            )
        except Exception as exc:
            logger.warning(
                "orchestrator.guardrails_health_client_init_failed", error=str(exc)
            )
            _guardrails_health_client = None

        # Register dependencies - check actual service readiness via HTTP
        _health_manager.register_dependency("config", lambda: _cfg is not None)
        _health_manager.register_dependency(
            "langchain", lambda: _langchain_executor is not None
        )
        _health_manager.register_dependency("llm", _check_llm_health)
        _health_manager.register_dependency("tts", _check_tts_health)
        _health_manager.register_dependency("guardrails", _check_guardrails_health)

        # Always mark startup complete (graceful degradation)
        _health_manager.mark_startup_complete()

        logger.info(
            "orchestrator.startup_complete",
            langchain_available=LANGCHAIN_AVAILABLE,
            executor_ready=_langchain_executor is not None,
            tts_client_ready=_tts_client is not None,
        )

    except Exception as exc:
        logger.error("orchestrator.startup_failed", error=str(exc))
        # Continue without crashing - service will report not_ready


async def _shutdown() -> None:
    """Service-specific shutdown logic."""
    global _tts_client
    if _tts_client:
        await _tts_client.close()
        _tts_client = None
    logger.info("orchestrator.shutdown")


# Create app using factory pattern
app = create_service_app(
    "orchestrator",
    "1.0.0",
    title="Enhanced Orchestrator",
    startup_callback=_startup,
    shutdown_callback=_shutdown,
)


# Initialize health endpoints
health_endpoints = HealthEndpoints(
    service_name="orchestrator",
    health_manager=_health_manager,
    custom_components={
        "config_loaded": lambda: _cfg is not None,
        "langchain_available": lambda: LANGCHAIN_AVAILABLE,
        "executor_ready": lambda: _langchain_executor is not None,
        "tts_client_ready": lambda: _tts_client is not None,
    },
)

# Include the health endpoints router
app.include_router(health_endpoints.get_router())


@app.post("/api/v1/transcripts", response_model=TranscriptProcessResponse)  # type: ignore[misc]
async def process_transcript(
    request: TranscriptProcessRequest,
) -> TranscriptProcessResponse:
    """Process transcript using LangChain orchestration with guardrails."""
    start_time = time.time()

    try:
        # Input validation with guardrails
        guardrails_url = get_env_with_default(
            "GUARDRAILS_BASE_URL", "http://guardrails:9300", str
        )
        try:
            guardrails_client = create_resilient_client(
                service_name="guardrails",
                base_url=guardrails_url,
                env_prefix="GUARDRAILS",
            )

            try:
                # Validate input
                validation_response = await guardrails_client.post_with_retry(
                    "/validate/input",
                    json={"text": request.transcript, "validation_type": "input"},
                    timeout=5.0,
                )
                validation_data = validation_response.json()

                if not validation_data.get("safe", True):
                    logger.warning(
                        "orchestrator.input_blocked",
                        reason=validation_data.get("reason"),
                        transcript=request.transcript[:100],
                    )

                    # Record blocked request metrics
                    if _llm_metrics and "llm_requests" in _llm_metrics:
                        _llm_metrics["llm_requests"].add(
                            1, attributes={"model": "orchestrator", "status": "blocked"}
                        )

                    await guardrails_client.close()
                    return TranscriptProcessResponse(
                        success=False,
                        response_text="I'm sorry, but I can't process that request.",
                        correlation_id=request.correlation_id,
                        error="Input blocked by guardrails",
                        audio_data=None,
                        audio_format=None,
                        tool_calls=None,
                    )

                # Use sanitized input
                sanitized_transcript = validation_data.get(
                    "sanitized", request.transcript
                )
                await guardrails_client.close()

            except ServiceUnavailableError as e:
                await guardrails_client.close()
                logger.warning("orchestrator.guardrails_unavailable", error=str(e))
                sanitized_transcript = request.transcript

        except Exception as e:
            logger.warning("orchestrator.guardrails_unavailable", error=str(e))
            sanitized_transcript = request.transcript

        # Process with LangChain
        try:
            response = await process_with_langchain(
                sanitized_transcript, request.user_id, _langchain_executor
            )
            # Validate response is not empty or error message
            if not response or response.strip() == "":
                logger.warning(
                    "orchestrator.empty_response",
                    transcript=sanitized_transcript[:100],
                    correlation_id=request.correlation_id,
                )
                response = f"I received your message: {sanitized_transcript[:100]}. Let me help you with that."
        except Exception as langchain_exc:
            logger.error(
                "orchestrator.langchain_failed",
                error=str(langchain_exc),
                error_type=type(langchain_exc).__name__,
                transcript=sanitized_transcript[:100],
                correlation_id=request.correlation_id,
            )
            # Fallback response
            response = f"I understand you asked: {sanitized_transcript[:100]}. I'm here to help."

        # Output validation with guardrails
        try:
            guardrails_client = create_resilient_client(
                service_name="guardrails",
                base_url=guardrails_url,
                env_prefix="GUARDRAILS",
            )

            try:
                # Validate output (increased timeout for toxicity detection on longer responses)
                output_validation = await guardrails_client.post_with_retry(
                    "/validate/output",
                    json={"text": response, "validation_type": "output"},
                    timeout=30.0,  # Increased from 5.0 to handle longer validation times
                )
                output_data = output_validation.json()

                if not output_data.get("safe", True):
                    logger.warning(
                        "orchestrator.output_blocked",
                        reason=output_data.get("reason"),
                    )
                    response = "I'm sorry, but I can't provide that response."
                else:
                    # Use filtered output
                    response = output_data.get("filtered", response)

                await guardrails_client.close()

            except ServiceUnavailableError as e:
                await guardrails_client.close()
                logger.warning("orchestrator.output_validation_failed", error=str(e))

        except Exception as e:
            logger.warning("orchestrator.output_validation_failed", error=str(e))

        # Synthesize audio using TTS service if client is available and response is not empty
        audio_data: str | None = None
        audio_format: str | None = None

        if _tts_client and response and len(response.strip()) > 0:
            try:
                logger.debug(
                    "orchestrator.tts_synthesis_start",
                    text_length=len(response),
                    correlation_id=request.correlation_id,
                )

                # Call TTS service to synthesize audio
                audio_bytes = await _tts_client.synthesize(
                    text=response,
                    voice="v2/en_speaker_1",  # Default voice
                    speed=1.0,
                    correlation_id=request.correlation_id,
                )

                if audio_bytes:
                    # Encode audio as base64 for JSON transmission
                    import base64

                    audio_data = base64.b64encode(audio_bytes).decode("utf-8")
                    audio_format = "wav"  # Bark returns WAV format
                    logger.info(
                        "orchestrator.tts_synthesis_completed",
                        audio_size=len(audio_bytes),
                        correlation_id=request.correlation_id,
                    )
                else:
                    logger.warning(
                        "orchestrator.tts_synthesis_returned_empty",
                        correlation_id=request.correlation_id,
                    )

            except ServiceUnavailableError as e:
                logger.warning(
                    "orchestrator.tts_unavailable",
                    error=str(e),
                    correlation_id=request.correlation_id,
                )
                # Continue without audio - text response is still valid
            except Exception as e:
                logger.error(
                    "orchestrator.tts_synthesis_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    correlation_id=request.correlation_id,
                )
                # Continue without audio - text response is still valid

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
            audio_data=audio_data,
            audio_format=audio_format,
            tool_calls=None,
            correlation_id=request.correlation_id,
            error=None,
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
            "orchestrator.transcript_processing_failed",
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
        service="orchestrator",
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


async def _check_llm_health() -> bool:
    """Check if LLM service (FLAN) is ready via resilient HTTP client."""
    if _llm_health_client is None:
        return False
    try:
        return await _llm_health_client.check_health()
    except Exception as exc:
        logger.debug("health.llm_check_failed", error=str(exc))
        return False


async def _check_tts_health() -> bool:
    """Check if TTS service (Bark) is ready via resilient HTTP client."""
    if _tts_health_client is None:
        return False
    try:
        return await _tts_health_client.check_health()
    except Exception as exc:
        logger.debug("health.tts_check_failed", error=str(exc))
        return False


async def _check_guardrails_health() -> bool:
    """Check if Guardrails service is ready via resilient HTTP client."""
    if _guardrails_health_client is None:
        return False
    try:
        return await _guardrails_health_client.check_health()
    except Exception as exc:
        logger.debug("health.guardrails_check_failed", error=str(exc))
        return False


@app.get("/api/v1/status", response_model=StatusResponse)  # type: ignore[misc]
async def get_status() -> StatusResponse:
    """Get orchestrator service status and connections."""
    return StatusResponse(
        service="orchestrator",
        status="healthy",
        version="1.0.0",
        uptime=None,
        connections=[
            ConnectionInfo(
                service="discord",
                status="connected",
                url="http://discord:8001",
                last_heartbeat=None,
            ),
            ConnectionInfo(
                service="flan",
                status="connected",
                url="http://flan:8200",
                last_heartbeat=None,
            ),
            ConnectionInfo(
                service="guardrails",
                status="available",
                url="http://guardrails:9300",
                last_heartbeat=None,
            ),
        ],
    )
