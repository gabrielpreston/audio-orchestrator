# Project Overview

**Goal:** A self-hosted Discord voice assistant that can join a voice channel, listen to speakers, transcribe, reason with a local LLM, synthesize a spoken reply, and play it back in the same channel—end-to-end on your own hardware (WSL2 for dev, Synology NAS for prod).

**Why self-hosted:** Privacy, cost control, and resilience. All speech, text, and generations stay on machines you control. The system is designed so each stage can be swapped (e.g., different STT, TTS, or LLM) without rewriting the bot.

# System Architecture (high level)

```
Discord Voice  →  Bot (Go)
    Opus            |
                    |─[Decode Opus → PCM]────────┐
                    |                             v
                    |                      Per-User Buffer (~N s)
                    |                             |
                    |                             v
                    |       [PCM → WAV] → STT (FastAPI/faster-whisper) → text
                    |                                                   |
                    |                                                   v
                    |                     LLM (llama.cpp server, OpenAI API shape)
                    |                                                   |
                    |                                                   v
                    |       TTS (Piper server) ← text → [WAV → PCM → Opus]
                    |                                                   |
                    └──────────────────────────────────────────────→ Discord playback
```

**Key processes**

* **Bot (Go, `discordgo`, `gopus`)**
  Subscribes to voice, decodes incoming Opus to PCM, batches per speaker, and orchestrates STT → LLM → TTS. Re-encodes the TTS WAV back into Opus and sends to the channel.
* **STT microservice (Python/FastAPI + faster-whisper)**
  Simple HTTP endpoint `POST /asr` that takes WAV → returns text.
* **LLM server (llama.cpp or llama-cpp-python)**
  Exposes OpenAI-compatible endpoints (e.g., `/v1/chat/completions`) so the bot can call it like a hosted model.
* **TTS server (Piper)**
  Exposes HTTP API to synthesize speech WAV from reply text.

# Guiding Principles

1. **Clarity first, then speed.**
   Code is written for readability. Comments explain *what*, *why*, and *how to extend safely*.
2. **Loose coupling via narrow interfaces.**
   The bot only knows that STT/LLM/TTS speak HTTP (or simple Go interfaces). Swap implementations without rippling changes.
3. **Single responsibility per package.**

   * `internal/voice`: Discord audio specifics + voice pipeline.
   * `internal/stt`, `internal/llm`, `internal/tts`: tiny HTTP clients.
   * `internal/audio`: WAV/PCM shims.
   * `internal/config`: env parsing & validation.
4. **Fail fast, fail loud.**
   Missing env or handler mismatches abort startup with actionable errors.
5. **Edge-aware, best-effort streaming.**
   Voice is lossy: decode/encode failures or empty results shouldn’t crash the loop. We contain errors to the current turn.
6. **Self-hosting as a first-class constraint.**
   Everything runs locally, dev→prod parity (WSL2 → Docker on Synology).
7. **Minimal privileged intents.**
   The bot only asks Discord for what it needs (Guilds + VoiceState).

# Key Design Strategies

## 1) Per-Speaker Batching

* **Why:** STT accuracy and prompt coherence improve with small contiguous chunks per speaker.
* **How:** We maintain a `userID → recorder` with a timer (e.g., `ChunkSeconds=3–8`). When it fires, we flush PCM → STT → LLM → TTS.
* **Trade-off:** Lower values reduce latency but can increase STT overhead; higher values improve accuracy but feel slower. Tunable via `RECORD_SECONDS`.

## 2) Event-driven SSRC Mapping

* **Why:** Incoming voice packets carry SSRC, not userID.
* **How:** We listen for `VoiceSpeakingUpdate` events and maintain `SSRC → userID`. This lets us attribute audio to the right buffers.

## 3) HTTP Edge Services via Tiny Clients

