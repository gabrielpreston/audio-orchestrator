"""Service orchestration helpers for integration testing via Docker Compose."""

import asyncio
import subprocess
from contextlib import asynccontextmanager
from typing import Any

import httpx


class DockerComposeManager:
    """Manages Docker Compose test services."""

    def __init__(self, compose_file: str = "docker-compose.test.yml"):
        self.compose_file = compose_file
        self.compose_cmd = self._detect_docker_compose()

    def _detect_docker_compose(self) -> list[str]:
        """Detect docker-compose or docker compose command."""
        try:
            subprocess.run(
                ["docker-compose", "version"], capture_output=True, check=True
            )
            return ["docker-compose"]
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ["docker", "compose"]

    async def start_services(self, services: list[str], timeout: float = 60.0) -> bool:
        """Start specified services using Docker Compose."""
        cmd = [
            *self.compose_cmd,
            "-f",
            self.compose_file,
            "up",
            "-d",
            "--build",
            *services,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            print(f"Failed to start services: {result.stderr}")
            return False

        # Wait for all services to be healthy
        for service in services:
            if not await self.wait_for_service_healthy(service, timeout):
                return False

        return True

    async def wait_for_service_healthy(
        self, service: str, timeout: float = 60.0
    ) -> bool:
        """Wait for service health check to pass."""
        service_ports = {
            "stt": 9000,
            "tts": 7000,
            "llm": 8000,
            "orchestrator": 8000,  # Note: Same as LLM, different containers
            "discord": 8001,  # Discord HTTP API port
        }

        if service not in service_ports:
            return False

        port = service_ports[service]
        url = f"http://{service}:{port}/health/ready"

        async with httpx.AsyncClient() as client:
            for _ in range(int(timeout)):
                try:
                    response = await client.get(url, timeout=5.0)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("status") == "ready":
                            return True
                except Exception as e:
                    print(f"Health check failed for {service}: {e}")
                    pass
                await asyncio.sleep(1.0)

        return False

    async def stop_services(self, services: list[str] | None = None):
        """Stop services using Docker Compose."""
        if services:
            cmd = [*self.compose_cmd, "-f", self.compose_file, "stop", *services]
        else:
            cmd = [*self.compose_cmd, "-f", self.compose_file, "down", "-v"]

        subprocess.run(cmd, capture_output=True, check=False)


# Global manager instance
_manager = DockerComposeManager()


@asynccontextmanager
async def docker_compose_test_context(services: list[str], timeout: float = 60.0):
    """Context manager for Docker Compose test services.

    Example:
        async with docker_compose_test_context(["stt", "tts"]):
            async with httpx.AsyncClient() as client:
                response = await client.get("http://stt:9000/health/ready")
    """
    try:
        success = await _manager.start_services(services, timeout)
        if not success:
            raise RuntimeError(f"Failed to start services: {services}")
        yield
    finally:
        await _manager.stop_services(services)


# Legacy functions for backward compatibility during migration
# These will be removed once all tests are migrated


async def start_test_services(services_list: list[str], timeout: float = 30.0) -> bool:
    """Legacy function - use docker_compose_test_context instead."""
    print(
        "WARNING: start_test_services is deprecated. Use docker_compose_test_context instead."
    )
    return await _manager.start_services(services_list, timeout)


async def wait_for_service_ready(service_name: str, timeout: float = 30.0) -> bool:
    """Legacy function - use docker_compose_test_context instead."""
    print(
        "WARNING: wait_for_service_ready is deprecated. Use docker_compose_test_context instead."
    )
    return await _manager.wait_for_service_healthy(service_name, timeout)


async def stop_test_services():
    """Legacy function - use docker_compose_test_context instead."""
    print(
        "WARNING: stop_test_services is deprecated. Use docker_compose_test_context instead."
    )
    await _manager.stop_services()


async def get_service_health(service_name: str) -> dict[str, Any] | None:
    """Get health status of a service."""
    service_ports = {
        "stt": 9000,
        "tts": 7000,
        "llm": 8000,
        "orchestrator": 8000,
    }

    if service_name not in service_ports:
        return None

    port = service_ports[service_name]
    url = f"http://{service_name}:{port}/health/ready"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=5.0)
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        print(f"Service health check failed for {service_name}: {e}")
        pass

    return None


async def is_service_running(service_name: str) -> bool:
    """Check if a service is running."""
    health = await get_service_health(service_name)
    return health is not None and health.get("status") == "ready"


# Legacy test_services_context for migration period
@asynccontextmanager
async def test_services_context(services_list: list[str], timeout: float = 30.0):
    """Legacy context manager - use docker_compose_test_context instead."""
    print(
        "WARNING: test_services_context is deprecated. Use docker_compose_test_context instead."
    )
    try:
        success = await _manager.start_services(services_list, timeout)
        if not success:
            raise RuntimeError("Failed to start test services")
        yield
    finally:
        await _manager.stop_services(services_list)
