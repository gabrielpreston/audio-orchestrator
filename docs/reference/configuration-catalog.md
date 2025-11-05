---
title: Configuration Catalog
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-18
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Reference ▸ Configuration Catalog

# Configuration Catalog

This catalog aggregates environment variables defined in `.env.sample` and service-specific overrides.
Update this file whenever you add, rename, or remove configuration keys.

> **Note**: The project now uses a type-safe configuration library (`services.common.config`) for
> configuration management. See the [Configuration Library Reference](configuration-library.md) for
> details on the new `ConfigBuilder` approach.

## Shared Defaults (`.env.common`)

| Variable | Description | Default |
| --- | --- | --- |
| `LOG_LEVEL` | Global logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). Case-insensitive - accepts lowercase. | `INFO` |
| `LOG_JSON` | Emit JSON-formatted logs when `true`. | `true` |
| `LOG_FULL_TRACEBACKS` | Control exception traceback verbosity. `true` forces full tracebacks, `false` forces summary format. If unset, uses full tracebacks for DEBUG level and summary for INFO+ level. | *(auto)* |
| `LOG_SAMPLE_VAD_N` | Sample high-frequency VAD events to reduce log volume. | `50` |
| `LOG_SAMPLE_UNKNOWN_USER_N` | Sample unknown user events to reduce log volume. | `100` |
| `LOG_RATE_LIMIT_PACKET_WARN_S` | Rate limit for packet warning logs (seconds). | `10` |
| `LOG_SAMPLE_SEGMENT_READY_RATE` | Sample rate for segment ready events. | *(empty)* |
| `LOG_SAMPLE_SEGMENT_READY_N` | Sample count for segment ready events. | *(empty)* |
| `DISCORD_WARMUP_AUDIO` | Enable Discord audio warm-up. | `true` |
| `STT_WARMUP` | Enable STT service warm-up. | `true` |
| `DISCORD_HTTP_MODE` | Enable Discord HTTP mode. | `false` |
| `ORCH_TIMEOUT` | Orchestrator client timeout (seconds). | `30` |
| `LLM_MAX_TOKENS` | Maximum tokens for LLM generation. | `128` |
| `LLM_TEMPERATURE` | LLM temperature setting. | `0.7` |
| `LLM_TOP_P` | LLM top-p setting. | `0.9` |
| `LLM_TOP_K` | LLM top-k setting. | `40` |
| `LLM_REPEAT_PENALTY` | LLM repeat penalty setting. | `1.1` |

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
| `AUDIO_SAMPLE_RATE` | General audio processing sample rate (Hz). | `16000` |
| `AUDIO_INPUT_SAMPLE_RATE` | Discord input audio sample rate (Hz). Used by accumulator logic. | `48000` |
| `AUDIO_VAD_SAMPLE_RATE` | Sample rate used for VAD analysis (Hz). | `16000` |
| `AUDIO_VAD_FRAME_MS` | Frame length used for VAD (milliseconds). | `30` |
| `AUDIO_VAD_AGGRESSIVENESS` | WebRTC VAD aggressiveness level (0-3). | `1` |
| `STT_BASE_URL` | Speech-to-text service URL. | `http://stt:9000` |
| `STT_TIMEOUT` | Timeout for STT requests (seconds). | `45` |
| `STT_MAX_RETRIES` | Number of retry attempts for STT calls. | `3` |
| `STT_FORCED_LANGUAGE` | Optional language code override. | `en` |
| `WAKE_MODEL_PATHS` | Additional wake model files. | *(empty)* |
| `WAKE_PHRASES` | Comma-separated list of wake phrases. | `hey atlas,ok atlas` |
| `WAKE_THRESHOLD` | Wake detection confidence threshold (0-1). | `0.5` |
| `WAKE_SAMPLE_RATE` | Sample rate for wake model (Hz). | `16000` |
| `METRICS_PORT` | Optional port for Prometheus metrics. | *(empty)* |
| `WAVEFORM_DEBUG_DIR` | Directory for debugging waveform artifacts. | *(empty)* |
| `ORCHESTRATOR_WAKE_PHRASES` | Orchestrator-specific wake phrases. | *(empty)* |
| `ORCHESTRATOR_URL` | Orchestrator service URL. | `http://orchestrator:8000` |

