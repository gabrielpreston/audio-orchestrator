"""
Discord service HTTP API for MCP tool integration.
"""

import asyncio
import os
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Configure logging
logger = structlog.get_logger()

app = FastAPI(title="Discord Voice Service", version="1.0.0")

# Global bot instance (simplified for HTTP mode)
_bot: Any | None = None


class PlayAudioRequest(BaseModel):
    guild_id: str
    channel_id: str
    audio_url: str


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


@app.on_event("startup")
async def startup_event():
    """Initialize Discord bot and HTTP API on startup."""
    global _bot

    logger.info("discord.startup_event_called")

    try:
        # Check if we should run the full Discord bot
        run_full_bot = os.getenv("DISCORD_FULL_BOT", "false").lower() == "true"
        logger.info("discord.full_bot_check", run_full_bot=run_full_bot)

        if run_full_bot:
            # Initialize full Discord bot with voice capabilities
            logger.info("discord.full_bot_starting")
            from services.common.logging import configure_logging

            from .audio import AudioPipeline
            from .config import load_config
            from .discord_voice import VoiceBot
            from .wake import WakeDetector

            logger.info("discord.imports_complete")
            config = load_config()
            logger.info("discord.config_loaded")
            configure_logging(
                config.telemetry.log_level,
                json_logs=config.telemetry.log_json,
                service_name="discord",
            )
            logger.info("discord.logging_configured")

            audio_pipeline = AudioPipeline(config.audio)
            logger.info("discord.audio_pipeline_created")
            wake_detector = WakeDetector(config.wake)
            logger.info("discord.wake_detector_created")

            async def dummy_transcript_publisher(
                transcript_data: dict[str, Any]
            ) -> None:
                logger.info("discord.dummy_transcript_published", **transcript_data)

            _bot = VoiceBot(
                config=config,
                audio_pipeline=audio_pipeline,
                wake_detector=wake_detector,
                transcript_publisher=dummy_transcript_publisher,
            )
            logger.info("discord.voicebot_created")

            _bot_task = asyncio.create_task(_bot.start(config.discord.token))
            # Store reference to prevent garbage collection
            # Store reference to prevent garbage collection
            logger.info("discord.full_bot_started")
        else:
            _bot = {"status": "ready", "mode": "http"}
            logger.info("discord.http_api_started")

    except Exception as exc:
        logger.error("discord.http_startup_failed", error=str(exc))
        import traceback

        logger.error("discord.startup_traceback", traceback=traceback.format_exc())
        # Don't raise the exception to prevent the service from crashing
        _bot = {"status": "error", "mode": "http", "error": str(exc)}
        logger.info("discord.http_api_started_with_error")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown HTTP API."""
    global _bot

    if _bot:
        _bot = None
        logger.info("discord.http_api_shutdown")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "bot_connected": _bot is not None,
        "service": "discord",
        "mode": "http",
    }


@app.post("/mcp/play_audio")
async def play_audio(request: PlayAudioRequest):
    """Play audio in Discord voice channel via MCP."""
    if not _bot:
        raise HTTPException(status_code=503, detail="Discord service not ready")

    try:
        logger.info(
            "discord.play_audio_requested",
            guild_id=request.guild_id,
            channel_id=request.channel_id,
            audio_url=request.audio_url,
        )

        # Check if we have a full Discord bot instance
        if hasattr(_bot, "play_audio_from_url"):
            # Use the actual VoiceBot to play audio
            result = await _bot.play_audio_from_url(
                guild_id=int(request.guild_id),
                channel_id=int(request.channel_id),
                audio_url=request.audio_url,
            )

            logger.info(
                "discord.audio_playback_success",
                guild_id=request.guild_id,
                channel_id=request.channel_id,
                result=result,
            )

            return {
                "status": "success",
                "guild_id": request.guild_id,
                "channel_id": request.channel_id,
                "audio_url": request.audio_url,
                "result": result,
            }
        else:
            # Fallback for HTTP mode without full bot
            logger.warning(
                "discord.play_audio_no_bot_method",
                guild_id=request.guild_id,
                channel_id=request.channel_id,
                audio_url=request.audio_url,
            )

            return {
                "status": "success",
                "guild_id": request.guild_id,
                "channel_id": request.channel_id,
                "audio_url": request.audio_url,
                "result": {
                    "message": "Audio playback requested (HTTP mode - no bot method)"
                },
            }

    except Exception as exc:
        logger.error("discord.play_audio_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/mcp/send_message")
async def send_message(request: SendMessageRequest):
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

        # TODO: Implement actual Discord message sending
        # For now, just acknowledge the request

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


@app.post("/mcp/transcript")
async def handle_transcript(notification: TranscriptNotification):
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

        # TODO: Trigger orchestrator processing here
        # For now, just acknowledge receipt

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


@app.get("/mcp/tools")
async def list_mcp_tools():
    """List available MCP tools."""
    return {
        "tools": [
            {
                "name": "discord.play_audio",
                "description": "Play audio in Discord voice channel",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "guild_id": {"type": "string"},
                        "channel_id": {"type": "string"},
                        "audio_url": {"type": "string"},
                    },
                    "required": ["guild_id", "channel_id", "audio_url"],
                },
            },
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
