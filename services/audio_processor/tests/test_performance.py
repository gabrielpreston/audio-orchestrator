"""Performance tests for the audio processor service."""

import asyncio
import base64
import time
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
import numpy as np
import pytest

from services.audio_processor.app import app


class TestAudioProcessorPerformance:
    """Performance tests for audio processor service."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def sample_pcm_data(self):
        """Create sample PCM data for testing."""
        # Generate 20ms of 16kHz audio (typical frame size)
        sample_rate = 16000
        duration = 0.02  # 20ms
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

    def create_pcm_frame(self, duration_ms: float = 20) -> dict:
        """Create PCM frame data for testing."""
        sample_rate = 16000
        duration = duration_ms / 1000.0
        samples = int(sample_rate * duration)

        # Generate sine wave
        frequency = 440
        t = np.linspace(0, duration, samples, False)
        audio_data = np.sin(2 * np.pi * frequency * t)

        # Convert to int16 PCM
        pcm_data = (audio_data * 32767).astype(np.int16).tobytes()

        return {
            "pcm": base64.b64encode(pcm_data).decode(),
            "timestamp": time.time(),
            "rms": 0.5,
            "duration": duration,
            "sequence": 1,
            "sample_rate": sample_rate,
        }

    def create_test_wav(self, duration_s: float = 1.0) -> bytes:
        """Create test WAV data."""
        import io
        import wave

        sample_rate = 16000
        samples = int(sample_rate * duration_s)

        # Generate sine wave
        frequency = 440
        t = np.linspace(0, duration_s, samples, False)
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

    @pytest.mark.asyncio
    async def test_frame_processing_latency_single(self, client):
        """Test single frame processing meets 20ms requirement."""
        with patch("services.audio_processor.app._audio_processor") as mock_processor:
            mock_processor.process_frame.return_value = Mock(
                pcm=b"processed_data", sequence=1, sample_rate=16000
            )
            mock_processor.calculate_quality_metrics.return_value = {
                "rms": 0.5,
                "snr_db": 20.0,
                "clarity_score": 0.8,
            }

            frame_data = self.create_pcm_frame(duration_ms=20)

            latencies = []
            for _ in range(100):
                start = time.perf_counter()
                response = client.post("/process/frame", json=frame_data)
                assert response.status_code == 200
                latencies.append(time.perf_counter() - start)

            p50 = np.percentile(latencies, 50)
            p95 = np.percentile(latencies, 95)
            p99 = np.percentile(latencies, 99)

            assert p50 < 0.015, f"P50 latency {p50 * 1000:.1f}ms exceeds 15ms target"
            assert p95 < 0.020, f"P95 latency {p95 * 1000:.1f}ms exceeds 20ms target"
            assert p99 < 0.030, f"P99 latency {p99 * 1000:.1f}ms exceeds 30ms limit"

    @pytest.mark.asyncio
    async def test_enhancement_latency_single(self, client):
        """Test audio enhancement meets 50ms requirement."""
        with patch("services.audio_processor.app._audio_enhancer") as mock_enhancer:
            mock_enhancer.enhance_audio.return_value = self.create_test_wav(
                duration_s=1.0
            )

            wav_data = self.create_test_wav(duration_s=1.0)

            latencies = []
            for _ in range(50):
                start = time.perf_counter()
                response = client.post("/enhance/audio", content=wav_data)
                assert response.status_code == 200
                latencies.append(time.perf_counter() - start)

            p50 = np.percentile(latencies, 50)
            p95 = np.percentile(latencies, 95)

            assert p50 < 0.040, f"P50 latency {p50 * 1000:.1f}ms exceeds 40ms target"
            assert p95 < 0.050, f"P95 latency {p95 * 1000:.1f}ms exceeds 50ms target"

    @pytest.mark.asyncio
    async def test_concurrent_load_10_requests(self, client):
        """Test performance under 10 concurrent requests."""
        with patch("services.audio_processor.app._audio_processor") as mock_processor:
            mock_processor.process_frame.return_value = Mock(
                pcm=b"processed_data", sequence=1, sample_rate=16000
            )
            mock_processor.calculate_quality_metrics.return_value = {
                "rms": 0.5,
                "snr_db": 20.0,
                "clarity_score": 0.8,
            }

            frame_data = self.create_pcm_frame()

            async def make_request():
                response = client.post("/process/frame", json=frame_data)
                assert response.status_code == 200
                return response

            tasks = [make_request() for _ in range(10)]

            start = time.perf_counter()
            responses = await asyncio.gather(*tasks)
            total_time = time.perf_counter() - start

            assert all(r.status_code == 200 for r in responses)
            assert (
                total_time < 0.100
            ), f"10 concurrent requests took {total_time * 1000:.1f}ms"

    @pytest.mark.asyncio
    async def test_concurrent_load_50_requests(self, client):
        """Test performance under 50 concurrent requests."""
        with patch("services.audio_processor.app._audio_processor") as mock_processor:
            mock_processor.process_frame.return_value = Mock(
                pcm=b"processed_data", sequence=1, sample_rate=16000
            )
            mock_processor.calculate_quality_metrics.return_value = {
                "rms": 0.5,
                "snr_db": 20.0,
                "clarity_score": 0.8,
            }

            frame_data = self.create_pcm_frame()

            async def make_request():
                response = client.post("/process/frame", json=frame_data)
                assert response.status_code == 200
                return response

            tasks = [make_request() for _ in range(50)]

            start = time.perf_counter()
            responses = await asyncio.gather(*tasks)
            total_time = time.perf_counter() - start

            assert all(r.status_code == 200 for r in responses)
            assert (
                total_time < 0.500
            ), f"50 concurrent requests took {total_time * 1000:.1f}ms"

    @pytest.mark.asyncio
    async def test_memory_stability_under_load(self, client):
        """Test memory stability during sustained load."""
        try:
            import psutil

            process = psutil.Process()
        except ImportError:
            pytest.skip("psutil not available")

        with patch("services.audio_processor.app._audio_processor") as mock_processor:
            mock_processor.process_frame.return_value = Mock(
                pcm=b"processed_data", sequence=1, sample_rate=16000
            )
            mock_processor.calculate_quality_metrics.return_value = {
                "rms": 0.5,
                "snr_db": 20.0,
                "clarity_score": 0.8,
            }

            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            frame_data = self.create_pcm_frame()

            # Process 1000 frames
            for _ in range(1000):
                response = client.post("/process/frame", json=frame_data)
                assert response.status_code == 200
                assert response.status_code == 200

            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory

            assert memory_increase < 100, f"Memory increased by {memory_increase:.1f}MB"

    @pytest.mark.asyncio
    async def test_end_to_end_voice_pipeline_latency(self, client):
        """Test complete voice pipeline latency."""
        with (
            patch("services.audio_processor.app._audio_processor") as mock_processor,
            patch("services.audio_processor.app._audio_enhancer") as mock_enhancer,
        ):
            mock_processor.process_frame.return_value = Mock(
                pcm=b"processed_data", sequence=1, sample_rate=16000
            )
            mock_processor.calculate_quality_metrics.return_value = {
                "rms": 0.5,
                "snr_db": 20.0,
                "clarity_score": 0.8,
            }
            mock_enhancer.enhance_audio.return_value = self.create_test_wav()

            # Simulate: Discord capture → audio-processor → STT
            start = time.perf_counter()

            # 1. Process frame
            frame_data = self.create_pcm_frame()
            frame_response = client.post("/process/frame", json=frame_data)
            assert frame_response.status_code == 200

            # 2. Enhance audio
            wav_data = self.create_test_wav()
            enhance_response = client.post("/enhance/audio", content=wav_data)
            assert enhance_response.status_code == 200

            total_latency = time.perf_counter() - start

            assert (
                total_latency < 0.100
            ), f"E2E pipeline took {total_latency * 1000:.1f}ms"

    def test_processing_time_consistency(self, client):
        """Test that processing time is consistent across requests."""
        with patch("services.audio_processor.app._audio_processor") as mock_processor:
            mock_processor.process_frame.return_value = Mock(
                pcm=b"processed_data", sequence=1, sample_rate=16000
            )
            mock_processor.calculate_quality_metrics.return_value = {
                "rms": 0.5,
                "snr_db": 20.0,
                "clarity_score": 0.8,
            }

            frame_data = self.create_pcm_frame()
            processing_times = []

            for _ in range(20):
                response = client.post("/process/frame", json=frame_data)
                assert response.status_code == 200
                assert response.status_code == 200

                data = response.json()
                processing_times.append(data["processing_time_ms"])

            # Check that processing times are reasonable
            avg_time = np.mean(processing_times)
            std_time = np.std(processing_times)

            assert (
                avg_time < 50
            ), f"Average processing time {avg_time:.1f}ms is too high"
            assert (
                std_time < avg_time * 0.5
            ), f"Processing time variance {std_time:.1f}ms is too high"

    def test_throughput_under_load(self, client):
        """Test throughput under sustained load."""
        with patch("services.audio_processor.app._audio_processor") as mock_processor:
            mock_processor.process_frame.return_value = Mock(
                pcm=b"processed_data", sequence=1, sample_rate=16000
            )
            mock_processor.calculate_quality_metrics.return_value = {
                "rms": 0.5,
                "snr_db": 20.0,
                "clarity_score": 0.8,
            }

            frame_data = self.create_pcm_frame()
            start_time = time.perf_counter()

            # Process 100 frames
            for _ in range(100):
                response = client.post("/process/frame", json=frame_data)
                assert response.status_code == 200
                assert response.status_code == 200

            total_time = time.perf_counter() - start_time
            throughput = 100 / total_time  # requests per second

            assert throughput > 10, f"Throughput {throughput:.1f} req/s is too low"

    def test_latency_percentiles(self, client):
        """Test latency percentiles for frame processing."""
        with patch("services.audio_processor.app._audio_processor") as mock_processor:
            mock_processor.process_frame.return_value = Mock(
                pcm=b"processed_data", sequence=1, sample_rate=16000
            )
            mock_processor.calculate_quality_metrics.return_value = {
                "rms": 0.5,
                "snr_db": 20.0,
                "clarity_score": 0.8,
            }

            frame_data = self.create_pcm_frame()
            latencies = []

            for _ in range(200):
                start = time.perf_counter()
                response = client.post("/process/frame", json=frame_data)
                assert response.status_code == 200
                latencies.append(time.perf_counter() - start)

            p50 = np.percentile(latencies, 50)
            p90 = np.percentile(latencies, 90)
            p95 = np.percentile(latencies, 95)
            p99 = np.percentile(latencies, 99)

            # Industry standards for real-time audio
            assert p50 < 0.010, f"P50 latency {p50 * 1000:.1f}ms exceeds 10ms"
            assert p90 < 0.015, f"P90 latency {p90 * 1000:.1f}ms exceeds 15ms"
            assert p95 < 0.020, f"P95 latency {p95 * 1000:.1f}ms exceeds 20ms"
            assert p99 < 0.030, f"P99 latency {p99 * 1000:.1f}ms exceeds 30ms"
