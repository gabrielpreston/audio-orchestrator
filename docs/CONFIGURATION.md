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
| `OPENAI_BASE_URL` | ✅ Yes | – | LLM endpoint base URL |
| `OPENAI_API_KEY` | ✅ Yes | – | API key for LLM |
| `OPENAI_MODEL` | ✅ Yes | – | Model name |
| `WHISPER_URL` | ✅ Yes | – | STT service endpoint |
| `TTS_URL` | ✅ Yes | – | TTS service endpoint |
| `RECORD_SECONDS` | Optional | `8` | Audio chunk size before transcription |

> ✅ TODO: Fill in details for all config fields and describe their impact.

---

## 2. Secrets Management
> ✅ TODO: Add instructions for handling secrets securely in development and production.

---

## 3. Advanced Settings
> ✅ TODO: Cover optional tuning knobs and runtime flags.
