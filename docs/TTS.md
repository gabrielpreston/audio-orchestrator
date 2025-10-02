# Text-to-Speech (TTS) integration

This project supports a pluggable TTS sidecar. By default the code recognizes `TTS_PROVIDER` and `TTS_URL` environment variables.

Recommended provider: Piper (self-hosted). This repository includes a `piper` service in `docker-compose.yml` that binds to port 7000 inside the compose network and publishes it on the host as `7000:7000`.

Environment variables

- `TTS_PROVIDER` - optional. Known value: `piper`. If set to `piper` and `TTS_URL` is not provided, the code will use the default URL `http://piper:7000/synthesize`.
- `TTS_URL` - optional. Full URL to POST text to for synthesis. If provided, it overrides provider defaults.
- `TTS_AUTH_TOKEN` - optional. If set, sent as the Authorization header value.
- `TTS_SAMPLE_RATE` - optional. Desired sample rate (code will try to request the format; the sidecar must honor it).
- `SAVE_AUDIO_ENABLED` / `SAVE_AUDIO_DIR` / `SAVE_AUDIO_DIR_CONTAINER` - existing options for saving synthesized WAVs; see existing docs.

Using Piper with docker-compose

1. Ensure `.env.docker` has any required model/config entries for Piper if necessary.
2. Start the stack:

```bash
docker-compose up -d piper
```

3. If using the full stack:

```bash
docker-compose up -d
```

Notes

- The TTS sidecar should implement a `/synthesize` POST endpoint that accepts JSON with at least a `text` field and returns WAV bytes with a 2xx status. The project `internal/voice/tts.go` currently posts `{"text":"..."}` to the configured URL and expects WAV bytes in the response.
- The default Piper image used in `docker-compose.yml` is `ghcr.io/rhasspy/piper:latest`. Adjust image and volume mounts to ensure model availability and desired voices.
- For production deployments, secure the sidecar (networking, API keys, TLS) as appropriate.
