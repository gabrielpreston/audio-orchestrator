"""Audio playback utilities for Discord voice channels."""

from __future__ import annotations

import io

import discord

from services.common.structured_logging import get_logger

logger = get_logger(__name__, service_name="discord")


async def play_audio_bytes(
    voice_client: discord.VoiceClient,
    audio_bytes: bytes,
    *,
    sample_rate: int = 22050,
    channels: int = 1,
    correlation_id: str | None = None,
) -> None:
    """Play audio bytes to Discord voice channel.

    Args:
        voice_client: Discord voice client to play audio on
        audio_bytes: Audio data as bytes (WAV format expected)
        sample_rate: Sample rate of the audio (default: 22050 for Bark TTS)
        channels: Number of audio channels (default: 1 for mono)
        correlation_id: Correlation ID for logging
    """
    if not voice_client or not voice_client.is_connected():
        logger.warning(
            "discord.audio_playback_skipped",
            reason="voice_client_not_connected",
            correlation_id=correlation_id,
        )
        return

    try:
        # Create an in-memory file-like object from the audio bytes
        audio_source = discord.FFmpegPCMAudio(
            source=io.BytesIO(audio_bytes),
            pipe=True,
            stderr=io.StringIO() if logger.isEnabledFor("DEBUG") else None,
        )

        # Play the audio
        voice_client.play(
            audio_source,
            after=lambda error: _playback_finished(error, correlation_id),
        )

        logger.info(
            "discord.audio_playback_started",
            audio_size=len(audio_bytes),
            sample_rate=sample_rate,
            channels=channels,
            correlation_id=correlation_id,
        )

    except Exception as exc:
        logger.error(
            "discord.audio_playback_failed",
            error=str(exc),
            error_type=type(exc).__name__,
            correlation_id=correlation_id,
        )
        raise


def _playback_finished(error: Exception | None, correlation_id: str | None) -> None:
    """Callback when audio playback finishes.

    Args:
        error: Error if playback failed, None if successful
        correlation_id: Correlation ID for logging
    """
    if error:
        logger.error(
            "discord.audio_playback_error",
            error=str(error),
            error_type=type(error).__name__,
            correlation_id=correlation_id,
        )
    else:
        logger.debug(
            "discord.audio_playback_completed",
            correlation_id=correlation_id,
        )
