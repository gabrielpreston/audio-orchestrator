"""
Canonical audio contracts and interfaces for mobile voice assistant integration.

This module defines the standardized audio formats, control plane message schemas,
and adapter interfaces that enable cross-platform mobile integration while
reusing the existing Discord-first audio pipeline.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

# ============================================================================
# Canonical Audio Contract
# ============================================================================


@dataclass
class AudioFrame:
    """Canonical audio frame structure for mobile integration."""

    # Core audio data
    pcm_data: bytes  # Raw PCM audio data
    timestamp: float  # Unix timestamp in seconds
    sample_rate: int = 16000  # Nominal rate for STT-oriented processing
    channels: int = 1  # Mono audio
    sample_width: int = 2  # 16-bit samples
    bit_depth: int = 16

    # Timing and metadata
    frame_duration_ms: int = 20  # Target frame duration
    sequence_number: int = 0  # Frame sequence for ordering

    # Processing markers
    is_speech: bool = False  # VAD detection result
    is_endpoint: bool = False  # End-of-speech marker
    confidence: float = 0.0  # VAD confidence score

    @property
    def samples_per_frame(self) -> int:
        """Calculate samples per frame based on sample rate and duration."""
        return int(self.sample_rate * self.frame_duration_ms / 1000)

    @property
    def expected_bytes(self) -> int:
        """Calculate expected frame size in bytes."""
        return self.samples_per_frame * self.channels * self.sample_width


@dataclass
class AudioSegment:
    """Audio segment with word-level timing information."""

    audio_frames: List[AudioFrame]
    transcript: str
    words: List["WordTiming"]
    start_time: float
    end_time: float
    confidence: float
    is_final: bool = False

    @property
    def duration_ms(self) -> int:
        """Calculate segment duration in milliseconds."""
        return int((self.end_time - self.start_time) * 1000)


@dataclass
class WordTiming:
    """Word-level timing information for transcripts."""

    word: str
    start_time: float  # Seconds from segment start
    end_time: float  # Seconds from segment start
    confidence: float = 0.0


# ============================================================================
# Control Plane Message Schemas
# ============================================================================


class MessageType(Enum):
    """Control plane message types."""

    # Client → Agent
    WAKE_DETECTED = "wake.detected"
    VAD_START_SPEECH = "vad.start_speech"
    VAD_END_SPEECH = "vad.end_speech"
    BARGE_IN_REQUEST = "barge_in.request"
    SESSION_STATE = "session.state"
    ROUTE_CHANGE = "route.change"

    # Agent → Client
    PLAYBACK_CONTROL = "playback.control"
    ENDPOINTING = "endpointing"
    TRANSCRIPT_PARTIAL = "transcript.partial"
    TRANSCRIPT_FINAL = "transcript.final"
    ERROR = "error"
    TELEMETRY_SNAPSHOT = "telemetry.snapshot"


@dataclass
class ControlMessage:
    """Base control plane message structure."""

    message_type: MessageType
    timestamp: float
    correlation_id: str
    payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary for JSON serialization."""
        return {
            "type": self.message_type.value,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
            "payload": self.payload,
        }


# Client → Agent Messages
@dataclass
class WakeDetectedMessage(ControlMessage):
    """Wake word detection message."""

    def __init__(self, correlation_id: str, confidence: float, timestamp: Optional[float] = None):
        super().__init__(
            message_type=MessageType.WAKE_DETECTED,
            timestamp=timestamp or datetime.now().timestamp(),
            correlation_id=correlation_id,
            payload={"confidence": confidence},
        )


@dataclass
class VADStartSpeechMessage(ControlMessage):
    """Voice activity detection start message."""

    def __init__(self, correlation_id: str, timestamp: Optional[float] = None):
        super().__init__(
            message_type=MessageType.VAD_START_SPEECH,
            timestamp=timestamp or datetime.now().timestamp(),
            correlation_id=correlation_id,
            payload={},
        )


@dataclass
class VADEndSpeechMessage(ControlMessage):
    """Voice activity detection end message."""

    def __init__(self, correlation_id: str, duration_ms: int, timestamp: Optional[float] = None):
        super().__init__(
            message_type=MessageType.VAD_END_SPEECH,
            timestamp=timestamp or datetime.now().timestamp(),
            correlation_id=correlation_id,
            payload={"duration_ms": duration_ms},
        )


@dataclass
class BargeInRequestMessage(ControlMessage):
    """Barge-in request message."""

    def __init__(self, correlation_id: str, reason: str, timestamp: Optional[float] = None):
        super().__init__(
            message_type=MessageType.BARGE_IN_REQUEST,
            timestamp=timestamp or datetime.now().timestamp(),
            correlation_id=correlation_id,
            payload={"reason": reason},
        )


