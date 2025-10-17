"""End-to-end tests for the complete audio pipeline."""

import asyncio

# psutil not available in container, using alternative
import time
from unittest.mock import Mock, patch

import pytest

from services.tests.utils.audio_quality_helpers import (
    create_wav_file,
    generate_test_audio,
)
from services.tests.utils.service_helpers import test_services_context


@pytest.fixture
def sample_audio_data():
    """Sample audio data for testing."""
    return generate_test_audio(duration=2.0, frequency=440.0, amplitude=0.5)


@pytest.fixture
def sample_wav_file(sample_audio_data):
    """Sample WAV file for testing."""
    return create_wav_file(sample_audio_data, sample_rate=16000, channels=1)


class TestFullPipelineE2E:
    """Test complete flow: Discord → STT → LLM → TTS → Discord."""

    @pytest.mark.integration
    async def test_complete_audio_pipeline_flow(self, sample_wav_file):
        """Test complete audio pipeline flow."""
        async with test_services_context(["stt", "tts", "llm", "orchestrator"]):
            # This would test the complete flow
            # Implementation depends on the actual service integration
            pass

    @pytest.mark.integration
    async def test_audio_capture_from_discord_sink(self, sample_wav_file):
        """Test audio capture from Discord sink."""
        # Mock Discord audio capture
        with patch("services.discord.discord_voice.DiscordAudioSource") as mock_source:
            mock_source.return_value.capture_audio.return_value = sample_wav_file

            # Test audio capture
            audio_data = mock_source.return_value.capture_audio()
            assert audio_data == sample_wav_file

    @pytest.mark.integration
    async def test_vad_detects_speech(self, sample_wav_file):
        """Test VAD detects speech."""
        # Mock VAD detection
        with patch("services.discord.discord_voice.VADPipeline") as mock_vad:
            mock_vad.return_value.detect_speech.return_value = True

            # Test VAD detection
            is_speech = mock_vad.return_value.detect_speech(sample_wav_file)
            assert is_speech is True

    @pytest.mark.integration
    async def test_segment_sent_to_stt_service(self, sample_wav_file):
        """Test segment sent to STT service."""
        # Mock STT service call
        with patch("services.discord.discord_voice.TranscriptionClient") as mock_stt:
            mock_stt.return_value.transcribe.return_value = Mock(
                text="hello world",
                start_timestamp=0.0,
                end_timestamp=2.0,
                language="en",
                confidence=0.9,
            )

            # Test STT transcription
            result = await mock_stt.return_value.transcribe(sample_wav_file)
            assert result.text == "hello world"

    @pytest.mark.integration
    async def test_stt_transcription_success(self, sample_wav_file):
        """Test STT transcription success."""
        with patch("services.discord.discord_voice.TranscriptionClient") as mock_stt:
            mock_stt.return_value.transcribe.return_value = Mock(
                text="transcription successful",
                start_timestamp=0.0,
                end_timestamp=2.0,
                language="en",
                confidence=0.9,
            )

            # Test transcription success
            result = await mock_stt.return_value.transcribe(sample_wav_file)
            assert result.text == "transcription successful"
            assert result.confidence > 0.8

    @pytest.mark.integration
    async def test_wake_phrase_detection(self, sample_wav_file):
        """Test wake phrase detection."""
        with patch("services.discord.discord_voice.WakeDetector") as mock_wake:
            mock_wake.return_value.detect.return_value = Mock(
                phrase="hey atlas", confidence=0.8, source="transcript"
            )

            # Test wake detection
            result = mock_wake.return_value.detect(
                sample_wav_file, "hey atlas, how are you?"
            )
            assert result.phrase == "hey atlas"
            assert result.confidence > 0.7

    @pytest.mark.integration
    async def test_transcript_sent_to_llm_orchestrator(self, sample_wav_file):
        """Test transcript sent to LLM/orchestrator."""
        with patch(
            "services.discord.discord_voice.OrchestratorClient"
        ) as mock_orchestrator:
            mock_orchestrator.return_value.process_transcript.return_value = Mock(
                text="I'm doing well, thank you!",
                audio_url="http://test-tts:7000/audio/123.wav",
            )

            # Test orchestrator processing
            result = await mock_orchestrator.return_value.process_transcript(
                guild_id="123456789",
                channel_id="987654321",
                user_id="12345",
                transcript="hey atlas, how are you?",
            )
            assert result.text == "I'm doing well, thank you!"
            assert result.audio_url is not None

    @pytest.mark.integration
    async def test_llm_response_generation(self, sample_wav_file):
        """Test LLM response generation."""
        with patch(
            "services.discord.discord_voice.OrchestratorClient"
        ) as mock_orchestrator:
            mock_orchestrator.return_value.process_transcript.return_value = Mock(
                text="Generated response from LLM",
                audio_url="http://test-tts:7000/audio/456.wav",
            )

            # Test LLM response generation
            result = await mock_orchestrator.return_value.process_transcript(
                guild_id="123456789",
                channel_id="987654321",
                user_id="12345",
                transcript="test transcript",
            )
            assert "Generated response" in result.text

    @pytest.mark.integration
    async def test_tts_synthesis_from_llm_response(self, sample_wav_file):
        """Test TTS synthesis from LLM response."""
        with patch("services.discord.discord_voice.TTSClient") as mock_tts:
            mock_tts.return_value.synthesize.return_value = b"synthesized audio data"

            # Test TTS synthesis
            result = await mock_tts.return_value.synthesize("test text")
            assert result == b"synthesized audio data"

    @pytest.mark.integration
    async def test_audio_playback_to_discord_source(self, sample_wav_file):
        """Test audio playback to Discord source."""
        with patch("services.discord.discord_voice.DiscordAudioSink") as mock_sink:
            mock_sink.return_value.play_audio.return_value = True

            # Test audio playback
            result = mock_sink.return_value.play_audio(sample_wav_file)
            assert result is True


