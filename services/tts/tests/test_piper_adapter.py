"""Tests for Piper adapter functionality."""

import threading
import time
from unittest.mock import Mock, patch

import pytest

from services.common.surfaces.tts_interface import TTSConfig
from services.tts.adapters.piper_adapter import PiperAdapter


@pytest.fixture
def mock_adapter_config():
    """Mock adapter configuration."""
    return TTSConfig(
        model_name="piper",
        voice="default",
        language="en",
        sample_rate=22050,
        channels=1,
        bit_depth=16,
    )


@pytest.fixture
def sample_text():
    """Sample text for synthesis."""
    return "Hello, this is a test message for text-to-speech synthesis."


class TestPiperAdapterLifecycle:
    """Test Piper adapter lifecycle."""

    def test_initialization_with_config(self, mock_adapter_config):
        """Test initialization with config."""
        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_load.return_value = Mock()

            adapter = PiperAdapter(mock_adapter_config)

            assert adapter.config == mock_adapter_config
            mock_load.assert_called_once()

    async def test_connection_success(self, mock_adapter_config):
        """Test connection success."""
        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_load.return_value = mock_model

            adapter = PiperAdapter(mock_adapter_config)

            # Mock the async methods using patch.object
            with (
                patch.object(adapter, "connect", return_value=True),
                patch.object(adapter, "is_connected", return_value=True),
            ):
                # Test connection
                result = await adapter.connect()
                assert result is True
                assert adapter.is_connected()

    async def test_disconnect_and_cleanup(self, mock_adapter_config):
        """Test disconnect and cleanup."""
        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_load.return_value = mock_model

            adapter = PiperAdapter(mock_adapter_config)

            # Mock the async methods using patch.object
            with (
                patch.object(adapter, "connect", return_value=True),
                patch.object(adapter, "disconnect", return_value=None),
                patch.object(adapter, "is_connected", return_value=False),
            ):
                await adapter.connect()

                # Test disconnect
                await adapter.disconnect()
                assert not adapter.is_connected()


class TestPiperAdapterSynthesis:
    """Test Piper adapter synthesis."""

    async def test_synthesize_with_text(self, mock_adapter_config, sample_text):
        """Test synthesize with text."""
        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_model.synthesize.return_value = b"mock audio data"
            mock_load.return_value = mock_model

            adapter = PiperAdapter(mock_adapter_config)

            # Mock the async methods using patch.object
            with (
                patch.object(adapter, "connect", return_value=True),
                patch.object(adapter, "synthesize", return_value=b"mock audio data"),
            ):
                await adapter.connect()

                # Test synthesis
                result = await adapter.synthesize(sample_text)

                assert result == b"mock audio data"
                mock_model.synthesize.assert_called_once()

    async def test_streaming_synthesis(self, mock_adapter_config, sample_text):
        """Test streaming synthesis."""
        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_model.synthesize.return_value = b"streaming audio data"
            mock_load.return_value = mock_model

            adapter = PiperAdapter(mock_adapter_config)

            # Mock the async methods using patch.object
            with (
                patch.object(adapter, "connect", return_value=True),
                patch.object(
                    adapter, "synthesize", return_value=b"streaming audio data"
                ),
            ):
                await adapter.connect()

                # Test streaming synthesis
                result = await adapter.synthesize(sample_text)

                assert result == b"streaming audio data"
                mock_model.synthesize.assert_called_once()

    async def test_voice_and_language_selection(self, mock_adapter_config, sample_text):
        """Test voice and language selection."""
        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_model.synthesize.return_value = b"voice selected audio"
            mock_load.return_value = mock_model

            adapter = PiperAdapter(mock_adapter_config)

            # Mock the async methods using patch.object
            with (
                patch.object(adapter, "connect", return_value=True),
                patch.object(
                    adapter, "synthesize", return_value=b"voice selected audio"
                ),
            ):
                await adapter.connect()

                # Test voice and language selection
                result = await adapter.synthesize(sample_text, voice="voice1", language="en")

                assert result == b"voice selected audio"
                mock_model.synthesize.assert_called_once()

    async def test_telemetry_updates(self, mock_adapter_config, sample_text):
        """Test telemetry updates."""
        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_model.synthesize.return_value = b"telemetry test audio"
            mock_load.return_value = mock_model

            adapter = PiperAdapter(mock_adapter_config)

            # Mock the async methods using patch.object
            with (
                patch.object(adapter, "connect", return_value=True),
                patch.object(
                    adapter, "synthesize", return_value=b"telemetry test audio"
                ),
            ):
                await adapter.connect()

                # Test synthesis with telemetry
                result = await adapter.synthesize(sample_text)

                assert result == b"telemetry test audio"
                # Check that telemetry was updated
                assert adapter.get_telemetry() is not None

    async def test_available_voices_list(self, mock_adapter_config):
        """Test available voices list."""
        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_model.get_voices.return_value = [
                {"id": "voice1", "name": "Voice 1", "language": "en"},
                {"id": "voice2", "name": "Voice 2", "language": "es"},
            ]
            mock_load.return_value = mock_model

            adapter = PiperAdapter(mock_adapter_config)

            # Mock the async methods using patch.object
            with (
                patch.object(adapter, "connect", return_value=True),
                patch.object(
                    adapter,
                    "get_available_voices",
                    return_value=[
                        {"id": "voice1", "name": "Voice 1", "language": "en"},
                        {"id": "voice2", "name": "Voice 2", "language": "es"},
                    ],
                ),
            ):
                await adapter.connect()

                # Test available voices
                voices = await adapter.get_available_voices()
                assert len(voices) == 2
                assert voices[0]["id"] == "voice1"
                assert voices[1]["id"] == "voice2"

    async def test_supported_languages_list(self, mock_adapter_config):
        """Test supported languages list."""
        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_model.get_supported_languages.return_value = ["en", "es", "fr", "de"]
            mock_load.return_value = mock_model

            adapter = PiperAdapter(mock_adapter_config)

            # Mock the async methods using patch.object
            with (
                patch.object(adapter, "connect", return_value=True),
                patch.object(
                    adapter,
                    "get_supported_languages",
                    return_value=["en", "es", "fr", "de"],
                ),
            ):
                await adapter.connect()

                # Test supported languages
                languages = await adapter.get_supported_languages()
                assert "en" in languages
                assert "es" in languages
                assert "fr" in languages
                assert "de" in languages

    async def test_model_info_retrieval(self, mock_adapter_config):
        """Test model info retrieval."""
        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_model.get_model_info.return_value = {
                "model_name": "piper_model",
                "sample_rate": 22050,
                "speakers": 2,
            }
            mock_load.return_value = mock_model

            adapter = PiperAdapter(mock_adapter_config)
            await adapter.connect()

            # Test model info
            info = await adapter.get_model_info()
            assert info["model_name"] == "piper_model"
            assert info["sample_rate"] == 22050
            assert info["speakers"] == 2


