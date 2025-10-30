from collections.abc import Iterable
import io
import os
import time
from typing import Any, cast
import wave

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile
from starlette.requests import ClientDisconnect

from services.common.config import (
    ServiceConfig,
    get_service_preset,
    load_config_from_env,
)
from services.common.health import HealthManager
from services.common.health_endpoints import HealthEndpoints
from services.common.structured_logging import configure_logging, get_logger
from services.common.tracing import setup_service_observability

from .audio_processor_client import STTAudioProcessorClient


# Configuration classes are now handled by the new config system


app = FastAPI(title="audio-orchestrator STT (faster-whisper)")

# Centralized configuration
_cfg: ServiceConfig = load_config_from_env(ServiceConfig, **get_service_preset("stt"))

MODEL_NAME = _cfg.faster_whisper.model
MODEL_PATH = _cfg.faster_whisper.model_path or "/app/models"
# Module-level cached model to avoid repeated loads
_model: Any = None
# Audio enhancer for preprocessing
_audio_enhancer: Any = None
# Audio processor client for remote enhancement
_audio_processor_client: STTAudioProcessorClient | None = None
# Health manager for service resilience
_health_manager = HealthManager("stt")
# Observability manager for metrics and tracing
_observability_manager = None
_stt_metrics: dict[str, Any] = {}
_http_metrics: dict[str, Any] = {}

# Enhancement statistics
_enhancement_stats: dict[str, int | float | str | None] = {
    "total_processed": 0,
    "successful": 0,
    "failed": 0,
    "last_error": None,
    "last_error_time": None,
    "total_duration_ms": 0.0,
    "avg_duration_ms": 0.0,
}


configure_logging(
    _cfg.logging.level,
    json_logs=_cfg.logging.json_logs,
    service_name="stt",
)
logger = get_logger(__name__, service_name="stt")


def _update_enhancement_stats(
    success: bool, duration_ms: float, error: str | None = None
) -> None:
    """Update enhancement statistics."""
    global _enhancement_stats  # noqa: PLW0602

    _enhancement_stats["total_processed"] = (
        int(_enhancement_stats["total_processed"] or 0) + 1
    )
    _enhancement_stats["total_duration_ms"] = (
        float(_enhancement_stats["total_duration_ms"] or 0.0) + duration_ms
    )
    _enhancement_stats["avg_duration_ms"] = float(
        _enhancement_stats["total_duration_ms"] or 0.0
    ) / int(_enhancement_stats["total_processed"] or 1)

    if success:
        _enhancement_stats["successful"] = (
            int(_enhancement_stats["successful"] or 0) + 1
        )
    else:
        _enhancement_stats["failed"] = int(_enhancement_stats["failed"] or 0) + 1
        _enhancement_stats["last_error"] = error
        _enhancement_stats["last_error_time"] = time.time()


@app.on_event("startup")  # type: ignore[misc]
async def _warm_model() -> None:
    """Ensure the Whisper model is loaded before serving traffic."""
    global _model, _audio_processor_client, _observability_manager

    try:
        # Setup observability first (most likely to succeed)
        _observability_manager = setup_service_observability("stt", "1.0.0")
        _observability_manager.instrument_fastapi(app)
        _health_manager.set_observability_manager(_observability_manager)

        # Try to load model with fallback
        try:
            _model = _lazy_load_model()
            logger.info("stt.model_loaded", model_name=MODEL_NAME)
        except Exception as exc:
            logger.warning("stt.model_load_failed", error=str(exc))
            # Try fallback to smaller model
            try:
                fallback_model_name = "tiny.en"  # Fallback model
                _model = _lazy_load_model()
                logger.info("stt.fallback_model_loaded", model_name=fallback_model_name)
            except Exception as fallback_exc:
                logger.error("stt.fallback_model_failed", error=str(fallback_exc))
                _model = None

        # Initialize audio processor client with fallback
        try:
            _audio_processor_client = STTAudioProcessorClient(
                base_url=_cfg.faster_whisper.audio_service_url or "http://audio:9100",
                timeout=_cfg.faster_whisper.audio_service_timeout or 50.0,
            )
            logger.info("stt.audio_processor_client_initialized")
        except Exception as exc:
            logger.warning("stt.audio_processor_client_init_failed", error=str(exc))
            _audio_processor_client = None

        # Always mark startup complete (graceful degradation)
        _health_manager.mark_startup_complete()

        # Optional warmup only if model loaded successfully
        if _model and _cfg.telemetry.stt_warmup:
            try:
                import tempfile
                import time as _time
                import numpy as np

                # Generate ~300ms silence at 16kHz mono int16
                samples = int(16000 * 0.3)
                pcm = (np.zeros(samples, dtype=np.int16)).tobytes()

                # Encode to WAV using AudioProcessor to match runtime path
                from services.common.audio import AudioProcessor

                processor = AudioProcessor("stt")
                wav_data = processor.pcm_to_wav(pcm, 16000, 1, 2)
                warm_start = _time.perf_counter()
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp.write(wav_data)
                    tmp_path = tmp.name
                try:
                    model = _lazy_load_model()
                    _ = model.transcribe(tmp_path, beam_size=6)
                except Exception as _exc:  # best-effort
                    logger.debug("stt.warmup_skipped", reason=str(_exc))
                finally:
                    from contextlib import suppress
                    import os as _os

                    with suppress(Exception):
                        _os.unlink(tmp_path)
                warm_ms = int((_time.perf_counter() - warm_start) * 1000)
                logger.info("stt.warmup_ms", value=warm_ms)
            except Exception as warmup_exc:
                logger.warning("stt.warmup_failed", error=str(warmup_exc))

    except Exception as exc:
        logger.error("stt.startup_failed", error=str(exc))
        # Still mark startup complete to avoid infinite startup loop
        _health_manager.mark_startup_complete()


