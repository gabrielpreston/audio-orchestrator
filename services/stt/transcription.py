"""Transcription request processing functions.

This module contains extracted functions for handling STT transcription requests,
separating concerns for better testability and maintainability.
"""

import hashlib
import time
from collections.abc import Iterable
from typing import Any, cast

from fastapi import HTTPException, Request

from services.common.structured_logging import correlation_context, get_logger

logger = get_logger(__name__, service_name="stt")


def resolve_correlation_id(request: Request, provided_id: str | None) -> str:
    """Resolve and validate correlation ID from request or generate new one.

    Args:
        request: FastAPI request object
        provided_id: Correlation ID provided as function parameter

    Returns:
        Validated correlation ID (generates new one if none provided)

    Raises:
        HTTPException: 400 if provided correlation ID is invalid
    """
    # Extract from headers, query params, or use provided
    headers_correlation = request.headers.get("X-Correlation-ID")
    query_correlation = request.query_params.get("correlation_id")
    correlation_id = provided_id or headers_correlation or query_correlation

    # Validate correlation ID if provided
    if correlation_id:
        from services.common.correlation import validate_correlation_id

        is_valid, error_msg = validate_correlation_id(correlation_id)
        if not is_valid:
            raise HTTPException(
                status_code=400, detail=f"Invalid correlation ID: {error_msg}"
            )

    # Generate STT correlation ID if none provided
    if not correlation_id:
        from services.common.correlation import generate_stt_correlation_id

        correlation_id = generate_stt_correlation_id()

    return correlation_id  # type: ignore[no-any-return]


async def prepare_audio_for_transcription(
    wav_bytes: bytes,
    correlation_id: str,
    audio_processor_client: Any | None,  # noqa: ARG001
    enhance_audio_func: Any,
) -> tuple[bytes, str]:
    """Prepare audio for transcription by enhancing and generating cache key.

    Args:
        wav_bytes: Original WAV audio bytes
        correlation_id: Correlation ID for logging
        audio_processor_client: Audio processor client (can be None, passed for API consistency)
        enhance_audio_func: Function to enhance audio (from app.py)

    Returns:
        Tuple of (enhanced_wav_bytes, cache_key)
    """
    # Apply audio enhancement if enabled (before cache check)
    enhanced_wav_bytes = await enhance_audio_func(wav_bytes, correlation_id)

    # Generate cache key from audio bytes (convert to hex string for hashing)
    cache_key = hashlib.sha256(enhanced_wav_bytes).hexdigest()

    return enhanced_wav_bytes, cache_key


def check_cache(
    cache: Any | None,
    cache_key: str,
    correlation_id: str,
) -> dict[str, Any] | None:
    """Check transcript cache for existing result.

    Args:
        cache: Transcript cache instance (can be None)
        cache_key: SHA256 hash of audio bytes
        correlation_id: Correlation ID for logging

    Returns:
        Cached result dict if found, None otherwise
    """
    if not cache:
        return None

    cached_result = cache.get(cache_key)
    if cached_result:
        # Add correlation_id to cached response if not present
        if correlation_id and "correlation_id" not in cached_result:
            cached_result["correlation_id"] = correlation_id

        cache_stats = cache.get_stats()
        # Log cache hit with correlation context
        with correlation_context(correlation_id) as request_logger:
            request_logger.info(
                "stt.cache_hit",
                cache_key=cache_key[:16],
                correlation_id=correlation_id,
                cache_hit_rate=round(cache_stats["hit_rate"], 3),
            )
        # Type check: ensure cached_result is a dict
        if isinstance(cached_result, dict):
            return cast("dict[str, Any]", cached_result)

    return None


