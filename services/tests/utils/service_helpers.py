"""Service orchestration helpers for integration testing."""

import asyncio
import os
import signal
import subprocess
import time
from contextlib import asynccontextmanager
from subprocess import Popen
from typing import Any

import httpx


class ServiceManager:
    """Manages test services for integration testing."""

    def __init__(self):
        self.services: dict[str, Popen[bytes]] = {}
        self.service_configs: dict[str, dict[str, Any]] = {}
        self.base_urls: dict[str, str] = {}

    def register_service(
        self,
        name: str,
        command: list[str],
        base_url: str,
        health_endpoint: str = "/health/ready",
        env_vars: dict[str, str] | None = None,
    ):
        """Register a service for testing."""
        self.service_configs[name] = {
            "command": command,
            "health_endpoint": health_endpoint,
            "env_vars": env_vars or {},
        }
        self.base_urls[name] = base_url

    async def start_services(
        self, services_list: list[str], timeout: float = 30.0
    ) -> bool:
        """Start specified services."""
        try:
            for service_name in services_list:
                if service_name not in self.service_configs:
                    raise ValueError(f"Service {service_name} not registered")

                config = self.service_configs[service_name]

                # Prepare environment
                env = os.environ.copy()
                env.update(config["env_vars"])

                # Start service
                process = subprocess.Popen(
                    config["command"],
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    preexec_fn=os.setsid if os.name != "nt" else None,
                )

                self.services[service_name] = process

                # Wait for service to be ready
                if not await self.wait_for_service_ready(service_name, timeout):
                    await self.stop_services()
                    return False

            return True

        except Exception as e:
            print(f"Error starting services: {e}")
            await self.stop_services()
            return False

    async def wait_for_service_ready(
        self, service_name: str, timeout: float = 30.0
    ) -> bool:
        """Wait for a service to be ready."""
        if service_name not in self.service_configs:
            return False

        config = self.service_configs[service_name]
        base_url = self.base_urls[service_name]
        health_endpoint = config["health_endpoint"]

        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        f"{base_url}{health_endpoint}", timeout=5.0
                    )
                    if response.status_code == 200:
                        return True
            except Exception as e:
                # Log the exception for debugging
                print(f"Health check failed for {service_name}: {e}")
                pass

            await asyncio.sleep(1.0)

        return False

    async def stop_services(self):
        """Stop all running services."""
        for service_name, process in self.services.items():
            try:
                if process.poll() is None:  # Process is still running
                    if os.name != "nt":
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                    else:
                        process.terminate()

                    # Wait for graceful shutdown
                    try:
                        process.wait(timeout=5.0)
                    except subprocess.TimeoutExpired:
                        # Force kill if graceful shutdown fails
                        if os.name != "nt":
                            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                        else:
                            process.kill()

            except Exception as e:
                print(f"Error stopping service {service_name}: {e}")

        self.services.clear()

    async def get_service_health(self, service_name: str) -> dict[str, Any] | None:
        """Get health status of a service."""
        if service_name not in self.base_urls:
            return None

        try:
            base_url = self.base_urls[service_name]
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{base_url}/health/ready", timeout=5.0)
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            # Log the exception for debugging
            print(f"Service metrics check failed for {service_name}: {e}")
            pass

        return None

    async def is_service_running(self, service_name: str) -> bool:
        """Check if a service is running."""
        if service_name not in self.services:
            return False

        process = self.services[service_name]
        return process.poll() is None


# Global service manager instance
_service_manager = ServiceManager()


async def start_test_services(services_list: list[str], timeout: float = 30.0) -> bool:
    """Start test services for integration testing."""
    return await _service_manager.start_services(services_list, timeout)


async def wait_for_service_ready(service_name: str, timeout: float = 30.0) -> bool:
    """Wait for a specific service to be ready."""
    return await _service_manager.wait_for_service_ready(service_name, timeout)


async def stop_test_services():
    """Stop all test services."""
    await _service_manager.stop_services()


async def get_service_health(service_name: str) -> dict[str, Any] | None:
    """Get health status of a service."""
    return await _service_manager.get_service_health(service_name)


async def is_service_running(service_name: str) -> bool:
    """Check if a service is running."""
    return await _service_manager.is_service_running(service_name)


def register_test_service(
    name: str,
    command: list[str],
    base_url: str,
    health_endpoint: str = "/health/ready",
    env_vars: dict[str, str] | None = None,
):
    """Register a test service."""
    _service_manager.register_service(
        name, command, base_url, health_endpoint, env_vars
    )


@asynccontextmanager
async def test_services_context(services_list: list[str], timeout: float = 30.0):
    """Context manager for test services."""
    try:
        success = await start_test_services(services_list, timeout)
        if not success:
            raise RuntimeError("Failed to start test services")
        yield
    finally:
        await stop_test_services()


# Default service configurations
def setup_default_services():
    """Setup default service configurations for testing."""

    # STT Service
    register_test_service(
        name="stt",
        command=["python", "-m", "services.stt.app"],
        base_url="http://localhost:9000",
        health_endpoint="/health/ready",
        env_vars={"FW_MODEL": "tiny", "FW_DEVICE": "cpu", "LOG_LEVEL": "INFO"},
    )

    # TTS Service
    register_test_service(
        name="tts",
        command=["python", "-m", "services.tts.app"],
        base_url="http://localhost:7000",
        health_endpoint="/health/ready",
        env_vars={"LOG_LEVEL": "INFO"},
    )

    # LLM Service (if available)
    register_test_service(
        name="llm",
        command=["python", "-m", "services.llm.app"],
        base_url="http://localhost:8000",
        health_endpoint="/health/ready",
        env_vars={"LOG_LEVEL": "INFO"},
    )

    # Orchestrator Service
    register_test_service(
        name="orchestrator",
        command=["python", "-m", "services.orchestrator.app"],
        base_url="http://localhost:8001",
        health_endpoint="/health/ready",
        env_vars={"LOG_LEVEL": "INFO"},
    )


# Initialize default services
setup_default_services()
