"""Discord service configuration entrypoint using the shared config library."""

from __future__ import annotations

from services.common.config import load_config_from_env, get_service_preset
from services.common.config import ServiceConfig as BotConfig
from services.common.service_configs import (
    AudioConfig,
    DiscordConfig,
    DiscordRuntimeConfig,
    MCPConfig,
    OrchestratorClientConfig,
    STTConfig,
    TelemetryConfig,
    WakeConfig,
)


def load_config() -> BotConfig:
    """Load Discord configuration via shared configuration library."""
    return load_config_from_env(BotConfig, **get_service_preset("discord"))


__all__ = [
    "AudioConfig",
    "BotConfig",
    "DiscordConfig",
    "MCPConfig",
    "STTConfig",
    "TelemetryConfig",
    "WakeConfig",
    "OrchestratorClientConfig",
    # Backward-compat alias for tests that import OrchestratorConfig
    "OrchestratorConfig",
    "DiscordRuntimeConfig",
    "load_config",
]

# Backward-compat import alias
OrchestratorConfig = OrchestratorClientConfig
