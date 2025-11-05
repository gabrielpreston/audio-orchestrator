"""Helpers for bridging discord-ext-voice-recv sinks into the audio pipeline."""

from __future__ import annotations

import asyncio
import importlib
import os
import time
from collections import deque
from collections.abc import Callable, Coroutine
from concurrent.futures import Future as ThreadFuture
from typing import Any

from structlog.stdlib import BoundLogger

from services.common.structured_logging import (
    get_logger,
    should_rate_limit,
    should_sample,
)


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

        # Diagnostic logging: Log every packet received (rate-limited)
        try:
            rate_s = float(os.getenv("LOG_RATE_LIMIT_PACKET_DEBUG_S", "1.0"))
        except Exception:
            rate_s = 1.0
        if should_rate_limit("discord.packet_received", rate_s):
            pcm_status = (
                "yes"
                if (getattr(data, "decoded_data", None) or getattr(data, "pcm", None))
                else "no"
            )
            self._logger.debug(
                "voice.packet_received",
                user_id=user_id,
                ssrc=ssrc,
                pcm_available=pcm_status,
            )

        # If we have a user_id, process immediately
        if user_id is not None:
            # Log first few packets at INFO level for debugging
            packet_count = getattr(self, "_packet_count", 0)
            self._packet_count = packet_count + 1

            if packet_count < 5:
                # Inspect data object attributes
                data_attrs = (
                    [attr for attr in dir(data) if not attr.startswith("_")]
                    if data
                    else []
                )
                pcm_attrs = [
                    attr
                    for attr in data_attrs
                    if "pcm" in attr.lower()
                    or "data" in attr.lower()
                    or "audio" in attr.lower()
                ]
                self._logger.info(
                    "voice.packet_processing",
                    packet_number=packet_count + 1,
                    user_id=user_id,
                    ssrc=ssrc,
                    data_type=type(data).__name__ if data else None,
                    data_attrs_count=len(data_attrs),
                    pcm_related_attrs=pcm_attrs[:10],  # First 10 relevant attrs
                    has_decoded_data=hasattr(data, "decoded_data") if data else False,
                    has_pcm=hasattr(data, "pcm") if data else False,
                    decoded_data_value=bool(getattr(data, "decoded_data", None))
                    if data
                    else False,
                    pcm_value=bool(getattr(data, "pcm", None)) if data else False,
                )

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
            if packet_count < 5:
                self._logger.info(
                    "voice.calling_process_packet",
                    packet_number=packet_count + 1,
                    user_id=user_id,
                )
            self._process_packet(user, data)
            if packet_count < 5:
                self._logger.info(
                    "voice.process_packet_completed",
                    packet_number=packet_count + 1,
                    user_id=user_id,
                )
            return

        # No user_id - buffer the packet if we have SSRC info
        if ssrc is not None:
            current_time = time.monotonic()

            # Track first time we see this SSRC
            if ssrc not in self._ssrc_first_seen:
                self._ssrc_first_seen[ssrc] = current_time
                # Log only first occurrence per SSRC to reduce spam
                if ssrc not in self._logged_unknown_ssrcs:
                    # Rate-limit first-unknown-ssrc logs
                    try:
                        rate_s = float(os.getenv("LOG_RATE_LIMIT_PACKET_WARN_S", "10"))
                    except Exception:
                        rate_s = 10.0
                    if should_rate_limit("discord.first_unknown_ssrc", rate_s):
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
            # Sample buffer status logs
            try:
                buffer_sample_n = int(os.getenv("LOG_SAMPLE_UNKNOWN_USER_N", "100"))
            except Exception:
                buffer_sample_n = 100
            if should_sample("discord.buffer_status", buffer_sample_n):
                self._logger.debug(
                    "voice.buffer_status",
                    ssrc=ssrc,
                    buffered_packets=len(buffer),
                    buffer_age=current_time - self._ssrc_first_seen[ssrc],
                )
        else:
            # No SSRC info - just log and drop
            try:
                sample_n = int(os.getenv("LOG_SAMPLE_UNKNOWN_USER_N", "100"))
            except Exception:
                sample_n = 100
            if should_sample("discord.receiver_unknown_user", sample_n):
                self._logger.debug("voice.receiver_unknown_user")

    def _process_packet(self, user: object | None, data: Any) -> None:
        """Process a single packet through the audio pipeline."""
        # Log first few calls at INFO level
        process_count = getattr(self, "_process_count", 0)
        self._process_count = process_count + 1

        if process_count < 5:
            # Inspect data object for PCM attributes
            data_attrs = (
                [attr for attr in dir(data) if not attr.startswith("_")] if data else []
            )
            pcm_attrs = [
                attr
                for attr in data_attrs
                if "pcm" in attr.lower()
                or "data" in attr.lower()
                or "audio" in attr.lower()
                or "decoded" in attr.lower()
            ]
            decoded_data_val = getattr(data, "decoded_data", None) if data else None
            pcm_val = getattr(data, "pcm", None) if data else None

            self._logger.info(
                "voice.process_packet_entry",
                packet_number=process_count + 1,
                user_id=getattr(user, "id", None) if user else None,
                data_type=type(data).__name__ if data else None,
                decoded_data_type=type(decoded_data_val).__name__
                if decoded_data_val is not None
                else None,
                decoded_data_len=len(decoded_data_val)
                if isinstance(decoded_data_val, bytes)
                else None,
                pcm_type=type(pcm_val).__name__ if pcm_val is not None else None,
                pcm_len=len(pcm_val) if isinstance(pcm_val, bytes) else None,
                pcm_related_attrs=pcm_attrs[:10],
            )

        pcm = getattr(data, "decoded_data", None) or getattr(data, "pcm", None)
        if not pcm:
            # Log PCM extraction failures with warning level
            self._logger.warning(
                "voice.pcm_extraction_failed",
                user_id=getattr(user, "id", None)
                if user
                else getattr(data, "user_id", None),
                ssrc=getattr(data, "ssrc", None),
                has_decoded_data=bool(getattr(data, "decoded_data", None)),
                has_pcm=bool(getattr(data, "pcm", None)),
            )
            return

        user_id = getattr(user, "id", None) if user else getattr(data, "user_id", None)
        if user_id is None:
            try:
                sample_n = int(os.getenv("LOG_SAMPLE_UNKNOWN_USER_N", "100"))
            except Exception:
                sample_n = 100
            if should_sample("discord.receiver_unknown_user", sample_n):
                self._logger.debug("voice.receiver_unknown_user")
            return

        sample_rate_raw = (
            getattr(data, "sample_rate", None)
            or getattr(data, "sampling_rate", None)
            or 48000
        )
        # Ensure sample_rate is a number, not a Mock or other object
        try:
            sample_rate = int(float(sample_rate_raw)) if sample_rate_raw else 48000
        except (TypeError, ValueError):
            sample_rate = 48000
        frame_count = len(pcm) // 2  # 16-bit mono
        duration = float(frame_count) / float(sample_rate) if sample_rate else 0.0

        # Note: Removed excessive PCM frame logging that was creating 97% of log volume
        # RMS and sample rate are already tracked in VAD decisions with proper sampling

        # Log first few successful processings
        if process_count < 5:
            self._logger.info(
                "voice.process_packet_success",
                packet_number=process_count + 1,
                user_id=user_id,
                pcm_length=len(pcm),
                sample_rate=sample_rate,
                duration=duration,
                frame_count=frame_count,
                about_to_call_callback=True,
            )

        future: ThreadFuture[None] = asyncio.run_coroutine_threadsafe(
            self._callback(user_id, pcm, duration, int(sample_rate)),
            self._loop,
        )
        future.add_done_callback(_consume_result)

        if process_count < 5:
            self._logger.info(
                "voice.process_packet_callback_scheduled",
                packet_number=process_count + 1,
                user_id=user_id,
            )

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

    # Track handler call count for diagnostic logging
    _handler_call_count = 0

    def handler(user: object | None, data: Any) -> None:
        """Handler that delegates to our buffered sink."""
        # Diagnostic logging at entry point - critical for debugging packet reception
        nonlocal _handler_call_count
        logger = _get_logger()
        try:
            rate_s = float(os.getenv("LOG_RATE_LIMIT_PACKET_DEBUG_S", "1.0"))
        except Exception:
            rate_s = 1.0
        # Log first few calls at INFO level, then rate-limit at DEBUG
        _handler_call_count += 1
        call_count = _handler_call_count

        if call_count < 5 or should_rate_limit("discord.handler_called", rate_s):
            log_level = logger.info if call_count < 5 else logger.debug
            log_level(
                "voice.handler_called",
                call_number=call_count + 1,
                has_user=user is not None,
                has_data=data is not None,
                user_id=getattr(user, "id", None) if user else None,
                data_type=type(data).__name__ if data else None,
                has_ssrc=bool(getattr(data, "ssrc", None) if data else None),
            )
        try:
            buffered_sink._handle_packet(user, data)
        except Exception as exc:
            logger.exception(
                "voice.handler_exception",
                error=str(exc),
                error_type=type(exc).__name__,
                has_user=user is not None,
                has_data=data is not None,
            )
            raise

    # BasicSink accepts the callback and supports decode option.
    assert voice_recv is not None
    basic_sink = voice_recv.BasicSink(handler, decode=True)

    _get_logger().info(
        "voice.basic_sink_created",
        sink_type=type(basic_sink).__name__,
        decode_enabled=True,
        has_handler=callable(handler),
    )

    return basic_sink


def _consume_result(future: ThreadFuture[None]) -> None:
    try:
        future.result()
    except Exception as exc:
        _get_logger().error("voice.receiver_callback_failed", error=str(exc))


__all__ = ["build_sink"]