def validate_request(
    wav_bytes: bytes,
    extract_audio_metadata_func: Any,
) -> tuple[int, int, int]:
    """Validate transcription request and extract audio metadata.

    Args:
        wav_bytes: WAV audio bytes
        extract_audio_metadata_func: Function to extract metadata (from app.py)

    Returns:
        Tuple of (channels, sampwidth, framerate)

    Raises:
        HTTPException: 400 if request is empty or invalid
    """
    import io
    import wave

    if not wav_bytes:
        raise HTTPException(status_code=400, detail="empty request body")

    # Validate WAV header
    if not wav_bytes.startswith(b"RIFF"):
        raise HTTPException(
            status_code=400, detail="Invalid WAV file: missing RIFF header"
        )

    # Extract metadata (this may already perform some validation)
    try:
        channels, sampwidth, framerate = extract_audio_metadata_func(wav_bytes)
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Failed to extract WAV metadata: {e}"
        ) from e

    # Additional defense-in-depth: Verify WAV can be opened and has frames
    # NOTE: This may duplicate validation in extract_audio_metadata_func, but provides
    # explicit check for zero frames which is a known issue
    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
            frames = wav.getnframes()
            if frames == 0:
                raise HTTPException(
                    status_code=400,
                    detail="WAV file contains zero frames (silent audio)",
                )
    except HTTPException:
        raise
    except Exception as e:
        # If wave.open fails, log but don't fail if extract_audio_metadata_func succeeded
        # This handles edge cases where wave.open is stricter than extract_audio_metadata_func
        logger.warning(
            "stt.wav_validation_warning",
            error=str(e),
            note="WAV metadata extraction succeeded but wave.open validation failed",
        )
        # Still raise exception as this indicates a potential issue
        raise HTTPException(
            status_code=400, detail=f"Invalid WAV file structure: {e}"
        ) from e

    return channels, sampwidth, framerate


async def ensure_model_ready(
    model_loader: Any | None,
) -> Any:
    """Ensure transcription model is loaded and ready.

    Args:
        model_loader: BackgroundModelLoader instance (can be None)

    Returns:
        Loaded model instance

    Raises:
        HTTPException: 503 if model is not available or still loading
    """
    if model_loader is None:
        raise HTTPException(status_code=503, detail="Model loader not initialized")

    if model_loader.is_loading():
        raise HTTPException(
            status_code=503,
            detail="Model is currently loading. Please try again shortly.",
        )

    if not model_loader.is_loaded():
        status = model_loader.get_status()
        error_msg = status.get("error", "Model not available")
        raise HTTPException(status_code=503, detail=f"Model not available: {error_msg}")

    # Ensure model is loaded (may trigger lazy load if background failed)
    if not await model_loader.ensure_loaded():
        status = model_loader.get_status()
        error_msg = status.get("error", "Model not available")
        raise HTTPException(status_code=503, detail=f"Model not available: {error_msg}")

    model = model_loader.get_model()
    if model is None:
        raise HTTPException(status_code=503, detail="Model not available")

    return model


