"""
Discord service HTTP API for MCP tool integration.
"""

import asyncio
import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from services.common.health import HealthManager, HealthStatus

# Configure logging
from services.common.logging import get_logger

from .config import load_config


logger = get_logger(__name__, service_name="discord")

app = FastAPI(title="Discord Voice Service", version="1.0.0")

# Global bot instance (simplified for HTTP mode)
_bot: Any | None = None
_health_manager = HealthManager("discord")


class SendMessageRequest(BaseModel):
    guild_id: str
    channel_id: str
    message: str


class TranscriptNotification(BaseModel):
    guild_id: str
    channel_id: str
    user_id: str
    transcript: str
    correlation_id: str | None = None


@app.on_event("startup")  # type: ignore[misc]
async def startup_event() -> None:
    """Initialize Discord bot and HTTP API on startup."""
    global _bot

    logger.info("discord.startup_event_called")

    try:
        # Load configuration
        config = load_config()

        # Register dependencies
        _health_manager.register_dependency("stt", _check_stt_health)
        _health_manager.register_dependency("orchestrator", _check_orchestrator_health)

        # Check if we should run the full Discord bot
        run_full_bot = config.runtime.full_bot  # type: ignore[attr-defined]
        logger.info("discord.full_bot_check", run_full_bot=run_full_bot)

        if run_full_bot:
            # Initialize full Discord bot with voice capabilities
            logger.info("discord.full_bot_starting")
            from services.common.logging import configure_logging

            from .audio import AudioPipeline
            from .discord_voice import VoiceBot
            from .wake import WakeDetector

            logger.info("discord.imports_complete")
            logger.info("discord.config_loaded")
            configure_logging(
                config.telemetry.log_level,  # type: ignore[attr-defined]
                json_logs=config.telemetry.log_json,  # type: ignore[attr-defined]
                service_name="discord",
            )
            logger.info("discord.logging_configured")

            audio_pipeline = AudioPipeline(config.audio, config.telemetry)  # type: ignore[arg-type]
            logger.info("discord.audio_pipeline_created")
            wake_detector = WakeDetector(config.wake)  # type: ignore[arg-type]
            logger.info("discord.wake_detector_created")

            async def dummy_transcript_publisher(
                transcript_data: dict[str, Any],
            ) -> None:
                logger.info("discord.dummy_transcript_published", **transcript_data)

            _bot = VoiceBot(
                config=config,
                audio_pipeline=audio_pipeline,
                wake_detector=wake_detector,
                transcript_publisher=dummy_transcript_publisher,
            )
            logger.info("discord.voicebot_created")

            _bot_task = asyncio.create_task(_bot.start(config.discord.token))  # type: ignore[attr-defined]
            # Store reference to prevent garbage collection
            # Store reference to prevent garbage collection
            logger.info("discord.full_bot_started")
        else:
            _bot = {"status": "ready", "mode": "http"}
            _health_manager.mark_startup_complete()  # For HTTP-only mode
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
    orch_url = os.getenv("ORCHESTRATOR_BASE_URL", "http://orchestrator:8000")
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


@app.post("/mcp/send_message")  # type: ignore[misc]
async def send_message(request: SendMessageRequest) -> dict[str, Any]:
    """Send text message to Discord channel via MCP."""
    if not _bot:
        raise HTTPException(status_code=503, detail="Discord service not ready")

    try:
        # For HTTP mode, we'll simulate the message sending
        # In a real implementation, this would connect to Discord and send the message
        logger.info(
            "discord.send_message_requested",
            guild_id=request.guild_id,
            channel_id=request.channel_id,
            message=request.message,
        )

        # NOTE: HTTP mode uses simulated message sending for testing/development.
        # Full Discord.py bot mode (when DISCORD_FULL_BOT=true) handles actual
        # message sending through the VoiceBot class.
        # For production HTTP-based message sending, implement Discord REST API client here.

        return {
            "status": "success",
            "guild_id": request.guild_id,
            "channel_id": request.channel_id,
            "message_id": "simulated_message_id",
            "content": request.message,
            "result": {"message": "Message sent (HTTP mode)"},
        }

    except Exception as exc:
        logger.error("discord.send_message_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/mcp/transcript")  # type: ignore[misc]
async def handle_transcript(notification: TranscriptNotification) -> dict[str, Any]:
    """Handle transcript notification from orchestrator."""
    if not _bot:
        raise HTTPException(status_code=503, detail="Discord service not ready")

    try:
        # Process transcript (this would trigger the voice assistant flow)
        logger.info(
            "discord.transcript_received",
            guild_id=notification.guild_id,
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

        return {
            "status": "received",
            "guild_id": notification.guild_id,
            "channel_id": notification.channel_id,
            "user_id": notification.user_id,
            "transcript": notification.transcript,
            "correlation_id": notification.correlation_id,
        }

    except Exception as exc:
        logger.error("discord.transcript_handling_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/mcp/tools")  # type: ignore[misc]
async def list_mcp_tools() -> dict[str, Any]:
    """List available MCP tools."""
    return {
        "tools": [
            {
                "name": "discord.send_message",
                "description": "Send a text message to Discord channel",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "guild_id": {"type": "string"},
                        "channel_id": {"type": "string"},
                        "message": {"type": "string"},
                    },
                    "required": ["guild_id", "channel_id", "message"],
                },
            },
        ]
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
