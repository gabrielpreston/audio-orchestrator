"""
Contract validation utilities for interface-first testing.

This module provides utilities for validating service contracts,
including health checks, API endpoints, performance, and security requirements.
"""

# dataclass import removed - ValidationResult is imported from base_contracts
import time
from typing import Any

import httpx

from services.tests.contracts.base_contracts import (
    EndpointContract,
    ServiceContract,
    ValidationResult,
)


# ValidationResult is imported from base_contracts


class ContractValidator:
    """Validator for service contracts."""

    def __init__(self, contract: ServiceContract):
        self.contract = contract
        self.start_time = time.time()

    async def validate_all(self) -> ValidationResult:
        """Validate all aspects of the service contract."""
        result = ValidationResult(
            contract_name=self.contract.service_name,
            passed=True,
            errors=[],
            warnings=[],
            performance_metrics={},
            validation_time_ms=0.0,
        )

        try:
            # Validate health contracts
            await self._validate_health_contracts(result)

            # Validate API contracts
            await self._validate_api_contracts(result)

            # Validate performance contracts
            if self.contract.performance:
                await self._validate_performance_contracts(result)

            # Validate security contracts
            if self.contract.security:
                await self._validate_security_contracts(result)

        except Exception as e:
            result.add_error(f"Validation failed with exception: {str(e)}")

        result.validation_time_ms = (time.time() - self.start_time) * 1000
        return result

    async def _validate_health_contracts(self, result: ValidationResult):
        """Validate health check endpoints."""
        async with httpx.AsyncClient(timeout=5.0) as client:
            for endpoint in self.contract.health_endpoints:
                try:
                    url = f"{self.contract.base_url}{endpoint.path}"
                    start_time = time.time()

                    response = await client.request(method=endpoint.method, url=url)

                    latency_ms = (time.time() - start_time) * 1000

                    # Check status code
                    if response.status_code not in endpoint.expected_status_codes:
                        result.add_error(
                            f"Health endpoint {endpoint.name} returned {response.status_code}, "
                            f"expected {endpoint.expected_status_codes}"
                        )

                    # Check response format
                    if response.status_code == 200:
                        try:
                            data = response.json()
                            if not self._validate_health_response(data, endpoint):
                                result.add_error(
                                    f"Health endpoint {endpoint.name} response format invalid"
                                )
                        except Exception as e:
                            result.add_error(
                                f"Health endpoint {endpoint.name} response not valid JSON: {str(e)}"
                            )

                    # Check latency
                    if latency_ms > endpoint.timeout_ms:
                        result.add_warning(
                            f"Health endpoint {endpoint.name} latency {latency_ms:.1f}ms exceeds timeout {endpoint.timeout_ms}ms"
                        )

                except httpx.TimeoutException:
                    result.add_error(f"Health endpoint {endpoint.name} timed out")
                except httpx.ConnectError:
                    result.add_error(
                        f"Health endpoint {endpoint.name} connection failed"
                    )
                except Exception as e:
                    result.add_error(
                        f"Health endpoint {endpoint.name} validation failed: {str(e)}"
                    )

    async def _validate_api_contracts(self, result: ValidationResult):
        """Validate API endpoints."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            for endpoint in self.contract.endpoints:
                try:
                    url = f"{self.contract.base_url}{endpoint.path}"
                    start_time = time.time()

                    # Generate test data
                    test_data = self._generate_test_data(endpoint)

                    response = await client.request(
                        method=endpoint.method,
                        url=url,
                        json=test_data
                        if endpoint.method in ["POST", "PUT", "PATCH"]
                        else None,
                    )

                    latency_ms = (time.time() - start_time) * 1000

                    # Check status code
                    if response.status_code not in endpoint.expected_status_codes:
                        result.add_error(
                            f"API endpoint {endpoint.name} returned {response.status_code}, "
                            f"expected {endpoint.expected_status_codes}"
                        )

                    # Check response format
                    if response.status_code == 200:
                        try:
                            data = response.json()
                            if not self._validate_api_response(data, endpoint):
                                result.add_error(
                                    f"API endpoint {endpoint.name} response format invalid"
                                )
                        except Exception as e:
                            result.add_error(
                                f"API endpoint {endpoint.name} response not valid JSON: {str(e)}"
                            )

                    # Check latency
                    if latency_ms > endpoint.timeout_ms:
                        result.add_warning(
                            f"API endpoint {endpoint.name} latency {latency_ms:.1f}ms exceeds timeout {endpoint.timeout_ms}ms"
                        )

                except httpx.TimeoutException:
                    result.add_error(f"API endpoint {endpoint.name} timed out")
                except httpx.ConnectError:
                    result.add_error(f"API endpoint {endpoint.name} connection failed")
                except Exception as e:
                    result.add_error(
                        f"API endpoint {endpoint.name} validation failed: {str(e)}"
                    )

    async def _validate_performance_contracts(self, result: ValidationResult):
        """Validate performance requirements."""
        if not self.contract.performance:
            return

        # This would be implemented with actual performance testing
        # For now, we'll add a placeholder
        result.performance_metrics = {
            "max_latency_ms": str(self.contract.performance.max_latency_ms),
            "min_throughput_rps": str(
                self.contract.performance.min_throughput_rps or 0
            ),
            "max_memory_mb": str(self.contract.performance.max_memory_mb or 0),
            "max_cpu_percent": str(self.contract.performance.max_cpu_percent or 0.0),
        }

    async def _validate_security_contracts(self, result: ValidationResult):
        """Validate security requirements."""
        if not self.contract.security:
            return

        # This would be implemented with actual security testing
        # For now, we'll add a placeholder
        pass

    def _validate_health_response(
        self, data: dict[str, Any], endpoint: EndpointContract
    ) -> bool:
        """Validate health response format."""
        if endpoint.name == "health_live":
            return "status" in data and data["status"] == "alive"
        elif endpoint.name == "health_ready":
            return (
                "status" in data
                and data["status"] in ["ready", "degraded", "not_ready"]
                and "service" in data
            )
        return True

    def _validate_api_response(
        self, data: dict[str, Any], endpoint: EndpointContract
    ) -> bool:
        """Validate API response format."""
        if endpoint.response_schema:
            # This would implement proper JSON schema validation
            # For now, we'll do basic checks
            return isinstance(data, dict)
        return True

    def _generate_test_data(self, endpoint: EndpointContract) -> dict[str, Any]:
        """Generate test data for API endpoints."""
        if not endpoint.request_schema:
            return {}

        # This would generate proper test data based on the schema
        # For now, we'll return basic test data
        test_data = {}

        if endpoint.name == "transcribe":
            test_data = {
                "audio": "base64_encoded_audio_data",
                "language": "en",
                "format": "wav",
            }
        elif endpoint.name == "chat_completions":
            test_data = {
                "model": "gpt-3.5-turbo",
                "messages": str([{"role": "user", "content": "Hello, world!"}]),
                "temperature": "0.7",
                "max_tokens": "100",
            }
        elif endpoint.name == "synthesize":
            test_data = {"text": "Hello, world!", "voice": "default", "speed": "1.0"}

        return test_data


class HealthContractValidator:
    """Specialized validator for health check contracts."""

    def __init__(self, service_name: str, base_url: str):
        self.service_name = service_name
        self.base_url = base_url

    async def validate_health_contract(self) -> ValidationResult:
        """Validate health check contract compliance."""
        result = ValidationResult(
            contract_name=f"{self.service_name}_health",
            passed=True,
            errors=[],
            warnings=[],
            performance_metrics={},
            validation_time_ms=0.0,
        )

        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                # Test /health/live
                try:
                    response = await client.get(f"{self.base_url}/health/live")
                    if response.status_code != 200:
                        result.add_error(
                            f"Health live endpoint returned {response.status_code}"
                        )
                    else:
                        data = response.json()
                        if data.get("status") != "alive":
                            result.add_error("Health live endpoint status not 'alive'")
                except Exception as e:
                    result.add_error(f"Health live endpoint failed: {str(e)}")

                # Test /health/ready
                try:
                    response = await client.get(f"{self.base_url}/health/ready")
                    if response.status_code not in [200, 503]:
                        result.add_error(
                            f"Health ready endpoint returned {response.status_code}"
                        )
                    else:
                        data = response.json()
                        if "status" not in data or "service" not in data:
                            result.add_error(
                                "Health ready endpoint missing required fields"
                            )
                        if data.get("status") not in ["ready", "degraded", "not_ready"]:
                            result.add_error(
                                f"Health ready endpoint invalid status: {data.get('status')}"
                            )
                except Exception as e:
                    result.add_error(f"Health ready endpoint failed: {str(e)}")

        except Exception as e:
            result.add_error(f"Health contract validation failed: {str(e)}")

        result.validation_time_ms = (time.time() - start_time) * 1000
        return result
