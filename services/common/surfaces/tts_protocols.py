"""TTS system protocols for audio-orchestrator.

This module defines protocol-based interfaces for TTS adapters,
replacing Abstract Base Classes with focused, composable protocols.
"""

from typing import Protocol, Any
from collections.abc import AsyncGenerator

from .tts_interface import TTSConfig, TTSResult


class TTSProcessingProtocol(Protocol):
    """Protocol for TTS processing operations."""

    async def synthesize(
        self, text: str, voice: str | None = None, language: str | None = None
    ) -> TTSResult: ...

    def synthesize_stream(
        self, text: str, voice: str | None = None, language: str | None = None
    ) -> AsyncGenerator[TTSResult, None]: ...


class TTSConfigurationProtocol(Protocol):
    """Protocol for TTS configuration management."""

    @property
    def config(self) -> TTSConfig: ...

    def get_config(self, key: str, default: Any = None) -> Any: ...
    def set_config(self, key: str, value: Any) -> None: ...
    def validate_config(self) -> bool: ...


class TTSConnectionProtocol(Protocol):
    """Protocol for TTS connection management."""

    async def initialize(self) -> bool: ...
    async def connect(self) -> bool: ...
    async def disconnect(self) -> None: ...
    async def cleanup(self) -> None: ...

    @property
    def is_initialized(self) -> bool: ...

    @property
    def is_connected(self) -> bool: ...


class TTSVoiceProtocol(Protocol):
    """Protocol for TTS voice management."""

    async def get_available_voices(self) -> list[dict[str, Any]]: ...
    async def get_supported_languages(self) -> list[str]: ...


class TTSCapabilitiesProtocol(Protocol):
    """Protocol for TTS capabilities and information."""

    async def get_model_info(self) -> dict[str, Any]: ...
    async def get_telemetry(self) -> dict[str, Any]: ...