# Initialize health endpoints
health_endpoints = HealthEndpoints(
    service_name="stt",
    health_manager=_health_manager,
    custom_components={
        "model_loaded": lambda: _model is not None,
        "model_name": lambda: MODEL_NAME,
        "enhancer_loaded": lambda: _audio_enhancer is not None,
        "enhancer_enabled": lambda: (
            _audio_enhancer.is_enhancement_enabled if _audio_enhancer else False
        ),
        "audio_processor_client_loaded": lambda: _audio_processor_client is not None,
    },
    custom_dependencies={
        "audio_processor": lambda: _audio_processor_client is not None,
    },
)

# Include the health endpoints router
app.include_router(health_endpoints.get_router())


def _parse_bool(value: str | None) -> bool:
    if value is None:
        return False
    return str(value).lower() in {"1", "true", "yes", "on"}


def _lazy_load_model() -> Any:
    global _model
    try:
        from faster_whisper import WhisperModel
    except Exception as e:
        logger.exception("stt.model_import_failed", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"faster-whisper import error: {e}"
        ) from e

    if _model is not None:
        logger.debug("stt.model_cache_hit", model_name=MODEL_NAME)
        return _model

    device = _cfg.faster_whisper.device
    compute_type = _cfg.faster_whisper.compute_type
    # Check if we have a local model directory
    local_model_path = os.path.join(MODEL_PATH, MODEL_NAME)
    model_path_or_name = (
        local_model_path if os.path.exists(local_model_path) else MODEL_NAME
    )

    try:
        if compute_type:
            _model = WhisperModel(
                model_path_or_name, device=device, compute_type=compute_type
            )
        else:
            _model = WhisperModel(model_path_or_name, device=device)
        logger.info(
            "stt.model_loaded",
            model_name=MODEL_NAME,
            model_path=model_path_or_name,
            is_local=os.path.exists(local_model_path),
            device=device,
            compute_type=compute_type or "default",
        )
    except Exception as e:
        logger.exception(
            "stt.model_load_error",
            model_name=MODEL_NAME,
            device=device,
            compute_type=compute_type,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"model load error: {e}") from e
    return _model


def _extract_audio_metadata(wav_bytes: bytes) -> tuple[int, int, int]:
    """Extract audio metadata using standardized audio processing."""
    from services.common.audio import AudioProcessor

    processor = AudioProcessor("stt")

    try:
        metadata = processor.extract_metadata(wav_bytes, "wav")

        # Validate sample width (only 16-bit supported)
        if metadata.sample_width != 2:
            raise HTTPException(
                status_code=400, detail="only 16-bit PCM WAV is supported"
            )

        return metadata.channels, metadata.sample_width, metadata.sample_rate

    except Exception:
        # Fallback to original implementation
        try:
            with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
                wf.getnframes()  # consume to ensure header validity
        except wave.Error as e:
            raise HTTPException(status_code=400, detail=f"invalid WAV: {e}") from e

        if sampwidth != 2:
            raise HTTPException(
                status_code=400, detail="only 16-bit PCM WAV is supported"
            )
        return channels, sampwidth, framerate


