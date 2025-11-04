"""Integration tests for Orchestrator service endpoints.

Tests focus on direct Orchestrator service endpoints that are not covered by
the text pipeline tests, including capabilities, status, and health checks.
"""

import httpx
import pytest

from services.tests.fixtures.integration_fixtures import Timeouts
from services.tests.integration.conftest import get_service_url
from services.tests.utils.service_helpers import docker_compose_test_context


# ============================================================================
# Orchestrator Service Endpoint Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_orchestrator_capabilities():
    """Test Orchestrator service /api/v1/capabilities endpoint."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        response = await client.get(
            f"{orchestrator_url}/api/v1/capabilities",
            timeout=Timeouts.STANDARD,
        )

        assert (
            response.status_code == 200
        ), f"Capabilities endpoint failed: {response.text}"
        data = response.json()

        # Validate response structure matches CapabilitiesResponse model
        assert "service" in data, "Response should contain service field"
        assert "capabilities" in data, "Response should contain capabilities field"
        assert "version" in data, "Response should contain version field"

        # Validate service name
        assert data["service"] == "orchestrator", "Service should be 'orchestrator'"

        # Validate capabilities is a list
        assert isinstance(data["capabilities"], list), "Capabilities should be a list"

        # Validate capability structure (if any capabilities are returned)
        if len(data["capabilities"]) > 0:
            capability = data["capabilities"][0]
            assert "name" in capability, "Capability should have name"
            assert isinstance(
                capability["name"], str
            ), "Capability name should be a string"
            if "description" in capability:
                assert isinstance(
                    capability["description"], str
                ), "Capability description should be a string"
            if "parameters" in capability:
                assert isinstance(
                    capability["parameters"], dict
                ), "Capability parameters should be a dict"

        # Validate version
        assert isinstance(data["version"], str), "Version should be a string"
        assert len(data["version"]) > 0, "Version should not be empty"


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_orchestrator_status():
    """Test Orchestrator service /api/v1/status endpoint."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        response = await client.get(
            f"{orchestrator_url}/api/v1/status",
            timeout=Timeouts.STANDARD,
        )

        assert response.status_code == 200, f"Status endpoint failed: {response.text}"
        data = response.json()

        # Validate response structure matches StatusResponse model
        assert "service" in data, "Response should contain service field"
        assert "status" in data, "Response should contain status field"
        assert "connections" in data, "Response should contain connections field"
        assert "version" in data, "Response should contain version field"

        # Validate service name
        assert data["service"] == "orchestrator", "Service should be 'orchestrator'"

        # Validate status is a string
        assert isinstance(data["status"], str), "Status should be a string"
        assert len(data["status"]) > 0, "Status should not be empty"

        # Validate connections is a list
        assert isinstance(data["connections"], list), "Connections should be a list"

        # Validate connection structure (if any connections are returned)
        if len(data["connections"]) > 0:
            connection = data["connections"][0]
            assert "service" in connection, "Connection should have service field"
            assert "status" in connection, "Connection should have status field"
            assert isinstance(
                connection["service"], str
            ), "Connection service should be a string"
            assert isinstance(
                connection["status"], str
            ), "Connection status should be a string"
            if "url" in connection and connection["url"] is not None:
                assert isinstance(
                    connection["url"], str
                ), "Connection URL should be a string"

        # Validate version
        assert isinstance(data["version"], str), "Version should be a string"
        assert len(data["version"]) > 0, "Version should not be empty"

        # Validate optional fields
        if "uptime" in data and data["uptime"] is not None:
            assert isinstance(data["uptime"], str), "Uptime should be a string"


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_orchestrator_health_live():
    """Test Orchestrator service /health/live endpoint."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        response = await client.get(
            f"{orchestrator_url}/health/live",
            timeout=Timeouts.STANDARD,
        )

        assert response.status_code == 200, f"Health live failed: {response.text}"
        data = response.json()

        # Validate response structure
        assert "status" in data, "Response should contain status field"
        assert data["status"] == "alive", "Status should be 'alive'"
        assert "service" in data, "Response should contain service field"
        assert data["service"] == "orchestrator", "Service should be 'orchestrator'"


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_orchestrator_health_ready():
    """Test Orchestrator service /health/ready endpoint."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        response = await client.get(
            f"{orchestrator_url}/health/ready",
            timeout=Timeouts.STANDARD,
        )

        # Service may be ready (200) or not ready (503) depending on dependency status
        assert response.status_code in [
            200,
            503,
        ], f"Health ready returned unexpected status: {response.status_code}"

        data = response.json()

        # Validate response structure
        assert "status" in data, "Response should contain status field"
        assert "service" in data, "Response should contain service field"
        assert data["service"] == "orchestrator", "Service should be 'orchestrator'"

        if response.status_code == 200:
            assert (
                data["status"] == "ready"
            ), "Status should be 'ready' when service is ready"
        else:
            assert (
                data["status"] == "not_ready"
            ), "Status should be 'not_ready' when service is not ready"


@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_orchestrator_status_error_handling():
    """Test Orchestrator service status endpoint handles dependency failures gracefully."""
    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        # Status endpoint should still return 200 even if dependencies have issues
        # (it reports the status, not fail)
        response = await client.get(
            f"{orchestrator_url}/api/v1/status",
            timeout=Timeouts.STANDARD,
        )

        # Status endpoint should always return 200 (it's informational)
        assert (
            response.status_code == 200
        ), "Status endpoint should return 200 even with dependency issues"

        data = response.json()
        assert "service" in data, "Response should contain service field"
        assert "connections" in data, "Response should contain connections field"

        # Connections may show failed status, but endpoint should still work
        for connection in data.get("connections", []):
            assert "service" in connection, "Connection should have service field"
            assert "status" in connection, "Connection should have status field"
            # Status may be "connected" or "disconnected" or similar, but should be present
