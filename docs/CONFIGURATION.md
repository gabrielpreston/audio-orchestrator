# Configuration Reference

This document is the canonical reference for environment variables used by the project. It focuses on variables that are actually read by code (Go and Python services) and provides: name, whether required, default (if any), primary files that reference the variable, and a short purpose note.

Keep this file up-to-date when adding new runtime flags. For machine-readable manifests or an `.env.sample` update, see the "Next steps" section at the end.

---

## How to read this table

- Variable: environment variable name.
- Required: whether code treats this as required at startup ("Yes") or optional ("No").
- Default: default value used by code when present in source (if any).


Minimal example `.env.local` snippet:

```env
# LLM / model
OPENAI_BASE_URL=http://127.0.0.1:8000/v1
OPENAI_API_KEY=changeme
OPENAI_MODEL=gpt-5
OPENAI_FALLBACK_MODEL=local
GPT5_ENABLED=true

# Rate/cost guardrails (optional)
LLM_MAX_TOKENS=4000
LLM_MAX_COST_PER_MINUTE_USD=1.00
LLM_USE_FUNCTION_CALLS=true
```

Notes:
- `OPENAI_BASE_URL` must expose an OpenAI-compatible REST shape (`/v1/chat/completions`).
- `OPENAI_MODEL` may be a remote provider model name (e.g., `gpt-5`) or a local server alias that resolves to `gpt-5` semantics.
- `OPENAI_FALLBACK_MODEL` should point to a smaller local model to reduce cost and latency when GPT-5 is unavailable.

## 3. Guardrails & Cost Controls

Enabling GPT-5 universally increases cost and may impact latency. Add runtime guardrails:

- Token limits: `LLM_MAX_TOKENS` (default 4k) and per-request `max_tokens` enforced by the client.
- Rate limiting: enforce `LLM_MAX_COST_PER_MINUTE_USD` and deny or queue requests when exceeded.
- Usage tiers: allow non-critical or dev sessions to automatically use `OPENAI_FALLBACK_MODEL`.
- Confirmation gates: for expensive multi-step plans (e.g., large repo-wide refactors), require explicit human confirmation before running full GPT-5 plan.

## 4. Secrets Management

- Keep `OPENAI_API_KEY` and any provider keys out of source control. Use `git-crypt`, `sops`, or your cloud secret manager in prod.

- For local dev, use `.env.local` that is gitignored. Example `.gitignore` entry:

```gitignore
.env.local
```

- Avoid logging full request payloads that contain sensitive prompts or tokens. Mask keys and redact PII in logs.

## 5. Rollout Strategy

1. Start by setting `OPENAI_MODEL=gpt-5` in a non-production environment with `OPENAI_FALLBACK_MODEL` configured.
2. Run smoke tests and measure cost/latency for common flows (transcribe -> plan -> edits).
3. Add CI checks to ensure `GPT5_ENABLED` and rate-limit env vars are present in production deploy manifests.
4. Gradually enable GPT-5 for more sessions once confidence and cost controls are in place.

---

## 6. Advanced / Optional Settings

- `LLM_DEFAULT_TEMPERATURE` — default temperature for chat completions (e.g., `0.2` for deterministic edits).
- `LLM_LOG_PROMPTS` — whether to persist prompts (default `false`). Only enable with strict access controls.
- `LLM_METRICS_EXPORT` — push usage metrics to Prometheus or external billing monitor.

---

## TODO: Secrets & Advanced Settings

> ✅ TODO: Add targeted guidance for secrets management and optional tuning flags. This section is intentionally condensed — I can expand it into separate sub-sections if you want more detail.

---

## Implemented environment variables (scanned from code)

Below is a consolidated, deduplicated list of environment variables that are referenced by the codebase (Go services under `internal/` and `cmd/`, and the Python services under `services/`). For each variable the most relevant file(s) are listed along with a short note on purpose.

- `DISCORD_BOT_TOKEN` — `cmd/bot/main.go`
  - Required. Discord bot authentication token.

- `GUILD_ID`, `VOICE_CHANNEL_ID` — `cmd/bot/main.go`
  - Optional auto-join target used at startup.

- `ALLOWED_USER_IDS` — `cmd/bot/main.go`
  - Comma-separated allow-list; when set the Processor accepts audio only from these user IDs.

- `DETAILED_EVENTS` — `cmd/bot/main.go`
  - Comma-separated event names which should always produce detailed dumps regardless of log level.

