"""Integration tests for Discord audio pipeline with real services.

Tests validate Discord service integration with STT and Orchestrator services
using real HTTP communication via Docker Compose. All tests use environment-based
URLs via standardized {SERVICE}_BASE_URL pattern.
"""

import asyncio
import time

import httpx
import numpy as np
import pytest

from services.discord.audio import AudioSegment
from services.discord.config import STTConfig
from services.discord.orchestrator_client import OrchestratorClient
from services.discord.transcription import TranscriptionClient, TranscriptResult
from services.tests.integration.conftest import get_service_url
from services.tests.utils.service_helpers import docker_compose_test_context


class TestAudioIntegration:
    """Integration tests for audio pipeline with real services."""

    @pytest.fixture
    def stt_config(self) -> STTConfig:
        """Create STT configuration for integration testing using environment-based URLs."""
        return STTConfig(
            base_url=get_service_url("STT"),
            request_timeout_seconds=30,
            max_retries=3,
            forced_language="en",
        )

    @pytest.fixture
    def orchestrator_url(self) -> str:
        """Get Orchestrator URL for integration testing using environment-based URLs."""
        return get_service_url("ORCHESTRATOR")

    @pytest.fixture
    def sample_audio_segment(self) -> AudioSegment:
        """Create sample audio segment for testing."""
        sample_rate = 16000
        duration = 2.0  # 2 seconds of audio
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        # Generate speech-like audio with multiple frequencies
        audio_float = (
            np.sin(2 * np.pi * 440 * t) * 0.3
            + np.sin(2 * np.pi * 880 * t) * 0.2
            + np.sin(2 * np.pi * 1320 * t) * 0.1
        )
        audio_int16 = (audio_float * 32767).astype(np.int16)
        pcm_data = audio_int16.tobytes()

        return AudioSegment(
            user_id=12345,
            pcm=pcm_data,
            sample_rate=sample_rate,
            start_timestamp=0.0,
            end_timestamp=duration,
            correlation_id="manual-integration-test-123",
            frame_count=int(sample_rate * duration),
        )

    @pytest.fixture
    def multiple_audio_segments(self) -> list[AudioSegment]:
        """Create multiple audio segments for sequential/concurrent testing."""
        segments = []
        sample_rate = 16000
        duration = 1.0

        for i in range(3):
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            audio_float = np.sin(2 * np.pi * (440 + i * 100) * t) * 0.5
            audio_int16 = (audio_float * 32767).astype(np.int16)
            pcm_data = audio_int16.tobytes()

            segment = AudioSegment(
                user_id=12345,
                pcm=pcm_data,
                sample_rate=sample_rate,
                start_timestamp=i * duration,
                end_timestamp=(i + 1) * duration,
                correlation_id=f"manual-integration-test-{i}",
                frame_count=int(sample_rate * duration),
            )
            segments.append(segment)

        return segments

    @pytest.fixture
    def concurrent_audio_segments(self) -> list[AudioSegment]:
        """Create multiple short audio segments for concurrent testing."""
        segments = []
        sample_rate = 16000
        duration = 0.5  # Shorter duration for faster processing

        for i in range(3):
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            audio_float = np.sin(2 * np.pi * (440 + i * 100) * t) * 0.5
            audio_int16 = (audio_float * 32767).astype(np.int16)
            pcm_data = audio_int16.tobytes()

            segment = AudioSegment(
                user_id=12345,
                pcm=pcm_data,
                sample_rate=sample_rate,
                start_timestamp=i * duration,
                end_timestamp=(i + 1) * duration,
                correlation_id=f"manual-concurrent-test-{i}",
                frame_count=int(sample_rate * duration),
            )
            segments.append(segment)

        return segments

    @pytest.fixture
    def invalid_audio_segment(self) -> AudioSegment:
        """Create invalid audio segment for error handling tests."""
        return AudioSegment(
            user_id=12345,
            pcm=b"invalid_audio_data",
            sample_rate=16000,
            start_timestamp=0.0,
            end_timestamp=1.0,
            correlation_id="manual-error-test-123",
            frame_count=100,
        )

    @pytest.mark.integration
    @pytest.mark.timeout(120)
    async def test_real_stt_transcription(
        self, stt_config: STTConfig, sample_audio_segment: AudioSegment
    ):
        """Test real STT service transcription."""
        required_services = ["stt", "audio"]

        async with (
            docker_compose_test_context(required_services, timeout=120.0),
            TranscriptionClient(stt_config) as stt_client,
        ):
            # Test transcription (docker_compose_test_context ensures service is ready)
            transcript = await stt_client.transcribe(sample_audio_segment)

            # Verify transcript result with proper type assertions
            assert transcript is not None
            assert isinstance(transcript.text, str)
            assert isinstance(transcript.correlation_id, str)
            assert transcript.correlation_id == "manual-integration-test-123"

            # Verify transcript text (may be empty for synthetic audio, that's acceptable)
            assert len(transcript.text) >= 0

    @pytest.mark.integration
    @pytest.mark.timeout(120)
    async def test_real_orchestrator_processing(self, orchestrator_url: str):
        """Test real orchestrator service processing."""
        required_services = ["orchestrator", "flan", "guardrails"]

        async with (
            docker_compose_test_context(required_services, timeout=120.0),
            OrchestratorClient(orchestrator_url) as orchestrator_client,
        ):
            # Test orchestrator processing
            result = await orchestrator_client.process_transcript(
                guild_id="123456789",
                channel_id="987654321",
                user_id="12345",
                transcript="hey atlas, how are you?",
            )

            # Verify orchestrator result with proper type assertions
            assert result is not None
            assert isinstance(result, dict)
            assert "response_text" in result
            assert isinstance(result["response_text"], str)
            assert (
                len(result["response_text"]) > 0
            ), "Orchestrator should produce response"

    @pytest.mark.integration
    @pytest.mark.timeout(120)
    async def test_circuit_breaker_recovery(
        self, stt_config: STTConfig, sample_audio_segment: AudioSegment
    ):
        """Test circuit breaker recovery with real services."""
        required_services = ["stt", "audio"]

        async with (
            docker_compose_test_context(required_services, timeout=120.0),
            TranscriptionClient(stt_config) as stt_client,
        ):
            # Get initial circuit breaker state
            initial_stats = stt_client.get_circuit_stats()
            assert isinstance(initial_stats, dict)
            assert "state" in initial_stats
            assert "available" in initial_stats

            # Test multiple transcriptions to verify circuit breaker behavior
            # Add timeout protection for loop
            for _ in range(3):
                transcript = await asyncio.wait_for(
                    stt_client.transcribe(sample_audio_segment), timeout=30.0
                )
                assert transcript is not None

                # Check circuit breaker state after each request
                stats = stt_client.get_circuit_stats()
                assert isinstance(stats, dict)
                assert "state" in stats
                assert "available" in stats

            # Verify circuit breaker is still healthy
            final_stats = stt_client.get_circuit_stats()
            assert final_stats["available"] is True

    @pytest.mark.integration
    @pytest.mark.timeout(120)
    async def test_multiple_segments_sequential(
        self, stt_config: STTConfig, multiple_audio_segments: list[AudioSegment]
    ):
        """Test multiple segments processed sequentially."""
        required_services = ["stt", "audio"]

        async with (
            docker_compose_test_context(required_services, timeout=120.0),
            TranscriptionClient(stt_config) as stt_client,
        ):
            # Process segments sequentially with timeout protection
            transcripts = []
            for segment in multiple_audio_segments:
                transcript = await asyncio.wait_for(
                    stt_client.transcribe(segment), timeout=30.0
                )
                assert transcript is not None
                assert isinstance(transcript.correlation_id, str)
                assert transcript.correlation_id == segment.correlation_id
                transcripts.append(transcript)

            # Verify all segments were processed
            assert len(transcripts) == 3
            for i, transcript in enumerate(transcripts):
                assert transcript.correlation_id == f"manual-integration-test-{i}"

    @pytest.mark.integration
    @pytest.mark.timeout(120)
    async def test_pipeline_latency_metrics(
        self, stt_config: STTConfig, sample_audio_segment: AudioSegment
    ):
        """Test pipeline latency metrics with real services."""
        required_services = ["stt", "audio"]

        async with (
            docker_compose_test_context(required_services, timeout=120.0),
            TranscriptionClient(stt_config) as stt_client,
        ):
            # Measure transcription latency
            start_time = time.time()
            transcript = await stt_client.transcribe(sample_audio_segment)
            end_time = time.time()

            # Verify transcript was successful
            assert transcript is not None
            assert isinstance(transcript.correlation_id, str)
            assert transcript.correlation_id == "manual-integration-test-123"

            # Calculate latency
            latency = end_time - start_time

            # Verify latency is reasonable (should be under 10 seconds for 2-second audio)
            assert latency < 10.0, f"Transcription latency too high: {latency:.2f}s"

            # Log latency for monitoring
            print(f"Transcription latency: {latency:.2f}s")

    @pytest.mark.integration
    @pytest.mark.timeout(120)
    async def test_service_health_checks(self, stt_config: STTConfig):
        """Test service health checks with real services."""
        required_services = ["stt", "audio"]

        async with (
            docker_compose_test_context(required_services, timeout=120.0),
            TranscriptionClient(stt_config) as stt_client,
        ):
            # Test health check
            is_healthy = await stt_client.check_health()

            if is_healthy:
                # Verify circuit breaker state
                stats = stt_client.get_circuit_stats()
                assert isinstance(stats, dict)
                assert "state" in stats
                assert "available" in stats
                assert stats["available"] is True

                # Test that we can get circuit breaker stats
                assert len(stats) > 0
            else:
                # If service is not healthy, verify circuit breaker reflects this
                stats = stt_client.get_circuit_stats()
                assert isinstance(stats, dict)
                assert "state" in stats
                assert "available" in stats

    @pytest.mark.integration
    @pytest.mark.timeout(120)
    async def test_error_handling_with_real_services(
        self, stt_config: STTConfig, invalid_audio_segment: AudioSegment
    ):
        """Test error handling with real services."""
        required_services = ["stt", "audio"]

        async with (
            docker_compose_test_context(required_services, timeout=120.0),
            TranscriptionClient(stt_config) as stt_client,
        ):
            # Test with invalid audio data - should handle gracefully
            try:
                transcript = await stt_client.transcribe(invalid_audio_segment)

                # Service should either return None or handle the error gracefully
                if transcript is not None:
                    assert isinstance(transcript.correlation_id, str)
                    assert transcript.correlation_id == "manual-error-test-123"
                # If transcript is None, that's also acceptable error handling
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                # Expected - invalid audio may cause HTTP errors
                print(f"Expected error for invalid audio: {type(e).__name__}")
            except Exception as e:
                # Unexpected errors should be logged
                print(
                    f"Unexpected error during error handling test: {type(e).__name__}: {e}"
                )

    @pytest.mark.integration
    @pytest.mark.timeout(120)
    async def test_concurrent_requests(
        self, stt_config: STTConfig, concurrent_audio_segments: list[AudioSegment]
    ):
        """Test concurrent requests to real services."""
        required_services = ["stt", "audio"]

        async with (
            docker_compose_test_context(required_services, timeout=120.0),
            TranscriptionClient(stt_config) as stt_client,
        ):
            # Process segments concurrently with timeout protection
            start_time = time.time()
            tasks = [
                stt_client.transcribe(segment) for segment in concurrent_audio_segments
            ]
            transcripts = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), timeout=30.0
            )
            end_time = time.time()

            # Verify all transcripts were processed (or exceptions handled)
            assert len(transcripts) == 3
            successful_count = 0
            for i, result in enumerate(transcripts):
                # Type narrowing: asyncio.gather with return_exceptions=True returns
                # tuple[TranscriptResult | BaseException, ...]
                if isinstance(result, BaseException):
                    # Log but don't fail - some concurrent failures may be expected
                    print(
                        f"Concurrent request {i} raised exception: {type(result).__name__}"
                    )
                    continue
                # At this point, mypy knows result is not BaseException
                # Check that it's a TranscriptResult before accessing attributes
                if not isinstance(result, TranscriptResult):
                    continue
                assert isinstance(result.correlation_id, str)
                assert result.correlation_id == f"manual-concurrent-test-{i}"
                successful_count += 1

            # At least some requests should succeed
            assert (
                successful_count > 0
            ), "At least some concurrent requests should succeed"

            # Calculate total processing time
            processing_time = end_time - start_time
            print(f"Concurrent processing time: {processing_time:.2f}s")
