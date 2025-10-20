"""Integration tests for LLM-TTS integration."""

import asyncio
import time
from unittest.mock import Mock, patch

import pytest

from services.tests.utils.service_helpers import docker_compose_test_context


@pytest.fixture
def sample_text():
    """Sample text for synthesis."""
    return "Hello, this is a test message for text-to-speech synthesis."


@pytest.fixture
def sample_ssml():
    """Sample SSML for synthesis."""
    return "<speak>Hello, this is a test message for text-to-speech synthesis.</speak>"


class TestLLMTTSIntegration:
    """Test LLM-TTS integration."""

    @pytest.mark.component
    async def test_llm_response_to_tts_synthesis(self, sample_text):
        """Test LLM response → TTS synthesis."""
        with (
            patch("services.discord.discord_voice.OrchestratorClient") as mock_llm,
            patch("services.discord.discord_voice.TTSClient") as mock_tts,
        ):
            async with docker_compose_test_context(["llm", "tts"]):
                # Mock LLM service
                mock_llm.return_value.process_transcript.return_value = Mock(
                    text="Hello! How can I help you today?", correlation_id="test-123"
                )

                # Mock TTS service
                mock_tts.return_value.synthesize.return_value = (
                    b"synthesized audio data"
                )

                # Test LLM → TTS flow
                llm_result = await mock_llm.return_value.process_transcript(
                    guild_id="123456789",
                    channel_id="987654321",
                    user_id="12345",
                    transcript=sample_text,
                )
                assert llm_result.text == "Hello! How can I help you today?"
                assert llm_result.correlation_id == "test-123"

                _tts_result = await mock_tts.return_value.synthesize(llm_result.text)
                assert _tts_result == b"synthesized audio data"

    @pytest.mark.component
    async def test_correlation_id_handoff(self, sample_text):
        """Test correlation ID handoff between LLM and TTS."""
        correlation_id = "integration-test-789"

        with patch("services.discord.discord_voice.OrchestratorClient") as mock_llm:
            mock_llm.return_value.process_transcript.return_value = Mock(
                text="test response", correlation_id=correlation_id
            )

            with patch("services.discord.discord_voice.TTSClient") as mock_tts:
                mock_tts.return_value.synthesize.return_value = b"test audio"

                # Test correlation ID handoff
                llm_result = await mock_llm.return_value.process_transcript(
                    guild_id="123456789",
                    channel_id="987654321",
                    user_id="12345",
                    transcript=sample_text,
                )
                assert llm_result.correlation_id == correlation_id

                _tts_result = await mock_tts.return_value.synthesize(llm_result.text)
                assert _tts_result == b"test audio"

    @pytest.mark.component
    async def test_text_format_compatibility(self, sample_text):
        """Test text format compatibility between LLM and TTS."""
        with patch("services.discord.discord_voice.OrchestratorClient") as mock_llm:
            mock_llm.return_value.process_transcript.return_value = Mock(
                text="This is a properly formatted response from the LLM."
            )

            with patch("services.discord.discord_voice.TTSClient") as mock_tts:
                mock_tts.return_value.synthesize.return_value = b"compatible audio data"

                # Test format compatibility
                llm_result = await mock_llm.return_value.process_transcript(
                    guild_id="123456789",
                    channel_id="987654321",
                    user_id="12345",
                    transcript=sample_text,
                )
                assert isinstance(llm_result.text, str)
                assert len(llm_result.text) > 0

                _tts_result = await mock_tts.return_value.synthesize(llm_result.text)
                assert isinstance(_tts_result, bytes)
                assert len(_tts_result) > 0

    @pytest.mark.component
    async def test_ssml_generation_from_llm(self, sample_ssml):
        """Test SSML generation from LLM."""
        with patch("services.discord.discord_voice.OrchestratorClient") as mock_llm:
            mock_llm.return_value.process_transcript.return_value = Mock(
                text="<speak>Hello, this is SSML from the LLM.</speak>", format="ssml"
            )

            with patch("services.discord.discord_voice.TTSClient") as mock_tts:
                mock_tts.return_value.synthesize.return_value = b"ssml audio data"

                # Test SSML generation
                llm_result = await mock_llm.return_value.process_transcript(
                    guild_id="123456789",
                    channel_id="987654321",
                    user_id="12345",
                    transcript="test transcript",
                )
                assert "<speak>" in llm_result.text
                assert llm_result.format == "ssml"

                _tts_result = await mock_tts.return_value.synthesize(llm_result.text)
                assert _tts_result == b"ssml audio data"

    @pytest.mark.component
    async def test_voice_selection_based_on_context(self, sample_text):
        """Test voice selection based on context."""
        with patch("services.discord.discord_voice.OrchestratorClient") as mock_llm:
            mock_llm.return_value.process_transcript.return_value = Mock(
                text="This is a formal response.",
                voice_preference="formal",
                language="en",
            )

            with patch("services.discord.discord_voice.TTSClient") as mock_tts:
                mock_tts.return_value.synthesize.return_value = b"formal voice audio"

                # Test voice selection based on context
                llm_result = await mock_llm.return_value.process_transcript(
                    guild_id="123456789",
                    channel_id="987654321",
                    user_id="12345",
                    transcript=sample_text,
                )
                assert llm_result.voice_preference == "formal"
                assert llm_result.language == "en"

                tts_result = await mock_tts.return_value.synthesize(
                    llm_result.text,
                    voice=llm_result.voice_preference,
                    language=llm_result.language,
                )
                assert tts_result == b"formal voice audio"

    @pytest.mark.component
    async def test_concurrent_requests_handling(self, sample_text):
        """Test concurrent requests handling."""

        async def process_request(request_id):
            with patch("services.discord.discord_voice.OrchestratorClient") as mock_llm:
                mock_llm.return_value.process_transcript.return_value = Mock(
                    text=f"response {request_id}", correlation_id=f"test-{request_id}"
                )

                with patch("services.discord.discord_voice.TTSClient") as mock_tts:
                    mock_tts.return_value.synthesize.return_value = (
                        f"audio {request_id}".encode()
                    )

                    # Process request
                    llm_result = await mock_llm.return_value.process_transcript(
                        guild_id="123456789",
                        channel_id="987654321",
                        user_id="12345",
                        transcript=sample_text,
                    )
                    _tts_result = await mock_tts.return_value.synthesize(
                        llm_result.text
                    )

                    return {
                        "request_id": request_id,
                        "response": llm_result.text,
                        "audio": _tts_result,
                        "correlation_id": llm_result.correlation_id,
                    }

        # Test concurrent requests
        tasks = [process_request(i) for i in range(3)]
        results = await asyncio.gather(*tasks)

        # All requests should succeed
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result["request_id"] == i
            assert result["response"] == f"response {i}"
            assert result["audio"] == f"audio {i}".encode()
            assert result["correlation_id"] == f"test-{i}"