@dataclass
class SessionStateMessage(ControlMessage):
    """Session state change message."""

    def __init__(self, correlation_id: str, action: str, timestamp: Optional[float] = None):
        super().__init__(
            message_type=MessageType.SESSION_STATE,
            timestamp=timestamp or datetime.now().timestamp(),
            correlation_id=correlation_id,
            payload={"action": action},
        )


@dataclass
class RouteChangeMessage(ControlMessage):
    """Audio route change message."""

    def __init__(
        self, correlation_id: str, output: str, input: str, timestamp: Optional[float] = None
    ):
        super().__init__(
            message_type=MessageType.ROUTE_CHANGE,
            timestamp=timestamp or datetime.now().timestamp(),
            correlation_id=correlation_id,
            payload={"output": output, "input": input},
        )


# Agent → Client Messages
@dataclass
class PlaybackControlMessage(ControlMessage):
    """Playback control message."""

    def __init__(
        self, correlation_id: str, action: str, reason: str = "", timestamp: Optional[float] = None
    ):
        super().__init__(
            message_type=MessageType.PLAYBACK_CONTROL,
            timestamp=timestamp or datetime.now().timestamp(),
            correlation_id=correlation_id,
            payload={"action": action, "reason": reason},
        )


@dataclass
class EndpointingMessage(ControlMessage):
    """Endpointing state message."""

    def __init__(self, correlation_id: str, state: str, timestamp: Optional[float] = None):
        super().__init__(
            message_type=MessageType.ENDPOINTING,
            timestamp=timestamp or datetime.now().timestamp(),
            correlation_id=correlation_id,
            payload={"state": state},
        )


@dataclass
class TranscriptPartialMessage(ControlMessage):
    """Partial transcript message."""

    def __init__(
        self, correlation_id: str, text: str, confidence: float, timestamp: Optional[float] = None
    ):
        super().__init__(
            message_type=MessageType.TRANSCRIPT_PARTIAL,
            timestamp=timestamp or datetime.now().timestamp(),
            correlation_id=correlation_id,
            payload={"text": text, "confidence": confidence},
        )


@dataclass
class TranscriptFinalMessage(ControlMessage):
    """Final transcript message with word timings."""

    def __init__(
        self,
        correlation_id: str,
        text: str,
        words: List[WordTiming],
        timestamp: Optional[float] = None,
    ):
        super().__init__(
            message_type=MessageType.TRANSCRIPT_FINAL,
            timestamp=timestamp or datetime.now().timestamp(),
            correlation_id=correlation_id,
            payload={
                "text": text,
                "words": [
                    {
                        "word": w.word,
                        "start": w.start_time,
                        "end": w.end_time,
                        "confidence": w.confidence,
                    }
                    for w in words
                ],
            },
        )


@dataclass
class ErrorMessage(ControlMessage):
    """Error message."""

    def __init__(
        self,
        correlation_id: str,
        code: str,
        message: str,
        recoverable: bool = True,
        timestamp: Optional[float] = None,
    ):
        super().__init__(
            message_type=MessageType.ERROR,
            timestamp=timestamp or datetime.now().timestamp(),
            correlation_id=correlation_id,
            payload={"code": code, "message": message, "recoverable": recoverable},
        )


@dataclass
class TelemetrySnapshotMessage(ControlMessage):
    """Telemetry snapshot message."""

    def __init__(
        self,
        correlation_id: str,
        rtt_ms: float,
        pl_percent: float,
        jitter_ms: float,
        timestamp: Optional[float] = None,
    ):
        super().__init__(
            message_type=MessageType.TELEMETRY_SNAPSHOT,
            timestamp=timestamp or datetime.now().timestamp(),
            correlation_id=correlation_id,
            payload={"rtt_ms": rtt_ms, "pl_percent": pl_percent, "jitter_ms": jitter_ms},
        )


# ============================================================================
# STT Adapter Contract
# ============================================================================


class STTAdapter:
    """Abstract STT adapter interface for provider abstraction."""

    async def start_stream(self, correlation_id: str) -> str:
        """Start a new STT stream."""
        raise NotImplementedError

    async def process_audio_frame(
        self, stream_id: str, frame: AudioFrame
    ) -> Optional[AudioSegment]:
        """Process an audio frame and return partial/final transcript if available."""
        raise NotImplementedError

    async def flush_stream(self, stream_id: str) -> Optional[AudioSegment]:
        """Flush the stream and return final transcript."""
        raise NotImplementedError

    async def stop_stream(self, stream_id: str) -> None:
        """Stop and cleanup the stream."""
        raise NotImplementedError


# ============================================================================
# TTS Adapter Contract
# ============================================================================


