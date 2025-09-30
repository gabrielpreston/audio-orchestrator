from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import time
import io
import wave
import os

app = FastAPI(title="discord-voice-lab STT (faster-whisper)")

MODEL_NAME = os.environ.get("FW_MODEL", "small")
# Module-level cached model to avoid repeated loads
_model = None


@app.post("/asr")
async def asr(request: Request):
    # Expect raw WAV bytes in the request body
    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="empty request body")

    # Load model lazily (import heavy deps only when needed)
    try:
        from faster_whisper import WhisperModel
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"faster-whisper import error: {e}")

    # Validate WAV container
    try:
        wf = wave.open(io.BytesIO(body), "rb")
    except wave.Error as e:
        raise HTTPException(status_code=400, detail=f"invalid WAV: {e}")

    # Only support PCM16LE mono 16k/48k etc.
    channels = wf.getnchannels()
    sampwidth = wf.getsampwidth()
    framerate = wf.getframerate()
    nframes = wf.getnframes()

    if sampwidth != 2:
        raise HTTPException(status_code=400, detail="only 16-bit PCM WAV is supported")

    pcm = wf.readframes(nframes)

    # Create model (this will use CPU by default; user can set device env)
    global _model
    device = os.environ.get("FW_DEVICE", "cpu")
    compute_type = os.environ.get("FW_COMPUTE_TYPE")
    # Load model once
    if _model is None:
        try:
            if compute_type:
                _model = WhisperModel(MODEL_NAME, device=device, compute_type=compute_type)
            else:
                _model = WhisperModel(MODEL_NAME, device=device)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"model load error: {e}")
    model = _model

    # Write incoming WAV bytes to a temp file and let the model handle I/O
    import tempfile
    # Allow clients to optionally request a translation task by passing
    # the `task=translate` query parameter. We also accept `beam_size` and
    # `language` query params to tune faster-whisper behavior at runtime.
    task = request.query_params.get('task')
    beam_size_q = request.query_params.get('beam_size')
    lang_q = request.query_params.get('language')
    word_ts_q = request.query_params.get('word_timestamps')
    # Accept a correlation id from the client (header or query param) and
    # echo it back in the response so callers can correlate requests.
    correlation_id = request.headers.get('X-Correlation-ID') or request.query_params.get('correlation_id')
    # default beam size (if not provided) — keep it modest to balance quality/latency
    beam_size = 5
    if beam_size_q:
        try:
            beam_size = int(beam_size_q)
            if beam_size < 1:
                beam_size = 5
        except Exception:
            raise HTTPException(status_code=400, detail="invalid beam_size query param")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(body)
            tmp_path = tmp.name
        # faster-whisper's transcribe signature accepts beam_size and optional
        # task/language parameters. If language is not provided we pass None
        # to allow automatic language detection.
        # Some faster-whisper variants support word-level timestamps; request it
        # only when asked via the query param.
        # Determine whether caller requested word-level timestamps and pass
        # that flag into the model.transcribe call (some faster-whisper
        # implementations accept a word_timestamps=True parameter).
        include_word_ts = False
        if word_ts_q:
            lv = str(word_ts_q).lower()
            if lv in ('1', 'true', 'yes'):
                include_word_ts = True

        # measure server-side processing time
        proc_start = time.time()
        if task == 'translate':
            if include_word_ts:
                segments, info = model.transcribe(tmp_path, beam_size=beam_size, task='translate', language=lang_q, word_timestamps=True)
            else:
                segments, info = model.transcribe(tmp_path, beam_size=beam_size, task='translate', language=lang_q)
        else:
            if include_word_ts:
                segments, info = model.transcribe(tmp_path, beam_size=beam_size, language=lang_q, word_timestamps=True)
            else:
                segments, info = model.transcribe(tmp_path, beam_size=beam_size, language=lang_q)
        # faster-whisper may return a generator/iterator for segments; convert
        # to a list so we can iterate it multiple times (build text and
        # optionally include word-level timestamps).
        try:
            segments = list(segments)
        except TypeError:
            # if segments is already a list, this will raise TypeError from list()
            # in some unlikely cases; ignore and continue with the original object.
            pass
        proc_end = time.time()
        processing_ms = int((proc_end - proc_start) * 1000)
        # Build a combined text and (optionally) include timestamped segments/words
        text = " ".join([seg.text for seg in segments])
        segments_out = []
        include_word_ts = False
        if word_ts_q:
            lv = str(word_ts_q).lower()
            if lv in ('1', 'true', 'yes'):
                include_word_ts = True
        if include_word_ts:
            for seg in segments:
                segdict = {
                    "start": getattr(seg, 'start', None),
                    "end": getattr(seg, 'end', None),
                    "text": getattr(seg, 'text', ""),
                }
                # some faster-whisper variants expose `words` on segments when
                # word timestamps are requested; include them if present.
                words = getattr(seg, 'words', None)
                if words:
                    segdict['words'] = []
                    for w in words:
                        # word objects typically have text/start/end attributes
                        segdict['words'].append({
                            'word': getattr(w, 'word', None) or getattr(w, 'text', None),
                            'start': getattr(w, 'start', None),
                            'end': getattr(w, 'end', None),
                        })
                segments_out.append(segdict)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"transcription error: {e}")
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    resp = {"text": text, "duration": info.duration}
    if task:
        resp["task"] = task
    # include correlation id if provided by client
    if correlation_id:
        resp["correlation_id"] = correlation_id
    # include server-side processing time (ms)
    try:
        resp["processing_ms"] = processing_ms
    except NameError:
        # if for some reason processing_ms isn't set, ignore
        pass
    if include_word_ts and segments_out:
        resp["segments"] = segments_out
    # include header with processing time for callers that prefer headers
    headers = {}
    if "processing_ms" in resp:
        headers["X-Processing-Time-ms"] = str(resp["processing_ms"])
    return JSONResponse(resp, headers=headers)
