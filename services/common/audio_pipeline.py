"""
Audio I/O Pipelines - Canonical Audio Contract and FFmpeg Façade

This module implements the canonical audio contract and FFmpeg-based audio processing
as specified in the Audio I/O Pipelines requirements. It provides:

1. Canonical frame format: 48kHz mono float32, 20ms frames (960 samples)
2. FFmpeg façade for decode/resample/loudnorm/framing operations
3. Boundary conversions only at ingress/egress
4. Jitter buffer and VAD chunker utilities
5. Metrics and observability support

Author: Senior Software Engineer (Python-first, library-oriented)
"""

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

import ffmpeg
import numpy as np
import webrtcvad

from .logging import get_logger

# Prometheus metrics removed


class AudioFormat(Enum):
    """Supported audio formats for boundary conversions."""

    PCM_16LE = "s16le"  # Discord playback format
    PCM_48K_MONO = "pcm_s16le"  # Internal processing
    FLOAT32 = "f32le"  # Internal canonical format
    OPUS = "opus"  # Discord voice receive


@dataclass(frozen=True)
class CanonicalFrame:
    """
    Canonical audio frame - the single source of truth for audio inside the system.

    Format: 48kHz mono float32, exactly 20ms (960 samples)
    """

    samples: np.ndarray  # float32, shape=(960,)
    timestamp: float  # monotonic time when frame was created
    sequence: int  # frame sequence number
    sample_rate: int = 48000  # Always 48kHz
    channels: int = 1  # Always mono
    frame_duration_ms: float = 20.0  # Always 20ms

    def __post_init__(self):
        """Validate frame format."""
        if len(self.samples) != 960:
            raise ValueError(
                f"Canonical frame must have exactly 960 samples, got {len(self.samples)}"
            )
        if self.samples.dtype != np.float32:
            raise ValueError(f"Canonical frame must be float32, got {self.samples.dtype}")
        if self.sample_rate != 48000:
            raise ValueError(f"Canonical frame must be 48kHz, got {self.sample_rate}")
        if self.channels != 1:
            raise ValueError(f"Canonical frame must be mono, got {self.channels}")


@dataclass
class AudioSegment:
    """Speech segment for STT processing."""

    frames: List[CanonicalFrame]
    start_timestamp: float
    end_timestamp: float
    correlation_id: str
    user_id: int

    @property
    def duration(self) -> float:
        """Duration in seconds."""
        return self.end_timestamp - self.start_timestamp

    @property
    def sample_count(self) -> int:
        """Total number of samples in the segment."""
        return len(self.frames) * 960


@dataclass
class JitterBuffer:
    """Jitter buffer for capture smoothing with overflow handling."""

    target_frames: int = 3  # Target 2-3 frames (40-60ms)
    max_frames: int = 8  # Max 8 frames (160ms) before dropping oldest
    frames: deque = field(default_factory=deque)

    def add_frame(self, frame: CanonicalFrame) -> List[CanonicalFrame]:
        """
        Add frame to buffer, return frames to emit.

        Returns:
            List of frames to emit (empty if buffering, or frames if ready/overflow)
        """
        self.frames.append(frame)

        # Check for overflow
        if len(self.frames) > self.max_frames:
            # Drop oldest frames to maintain max_frames limit
            dropped_frames = []
            while len(self.frames) > self.max_frames:
                dropped_frames.append(self.frames.popleft())
            return dropped_frames

        # Emit frames if we have enough buffered
        if len(self.frames) >= self.target_frames:
            frames_to_emit = []
            while len(self.frames) >= self.target_frames:
                frames_to_emit.append(self.frames.popleft())
            return frames_to_emit

        return []  # Still buffering

    def flush(self) -> List[CanonicalFrame]:
        """Flush all remaining frames."""
        frames = list(self.frames)
        self.frames.clear()
        return frames


