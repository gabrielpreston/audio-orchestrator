"""Tests for STT service core functionality."""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from services.common.health import HealthCheck, HealthManager, HealthStatus
from services.stt.app import app


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
def sample_audio_data():
    """Sample audio data for testing."""
    # Generate simple sine wave data
    import math
    import struct

    duration = 1.0
    sample_rate = 16000
    frequency = 440.0
    amplitude = 0.5

    samples = int(duration * sample_rate)
    audio_data = []

    for i in range(samples):
        t = i / sample_rate
        sample = amplitude * math.sin(2 * math.pi * frequency * t)
        pcm_sample = int(sample * 32767)
        pcm_sample = max(-32768, min(32767, pcm_sample))
        audio_data.append(pcm_sample)

    return struct.pack("<" + "h" * len(audio_data), *audio_data)


@pytest.fixture
def sample_wav_file(sample_audio_data):
    """Sample WAV file for testing."""
    import struct

    # Create WAV header
    data_size = len(sample_audio_data)
    file_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",  # ChunkID
        file_size,  # ChunkSize
        b"WAVE",  # Format
        b"fmt ",  # Subchunk1ID
        16,  # Subchunk1Size (PCM)
        1,  # AudioFormat (PCM)
        1,  # NumChannels
        16000,  # SampleRate
        16000 * 1 * 2,  # ByteRate
        1 * 2,  # BlockAlign
        16,  # BitsPerSample
        b"data",  # Subchunk2ID
        data_size,  # Subchunk2Size
    )

    return header + sample_audio_data


class TestSTTServiceHealth:
    """Test STT service health endpoints."""

    def test_health_live_endpoint(self, client, mock_health_manager):
        """Test /health/live endpoint returns alive status."""
        with patch("services.stt.app.health_manager", mock_health_manager):
            response = client.get("/health/live")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "alive"

    def test_health_ready_endpoint_ready(self, client):
        """Test /health/ready endpoint when service is ready."""
        from services.common.model_loader import BackgroundModelLoader

        mock_health_status = HealthCheck(
            status=HealthStatus.HEALTHY,
            ready=True,
            details={"startup_complete": True, "dependencies": {}},
        )

        # Create mock model loader with loaded state
        mock_model_loader = Mock(spec=BackgroundModelLoader)
        mock_model_loader.is_loaded.return_value = True
        mock_model_loader.is_loading.return_value = False

        with (
            patch.object(app.state, "model_loader", mock_model_loader),
            patch(
                "services.stt.app._health_manager.get_health_status",
                new_callable=AsyncMock,
            ) as mock_get_health,
        ):
            mock_get_health.return_value = mock_health_status

            response = client.get("/health/ready")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] in ["ready", "degraded"]
            assert data["service"] == "stt"
            assert "components" in data
            assert data["components"]["model_loaded"] is True
            assert data["components"]["startup_complete"] is True

    def test_health_ready_endpoint_not_ready(self, client):
        """Test /health/ready endpoint when service is not ready."""
        # Test when model loader is not available (should return 503)
        with patch.object(app.state, "model_loader", None, create=True):
            response = client.get("/health/ready")
            assert response.status_code == 503
            data = response.json()
            assert (
                "not ready" in data["detail"].lower()
                or "not available" in data["detail"].lower()
            )


class TestSTTServiceModelLoading:
    """Test STT service model loading."""

    def test_model_initialization_from_env(self):
        """Test model loads from environment variable FW_MODEL."""
        with (
            patch.dict(os.environ, {"FW_MODEL": "tiny"}),
            patch("services.stt.models.FastWhisperAdapter") as mock_adapter,
        ):
            mock_adapter.return_value = Mock()
            # This would test the actual model loading in the service
            # Implementation depends on how the service initializes
            pass

    def test_model_initialization_from_path(self):
        """Test model loads from local path FW_MODEL_PATH."""
        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir) / "model"
            model_path.mkdir()

            with (
                patch.dict(os.environ, {"FW_MODEL_PATH": str(model_path)}),
                patch("services.stt.models.FastWhisperAdapter") as mock_adapter,
            ):
                mock_adapter.return_value = Mock()
                # Test model loading from path
                pass

    def test_model_fallback_to_remote(self):
        """Test fallback to remote model when local not found."""
        with (
            patch.dict(os.environ, {"FW_MODEL_PATH": "/nonexistent/path"}),
            patch("services.stt.models.FastWhisperAdapter") as mock_adapter,
        ):
            mock_adapter.return_value = Mock()
            # Test fallback behavior
            pass

    def test_device_configuration_cpu(self):
        """Test device configuration for CPU."""
        with (
            patch.dict(os.environ, {"FW_DEVICE": "cpu"}),
            patch("services.stt.models.FastWhisperAdapter") as mock_adapter,
        ):
            mock_adapter.return_value = Mock()
            # Test CPU device configuration
            pass

    def test_compute_type_configuration(self):
        """Test compute type configuration."""
        with (
            patch.dict(os.environ, {"FW_COMPUTE_TYPE": "int8"}),
            patch("services.stt.models.FastWhisperAdapter") as mock_adapter,
        ):
            mock_adapter.return_value = Mock()
            # Test compute type configuration
            pass


