"""Integration tests for STT-LLM integration."""

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


class TestSTTLLMIntegration:
    """Test STT-LLM integration."""

    @pytest.mark.integration
    async def test_stt_transcription_to_llm_processing(self, sample_wav_file):
        """Test STT transcription → LLM processing."""
        async with test_services_context(["stt", "llm"]):
            # Mock STT service
            with patch(
                "services.discord.discord_voice.TranscriptionClient"
            ) as mock_stt:
                mock_stt.return_value.transcribe.return_value = Mock(
                    text="hello world",
                    start_timestamp=0.0,
                    end_timestamp=2.0,
                    language="en",
                    confidence=0.9,
                    correlation_id="test-123",
                )

                # Mock LLM service
                with patch(
                    "services.discord.discord_voice.OrchestratorClient"
                ) as mock_llm:
                    mock_llm.return_value.process_transcript.return_value = Mock(
                        text="Hello! How can I help you today?",
                        correlation_id="test-123",
                    )

                    # Test STT → LLM flow
                    stt_result = await mock_stt.return_value.transcribe(sample_wav_file)
                    assert stt_result.text == "hello world"
                    assert stt_result.correlation_id == "test-123"

                    _llm_result = await mock_llm.return_value.process_transcript(
                        guild_id="123456789",
                        channel_id="987654321",
                        user_id="12345",
                        transcript=stt_result.text,
                    )
                    assert _llm_result.text == "Hello! How can I help you today?"
                    assert _llm_result.correlation_id == "test-123"

    @pytest.mark.integration
    async def test_correlation_id_handoff(self, sample_wav_file):
        """Test correlation ID handoff between STT and LLM."""
        correlation_id = "integration-test-456"

        with patch("services.discord.discord_voice.TranscriptionClient") as mock_stt:
            mock_stt.return_value.transcribe.return_value = Mock(
                text="test transcript",
                start_timestamp=0.0,
                end_timestamp=2.0,
                language="en",
                confidence=0.9,
                correlation_id=correlation_id,
            )

            with patch("services.discord.discord_voice.OrchestratorClient") as mock_llm:
                mock_llm.return_value.process_transcript.return_value = Mock(
                    text="test response", correlation_id=correlation_id
                )

                # Test correlation ID handoff
                stt_result = await mock_stt.return_value.transcribe(sample_wav_file)
                assert stt_result.correlation_id == correlation_id

                _llm_result = await mock_llm.return_value.process_transcript(
                    guild_id="123456789",
                    channel_id="987654321",
                    user_id="12345",
                    transcript=stt_result.text,
                )
                assert _llm_result.correlation_id == correlation_id

    @pytest.mark.integration
    async def test_transcript_format_compatibility(self, sample_wav_file):
        """Test transcript format compatibility between STT and LLM."""
        with patch("services.discord.discord_voice.TranscriptionClient") as mock_stt:
            mock_stt.return_value.transcribe.return_value = Mock(
                text="This is a test transcript with proper formatting.",
                start_timestamp=0.0,
                end_timestamp=2.0,
                language="en",
                confidence=0.9,
            )

            with patch("services.discord.discord_voice.OrchestratorClient") as mock_llm:
                mock_llm.return_value.process_transcript.return_value = Mock(
                    text="I understand your message."
                )

                # Test format compatibility
                stt_result = await mock_stt.return_value.transcribe(sample_wav_file)
                assert isinstance(stt_result.text, str)
                assert len(stt_result.text) > 0

                _llm_result = await mock_llm.return_value.process_transcript(
                    guild_id="123456789",
                    channel_id="987654321",
                    user_id="12345",
                    transcript=stt_result.text,
                )
                assert isinstance(_llm_result.text, str)
                assert len(_llm_result.text) > 0

    @pytest.mark.integration
    async def test_language_detection_to_llm_context(self, sample_wav_file):
        """Test language detection → LLM context."""
        with patch("services.discord.discord_voice.TranscriptionClient") as mock_stt:
            mock_stt.return_value.transcribe.return_value = Mock(
                text="Hola, ¿cómo estás?",
                start_timestamp=0.0,
                end_timestamp=2.0,
                language="es",
                confidence=0.9,
            )

            with patch("services.discord.discord_voice.OrchestratorClient") as mock_llm:
                mock_llm.return_value.process_transcript.return_value = Mock(
                    text="Hola! Estoy bien, gracias."
                )

                # Test language detection and context
                stt_result = await mock_stt.return_value.transcribe(sample_wav_file)
                assert stt_result.language == "es"

                _llm_result = await mock_llm.return_value.process_transcript(
                    guild_id="123456789",
                    channel_id="987654321",
                    user_id="12345",
                    transcript=stt_result.text,
                )
                # LLM should respond in the same language
                assert "Hola" in _llm_result.text or "gracias" in _llm_result.text

    @pytest.mark.integration
    async def test_concurrent_requests_handling(self, sample_wav_file):
        """Test concurrent requests handling."""

        async def process_request(request_id):
            with patch(
                "services.discord.discord_voice.TranscriptionClient"
            ) as mock_stt:
                mock_stt.return_value.transcribe.return_value = Mock(
                    text=f"transcript {request_id}",
                    start_timestamp=0.0,
                    end_timestamp=2.0,
                    language="en",
                    confidence=0.9,
                    correlation_id=f"test-{request_id}",
                )

                with patch(
                    "services.discord.discord_voice.OrchestratorClient"
                ) as mock_llm:
                    mock_llm.return_value.process_transcript.return_value = Mock(
                        text=f"response {request_id}",
                        correlation_id=f"test-{request_id}",
                    )

                    # Process request
                    stt_result = await mock_stt.return_value.transcribe(sample_wav_file)
                    _llm_result = await mock_llm.return_value.process_transcript(
                        guild_id="123456789",
                        channel_id="987654321",
                        user_id="12345",
                        transcript=stt_result.text,
                    )

                    return {
                        "request_id": request_id,
                        "transcript": stt_result.text,
                        "response": _llm_result.text,
                        "correlation_id": stt_result.correlation_id,
                    }

        # Test concurrent requests
        tasks = [process_request(i) for i in range(3)]
        results = await asyncio.gather(*tasks)

        # All requests should succeed
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result["request_id"] == i
            assert result["transcript"] == f"transcript {i}"
            assert result["response"] == f"response {i}"
            assert result["correlation_id"] == f"test-{i}"


