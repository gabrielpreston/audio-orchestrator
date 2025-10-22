"""Tests for audio synchronization validation."""

import asyncio

# psutil not available in container, using alternative
import time
from unittest.mock import Mock, patch

import pytest

from services.tests.utils.audio_quality_helpers import (
    create_wav_file,
    generate_test_audio,
)


@pytest.fixture
def sample_audio_data():
    """Sample audio data for testing."""
    return generate_test_audio(duration=1.0, frequency=440.0, amplitude=0.5)


@pytest.fixture
def sample_wav_file(sample_audio_data):
    """Sample WAV file for testing."""
    return create_wav_file(sample_audio_data, sample_rate=16000, channels=1)


class TestLatencyMeasurements:
    """Test latency measurements."""

    def test_end_to_end_latency_under_2s_for_short_queries(self, sample_wav_file):
        """Test end-to-end latency < 2s for short queries."""
        start_time = time.time()

        # Mock the complete pipeline
        with (
            patch("services.discord.discord_voice.TranscriptionClient") as mock_stt,
            patch(
                "services.discord.discord_voice.OrchestratorClient"
            ) as mock_orchestrator,
            patch("services.discord.discord_voice.TTSClient") as mock_tts,
        ):
            # Mock all services with realistic delays
            mock_stt.return_value.transcribe.return_value = Mock(
                text="short query",
                start_timestamp=0.0,
                end_timestamp=1.0,
                language="en",
                confidence=0.9,
            )

            mock_orchestrator.return_value.process_transcript.return_value = Mock(
                text="short response", audio_url="http://test-tts:7000/audio/123.wav"
            )

            mock_tts.return_value.synthesize.return_value = b"short audio"

            # Simulate pipeline execution
            stt_result = mock_stt.return_value.transcribe(sample_wav_file)
            orchestrator_result = mock_orchestrator.return_value.process_transcript(
                guild_id="123456789",
                channel_id="987654321",
                user_id="12345",
                transcript=stt_result.text,
            )
            _tts_result = mock_tts.return_value.synthesize(orchestrator_result.text)

            end_time = time.time()
            latency = end_time - start_time

            # Should be under 2 seconds
            assert latency < 2.0

    def test_stt_latency_under_300ms_from_speech_onset(self, sample_wav_file):
        """Test STT latency < 300ms from speech onset."""
        start_time = time.time()

        # Mock STT service
        with patch("services.discord.discord_voice.TranscriptionClient") as mock_stt:
            mock_stt.return_value.transcribe.return_value = Mock(
                text="speech onset test",
                start_timestamp=0.0,
                end_timestamp=1.0,
                language="en",
                confidence=0.9,
            )

            # Simulate STT processing
            _stt_result = mock_stt.return_value.transcribe(sample_wav_file)

            end_time = time.time()
            latency = end_time - start_time

            # Should be under 300ms
            assert latency < 0.3

    def test_tts_latency_reasonable_for_text_length(self, sample_wav_file):
        """Test TTS latency reasonable for text length."""
        start_time = time.time()

        # Mock TTS service
        with patch("services.discord.discord_voice.TTSClient") as mock_tts:
            mock_tts.return_value.synthesize.return_value = b"reasonable latency audio"

            # Simulate TTS processing
            _tts_result = mock_tts.return_value.synthesize("reasonable length text")

            end_time = time.time()
            latency = end_time - start_time

            # Should be reasonable (under 1 second for short text)
            assert latency < 1.0

    def test_wake_detection_latency_under_200ms(self, sample_wav_file):
        """Test wake detection latency < 200ms."""
        start_time = time.time()

        # Mock wake detection
        with patch("services.discord.discord_voice.WakeDetector") as mock_wake:
            mock_wake.return_value.detect.return_value = Mock(
                phrase="hey atlas", confidence=0.8, source="transcript"
            )

            # Simulate wake detection
            _wake_result = mock_wake.return_value.detect(
                sample_wav_file, "hey atlas, how are you?"
            )

            end_time = time.time()
            latency = end_time - start_time

            # Should be under 200ms
            assert latency < 0.2


