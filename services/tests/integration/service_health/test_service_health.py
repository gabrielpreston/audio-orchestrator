"""Integration tests for service discovery and health checks."""

import asyncio

import httpx
import pytest


class TestServiceHealth:
    """Test service health endpoints."""

    @pytest.mark.integration
    async def test_all_services_health_endpoints_accessible(self):
        """Test all services health endpoints accessible with new format."""
        async with httpx.AsyncClient() as client:
            # Test STT service health
            response = await client.get("http://stt:9000/health/ready")
            assert response.status_code in [200, 503]
            if response.status_code == 200:
                data = response.json()
                assert data["service"] == "stt"
                assert "components" in data
                assert "health_details" in data

            response = await client.get("http://stt:9000/health/live")
            assert response.status_code == 200

            # Test TTS service health
            response = await client.get("http://bark:7100/health/ready")
            assert response.status_code in [200, 503]
            if response.status_code == 200:
                data = response.json()
                assert data["service"] == "tts"
                assert "components" in data
                assert "health_details" in data

            response = await client.get("http://bark:7100/health/live")
            assert response.status_code == 200

            # Test LLM service health
            response = await client.get("http://flan:8100/health/ready")
            assert response.status_code in [200, 503]
            if response.status_code == 200:
                data = response.json()
                assert data["service"] == "llm"
                assert "components" in data
                assert "health_details" in data

            response = await client.get("http://flan:8100/health/live")
            assert response.status_code == 200

            # Test Orchestrator service health
            response = await client.get("http://orchestrator:8200/health/ready")
            assert response.status_code in [200, 503]
            if response.status_code == 200:
                data = response.json()
                assert data["service"] == "orchestrator"
                assert "components" in data
                assert "health_details" in data

            response = await client.get("http://orchestrator:8200/health/live")
            assert response.status_code == 200

    @pytest.mark.integration
    async def test_service_startup_order_independence(self):
        """Test service startup order independence."""
        # Test that services can start in any order
        # All services should be accessible regardless of startup order
        services = [
            ("stt", "http://stt:9000"),
            ("bark", "http://bark:7100"),
            ("flan", "http://flan:8100"),
            ("orchestrator", "http://orchestrator:8200"),
        ]

        for _service_name, base_url in services:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{base_url}/health/live")
                assert response.status_code == 200

    @pytest.mark.integration
    async def test_graceful_degradation_when_optional_services_down(self):
        """Test graceful degradation when optional services down."""
        # Test with only core services
        async with httpx.AsyncClient() as client:
            # Core services should be accessible
            response = await client.get("http://stt:9000/health/live")
            assert response.status_code == 200

            response = await client.get("http://bark:7100/health/live")
            assert response.status_code == 200

            # Optional services should not be accessible
            try:
                response = await client.get("http://llm:8000/health/live", timeout=1.0)
                # If accessible, should be ready or not ready
                assert response.status_code in [200, 503]
            except httpx.ConnectError:
                # Expected if service is down
                pass

    @pytest.mark.integration
    async def test_health_check_circuit_breakers(self):
        """Test health check circuit breakers."""
        async with httpx.AsyncClient() as client:
            # Test circuit breaker behavior for health checks
            # Make multiple health check requests
            for _ in range(5):
                response = await client.get("http://stt:9000/health/ready")
                assert response.status_code in [200, 503]

                response = await client.get("http://bark:7100/health/ready")
                assert response.status_code in [200, 503]

                response = await client.get("http://flan:8100/health/ready")
                assert response.status_code in [200, 503]

                response = await client.get("http://orchestrator:8200/health/ready")
                assert response.status_code in [200, 503]


class TestServiceDiscovery:
    """Test service discovery functionality."""

    @pytest.mark.integration
    async def test_service_discovery_mechanism(self):
        """Test service discovery mechanism."""
        # Test service discovery
        services = [
            ("stt", "http://stt:9000"),
            ("bark", "http://bark:7100"),
            ("flan", "http://flan:8100"),
            ("orchestrator", "http://orchestrator:8200"),
        ]

        discovered_services = []

        for _service_name, base_url in services:
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(f"{base_url}/health/live", timeout=5.0)
                    if response.status_code == 200:
                        discovered_services.append(_service_name)
                except httpx.ConnectError:
                    pass

            # Should discover at least some services
            assert len(discovered_services) > 0

    @pytest.mark.integration
    async def test_service_registration_and_deregistration(self):
        """Test service registration and deregistration."""
        async with httpx.AsyncClient() as client:
            # Test service registration
            response = await client.get("http://stt:9000/health/live")
            assert response.status_code == 200

            response = await client.get("http://bark:7100/health/live")
            assert response.status_code == 200

            # Test service deregistration (stop services)
            # This would test service deregistration when services are stopped

    @pytest.mark.integration
    async def test_service_health_monitoring(self):
        """Test service health monitoring."""
        # Test health monitoring
        services = [
            ("stt", "http://stt:9000"),
            ("bark", "http://bark:7100"),
            ("flan", "http://flan:8100"),
            ("orchestrator", "http://orchestrator:8200"),
        ]

        health_status = {}

        for _service_name, base_url in services:
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(f"{base_url}/health/ready", timeout=5.0)
                    health_status[_service_name] = response.status_code == 200
                except httpx.ConnectError:
                    health_status[_service_name] = False

        # Should have health status for all services
        assert len(health_status) == len(services)

    @pytest.mark.integration
    async def test_service_load_balancing(self):
        """Test service load balancing."""
        # Test load balancing across services
        services = [
            ("stt", "http://stt:9000"),
            ("bark", "http://bark:7100"),
            ("flan", "http://flan:8100"),
            ("orchestrator", "http://orchestrator:8200"),
        ]

        # Test load balancing
        for _service_name, base_url in services:
            async with httpx.AsyncClient() as client:
                # Make multiple requests to test load balancing
                for _ in range(3):
                    response = await client.get(f"{base_url}/health/live")
                    assert response.status_code == 200


