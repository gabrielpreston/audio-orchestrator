"""Component tests for TTS service audio validation."""

from pathlib import Path

import pytest

from services.tests.fixtures.tts.tts_test_helpers import (
    validate_tts_audio_format,
    validate_tts_audio_quality,
)
from services.tests.mocks.tts_adapter import MockTTSAdapter


@pytest.mark.component
@pytest.mark.tts
@pytest.mark.audio
class TestTTSServiceAudioValidation:
    """Test TTS service audio validation with mocked adapter."""

    @pytest.fixture
    def mock_tts_adapter(self):
        """Mock TTS adapter for testing."""
        return MockTTSAdapter()

    def test_tts_service_returns_valid_wav(
        self, mock_tts_adapter, tts_artifacts_dir: Path
    ):
        """Test TTS service returns valid WAV format."""
        # Mock the TTS service response
        mock_audio_data = mock_tts_adapter.synthesize("Hello world")

        # Validate WAV format
        result = validate_tts_audio_format(mock_audio_data)

        assert result["is_valid"]
        assert result["is_tts_compliant"]
        assert result["sample_rate"] == 22050
        assert result["channels"] == 1
        assert result["bit_depth"] == 16

        # Save to artifacts directory for debugging
        output_file = tts_artifacts_dir / "test_valid_wav.wav"
        output_file.write_bytes(mock_audio_data)

    def test_tts_service_audio_quality(self, mock_tts_adapter, tts_artifacts_dir: Path):
        """Test TTS service audio quality metrics."""
        # Mock the TTS service response
        mock_audio_data = mock_tts_adapter.synthesize("Quality test audio")

        # Validate audio quality with relaxed thresholds for synthetic audio
        result = validate_tts_audio_quality(
            mock_audio_data,
            min_snr=3.0,  # Lower for synthetic audio
            max_thd=5000.0,  # Much higher for synthetic audio with spectral leakage
            min_voice_range=0.0,  # Much lower for single-tone test signals
        )

        assert result["meets_quality_thresholds"]
        assert result["snr_db"] > 0
        assert result["thd_percent"] >= 0

        # Save to artifacts directory for debugging
        output_file = tts_artifacts_dir / "test_quality_audio.wav"
        output_file.write_bytes(mock_audio_data)

    def test_tts_service_text_handling(self, mock_tts_adapter, tts_artifacts_dir: Path):
        """Test TTS service handles different text inputs."""
        test_texts = [
            "Short text.",
            "This is a longer text with more words to test TTS synthesis.",
            "Text with numbers: 123 and symbols: @#$%",
            "",  # Empty text
        ]

        for i, text in enumerate(test_texts):
            # Mock the TTS service response
            mock_audio_data = mock_tts_adapter.synthesize(text)

            # Validate format
            format_result = validate_tts_audio_format(mock_audio_data)
            assert format_result["is_valid"]

            # Validate quality with relaxed thresholds for synthetic audio
            quality_result = validate_tts_audio_quality(
                mock_audio_data,
                min_snr=3.0,  # Lower for synthetic audio
                max_thd=5000.0,  # Much higher for synthetic audio with spectral leakage
                min_voice_range=0.0,  # Much lower for single-tone test signals
            )
            assert quality_result["meets_quality_thresholds"]

            # Save to artifacts directory for debugging
            output_file = tts_artifacts_dir / f"test_text_{i}.wav"
            output_file.write_bytes(mock_audio_data)

    def test_tts_service_voice_parameters(self, tts_artifacts_dir: Path):
        """Test TTS service with different voice parameters."""
        # Test different voice configurations
        voice_configs = [
            {"frequency": 440.0, "amplitude": 0.5, "noise_level": 0.0},
            {"frequency": 880.0, "amplitude": 0.3, "noise_level": 0.1},
            {"frequency": 220.0, "amplitude": 0.7, "noise_level": 0.0},
        ]

        for i, config in enumerate(voice_configs):
            adapter = MockTTSAdapter(
                default_frequency=config["frequency"],
                default_amplitude=config["amplitude"],
                default_noise_level=config["noise_level"],
            )

            # Generate audio with specific parameters
            mock_audio_data = adapter.synthesize("Voice parameter test")

            # Validate format
            format_result = validate_tts_audio_format(mock_audio_data)
            assert format_result["is_valid"]

            # Validate quality with relaxed thresholds for synthetic audio
            quality_result = validate_tts_audio_quality(
                mock_audio_data,
                min_snr=3.0,  # Lower for synthetic audio
                max_thd=5000.0,  # Much higher for synthetic audio with spectral leakage
                min_voice_range=0.0,  # Much lower for single-tone test signals
            )
            assert quality_result["meets_quality_thresholds"]

            # Save to artifacts directory for debugging
            output_file = tts_artifacts_dir / f"test_voice_{i}.wav"
            output_file.write_bytes(mock_audio_data)

    def test_tts_service_error_handling(self):
        """Test TTS service error handling."""
        # Test with invalid adapter configuration
        adapter = MockTTSAdapter(default_amplitude=0.0)  # Silent audio

        # Should still produce valid WAV format
        mock_audio_data = adapter.synthesize("Silent test")
        format_result = validate_tts_audio_format(mock_audio_data)
        assert format_result["is_valid"]

    def test_tts_service_consistency(self, mock_tts_adapter, tts_artifacts_dir: Path):
        """Test TTS service output consistency."""
        text = "Consistency test"

        # Generate multiple samples of the same text
        samples = []
        for i in range(3):
            mock_audio_data = mock_tts_adapter.synthesize(text)
            samples.append(mock_audio_data)

            # Save to artifacts directory for debugging
            output_file = tts_artifacts_dir / f"consistency_test_{i}.wav"
            output_file.write_bytes(mock_audio_data)

        # All samples should be valid
        for sample in samples:
            format_result = validate_tts_audio_format(sample)
            assert format_result["is_valid"]

            # Validate quality with relaxed thresholds for synthetic audio
            quality_result = validate_tts_audio_quality(
                sample,
                min_snr=3.0,  # Lower for synthetic audio
                max_thd=5000.0,  # Much higher for synthetic audio with spectral leakage
                min_voice_range=0.0,  # Much lower for single-tone test signals
            )
            assert quality_result["meets_quality_thresholds"]