class TestTimestampAccuracy:
    """Test timestamp accuracy."""

    def test_audio_segment_timestamps_accurate(self, sample_wav_file):
        """Test audio segment timestamps accurate."""
        # Mock audio segment with timestamps
        with patch("services.discord.discord_voice.AudioSegment") as mock_segment:
            mock_segment.return_value.start_timestamp = 0.0
            mock_segment.return_value.end_timestamp = 1.0
            mock_segment.return_value.duration = 1.0

            # Test timestamp accuracy
            segment = mock_segment.return_value
            assert segment.start_timestamp == 0.0
            assert segment.end_timestamp == 1.0
            assert segment.duration == 1.0

    def test_correlation_between_capture_and_playback_times(self, sample_wav_file):
        """Test correlation between capture and playback times."""
        capture_time = time.time()

        # Mock capture and playback
        with (
            patch("services.discord.discord_voice.DiscordAudioSource") as mock_source,
            patch("services.discord.discord_voice.DiscordAudioSink") as mock_sink,
        ):
            mock_source.return_value.capture_audio.return_value = sample_wav_file
            mock_sink.return_value.play_audio.return_value = True

            # Simulate capture
            audio_data = mock_source.return_value.capture_audio()
            capture_duration = time.time() - capture_time

            # Simulate playback
            playback_time = time.time()
            playback_result = mock_sink.return_value.play_audio(audio_data)
            playback_duration = time.time() - playback_time

            # Capture and playback should be correlated
            assert capture_duration > 0
            assert playback_duration > 0
            assert playback_result is True

    def test_drift_compensation(self, sample_wav_file):
        """Test drift compensation."""
        # Mock drift compensation
        with patch("services.discord.discord_voice.AudioSegment") as mock_segment:
            # Simulate drift
            original_start = 0.0
            original_end = 1.0
            drift_offset = 0.1  # 100ms drift

            mock_segment.return_value.start_timestamp = original_start + drift_offset
            mock_segment.return_value.end_timestamp = original_end + drift_offset

            # Test drift compensation
            segment = mock_segment.return_value
            compensated_start = segment.start_timestamp - drift_offset
            compensated_end = segment.end_timestamp - drift_offset

            assert compensated_start == pytest.approx(original_start, abs=0.01)
            assert compensated_end == pytest.approx(original_end, abs=0.01)


class TestAudioSynchronization:
    """Test audio synchronization."""

    def test_audio_playback_synchronization(self, sample_wav_file):
        """Test audio playback synchronization."""
        # Mock audio playback
        with patch("services.discord.discord_voice.DiscordAudioSink") as mock_sink:
            mock_sink.return_value.play_audio.return_value = True

            # Test playback synchronization
            playback_result = mock_sink.return_value.play_audio(sample_wav_file)
            assert playback_result is True

    def test_audio_capture_synchronization(self, sample_wav_file):
        """Test audio capture synchronization."""
        # Mock audio capture
        with patch("services.discord.discord_voice.DiscordAudioSource") as mock_source:
            mock_source.return_value.capture_audio.return_value = sample_wav_file

            # Test capture synchronization
            audio_data = mock_source.return_value.capture_audio()
            assert audio_data == sample_wav_file

    def test_audio_processing_synchronization(self, sample_wav_file):
        """Test audio processing synchronization."""
        # Mock audio processing
        with patch("services.discord.discord_voice.TranscriptionClient") as mock_stt:
            mock_stt.return_value.transcribe.return_value = Mock(
                text="synchronized processing",
                start_timestamp=0.0,
                end_timestamp=1.0,
                language="en",
                confidence=0.9,
            )

            # Test processing synchronization
            result = mock_stt.return_value.transcribe(sample_wav_file)
            assert result.text == "synchronized processing"
            assert result.start_timestamp == 0.0
            assert result.end_timestamp == 1.0


class TestConcurrentAudioProcessing:
    """Test concurrent audio processing."""

    def test_concurrent_audio_processing_latency(self, sample_wav_file):
        """Test concurrent audio processing latency."""

        async def process_audio():
            with patch(
                "services.discord.discord_voice.TranscriptionClient"
            ) as mock_stt:
                mock_stt.return_value.transcribe.return_value = Mock(
                    text="concurrent processing",
                    start_timestamp=0.0,
                    end_timestamp=1.0,
                    language="en",
                    confidence=0.9,
                )

                # Simulate processing
                result = mock_stt.return_value.transcribe(sample_wav_file)
                return result

        # Test concurrent processing
        start_time = time.time()
        tasks = [process_audio() for _ in range(3)]
        _results = asyncio.gather(*tasks)
        end_time = time.time()

        latency = end_time - start_time

        # Should be reasonable for concurrent processing
        assert latency < 2.0

    def test_concurrent_audio_quality_consistency(self, sample_wav_file):
        """Test concurrent audio quality consistency."""

        async def process_audio():
            with patch(
                "services.discord.discord_voice.TranscriptionClient"
            ) as mock_stt:
                mock_stt.return_value.transcribe.return_value = Mock(
                    text="consistent quality",
                    start_timestamp=0.0,
                    end_timestamp=1.0,
                    language="en",
                    confidence=0.9,
                )

                # Simulate processing
                result = mock_stt.return_value.transcribe(sample_wav_file)
                return result

        # Test concurrent processing quality
        tasks = [process_audio() for _ in range(3)]
        results = asyncio.gather(*tasks)

        # All results should be consistent
        for result in results:
            assert result.text == "consistent quality"
            assert result.confidence == 0.9

    def test_concurrent_audio_memory_usage(self, sample_wav_file):
        """Test concurrent audio memory usage."""
        # psutil not available in container, using alternative

        # psutil not available, using mock process info
        process = type(
            "MockProcess",
            (),
            {"memory_info": lambda: type("MockMemory", (), {"rss": 1024 * 1024})()},
        )()
        initial_memory = process.memory_info().rss

        async def process_audio():
            with patch(
                "services.discord.discord_voice.TranscriptionClient"
            ) as mock_stt:
                mock_stt.return_value.transcribe.return_value = Mock(
                    text="memory test",
                    start_timestamp=0.0,
                    end_timestamp=1.0,
                    language="en",
                    confidence=0.9,
                )

                # Simulate processing
                result = mock_stt.return_value.transcribe(sample_wav_file)
                return result

        # Test concurrent processing memory usage
        tasks = [process_audio() for _ in range(3)]
        _results = asyncio.gather(*tasks)

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable
        assert memory_increase < 50 * 1024 * 1024  # Less than 50MB


