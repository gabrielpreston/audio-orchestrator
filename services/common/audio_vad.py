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
            return is_speech

        except Exception as exc:
            self._logger.warning("audio_vad.detection_failed", error=str(exc))
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
            frame_duration_ms = 30  # Use 30ms frames
            frame_length = int(target_sample_rate * frame_duration_ms / 1000)

            frame_data = np.frombuffer(frame.pcm, dtype=np.int16)
            if len(frame_data) > frame_length:
                frame_data = frame_data[:frame_length]
            elif len(frame_data) < frame_length:
                frame_data = np.pad(frame_data, (0, frame_length - len(frame_data)))

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
        frame_duration_ms = 30  # Use 30ms frames
        frame_length = int(target_sample_rate * frame_duration_ms / 1000)

        if len(frame_data) > frame_length:
            frame_data = frame_data[:frame_length]
        elif len(frame_data) < frame_length:
            frame_data = np.pad(frame_data, (0, frame_length - len(frame_data)))

        frame_bytes = frame_data.astype(np.int16).tobytes()
        return frame_bytes, target_sample_rate