## Force Model Download (`.env.common` or service-specific)

| Variable | Description | Default |
| --- | --- | --- |
| `FORCE_MODEL_DOWNLOAD` | Global setting to force re-download of all models on startup (bypasses cache). | `false` |
| `FORCE_MODEL_DOWNLOAD_WHISPER_MODEL` | Force download for STT service Whisper model (overrides global). | `false` |
| `FORCE_MODEL_DOWNLOAD_FLAN_T5` | Force download for FLAN service FLAN-T5 model (overrides global). | `false` |
| `FORCE_MODEL_DOWNLOAD_TOXICITY_MODEL` | Force download for Guardrails service toxicity model (overrides global). | `false` |
| `FORCE_MODEL_DOWNLOAD_BARK_MODELS` | Force download for Bark service models (overrides global). | `false` |
| `FORCE_MODEL_DOWNLOAD_METRICGAN` | Force download for STT service MetricGAN model (overrides global). | `false` |

## STT Service (`services/stt/.env.service`)

| Variable | Description | Default |
| --- | --- | --- |
| `FW_MODEL` | faster-whisper model name. | `medium.en` |
| `FW_DEVICE` | Execution target (`cpu`, `cuda`). | `cpu` |
| `FW_COMPUTE_TYPE` | Precision trade-off for inference. | `int8` |
| `FORCE_MODEL_DOWNLOAD_WHISPER_MODEL` | Force download for Whisper model (overrides global). | `false` |
| `STT_ENABLE_PREWARM` | Pre-warming to ensure models are ready before serving traffic. | `true` |
| `STT_ENABLE_CACHE` | Result caching for identical audio requests (significant speedup for repeated audio). | `true` |
| `STT_CACHE_MAX_ENTRIES` | Maximum number of cached transcripts. | `200` |
| `STT_CACHE_MAX_SIZE_MB` | Maximum cache size in megabytes. | `1000` |

## FLAN Service (`services/flan/.env.service`)

| Variable | Description | Default |
| --- | --- | --- |
| `PORT` | HTTP listen port. | `8100` |
| `FLAN_T5_MODEL_SIZE` | FLAN-T5 model size (`google/flan-t5-base`, `google/flan-t5-large`, `google/flan-t5-xl`). | `google/flan-t5-large` |
| `TRANSFORMERS_CACHE` | Hugging Face cache directory. | `/app/models` |
| `ENABLE_MODEL_CACHING` | Enable model caching. | `true` |
| `MAX_SEQUENCE_LENGTH` | Maximum sequence length for input. | `512` |
| `TEMPERATURE` | Generation temperature. | `0.7` |
| `TOP_P` | Top-p sampling parameter. | `0.9` |
| `TOP_K` | Top-k sampling parameter. | `50` |
| `REPETITION_PENALTY` | Repetition penalty. | `1.1` |
| `HF_HOME` | Hugging Face home directory for model storage. | `/app/models` |
| `FORCE_MODEL_DOWNLOAD_FLAN_T5` | Force download for FLAN-T5 model (overrides global). | `false` |
| `FLAN_ENABLE_TORCH_COMPILE` | Enable torch.compile() optimization (20-40% speedup on PyTorch 2.0+). | `true` |
| `FLAN_COMPILE_MODE` | torch.compile() mode (`default`, `reduce-overhead`, `max-autotune`, `max-autotune-no-cudagraphs`). | `default` |
| `FLAN_ENABLE_PREWARM` | Pre-warming to trigger torch.compile() warmup during startup. | `true` |
| `FLAN_ENABLE_CACHE` | Result caching for repeated prompts (optional, disabled by default). | `false` |
| `FLAN_CACHE_MAX_ENTRIES` | Maximum number of cached generations. | `100` |
| `FLAN_CACHE_MAX_SIZE_MB` | Maximum cache size in megabytes. | `500` |

