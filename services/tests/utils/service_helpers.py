"""Service orchestration helpers for integration testing via Docker Compose."""

import asyncio
import subprocess
import time
from contextlib import asynccontextmanager
from typing import Any

import httpx

from services.tests.integration.conftest import get_service_url


class DockerComposeManager:
    """Manages Docker Compose test services."""

    def __init__(self, compose_file: str = "docker-compose.test.yml"):
        self.compose_file = compose_file
        self.compose_cmd = ["docker", "compose"]

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
        """Wait for service health check to pass with service-specific readiness validation.

        Uses environment-based URLs with standardized {SERVICE}_BASE_URL pattern.
        Service names should match Docker service names (lowercase) which map to
        agnostic service names (uppercase) in environment variables.

        Service-specific validation:
        - STT: Tries actual transcription request with test audio
        - Orchestrator: Checks /health/dependencies for LLM and Guardrails readiness
        - TTS: Checks health components for model_loaded status
        - LLM: Verifies model loaded via health components
        - Others: Standard /health/ready check with status="ready"
        """
        # Map Docker service names to agnostic service names for URL lookup
        service_name_map = {
            "stt": "STT",
            "tts": "TTS",
            "bark": "TTS",  # Implementation name maps to agnostic service name
            "llm": "LLM",
            "flan": "LLM",  # Implementation name maps to agnostic service name
            "orchestrator": "ORCHESTRATOR",
            "discord": "DISCORD",
            "audio": "AUDIO",
            "guardrails": "GUARDRAILS",
            "testing": "TESTING",
        }

        agnostic_name = service_name_map.get(service.lower(), service.upper())
        base_url = get_service_url(agnostic_name)

        async with httpx.AsyncClient() as client:
            # Use exponential backoff with max 30 attempts to avoid wasting time
            # Timeout is total time, not number of attempts
            max_attempts = min(30, max(10, int(timeout / 2)))
            initial_delay = 0.5
            max_delay = 2.0

            start_time = time.time()
            for attempt in range(max_attempts):
                try:
                    # Check if we've exceeded total timeout
                    elapsed = time.time() - start_time
                    if elapsed >= timeout:
                        return False

                    # First check basic /health/ready endpoint
                    response = await client.get(f"{base_url}/health/ready", timeout=5.0)

                    # Initialize error tracking
                    error_detail = None
                    dep_errors = []

                    if response.status_code != 200:
                        # Extract error detail from 503 response
                        if response.status_code == 503:
                            try:
                                error_body = response.json()
                                error_detail = error_body.get(
                                    "detail", "Service unavailable"
                                )
                            except Exception:
                                error_detail = response.text or "Service unavailable"

                        # Query /health/dependencies for detailed error info
                        try:
                            deps_response = await client.get(
                                f"{base_url}/health/dependencies", timeout=5.0
                            )
                            if deps_response.status_code == 200:
                                deps_data = deps_response.json()
                                # Extract error messages from dependency info (dict format)
                                for name, info in deps_data.get(
                                    "dependencies", {}
                                ).items():
                                    if isinstance(info, dict):
                                        if (
                                            not info.get("available", False)
                                            and "error" in info
                                        ):
                                            dep_errors.append(
                                                f"{name}: {info['error']}"
                                            )
                                    elif not bool(info):
                                        dep_errors.append(f"{name}: unavailable")
                        except Exception:  # noqa: S110
                            # Fail gracefully if we can't query dependencies - diagnostics are optional
                            pass

                        # Log detailed diagnostics every 5 attempts
                        if attempt % 5 == 0:
                            error_parts = [
                                f"Health check failed for {service} (attempt {attempt + 1})"
                            ]
                            if error_detail:
                                error_parts.append(f"Error: {error_detail}")
                            if dep_errors:
                                error_parts.append(
                                    f"Dependency errors: {'; '.join(dep_errors)}"
                                )
                            print("\n".join(error_parts))
                            await self._log_service_diagnostics(service)

                        delay = min(initial_delay * (1.5 ** min(attempt, 5)), max_delay)
                        await asyncio.sleep(delay)
                        continue

                    data = response.json()
                    if data.get("status") != "ready":
                        delay = min(initial_delay * (1.5 ** min(attempt, 5)), max_delay)
                        await asyncio.sleep(delay)
                        continue

                    # Service-specific readiness validation
                    service_lower = service.lower()
                    if service_lower == "stt":
                        # STT: Try actual transcription request
                        if not await self._validate_stt_readiness(client, base_url):
                            delay = min(
                                initial_delay * (1.5 ** min(attempt, 5)), max_delay
                            )
                            await asyncio.sleep(delay)
                            continue
                    elif service_lower == "orchestrator":
                        # Orchestrator: Check /health/dependencies for LLM and Guardrails
                        if not await self._validate_orchestrator_readiness(
                            client, base_url
                        ):
                            delay = min(
                                initial_delay * (1.5 ** min(attempt, 5)), max_delay
                            )
                            await asyncio.sleep(delay)
                            continue
                    elif service_lower in ("tts", "bark"):
                        # TTS: Check health components for model_loaded status
                        if not await self._validate_tts_readiness(
                            client, base_url, data
                        ):
                            delay = min(
                                initial_delay * (1.5 ** min(attempt, 5)), max_delay
                            )
                            await asyncio.sleep(delay)
                            continue
                    elif service_lower in (
                        "llm",
                        "flan",
                    ) and not await self._validate_llm_readiness(
                        client, base_url, data
                    ):
                        # LLM: Verify model loaded via health components
                        delay = min(initial_delay * (1.5 ** min(attempt, 5)), max_delay)
                        await asyncio.sleep(delay)
                        continue

                    # Service is ready
                    return True

                except Exception as e:
                    # Exception handler catches network errors, timeouts, etc.
                    # httpx returns Response objects for HTTP status codes, so 503 won't be here
                    # But connection errors, timeouts, etc. will be caught here
                    error_detail = str(e)

                    # Log detailed diagnostics every 5 attempts (not just first 5)
                    # This logs on attempts 0, 5, 10, 15, 20, etc. (0-indexed)
                    if attempt % 5 == 0:
                        error_parts = [
                            f"Health check failed for {service} (attempt {attempt + 1})"
                        ]
                        if error_detail:
                            error_parts.append(f"Error: {error_detail}")
                        print("\n".join(error_parts))

                        # Optional: Attempt container log inspection
                        await self._log_service_diagnostics(service)

                    delay = min(initial_delay * (1.5 ** min(attempt, 5)), max_delay)
                    await asyncio.sleep(delay)

        return False

    async def _validate_stt_readiness(
        self, client: httpx.AsyncClient, base_url: str
    ) -> bool:
        """Validate STT readiness by attempting actual transcription.

        Note: This sends a test transcription request. For services that
        are already known to be running (via make run-test), we can skip this
        expensive validation and just check /health/ready status.
        """
        try:
            # Use real speech audio if available, otherwise fall back to synthetic
            from io import BytesIO
            from pathlib import Path

            # Try to load real speech sample
            fixtures_dir = Path(__file__).parent.parent.parent / "fixtures" / "audio"
            speech_file = fixtures_dir / "spoken_english.wav"

            if speech_file.exists():
                test_audio = speech_file.read_bytes()
                print(
                    f"Using real speech sample for STT validation: {speech_file.name}"
                )
            else:
                # Fallback to synthetic audio if speech sample not available
                from services.tests.utils.audio_quality_helpers import (
                    create_wav_file,
                    generate_test_audio,
                )

                test_audio = create_wav_file(
                    generate_test_audio(duration=1.0, frequency=440.0, amplitude=0.5),
                    sample_rate=16000,
                    channels=1,
                )
                print(
                    "Using synthetic audio for STT validation (spoken_english.wav not found)"
                )

            # STT /transcribe endpoint expects multipart form data with 'file' field
            files = {"file": ("test_validation.wav", BytesIO(test_audio), "audio/wav")}

            response = await client.post(
                f"{base_url}/transcribe",
                files=files,
                timeout=10.0,
            )
            return response.status_code == 200
        except Exception:
            return False

    async def _validate_orchestrator_readiness(
        self, client: httpx.AsyncClient, base_url: str
    ) -> bool:
        """Validate Orchestrator readiness by checking dependencies."""
        try:
            response = await client.get(f"{base_url}/health/dependencies", timeout=5.0)
            if response.status_code != 200:
                return False

            deps = response.json()
            # Check that LLM and Guardrails dependencies are ready
            # Handle dict format from /health/dependencies endpoint
            llm_info = deps.get("dependencies", {}).get("llm", {})
            guardrails_info = deps.get("dependencies", {}).get("guardrails", {})

            # Handle both dict format (new) and bool (legacy - should not occur after Component 5)
            llm_ready = (
                llm_info.get("available", False)
                if isinstance(llm_info, dict)
                else bool(llm_info)
            )
            guardrails_ready = (
                guardrails_info.get("available", False)
                if isinstance(guardrails_info, dict)
                else bool(guardrails_info)
            )

            return llm_ready and guardrails_ready
        except Exception:
            return False

    async def _validate_tts_readiness(
        self, client: httpx.AsyncClient, base_url: str, health_data: dict[str, Any]
    ) -> bool:
        """Validate TTS readiness by checking model_loaded component."""
        components = health_data.get("components", {})
        model_loaded = components.get("model_loaded", False)
        return bool(model_loaded)

    async def _validate_llm_readiness(
        self, client: httpx.AsyncClient, base_url: str, health_data: dict[str, Any]
    ) -> bool:
        """Validate LLM readiness by checking model_loaded component."""
        components = health_data.get("components", {})
        model_loaded = components.get("model_loaded", False)
        return bool(model_loaded)

    async def _log_service_diagnostics(self, service: str) -> None:
        """Attempt to log container diagnostics if docker available."""
        try:
            # Use docker-compose.test.yml as specified in DockerComposeManager.__init__
            cmd = [
                "docker",
                "compose",
                "-f",
                self.compose_file,  # "docker-compose.test.yml"
                "logs",
                "--tail=50",
                service,
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=5.0, check=False
            )
            if result.returncode == 0 and result.stdout:
                print(f"Container logs for {service}:\n{result.stdout}")
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):  # noqa: S110, BLE001
            # Docker unavailable or service not found - fail silently (diagnostics are optional)
            pass

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

    Services are expected to already be running via 'make run-test'.
    This context manager just waits for services to be ready without
    starting/stopping them, since 'docker' command is not available
    inside the test container.

    Example:
        async with docker_compose_test_context(["stt", "tts"]):
            async with httpx.AsyncClient() as client:
                response = await client.get("http://stt:9000/health/ready")
    """
    # Wait for services to be healthy (they're already running)
    for service in services:
        if not await _manager.wait_for_service_healthy(service, timeout):
            # Query /health/dependencies for detailed error information
            service_name_map = {
                "stt": "STT",
                "tts": "TTS",
                "bark": "TTS",
                "llm": "LLM",
                "flan": "LLM",
                "orchestrator": "ORCHESTRATOR",
                "discord": "DISCORD",
                "audio": "AUDIO",
                "guardrails": "GUARDRAILS",
                "testing": "TESTING",
            }

            agnostic_name = service_name_map.get(service.lower(), service.upper())
            base_url = get_service_url(agnostic_name)

            error_parts = [
                f"Service {service} not ready after {timeout}s",
                f"Service URL: {base_url}",
                "",
                "Troubleshooting steps:",
                "1. Check if the service is running: docker compose ps",
                "2. Check service logs: docker compose logs {service}",
                "3. Verify service configuration and environment variables",
                "4. Check network connectivity between services",
            ]

            # Try to get detailed dependency errors
            try:
                async with httpx.AsyncClient() as client:
                    deps_response = await client.get(
                        f"{base_url}/health/dependencies", timeout=5.0
                    )
                    if deps_response.status_code == 200:
                        deps_data = deps_response.json()
                        failing_deps = []
                        for name, info in deps_data.get("dependencies", {}).items():
                            if isinstance(info, dict):
                                if not info.get("available", False):
                                    error_msg = info.get("error", "unavailable")
                                    failing_deps.append(f"  - {name}: {error_msg}")
                            elif not bool(info):
                                failing_deps.append(f"  - {name}: unavailable")

                        if failing_deps:
                            error_parts.append("")
                            error_parts.append("Failing dependencies:")
                            error_parts.extend(failing_deps)
            except Exception:  # noqa: S110
                # Fail gracefully if we can't query dependencies (diagnostics are optional)
                pass

            raise RuntimeError("\n".join(error_parts))
    yield
    # No cleanup needed - services remain running


async def get_service_health(service_name: str) -> dict[str, Any] | None:
    """Get health status of a service.

    Uses environment-based URLs with standardized {SERVICE}_BASE_URL pattern.
    """
    # Map Docker service names to agnostic service names for URL lookup
    service_name_map = {
        "stt": "STT",
        "tts": "TTS",
        "bark": "TTS",  # Implementation name maps to agnostic service name
        "llm": "LLM",
        "flan": "LLM",  # Implementation name maps to agnostic service name
        "orchestrator": "ORCHESTRATOR",
        "discord": "DISCORD",
        "audio": "AUDIO",
        "guardrails": "GUARDRAILS",
        "testing": "TESTING",
    }

    agnostic_name = service_name_map.get(service_name.lower(), service_name.upper())
    base_url = get_service_url(agnostic_name)
    url = f"{base_url}/health/ready"

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
