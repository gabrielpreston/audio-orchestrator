"""Shared fixtures for Discord component tests."""

import numpy as np
import pytest

from services.discord.audio import AudioSegment


@pytest.fixture
def sample_pcm_audio() -> bytes:
    """Generate sample PCM audio data."""
    # Generate 1 second of 16kHz mono audio with sine wave
    sample_rate = 16000
    duration = 1.0
    frequency = 440  # A4 note

    t = np.linspace(0, duration, int(sample_rate * duration), False)
    audio_float = np.sin(2 * np.pi * frequency * t) * 0.5  # 50% amplitude
    audio_int16 = (audio_float * 32767).astype(np.int16)
    return audio_int16.tobytes()


@pytest.fixture
def sample_audio_segment_fixture(sample_pcm_audio):
    """Create sample audio segment (default 16kHz)."""
    return AudioSegment(
        user_id=12345,
        pcm=sample_pcm_audio,
        sample_rate=16000,
        start_timestamp=0.0,
        end_timestamp=1.0,
        correlation_id="test-correlation-123",
        frame_count=16000,
    )
