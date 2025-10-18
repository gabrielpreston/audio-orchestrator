"""Discord service configuration entrypoint using the shared config library."""

from __future__ import annotations

from services.common.config import ConfigBuilder, Environment
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
    return (
        ConfigBuilder.for_service("discord", Environment.DOCKER)
        .add_config("discord", DiscordConfig)
        .add_config("audio", AudioConfig)
        .add_config("stt", STTConfig)
        .add_config("wake", WakeConfig)
        .add_config("mcp", MCPConfig)
        .add_config("telemetry", TelemetryConfig)
        .add_config("orchestrator", OrchestratorClientConfig)
        .add_config("runtime", DiscordRuntimeConfig)
        .load()
    )


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
