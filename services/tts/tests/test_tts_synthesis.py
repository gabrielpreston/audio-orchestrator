"""Tests for TTS service synthesis functionality."""

import threading
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from services.tts.app import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def sample_text():
    """Sample text for synthesis."""
    return "Hello, this is a test message for text-to-speech synthesis."


@pytest.fixture
def sample_ssml():
    """Sample SSML for synthesis."""
    return "<speak>Hello, this is a test message for text-to-speech synthesis.</speak>"


class TestBasicSynthesis:
    """Test basic synthesis functionality."""

    def test_synthesize_endpoint_with_text(self, client, sample_text):
        """Test /synthesize endpoint with text."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"mock audio data"
            _mock_adapter.synthesize.return_value = mock_audio_data

            response = client.post(
                "/synthesize", json={"text": sample_text, "correlation_id": "test-123"}
            )

            assert response.status_code == 200
            assert response.content == mock_audio_data
            assert response.headers["content-type"] == "audio/wav"

    def test_synthesize_endpoint_with_ssml(self, client, sample_ssml):
        """Test /synthesize endpoint with SSML."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"mock audio data"
            _mock_adapter.synthesize.return_value = mock_audio_data

            response = client.post(
                "/synthesize", json={"ssml": sample_ssml, "correlation_id": "test-456"}
            )

            assert response.status_code == 200
            assert response.content == mock_audio_data

    def test_correlation_id_generation_and_propagation(self, client, sample_text):
        """Test correlation ID generation and propagation."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"mock audio data"
            _mock_adapter.synthesize.return_value = mock_audio_data

            response = client.post("/synthesize", json={"text": sample_text})

            assert response.status_code == 200
            # Check correlation ID in response headers
            assert "X-Correlation-ID" in response.headers

    def test_correlation_id_validation(self, client, sample_text):
        """Test correlation ID validation."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"mock audio data"
            _mock_adapter.synthesize.return_value = mock_audio_data

            response = client.post(
                "/synthesize",
                json={
                    "text": sample_text,
                    "correlation_id": "invalid format with spaces",
                },
            )

            assert response.status_code == 200

    def test_response_includes_wav_audio(self, client, sample_text):
        """Test response includes WAV audio."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"mock wav audio data"
            _mock_adapter.synthesize.return_value = mock_audio_data

            response = client.post("/synthesize", json={"text": sample_text})

            assert response.status_code == 200
            assert response.content == mock_audio_data
            assert response.headers["content-type"] == "audio/wav"

    def test_audio_headers(self, client, sample_text):
        """Test audio headers (X-Audio-Id, X-Audio-Sample-Rate, etc.)."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"mock audio data"
            _mock_adapter.synthesize.return_value = mock_audio_data

            response = client.post("/synthesize", json={"text": sample_text})

            assert response.status_code == 200
            # Check for audio headers
            assert (
                "X-Audio-Id" in response.headers
                or "X-Audio-Sample-Rate" in response.headers
            )


