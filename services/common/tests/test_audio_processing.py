"""Tests for audio processing helper module."""

import base64
from unittest.mock import AsyncMock, Mock

import pytest

from services.common.audio_processing import process_audio_request
from services.common.surfaces.types import AudioSegment, PCMFrame


@pytest.fixture
def sample_pcm_bytes():
    """Create sample PCM bytes for testing."""
    return b"\x00\x01\x02\x03\x04\x05\x06\x07"


@pytest.fixture
def sample_pcm_base64(sample_pcm_bytes):
    """Create sample base64-encoded PCM for testing."""
    return base64.b64encode(sample_pcm_bytes).decode()


@pytest.fixture
def mock_logger():
    """Create a mock structured logger."""
    logger = Mock()
    logger.debug = Mock()
    logger.info = Mock()
    logger.error = Mock()
    return logger


@pytest.fixture
def mock_audio_metrics():
    """Create mock audio metrics dictionary."""
    return {
        "audio_processing_duration": Mock(record=Mock()),
        "audio_chunks_processed": Mock(add=Mock()),
        "audio_quality_score": Mock(record=Mock()),
    }


@pytest.mark.asyncio
async def test_process_frame_success(
    sample_pcm_bytes, sample_pcm_base64, mock_logger, mock_audio_metrics
):
    """Test successful frame processing."""
    # Create a frame
    original_frame = PCMFrame(
        pcm=sample_pcm_bytes,
        timestamp=1.0,
        rms=0.5,
        duration=0.02,
        sequence=1,
        sample_rate=16000,
    )

    processed_pcm = b"\x10\x11\x12\x13\x14\x15\x16\x17"
    processed_frame = PCMFrame(
        pcm=processed_pcm,
        timestamp=1.0,
        rms=0.6,
        duration=0.02,
        sequence=1,
        sample_rate=16000,
    )

    quality_metrics = {"rms": 0.6, "snr_db": 20.0}

    # Mock callbacks
    build_domain_object = Mock(return_value=original_frame)
    process_audio = AsyncMock(return_value=processed_frame)
    calculate_metrics = AsyncMock(return_value=quality_metrics)

    # Call helper
    result = await process_audio_request(
        pcm_base64=sample_pcm_base64,
        build_domain_object=build_domain_object,
        process_audio=process_audio,
        calculate_metrics=calculate_metrics,
        audio_metrics=mock_audio_metrics,
        logger=mock_logger,
        stage="frame_processing",
        chunk_type="frame",
        log_level="debug",
        log_attributes={"sequence": 1},
    )

    # Verify result
    assert result["success"] is True
    assert result["pcm"] == base64.b64encode(processed_pcm).decode()
    assert result["error"] is None
    assert result["quality_metrics"] == quality_metrics
    assert result["processing_time_ms"] >= 0

    # Verify callbacks called
    build_domain_object.assert_called_once_with(sample_pcm_bytes)
    process_audio.assert_called_once_with(original_frame)
    calculate_metrics.assert_called_once_with(processed_frame)

    # Verify metrics recorded
    mock_audio_metrics["audio_processing_duration"].record.assert_called_once()
    call_args = mock_audio_metrics["audio_processing_duration"].record.call_args
    assert call_args[0][0] >= 0  # processing time
    assert call_args[1]["attributes"] == {
        "stage": "frame_processing",
        "status": "success",
        "service": "audio",
    }

    mock_audio_metrics["audio_chunks_processed"].add.assert_called_once_with(
        1, attributes={"type": "frame", "service": "audio"}
    )

    # Verify logging (debug level for frames)
    mock_logger.debug.assert_called_once()
    log_call = mock_logger.debug.call_args
    assert log_call[0][0] == "audio.frame_processed"
    assert "sequence" in log_call[1]
    assert "processing_time_ms" in log_call[1]


