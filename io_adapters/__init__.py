"""I/O adapters package for audio input and output handling."""

from .audio_input_adapter import AudioInputAdapter
from .audio_output_adapter import AudioOutputAdapter
from .adapter_registry import (
    AdapterRegistry,
    registry,
    register_input_adapter,
    register_output_adapter,
    get_input_adapter,
    get_output_adapter,
)

__all__ = [
    "AudioInputAdapter",
    "AudioOutputAdapter",
    "AdapterRegistry",
    "registry",
    "register_input_adapter",
    "register_output_adapter",
    "get_input_adapter",
    "get_output_adapter",
]
