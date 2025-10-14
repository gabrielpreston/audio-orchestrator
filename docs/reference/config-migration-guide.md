# Configuration Migration Guide

This guide shows how to migrate each service from the current configuration management approach to the new common configuration library.

## Overview

The new configuration library provides:
- **Type safety** with full validation
- **Consistent patterns** across all services
- **Automatic environment variable loading**
- **Comprehensive error handling**
- **Self-documenting configuration**

## Discord Service Migration

### Current Approach

```python
# services/discord/config.py
@dataclass(slots=True)
class DiscordConfig:
    token: str
    guild_id: int
    voice_channel_id: int
    intents: List[str] = field(default_factory=lambda: ["guilds", "voice_states", "guild_messages"])
    auto_join: bool = False
    # ... more fields

def load_config() -> BotConfig:
    # 100+ lines of manual environment variable parsing
    discord = DiscordConfig(
        token=_require_env("DISCORD_BOT_TOKEN"),
        guild_id=_get_int("DISCORD_GUILD_ID"),
        voice_channel_id=_get_int("DISCORD_VOICE_CHANNEL_ID"),
        # ... more parsing
    )
    # ... more sections
    return BotConfig(discord=discord, audio=audio, stt=stt, wake=wake, mcp=mcp, telemetry=telemetry)
```

### New Approach

```python
# services/discord/config.py
from services.common.config import ConfigBuilder, Environment
from services.common.service_configs import (
    DiscordConfig, AudioConfig, STTConfig, WakeConfig, MCPConfig, TelemetryConfig
)

def load_config():
    return (
        ConfigBuilder.for_service("discord", Environment.DOCKER)
        .add_config("discord", DiscordConfig)
        .add_config("audio", AudioConfig)
        .add_config("stt", STTConfig)
        .add_config("wake", WakeConfig)
        .add_config("mcp", MCPConfig)
        .add_config("telemetry", TelemetryConfig)
        .load()
    )
```

### Usage Changes

**Before:**
```python
config = load_config()
print(config.discord.token)
print(config.audio.sample_rate)
```

**After:**
```python
config = load_config()
print(config.discord.token)
print(config.audio.input_sample_rate_hz)  # More descriptive field name
```

## STT Service Migration

### Current Approach

```python
# services/stt/app.py
MODEL_NAME = os.environ.get("FW_MODEL", "small")
device = os.environ.get("FW_DEVICE", "cpu")
compute_type = os.environ.get("FW_COMPUTE_TYPE")

def _env_bool(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes", "on"}

configure_logging(
    os.getenv("LOG_LEVEL", "INFO"),
    json_logs=_env_bool("LOG_JSON", "true"),
    service_name="stt",
)
```

### New Approach

```python
# services/stt/app.py
from services.common.config import ConfigBuilder, Environment
from services.common.service_configs import FasterWhisperConfig, LoggingConfig, HttpConfig

def load_config():
    return (
        ConfigBuilder.for_service("stt", Environment.DOCKER)
        .add_config("logging", LoggingConfig)
        .add_config("http", HttpConfig)
        .add_config("faster_whisper", FasterWhisperConfig)
        .load()
    )

config = load_config()
configure_logging(
    config.logging.level,
    json_logs=config.logging.json_logs,
    service_name="stt",
)
```

### Usage Changes

**Before:**
```python
MODEL_NAME = os.environ.get("FW_MODEL", "small")
device = os.environ.get("FW_DEVICE", "cpu")
compute_type = os.environ.get("FW_COMPUTE_TYPE")
```

**After:**
```python
config = load_config()
model_name = config.faster_whisper.model
device = config.faster_whisper.device
compute_type = config.faster_whisper.compute_type
```

## TTS Service Migration

### Current Approach

