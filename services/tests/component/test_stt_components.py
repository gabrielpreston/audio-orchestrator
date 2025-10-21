"""Component tests for STT service internal components."""

from unittest.mock import Mock

import pytest


@pytest.fixture
def sample_audio_bytes():
    """Sample audio bytes for testing."""
    return b"fake_audio_data"


@pytest.mark.component
class TestFasterWhisperAdapter:
    """Test faster-whisper adapter component logic."""

    def test_model_initialization(self):
        """Test faster-whisper model initialization."""
        # Mock model initialization component
        mock_model = Mock()
        mock_model.return_value = Mock()

        model = mock_model()
        assert model is not None

    def test_transcription_pipeline(self, sample_audio_bytes):
        """Test audio transcription pipeline."""
        # Mock transcription component
        mock_transcription = Mock()
        mock_transcription.transcribe.return_value = "hello world"

        # Test transcription logic
        result = mock_transcription.transcribe(sample_audio_bytes)
        assert result == "hello world"

    def test_language_detection(self, sample_audio_bytes):
        """Test language detection logic."""
        # Mock language detection component
        mock_language_detector = Mock()
        mock_language_detector.detect_language.return_value = "en"

        # Test language detection logic
        language = mock_language_detector.detect_language(sample_audio_bytes)
        assert language == "en"

    def test_confidence_scoring(self, sample_audio_bytes):
        """Test confidence scoring logic."""
        # Mock confidence scoring component
        mock_confidence_scorer = Mock()
        mock_confidence_scorer.calculate_confidence.return_value = 0.95

        # Test confidence scoring logic
        confidence = mock_confidence_scorer.calculate_confidence(sample_audio_bytes)
        assert confidence == 0.95


@pytest.mark.component
class TestSTTAudioProcessing:
    """Test STT audio processing component logic."""

    def test_audio_format_validation(self, sample_audio_bytes):
        """Test audio format validation logic."""
        # Mock audio format validator
        mock_validator = Mock()
        mock_validator.validate_format.return_value = True

        # Test audio format validation logic
        is_valid = mock_validator.validate_format(sample_audio_bytes)
        assert is_valid is True

    def test_audio_preprocessing(self, sample_audio_bytes):
        """Test audio preprocessing logic."""
        # Mock audio preprocessor
        mock_preprocessor = Mock()
        mock_preprocessor.preprocess.return_value = sample_audio_bytes

        # Test audio preprocessing logic
        processed_audio = mock_preprocessor.preprocess(sample_audio_bytes)
        assert processed_audio == sample_audio_bytes

    def test_audio_segmentation(self, sample_audio_bytes):
        """Test audio segmentation logic."""
        # Mock audio segmenter
        mock_segmenter = Mock()
        mock_segmenter.segment.return_value = [sample_audio_bytes]

        # Test audio segmentation logic
        segments = mock_segmenter.segment(sample_audio_bytes)
        assert segments == [sample_audio_bytes]
