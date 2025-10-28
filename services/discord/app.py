"""
Discord service HTTP API for tool integration.
"""

import os
from typing import Any

from fastapi import FastAPI, HTTPException
import httpx

from services.common.audio_metrics import (
    create_audio_metrics,
    create_http_metrics,
    create_stt_metrics,
)
from services.common.health import HealthManager, HealthStatus

# Configure logging
from services.common.structured_logging import get_logger
from services.common.tracing import setup_service_observability

from .config import load_config
from .models import (
    MessageSendRequest,
    MessageSendResponse,
    TranscriptNotificationRequest,
    TranscriptNotificationResponse,
    CapabilitiesResponse,
    CapabilityInfo,
)


logger = get_logger(__name__, service_name="discord")

app = FastAPI(title="Discord Voice Service", version="1.0.0")

# Global instances
_bot: Any | None = None
_health_manager = HealthManager("discord")
_observability_manager = None
_stt_metrics = {}
_audio_metrics = {}
_http_metrics = {}


# Remove old tool models - now using models.py


@app.on_event("startup")  # type: ignore[misc]
async def startup_event() -> None:
    """Initialize Discord bot and HTTP API on startup."""
    global _bot, _observability_manager, _stt_metrics, _audio_metrics, _http_metrics

    logger.info("discord.startup_event_called")

    try:
        # Setup observability (tracing + metrics)
        _observability_manager = setup_service_observability("discord", "1.0.0")
        _observability_manager.instrument_fastapi(app)

        # Create service-specific metrics
        _stt_metrics = create_stt_metrics(_observability_manager)
        _audio_metrics = create_audio_metrics(_observability_manager)
        _http_metrics = create_http_metrics(_observability_manager)

        # Set observability manager in health manager
        _health_manager.set_observability_manager(_observability_manager)

        # Load configuration (not used in HTTP-only mode)
        _ = load_config()

        # Register dependencies
        _health_manager.register_dependency("stt", _check_stt_health)
        _health_manager.register_dependency("orchestrator", _check_orchestrator_health)

        # HTTP-only mode - no full Discord bot
        _bot = {"status": "ready", "mode": "http"}
        _health_manager.mark_startup_complete()
        logger.info("discord.http_api_started")

    except Exception as exc:
        logger.error("discord.http_startup_failed", error=str(exc))
        import traceback

        logger.error("discord.startup_traceback", traceback=traceback.format_exc())
        # Don't raise the exception to prevent the service from crashing
        _bot = {"status": "error", "mode": "http", "error": str(exc)}
        logger.info("discord.http_api_started_with_error")


async def _check_stt_health() -> bool:
    """Check STT service health."""
    stt_url = os.getenv("STT_BASE_URL", "http://stt:9000")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{stt_url}/health/ready", timeout=5.0)
            return bool(response.status_code == 200)
    except Exception:
        return False


async def _check_orchestrator_health() -> bool:
    """Check Orchestrator service health."""
    orch_url = os.getenv("ORCHESTRATOR_BASE_URL", "http://orchestrator:8200")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{orch_url}/health/ready", timeout=5.0)
            return bool(response.status_code == 200)
    except Exception:
        return False


@app.on_event("shutdown")  # type: ignore[misc]
async def shutdown_event() -> None:
    """Shutdown HTTP API."""
    global _bot

    if _bot:
        _bot = None
        logger.info("discord.http_api_shutdown")


@app.get("/health/live")  # type: ignore[misc]
async def health_live() -> dict[str, str]:
    """Liveness check - is process running."""
    return {"status": "alive", "service": "discord"}


@app.get("/health/ready")  # type: ignore[misc]
async def health_ready() -> dict[str, Any]:
    """Readiness check - can serve requests."""
    if _bot is None:
        raise HTTPException(status_code=503, detail="Bot not connected")

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
        "service": "discord",
        "components": {
            "bot_connected": _bot is not None,
            "mode": "http",
            "startup_complete": _health_manager._startup_complete,
        },
        "dependencies": health_status.details.get("dependencies", {}),
        "health_details": health_status.details,
    }


@app.post("/api/v1/messages", response_model=MessageSendResponse)  # type: ignore[misc]
async def send_message(request: MessageSendRequest) -> MessageSendResponse:
    """Send text message to Discord channel."""
    if not _bot:
        raise HTTPException(status_code=503, detail="Discord service not ready")

    try:
        # For HTTP mode, we'll simulate the message sending
        # In a real implementation, this would connect to Discord and send the message
        logger.info(
            "discord.send_message_requested",
            channel_id=request.channel_id,
            content=request.content,
            correlation_id=request.correlation_id,
        )

        # NOTE: HTTP mode uses simulated message sending for testing/development.
        # Full Discord.py bot mode (when DISCORD_FULL_BOT=true) handles actual
        # message sending through the VoiceBot class.
        # For production HTTP-based message sending, implement Discord REST API client here.

        return MessageSendResponse(
            success=True,
            message_id="simulated_message_id",
            correlation_id=request.correlation_id,
        )

    except Exception as exc:
        logger.error("discord.send_message_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post(
    "/api/v1/notifications/transcript", response_model=TranscriptNotificationResponse
)  # type: ignore[misc]
async def handle_transcript(
    notification: TranscriptNotificationRequest,
) -> TranscriptNotificationResponse:
    """Handle transcript notification from orchestrator."""
    if not _bot:
        raise HTTPException(status_code=503, detail="Discord service not ready")

    try:
        # Process transcript (this would trigger the voice assistant flow)
        logger.info(
            "discord.transcript_received",
            channel_id=notification.channel_id,
            user_id=notification.user_id,
            transcript=notification.transcript,
            correlation_id=notification.correlation_id,
        )

        # NOTE: This endpoint receives transcript notifications from the orchestrator.
        # In the current architecture, the orchestrator initiates processing after receiving
        # transcripts from the STT service. This endpoint serves as a notification/webhook.
        # Full processing flow: Discord → STT → Orchestrator → [this endpoint for notifications]
        # If bidirectional communication is needed, implement orchestrator client call here.

        return TranscriptNotificationResponse(
            success=True,
            correlation_id=notification.correlation_id,
        )

    except Exception as exc:
        logger.error("discord.transcript_handling_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/v1/capabilities", response_model=CapabilitiesResponse)  # type: ignore[misc]
async def list_capabilities() -> CapabilitiesResponse:
    """List available Discord service capabilities."""
    return CapabilitiesResponse(
        service="discord",
        version="1.0.0",
        capabilities=[
            CapabilityInfo(
                name="send_message",
                description="Send a text message to Discord channel",
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
            CapabilityInfo(
                name="transcript_notification",
                description="Receive transcript notifications from orchestrator",
                parameters={
                    "type": "object",
                    "properties": {
                        "transcript": {
                            "type": "string",
                            "description": "Transcript text",
                        },
                        "user_id": {"type": "string", "description": "Discord user ID"},
                        "channel_id": {
                            "type": "string",
                            "description": "Discord channel ID",
                        },
                        "correlation_id": {
                            "type": "string",
                            "description": "Correlation ID for tracing",
                        },
                    },
                    "required": ["transcript", "user_id", "channel_id"],
                },
            ),
        ],
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
