"""Discord client wiring for the Python voice bot."""

from __future__ import annotations

import asyncio
import io
from contextlib import suppress
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, Optional

import aiohttp
import discord

try:
    from discord.ext import voice_recv as discord_voice_recv  # type: ignore[attr-defined]
except ImportError:
    discord_voice_recv = None
else:
    # Patch in the voice receive-capable client provided by discord-ext-voice-recv.
    discord.VoiceClient = discord_voice_recv.VoiceRecvClient  # type: ignore[assignment]
    try:
        discord.opus._load_default()
    except OSError:
        pass

from .audio import AudioPipeline, AudioSegment, rms_from_pcm
from .config import BotConfig, DiscordConfig
from .mcp import MCPServer
from .transcription import TranscriptResult, TranscriptionClient
from .wake import WakeDetector
from .receiver import build_sink


@dataclass(slots=True)
class SegmentContext:
    """Metadata about a captured audio segment."""

    segment: AudioSegment
    guild_id: int
    channel_id: int


TranscriptPublisher = Callable[[Dict[str, object]], Awaitable[None]]


class VoiceBot(discord.Client):
    """Discord client that orchestrates voice capture and downstream processing."""

    def __init__(
        self,
        config: BotConfig,
        audio_pipeline: AudioPipeline,
        wake_detector: WakeDetector,
        transcript_publisher: TranscriptPublisher,
    ) -> None:
        intents = self._build_intents(config.discord)
        super().__init__(intents=intents)
        self.config = config
        self.audio_pipeline = audio_pipeline
        self._wake_detector = wake_detector
        self._publish_transcript = transcript_publisher
        self._segment_queue: "asyncio.Queue[SegmentContext]" = asyncio.Queue()
        self._segment_task: Optional[asyncio.Task[None]] = None
        self._shutdown = asyncio.Event()
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._voice_receivers: Dict[int, object] = {}

    async def setup_hook(self) -> None:
        self._loop = asyncio.get_running_loop()
        if self._http_session is None:
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
        for guild_id in list(self._voice_receivers.keys()):
            voice_client = self._voice_client_for_guild(guild_id)
            self._stop_voice_receiver(guild_id, voice_client)
        if self._http_session:
            await self._http_session.close()
        await super().close()

    async def on_ready(self) -> None:
        if self.config.discord.auto_join:
            await self.join_voice_channel(
                self.config.discord.guild_id, self.config.discord.voice_channel_id
            )

    async def join_voice_channel(self, guild_id: int, channel_id: int) -> Dict[str, object]:
        await self.wait_until_ready()
        guild = self.get_guild(guild_id)
        if not guild:
            raise ValueError(f"Guild {guild_id} not found")
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            raise ValueError(f"Channel {channel_id} is not a voice channel")

        voice_client = self._voice_client_for_guild(guild_id)
        desired_cls = (discord_voice_recv.VoiceRecvClient if discord_voice_recv else discord.VoiceClient)  # type: ignore[attr-defined]

        if voice_client and voice_client.channel and voice_client.channel.id == channel_id:
            if discord_voice_recv and not isinstance(voice_client, discord_voice_recv.VoiceRecvClient):  # type: ignore[attr-defined]
                await voice_client.disconnect()
                voice_client = None
            else:
                self._ensure_voice_receiver(voice_client)
                return {"status": "already_connected", "guild_id": guild_id, "channel_id": channel_id}

        if voice_client and voice_client.channel:
            await voice_client.move_to(channel)
            self._ensure_voice_receiver(voice_client)
        else:
            connect_kwargs = {"cls": desired_cls} if discord_voice_recv else {}
            voice_client = await channel.connect(**connect_kwargs)
            if voice_client:
                self._ensure_voice_receiver(voice_client)
        return {"status": "connected", "guild_id": guild_id, "channel_id": channel_id}

    async def leave_voice_channel(self, guild_id: int) -> Dict[str, object]:
        await self.wait_until_ready()
        voice_client = self._voice_client_for_guild(guild_id)
        if not voice_client:
            return {"status": "not_connected", "guild_id": guild_id}

        channel_id = voice_client.channel.id if voice_client.channel else None
        self._stop_voice_receiver(guild_id, voice_client)
        await voice_client.disconnect()
        return {"status": "disconnected", "guild_id": guild_id, "channel_id": channel_id}

    async def send_text_message(self, channel_id: int, content: str) -> Dict[str, object]:
        await self.wait_until_ready()
        channel = self.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            raise ValueError(f"Channel {channel_id} is not a text channel")
        message = await channel.send(content)
        return {"status": "sent", "channel_id": channel_id, "message_id": message.id}

    async def play_audio_from_url(self, guild_id: int, channel_id: int, audio_url: str) -> Dict[str, object]:
        await self.wait_until_ready()
        if not self._http_session:
            timeout = aiohttp.ClientTimeout(total=30)
            self._http_session = aiohttp.ClientSession(timeout=timeout)
        context = SegmentContext(
            segment=AudioSegment(
                user_id=0,
                pcm=b"",
                start_timestamp=0.0,
                end_timestamp=0.0,
                correlation_id="manual",
                frame_count=0,
            ),
            guild_id=guild_id,
            channel_id=channel_id,
        )
        await self._play_tts(audio_url, context)
        return {"status": "playing", "guild_id": guild_id, "channel_id": channel_id}

    async def ingest_voice_packet(self, user_id: int, pcm: bytes, frame_duration: float) -> None:
        """Entry point for voice receivers to feed PCM data into the pipeline."""

        rms = rms_from_pcm(pcm)
        segment = self.audio_pipeline.register_frame(user_id, pcm, rms, frame_duration)
        if not segment:
            return
        voice_state = self._resolve_voice_state(user_id)
        if not voice_state or not voice_state.channel:
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
            while not self._shutdown.is_set():
                context = await self._segment_queue.get()
                try:
                    transcript = await stt_client.transcribe(context.segment)
                    await self._handle_transcript(context, transcript)
                except asyncio.CancelledError:
                    raise
                except Exception:  # noqa: BLE001
                    pass
                finally:
                    self._segment_queue.task_done()

    async def _handle_transcript(
        self,
        context: SegmentContext,
        transcript: TranscriptResult,
    ) -> None:
        wake_phrase = self._wake_detector.first_match(transcript.text)
        if not wake_phrase:
            return

        payload: Dict[str, object] = {
            "text": transcript.text,
            "user_id": context.segment.user_id,
            "channel_id": context.channel_id,
            "guild_id": context.guild_id,
            "correlation_id": transcript.correlation_id,
            "wake_phrase": wake_phrase,
            "timestamps": {
                "start": transcript.start_timestamp,
                "end": transcript.end_timestamp,
            },
            "language": transcript.language,
            "confidence": transcript.confidence,
            "frames": context.segment.frame_count,
        }
        await self._publish_transcript(payload)

    async def _play_tts(self, audio_url: str, context: SegmentContext) -> None:
        if not self._http_session:
            return
        voice_client = self._voice_client_for_guild(context.guild_id)
        if not voice_client:
            return
        if voice_client.is_playing():
            voice_client.stop()
        try:
            async with self._http_session.get(audio_url) as response:
                response.raise_for_status()
                data = await response.read()
        except Exception:  # noqa: BLE001
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

    def _ensure_voice_receiver(self, voice_client: discord.VoiceClient) -> None:
        if self._loop is None:
            return
        guild_id = voice_client.guild.id if voice_client.guild else None
        channel_id = voice_client.channel.id if voice_client.channel else None
        if guild_id is None or channel_id is None:
            return
        if guild_id in self._voice_receivers:
            return
        try:
            assert self._loop is not None
            receiver = build_sink(self._loop, self.ingest_voice_packet)
        except Exception:  # noqa: BLE001
            return
        try:
            voice_client.listen(receiver)
        except Exception:  # noqa: BLE001
            return
        self._voice_receivers[guild_id] = receiver

    def _stop_voice_receiver(self, guild_id: int, voice_client: Optional[discord.VoiceClient]) -> None:
        receiver = self._voice_receivers.pop(guild_id, None)
        if not receiver:
            return
        if voice_client:
            with suppress(Exception):
                voice_client.stop_listening()
        if hasattr(receiver, "cleanup"):
            with suppress(Exception):
                receiver.cleanup()

    @staticmethod
    def _build_intents(config: DiscordConfig) -> discord.Intents:
        intents = discord.Intents.none()
        intent_aliases = {
            "guild_voice_states": "voice_states",
        }
        for raw_name in config.intents:
            name = intent_aliases.get(raw_name, raw_name)
            if hasattr(intents, name):
                setattr(intents, name, True)
        return intents


async def run_bot(config: BotConfig) -> None:
    """Entrypoint that wires together all components."""

    audio_pipeline = AudioPipeline(config.audio)
    wake_detector = WakeDetector(config.wake.wake_phrases)
    server = MCPServer(config)
    bot = VoiceBot(config, audio_pipeline, wake_detector, server.publish_transcript)
    server.attach_voice_bot(bot)

    bot_task = asyncio.create_task(bot.start(config.discord.token))
    server_task = asyncio.create_task(server.serve())
    try:
        await bot_task
    finally:
        await server.shutdown()
        with suppress(asyncio.CancelledError):
            await server_task
        await bot.close()
        if not bot_task.done():
            bot_task.cancel()
            with suppress(asyncio.CancelledError):
                await bot_task


__all__ = ["SegmentContext", "TranscriptPublisher", "VoiceBot", "run_bot"]
