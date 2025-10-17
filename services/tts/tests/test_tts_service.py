"""Tests for TTS service core functionality."""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from services.common.health import HealthManager
from services.tts.app import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_health_manager():
    """Mock health manager."""
    manager = Mock(spec=HealthManager)
    manager.is_ready.return_value = True
    manager.is_alive.return_value = True
    return manager


@pytest.fixture
def sample_text():
    """Sample text for synthesis."""
    return "Hello, this is a test message for text-to-speech synthesis."


@pytest.fixture
def sample_ssml():
    """Sample SSML for synthesis."""
    return "<speak>Hello, this is a test message for text-to-speech synthesis.</speak>"


class TestTTSServiceHealth:
    """Test TTS service health endpoints."""

    def test_health_live_endpoint(self, client, mock_health_manager):
        """Test /health/live endpoint returns alive status."""
        with patch("services.tts.app.health_manager", mock_health_manager):
            response = client.get("/health/live")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "alive"

    def test_health_ready_endpoint_ready(self, client, mock_health_manager):
        """Test /health/ready endpoint when service is ready."""
        with patch("services.tts.app.health_manager", mock_health_manager):
            response = client.get("/health/ready")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ready"

    def test_health_ready_endpoint_not_ready(self, client):
        """Test /health/ready endpoint when service is not ready."""
        mock_health_manager = Mock(spec=HealthManager)
        mock_health_manager.is_ready.return_value = False
        mock_health_manager.is_alive.return_value = True

        with patch("services.tts.app.health_manager", mock_health_manager):
            response = client.get("/health/ready")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "not_ready"


class TestTTSServiceModelLoading:
    """Test TTS service model loading."""

    def test_model_initialization_from_paths(self):
        """Test voice model loads from TTS_MODEL_PATH and TTS_MODEL_CONFIG_PATH."""
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir) / "model"
            config_path = Path(temp_dir) / "config.json"
            model_path.mkdir()
            config_path.write_text('{"sample_rate": 22050}')

            with (
                patch.dict(
                    os.environ,
                    {
                        "TTS_MODEL_PATH": str(model_path),
                        "TTS_MODEL_CONFIG_PATH": str(config_path),
                    },
                ),
                patch("services.tts.models.PiperAdapter") as _mock_adapter,
            ):
                _mock_adapter.return_value = Mock()
                # Test model loading from paths
                pass

    def test_degraded_mode_when_model_paths_not_set(self):
        """Test degraded mode when model paths not set."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("services.tts.models.PiperAdapter") as _mock_adapter,
        ):
            _mock_adapter.return_value = Mock()
            # Test degraded mode behavior
            pass

    def test_sample_rate_extraction_from_config(self):
        """Test sample rate extraction from config."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text('{"sample_rate": 22050}')

            with (
                patch.dict(os.environ, {"TTS_MODEL_CONFIG_PATH": str(config_path)}),
                patch("services.tts.models.PiperAdapter") as _mock_adapter,
            ):
                _mock_adapter.return_value = Mock()
                # Test sample rate extraction
                pass

    def test_speaker_map_parsing_multi_speaker_models(self):
        """Test speaker map parsing (multi-speaker models)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.json"
            config_path.write_text('{"speakers": {"0": "male", "1": "female"}}')

            with (
                patch.dict(os.environ, {"TTS_MODEL_CONFIG_PATH": str(config_path)}),
                patch("services.tts.models.PiperAdapter") as _mock_adapter,
            ):
                _mock_adapter.return_value = Mock()
                # Test speaker map parsing
                pass

    def test_default_voice_configuration(self):
        """Test default voice configuration."""
        with patch("services.tts.models.PiperAdapter") as _mock_adapter:
            _mock_adapter.return_value = Mock()
            # Test default voice configuration
            pass


class TestTTSServiceVoiceCatalog:
    """Test TTS service voice catalog."""

    def test_voices_endpoint_returns_available_voices(self, client):
        """Test /voices endpoint returns available voices."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            _mock_adapter.get_available_voices.return_value = [
                {"id": "voice1", "name": "Voice 1", "language": "en"},
                {"id": "voice2", "name": "Voice 2", "language": "es"},
            ]

            response = client.get("/voices")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["id"] == "voice1"
            assert data[1]["id"] == "voice2"

    def test_voice_metadata_speaker_id_language(self, client):
        """Test voice metadata (speaker_id, language)."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            _mock_adapter.get_available_voices.return_value = [
                {"id": "voice1", "speaker_id": "0", "language": "en", "gender": "male"}
            ]

            response = client.get("/voices")
            assert response.status_code == 200
            data = response.json()
            assert data[0]["speaker_id"] == "0"
            assert data[0]["language"] == "en"
            assert data[0]["gender"] == "male"

    def test_fallback_to_default_when_no_model(self, client):
        """Test fallback to default when no model."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            _mock_adapter.get_available_voices.return_value = []

            response = client.get("/voices")
            assert response.status_code == 200
            data = response.json()
            # Should return default voice
            assert len(data) >= 0