## Orchestrator Service (`services/orchestrator/.env.service`)

| Variable | Description | Default |
| --- | --- | --- |
| `PORT` | HTTP listen port. | `8200` |
| `LLM_BASE_URL` | LLM service URL (agnostic service name, implementation: FLAN-T5). | `http://flan:8100` |
| `GUARDRAILS_BASE_URL` | Guardrails service URL. | `http://guardrails:9300` |
| `TTS_BASE_URL` | TTS service URL (agnostic service name, implementation: Bark). | `http://bark:7100` |
| `TTS_AUTH_TOKEN` | Bearer token for TTS service authentication. | `changeme` |
| `ORCHESTRATOR_DEBUG_SAVE` | Enable debug data collection. | `false` |

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

## Guardrails Service (`services/guardrails/.env.service`)

| Variable | Description | Default |
| --- | --- | --- |
| `PORT` | HTTP listen port. | `9300` |
| `TOXICITY_MODEL` | Toxicity detection model identifier. | `unitary/toxic-bert` |
| `ENABLE_PII_DETECTION` | Enable PII (Personally Identifiable Information) detection. | `true` |
| `FORCE_MODEL_DOWNLOAD_TOXICITY_MODEL` | Force download for toxicity model (overrides global). | `false` |
| `HF_HOME` | Hugging Face home directory for model storage. | `/app/models` |

## Bark TTS Service (`services/bark/.env.service`)

| Variable | Description | Default |
| --- | --- | --- |
| `PORT` | HTTP listen port. | `7100` |
| `BARK_USE_SMALL_MODELS` | Enable small models for 30-50% speedup (slight quality trade-off). | `true` |
| `BARK_ENABLE_TORCH_COMPILE` | Enable torch.compile() optimization (replaces deprecated Better Transformer). | `true` |
| `BARK_COMPILE_MODE` | torch.compile() mode (`default`, `reduce-overhead`, `max-autotune`, `max-autotune-no-cudagraphs`). | `max-autotune-no-cudagraphs` |
| `BARK_ENABLE_PREWARM` | Pre-warming to trigger torch.compile() warmup during startup. | `true` |
| `BARK_ENABLE_CACHE` | Result caching for repeated synthesis requests. | `true` |
| `BARK_CACHE_MAX_ENTRIES` | Maximum number of cached results. | `100` |
| `BARK_CACHE_MAX_SIZE_MB` | Maximum cache size in megabytes. | `500` |
| `BARK_ENABLE_INT8_QUANTIZATION` | Enable INT8 quantization (disabled by default, requires quality validation). | `false` |
| `FORCE_MODEL_DOWNLOAD_BARK_MODELS` | Force download for Bark models (overrides global). | `false` |
| `HF_HOME` | Hugging Face home directory for model storage. | `/app/models` |
| `HOME` | Container home directory path. | `/app` |
| `XDG_CACHE_HOME` | XDG cache directory path. | `/app/models` |
| `OMP_NUM_THREADS` | Number of OpenMP threads (match CPU count). | `8` |
| `MKL_NUM_THREADS` | Number of MKL threads (match CPU count). | `8` |
| `PYTORCH_CUDA_ALLOC_CONF` | PyTorch CUDA memory allocation configuration. | `max_split_size_mb:128,expandable_segments:True` |

## Service URLs

For a complete list of all service URLs accessible from your browser, including health check endpoints and API documentation, see the [Service URLs Reference](service-urls.md).

## Change Management

-  Update `.env.sample` and the relevant `.env.service` files when introducing new variables.
-  Reflect changes in this catalog and reference them from affected runbooks or proposals.
-  Include new configuration requirements in the PR summary to alert reviewers.
