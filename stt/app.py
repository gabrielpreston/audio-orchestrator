from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
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
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(body)
            tmp_path = tmp.name
        segments, info = model.transcribe(tmp_path, beam_size=5, language=None)
        text = " ".join([seg.text for seg in segments])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"transcription error: {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    return JSONResponse({"text": text, "duration": info.duration})
