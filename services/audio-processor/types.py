"""Data types for the audio processor service.

This module imports and re-exports the standardized data types
from the Discord service for consistency across the audio pipeline.
"""

from services.discord.audio import AudioSegment, PCMFrame


__all__ = ["AudioSegment", "PCMFrame"]