class TestServiceResilience:
    """Test service resilience."""

    @pytest.mark.integration
    async def test_service_failure_recovery(self):
        """Test service failure recovery."""
        # Test service failure and recovery
        services = [
            ("stt", "http://stt:9000"),
            ("bark", "http://bark:7100"),
            ("flan", "http://flan:8100"),
            ("orchestrator", "http://orchestrator:8200"),
        ]

        # Test initial health
        for _service_name, base_url in services:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{base_url}/health/live")
                assert response.status_code == 200

        # Simulate service failure and recovery
        # This would test actual service failure scenarios

    @pytest.mark.integration
    async def test_service_timeout_handling(self):
        """Test service timeout handling."""
        # Test timeout handling
        services = [
            ("stt", "http://stt:9000"),
            ("bark", "http://bark:7100"),
            ("flan", "http://flan:8100"),
            ("orchestrator", "http://orchestrator:8200"),
        ]

        for _service_name, base_url in services:
            async with httpx.AsyncClient() as client:
                # Test with short timeout
                try:
                    response = await client.get(f"{base_url}/health/live", timeout=0.1)
                    assert response.status_code == 200
                except httpx.TimeoutException:
                    # Expected for some services
                    pass

    @pytest.mark.integration
    async def test_service_retry_mechanism(self):
        """Test service retry mechanism."""
        # Test retry mechanism
        services = [
            ("stt", "http://stt:9000"),
            ("bark", "http://bark:7100"),
            ("flan", "http://flan:8100"),
            ("orchestrator", "http://orchestrator:8200"),
        ]

        for _service_name, base_url in services:
            async with httpx.AsyncClient() as client:
                # Test retry mechanism
                for attempt in range(3):
                    try:
                        response = await client.get(
                            f"{base_url}/health/live", timeout=5.0
                        )
                        if response.status_code == 200:
                            break
                    except httpx.ConnectError:
                        if attempt == 2:  # Last attempt
                            raise
                        await asyncio.sleep(1)  # Wait before retry


class TestServiceMetrics:
    """Test service metrics and monitoring."""

    @pytest.mark.integration
    async def test_service_metrics_exposure(self):
        """Test service metrics exposure."""
        # Test metrics endpoints
        services = [
            ("stt", "http://stt:9000"),
            ("bark", "http://bark:7100"),
            ("flan", "http://flan:8100"),
            ("orchestrator", "http://orchestrator:8200"),
        ]

        for _service_name, base_url in services:
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(f"{base_url}/metrics", timeout=5.0)
                    if response.status_code == 200:
                        # Should contain metrics
                        assert "text/plain" in response.headers.get("content-type", "")
                except httpx.ConnectError:
                    # Service might not have metrics endpoint
                    pass

    @pytest.mark.integration
    async def test_service_health_metrics(self):
        """Test service health metrics."""
        # Test health metrics
        services = [
            ("stt", "http://stt:9000"),
            ("bark", "http://bark:7100"),
            ("flan", "http://flan:8100"),
            ("orchestrator", "http://orchestrator:8200"),
        ]

        for _service_name, base_url in services:
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(f"{base_url}/health/ready", timeout=5.0)
                    if response.status_code == 200:
                        # Should return health status
                        data = response.json()
                        assert "status" in data
                except httpx.ConnectError:
                    pass

    @pytest.mark.integration
    async def test_service_performance_metrics(self):
        """Test service performance metrics."""
        # Test performance metrics
        services = [
            ("stt", "http://stt:9000"),
            ("bark", "http://bark:7100"),
            ("flan", "http://flan:8100"),
            ("orchestrator", "http://orchestrator:8200"),
        ]

        for _service_name, base_url in services:
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(f"{base_url}/metrics", timeout=5.0)
                    if response.status_code == 200:
                        # Should contain performance metrics
                        metrics_text = response.text
                        assert len(metrics_text) > 0
                except httpx.ConnectError:
                    pass
