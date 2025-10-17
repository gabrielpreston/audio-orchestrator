"""Configuration helpers for the Python Discord voice bot."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class DiscordConfig:
    """Discord-specific settings."""

    token: str
    guild_id: int
    voice_channel_id: int
    intents: list[str] = field(
        default_factory=lambda: ["guilds", "voice_states", "guild_messages"]
    )
    auto_join: bool = False
    voice_connect_timeout_seconds: float = 15.0
    voice_connect_max_attempts: int = 3
    voice_reconnect_initial_backoff_seconds: float = 5.0
    voice_reconnect_max_backoff_seconds: float = 60.0


@dataclass(slots=True)
class AudioConfig:
    """Audio pipeline knobs."""

    silence_timeout_seconds: float = 1.0
    max_segment_duration_seconds: float = 15.0
    min_segment_duration_seconds: float = 0.3
    aggregation_window_seconds: float = 1.5
    allowlist_user_ids: list[int] = field(default_factory=list)
    input_sample_rate_hz: int = 48000
    vad_sample_rate_hz: int = 16000
    vad_frame_duration_ms: int = 30
    vad_aggressiveness: int = 1


@dataclass(slots=True)
class STTConfig:
    """Transcription service configuration."""

    base_url: str
    request_timeout_seconds: float = 45.0
    max_retries: int = 3
    forced_language: str | None = "en"


@dataclass(slots=True)
class OrchestratorConfig:
    """Orchestrator service configuration."""

    base_url: str
    timeout_seconds: float = 30.0
    max_retries: int = 3


@dataclass(slots=True)
class MCPConfig:
    """Configuration for manifest loading and transports."""

    manifest_paths: list[Path] = field(default_factory=list)
    websocket_url: str | None = None
    command_path: Path | None = None
    registration_url: str | None = None
    heartbeat_interval_seconds: float = 30.0


@dataclass(slots=True)
class TelemetryConfig:
    """Diagnostics options."""

    log_level: str = "INFO"
    log_json: bool = True
    metrics_port: int | None = None
    waveform_debug_dir: Path | None = None


@dataclass(slots=True)
class BotConfig:
    """Composite configuration for the Python Discord bot."""

    discord: DiscordConfig
    audio: AudioConfig
    stt: STTConfig
    wake: WakeConfig
    mcp: MCPConfig
    telemetry: TelemetryConfig


@dataclass(slots=True)
class WakeConfig:
    """Wake phrase detection settings."""

    wake_phrases: list[str] = field(default_factory=lambda: ["hey atlas", "ok atlas"])
    model_paths: list[Path] = field(default_factory=list)
    activation_threshold: float = 0.5
    target_sample_rate_hz: int = 16000
    enabled: bool = True


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _get_int(name: str, default: int | None = None) -> int:
    raw = os.getenv(name)
    if raw is None:
        if default is None:
            raise RuntimeError(f"Missing required integer environment variable: {name}")
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} must be an integer") from exc


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def load_config() -> BotConfig:
    """Load configuration from environment variables."""

    discord = DiscordConfig(
        token=_require_env("DISCORD_BOT_TOKEN"),
        guild_id=_get_int("DISCORD_GUILD_ID"),
        voice_channel_id=_get_int("DISCORD_VOICE_CHANNEL_ID"),
        intents=_split_csv(os.getenv("DISCORD_INTENTS", "guilds,voice_states")),
        auto_join=os.getenv("DISCORD_AUTO_JOIN", "false").lower() == "true",
        voice_connect_timeout_seconds=float(
            os.getenv("DISCORD_VOICE_CONNECT_TIMEOUT", "15")
        ),
        voice_connect_max_attempts=max(
            1, int(os.getenv("DISCORD_VOICE_CONNECT_ATTEMPTS", "3"))
        ),
        voice_reconnect_initial_backoff_seconds=float(
            os.getenv("DISCORD_VOICE_RECONNECT_BASE_DELAY", "5")
        ),
        voice_reconnect_max_backoff_seconds=float(
            os.getenv("DISCORD_VOICE_RECONNECT_MAX_DELAY", "60")
        ),
    )

    allowlist_raw = os.getenv("AUDIO_ALLOWLIST", "")
    allowlist_ids = (
        [int(item) for item in _split_csv(allowlist_raw)] if allowlist_raw else []
    )

    audio = AudioConfig(
        silence_timeout_seconds=float(os.getenv("AUDIO_SILENCE_TIMEOUT", "0.75")),
        max_segment_duration_seconds=float(
            os.getenv("AUDIO_MAX_SEGMENT_DURATION", "15")
        ),
        min_segment_duration_seconds=float(
            os.getenv("AUDIO_MIN_SEGMENT_DURATION", "0.3")
        ),
        aggregation_window_seconds=float(os.getenv("AUDIO_AGGREGATION_WINDOW", "1.5")),
        allowlist_user_ids=allowlist_ids,
        input_sample_rate_hz=int(os.getenv("AUDIO_SAMPLE_RATE", "48000")),
        vad_sample_rate_hz=int(os.getenv("AUDIO_VAD_SAMPLE_RATE", "16000")),
        vad_frame_duration_ms=int(os.getenv("AUDIO_VAD_FRAME_MS", "30")),
        vad_aggressiveness=int(os.getenv("AUDIO_VAD_AGGRESSIVENESS", "2")),
    )

    stt_forced_language = os.getenv("STT_FORCED_LANGUAGE", "en")
    stt = STTConfig(
        base_url=_require_env("STT_BASE_URL"),
        request_timeout_seconds=float(os.getenv("STT_TIMEOUT", "45")),
        max_retries=int(os.getenv("STT_MAX_RETRIES", "3")),
        forced_language=stt_forced_language if stt_forced_language else None,
    )

    wake_model_paths = [
        Path(part) for part in _split_csv(os.getenv("WAKE_MODEL_PATHS", ""))
    ]
    wake = WakeConfig(
        wake_phrases=_split_csv(os.getenv("WAKE_PHRASES", "hey atlas,ok atlas")),
        model_paths=wake_model_paths,
        activation_threshold=float(os.getenv("WAKE_THRESHOLD", "0.5")),
        target_sample_rate_hz=int(
            os.getenv("WAKE_SAMPLE_RATE", os.getenv("AUDIO_VAD_SAMPLE_RATE", "16000"))
        ),
        enabled=os.getenv("WAKE_DETECTION_ENABLED", "true").lower() == "true",
    )

    manifest_paths = [Path(part) for part in _split_csv(os.getenv("MCP_MANIFESTS", ""))]
    mcp = MCPConfig(
        manifest_paths=manifest_paths,
        websocket_url=os.getenv("MCP_WEBSOCKET_URL"),
        command_path=(
            Path(os.getenv("MCP_COMMAND_PATH", ""))
            if os.getenv("MCP_COMMAND_PATH")
            else None
        ),
        registration_url=os.getenv("MCP_REGISTRATION_URL"),
        heartbeat_interval_seconds=float(os.getenv("MCP_HEARTBEAT_INTERVAL", "30")),
    )

    metrics_port_env = os.getenv("METRICS_PORT")
    waveform_debug_env = os.getenv("WAVEFORM_DEBUG_DIR")
    telemetry = TelemetryConfig(
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_json=os.getenv("LOG_JSON", "true").lower() == "true",
        metrics_port=int(metrics_port_env) if metrics_port_env else None,
        waveform_debug_dir=Path(waveform_debug_env) if waveform_debug_env else None,
    )

    return BotConfig(
        discord=discord,
        audio=audio,
        stt=stt,
        wake=wake,
        mcp=mcp,
        telemetry=telemetry,
    )


__all__ = [
    "AudioConfig",
    "BotConfig",
    "DiscordConfig",
    "MCPConfig",
    "STTConfig",
    "TelemetryConfig",
    "WakeConfig",
    "load_config",
]
