"""Configuration helpers for the Python Discord voice bot."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass(slots=True)
class DiscordConfig:
    """Discord-specific settings."""

    token: str
    guild_id: int
    voice_channel_id: int
    intents: List[str] = field(default_factory=lambda: ["guilds", "voice_states", "guild_messages"])
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
    allowlist_user_ids: List[int] = field(default_factory=list)
    input_sample_rate_hz: int = 48000
    vad_sample_rate_hz: int = 16000
    vad_frame_duration_ms: int = 30
    vad_aggressiveness: int = 1

    # Audio I/O Pipeline Configuration
    canonical_sample_rate: int = 48000
    canonical_frame_ms: int = 20
    canonical_samples_per_frame: int = 960
    jitter_target_frames: int = 3
    jitter_max_frames: int = 8
    vad_padding_ms: int = 200
    loudnorm_enabled: bool = True
    loudnorm_target_lufs: float = -16.0
    loudnorm_target_tp: float = -1.5
    loudnorm_lra: int = 11
    underrun_silence_frames: int = 1
    overflow_drop_oldest: bool = True


@dataclass(slots=True)
class STTConfig:
    """Transcription service configuration."""

    base_url: str
    request_timeout_seconds: float = 45.0
    max_retries: int = 3
    forced_language: Optional[str] = "en"


@dataclass(slots=True)
class MCPConfig:
    """Configuration for manifest loading and transports."""

    manifest_paths: List[Path] = field(default_factory=list)
    websocket_url: Optional[str] = None
    command_path: Optional[Path] = None
    registration_url: Optional[str] = None
    heartbeat_interval_seconds: float = 30.0


@dataclass(slots=True)
class TelemetryConfig:
    """Diagnostics options."""

    log_level: str = "INFO"
    log_json: bool = True
    metrics_port: Optional[int] = None
    waveform_debug_dir: Optional[Path] = None


@dataclass(slots=True)
class BotConfig:
    """Composite configuration for the Python Discord bot."""

    discord: DiscordConfig
    audio: AudioConfig
    stt: STTConfig
    wake: "WakeConfig"
    mcp: MCPConfig
    telemetry: TelemetryConfig


@dataclass(slots=True)
class WakeConfig:
    """Wake phrase detection settings."""

    wake_phrases: List[str] = field(default_factory=lambda: ["hey atlas", "ok atlas"])
    model_paths: List[Path] = field(default_factory=list)
    activation_threshold: float = 0.5
    target_sample_rate_hz: int = 16000


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _get_int(name: str, default: Optional[int] = None) -> int:
    raw = os.getenv(name)
    if raw is None:
        if default is None:
            raise RuntimeError(f"Missing required integer environment variable: {name}")
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} must be an integer") from exc


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def load_config() -> BotConfig:
    """Load configuration from environment variables."""

    discord = DiscordConfig(
        token=_require_env("DISCORD_BOT_TOKEN"),
        guild_id=_get_int("DISCORD_GUILD_ID"),
        voice_channel_id=_get_int("DISCORD_VOICE_CHANNEL_ID"),
        intents=_split_csv(os.getenv("DISCORD_INTENTS", "guilds,voice_states")),
        auto_join=os.getenv("DISCORD_AUTO_JOIN", "false").lower() == "true",
        voice_connect_timeout_seconds=float(os.getenv("DISCORD_VOICE_CONNECT_TIMEOUT", "15")),
        voice_connect_max_attempts=max(1, int(os.getenv("DISCORD_VOICE_CONNECT_ATTEMPTS", "3"))),
        voice_reconnect_initial_backoff_seconds=float(
            os.getenv("DISCORD_VOICE_RECONNECT_BASE_DELAY", "5")
        ),
        voice_reconnect_max_backoff_seconds=float(
            os.getenv("DISCORD_VOICE_RECONNECT_MAX_DELAY", "60")
        ),
    )

    allowlist_raw = os.getenv("AUDIO_ALLOWLIST", "")
    allowlist_ids = [int(item) for item in _split_csv(allowlist_raw)] if allowlist_raw else []

    audio = AudioConfig(
        silence_timeout_seconds=float(os.getenv("AUDIO_SILENCE_TIMEOUT", "0.75")),
        max_segment_duration_seconds=float(os.getenv("AUDIO_MAX_SEGMENT_DURATION", "15")),
        min_segment_duration_seconds=float(os.getenv("AUDIO_MIN_SEGMENT_DURATION", "0.3")),
        aggregation_window_seconds=float(os.getenv("AUDIO_AGGREGATION_WINDOW", "1.5")),
        allowlist_user_ids=allowlist_ids,
        input_sample_rate_hz=int(os.getenv("AUDIO_SAMPLE_RATE", "48000")),
        vad_sample_rate_hz=int(os.getenv("AUDIO_VAD_SAMPLE_RATE", "16000")),
        vad_frame_duration_ms=int(os.getenv("AUDIO_VAD_FRAME_MS", "30")),
        vad_aggressiveness=int(os.getenv("AUDIO_VAD_AGGRESSIVENESS", "2")),
        # Audio I/O Pipeline Configuration
        canonical_sample_rate=int(os.getenv("AUDIO_CANONICAL_SAMPLE_RATE", "48000")),
        canonical_frame_ms=int(os.getenv("AUDIO_CANONICAL_FRAME_MS", "20")),
        canonical_samples_per_frame=int(os.getenv("AUDIO_CANONICAL_SAMPLES_PER_FRAME", "960")),
        jitter_target_frames=int(os.getenv("AUDIO_JITTER_TARGET_FRAMES", "3")),
        jitter_max_frames=int(os.getenv("AUDIO_JITTER_MAX_FRAMES", "8")),
        vad_padding_ms=int(os.getenv("AUDIO_VAD_PADDING_MS", "200")),
        loudnorm_enabled=os.getenv("AUDIO_LOUDNORM_ENABLED", "true").lower() == "true",
        loudnorm_target_lufs=float(os.getenv("AUDIO_LOUDNORM_TARGET_LUFS", "-16.0")),
        loudnorm_target_tp=float(os.getenv("AUDIO_LOUDNORM_TARGET_TP", "-1.5")),
        loudnorm_lra=int(os.getenv("AUDIO_LOUDNORM_LRA", "11")),
        underrun_silence_frames=int(os.getenv("AUDIO_UNDERRUN_SILENCE_FRAMES", "1")),
        overflow_drop_oldest=os.getenv("AUDIO_OVERFLOW_DROP_OLDEST", "true").lower() == "true",
    )

    stt_forced_language = os.getenv("STT_FORCED_LANGUAGE", "en")
    stt = STTConfig(
        base_url=_require_env("STT_BASE_URL"),
        request_timeout_seconds=float(os.getenv("STT_TIMEOUT", "45")),
        max_retries=int(os.getenv("STT_MAX_RETRIES", "3")),
        forced_language=stt_forced_language if stt_forced_language else None,
    )

    wake_model_paths = [Path(part) for part in _split_csv(os.getenv("WAKE_MODEL_PATHS", ""))]
    wake = WakeConfig(
        wake_phrases=_split_csv(os.getenv("WAKE_PHRASES", "hey atlas,ok atlas")),
        model_paths=wake_model_paths,
        activation_threshold=float(os.getenv("WAKE_THRESHOLD", "0.5")),
        target_sample_rate_hz=int(
            os.getenv("WAKE_SAMPLE_RATE", os.getenv("AUDIO_VAD_SAMPLE_RATE", "16000"))
        ),
    )

    manifest_paths = [Path(part) for part in _split_csv(os.getenv("MCP_MANIFESTS", ""))]
    mcp = MCPConfig(
        manifest_paths=manifest_paths,
        websocket_url=os.getenv("MCP_WEBSOCKET_URL"),
        command_path=(
            Path(os.getenv("MCP_COMMAND_PATH", "")) if os.getenv("MCP_COMMAND_PATH") else None
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