async def _transcribe_request(
    request: Request,
    wav_bytes: bytes,
    *,
    correlation_id: str | None,
    filename: str | None,
) -> JSONResponse:
    from services.common.structured_logging import correlation_context

    with correlation_context(correlation_id) as request_logger:
        # Top-level timing for the request (includes validation, file I/O, model work)
        req_start = time.time()

        if not wav_bytes:
            raise HTTPException(status_code=400, detail="empty request body")

        # Apply audio enhancement if enabled
        correlation_id = request.headers.get(
            "X-Correlation-ID"
        ) or request.query_params.get("correlation_id")
        wav_bytes = await _enhance_audio_if_enabled(wav_bytes, correlation_id)

        channels, _sampwidth, framerate = _extract_audio_metadata(wav_bytes)

    model = _lazy_load_model()
    device = _cfg.faster_whisper.device
    # Write incoming WAV bytes to a temp file and let the model handle I/O
    import tempfile

    # Allow clients to optionally request a translation task by passing
    # the `task=translate` query parameter. We also accept `beam_size` and
    # `language` query params to tune faster-whisper behavior at runtime.
    task = request.query_params.get("task")
    beam_size_q = request.query_params.get("beam_size")
    lang_q = request.query_params.get("language")
    word_ts_q = request.query_params.get("word_timestamps")
    vad_filter_q = request.query_params.get("vad_filter")
    initial_prompt = request.query_params.get("initial_prompt")
    language = lang_q
    include_word_ts = _parse_bool(word_ts_q)
    # default beam size (if not provided) — keep it modest to balance quality/latency
    beam_size = 6
    if beam_size_q:
        try:
            beam_size = int(beam_size_q)
            if beam_size < 1:
                beam_size = 6
        except Exception:
            raise HTTPException(status_code=400, detail="invalid beam_size query param")

    tmp_path = None
    # metadata for response payload
    input_bytes = len(wav_bytes)
    from services.common.correlation import generate_stt_correlation_id

    request_id = request.headers.get("X-Correlation-ID") or request.query_params.get(
        "correlation_id"
    )
    headers_correlation = request.headers.get("X-Correlation-ID")
    correlation_id = (
        correlation_id
        or headers_correlation
        or request.query_params.get("correlation_id")
    )

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
        correlation_id = generate_stt_correlation_id()

    # Bind correlation ID to logger for this request
    from services.common.structured_logging import bind_correlation_id

    request_logger = bind_correlation_id(logger, correlation_id)

    processing_ms: int | None = None
    info: Any = None
    segments_list: list[Any] = []
    text = ""
    segments_out: list[dict[str, Any]] = []

    # Calculate audio duration for metrics (disabled for now)
    # audio_duration = len(wav_bytes) / (channels * sampwidth * framerate) if channels and sampwidth and framerate else 0

    try:
        request_logger.debug(
            "stt.request_received",
            correlation_id=correlation_id,
            input_bytes=input_bytes,
            task=task,
            beam_size=beam_size,
            language=language,
            filename=filename,
            channels=channels,
            sample_rate=framerate,
        )
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name
        # faster-whisper's transcribe signature accepts beam_size and optional
        # task/language parameters. If language is not provided we pass None
        # to allow automatic language detection.
        # Some faster-whisper variants support word-level timestamps; request it
        # only when asked via the query param.
        # Determine whether caller requested word-level timestamps and pass
        # that flag into the model.transcribe call (some faster-whisper
        # implementations accept a word_timestamps=True parameter).
        # measure server-side processing time (model inference portion)
        proc_start = time.time()
        request_logger.info(
            "stt.processing_started",
            correlation_id=correlation_id,
            model=MODEL_NAME,
            device=device,
            input_bytes=input_bytes,
            beam_size=beam_size,
            language=language,
        )
        transcribe_kwargs: dict[str, object] = {"beam_size": beam_size}
        if task == "translate":
            transcribe_kwargs.update({"task": "translate", "language": language})
        elif language is not None:
            transcribe_kwargs["language"] = language
        if include_word_ts:
            transcribe_kwargs["word_timestamps"] = True
        if vad_filter_q and _parse_bool(vad_filter_q):
            transcribe_kwargs["vad_filter"] = True
        if initial_prompt:
            transcribe_kwargs["initial_prompt"] = initial_prompt
        raw_segments, info = model.transcribe(tmp_path, **transcribe_kwargs)
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
        proc_end = time.time()
        processing_ms = int((proc_end - proc_start) * 1000)

        # Track STT metrics (disabled for now)
        # _metrics_collector.track_stt_request(
        #     duration=processing_ms / 1000.0,
        #     audio_duration=audio_duration,
        #     status="success"
        # )

        request_logger.info(
            "stt.request_processed",
            correlation_id=correlation_id,
            processing_ms=processing_ms,
            segments=len(segments_list),
        )
        # Build a combined text and (optionally) include timestamped segments/words
        text = " ".join(getattr(seg, "text", "") for seg in segments_list).strip()
        if include_word_ts:
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
    except Exception as e:
        # Track error metrics (disabled for now)
        # _metrics_collector.track_stt_request(
        #     duration=0,
        #     audio_duration=audio_duration,
        #     status="error"
        # )
        # _metrics_collector.track_error("transcription_error", "stt")

        logger.exception(
            "stt.transcription_error", correlation_id=correlation_id, error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"transcription error: {e}") from e
    finally:
        if tmp_path:
            from contextlib import suppress

            with suppress(Exception):
                os.unlink(tmp_path)

    req_end = time.time()
    total_ms = int((req_end - req_start) * 1000)

    resp: dict[str, Any] = {
        "text": text,
        "duration": getattr(info, "duration", None),
        "language": getattr(info, "language", None),
        "confidence": getattr(info, "language_probability", None),
    }
    if task:
        resp["task"] = task
    # include correlation id if provided by client
    if correlation_id:
        resp["correlation_id"] = correlation_id
    # include server-side processing time (ms)
    try:
        resp["processing_ms"] = processing_ms
        resp["total_ms"] = total_ms
        resp["input_bytes"] = input_bytes
        resp["model"] = MODEL_NAME
        resp["device"] = device
        if request_id:
            resp["request_id"] = request_id
    except NameError:
        # if for some reason processing_ms isn't set, ignore
        pass
    if include_word_ts and segments_out:
        resp["segments"] = segments_out
    # include header with processing time for callers that prefer headers
    headers = {}
    if "processing_ms" in resp:
        headers["X-Processing-Time-ms"] = str(resp["processing_ms"])
    if "total_ms" in resp:
        headers["X-Total-Time-ms"] = str(resp["total_ms"])
    if "input_bytes" in resp:
        headers["X-Input-Bytes"] = str(resp["input_bytes"])
    request_logger.info(
        "stt.response_ready",
        correlation_id=correlation_id,
        text_length=len(resp.get("text", "")),
        processing_ms=resp.get("processing_ms"),
        total_ms=resp.get("total_ms"),
    )
    if resp.get("text"):
        request_logger.debug(
            "stt.transcription_text",
            correlation_id=correlation_id,
            text=resp["text"],
        )
    return JSONResponse(resp, headers=headers)


