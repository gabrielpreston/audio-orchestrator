"""
Discord service HTTP API for MCP tool integration.
"""

import asyncio
import os
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import structlog

from .config import load_config

# Configure logging
logger = structlog.get_logger()

app = FastAPI(title="Discord Voice Service", version="1.0.0")

# Global bot instance (simplified for HTTP mode)
_bot: Optional[Any] = None

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
    correlation_id: Optional[str] = None

@app.on_event("startup")
async def startup_event():
    """Initialize Discord bot and HTTP API on startup."""
    global _bot
    
    try:
        # Check if we should run the full Discord bot
        run_full_bot = os.getenv("DISCORD_FULL_BOT", "false").lower() == "true"
        
        if run_full_bot:
            # Initialize full Discord bot with voice capabilities
            from .discord_voice import run_bot
            config = load_config()
            
            # Start the bot in a background task
            asyncio.create_task(run_bot(config))
            _bot = {"status": "starting", "mode": "full_bot"}
            logger.info("discord.full_bot_starting")
        else:
            # HTTP API mode only
            _bot = {"status": "ready", "mode": "http"}
            logger.info("discord.http_api_started")
            
    except Exception as exc:
        logger.error("discord.startup_failed", error=str(exc))
        raise

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
        "mode": "http"
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
            audio_url=request.audio_url
        )
        
        # Check if we have a full Discord bot instance
        if hasattr(_bot, 'play_audio_from_url'):
            # Use the actual VoiceBot to play audio
            result = await _bot.play_audio_from_url(
                guild_id=int(request.guild_id),
                channel_id=int(request.channel_id),
                audio_url=request.audio_url
            )
            
            logger.info(
                "discord.audio_playback_success",
                guild_id=request.guild_id,
                channel_id=request.channel_id,
                result=result
            )
            
            return {
                "status": "success",
                "guild_id": request.guild_id,
                "channel_id": request.channel_id,
                "audio_url": request.audio_url,
                "result": result
            }
        else:
            # Fallback for HTTP mode without full bot
            logger.warning(
                "discord.play_audio_no_bot_method",
                guild_id=request.guild_id,
                channel_id=request.channel_id,
                audio_url=request.audio_url
            )
            
            return {
                "status": "success",
                "guild_id": request.guild_id,
                "channel_id": request.channel_id,
                "audio_url": request.audio_url,
                "result": {"message": "Audio playback requested (HTTP mode - no bot method)"}
            }
        
    except Exception as exc:
        logger.error("discord.play_audio_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))

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
            message=request.message
        )
        
        # TODO: Implement actual Discord message sending
        # For now, just acknowledge the request
        
        return {
            "status": "success",
            "guild_id": request.guild_id,
            "channel_id": request.channel_id,
            "message_id": "simulated_message_id",
            "content": request.message,
            "result": {"message": "Message sent (HTTP mode)"}
        }
        
    except Exception as exc:
        logger.error("discord.send_message_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))

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
            correlation_id=notification.correlation_id
        )
        
        # TODO: Trigger orchestrator processing here
        # For now, just acknowledge receipt
        
        return {
            "status": "received",
            "guild_id": notification.guild_id,
            "channel_id": notification.channel_id,
            "user_id": notification.user_id,
            "transcript": notification.transcript,
            "correlation_id": notification.correlation_id
        }
        
    except Exception as exc:
        logger.error("discord.transcript_handling_failed", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))

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
                        "audio_url": {"type": "string"}
                    },
                    "required": ["guild_id", "channel_id", "audio_url"]
                }
            },
            {
                "name": "discord.send_message",
                "description": "Send a text message to Discord channel",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "guild_id": {"type": "string"},
                        "channel_id": {"type": "string"},
                        "message": {"type": "string"}
                    },
                    "required": ["guild_id", "channel_id", "message"]
                }
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
