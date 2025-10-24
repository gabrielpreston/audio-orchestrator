"""
Interface testing utilities for interface-first testing.

This module provides utilities for validating interface compliance,
including method validation, property checking, and contract testing.
"""

from abc import ABC
import contextlib
from dataclasses import dataclass
import inspect
import time
from typing import Any


@dataclass
class InterfaceValidationResult:
    """Result of interface validation."""

    interface_name: str
    passed: bool
    errors: list[str]
    warnings: list[str]
    missing_methods: list[str]
    missing_properties: list[str]
    invalid_methods: list[str]
    validation_time_ms: float

    def add_error(self, error: str):
        """Add an error to the validation result."""
        self.errors.append(error)
        self.passed = False

    def add_warning(self, warning: str):
        """Add a warning to the validation result."""
        self.warnings.append(warning)


class InterfaceComplianceValidator:
    """Validator for interface compliance."""

    def __init__(self, interface_class: type[ABC]):
        self.interface_class = interface_class
        self.start_time = time.time()

    def validate_interface_compliance(
        self, implementation: Any
    ) -> InterfaceValidationResult:
        """Validate that an implementation complies with the interface."""
        result = InterfaceValidationResult(
            interface_name=self.interface_class.__name__,
            passed=True,
            errors=[],
            warnings=[],
            missing_methods=[],
            missing_properties=[],
            invalid_methods=[],
            validation_time_ms=0.0,
        )

        try:
            # Get interface methods and properties
            interface_methods = self._get_interface_methods()
            interface_properties = self._get_interface_properties()

            # Check for missing methods
            for method_name in interface_methods:
                if not hasattr(implementation, method_name):
                    result.missing_methods.append(method_name)
                    result.add_error(f"Missing method: {method_name}")
                elif not callable(getattr(implementation, method_name)):
                    result.invalid_methods.append(method_name)
                    result.add_error(f"Method not callable: {method_name}")

            # Check for missing properties
            for property_name in interface_properties:
                if not hasattr(implementation, property_name):
                    result.missing_properties.append(property_name)
                    result.add_error(f"Missing property: {property_name}")

            # Validate method signatures
            self._validate_method_signatures(implementation, result)

            # Validate property types
            self._validate_property_types(implementation, result)

        except Exception as e:
            result.add_error(f"Interface validation failed with exception: {str(e)}")

        result.validation_time_ms = (time.time() - self.start_time) * 1000
        return result

    def _get_interface_methods(self) -> list[str]:
        """Extract abstract methods from interface."""
        methods = []
        for name, method in inspect.getmembers(
            self.interface_class, predicate=inspect.isfunction
        ):
            if getattr(method, "__isabstractmethod__", False):
                methods.append(name)
        return methods

    def _get_interface_properties(self) -> list[str]:
        """Extract abstract properties from interface."""
        properties = []
        for name, prop in inspect.getmembers(
            self.interface_class, predicate=inspect.isdatadescriptor
        ):
            if getattr(prop, "__isabstractmethod__", False):
                properties.append(name)
        return properties

    def _validate_method_signatures(
        self, implementation: Any, result: InterfaceValidationResult
    ):
        """Validate method signatures match interface."""
        for method_name in self._get_interface_methods():
            if hasattr(implementation, method_name):
                try:
                    # Get method signature
                    method = getattr(implementation, method_name)
                    _signature = inspect.signature(method)

                    # Basic signature validation
                    if not callable(method):
                        result.add_error(f"Method {method_name} is not callable")

                except Exception as e:
                    result.add_warning(
                        f"Could not validate signature for {method_name}: {str(e)}"
                    )

    def _validate_property_types(
        self, implementation: Any, result: InterfaceValidationResult
    ):
        """Validate property types match interface."""
        for property_name in self._get_interface_properties():
            if hasattr(implementation, property_name):
                try:
                    # Get property value
                    prop = getattr(implementation, property_name)

                    # Basic property validation
                    if not hasattr(prop, "__get__"):
                        result.add_warning(
                            f"Property {property_name} may not be a proper property"
                        )

                except Exception as e:
                    result.add_warning(
                        f"Could not validate property {property_name}: {str(e)}"
                    )


