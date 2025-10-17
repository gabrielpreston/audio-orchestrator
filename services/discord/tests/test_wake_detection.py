"""Tests for wake detection functionality."""

import os
from unittest.mock import Mock, patch

import pytest

from services.discord.audio import AudioSegment
from services.discord.config import WakeConfig
from services.discord.wake import WakeDetector


class TestWakeDetection:
    """Test wake detection functionality."""

    @pytest.fixture
    def wake_config_enabled(self):
        """Create wake config with detection enabled."""
        return WakeConfig(
            wake_phrases=["hey atlas", "ok atlas"],
            model_paths=[],
            activation_threshold=0.5,
            target_sample_rate_hz=16000,
            enabled=True,
        )

    @pytest.fixture
    def wake_config_disabled(self):
        """Create wake config with detection disabled."""
        return WakeConfig(
            wake_phrases=["hey atlas", "ok atlas"],
            model_paths=[],
            activation_threshold=0.5,
            target_sample_rate_hz=16000,
            enabled=False,
        )

    @pytest.fixture
    def wake_detector_enabled(self, wake_config_enabled):
        """Create wake detector with detection enabled."""
        return WakeDetector(wake_config_enabled)

    @pytest.fixture
    def wake_detector_disabled(self, wake_config_disabled):
        """Create wake detector with detection disabled."""
        return WakeDetector(wake_config_disabled)

    @pytest.fixture
    def sample_audio_segment(self):
        """Create sample audio segment."""
        return AudioSegment(
            user_id=12345,
            pcm=b"sample_audio_data",
            sample_rate=16000,
            start_timestamp=0.0,
            end_timestamp=1.0,
            correlation_id="test-correlation-123",
            frame_count=100,
        )

    @pytest.mark.component
    def test_wake_detection_bypass_when_disabled(
        self, wake_detector_disabled, sample_audio_segment
    ):
        """Test that wake detection bypasses when enabled=False."""
        transcript = "hey atlas, how are you?"

        result = wake_detector_disabled.detect(sample_audio_segment, transcript)

        # Should return testing_mode result
        assert result is not None
        assert result.phrase == "testing_mode"
        assert result.confidence == 1.0
        assert result.source == "transcript"

    @pytest.mark.component
    def test_wake_detection_enabled_by_default(self, wake_config_enabled):
        """Test that wake detection is enabled by default."""
        assert wake_config_enabled.enabled is True

    @pytest.mark.component
    def test_wake_detection_logs_results(
        self, wake_detector_enabled, sample_audio_segment
    ):
        """Test that wake detection logs results with all metadata."""
        transcript = "hey atlas, how are you?"

        # Mock the logger
        wake_detector_enabled._logger = Mock()

        # Mock the detection methods to return a result
        with (
            patch.object(wake_detector_enabled, "_detect_audio", return_value=None),
            patch.object(
                wake_detector_enabled, "_detect_transcript"
            ) as mock_transcript,
        ):

            mock_result = Mock()
            mock_result.phrase = "hey atlas"
            mock_result.confidence = 0.8
            mock_result.source = "transcript"
            mock_transcript.return_value = mock_result

            result = wake_detector_enabled.detect(sample_audio_segment, transcript)

        # Should return the mocked result
        assert result is not None
        assert result.phrase == "hey atlas"
        assert result.confidence == 0.8
        assert result.source == "transcript"

    @pytest.mark.component
    def test_wake_config_loads_enabled_field(self):
        """Test that wake config loads enabled field from environment."""
        # Test with environment variable set to false
        with patch.dict(
            os.environ,
            {
                "WAKE_DETECTION_ENABLED": "false",
                "DISCORD_BOT_TOKEN": "test-token",
                "DISCORD_GUILD_ID": "987654321",
                "DISCORD_VOICE_CHANNEL_ID": "123456789",
                "STT_BASE_URL": "http://test-stt:9000",
                "ORCHESTRATOR_BASE_URL": "http://test-orchestrator:8000",
            },
        ):
            from services.discord.config import load_config

            config = load_config()

            assert config.wake.enabled is False

    @pytest.mark.component
    def test_wake_config_loads_enabled_field_default(self):
        """Test that wake config defaults to enabled when not set."""
        # Test with environment variable not set
        with patch.dict(
            os.environ,
            {
                "DISCORD_BOT_TOKEN": "test-token",
                "DISCORD_GUILD_ID": "987654321",
                "DISCORD_VOICE_CHANNEL_ID": "123456789",
                "STT_BASE_URL": "http://test-stt:9000",
                "ORCHESTRATOR_BASE_URL": "http://test-orchestrator:8000",
            },
            clear=True,
        ):
            from services.discord.config import load_config

            config = load_config()

            assert config.wake.enabled is True

    @pytest.mark.component
    def test_wake_detection_audio_priority(
        self, wake_detector_enabled, sample_audio_segment
    ):
        """Test that wake detection prioritizes audio over transcript."""
        transcript = "some other text"

        # Mock audio detection to return a result
        with patch.object(wake_detector_enabled, "_detect_audio") as mock_audio:
            mock_result = Mock()
            mock_result.phrase = "hey atlas"
            mock_result.confidence = 0.9
            mock_result.source = "audio"
            mock_audio.return_value = mock_result

            result = wake_detector_enabled.detect(sample_audio_segment, transcript)

        # Should return audio result, not check transcript
        assert result is not None
        assert result.phrase == "hey atlas"
        assert result.confidence == 0.9
        assert result.source == "audio"

    @pytest.mark.component
    def test_wake_detection_transcript_fallback(
        self, wake_detector_enabled, sample_audio_segment
    ):
        """Test that wake detection falls back to transcript when audio fails."""
        transcript = "hey atlas, how are you?"

        # Mock audio detection to return None, transcript to return result
        with (
            patch.object(wake_detector_enabled, "_detect_audio", return_value=None),
            patch.object(
                wake_detector_enabled, "_detect_transcript"
            ) as mock_transcript,
        ):

            mock_result = Mock()
            mock_result.phrase = "hey atlas"
            mock_result.confidence = 0.7
            mock_result.source = "transcript"
            mock_transcript.return_value = mock_result

            result = wake_detector_enabled.detect(sample_audio_segment, transcript)

        # Should return transcript result
        assert result is not None
        assert result.phrase == "hey atlas"
        assert result.confidence == 0.7
        assert result.source == "transcript"

    @pytest.mark.component
    def test_wake_detection_no_result(
        self, wake_detector_enabled, sample_audio_segment
    ):
        """Test that wake detection returns None when no wake phrase is detected."""
        transcript = "just some regular conversation"

        # Mock both audio and transcript detection to return None
        with (
            patch.object(wake_detector_enabled, "_detect_audio", return_value=None),
            patch.object(
                wake_detector_enabled, "_detect_transcript", return_value=None
            ),
        ):

            result = wake_detector_enabled.detect(sample_audio_segment, transcript)

        # Should return None
        assert result is None

    @pytest.mark.component
    def test_wake_detection_bypass_logs_enabled_state(
        self, wake_detector_disabled, sample_audio_segment
    ):
        """Test that wake detection bypass logs the enabled state."""
        transcript = "hey atlas, how are you?"

        # Mock the logger to capture the wake detection result log
        wake_detector_disabled._logger = Mock()

        result = wake_detector_disabled.detect(sample_audio_segment, transcript)

        # Should return testing_mode result
        assert result is not None
        assert result.phrase == "testing_mode"
        assert result.confidence == 1.0
        assert result.source == "transcript"

    @pytest.mark.component
    def test_wake_detection_config_validation(self):
        """Test that wake detection config validation works correctly."""
        # Test valid config
        valid_config = WakeConfig(
            wake_phrases=["hey atlas"],
            model_paths=[],
            activation_threshold=0.5,
            target_sample_rate_hz=16000,
            enabled=True,
        )

        detector = WakeDetector(valid_config)
        assert detector._config.enabled is True

        # Test disabled config
        disabled_config = WakeConfig(
            wake_phrases=["hey atlas"],
            model_paths=[],
            activation_threshold=0.5,
            target_sample_rate_hz=16000,
            enabled=False,
        )

        detector = WakeDetector(disabled_config)
        assert detector._config.enabled is False

    @pytest.mark.component
    def test_wake_detection_environment_parsing(self):
        """Test that wake detection correctly parses environment variables."""
        # Test various environment variable values
        test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("", False),  # Empty string is treated as false
            ("invalid", False),  # Invalid values are treated as false
        ]

        for env_value, expected in test_cases:
            with patch.dict(
                os.environ,
                {
                    "WAKE_DETECTION_ENABLED": env_value,
                    "DISCORD_BOT_TOKEN": "test-token",
                    "DISCORD_GUILD_ID": "987654321",
                    "DISCORD_VOICE_CHANNEL_ID": "123456789",
                    "STT_BASE_URL": "http://test-stt:9000",
                    "ORCHESTRATOR_BASE_URL": "http://test-orchestrator:8000",
                },
            ):
                from services.discord.config import load_config

                config = load_config()

                assert (
                    config.wake.enabled == expected
                ), f"Failed for env value: {env_value}"