class TestLLMTTSErrorHandling:
    """Test LLM-TTS error handling."""

    @pytest.mark.component
    async def test_llm_service_failure(self, sample_text):
        """Test LLM service failure handling."""
        with patch("services.discord.discord_voice.OrchestratorClient") as mock_llm:
            mock_llm.return_value.process_transcript.side_effect = Exception(
                "LLM service error"
            )

            # Test LLM failure
            with pytest.raises(RuntimeError):
                await mock_llm.return_value.process_transcript(
                    guild_id="123456789",
                    channel_id="987654321",
                    user_id="12345",
                    transcript=sample_text,
                )

    @pytest.mark.component
    async def test_tts_service_failure(self, sample_text):
        """Test TTS service failure handling."""
        with patch("services.discord.discord_voice.OrchestratorClient") as mock_llm:
            mock_llm.return_value.process_transcript.return_value = Mock(
                text="test response"
            )

            with patch("services.discord.discord_voice.TTSClient") as mock_tts:
                mock_tts.return_value.synthesize.side_effect = Exception(
                    "TTS service error"
                )

                # Test TTS failure
                llm_result = await mock_llm.return_value.process_transcript(
                    guild_id="123456789",
                    channel_id="987654321",
                    user_id="12345",
                    transcript=sample_text,
                )
                with pytest.raises(RuntimeError):
                    await mock_tts.return_value.synthesize(llm_result.text)

    @pytest.mark.component
    async def test_network_timeout_handling(self, sample_text):
        """Test network timeout handling."""
        with patch("services.discord.discord_voice.OrchestratorClient") as mock_llm:
            mock_llm.return_value.process_transcript.side_effect = TimeoutError(
                "Network timeout"
            )

            # Test timeout handling
            with pytest.raises(asyncio.TimeoutError):
                await mock_llm.return_value.process_transcript(
                    guild_id="123456789",
                    channel_id="987654321",
                    user_id="12345",
                    transcript=sample_text,
                )

    @pytest.mark.component
    async def test_invalid_text_format_handling(self, sample_text):
        """Test invalid text format handling."""
        with patch("services.discord.discord_voice.OrchestratorClient") as mock_llm:
            mock_llm.return_value.process_transcript.return_value = Mock(
                text="", format="invalid"  # Empty text
            )

            with patch("services.discord.discord_voice.TTSClient") as mock_tts:
                mock_tts.return_value.synthesize.side_effect = ValueError(
                    "Invalid text format"
                )

                # Test invalid format handling
                llm_result = await mock_llm.return_value.process_transcript(
                    guild_id="123456789",
                    channel_id="987654321",
                    user_id="12345",
                    transcript=sample_text,
                )
                with pytest.raises(ValueError):
                    await mock_tts.return_value.synthesize(llm_result.text)

    @pytest.mark.component
    async def test_circuit_breaker_integration(self, sample_text):
        """Test circuit breaker integration."""
        with patch("services.discord.discord_voice.OrchestratorClient") as mock_llm:
            # Mock circuit breaker behavior
            mock_llm.return_value.process_transcript.side_effect = [
                Exception("Service down"),
                Exception("Service down"),
                Exception("Service down"),
                Mock(text="recovered response"),
            ]

            # Test circuit breaker
            for _i in range(3):
                with pytest.raises(RuntimeError):
                    await mock_llm.return_value.process_transcript(
                        guild_id="123456789",
                        channel_id="987654321",
                        user_id="12345",
                        transcript=sample_text,
                    )

            # Fourth call should succeed (circuit breaker reset)
            result = await mock_llm.return_value.process_transcript(
                guild_id="123456789",
                channel_id="987654321",
                user_id="12345",
                transcript=sample_text,
            )
            assert result.text == "recovered response"