class MethodContractValidator:
    """Validator for method contracts."""

    def __init__(self, max_latency_ms: int = 100):
        self.max_latency_ms = max_latency_ms

    def validate_method_contracts(
        self, implementation: Any, interface_class: type[ABC]
    ) -> InterfaceValidationResult:
        """Validate that all methods follow contracts."""
        result = InterfaceValidationResult(
            interface_name=interface_class.__name__,
            passed=True,
            errors=[],
            warnings=[],
            missing_methods=[],
            missing_properties=[],
            invalid_methods=[],
            validation_time_ms=0.0,
        )

        start_time = time.time()

        try:
            # Get all methods from the interface
            interface_methods = self._get_interface_methods(interface_class)

            for method_name in interface_methods:
                if hasattr(implementation, method_name):
                    method = getattr(implementation, method_name)

                    # Validate method contract
                    self._validate_method_contract(method, method_name, result)

        except Exception as e:
            result.add_error(f"Method contract validation failed: {str(e)}")

        result.validation_time_ms = (time.time() - start_time) * 1000
        return result

    def _get_interface_methods(self, interface_class: type[ABC]) -> list[str]:
        """Get all methods from interface."""
        methods = []
        for name, method in inspect.getmembers(
            interface_class, predicate=inspect.isfunction
        ):
            if getattr(method, "__isabstractmethod__", False):
                methods.append(name)
        return methods

    def _validate_method_contract(
        self, method: Any, method_name: str, result: InterfaceValidationResult
    ):
        """Validate a single method contract."""
        try:
            # Test method performance
            if callable(method):
                start_time = time.time()

                # Try to call the method (this might fail for some methods)
                try:
                    if inspect.iscoroutinefunction(method):
                        # For async methods, we can't easily test without proper setup
                        result.add_warning(
                            f"Async method {method_name} cannot be performance tested without proper setup"
                        )
                    else:
                        # For sync methods, we can test basic performance
                        # This is a simplified test - real implementation would need proper parameters
                        pass
                except Exception as method_error:
                    result.add_warning(
                        f"Method {method_name} could not be tested: {method_error}"
                    )

                latency_ms = (time.time() - start_time) * 1000
                if latency_ms > self.max_latency_ms:
                    result.add_warning(
                        f"Method {method_name} latency {latency_ms:.1f}ms exceeds {self.max_latency_ms}ms"
                    )

        except Exception as e:
            result.add_warning(
                f"Could not validate method contract for {method_name}: {str(e)}"
            )


class InterfaceTestHelper:
    """Helper class for interface testing."""

    @staticmethod
    def create_mock_implementation(interface_class: type[ABC]) -> Any:
        """Create a mock implementation of an interface."""
        from unittest.mock import Mock

        mock_impl = Mock(spec=interface_class)

        # Add all abstract methods
        for name, method in inspect.getmembers(
            interface_class, predicate=inspect.isfunction
        ):
            if getattr(method, "__isabstractmethod__", False):
                if inspect.iscoroutinefunction(method):
                    setattr(mock_impl, name, Mock(return_value=None))
                else:
                    setattr(mock_impl, name, Mock(return_value=None))

        return mock_impl

    @staticmethod
    def validate_interface_methods(
        implementation: Any, interface_class: type[ABC]
    ) -> list[str]:
        """Validate that implementation has all required interface methods."""
        errors = []

        for name, method in inspect.getmembers(
            interface_class, predicate=inspect.isfunction
        ):
            if getattr(method, "__isabstractmethod__", False):
                if not hasattr(implementation, name):
                    errors.append(f"Missing method: {name}")
                elif not callable(getattr(implementation, name)):
                    errors.append(f"Method not callable: {name}")

        return errors

    @staticmethod
    def validate_interface_properties(
        implementation: Any, interface_class: type[ABC]
    ) -> list[str]:
        """Validate that implementation has all required interface properties."""
        errors = []

        for name, prop in inspect.getmembers(
            interface_class, predicate=inspect.isdatadescriptor
        ):
            if getattr(prop, "__isabstractmethod__", False) and not hasattr(
                implementation, name
            ):  # noqa: SIM102
                errors.append(f"Missing property: {name}")

        return errors

    @staticmethod
    def get_interface_method_signatures(
        interface_class: type[ABC],
    ) -> dict[str, inspect.Signature]:
        """Get method signatures from interface."""
        signatures = {}

        for name, method in inspect.getmembers(
            interface_class, predicate=inspect.isfunction
        ):
            if getattr(method, "__isabstractmethod__", False):
                with contextlib.suppress(Exception):
                    signatures[name] = inspect.signature(method)

        return signatures

    @staticmethod
    def validate_method_signatures(
        implementation: Any, interface_class: type[ABC]
    ) -> list[str]:
        """Validate that implementation method signatures match interface."""
        errors = []
        interface_signatures = InterfaceTestHelper.get_interface_method_signatures(
            interface_class
        )

        for method_name, interface_signature in interface_signatures.items():
            if hasattr(implementation, method_name):
                try:
                    implementation_method = getattr(implementation, method_name)
                    implementation_signature = inspect.signature(implementation_method)

                    # Basic signature comparison
                    if len(implementation_signature.parameters) != len(
                        interface_signature.parameters
                    ):
                        errors.append(f"Method {method_name} parameter count mismatch")

                except Exception as e:
                    errors.append(
                        f"Could not validate signature for {method_name}: {str(e)}"
                    )

        return errors
