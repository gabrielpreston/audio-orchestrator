"""Component tests for AudioProcessorWrapper."""

import time
from unittest.mock import AsyncMock, Mock

import pytest

from services.common.surfaces.types import PCMFrame
from services.common.audio_processing_core import AudioProcessingCore
from services.discord.audio import AudioSegment
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

        telemetry_config = Mock()
        telemetry_config.waveform_debug_dir = None

        return audio_config, telemetry_config

    async def test_register_frame_async_success(
        self, mock_audio_processor_core, mock_config, sample_pcm_audio
    ):
        """Test frame registration with successful processing."""
        audio_config, telemetry_config = mock_config

        # Create processed frame response
        processed_frame = PCMFrame(
            pcm=sample_pcm_audio + b"_processed",
            timestamp=time.time(),
            rms=0.6,
            duration=0.03,
            sequence=1,
            sample_rate=48000,
        )
        mock_audio_processor_core.process_frame.return_value = processed_frame

        # Create wrapper with injected client
        wrapper = AudioProcessorWrapper(
            audio_config=audio_config,
            telemetry_config=telemetry_config,
            audio_processor_core=mock_audio_processor_core,
        )

        # Test frame registration
        user_id = 12345
        result = await wrapper.register_frame_async(
            user_id=user_id,
            pcm=sample_pcm_audio,
            rms=0.5,
            duration=0.03,
            sample_rate=48000,
        )

        # Verify segment was created
        assert result is not None
        assert isinstance(result, AudioSegment)
        assert result.user_id == user_id  # user_id is int in discord AudioSegment
        assert result.pcm == processed_frame.pcm
        assert result.sample_rate == processed_frame.sample_rate
        assert result.frame_count == 1

        # Verify client was called
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
        """Test segment creation from processed frame validates structure."""
        audio_config, telemetry_config = mock_config

        # Create processed frame response
        frame_timestamp = time.time()
        processed_frame = PCMFrame(
            pcm=sample_pcm_audio + b"_processed",
            timestamp=frame_timestamp,
            rms=0.6,
            duration=0.05,
            sequence=1,
            sample_rate=48000,
        )
        mock_audio_processor_core.process_frame.return_value = processed_frame

        # Create wrapper with injected client
        wrapper = AudioProcessorWrapper(
            audio_config=audio_config,
            telemetry_config=telemetry_config,
            audio_processor_core=mock_audio_processor_core,
        )

        # Test frame registration
        user_id = 12345
        result = await wrapper.register_frame_async(
            user_id=user_id,
            pcm=sample_pcm_audio,
            rms=0.5,
            duration=0.05,
            sample_rate=48000,
        )

        # Verify segment structure
        assert result is not None
        assert result.user_id == user_id  # user_id is int in discord AudioSegment
        assert result.pcm == processed_frame.pcm
        assert result.start_timestamp == processed_frame.timestamp
        assert (
            result.end_timestamp == processed_frame.timestamp + processed_frame.duration
        )
        assert result.frame_count == 1
        assert result.sample_rate == processed_frame.sample_rate
        assert result.correlation_id is not None
        assert result.correlation_id.startswith(f"frame-{user_id}-")

        await wrapper.close()

    async def test_correlation_id_generation(
        self, mock_audio_processor_core, mock_config, sample_pcm_audio
    ):
        """Test dynamic correlation ID generation (format: f"frame-{user_id}-{int(timestamp)}")."""
        audio_config, telemetry_config = mock_config

        # Create processed frame response with specific timestamp
        frame_timestamp = 1234567.89
        processed_frame = PCMFrame(
            pcm=sample_pcm_audio,
            timestamp=frame_timestamp,
            rms=0.5,
            duration=0.03,
            sequence=1,
            sample_rate=48000,
        )
        mock_audio_processor_core.process_frame.return_value = processed_frame

        # Create wrapper with injected client
        wrapper = AudioProcessorWrapper(
            audio_config=audio_config,
            telemetry_config=telemetry_config,
            audio_processor_core=mock_audio_processor_core,
        )

        # Test frame registration
        user_id = 99999
        result = await wrapper.register_frame_async(
            user_id=user_id,
            pcm=sample_pcm_audio,
            rms=0.5,
            duration=0.03,
            sample_rate=48000,
        )

        # Verify correlation ID format
        assert result is not None
        assert result.correlation_id.startswith(f"frame-{user_id}-")
        expected_suffix = str(int(frame_timestamp))
        assert result.correlation_id.endswith(expected_suffix)

        await wrapper.close()

    async def test_frame_to_segment_conversion(
        self, mock_audio_processor_core, mock_config, sample_pcm_audio
    ):
        """Test correct PCMFrame → AudioSegment conversion (PCM data, timestamps, frame_count)."""
        audio_config, telemetry_config = mock_config

        # Create processed frame response
        frame_timestamp = 1000.0
        processed_frame = PCMFrame(
            pcm=sample_pcm_audio + b"_processed",
            timestamp=frame_timestamp,
            rms=0.7,
            duration=0.04,
            sequence=42,
            sample_rate=16000,
        )
        mock_audio_processor_core.process_frame.return_value = processed_frame

        # Create wrapper with injected client
        wrapper = AudioProcessorWrapper(
            audio_config=audio_config,
            telemetry_config=telemetry_config,
            audio_processor_core=mock_audio_processor_core,
        )

        # Test frame registration
        user_id = 54321
        result = await wrapper.register_frame_async(
            user_id=user_id,
            pcm=sample_pcm_audio,
            rms=0.5,
            duration=0.04,
            sample_rate=16000,
        )

        # Verify conversion
        assert result is not None
        # PCM data from processed frame
        assert result.pcm == processed_frame.pcm
        # Timestamps from processed frame
        assert result.start_timestamp == processed_frame.timestamp
        assert (
            result.end_timestamp == processed_frame.timestamp + processed_frame.duration
        )
        # Frame count is set to 1 (simplified implementation)
        assert result.frame_count == 1
        # Sample rate from processed frame
        assert result.sample_rate == processed_frame.sample_rate

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
