"""Examples demonstrating how to use the configuration management library.

This module shows various ways to use the configuration system for different
services and scenarios.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .config import (
    BaseConfig,
    ConfigBuilder,
    Environment,
    create_field_definition,
    load_service_config,
)
from .service_configs import (
    AudioConfig,
    DiscordConfig,
    FasterWhisperConfig,
    HttpConfig,
    LlamaConfig,
    LoggingConfig,
    MCPConfig,
    OrchestratorConfig,
    STTConfig,
    TelemetryConfig,
    TTSConfig,
    WakeConfig,
)


def example_discord_service_config():
    """Example: Load configuration for Discord service."""
    print("=== Discord Service Configuration Example ===")

    # Method 1: Using the builder pattern
    builder = ConfigBuilder.for_service("discord", Environment.DOCKER)
    config = (
        builder.add_config("discord", DiscordConfig)
        .add_config("audio", AudioConfig)
        .add_config("stt", STTConfig)
        .add_config("wake", WakeConfig)
        .add_config("mcp", MCPConfig)
        .add_config("telemetry", TelemetryConfig)
        .load()
    )

    # Validate the configuration
    try:
        config.validate()
        print("✓ Configuration is valid")
    except Exception as e:
        print(f"✗ Configuration validation failed: {e}")
        return None

    # Access configuration values
    print(
        f"Discord token: {config.discord.token[:10]}..."
        if config.discord.token
        else "Not set"
    )
    print(f"Guild ID: {config.discord.guild_id}")
    print(f"Voice channel ID: {config.discord.voice_channel_id}")
    print(f"Audio sample rate: {config.audio.input_sample_rate_hz} Hz")
    print(f"STT base URL: {config.stt.base_url}")
    print(f"Wake phrases: {config.wake.wake_phrases}")

    # Convert to dictionary
    config_dict = config.to_dict()
    print(f"Configuration sections: {list(config_dict['configs'].keys())}")

    return config


def example_stt_service_config():
    """Example: Load configuration for STT service."""
    print("\n=== STT Service Configuration Example ===")

    # Method 2: Using the convenience function
    config = load_service_config("stt", Environment.DOCKER)

    # Add STT-specific configuration
    config.configs["faster_whisper"] = FasterWhisperConfig()

    # Set some environment variables for demonstration
    os.environ["STT_BASE_URL"] = "http://stt:9000"
    os.environ["FW_MODEL"] = "medium.en"
    os.environ["FW_DEVICE"] = "cpu"
    os.environ["FW_COMPUTE_TYPE"] = "int8"

    # Reload configuration to pick up environment variables
    builder = ConfigBuilder.for_service("stt", Environment.DOCKER)
    config = (
        builder.add_config("logging", config.configs["logging"])
        .add_config("http", config.configs["http"])
        .add_config("faster_whisper", FasterWhisperConfig)
        .load()
    )

    try:
        config.validate()
        print("✓ STT configuration is valid")
    except Exception as e:
        print(f"✗ STT configuration validation failed: {e}")
        return None

    print(f"Faster-whisper model: {config.faster_whisper.model}")
    print(f"Device: {config.faster_whisper.device}")
    print(f"Compute type: {config.faster_whisper.compute_type}")
    print(f"HTTP timeout: {config.http.timeout} seconds")

    return config


def example_tts_service_config():
    """Example: Load configuration for TTS service."""
    print("\n=== TTS Service Configuration Example ===")

    # Method 3: Manual configuration building
    builder = ConfigBuilder.for_service("tts", Environment.DOCKER)

    # Set environment variables for demonstration
    os.environ["TTS_MODEL_PATH"] = "/app/models/piper/en_US-amy-medium.onnx"
    os.environ["TTS_MODEL_CONFIG_PATH"] = "/app/models/piper/en_US-amy-medium.onnx.json"
    os.environ["TTS_MAX_TEXT_LENGTH"] = "2000"
    os.environ["TTS_MAX_CONCURRENCY"] = "8"
    os.environ["TTS_RATE_LIMIT_PER_MINUTE"] = "120"

    # Create a fresh builder for TTS service
    builder = ConfigBuilder.for_service("tts", Environment.DOCKER)
    config = (
        builder.add_config("logging", LoggingConfig)
        .add_config("http", HttpConfig)
        .add_config("tts", TTSConfig)
        .load()
    )

    try:
        config.validate()
        print("✓ TTS configuration is valid")
    except Exception as e:
        print(f"✗ TTS configuration validation failed: {e}")
        return None

    print(f"TTS port: {config.tts.port}")
    print(f"Model path: {config.tts.model_path}")
    print(f"Max text length: {config.tts.max_text_length}")
    print(f"Max concurrency: {config.tts.max_concurrency}")
    print(f"Rate limit: {config.tts.rate_limit_per_minute} requests/minute")

    return config


def example_orchestrator_service_config():
    """Example: Load configuration for orchestrator service."""
    print("\n=== Orchestrator Service Configuration Example ===")

    # Set environment variables for demonstration
    os.environ["LLAMA_MODEL_PATH"] = "/app/models/llama-2-7b.Q4_K_M.gguf"
    os.environ["LLAMA_CTX"] = "4096"
    os.environ["LLAMA_THREADS"] = "8"
    os.environ["TTS_BASE_URL"] = "http://tts:7000"
    os.environ["TTS_VOICE"] = "default"
    os.environ["ORCH_AUTH_TOKEN"] = "demo-token-12345"  # noqa: S105

    builder = ConfigBuilder.for_service("orchestrator", Environment.DOCKER)
    config = (
        builder.add_config(
            "logging", TelemetryConfig
        )  # Use TelemetryConfig for logging
        .add_config("http", HttpConfig)
        .add_config("llama", LlamaConfig)
        .add_config("orchestrator", OrchestratorConfig)
        .load()
    )

    try:
        config.validate()
        print("✓ Orchestrator configuration is valid")
    except Exception as e:
        print(f"✗ Orchestrator configuration validation failed: {e}")
        return None

    print(f"Orchestrator port: {config.orchestrator.port}")
    print(f"Llama model path: {config.llama.model_path}")
    print(f"Context length: {config.llama.context_length}")
    print(f"Threads: {config.llama.threads}")
    print(f"TTS base URL: {config.orchestrator.tts_base_url}")
    print(f"Auth token: {'Set' if config.orchestrator.auth_token else 'Not set'}")

    return config


def example_configuration_validation():
    """Example: Demonstrate configuration validation."""
    print("\n=== Configuration Validation Example ===")

    # Create a configuration with invalid values
    builder = ConfigBuilder.for_service("test", Environment.DEVELOPMENT)

    # Set invalid environment variables
    os.environ["TEST_PORT"] = "99999"  # Invalid port
    os.environ["TEST_TIMEOUT"] = "-1"  # Invalid timeout
    os.environ["TEST_URL"] = "not-a-url"  # Invalid URL

    # This would fail validation, but let's catch the exception
    try:
        from .config import HttpConfig

        config = builder.add_config("http", HttpConfig).load()
        config.validate()
        print("✓ Configuration is valid")
    except Exception as e:
        print(f"✗ Configuration validation failed as expected: {e}")

    # Clean up
    for key in ["TEST_PORT", "TEST_TIMEOUT", "TEST_URL"]:
        os.environ.pop(key, None)


def example_configuration_persistence():
    """Example: Save and load configuration from file."""
    print("\n=== Configuration Persistence Example ===")

    # Create a configuration
    config = load_service_config("discord", Environment.DOCKER)

    # Save to file
    config_file = Path(tempfile.mkstemp(suffix=".json")[1])  # nosec S108
    config.save_to_file(config_file)
    print(f"✓ Configuration saved to {config_file}")

    # Load from file
    try:
        loaded_config = config.__class__.load_from_file(config_file)
        print("✓ Configuration loaded from file")
        print(f"Service: {loaded_config.service_name}")
        print(f"Environment: {loaded_config.environment.value}")
    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")

    # Clean up
    if config_file.exists():
        config_file.unlink()


def example_custom_configuration():
    """Example: Create a custom configuration class."""
    print("\n=== Custom Configuration Example ===")

    class CustomServiceConfig(BaseConfig):
        """Custom service configuration example."""

        def __init__(
            self,
            service_name: str = "custom",
            max_connections: int = 100,
            enable_feature_x: bool = False,
            **kwargs,
        ):
            super().__init__(**kwargs)
            self.service_name = service_name
            self.max_connections = max_connections
            self.enable_feature_x = enable_feature_x

        @classmethod
        def get_field_definitions(cls):
            return [
                create_field_definition(
                    name="service_name",
                    field_type=str,
                    default="custom",
                    description="Name of the custom service",
                    env_var="CUSTOM_SERVICE_NAME",
                ),
                create_field_definition(
                    name="max_connections",
                    field_type=int,
                    default=100,
                    description="Maximum number of connections",
                    min_value=1,
                    max_value=1000,
                    env_var="CUSTOM_MAX_CONNECTIONS",
                ),
                create_field_definition(
                    name="enable_feature_x",
                    field_type=bool,
                    default=False,
                    description="Whether to enable feature X",
                    env_var="CUSTOM_ENABLE_FEATURE_X",
                ),
            ]

    # Use the custom configuration
    builder = ConfigBuilder.for_service("custom", Environment.DEVELOPMENT)
    config = builder.add_config("custom", CustomServiceConfig).load()

    try:
        config.validate()
        print("✓ Custom configuration is valid")
        print(f"Service name: {config.custom.service_name}")
        print(f"Max connections: {config.custom.max_connections}")
        print(f"Feature X enabled: {config.custom.enable_feature_x}")
    except Exception as e:
        print(f"✗ Custom configuration validation failed: {e}")


def main():
    """Run all configuration examples."""
    print("Configuration Management Library Examples")
    print("=" * 50)

    # Run examples
    example_discord_service_config()
    example_stt_service_config()
    example_tts_service_config()
    example_orchestrator_service_config()
    example_configuration_validation()
    example_configuration_persistence()
    example_custom_configuration()

    print("\n" + "=" * 50)
    print("All examples completed!")


if __name__ == "__main__":
    main()
