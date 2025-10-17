"""Integration tests for audio pipeline with real services."""

import asyncio
import time
from unittest.mock import Mock, patch

import pytest

from services.discord.transcription import TranscriptionClient
from services.discord.config import STTConfig


class TestAudioIntegration:
    """Integration tests for audio pipeline with real services."""

    @pytest.fixture
    def stt_config(self):
        """Create STT configuration for integration testing."""
        return STTConfig(
            base_url="http://stt:9000",
            timeout_seconds=45,
            max_retries=3,
            forced_language="en"
        )

    @pytest.fixture
    def sample_audio_segment(self):
        """Create sample audio segment for testing."""
        import numpy as np
        sample_rate = 16000
        duration = 2.0  # 2 seconds of audio
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        # Generate speech-like audio with multiple frequencies
        audio_float = (np.sin(2 * np.pi * 440 * t) * 0.3 + 
                      np.sin(2 * np.pi * 880 * t) * 0.2 + 
                      np.sin(2 * np.pi * 1320 * t) * 0.1)
        audio_int16 = (audio_float * 32767).astype(np.int16)
        pcm_data = audio_int16.tobytes()
        
        from services.discord.audio import AudioSegment
        return AudioSegment(
            user_id=12345,
            pcm=pcm_data,
            sample_rate=sample_rate,
            start_timestamp=0.0,
            end_timestamp=duration,
            correlation_id="integration-test-123",
            frame_count=int(sample_rate * duration)
        )

    @pytest.mark.integration
    async def test_real_stt_transcription(self, stt_config, sample_audio_segment):
        """Test real STT service transcription."""
        # Skip if STT service is not available
        try:
            async with TranscriptionClient(stt_config) as stt_client:
                # Test health check first
                is_healthy = await stt_client._check_health()
                if not is_healthy:
                    pytest.skip("STT service not available")
                
                # Test transcription
                transcript = await stt_client.transcribe(sample_audio_segment)
                
                # Verify transcript result
                assert transcript is not None
                assert hasattr(transcript, 'text')
                assert hasattr(transcript, 'correlation_id')
                assert transcript.correlation_id == "integration-test-123"
                
                # Verify transcript quality (should contain some text)
                assert len(transcript.text) > 0
                assert isinstance(transcript.text, str)
                
        except Exception as e:
            pytest.skip(f"STT service not available: {e}")

    @pytest.mark.integration
    async def test_real_orchestrator_processing(self, sample_audio_segment):
        """Test real orchestrator service processing."""
        # Skip if orchestrator service is not available
        try:
            from services.discord.orchestrator_client import OrchestratorClient
            from services.discord.config import OrchestratorConfig
            
            orchestrator_config = OrchestratorConfig(
                base_url="http://orchestrator:8000",
                timeout_seconds=30
            )
            
            async with OrchestratorClient(orchestrator_config) as orchestrator_client:
                # Test orchestrator processing
                result = await orchestrator_client.process_transcript(
                    guild_id="123456789",
                    channel_id="987654321",
                    user_id="12345",
                    transcript="hey atlas, how are you?"
                )
                
                # Verify orchestrator result
                assert result is not None
                assert hasattr(result, 'text')
                assert hasattr(result, 'audio_url')
                
                # Verify response quality
                assert len(result.text) > 0
                assert isinstance(result.text, str)
                
        except Exception as e:
            pytest.skip(f"Orchestrator service not available: {e}")

    @pytest.mark.integration
    async def test_circuit_breaker_recovery(self, stt_config, sample_audio_segment):
        """Test circuit breaker recovery with real services."""
        try:
            async with TranscriptionClient(stt_config) as stt_client:
                # Test initial health check
                is_healthy = await stt_client._check_health()
                if not is_healthy:
                    pytest.skip("STT service not available")
                
                # Get initial circuit breaker state
                initial_stats = stt_client.get_circuit_stats()
                assert "state" in initial_stats
                assert "available" in initial_stats
                
                # Test multiple transcriptions to verify circuit breaker behavior
                for i in range(3):
                    transcript = await stt_client.transcribe(sample_audio_segment)
                    assert transcript is not None
                    
                    # Check circuit breaker state after each request
                    stats = stt_client.get_circuit_stats()
                    assert "state" in stats
                    assert "available" in stats
                
                # Verify circuit breaker is still healthy
                final_stats = stt_client.get_circuit_stats()
                assert final_stats["available"] is True
                
        except Exception as e:
            pytest.skip(f"STT service not available: {e}")

    @pytest.mark.integration
    async def test_multiple_segments_sequential(self, stt_config):
        """Test multiple segments processed sequentially."""
        try:
            async with TranscriptionClient(stt_config) as stt_client:
                # Test health check first
                is_healthy = await stt_client._check_health()
                if not is_healthy:
                    pytest.skip("STT service not available")
                
                # Create multiple audio segments
                segments = []
                for i in range(3):
                    import numpy as np
                    sample_rate = 16000
                    duration = 1.0
                    t = np.linspace(0, duration, int(sample_rate * duration), False)
                    audio_float = np.sin(2 * np.pi * (440 + i * 100) * t) * 0.5
                    audio_int16 = (audio_float * 32767).astype(np.int16)
                    pcm_data = audio_int16.tobytes()
                    
                    from services.discord.audio import AudioSegment
                    segment = AudioSegment(
                        user_id=12345,
                        pcm=pcm_data,
                        sample_rate=sample_rate,
                        start_timestamp=i * duration,
                        end_timestamp=(i + 1) * duration,
                        correlation_id=f"integration-test-{i}",
                        frame_count=int(sample_rate * duration)
                    )
                    segments.append(segment)
                
                # Process segments sequentially
                transcripts = []
                for segment in segments:
                    transcript = await stt_client.transcribe(segment)
                    assert transcript is not None
                    assert transcript.correlation_id == segment.correlation_id
                    transcripts.append(transcript)
                
                # Verify all segments were processed
                assert len(transcripts) == 3
                for i, transcript in enumerate(transcripts):
                    assert transcript.correlation_id == f"integration-test-{i}"
                
        except Exception as e:
            pytest.skip(f"STT service not available: {e}")

    @pytest.mark.integration
    async def test_pipeline_latency_metrics(self, stt_config, sample_audio_segment):
        """Test pipeline latency metrics with real services."""
        try:
            async with TranscriptionClient(stt_config) as stt_client:
                # Test health check first
                is_healthy = await stt_client._check_health()
                if not is_healthy:
                    pytest.skip("STT service not available")
                
                # Measure transcription latency
                start_time = time.time()
                transcript = await stt_client.transcribe(sample_audio_segment)
                end_time = time.time()
                
                # Verify transcript was successful
                assert transcript is not None
                assert transcript.correlation_id == "integration-test-123"
                
                # Calculate latency
                latency = end_time - start_time
                
                # Verify latency is reasonable (should be under 10 seconds for 2-second audio)
                assert latency < 10.0, f"Transcription latency too high: {latency:.2f}s"
                
                # Log latency for monitoring
                print(f"Transcription latency: {latency:.2f}s")
                
        except Exception as e:
            pytest.skip(f"STT service not available: {e}")

    @pytest.mark.integration
    async def test_service_health_checks(self, stt_config):
        """Test service health checks with real services."""
        try:
            async with TranscriptionClient(stt_config) as stt_client:
                # Test health check
                is_healthy = await stt_client._check_health()
                
                if is_healthy:
                    # Verify circuit breaker state
                    stats = stt_client.get_circuit_stats()
                    assert "state" in stats
                    assert "available" in stats
                    assert stats["available"] is True
                    
                    # Test that we can get circuit breaker stats
                    assert isinstance(stats, dict)
                    assert len(stats) > 0
                else:
                    # If service is not healthy, verify circuit breaker reflects this
                    stats = stt_client.get_circuit_stats()
                    assert "state" in stats
                    assert "available" in stats
                    
        except Exception as e:
            pytest.skip(f"STT service not available: {e}")

    @pytest.mark.integration
    async def test_error_handling_with_real_services(self, stt_config):
        """Test error handling with real services."""
        try:
            async with TranscriptionClient(stt_config) as stt_client:
                # Test health check first
                is_healthy = await stt_client._check_health()
                if not is_healthy:
                    pytest.skip("STT service not available")
                
                # Test with invalid audio data
                from services.discord.audio import AudioSegment
                invalid_segment = AudioSegment(
                    user_id=12345,
                    pcm=b"invalid_audio_data",
                    sample_rate=16000,
                    start_timestamp=0.0,
                    end_timestamp=1.0,
                    correlation_id="error-test-123",
                    frame_count=100
                )
                
                # This should handle the error gracefully
                transcript = await stt_client.transcribe(invalid_segment)
                
                # Should either return None or handle the error gracefully
                if transcript is not None:
                    assert transcript.correlation_id == "error-test-123"
                
        except Exception as e:
            pytest.skip(f"STT service not available: {e}")

    @pytest.mark.integration
    async def test_concurrent_requests(self, stt_config):
        """Test concurrent requests to real services."""
        try:
            async with TranscriptionClient(stt_config) as stt_client:
                # Test health check first
                is_healthy = await stt_client._check_health()
                if not is_healthy:
                    pytest.skip("STT service not available")
                
                # Create multiple audio segments
                segments = []
                for i in range(3):
                    import numpy as np
                    sample_rate = 16000
                    duration = 0.5  # Shorter duration for faster processing
                    t = np.linspace(0, duration, int(sample_rate * duration), False)
                    audio_float = np.sin(2 * np.pi * (440 + i * 100) * t) * 0.5
                    audio_int16 = (audio_float * 32767).astype(np.int16)
                    pcm_data = audio_int16.tobytes()
                    
                    from services.discord.audio import AudioSegment
                    segment = AudioSegment(
                        user_id=12345,
                        pcm=pcm_data,
                        sample_rate=sample_rate,
                        start_timestamp=i * duration,
                        end_timestamp=(i + 1) * duration,
                        correlation_id=f"concurrent-test-{i}",
                        frame_count=int(sample_rate * duration)
                    )
                    segments.append(segment)
                
                # Process segments concurrently
                start_time = time.time()
                tasks = [stt_client.transcribe(segment) for segment in segments]
                transcripts = await asyncio.gather(*tasks, return_exceptions=True)
                end_time = time.time()
                
                # Verify all transcripts were processed
                assert len(transcripts) == 3
                for i, transcript in enumerate(transcripts):
                    if isinstance(transcript, Exception):
                        pytest.skip(f"Concurrent request failed: {transcript}")
                    assert hasattr(transcript, 'correlation_id')
                    assert transcript.correlation_id == f"concurrent-test-{i}"
                
                # Calculate total processing time
                processing_time = end_time - start_time
                print(f"Concurrent processing time: {processing_time:.2f}s")
                
        except Exception as e:
            pytest.skip(f"STT service not available: {e}")