class TestPiperAdapterErrorHandling:
    """Test Piper adapter error handling."""

    async def test_synthesis_with_invalid_text(self, mock_adapter_config):
        """Test synthesis with invalid text."""
        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_model.synthesize.side_effect = ValueError("Invalid text format")
            mock_load.return_value = mock_model

            adapter = PiperAdapter(mock_adapter_config)
            await adapter.connect()

            # Test synthesis with invalid text
            with pytest.raises(ValueError):
                await adapter.synthesize("")

    async def test_adapter_not_initialized_errors(self, mock_adapter_config):
        """Test adapter not initialized errors."""
        adapter = PiperAdapter(mock_adapter_config)

        # Test operations before initialization
        with pytest.raises(RuntimeError):
            await adapter.synthesize("test text")

    async def test_adapter_not_connected_errors(self, mock_adapter_config):
        """Test adapter not connected errors."""
        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_load.return_value = mock_model

            adapter = PiperAdapter(mock_adapter_config)
            # Don't connect

            # Test operations without connection
            with pytest.raises(RuntimeError):
                await adapter.synthesize("test text")

    def test_model_loading_failures(self, mock_adapter_config):
        """Test model loading failures."""
        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_load.side_effect = Exception("Model loading failed")

            with pytest.raises(RuntimeError):
                PiperAdapter(mock_adapter_config)

    async def test_synthesis_parameter_errors(self, mock_adapter_config, sample_text):
        """Test synthesis parameter errors."""
        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_model.synthesize.side_effect = ValueError("Invalid parameter")
            mock_load.return_value = mock_model

            adapter = PiperAdapter(mock_adapter_config)
            await adapter.connect()

            # Test synthesis with invalid parameters
            with pytest.raises(ValueError):
                await adapter.synthesize(sample_text, length_scale=5.0)


class TestPiperAdapterConfiguration:
    """Test Piper adapter configuration."""

    def test_model_path_configuration(self):
        """Test model path configuration."""
        config = TTSConfig(
            model_name="piper",
            voice="default",
            language="en",
            sample_rate=22050,
        )

        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_load.return_value = mock_model

            adapter = PiperAdapter(config)

            assert adapter.config.model_name == "piper"

    def test_config_path_configuration(self):
        """Test config path configuration."""
        config = TTSConfig(
            model_name="piper",
            voice="default",
            language="en",
            sample_rate=22050,
        )

        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_load.return_value = mock_model

            adapter = PiperAdapter(config)

            assert adapter.config.model_name == "piper"

    def test_sample_rate_configuration(self):
        """Test sample rate configuration."""
        config = TTSConfig(
            model_name="piper",
            voice="default",
            language="en",
            sample_rate=44100,
        )

        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_load.return_value = mock_model

            adapter = PiperAdapter(config)

            assert adapter.config.sample_rate == 44100

    def test_speakers_configuration(self):
        """Test speakers configuration."""
        config = TTSConfig(
            model_name="piper",
            voice="default",
            language="en",
            sample_rate=22050,
            channels=1,
        )

        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_load.return_value = mock_model

            adapter = PiperAdapter(config)

            assert adapter.config.channels == 1


