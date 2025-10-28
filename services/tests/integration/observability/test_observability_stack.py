"""Integration tests for the OpenTelemetry observability stack."""

import asyncio
import pytest
import httpx

from services.tests.utils.service_helpers import docker_compose_test_context


@pytest.mark.integration
async def test_otel_collector_health():
    """Test OTel Collector health endpoint."""
    async with (
        docker_compose_test_context(["otel-collector"]),
        httpx.AsyncClient() as client,
    ):
        response = await client.get("http://otel-collector:13133/")
        assert response.status_code == 200


@pytest.mark.integration
async def test_prometheus_scraping_otel_collector():
    """Test Prometheus can scrape metrics from OTel Collector."""
    async with docker_compose_test_context(["otel-collector", "prometheus"]):
        # Wait for Prometheus to scrape
        await asyncio.sleep(30)

        async with httpx.AsyncClient() as client:
            response = await client.get("http://prometheus:9090/api/v1/targets")
            assert response.status_code == 200

            targets = response.json()
            otel_target = next(
                (
                    t
                    for t in targets["data"]["activeTargets"]
                    if t["labels"]["job"] == "otel-collector"
                ),
                None,
            )
            assert otel_target is not None
            assert otel_target["health"] == "up"


@pytest.mark.integration
async def test_jaeger_trace_collection():
    """Test Jaeger can collect traces from OTel Collector."""
    async with docker_compose_test_context(["otel-collector", "jaeger"]):
        # Wait for Jaeger to be ready
        await asyncio.sleep(10)

        async with httpx.AsyncClient() as client:
            response = await client.get("http://jaeger:16686/api/services")
            assert response.status_code == 200


@pytest.mark.integration
async def test_grafana_datasource_configuration():
    """Test Grafana datasources are properly configured."""
    async with docker_compose_test_context(["grafana", "prometheus", "jaeger"]):
        # Wait for Grafana to load datasources
        await asyncio.sleep(15)

        async with httpx.AsyncClient() as client:
            # Test Prometheus datasource
            response = await client.get("http://grafana:3000/api/datasources")
            assert response.status_code == 200

            datasources = response.json()
            prometheus_ds = next(
                (ds for ds in datasources if ds["type"] == "prometheus"), None
            )
            assert prometheus_ds is not None
            assert prometheus_ds["url"] == "http://prometheus:9090"


@pytest.mark.integration
async def test_service_metrics_flow():
    """Test complete metrics flow from service to Prometheus."""
    async with docker_compose_test_context(
        ["otel-collector", "prometheus", "stt", "audio"]
    ):
        # Generate some test traffic
        async with httpx.AsyncClient() as client:
            # Make requests to services to generate metrics
            for _ in range(5):
                try:
                    await client.get("http://stt:9000/health/ready", timeout=5)
                    await client.get("http://audio:9100/health/ready", timeout=5)
                except httpx.ConnectError:
                    pass  # Service might not be ready yet
                await asyncio.sleep(1)

        # Wait for metrics to flow through
        await asyncio.sleep(30)

        # Check Prometheus for audio_orchestrator metrics
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://prometheus:9090/api/v1/query",
                params={"query": "audio_orchestrator_http_requests_total"},
            )
            assert response.status_code == 200

            result = response.json()
            # Should have some metrics
            assert "data" in result
            assert "result" in result["data"]


@pytest.mark.integration
async def test_distributed_tracing_flow():
    """Test distributed tracing from service to Jaeger."""
    async with docker_compose_test_context(
        ["otel-collector", "jaeger", "stt", "audio"]
    ):
        # Generate test traffic with tracing
        async with httpx.AsyncClient() as client:
            # Make requests that should create traces
            for _ in range(3):
                try:
                    await client.get("http://stt:9000/health/ready", timeout=5)
                    await client.get("http://audio:9100/health/ready", timeout=5)
                except httpx.ConnectError:
                    pass
                await asyncio.sleep(1)

        # Wait for traces to be collected
        await asyncio.sleep(20)

        # Check Jaeger for traces
        async with httpx.AsyncClient() as client:
            response = await client.get("http://jaeger:16686/api/services")
            assert response.status_code == 200

            services = response.json()
            # Should have traces from our services
            service_names = [s["name"] for s in services["data"]]
            assert any("stt" in name for name in service_names)
            assert any("audio" in name for name in service_names)


@pytest.mark.integration
async def test_observability_stack_resilience():
    """Test that application services work when observability is down."""
    async with (
        docker_compose_test_context(["stt", "audio", "discord"]),
        httpx.AsyncClient() as client,
    ):
        # Services should start and work without observability
        # Test service health
        response = await client.get("http://stt:9000/health/ready", timeout=10)
        assert response.status_code == 200

        response = await client.get("http://audio:9100/health/ready", timeout=10)
        assert response.status_code == 200


@pytest.mark.integration
async def test_grafana_dashboard_provisioning():
    """Test that Grafana dashboards are properly provisioned."""
    async with docker_compose_test_context(["grafana"]):
        # Wait for Grafana to load dashboards
        await asyncio.sleep(20)

        async with httpx.AsyncClient() as client:
            response = await client.get("http://grafana:3000/api/search?type=dash-db")
            assert response.status_code == 200

            dashboards = response.json()
            # Should have our provisioned dashboards
            dashboard_titles = [d["title"] for d in dashboards]
            assert "Audio Orchestrator Overview" in dashboard_titles
            assert "Audio Pipeline" in dashboard_titles
            assert "Service Details" in dashboard_titles
