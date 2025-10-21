"""I/O Adapter framework for audio-orchestrator services.

This module provides the core abstractions for audio input and output adapters,
enabling flexible audio processing across different platforms and protocols.

Key Components:
- AudioInputAdapter: Abstract base class for audio input sources
- AudioOutputAdapter: Abstract base class for audio output destinations
- AdapterManager: Adapter registration and management
- DiscordAudioInputAdapter: Discord-specific audio input
- DiscordAudioOutputAdapter: Discord-specific audio output

Usage:
    from services.orchestrator.adapters import AudioInputAdapter, AudioOutputAdapter
    
    class MyInputAdapter(AudioInputAdapter):
        async def start_capture(self) -> None:
            # Start capturing audio
            pass
    
    class MyOutputAdapter(AudioOutputAdapter):
        async def play_audio(self, audio_data: bytes) -> None:
            # Play audio data
            pass
"""

from .base import AudioInputAdapter, AudioOutputAdapter
from .manager import AdapterManager
from .types import AudioChunk, AudioMetadata, AdapterConfig

__all__ = [
    "AudioInputAdapter",
    "AudioOutputAdapter", 
    "AdapterManager",
    "AudioChunk",
    "AudioMetadata",
    "AdapterConfig",
]