class FFmpegFacade:
    """FFmpeg façade for audio processing operations."""

    def __init__(self, service_name: str = "common"):
        self.service_name = service_name
        self._logger = get_logger(__name__, service_name=service_name)

        # Metrics - disabled to prevent collision
        # TODO: Re-enable metrics with proper singleton pattern
        self._decode_errors = None
        self._resample_errors = None
        self._loudnorm_errors = None
        self._processing_duration = None

    def decode_to_canonical(
        self,
        audio_data: bytes,
        input_format: Optional[str] = None,
        input_sample_rate: Optional[int] = None,
    ) -> List[CanonicalFrame]:
        """
        Decode audio data to canonical frames.

        Args:
            audio_data: Raw audio bytes (Opus, PCM, WAV, etc.)
            input_format: Hint for input format (opus, pcm, wav)
            input_sample_rate: Hint for input sample rate

        Returns:
            List of canonical frames
        """
        start_time = time.perf_counter()

        try:
            # Use FFmpeg to decode to 48kHz mono float32
            input_stream = ffmpeg.input("pipe:", format=input_format or "auto")

            # Convert to canonical format: 48kHz mono float32
            output_stream = (
                input_stream.audio.filter("aresample", 48000)  # Resample to 48kHz
                .filter("channels", 1)  # Convert to mono
                .output("pipe:", format="f32le", acodec="pcm_f32le")  # float32 little-endian
            )

            process = ffmpeg.run_async(
                output_stream, input=audio_data, pipe_stdout=True, pipe_stderr=True, quiet=True
            )

            stdout, stderr = process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="ignore")
                self._logger.error(
                    "ffmpeg.decode_failed",
                    error=error_msg,
                    input_format=input_format,
                    input_bytes=len(audio_data),
                )
                # Metrics removed
                return []

            # Convert bytes to float32 array
            audio_array = np.frombuffer(stdout, dtype=np.float32)

            # Split into 20ms frames (960 samples each)
            frames = []
            frame_size = 960  # 20ms at 48kHz
            timestamp = time.monotonic()

            for i in range(0, len(audio_array), frame_size):
                frame_samples = audio_array[i : i + frame_size]

                # Pad last frame if needed
                if len(frame_samples) < frame_size:
                    padded = np.zeros(frame_size, dtype=np.float32)
                    padded[: len(frame_samples)] = frame_samples
                    frame_samples = padded

                frame = CanonicalFrame(
                    samples=frame_samples,
                    timestamp=timestamp + (i / frame_size) * 0.02,  # 20ms per frame
                    sequence=i // frame_size,
                )
                frames.append(frame)

            duration = time.perf_counter() - start_time
            # Metrics removed
            self._logger.debug(
                "ffmpeg.decode_success",
                input_bytes=len(audio_data),
                output_frames=len(frames),
                duration_ms=duration * 1000,
            )

            return frames

        except Exception as exc:
            self._logger.error(
                "ffmpeg.decode_exception",
                error=str(exc),
                input_format=input_format,
                input_bytes=len(audio_data),
            )
            # Metrics removed
            return []

    def resample_for_stt(self, frames: List[CanonicalFrame]) -> bytes:
        """
        Resample canonical frames to 16kHz mono for STT processing.

        Args:
            frames: List of canonical frames

        Returns:
            PCM bytes at 16kHz mono (s16le format)
        """
        if not frames:
            return b""

        start_time = time.perf_counter()

        try:
            # Concatenate all frames
            audio_data = np.concatenate([frame.samples for frame in frames])

            # Use FFmpeg to resample 48kHz -> 16kHz
            input_stream = ffmpeg.input("pipe:", format="f32le", ar=48000, ac=1)
            output_stream = input_stream.audio.filter(
                "aresample", 16000
            ).output(  # Resample to 16kHz
                "pipe:", format="s16le", acodec="pcm_s16le"
            )  # 16-bit PCM

            process = ffmpeg.run_async(
                output_stream,
                input=audio_data.tobytes(),
                pipe_stdout=True,
                pipe_stderr=True,
                quiet=True,
            )

            stdout, stderr = process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="ignore")
                self._logger.error(
                    "ffmpeg.resample_failed", error=error_msg, input_frames=len(frames)
                )
                # Metrics removed
                return b""

            duration = time.perf_counter() - start_time
            # Metrics removed
            self._logger.debug(
                "ffmpeg.resample_success",
                input_frames=len(frames),
                output_bytes=len(stdout),
                duration_ms=duration * 1000,
            )

            return stdout

        except Exception as exc:
            self._logger.error(
                "ffmpeg.resample_exception", error=str(exc), input_frames=len(frames)
            )
            # Metrics removed
            return b""

    def loudness_normalize(
        self, frames: List[CanonicalFrame], target_lufs: float = -16.0, target_tp: float = -1.5
    ) -> List[CanonicalFrame]:
        """
        Apply EBU R128 loudness normalization to frames.

        Args:
            frames: List of canonical frames
            target_lufs: Target integrated loudness in LUFS
            target_tp: Target true peak in dBFS

        Returns:
            List of normalized canonical frames
        """
        if not frames:
            return []

        start_time = time.perf_counter()

        try:
            # Concatenate all frames
            audio_data = np.concatenate([frame.samples for frame in frames])

            # Use FFmpeg loudnorm filter
            input_stream = ffmpeg.input("pipe:", format="f32le", ar=48000, ac=1)
            output_stream = input_stream.audio.filter(
                "loudnorm", I=target_lufs, TP=target_tp, LRA=11
            ).output("pipe:", format="f32le", acodec="pcm_f32le")

            process = ffmpeg.run_async(
                output_stream,
                input=audio_data.tobytes(),
                pipe_stdout=True,
                pipe_stderr=True,
                quiet=True,
            )

            stdout, stderr = process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="ignore")
                self._logger.error(
                    "ffmpeg.loudnorm_failed", error=error_msg, input_frames=len(frames)
                )
                # Metrics removed
                return frames  # Return original frames on error

            # Convert back to frames
            normalized_array = np.frombuffer(stdout, dtype=np.float32)

            # Split back into 20ms frames
            normalized_frames = []
            frame_size = 960
            base_timestamp = frames[0].timestamp if frames else time.monotonic()

            for i in range(0, len(normalized_array), frame_size):
                frame_samples = normalized_array[i : i + frame_size]

                # Pad last frame if needed
                if len(frame_samples) < frame_size:
                    padded = np.zeros(frame_size, dtype=np.float32)
                    padded[: len(frame_samples)] = frame_samples
                    frame_samples = padded

                frame = CanonicalFrame(
                    samples=frame_samples,
                    timestamp=base_timestamp + (i / frame_size) * 0.02,
                    sequence=i // frame_size,
                )
                normalized_frames.append(frame)

            duration = time.perf_counter() - start_time
            # Metrics removed
            self._logger.debug(
                "ffmpeg.loudnorm_success",
                input_frames=len(frames),
                output_frames=len(normalized_frames),
                duration_ms=duration * 1000,
            )

            return normalized_frames

        except Exception as exc:
            self._logger.error(
                "ffmpeg.loudnorm_exception", error=str(exc), input_frames=len(frames)
            )
            if self._loudnorm_errors:
                self._loudnorm_errors.inc()
            return frames  # Return original frames on error

    def frames_to_discord_pcm(self, frames: List[CanonicalFrame]) -> bytes:
        """
        Convert canonical frames to Discord playback format (s16le 48kHz mono).

        Args:
            frames: List of canonical frames

        Returns:
            PCM bytes in s16le format for Discord playback
        """
        if not frames:
            return b""

        try:
            # Concatenate all frames
            audio_data = np.concatenate([frame.samples for frame in frames])

            # Convert float32 to int16
            # Clamp to [-1.0, 1.0] range and scale to int16
            audio_data = np.clip(audio_data, -1.0, 1.0)
            audio_int16 = (audio_data * 32767).astype(np.int16)

            return audio_int16.tobytes()

        except Exception as exc:
            self._logger.error(
                "ffmpeg.discord_pcm_failed", error=str(exc), input_frames=len(frames)
            )
            return b""


