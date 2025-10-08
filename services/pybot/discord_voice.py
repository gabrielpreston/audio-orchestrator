"""Discord client wiring for the Python voice bot."""

from __future__ import annotations

import asyncio
import io
from dataclasses import dataclass
from typing import Optional

import aiohttp
import discord

from .audio import AudioPipeline, AudioSegment, rms_from_pcm
from .config import BotConfig, DiscordConfig
from .logging import get_logger
from .mcp import MCPManager
from .orchestrator import OrchestratorClient, OrchestratorRequest
from .transcription import TranscriptResult, TranscriptionClient
from .wake import WakeDetector


@dataclass(slots=True)
class SegmentContext:
    """Metadata about a captured audio segment."""

    segment: AudioSegment
    guild_id: int
    channel_id: int


class VoiceBot(discord.Client):
    """Discord client that orchestrates voice capture and downstream processing."""

    def __init__(
        self,
        config: BotConfig,
        audio_pipeline: AudioPipeline,
        wake_detector: WakeDetector,
        mcp_manager: MCPManager,
    ) -> None:
        intents = self._build_intents(config.discord)
        super().__init__(intents=intents)
        self.config = config
        self.audio_pipeline = audio_pipeline
        self._wake_detector = wake_detector
        self._mcp_manager = mcp_manager
        self._logger = get_logger(__name__)
        self._segment_queue: "asyncio.Queue[SegmentContext]" = asyncio.Queue()
        self._segment_task: Optional[asyncio.Task[None]] = None
        self._shutdown = asyncio.Event()
        self._http_session: Optional[aiohttp.ClientSession] = None

    async def setup_hook(self) -> None:
        self._http_session = aiohttp.ClientSession()
        self._segment_task = asyncio.create_task(self._segment_consumer())

    async def close(self) -> None:
        self._shutdown.set()
        if self._segment_task:
            self._segment_task.cancel()
            try:
                await self._segment_task
            except asyncio.CancelledError:
                pass
        if self._http_session:
            await self._http_session.close()
        await super().close()

    async def on_ready(self) -> None:
        self._logger.info(
            "discord.ready",
            extra={
                "user": str(self.user),
                "guilds": [guild.id for guild in self.guilds],
                "manifests": [manifest.name for manifest in self._mcp_manager.manifests],
            },
        )
        if self.config.discord.auto_join:
            await self._auto_join_voice()

    async def _auto_join_voice(self) -> None:
        guild = self.get_guild(self.config.discord.guild_id)
        if not guild:
            self._logger.error("discord.guild_not_found", extra={"guild_id": self.config.discord.guild_id})
            return
        channel = guild.get_channel(self.config.discord.voice_channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            self._logger.error(
                "discord.channel_not_found",
                extra={"channel_id": self.config.discord.voice_channel_id},
            )
            return
        try:
            await channel.connect()
        except Exception as exc:  # noqa: BLE001
            self._logger.error(
                "discord.voice_connect_failed",
                extra={"guild_id": guild.id, "channel_id": channel.id, "error": str(exc)},
            )
        else:
            self._logger.info(
                "discord.voice_connected",
                extra={"guild_id": guild.id, "channel_id": channel.id},
            )

    async def ingest_voice_packet(self, user_id: int, pcm: bytes, frame_duration: float) -> None:
        """Entry point for voice receivers to feed PCM data into the pipeline."""

        rms = rms_from_pcm(pcm)
        segment = self.audio_pipeline.register_frame(user_id, pcm, rms, frame_duration)
        if not segment:
            return
        voice_state = self._resolve_voice_state(user_id)
        if not voice_state:
            self._logger.warning(
                "discord.voice_state_missing",
                extra={"user_id": user_id},
            )
            return
        if not voice_state.channel:
            self._logger.warning(
                "discord.voice_channel_missing",
                extra={"user_id": user_id},
            )
            return
        context = SegmentContext(
            segment=segment,
            guild_id=voice_state.channel.guild.id,
            channel_id=voice_state.channel.id,
        )
        await self._segment_queue.put(context)

    def _resolve_voice_state(self, user_id: int) -> Optional[discord.VoiceState]:
        for guild in self.guilds:
            member = guild.get_member(user_id)
            if member and member.voice and member.voice.channel:
                return member.voice
        return None

    async def _segment_consumer(self) -> None:
        await asyncio.sleep(0)
        async with TranscriptionClient(self.config.stt) as stt_client:
            async with OrchestratorClient(self.config.orchestrator, self._wake_detector) as orchestrator:
                while not self._shutdown.is_set():
                    context = await self._segment_queue.get()
                    transcript = await stt_client.transcribe(context.segment)
                    await self._handle_transcript(context, transcript, orchestrator)

    async def _handle_transcript(
        self,
        context: SegmentContext,
        transcript: TranscriptResult,
        orchestrator: OrchestratorClient,
    ) -> None:
        request = OrchestratorRequest(
            text=transcript.text,
            user_id=context.segment.user_id,
            channel_id=context.channel_id,
            guild_id=context.guild_id,
            correlation_id=transcript.correlation_id,
        )
        response = await orchestrator.maybe_invoke(request, transcript)
        if response and response.tts_audio_url:
            await self._play_tts(response.tts_audio_url, context)

    async def _play_tts(self, audio_url: str, context: SegmentContext) -> None:
        if not self._http_session:
            self._logger.warning("tts.http_session_missing")
            return
        voice_client = self._voice_client_for_guild(context.guild_id)
        if not voice_client:
            self._logger.warning(
                "tts.voice_client_missing",
                extra={"guild_id": context.guild_id},
            )
            return
        if voice_client.is_playing():
            voice_client.stop()
        try:
            async with self._http_session.get(audio_url) as response:
                response.raise_for_status()
                data = await response.read()
        except Exception as exc:  # noqa: BLE001
            self._logger.error(
                "tts.download_failed",
                extra={
                    "audio_url": audio_url,
                    "error": str(exc),
                },
            )
            return
        class MemoryAudio(discord.AudioSource):
            def __init__(self, payload: bytes) -> None:
                self._buffer = io.BytesIO(payload)

            def read(self) -> bytes:
                return self._buffer.read(3840)

            def is_opus(self) -> bool:
                return False

        voice_client.play(MemoryAudio(data))

    def _voice_client_for_guild(self, guild_id: int) -> Optional[discord.VoiceClient]:
        for voice_client in self.voice_clients:
            if voice_client.guild and voice_client.guild.id == guild_id:
                return voice_client
        return None

    @staticmethod
    def _build_intents(config: DiscordConfig) -> discord.Intents:
        intents = discord.Intents.none()
        for name in config.intents:
            if hasattr(intents, name):
                setattr(intents, name, True)
        return intents


async def run_bot(config: BotConfig) -> None:
    """Entrypoint that wires together all components."""

    audio_pipeline = AudioPipeline(config.audio)
    wake_detector = WakeDetector(config.orchestrator.wake_phrases)
    async with MCPManager(config.mcp) as mcp_manager:
        bot = VoiceBot(config, audio_pipeline, wake_detector, mcp_manager)
        async with bot:
            await bot.start(config.discord.token)


__all__ = ["VoiceBot", "run_bot", "SegmentContext"]
