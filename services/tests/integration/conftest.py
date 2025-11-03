"""Configuration and fixtures for integration tests.

This module provides environment-based service URL configuration using
standardized {SERVICE}_BASE_URL pattern with agnostic service names.
"""

from typing import Any

import pytest

from services.common.config.loader import get_env_with_default


def get_service_url(service_name: str) -> str:
    """Get service URL from environment variable with default.

    Uses standardized {SERVICE}_BASE_URL pattern with agnostic service names.
    Service names should be uppercase (e.g., "LLM", "TTS", "STT").

    Args:
        service_name: Service name (e.g., "LLM", "TTS", "STT", "ORCHESTRATOR")

    Returns:
        Service base URL loaded from environment or default Docker Compose URL
    """
    env_var = f"{service_name.upper()}_BASE_URL"

    # Default URLs based on Docker service names and internal ports
    defaults = {
        "STT": "http://stt:9000",
        "ORCHESTRATOR": "http://orchestrator:8200",
        "LLM": "http://flan:8100",  # Service: LLM, implementation: FLAN-T5
        "TTS": "http://bark:7100",  # Service: TTS, implementation: Bark
        "GUARDRAILS": "http://guardrails:9300",
        "DISCORD": "http://discord:8001",
        "TESTING": "http://testing:8080",
    }

    default_url = defaults.get(
        service_name.upper(), f"http://{service_name.lower()}:8000"
    )
    return get_env_with_default(env_var, default_url, str)


@pytest.fixture
def service_url() -> Any:
    """Pytest fixture factory for service URLs.

    Usage:
        def test_my_service(service_url):
            stt_url = service_url("STT")
            llm_url = service_url("LLM")
    """

    def _get_service_url(service_name: str) -> str:
        return get_service_url(service_name)

    return _get_service_url


@pytest.fixture
def all_service_urls() -> dict[str, str]:
    """Fixture providing all service URLs as a dictionary.

    Returns:
        Dict mapping service names (uppercase) to base URLs
    """
    services = [
        "AUDIO",
        "STT",
        "ORCHESTRATOR",
        "LLM",
        "TTS",
        "GUARDRAILS",
        "DISCORD",
        "TESTING",
    ]
    return {service: get_service_url(service) for service in services}
