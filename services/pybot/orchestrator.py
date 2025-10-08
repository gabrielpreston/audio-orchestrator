"""Client for orchestrating downstream tool calls and responses."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Optional

import aiohttp

from .config import OrchestratorConfig
from .logging import get_logger
from .transcription import TranscriptResult
from .wake import WakeDetector


@dataclass(slots=True)
class OrchestratorRequest:
    """Structured payload sent to the orchestrator service."""

    text: str
    user_id: int
    channel_id: int
    guild_id: int
    correlation_id: str


@dataclass(slots=True)
class OrchestratorResponse:
    """Response from the orchestrator."""

    text: str
    tool_calls: Dict[str, Any]
    tts_audio_url: Optional[str]
    correlation_id: str
    raw_response: Dict[str, Any]


class OrchestratorClient:
    """Wraps orchestrator HTTP API and wake-word filtering."""

    def __init__(self, config: OrchestratorConfig, wake_detector: WakeDetector, *, session: Optional[aiohttp.ClientSession] = None) -> None:
        self._config = config
        self._wake_detector = wake_detector
        self._session = session
        self._owns_session = session is None
        self._logger = get_logger(__name__)

    async def __aenter__(self) -> "OrchestratorClient":
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=self._config.request_timeout_seconds)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        if self._owns_session and self._session:
            await self._session.close()

    async def maybe_invoke(
        self,
        request: OrchestratorRequest,
        transcript: TranscriptResult,
    ) -> Optional[OrchestratorResponse]:
        """Call the orchestrator if wake phrase detected."""

        if not self._wake_detector.matches(transcript.text):
            self._logger.debug(
                "orchestrator.skipping",
                extra={
                    "correlation_id": request.correlation_id,
                    "reason": "no_wake_phrase",
                },
            )
            return None
        if not self._config.base_url:
            self._logger.warning(
                "orchestrator.disabled",
                extra={"correlation_id": request.correlation_id},
            )
            return None
        return await self._invoke(request, transcript)

    async def _invoke(self, request: OrchestratorRequest, transcript: TranscriptResult) -> OrchestratorResponse:
        if not self._session:
            raise RuntimeError("OrchestratorClient must be used as an async context manager")

        payload = {
            "text": transcript.text,
            "user_id": request.user_id,
            "channel_id": request.channel_id,
            "guild_id": request.guild_id,
            "correlation_id": request.correlation_id,
            "wake_phrase": self._wake_detector.first_match(transcript.text),
            "timestamps": {
                "start": transcript.start_timestamp,
                "end": transcript.end_timestamp,
            },
        }

        attempt = 0
        while True:
            attempt += 1
            try:
                assert self._session is not None
                async with self._session.post(f"{self._config.base_url}/orchestrate", json=payload) as response:
                    response.raise_for_status()
                    data = await response.json()
                    return OrchestratorResponse(
                        text=data.get("response", ""),
                        tool_calls=data.get("tool_calls", {}),
                        tts_audio_url=data.get("tts_audio_url"),
                        correlation_id=request.correlation_id,
                        raw_response=data,
                    )
            except Exception as exc:  # noqa: BLE001
                if attempt >= self._config.max_retries:
                    self._logger.error(
                        "orchestrator.invoke_failed",
                        extra={
                            "correlation_id": request.correlation_id,
                            "attempt": attempt,
                            "error": str(exc),
                        },
                    )
                    raise
                backoff = min(2 ** (attempt - 1), 10)
                self._logger.warning(
                    "orchestrator.retry",
                    extra={
                        "correlation_id": request.correlation_id,
                        "attempt": attempt,
                        "backoff": backoff,
                    },
                )
                await asyncio.sleep(backoff)


__all__ = ["OrchestratorClient", "OrchestratorRequest", "OrchestratorResponse"]
