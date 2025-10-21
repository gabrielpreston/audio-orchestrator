"""Core data types for the audio pipeline."""

from typing import NamedTuple, Optional
from datetime import datetime


class AudioChunk(NamedTuple):
    """Represents a chunk of audio data with metadata."""

    pcm_bytes: bytes
    sample_rate: int
    channels: int
    timestamp_ms: int


class ProcessedSegment(NamedTuple):
    """Represents a processed audio segment with transcription."""

    transcript: str
    start_time_ms: int
    end_time_ms: int
    confidence: Optional[float] = None
    language: Optional[str] = None


class ConversationContext(NamedTuple):
    """Represents the current conversation context."""

    session_id: str
    history: list[tuple[str, str]]  # List of (user_input, agent_response) pairs
    created_at: datetime
    last_active_at: datetime
    metadata: Optional[dict] = None


class ExternalAction(NamedTuple):
    """Represents an external action to be performed by an agent."""

    action_type: str
    parameters: dict
    priority: int = 0
    timeout_seconds: Optional[int] = None