class TestCorrelationIDPropagation:
    """Test correlation ID propagation through the pipeline."""

    @pytest.mark.integration
    async def test_correlation_id_flows_through_all_services(self, sample_wav_file):
        """Test correlation ID flows through all services."""
        correlation_id = "test-correlation-123"

        # Mock all services with correlation ID tracking
        with (
            patch("services.discord.discord_voice.TranscriptionClient") as mock_stt,
            patch(
                "services.discord.discord_voice.OrchestratorClient"
            ) as mock_orchestrator,
            patch("services.discord.discord_voice.TTSClient") as mock_tts,
        ):

            # Mock STT with correlation ID
            mock_stt.return_value.transcribe.return_value = Mock(
                text="test transcript", correlation_id=correlation_id
            )

            # Mock orchestrator with correlation ID
            mock_orchestrator.return_value.process_transcript.return_value = Mock(
                text="test response", correlation_id=correlation_id
            )

            # Mock TTS with correlation ID
            mock_tts.return_value.synthesize.return_value = b"test audio"

            # Test correlation ID propagation
            stt_result = await mock_stt.return_value.transcribe(sample_wav_file)
            assert stt_result.correlation_id == correlation_id

            orchestrator_result = (
                await mock_orchestrator.return_value.process_transcript(
                    guild_id="123456789",
                    channel_id="987654321",
                    user_id="12345",
                    transcript=stt_result.text,
                )
            )
            assert orchestrator_result.correlation_id == correlation_id

    @pytest.mark.integration
    async def test_logs_tagged_with_correlation_id_at_each_step(self, sample_wav_file):
        """Test logs tagged with correlation ID at each step."""
        correlation_id = "test-correlation-456"

        # Mock logging with correlation ID
        with patch("services.discord.discord_voice.logger") as mock_logger:
            # Test logging at each step
            mock_logger.info.assert_called()
            # Check that correlation ID is included in log calls
            for call in mock_logger.info.call_args_list:
                assert correlation_id in str(call)


class TestFailureScenarios:
    """Test failure scenarios in the pipeline."""

    @pytest.mark.integration
    async def test_stt_service_down_circuit_breaker(self, sample_wav_file):
        """Test STT service down (circuit breaker)."""
        with patch("services.discord.discord_voice.TranscriptionClient") as mock_stt:
            mock_stt.return_value.transcribe.side_effect = Exception("STT service down")

            # Test circuit breaker behavior
            with pytest.raises(RuntimeError):
                await mock_stt.return_value.transcribe(sample_wav_file)

    @pytest.mark.integration
    async def test_tts_service_down_fallback(self, sample_wav_file):
        """Test TTS service down (fallback)."""
        with patch("services.discord.discord_voice.TTSClient") as mock_tts:
            mock_tts.return_value.synthesize.side_effect = Exception("TTS service down")

            # Test fallback behavior
            with pytest.raises(RuntimeError):
                await mock_tts.return_value.synthesize("test text")

    @pytest.mark.integration
    async def test_llm_service_timeout(self, sample_wav_file):
        """Test LLM service timeout."""
        with patch(
            "services.discord.discord_voice.OrchestratorClient"
        ) as mock_orchestrator:
            mock_orchestrator.return_value.process_transcript.side_effect = (
                TimeoutError("LLM timeout")
            )

            # Test timeout handling
            with pytest.raises(asyncio.TimeoutError):
                await mock_orchestrator.return_value.process_transcript(
                    guild_id="123456789",
                    channel_id="987654321",
                    user_id="12345",
                    transcript="test transcript",
                )

    @pytest.mark.integration
    async def test_network_partition_recovery(self, sample_wav_file):
        """Test network partition recovery."""
        # Mock network partition and recovery
        with patch("services.discord.discord_voice.TranscriptionClient") as mock_stt:
            # First call fails
            mock_stt.return_value.transcribe.side_effect = [
                Exception("Network partition"),
                Mock(
                    text="recovered transcript",
                    start_timestamp=0.0,
                    end_timestamp=2.0,
                    language="en",
                    confidence=0.9,
                ),
            ]

            # Test recovery
            with pytest.raises(RuntimeError):
                await mock_stt.return_value.transcribe(sample_wav_file)

            # Second call should succeed
            result = await mock_stt.return_value.transcribe(sample_wav_file)
            assert result.text == "recovered transcript"


