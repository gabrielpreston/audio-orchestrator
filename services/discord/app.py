"""
Discord service HTTP API for tool integration.
"""

import asyncio
from contextlib import suppress
import os
from typing import Any

from fastapi import HTTPException
import httpx

from services.common.audio_metrics import (
    create_audio_metrics,
    create_http_metrics,
    create_stt_metrics,
)
from services.common.health import HealthManager
from services.common.health_endpoints import HealthEndpoints

# Configure logging
from services.common.structured_logging import get_logger
from services.common.tracing import get_observability_manager
from services.common.app_factory import create_service_app

from .audio_processor_wrapper import AudioProcessorWrapper
from .config import load_config
from .discord_voice import TranscriptPublisher, VoiceBot
from .models import (
    CapabilitiesResponse,
    CapabilityInfo,
    MessageSendRequest,
    MessageSendResponse,
    TranscriptNotificationRequest,
    TranscriptNotificationResponse,
)
from .wake import WakeDetector


logger = get_logger(__name__, service_name="discord")

# Global instances
_bot: Any | None = None
_bot_task: asyncio.Task[None] | None = None
_health_manager = HealthManager("discord")
_observability_manager: Any = None
_stt_metrics: dict[str, Any] = {}
_audio_metrics: dict[str, Any] = {}
_http_metrics: dict[str, Any] = {}


# Remove old tool models - now using models.py


def _create_transcript_publisher() -> TranscriptPublisher:
    """Create a transcript publisher for the VoiceBot."""

    async def transcript_publisher(transcript_data: dict[str, Any]) -> None:
        """Publish transcript data - currently just logs it."""
        logger.info("discord.transcript_received", **transcript_data)

    return transcript_publisher


async def _start_discord_bot(config: Any, observability_manager: Any) -> None:
    """Start the Discord bot as a background task."""
    global _bot, _bot_task

    try:
        logger.info("discord.bot_starting")

        # Create bot components
        audio_processor_wrapper = AudioProcessorWrapper(config.audio, config.telemetry)
        wake_detector = WakeDetector(config.wake)
        transcript_publisher = _create_transcript_publisher()

        # Create VoiceBot instance
        bot = VoiceBot(
            config,
            audio_processor_wrapper,
            wake_detector,
            transcript_publisher,
            metrics=_audio_metrics,
        )

        # Share the observability manager with the bot's health manager
        # The bot has its own health manager for internal tracking, but we can
        # share observability for consistent metrics
        if observability_manager:
            bot._health_manager.set_observability_manager(observability_manager)

        # Store bot reference
        _bot = bot

        # Start bot connection (non-blocking)
        bot_task = asyncio.create_task(bot.start(config.discord.token))
        _bot_task = bot_task

        logger.info("discord.bot_start_task_created")

        # Bot task runs forever, so we don't await it here
        # The on_ready event will fire when the bot connects

    except Exception as exc:
        logger.error(
            "discord.bot_initialization_failed",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        import traceback

        logger.error("discord.bot_init_traceback", traceback=traceback.format_exc())
        # Set bot to error state but don't crash the HTTP API
        _bot = {"status": "error", "mode": "bot", "error": str(exc)}
        if _bot_task:
            _bot_task.cancel()
            _bot_task = None


async def _startup() -> None:
    """Initialize Discord bot and HTTP API on startup."""
    global _observability_manager, _stt_metrics, _audio_metrics, _http_metrics

    logger.info("discord.startup_event_called")

    try:
        # Get observability manager (factory already setup observability)
        _observability_manager = get_observability_manager("discord")

        # Create service-specific metrics
        _stt_metrics = create_stt_metrics(_observability_manager)
        _audio_metrics = create_audio_metrics(_observability_manager)
        _http_metrics = create_http_metrics(_observability_manager)

        # Set observability manager in health manager
        _health_manager.set_observability_manager(_observability_manager)

        # Load configuration
        config = load_config()

        # Register dependencies
        _health_manager.register_dependency("stt", _check_stt_health)
        _health_manager.register_dependency("orchestrator", _check_orchestrator_health)

        # Start Discord bot as background task
        asyncio.create_task(_start_discord_bot(config, _observability_manager))

        # Mark HTTP API as ready (bot will mark itself ready when connected)
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


async def _shutdown() -> None:
    """Shutdown HTTP API and Discord bot."""
    global _bot, _bot_task

    logger.info("discord.shutdown_event_called")

    # Close Discord bot if it's running
    if _bot and isinstance(_bot, VoiceBot):
        try:
            logger.info("discord.bot_shutting_down")
            await _bot.close()
            logger.info("discord.bot_closed")
        except Exception as exc:
            logger.error(
                "discord.bot_shutdown_error",
                error=str(exc),
                error_type=type(exc).__name__,
            )

    # Cancel bot task if it exists
    if _bot_task:
        try:
            if not _bot_task.done():
                _bot_task.cancel()
                with suppress(asyncio.CancelledError):
                    await _bot_task
            logger.info("discord.bot_task_cancelled")
        except Exception as exc:
            logger.error(
                "discord.bot_task_cancel_error",
                error=str(exc),
                error_type=type(exc).__name__,
            )
        finally:
            _bot_task = None

    _bot = None
    logger.info("discord.http_api_shutdown")


# Create app using factory pattern (after all function definitions)
app = create_service_app(
    "discord",
    "1.0.0",
    title="Discord Voice Service",
    startup_callback=_startup,
    shutdown_callback=_shutdown,
)


def _get_bot_status() -> dict[str, Any]:
    """Get bot connection status."""
    try:
        if _bot is None:
            return {"connected": False, "mode": "initializing"}
        elif isinstance(_bot, VoiceBot):
            # VoiceBot inherits from discord.Client which has is_ready property
            return {
                "connected": _bot.is_ready,
                "mode": "bot",
                "user": str(_bot.user) if _bot.user else None,
            }
        elif isinstance(_bot, dict):
            return {
                "connected": False,
                "mode": _bot.get("mode", "unknown"),
                "status": _bot.get("status", "unknown"),
                "error": _bot.get("error"),
            }
        else:
            return {"connected": False, "mode": "unknown"}
    except Exception:
        # Return safe default if anything fails
        return {"connected": False, "mode": "error"}


# Initialize health endpoints
health_endpoints = HealthEndpoints(
    service_name="discord",
    health_manager=_health_manager,
    custom_components={
        "bot_connected": lambda: isinstance(_bot, VoiceBot) and _bot.is_ready,
        "bot_status": lambda: _get_bot_status(),
    },
    custom_dependencies={
        "stt": _check_stt_health,
        "orchestrator": _check_orchestrator_health,
    },
)

# Include the health endpoints router
app.include_router(health_endpoints.get_router())


@app.post("/api/v1/messages", response_model=MessageSendResponse)  # type: ignore[misc]
async def send_message(request: MessageSendRequest) -> MessageSendResponse:
    """Send text message to Discord channel."""
    if not _bot or not isinstance(_bot, VoiceBot):
        raise HTTPException(
            status_code=503,
            detail="Discord bot not ready or not connected",
        )

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
    # This endpoint can work even if bot isn't ready (it's a notification endpoint)
    # But we check if the service is at least initialized
    if _bot is None:
        raise HTTPException(status_code=503, detail="Discord service not initialized")

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
