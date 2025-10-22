# Text-to-Speech Service (Piper)

The TTS container wraps [Piper](https://github.com/rhasspy/piper) to synthesize
neural speech for orchestrator responses. It loads an ONNX voice at startup,
exposes a FastAPI interface, and streams generated WAV audio directly to
callers.

## Endpoints

-  `GET /voices` — enumerate available speakers included in the active Piper
  model.
-  `POST /synthesize` — accept SSML or plain text and stream an `audio/wav`
  response body for immediate playback.
-  `GET /metrics` — Prometheus counters and histograms covering request volume,
  synthesis latency, audio duration, and payload size.

## Configuration

Copy the `./services/tts/.env.service` block from `.env.sample`, populate the
required fields, and keep shared logging defaults in `.env.common`.

| Variable | Purpose |
| --- | --- |
| `PORT` | HTTP port exposed by the container (default `7000`). |
| `TTS_MODEL_PATH` | Filesystem path to the Piper ONNX model. |
| `TTS_MODEL_CONFIG_PATH` | Matching Piper JSON metadata file. |
| `TTS_DEFAULT_VOICE` | Optional speaker name used when requests omit one. |
| `TTS_MAX_TEXT_LENGTH` | Hard limit on accepted SSML/text characters. |
| `TTS_MAX_CONCURRENCY` | Concurrent synthesis jobs allowed before returning `429`. |
| `TTS_RATE_LIMIT_PER_MINUTE` | Token bucket limit applied per client IP. |
| `TTS_AUTH_TOKEN` | Bearer token required for non-public deployments. |
| `TTS_LENGTH_SCALE` | Time-stretch factor applied to generated speech. |
| `TTS_NOISE_SCALE` | Controls sampling variance (lower is more deterministic). |
| `TTS_NOISE_W` | Adjusts breathiness for unvoiced phonemes. |

The Piper runtime caches loaded voices under `/app/models`. Mount a host
`./services/models/piper/` directory with the desired voices and reference them using the
paths above.

## Orchestrator integration

The orchestrator forwards SSML responses to `POST /synthesize`, then base64
encodes the streamed WAV payload when replying to the Discord bridge. No signed
URLs or cached downloads are generated, keeping synthesized speech ephemeral.

## Local development tips

-  Run `make run` to build and start the TTS container alongside the Discord,
  STT, and orchestrator services.
-  Use `make logs SERVICE=tts` to follow synthesis output and monitor rate-limit
  or concurrency rejections.
-  Visit `http://localhost:7000/docs` once the container is running to exercise
  the OpenAPI interface and sanity-check voice settings.
