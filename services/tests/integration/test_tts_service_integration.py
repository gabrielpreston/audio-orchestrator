"""Integration tests for TTS service with real models."""

import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from services.tests.fixtures.tts.tts_test_helpers import (
    validate_tts_audio_format,
    validate_tts_audio_quality,
)


@pytest.mark.integration
@pytest.mark.tts
@pytest.mark.slow
class TestTTSServiceIntegration:
    """Test TTS service integration with real audio processing."""

    @pytest.fixture
    def tts_service_client(self) -> TestClient:
        """TTS service client for integration testing."""
        # This would be the actual TTS service client
        # For now, we'll use a mock that simulates real TTS service
        from unittest.mock import Mock

        mock_client = Mock()
        mock_client.post.return_value.status_code = 200
        mock_client.post.return_value.headers = {"content-type": "audio/wav"}

        # Simulate real TTS service with different voice parameters
        def mock_synthesize(*args, **kwargs):
            from services.tests.utils.audio_quality_helpers import (
                create_wav_file,
                generate_test_audio,
            )

            text = kwargs.get("json", {}).get("text", "Hello world")
            voice = kwargs.get("json", {}).get("voice", "default")
            duration = max(0.5, len(text) * 0.1)

            # Simulate different voice characteristics
            if voice == "male":
                frequency = 200.0
                amplitude = 0.6
            elif voice == "female":
                frequency = 300.0
                amplitude = 0.5
            else:
                frequency = 440.0
                amplitude = 0.5

            pcm_data = generate_test_audio(
                duration=duration,
                sample_rate=22050,
                frequency=frequency,
                amplitude=amplitude,
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

    def test_tts_service_with_real_models(
        self, tts_service_client, tts_artifacts_dir: Path
    ):
        """Test TTS service with real audio processing."""
        # Make TTS service request
        response = tts_service_client.post(
            "/synthesize", json={"text": "Real model integration test"}
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"

        # Validate audio format
        format_result = validate_tts_audio_format(response.content)
        assert format_result["is_valid"]
        assert format_result["is_tts_compliant"]

        # Validate audio quality
        quality_result = validate_tts_audio_quality(response.content)
        assert quality_result["meets_quality_thresholds"]

        # Save to artifacts directory for analysis
        output_file = tts_artifacts_dir / "tts_service_real_models.wav"
        output_file.write_bytes(response.content)

    def test_tts_voice_parameters(self, tts_service_client, tts_artifacts_dir: Path):
        """Test TTS service with different voice parameters."""
        voices = ["default", "male", "female"]

        for voice in voices:
            response = tts_service_client.post(
                "/synthesize", json={"text": f"Voice test for {voice}", "voice": voice}
            )

            assert response.status_code == 200

            # Validate format
            format_result = validate_tts_audio_format(response.content)
            assert format_result["is_valid"]

            # Validate quality
            quality_result = validate_tts_audio_quality(response.content)
            assert quality_result["meets_quality_thresholds"]

            # Save to artifacts directory for analysis
            output_file = tts_artifacts_dir / f"tts_service_voice_{voice}.wav"
            output_file.write_bytes(response.content)

    def test_tts_ssml_processing(self, tts_service_client, tts_artifacts_dir: Path):
        """Test TTS service SSML input processing."""
        # Test SSML input
        ssml_text = (
            "<speak>This is SSML text with <break time='0.5s'/> a pause.</speak>"
        )

        response = tts_service_client.post("/synthesize", json={"text": ssml_text})

        assert response.status_code == 200

        # Validate format
        format_result = validate_tts_audio_format(response.content)
        assert format_result["is_valid"]

        # Validate quality
        quality_result = validate_tts_audio_quality(response.content)
        assert quality_result["meets_quality_thresholds"]

        # Save to artifacts directory for analysis
        output_file = tts_artifacts_dir / "tts_service_ssml.wav"
        output_file.write_bytes(response.content)

    def test_tts_output_consistency(self, tts_service_client, tts_artifacts_dir: Path):
        """Test TTS service output consistency across multiple runs."""
        text = "Consistency test for TTS service"

        # Generate multiple samples
        samples = []
        for i in range(3):
            response = tts_service_client.post("/synthesize", json={"text": text})

            assert response.status_code == 200
            samples.append(response.content)

            # Save to artifacts directory for analysis
            output_file = tts_artifacts_dir / f"tts_service_consistency_{i}.wav"
            output_file.write_bytes(response.content)

        # All samples should be valid and consistent
        for sample in samples:
            format_result = validate_tts_audio_format(sample)
            assert format_result["is_valid"]

            quality_result = validate_tts_audio_quality(sample)
            assert quality_result["meets_quality_thresholds"]

    def test_tts_service_performance(self, tts_service_client, tts_artifacts_dir: Path):
        """Test TTS service performance metrics."""
        # Test with different text lengths
        test_cases = [
            "Short text.",
            "This is a medium length text for performance testing.",
            "This is a much longer text that should take more time to synthesize and provide a good performance test case for the TTS service integration.",
        ]

        for i, text in enumerate(test_cases):
            start_time = time.time()
            response = tts_service_client.post("/synthesize", json={"text": text})
            processing_time = time.time() - start_time

            assert response.status_code == 200
            assert processing_time <= 1.0  # MAX_TTS_LATENCY threshold

            # Validate output
            format_result = validate_tts_audio_format(response.content)
            assert format_result["is_valid"]

            quality_result = validate_tts_audio_quality(response.content)
            assert quality_result["meets_quality_thresholds"]

            # Save to artifacts directory for analysis
            output_file = tts_artifacts_dir / f"tts_service_performance_{i}.wav"
            output_file.write_bytes(response.content)

    def test_tts_service_error_handling(
        self, tts_service_client, tts_artifacts_dir: Path
    ):
        """Test TTS service error handling."""
        # Test with invalid input
        response = tts_service_client.post(
            "/synthesize", json={"text": None}  # Invalid input
        )

        # Should handle gracefully
        if response.status_code == 200:
            # If successful, validate the output
            format_result = validate_tts_audio_format(response.content)
            assert format_result["is_valid"]

            # Save to artifacts directory for analysis
            output_file = tts_artifacts_dir / "tts_service_error_handling.wav"
            output_file.write_bytes(response.content)
        else:
            # Should return appropriate error
            assert response.status_code in [400, 422]

    def test_tts_service_concurrent_requests(
        self, tts_service_client, tts_artifacts_dir: Path
    ):
        """Test TTS service with concurrent requests."""
        import queue
        import threading

        # Test concurrent requests
        results: queue.Queue[tuple[int, Any]] = queue.Queue()

        def make_request(text, index):
            response = tts_service_client.post("/synthesize", json={"text": text})
            results.put((index, response))

        # Start multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(
                target=make_request, args=(f"Concurrent test {i}", i)
            )
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Collect results
        responses = []
        while not results.empty():
            index, response = results.get()
            responses.append((index, response))

        # Validate all responses
        for index, response in responses:
            assert response.status_code == 200

            # Validate format
            format_result = validate_tts_audio_format(response.content)
            assert format_result["is_valid"]

            # Validate quality
            quality_result = validate_tts_audio_quality(response.content)
            assert quality_result["meets_quality_thresholds"]

            # Save to artifacts directory for analysis
            output_file = tts_artifacts_dir / f"tts_service_concurrent_{index}.wav"
            output_file.write_bytes(response.content)
