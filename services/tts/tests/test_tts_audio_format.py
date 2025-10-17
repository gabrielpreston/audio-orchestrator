"""Unit tests for TTS audio format validation."""

import pytest

from services.tests.fixtures.tts.tts_test_helpers import validate_tts_audio_format
from services.tests.utils.audio_quality_helpers import (
    create_wav_file,
    generate_test_audio,
)


@pytest.mark.unit
@pytest.mark.tts
class TestTTSAudioFormatValidation:
    """Test TTS audio format validation functions."""

    def test_validate_tts_wav_format(self):
        """Test WAV format validation for TTS audio."""
        # Generate test audio
        pcm_data = generate_test_audio(
            duration=1.0,
            sample_rate=22050,
            frequency=440.0,
            amplitude=0.5,
        )
        wav_data = create_wav_file(pcm_data, sample_rate=22050, channels=1)

        # Validate format
        result = validate_tts_audio_format(wav_data)

        assert result["is_valid"]
        assert result["tts_requirements"]["sample_rate_ok"]
        assert result["tts_requirements"]["channels_ok"]
        assert result["tts_requirements"]["bit_depth_ok"]
        assert result["tts_requirements"]["duration_ok"]
        assert result["is_tts_compliant"]

    def test_validate_tts_sample_rate(self):
        """Test 22.05kHz sample rate validation."""
        # Generate audio with correct sample rate
        pcm_data = generate_test_audio(
            duration=1.0,
            sample_rate=22050,
            frequency=440.0,
            amplitude=0.5,
        )
        wav_data = create_wav_file(pcm_data, sample_rate=22050, channels=1)

        result = validate_tts_audio_format(wav_data)

        assert result["sample_rate"] == 22050
        assert result["tts_requirements"]["sample_rate_ok"]

    def test_validate_tts_channels(self):
        """Test mono audio validation."""
        # Generate mono audio
        pcm_data = generate_test_audio(
            duration=1.0,
            sample_rate=22050,
            frequency=440.0,
            amplitude=0.5,
        )
        wav_data = create_wav_file(pcm_data, sample_rate=22050, channels=1)

        result = validate_tts_audio_format(wav_data)

        assert result["channels"] == 1
        assert result["tts_requirements"]["channels_ok"]

    def test_validate_tts_bit_depth(self):
        """Test 16-bit validation."""
        # Generate 16-bit audio
        pcm_data = generate_test_audio(
            duration=1.0,
            sample_rate=22050,
            frequency=440.0,
            amplitude=0.5,
        )
        wav_data = create_wav_file(pcm_data, sample_rate=22050, channels=1)

        result = validate_tts_audio_format(wav_data)

        assert result["bit_depth"] == 16
        assert result["tts_requirements"]["bit_depth_ok"]

    def test_validate_tts_duration(self):
        """Test minimum duration validation."""
        # Generate short audio
        pcm_data = generate_test_audio(
            duration=0.2,  # Longer than 0.1s minimum
            sample_rate=22050,
            frequency=440.0,
            amplitude=0.5,
        )
        wav_data = create_wav_file(pcm_data, sample_rate=22050, channels=1)

        result = validate_tts_audio_format(wav_data)

        assert result["duration"] > 0.1
        assert result["tts_requirements"]["duration_ok"]

    def test_invalid_tts_format_rejection(self):
        """Test rejection of invalid TTS format."""
        # Create invalid audio data
        invalid_audio = b"invalid wav data"

        result = validate_tts_audio_format(invalid_audio)

        assert not result["is_valid"]
        assert not result["is_tts_compliant"]
        assert "error" in result

    def test_wrong_sample_rate_rejection(self):
        """Test rejection of wrong sample rate."""
        # Generate audio with wrong sample rate
        pcm_data = generate_test_audio(
            duration=1.0,
            sample_rate=16000,  # Wrong sample rate
            frequency=440.0,
            amplitude=0.5,
        )
        wav_data = create_wav_file(pcm_data, sample_rate=16000, channels=1)

        result = validate_tts_audio_format(wav_data)

        assert not result["tts_requirements"]["sample_rate_ok"]
        assert not result["is_tts_compliant"]

    def test_wrong_channels_rejection(self):
        """Test rejection of stereo audio."""
        # Generate stereo audio
        pcm_data = generate_test_audio(
            duration=1.0,
            sample_rate=22050,
            frequency=440.0,
            amplitude=0.5,
        )
        wav_data = create_wav_file(pcm_data, sample_rate=22050, channels=2)

        result = validate_tts_audio_format(wav_data)

        assert not result["tts_requirements"]["channels_ok"]
        assert not result["is_tts_compliant"]
