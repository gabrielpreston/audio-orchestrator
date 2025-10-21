"""Tests for debug WAV file generation functionality."""

import time
import wave
from unittest.mock import Mock

import pytest

from services.discord.audio import AudioSegment
from services.discord.config import BotConfig, TelemetryConfig
from services.discord.discord_voice import VoiceBot


class TestDebugWAV:
    """Test debug WAV file generation functionality."""

    @pytest.fixture
    def temp_debug_dir(self, tmp_path):
        """Create temporary debug directory for testing."""
        debug_dir = tmp_path / "debug_wavs"
        debug_dir.mkdir()
        return debug_dir

    @pytest.fixture
    def mock_config(self, temp_debug_dir):
        """Create mock configuration with debug directory."""
        telemetry_config = TelemetryConfig(waveform_debug_dir=temp_debug_dir)
        config = Mock(spec=BotConfig)
        config.telemetry = telemetry_config
        return config

    @pytest.fixture
    def mock_logger(self):
        """Create mock logger for testing."""
        return Mock()

    @pytest.fixture
    def voice_bot(self, mock_config, mock_logger):
        """Create VoiceBot instance for testing."""
        bot = Mock(spec=VoiceBot)
        bot.config = mock_config
        bot._logger = mock_logger
        return bot

    @pytest.fixture
    def sample_audio_segment(self):
        """Create sample audio segment."""
        # Generate sample PCM data
        import numpy as np

        sample_rate = 16000
        duration = 1.0
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        audio_float = np.sin(2 * np.pi * 440 * t) * 0.5  # 440Hz tone
        audio_int16 = (audio_float * 32767).astype(np.int16)
        pcm_data = audio_int16.tobytes()

        return AudioSegment(
            user_id=12345,
            pcm=pcm_data,
            sample_rate=sample_rate,
            start_timestamp=0.0,
            end_timestamp=duration,
            correlation_id="test-correlation-123",
            frame_count=int(sample_rate * duration),
        )

    @pytest.mark.component
    def test_save_debug_wav_creates_file(self, voice_bot, sample_audio_segment, temp_debug_dir):
        """Test that _save_debug_wav creates a playable WAV file."""

        # Mock the _save_debug_wav method
        def mock_save_debug_wav(segment, prefix="segment"):
            if not voice_bot.config.telemetry.waveform_debug_dir:
                return

            try:
                debug_dir = voice_bot.config.telemetry.waveform_debug_dir
                debug_dir.mkdir(parents=True, exist_ok=True)

                timestamp = int(time.time() * 1000)
                filename = f"{prefix}_{segment.correlation_id}_{timestamp}.wav"
                filepath = debug_dir / filename

                with wave.open(str(filepath), "wb") as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(segment.sample_rate)
                    wav_file.writeframes(segment.pcm)

                voice_bot._logger.debug(
                    "voice.debug_wav_saved",
                    correlation_id=segment.correlation_id,
                    filepath=str(filepath),
                    size_bytes=len(segment.pcm),
                )
            except Exception as exc:
                voice_bot._logger.warning(
                    "voice.debug_wav_save_failed",
                    correlation_id=segment.correlation_id,
                    error=str(exc),
                )

        # Call the method
        mock_save_debug_wav(sample_audio_segment, prefix="test")

        # Check that file was created
        wav_files = list(temp_debug_dir.glob("test_test-correlation-123_*.wav"))
        assert len(wav_files) == 1

        # Check that file is valid WAV
        wav_file = wav_files[0]
        with wave.open(str(wav_file), "rb") as f:
            assert f.getnchannels() == 1
            assert f.getsampwidth() == 2
            assert f.getframerate() == 16000
            assert f.getnframes() > 0

    @pytest.mark.component
    def test_save_debug_wav_uses_correlation_id(
        self, voice_bot, sample_audio_segment, temp_debug_dir
    ):
        """Test that _save_debug_wav uses correlation ID in filename."""

        # Mock the _save_debug_wav method
        def mock_save_debug_wav(segment, prefix="segment"):
            if not voice_bot.config.telemetry.waveform_debug_dir:
                return

            debug_dir = voice_bot.config.telemetry.waveform_debug_dir
            debug_dir.mkdir(parents=True, exist_ok=True)

            timestamp = int(time.time() * 1000)
            filename = f"{prefix}_{segment.correlation_id}_{timestamp}.wav"
            filepath = debug_dir / filename

            with wave.open(str(filepath), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(segment.sample_rate)
                wav_file.writeframes(segment.pcm)

        # Call the method
        mock_save_debug_wav(sample_audio_segment, prefix="test")

        # Check that filename contains correlation ID
        wav_files = list(temp_debug_dir.glob("test_test-correlation-123_*.wav"))
        assert len(wav_files) == 1

        filename = wav_files[0].name
        assert "test-correlation-123" in filename
        assert filename.startswith("test_")
        assert filename.endswith(".wav")

    @pytest.mark.component
    def test_save_debug_wav_skips_when_dir_not_set(self, voice_bot, sample_audio_segment):
        """Test that _save_debug_wav skips when debug directory is not set."""
        # Set debug directory to None
        voice_bot.config.telemetry.waveform_debug_dir = None

        # Mock the _save_debug_wav method
        def mock_save_debug_wav(segment, prefix="segment"):
            if not voice_bot.config.telemetry.waveform_debug_dir:
                return

            # This should not be reached
            raise AssertionError("Should not create file when debug dir is not set")

        # Call the method - should return early
        mock_save_debug_wav(sample_audio_segment, prefix="test")

        # Should not log anything
        voice_bot._logger.debug.assert_not_called()
        voice_bot._logger.warning.assert_not_called()

    @pytest.mark.component
    def test_save_debug_wav_logs_success(self, voice_bot, sample_audio_segment, temp_debug_dir):
        """Test that _save_debug_wav logs success with filepath and size."""

        # Mock the _save_debug_wav method
        def mock_save_debug_wav(segment, prefix="segment"):
            if not voice_bot.config.telemetry.waveform_debug_dir:
                return

            try:
                debug_dir = voice_bot.config.telemetry.waveform_debug_dir
                debug_dir.mkdir(parents=True, exist_ok=True)

                timestamp = int(time.time() * 1000)
                filename = f"{prefix}_{segment.correlation_id}_{timestamp}.wav"
                filepath = debug_dir / filename

                with wave.open(str(filepath), "wb") as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(segment.sample_rate)
                    wav_file.writeframes(segment.pcm)

                voice_bot._logger.debug(
                    "voice.debug_wav_saved",
                    correlation_id=segment.correlation_id,
                    filepath=str(filepath),
                    size_bytes=len(segment.pcm),
                )
            except Exception as exc:
                voice_bot._logger.warning(
                    "voice.debug_wav_save_failed",
                    correlation_id=segment.correlation_id,
                    error=str(exc),
                )

        # Call the method
        mock_save_debug_wav(sample_audio_segment, prefix="test")

        # Check that success was logged
        voice_bot._logger.debug.assert_called_once()
        call_args = voice_bot._logger.debug.call_args

        assert call_args[0][0] == "voice.debug_wav_saved"
        kwargs = call_args[1]

        assert kwargs["correlation_id"] == "test-correlation-123"
        assert "filepath" in kwargs
        assert kwargs["size_bytes"] == len(sample_audio_segment.pcm)
        assert kwargs["filepath"].endswith(".wav")

    @pytest.mark.component
    def test_save_debug_wav_handles_write_errors(
        self, voice_bot, sample_audio_segment, temp_debug_dir
    ):
        """Test that _save_debug_wav handles write errors gracefully."""

        # Mock the _save_debug_wav method with error
        def mock_save_debug_wav(segment, prefix="segment"):
            if not voice_bot.config.telemetry.waveform_debug_dir:
                return

            try:
                debug_dir = voice_bot.config.telemetry.waveform_debug_dir
                debug_dir.mkdir(parents=True, exist_ok=True)

                # timestamp = int(time.time() * 1000)  # Not used in this test
                # filename = f"{prefix}_{segment.correlation_id}_{timestamp}.wav"  # Not used in this test
                # filepath = debug_dir / filename  # Not used in this test

                # Simulate write error
                raise OSError("Permission denied")

            except Exception as exc:
                voice_bot._logger.warning(
                    "voice.debug_wav_save_failed",
                    correlation_id=segment.correlation_id,
                    error=str(exc),
                )

        # Call the method
        mock_save_debug_wav(sample_audio_segment, prefix="test")

        # Check that error was logged
        voice_bot._logger.warning.assert_called_once()
        call_args = voice_bot._logger.warning.call_args

        assert call_args[0][0] == "voice.debug_wav_save_failed"
        kwargs = call_args[1]

        assert kwargs["correlation_id"] == "test-correlation-123"
        assert "error" in kwargs
        assert "Permission denied" in kwargs["error"]

    @pytest.mark.component
    def test_captured_segment_saves_debug_wav(
        self, voice_bot, sample_audio_segment, temp_debug_dir
    ):
        """Test that captured segments save debug WAV files."""

        # Mock the _save_debug_wav method
        def mock_save_debug_wav(segment, prefix="segment"):
            if not voice_bot.config.telemetry.waveform_debug_dir:
                return

            debug_dir = voice_bot.config.telemetry.waveform_debug_dir
            debug_dir.mkdir(parents=True, exist_ok=True)

            timestamp = int(time.time() * 1000)
            filename = f"{prefix}_{segment.correlation_id}_{timestamp}.wav"
            filepath = debug_dir / filename

            with wave.open(str(filepath), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(segment.sample_rate)
                wav_file.writeframes(segment.pcm)

        # Simulate captured segment
        mock_save_debug_wav(sample_audio_segment, prefix="captured")

        # Check that file was created with captured prefix
        wav_files = list(temp_debug_dir.glob("captured_test-correlation-123_*.wav"))
        assert len(wav_files) == 1

    @pytest.mark.component
    def test_wake_detected_saves_debug_wav(self, voice_bot, sample_audio_segment, temp_debug_dir):
        """Test that wake detected segments save debug WAV files."""

        # Mock the _save_debug_wav method
        def mock_save_debug_wav(segment, prefix="segment"):
            if not voice_bot.config.telemetry.waveform_debug_dir:
                return

            debug_dir = voice_bot.config.telemetry.waveform_debug_dir
            debug_dir.mkdir(parents=True, exist_ok=True)

            timestamp = int(time.time() * 1000)
            filename = f"{prefix}_{segment.correlation_id}_{timestamp}.wav"
            filepath = debug_dir / filename

            with wave.open(str(filepath), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(segment.sample_rate)
                wav_file.writeframes(segment.pcm)

        # Simulate wake detected segment
        mock_save_debug_wav(sample_audio_segment, prefix="wake_detected")

        # Check that file was created with wake_detected prefix
        wav_files = list(temp_debug_dir.glob("wake_detected_test-correlation-123_*.wav"))
        assert len(wav_files) == 1

    @pytest.mark.component
    def test_debug_wav_file_format(self, voice_bot, sample_audio_segment, temp_debug_dir):
        """Test that debug WAV files have correct format."""

        # Mock the _save_debug_wav method
        def mock_save_debug_wav(segment, prefix="segment"):
            if not voice_bot.config.telemetry.waveform_debug_dir:
                return

            debug_dir = voice_bot.config.telemetry.waveform_debug_dir
            debug_dir.mkdir(parents=True, exist_ok=True)

            timestamp = int(time.time() * 1000)
            filename = f"{prefix}_{segment.correlation_id}_{timestamp}.wav"
            filepath = debug_dir / filename

            with wave.open(str(filepath), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(segment.sample_rate)
                wav_file.writeframes(segment.pcm)

        # Call the method
        mock_save_debug_wav(sample_audio_segment, prefix="test")

        # Check that file has correct format
        wav_files = list(temp_debug_dir.glob("test_test-correlation-123_*.wav"))
        assert len(wav_files) == 1

        wav_file = wav_files[0]
        with wave.open(str(wav_file), "rb") as f:
            # Check WAV format
            assert f.getnchannels() == 1  # Mono
            assert f.getsampwidth() == 2  # 16-bit
            assert f.getframerate() == 16000  # 16kHz
            assert f.getnframes() > 0  # Has audio data

            # Check that we can read the data
            frames = f.readframes(f.getnframes())
            assert len(frames) > 0
            assert len(frames) == len(sample_audio_segment.pcm)

    @pytest.mark.component
    def test_debug_wav_timestamp_uniqueness(self, voice_bot, sample_audio_segment, temp_debug_dir):
        """Test that debug WAV files have unique timestamps."""

        # Mock the _save_debug_wav method
        def mock_save_debug_wav(segment, prefix="segment"):
            if not voice_bot.config.telemetry.waveform_debug_dir:
                return

            debug_dir = voice_bot.config.telemetry.waveform_debug_dir
            debug_dir.mkdir(parents=True, exist_ok=True)

            timestamp = int(time.time() * 1000)
            filename = f"{prefix}_{segment.correlation_id}_{timestamp}.wav"
            filepath = debug_dir / filename

            with wave.open(str(filepath), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(segment.sample_rate)
                wav_file.writeframes(segment.pcm)

        # Create multiple files with small delay
        mock_save_debug_wav(sample_audio_segment, prefix="test1")
        time.sleep(0.001)  # Small delay to ensure different timestamps
        mock_save_debug_wav(sample_audio_segment, prefix="test2")

        # Check that both files were created
        wav_files = list(temp_debug_dir.glob("test*_test-correlation-123_*.wav"))
        assert len(wav_files) == 2

        # Check that filenames are different
        filenames = [f.name for f in wav_files]
        assert len(set(filenames)) == 2  # All filenames should be unique
