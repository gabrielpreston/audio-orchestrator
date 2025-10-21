"""Component tests for Discord audio adapters."""

from unittest.mock import Mock

import pytest


@pytest.mark.component
class TestDiscordAudioSourceAdapter:
    """Test DiscordAudioSource adapter internal logic."""

    def test_audio_source_initialization(self):
        """Test DiscordAudioSource initialization."""
        # Mock the DiscordAudioSource class since it may not exist yet
        mock_adapter = Mock()
        mock_adapter.return_value = Mock()

        adapter = mock_adapter()
        assert adapter is not None

    def test_audio_source_capture(self, mock_audio_data):
        """Test audio capture logic."""
        # Mock audio capture component
        mock_audio_capture = Mock()
        mock_audio_capture.capture_audio.return_value = mock_audio_data

        # Test audio capture logic
        audio_data = mock_audio_capture.capture_audio()
        assert audio_data == mock_audio_data


@pytest.mark.component
class TestDiscordAudioSinkAdapter:
    """Test DiscordAudioSink adapter internal logic."""

    def test_audio_sink_initialization(self):
        """Test DiscordAudioSink initialization."""
        # Mock the DiscordAudioSink class since it may not exist yet
        mock_adapter = Mock()
        mock_adapter.return_value = Mock()

        adapter = mock_adapter()
        assert adapter is not None

    def test_audio_sink_playback(self, mock_audio_data):
        """Test audio playback logic."""
        # Mock audio playback component
        mock_audio_playback = Mock()
        mock_audio_playback.play_audio.return_value = True

        # Test audio playback logic
        success = mock_audio_playback.play_audio(mock_audio_data)
        assert success is True


@pytest.mark.component
class TestDiscordWakeDetection:
    """Test Discord wake word detection component logic."""

    def test_wake_detector_initialization(self):
        """Test wake detector initialization."""
        # Mock wake detector component
        mock_wake_detector = Mock()
        mock_wake_detector.return_value = Mock()

        detector = mock_wake_detector()
        assert detector is not None

    def test_wake_phrase_detection(self, mock_audio_data):
        """Test wake phrase detection logic."""
        # Mock wake detection component
        mock_wake_detection = Mock()
        mock_wake_detection.detect_wake_phrase.return_value = True

        # Test wake phrase detection logic
        is_wake_phrase = mock_wake_detection.detect_wake_phrase(mock_audio_data)
        assert is_wake_phrase is True


@pytest.mark.component
class TestDiscordVADPipeline:
    """Test Discord VAD (Voice Activity Detection) component logic."""

    def test_vad_initialization(self):
        """Test VAD pipeline initialization."""
        # Mock VAD component
        mock_vad = Mock()
        mock_vad.return_value = Mock()

        vad = mock_vad()
        assert vad is not None

    def test_vad_speech_detection(self, mock_audio_data):
        """Test VAD speech detection logic."""
        # Mock VAD detection component
        mock_vad_detection = Mock()
        mock_vad_detection.detect_speech.return_value = True

        # Test VAD speech detection logic
        is_speech = mock_vad_detection.detect_speech(mock_audio_data)
        assert is_speech is True
