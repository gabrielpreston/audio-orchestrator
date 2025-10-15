"""Test configuration for services.common module."""

import os
from collections.abc import Generator
from pathlib import Path
from unittest import mock

import pytest

from services.common.config import ServiceConfig
from services.common.service_configs import (AudioConfig, DiscordConfig,
                                             HttpConfig, LoggingConfig)


@pytest.fixture
def mock_environment() -> Generator[dict[str, str], None, None]:
    """Mock environment variables for testing."""
    with mock.patch.dict(os.environ, {}, clear=True):
        yield {}


@pytest.fixture
def test_logging_config() -> LoggingConfig:
    """Provide a test logging configuration."""
    return LoggingConfig(level="DEBUG", json_logs=True, service_name="test-service")


@pytest.fixture
def test_http_config() -> HttpConfig:
    """Provide a test HTTP configuration."""
    return HttpConfig(
        timeout=30.0, max_retries=3, retry_delay=1.0, user_agent="test-agent/1.0"
    )


@pytest.fixture
def test_audio_config() -> AudioConfig:
    """Provide a test audio configuration."""
    return AudioConfig(
        silence_timeout_seconds=1.0,
        max_segment_duration_seconds=15.0,
        input_sample_rate_hz=48000,
        vad_sample_rate_hz=16000,
    )


@pytest.fixture
def test_discord_config() -> DiscordConfig:
    """Provide a test Discord configuration."""
    return DiscordConfig(
        token="test-token",
        guild_id=123456789,
        voice_channel_id=987654321,
        intents=["guilds", "voice_states"],
        auto_join=False,
    )


@pytest.fixture
def test_service_config(
    test_logging_config: LoggingConfig, test_http_config: HttpConfig
) -> ServiceConfig:
    """Provide a test service configuration."""
    return ServiceConfig(
        service_name="test-service",
        environment="development",
        configs={"logging": test_logging_config, "http": test_http_config},
    )


@pytest.fixture
def temp_config_file(tmp_path: Path) -> Path:
    """Create a temporary configuration file for testing."""
    config_file = tmp_path / "test_config.json"
    config_file.write_text('{"test": "value"}')
    return config_file
