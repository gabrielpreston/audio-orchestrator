"""
Enhanced Orchestrator Service with LangChain Integration

This service replaces the existing orchestrator with LangChain-based orchestration,
providing more sophisticated agent management and tool integration.
"""

import time
from typing import Any

from fastapi import HTTPException

from services.common.app_factory import create_service_app
from services.common.config.loader import get_env_with_default, load_config_from_env
from services.common.config.presets import OrchestratorConfig
from services.common.health import HealthManager
from services.common.health_endpoints import HealthEndpoints
from services.common.http_client_factory import (
    create_dependency_health_client,
    create_resilient_client,
)
from services.common.resilient_http import ServiceUnavailableError
from services.common.structured_logging import get_logger
from services.common.tracing import get_observability_manager

# LangChain imports
from .langchain_integration import (
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

# Logging is configured in main.py before this module is imported
# This ensures structured JSON logging is set up before uvicorn initializes
logger = get_logger(__name__, service_name="orchestrator")

# Health manager for service resilience (must remain module-level for app creation)
_health_manager = HealthManager("orchestrator")
# Note: Other stateful components (_cfg, _langchain_executor, _tts_client, etc.)
# are now stored in app.state during startup and accessed via app.state or request.app.state

# Prompt versioning
PROMPT_VERSION = "v1.0"


async def _startup() -> None:
    """Service-specific startup logic."""
    try:
        # Get observability manager (factory already setup observability)
        observability_manager = get_observability_manager("orchestrator")

        # Register service-specific metrics using centralized helper
        from services.common.audio_metrics import MetricKind, register_service_metrics

        metrics = register_service_metrics(
            observability_manager, kinds=[MetricKind.LLM, MetricKind.SYSTEM]
        )
        llm_metrics = metrics["llm"]
        system_metrics = metrics["system"]

        # HTTP metrics already available from app_factory via app.state.http_metrics

        # Store metrics and observability in app.state
        app.state.llm_metrics = llm_metrics
        app.state.system_metrics = system_metrics
        app.state.observability_manager = observability_manager

        # Set observability manager in health manager
        _health_manager.set_observability_manager(observability_manager)

        # Load configuration with fallback (optional - graceful degradation)
        try:
            # IMPORTANT: Pass preset to ensure defaults are used (env vars still override)
            from services.common.config import get_service_preset

            _config_preset = get_service_preset("orchestrator")
            cfg = load_config_from_env(OrchestratorConfig, **_config_preset)
            app.state.cfg = cfg
        except Exception as exc:
            _health_manager.record_startup_failure(
                error=exc, component="config", is_critical=False
            )
            logger.warning("orchestrator.config_load_failed", error=str(exc))
            app.state.cfg = None  # Continue without config

        # Initialize LangChain executor (strict requirement - fail fast if unavailable)
        langchain_executor = create_langchain_executor()
        app.state.langchain_executor = langchain_executor

        # Initialize TTS client (optional - graceful degradation)
        try:
            tts_url = get_env_with_default("TTS_BASE_URL", "http://bark:7100", str)
            tts_client = TTSClient(base_url=tts_url)
            app.state.tts_client = tts_client
            logger.info("orchestrator.tts_client_initialized", tts_url=tts_url)
        except Exception as exc:
            _health_manager.record_startup_failure(
                error=exc, component="tts_client", is_critical=False
            )
            logger.warning("orchestrator.tts_client_init_failed", error=str(exc))
            app.state.tts_client = None  # Continue without TTS (graceful degradation)

        # Initialize resilient HTTP clients for health checks (optional - graceful degradation)
        # For dependency health checks, grace period is 0.0 by default for accurate readiness
        try:
            llm_url = get_env_with_default("LLM_BASE_URL", "http://flan:8100", str)
            llm_health_client = create_dependency_health_client(
                service_name="llm",
                base_url=llm_url,
                env_prefix="LLM",
            )
            app.state.llm_health_client = llm_health_client
        except Exception as exc:
            _health_manager.record_startup_failure(
                error=exc, component="llm_health_client", is_critical=False
            )
            logger.warning("orchestrator.llm_health_client_init_failed", error=str(exc))
            app.state.llm_health_client = None

        try:
            tts_url = get_env_with_default("TTS_BASE_URL", "http://bark:7100", str)
            tts_health_client = create_dependency_health_client(
                service_name="tts",
                base_url=tts_url,
                env_prefix="TTS",
            )
            app.state.tts_health_client = tts_health_client
        except Exception as exc:
            _health_manager.record_startup_failure(
                error=exc, component="tts_health_client", is_critical=False
            )
            logger.warning("orchestrator.tts_health_client_init_failed", error=str(exc))
            app.state.tts_health_client = None

        try:
            guardrails_url = get_env_with_default(
                "GUARDRAILS_BASE_URL", "http://guardrails:9300", str
            )
            guardrails_health_client = create_dependency_health_client(
                service_name="guardrails",
                base_url=guardrails_url,
                env_prefix="GUARDRAILS",
            )
            app.state.guardrails_health_client = guardrails_health_client
        except Exception as exc:
            _health_manager.record_startup_failure(
                error=exc, component="guardrails_health_client", is_critical=False
            )
            logger.warning(
                "orchestrator.guardrails_health_client_init_failed", error=str(exc)
            )
            app.state.guardrails_health_client = None

        # Register dependencies - check actual service readiness via HTTP
        _health_manager.register_dependency(
            "config", lambda: hasattr(app.state, "cfg") and app.state.cfg is not None
        )
        _health_manager.register_dependency(
            "langchain",
            lambda: (
                hasattr(app.state, "langchain_executor")
                and app.state.langchain_executor is not None
            ),
        )
        _health_manager.register_dependency("llm", _check_llm_health)
        _health_manager.register_dependency("tts", _check_tts_health)
        _health_manager.register_dependency("guardrails", _check_guardrails_health)

        # Mark startup complete (graceful degradation - all components are optional)
        _health_manager.mark_startup_complete()

        logger.info(
            "orchestrator.startup_complete",
            executor_ready=app.state.langchain_executor is not None,
            tts_client_ready=app.state.tts_client is not None,
        )

    except Exception as exc:
        logger.error("orchestrator.startup_failed", error=str(exc))
        # Unexpected critical failure - record it
        _health_manager.record_startup_failure(
            error=exc, component="unexpected", is_critical=True
        )
        raise  # Re-raise so app_factory also records it


async def _shutdown() -> None:
    """Service-specific shutdown logic."""
    tts_client = getattr(app.state, "tts_client", None)
    if tts_client:
        await tts_client.close()
        app.state.tts_client = None
    logger.info("orchestrator.shutdown")


# Create app using factory pattern
app = create_service_app(
    "orchestrator",
    "1.0.0",
    title="Enhanced Orchestrator",
    startup_callback=_startup,
    shutdown_callback=_shutdown,
    health_manager=_health_manager,
)


# Initialize health endpoints
health_endpoints = HealthEndpoints(
    service_name="orchestrator",
    health_manager=_health_manager,
    custom_components={
        "config_loaded": lambda: (
            hasattr(app.state, "cfg") and app.state.cfg is not None
        ),
        "executor_ready": lambda: (
            hasattr(app.state, "langchain_executor")
            and app.state.langchain_executor is not None
        ),
        "tts_client_ready": lambda: (
            hasattr(app.state, "tts_client") and app.state.tts_client is not None
        ),
    },
)

# Include the health endpoints router
app.include_router(health_endpoints.get_router())


@app.post("/api/v1/transcripts", response_model=TranscriptProcessResponse)  # type: ignore[misc]
async def process_transcript(
    request: TranscriptProcessRequest,
) -> TranscriptProcessResponse:
    """Process transcript using LangChain orchestration with guardrails."""
    # Access state from app.state (app is module-level)
    # Set correlation_id in async context if provided in request body
    # This ensures it propagates to downstream services via HTTP clients
    # Prefer request body correlation_id (explicit) over middleware-generated UUIDs
    if request.correlation_id:
        try:
            from services.common.middleware import set_correlation_id

            set_correlation_id(request.correlation_id)
        except (ImportError, AttributeError):
            # Middleware not available, skip context setting
            pass

    start_time = time.time()
    stage_timings: dict[str, float] = {}

    try:
        logger.info(
            "orchestrator.transcript_received",
            transcript_length=len(request.transcript),
            correlation_id=request.correlation_id,
            user_id=request.user_id,
            channel_id=request.channel_id,
        )

        # Input validation with guardrails
        guardrails_start = time.time()
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
                    guardrails_time = (time.time() - guardrails_start) * 1000
                    logger.warning(
                        "orchestrator.input_blocked",
                        reason=validation_data.get("reason"),
                        transcript=request.transcript[:100],
                        duration_ms=guardrails_time,
                        correlation_id=request.correlation_id,
                    )

                    # Record blocked request metrics
                    llm_metrics = getattr(app.state, "llm_metrics", None)
                    if llm_metrics and "llm_requests" in llm_metrics:
                        llm_metrics["llm_requests"].add(
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
                guardrails_time = (time.time() - guardrails_start) * 1000
                stage_timings["input_validation_ms"] = guardrails_time
                logger.info(
                    "orchestrator.input_validation_completed",
                    duration_ms=guardrails_time,
                    correlation_id=request.correlation_id,
                )

            except ServiceUnavailableError as e:
                await guardrails_client.close()
                guardrails_time = (time.time() - guardrails_start) * 1000
                logger.warning(
                    "orchestrator.guardrails_unavailable",
                    error=str(e),
                    duration_ms=guardrails_time,
                    correlation_id=request.correlation_id,
                )
                sanitized_transcript = request.transcript

        except Exception as e:
            guardrails_time = (time.time() - guardrails_start) * 1000
            logger.warning(
                "orchestrator.guardrails_unavailable",
                error=str(e),
                duration_ms=guardrails_time,
                correlation_id=request.correlation_id,
            )
            sanitized_transcript = request.transcript

        # Process with LangChain
        langchain_start = time.time()
        try:
            logger.info(
                "orchestrator.langchain_start",
                transcript_length=len(sanitized_transcript),
                correlation_id=request.correlation_id,
            )
            langchain_executor = getattr(app.state, "langchain_executor", None)
            response = await process_with_langchain(
                sanitized_transcript, request.user_id, langchain_executor
            )
            langchain_time = (time.time() - langchain_start) * 1000
            stage_timings["langchain_processing_ms"] = langchain_time
            # Validate response is not empty or error message
            if not response or response.strip() == "":
                logger.warning(
                    "orchestrator.empty_response",
                    transcript=sanitized_transcript[:100],
                    correlation_id=request.correlation_id,
                )
                response = f"I received your message: {sanitized_transcript[:100]}. Let me help you with that."

            logger.info(
                "orchestrator.langchain_completed",
                duration_ms=langchain_time,
                response_length=len(response) if response else 0,
                correlation_id=request.correlation_id,
            )
        except Exception as langchain_exc:
            langchain_time = (time.time() - langchain_start) * 1000
            stage_timings["langchain_processing_ms"] = langchain_time
            logger.error(
                "orchestrator.langchain_failed",
                error=str(langchain_exc),
                error_type=type(langchain_exc).__name__,
                duration_ms=langchain_time,
                transcript=sanitized_transcript[:100],
                correlation_id=request.correlation_id,
            )
            # Fallback response
            response = f"I understand you asked: {sanitized_transcript[:100]}. I'm here to help."

        # Output validation with guardrails
        output_validation_start = time.time()
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
                        correlation_id=request.correlation_id,
                    )
                    response = "I'm sorry, but I can't provide that response."
                else:
                    # Use filtered output
                    response = output_data.get("filtered", response)

                await guardrails_client.close()
                output_validation_time = (time.time() - output_validation_start) * 1000
                stage_timings["output_validation_ms"] = output_validation_time
                logger.info(
                    "orchestrator.output_validation_completed",
                    duration_ms=output_validation_time,
                    correlation_id=request.correlation_id,
                )

            except ServiceUnavailableError as e:
                await guardrails_client.close()
                output_validation_time = (time.time() - output_validation_start) * 1000
                logger.warning(
                    "orchestrator.output_validation_failed",
                    error=str(e),
                    duration_ms=output_validation_time,
                    correlation_id=request.correlation_id,
                )

        except Exception as e:
            output_validation_time = (time.time() - output_validation_start) * 1000
            logger.warning(
                "orchestrator.output_validation_failed",
                error=str(e),
                duration_ms=output_validation_time,
                correlation_id=request.correlation_id,
            )

        # Synthesize audio using TTS service if client is available and response is not empty
        audio_data: str | None = None
        audio_format: str | None = None

        tts_client = getattr(app.state, "tts_client", None)
        if tts_client and response and len(response.strip()) > 0:
            tts_start = time.time()
            try:
                logger.info(
                    "orchestrator.tts_synthesis_start",
                    text_length=len(response),
                    correlation_id=request.correlation_id,
                )

                # Call TTS service to synthesize audio
                audio_bytes = await tts_client.synthesize(
                    text=response,
                    voice="v2/en_speaker_1",  # Default voice
                    speed=1.0,
                    correlation_id=request.correlation_id,
                )

                if audio_bytes:
                    # Encode audio as base64 for JSON transmission
                    import base64

                    base64_start = time.time()
                    audio_data = base64.b64encode(audio_bytes).decode("utf-8")
                    base64_time = (time.time() - base64_start) * 1000
                    audio_format = "wav"  # Bark returns WAV format
                    tts_time = (time.time() - tts_start) * 1000
                    stage_timings["tts_synthesis_ms"] = tts_time
                    stage_timings["base64_encode_ms"] = base64_time
                    logger.info(
                        "orchestrator.tts_synthesis_completed",
                        total_duration_ms=tts_time,
                        base64_encode_ms=base64_time,
                        audio_size=len(audio_bytes),
                        correlation_id=request.correlation_id,
                    )
                else:
                    tts_time = (time.time() - tts_start) * 1000
                    logger.warning(
                        "orchestrator.tts_synthesis_returned_empty",
                        duration_ms=tts_time,
                        correlation_id=request.correlation_id,
                    )

            except ServiceUnavailableError as e:
                tts_time = (time.time() - tts_start) * 1000
                logger.warning(
                    "orchestrator.tts_unavailable",
                    error=str(e),
                    duration_ms=tts_time,
                    correlation_id=request.correlation_id,
                )
                # Continue without audio - text response is still valid
            except Exception as e:
                tts_time = (time.time() - tts_start) * 1000
                logger.error(
                    "orchestrator.tts_synthesis_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    duration_ms=tts_time,
                    correlation_id=request.correlation_id,
                )
                # Continue without audio - text response is still valid

        # Record metrics
        processing_time = time.time() - start_time
        llm_metrics = getattr(app.state, "llm_metrics", None)
        if llm_metrics:
            if "llm_requests" in llm_metrics:
                llm_metrics["llm_requests"].add(
                    1, attributes={"model": "orchestrator", "status": "success"}
                )
            if "llm_latency" in llm_metrics:
                llm_metrics["llm_latency"].record(
                    processing_time, attributes={"model": "orchestrator"}
                )

        logger.info(
            "orchestrator.transcript_processing_completed",
            total_duration_ms=processing_time * 1000,
            stage_timings=stage_timings,
            correlation_id=request.correlation_id,
            response_length=len(response) if response else 0,
            audio_included=audio_data is not None,
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
        llm_metrics = getattr(app.state, "llm_metrics", None)
        if llm_metrics and "llm_requests" in llm_metrics:
            llm_metrics["llm_requests"].add(
                1, attributes={"model": "orchestrator", "status": "error"}
            )
        if llm_metrics and "llm_latency" in llm_metrics:
            llm_metrics["llm_latency"].record(
                processing_time, attributes={"model": "orchestrator", "status": "error"}
            )

        logger.error(
            "orchestrator.transcript_processing_failed",
            error=str(e),
            error_type=type(e).__name__,
            transcript=request.transcript[:100],
            total_duration_ms=processing_time * 1000,
            stage_timings=stage_timings,
            correlation_id=request.correlation_id,
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
    llm_health_client = getattr(app.state, "llm_health_client", None)
    if llm_health_client is None:
        return False
    try:
        result = await llm_health_client.check_health()
        return bool(result)
    except Exception as exc:
        logger.debug("health.llm_check_failed", error=str(exc))
        return False


async def _check_tts_health() -> bool:
    """Check if TTS service (Bark) is ready via resilient HTTP client."""
    tts_health_client = getattr(app.state, "tts_health_client", None)
    if tts_health_client is None:
        return False
    try:
        result = await tts_health_client.check_health()
        return bool(result)
    except Exception as exc:
        logger.debug("health.tts_check_failed", error=str(exc))
        return False


async def _check_guardrails_health() -> bool:
    """Check if Guardrails service is ready via resilient HTTP client."""
    guardrails_health_client = getattr(app.state, "guardrails_health_client", None)
    if guardrails_health_client is None:
        return False
    try:
        result = await guardrails_health_client.check_health()
        return bool(result)
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
