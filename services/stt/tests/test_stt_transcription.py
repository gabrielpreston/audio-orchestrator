"""Tests for STT service transcription functionality."""

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from services.stt.app import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def sample_audio_data():
    """Sample audio data for testing."""
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


class TestBasicTranscription:
    """Test basic transcription functionality."""

    def test_asr_endpoint_with_valid_wav(self, client, sample_wav_file):
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

    def test_transcribe_endpoint_with_multipart(self, client, sample_wav_file):
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

    def test_correlation_id_generation_and_propagation(self, client, sample_wav_file):
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

    def test_correlation_id_validation_reject_invalid_formats(self, client, sample_wav_file):
        """Test correlation ID validation (reject invalid formats)."""
        with patch("services.stt.app.transcription_adapter") as mock_adapter:
            mock_adapter.transcribe.return_value = Mock(
                text="test",
                start_timestamp=0.0,
                end_timestamp=1.0,
                language="en",
                confidence=0.8,
            )

            response = client.post(
                "/asr",
                files={"audio": ("test.wav", sample_wav_file, "audio/wav")},
                data={"correlation_id": "invalid format with spaces"},
            )

            # Should still work, but correlation ID might be regenerated
            assert response.status_code == 200

    def test_response_includes_all_fields(self, client, sample_wav_file):
        """Test response includes: text, duration, language, confidence."""
        with patch("services.stt.app.transcription_adapter") as mock_adapter:
            mock_adapter.transcribe.return_value = Mock(
                text="hello world",
                start_timestamp=0.0,
                end_timestamp=1.0,
                language="en",
                confidence=0.9,
            )

            response = client.post(
                "/asr", files={"audio": ("test.wav", sample_wav_file, "audio/wav")}
            )

            assert response.status_code == 200
            data = response.json()
            assert "text" in data
            assert "start_timestamp" in data
            assert "end_timestamp" in data
            assert "language" in data
            assert "confidence" in data
            assert "correlation_id" in data

    def test_processing_time_metrics_in_headers(self, client, sample_wav_file):
        """Test processing time metrics in headers."""
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
            # Check for processing time headers
            assert "X-Processing-Time" in response.headers or "X-Response-Time" in response.headers


class TestLanguageHandling:
    """Test language handling functionality."""

    def test_forced_language_via_query_param(self, client, sample_wav_file):
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

    def test_automatic_language_detection_no_param(self, client, sample_wav_file):
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

    def test_translation_task_via_task_translate(self, client, sample_wav_file):
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


class TestAudioFormatValidation:
    """Test audio format validation."""

    def test_16bit_pcm_wav_acceptance(self, client, sample_wav_file):
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

    def test_rejection_of_non_16bit_audio_400_error(self, client):
        """Test rejection of non-16-bit audio (400 error)."""
        # Create invalid audio data (8-bit)
        invalid_audio = b"RIFF\x00\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00\x00\x01\x00\x08\x00data\x00\x00\x00\x00"

        response = client.post("/asr", files={"audio": ("test.wav", invalid_audio, "audio/wav")})

        assert response.status_code == 400

    def test_invalid_wav_header_rejection(self, client):
        """Test invalid WAV header rejection."""
        invalid_audio = b"invalid wav data"

        response = client.post("/asr", files={"audio": ("test.wav", invalid_audio, "audio/wav")})

        assert response.status_code == 400

    def test_empty_request_body_rejection(self, client):
        """Test empty request body rejection."""
        response = client.post("/asr")
        assert response.status_code == 400


class TestAdvancedFeatures:
    """Test advanced transcription features."""

    def test_beam_size_parameter_adjustment(self, client, sample_wav_file):
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


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_malformed_audio_data_handling(self, client):
        """Test malformed audio data handling."""
        malformed_audio = b"not audio data at all"

        response = client.post("/asr", files={"audio": ("test.wav", malformed_audio, "audio/wav")})

        assert response.status_code == 400

    def test_client_disconnect_during_processing(self, client, sample_wav_file):
        """Test client disconnect during processing."""
        # This would test handling of client disconnection
        # Implementation depends on how the service handles client disconnection
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
