"""Discord service configuration entrypoint using the shared config library."""

from __future__ import annotations

from services.common.config import AudioConfig, DiscordConfig, OrchestratorConfig
from services.common.config import ServiceConfig as BotConfig
from services.common.config import (
    STTConfig,
    TelemetryConfig,
    WakeConfig,
    get_service_preset,
    load_config_from_env,
)


def load_config() -> BotConfig:
    """Load Discord configuration via shared configuration library."""
    return load_config_from_env(BotConfig, **get_service_preset("discord"))


__all__ = [
    "AudioConfig",
    "BotConfig",
    "DiscordConfig",
    "OrchestratorConfig",
    "STTConfig",
    "TelemetryConfig",
    "WakeConfig",
    "load_config",
]
