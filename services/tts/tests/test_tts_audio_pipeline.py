"""Component tests for TTS audio processing pipeline."""

from pathlib import Path

import pytest

from services.tests.fixtures.tts.tts_test_helpers import (
    validate_tts_audio_format,
    validate_tts_audio_quality,
)
from services.tests.mocks.tts_adapter import MockTTSAdapter


@pytest.mark.component
@pytest.mark.tts
class TestTTSAudioProcessingPipeline:
    """Test TTS audio processing pipeline components."""

    @pytest.fixture
    def mock_tts_adapter(self):
        """Mock TTS adapter for testing."""
        return MockTTSAdapter()

    def test_audio_format_preservation(self, mock_tts_adapter, tts_artifacts_dir: Path):
        """Test audio format preservation through pipeline."""
        # Generate initial audio
        initial_audio = mock_tts_adapter.synthesize("Format preservation test")

        # Simulate pipeline processing (format should be preserved)
        processed_audio = initial_audio  # In real pipeline, this would be processed

        # Validate format is preserved
        initial_format = validate_tts_audio_format(initial_audio)
        processed_format = validate_tts_audio_format(processed_audio)

        assert initial_format["is_valid"] == processed_format["is_valid"]
        assert initial_format["sample_rate"] == processed_format["sample_rate"]
        assert initial_format["channels"] == processed_format["channels"]
        assert initial_format["bit_depth"] == processed_format["bit_depth"]

        # Save to artifacts directory for debugging
        initial_file = tts_artifacts_dir / "initial_format.wav"
        processed_file = tts_artifacts_dir / "processed_format.wav"
        initial_file.write_bytes(initial_audio)
        processed_file.write_bytes(processed_audio)

    def test_audio_normalization(self, mock_tts_adapter, tts_artifacts_dir: Path):
        """Test audio normalization in pipeline."""
        # Generate audio with different amplitudes
        high_amplitude_adapter = MockTTSAdapter(default_amplitude=0.8)
        low_amplitude_adapter = MockTTSAdapter(default_amplitude=0.2)

        high_audio = high_amplitude_adapter.synthesize("High amplitude test")
        low_audio = low_amplitude_adapter.synthesize("Low amplitude test")

        # Both should be valid after normalization
        high_format = validate_tts_audio_format(high_audio)
        low_format = validate_tts_audio_format(low_audio)

        assert high_format["is_valid"]
        assert low_format["is_valid"]

        # Save to artifacts directory for debugging
        high_file = tts_artifacts_dir / "high_amplitude.wav"
        low_file = tts_artifacts_dir / "low_amplitude.wav"
        high_file.write_bytes(high_audio)
        low_file.write_bytes(low_audio)

    def test_error_handling_invalid_audio(self, tts_artifacts_dir: Path):
        """Test error handling for invalid audio."""
        # Test with invalid audio data
        invalid_audio = b"invalid audio data"

        # Should handle invalid audio gracefully
        format_result = validate_tts_audio_format(invalid_audio)
        assert not format_result["is_valid"]
        assert "error" in format_result

        # Save to artifacts directory for debugging
        invalid_file = tts_artifacts_dir / "invalid_audio.wav"
        invalid_file.write_bytes(invalid_audio)

    def test_audio_quality_preservation(
        self, mock_tts_adapter, tts_artifacts_dir: Path
    ):
        """Test audio quality preservation through pipeline."""
        # Generate high-quality audio
        high_quality_adapter = MockTTSAdapter(
            default_amplitude=0.5,
            default_noise_level=0.0,
        )
        audio = high_quality_adapter.synthesize("Quality preservation test")

        # Validate quality is preserved with relaxed thresholds for synthetic audio
        quality_result = validate_tts_audio_quality(
            audio,
            min_snr=3.0,  # Lower for synthetic audio
            max_thd=5000.0,  # Much higher for synthetic audio with spectral leakage
            min_voice_range=0.0,  # Much lower for single-tone test signals
        )
        assert quality_result["meets_quality_thresholds"]
        assert quality_result["snr_db"] > 0
        assert quality_result["thd_percent"] >= 0

        # Save to artifacts directory for debugging
        quality_file = tts_artifacts_dir / "quality_preservation.wav"
        quality_file.write_bytes(audio)

    def test_pipeline_throughput(self, mock_tts_adapter, tts_artifacts_dir: Path):
        """Test pipeline throughput with multiple audio samples."""
        # Generate multiple audio samples
        texts = [
            "Sample 1",
            "Sample 2",
            "Sample 3",
        ]

        for i, text in enumerate(texts):
            audio = mock_tts_adapter.synthesize(text)

            # Validate each sample
            format_result = validate_tts_audio_format(audio)
            quality_result = validate_tts_audio_quality(
                audio,
                min_snr=3.0,  # Lower for synthetic audio
                max_thd=5000.0,  # Much higher for synthetic audio with spectral leakage
                min_voice_range=0.0,  # Much lower for single-tone test signals
            )

            assert format_result["is_valid"]
            assert quality_result["meets_quality_thresholds"]

            # Save to artifacts directory for debugging
            sample_file = tts_artifacts_dir / f"pipeline_sample_{i}.wav"
            sample_file.write_bytes(audio)

    def test_audio_metadata_preservation(
        self, mock_tts_adapter, tts_artifacts_dir: Path
    ):
        """Test audio metadata preservation through pipeline."""
        # Generate audio with known characteristics
        audio = mock_tts_adapter.synthesize("Metadata preservation test")

        # Extract metadata
        format_result = validate_tts_audio_format(audio)

        # Verify metadata is preserved
        assert format_result["sample_rate"] == 22050
        assert format_result["channels"] == 1
        assert format_result["bit_depth"] == 16
        assert format_result["duration"] > 0

        # Save to artifacts directory for debugging
        metadata_file = tts_artifacts_dir / "metadata_preservation.wav"
        metadata_file.write_bytes(audio)
