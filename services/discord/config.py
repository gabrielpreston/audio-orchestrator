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


@dataclass(slots=True)
class AudioConfig:
    """Audio pipeline knobs."""

    vad_threshold: float = 40.0
    silence_timeout_seconds: float = 0.75
    max_segment_duration_seconds: float = 15.0
    min_segment_duration_seconds: float = 0.3
    aggregation_window_seconds: float = 1.5
    allowlist_user_ids: List[int] = field(default_factory=list)


@dataclass(slots=True)
class STTConfig:
    """Transcription service configuration."""

    base_url: str
    request_timeout_seconds: float = 15.0
    max_retries: int = 3


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
    )

    allowlist_raw = os.getenv("AUDIO_ALLOWLIST", "")
    allowlist_ids = [int(item) for item in _split_csv(allowlist_raw)] if allowlist_raw else []

    audio = AudioConfig(
        vad_threshold=float(os.getenv("AUDIO_VAD_THRESHOLD", "40.0")),
        silence_timeout_seconds=float(os.getenv("AUDIO_SILENCE_TIMEOUT", "0.75")),
        max_segment_duration_seconds=float(os.getenv("AUDIO_MAX_SEGMENT_DURATION", "15")),
        min_segment_duration_seconds=float(os.getenv("AUDIO_MIN_SEGMENT_DURATION", "0.3")),
        aggregation_window_seconds=float(os.getenv("AUDIO_AGGREGATION_WINDOW", "1.5")),
        allowlist_user_ids=allowlist_ids,
    )

    stt = STTConfig(
        base_url=_require_env("STT_BASE_URL"),
        request_timeout_seconds=float(os.getenv("STT_TIMEOUT", "15")),
        max_retries=int(os.getenv("STT_MAX_RETRIES", "3")),
    )

    wake = WakeConfig(
        wake_phrases=_split_csv(
            os.getenv("WAKE_PHRASES", os.getenv("ORCHESTRATOR_WAKE_PHRASES", "hey atlas,ok atlas"))
        ),
    )

    manifest_paths = [Path(part) for part in _split_csv(os.getenv("MCP_MANIFESTS", ""))]
    mcp = MCPConfig(
        manifest_paths=manifest_paths,
        websocket_url=os.getenv("MCP_WEBSOCKET_URL"),
        command_path=Path(os.getenv("MCP_COMMAND_PATH", "")) if os.getenv("MCP_COMMAND_PATH") else None,
        registration_url=os.getenv("MCP_REGISTRATION_URL"),
        heartbeat_interval_seconds=float(os.getenv("MCP_HEARTBEAT_INTERVAL", "30")),
    )

    telemetry = TelemetryConfig(
        metrics_port=int(os.getenv("METRICS_PORT")) if os.getenv("METRICS_PORT") else None,
        waveform_debug_dir=Path(os.getenv("WAVEFORM_DEBUG_DIR", "")) if os.getenv("WAVEFORM_DEBUG_DIR") else None,
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
