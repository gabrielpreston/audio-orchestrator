"""Helpers for bridging discord-ext-voice-recv sinks into the audio pipeline."""

from __future__ import annotations

import asyncio
import importlib
import time
from collections import deque
from collections.abc import Callable, Coroutine
from concurrent.futures import Future as ThreadFuture
from typing import Any

from structlog.stdlib import BoundLogger

from services.common.logging import get_logger

voice_recv: Any | None
try:
    voice_recv = importlib.import_module("discord.ext.voice_recv")
except ImportError as exc:  # pragma: no cover - handled at runtime
    voice_recv = None
    _IMPORT_ERROR: ImportError | None = exc
else:
    _IMPORT_ERROR = None

FrameCallback = Callable[[int, bytes, float, int], Coroutine[Any, Any, None]]

_LOGGER: BoundLogger | None = None


def _get_logger() -> BoundLogger:
    global _LOGGER
    if _LOGGER is None:
        _LOGGER = get_logger(__name__, service_name="discord")
    return _LOGGER


class BufferedVoiceSink:
    """Custom sink that buffers RTP packets for unknown SSRCs until user mapping arrives."""

    def __init__(self, loop: asyncio.AbstractEventLoop, callback: FrameCallback):
        self._loop = loop
        self._callback = callback
        self._logger = _get_logger()

        # Buffer for unknown SSRCs (max 5 seconds worth of packets)
        self._unknown_ssrc_buffers: dict[int, deque[tuple[object, Any]]] = {}
        self._logged_unknown_ssrcs: set[int] = set()
        self._buffer_expiry: dict[int, float] = {}
        self._max_buffer_packets = 250  # ~5 seconds at 50 packets/second
        self._buffer_timeout = 5.0  # seconds

        # Track when we first see each SSRC
        self._ssrc_first_seen: dict[int, float] = {}

    def _cleanup_expired_buffers(self) -> None:
        """Remove expired buffers for SSRCs that never got user mapping."""
        current_time = time.monotonic()
        expired_ssrcs = [
            ssrc
            for ssrc, expiry in self._buffer_expiry.items()
            if current_time > expiry
        ]
        for ssrc in expired_ssrcs:
            buffer_size = len(self._unknown_ssrc_buffers.get(ssrc, []))
            if buffer_size > 0:
                self._logger.debug(
                    "voice.buffer_expired",
                    ssrc=ssrc,
                    buffered_packets=buffer_size,
                    duration=current_time
                    - self._ssrc_first_seen.get(ssrc, current_time),
                )
            self._unknown_ssrc_buffers.pop(ssrc, None)
            self._buffer_expiry.pop(ssrc, None)
            self._ssrc_first_seen.pop(ssrc, None)

    def _handle_packet(self, user: object | None, data: Any) -> None:
        """Handle incoming RTP packet - either process immediately or buffer."""
        # Extract user_id and SSRC info
        user_id = getattr(user, "id", None) if user else getattr(data, "user_id", None)
        ssrc = getattr(data, "ssrc", None)

        # If we have a user_id, process immediately
        if user_id is not None:
            # Log SSRC mapping when we first see a user
            if ssrc and ssrc not in self._logged_unknown_ssrcs:
                self._logger.info(
                    "voice.ssrc_mapping_received",
                    ssrc=ssrc,
                    user_id=user_id,
                    buffered_packets=len(self._unknown_ssrc_buffers.get(ssrc, [])),
                )

            # Check if we have buffered packets for this user's SSRC
            if ssrc and ssrc in self._unknown_ssrc_buffers:
                buffered_packets = self._unknown_ssrc_buffers[ssrc]
                self._logger.info(
                    "voice.buffered_packets_flushed",
                    ssrc=ssrc,
                    user_id=user_id,
                    buffered_packets=len(buffered_packets),
                )

                # Process buffered packets first
                for buffered_user, buffered_data in buffered_packets:
                    self._process_packet(buffered_user, buffered_data)

                # Clean up buffer
                self._unknown_ssrc_buffers.pop(ssrc, None)
                self._buffer_expiry.pop(ssrc, None)
                self._ssrc_first_seen.pop(ssrc, None)

            # Process current packet
            self._process_packet(user, data)
            return

        # No user_id - buffer the packet if we have SSRC info
        if ssrc is not None:
            current_time = time.monotonic()

            # Track first time we see this SSRC
            if ssrc not in self._ssrc_first_seen:
                self._ssrc_first_seen[ssrc] = current_time
                # Log only first occurrence per SSRC to reduce spam
                if ssrc not in self._logged_unknown_ssrcs:
                    self._logger.debug("voice.first_packet_unknown_ssrc", ssrc=ssrc)
                    self._logged_unknown_ssrcs.add(ssrc)

            # Clean up expired buffers periodically
            if len(self._unknown_ssrc_buffers) > 10:  # Only when we have many buffers
                self._cleanup_expired_buffers()

            # Add to buffer
            buffer = self._unknown_ssrc_buffers.setdefault(ssrc, deque())
            buffer.append((user, data))
            self._buffer_expiry[ssrc] = current_time + self._buffer_timeout

            # Limit buffer size
            while len(buffer) > self._max_buffer_packets:
                buffer.popleft()

            # Log buffer status occasionally
            if len(buffer) % 50 == 0:  # Every 50 packets
                self._logger.debug(
                    "voice.buffer_status",
                    ssrc=ssrc,
                    buffered_packets=len(buffer),
                    buffer_age=current_time - self._ssrc_first_seen[ssrc],
                )
        else:
            # No SSRC info - just log and drop
            self._logger.debug("voice.receiver_unknown_user")

    def _process_packet(self, user: object | None, data: Any) -> None:
        """Process a single packet through the audio pipeline."""
        pcm = getattr(data, "decoded_data", None) or getattr(data, "pcm", None)
        if not pcm:
            return

        user_id = getattr(user, "id", None) if user else getattr(data, "user_id", None)
        if user_id is None:
            self._logger.debug("voice.receiver_unknown_user")
            return

        sample_rate = (
            getattr(data, "sample_rate", None)
            or getattr(data, "sampling_rate", None)
            or 48000
        )
        frame_count = len(pcm) // 2  # 16-bit mono
        duration = float(frame_count) / float(sample_rate) if sample_rate else 0.0

        # Note: Removed excessive PCM frame logging that was creating 97% of log volume
        # RMS and sample rate are already tracked in VAD decisions with proper sampling

        future: ThreadFuture[None] = asyncio.run_coroutine_threadsafe(
            self._callback(user_id, pcm, duration, int(sample_rate)),
            self._loop,
        )
        future.add_done_callback(_consume_result)

    def _calculate_rms(self, pcm: bytes) -> float:
        """Calculate RMS for PCM data."""
        if not pcm:
            return 0.0
        try:
            import audioop

            return float(audioop.rms(pcm, 2))
        except Exception:
            return 0.0


def build_sink(loop: asyncio.AbstractEventLoop, callback: FrameCallback) -> Any:
    """Return a BasicSink that forwards decoded PCM frames to the pipeline."""

    if voice_recv is None:  # pragma: no cover - safety net for missing dependency
        message = (
            "discord-ext-voice-recv is not available; install to enable voice receive"
        )
        if _IMPORT_ERROR:
            message = f"{message}: {type(_IMPORT_ERROR).__name__}: {_IMPORT_ERROR}"
        raise RuntimeError(message)

    # Create our buffered sink
    buffered_sink = BufferedVoiceSink(loop, callback)

    def handler(user: object | None, data: Any) -> None:
        """Handler that delegates to our buffered sink."""
        buffered_sink._handle_packet(user, data)

    # BasicSink accepts the callback and supports decode option.
    assert voice_recv is not None
    return voice_recv.BasicSink(handler, decode=True)


def _consume_result(future: ThreadFuture[None]) -> None:
    try:
        future.result()
    except Exception as exc:
        _get_logger().error("voice.receiver_callback_failed", error=str(exc))


__all__ = ["build_sink"]
