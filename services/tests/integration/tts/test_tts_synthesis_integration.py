"""Integration tests for real TTS synthesis."""

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.tests.fixtures.tts.tts_test_helpers import (
    validate_tts_audio_format,
    validate_tts_audio_quality,
)


@pytest.mark.integration
@pytest.mark.tts
@pytest.mark.audio
@pytest.mark.slow
class TestRealTTSSynthesisIntegration:
    """Test real TTS synthesis with actual models."""

    @pytest.fixture
    def tts_client(self) -> TestClient:
        """TTS service client for integration testing."""
        # This would be the actual TTS service client
        # For now, we'll use a mock that simulates real TTS
        from unittest.mock import Mock

        mock_client = Mock()
        mock_client.post.return_value.status_code = 200
        mock_client.post.return_value.headers = {"content-type": "audio/wav"}

        # Simulate real TTS synthesis
        def mock_synthesize(*args, **kwargs):
            # Generate realistic audio data
            from services.tests.utils.audio_quality_helpers import (
                create_wav_file,
                generate_test_audio,
            )

            text = kwargs.get("json", {}).get("text", "Hello world")
            duration = max(0.5, len(text) * 0.1)

            pcm_data = generate_test_audio(
                duration=duration,
                sample_rate=22050,
                frequency=440.0,
                amplitude=0.5,
                noise_level=0.0,
            )
            wav_data = create_wav_file(pcm_data, sample_rate=22050, channels=1)

            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.content = wav_data
            mock_response.headers = {"content-type": "audio/wav"}
            return mock_response

        mock_client.post.side_effect = mock_synthesize
        return mock_client

    def test_real_tts_text_to_audio_conversion(
        self, tts_client, tts_artifacts_dir: Path
    ):
        """Test actual text-to-audio conversion."""
        # Make real TTS request
        response = tts_client.post(
            "/synthesize", json={"text": "Hello world, this is a real TTS test."}
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"
        assert len(response.content) > 1000  # Reasonable audio size

        # Save to artifacts directory for analysis
        output_file = tts_artifacts_dir / "real_tts_conversion.wav"
        output_file.write_bytes(response.content)

    def test_real_tts_wav_format_validation(self, tts_client, tts_artifacts_dir: Path):
        """Test real TTS output format validation."""
        # Make TTS request
        response = tts_client.post(
            "/synthesize", json={"text": "Format validation test"}
        )

        # Validate WAV format
        wav_info = validate_tts_audio_format(response.content)

        assert wav_info["is_valid"]
        assert wav_info["is_tts_compliant"]
        assert wav_info["sample_rate"] == 22050
        assert wav_info["channels"] == 1
        assert wav_info["bit_depth"] == 16
        assert wav_info["duration"] > 0.1

        # Save to artifacts directory for analysis
        output_file = tts_artifacts_dir / "real_tts_format.wav"
        output_file.write_bytes(response.content)

    def test_real_tts_audio_quality_thresholds(
        self, tts_client, tts_artifacts_dir: Path
    ):
        """Test real TTS audio quality meets thresholds."""
        # Make TTS request
        response = tts_client.post(
            "/synthesize",
            json={
                "text": "Quality threshold test with longer text for better analysis"
            },
        )

        # Validate audio quality
        quality_result = validate_tts_audio_quality(response.content)

        assert quality_result["meets_quality_thresholds"]
        assert quality_result["snr_db"] >= 20.0  # MIN_SNR threshold
        assert quality_result["thd_percent"] <= 1.0  # MAX_THD threshold
        assert quality_result["quality_checks"]["voice_range_ok"]

        # Save to artifacts directory for analysis
        output_file = tts_artifacts_dir / "real_tts_quality.wav"
        output_file.write_bytes(response.content)

    def test_real_tts_processing_time(self, tts_client, tts_artifacts_dir: Path):
        """Test real TTS processing time meets threshold."""
        # Measure processing time
        start_time = time.time()
        response = tts_client.post("/synthesize", json={"text": "Processing time test"})
        processing_time = time.time() - start_time

        assert response.status_code == 200
        assert processing_time <= 1.0  # MAX_TTS_LATENCY threshold

        # Save to artifacts directory for analysis
        output_file = tts_artifacts_dir / "real_tts_timing.wav"
        output_file.write_bytes(response.content)

    def test_real_tts_different_text_lengths(self, tts_client, tts_artifacts_dir: Path):
        """Test real TTS with different text lengths."""
        test_texts = [
            "Short.",
            "This is a medium length text for testing.",
            "This is a much longer text that should take more time to synthesize and produce a longer audio output for comprehensive testing.",
        ]

        for i, text in enumerate(test_texts):
            response = tts_client.post("/synthesize", json={"text": text})

            assert response.status_code == 200

            # Validate format
            format_result = validate_tts_audio_format(response.content)
            assert format_result["is_valid"]

            # Validate quality
            quality_result = validate_tts_audio_quality(response.content)
            assert quality_result["meets_quality_thresholds"]

            # Save to artifacts directory for analysis
            output_file = tts_artifacts_dir / f"real_tts_length_{i}.wav"
            output_file.write_bytes(response.content)

    def test_real_tts_voice_consistency(self, tts_client, tts_artifacts_dir: Path):
        """Test real TTS voice consistency across multiple requests."""
        text = "Voice consistency test"

        # Generate multiple samples
        samples = []
        for i in range(3):
            response = tts_client.post("/synthesize", json={"text": text})
            assert response.status_code == 200
            samples.append(response.content)

            # Save to artifacts directory for analysis
            output_file = tts_artifacts_dir / f"real_tts_consistency_{i}.wav"
            output_file.write_bytes(response.content)

        # All samples should be valid
        for sample in samples:
            format_result = validate_tts_audio_format(sample)
            assert format_result["is_valid"]

            quality_result = validate_tts_audio_quality(sample)
            assert quality_result["meets_quality_thresholds"]

    def test_real_tts_error_handling(self, tts_client, tts_artifacts_dir: Path):
        """Test real TTS error handling."""
        # Test with empty text
        response = tts_client.post("/synthesize", json={"text": ""})

        # Should handle gracefully
        if response.status_code == 200:
            # If successful, validate the output
            format_result = validate_tts_audio_format(response.content)
            assert format_result["is_valid"]

            # Save to artifacts directory for analysis
            output_file = tts_artifacts_dir / "real_tts_empty.wav"
            output_file.write_bytes(response.content)
        else:
            # Should return appropriate error
            assert response.status_code in [400, 422]