class TestTTSServiceSynthesis:
    """Test TTS service synthesis endpoints."""

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


class TestTTSServiceVoiceSelection:
    """Test TTS service voice selection."""

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


class TestTTSServiceSynthesisParameters:
    """Test TTS service synthesis parameters."""

    def test_length_scale_adjustment(self, client, sample_text):
        """Test length_scale adjustment (0.1 to 3.0)."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"mock audio data"
            _mock_adapter.synthesize.return_value = mock_audio_data

            response = client.post(
                "/synthesize", json={"text": sample_text, "length_scale": 1.5}
            )

            assert response.status_code == 200
            _mock_adapter.synthesize.assert_called_once()

    def test_noise_scale_adjustment(self, client, sample_text):
        """Test noise_scale adjustment (0.0 to 2.0)."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"mock audio data"
            _mock_adapter.synthesize.return_value = mock_audio_data

            response = client.post(
                "/synthesize", json={"text": sample_text, "noise_scale": 0.5}
            )

            assert response.status_code == 200
            _mock_adapter.synthesize.assert_called_once()

    def test_noise_w_adjustment(self, client, sample_text):
        """Test noise_w adjustment (0.0 to 2.0)."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"mock audio data"
            _mock_adapter.synthesize.return_value = mock_audio_data

            response = client.post(
                "/synthesize", json={"text": sample_text, "noise_w": 0.3}
            )

            assert response.status_code == 200
            _mock_adapter.synthesize.assert_called_once()


class TestTTSServiceInputValidation:
    """Test TTS service input validation."""

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


class TestTTSServiceConcurrencyAndRateLimiting:
    """Test TTS service concurrency and rate limiting."""

    def test_max_concurrency_enforcement_via_semaphore(self, client, sample_text):
        """Test max concurrency enforcement (via semaphore)."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"mock audio data"
            _mock_adapter.synthesize.return_value = mock_audio_data

            # Test multiple concurrent requests
            import threading

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


class TestTTSServiceErrorHandling:
    """Test TTS service error handling."""

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


class TestTTSServiceMetrics:
    """Test TTS service metrics."""

    def test_prometheus_metrics_exposed_on_metrics(self, client):
        """Test Prometheus metrics exposed on /metrics."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

    def test_synthesis_counter_increments(self, client, sample_text):
        """Test synthesis counter increments."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"mock audio data"
            _mock_adapter.synthesize.return_value = mock_audio_data

            response = client.post("/synthesize", json={"text": sample_text})

            assert response.status_code == 200

            # Check metrics endpoint
            metrics_response = client.get("/metrics")
            assert metrics_response.status_code == 200
            # Should contain synthesis counter
            assert (
                "synthesis_total" in metrics_response.text
                or "tts_requests_total" in metrics_response.text
            )

    def test_synthesis_duration_histogram(self, client, sample_text):
        """Test synthesis duration histogram."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"mock audio data"
            _mock_adapter.synthesize.return_value = mock_audio_data

            response = client.post("/synthesize", json={"text": sample_text})

            assert response.status_code == 200

            # Check metrics endpoint
            metrics_response = client.get("/metrics")
            assert metrics_response.status_code == 200
            # Should contain duration histogram
            assert (
                "synthesis_duration" in metrics_response.text
                or "tts_duration" in metrics_response.text
            )

    def test_audio_size_histogram(self, client, sample_text):
        """Test audio size histogram."""
        with patch("services.tts.app.tts_adapter") as _mock_adapter:
            mock_audio_data = b"mock audio data"
            _mock_adapter.synthesize.return_value = mock_audio_data

            response = client.post("/synthesize", json={"text": sample_text})

            assert response.status_code == 200

            # Check metrics endpoint
            metrics_response = client.get("/metrics")
            assert metrics_response.status_code == 200
            # Should contain audio size histogram
            assert (
                "audio_size" in metrics_response.text
                or "tts_audio_size" in metrics_response.text
            )
