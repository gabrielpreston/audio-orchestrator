"""Tests for audio quality metrics calculation."""

import numpy as np
import pytest

from services.common.audio_quality import AudioQualityMetrics
from services.common.surfaces.types import AudioSegment, PCMFrame


@pytest.fixture
def sample_pcm_bytes():
    """Create sample PCM bytes for testing."""
    # Generate 1000 samples of a sine wave at 440Hz, 16kHz sample rate
    sample_rate = 16000
    duration = 1000 / sample_rate  # 1000 samples
    t = np.linspace(0, duration, 1000, False)
    frequency = 440.0
    audio_data = np.sin(2 * np.pi * frequency * t)
    # Convert to int16 PCM
    pcm_bytes = (audio_data * 32767).astype(np.int16).tobytes()
    return pcm_bytes


@pytest.fixture
def silent_pcm_bytes():
    """Create silent PCM bytes (all zeros)."""
    return b"\x00\x00" * 1000  # 1000 samples of zeros


@pytest.fixture
def constant_pcm_bytes():
    """Create constant PCM bytes (all same value)."""
    return b"\x10\x00" * 1000  # 1000 samples of constant value


@pytest.mark.asyncio
async def test_calculate_metrics_with_valid_audio(sample_pcm_bytes):
    """Test quality metrics calculation with valid audio."""
    frame = PCMFrame(
        pcm=sample_pcm_bytes,
        sample_rate=16000,
        timestamp=0.0,
        duration=0.0625,  # 1000 samples / 16000
        rms=0.5,
        sequence=0,
        channels=1,
        sample_width=2,
    )

    metrics = await AudioQualityMetrics.calculate_metrics(frame)

    assert "rms" in metrics
    assert "snr_db" in metrics
    assert "clarity_score" in metrics
    assert "dominant_frequency_hz" in metrics
    assert "sample_rate" in metrics
    assert "duration_ms" in metrics

    # Valid audio should have positive RMS
    assert metrics["rms"] > 0
    # SNR should be finite (not -Infinity)
    assert np.isfinite(metrics["snr_db"])
    # Clarity score should be between 0 and 1
    assert 0.0 <= metrics["clarity_score"] <= 1.0
    # Dominant frequency should be around 440Hz
    assert 400 <= metrics["dominant_frequency_hz"] <= 500


@pytest.mark.asyncio
async def test_calculate_metrics_with_silent_audio(silent_pcm_bytes):
    """Test quality metrics calculation with silent audio (all zeros)."""
    frame = PCMFrame(
        pcm=silent_pcm_bytes,
        sample_rate=16000,
        timestamp=0.0,
        duration=0.0625,
        rms=0.0,
        sequence=0,
        channels=1,
        sample_width=2,
    )

    metrics = await AudioQualityMetrics.calculate_metrics(frame)

    assert metrics["rms"] == 0.0
    assert metrics["snr_db"] == -np.inf
    assert metrics["clarity_score"] == 0.0
    assert metrics["dominant_frequency_hz"] == 0.0
    assert metrics["sample_rate"] == 16000


@pytest.mark.asyncio
async def test_calculate_metrics_with_constant_audio(constant_pcm_bytes):
    """Test quality metrics calculation with constant audio."""
    frame = PCMFrame(
        pcm=constant_pcm_bytes,
        sample_rate=16000,
        timestamp=0.0,
        duration=0.0625,
        rms=0.001,  # Very low RMS
        sequence=0,
        channels=1,
        sample_width=2,
    )

    metrics = await AudioQualityMetrics.calculate_metrics(frame)

    # Constant audio should have valid metrics (may or may not be detected as silent)
    assert metrics["rms"] >= 0.0
    # SNR should be finite (constant audio may have positive or negative SNR)
    assert np.isfinite(metrics["snr_db"]) or metrics["snr_db"] == -np.inf
    assert 0.0 <= metrics["clarity_score"] <= 1.0


@pytest.mark.asyncio
async def test_calculate_metrics_with_very_short_audio():
    """Test quality metrics calculation with very short audio (< 10 samples)."""
    # Create very short audio (5 samples)
    short_pcm = b"\x00\x01\x02\x03\x04" * 2  # 10 bytes = 5 samples
    frame = PCMFrame(
        pcm=short_pcm,
        sample_rate=16000,
        timestamp=0.0,
        duration=0.0003125,  # 5 samples / 16000
        rms=0.001,
        sequence=0,
        channels=1,
        sample_width=2,
    )

    # Should not crash
    metrics = await AudioQualityMetrics.calculate_metrics(frame)

    assert "rms" in metrics
    assert "snr_db" in metrics
    assert "clarity_score" in metrics


@pytest.mark.asyncio
async def test_calculate_metrics_with_audio_segment(sample_pcm_bytes):
    """Test quality metrics calculation with AudioSegment."""
    segment = AudioSegment(
        user_id="test",
        pcm=sample_pcm_bytes,
        start_timestamp=0.0,
        end_timestamp=0.0625,
        correlation_id="test-123",
        frame_count=1,
        sample_rate=16000,
    )

    metrics = await AudioQualityMetrics.calculate_metrics(segment)

    assert "rms" in metrics
    assert "snr_db" in metrics
    assert "clarity_score" in metrics
    assert metrics["sample_rate"] == 16000


@pytest.mark.asyncio
async def test_calculate_metrics_handles_infinity_gracefully(silent_pcm_bytes):
    """Test that -Infinity SNR is handled gracefully in clarity_score."""
    frame = PCMFrame(
        pcm=silent_pcm_bytes,
        sample_rate=16000,
        timestamp=0.0,
        duration=0.0625,
        rms=0.0,
        sequence=0,
        channels=1,
        sample_width=2,
    )

    metrics = await AudioQualityMetrics.calculate_metrics(frame)

    # Clarity score should be 0.0, not -Infinity
    assert metrics["clarity_score"] == 0.0
    assert not np.isinf(metrics["clarity_score"])


def test_validate_quality_thresholds_passes():
    """Test quality threshold validation with good metrics."""
    metrics = {
        "rms": 200.0,
        "snr_db": 25.0,
        "clarity_score": 0.8,
    }

    result = AudioQualityMetrics.validate_quality_thresholds(metrics)

    assert result["meets_thresholds"] is True
    assert len(result["failures"]) == 0


def test_validate_quality_thresholds_fails():
    """Test quality threshold validation with poor metrics."""
    metrics = {
        "rms": 50.0,  # Below minimum 100.0
        "snr_db": 5.0,  # Below minimum 10.0
        "clarity_score": 0.2,  # Below minimum 0.3
    }

    result = AudioQualityMetrics.validate_quality_thresholds(metrics)

    assert result["meets_thresholds"] is False
    assert len(result["failures"]) > 0


def test_validate_quality_thresholds_with_infinity():
    """Test quality threshold validation with -Infinity SNR."""
    metrics = {
        "rms": 0.0,
        "snr_db": -np.inf,
        "clarity_score": 0.0,
    }

    result = AudioQualityMetrics.validate_quality_thresholds(metrics)

    # Should handle -Infinity gracefully
    assert result["snr_db"] == -np.inf
    assert result["meets_thresholds"] is False
    assert len(result["failures"]) > 0
