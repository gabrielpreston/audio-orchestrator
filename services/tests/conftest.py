"""Global test configuration and fixtures for audio-orchestrator."""

from collections.abc import Generator
import os
from pathlib import Path
import random
import shutil
import tempfile
from typing import Any
from unittest import mock

from freezegun import freeze_time
import pytest
import structlog

# Import integration test fixtures
from services.tests.fixtures.integration_fixtures import *  # noqa: F401, F403
from services.tests.fixtures.voice_pipeline_fixtures import *  # noqa: F401, F403


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
def reset_environment():
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


@pytest.fixture(scope="session")
def test_artifacts_dir() -> Generator[Path, None, None]:
    """Centralized test artifacts directory with auto-cleanup."""
    artifacts_dir = Path(os.getenv("TEST_ARTIFACTS_DIR", "test_artifacts"))
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    yield artifacts_dir
    # Cleanup after all tests
    if artifacts_dir.exists():
        shutil.rmtree(artifacts_dir, ignore_errors=True)


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
def test_config() -> dict[str, Any]:
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


# Interface-first testing fixtures
@pytest.fixture
def service_contracts():
    """Fixture for service contracts."""
    from services.tests.contracts.audio_preprocessor_contract import (
        AUDIO_PREPROCESSOR_CONTRACT,
    )
    from services.tests.contracts.audio_contract import (
        AUDIO_PROCESSOR_CONTRACT,
    )
    from services.tests.contracts.discord_contract import DISCORD_CONTRACT
    from services.tests.contracts.guardrails_contract import GUARDRAILS_CONTRACT
    from services.tests.contracts.llm_contract import LLM_CONTRACT
    from services.tests.contracts.orchestrator_contract import ORCHESTRATOR_CONTRACT
    from services.tests.contracts.stt_contract import STT_CONTRACT
    from services.tests.contracts.tts_contract import TTS_CONTRACT

    return {
        "stt": STT_CONTRACT,
        "llm": LLM_CONTRACT,
        "tts": TTS_CONTRACT,
        "orchestrator": ORCHESTRATOR_CONTRACT,
        "audio": AUDIO_PROCESSOR_CONTRACT,
        "audio_preprocessor": AUDIO_PREPROCESSOR_CONTRACT,
        "guardrails": GUARDRAILS_CONTRACT,
        "discord": DISCORD_CONTRACT,
    }


@pytest.fixture
def contract_validators():
    """Fixture for contract validators."""
    from services.tests.utils.contract_validators import ContractValidator

    return ContractValidator


@pytest.fixture
def protocol_implementations():
    """Fixture for protocol implementations."""
    from services.common.surfaces.protocols import (
        AudioCaptureProtocol,
        AudioPlaybackProtocol,
        SurfaceControlProtocol,
        SurfaceTelemetryProtocol,
    )
    from services.tests.utils.protocol_testing import create_protocol_mock

    return {
        "AudioCaptureProtocol": AudioCaptureProtocol,
        "AudioPlaybackProtocol": AudioPlaybackProtocol,
        "SurfaceControlProtocol": SurfaceControlProtocol,
        "SurfaceTelemetryProtocol": SurfaceTelemetryProtocol,
        "create_mock": create_protocol_mock,
    }


@pytest.fixture
def mock_pcm_frames():
    """Fixture for mock PCMFrame objects."""
    import time

    from services.common.surfaces.types import PCMFrame

    return [
        PCMFrame(
            pcm=b"\x00\x01\x02\x03" * 1000,
            sample_rate=16000,
            channels=1,
            timestamp=time.time(),
            rms=0.5,
            duration=0.1,
            sequence=1,
        ),
        PCMFrame(
            pcm=b"\x04\x05\x06\x07" * 1000,
            sample_rate=16000,
            channels=1,
            timestamp=time.time(),
            rms=0.5,
            duration=0.1,
            sequence=2,
        ),
        PCMFrame(
            pcm=b"\x08\x09\x0a\x0b" * 1000,
            sample_rate=16000,
            channels=1,
            timestamp=time.time(),
            rms=0.5,
            duration=0.1,
            sequence=3,
        ),
    ]


@pytest.fixture
def service_discovery_fixtures():
    """Fixture for service discovery testing."""
    return {
        "stt_implementations": [
            "http://stt:9000",
            "http://stt-alternative:9000",
            "http://stt-backup:9000",
        ],
        "llm_implementations": [
            "http://llm:8100",
            "http://llm-alternative:8100",
            "http://llm-backup:8100",
        ],
        "tts_implementations": [
            "http://tts:7100",
            "http://tts-alternative:7100",
            "http://tts-backup:7100",
        ],
    }


# Pytest configuration
def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest - markers are now defined in pyproject.toml only."""
    # Markers are now defined in pyproject.toml - no need to register here
    # This function is kept for any future pytest configuration needs
    pass


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Automatically assign markers based on test file location and industry standards."""
    for item in items:
        # Get the test file path relative to the tests directory
        test_path = str(item.fspath)
        if "services/tests/" in test_path:
            relative_path = test_path.split("services/tests/")[1]
        else:
            continue

        # Primary markers based on industry-standard directory structure
        if relative_path.startswith("unit/"):
            item.add_marker(pytest.mark.unit)
        elif relative_path.startswith("component/"):
            item.add_marker(pytest.mark.component)
        elif relative_path.startswith("integration/"):
            item.add_marker(pytest.mark.integration)
        elif relative_path.startswith("e2e/"):
            item.add_marker(pytest.mark.e2e)

        # Secondary markers for interface-first testing (dual marking)
        if relative_path.startswith("component/interfaces/"):
            item.add_marker(pytest.mark.interface)
        elif relative_path.startswith("integration/contracts/"):
            item.add_marker(pytest.mark.contract)
        elif relative_path.startswith("integration/hot_swap/"):
            item.add_marker(pytest.mark.hot_swap)
        elif relative_path.startswith("integration/security/"):
            item.add_marker(pytest.mark.security)
        elif relative_path.startswith("integration/performance/"):
            item.add_marker(pytest.mark.performance)

        # Service-specific markers (legacy - being phased out)
        if "discord" in relative_path:
            item.add_marker(pytest.mark.discord)
        if "stt" in relative_path:
            item.add_marker(pytest.mark.stt)
        if "tts" in relative_path:
            item.add_marker(pytest.mark.tts)
        if "llm" in relative_path:
            item.add_marker(pytest.mark.llm)
        if "orchestrator" in relative_path:
            item.add_marker(pytest.mark.orchestrator)
        if "audio" in relative_path or "audio" in item.name:
            item.add_marker(pytest.mark.audio)


@pytest.fixture
def tts_artifacts_dir(test_artifacts_dir: Path) -> Path:
    """Get TTS test artifacts directory."""
    tts_dir = test_artifacts_dir / "tts"
    tts_dir.mkdir(parents=True, exist_ok=True)
    return tts_dir