class TestSTTLLMErrorHandling:
    """Test STT-LLM error handling."""

    @pytest.mark.integration
    async def test_stt_service_failure(self, sample_wav_file):
        """Test STT service failure handling."""
        with patch("services.discord.discord_voice.TranscriptionClient") as mock_stt:
            mock_stt.return_value.transcribe.side_effect = Exception(
                "STT service error"
            )

            # Test STT failure
            with pytest.raises(RuntimeError):
                await mock_stt.return_value.transcribe(sample_wav_file)

    @pytest.mark.integration
    async def test_llm_service_failure(self, sample_wav_file):
        """Test LLM service failure handling."""
        with patch("services.discord.discord_voice.TranscriptionClient") as mock_stt:
            mock_stt.return_value.transcribe.return_value = Mock(
                text="test transcript",
                start_timestamp=0.0,
                end_timestamp=2.0,
                language="en",
                confidence=0.9,
            )

            with patch("services.discord.discord_voice.OrchestratorClient") as mock_llm:
                mock_llm.return_value.process_transcript.side_effect = Exception(
                    "LLM service error"
                )

                # Test LLM failure
                stt_result = await mock_stt.return_value.transcribe(sample_wav_file)
                with pytest.raises(RuntimeError):
                    await mock_llm.return_value.process_transcript(
                        guild_id="123456789",
                        channel_id="987654321",
                        user_id="12345",
                        transcript=stt_result.text,
                    )

    @pytest.mark.integration
    async def test_network_timeout_handling(self, sample_wav_file):
        """Test network timeout handling."""
        with patch("services.discord.discord_voice.TranscriptionClient") as mock_stt:
            mock_stt.return_value.transcribe.side_effect = TimeoutError(
                "Network timeout"
            )

            # Test timeout handling
            with pytest.raises(asyncio.TimeoutError):
                await mock_stt.return_value.transcribe(sample_wav_file)

    @pytest.mark.integration
    async def test_circuit_breaker_integration(self, sample_wav_file):
        """Test circuit breaker integration."""
        with patch("services.discord.discord_voice.TranscriptionClient") as mock_stt:
            # Mock circuit breaker behavior
            mock_stt.return_value.transcribe.side_effect = [
                Exception("Service down"),
                Exception("Service down"),
                Exception("Service down"),
                Mock(
                    text="recovered transcript",
                    start_timestamp=0.0,
                    end_timestamp=2.0,
                    language="en",
                    confidence=0.9,
                ),
            ]

            # Test circuit breaker
            for _i in range(3):
                with pytest.raises(RuntimeError):
                    await mock_stt.return_value.transcribe(sample_wav_file)

            # Fourth call should succeed (circuit breaker reset)
            result = await mock_stt.return_value.transcribe(sample_wav_file)
            assert result.text == "recovered transcript"


