"""Audio processing utilities for LiveKit agent service."""

import asyncio
import io
from typing import Optional, Tuple

import numpy as np
import soundfile as sf
from livekit import rtc
from livekit.agents import AutoSubscribe, WorkerOptions, cli, llm, stt, tts, vad, worker

from ..common.audio import AudioProcessor
from ..common.audio_contracts import AudioFrame, CANONICAL_SAMPLE_RATE, CANONICAL_FRAME_MS


class LiveKitAudioProcessor:
    """Audio processor for LiveKit WebRTC integration."""
    
    def __init__(self):
        self.audio_processor = AudioProcessor("livekit")
        self._opus_decoder = None
        self._opus_encoder = None
    
    async def decode_opus_to_pcm(self, opus_data: bytes) -> bytes:
        """Decode Opus audio data to PCM format."""
        try:
            # For now, we'll use a simple approach
            # In production, you'd use proper Opus decoding
            # This is a placeholder that assumes the data is already PCM
            return opus_data
        except Exception as e:
            raise RuntimeError(f"Failed to decode Opus audio: {e}")
    
    async def encode_pcm_to_opus(self, pcm_data: bytes, sample_rate: int = CANONICAL_SAMPLE_RATE) -> bytes:
        """Encode PCM audio data to Opus format."""
        try:
            # For now, we'll use a simple approach
            # In production, you'd use proper Opus encoding
            # This is a placeholder that assumes the data is already in the right format
            return pcm_data
        except Exception as e:
            raise RuntimeError(f"Failed to encode PCM to Opus: {e}")
    
    def create_audio_frame(
        self,
        pcm_data: bytes,
        timestamp: float,
        sequence_number: int = 0,
        is_speech: bool = False,
        is_endpoint: bool = False,
        confidence: float = 0.0
    ) -> AudioFrame:
        """Create a canonical audio frame from PCM data."""
        return AudioFrame(
            pcm_data=pcm_data,
            sample_rate=CANONICAL_SAMPLE_RATE,
            channels=1,
            sample_width=2,
            bit_depth=16,
            timestamp=timestamp,
            frame_duration_ms=CANONICAL_FRAME_MS,
            sequence_number=sequence_number,
            is_speech=is_speech,
            is_endpoint=is_endpoint,
            confidence=confidence
        )
    
    def resample_audio(
        self,
        pcm_data: bytes,
        from_rate: int,
        to_rate: int = CANONICAL_SAMPLE_RATE
    ) -> bytes:
        """Resample audio data to canonical format."""
        if from_rate == to_rate:
            return pcm_data
        
        return self.audio_processor.resample_audio(
            pcm_data,
            from_rate=from_rate,
            to_rate=to_rate,
            channels=1,
            sample_width=2
        )
    
    def normalize_audio(self, pcm_data: bytes) -> Tuple[bytes, float]:
        """Normalize audio data."""
        return self.audio_processor.normalize_audio(pcm_data, sample_width=2)
    
    def calculate_rms(self, pcm_data: bytes) -> float:
        """Calculate RMS level of audio data."""
        return self.audio_processor.calculate_rms(pcm_data, sample_width=2)
    
    def validate_audio_frame(self, frame: AudioFrame) -> bool:
        """Validate audio frame structure."""
        if not frame.pcm_data:
            return False
        
        expected_bytes = frame.expected_bytes
        actual_bytes = len(frame.pcm_data)
        
        # Allow some tolerance for frame size variations
        tolerance = expected_bytes // 10  # 10% tolerance
        return abs(actual_bytes - expected_bytes) <= tolerance