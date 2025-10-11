"""Helpers for bridging discord-ext-voice-recv sinks into the audio pipeline."""

from __future__ import annotations

import asyncio
from concurrent.futures import Future as ThreadFuture
from typing import Any, Callable, Coroutine, Optional

from structlog.stdlib import BoundLogger

from services.common.logging import get_logger

try:
    from discord.ext import voice_recv as _voice_recv
except ImportError as exc:  # pragma: no cover - handled at runtime
    _voice_recv = None
    _IMPORT_ERROR: Optional[ImportError] = exc
else:
    _IMPORT_ERROR = None

voice_recv: Optional[Any] = _voice_recv

FrameCallback = Callable[[int, bytes, float, int], Coroutine[Any, Any, None]]

_LOGGER: Optional[BoundLogger] = None


def _get_logger() -> BoundLogger:
    global _LOGGER
    if _LOGGER is None:
        _LOGGER = get_logger(__name__, service_name="discord")
    return _LOGGER


def build_sink(loop: asyncio.AbstractEventLoop, callback: FrameCallback) -> Any:
    """Return a BasicSink that forwards decoded PCM frames to the pipeline."""

    if voice_recv is None:  # pragma: no cover - safety net for missing dependency
        message = "discord-ext-voice-recv is not available; install to enable voice receive"
        if _IMPORT_ERROR:
            message = f"{message}: {type(_IMPORT_ERROR).__name__}: {_IMPORT_ERROR}"
        raise RuntimeError(message)

    logger = _get_logger()

    def handler(user: Optional[object], data: Any) -> None:
        pcm = getattr(data, "decoded_data", None) or getattr(data, "pcm", None)
        if not pcm:
            return
        user_id = getattr(user, "id", None) if user else getattr(data, "user_id", None)
        if user_id is None:
            logger.debug("voice.receiver_unknown_user")
            return
        sample_rate = (
            getattr(data, "sample_rate", None) or getattr(data, "sampling_rate", None) or 48000
        )
        frame_count = len(pcm) // 2  # 16-bit mono
        duration = float(frame_count) / float(sample_rate) if sample_rate else 0.0
        future: ThreadFuture[None] = asyncio.run_coroutine_threadsafe(
            callback(user_id, pcm, duration, int(sample_rate)),
            loop,
        )
        future.add_done_callback(_consume_result)

    # BasicSink accepts the callback and supports decode option.
    assert voice_recv is not None
    return voice_recv.BasicSink(handler, decode=True)


def _consume_result(future: ThreadFuture[None]) -> None:
    try:
        future.result()
    except Exception as exc:  # noqa: BLE001
        _get_logger().error("voice.receiver_callback_failed", error=str(exc))


__all__ = ["build_sink"]