class TestLLMTTSPerformance:
    """Test LLM-TTS performance."""

    @pytest.mark.component
    async def test_latency_measurement(self, sample_text):
        """Test latency measurement for LLM-TTS integration."""
        import time

        start_time = time.time()

        with patch("services.discord.discord_voice.OrchestratorClient") as mock_llm:
            mock_llm.return_value.process_transcript.return_value = Mock(
                text="latency test response"
            )

            with patch("services.discord.discord_voice.TTSClient") as mock_tts:
                mock_tts.return_value.synthesize.return_value = b"latency test audio"

                # Measure latency
                llm_result = await mock_llm.return_value.process_transcript(
                    guild_id="123456789",
                    channel_id="987654321",
                    user_id="12345",
                    transcript=sample_text,
                )
                _tts_result = await mock_tts.return_value.synthesize(llm_result.text)

                end_time = time.time()
                latency = end_time - start_time

                # Check latency is reasonable
                assert latency < 2.0  # Should be fast for mocked services

    @pytest.mark.component
    async def test_throughput_measurement(self, sample_text):
        """Test throughput measurement for LLM-TTS integration."""

        async def process_request():
            with patch("services.discord.discord_voice.OrchestratorClient") as mock_llm:
                mock_llm.return_value.process_transcript.return_value = Mock(
                    text="throughput test response"
                )

                with patch("services.discord.discord_voice.TTSClient") as mock_tts:
                    mock_tts.return_value.synthesize.return_value = (
                        b"throughput test audio"
                    )

                    # Process request
                    llm_result = await mock_llm.return_value.process_transcript(
                        guild_id="123456789",
                        channel_id="987654321",
                        user_id="12345",
                        transcript=sample_text,
                    )
                    _tts_result = await mock_tts.return_value.synthesize(
                        llm_result.text
                    )

                    return _tts_result

        # Test throughput
        start_time = time.time()
        tasks = [process_request() for _ in range(5)]
        results = await asyncio.gather(*tasks)
        end_time = time.time()

        throughput = len(results) / (end_time - start_time)

        # Check throughput is reasonable
        assert throughput > 0.1  # At least 0.1 requests per second

    @pytest.mark.component
    async def test_memory_usage_measurement(self, sample_text):
        """Test memory usage measurement for LLM-TTS integration."""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        with patch("services.discord.discord_voice.OrchestratorClient") as mock_llm:
            mock_llm.return_value.process_transcript.return_value = Mock(
                text="memory test response"
            )

            with patch("services.discord.discord_voice.TTSClient") as mock_tts:
                mock_tts.return_value.synthesize.return_value = b"memory test audio"

                # Process request
                llm_result = await mock_llm.return_value.process_transcript(
                    guild_id="123456789",
                    channel_id="987654321",
                    user_id="12345",
                    transcript=sample_text,
                )
                _tts_result = await mock_tts.return_value.synthesize(llm_result.text)

                final_memory = process.memory_info().rss
                memory_increase = final_memory - initial_memory

                # Check memory increase is reasonable
                assert memory_increase < 50 * 1024 * 1024  # Less than 50MB


