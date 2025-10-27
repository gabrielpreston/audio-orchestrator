"""Protocol testing utilities for audio-orchestrator.

This module provides utilities for testing protocol compliance,
replacing ABC-specific validation with protocol-based testing.
"""

import inspect
from typing import Any, get_type_hints
from unittest.mock import Mock

from services.common.structured_logging import get_logger


logger = get_logger(__name__)


def assert_implements_protocol(obj: Any, protocol: type) -> None:
    """Assert that object implements protocol.

    Args:
        obj: Object to check
        protocol: Protocol class to check against

    Raises:
        AssertionError: If object doesn't implement protocol
    """
    if not isinstance(protocol, type):
        raise TypeError("protocol must be a type")

    # Get all methods from the protocol
    protocol_methods = []
    for name, _method in inspect.getmembers(protocol, predicate=inspect.isfunction):
        if not name.startswith("_"):
            protocol_methods.append(name)

    # Check if object has all required methods
    missing_methods = []
    for method_name in protocol_methods:
        if not hasattr(obj, method_name):
            missing_methods.append(method_name)

    if missing_methods:
        raise AssertionError(
            f"Object {type(obj).__name__} does not implement protocol {protocol.__name__}. "
            f"Missing methods: {missing_methods}"
        )

    # Check method signatures if possible
    try:
        for method_name in protocol_methods:
            obj_method = getattr(obj, method_name)
            protocol_method = getattr(protocol, method_name)

            # Compare signatures
            obj_sig = inspect.signature(obj_method)
            protocol_sig = inspect.signature(protocol_method)

            if obj_sig != protocol_sig:
                logger.warning(
                    f"Method {method_name} signature mismatch",
                    extra={
                        "object_signature": str(obj_sig),
                        "protocol_signature": str(protocol_sig),
                    },
                )
    except Exception as e:
        logger.warning("Could not validate method signatures", extra={"error": str(e)})


def create_protocol_mock(protocol: type) -> Any:
    """Create mock object implementing protocol.

    Args:
        protocol: Protocol class to mock

    Returns:
        Mock object implementing the protocol
    """
    from unittest.mock import Mock

    mock = Mock()
    mock.__class__.__name__ = f"Mock{protocol.__name__}"

    # Get all methods from the protocol
    for name, _method in inspect.getmembers(protocol, predicate=inspect.isfunction):
        if not name.startswith("_"):
            # Create a mock method
            mock_method = Mock()
            mock_method.__name__ = name
            setattr(mock, name, mock_method)

    return mock


def validate_protocol_compliance(obj: Any, protocol: type) -> dict[str, Any]:
    """Validate protocol compliance and return detailed results.

    Args:
        obj: Object to validate
        protocol: Protocol class to validate against

    Returns:
        Dictionary with validation results
    """
    result: dict[str, Any] = {
        "compliant": True,
        "missing_methods": [],
        "signature_mismatches": [],
        "type_hints": {},
    }

    # Get all methods from the protocol
    protocol_methods = []
    for name, _method in inspect.getmembers(protocol, predicate=inspect.isfunction):
        if not name.startswith("_"):
            protocol_methods.append(name)

    # Check method existence
    for method_name in protocol_methods:
        if not hasattr(obj, method_name):
            result["missing_methods"].append(method_name)
            result["compliant"] = False

    # Check method signatures
    for method_name in protocol_methods:
        if hasattr(obj, method_name):
            try:
                obj_method = getattr(obj, method_name)
                protocol_method = getattr(protocol, method_name)

                obj_sig = inspect.signature(obj_method)
                protocol_sig = inspect.signature(protocol_method)

                if obj_sig != protocol_sig:
                    result["signature_mismatches"].append(
                        {
                            "method": method_name,
                            "object_signature": str(obj_sig),
                            "protocol_signature": str(protocol_sig),
                        }
                    )

                # Get type hints
                try:
                    obj_hints = get_type_hints(obj_method)
                    protocol_hints = get_type_hints(protocol_method)
                    result["type_hints"][method_name] = {
                        "object": obj_hints,
                        "protocol": protocol_hints,
                    }
                except Exception as e:
                    logger.warning(
                        f"Could not validate method {method_name}",
                        extra={"error": str(e)},
                    )
            except Exception as e:
                logger.warning(
                    f"Could not validate method {method_name}", extra={"error": str(e)}
                )

    return result


def create_protocol_test_fixture(protocol: type) -> Any:
    """Create a test fixture that implements a protocol.

    Args:
        protocol: Protocol class to implement

    Returns:
        Test fixture implementing the protocol
    """

    class ProtocolTestFixture:
        """Test fixture implementing the given protocol."""

        def __init__(self) -> None:
            self._mock_data: dict[str, Any] = {}

        def __getattr__(self, name: str) -> Any:
            """Return mock data for any attribute access."""
            if name.startswith("_"):
                return super().__getattribute__(name)

            if name not in self._mock_data:
                self._mock_data[name] = Mock()

            return self._mock_data[name]

        def set_mock_data(self, name: str, value: Any) -> None:
            """Set mock data for a specific method."""
            self._mock_data[name] = value

    return ProtocolTestFixture()


def assert_protocol_composition(obj: Any, protocols: list[type]) -> None:
    """Assert that object implements multiple protocols.

    Args:
        obj: Object to check
        protocols: List of protocol classes to check against

    Raises:
        AssertionError: If object doesn't implement any protocol
    """
    for protocol in protocols:
        assert_implements_protocol(obj, protocol)