class TTSAdapter:
    """Abstract TTS adapter interface for provider abstraction."""

    async def synthesize_text(
        self, text: str, voice: str = "default", correlation_id: str = ""
    ) -> bytes:
        """Synthesize text to audio and return as bytes."""
        raise NotImplementedError

    async def start_stream(self, correlation_id: str) -> str:
        """Start a new TTS stream for incremental synthesis."""
        raise NotImplementedError

    async def add_text_chunk(self, stream_id: str, text: str) -> None:
        """Add text chunk to the stream."""
        raise NotImplementedError

    async def get_audio_chunk(self, stream_id: str) -> Optional[bytes]:
        """Get the next audio chunk from the stream."""
        raise NotImplementedError

    async def pause_stream(self, stream_id: str) -> None:
        """Pause the TTS stream."""
        raise NotImplementedError

    async def resume_stream(self, stream_id: str) -> None:
        """Resume the TTS stream."""
        raise NotImplementedError

    async def stop_stream(self, stream_id: str) -> None:
        """Stop and cleanup the stream."""
        raise NotImplementedError


# ============================================================================
# Session State Management
# ============================================================================


class SessionState(Enum):
    """Mobile session states."""

    IDLE = "idle"
    ARMING = "arming"
    LIVE_LISTEN = "live_listen"
    PROCESSING = "processing"
    RESPONDING = "responding"
    TEARDOWN = "teardown"


class EndpointingState(Enum):
    """Endpointing states."""

    LISTENING = "listening"
    PROCESSING = "processing"
    RESPONDING = "responding"


class PlaybackAction(Enum):
    """Playback control actions."""

    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"


class AudioRoute(Enum):
    """Audio routing options."""

    SPEAKER = "speaker"
    EARPIECE = "earpiece"
    BLUETOOTH = "bt"


class AudioInput(Enum):
    """Audio input sources."""

    BUILT_IN = "built_in"
    BLUETOOTH = "bt"


# ============================================================================
# Configuration and Constants
# ============================================================================

# Audio processing constants
CANONICAL_SAMPLE_RATE = 16000
CANONICAL_FRAME_MS = 20
CANONICAL_CHANNELS = 1
CANONICAL_SAMPLE_WIDTH = 2
CANONICAL_BIT_DEPTH = 16

# WebRTC/Opus constants for transport
OPUS_SAMPLE_RATE = 48000
OPUS_FRAME_MS = 20
OPUS_CHANNELS = 1

# Latency targets (milliseconds)
TARGET_RTT_MEDIAN = 400
TARGET_RTT_P95 = 650
TARGET_BARGE_IN_PAUSE = 250

# Quality targets
MAX_PACKET_LOSS_PERCENT = 10
MAX_JITTER_MS = 80
TARGET_UPTIME_PERCENT = 99.9

# Session timeouts
MAX_SESSION_DURATION_MINUTES = 30
WAKE_COOLDOWN_MS = 1000
VAD_TIMEOUT_MS = 2000
ENDPOINTING_TIMEOUT_MS = 5000


__all__ = [
    # Audio contracts
    "AudioFrame",
    "AudioSegment",
    "WordTiming",
    # Control messages
    "MessageType",
    "ControlMessage",
    "WakeDetectedMessage",
    "VADStartSpeechMessage",
    "VADEndSpeechMessage",
    "BargeInRequestMessage",
    "SessionStateMessage",
    "RouteChangeMessage",
    "PlaybackControlMessage",
    "EndpointingMessage",
    "TranscriptPartialMessage",
    "TranscriptFinalMessage",
    "ErrorMessage",
    "TelemetrySnapshotMessage",
    # Adapters
    "STTAdapter",
    "TTSAdapter",
    # State enums
    "SessionState",
    "EndpointingState",
    "PlaybackAction",
    "AudioRoute",
    "AudioInput",
    # Constants
    "CANONICAL_SAMPLE_RATE",
    "CANONICAL_FRAME_MS",
    "CANONICAL_CHANNELS",
    "CANONICAL_SAMPLE_WIDTH",
    "CANONICAL_BIT_DEPTH",
    "OPUS_SAMPLE_RATE",
    "OPUS_FRAME_MS",
    "OPUS_CHANNELS",
    "TARGET_RTT_MEDIAN",
    "TARGET_RTT_P95",
    "TARGET_BARGE_IN_PAUSE",
    "MAX_PACKET_LOSS_PERCENT",
    "MAX_JITTER_MS",
    "TARGET_UPTIME_PERCENT",
    "MAX_SESSION_DURATION_MINUTES",
    "WAKE_COOLDOWN_MS",
    "VAD_TIMEOUT_MS",
    "ENDPOINTING_TIMEOUT_MS",
]
