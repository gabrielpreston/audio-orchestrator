"""Shared audio processing helper for frame and segment processing endpoints.

This module provides a generic helper function to eliminate code duplication
between audio processing endpoints by handling common concerns like base64
decoding/encoding, metrics recording, error handling, and logging.

Example usage:

    ```python
    # In endpoint handler
    result = await process_audio_request(
        pcm_base64=request.pcm,
        build_domain_object=lambda pcm: PCMFrame(
            pcm=pcm,
            timestamp=request.timestamp,
            rms=request.rms,
            duration=request.duration,
            sequence=request.sequence,
            sample_rate=request.sample_rate,
        ),
        process_audio=lambda frame: audio_processor.process_frame(frame),
        calculate_metrics=lambda frame: audio_processor.calculate_quality_metrics(frame),
        audio_metrics=_audio_metrics,
        logger=_logger,
        stage="frame_processing",
        chunk_type="frame",
        log_level="debug",
        log_attributes={"sequence": request.sequence},
        original_pcm_base64=request.pcm,
    )

    return ProcessingResponse(**result)
    ```
"""

from __future__ import annotations

import base64
import time
from collections.abc import Awaitable, Callable
from typing import Any

from services.common.surfaces.types import AudioSegment, PCMFrame


async def process_audio_request(
    pcm_base64: str,
    build_domain_object: Callable[[bytes], PCMFrame | AudioSegment],
    process_audio: Callable[
        [PCMFrame | AudioSegment], Awaitable[PCMFrame | AudioSegment]
    ],
    calculate_metrics: Callable[[PCMFrame | AudioSegment], Awaitable[dict[str, Any]]],
    audio_metrics: dict[str, Any] | None,
    logger: Any,
    stage: str,
    chunk_type: str,
    log_level: str = "debug",
    log_attributes: dict[str, Any] | None = None,
    original_pcm_base64: str | None = None,
) -> dict[str, Any]:
    """Process an audio request with common concerns handled.

    This function handles the common pattern of:
    1. Decoding base64 PCM data
    2. Building domain objects (PCMFrame or AudioSegment)
    3. Processing the audio
    4. Calculating quality metrics
    5. Recording metrics
    6. Encoding the result
    7. Logging
    8. Error handling

    Args:
        pcm_base64: Base64-encoded PCM audio data
        build_domain_object: Callback to build PCMFrame or AudioSegment from decoded PCM bytes
        process_audio: Async callback to process the domain object
        calculate_metrics: Async callback to calculate quality metrics from processed object
        audio_metrics: Dictionary of metric instruments (from create_audio_metrics)
        logger: Structured logger instance
        stage: Stage name for metrics (e.g., "frame_processing", "segment_processing")
        chunk_type: Chunk type for metrics (e.g., "frame", "segment")
        log_level: Log level for success ("debug" or "info")
        log_attributes: Additional attributes to include in success log
        original_pcm_base64: Original PCM data to return on error (defaults to pcm_base64)

    Returns:
        Dictionary matching ProcessingResponse structure:
        {
            "success": bool,
            "pcm": str,  # Base64-encoded processed PCM
            "processing_time_ms": float,
            "quality_metrics": dict[str, Any] | None,
            "error": str | None,
        }
    """
    start_time = time.perf_counter()
    original_pcm = original_pcm_base64 or pcm_base64
    log_attrs = log_attributes or {}

    try:
        # Decode PCM data
        pcm_data = base64.b64decode(pcm_base64)

        # Build domain object
        domain_object = build_domain_object(pcm_data)

        # Process audio
        processed_object = await process_audio(domain_object)

        # Calculate quality metrics
        quality_metrics = await calculate_metrics(processed_object)

        processing_time = (time.perf_counter() - start_time) * 1000

        # Record success metrics
        if audio_metrics:
            if "audio_processing_duration" in audio_metrics:
                audio_metrics["audio_processing_duration"].record(
                    processing_time / 1000,
                    attributes={
                        "stage": stage,
                        "status": "success",
                        "service": "audio",
                    },
                )
            if "audio_chunks_processed" in audio_metrics:
                audio_metrics["audio_chunks_processed"].add(
                    1, attributes={"type": chunk_type, "service": "audio"}
                )
            # Segments may also record audio_quality_score
            if "audio_quality_score" in audio_metrics and quality_metrics:
                quality_score = quality_metrics.get("overall_score", 0.0)
                audio_metrics["audio_quality_score"].record(quality_score)

        # Encode processed PCM data
        processed_pcm = base64.b64encode(processed_object.pcm).decode()

        # Log success
        log_message = f"audio.{chunk_type}_processed"
        log_data = {
            **log_attrs,
            "processing_time_ms": processing_time,
            "quality_metrics": quality_metrics,
        }

        if log_level == "info":
            logger.info(log_message, **log_data)
        else:
            logger.debug(log_message, **log_data)

        return {
            "success": True,
            "pcm": processed_pcm,
            "processing_time_ms": processing_time,
            "quality_metrics": quality_metrics,
            "error": None,
        }

    except Exception as exc:
        processing_time = (time.perf_counter() - start_time) * 1000

        # Record error metrics
        if audio_metrics and "audio_processing_duration" in audio_metrics:
            audio_metrics["audio_processing_duration"].record(
                processing_time / 1000,
                attributes={
                    "stage": stage,
                    "status": "error",
                    "service": "audio",
                },
            )

        # Log error
        error_log_message = f"audio.{chunk_type}_processing_failed"
        error_log_data = {
            **log_attrs,
            "error": str(exc),
            "processing_time_ms": processing_time,
        }
        logger.error(error_log_message, **error_log_data)

        return {
            "success": False,
            "pcm": original_pcm,
            "processing_time_ms": processing_time,
            "quality_metrics": None,
            "error": str(exc),
        }