* **Why:** Keep the bot small and testable.
* **How:** Each of STT/LLM/TTS implements a tiny interface:

  * `STT.TranscribeWAV(ctx, wav []byte) (string, error)`
  * `LLM.Chat(ctx, username, text string) (string, error)`
  * `TTS.Synthesize(ctx, text string) ([]byte, error)`

Swapping engines (e.g., Whisper CPP, NVIDIA Riva, different LLM, or another TTS) is localized to one file.

## 4) OpenAI-compatible LLM API

* **Why:** **Portability.** Using the OpenAI Chat Completions shape means any compliant backend (local llama.cpp server, text-generation-webui adapters, etc.) just works.

## 5) Operational Safety

* The bot **does not** self-deafen (or it wouldn’t receive audio).
* The bot toggles `Speaking(true/false)` when sending audio, keeping Discord state clean.
* PCM/Opus conversion uses well-understood, conservative settings (48kHz stereo, 20ms frames).

# Developer Workflow

## Local Dev (WSL2)

* **Prereqs:** Go 1.22+, Python venvs for STT, Piper for TTS, llama.cpp server for LLM.
* **Services:**

  * LLM: `llama-server` or `llama_cpp.server` on `127.0.0.1:8000`
  * STT: `uvicorn ...:app` on `127.0.0.1:9000`
  * TTS: `piper_server` on `127.0.0.1:8080`
* **Bot:** `source bot/.env.local && go run ./bot/cmd/bot` (or `make bot`).

## Config (env)

```
DISCORD_BOT_TOKEN=...
GUILD_ID=...                 # voice auto-join
VOICE_CHANNEL_ID=...

OPENAI_BASE_URL=http://127.0.0.1:8000/v1
OPENAI_API_KEY=local-key
OPENAI_MODEL=local

WHISPER_URL=http://127.0.0.1:9000/asr
TTS_URL=http://127.0.0.1:8080/api/tts

RECORD_SECONDS=8
```

## Docker / Synology

* Each service gets its own container; the bot depends on the three endpoints being reachable on the NAS network.
* Persist model files via volumes (`./models`, voices directory for Piper).
* Pin CPU/memory as needed; llama.cpp benefits from CPU AVX/AVX2 or GPU builds if available.

# Performance Tuning & Latency

* **RECORD_SECONDS**: primary lever (3–8s common).
* **Opus bitrate**: we default to 64 kbps; safe and predictable.
* **Model choice**: a small instruct model (e.g., 3–7B Q* GGUF) gives good latency; larger models will slow replies.
* **STT model**: faster-whisper “small”/“base” for speed; “medium” if quality needed.
* **TTS voice**: pick a Piper voice with fast inference on your hardware.

# Testing & Troubleshooting

* **Handlers:** if you see `Invalid handler type` at startup, a handler signature is wrong.
  Use the typed registration:

  ```go
  sess.AddHandler(discordgo.VoiceSpeakingUpdateHandler(vp.HandleSpeakingUpdate))
  ```
* **No audio in:** ensure `deaf=false` on `ChannelVoiceJoin`, and `vc.OpusRecv != nil`.
* **No audio out:** check `vc.Speaking(true)` succeeds; ensure TTS returns a valid WAV.
* **Service health:** curl the three endpoints (STT/LLM/TTS) directly from the bot host to verify connectivity and payload shape.

# Security & Privacy

* The bot never sends user audio/text to third-party APIs unless you point it there.
* Keep your Discord bot token out of logs and source control.
* Prefer loopback addresses in dev; lock down interfaces in Docker (`--network`/firewall rules).

# Extensibility Map

* **VAD-based flushing:** Replace fixed timers with voice activity detection to flush at end-of-utterance for lower perceived latency.
* **Function calls / tools:** Expose a tool layer in the LLM client to integrate retrieval or game APIs.
* **Slash commands:** Add `/join`, `/leave`, `/say`, `/latency` for ops.
* **Observability:** Add structured logs and optional Prometheus metrics per stage (decode, STT, LLM, TTS, playback).