@pytest.mark.asyncio
async def test_process_segment_success(
    sample_pcm_bytes, sample_pcm_base64, mock_logger, mock_audio_metrics
):
    """Test successful segment processing."""
    # Create a segment
    original_segment = AudioSegment(
        user_id="123",
        pcm=sample_pcm_bytes,
        start_timestamp=1.0,
        end_timestamp=2.0,
        correlation_id="test-123",
        frame_count=10,
        sample_rate=16000,
    )

    processed_pcm = b"\x20\x21\x22\x23\x24\x25\x26\x27"
    processed_segment = AudioSegment(
        user_id="123",
        pcm=processed_pcm,
        start_timestamp=1.0,
        end_timestamp=2.0,
        correlation_id="test-123",
        frame_count=10,
        sample_rate=16000,
    )

    quality_metrics = {
        "rms": 0.7,
        "snr_db": 25.0,
        "overall_score": 0.85,
    }

    # Mock callbacks
    build_domain_object = Mock(return_value=original_segment)
    process_audio = AsyncMock(return_value=processed_segment)
    calculate_metrics = AsyncMock(return_value=quality_metrics)

    # Call helper
    result = await process_audio_request(
        pcm_base64=sample_pcm_base64,
        build_domain_object=build_domain_object,
        process_audio=process_audio,
        calculate_metrics=calculate_metrics,
        audio_metrics=mock_audio_metrics,
        logger=mock_logger,
        stage="segment_processing",
        chunk_type="segment",
        log_level="info",
        log_attributes={"correlation_id": "test-123", "user_id": 123},
    )

    # Verify result
    assert result["success"] is True
    assert result["pcm"] == base64.b64encode(processed_pcm).decode()
    assert result["error"] is None
    assert result["quality_metrics"] == quality_metrics

    # Verify metrics recorded (including quality score)
    mock_audio_metrics["audio_quality_score"].record.assert_called_once_with(0.85)

    # Verify logging (info level for segments)
    mock_logger.info.assert_called_once()
    log_call = mock_logger.info.call_args
    assert log_call[0][0] == "audio.segment_processed"
    assert "correlation_id" in log_call[1]
    assert "user_id" in log_call[1]


@pytest.mark.asyncio
async def test_base64_decode_failure(mock_logger, mock_audio_metrics):
    """Test handling of invalid base64 string."""
    invalid_base64 = "!!!invalid-base64!!!"

    build_domain_object = Mock()
    process_audio = AsyncMock()
    calculate_metrics = AsyncMock()

    result = await process_audio_request(
        pcm_base64=invalid_base64,
        build_domain_object=build_domain_object,
        process_audio=process_audio,
        calculate_metrics=calculate_metrics,
        audio_metrics=mock_audio_metrics,
        logger=mock_logger,
        stage="frame_processing",
        chunk_type="frame",
    )

    # Verify error response
    assert result["success"] is False
    assert result["error"] is not None
    assert result["pcm"] == invalid_base64  # Original returned
    assert result["quality_metrics"] is None

    # Verify error metrics recorded
    mock_audio_metrics["audio_processing_duration"].record.assert_called_once()
    call_args = mock_audio_metrics["audio_processing_duration"].record.call_args
    assert call_args[1]["attributes"]["status"] == "error"

    # Verify error logged
    mock_logger.error.assert_called_once()
    error_log_call = mock_logger.error.call_args
    assert "frame_processing_failed" in error_log_call[0][0]


@pytest.mark.asyncio
async def test_processing_failure(
    sample_pcm_bytes, sample_pcm_base64, mock_logger, mock_audio_metrics
):
    """Test handling of processing failure."""
    frame = PCMFrame(
        pcm=sample_pcm_bytes,
        timestamp=1.0,
        rms=0.5,
        duration=0.02,
        sequence=1,
        sample_rate=16000,
    )

    build_domain_object = Mock(return_value=frame)
    process_audio = AsyncMock(side_effect=Exception("Processing failed"))
    calculate_metrics = AsyncMock()

    result = await process_audio_request(
        pcm_base64=sample_pcm_base64,
        build_domain_object=build_domain_object,
        process_audio=process_audio,
        calculate_metrics=calculate_metrics,
        audio_metrics=mock_audio_metrics,
        logger=mock_logger,
        stage="frame_processing",
        chunk_type="frame",
        original_pcm_base64=sample_pcm_base64,
    )

    # Verify error response
    assert result["success"] is False
    assert "Processing failed" in result["error"]
    assert result["pcm"] == sample_pcm_base64
    assert result["quality_metrics"] is None

    # Verify calculate_metrics was NOT called (processing failed first)
    calculate_metrics.assert_not_called()


@pytest.mark.asyncio
async def test_metrics_calculation_failure(
    sample_pcm_bytes, sample_pcm_base64, mock_logger, mock_audio_metrics
):
    """Test handling of metrics calculation failure."""
    frame = PCMFrame(
        pcm=sample_pcm_bytes,
        timestamp=1.0,
        rms=0.5,
        duration=0.02,
        sequence=1,
        sample_rate=16000,
    )

    processed_frame = PCMFrame(
        pcm=sample_pcm_bytes,
        timestamp=1.0,
        rms=0.6,
        duration=0.02,
        sequence=1,
        sample_rate=16000,
    )

    build_domain_object = Mock(return_value=frame)
    process_audio = AsyncMock(return_value=processed_frame)
    calculate_metrics = AsyncMock(side_effect=Exception("Metrics calculation failed"))

    result = await process_audio_request(
        pcm_base64=sample_pcm_base64,
        build_domain_object=build_domain_object,
        process_audio=process_audio,
        calculate_metrics=calculate_metrics,
        audio_metrics=mock_audio_metrics,
        logger=mock_logger,
        stage="frame_processing",
        chunk_type="frame",
    )

    # Verify error response
    assert result["success"] is False
    assert "Metrics calculation failed" in result["error"]