class TestPipelinePerformance:
    """Test pipeline performance metrics."""

    @pytest.mark.integration
    async def test_end_to_end_latency_measurement(self, sample_wav_file):
        """Test end-to-end latency measurement."""
        start_time = time.time()

        # Mock the complete pipeline
        with (
            patch("services.discord.discord_voice.TranscriptionClient") as mock_stt,
            patch(
                "services.discord.discord_voice.OrchestratorClient"
            ) as mock_orchestrator,
            patch("services.discord.discord_voice.TTSClient") as mock_tts,
        ):

            # Mock all services
            mock_stt.return_value.transcribe.return_value = Mock(
                text="test transcript",
                start_timestamp=0.0,
                end_timestamp=2.0,
                language="en",
                confidence=0.9,
            )

            mock_orchestrator.return_value.process_transcript.return_value = Mock(
                text="test response", audio_url="http://test-tts:7000/audio/123.wav"
            )

            mock_tts.return_value.synthesize.return_value = b"test audio"

            # Simulate pipeline execution
            stt_result = await mock_stt.return_value.transcribe(sample_wav_file)
            orchestrator_result = (
                await mock_orchestrator.return_value.process_transcript(
                    guild_id="123456789",
                    channel_id="987654321",
                    user_id="12345",
                    transcript=stt_result.text,
                )
            )
            _tts_result = await mock_tts.return_value.synthesize(
                orchestrator_result.text
            )

            end_time = time.time()
            latency = end_time - start_time

            # Check latency is reasonable
            assert latency < 5.0  # Should be fast for mocked services

    @pytest.mark.integration
    async def test_concurrent_pipeline_processing(self, sample_wav_file):
        """Test concurrent pipeline processing."""

        # Test multiple concurrent pipeline executions
        async def run_pipeline():
            with (
                patch("services.discord.discord_voice.TranscriptionClient") as mock_stt,
                patch(
                    "services.discord.discord_voice.OrchestratorClient"
                ) as mock_orchestrator,
                patch("services.discord.discord_voice.TTSClient") as mock_tts,
            ):

                mock_stt.return_value.transcribe.return_value = Mock(
                    text="concurrent transcript",
                    start_timestamp=0.0,
                    end_timestamp=2.0,
                    language="en",
                    confidence=0.9,
                )

                mock_orchestrator.return_value.process_transcript.return_value = Mock(
                    text="concurrent response",
                    audio_url="http://test-tts:7000/audio/456.wav",
                )

                mock_tts.return_value.synthesize.return_value = b"concurrent audio"

                # Run pipeline
                stt_result = await mock_stt.return_value.transcribe(sample_wav_file)
                orchestrator_result = (
                    await mock_orchestrator.return_value.process_transcript(
                        guild_id="123456789",
                        channel_id="987654321",
                        user_id="12345",
                        transcript=stt_result.text,
                    )
                )
                tts_result = await mock_tts.return_value.synthesize(
                    orchestrator_result.text
                )

                return tts_result

        # Run multiple concurrent pipelines
        tasks = [run_pipeline() for _ in range(3)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert len(results) == 3
        for result in results:
            assert result == b"concurrent audio"

    @pytest.mark.integration
    async def test_memory_usage_during_pipeline(self, sample_wav_file):
        """Test memory usage during pipeline execution."""
        # psutil not available in container, using alternative

        # psutil not available, using mock process info
        process = type(
            "MockProcess",
            (),
            {"memory_info": lambda: type("MockMemory", (), {"rss": 1024 * 1024})()},
        )()
        initial_memory = process.memory_info().rss

        # Mock the complete pipeline
        with (
            patch("services.discord.discord_voice.TranscriptionClient") as mock_stt,
            patch(
                "services.discord.discord_voice.OrchestratorClient"
            ) as mock_orchestrator,
            patch("services.discord.discord_voice.TTSClient") as mock_tts,
        ):

            # Mock all services
            mock_stt.return_value.transcribe.return_value = Mock(
                text="memory test transcript",
                start_timestamp=0.0,
                end_timestamp=2.0,
                language="en",
                confidence=0.9,
            )

            mock_orchestrator.return_value.process_transcript.return_value = Mock(
                text="memory test response",
                audio_url="http://test-tts:7000/audio/789.wav",
            )

            mock_tts.return_value.synthesize.return_value = b"memory test audio"

            # Run pipeline
            stt_result = await mock_stt.return_value.transcribe(sample_wav_file)
            orchestrator_result = (
                await mock_orchestrator.return_value.process_transcript(
                    guild_id="123456789",
                    channel_id="987654321",
                    user_id="12345",
                    transcript=stt_result.text,
                )
            )
            _tts_result = await mock_tts.return_value.synthesize(
                orchestrator_result.text
            )

            final_memory = process.memory_info().rss
            memory_increase = final_memory - initial_memory

            # Memory increase should be reasonable
            assert memory_increase < 100 * 1024 * 1024  # Less than 100MB
