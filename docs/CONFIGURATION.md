# Configuration Reference [PLACEHOLDER]

## Purpose
This document centralizes all environment variables, configuration knobs, and runtime options. It’s the canonical reference for setting up `.env.local` and understanding how configuration influences system behavior.

---

## 1. Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_BOT_TOKEN` | ✅ Yes | – | Discord bot authentication token |
| `GUILD_ID` | ✅ Yes | – | Discord server ID for auto-join |
| `VOICE_CHANNEL_ID` | ✅ Yes | – | Voice channel ID for auto-join |
| `OPENAI_BASE_URL` | ✅ Yes | – | LLM endpoint base URL (OpenAI-compatible; e.g. local llama.cpp server or remote API) |
| `OPENAI_API_KEY` | ✅ Yes | – | API key for LLM or service token for local OpenAI-shaped servers |
| `OPENAI_MODEL` | ✅ Yes | `gpt-5` | Model name. To enable GPT-5 for all clients set this to `gpt-5`. Keep a fallback model for development (see `OPENAI_FALLBACK_MODEL`). |
| `OPENAI_FALLBACK_MODEL` | Optional | `local` | Fallback model name to use when `gpt-5` is unavailable (development/local inference). |
| `GPT5_ENABLED` | Optional | `true` | Toggle to explicitly enable GPT-5 for all clients. Set to `false` to disable and force fallbacks. |
| `WHISPER_URL` | ✅ Yes | – | STT service endpoint |
| `WHISPER_TRANSLATE` | Optional | `false` | When set to `true` (or `1`), the audio sent to `WHISPER_URL` will include a `task=translate` query parameter requesting translation into English when supported by the STT service. |
| `TEXT_FORWARD_URL` | Optional | – | If set, recognized text (JSON) will be POSTed to this URL for downstream processing (best-effort). Payload: {"user_id","ssrc","transcript"}. |
| `ORCHESTRATOR_URL` | Optional | – | If set, aggregated transcripts will be POSTed to this URL for orchestration/planning. Payload: {"user_id","ssrc","transcript","source"}. |
| `ORCH_AUTH_TOKEN` | Optional | – | Optional bearer token sent in the Authorization header when calling `ORCHESTRATOR_URL`. |
| `TTS_URL` | Optional | – | If set, the orchestrator's `reply` field (if present) will be POSTed to this URL as {"text":"..."} and the returned audio will be saved to `SAVE_AUDIO_DIR` (if configured). |
| `TTS_AUTH_TOKEN` | Optional | – | Optional bearer token for `TTS_URL`. If absent, `ORCH_AUTH_TOKEN` will be used for TTS requests as a fallback. |

Notes:
- When `ORCHESTRATOR_URL` is configured, the processor will POST aggregated transcripts and expect an optional JSON response with a `reply` string field. If `reply` is present and `TTS_URL` is configured, the reply will be synthesized and saved as a WAV sidecar.
- The TTS integration is best-effort: failures to call the TTS service are logged but do not interrupt transcription.
| `TTS_URL` | ✅ Yes | – | TTS service endpoint |
| `RECORD_SECONDS` | Optional | `8` | Audio chunk size before transcription |

> ✅ Completed: Added GPT-5 guidance and safety/rollout variables.

---

## 2. Enabling GPT-5 for all clients

Recommendation: to make GPT-5 the default model used by the bot and all internal clients, set `OPENAI_MODEL=gpt-5` in your `.env.local` (or environment) and ensure `GPT5_ENABLED=true`.

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

```
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

## 2. Secrets Management
> ✅ TODO: Add instructions for handling secrets securely in development and production.

---

## 3. Advanced Settings
> ✅ TODO: Cover optional tuning knobs and runtime flags.