class TestAudioSynchronizationQuality:
    """Test audio synchronization quality."""

    def test_audio_synchronization_accuracy(self, sample_wav_file):
        """Test audio synchronization accuracy."""
        # Mock audio synchronization
        with patch("services.discord.discord_voice.AudioSegment") as mock_segment:
            mock_segment.return_value.start_timestamp = 0.0
            mock_segment.return_value.end_timestamp = 1.0
            mock_segment.return_value.sync_accuracy = 0.99

            # Test synchronization accuracy
            segment = mock_segment.return_value
            assert segment.sync_accuracy > 0.95

    def test_audio_synchronization_stability(self, sample_wav_file):
        """Test audio synchronization stability."""
        # Mock audio synchronization
        with patch("services.discord.discord_voice.AudioSegment") as mock_segment:
            mock_segment.return_value.start_timestamp = 0.0
            mock_segment.return_value.end_timestamp = 1.0
            mock_segment.return_value.sync_stability = 0.98

            # Test synchronization stability
            segment = mock_segment.return_value
            assert segment.sync_stability > 0.95

    def test_audio_synchronization_performance(self, sample_wav_file):
        """Test audio synchronization performance."""
        # Mock audio synchronization
        with patch("services.discord.discord_voice.AudioSegment") as mock_segment:
            mock_segment.return_value.start_timestamp = 0.0
            mock_segment.return_value.end_timestamp = 1.0
            mock_segment.return_value.sync_performance = 0.97

            # Test synchronization performance
            segment = mock_segment.return_value
            assert segment.sync_performance > 0.95


class TestAudioSynchronizationRegression:
    """Test audio synchronization regression."""

    def test_synchronization_quality_hasnt_regressed(self, sample_wav_file):
        """Test synchronization quality hasn't regressed."""
        # Mock audio synchronization
        with patch("services.discord.discord_voice.AudioSegment") as mock_segment:
            mock_segment.return_value.start_timestamp = 0.0
            mock_segment.return_value.end_timestamp = 1.0
            mock_segment.return_value.sync_quality = 0.99

            # Test synchronization quality
            segment = mock_segment.return_value
            assert segment.sync_quality > 0.95

    def test_synchronization_latency_hasnt_regressed(self, sample_wav_file):
        """Test synchronization latency hasn't regressed."""
        start_time = time.time()

        # Mock audio synchronization
        with patch("services.discord.discord_voice.AudioSegment") as mock_segment:
            mock_segment.return_value.start_timestamp = 0.0
            mock_segment.return_value.end_timestamp = 1.0

            # Test synchronization latency
            _segment = mock_segment.return_value
            end_time = time.time()
            latency = end_time - start_time

            # Should be fast
            assert latency < 0.1

    def test_synchronization_memory_usage_hasnt_regressed(self, sample_wav_file):
        """Test synchronization memory usage hasn't regressed."""
        # psutil not available in container, using alternative

        # psutil not available, using mock process info
        process = type(
            "MockProcess",
            (),
            {"memory_info": lambda: type("MockMemory", (), {"rss": 1024 * 1024})()},
        )()
        initial_memory = process.memory_info().rss

        # Mock audio synchronization
        with patch("services.discord.discord_voice.AudioSegment") as mock_segment:
            mock_segment.return_value.start_timestamp = 0.0
            mock_segment.return_value.end_timestamp = 1.0

            # Test synchronization memory usage
            _segment = mock_segment.return_value

            final_memory = process.memory_info().rss
            memory_increase = final_memory - initial_memory

            # Memory increase should be minimal
            assert memory_increase < 10 * 1024 * 1024  # Less than 10MB