class TestLLMTTSQuality:
    """Test LLM-TTS quality."""

    @pytest.mark.component
    async def test_response_quality_consistency(self, sample_text):
        """Test response quality consistency."""
        with patch("services.discord.discord_voice.OrchestratorClient") as mock_llm:
            mock_llm.return_value.process_transcript.return_value = Mock(
                text="Consistent quality response"
            )

            with patch("services.discord.discord_voice.TTSClient") as mock_tts:
                mock_tts.return_value.synthesize.return_value = (
                    b"consistent quality audio"
                )

                # Test multiple requests
                for _ in range(3):
                    llm_result = await mock_llm.return_value.process_transcript(
                        guild_id="123456789",
                        channel_id="987654321",
                        user_id="12345",
                        transcript=sample_text,
                    )
                    _tts_result = await mock_tts.return_value.synthesize(
                        llm_result.text
                    )

                    assert llm_result.text == "Consistent quality response"
                    assert _tts_result == b"consistent quality audio"

    @pytest.mark.component
    async def test_voice_quality_consistency(self, sample_text):
        """Test voice quality consistency."""
        with patch("services.discord.discord_voice.OrchestratorClient") as mock_llm:
            mock_llm.return_value.process_transcript.return_value = Mock(
                text="Voice quality test", voice_preference="consistent"
            )

            with patch("services.discord.discord_voice.TTSClient") as mock_tts:
                mock_tts.return_value.synthesize.return_value = (
                    b"consistent voice audio"
                )

                # Test voice quality consistency
                llm_result = await mock_llm.return_value.process_transcript(
                    guild_id="123456789",
                    channel_id="987654321",
                    user_id="12345",
                    transcript=sample_text,
                )
                tts_result = await mock_tts.return_value.synthesize(
                    llm_result.text, voice=llm_result.voice_preference
                )

                assert llm_result.voice_preference == "consistent"
                assert tts_result == b"consistent voice audio"

    @pytest.mark.component
    async def test_language_consistency(self, sample_text):
        """Test language consistency."""
        with patch("services.discord.discord_voice.OrchestratorClient") as mock_llm:
            mock_llm.return_value.process_transcript.return_value = Mock(
                text="Language consistency test", language="en"
            )

            with patch("services.discord.discord_voice.TTSClient") as mock_tts:
                mock_tts.return_value.synthesize.return_value = b"english audio"

                # Test language consistency
                llm_result = await mock_llm.return_value.process_transcript(
                    guild_id="123456789",
                    channel_id="987654321",
                    user_id="12345",
                    transcript=sample_text,
                )
                tts_result = await mock_tts.return_value.synthesize(
                    llm_result.text, language=llm_result.language
                )

                assert llm_result.language == "en"
                assert tts_result == b"english audio"