@app.post("/asr")  # type: ignore[misc]
async def asr(request: Request) -> JSONResponse:
    # Expect raw WAV bytes in the request body
    body = await request.body()
    logger.info(
        "stt.asr_request",
        content_length=len(body),
        correlation_id=request.headers.get("X-Correlation-ID"),
    )
    return await _transcribe_request(
        request,
        body,
        correlation_id=request.headers.get("X-Correlation-ID")
        or request.query_params.get("correlation_id"),
        filename=None,
    )


async def _enhance_audio_if_enabled(
    wav_bytes: bytes, correlation_id: str | None = None
) -> bytes:
    """Apply audio enhancement if enabled.

    Args:
        wav_bytes: WAV format audio
        correlation_id: Optional correlation ID for request tracking

    Returns:
        Enhanced WAV audio or original if enhancement disabled
    """
    # Try remote audio processor first
    if _audio_processor_client is not None:
        try:
            enhanced_wav = await _audio_processor_client.enhance_audio(
                wav_bytes, correlation_id
            )
            if enhanced_wav != wav_bytes:  # Enhancement was applied
                logger.debug(
                    "stt.audio_enhanced_remote",
                    correlation_id=correlation_id,
                    input_size=len(wav_bytes),
                    output_size=len(enhanced_wav),
                )
                return enhanced_wav
        except Exception as exc:
            logger.warning(
                "stt.remote_enhancement_failed",
                correlation_id=correlation_id,
                error=str(exc),
            )

    # Fallback to local enhancement
    if _audio_enhancer is None or not _audio_enhancer.is_enhancement_enabled:
        return wav_bytes

    start_time = time.time()

    try:
        import numpy as np

        from services.common.audio import AudioProcessor

        # Convert WAV to numpy array
        processor = AudioProcessor("stt")
        pcm_data, metadata = processor.wav_to_pcm(wav_bytes)

        # Convert PCM to float32 array
        audio_np = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32)
        audio_np = audio_np / 32768.0  # Normalize to [-1, 1]

        # Apply high-pass filter
        filtered = _audio_enhancer.apply_high_pass_filter(
            audio_np,
            sample_rate=metadata.sample_rate,
        )

        # Apply MetricGAN+ enhancement
        enhanced = _audio_enhancer.enhance_audio(
            filtered,
            sample_rate=metadata.sample_rate,
        )

        # Convert back to int16 PCM
        enhanced_int16 = (enhanced * 32768.0).astype(np.int16)
        enhanced_pcm = enhanced_int16.tobytes()

        # Convert back to WAV
        enhanced_wav = processor.pcm_to_wav(
            enhanced_pcm,
            sample_rate=metadata.sample_rate,
            channels=metadata.channels,
            sample_width=metadata.sample_width,
        )

        # Calculate enhancement duration
        enhancement_duration = (time.time() - start_time) * 1000

        # Log successful enhancement with metrics
        logger.debug(
            "stt.audio_enhanced_local",
            correlation_id=correlation_id,
            input_size=len(wav_bytes),
            output_size=len(enhanced_wav),
            enhancement_duration_ms=enhancement_duration,
            sample_rate=metadata.sample_rate,
            channels=metadata.channels,
        )

        # Update enhancement statistics
        _update_enhancement_stats(success=True, duration_ms=enhancement_duration)

        return enhanced_wav

    except Exception as exc:
        # Calculate error duration
        error_duration = (time.time() - start_time) * 1000

        # Log error with enhanced context
        logger.error(
            "stt.enhancement_error",
            correlation_id=correlation_id,
            error=str(exc),
            error_type=type(exc).__name__,
            input_size=len(wav_bytes),
            error_duration_ms=error_duration,
            fallback_used=True,
        )

        # Update enhancement statistics
        _update_enhancement_stats(
            success=False, duration_ms=error_duration, error=str(exc)
        )

        # Fallback to original audio
        return wav_bytes