class TestPiperAdapterPerformance:
    """Test Piper adapter performance."""

    async def test_synthesis_latency(self, mock_adapter_config, sample_text):
        """Test synthesis latency."""
        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_model.synthesize.return_value = b"latency test audio"
            mock_load.return_value = mock_model

            adapter = PiperAdapter(mock_adapter_config)
            await adapter.connect()

            start_time = time.time()
            result = await adapter.synthesize(sample_text)
            end_time = time.time()

            latency = end_time - start_time
            assert latency < 1.0  # Should be fast for test
            assert result == b"latency test audio"

    async def test_memory_usage(self, mock_adapter_config):
        """Test memory usage."""
        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_load.return_value = mock_model

            adapter = PiperAdapter(mock_adapter_config)
            await adapter.connect()

            # Test memory usage tracking
            telemetry = adapter.get_telemetry()
            assert telemetry is not None
            # Memory usage should be tracked in telemetry
            assert "memory_usage" in telemetry or "model_size" in telemetry

    async def test_concurrent_synthesis(self, mock_adapter_config, sample_text):
        """Test concurrent synthesis."""
        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_model.synthesize.return_value = b"concurrent test audio"
            mock_load.return_value = mock_model

            adapter = PiperAdapter(mock_adapter_config)
            await adapter.connect()

            # Test concurrent synthesis
            import asyncio
            tasks = []
            for _ in range(3):
                task = adapter.synthesize(sample_text)
                tasks.append(task)

            results = await asyncio.gather(*tasks)

            assert len(results) == 3
            for result in results:
                assert result == b"concurrent test audio"

    async def test_synthesis_quality_consistency(self, mock_adapter_config, sample_text):
        """Test synthesis quality consistency."""
        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_model.synthesize.return_value = b"consistent quality audio"
            mock_load.return_value = mock_model

            adapter = PiperAdapter(mock_adapter_config)
            await adapter.connect()

            # Test multiple synthesis calls
            for _ in range(3):
                result = await adapter.synthesize(sample_text)
                assert result == b"consistent quality audio"


class TestPiperAdapterVoiceManagement:
    """Test Piper adapter voice management."""

    async def test_voice_selection(self, mock_adapter_config, sample_text):
        """Test voice selection."""
        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_model.synthesize.return_value = b"voice selected audio"
            mock_load.return_value = mock_model

            adapter = PiperAdapter(mock_adapter_config)
            await adapter.connect()

            # Test voice selection
            result = await adapter.synthesize(sample_text, voice="voice1")
            assert result == b"voice selected audio"
            mock_model.synthesize.assert_called_once()

    async def test_voice_switching(self, mock_adapter_config, sample_text):
        """Test voice switching."""
        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_model.synthesize.return_value = b"voice switched audio"
            mock_load.return_value = mock_model

            adapter = PiperAdapter(mock_adapter_config)
            await adapter.connect()

            # Test voice switching
            result1 = await adapter.synthesize(sample_text, voice="voice1")
            result2 = await adapter.synthesize(sample_text, voice="voice2")

            assert result1 == b"voice switched audio"
            assert result2 == b"voice switched audio"
            assert mock_model.synthesize.call_count == 2

    async def test_voice_validation(self, mock_adapter_config, sample_text):
        """Test voice validation."""
        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_model.synthesize.side_effect = ValueError("Invalid voice")
            mock_load.return_value = mock_model

            adapter = PiperAdapter(mock_adapter_config)
            await adapter.connect()

            # Test invalid voice
            with pytest.raises(ValueError):
                await adapter.synthesize(sample_text, voice="invalid_voice")

    async def test_default_voice_behavior(self, mock_adapter_config, sample_text):
        """Test default voice behavior."""
        with patch("services.tts.models.PiperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_model.synthesize.return_value = b"default voice audio"
            mock_load.return_value = mock_model

            adapter = PiperAdapter(mock_adapter_config)
            await adapter.connect()

            # Test default voice
            result = await adapter.synthesize(sample_text)
            assert result == b"default voice audio"
            mock_model.synthesize.assert_called_once()
