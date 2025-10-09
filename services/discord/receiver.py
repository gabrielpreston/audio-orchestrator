"""Helpers for bridging discord-ext-voice-recv sinks into the audio pipeline."""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional

from structlog.stdlib import BoundLogger

from services.common.logging import get_logger

try:
    from discord.ext import voice_recv  # type: ignore[attr-defined]
except ImportError as exc:  # pragma: no cover - handled at runtime
    voice_recv = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

FrameCallback = Callable[[int, bytes, float, int], Awaitable[None]]

_LOGGER: Optional[BoundLogger] = None


def _get_logger() -> BoundLogger:
    global _LOGGER
    if _LOGGER is None:
        _LOGGER = get_logger(__name__, service_name="discord")
    return _LOGGER


def build_sink(loop: asyncio.AbstractEventLoop, callback: FrameCallback) -> "voice_recv.BasicSink":  # type: ignore[misc]
    """Return a BasicSink that forwards decoded PCM frames to the pipeline."""

    if voice_recv is None:  # pragma: no cover - safety net for missing dependency
        message = "discord-ext-voice-recv is not available; install to enable voice receive"
        if _IMPORT_ERROR:
            message = f"{message}: {type(_IMPORT_ERROR).__name__}: {_IMPORT_ERROR}"
        raise RuntimeError(message)

    logger = _get_logger()

    def handler(user: Optional[object], data: "voice_recv.VoiceData") -> None:  # type: ignore[valid-type]
        pcm = getattr(data, "decoded_data", None) or getattr(data, "pcm", None)
        if not pcm:
            return
        user_id = getattr(user, "id", None) if user else getattr(data, "user_id", None)
        if user_id is None:
            logger.debug("voice.receiver_unknown_user")
            return
        sample_rate = getattr(data, "sample_rate", None) or getattr(data, "sampling_rate", None) or 48000
        frame_count = len(pcm) // 2  # 16-bit mono
        duration = float(frame_count) / float(sample_rate) if sample_rate else 0.0
        future = asyncio.run_coroutine_threadsafe(callback(user_id, pcm, duration, int(sample_rate)), loop)
        future.add_done_callback(_consume_result)

    # BasicSink accepts the callback and supports decode option.
    return voice_recv.BasicSink(handler, decode=True)


def _consume_result(future: "asyncio.Future[None]") -> None:
    try:
        future.result()
    except Exception as exc:  # noqa: BLE001
        _get_logger().error("voice.receiver_callback_failed", error=str(exc))


__all__ = ["build_sink"]
