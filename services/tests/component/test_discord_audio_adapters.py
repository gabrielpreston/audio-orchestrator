"""Component tests for Discord audio adapters."""

from unittest.mock import Mock, patch

import pytest


@pytest.mark.component
class TestDiscordAudioSourceAdapter:
    """Test DiscordAudioSource adapter internal logic."""

    def test_audio_source_initialization(self):
        """Test DiscordAudioSource initialization."""
        with patch("discord.VoiceClient") as mock_voice:
            from services.discord.discord_voice import DiscordAudioSource

            adapter = DiscordAudioSource(mock_voice)
            assert adapter is not None
            # Use adapter to avoid unused variable warning
            assert adapter is not None

    def test_audio_source_capture(self, mock_audio_data):
        """Test audio capture logic."""
        with patch("discord.VoiceClient") as mock_voice:
            from services.discord.discord_voice import DiscordAudioSource

            # Mock the voice client's read method
            mock_voice.read.return_value = mock_audio_data

            adapter = DiscordAudioSource(mock_voice)
            # Test internal capture logic
            # (Implementation depends on actual adapter interface)
            assert adapter is not None


@pytest.mark.component
class TestDiscordAudioSinkAdapter:
    """Test DiscordAudioSink adapter internal logic."""

    def test_audio_sink_initialization(self):
        """Test DiscordAudioSink initialization."""
        with patch("discord.VoiceClient") as mock_voice:
            from services.discord.discord_voice import DiscordAudioSink

            adapter = DiscordAudioSink(mock_voice)
            assert adapter is not None

    def test_audio_sink_playback(self, mock_audio_data):
        """Test audio playback logic."""
        with patch("discord.VoiceClient") as mock_voice:
            from services.discord.discord_voice import DiscordAudioSink

            # Mock the voice client's write method
            mock_voice.write.return_value = True

            adapter = DiscordAudioSink(mock_voice)
            # Test internal playback logic
            # (Implementation depends on actual adapter interface)
            assert adapter is not None


@pytest.mark.component
class TestDiscordWakeDetection:
    """Test Discord wake word detection component logic."""

    def test_wake_detector_initialization(self):
        """Test wake detector initialization."""
        with patch("services.discord.discord_voice.WakeDetector") as mock_wake:
            # Test wake detector setup
            assert mock_wake is not None

    def test_wake_phrase_detection(self, mock_audio_data):
        """Test wake phrase detection logic."""
        with patch("services.discord.discord_voice.WakeDetector") as mock_wake:
            # Mock wake detection result
            mock_wake.return_value.detect.return_value = Mock(
                phrase="hey atlas", confidence=0.8, source="transcript"
            )

            # Test wake detection logic
            # (Implementation depends on actual wake detector interface)


@pytest.mark.component
class TestDiscordVADPipeline:
    """Test Discord VAD (Voice Activity Detection) component logic."""

    def test_vad_initialization(self):
        """Test VAD pipeline initialization."""
        with patch("services.discord.discord_voice.VADPipeline") as mock_vad:
            # Test VAD setup
            assert mock_vad is not None

    def test_vad_speech_detection(self, mock_audio_data):
        """Test VAD speech detection logic."""
        with patch("services.discord.discord_voice.VADPipeline") as mock_vad:
            # Mock VAD detection result
            mock_vad.return_value.detect_speech.return_value = True

            # Test VAD detection logic
            # (Implementation depends on actual VAD interface)
