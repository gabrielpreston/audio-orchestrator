# Development Guide

## Purpose
This guide explains the *day-to-day developer workflow* for contributing to this project. It focuses on practical details — how to run services locally, debug issues, and safely extend the system — beyond the conceptual overview provided in `ONBOARDING.md`.

---

## 1. Local Environment Setup
Completed checklist (developer-friendly)

1. Prerequisites

- Go 1.22+ (recommended)
- Python 3.10+ for STT/TTS microservices
- ffmpeg (for PCM/WAV conversions)
- `make` and standard build tools (git, curl)
- Optional: `llama.cpp` or a local OpenAI-compatible LLM server (see below)

2. Quick setup (example)

```bash
# clone
git clone <repo> && cd discord-voice-lab

# create a local env file
cp .env.sample .env.local
# edit .env.local to set your Discord token and LLM endpoints (see CONFIGURATION.md)

# start STT (in a separate terminal)
cd stt && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn stt.app:app --reload --host 127.0.0.1 --port 9000

# start TTS (piper) if you use it (follow Piper README)

# start a local LLM server (examples in next section) and then run the bot
make bot
```

3. Local LLM (OpenAI-compatible) options

Use one of the following depending on your hardware and needs:

- Remote OpenAI provider: set `OPENAI_BASE_URL` to the provider URL and `OPENAI_MODEL=gpt-5`.
- Local llama.cpp / llama-cpp-python server that implements the OpenAI API shape (recommended for offline dev)
	- Example: run `llama.cpp` server or a minimal adapter such as `server.py` that wraps llama-cpp-python and exposes `/v1/chat/completions`.
- A smaller local model for dev: set `OPENAI_FALLBACK_MODEL=local` and point `OPENAI_BASE_URL` to your local server.

Notes:
- For development, prefer an OpenAI-compatible local server to test `gpt-5` integration without incurring remote costs.
- If you don't have GPT-5 access, set `OPENAI_MODEL` to your fallback and keep `OPENAI_FALLBACK_MODEL` configured.

---

## 2. Recommended Dev Commands
Common targets (example `Makefile` targets expected in repo)

- `make bot` — build & run the Discord bot (local dev)
- `make stt` — start the STT service
- `make tts` — start Piper or TTS service
- `make llm-server` — start local OpenAI-compatible LLM server
- `make test` — run unit tests
- `make smoke` — run an end-to-end smoke test (transcribe -> reply)

If a `Makefile` is not present, replace with the suggested commands above or add a small `Makefile` to the repo.

---

## 3. Running Components in Isolation
Guidance

- Run STT: curl the `/asr` endpoint with a WAV file to validate expected transcript shape.
- Run LLM: POST to `/v1/chat/completions` on your `OPENAI_BASE_URL` with a small prompt to validate model responses.
- Run TTS: POST to the TTS endpoint with a short string and verify returned WAV.
- Run Bot: set `DISCORD_BOT_TOKEN` and `VOICE_CHANNEL_ID` in `.env.local`, then `make bot` or `go run ./bot/cmd/bot`.

Tip: use `ngrok` or `socat` to expose local endpoints for mobile/remote testing when needed, but avoid exposing secrets.

---

## 4. Debugging & Troubleshooting
Practical tips

- No audio in Discord: ensure the bot did not self-deafen and `VoiceSpeakingUpdate` mapping is present.
- STT timeouts: increase `RECORD_SECONDS` or check `WHISPER_URL` health.
- LLM unexpected outputs: verify `OPENAI_MODEL` and `OPENAI_BASE_URL`; run a small prompt against the model directly to inspect tokens and temperature.
- High cost or slow responses: temporarily set `OPENAI_MODEL` to `OPENAI_FALLBACK_MODEL` and reduce `LLM_MAX_TOKENS`.

Debugging `gpt-5` specific issues

- If your local LLM adapter does not support `gpt-5`, the client will fall back to `OPENAI_FALLBACK_MODEL` when `GPT5_ENABLED=false` or on failures.
- Add verbose logging around LLM client calls (ensure `LLM_LOG_PROMPTS` is disabled in prod).

---

## 5. Testing & QA
Testing guidance

- Unit tests: place under `./internal/...` packages as usual for Go; run `go test ./...`.
- Integration tests: provide a lightweight `tests/e2e` harness that spins up STT/LLM/TTS mocks (or real local servers) and runs sample flows.
- LLM mocking: create a deterministic mock service that returns canned chat completions to make tests stable and cheap.

Example LLM mock (Python Flask/FastAPI)

```python
from fastapi import FastAPI
app = FastAPI()

@app.post('/v1/chat/completions')
async def chat(req: dict):
	return {
		'id': 'mock-1',
		'object': 'chat.completion',
		'choices': [{'message': {'role': 'assistant', 'content': 'ok'}}],
		'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}
	}

# run: uvicorn mock:app --port 8001
```

Edge cases and test tips

- Test fallback behavior by configuring `OPENAI_BASE_URL` to an invalid URL and asserting the bot switches to `OPENAI_FALLBACK_MODEL`.
- Add tests that validate guardrail enforcement (e.g., request denied when `LLM_MAX_COST_PER_MINUTE_USD` exceeded).
