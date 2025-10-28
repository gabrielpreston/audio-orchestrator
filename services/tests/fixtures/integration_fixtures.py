"""Fixtures for integration tests."""

import asyncio
import base64
from typing import Any

import httpx
import pytest

from services.tests.utils.audio_quality_helpers import (
    create_wav_file,
    generate_test_audio,
)

# Service configuration constants
SERVICES = [
    ("stt", "http://stt:9000"),
    ("bark", "http://bark:7100"),
    ("flan", "http://flan:8100"),
    ("orchestrator", "http://orchestrator:8200"),
]


# Standard timeout constants
class Timeouts:
    """Standard timeout values for integration tests."""

    HEALTH_CHECK = 5.0  # Health endpoint checks
    SHORT = 1.0  # Fast operations that should fail quickly
    STRESS_TEST = 0.1  # Intentional timeout testing
    STANDARD = 30.0  # Normal HTTP requests
    LONG_RUNNING = 60.0  # STT, LLM, orchestrator processing


@pytest.fixture
async def http_client():
    """Shared HTTP client for integration tests.

    Provides a function-scoped httpx.AsyncClient for integration tests.
    Each test gets a fresh client with automatic connection pooling.
    """
    async with httpx.AsyncClient() as client:
        yield client


@pytest.fixture
def services():
    """Standard services list for integration tests.

    Returns list of (service_name, base_url) tuples for all services.
    """
    return SERVICES.copy()


@pytest.fixture
def timeouts():
    """Standard timeout values for integration tests."""
    return Timeouts


@pytest.fixture
def sample_audio_bytes() -> bytes:
    """Generate sample audio as bytes for HTTP requests."""
    pcm_data = generate_test_audio(duration=2.0, frequency=440.0, amplitude=0.5)
    return create_wav_file(pcm_data, sample_rate=16000, channels=1)


@pytest.fixture
def base64_audio(sample_audio_bytes: bytes) -> str:
    """Base64-encoded audio for JSON requests."""
    return base64.b64encode(sample_audio_bytes).decode()


@pytest.fixture
def test_transcript() -> str:
    """Sample transcript for testing."""
    return "hello world, this is a test"


@pytest.fixture
def test_auth_token() -> str:
    """Test authentication token."""
    return "test-token"


@pytest.fixture
def test_guild_id() -> str:
    """Test Discord guild ID."""
    return "123456789"


@pytest.fixture
def test_channel_id() -> str:
    """Test Discord channel ID."""
    return "987654321"


@pytest.fixture
def test_user_id() -> str:
    """Test Discord user ID."""
    return "12345"


@pytest.fixture
def test_correlation_id() -> str:
    """Test correlation ID for request tracking."""
    return "test-correlation-1234567890abcdef"


# REST API fixtures removed - using REST API now


# Health check utilities
async def check_service_health(
    client: httpx.AsyncClient,
    base_url: str,
    timeout: float = Timeouts.HEALTH_CHECK,
) -> bool:
    """Check if a service health/live endpoint responds with 200.

    Args:
        client: httpx AsyncClient instance
        base_url: Service base URL (e.g., "http://stt:9000")
        timeout: Request timeout in seconds

    Returns:
        True if service responds with 200, False otherwise
    """
    try:
        response = await client.get(f"{base_url}/health/live", timeout=timeout)
        return response.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


async def check_service_ready(
    client: httpx.AsyncClient,
    base_url: str,
    timeout: float = Timeouts.HEALTH_CHECK,
) -> bool:
    """Check if a service health/ready endpoint responds with 200.

    Args:
        client: httpx AsyncClient instance
        base_url: Service base URL (e.g., "http://stt:9000")
        timeout: Request timeout in seconds

    Returns:
        True if service responds with 200, False otherwise
    """
    try:
        response = await client.get(f"{base_url}/health/ready", timeout=timeout)
        return response.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


async def get_service_health_details(
    client: httpx.AsyncClient,
    base_url: str,
    timeout: float = Timeouts.HEALTH_CHECK,
) -> dict[str, Any] | None:
    """Get detailed health status from a service.

    Args:
        client: httpx AsyncClient instance
        base_url: Service base URL (e.g., "http://stt:9000")
        timeout: Request timeout in seconds

    Returns:
        Health details dict if service responds with 200, None otherwise
    """
    try:
        response = await client.get(f"{base_url}/health/ready", timeout=timeout)
        if response.status_code == 200:
            return response.json()
        return None
    except (httpx.ConnectError, httpx.TimeoutException):
        return None


async def get_service_metrics(
    client: httpx.AsyncClient,
    base_url: str,
    timeout: float = Timeouts.HEALTH_CHECK,
) -> str | None:
    """Get Prometheus metrics from a service.

    Args:
        client: httpx AsyncClient instance
        base_url: Service base URL (e.g., "http://stt:9000")
        timeout: Request timeout in seconds

    Returns:
        Metrics text if service responds with 200, None otherwise
    """
    try:
        response = await client.get(f"{base_url}/metrics", timeout=timeout)
        if response.status_code == 200:
            return response.text
        return None
    except (httpx.ConnectError, httpx.TimeoutException):
        return None


async def check_all_services_health(
    client: httpx.AsyncClient,
    service_list: list[tuple[str, str]],
    timeout: float = Timeouts.HEALTH_CHECK,
) -> dict[str, bool]:
    """Check health status of all services.

    Args:
        client: httpx AsyncClient instance
        service_list: List of (service_name, base_url) tuples
        timeout: Request timeout in seconds

    Returns:
        Dict mapping service_name to health status (True/False)
    """
    results = {}
    for service_name, base_url in service_list:
        results[service_name] = await check_service_health(client, base_url, timeout)
    return results


async def check_all_services_ready(
    client: httpx.AsyncClient,
    service_list: list[tuple[str, str]],
    timeout: float = Timeouts.HEALTH_CHECK,
) -> dict[str, bool]:
    """Check readiness status of all services.

    Args:
        client: httpx AsyncClient instance
        service_list: List of (service_name, base_url) tuples
        timeout: Request timeout in seconds

    Returns:
        Dict mapping service_name to readiness status (True/False)
    """
    results = {}
    for service_name, base_url in service_list:
        results[service_name] = await check_service_ready(client, base_url, timeout)
    return results


# Retry utilities
async def retry_request(
    client: httpx.AsyncClient,
    url: str,
    max_attempts: int = 3,
    retry_delay: float = 1.0,
    timeout: float = Timeouts.STANDARD,
    **kwargs,
) -> httpx.Response:
    """Retry HTTP request with exponential backoff.

    Args:
        client: httpx AsyncClient instance
        url: Request URL
        max_attempts: Maximum retry attempts
        retry_delay: Initial delay between retries in seconds
        timeout: Request timeout in seconds
        **kwargs: Additional arguments passed to client.get()

    Returns:
        httpx.Response object

    Raises:
        httpx.ConnectError: If all retry attempts fail
    """
    for attempt in range(max_attempts):
        try:
            response = await client.get(url, timeout=timeout, **kwargs)
            if response.status_code == 200:
                return response
        except httpx.ConnectError:
            if attempt == max_attempts - 1:
                raise
            await asyncio.sleep(retry_delay * (2**attempt))
    raise httpx.ConnectError(f"Failed after {max_attempts} attempts")