class VADChunker:
    """Voice Activity Detection chunker for speech segmentation."""

    def __init__(
        self, aggressiveness: int = 2, padding_ms: int = 200, service_name: str = "common"
    ):
        self.aggressiveness = max(0, min(3, aggressiveness))
        self.padding_ms = padding_ms
        self.padding_frames = max(1, padding_ms // 20)  # Convert to 20ms frames
        self._logger = get_logger(__name__, service_name=service_name)

        self._vad = webrtcvad.Vad(self.aggressiveness)
        self._speech_frames: List[CanonicalFrame] = []
        self._silence_frames: List[CanonicalFrame] = []
        self._in_speech = False
        self._speech_start_frame = 0

        # Metrics - disabled to prevent collision
        # TODO: Re-enable metrics with proper singleton pattern
        self._speech_segments = None
        self._vad_errors = None

    def process_frame(self, frame: CanonicalFrame) -> Optional[AudioSegment]:
        """
        Process a canonical frame for speech detection.

        Args:
            frame: Canonical frame to process

        Returns:
            AudioSegment if speech segment is complete, None otherwise
        """
        try:
            # Convert frame to 16kHz for VAD (WebRTC VAD requires 16kHz)
            vad_frame = self._frame_to_vad_format(frame)

            if not vad_frame:
                return None

            is_speech = self._vad.is_speech(vad_frame, 16000)

            if is_speech:
                if not self._in_speech:
                    # Start of speech
                    self._in_speech = True
                    self._speech_start_frame = len(self._speech_frames)
                    self._logger.debug("vad.speech_started", frame_sequence=frame.sequence)

                # Add to speech buffer
                self._speech_frames.append(frame)
                self._silence_frames.clear()

            else:
                if self._in_speech:
                    # Add to silence buffer
                    self._silence_frames.append(frame)

                    # Check if we should end speech segment
                    if len(self._silence_frames) >= self.padding_frames:
                        # End of speech segment
                        segment = self._create_speech_segment()
                        self._reset_buffers()
                        return segment
                else:
                    # Not in speech, clear any accumulated frames
                    self._speech_frames.clear()
                    self._silence_frames.clear()

            return None

        except Exception as exc:
            self._logger.error(
                "vad.process_frame_error", error=str(exc), frame_sequence=frame.sequence
            )
            # Metrics removed
            return None

    def flush(self) -> Optional[AudioSegment]:
        """Flush any remaining speech segment."""
        if self._speech_frames:
            segment = self._create_speech_segment()
            self._reset_buffers()
            return segment
        return None

    def _frame_to_vad_format(self, frame: CanonicalFrame) -> Optional[bytes]:
        """Convert canonical frame to 16kHz format for VAD."""
        try:
            # Resample 48kHz -> 16kHz using simple decimation
            # This is a simplified approach; in production, use proper resampling
            decimation_factor = 3  # 48000 / 16000 = 3
            decimated = frame.samples[::decimation_factor]

            # Convert float32 to int16
            audio_int16 = (decimated * 32767).astype(np.int16)

            # VAD expects exactly 10ms, 20ms, or 30ms frames
            # We have 20ms worth of 16kHz samples (320 samples)
            if len(audio_int16) != 320:
                # Pad or truncate to exactly 320 samples
                if len(audio_int16) < 320:
                    padded = np.zeros(320, dtype=np.int16)
                    padded[: len(audio_int16)] = audio_int16
                    audio_int16 = padded
                else:
                    audio_int16 = audio_int16[:320]

            return audio_int16.tobytes()

        except Exception as exc:
            self._logger.error(
                "vad.frame_conversion_error", error=str(exc), frame_sequence=frame.sequence
            )
            return None

    def _create_speech_segment(self) -> AudioSegment:
        """Create speech segment from buffered frames."""
        if not self._speech_frames:
            raise ValueError("No speech frames to create segment")

        # Add padding frames
        all_frames = self._speech_frames + self._silence_frames

        start_timestamp = all_frames[0].timestamp
        end_timestamp = all_frames[-1].timestamp + 0.02  # Add frame duration

        # Generate correlation ID
        from .correlation import generate_discord_correlation_id

        correlation_id = generate_discord_correlation_id(0)  # TODO: Get actual user_id

        segment = AudioSegment(
            frames=all_frames,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            correlation_id=correlation_id,
            user_id=0,  # TODO: Get actual user_id
        )

        # Metrics removed

        self._logger.info(
            "vad.speech_segment_created",
            correlation_id=correlation_id,
            frame_count=len(all_frames),
            duration=segment.duration,
        )

        return segment

    def _reset_buffers(self):
        """Reset internal buffers."""
        self._speech_frames.clear()
        self._silence_frames.clear()
        self._in_speech = False
        self._speech_start_frame = 0


class AudioPipeline:
    """
    Main audio pipeline orchestrating the canonical audio contract.

    This class implements the Audio-to-Text (A2T) and Text-to-Audio (T2A) pipelines
    according to the specification, ensuring all audio processing follows the
    canonical frame format and boundary conversion rules.
    """

    def __init__(self, service_name: str = "common"):
        self.service_name = service_name
        self._logger = get_logger(__name__, service_name=service_name)

        # Initialize components
        self._ffmpeg = FFmpegFacade(service_name)
        self._jitter_buffer = JitterBuffer()
        self._vad_chunker = VADChunker(service_name=service_name)

        # Metrics - disabled to prevent collision
        # TODO: Re-enable metrics with proper singleton pattern
        self._frames_processed = None
        self._frames_dropped = None
        self._segments_created = None
        self._jitter_depth = None

    def process_discord_audio(
        self, audio_data: bytes, user_id: int, input_format: str = "opus"
    ) -> List[AudioSegment]:
        """
        Process Discord audio data through the A2T pipeline.

        Args:
            audio_data: Raw audio data from Discord
            user_id: Discord user ID
            input_format: Input format (opus, pcm, etc.)

        Returns:
            List of speech segments ready for STT
        """
        # Step 1: Decode to canonical frames
        frames = self._ffmpeg.decode_to_canonical(audio_data, input_format)
        if not frames:
            return []

        # Step 2: Process through jitter buffer
        segments = []
        for frame in frames:
            # Add frame to jitter buffer
            emitted_frames = self._jitter_buffer.add_frame(frame)

            # Process emitted frames through VAD
            for emitted_frame in emitted_frames:
                segment = self._vad_chunker.process_frame(emitted_frame)
                if segment:
                    segments.append(segment)

            # Update metrics
            # Metrics removed

        # Flush any remaining speech segment
        final_segment = self._vad_chunker.flush()
        if final_segment:
            segments.append(final_segment)

        # Metrics removed

        return segments

    def prepare_stt_audio(self, segment: AudioSegment) -> bytes:
        """
        Prepare audio segment for STT processing (resample to 16kHz).

        Args:
            segment: Speech segment

        Returns:
            PCM bytes at 16kHz mono for STT
        """
        return self._ffmpeg.resample_for_stt(segment.frames)

    def process_tts_audio(
        self, audio_bytes: bytes, input_format: str = "wav"
    ) -> List[CanonicalFrame]:
        """
        Process TTS audio data through the T2A pipeline.

        Args:
            audio_bytes: TTS audio data
            input_format: Input format (wav, mp3, etc.)

        Returns:
            List of canonical frames ready for Discord playback
        """
        # Step 1: Decode to canonical frames
        frames = self._ffmpeg.decode_to_canonical(audio_bytes, input_format)
        if not frames:
            return []

        # Step 2: Apply loudness normalization
        normalized_frames = self._ffmpeg.loudness_normalize(frames)

        return normalized_frames

    def frames_to_discord_playback(self, frames: List[CanonicalFrame]) -> bytes:
        """
        Convert canonical frames to Discord playback format.

        Args:
            frames: List of canonical frames

        Returns:
            PCM bytes in s16le format for Discord
        """
        return self._ffmpeg.frames_to_discord_pcm(frames)

    def create_silence_frame(self, duration_ms: float = 20.0) -> CanonicalFrame:
        """
        Create a silence frame for underrun handling.

        Args:
            duration_ms: Frame duration in milliseconds

        Returns:
            Silence canonical frame
        """
        if duration_ms != 20.0:
            raise ValueError("Only 20ms frames are supported")

        silence_samples = np.zeros(960, dtype=np.float32)

        return CanonicalFrame(
            samples=silence_samples, timestamp=time.monotonic(), sequence=0  # Will be set by caller
        )


# Convenience functions for backward compatibility
def create_audio_pipeline(service_name: str = "common") -> AudioPipeline:
    """Create an audio pipeline for a specific service."""
    return AudioPipeline(service_name)


def create_canonical_frame(samples: np.ndarray, timestamp: float, sequence: int) -> CanonicalFrame:
    """Create a canonical frame with validation."""
    return CanonicalFrame(samples=samples, timestamp=timestamp, sequence=sequence)


__all__ = [
    "CanonicalFrame",
    "AudioSegment",
    "JitterBuffer",
    "VADChunker",
    "FFmpegFacade",
    "AudioPipeline",
    "AudioFormat",
    "create_audio_pipeline",
    "create_canonical_frame",
]
