"""Tests for the audio processor API endpoints."""

import base64
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from services.audio.app import app


class TestAudioProcessorAPI:
    """Test cases for audio processor API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def sample_pcm_data(self):
        """Create sample PCM data for testing."""
        import numpy as np

        # Generate 1 second of 16kHz audio
        sample_rate = 16000
        duration = 1.0
        samples = int(sample_rate * duration)

        # Generate sine wave
        frequency = 440  # A4 note
        t = np.linspace(0, duration, samples, False)
        audio_data = np.sin(2 * np.pi * frequency * t)

        # Convert to int16 PCM
        pcm_data = (audio_data * 32767).astype(np.int16).tobytes()
        return base64.b64encode(pcm_data).decode()

    @pytest.fixture
    def sample_wav_data(self):
        """Create sample WAV data for testing."""
        import io
        import wave

        import numpy as np

        # Generate 1 second of 16kHz audio
        sample_rate = 16000
        duration = 1.0
        samples = int(sample_rate * duration)

        # Generate sine wave
        frequency = 440  # A4 note
        t = np.linspace(0, duration, samples, False)
        audio_data = np.sin(2 * np.pi * frequency * t)

        # Convert to int16 PCM
        pcm_data = (audio_data * 32767).astype(np.int16)

        # Create WAV file
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data.tobytes())

        return wav_buffer.getvalue()

    def test_health_live(self, client):
        """Test liveness health check."""
        response = client.get("/health/live")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert data["service"] == "audio"

    def test_health_ready(self, client):
        """Test readiness health check."""
        response = client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "service" in data
        assert "components" in data
        assert "dependencies" in data
        assert "health_details" in data
        assert "performance" in data

    def test_process_frame_success(self, client, sample_pcm_data):
        """Test successful frame processing."""
        with patch("services.audio.app._audio") as mock_processor:
            mock_processor.process_frame.return_value = Mock(
                pcm=base64.b64decode(sample_pcm_data), sequence=1, sample_rate=16000
            )
            mock_processor.calculate_quality_metrics.return_value = {
                "rms": 0.5,
                "snr_db": 20.0,
                "clarity_score": 0.8,
            }

            response = client.post(
                "/process/frame",
                json={
                    "pcm": sample_pcm_data,
                    "timestamp": 0.0,
                    "rms": 0.5,
                    "duration": 1.0,
                    "sequence": 1,
                    "sample_rate": 16000,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "pcm" in data
            assert "processing_time_ms" in data
            assert "quality_metrics" in data
            assert data["quality_metrics"]["rms"] == 0.5

    def test_process_frame_processor_not_initialized(self, client, sample_pcm_data):
        """Test frame processing when processor is not initialized."""
        with patch("services.audio.app._audio", None):
            response = client.post(
                "/process/frame",
                json={
                    "pcm": sample_pcm_data,
                    "timestamp": 0.0,
                    "rms": 0.5,
                    "duration": 1.0,
                    "sequence": 1,
                    "sample_rate": 16000,
                },
            )

            assert response.status_code == 503
            data = response.json()
            assert "Audio processor not initialized" in data["detail"]

    def test_process_segment_success(self, client, sample_pcm_data):
        """Test successful segment processing."""
        with patch("services.audio.app._audio") as mock_processor:
            mock_processor.process_segment.return_value = Mock(
                pcm=base64.b64decode(sample_pcm_data),
                user_id=12345,
                correlation_id="test-123",
                sample_rate=16000,
            )
            mock_processor.calculate_quality_metrics.return_value = {
                "rms": 0.5,
                "snr_db": 20.0,
                "clarity_score": 0.8,
            }

            response = client.post(
                "/process/segment",
                json={
                    "user_id": 12345,
                    "pcm": sample_pcm_data,
                    "start_timestamp": 0.0,
                    "end_timestamp": 1.0,
                    "correlation_id": "test-123",
                    "frame_count": 1,
                    "sample_rate": 16000,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "pcm" in data
            assert "processing_time_ms" in data
            assert "quality_metrics" in data

    def test_process_segment_processor_not_initialized(self, client, sample_pcm_data):
        """Test segment processing when processor is not initialized."""
        with patch("services.audio.app._audio", None):
            response = client.post(
                "/process/segment",
                json={
                    "user_id": 12345,
                    "pcm": sample_pcm_data,
                    "start_timestamp": 0.0,
                    "end_timestamp": 1.0,
                    "correlation_id": "test-123",
                    "frame_count": 1,
                    "sample_rate": 16000,
                },
            )

            assert response.status_code == 503
            data = response.json()
            assert "Audio processor not initialized" in data["detail"]

    def test_enhance_audio_success(self, client, sample_wav_data):
        """Test successful audio enhancement."""
        from unittest.mock import AsyncMock

        with patch("services.audio.app._audio_enhancer") as mock_enhancer:
            mock_enhancer.enhance_audio_bytes = AsyncMock(return_value=sample_wav_data)

            response = client.post("/enhance/audio", content=sample_wav_data)

            assert response.status_code == 200
            assert response.content == sample_wav_data

    def test_enhance_audio_enhancer_not_initialized(self, client, sample_wav_data):
        """Test audio enhancement when enhancer is not initialized."""
        with patch("services.audio.app._audio_enhancer", None):
            response = client.post("/enhance/audio", content=sample_wav_data)

            assert response.status_code == 503
            data = response.json()
            assert "Audio enhancer not initialized" in data["detail"]

    def test_enhance_audio_error_handling(self, client, sample_wav_data):
        """Test audio enhancement error handling."""
        with patch("services.audio.app._audio_enhancer") as mock_enhancer:
            mock_enhancer.enhance_audio_bytes.side_effect = Exception(
                "Enhancement failed"
            )

            response = client.post("/enhance/audio", content=sample_wav_data)

            # Should return original data on error
            assert response.status_code == 200
            assert response.content == sample_wav_data

    def test_enhance_audio_single_body_read(self, client, sample_wav_data):
        """Verify request body is cached and reused (indirect test via error path)."""
        from unittest.mock import AsyncMock

        # Test that error path returns cached original data (proving single read)
        with patch("services.audio.app._audio_enhancer") as mock_enhancer:
            mock_enhancer.enhance_audio_bytes = AsyncMock(
                side_effect=Exception("Test error")
            )

            response = client.post("/enhance/audio", content=sample_wav_data)

            # Should return original data on error (proving it was cached from single read)
            assert response.status_code == 200
            assert response.content == sample_wav_data
            # Verify enhance_audio_bytes was called with the body data (proves single read occurred)
            mock_enhancer.enhance_audio_bytes.assert_called_once()
            # Verify the call argument matches our input (proves caching worked)
            call_args = mock_enhancer.enhance_audio_bytes.call_args[0][0]
            assert call_args == sample_wav_data

    def test_get_metrics(self, client):
        """Test metrics endpoint."""
        response = client.get("/metrics")

        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "uptime_seconds" in data
        assert "status" in data
        assert "components" in data
        assert data["service"] == "audio"

    def test_process_frame_invalid_data(self, client):
        """Test frame processing with invalid data."""
        response = client.post(
            "/process/frame",
            json={
                "pcm": "invalid-base64",
                "timestamp": 0.0,
                "rms": 0.5,
                "duration": 1.0,
                "sequence": 1,
                "sample_rate": 16000,
            },
        )

        # Should handle gracefully
        assert response.status_code in [200, 422]  # Either success or validation error

    def test_process_segment_invalid_data(self, client):
        """Test segment processing with invalid data."""
        response = client.post(
            "/process/segment",
            json={
                "user_id": "invalid-user-id",
                "pcm": "invalid-base64",
                "start_timestamp": 0.0,
                "end_timestamp": 1.0,
                "correlation_id": "test-123",
                "frame_count": 1,
                "sample_rate": 16000,
            },
        )

        # Should handle gracefully
        assert response.status_code in [200, 422]  # Either success or validation error

    def test_process_frame_error_handling(self, client, sample_pcm_data):
        """Test frame processing error handling."""
        with patch("services.audio.app._audio") as mock_processor:
            mock_processor.process_frame.side_effect = Exception("Processing failed")

            response = client.post(
                "/process/frame",
                json={
                    "pcm": sample_pcm_data,
                    "timestamp": 0.0,
                    "rms": 0.5,
                    "duration": 1.0,
                    "sequence": 1,
                    "sample_rate": 16000,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "error" in data
            assert "Processing failed" in data["error"]

    def test_process_segment_error_handling(self, client, sample_pcm_data):
        """Test segment processing error handling."""
        with patch("services.audio.app._audio") as mock_processor:
            mock_processor.process_segment.side_effect = Exception("Processing failed")

            response = client.post(
                "/process/segment",
                json={
                    "user_id": 12345,
                    "pcm": sample_pcm_data,
                    "start_timestamp": 0.0,
                    "end_timestamp": 1.0,
                    "correlation_id": "test-123",
                    "frame_count": 1,
                    "sample_rate": 16000,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "error" in data
            assert "Processing failed" in data["error"]