```python
# services/tts/app.py
_MODEL_PATH = os.getenv("TTS_MODEL_PATH")
_MODEL_CONFIG_PATH = os.getenv("TTS_MODEL_CONFIG_PATH")
_DEFAULT_VOICE = os.getenv("TTS_DEFAULT_VOICE")
_MAX_TEXT_LENGTH = _env_int("TTS_MAX_TEXT_LENGTH", 1000, minimum=32, maximum=10000)
_MAX_CONCURRENCY = _env_int("TTS_MAX_CONCURRENCY", 4, minimum=1, maximum=64)
# ... more variables

def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    value = default
    if raw is not None:
        try:
            value = int(raw)
        except ValueError:
            pass
    if value < minimum:
        value = minimum
    if value > maximum:
        value = maximum
    return value
```

### New Approach

```python
# services/tts/app.py
from services.common.config import ConfigBuilder, Environment
from services.common.service_configs import TTSConfig, LoggingConfig, HttpConfig

def load_config():
    return (
        ConfigBuilder.for_service("tts", Environment.DOCKER)
        .add_config("logging", LoggingConfig)
        .add_config("http", HttpConfig)
        .add_config("tts", TTSConfig)
        .load()
    )

config = load_config()
```

### Usage Changes

**Before:**
```python
_MODEL_PATH = os.getenv("TTS_MODEL_PATH")
_MAX_TEXT_LENGTH = _env_int("TTS_MAX_TEXT_LENGTH", 1000, minimum=32, maximum=10000)
```

**After:**
```python
config = load_config()
model_path = config.tts.model_path
max_text_length = config.tts.max_text_length
```

## LLM Service Migration

### Current Approach

```python
# services/llm/app.py
_LLAMA: Optional[Llama] = None
_TTS_CLIENT: Optional[httpx.AsyncClient] = None
_TTS_BASE_URL = os.getenv("TTS_BASE_URL")
_TTS_VOICE = os.getenv("TTS_VOICE")
_TTS_AUTH_TOKEN = os.getenv("TTS_AUTH_TOKEN")
_MCP_CONFIG_PATH = os.getenv("MCP_CONFIG_PATH", "./mcp.json")

def _tts_timeout() -> float:
    try:
        return float(os.getenv("TTS_TIMEOUT", "30"))
    except ValueError:
        return 30.0

def _load_llama() -> Optional[Llama]:
    model_path = os.getenv("LLAMA_MODEL_PATH", "/app/models/llama2-7b.gguf")
    ctx = int(os.getenv("LLAMA_CTX", "2048"))
    threads = int(os.getenv("LLAMA_THREADS", str(max(os.cpu_count() or 1, 1))))
    # ... more parsing
```

### New Approach

```python
# services/llm/app.py
from services.common.config import ConfigBuilder, Environment
from services.common.service_configs import LlamaConfig, OrchestratorConfig, LoggingConfig, HttpConfig

def load_config():
    return (
        ConfigBuilder.for_service("orchestrator", Environment.DOCKER)
        .add_config("logging", LoggingConfig)
        .add_config("http", HttpConfig)
        .add_config("llama", LlamaConfig)
        .add_config("orchestrator", OrchestratorConfig)
        .load()
    )

config = load_config()
```

### Usage Changes

**Before:**
```python
model_path = os.getenv("LLAMA_MODEL_PATH", "/app/models/llama2-7b.gguf")
ctx = int(os.getenv("LLAMA_CTX", "2048"))
tts_base_url = os.getenv("TTS_BASE_URL")
```

**After:**
```python
config = load_config()
model_path = config.llama.model_path
ctx = config.llama.context_length
tts_base_url = config.orchestrator.tts_base_url
```

## Environment Variable Mapping

The new configuration library automatically maps field names to environment variables:

### Discord Service

| Field | Environment Variable |
|-------|---------------------|
| `discord.token` | `DISCORD_BOT_TOKEN` |
| `discord.guild_id` | `DISCORD_GUILD_ID` |
| `discord.voice_channel_id` | `DISCORD_VOICE_CHANNEL_ID` |
| `audio.input_sample_rate_hz` | `AUDIO_SAMPLE_RATE` |
| `stt.base_url` | `STT_BASE_URL` |