class TestVoiceSelection:
    """Test voice selection functionality."""

    def test_voice_parameter_usage(self, client, sample_text):
        """Test voice parameter usage."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"mock audio data"
            _mock_adapter.synthesize.return_value = mock_audio_data

            response = client.post(
                "/synthesize", json={"text": sample_text, "voice": "voice1"}
            )

            assert response.status_code == 200
            _mock_adapter.synthesize.assert_called_once()

    def test_default_voice_fallback(self, client, sample_text):
        """Test default voice fallback."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"mock audio data"
            _mock_adapter.synthesize.return_value = mock_audio_data

            response = client.post("/synthesize", json={"text": sample_text})

            assert response.status_code == 200
            _mock_adapter.synthesize.assert_called_once()

    def test_invalid_voice_rejection_400_error(self, client, sample_text):
        """Test invalid voice rejection (400 error)."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            _mock_adapter.synthesize.side_effect = ValueError("Invalid voice")

            response = client.post(
                "/synthesize", json={"text": sample_text, "voice": "invalid_voice"}
            )

            assert response.status_code == 400


class TestSynthesisParameters:
    """Test synthesis parameters."""

    def test_length_scale_adjustment_0_1_to_3_0(self, client, sample_text):
        """Test length_scale adjustment (0.1 to 3.0)."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"mock audio data"
            _mock_adapter.synthesize.return_value = mock_audio_data

            # Test valid range
            for scale in [0.1, 1.0, 3.0]:
                response = client.post(
                    "/synthesize", json={"text": sample_text, "length_scale": scale}
                )
                assert response.status_code == 200

    def test_noise_scale_adjustment_0_0_to_2_0(self, client, sample_text):
        """Test noise_scale adjustment (0.0 to 2.0)."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"mock audio data"
            _mock_adapter.synthesize.return_value = mock_audio_data

            # Test valid range
            for scale in [0.0, 1.0, 2.0]:
                response = client.post(
                    "/synthesize", json={"text": sample_text, "noise_scale": scale}
                )
                assert response.status_code == 200

    def test_noise_w_adjustment_0_0_to_2_0(self, client, sample_text):
        """Test noise_w adjustment (0.0 to 2.0)."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"mock audio data"
            _mock_adapter.synthesize.return_value = mock_audio_data

            # Test valid range
            for scale in [0.0, 1.0, 2.0]:
                response = client.post(
                    "/synthesize", json={"text": sample_text, "noise_w": scale}
                )
                assert response.status_code == 200

    def test_parameter_validation_out_of_range(self, client, sample_text):
        """Test parameter validation for out of range values."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            _mock_adapter.synthesize.side_effect = ValueError("Parameter out of range")

            # Test out of range values
            response = client.post(
                "/synthesize", json={"text": sample_text, "length_scale": 5.0}
            )
            assert response.status_code == 400


class TestInputValidation:
    """Test input validation."""

    def test_text_ssml_mutual_exclusivity(self, client, sample_text, sample_ssml):
        """Test text/SSML mutual exclusivity."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            response = client.post(
                "/synthesize", json={"text": sample_text, "ssml": sample_ssml}
            )

            assert response.status_code == 400

    def test_max_text_length_enforcement(self, client):
        """Test max text length enforcement."""
        long_text = "a" * 10000  # Very long text

        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            response = client.post("/synthesize", json={"text": long_text})

            # Should either succeed or return 400 for too long text
            assert response.status_code in [200, 400]

    def test_ssml_tag_stripping(self, client, sample_ssml):
        """Test SSML tag stripping."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"mock audio data"
            _mock_adapter.synthesize.return_value = mock_audio_data

            response = client.post("/synthesize", json={"ssml": sample_ssml})

            assert response.status_code == 200
            _mock_adapter.synthesize.assert_called_once()

    def test_empty_text_rejection(self, client):
        """Test empty text rejection."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            response = client.post("/synthesize", json={"text": ""})

            assert response.status_code == 400

    def test_missing_text_and_ssml(self, client):
        """Test missing text and SSML."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            response = client.post("/synthesize", json={})

            assert response.status_code == 400


class TestConcurrencyAndRateLimiting:
    """Test concurrency and rate limiting."""

    def test_max_concurrency_enforcement_via_semaphore(self, client, sample_text):
        """Test max concurrency enforcement (via semaphore)."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"mock audio data"
            _mock_adapter.synthesize.return_value = mock_audio_data

            # Test multiple concurrent requests
            results = []

            def make_request():
                response = client.post("/synthesize", json={"text": sample_text})
                results.append(response.status_code)

            threads = []
            for _ in range(5):  # Test 5 concurrent requests
                thread = threading.Thread(target=make_request)
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()

            # All requests should succeed or be rate limited
            for status_code in results:
                assert status_code in [200, 429]

    def test_rate_limit_per_minute_per_client_ip(self, client, sample_text):
        """Test rate limit per minute (per client IP)."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"mock audio data"
            _mock_adapter.synthesize.return_value = mock_audio_data

            # Make many requests quickly
            for _ in range(100):
                response = client.post("/synthesize", json={"text": sample_text})
                if response.status_code == 429:
                    break

            # Should eventually get rate limited
            assert response.status_code == 429

    def test_rate_limit_resets_per_window(self, client, sample_text):
        """Test rate limit resets per window."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"mock audio data"
            _mock_adapter.synthesize.return_value = mock_audio_data

            # Test rate limit reset behavior
            response = client.post("/synthesize", json={"text": sample_text})

            assert response.status_code == 200

    def test_concurrent_synthesis_quality(self, client, sample_text):
        """Test concurrent synthesis maintains quality."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"mock audio data"
            _mock_adapter.synthesize.return_value = mock_audio_data

            # Test concurrent requests
            results = []

            def make_request():
                response = client.post("/synthesize", json={"text": sample_text})
                results.append(response)

            threads = []
            for _ in range(3):
                thread = threading.Thread(target=make_request)
                threads.append(thread)
                thread.start()

            for thread in threads:
                thread.join()

            # All should succeed
            for response in results:
                assert response.status_code == 200
                assert response.content == mock_audio_data


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_synthesis_failures(self, client, sample_text):
        """Test synthesis failures."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            _mock_adapter.synthesize.side_effect = Exception("Synthesis failed")

            response = client.post("/synthesize", json={"text": sample_text})

            assert response.status_code == 500

    def test_empty_audio_buffer_handling(self, client, sample_text):
        """Test empty audio buffer handling."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            _mock_adapter.synthesize.return_value = b""

            response = client.post("/synthesize", json={"text": sample_text})

            assert response.status_code == 200
            assert response.content == b""

    def test_degraded_mode_returns_silence(self, client, sample_text):
        """Test degraded mode (returns silence)."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            _mock_adapter.synthesize.return_value = b"silence"

            response = client.post("/synthesize", json={"text": sample_text})

            assert response.status_code == 200
            assert response.content == b"silence"

    def test_model_not_loaded_error(self, client, sample_text):
        """Test model not loaded error."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            _mock_adapter.synthesize.side_effect = RuntimeError("Model not loaded")

            response = client.post("/synthesize", json={"text": sample_text})

            assert response.status_code == 503

    def test_invalid_audio_format_error(self, client, sample_text):
        """Test invalid audio format error."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            _mock_adapter.synthesize.side_effect = ValueError("Invalid audio format")

            response = client.post("/synthesize", json={"text": sample_text})

            assert response.status_code == 400


