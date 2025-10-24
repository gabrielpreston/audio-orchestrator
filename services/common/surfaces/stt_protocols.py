"""STT system protocols for audio-orchestrator.

This module defines protocol-based interfaces for STT adapters,
replacing Abstract Base Classes with focused, composable protocols.
"""

from typing import Protocol, Any
from collections.abc import AsyncGenerator

from .types import AudioFormat, AudioMetadata
from .stt_interface import STTConfig, STTResult


class STTProcessingProtocol(Protocol):
    """Protocol for STT processing operations."""

    async def transcribe(
        self,
        audio_data: bytes,
        audio_format: AudioFormat,
        metadata: AudioMetadata | None = None,
    ) -> STTResult: ...

    def transcribe_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        audio_format: AudioFormat,
        metadata: AudioMetadata | None = None,
    ) -> AsyncGenerator[STTResult, None]: ...


class STTConfigurationProtocol(Protocol):
    """Protocol for STT configuration management."""

    @property
    def config(self) -> STTConfig: ...

    def get_config(self, key: str, default: Any = None) -> Any: ...
    def set_config(self, key: str, value: Any) -> None: ...
    def validate_config(self) -> bool: ...


class STTConnectionProtocol(Protocol):
    """Protocol for STT connection management."""

    async def initialize(self) -> bool: ...
    async def connect(self) -> bool: ...
    async def disconnect(self) -> None: ...
    async def cleanup(self) -> None: ...

    @property
    def is_initialized(self) -> bool: ...

    @property
    def is_connected(self) -> bool: ...


class STTCapabilitiesProtocol(Protocol):
    """Protocol for STT capabilities and information."""

    async def get_supported_languages(self) -> list[str]: ...
    async def get_model_info(self) -> dict[str, Any]: ...
    async def get_telemetry(self) -> dict[str, Any]: ...