@app.post("/transcribe")  # type: ignore[misc]
async def transcribe(request: Request) -> JSONResponse:
    try:
        form = await request.form()
    except ClientDisconnect:
        correlation_id = request.headers.get(
            "X-Correlation-ID"
        ) or request.query_params.get("correlation_id")
        logger.info(
            "stt.client_disconnect",
            correlation_id=correlation_id,
            detail="client closed connection during multipart parse",
        )
        return JSONResponse({"detail": "client disconnected"}, status_code=499)
    upload = form.get("file")
    if upload is None:
        logger.warning(
            "stt.transcribe_missing_file",
            fields=list(form.keys()),
        )
        raise HTTPException(status_code=400, detail="missing 'file' form field")

    metadata_value = form.get("metadata")

    filename: str | None = None
    wav_bytes: bytes
    if isinstance(upload, UploadFile):
        filename = upload.filename
        wav_bytes = await upload.read()
        await upload.close()
    elif isinstance(upload, (bytes, bytearray)):
        wav_bytes = bytes(upload)
    else:
        logger.warning(
            "stt.transcribe_unsupported_payload",
            payload_type=type(upload).__name__,
        )
        raise HTTPException(status_code=400, detail="unsupported file payload")

    # Sample noisy request logs to reduce verbosity in production
    try:
        sample_n = _cfg.telemetry.log_sample_stt_request_n or 25
    except Exception:
        sample_n = 25
    from services.common.structured_logging import should_sample

    if should_sample("stt.transcribe_request", sample_n):
        logger.info(
            "stt.transcribe_request",
            filename=filename,
            input_bytes=len(wav_bytes),
            correlation_id=metadata_value,
        )

    return await _transcribe_request(
        request,
        wav_bytes,
        correlation_id=metadata_value,
        filename=filename,
    )


# Test change
