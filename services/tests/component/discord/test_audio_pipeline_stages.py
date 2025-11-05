"""Component tests for audio pipeline stage integration."""

import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from services.common.audio_processing_core import AudioProcessingCore
from services.common.surfaces.types import PCMFrame
from services.discord.audio_processor_wrapper import AudioProcessorWrapper
from services.discord.config import STTConfig
from services.discord.transcription import TranscriptionClient, TranscriptResult


@pytest.mark.component
@pytest.mark.asyncio
class TestAudioPipelineStages:
    """Component tests for audio pipeline stage integration."""

    @pytest.fixture
    def mock_audio_processor_core(self):
        """Create mock AudioProcessingCore."""
        core = AsyncMock(spec=AudioProcessingCore)
        core.process_frame = AsyncMock()
        return core

    @pytest.fixture
    def mock_audio_processor_wrapper(self, mock_audio_processor_core, mock_config):
        """Create AudioProcessorWrapper with mocked core."""
        audio_config, telemetry_config = mock_config
        return AudioProcessorWrapper(
            audio_config=audio_config,
            telemetry_config=telemetry_config,
            audio_processor_core=mock_audio_processor_core,
        )

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration."""
        audio_config = Mock()
        audio_config.enable_vad = True
        audio_config.enable_enhancement = True
        audio_config.vad_aggressiveness = 1
        # Add accumulator config fields
        audio_config.silence_timeout_seconds = 0.75
        audio_config.max_segment_duration_seconds = 15.0
        audio_config.min_segment_duration_seconds = 0.3
        audio_config.aggregation_window_seconds = 1.5
        audio_config.input_sample_rate_hz = 48000
        audio_config.vad_sample_rate_hz = 16000
        audio_config.vad_frame_duration_ms = 30

        telemetry_config = Mock()
        telemetry_config.waveform_debug_dir = None

        return audio_config, telemetry_config

    async def test_stage_voice_capture_to_processor(
        self, mock_audio_processor_wrapper, sample_pcm_audio
    ):
        """Test ingest_voice_packet() → AudioProcessorWrapper.register_frame_async()."""
        # Simulate voice packet ingestion
        user_id = 12345
        rms = 0.5
        duration = 0.03
        sample_rate = 48000

        # Create processed frame response
        processed_frame = PCMFrame(
            pcm=sample_pcm_audio + b"_processed",
            timestamp=time.time(),
            rms=0.6,
            duration=duration,
            sequence=1,
            sample_rate=sample_rate,
        )
        mock_audio_processor_wrapper._audio_processor_core.process_frame.return_value = processed_frame

        # Mock VAD to detect speech
        with patch(
            "services.discord.audio_processor_wrapper.VADProcessor.detect_speech",
            new_callable=AsyncMock,
        ) as mock_vad:
            mock_vad.return_value = True  # Speech detected

            # Simulate ingest_voice_packet calling register_frame_async
            # Single frame will return None (not enough for segment)
            segment = await mock_audio_processor_wrapper.register_frame_async(
                user_id=user_id,
                pcm=sample_pcm_audio,
                rms=rms,
                duration=duration,
                sample_rate=sample_rate,
            )

            # With accumulator, single frame returns None
            assert segment is None

            # Verify processor was called
            mock_audio_processor_wrapper._audio_processor_core.process_frame.assert_called_once()

    async def test_stage_processor_to_segment(
        self, mock_audio_processor_core, mock_config, sample_pcm_audio
    ):
        """Test frame processing → Segment creation with accumulator logic."""
        audio_config, telemetry_config = mock_config

        # Create wrapper
        wrapper = AudioProcessorWrapper(
            audio_config=audio_config,
            telemetry_config=telemetry_config,
            audio_processor_core=mock_audio_processor_core,
        )

        # Mock VAD to detect speech
        with patch(
            "services.discord.audio_processor_wrapper.VADProcessor.detect_speech",
            new_callable=AsyncMock,
        ) as mock_vad:
            mock_vad.return_value = True  # Speech detected

            # Set max duration low to trigger segment creation
            audio_config.max_segment_duration_seconds = 0.5

            # Send frames until segment is created
            user_id = 12345
            base_time = time.time()
            segment = None

            for i in range(12):  # 12 frames * 0.05 = 0.6 seconds > 0.5 max
                frame_time = base_time + (i * 0.05)
                processed_frame = PCMFrame(
                    pcm=sample_pcm_audio + b"_processed",
                    timestamp=frame_time,
                    rms=0.6,
                    duration=0.05,
                    sequence=i + 1,
                    sample_rate=48000,
                )
                mock_audio_processor_core.process_frame.return_value = processed_frame

                result = await wrapper.register_frame_async(
                    user_id=user_id,
                    pcm=sample_pcm_audio,
                    rms=0.5,
                    duration=0.05,
                    sample_rate=48000,
                )

                if result is not None:
                    segment = result
                    break

            # Verify segment structure
            assert segment is not None
            assert segment.user_id == user_id
            assert segment.frame_count > 1  # Multiple frames accumulated
            assert segment.duration >= 0.5  # At least max duration
            assert segment.correlation_id is not None
            assert segment.correlation_id.startswith("discord-")

            await wrapper.close()

    async def test_stage_segment_to_stt(self, sample_audio_segment_fixture):
        """Test segment → TranscriptionClient.transcribe() → TranscriptResult."""
        # Create STT config
        stt_config = STTConfig(
            base_url="http://test-stt:9000",
            request_timeout_seconds=45,
            max_retries=3,
            forced_language="en",
        )

        # Mock ResilientHTTPClient
        mock_resilient_client = AsyncMock()
        mock_resilient_client.post_with_retry = AsyncMock()
        mock_resilient_client.check_health = AsyncMock(return_value=True)
        mock_resilient_client.close = AsyncMock()

        # Configure mock response
        response = Mock()
        response.status_code = 200
        response.json = Mock(
            return_value={
                "text": "test transcript",
                "confidence": 0.95,
                "language": "en",
            }
        )
        response.aclose = AsyncMock()
        mock_resilient_client.post_with_retry.return_value = response

        # Patch ResilientHTTPClient constructor
        with patch(
            "services.discord.transcription.ResilientHTTPClient",
            return_value=mock_resilient_client,
        ):
            # Create client and test
            async with TranscriptionClient(stt_config) as client:
                client._http_client = mock_resilient_client

                result = await client.transcribe(sample_audio_segment_fixture)

                # Verify transcript result
                assert result is not None
                assert isinstance(result, TranscriptResult)
                assert result.text == "test transcript"
                assert (
                    result.correlation_id == sample_audio_segment_fixture.correlation_id
                )
                assert result.confidence == 0.95
                assert result.language == "en"

                # Verify request was made
                mock_resilient_client.post_with_retry.assert_called_once()

    async def test_stage_format_conversion_chain(
        self, mock_audio_processor_core, mock_config, sample_pcm_audio
    ):
        """Test format conversion through pipeline (PCM → processed → WAV)."""
        audio_config, telemetry_config = mock_config

        # Create wrapper
        wrapper = AudioProcessorWrapper(
            audio_config=audio_config,
            telemetry_config=telemetry_config,
            audio_processor_core=mock_audio_processor_core,
        )

        # Mock VAD to detect speech
        with patch(
            "services.discord.audio_processor_wrapper.VADProcessor.detect_speech",
            new_callable=AsyncMock,
        ) as mock_vad:
            mock_vad.return_value = True  # Speech detected

            # Set max duration low to trigger segment creation
            audio_config.max_segment_duration_seconds = 0.5

            # Send frames until segment is created
            user_id = 12345
            base_time = time.time()
            segment = None

            for i in range(12):
                frame_time = base_time + (i * 0.05)
                processed_frame = PCMFrame(
                    pcm=sample_pcm_audio + b"_processed",
                    timestamp=frame_time,
                    rms=0.6,
                    duration=0.05,
                    sequence=i + 1,
                    sample_rate=48000,
                )
                mock_audio_processor_core.process_frame.return_value = processed_frame

                result = await wrapper.register_frame_async(
                    user_id=user_id,
                    pcm=sample_pcm_audio,
                    rms=0.5,
                    duration=0.05,
                    sample_rate=48000,
                )

                if result is not None:
                    segment = result
                    break

            assert segment is not None
            # Processed PCM data (concatenated from frames)
            assert len(segment.pcm) > 0

        # Now test PCM → WAV conversion via TranscriptionClient
        stt_config = STTConfig(
            base_url="http://test-stt:9000",
            request_timeout_seconds=45,
            max_retries=3,
            forced_language="en",
        )

        mock_resilient_client = AsyncMock()
        mock_resilient_client.post_with_retry = AsyncMock()
        mock_resilient_client.check_health = AsyncMock(return_value=True)
        mock_resilient_client.close = AsyncMock()

        response = Mock()
        response.status_code = 200
        response.json = Mock(return_value={"text": "test"})
        response.aclose = AsyncMock()
        mock_resilient_client.post_with_retry.return_value = response

        with patch(
            "services.discord.transcription.ResilientHTTPClient",
            return_value=mock_resilient_client,
        ):
            # Convert segment (PCM) to WAV
            async with TranscriptionClient(stt_config) as client:
                client._http_client = mock_resilient_client

                transcript_result: TranscriptResult | None = await client.transcribe(
                    segment
                )

                # Verify conversion happened (WAV file was created)
                assert transcript_result is not None
                call_args = mock_resilient_client.post_with_retry.call_args
                assert "files" in call_args[1]
                files = call_args[1]["files"]
                assert "file" in files
                wav_filename, wav_bytes, content_type = files["file"]
                assert wav_filename.endswith(".wav")
                assert content_type == "audio/wav"
                assert len(wav_bytes) > 0  # WAV data exists

        await wrapper.close()

    async def test_stage_quality_metrics_propagation(
        self, mock_audio_processor_core, mock_config, sample_pcm_audio
    ):
        """Test quality metrics preservation in accumulated segments."""
        audio_config, telemetry_config = mock_config

        # Create wrapper
        wrapper = AudioProcessorWrapper(
            audio_config=audio_config,
            telemetry_config=telemetry_config,
            audio_processor_core=mock_audio_processor_core,
        )

        # Mock VAD to detect speech
        with patch(
            "services.discord.audio_processor_wrapper.VADProcessor.detect_speech",
            new_callable=AsyncMock,
        ) as mock_vad:
            mock_vad.return_value = True  # Speech detected

            # Set max duration low to trigger segment creation
            audio_config.max_segment_duration_seconds = 0.5

            # Send frames until segment is created
            base_time = time.time()
            segment = None

            for i in range(12):
                frame_time = base_time + (i * 0.05)
                processed_frame = PCMFrame(
                    pcm=sample_pcm_audio + b"_processed",
                    timestamp=frame_time,
                    rms=0.7,  # Quality metric
                    duration=0.05,
                    sequence=i + 1,
                    sample_rate=48000,
                )
                mock_audio_processor_core.process_frame.return_value = processed_frame

                result = await wrapper.register_frame_async(
                    user_id=12345,
                    pcm=sample_pcm_audio,
                    rms=0.5,
                    duration=0.05,
                    sample_rate=48000,
                )

                if result is not None:
                    segment = result
                    break

            # Verify segment preserves quality metrics
            assert segment is not None
            assert segment.sample_rate == processed_frame.sample_rate

            # Verify timestamps span from first to last frame
            assert segment.start_timestamp >= base_time
            assert segment.end_timestamp > segment.start_timestamp

            await wrapper.close()
