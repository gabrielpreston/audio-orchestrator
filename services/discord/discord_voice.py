"""Discord client wiring for the Python voice bot."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum
import random
import time
from typing import Any

import discord
import httpx

from services.common.health import HealthManager
from services.common.structured_logging import get_logger

from .audio import AudioSegment, rms_from_pcm
from .audio_processor_wrapper import AudioProcessorWrapper
from .config import BotConfig, DiscordConfig
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
        # Log at module load to verify override
        _temp_logger = get_logger(__name__, service_name="discord")
        _temp_logger.info(
            "voice.recv_client_override_applied",
            recv_client_type=recv_client_cls.__name__,
            has_listen_method=hasattr(recv_client_cls, "listen"),
        )
    else:
        _temp_logger = get_logger(__name__, service_name="discord")
        _temp_logger.warning(
            "voice.recv_client_not_found",
            message="VoiceRecvClient class not found in voice_recv module",
        )
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
        audio_processor_wrapper: AudioProcessorWrapper,
        wake_detector: WakeDetector,
        transcript_publisher: TranscriptPublisher,
        metrics: dict[str, Any] | None = None,
        stt_health_check: Callable[[], Awaitable[bool]] | None = None,
        orchestrator_health_check: Callable[[], Awaitable[bool]] | None = None,
    ) -> None:
        intents = self._build_intents(config.discord)
        super().__init__(intents=intents)
        self.config = config
        self.audio_processor_wrapper = audio_processor_wrapper
        self._wake_detector = wake_detector
        self._publish_transcript = transcript_publisher
        self._logger = get_logger(__name__, service_name="discord")
        self._metrics = metrics or {}
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
        # Track last packet received timestamp per guild for health monitoring
        self._last_packet_timestamps: dict[int, float] = {}
        self._health_monitor_task: asyncio.Task[None] | None = None

        # Health manager for service resilience (follows project HealthManager pattern)
        self._health_manager = HealthManager("discord")

        # Register dependencies with HealthManager (standard pattern across all services)
        # Health checks are provided as callbacks from app.py which uses ResilientHTTPClient
        if stt_health_check is not None:
            self._health_manager.register_dependency("stt", stt_health_check)
        if orchestrator_health_check is not None:
            self._health_manager.register_dependency(
                "orchestrator", orchestrator_health_check
            )

        # Initialize orchestrator client
        self._orchestrator_client = OrchestratorClient()

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
        # Optional audio warm-up to avoid first-interaction latency spikes
        if self.config.telemetry.discord_warmup_audio:

            async def _do_warmup() -> None:
                import time

                import numpy as np

                from .transcription import _pcm_to_wav

                try:
                    # 200ms of silence at 48kHz mono int16
                    sample_rate = 48000
                    duration_s = 0.2
                    samples = int(sample_rate * duration_s)
                    pcm = (np.zeros(samples, dtype=np.int16)).tobytes()
                    start = time.perf_counter()
                    # Offload encode to thread pool
                    await asyncio.to_thread(_pcm_to_wav, pcm, sample_rate=sample_rate)
                    elapsed_ms = int((time.perf_counter() - start) * 1000)
                    self._logger.debug("audio.encode_warmup_ms", value=elapsed_ms)
                except Exception as exc:
                    self._logger.debug("audio.encode_warmup_failed", error=str(exc))

            # Fire and forget; do not block setup
            asyncio.create_task(_do_warmup())
        self._segment_task = asyncio.create_task(self._segment_consumer())
        self._idle_flush_task = asyncio.create_task(self._idle_flush_loop())
        # Start health monitoring task
        self._health_monitor_task = asyncio.create_task(self._health_monitor_loop())

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
        if self._health_monitor_task:
            self._health_monitor_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._health_monitor_task
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

    async def _validate_gateway_session(
        self, max_wait_seconds: float = 5.0, min_delay_seconds: float = 1.0
    ) -> bool:
        """Validate Gateway session is stable before voice connection.

        Waits for at least one heartbeat ACK (latency becomes finite),
        confirming the Gateway session is actively responding.

        Args:
            max_wait_seconds: Maximum time to wait for heartbeat validation
            min_delay_seconds: Minimum delay if validation times out

        Returns:
            True if session appears stable (heartbeat ACK received or min delay elapsed)
        """
        if not self.is_ready:
            return False

        start_time = asyncio.get_event_loop().time()
        check_interval = 0.1  # Check every 100ms

        # Wait for heartbeat ACK (latency becomes finite)
        while asyncio.get_event_loop().time() - start_time < max_wait_seconds:
            # Heartbeat ACK received - session is active
            # Additional check: ensure latency is reasonable (Discord Gateway typically < 60s)
            if (
                self.latency != float("inf")
                and self.latency > 0
                and self.latency < 60.0
            ):
                elapsed = asyncio.get_event_loop().time() - start_time
                self._logger.debug(
                    "discord.gateway_session_validated",
                    latency=self.latency,
                    elapsed_seconds=round(elapsed, 2),
                )
                return True

            await asyncio.sleep(check_interval)

        # Fallback: ensure minimum delay has elapsed
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed < min_delay_seconds:
            remaining = min_delay_seconds - elapsed
            self._logger.debug(
                "discord.gateway_session_min_delay",
                remaining_seconds=round(remaining, 2),
                message="Waiting for minimum delay before voice connection",
            )
            await asyncio.sleep(remaining)

        self._logger.warning(
            "discord.gateway_session_validation_timeout",
            elapsed_seconds=round(elapsed, 2),
            latency=self.latency,
            message="Proceeding with voice connection despite heartbeat validation timeout",
        )
        return True

    async def on_ready(self) -> None:
        """Called when Discord bot is ready and connected.

        Note: Dependencies are already checked before Discord connection in _start_discord_bot().
        """
        self._logger.info(
            "discord.ready",
            user=str(self.user),
            guilds=[guild.id for guild in self.guilds],
        )
        # Dependencies are already checked before Discord connection in _start_discord_bot()
        if self.config.discord.auto_join:
            # Validate Gateway session is stable before attempting voice connection
            # This prevents 4006 errors from session invalidation
            max_wait = getattr(
                self.config.discord,
                "voice_gateway_validation_timeout_seconds",
                5.0,
            )
            min_delay = getattr(
                self.config.discord,
                "voice_gateway_min_delay_seconds",
                1.0,
            )

            session_valid = await self._validate_gateway_session(
                max_wait_seconds=max_wait,
                min_delay_seconds=min_delay,
            )

            if not session_valid:
                self._logger.warning(
                    "discord.gateway_session_validation_failed",
                    latency=self.latency,
                    message="Gateway session validation failed, proceeding with voice connection anyway",
                )

            try:
                await self.join_voice_channel(
                    self.config.discord.guild_id,
                    self.config.discord.voice_channel_id,
                )
            except Exception as exc:
                self._logger.exception(
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

        self._logger.info(
            "discord.voice_join_attempt",
            guild_id=guild_id,
            channel_id=channel_id,
            channel_name=getattr(channel, "name", None),
        )

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
                0.5,
                self.config.discord.voice_reconnect_initial_backoff_seconds,
            )
            max_backoff = max(
                base_backoff,
                self.config.discord.voice_reconnect_max_backoff_seconds,
            )

            self._logger.info(
                "discord.voice_connect_starting",
                guild_id=guild_id,
                channel_id=channel_id,
                timeout=timeout,
                max_attempts=max_attempts,
                base_backoff=base_backoff,
                max_backoff=max_backoff,
            )

            attempt = 0
            delay = 0.0
            last_exc: Exception | None = None
            connection_start_time = time.time()
            while attempt < max_attempts:
                if delay > 0:
                    await asyncio.sleep(delay)
                attempt += 1
                attempt_start_time = time.time()
                self._logger.debug(
                    "discord.voice_connect_attempt",
                    guild_id=guild_id,
                    channel_id=channel_id,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    delay=delay,
                )
                connect_kwargs = {
                    "cls": desired_cls,
                    "timeout": timeout,
                    "reconnect": False,
                }
                try:
                    voice_client = self._voice_client_for_guild(guild_id)
                    if voice_client and voice_client.channel:
                        self._logger.debug(
                            "discord.voice_move_attempt",
                            guild_id=guild_id,
                            channel_id=channel_id,
                            from_channel_id=voice_client.channel.id,
                        )
                        await voice_client.move_to(channel)
                    else:
                        self._logger.debug(
                            "discord.voice_new_connect_attempt",
                            guild_id=guild_id,
                            channel_id=channel_id,
                            timeout=timeout,
                        )
                        voice_client = await channel.connect(**connect_kwargs)
                    if voice_client is None:
                        raise RuntimeError(
                            "Voice client unavailable after connect attempt"
                        )
                    if not voice_client.is_connected():
                        raise RuntimeError(
                            "Voice client reported disconnected immediately"
                        )

                    # CRITICAL: Verify client type and listen() method availability
                    actual_type = type(voice_client).__name__
                    has_listen = hasattr(voice_client, "listen")
                    recv_cls = (
                        getattr(discord_voice_recv, "VoiceRecvClient", None)
                        if discord_voice_recv
                        else None
                    )
                    is_voice_recv = (
                        isinstance(voice_client, recv_cls) if recv_cls else False
                    )

                    self._logger.info(
                        "voice.client_type_verification",
                        guild_id=guild_id,
                        channel_id=channel_id,
                        actual_client_type=actual_type,
                        desired_type=desired_cls.__name__
                        if isinstance(desired_cls, type)
                        else "unknown",
                        has_listen_method=has_listen,
                        is_voice_recv_client=is_voice_recv,
                        endpoint=getattr(voice_client, "endpoint", None),
                        session_id=getattr(voice_client, "session_id", None),
                    )

                    if not has_listen:
                        self._logger.error(
                            "voice.listen_method_missing",
                            guild_id=guild_id,
                            channel_id=channel_id,
                            voice_client_type=actual_type,
                            message="Voice client does not have listen() method - cannot receive audio",
                            exc_info=True,
                        )
                        # Continue anyway to see if _ensure_voice_receiver handles it

                    # Log voice connection state before setting up receiver
                    self._logger.debug(
                        "voice.connection_state_before_receiver",
                        guild_id=guild_id,
                        channel_id=channel_id,
                        is_connected=voice_client.is_connected(),
                        endpoint=getattr(voice_client, "endpoint", None),
                        session_id=getattr(voice_client, "session_id", None),
                    )

                    self._ensure_voice_receiver(voice_client)

                    connection_duration = time.time() - connection_start_time
                    attempt_duration = time.time() - attempt_start_time
                    self._logger.info(
                        "discord.voice_connected",
                        guild_id=guild_id,
                        channel_id=channel_id,
                        attempt=attempt,
                        connection_duration_ms=round(connection_duration * 1000, 2),
                        attempt_duration_ms=round(attempt_duration * 1000, 2),
                    )
                    return {
                        "status": "connected",
                        "guild_id": guild_id,
                        "channel_id": channel_id,
                    }
                except TimeoutError as exc:
                    last_exc = exc
                    attempt_duration = time.time() - attempt_start_time
                    exponential = base_backoff * (2 ** (attempt - 1))
                    delay = min(max_backoff, exponential) + random.uniform(
                        0, base_backoff
                    )  # noqa: S311 - jitter for retries, not cryptographic
                    self._logger.warning(
                        "discord.voice_connect_retry",
                        guild_id=guild_id,
                        channel_id=channel_id,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        error=str(exc),
                        error_type=type(exc).__name__,
                        error_category="timeout",
                        timeout_seconds=timeout,
                        attempt_duration_ms=round(attempt_duration * 1000, 2),
                        retry_delay_seconds=round(delay, 2),
                    )
                    await self._cleanup_failed_voice_client(guild_id)
                    if attempt >= max_attempts:
                        break
                    continue
                except Exception as exc:
                    last_exc = exc
                    attempt_duration = time.time() - attempt_start_time
                    # Discord API error 4006 (ConnectionClosed) is common and transient
                    # It typically indicates session invalidation during handshake
                    # Retry logic handles this automatically
                    is_connection_closed = "ConnectionClosed" in type(
                        exc
                    ).__name__ or "4006" in str(exc)
                    exponential = base_backoff * (2 ** (attempt - 1))
                    delay = min(max_backoff, exponential) + random.uniform(
                        0, base_backoff
                    )  # noqa: S311 - jitter for retries, not cryptographic
                    self._logger.warning(
                        "discord.voice_connect_retry",
                        guild_id=guild_id,
                        channel_id=channel_id,
                        attempt=attempt,
                        max_attempts=max_attempts,
                        error=str(exc),
                        error_type=type(exc).__name__,
                        error_category="connection_closed"
                        if is_connection_closed
                        else "other",
                        attempt_duration_ms=round(attempt_duration * 1000, 2),
                        retry_delay_seconds=round(delay, 2),
                    )
                    await self._cleanup_failed_voice_client(guild_id)
                    if attempt >= max_attempts:
                        break
                    continue

            total_duration = time.time() - connection_start_time
            self._logger.error(
                "discord.voice_connect_failed",
                guild_id=guild_id,
                channel_id=channel_id,
                attempts=max_attempts,
                total_duration_ms=round(total_duration * 1000, 2),
                error=str(last_exc) if last_exc else None,
                error_type=type(last_exc).__name__ if last_exc else None,
                exc_info=last_exc
                is not None,  # Only set exc_info if we have an exception
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

    async def ingest_voice_packet(
        self,
        user_id: int,
        pcm: bytes,
        frame_duration: float,
        sample_rate: int,
    ) -> None:
        """Entry point for voice receivers to feed PCM data into the pipeline."""

        voice_state = await self._resolve_voice_state(user_id)
        if not voice_state or not voice_state.channel:
            # Promote to INFO level for visibility (was DEBUG)
            self._logger.info(
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

        # Update packet timestamp for health monitoring
        self.update_packet_timestamp(guild_id)

        # Use int16-domain RMS to align with normalization target units
        frame_start_time = time.perf_counter()
        try:
            import audioop

            rms = float(audioop.rms(pcm, 2))
        except Exception:
            rms = rms_from_pcm(pcm)

        # Early PCM validation: Skip silent/zero-amplitude frames
        min_rms_threshold = getattr(self.config.audio, "min_audio_rms_threshold", 10.0)
        if rms < min_rms_threshold:
            # Sample logging to avoid verbosity (1% sample rate)
            import random

            if random.random() < 0.01:
                self._logger.debug(
                    "voice.silent_frame_skipped",
                    user_id=user_id,
                    rms=rms,
                    threshold=min_rms_threshold,
                )
            return  # Skip processing silent frame

        # Process frame with audio processor wrapper
        try:
            segment = await self.audio_processor_wrapper.register_frame_async(
                user_id, pcm, rms, frame_duration, sample_rate
            )
            frame_processing_time = time.perf_counter() - frame_start_time
            if frame_processing_time > 0.050:  # Log if processing takes > 50ms
                self._logger.debug(
                    "voice.frame_processing_slow",
                    user_id=user_id,
                    processing_time_ms=round(frame_processing_time * 1000, 2),
                    frame_duration=frame_duration,
                    sample_rate=sample_rate,
                )
        except Exception as exc:
            frame_processing_time = time.perf_counter() - frame_start_time
            self._logger.exception(
                "voice.frame_processing_failed",
                user_id=user_id,
                error=str(exc),
                processing_time_ms=round(frame_processing_time * 1000, 2),
            )
            return
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
        queue_depth_after = pending_segments + 1
        queue_threshold = 10  # Log warning if queue depth exceeds this

        self._logger.debug(
            "voice.segment_enqueued",
            correlation_id=segment.correlation_id,
            user_id=segment.user_id,
            guild_id=segment_context.guild_id,
            channel_id=segment_context.channel_id,
            frames=segment.frame_count,
            duration=segment.duration,
            queue_depth=queue_depth_after,
        )

        # Log warning if queue depth exceeds threshold
        if queue_depth_after > queue_threshold:
            self._logger.warning(
                "voice.queue_depth_high",
                correlation_id=segment.correlation_id,
                queue_depth=queue_depth_after,
                threshold=queue_threshold,
                message=f"Queue depth ({queue_depth_after}) exceeds threshold ({queue_threshold})",
            )

        # Save debug audio segment

        await self._segment_queue.put(segment_context)

    async def _resolve_voice_state(self, user_id: int) -> discord.VoiceState | None:
        """Resolve voice state for user, fetching member if not cached."""
        for guild in self.guilds:
            member = guild.get_member(user_id)
            if member is None:
                # Member not cached - fetch explicitly
                self._logger.debug(
                    "voice.member_not_cached",
                    guild_id=guild.id,
                    user_id=user_id,
                )
                try:
                    member = await guild.fetch_member(user_id)
                    self._logger.debug(
                        "voice.member_fetched",
                        guild_id=guild.id,
                        user_id=user_id,
                    )
                except (discord.NotFound, discord.HTTPException) as exc:
                    self._logger.debug(
                        "voice.member_fetch_failed",
                        guild_id=guild.id,
                        user_id=user_id,
                        error=str(exc),
                    )
                    continue

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
                segments = self.audio_processor_wrapper.flush_inactive()
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
        """Consumer that checks dependencies via HealthManager (standard pattern).

        Uses HealthManager.check_ready() to verify dependencies are available before processing.
        This follows the same pattern as all other services in the project.
        """
        self._logger.info(
            "voice.segment_consumer_starting",
            message="Segment consumer task starting",
        )
        # Wait for dependencies to be ready (aligned with HealthManager pattern)
        # HealthManager uses ResilientHTTPClient with exponential backoff and caching
        timeout = 300.0
        start = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start < timeout:
            if await self._health_manager.check_ready():
                self._logger.info("service.dependencies_ready")
                break
            await asyncio.sleep(2.0)
        else:
            self._logger.error(
                "service.dependency_timeout",
                timeout=timeout,
                message="Dependencies not ready within timeout, consumer exiting",
                exc_info=True,
            )
            return

        self._logger.info(
            "voice.segment_consumer_entering_loop",
            message="Dependencies ready, entering segment processing loop",
        )
        await asyncio.sleep(0)
        try:
            async with TranscriptionClient(
                self.config.stt, metrics=self._metrics
            ) as stt_client:
                self._logger.debug(
                    "voice.segment_consumer_stt_client_ready",
                    message="STT client context manager entered successfully",
                )
                last_heartbeat = asyncio.get_event_loop().time()
                heartbeat_interval = 60.0  # Log heartbeat every 60 seconds

                while not self._shutdown.is_set():
                    queue_depth = self._segment_queue.qsize()
                    self._logger.debug(
                        "voice.segment_consumer_waiting_for_segment",
                        queue_depth=queue_depth,
                        message="Waiting for segment from queue",
                    )
                    context = await self._segment_queue.get()
                    self._logger.debug(
                        "voice.segment_consumer_segment_received",
                        correlation_id=context.segment.correlation_id,
                        queue_depth_remaining=self._segment_queue.qsize(),
                        message="Segment received from queue",
                    )

                    # Periodic heartbeat logging
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_heartbeat >= heartbeat_interval:
                        self._logger.info(
                            "voice.segment_consumer_heartbeat",
                            queue_depth=self._segment_queue.qsize(),
                            message="Segment consumer heartbeat - still running",
                        )
                        last_heartbeat = current_time

                    # Bind correlation ID to logger for this segment before try block
                    # This ensures logger is available for all error paths
                    segment_logger = self._logger.bind(
                        correlation_id=context.segment.correlation_id
                    )

                    try:
                        # Get circuit breaker stats for logging
                        circuit_stats = stt_client.get_circuit_stats()
                        segment_logger.debug(
                            "voice.segment_processing_start",
                            guild_id=context.guild_id,
                            channel_id=context.channel_id,
                            frames=context.segment.frame_count,
                            stt_circuit_state=circuit_stats.get("state", "unknown"),
                            stt_circuit_available=circuit_stats.get("available", True),
                            stt_circuit_failure_count=circuit_stats.get(
                                "failure_count", 0
                            ),
                            stt_circuit_success_count=circuit_stats.get(
                                "success_count", 0
                            ),
                            queue_depth_at_start=self._segment_queue.qsize(),
                        )
                        transcript = await stt_client.transcribe(context.segment)

                        if transcript is None:
                            # STT unavailable - drop segment
                            segment_logger.info(
                                "voice.segment_dropped_stt_unavailable",
                                guild_id=context.guild_id,
                                channel_id=context.channel_id,
                            )
                            # NOTE: Future enhancement - send pre-canned text response when orchestrator unavailable
                            # Requires implementing text message sending capability in Discord bot
                            # await self._send_fallback_response(context, "Voice processing unavailable")
                            continue

                        # Process transcript normally
                        segment_logger.info(
                            "voice.segment_processing_complete",
                            guild_id=context.guild_id,
                            channel_id=context.channel_id,
                            text_length=len(transcript.text),
                            confidence=transcript.confidence,
                            pre_stt_ms=transcript.pre_stt_encode_ms,
                            stt_ms=transcript.stt_latency_ms,
                        )
                        await self._handle_transcript(context, transcript)
                    except asyncio.CancelledError:
                        self._logger.info(
                            "voice.segment_consumer_cancelled",
                            message="Segment consumer task cancelled",
                        )
                        raise
                    except Exception as exc:
                        segment_logger.exception(
                            "voice.segment_processing_failed",
                            guild_id=context.guild_id,
                            channel_id=context.channel_id,
                            error=str(exc),
                        )
                    finally:
                        self._segment_queue.task_done()
        except Exception as exc:
            self._logger.exception(
                "voice.segment_consumer_stt_context_failed",
                error=str(exc),
                message="Failed to enter or exit STT client context manager",
            )

    async def _handle_transcript(
        self,
        context: SegmentContext,
        transcript: TranscriptResult,
    ) -> None:
        # Bind correlation ID to logger for this transcript
        from services.common.structured_logging import bind_correlation_id

        transcript_logger = bind_correlation_id(self._logger, transcript.correlation_id)

        # Log wake detection attempt with latency
        # Offload wake detection to thread pool to prevent blocking event loop
        wake_detection_start = time.perf_counter()
        try:
            detection = await asyncio.to_thread(
                self._wake_detector.detect, context.segment, transcript.text
            )
            wake_detection_latency = time.perf_counter() - wake_detection_start
        except Exception as exc:
            wake_detection_latency = time.perf_counter() - wake_detection_start
            transcript_logger.warning(
                "voice.wake_detection_failed",
                error=str(exc),
                latency_ms=round(wake_detection_latency * 1000, 2),
                exc_info=True,
                message="Wake detection failed, continuing without wake phrase",
            )
            detection = None

        transcript_logger.debug(
            "voice.wake_detection_result",
            detected=bool(detection),
            wake_phrase=detection.phrase if detection else None,
            wake_confidence=detection.confidence if detection else None,
            wake_source=detection.source if detection else None,
            transcript_preview=_truncate_text(transcript.text),
            wake_enabled=self._wake_detector._config.enabled,
            latency_ms=round(wake_detection_latency * 1000, 2)
            if detection or wake_detection_latency > 0
            else None,
        )

        if not detection:
            transcript_logger.debug(
                "voice.segment_ignored",
                reason="wake_not_detected",
                transcript_preview=_truncate_text(transcript.text),
            )
            # Save debug data for ignored segments
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
        transcript_logger.info(
            "wake.detected",
            wake_phrase=detection.phrase,
            wake_confidence=detection.confidence,
            wake_source=detection.source,
            guild_id=context.guild_id,
            channel_id=context.channel_id,
        )

        # Save debug data for wake detection
        # Send transcript to orchestrator for processing
        orchestrator_start = time.perf_counter()
        try:
            orchestrator_result = await self._orchestrator_client.process_transcript(
                guild_id=str(context.guild_id),
                channel_id=str(context.channel_id),
                user_id=str(context.segment.user_id),
                transcript=transcript.text,
                correlation_id=transcript.correlation_id,
            )
            orchestrator_latency = time.perf_counter() - orchestrator_start

            transcript_logger.info(
                "voice.transcript_sent_to_orchestrator",
                guild_id=context.guild_id,
                channel_id=context.channel_id,
                orchestrator_result=orchestrator_result,
                latency_ms=round(orchestrator_latency * 1000, 2),
            )

            # Save debug data for orchestrator communication

            # Handle orchestrator response (audio playback, text fallback, etc.)
            if orchestrator_result and orchestrator_result.get("success"):
                # Extract audio data if available
                audio_data_b64 = orchestrator_result.get("audio_data")
                audio_format = orchestrator_result.get("audio_format", "wav")
                response_text = orchestrator_result.get("response_text")

                if audio_data_b64:
                    # Decode base64 audio data
                    import base64

                    try:
                        audio_decode_start = time.perf_counter()
                        audio_bytes = base64.b64decode(audio_data_b64)
                        audio_decode_time = time.perf_counter() - audio_decode_start
                        transcript_logger.info(
                            "voice.audio_received_from_orchestrator",
                            audio_size=len(audio_bytes),
                            audio_format=audio_format,
                            correlation_id=transcript.correlation_id,
                            decode_time_ms=round(audio_decode_time * 1000, 2),
                        )

                        # Play audio to Discord voice channel
                        voice_client = self._voice_client_for_guild(context.guild_id)
                        if voice_client and voice_client.is_connected():
                            await self._play_audio_to_voice(
                                voice_client,
                                audio_bytes,
                                correlation_id=transcript.correlation_id,
                            )
                        else:
                            transcript_logger.warning(
                                "voice.audio_playback_skipped",
                                reason="voice_client_not_connected",
                                correlation_id=transcript.correlation_id,
                            )
                            # Fallback to text message if voice not connected
                            if response_text:
                                await self._send_fallback_text_response(
                                    context, response_text, transcript.correlation_id
                                )

                    except Exception as audio_exc:
                        transcript_logger.exception(
                            "voice.audio_playback_failed",
                            error=str(audio_exc),
                            correlation_id=transcript.correlation_id,
                        )
                        # Fallback to text message on audio playback failure
                        if response_text:
                            await self._send_fallback_text_response(
                                context, response_text, transcript.correlation_id
                            )
                elif response_text:
                    # No audio, but we have text - send as text message
                    transcript_logger.info(
                        "voice.text_response_received",
                        text_length=len(response_text),
                        correlation_id=transcript.correlation_id,
                    )
                    await self._send_fallback_text_response(
                        context, response_text, transcript.correlation_id
                    )

        except Exception as exc:
            transcript_logger.exception(
                "voice.orchestrator_communication_failed",
                guild_id=context.guild_id,
                channel_id=context.channel_id,
                error=str(exc),
            )

        # Also publish to the original transcript publisher for compatibility
        await self._publish_transcript(payload)
        transcript_logger.info(
            "voice.transcript_published",
            guild_id=context.guild_id,
            channel_id=context.channel_id,
        )

    def _voice_client_for_guild(self, guild_id: int) -> discord.VoiceClient | None:
        for voice_client in self.voice_clients:
            if voice_client.guild and voice_client.guild.id == guild_id:
                return voice_client
        return None

    async def _play_audio_to_voice(
        self,
        voice_client: discord.VoiceClient,
        audio_bytes: bytes,
        *,
        correlation_id: str | None = None,
    ) -> None:
        """Play audio bytes to Discord voice channel.

        Args:
            voice_client: Discord voice client to play audio on
            audio_bytes: Audio data as bytes (WAV format expected)
            correlation_id: Correlation ID for logging
        """
        if not voice_client or not voice_client.is_connected():
            self._logger.warning(
                "voice.audio_playback_skipped",
                reason="voice_client_not_connected",
                correlation_id=correlation_id,
            )
            return

        try:
            import io

            # Create an in-memory file-like object from the audio bytes
            audio_source = discord.FFmpegPCMAudio(
                source=io.BytesIO(audio_bytes),
                pipe=True,
            )

            # Play the audio
            voice_client.play(
                audio_source,
                after=lambda error: self._playback_finished(error, correlation_id),
            )

            self._logger.info(
                "voice.audio_playback_started",
                audio_size=len(audio_bytes),
                correlation_id=correlation_id,
            )

        except Exception as exc:
            self._logger.exception(
                "voice.audio_playback_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                correlation_id=correlation_id,
            )
            raise

    def _playback_finished(
        self, error: Exception | None, correlation_id: str | None
    ) -> None:
        """Callback when audio playback finishes.

        Args:
            error: Error if playback failed, None if successful
            correlation_id: Correlation ID for logging
        """
        if error:
            self._logger.error(
                "voice.audio_playback_error",
                error=str(error),
                error_type=type(error).__name__,
                correlation_id=correlation_id,
                exc_info=True,
            )
        else:
            self._logger.debug(
                "voice.audio_playback_completed",
                correlation_id=correlation_id,
            )

    async def _send_fallback_text_response(
        self,
        context: SegmentContext,
        text: str,
        correlation_id: str | None = None,
    ) -> None:
        """Send text response as fallback when audio playback is not available.

        Args:
            context: Segment context with guild and channel IDs
            text: Text to send
            correlation_id: Correlation ID for logging
        """
        try:
            # Try to send text message to the channel
            await self.send_text_message(context.channel_id, text)
            self._logger.info(
                "voice.fallback_text_sent",
                channel_id=context.channel_id,
                text_length=len(text),
                correlation_id=correlation_id,
            )
        except Exception as exc:
            self._logger.exception(
                "voice.fallback_text_failed",
                error=str(exc),
                channel_id=context.channel_id,
                correlation_id=correlation_id,
            )

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
            0.5,
            self.config.discord.voice_reconnect_initial_backoff_seconds,
        )
        max_backoff = max(
            base_backoff,
            self.config.discord.voice_reconnect_max_backoff_seconds,
        )
        attempt = 0
        while not self._shutdown.is_set():
            attempt += 1
            try:
                await self.join_voice_channel(guild_id, channel_id)
            except Exception as exc:
                exponential = base_backoff * (2 ** max(0, attempt - 1))
                delay = min(max_backoff, exponential) + random.uniform(0, base_backoff)  # noqa: S311 - jitter for retries, not cryptographic
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

    def update_packet_timestamp(self, guild_id: int) -> None:
        """Update the last packet received timestamp for a guild.

        Called by receiver when packets are successfully processed.
        Used by health monitoring to detect PacketRouter crashes.

        Args:
            guild_id: Discord guild ID
        """
        self._last_packet_timestamps[guild_id] = time.time()

    async def _health_monitor_loop(self) -> None:
        """Periodic health check to detect PacketRouter crashes.

        Monitors packet reception timestamps and triggers reconnection
        when no packets are received for the configured timeout duration.
        """
        check_interval = 1.0  # Check every 1 second
        while not self._shutdown.is_set():
            try:
                await asyncio.sleep(check_interval)

                if self._shutdown.is_set():
                    break

                current_time = time.time()
                timeout = self.config.discord.voice_health_monitor_timeout_s

                # Check each guild for stale connections
                for guild_id, last_packet_time in list(
                    self._last_packet_timestamps.items()
                ):
                    time_since_last_packet = current_time - last_packet_time

                    if time_since_last_packet > timeout:
                        # Check if voice client is still connected (indicates PacketRouter crash)
                        voice_client = self._voice_client_for_guild(guild_id)
                        if voice_client and voice_client.is_connected():
                            # Voice client is connected but no packets received = PacketRouter crash
                            channel_id = (
                                voice_client.channel.id
                                if voice_client.channel
                                else None
                            )
                            self._logger.warning(
                                "discord.voice_health_monitor_timeout",
                                guild_id=guild_id,
                                channel_id=channel_id,
                                time_since_last_packet=time_since_last_packet,
                                timeout=timeout,
                                reason="packet_router_crashed",
                            )

                            # Trigger existing reconnection logic
                            if channel_id and guild_id not in self._suppress_reconnect:
                                self._schedule_voice_reconnect(
                                    guild_id,
                                    channel_id,
                                    reason="packet_router_crashed",
                                )

                            # Clear timestamp to avoid repeated triggers
                            self._last_packet_timestamps.pop(guild_id, None)

                # Clean up timestamps for disconnected guilds
                for guild_id in list(self._last_packet_timestamps.keys()):
                    voice_client = self._voice_client_for_guild(guild_id)
                    if not voice_client or not voice_client.is_connected():
                        self._last_packet_timestamps.pop(guild_id, None)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._logger.exception(
                    "discord.health_monitor_error",
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                # Continue monitoring despite errors
                await asyncio.sleep(check_interval)

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
            self._logger.warning(
                "voice.receiver_skip_missing_context",
                guild_id=guild_id,
                channel_id=channel_id,
                has_guild=voice_client.guild is not None,
                has_channel=voice_client.channel is not None,
            )
            return
        if guild_id in self._voice_receivers:
            self._logger.debug(
                "voice.receiver_already_registered",
                guild_id=guild_id,
                channel_id=channel_id,
            )
            return

        # Create receiver sink
        try:
            assert self._loop is not None
            receiver = build_sink(self._loop, self.ingest_voice_packet)

            # Log receiver creation
            self._logger.debug(
                "voice.receiver_created",
                guild_id=guild_id,
                channel_id=channel_id,
                receiver_type=type(receiver).__name__,
            )
        except Exception as exc:
            self._logger.exception(
                "voice.receiver_creation_failed",
                guild_id=guild_id,
                channel_id=channel_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return

        # Attach receiver to voice client
        try:
            # CRITICAL: Verify listen() method exists before calling
            if not hasattr(voice_client, "listen"):
                self._logger.error(
                    "voice.listen_method_missing_in_attach",
                    guild_id=guild_id,
                    channel_id=channel_id,
                    voice_client_type=type(voice_client).__name__,
                    available_methods=[
                        m
                        for m in dir(voice_client)
                        if not m.startswith("_")
                        and callable(getattr(voice_client, m, None))
                    ],
                    message="Cannot attach receiver - listen() method does not exist",
                    exc_info=True,
                )
                return

            # Log voice client state before attaching
            self._logger.info(
                "voice.attaching_receiver",
                guild_id=guild_id,
                channel_id=channel_id,
                voice_client_connected=voice_client.is_connected(),
                voice_client_type=type(voice_client).__name__,
                receiver_type=type(receiver).__name__,
                endpoint=getattr(voice_client, "endpoint", None),
                has_listen_method=hasattr(voice_client, "listen"),
            )

            voice_client.listen(receiver)

            # Initialize packet timestamp for health monitoring
            self.update_packet_timestamp(guild_id)

            # Log successful attachment at INFO level for visibility
            self._logger.info(
                "voice.receiver_attached",
                guild_id=guild_id,
                channel_id=channel_id,
                voice_client_type=type(voice_client).__name__,
                receiver_type=type(receiver).__name__,
            )
        except Exception as exc:
            self._logger.exception(
                "voice.receiver_start_failed",
                guild_id=guild_id,
                channel_id=channel_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return

        self._voice_receivers[guild_id] = receiver
        self._logger.info(
            "voice.receiver_started",
            guild_id=guild_id,
            channel_id=channel_id,
        )

        # Log voice client state after successful attachment
        self._logger.debug(
            "voice.client_state_after_attachment",
            guild_id=guild_id,
            channel_id=channel_id,
            is_connected=voice_client.is_connected(),
            receiver_registered=guild_id in self._voice_receivers,
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


async def run_bot(config: BotConfig) -> None:
    """Entrypoint that wires together all components."""

    wake_detector = WakeDetector(config.wake)
    audio_processor_wrapper = AudioProcessorWrapper(
        config.audio, config.telemetry, wake_detector=wake_detector
    )

    # Create dummy transcript publisher for standalone bot mode
    async def dummy_transcript_publisher(transcript_data: dict[str, Any]) -> None:
        """Dummy transcript publisher for standalone bot mode."""
        logger = get_logger(__name__, service_name="discord")
        logger.info("discord.transcript_received", **transcript_data)

    bot = VoiceBot(
        config, audio_processor_wrapper, wake_detector, dummy_transcript_publisher
    )

    bot_task = asyncio.create_task(bot.start(config.discord.token))
    try:
        await bot_task
    finally:
        await bot.close()
        if not bot_task.done():
            bot_task.cancel()
            with suppress(asyncio.CancelledError):
                await bot_task


__all__ = ["SegmentContext", "TranscriptPublisher", "VoiceBot", "run_bot"]