def parse_transcription_params(
    request: Request,
    config: Any,
    parse_bool_func: Any,
) -> dict[str, Any]:
    """Parse and validate transcription parameters from request query params.

    Args:
        request: FastAPI request object
        config: Service configuration object
        parse_bool_func: Function to parse boolean strings (from app.py)

    Returns:
        Dict with transcription parameters:
        - task: str | None
        - beam_size: int
        - language: str | None
        - include_word_ts: bool
        - vad_filter: bool
        - initial_prompt: str | None

    Raises:
        HTTPException: 400 if beam_size is invalid
    """
    task = request.query_params.get("task")
    beam_size_q = request.query_params.get("beam_size")
    lang_q = request.query_params.get("language")
    word_ts_q = request.query_params.get("word_timestamps")
    vad_filter_q = request.query_params.get("vad_filter")
    initial_prompt = request.query_params.get("initial_prompt")

    language = lang_q
    include_word_ts = parse_bool_func(word_ts_q)

    # Use configured beam_size as default (optimized to 5 for quality/latency balance)
    beam_size = getattr(config.faster_whisper, "beam_size", 5) or 5
    if beam_size_q:
        try:
            beam_size = int(beam_size_q)
            if beam_size < 1:
                beam_size = getattr(config.faster_whisper, "beam_size", 5) or 5
        except (ValueError, TypeError) as exc:
            logger.warning(
                "stt.invalid_beam_size",
                beam_size=beam_size_q,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise HTTPException(
                status_code=400, detail="invalid beam_size query param"
            ) from exc

    return {
        "task": task,
        "beam_size": beam_size,
        "language": language,
        "include_word_ts": include_word_ts,
        "vad_filter": parse_bool_func(vad_filter_q),
        "initial_prompt": initial_prompt,
    }


async def execute_inference(
    model: Any,
    tmp_path: str,
    params: dict[str, Any],
    device: str,
    correlation_id: str,
    model_name: str,
    validate_cuda_runtime_func: Any,
    get_model_device_info_func: Any,
    request_logger: Any,
    input_bytes: int,
) -> tuple[list[Any], Any, dict[str, Any], float]:
    """Execute faster-whisper transcription inference.

    Args:
        model: Loaded WhisperModel instance
        tmp_path: Path to temporary WAV file
        params: Transcription parameters dict
        device: Target device ("cpu" or "cuda")
        correlation_id: Correlation ID for logging
        model_name: Model name for logging
        validate_cuda_runtime_func: Function to validate CUDA (from app.py)
        get_model_device_info_func: Function to get device info (from app.py)
        request_logger: Logger instance with correlation context
        input_bytes: Size of input audio in bytes (avoids filesystem stat call)

    Returns:
        Tuple of (segments_list, info, device_info, inference_duration)

    Raises:
        HTTPException: 503 if CUDA validation fails or inference errors occur
        RuntimeError: For non-CUDA inference errors
    """

    # Get device info for logging (STT-specific for CTranslate2)
    device_info = {}
    if model:
        try:
            model_device_info = get_model_device_info_func(model)
            device_info = {
                "intended_device": device,
                **model_device_info,
            }
        except Exception:
            device_info = {
                "intended_device": device,
                "actual_device": "unknown",
            }

    request_logger.info(
        "stt.processing_started",
        correlation_id=correlation_id,
        model=model_name,
        input_bytes=input_bytes,
        beam_size=params["beam_size"],
        language=params["language"],
        task=params["task"],
        include_word_timestamps=params["include_word_ts"],
        decision="starting_transcription_inference",
    )

    # Log device info
    request_logger.info(
        "stt.processing_started.device_info",
        correlation_id=correlation_id,
        intended_device=device_info.get("intended_device"),
        actual_device=device_info.get("actual_device", "unknown"),
        device_verified=device_info.get("device_verified", False),
        model_on_device=device_info.get("model_on_device"),
        pytorch_cuda_available=device_info.get("pytorch_cuda_available", False),
        pytorch_cuda_device_name=device_info.get("pytorch_cuda_device_name"),
        phase="inference_start",
    )

    # Build transcribe kwargs
    transcribe_kwargs: dict[str, object] = {"beam_size": params["beam_size"]}
    if params["task"] == "translate":
        transcribe_kwargs.update({"task": "translate", "language": params["language"]})
    elif params["language"] is not None:
        transcribe_kwargs["language"] = params["language"]
    if params["include_word_ts"]:
        transcribe_kwargs["word_timestamps"] = True
    if params["vad_filter"]:
        transcribe_kwargs["vad_filter"] = True
    if params["initial_prompt"]:
        transcribe_kwargs["initial_prompt"] = params["initial_prompt"]

    # Validate CUDA runtime before inference if using CUDA
    if device == "cuda" and not validate_cuda_runtime_func():
        request_logger.error(
            "stt.cuda_runtime_unavailable_at_inference",
            correlation_id=correlation_id,
            actual_device=device_info.get("actual_device", "unknown"),
            decision="cuda_validation_failed",
        )
        raise HTTPException(
            status_code=503,
            detail="CUDA runtime unavailable. Model may need to be reloaded with CPU device.",
        )

    inference_start = time.time()
    try:
        raw_segments, info = model.transcribe(tmp_path, **transcribe_kwargs)
        inference_duration = time.time() - inference_start

        # Log successful inference with device confirmation
        request_logger.info(
            "stt.inference_completed",
            correlation_id=correlation_id,
            inference_duration_ms=round(inference_duration * 1000, 2),
            decision="inference_success",
        )

        # Log device info
        request_logger.info(
            "stt.inference_completed.device_info",
            correlation_id=correlation_id,
            intended_device=device_info.get("intended_device"),
            actual_device=device_info.get("actual_device", "unknown"),
            model_on_device=device_info.get("model_on_device"),
            phase="inference_complete",
        )
    except (RuntimeError, OSError) as e:
        inference_duration = time.time() - inference_start
        error_str = str(e).lower()
        # Check if this is a CUDA-related error
        if any(
            keyword in error_str
            for keyword in ["cuda", "cudnn", "gpu", "cuda error", "invalid handle"]
        ):
            request_logger.error(
                "stt.cuda_inference_error",
                correlation_id=correlation_id,
                error=str(e),
                error_type=type(e).__name__,
                intended_device=device_info.get("intended_device"),
                actual_device=device_info.get("actual_device", "unknown"),
                model_on_device=device_info.get("model_on_device"),
                inference_duration_ms=round(inference_duration * 1000, 2),
                decision="cuda_inference_failed",
            )
            raise HTTPException(
                status_code=503,
                detail=f"CUDA inference failed: {str(e)}. Service may need CPU device configuration.",
            ) from e
        # Re-raise non-CUDA errors
        raise
    except Exception as e:
        inference_duration = time.time() - inference_start
        # Log other errors but don't assume they're CUDA-related
        request_logger.error(
            "stt.inference_error",
            correlation_id=correlation_id,
            error=str(e),
            error_type=type(e).__name__,
            intended_device=device_info.get("intended_device"),
            actual_device=device_info.get("actual_device", "unknown"),
            model_on_device=device_info.get("model_on_device"),
            inference_duration_ms=round(inference_duration * 1000, 2),
        )
        raise

    # faster-whisper may return a generator/iterator for segments; convert
    # to a list so we can iterate it multiple times (build text and
    # optionally include word-level timestamps).
    if isinstance(raw_segments, list):
        segments_list = raw_segments
    else:
        try:
            segments_list = list(cast("Iterable[Any]", raw_segments))
        except TypeError:
            segments_list = [raw_segments]

    return segments_list, info, device_info, inference_duration


def build_transcription_response(
    segments_list: list[Any],
    info: Any,
    params: dict[str, Any],
    processing_ms: int,
    total_ms: int,
    input_bytes: int,
    correlation_id: str,
    model_name: str,
    device: str,
) -> dict[str, Any]:
    """Build transcription response dictionary from inference results.

    Args:
        segments_list: List of transcription segments
        info: Transcription info object from faster-whisper
        params: Transcription parameters dict
        processing_ms: Processing time in milliseconds
        total_ms: Total request time in milliseconds
        input_bytes: Input audio size in bytes
        correlation_id: Correlation ID
        model_name: Model name
        device: Device used for inference

    Returns:
        Response dictionary with transcription results
    """
    # Build a combined text
    text = " ".join(getattr(seg, "text", "") for seg in segments_list).strip()

    # Build segments with word timestamps if requested
    segments_out: list[dict[str, Any]] = []
    if params["include_word_ts"]:
        for seg in segments_list:
            segment_entry: dict[str, Any] = {
                "start": getattr(seg, "start", None),
                "end": getattr(seg, "end", None),
                "text": getattr(seg, "text", ""),
            }
            # some faster-whisper variants expose `words` on segments when
            # word timestamps are requested; include them if present.
            words = getattr(seg, "words", None)
            word_entries: list[dict[str, Any]] = []
            if isinstance(words, list):
                for w in words:
                    word_entries.append(
                        {
                            "word": getattr(w, "word", None)
                            or getattr(w, "text", None),
                            "start": getattr(w, "start", None),
                            "end": getattr(w, "end", None),
                        }
                    )
            elif words is not None:
                word_entries.append(
                    {
                        "word": getattr(words, "word", None)
                        or getattr(words, "text", None),
                        "start": getattr(words, "start", None),
                        "end": getattr(words, "end", None),
                    }
                )
            if word_entries:
                segment_entry["words"] = word_entries
            segments_out.append(segment_entry)

    resp: dict[str, Any] = {
        "text": text,
        "duration": getattr(info, "duration", None),
        "language": getattr(info, "language", None),
        "confidence": getattr(info, "language_probability", None),
        "processing_ms": processing_ms,
        "total_ms": total_ms,
        "input_bytes": input_bytes,
        "model": model_name,
        "device": device,
    }

    if params["task"]:
        resp["task"] = params["task"]

    # include correlation id if provided by client
    if correlation_id:
        resp["correlation_id"] = correlation_id

    if params["include_word_ts"] and segments_out:
        resp["segments"] = segments_out

    return resp


def record_transcription_metrics(
    metrics: dict[str, Any] | None,
    status: str,
    processing_seconds: float,
) -> None:
    """Record transcription metrics.

    Args:
        metrics: Metrics dictionary (can be None)
        status: Status string ("success" or "error")
        processing_seconds: Processing time in seconds
    """
    if not metrics:
        return

    if "stt_requests" in metrics:
        metrics["stt_requests"].add(1, attributes={"status": status})
    if "stt_latency" in metrics:
        metrics["stt_latency"].record(processing_seconds, attributes={"status": status})


def cache_transcription_result(
    cache: Any | None,
    cache_key: str,
    response: dict[str, Any],
) -> None:
    """Cache transcription result.

    Args:
        cache: Transcript cache instance (can be None)
        cache_key: SHA256 hash of audio bytes
        response: Response dictionary to cache
    """
    if cache:
        cache.put(cache_key, response)