### STT Service

| Field | Environment Variable |
|-------|---------------------|
| `faster_whisper.model` | `FW_MODEL` |
| `faster_whisper.device` | `FW_DEVICE` |
| `faster_whisper.compute_type` | `FW_COMPUTE_TYPE` |

### TTS Service

| Field | Environment Variable |
|-------|---------------------|
| `tts.model_path` | `TTS_MODEL_PATH` |
| `tts.model_config_path` | `TTS_MODEL_CONFIG_PATH` |
| `tts.max_text_length` | `TTS_MAX_TEXT_LENGTH` |
| `tts.max_concurrency` | `TTS_MAX_CONCURRENCY` |

### Orchestrator Service

| Field | Environment Variable |
|-------|---------------------|
| `llama.model_path` | `LLAMA_MODEL_PATH` |
| `llama.context_length` | `LLAMA_CTX` |
| `llama.threads` | `LLAMA_THREADS` |
| `orchestrator.tts_base_url` | `TTS_BASE_URL` |

## Validation Benefits

The new configuration library provides comprehensive validation:

### Type Validation

```python
# Automatically validates types
config.discord.guild_id  # Must be int
config.audio.silence_timeout_seconds  # Must be float
config.stt.base_url  # Must be str
```

### Range Validation

```python
# Automatically validates ranges
config.audio.input_sample_rate_hz  # Must be in [8000, 16000, 22050, 44100, 48000]
config.discord.voice_connect_timeout_seconds  # Must be between 1.0 and 300.0
```

### Required Field Validation

```python
# Automatically validates required fields
config.discord.token  # Must be provided
config.stt.base_url  # Must be provided
```

### Custom Validation

```python
# Custom validators for complex validation
config.stt.base_url  # Must be a valid URL
config.discord.guild_id  # Must be a positive integer
```

## Error Handling

The new configuration library provides clear error messages:

### Before (Current)

```python
# Cryptic error messages
ValueError: invalid literal for int() with base 10: 'not_a_number'
KeyError: 'DISCORD_BOT_TOKEN'
```

### After (New)

```python
# Clear error messages
ValidationError: Field 'guild_id' with value 'not_a_number' failed validation: Expected type int, got str
RequiredFieldError: Required field 'token' is missing
```

## Migration Steps

1. **Install the new configuration library** (already done)
2. **Update service imports** to use the new configuration classes
3. **Replace manual environment variable parsing** with the new configuration loader
4. **Update field access** to use the new configuration structure
5. **Add validation calls** where appropriate
6. **Test the migration** with existing environment variables
7. **Update documentation** to reflect the new configuration approach

## Testing the Migration

To test the migration:

1. **Set up environment variables** as they currently are
2. **Load configuration** using the new library
3. **Validate configuration** to ensure all fields are correct
4. **Compare values** with the old configuration approach
5. **Test error handling** with invalid values

```python
# Test script
from services.common.config import ConfigBuilder, Environment
from services.common.service_configs import DiscordConfig

# Load configuration
config = (
    ConfigBuilder.for_service("discord", Environment.DOCKER)
    .add_config("discord", DiscordConfig)
    .load()
)

# Validate configuration
try:
    config.validate()
    print("✓ Configuration is valid")
except Exception as e:
    print(f"✗ Configuration validation failed: {e}")

# Print configuration values
print(f"Token: {config.discord.token[:10]}..." if config.discord.token else "Not set")
print(f"Guild ID: {config.discord.guild_id}")
print(f"Voice Channel ID: {config.discord.voice_channel_id}")
```

## Benefits of Migration

1. **Reduced Code**: Eliminate 100+ lines of manual parsing per service
2. **Type Safety**: Catch configuration errors at startup
3. **Consistency**: Unified configuration patterns across all services
4. **Maintainability**: Easy to add new configuration fields
5. **Documentation**: Self-documenting configuration with descriptions
6. **Validation**: Comprehensive validation with clear error messages
7. **Testing**: Easy to test configuration loading and validation