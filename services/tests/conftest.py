"""Global test configuration and fixtures for discord-voice-lab."""

import os
import random
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator
from unittest import mock

import pytest
import structlog
from freezegun import freeze_time


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment() -> None:
    """Set up the test environment for deterministic testing."""
    # Set timezone to UTC for consistent time handling
    os.environ["TZ"] = "UTC"

    # Disable Python bytecode generation
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

    # Set deterministic random seeds
    random.seed(42)
    os.environ["PYTHONHASHSEED"] = "42"

    # Configure structured logging for tests
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


@pytest.fixture(autouse=True)
def reset_environment() -> None:
    """Reset environment variables before each test."""
    # Store original environment
    original_env = os.environ.copy()

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def mock_time() -> Generator[Any, None, None]:
    """Freeze time for deterministic testing."""
    with freeze_time("2024-01-01 12:00:00") as frozen_time:
        yield frozen_time


@pytest.fixture
def mock_uuid() -> Generator[Any, None, None]:
    """Mock UUID generation for deterministic correlation IDs."""
    with mock.patch("uuid.uuid4") as mock_uuid_func:
        mock_uuid_func.return_value = mock.Mock(hex="1234567890abcdef")
        yield mock_uuid_func


@pytest.fixture
def mock_random() -> Generator[Any, None, None]:
    """Mock random number generation for deterministic testing."""
    with mock.patch("random.random") as mock_random_func:
        mock_random_func.return_value = 0.5
        yield mock_random_func


@pytest.fixture
def test_config() -> Dict[str, Any]:
    """Provide test configuration values."""
    return {
        "log_level": "DEBUG",
        "log_json": True,
        "timeout": 30.0,
        "max_retries": 3,
        "retry_delay": 1.0,
    }


@pytest.fixture
def correlation_id() -> str:
    """Provide a deterministic correlation ID for testing."""
    return "test-correlation-1234567890abcdef"


@pytest.fixture
def mock_audio_data() -> bytes:
    """Provide mock audio data for testing."""
    # Simple WAV file header + minimal audio data
    return b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x40\x1f\x00\x00\x80\x3e\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"


@pytest.fixture
def mock_audio_file(temp_dir: Path, mock_audio_data: bytes) -> Path:
    """Create a mock audio file for testing."""
    audio_file = temp_dir / "test_audio.wav"
    audio_file.write_bytes(mock_audio_data)
    return audio_file


# Pytest configuration
def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: Unit tests (fast, isolated, no external dependencies)"
    )
    config.addinivalue_line(
        "markers", "component: Component tests (with mocked external dependencies)"
    )
    config.addinivalue_line("markers", "integration: Integration tests (require Docker Compose)")
    config.addinivalue_line("markers", "e2e: End-to-end tests (manual trigger only)")
    config.addinivalue_line("markers", "slow: Slow tests (>1 second execution time)")
    config.addinivalue_line(
        "markers", "external: Tests requiring external services or network access"
    )
    config.addinivalue_line("markers", "audio: Tests involving audio processing")
    config.addinivalue_line("markers", "discord: Tests involving Discord API")
    config.addinivalue_line("markers", "stt: Tests involving speech-to-text")
    config.addinivalue_line("markers", "tts: Tests involving text-to-speech")
    config.addinivalue_line("markers", "llm: Tests involving language model")
    config.addinivalue_line("markers", "orchestrator: Tests involving orchestration logic")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Modify test collection to add markers based on test location."""
    for item in items:
        # Add markers based on test file location
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "component" in str(item.fspath):
            item.add_marker(pytest.mark.component)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)

        # Add service-specific markers
        if "discord" in str(item.fspath):
            item.add_marker(pytest.mark.discord)
        elif "stt" in str(item.fspath):
            item.add_marker(pytest.mark.stt)
        elif "tts" in str(item.fspath):
            item.add_marker(pytest.mark.tts)
        elif "llm" in str(item.fspath):
            item.add_marker(pytest.mark.llm)
        elif "orchestrator" in str(item.fspath):
            item.add_marker(pytest.mark.orchestrator)

        # Add audio marker for audio-related tests
        if "audio" in str(item.fspath) or "audio" in item.name:
            item.add_marker(pytest.mark.audio)