- `MCP_SERVER_URL`, `MCP_SERVICE_NAME`, `BOT_EXTERNAL_URL` — `cmd/bot/main.go`, `internal/mcp/registrar.go`, `services/llm/app.py`
  - Service registry / MCP configuration used for registration and discovery.

- `WHISPER_URL`, `WHISPER_TRANSLATE`, `STT_BEAM_SIZE`, `STT_LANGUAGE`, `STT_WORD_TIMESTAMPS`, `WHISPER_TIMEOUT_MS`, `TEXT_FORWARD_URL` — `internal/voice/whisper_client.go`
  - STT endpoint, query-params and timeouts. `WHISPER_URL` is required for posting decoded PCM to the STT service.

- `ORCHESTRATOR_URL`, `ORCH_AUTH_TOKEN`, `ORCH_TIMEOUT_MS` — `internal/voice/orchestrator.go`, `internal/voice/processor.go`, `services/llm/app.py`
  - Orchestrator (LLM) endpoint, optional bearer token, and timeouts used when forwarding aggregated transcripts.

- `TTS_PROVIDER`, `TTS_URL`, `TTS_AUTH_TOKEN` — `internal/voice/processor_helpers.go`, docs/TTS.md
  - TTS integration settings. `TTS_URL` overrides provider defaults; `TTS_AUTH_TOKEN` is sent as an Authorization header when provided.

- `SAVE_AUDIO_ENABLED`, `SAVE_AUDIO_DIR`, `SAVE_AUDIO_DIR_CONTAINER`, `SAVE_AUDIO_DIR_HOST`, `SAVE_AUDIO_RETENTION_HOURS`, `SAVE_AUDIO_CLEAN_INTERVAL_MIN`, `SAVE_AUDIO_MAX_FILES`, `SIDECAR_LOCKING` — `internal/voice/processor_helpers.go`, `internal/voice/processor.go`, `internal/voice/sidecar.go`, .env.sample, .env.docker
  - Controls saving decoded WAVs and JSON sidecars and the retention/cleanup behavior for saved audio.

- `MIN_FLUSH_MS`, `FLUSH_TIMEOUT_MS`, `MAX_ACCUM_MS`, `VAD_RMS_THRESHOLD`, `FLUSH_ON_MIN`, `SILENCE_TIMEOUT_MS`, `TRANSCRIPT_AGG_MS`, `WAKE_PHRASE_WINDOW_S`, `WAKE_PHRASES` — `internal/voice/processor.go`, `internal/voice/processor_helpers.go`
  - Audio accumulation / VAD / flush tuning knobs and wake-phrase detection parameters.

- `LLAMA_BIN`, `LLAMA_MODEL_PATH`, `PORT` — `services/llm/app.py`, `services/mcp-server/main.go`
  - Local LLM adapter binary and model path; `PORT` is used by the Python services when run standalone.

- `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_FALLBACK_MODEL`, `GPT5_ENABLED`, `LLM_MAX_TOKENS`, `LLM_MAX_COST_PER_MINUTE_USD`, `LLM_USE_FUNCTION_CALLS`, `LLM_DEFAULT_TEMPERATURE`, `LLM_LOG_PROMPTS`, `LLM_METRICS_EXPORT` — docs references and orchestrator/LLM client config
  - LLM provider and runtime guardrail settings. These are referenced in docs and used by LLM/orchestrator-related code paths; keep them configured when integrating with remote OpenAI-compatible endpoints.

- `FW_MODEL`, `FW_DEVICE`, `FW_COMPUTE_TYPE` — `services/stt/app.py`
  - Fast-whisper model selection and device/compute-type tuning for the STT service.

- `LOG_LEVEL`, `PAYLOAD_MAX_BYTES`, `REDACT_LARGE_BYTES` — `internal/logging/logging.go`, `.github/copilot-instructions.md`, and various entrypoints
  - Logging and debug controls used across services.

Notes:

- This list was generated by scanning for direct env accesses (e.g., `os.Getenv`, `os.LookupEnv`, `os.environ.get`, etc.) across Go and Python sources. It includes variables referenced in `.env.sample` / `.env.docker` that the code uses.

- If you'd like, I can:
  - Split this appendix into a dedicated `docs/ENV_VARS.md` and add machine-readable output (JSON/TOML) for automation, or
  - Update `.env.sample` to include any missing example values for implemented vars.
