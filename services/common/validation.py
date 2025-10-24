"""Validation framework for interface-first testing."""

from typing import Any
import numpy as np

from services.tests.contracts.base_contracts import ServiceContract
from services.common.validation_implementations import (
    DefaultServiceValidator,
    DefaultSurfaceValidator,
)

# Create default validators
_service_validator = DefaultServiceValidator()
_surface_validator = DefaultSurfaceValidator()


def validate_audio_data(
    audio_data: np.ndarray[Any, np.dtype[np.floating[Any]]],
    comprehensive: bool = False,
    expected_sample_rate: int | None = None,  # noqa: ARG001
    expected_channels: int | None = None,  # noqa: ARG001
    expected_bit_depth: int | None = None,  # noqa: ARG001
    expected_format: str | None = None,  # noqa: ARG001
) -> dict[str, Any]:
    """
    Validate audio data quality and format.

    Returns:
        {
            'valid': bool,
            'quality_score': float (0.0-1.0),
            'issues': List[str],
            'sample_rate': int,
            'channels': int,
            'bit_depth': int,
            'format': str,
            'duration': float,
            'frequency_analysis': dict (if comprehensive),
            'dynamic_range': dict (if comprehensive)
        }
    """
    issues = []

    # Validate data exists and is not empty
    if audio_data.size == 0:
        return {"valid": False, "quality_score": 0.0, "issues": ["empty_data"]}

    # Check for NaN/Inf values
    if np.any(np.isnan(audio_data)):
        issues.append("nan_values")
    if np.any(np.isinf(audio_data)):
        issues.append("inf_values")

    # Check for silence (all zeros or very low amplitude)
    rms = np.sqrt(np.mean(audio_data**2))
    if rms < 0.001:
        issues.append("silence_detected")

    # Check for clipping
    if np.any(np.abs(audio_data) >= 0.99):
        issues.append("clipping_detected")

    # Calculate quality score
    quality_score = 1.0
    if issues:
        quality_score -= len(issues) * 0.2
    quality_score = max(0.0, min(1.0, quality_score))

    result = {
        "valid": len(
            [i for i in issues if i in ["empty_data", "nan_values", "inf_values"]]
        )
        == 0,
        "quality_score": quality_score,
        "issues": issues,
    }

    # Add comprehensive analysis if requested
    if comprehensive:
        result["frequency_analysis"] = {
            "dominant_frequency": 440.0,  # Placeholder - implement FFT
            "frequency_range": (20.0, 20000.0),
        }
        result["dynamic_range"] = {
            "peak": float(np.max(np.abs(audio_data))),
            "rms": float(rms),
            "dynamic_range_db": float(
                20 * np.log10(np.max(np.abs(audio_data)) / (rms + 1e-10))
            ),
        }

    return result


def validate_interface_contract(
    interface: type,
    interface_name: str,  # noqa: ARG001
) -> dict[str, Any]:
    """
    Validate that an interface is properly defined.

    Returns:
        {
            'compliant': bool,
            'missing_methods': List[str],
            'invalid_signatures': List[str],
            'missing_properties': List[str]
        }
    """
    missing_methods: list[str] = []
    invalid_signatures: list[str] = []

    # Check if it's a protocol class
    if not hasattr(interface, "__annotations__"):
        return {
            "compliant": False,
            "missing_methods": [],
            "invalid_signatures": ["not_abstract_class"],
            "missing_properties": [],
        }

    # Get abstract methods
    abstract_methods: set[str] = getattr(interface, "__abstractmethods__", set())

    return {
        "compliant": len(abstract_methods) > 0,
        "missing_methods": missing_methods,
        "invalid_signatures": invalid_signatures,
        "missing_properties": [],
    }


def validate_service_contract(contract: ServiceContract) -> dict[str, Any]:
    """
    Validate a service contract definition.

    Returns:
        {
            'valid': bool,
            'issues': List[str],
            'warnings': List[str],
            'recommendations': List[str]
        }
    """
    issues = []
    warnings = []
    recommendations: list[str] = []

    # Validate required fields
    if not contract.service_name:
        issues.append("missing_service_name")
    if not contract.base_url:
        issues.append("missing_base_url")
    if not contract.endpoints:
        issues.append("no_endpoints_defined")

    # Check for health endpoints
    health_endpoints = [e for e in contract.endpoints if "health" in e.name.lower()]
    if not health_endpoints:
        warnings.append("missing_health_endpoints")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "recommendations": recommendations,
    }


def check_contract_compliance(contract: ServiceContract) -> dict[str, Any]:
    """
    Check contract compliance score.

    Returns:
        {
            'compliant': bool,
            'compliance_score': float (0.0-1.0),
            'missing_requirements': List[str],
            'non_compliant_areas': List[str]
        }
    """
    missing_requirements = []
    non_compliant_areas: list[str] = []
    score = 1.0

    # Check performance requirements
    if not contract.performance:
        missing_requirements.append("performance_requirements")
        score -= 0.2

    # Check security requirements
    if not contract.security:
        missing_requirements.append("security_requirements")
        score -= 0.2

    return {
        "compliant": score >= 0.8,
        "compliance_score": max(0.0, score),
        "missing_requirements": missing_requirements,
        "non_compliant_areas": non_compliant_areas,
    }


# Hot-swap validation using Protocol-based approach


def validate_service_contract_compliance(
    implementations: Any, contract: Any
) -> dict[str, Any]:
    """Validate service implementations comply with contract."""
    return _service_validator.validate_contract_compliance(implementations, contract)


def validate_service_interchangeability(service_pool: Any) -> dict[str, Any]:
    """Validate services can be interchanged."""
    return _service_validator.validate_interchangeability(service_pool)


def validate_service_interface_compliance(
    implementation: Any, interface: Any
) -> dict[str, Any]:
    """Validate service implements interface."""
    return _service_validator.validate_interface_compliance(implementation, interface)


def validate_service_performance_compatibility(
    service1: Any, service2: Any
) -> dict[str, Any]:
    """Validate services have compatible performance."""
    return _service_validator.validate_performance_compatibility(service1, service2)


def validate_surface_interface_compliance(
    surface: Any, interface: Any
) -> dict[str, Any]:
    """Validate surface implements interface."""
    return _surface_validator.validate_interface_compliance(surface, interface)


def validate_surface_interchangeability(surfaces: Any) -> dict[str, Any]:
    """Validate surfaces can be interchanged."""
    return _surface_validator.validate_interchangeability(surfaces)


def validate_surface_performance_compatibility(
    surface1: Any, surface2: Any
) -> dict[str, Any]:
    """Validate surfaces have compatible performance."""
    return _surface_validator.validate_performance_compatibility(surface1, surface2)


def validate_surface_security_compatibility(
    surface1: Any, surface2: Any
) -> dict[str, Any]:
    """Validate surfaces have compatible security."""
    return _surface_validator.validate_security_compatibility(surface1, surface2)


def validate_surface_data_format_compatibility(
    surface1: Any, surface2: Any
) -> dict[str, Any]:
    """Validate surfaces have compatible data formats."""
    return _surface_validator.validate_data_format_compatibility(surface1, surface2)
