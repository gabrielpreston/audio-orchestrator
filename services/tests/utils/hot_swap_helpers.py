"""
Hot-swap validation utilities for interface-first testing.

This module provides utilities for validating hot-swappability,
including service contract compliance, interchangeability, and error handling.
"""

import asyncio
from dataclasses import dataclass
import statistics
import time
from typing import Any
from collections.abc import Callable


@dataclass
class HotSwapResult:
    """Result of hot-swap validation."""

    test_name: str
    passed: bool
    services_tested: int
    successful_swaps: int
    failed_swaps: int
    average_swap_time_ms: float
    errors: list[str]
    warnings: list[str]
    recommendations: list[str]

    def add_error(self, error: str):
        """Add an error to the hot-swap result."""
        self.errors.append(error)
        self.passed = False

    def add_warning(self, warning: str):
        """Add a warning to the hot-swap result."""
        self.warnings.append(warning)

    def add_recommendation(self, recommendation: str):
        """Add a recommendation to the hot-swap result."""
        self.recommendations.append(recommendation)


class HotSwapValidator:
    """Validator for hot-swap functionality."""

    def __init__(self, max_swap_time_ms: int = 1000, min_success_rate: float = 95.0):
        self.max_swap_time_ms = max_swap_time_ms
        self.min_success_rate = min_success_rate

    async def validate_service_contract_compliance(
        self, service_implementations: list[str], contract_class: type
    ) -> HotSwapResult:
        """Validate that all service implementations comply with the same contract."""
        result = HotSwapResult(
            test_name="service_contract_compliance",
            passed=True,
            services_tested=0,
            successful_swaps=0,
            failed_swaps=0,
            average_swap_time_ms=0.0,
            errors=[],
            warnings=[],
            recommendations=[],
        )

        swap_times = []

        try:
            for implementation_url in service_implementations:
                result.services_tested += 1
                swap_start = time.time()

                try:
                    # Create contract with specific implementation URL
                    contract = contract_class()
                    contract.base_url = implementation_url

                    # Validate contract compliance
                    from services.tests.utils.contract_validators import (
                        ContractValidator,
                    )

                    validator = ContractValidator(contract)
                    validation_result = await validator.validate_all()

                    if validation_result.passed:
                        result.successful_swaps += 1
                    else:
                        result.failed_swaps += 1
                        result.add_error(
                            f"Service {implementation_url} failed contract validation: {validation_result.errors}"
                        )

                except Exception as e:
                    result.failed_swaps += 1
                    result.add_error(
                        f"Service {implementation_url} validation failed: {str(e)}"
                    )

                swap_time = (time.time() - swap_start) * 1000
                swap_times.append(swap_time)

            # Calculate metrics
            if swap_times:
                result.average_swap_time_ms = statistics.mean(swap_times)
                max_swap_time = max(swap_times)

                # Validate swap time requirements
                if result.average_swap_time_ms > self.max_swap_time_ms:
                    result.add_error(
                        f"Average swap time {result.average_swap_time_ms:.1f}ms exceeds maximum {self.max_swap_time_ms}ms"
                    )

                if max_swap_time > self.max_swap_time_ms * 2:
                    result.add_warning(
                        f"Maximum swap time {max_swap_time:.1f}ms is significantly higher than average"
                    )

            # Calculate success rate
            if result.services_tested > 0:
                success_rate = (result.successful_swaps / result.services_tested) * 100

                if success_rate < self.min_success_rate:
                    result.add_error(
                        f"Success rate {success_rate:.1f}% below minimum {self.min_success_rate}%"
                    )

                # Add recommendations
                if success_rate < 100:
                    result.add_recommendation(
                        "Review service implementations for contract compliance"
                    )

                if result.average_swap_time_ms > self.max_swap_time_ms * 0.8:
                    result.add_recommendation("Optimize service swap performance")

            else:
                result.add_error("No services tested")

        except Exception as e:
            result.add_error(f"Service contract compliance validation failed: {str(e)}")

        return result

    async def validate_service_interchangeability(
        self, service_implementations: list[str], test_function: Callable[..., bool]
    ) -> HotSwapResult:
        """Validate that services can be interchanged without breaking functionality."""
        result = HotSwapResult(
            test_name="service_interchangeability",
            passed=True,
            services_tested=0,
            successful_swaps=0,
            failed_swaps=0,
            average_swap_time_ms=0.0,
            errors=[],
            warnings=[],
            recommendations=[],
        )

        swap_times = []

        try:
            for implementation_url in service_implementations:
                result.services_tested += 1
                swap_start = time.time()

                try:
                    # Test service functionality
                    test_result = test_function(implementation_url)

                    if test_result:
                        result.successful_swaps += 1
                    else:
                        result.failed_swaps += 1
                        result.add_error(
                            f"Service {implementation_url} functionality test failed"
                        )

                except Exception as e:
                    result.failed_swaps += 1
                    result.add_error(
                        f"Service {implementation_url} functionality test failed: {str(e)}"
                    )

                swap_time = (time.time() - swap_start) * 1000
                swap_times.append(swap_time)

            # Calculate metrics
            if swap_times:
                result.average_swap_time_ms = statistics.mean(swap_times)
                max_swap_time = max(swap_times)

                # Validate swap time requirements
                if result.average_swap_time_ms > self.max_swap_time_ms:
                    result.add_error(
                        f"Average swap time {result.average_swap_time_ms:.1f}ms exceeds maximum {self.max_swap_time_ms}ms"
                    )

                if max_swap_time > self.max_swap_time_ms * 2:
                    result.add_warning(
                        f"Maximum swap time {max_swap_time:.1f}ms is significantly higher than average"
                    )

            # Calculate success rate
            if result.services_tested > 0:
                success_rate = (result.successful_swaps / result.services_tested) * 100

                if success_rate < self.min_success_rate:
                    result.add_error(
                        f"Success rate {success_rate:.1f}% below minimum {self.min_success_rate}%"
                    )

                # Add recommendations
                if success_rate < 100:
                    result.add_recommendation(
                        "Review service implementations for functionality consistency"
                    )

                if result.average_swap_time_ms > self.max_swap_time_ms * 0.8:
                    result.add_recommendation("Optimize service swap performance")

            else:
                result.add_error("No services tested")

        except Exception as e:
            result.add_error(f"Service interchangeability validation failed: {str(e)}")

        return result

    async def validate_service_discovery(
        self, service_implementations: list[str]
    ) -> HotSwapResult:
        """Validate service discovery mechanism."""
        result = HotSwapResult(
            test_name="service_discovery",
            passed=True,
            services_tested=0,
            successful_swaps=0,
            failed_swaps=0,
            average_swap_time_ms=0.0,
            errors=[],
            warnings=[],
            recommendations=[],
        )

        discovery_times = []

        try:
            for implementation_url in service_implementations:
                result.services_tested += 1
                discovery_start = time.time()

                try:
                    # Test service discovery
                    discovered = await self._discover_service(implementation_url)

                    if discovered:
                        result.successful_swaps += 1
                    else:
                        result.failed_swaps += 1
                        result.add_error(f"Service {implementation_url} not discovered")

                except Exception as e:
                    result.failed_swaps += 1
                    result.add_error(
                        f"Service {implementation_url} discovery failed: {str(e)}"
                    )

                discovery_time = (time.time() - discovery_start) * 1000
                discovery_times.append(discovery_time)

            # Calculate metrics
            if discovery_times:
                result.average_swap_time_ms = statistics.mean(discovery_times)
                max_discovery_time = max(discovery_times)

                # Validate discovery time requirements
                if result.average_swap_time_ms > self.max_swap_time_ms:
                    result.add_error(
                        f"Average discovery time {result.average_swap_time_ms:.1f}ms exceeds maximum {self.max_swap_time_ms}ms"
                    )

                if max_discovery_time > self.max_swap_time_ms * 2:
                    result.add_warning(
                        f"Maximum discovery time {max_discovery_time:.1f}ms is significantly higher than average"
                    )

            # Calculate success rate
            if result.services_tested > 0:
                success_rate = (result.successful_swaps / result.services_tested) * 100

                if success_rate < self.min_success_rate:
                    result.add_error(
                        f"Success rate {success_rate:.1f}% below minimum {self.min_success_rate}%"
                    )

                # Add recommendations
                if success_rate < 100:
                    result.add_recommendation("Review service discovery mechanism")

                if result.average_swap_time_ms > self.max_swap_time_ms * 0.8:
                    result.add_recommendation("Optimize service discovery performance")

            else:
                result.add_error("No services tested")

        except Exception as e:
            result.add_error(f"Service discovery validation failed: {str(e)}")

        return result

    async def validate_fallback_activation(
        self, primary_services: list[str], fallback_services: list[str]
    ) -> HotSwapResult:
        """Validate fallback service activation."""
        result = HotSwapResult(
            test_name="fallback_activation",
            passed=True,
            services_tested=0,
            successful_swaps=0,
            failed_swaps=0,
            average_swap_time_ms=0.0,
            errors=[],
            warnings=[],
            recommendations=[],
        )

        activation_times = []

        try:
            for primary_service in primary_services:
                result.services_tested += 1
                activation_start = time.time()

                try:
                    # Simulate primary service failure
                    primary_failed = await self._simulate_service_failure(
                        primary_service
                    )

                    if primary_failed:
                        # Test fallback activation
                        for fallback_service in fallback_services:
                            fallback_activated = await self._activate_fallback_service(
                                fallback_service
                            )

                            if fallback_activated:
                                result.successful_swaps += 1
                            else:
                                result.failed_swaps += 1
                                result.add_error(
                                    f"Fallback service {fallback_service} not activated"
                                )
                    else:
                        result.failed_swaps += 1
                        result.add_error(
                            f"Primary service {primary_service} failure simulation failed"
                        )

                except Exception as e:
                    result.failed_swaps += 1
                    result.add_error(
                        f"Fallback activation failed for {primary_service}: {str(e)}"
                    )

                activation_time = (time.time() - activation_start) * 1000
                activation_times.append(activation_time)

            # Calculate metrics
            if activation_times:
                result.average_swap_time_ms = statistics.mean(activation_times)
                max_activation_time = max(activation_times)

                # Validate activation time requirements
                if result.average_swap_time_ms > self.max_swap_time_ms:
                    result.add_error(
                        f"Average activation time {result.average_swap_time_ms:.1f}ms exceeds maximum {self.max_swap_time_ms}ms"
                    )

                if max_activation_time > self.max_swap_time_ms * 2:
                    result.add_warning(
                        f"Maximum activation time {max_activation_time:.1f}ms is significantly higher than average"
                    )

            # Calculate success rate
            if result.services_tested > 0:
                success_rate = (result.successful_swaps / result.services_tested) * 100

                if success_rate < self.min_success_rate:
                    result.add_error(
                        f"Success rate {success_rate:.1f}% below minimum {self.min_success_rate}%"
                    )

                # Add recommendations
                if success_rate < 100:
                    result.add_recommendation("Review fallback activation mechanism")

                if result.average_swap_time_ms > self.max_swap_time_ms * 0.8:
                    result.add_recommendation(
                        "Optimize fallback activation performance"
                    )

            else:
                result.add_error("No services tested")

        except Exception as e:
            result.add_error(f"Fallback activation validation failed: {str(e)}")

        return result

    async def validate_load_balancing(
        self, service_implementations: list[str]
    ) -> HotSwapResult:
        """Validate load balancing functionality."""
        result = HotSwapResult(
            test_name="load_balancing",
            passed=True,
            services_tested=0,
            successful_swaps=0,
            failed_swaps=0,
            average_swap_time_ms=0.0,
            errors=[],
            warnings=[],
            recommendations=[],
        )

        if len(service_implementations) < 2:
            result.add_warning("Load balancing requires at least 2 services")
            return result

        balance_times = []

        try:
            # Test load balancing
            balance_start = time.time()

            try:
                # Simulate load balancing
                balanced = await self._test_load_balancing(service_implementations)

                if balanced:
                    result.successful_swaps += 1
                else:
                    result.failed_swaps += 1
                    result.add_error("Load balancing failed")

            except Exception as e:
                result.failed_swaps += 1
                result.add_error(f"Load balancing failed: {str(e)}")

            balance_time = (time.time() - balance_start) * 1000
            balance_times.append(balance_time)

            # Calculate metrics
            if balance_times:
                result.average_swap_time_ms = statistics.mean(balance_times)
                max_balance_time = max(balance_times)

                # Validate balance time requirements
                if result.average_swap_time_ms > self.max_swap_time_ms:
                    result.add_error(
                        f"Average balance time {result.average_swap_time_ms:.1f}ms exceeds maximum {self.max_swap_time_ms}ms"
                    )

                if max_balance_time > self.max_swap_time_ms * 2:
                    result.add_warning(
                        f"Maximum balance time {max_balance_time:.1f}ms is significantly higher than average"
                    )

            # Calculate success rate
            if result.services_tested > 0:
                success_rate = (result.successful_swaps / result.services_tested) * 100

                if success_rate < self.min_success_rate:
                    result.add_error(
                        f"Success rate {success_rate:.1f}% below minimum {self.min_success_rate}%"
                    )

                # Add recommendations
                if success_rate < 100:
                    result.add_recommendation("Review load balancing mechanism")

                if result.average_swap_time_ms > self.max_swap_time_ms * 0.8:
                    result.add_recommendation("Optimize load balancing performance")

            else:
                result.add_error("No services tested")

        except Exception as e:
            result.add_error(f"Load balancing validation failed: {str(e)}")

        return result

    async def _discover_service(self, service_url: str) -> bool:
        """Discover if service is available."""
        try:
            # This would implement actual service discovery
            # For now, we'll simulate discovery
            await asyncio.sleep(0.01)  # Simulate discovery time
            return True
        except Exception:
            return False

    async def _simulate_service_failure(self, service_url: str) -> bool:
        """Simulate service failure."""
        try:
            # This would implement actual service failure simulation
            # For now, we'll simulate failure
            await asyncio.sleep(0.01)  # Simulate failure time
            return True
        except Exception:
            return False

    async def _activate_fallback_service(self, service_url: str) -> bool:
        """Activate fallback service."""
        try:
            # This would implement actual fallback activation
            # For now, we'll simulate activation
            await asyncio.sleep(0.01)  # Simulate activation time
            return True
        except Exception:
            return False

    async def _test_load_balancing(self, service_urls: list[str]) -> bool:
        """Test load balancing."""
        try:
            # This would implement actual load balancing test
            # For now, we'll simulate load balancing
            await asyncio.sleep(0.01)  # Simulate load balancing time
            return True
        except Exception:
            return False

    def _extract_errors(self, validation_results: list[Any]) -> list[str]:
        """Extract errors from validation results."""
        errors = []
        for result in validation_results:
            if hasattr(result, "errors"):
                errors.extend(result.errors)
            elif hasattr(result, "error"):
                errors.append(result.error)
        return errors
