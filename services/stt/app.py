import io
import os
import time
import wave
from collections.abc import Iterable
from typing import Any, cast

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile
from starlette.requests import ClientDisconnect

from services.common.debug import get_debug_manager
from services.common.logging import configure_logging, get_logger

app = FastAPI(title="discord-voice-lab STT (faster-whisper)")

MODEL_NAME = os.environ.get("FW_MODEL", "small")
# Module-level cached model to avoid repeated loads
_model: Any = None
# Debug manager for saving debug files
_debug_manager = get_debug_manager("stt")


def _env_bool(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes", "on"}


configure_logging(
    os.getenv("LOG_LEVEL", "INFO"),
    json_logs=_env_bool("LOG_JSON", "true"),
    service_name="stt",
)
logger = get_logger(__name__, service_name="stt")


@app.on_event("startup")
async def _warm_model() -> None:
    """Ensure the Whisper model is loaded before serving traffic."""

    try:
        _lazy_load_model()
        logger.info("stt.model_preloaded", model_name=MODEL_NAME)
    except HTTPException:
        # _lazy_load_model already logged and raised; propagate to fail fast.
        raise
    except Exception as exc:
        logger.exception(
            "stt.model_preload_failed", model_name=MODEL_NAME, error=str(exc)
        )
        raise


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

    device = os.environ.get("FW_DEVICE", "cpu")
    compute_type = os.environ.get("FW_COMPUTE_TYPE")
    try:
        if compute_type:
            _model = WhisperModel(MODEL_NAME, device=device, compute_type=compute_type)
        else:
            _model = WhisperModel(MODEL_NAME, device=device)
        logger.info(
            "stt.model_loaded",
            model_name=MODEL_NAME,
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
    # Top-level timing for the request (includes validation, file I/O, model work)
    req_start = time.time()

    if not wav_bytes:
        raise HTTPException(status_code=400, detail="empty request body")

    channels, sampwidth, framerate = _extract_audio_metadata(wav_bytes)

    model = _lazy_load_model()
    device = os.environ.get("FW_DEVICE", "cpu")

    # Write incoming WAV bytes to a temp file and let the model handle I/O
    import tempfile

    # Allow clients to optionally request a translation task by passing
    # the `task=translate` query parameter. We also accept `beam_size` and
    # `language` query params to tune faster-whisper behavior at runtime.
    task = request.query_params.get("task")
    beam_size_q = request.query_params.get("beam_size")
    lang_q = request.query_params.get("language")
    word_ts_q = request.query_params.get("word_timestamps")
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

    # Generate STT correlation ID if none provided
    if not correlation_id:
        correlation_id = generate_stt_correlation_id()
    processing_ms: int | None = None
    info: Any = None
    segments_list: list[Any] = []
    text = ""
    segments_out: list[dict[str, Any]] = []
    try:
        logger.debug(
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
        transcribe_kwargs: dict[str, object] = {"beam_size": beam_size}
        if task == "translate":
            transcribe_kwargs.update({"task": "translate", "language": language})
        elif language is not None:
            transcribe_kwargs["language"] = language
        if include_word_ts:
            transcribe_kwargs["word_timestamps"] = True
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
        logger.info(
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

    # Save debug data for transcription
    _save_debug_transcription(
        correlation_id=correlation_id,
        wav_bytes=wav_bytes,
        text=text,
        segments=segments_out,
        processing_ms=processing_ms,
        total_ms=total_ms,
        input_bytes=input_bytes,
        channels=channels,
        framerate=framerate,
        language=getattr(info, "language", None),
        confidence=getattr(info, "language_probability", None),
        task=task,
        beam_size=beam_size,
        filename=filename,
    )

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
    logger.debug(
        "stt.response_ready",
        correlation_id=correlation_id,
        text_length=len(resp.get("text", "")),
        processing_ms=resp.get("processing_ms"),
        total_ms=resp.get("total_ms"),
    )
    if resp.get("text"):
        logger.debug(
            "stt.transcription_text",
            correlation_id=correlation_id,
            text=resp["text"],
        )
    return JSONResponse(resp, headers=headers)


@app.post("/asr")
async def asr(request: Request):
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


@app.post("/transcribe")
async def transcribe(request: Request):
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


def _save_debug_transcription(
    correlation_id: str | None,
    wav_bytes: bytes,
    text: str,
    segments: list[dict[str, Any]],
    processing_ms: int | None,
    total_ms: int,
    input_bytes: int,
    channels: int,
    framerate: int,
    language: str | None,
    confidence: float | None,
    task: str | None,
    beam_size: int,
    filename: str | None,
) -> None:
    """Save debug data for transcription requests."""
    if not correlation_id:
        return

    try:
        # Save incoming audio
        _debug_manager.save_audio_file(
            correlation_id=correlation_id,
            audio_data=wav_bytes,
            filename_prefix="input_audio",
            sample_rate=framerate,
        )

        # Save transcription result
        _debug_manager.save_text_file(
            correlation_id=correlation_id,
            content=f"Transcription Result:\n{text}\n\nLanguage: {language}\nConfidence: {confidence}",
            filename_prefix="transcription_result",
        )

        # Save detailed segments if available
        if segments:
            segments_content = "Transcription Segments:\n"
            for i, segment in enumerate(segments):
                segments_content += f"\nSegment {i+1}:\n"
                segments_content += f"  Start: {segment.get('start', 'N/A')}\n"
                segments_content += f"  End: {segment.get('end', 'N/A')}\n"
                segments_content += f"  Text: {segment.get('text', '')}\n"
                if "words" in segment:
                    segments_content += f"  Words: {segment['words']}\n"

            _debug_manager.save_text_file(
                correlation_id=correlation_id,
                content=segments_content,
                filename_prefix="transcription_segments",
            )

        # Save processing metadata
        _debug_manager.save_json_file(
            correlation_id=correlation_id,
            data={
                "filename": filename,
                "input_bytes": input_bytes,
                "channels": channels,
                "sample_rate": framerate,
                "language": language,
                "confidence": confidence,
                "task": task,
                "beam_size": beam_size,
                "processing_ms": processing_ms,
                "total_ms": total_ms,
                "text_length": len(text),
                "segments_count": len(segments),
                "model_name": MODEL_NAME,
                "device": os.environ.get("FW_DEVICE", "cpu"),
            },
            filename_prefix="transcription_metadata",
        )

        # Save manifest
        files = {}
        audio_file = _debug_manager.save_audio_file(
            correlation_id=correlation_id,
            audio_data=wav_bytes,
            filename_prefix="input_audio",
            sample_rate=framerate,
        )
        if audio_file:
            files["input_audio"] = str(audio_file)

        _debug_manager.save_manifest(
            correlation_id=correlation_id,
            metadata={
                "service": "stt",
                "event": "transcription_complete",
                "filename": filename,
                "language": language,
            },
            files=files,
            stats={
                "input_bytes": input_bytes,
                "processing_ms": processing_ms or 0,
                "total_ms": total_ms,
                "text_length": len(text),
                "segments_count": len(segments),
            },
        )

    except Exception as exc:
        logger.error(
            "stt.debug_transcription_save_failed",
            correlation_id=correlation_id,
            error=str(exc),
        )