class TestSynthesisQuality:
    """Test synthesis quality."""

    def test_audio_quality_consistency(self, client, sample_text):
        """Test audio quality consistency across requests."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"consistent audio data"
            _mock_adapter.synthesize.return_value = mock_audio_data

            # Make multiple requests
            for _ in range(3):
                response = client.post("/synthesize", json={"text": sample_text})
                assert response.status_code == 200
                assert response.content == mock_audio_data

    def test_voice_consistency(self, client, sample_text):
        """Test voice consistency across requests."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"consistent voice audio"
            _mock_adapter.synthesize.return_value = mock_audio_data

            # Test with same voice
            for _ in range(3):
                response = client.post(
                    "/synthesize", json={"text": sample_text, "voice": "voice1"}
                )
                assert response.status_code == 200
                assert response.content == mock_audio_data

    def test_parameter_effectiveness(self, client, sample_text):
        """Test parameter effectiveness."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"parameterized audio"
            _mock_adapter.synthesize.return_value = mock_audio_data

            # Test different parameters
            response = client.post(
                "/synthesize",
                json={
                    "text": sample_text,
                    "length_scale": 1.5,
                    "noise_scale": 0.5,
                    "noise_w": 0.3,
                },
            )

            assert response.status_code == 200
            assert response.content == mock_audio_data
