"""Voice Activity Detection (VAD) module for frame-level speech detection.

This module provides lightweight VAD functionality using WebRTC VAD for
real-time frame processing. It can be used independently or as part of
the audio processing pipeline.
"""

from __future__ import annotations


import numpy as np
import webrtcvad

from services.common.structured_logging import get_logger
from services.common.surfaces.types import PCMFrame

logger = get_logger(__name__)


class VADProcessor:
    """Voice Activity Detection using WebRTC VAD."""

    def __init__(self, aggressiveness: int = 1) -> None:
        """Initialize VAD processor.

        Args:
            aggressiveness: VAD aggressiveness mode (0=quality, 1=low bitrate, 2=aggressive, 3=very aggressive)
        """
        self._vad = webrtcvad.Vad(aggressiveness)
        self._aggressiveness = aggressiveness
        self._logger = get_logger(__name__)

    async def detect_speech(self, frame: PCMFrame) -> bool:
        """Detect if frame contains speech.

        Args:
            frame: PCM frame to analyze

        Returns:
            True if speech detected, False otherwise
        """
        try:
            # Convert to 16kHz for VAD (required by webrtcvad)
            frame_bytes, sample_rate = self._prepare_frame_for_vad(frame)

            # Apply VAD
            is_speech: bool = self._vad.is_speech(frame_bytes, sample_rate)

            # Log VAD decisions for debugging (first few calls and occasional samples)
            if not hasattr(self, "_vad_call_count"):
                self._vad_call_count = 0
            self._vad_call_count += 1

            if self._vad_call_count <= 10 or self._vad_call_count % 100 == 0:
                frame_rms = np.frombuffer(frame.pcm, dtype=np.int16)
                frame_rms = np.sqrt(np.mean(frame_rms.astype(np.float32) ** 2))
                self._logger.debug(
                    "audio_vad.detection_result",
                    is_speech=is_speech,
                    input_sample_rate=frame.sample_rate,
                    input_samples=len(frame.pcm) // 2,
                    vad_sample_rate=sample_rate,
                    vad_samples=len(frame_bytes) // 2,
                    frame_rms=float(frame_rms),
                    aggressiveness=self._aggressiveness,
                )

            return is_speech

        except Exception as exc:
            self._logger.warning(
                "audio_vad.detection_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                frame_sample_rate=frame.sample_rate if frame else None,
                frame_pcm_len=len(frame.pcm) if frame and frame.pcm else None,
            )
            # Default to speech on error to avoid false negatives
            return True

    async def apply_vad(self, frame: PCMFrame) -> PCMFrame:
        """Apply voice activity detection to frame and modify if non-speech.

        Args:
            frame: PCM frame to process

        Returns:
            Frame with VAD applied (volume reduced for non-speech frames)
        """
        try:
            # Convert to 16kHz for VAD (required by webrtcvad)
            frame_bytes, sample_rate = self._prepare_frame_for_vad(frame)

            # Apply VAD
            is_speech = self._vad.is_speech(frame_bytes, sample_rate)

            # Update frame based on VAD result
            if not is_speech:
                # Reduce volume for non-speech frames
                frame_data = np.frombuffer(frame.pcm, dtype=np.int16)
                frame_data = (frame_data * 0.1).astype(np.int16)
                frame.pcm = frame_data.tobytes()

            return frame

        except Exception as exc:
            self._logger.warning("audio_vad.vad_failed", error=str(exc))
            return frame

    def _prepare_frame_for_vad(self, frame: PCMFrame) -> tuple[bytes, int]:
        """Prepare frame for VAD by converting to 16kHz if needed.

        Args:
            frame: PCM frame to prepare

        Returns:
            Tuple of (frame bytes, sample rate)
        """
        target_sample_rate = 16000

        # If already at 16kHz, use directly
        if frame.sample_rate == target_sample_rate:
            # Ensure frame is correct length for VAD (10ms, 20ms, or 30ms)
            frame_duration_ms = 20  # Use 20ms frames (320 samples at 16kHz)
            frame_length = int(target_sample_rate * frame_duration_ms / 1000)

            frame_data = np.frombuffer(frame.pcm, dtype=np.int16)
            if len(frame_data) > frame_length:
                # Take first 20ms for VAD (discard remainder)
                frame_data = frame_data[:frame_length]
            elif len(frame_data) < frame_length:
                # Pad with zeros if too short
                frame_data = np.pad(
                    frame_data, (0, frame_length - len(frame_data)), mode="constant"
                )

            return frame_data.astype(np.int16).tobytes(), target_sample_rate

        # Convert to 16kHz for VAD
        frame_data = np.frombuffer(frame.pcm, dtype=np.int16)
        if frame.sample_rate > target_sample_rate:
            # Downsample
            ratio = frame.sample_rate // target_sample_rate
            frame_data = frame_data[::ratio]
        else:
            # Upsample (simple repeat)
            ratio = target_sample_rate // frame.sample_rate
            frame_data = np.repeat(frame_data, ratio)

        # Ensure frame is correct length for VAD (10ms, 20ms, or 30ms)
        # Use 20ms frames for better compatibility with 40ms Discord frames
        # (split 40ms into two 20ms chunks would be ideal, but for now use 20ms)
        frame_duration_ms = 20  # Use 20ms frames (320 samples at 16kHz)
        frame_length = int(target_sample_rate * frame_duration_ms / 1000)

        if len(frame_data) > frame_length:
            # Take first 20ms for VAD (discard remainder)
            frame_data = frame_data[:frame_length]
        elif len(frame_data) < frame_length:
            # Pad with zeros if too short
            frame_data = np.pad(
                frame_data, (0, frame_length - len(frame_data)), mode="constant"
            )

        frame_bytes = frame_data.astype(np.int16).tobytes()
        return frame_bytes, target_sample_rate