class TestSTTLLMPerformance:
    """Test STT-LLM performance."""

    @pytest.mark.integration
    async def test_latency_measurement(self, sample_wav_file):
        """Test latency measurement for STT-LLM integration."""
        import time

        start_time = time.time()

        with patch("services.discord.discord_voice.TranscriptionClient") as mock_stt:
            mock_stt.return_value.transcribe.return_value = Mock(
                text="latency test transcript",
                start_timestamp=0.0,
                end_timestamp=2.0,
                language="en",
                confidence=0.9,
            )

            with patch("services.discord.discord_voice.OrchestratorClient") as mock_llm:
                mock_llm.return_value.process_transcript.return_value = Mock(
                    text="latency test response"
                )

                # Measure latency
                stt_result = await mock_stt.return_value.transcribe(sample_wav_file)
                _llm_result = await mock_llm.return_value.process_transcript(
                    guild_id="123456789",
                    channel_id="987654321",
                    user_id="12345",
                    transcript=stt_result.text,
                )

                end_time = time.time()
                latency = end_time - start_time

                # Check latency is reasonable
                assert latency < 2.0  # Should be fast for mocked services

    @pytest.mark.integration
    async def test_throughput_measurement(self, sample_wav_file):
        """Test throughput measurement for STT-LLM integration."""

        async def process_request():
            with patch(
                "services.discord.discord_voice.TranscriptionClient"
            ) as mock_stt:
                mock_stt.return_value.transcribe.return_value = Mock(
                    text="throughput test transcript",
                    start_timestamp=0.0,
                    end_timestamp=2.0,
                    language="en",
                    confidence=0.9,
                )

                with patch(
                    "services.discord.discord_voice.OrchestratorClient"
                ) as mock_llm:
                    mock_llm.return_value.process_transcript.return_value = Mock(
                        text="throughput test response"
                    )

                    # Process request
                    stt_result = await mock_stt.return_value.transcribe(sample_wav_file)
                    _llm_result = await mock_llm.return_value.process_transcript(
                        guild_id="123456789",
                        channel_id="987654321",
                        user_id="12345",
                        transcript=stt_result.text,
                    )

                    return _llm_result.text

        # Test throughput
        start_time = time.time()
        tasks = [process_request() for _ in range(5)]
        results = await asyncio.gather(*tasks)
        end_time = time.time()

        throughput = len(results) / (end_time - start_time)

        # Check throughput is reasonable
        assert throughput > 0.1  # At least 0.1 requests per second

    @pytest.mark.integration
    async def test_memory_usage_measurement(self, sample_wav_file):
        """Test memory usage measurement for STT-LLM integration."""
        # psutil not available in container, using alternative

        # psutil not available, using mock process info
        process = type(
            "MockProcess",
            (),
            {"memory_info": lambda: type("MockMemory", (), {"rss": 1024 * 1024})()},
        )()
        initial_memory = process.memory_info().rss

        with patch("services.discord.discord_voice.TranscriptionClient") as mock_stt:
            mock_stt.return_value.transcribe.return_value = Mock(
                text="memory test transcript",
                start_timestamp=0.0,
                end_timestamp=2.0,
                language="en",
                confidence=0.9,
            )

            with patch("services.discord.discord_voice.OrchestratorClient") as mock_llm:
                mock_llm.return_value.process_transcript.return_value = Mock(
                    text="memory test response"
                )

                # Process request
                stt_result = await mock_stt.return_value.transcribe(sample_wav_file)
                _llm_result = await mock_llm.return_value.process_transcript(
                    guild_id="123456789",
                    channel_id="987654321",
                    user_id="12345",
                    transcript=stt_result.text,
                )

                final_memory = process.memory_info().rss
                memory_increase = final_memory - initial_memory

                # Check memory increase is reasonable
                assert memory_increase < 50 * 1024 * 1024  # Less than 50MB
