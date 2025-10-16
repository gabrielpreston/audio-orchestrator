"""Discord client wiring for the Python voice bot."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum
from typing import Any

import discord
import httpx

from services.common.debug import get_debug_manager
from services.common.logging import get_logger

from .audio import AudioPipeline, AudioSegment, rms_from_pcm
from .config import BotConfig, DiscordConfig
from .mcp import MCPServer
from .orchestrator_client import OrchestratorClient
from .receiver import build_sink
from .transcription import TranscriptionClient, TranscriptResult
from .wake import WakeDetector

try:
    from discord.ext import voice_recv as _voice_recv
except ImportError:
    _voice_recv = None
else:
    recv_client_cls = getattr(_voice_recv, "VoiceRecvClient", None)
    if isinstance(recv_client_cls, type):
        discord.VoiceClient = recv_client_cls
    with suppress(OSError):
        discord.opus._load_default()

discord_voice_recv: Any | None = _voice_recv


@dataclass(slots=True)
class SegmentContext:
    """Metadata about a captured audio segment."""

    segment: AudioSegment
    guild_id: int
    channel_id: int


TranscriptPublisher = Callable[[dict[str, object]], Awaitable[None]]


def _truncate_text(value: str | None, *, limit: int = 120) -> str | None:
    if not value:
        return None
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3] + "..."


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
        self._logger = get_logger(__name__, service_name="discord")
        self._segment_queue: asyncio.Queue[SegmentContext] = asyncio.Queue()
        self._segment_task: asyncio.Task[None] | None = None
        self._idle_flush_task: asyncio.Task[None] | None = None
        self._shutdown = asyncio.Event()
        self._http_session: httpx.AsyncClient | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._voice_receivers: dict[int, object] = {}
        self._voice_contexts: dict[int, tuple[int, int]] = {}
        self._voice_join_locks: dict[int, asyncio.Lock] = {}
        self._voice_reconnect_tasks: dict[int, asyncio.Task[None]] = {}
        self._suppress_reconnect: set[int] = set()

        # Initialize orchestrator client
        self._orchestrator_client = OrchestratorClient()

        # Initialize debug manager
        self._debug_manager = get_debug_manager("discord")
        if discord_voice_recv is None:
            self._logger.critical(
                "voice.recv_extension_missing",
                message="discord-ext-voice-recv not available; voice receive disabled",
            )
            raise RuntimeError(
                "discord-ext-voice-recv not available; voice receive disabled"
            )

    async def setup_hook(self) -> None:
        self._loop = asyncio.get_running_loop()
        if self._http_session is None:
            timeout = httpx.Timeout(30.0, connect=10.0)
            self._http_session = httpx.AsyncClient(timeout=timeout)
        self._segment_task = asyncio.create_task(self._segment_consumer())
        self._idle_flush_task = asyncio.create_task(self._idle_flush_loop())

    async def close(self) -> None:
        self._shutdown.set()
        reconnect_tasks = list(self._voice_reconnect_tasks.values())
        self._voice_reconnect_tasks.clear()
        for task in reconnect_tasks:
            task.cancel()
        for task in reconnect_tasks:
            with suppress(asyncio.CancelledError):
                await task
        if self._segment_task:
            self._segment_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._segment_task
        if self._idle_flush_task:
            self._idle_flush_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._idle_flush_task
        disconnect_coros: list[Awaitable[None]] = []
        for voice_client in list(self.voice_clients):
            guild_id = voice_client.guild.id if voice_client.guild else None
            if guild_id is not None:
                self._stop_voice_receiver(guild_id, voice_client)
            disconnect_coros.append(self._disconnect_voice_client(voice_client))
        if disconnect_coros:
            await asyncio.gather(*disconnect_coros, return_exceptions=True)
        if self._http_session:
            await self._http_session.aclose()
        await super().close()

    async def on_ready(self) -> None:
        self._logger.info(
            "discord.ready",
            user=str(self.user),
            guilds=[guild.id for guild in self.guilds],
        )
        if self.config.discord.auto_join:
            try:
                await self.join_voice_channel(
                    self.config.discord.guild_id, self.config.discord.voice_channel_id
                )
            except Exception as exc:
                self._logger.error(
                    "discord.voice_auto_join_failed",
                    guild_id=self.config.discord.guild_id,
                    channel_id=self.config.discord.voice_channel_id,
                    error=str(exc),
                )
                self._schedule_voice_reconnect(
                    self.config.discord.guild_id,
                    self.config.discord.voice_channel_id,
                    reason="auto_join_failed",
                )

    async def join_voice_channel(
        self, guild_id: int, channel_id: int
    ) -> dict[str, object]:
        await self.wait_until_ready()
        guild = self.get_guild(guild_id)
        if not guild:
            raise ValueError(f"Guild {guild_id} not found")
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            raise ValueError(f"Channel {channel_id} is not a voice channel")

        lock = self._voice_join_locks.setdefault(guild_id, asyncio.Lock())
        async with lock:
            self._cancel_pending_reconnect(guild_id)
            voice_client = self._voice_client_for_guild(guild_id)
            recv_client_cls = getattr(discord_voice_recv, "VoiceRecvClient", None)
            if isinstance(recv_client_cls, type):
                desired_cls: type[discord.VoiceClient] = recv_client_cls
            else:
                desired_cls = discord.VoiceClient

            if (
                voice_client
                and voice_client.channel
                and voice_client.channel.id == channel_id
            ):
                if isinstance(recv_client_cls, type) and not isinstance(
                    voice_client, recv_client_cls
                ):
                    await voice_client.disconnect()
                    voice_client = None
                else:
                    self._logger.info(
                        "discord.voice_already_connected",
                        guild_id=guild_id,
                        channel_id=channel_id,
                    )
                    self._ensure_voice_receiver(voice_client)
                    return {
                        "status": "already_connected",
                        "guild_id": guild_id,
                        "channel_id": channel_id,
                    }

            timeout = max(1.0, self.config.discord.voice_connect_timeout_seconds)
            max_attempts = max(1, self.config.discord.voice_connect_max_attempts)
            base_backoff = max(
                0.5, self.config.discord.voice_reconnect_initial_backoff_seconds
            )
            max_backoff = max(
                base_backoff, self.config.discord.voice_reconnect_max_backoff_seconds
            )

            attempt = 0
            delay = 0.0
            last_exc: Exception | None = None
            while attempt < max_attempts:
                if delay > 0:
                    await asyncio.sleep(delay)
                attempt += 1
                connect_kwargs = {
                    "cls": desired_cls,
                    "timeout": timeout,
                    "reconnect": False,
                }
                try:
                    voice_client = self._voice_client_for_guild(guild_id)
                    if voice_client and voice_client.channel:
                        await voice_client.move_to(channel)
                    else:
                        voice_client = await channel.connect(**connect_kwargs)
                    if voice_client is None:
                        raise RuntimeError(
                            "Voice client unavailable after connect attempt"
                        )
                    if not voice_client.is_connected():
                        raise RuntimeError(
                            "Voice client reported disconnected immediately"
                        )
                    self._ensure_voice_receiver(voice_client)
                    self._logger.info(
                        "discord.voice_connected",
                        guild_id=guild_id,
                        channel_id=channel_id,
                        attempt=attempt,
                    )
                    return {
                        "status": "connected",
                        "guild_id": guild_id,
                        "channel_id": channel_id,
                    }
                except Exception as exc:
                    last_exc = exc
                    self._logger.warning(
                        "discord.voice_connect_retry",
                        guild_id=guild_id,
                        channel_id=channel_id,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        error=str(exc),
                    )
                    await self._cleanup_failed_voice_client(guild_id)
                    if attempt >= max_attempts:
                        break
                    exponential = base_backoff * (2 ** (attempt - 1))
                    delay = min(max_backoff, exponential) + random.uniform(
                        0, base_backoff
                    )  # noqa: S311 - jitter for retries, not cryptographic
                    continue

            self._logger.error(
                "discord.voice_connect_failed",
                guild_id=guild_id,
                channel_id=channel_id,
                attempts=max_attempts,
                error=str(last_exc) if last_exc else None,
            )
            if last_exc:
                raise last_exc
            raise RuntimeError("Voice connection attempts exhausted")

    async def leave_voice_channel(self, guild_id: int) -> dict[str, object]:
        await self.wait_until_ready()
        voice_client = self._voice_client_for_guild(guild_id)
        if not voice_client:
            self._logger.warning(
                "discord.voice_client_missing",
                guild_id=guild_id,
            )
            return {"status": "not_connected", "guild_id": guild_id}

        channel_id = voice_client.channel.id if voice_client.channel else None
        self._cancel_pending_reconnect(guild_id)
        self._suppress_reconnect.add(guild_id)
        try:
            self._stop_voice_receiver(guild_id, voice_client)
            await voice_client.disconnect()
        finally:
            self._suppress_reconnect.discard(guild_id)
        self._logger.info(
            "discord.voice_disconnected",
            guild_id=guild_id,
            channel_id=channel_id,
        )
        return {
            "status": "disconnected",
            "guild_id": guild_id,
            "channel_id": channel_id,
        }

    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if self.user is None or member.id != self.user.id:
            return
        guild_id = member.guild.id
        if guild_id in self._suppress_reconnect:
            return
        if self._shutdown.is_set():
            return
        if (
            not self.config.discord.auto_join
            or guild_id != self.config.discord.guild_id
        ):
            return
        target_channel_id = self.config.discord.voice_channel_id
        if after.channel is not None:
            return
        previous_channel_id = before.channel.id if before.channel else None
        if previous_channel_id is not None and previous_channel_id != target_channel_id:
            return
        self._logger.warning(
            "discord.voice_connection_lost",
            guild_id=guild_id,
            channel_id=previous_channel_id,
        )
        self._schedule_voice_reconnect(
            guild_id,
            target_channel_id,
            reason="voice_state_disconnected",
        )

    async def send_text_message(
        self, channel_id: int, content: str
    ) -> dict[str, object]:
        await self.wait_until_ready()
        channel = self.get_channel(channel_id)
        if channel is None:
            raise ValueError(f"Channel {channel_id} not found")
        if not isinstance(
            channel,
            (
                discord.TextChannel,
                discord.VoiceChannel,
                discord.StageChannel,
                discord.Thread,
            ),
        ):
            raise ValueError(f"Channel {channel_id} does not support text messages")
        message = await channel.send(content)
        channel_type = getattr(channel, "type", None)
        if isinstance(channel_type, Enum):
            channel_type_name = channel_type.name
        elif channel_type is None:
            channel_type_name = None
        else:
            channel_type_name = str(channel_type)
        self._logger.info(
            "discord.text_message_sent",
            channel_id=channel_id,
            message_id=message.id,
            channel_type=channel_type_name,
        )
        payload: dict[str, object] = {
            "status": "sent",
            "channel_id": channel_id,
            "message_id": message.id,
        }
        if channel_type_name:
            payload["channel_type"] = channel_type_name
        return payload

    async def play_audio_from_url(
        self,
        guild_id: int,
        channel_id: int,
        audio_url: str,
    ) -> dict[str, object]:
        await self.wait_until_ready()
        if not self._http_session:
            timeout = httpx.Timeout(30.0, connect=10.0)
            self._http_session = httpx.AsyncClient(timeout=timeout)
        from services.common.correlation import generate_manual_correlation_id

        context = SegmentContext(
            segment=AudioSegment(
                user_id=0,
                pcm=b"",
                start_timestamp=0.0,
                end_timestamp=0.0,
                correlation_id=generate_manual_correlation_id("discord", "play_audio"),
                frame_count=0,
                sample_rate=self.config.audio.input_sample_rate_hz,
            ),
            guild_id=guild_id,
            channel_id=channel_id,
        )
        await self._play_tts(audio_url, context)
        return {"status": "playing", "guild_id": guild_id, "channel_id": channel_id}

    async def ingest_voice_packet(
        self,
        user_id: int,
        pcm: bytes,
        frame_duration: float,
        sample_rate: int,
    ) -> None:
        """Entry point for voice receivers to feed PCM data into the pipeline."""

        voice_state = self._resolve_voice_state(user_id)
        if not voice_state or not voice_state.channel:
            self._logger.debug(
                "discord.voice_state_unavailable",
                user_id=user_id,
                pcm_bytes=len(pcm),
                frame_duration=frame_duration,
                sample_rate=sample_rate,
            )
            return

        guild_id = voice_state.channel.guild.id
        channel_id = voice_state.channel.id
        self._voice_contexts[user_id] = (guild_id, channel_id)

        rms = rms_from_pcm(pcm)
        segment = self.audio_pipeline.register_frame(
            user_id, pcm, rms, frame_duration, sample_rate
        )
        if not segment:
            return
        await self._enqueue_segment(segment, context=(guild_id, channel_id))

    async def _enqueue_segment(
        self,
        segment: AudioSegment,
        *,
        context: tuple[int, int] | None = None,
    ) -> None:
        if context is None:
            context = self._voice_contexts.get(segment.user_id)
        if context is None:
            self._logger.warning(
                "discord.voice_context_missing",
                user_id=segment.user_id,
            )
            return
        guild_id, channel_id = context
        segment_context = SegmentContext(
            segment=segment,
            guild_id=guild_id,
            channel_id=channel_id,
        )
        pending_segments = self._segment_queue.qsize()
        self._logger.debug(
            "voice.segment_enqueued",
            correlation_id=segment.correlation_id,
            user_id=segment.user_id,
            guild_id=segment_context.guild_id,
            channel_id=segment_context.channel_id,
            frames=segment.frame_count,
            duration=segment.duration,
            queue_depth=pending_segments + 1,
        )

        # Save debug audio segment
        self._save_debug_voice_segment(segment_context)

        await self._segment_queue.put(segment_context)

    def _resolve_voice_state(self, user_id: int) -> discord.VoiceState | None:
        for guild in self.guilds:
            member = guild.get_member(user_id)
            if member and member.voice and member.voice.channel:
                return member.voice
        return None

    async def _idle_flush_loop(self) -> None:
        """Periodically flush stale accumulators so silence gaps emit segments."""

        interval = max(self.config.audio.silence_timeout_seconds / 2.0, 0.1)
        interval = min(interval, 0.5)
        try:
            self._logger.debug(
                "voice.idle_flush_loop_started",
                interval=interval,
            )
            while not self._shutdown.is_set():
                segments = self.audio_pipeline.flush_inactive()
                for segment in segments:
                    await self._enqueue_segment(
                        segment,
                        context=self._voice_contexts.get(segment.user_id),
                    )
                try:
                    await asyncio.wait_for(self._shutdown.wait(), timeout=interval)
                except TimeoutError:
                    continue
        except asyncio.CancelledError:
            raise
        finally:
            self._logger.debug("voice.idle_flush_loop_stopped")

    async def _segment_consumer(self) -> None:
        await asyncio.sleep(0)
        async with TranscriptionClient(self.config.stt) as stt_client:
            while not self._shutdown.is_set():
                context = await self._segment_queue.get()
                try:
                    self._logger.debug(
                        "voice.segment_processing_start",
                        correlation_id=context.segment.correlation_id,
                        guild_id=context.guild_id,
                        channel_id=context.channel_id,
                        frames=context.segment.frame_count,
                    )
                    transcript = await stt_client.transcribe(context.segment)
                    self._logger.info(
                        "voice.segment_processing_complete",
                        correlation_id=transcript.correlation_id,
                        guild_id=context.guild_id,
                        channel_id=context.channel_id,
                        text_length=len(transcript.text),
                        confidence=transcript.confidence,
                    )
                    await self._handle_transcript(context, transcript)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self._logger.error(
                        "voice.segment_processing_failed",
                        guild_id=context.guild_id,
                        channel_id=context.channel_id,
                        correlation_id=context.segment.correlation_id,
                        error=str(exc),
                    )
                finally:
                    self._segment_queue.task_done()

    async def _handle_transcript(
        self,
        context: SegmentContext,
        transcript: TranscriptResult,
    ) -> None:
        detection = self._wake_detector.detect(context.segment, transcript.text)
        if not detection:
            self._logger.debug(
                "voice.segment_ignored",
                correlation_id=transcript.correlation_id,
                reason="wake_not_detected",
                transcript_preview=_truncate_text(transcript.text),
            )
            # Save debug data for ignored segments
            self._save_debug_ignored_segment(context, transcript)
            return

        payload: dict[str, object] = {
            "text": transcript.text,
            "user_id": context.segment.user_id,
            "channel_id": context.channel_id,
            "guild_id": context.guild_id,
            "correlation_id": transcript.correlation_id,
            "wake_phrase": detection.phrase,
            "timestamps": {
                "start": transcript.start_timestamp,
                "end": transcript.end_timestamp,
            },
            "language": transcript.language,
            "confidence": transcript.confidence,
            "frames": context.segment.frame_count,
        }
        if detection.confidence is not None:
            payload["wake_confidence"] = detection.confidence
        payload["wake_source"] = detection.source
        self._logger.info(
            "wake.detected",
            correlation_id=transcript.correlation_id,
            wake_phrase=detection.phrase,
            wake_confidence=detection.confidence,
            wake_source=detection.source,
            guild_id=context.guild_id,
            channel_id=context.channel_id,
        )

        # Save debug data for wake detection
        self._save_debug_wake_detection(context, transcript, detection)
        # Send transcript to orchestrator for processing
        try:
            orchestrator_result = await self._orchestrator_client.process_transcript(
                guild_id=str(context.guild_id),
                channel_id=str(context.channel_id),
                user_id=str(context.segment.user_id),
                transcript=transcript.text,
                correlation_id=transcript.correlation_id,
            )

            self._logger.info(
                "voice.transcript_sent_to_orchestrator",
                correlation_id=transcript.correlation_id,
                guild_id=context.guild_id,
                channel_id=context.channel_id,
                orchestrator_result=orchestrator_result,
            )

            # Save debug data for orchestrator communication
            self._save_debug_orchestrator_communication(
                context, transcript, orchestrator_result
            )

            # TODO: Handle orchestrator response (TTS audio, tool calls, etc.)
            # For now, just log the result

        except Exception as exc:
            self._logger.error(
                "voice.orchestrator_communication_failed",
                correlation_id=transcript.correlation_id,
                guild_id=context.guild_id,
                channel_id=context.channel_id,
                error=str(exc),
            )

        # Also publish to the original transcript publisher for compatibility
        await self._publish_transcript(payload)
        self._logger.info(
            "voice.transcript_published",
            correlation_id=transcript.correlation_id,
            guild_id=context.guild_id,
            channel_id=context.channel_id,
        )

    async def _play_tts(self, audio_url: str, context: SegmentContext) -> None:
        if not self._http_session:
            self._logger.warning("tts.http_session_missing")
            return
        voice_client = self._voice_client_for_guild(context.guild_id)
        if not voice_client:
            self._logger.warning(
                "tts.voice_client_missing",
                guild_id=context.guild_id,
            )
            return
        if voice_client.is_playing():
            voice_client.stop()
        try:
            # Use FFmpegPCMAudio for automatic format conversion
            # This handles the conversion from TTS format to Discord's required format
            audio_source = discord.FFmpegPCMAudio(audio_url)
            voice_client.play(audio_source)

            self._logger.info(
                "tts.audio_playback_started",
                audio_url=audio_url,
                guild_id=context.guild_id,
                channel_id=context.channel_id,
            )

            # Save debug data for TTS playback
            self._save_debug_tts_playback(context, audio_url)
        except Exception as exc:
            self._logger.error(
                "tts.playback_failed",
                audio_url=audio_url,
                guild_id=context.guild_id,
                channel_id=context.channel_id,
                error=str(exc),
            )

    def _voice_client_for_guild(self, guild_id: int) -> discord.VoiceClient | None:
        for voice_client in self.voice_clients:
            if voice_client.guild and voice_client.guild.id == guild_id:
                return voice_client
        return None

    def _cancel_pending_reconnect(self, guild_id: int) -> None:
        task = self._voice_reconnect_tasks.get(guild_id)
        if not task:
            return
        current_task = asyncio.current_task()
        if current_task is task:
            return
        self._voice_reconnect_tasks.pop(guild_id, None)
        task.cancel()

    def _schedule_voice_reconnect(
        self, guild_id: int, channel_id: int, *, reason: str
    ) -> None:
        if self._shutdown.is_set():
            return
        if guild_id in self._voice_reconnect_tasks:
            return
        if self._loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                return
        self._logger.info(
            "discord.voice_reconnect_scheduled",
            guild_id=guild_id,
            channel_id=channel_id,
            reason=reason,
        )
        task = self._loop.create_task(
            self._voice_reconnect_worker(guild_id, channel_id, reason)
        )
        self._voice_reconnect_tasks[guild_id] = task

        def _finalizer(completed: asyncio.Task[None], gid: int = guild_id) -> None:
            self._voice_reconnect_tasks.pop(gid, None)
            with suppress(Exception):
                completed.result()

        task.add_done_callback(_finalizer)

    async def _voice_reconnect_worker(
        self, guild_id: int, channel_id: int, reason: str
    ) -> None:
        base_backoff = max(
            0.5, self.config.discord.voice_reconnect_initial_backoff_seconds
        )
        max_backoff = max(
            base_backoff, self.config.discord.voice_reconnect_max_backoff_seconds
        )
        attempt = 0
        while not self._shutdown.is_set():
            attempt += 1
            try:
                await self.join_voice_channel(guild_id, channel_id)
            except Exception as exc:
                exponential = base_backoff * (2 ** max(0, attempt - 1))
                delay = min(max_backoff, exponential) + random.uniform(
                    0, base_backoff
                )  # noqa: S311 - jitter for retries, not cryptographic
                self._logger.warning(
                    "discord.voice_reconnect_retry",
                    guild_id=guild_id,
                    channel_id=channel_id,
                    attempt=attempt,
                    reason=reason,
                    error=str(exc),
                    next_delay=delay,
                )
                try:
                    await asyncio.wait_for(self._shutdown.wait(), timeout=delay)
                    return
                except TimeoutError:
                    continue
            else:
                self._logger.info(
                    "discord.voice_reconnect_success",
                    guild_id=guild_id,
                    channel_id=channel_id,
                    attempts=attempt,
                    reason=reason,
                )
                return

    def _ensure_voice_receiver(self, voice_client: discord.VoiceClient) -> None:
        if self._loop is None:
            self._logger.warning(
                "voice.receiver_loop_missing",
                guild_id=voice_client.guild.id if voice_client.guild else None,
            )
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
        except Exception:
            return
        try:
            voice_client.listen(receiver)
        except Exception as exc:
            self._logger.error(
                "voice.receiver_start_failed",
                guild_id=guild_id,
                channel_id=channel_id,
                error=str(exc),
            )
            return
        self._voice_receivers[guild_id] = receiver
        self._logger.info(
            "voice.receiver_started",
            guild_id=guild_id,
            channel_id=channel_id,
        )

    def _stop_voice_receiver(
        self,
        guild_id: int,
        voice_client: discord.VoiceClient | None,
    ) -> None:
        receiver = self._voice_receivers.pop(guild_id, None)
        if not receiver:
            return
        if voice_client:
            with suppress(Exception):
                voice_client.stop_listening()
        if hasattr(receiver, "cleanup"):
            with suppress(Exception):
                receiver.cleanup()
        self._logger.info(
            "voice.receiver_stopped",
            guild_id=guild_id,
            channel_id=(
                voice_client.channel.id
                if voice_client and voice_client.channel
                else None
            ),
        )

    async def _disconnect_voice_client(self, voice_client: discord.VoiceClient) -> None:
        channel_id = voice_client.channel.id if voice_client.channel else None
        try:
            await voice_client.disconnect(force=True)
            self._logger.info(
                "discord.voice_force_disconnected",
                guild_id=voice_client.guild.id if voice_client.guild else None,
                channel_id=channel_id,
            )
        except Exception as exc:
            self._logger.warning(
                "discord.voice_force_disconnect_exception",
                guild_id=voice_client.guild.id if voice_client.guild else None,
                channel_id=channel_id,
                error=str(exc),
            )

    async def _cleanup_failed_voice_client(self, guild_id: int) -> None:
        voice_client = self._voice_client_for_guild(guild_id)
        if not voice_client:
            return
        self._stop_voice_receiver(guild_id, voice_client)
        with suppress(Exception):
            await voice_client.disconnect(force=True)

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

    def _save_debug_voice_segment(self, context: SegmentContext) -> None:
        """Save debug data for voice segments."""
        try:
            correlation_id = context.segment.correlation_id

            # Save audio segment
            self._debug_manager.save_audio_file(
                correlation_id=correlation_id,
                audio_data=context.segment.pcm,
                filename_prefix="voice_segment",
                sample_rate=context.segment.sample_rate,
            )

            # Save segment metadata
            self._debug_manager.save_json_file(
                correlation_id=correlation_id,
                data={
                    "user_id": context.segment.user_id,
                    "guild_id": context.guild_id,
                    "channel_id": context.channel_id,
                    "start_timestamp": context.segment.start_timestamp,
                    "end_timestamp": context.segment.end_timestamp,
                    "duration": context.segment.duration,
                    "frame_count": context.segment.frame_count,
                    "sample_rate": context.segment.sample_rate,
                    "pcm_size_bytes": len(context.segment.pcm),
                },
                filename_prefix="voice_metadata",
            )

        except Exception as exc:
            self._logger.error(
                "discord.debug_voice_segment_save_failed",
                correlation_id=context.segment.correlation_id,
                error=str(exc),
            )

    def _save_debug_ignored_segment(
        self, context: SegmentContext, transcript: TranscriptResult
    ) -> None:
        """Save debug data for ignored segments (no wake word detected)."""
        try:
            correlation_id = transcript.correlation_id

            # Save transcript text
            self._debug_manager.save_text_file(
                correlation_id=correlation_id,
                content=f"Transcript: {transcript.text}\nConfidence: {transcript.confidence}\nLanguage: {transcript.language}",
                filename_prefix="ignored_transcript",
            )

            # Save ignored segment metadata
            self._debug_manager.save_json_file(
                correlation_id=correlation_id,
                data={
                    "user_id": context.segment.user_id,
                    "guild_id": context.guild_id,
                    "channel_id": context.channel_id,
                    "transcript": transcript.text,
                    "confidence": transcript.confidence,
                    "language": transcript.language,
                    "reason": "wake_not_detected",
                    "segment_duration": context.segment.duration,
                },
                filename_prefix="ignored_metadata",
            )

        except Exception as exc:
            self._logger.error(
                "discord.debug_ignored_segment_save_failed",
                correlation_id=transcript.correlation_id,
                error=str(exc),
            )

    def _save_debug_wake_detection(
        self, context: SegmentContext, transcript: TranscriptResult, detection
    ) -> None:
        """Save debug data for wake word detection."""
        try:
            correlation_id = transcript.correlation_id

            # Save wake detection details
            self._debug_manager.save_text_file(
                correlation_id=correlation_id,
                content=f"Wake Phrase: {detection.phrase}\nConfidence: {detection.confidence}\nSource: {detection.source}\nTranscript: {transcript.text}",
                filename_prefix="wake_detection",
            )

            # Save wake detection metadata
            self._debug_manager.save_json_file(
                correlation_id=correlation_id,
                data={
                    "user_id": context.segment.user_id,
                    "guild_id": context.guild_id,
                    "channel_id": context.channel_id,
                    "wake_phrase": detection.phrase,
                    "wake_confidence": detection.confidence,
                    "wake_source": detection.source,
                    "transcript": transcript.text,
                    "transcript_confidence": transcript.confidence,
                    "language": transcript.language,
                    "segment_duration": context.segment.duration,
                },
                filename_prefix="wake_metadata",
            )

        except Exception as exc:
            self._logger.error(
                "discord.debug_wake_detection_save_failed",
                correlation_id=transcript.correlation_id,
                error=str(exc),
            )

    def _save_debug_orchestrator_communication(
        self,
        context: SegmentContext,
        transcript: TranscriptResult,
        orchestrator_result: dict[str, Any],
    ) -> None:
        """Save debug data for orchestrator communication."""
        try:
            correlation_id = transcript.correlation_id

            # Save orchestrator response
            self._debug_manager.save_text_file(
                correlation_id=correlation_id,
                content=f"Orchestrator Response:\n{orchestrator_result}",
                filename_prefix="orchestrator_response",
            )

            # Save orchestrator communication metadata
            self._debug_manager.save_json_file(
                correlation_id=correlation_id,
                data={
                    "user_id": context.segment.user_id,
                    "guild_id": context.guild_id,
                    "channel_id": context.channel_id,
                    "transcript": transcript.text,
                    "orchestrator_result": orchestrator_result,
                    "timestamp": transcript.start_timestamp,
                },
                filename_prefix="orchestrator_metadata",
            )

        except Exception as exc:
            self._logger.error(
                "discord.debug_orchestrator_communication_save_failed",
                correlation_id=transcript.correlation_id,
                error=str(exc),
            )

    def _save_debug_tts_playback(self, context: SegmentContext, audio_url: str) -> None:
        """Save debug data for TTS playback."""
        try:
            correlation_id = context.segment.correlation_id

            # Save TTS playback details
            self._debug_manager.save_text_file(
                correlation_id=correlation_id,
                content=f"TTS Audio URL: {audio_url}\nGuild ID: {context.guild_id}\nChannel ID: {context.channel_id}",
                filename_prefix="tts_playback",
            )

            # Save TTS playback metadata
            self._debug_manager.save_json_file(
                correlation_id=correlation_id,
                data={
                    "user_id": context.segment.user_id,
                    "guild_id": context.guild_id,
                    "channel_id": context.channel_id,
                    "audio_url": audio_url,
                    "timestamp": context.segment.start_timestamp,
                },
                filename_prefix="tts_metadata",
            )

        except Exception as exc:
            self._logger.error(
                "discord.debug_tts_playback_save_failed",
                correlation_id=context.segment.correlation_id,
                error=str(exc),
            )


async def run_bot(config: BotConfig) -> None:
    """Entrypoint that wires together all components."""

    audio_pipeline = AudioPipeline(config.audio)
    wake_detector = WakeDetector(config.wake)
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
