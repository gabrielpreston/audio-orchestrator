"""Component tests for AudioProcessorWrapper."""

import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from services.common.surfaces.types import PCMFrame
from services.common.audio_processing_core import AudioProcessingCore
from services.discord.audio_processor_wrapper import AudioProcessorWrapper


@pytest.mark.component
@pytest.mark.asyncio
class TestAudioProcessorWrapper:
    """Component tests for AudioProcessorWrapper."""

    @pytest.fixture
    def mock_audio_processor_core(self):
        """Create mock AudioProcessingCore."""
        core = AsyncMock(spec=AudioProcessingCore)
        core.process_frame = AsyncMock()
        return core

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

    async def test_register_frame_async_success(
        self, mock_audio_processor_core, mock_config, sample_pcm_audio
    ):
        """Test frame registration with successful processing.

        With accumulator logic, a single frame typically returns None unless
        it triggers a flush (max duration or silence timeout after min duration).
        This test verifies that frames are processed but segments are only created
        when conditions are met.
        """
        audio_config, telemetry_config = mock_config

        # Create processed frame response
        base_time = time.time()
        processed_frame = PCMFrame(
            pcm=sample_pcm_audio + b"_processed",
            timestamp=base_time,
            rms=0.6,
            duration=0.03,
            sequence=1,
            sample_rate=48000,
        )
        mock_audio_processor_core.process_frame.return_value = processed_frame

        # Mock VAD to detect speech
        with patch(
            "services.discord.audio_processor_wrapper.VADProcessor.detect_speech",
            new_callable=AsyncMock,
        ) as mock_vad:
            mock_vad.return_value = True  # Speech detected

            # Create wrapper with injected client
            wrapper = AudioProcessorWrapper(
                audio_config=audio_config,
                telemetry_config=telemetry_config,
                audio_processor_core=mock_audio_processor_core,
            )

            # Test frame registration - single frame should return None (not enough for segment)
            user_id = 12345
            result = await wrapper.register_frame_async(
                user_id=user_id,
                pcm=sample_pcm_audio,
                rms=0.5,
                duration=0.03,
                sample_rate=48000,
            )

            # With accumulator, single frame should return None (not enough duration)
            assert result is None

            # Verify frame was processed
            mock_audio_processor_core.process_frame.assert_called_once()
            call_frame = mock_audio_processor_core.process_frame.call_args[0][0]
            assert call_frame.pcm == sample_pcm_audio
            assert call_frame.sample_rate == 48000

            await wrapper.close()

    async def test_register_frame_async_service_unavailable(
        self, mock_audio_processor_core, mock_config, sample_pcm_audio
    ):
        """Test graceful handling when core returns None."""
        audio_config, telemetry_config = mock_config

        # Configure mock to return None (processing unavailable)
        mock_audio_processor_core.process_frame.return_value = None

        # Create wrapper with injected client
        wrapper = AudioProcessorWrapper(
            audio_config=audio_config,
            telemetry_config=telemetry_config,
            audio_processor_core=mock_audio_processor_core,
        )

        # Test frame registration
        result = await wrapper.register_frame_async(
            user_id=12345,
            pcm=sample_pcm_audio,
            rms=0.5,
            duration=0.03,
            sample_rate=48000,
        )

        # Verify None is returned
        assert result is None

        await wrapper.close()

    async def test_register_frame_async_segment_creation(
        self, mock_audio_processor_core, mock_config, sample_pcm_audio
    ):
        """Test segment creation when max duration is reached."""
        audio_config, telemetry_config = mock_config

        # Create wrapper with injected client
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

            # Send enough frames to exceed max_segment_duration_seconds
            # max is 15.0 seconds, each frame is 0.05 seconds, need ~300 frames
            # But to keep test fast, set max_duration to 0.5 seconds (10 frames)
            audio_config.max_segment_duration_seconds = 0.5

            user_id = 12345
            base_time = time.time()
            segment = None

            # Send frames until segment is created (max duration)
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

            # Verify segment was created due to max duration
            assert segment is not None
            assert segment.user_id == user_id
            assert segment.frame_count > 1  # Multiple frames accumulated
            assert segment.duration >= 0.5  # At least max duration
            assert segment.correlation_id is not None
            assert segment.correlation_id.startswith("discord-")

            await wrapper.close()

    async def test_correlation_id_generation(
        self, mock_audio_processor_core, mock_config, sample_pcm_audio
    ):
        """Test correlation ID generation uses standard format."""
        audio_config, telemetry_config = mock_config

        # Create wrapper with injected client
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

            user_id = 99999
            base_time = time.time()
            segment = None

            # Send enough frames to trigger max duration
            for i in range(12):
                frame_time = base_time + (i * 0.05)
                processed_frame = PCMFrame(
                    pcm=sample_pcm_audio,
                    timestamp=frame_time,
                    rms=0.5,
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

            # Verify correlation ID format (standard format: discord-{user_id}-{timestamp_ms}-{suffix})
            assert segment is not None
            assert segment.correlation_id.startswith(f"discord-{user_id}-")
            # Should contain timestamp and unique suffix
            parts = segment.correlation_id.split("-")
            assert len(parts) >= 3  # discord, user_id, timestamp, suffix

            await wrapper.close()

    async def test_frame_to_segment_conversion(
        self, mock_audio_processor_core, mock_config, sample_pcm_audio
    ):
        """Test correct PCMFrame → AudioSegment conversion with accumulated frames."""
        audio_config, telemetry_config = mock_config

        # Create wrapper with injected client
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

            user_id = 54321
            base_timestamp = 1000.0
            segment = None

            # Send frames until segment is created
            for i in range(12):
                frame_time = base_timestamp + (i * 0.05)
                processed_frame = PCMFrame(
                    pcm=sample_pcm_audio + b"_processed",
                    timestamp=frame_time,
                    rms=0.7,
                    duration=0.04,
                    sequence=i + 1,
                    sample_rate=16000,
                )
                mock_audio_processor_core.process_frame.return_value = processed_frame

                result = await wrapper.register_frame_async(
                    user_id=user_id,
                    pcm=sample_pcm_audio,
                    rms=0.5,
                    duration=0.04,
                    sample_rate=16000,
                )

                if result is not None:
                    segment = result
                    break

            # Verify conversion with accumulated frames
            assert segment is not None
            # PCM data should be concatenated from all frames
            assert len(segment.pcm) > 0
            # Timestamps span from first to last frame
            assert segment.start_timestamp >= base_timestamp
            assert segment.end_timestamp > segment.start_timestamp
            # Frame count should be multiple frames
            assert segment.frame_count > 1
            # Sample rate from processed frames
            assert segment.sample_rate == 16000

            await wrapper.close()

    async def test_health_check_delegation(
        self, mock_audio_processor_core, mock_config
    ):
        """Test health check returns True for library-based implementation."""
        audio_config, telemetry_config = mock_config

        # Create wrapper with injected client
        wrapper = AudioProcessorWrapper(
            audio_config=audio_config,
            telemetry_config=telemetry_config,
            audio_processor_core=mock_audio_processor_core,
        )

        # Test health check
        result = await wrapper.health_check()

        # Verify results
        assert result is True
        # Health check is now just a simple True return for library-based implementation

        await wrapper.close()
