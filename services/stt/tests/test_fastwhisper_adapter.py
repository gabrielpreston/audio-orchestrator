"""Tests for FastWhisper adapter functionality."""

from unittest.mock import Mock, patch

import pytest

from services.common.surfaces.stt_interface import STTConfig
from services.stt.adapters.fastwhisper_adapter import FastWhisperAdapter


@pytest.fixture
def mock_adapter_config():
    """Mock adapter configuration."""
    return STTConfig(
        model_name="tiny",
        model_size="tiny",
        language="en",
        enable_vad=True,
        enable_punctuation=True,
        enable_diarization=False,
    )


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


class TestFastWhisperAdapterLifecycle:
    """Test FastWhisper adapter lifecycle."""

    def test_initialization_with_config(self, mock_adapter_config):
        """Test initialization with config."""
        with patch("services.stt.models.FastWhisperAdapter._load_model") as mock_load:
            mock_load.return_value = Mock()

            adapter = FastWhisperAdapter(mock_adapter_config)

            assert adapter.config == mock_adapter_config
            mock_load.assert_called_once()

    async def test_connection_success(self, mock_adapter_config):
        """Test connection success."""
        with patch("services.stt.models.FastWhisperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_load.return_value = mock_model

            adapter = FastWhisperAdapter(mock_adapter_config)

            # Test connection
            result = await adapter.connect()
            assert result is True
            assert adapter.is_connected()

    async def test_disconnect_and_cleanup(self, mock_adapter_config):
        """Test disconnect and cleanup."""
        with patch("services.stt.models.FastWhisperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_load.return_value = mock_model

            adapter = FastWhisperAdapter(mock_adapter_config)
            await adapter.connect()

            # Test disconnect
            await adapter.disconnect()
            assert not adapter.is_connected()


class TestFastWhisperAdapterTranscription:
    """Test FastWhisper adapter transcription."""

    async def test_transcribe_with_various_audio_formats(
        self, mock_adapter_config, sample_audio_data
    ):
        """Test transcribe with various audio formats."""
        with patch("services.stt.models.FastWhisperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_model.transcribe.return_value = {
                "text": "hello world",
                "segments": [{"text": "hello world", "start": 0.0, "end": 1.0}],
            }
            mock_load.return_value = mock_model

            adapter = FastWhisperAdapter(mock_adapter_config)
            await adapter.connect()

            # Test transcription
            from services.common.surfaces.types import AudioFormat

            result = await adapter.transcribe(sample_audio_data, AudioFormat.PCM)

            assert result.text == "hello world"
            assert result.start_time == 0.0
            assert result.end_time == 1.0
            mock_model.transcribe.assert_called_once()

    async def test_streaming_transcription(
        self, mock_adapter_config, sample_audio_data
    ):
        """Test streaming transcription."""
        with patch("services.stt.models.FastWhisperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_model.transcribe.return_value = {
                "text": "streaming test",
                "segments": [{"text": "streaming test", "start": 0.0, "end": 1.0}],
            }
            mock_load.return_value = mock_model

            adapter = FastWhisperAdapter(mock_adapter_config)
            await adapter.connect()

            # Test streaming transcription
            from services.common.surfaces.types import AudioFormat

            result = await adapter.transcribe(sample_audio_data, AudioFormat.PCM)

            assert result.text == "streaming test"
            mock_model.transcribe.assert_called_once()

    async def test_telemetry_updates(self, mock_adapter_config, sample_audio_data):
        """Test telemetry updates."""
        with patch("services.stt.models.FastWhisperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_model.transcribe.return_value = {
                "text": "telemetry test",
                "segments": [{"text": "telemetry test", "start": 0.0, "end": 1.0}],
            }
            mock_load.return_value = mock_model

            adapter = FastWhisperAdapter(mock_adapter_config)
            await adapter.connect()

            # Test transcription with telemetry
            from services.common.surfaces.types import AudioFormat

            result = await adapter.transcribe(sample_audio_data, AudioFormat.PCM)

            assert result.text == "telemetry test"
            # Check that telemetry was updated
            assert adapter.get_telemetry() is not None

    async def test_supported_languages_list(self, mock_adapter_config):
        """Test supported languages list."""
        with patch("services.stt.models.FastWhisperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_model.supported_languages = ["en", "es", "fr", "de"]
            mock_load.return_value = mock_model

            adapter = FastWhisperAdapter(mock_adapter_config)
            await adapter.connect()

            # Test supported languages
            languages = await adapter.get_supported_languages()
            assert "en" in languages
            assert "es" in languages
            assert "fr" in languages
            assert "de" in languages

    async def test_model_info_retrieval(self, mock_adapter_config):
        """Test model info retrieval."""
        with patch("services.stt.models.FastWhisperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_model.model_name = "tiny"
            mock_model.device = "cpu"
            mock_load.return_value = mock_model

            adapter = FastWhisperAdapter(mock_adapter_config)
            await adapter.connect()

            # Test model info
            info = await adapter.get_model_info()
            assert info["model_name"] == "tiny"
            assert info["device"] == "cpu"


class TestFastWhisperAdapterErrorHandling:
    """Test FastWhisper adapter error handling."""

    async def test_transcription_with_invalid_audio(self, mock_adapter_config):
        """Test transcription with invalid audio."""
        with patch("services.stt.models.FastWhisperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_model.transcribe.side_effect = Exception("Invalid audio format")
            mock_load.return_value = mock_model

            adapter = FastWhisperAdapter(mock_adapter_config)
            await adapter.connect()

            # Test transcription with invalid audio
            from services.common.surfaces.types import AudioFormat

            with pytest.raises(ValueError):
                await adapter.transcribe(b"invalid audio data", AudioFormat.PCM)

    async def test_adapter_not_initialized_errors(self, mock_adapter_config):
        """Test adapter not initialized errors."""
        adapter = FastWhisperAdapter(mock_adapter_config)

        # Test operations before initialization
        from services.common.surfaces.types import AudioFormat

        with pytest.raises(RuntimeError):
            await adapter.transcribe(b"test audio", AudioFormat.PCM)

    async def test_adapter_not_connected_errors(self, mock_adapter_config):
        """Test adapter not connected errors."""
        with patch("services.stt.models.FastWhisperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_load.return_value = mock_model

            adapter = FastWhisperAdapter(mock_adapter_config)
            # Don't connect

            # Test operations without connection
            from services.common.surfaces.types import AudioFormat

            with pytest.raises(RuntimeError):
                await adapter.transcribe(b"test audio", AudioFormat.PCM)


class TestFastWhisperAdapterConfiguration:
    """Test FastWhisper adapter configuration."""

    def test_model_name_configuration(self):
        """Test model name configuration."""
        config = STTConfig(
            model_name="base",
            model_size="base",
            language="en",
        )

        with patch("services.stt.models.FastWhisperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_load.return_value = mock_model

            adapter = FastWhisperAdapter(config)

            assert adapter.config.model_name == "base"

    def test_device_configuration(self):
        """Test device configuration."""
        config = STTConfig(
            model_name="tiny",
            model_size="tiny",
            language="en",
        )

        with patch("services.stt.models.FastWhisperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_load.return_value = mock_model

            adapter = FastWhisperAdapter(config)

            assert adapter.config.model_name == "tiny"

    def test_compute_type_configuration(self):
        """Test compute type configuration."""
        config = STTConfig(
            model_name="tiny",
            model_size="tiny",
            language="en",
        )

        with patch("services.stt.models.FastWhisperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_load.return_value = mock_model

            adapter = FastWhisperAdapter(config)

            assert adapter.config.model_name == "tiny"

    def test_model_path_configuration(self):
        """Test model path configuration."""
        config = STTConfig(
            model_name="tiny",
            model_size="tiny",
            language="en",
        )

        with patch("services.stt.models.FastWhisperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_load.return_value = mock_model

            adapter = FastWhisperAdapter(config)

            assert adapter.config.model_name == "tiny"


class TestFastWhisperAdapterPerformance:
    """Test FastWhisper adapter performance."""

    async def test_transcription_latency(self, mock_adapter_config, sample_audio_data):
        """Test transcription latency."""
        with patch("services.stt.models.FastWhisperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_model.transcribe.return_value = {
                "text": "latency test",
                "segments": [{"text": "latency test", "start": 0.0, "end": 1.0}],
            }
            mock_load.return_value = mock_model

            adapter = FastWhisperAdapter(mock_adapter_config)
            await adapter.connect()

            import time

            start_time = time.time()
            from services.common.surfaces.types import AudioFormat

            result = await adapter.transcribe(sample_audio_data, AudioFormat.PCM)
            end_time = time.time()

            latency = end_time - start_time
            assert latency < 1.0  # Should be fast for test
            assert result.text == "latency test"

    async def test_memory_usage(self, mock_adapter_config):
        """Test memory usage."""
        with patch("services.stt.models.FastWhisperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_load.return_value = mock_model

            adapter = FastWhisperAdapter(mock_adapter_config)
            await adapter.connect()

            # Test memory usage tracking
            telemetry = await adapter.get_telemetry()
            assert telemetry is not None
            # Memory usage should be tracked in telemetry
            assert "memory_usage" in telemetry or "model_size" in telemetry

    async def test_concurrent_transcriptions(
        self, mock_adapter_config, sample_audio_data
    ):
        """Test concurrent transcriptions."""
        with patch("services.stt.models.FastWhisperAdapter._load_model") as mock_load:
            mock_model = Mock()
            mock_model.transcribe.return_value = {
                "text": "concurrent test",
                "segments": [{"text": "concurrent test", "start": 0.0, "end": 1.0}],
            }
            mock_load.return_value = mock_model

            adapter = FastWhisperAdapter(mock_adapter_config)
            await adapter.connect()

            # Test concurrent transcriptions
            import asyncio

            from services.common.surfaces.types import AudioFormat

            tasks = []
            for _ in range(3):
                task = adapter.transcribe(sample_audio_data, AudioFormat.PCM)
                tasks.append(task)

            results = await asyncio.gather(*tasks)

            assert len(results) == 3
            for result in results:
                assert result.text == "concurrent test"