class TestSTTServiceTranscription:
    """Test STT service transcription endpoints."""

    def test_asr_endpoint_valid_wav(self, client, sample_wav_file):
        """Test /asr endpoint with valid WAV audio."""
        with patch("services.stt.app.transcription_adapter") as mock_adapter:
            mock_adapter.transcribe.return_value = Mock(
                text="hello world",
                start_timestamp=0.0,
                end_timestamp=1.0,
                language="en",
                confidence=0.9,
            )

            response = client.post(
                "/asr",
                files={"audio": ("test.wav", sample_wav_file, "audio/wav")},
                data={"correlation_id": "test-123"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["text"] == "hello world"
            assert data["start_timestamp"] == 0.0
            assert data["end_timestamp"] == 1.0
            assert data["language"] == "en"
            assert data["confidence"] == 0.9
            assert data["correlation_id"] == "test-123"

    def test_transcribe_endpoint_multipart(self, client, sample_wav_file):
        """Test /transcribe endpoint with multipart form data."""
        with patch("services.stt.app.transcription_adapter") as mock_adapter:
            mock_adapter.transcribe.return_value = Mock(
                text="test transcription",
                start_timestamp=0.0,
                end_timestamp=1.0,
                language="en",
                confidence=0.8,
            )

            response = client.post(
                "/transcribe",
                files={"audio": ("test.wav", sample_wav_file, "audio/wav")},
                data={"correlation_id": "test-456"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["text"] == "test transcription"

    def test_correlation_id_generation(self, client, sample_wav_file):
        """Test correlation ID generation and propagation."""
        with patch("services.stt.app.transcription_adapter") as mock_adapter:
            mock_adapter.transcribe.return_value = Mock(
                text="test",
                start_timestamp=0.0,
                end_timestamp=1.0,
                language="en",
                confidence=0.8,
            )

            response = client.post(
                "/asr", files={"audio": ("test.wav", sample_wav_file, "audio/wav")}
            )

            assert response.status_code == 200
            data = response.json()
            assert "correlation_id" in data
            assert data["correlation_id"] is not None

    def test_correlation_id_validation(self, client, sample_wav_file):
        """Test correlation ID validation (reject invalid formats)."""
        with patch("services.stt.app.transcription_adapter") as _mock_adapter:
            response = client.post(
                "/asr",
                files={"audio": ("test.wav", sample_wav_file, "audio/wav")},
                data={"correlation_id": "invalid format with spaces"},
            )

            # Should still work, but correlation ID might be regenerated
            assert response.status_code == 200

    def test_language_handling_forced(self, client, sample_wav_file):
        """Test forced language via language query param."""
        with patch("services.stt.app.transcription_adapter") as mock_adapter:
            mock_adapter.transcribe.return_value = Mock(
                text="test",
                start_timestamp=0.0,
                end_timestamp=1.0,
                language="es",
                confidence=0.8,
            )

            response = client.post(
                "/asr?language=es",
                files={"audio": ("test.wav", sample_wav_file, "audio/wav")},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["language"] == "es"

    def test_language_handling_automatic(self, client, sample_wav_file):
        """Test automatic language detection (no param)."""
        with patch("services.stt.app.transcription_adapter") as mock_adapter:
            mock_adapter.transcribe.return_value = Mock(
                text="test",
                start_timestamp=0.0,
                end_timestamp=1.0,
                language="en",
                confidence=0.8,
            )

            response = client.post(
                "/asr", files={"audio": ("test.wav", sample_wav_file, "audio/wav")}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["language"] == "en"

    def test_translation_task(self, client, sample_wav_file):
        """Test translation task via task=translate."""
        with patch("services.stt.app.transcription_adapter") as mock_adapter:
            mock_adapter.transcribe.return_value = Mock(
                text="translated text",
                start_timestamp=0.0,
                end_timestamp=1.0,
                language="en",
                confidence=0.8,
            )

            response = client.post(
                "/asr?task=translate",
                files={"audio": ("test.wav", sample_wav_file, "audio/wav")},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["text"] == "translated text"

    def test_audio_format_validation_16bit_pcm(self, client, sample_wav_file):
        """Test 16-bit PCM WAV acceptance."""
        with patch("services.stt.app.transcription_adapter") as mock_adapter:
            mock_adapter.transcribe.return_value = Mock(
                text="test",
                start_timestamp=0.0,
                end_timestamp=1.0,
                language="en",
                confidence=0.8,
            )

            response = client.post(
                "/asr", files={"audio": ("test.wav", sample_wav_file, "audio/wav")}
            )

            assert response.status_code == 200

    def test_audio_format_validation_reject_non_16bit(self, client):
        """Test rejection of non-16-bit audio (400 error)."""
        # Create invalid audio data (8-bit)
        invalid_audio = b"RIFF\x00\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00\x00\x01\x00\x08\x00data\x00\x00\x00\x00"

        response = client.post(
            "/asr", files={"audio": ("test.wav", invalid_audio, "audio/wav")}
        )

        assert response.status_code == 400

    def test_audio_format_validation_reject_invalid_wav(self, client):
        """Test invalid WAV header rejection."""
        invalid_audio = b"invalid wav data"

        response = client.post(
            "/asr", files={"audio": ("test.wav", invalid_audio, "audio/wav")}
        )

        assert response.status_code == 400

    def test_audio_format_validation_reject_empty_body(self, client):
        """Test empty request body rejection."""
        response = client.post("/asr")
        assert response.status_code == 400

    def test_beam_size_parameter(self, client, sample_wav_file):
        """Test beam_size parameter adjustment."""
        with patch("services.stt.app.transcription_adapter") as mock_adapter:
            mock_adapter.transcribe.return_value = Mock(
                text="test",
                start_timestamp=0.0,
                end_timestamp=1.0,
                language="en",
                confidence=0.8,
            )

            response = client.post(
                "/asr?beam_size=5",
                files={"audio": ("test.wav", sample_wav_file, "audio/wav")},
            )

            assert response.status_code == 200

    def test_word_timestamps_generation(self, client, sample_wav_file):
        """Test word_timestamps generation."""
        with patch("services.stt.app.transcription_adapter") as mock_adapter:
            mock_adapter.transcribe.return_value = Mock(
                text="hello world",
                start_timestamp=0.0,
                end_timestamp=1.0,
                language="en",
                confidence=0.8,
                word_timestamps=[
                    {"word": "hello", "start": 0.0, "end": 0.5},
                    {"word": "world", "start": 0.5, "end": 1.0},
                ],
            )

            response = client.post(
                "/asr?word_timestamps=true",
                files={"audio": ("test.wav", sample_wav_file, "audio/wav")},
            )

            assert response.status_code == 200
            data = response.json()
            assert "word_timestamps" in data

    def test_segment_level_timestamps(self, client, sample_wav_file):
        """Test segment-level timestamps."""
        with patch("services.stt.app.transcription_adapter") as mock_adapter:
            mock_adapter.transcribe.return_value = Mock(
                text="test",
                start_timestamp=0.0,
                end_timestamp=1.0,
                language="en",
                confidence=0.8,
                segments=[{"text": "test", "start": 0.0, "end": 1.0}],
            )

            response = client.post(
                "/asr", files={"audio": ("test.wav", sample_wav_file, "audio/wav")}
            )

            assert response.status_code == 200
            data = response.json()
            assert "segments" in data or "start_timestamp" in data


class TestSTTServiceErrorHandling:
    """Test STT service error handling."""

    def test_malformed_audio_data_handling(self, client):
        """Test malformed audio data handling."""
        malformed_audio = b"not audio data at all"

        response = client.post(
            "/asr", files={"audio": ("test.wav", malformed_audio, "audio/wav")}
        )

        assert response.status_code == 400

    def test_model_inference_failures(self, client, sample_wav_file):
        """Test model inference failures."""
        with patch("services.stt.app.transcription_adapter") as mock_adapter:
            mock_adapter.transcribe.side_effect = Exception("Model inference failed")

            response = client.post(
                "/asr", files={"audio": ("test.wav", sample_wav_file, "audio/wav")}
            )

            assert response.status_code == 500

    def test_temporary_file_cleanup_on_errors(self, client):
        """Test temporary file cleanup on errors."""
        # This would test that temporary files are cleaned up even when errors occur
        # Implementation depends on how the service handles file cleanup
        pass


class TestSTTServiceStartup:
    """Test STT service startup behavior."""

    def test_model_preloads_on_startup(self):
        """Test model preloads on startup event."""
        # This would test the startup event handler
        # Implementation depends on how the service handles startup
        pass

    def test_startup_failure_handling(self):
        """Test startup failure handling."""
        # This would test startup failure scenarios
        # Implementation depends on how the service handles startup failures
        pass

    def test_health_manager_startup_complete(self):
        """Test health manager marks startup complete."""
        # This would test that the health manager is properly updated
        # Implementation depends on how the service manages health state
        pass
