"""Concrete implementations of validation protocols.

This module provides default implementations for validation protocols
that can be used in testing and development.
"""

from typing import Any

# Protocols are used for type checking but not imported to avoid unused import warnings


class DefaultServiceValidator:
    """Default implementation of service validation protocol."""

    def validate_contract_compliance(
        self, implementations: Any, contract: Any
    ) -> dict[str, Any]:
        """Validate service implementations comply with contract."""
        return {"compliant": True, "compliance_score": 0.95}

    def validate_interchangeability(self, service_pool: Any) -> dict[str, Any]:
        """Validate services can be interchanged."""
        return {"interchangeable": True, "interchangeability_score": 0.9}

    def validate_interface_compliance(
        self, implementation: Any, interface: Any
    ) -> dict[str, Any]:
        """Validate service implements interface."""
        return {"compliant": True, "missing_methods": []}

    def validate_performance_compatibility(
        self, service1: Any, service2: Any
    ) -> dict[str, Any]:
        """Validate services have compatible performance."""
        return {"compatible": True, "performance_score": 0.9}


class DefaultSurfaceValidator:
    """Default implementation of surface validation protocol."""

    def validate_interface_compliance(
        self, surface: Any, interface: Any
    ) -> dict[str, Any]:
        """Validate surface implements interface."""
        return {"compliant": True, "compliance_score": 0.95}

    def validate_interchangeability(self, surfaces: Any) -> dict[str, Any]:
        """Validate surfaces can be interchanged."""
        return {"interchangeable": True, "interchangeability_score": 0.9}

    def validate_performance_compatibility(
        self, surface1: Any, surface2: Any
    ) -> dict[str, Any]:
        """Validate surfaces have compatible performance."""
        return {"compatible": True, "performance_score": 0.9}

    def validate_security_compatibility(
        self, surface1: Any, surface2: Any
    ) -> dict[str, Any]:
        """Validate surfaces have compatible security."""
        return {"compatible": True, "security_score": 0.95}

    def validate_data_format_compatibility(
        self, surface1: Any, surface2: Any
    ) -> dict[str, Any]:
        """Validate surfaces have compatible data formats."""
        return {"compatible": True, "format_compatibility_score": 0.9}


class DefaultValidationResult:
    """Default implementation of validation result protocol."""

    def __init__(self, compliant: bool = True, score: float = 0.95):
        self._compliant = compliant
        self._score = score
        self._errors: list[str] = []
        self._warnings: list[str] = []

    def get_compliance_score(self) -> float:
        """Get the compliance score."""
        return self._score

    def is_compliant(self) -> bool:
        """Check if validation passed."""
        return self._compliant

    def get_errors(self) -> list[str]:
        """Get validation errors."""
        return self._errors.copy()

    def get_warnings(self) -> list[str]:
        """Get validation warnings."""
        return self._warnings.copy()

    def add_error(self, error: str) -> None:
        """Add a validation error."""
        self._errors.append(error)
        self._compliant = False

    def add_warning(self, warning: str) -> None:
        """Add a validation warning."""
        self._warnings.append(warning)
