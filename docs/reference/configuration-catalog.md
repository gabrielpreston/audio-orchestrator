---
title: Configuration Catalog
author: Discord Voice Lab Team
status: active
last-updated: 2024-07-05
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Reference ▸ Configuration Catalog

# Configuration Catalog

This catalog aggregates environment variables defined in `.env.sample` and service-specific overrides.
Update this file whenever you add, rename, or remove configuration keys.

## Shared Defaults (`.env.common`)

| Variable | Description | Default |
| --- | --- | --- |
| `LOG_LEVEL` | Global logging verbosity (`debug`, `info`, `warning`). | `info` |
| `LOG_JSON` | Emit JSON-formatted logs when `true`. | `true` |

## Docker Overrides (`.env.docker`)

| Variable | Description | Default |
| --- | --- | --- |
| `PUID` | Host user ID applied to container file ownership. | `1000` |
| `PGID` | Host group ID applied to container file ownership. | `1000` |
| `TZ` | Timezone for containerized processes. | `Etc/UTC` |

## Discord Service (`services/discord/.env.service`)

| Variable | Description | Default |
| --- | --- | --- |
| `DISCORD_BOT_TOKEN` | Discord bot token used for authentication. | `changeme` |
| `DISCORD_GUILD_ID` | Guild ID for the target server. | `000000000000000000` |
| `DISCORD_VOICE_CHANNEL_ID` | Voice channel ID to auto-join. | `000000000000000000` |
| `DISCORD_AUTO_JOIN` | Auto-join the configured voice channel on startup. | `false` |
| `DISCORD_INTENTS` | Enabled intents for the gateway connection. | `guilds,guild_voice_states` |
| `DISCORD_VOICE_CONNECT_TIMEOUT` | Voice connection timeout (seconds). | `15` |
| `DISCORD_VOICE_CONNECT_ATTEMPTS` | Number of voice connection retries. | `3` |
| `DISCORD_VOICE_RECONNECT_BASE_DELAY` | Base delay before voice reconnect attempts. | `5` |
| `DISCORD_VOICE_RECONNECT_MAX_DELAY` | Maximum delay for exponential backoff. | `60` |
| `AUDIO_ALLOWLIST` | Optional list of user IDs permitted to trigger wake phrases. | *(empty)* |
| `AUDIO_SILENCE_TIMEOUT` | Seconds of silence before finalizing a segment. | `0.75` |
| `AUDIO_MAX_SEGMENT_DURATION` | Maximum length of a single audio segment (seconds). | `15` |
| `AUDIO_MIN_SEGMENT_DURATION` | Minimum length before a segment is considered speech (seconds). | `0.3` |
| `AUDIO_AGGREGATION_WINDOW` | Sliding window size for VAD aggregation (seconds). | `1.5` |
| `AUDIO_SAMPLE_RATE` | Discord capture sample rate (Hz). | `48000` |
| `AUDIO_VAD_SAMPLE_RATE` | Sample rate used for VAD analysis (Hz). | `16000` |
| `AUDIO_VAD_FRAME_MS` | Frame length used for VAD (milliseconds). | `30` |
| `AUDIO_VAD_AGGRESSIVENESS` | WebRTC VAD aggressiveness level (0-3). | `2` |
| `STT_BASE_URL` | Speech-to-text service URL. | `http://stt:9000` |
| `STT_TIMEOUT` | Timeout for STT requests (seconds). | `45` |
| `STT_MAX_RETRIES` | Number of retry attempts for STT calls. | `3` |
| `STT_FORCED_LANGUAGE` | Optional language code override. | `en` |
| `WAKE_MODEL_PATHS` | Additional wake model files. | *(empty)* |
| `WAKE_PHRASES` | Comma-separated list of wake phrases. | `hey atlas,ok atlas` |
| `ORCHESTRATOR_WAKE_PHRASES` | Wake phrases forwarded to the orchestrator. | *(empty)* |
| `WAKE_THRESHOLD` | Wake detection confidence threshold (0-1). | `0.5` |
| `WAKE_SAMPLE_RATE` | Sample rate for wake model (Hz). | `16000` |
| `MCP_MANIFESTS` | Comma-separated list of manifest paths. | *(empty)* |
| `MCP_WEBSOCKET_URL` | WebSocket endpoint for remote MCP hub. | *(empty)* |
| `MCP_COMMAND_PATH` | Command to launch a local MCP server. | *(empty)* |
| `MCP_REGISTRATION_URL` | Remote registration endpoint. | *(empty)* |
| `MCP_HEARTBEAT_INTERVAL` | Seconds between MCP heartbeat pings. | `30` |
| `METRICS_PORT` | Optional port for Prometheus metrics. | *(empty)* |
| `WAVEFORM_DEBUG_DIR` | Directory for debugging waveform artifacts. | *(empty)* |

## STT Service (`services/stt/.env.service`)

| Variable | Description | Default |
| --- | --- | --- |
| `FW_MODEL` | faster-whisper model name. | `medium.en` |
| `FW_DEVICE` | Execution target (`cpu`, `cuda`). | `cpu` |
| `FW_COMPUTE_TYPE` | Precision trade-off for inference. | `int8` |

## LLM Orchestrator (`services/llm/.env.service`)

| Variable | Description | Default |
| --- | --- | --- |
| `LLAMA_BIN` | Path to the llama.cpp binary. | `/app/llama.cpp/build/bin/llama-cli` |
| `LLAMA_MODEL_PATH` | GGUF model path. | `/app/models/llama-2-7b.Q4_K_M.gguf` |
| `LLAMA_CTX` | Context window size. | `2048` |
| `LLAMA_THREADS` | Number of CPU threads to use. | `4` |
| `ORCH_AUTH_TOKEN` | Bearer token for orchestrator APIs. | `changeme` |
| `PORT` | HTTP listen port. | `8000` |
| `TTS_BASE_URL` | Downstream TTS endpoint. | `http://tts:7000` |
| `TTS_VOICE` | Default voice identifier. | *(empty)* |
| `TTS_TIMEOUT` | Timeout for TTS requests (seconds). | `30` |

## TTS Service (`services/tts/.env.service`)

| Variable | Description | Default |
| --- | --- | --- |
| `PORT` | HTTP listen port. | `7000` |
| `TTS_MODEL_PATH` | Piper model path. | `/app/models/piper/en_US-amy-medium.onnx` |
| `TTS_MODEL_CONFIG_PATH` | Piper model config path. | `/app/models/piper/en_US-amy-medium.onnx.json` |
| `TTS_DEFAULT_VOICE` | Voice preset override. | *(empty)* |
| `TTS_MAX_TEXT_LENGTH` | Maximum characters per synthesis request. | `1000` |
| `TTS_MAX_CONCURRENCY` | Maximum concurrent synthesis operations. | `4` |
| `TTS_RATE_LIMIT_PER_MINUTE` | Requests allowed per minute. | `60` |
| `TTS_AUTH_TOKEN` | Bearer token required for synthesis calls. | `changeme` |
| `TTS_LENGTH_SCALE` | Speech tempo modifier. | `1.0` |
| `TTS_NOISE_SCALE` | Controls noise added during synthesis. | `0.667` |
| `TTS_NOISE_W` | Controls breathiness of speech. | `0.8` |

## Change Management

- Update `.env.sample` and the relevant `.env.service` files when introducing new variables.
- Reflect changes in this catalog and reference them from affected runbooks or proposals.
- Include new configuration requirements in the PR summary to alert reviewers.
