"""Validation protocols for interface-first testing.

This module defines protocols that define validation contracts
without requiring unused parameters in stub functions.
"""

from typing import Any, Protocol


class ServiceValidationProtocol(Protocol):
    """Protocol for service validation operations."""

    def validate_contract_compliance(
        self, implementations: Any, contract: Any
    ) -> dict[str, Any]:
        """Validate service implementations comply with contract."""
        ...

    def validate_interchangeability(self, service_pool: Any) -> dict[str, Any]:
        """Validate services can be interchanged."""
        ...

    def validate_interface_compliance(
        self, implementation: Any, interface: Any
    ) -> dict[str, Any]:
        """Validate service implements interface."""
        ...

    def validate_performance_compatibility(
        self, service1: Any, service2: Any
    ) -> dict[str, Any]:
        """Validate services have compatible performance."""
        ...


class SurfaceValidationProtocol(Protocol):
    """Protocol for surface validation operations."""

    def validate_interface_compliance(
        self, surface: Any, interface: Any
    ) -> dict[str, Any]:
        """Validate surface implements interface."""
        ...

    def validate_interchangeability(self, surfaces: Any) -> dict[str, Any]:
        """Validate surfaces can be interchanged."""
        ...

    def validate_performance_compatibility(
        self, surface1: Any, surface2: Any
    ) -> dict[str, Any]:
        """Validate surfaces have compatible performance."""
        ...

    def validate_security_compatibility(
        self, surface1: Any, surface2: Any
    ) -> dict[str, Any]:
        """Validate surfaces have compatible security."""
        ...

    def validate_data_format_compatibility(
        self, surface1: Any, surface2: Any
    ) -> dict[str, Any]:
        """Validate surfaces have compatible data formats."""
        ...


class ValidationResultProtocol(Protocol):
    """Protocol for validation result objects."""

    def get_compliance_score(self) -> float:
        """Get the compliance score."""
        ...

    def is_compliant(self) -> bool:
        """Check if validation passed."""
        ...

    def get_errors(self) -> list[str]:
        """Get validation errors."""
        ...

    def get_warnings(self) -> list[str]:
        """Get validation warnings."""
        ...