@pytest.mark.asyncio
async def test_no_metrics_dict(sample_pcm_bytes, sample_pcm_base64, mock_logger):
    """Test handling when audio_metrics is None."""
    frame = PCMFrame(
        pcm=sample_pcm_bytes,
        timestamp=1.0,
        rms=0.5,
        duration=0.02,
        sequence=1,
        sample_rate=16000,
    )

    processed_frame = PCMFrame(
        pcm=sample_pcm_bytes,
        timestamp=1.0,
        rms=0.6,
        duration=0.02,
        sequence=1,
        sample_rate=16000,
    )

    quality_metrics = {"rms": 0.6}

    build_domain_object = Mock(return_value=frame)
    process_audio = AsyncMock(return_value=processed_frame)
    calculate_metrics = AsyncMock(return_value=quality_metrics)

    # Call with None metrics
    result = await process_audio_request(
        pcm_base64=sample_pcm_base64,
        build_domain_object=build_domain_object,
        process_audio=process_audio,
        calculate_metrics=calculate_metrics,
        audio_metrics=None,
        logger=mock_logger,
        stage="frame_processing",
        chunk_type="frame",
    )

    # Should still succeed
    assert result["success"] is True


@pytest.mark.asyncio
async def test_custom_log_attributes(
    sample_pcm_bytes, sample_pcm_base64, mock_logger, mock_audio_metrics
):
    """Test that custom log attributes are included in logs."""
    frame = PCMFrame(
        pcm=sample_pcm_bytes,
        timestamp=1.0,
        rms=0.5,
        duration=0.02,
        sequence=1,
        sample_rate=16000,
    )

    processed_frame = PCMFrame(
        pcm=sample_pcm_bytes,
        timestamp=1.0,
        rms=0.6,
        duration=0.02,
        sequence=1,
        sample_rate=16000,
    )

    build_domain_object = Mock(return_value=frame)
    process_audio = AsyncMock(return_value=processed_frame)
    calculate_metrics = AsyncMock(return_value={})

    custom_attrs = {"custom_field": "custom_value", "another_field": 42}

    await process_audio_request(
        pcm_base64=sample_pcm_base64,
        build_domain_object=build_domain_object,
        process_audio=process_audio,
        calculate_metrics=calculate_metrics,
        audio_metrics=mock_audio_metrics,
        logger=mock_logger,
        stage="frame_processing",
        chunk_type="frame",
        log_attributes=custom_attrs,
    )

    # Verify custom attributes in log
    log_call = mock_logger.debug.call_args
    assert log_call[1]["custom_field"] == "custom_value"
    assert log_call[1]["another_field"] == 42


@pytest.mark.asyncio
async def test_segment_quality_score_not_recorded_when_missing(
    sample_pcm_bytes, sample_pcm_base64, mock_logger, mock_audio_metrics
):
    """Test that quality score is only recorded when present in metrics."""
    segment = AudioSegment(
        user_id="123",
        pcm=sample_pcm_bytes,
        start_timestamp=1.0,
        end_timestamp=2.0,
        correlation_id="test-123",
        frame_count=10,
        sample_rate=16000,
    )

    processed_segment = AudioSegment(
        user_id="123",
        pcm=sample_pcm_bytes,
        start_timestamp=1.0,
        end_timestamp=2.0,
        correlation_id="test-123",
        frame_count=10,
        sample_rate=16000,
    )

    # Quality metrics without overall_score
    quality_metrics = {"rms": 0.7, "snr_db": 25.0}

    build_domain_object = Mock(return_value=segment)
    process_audio = AsyncMock(return_value=processed_segment)
    calculate_metrics = AsyncMock(return_value=quality_metrics)

    await process_audio_request(
        pcm_base64=sample_pcm_base64,
        build_domain_object=build_domain_object,
        process_audio=process_audio,
        calculate_metrics=calculate_metrics,
        audio_metrics=mock_audio_metrics,
        logger=mock_logger,
        stage="segment_processing",
        chunk_type="segment",
    )

    # Quality score should NOT be recorded when overall_score is missing
    mock_audio_metrics["audio_quality_score"].record.assert_not_called()
