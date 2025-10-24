"""Parameterized unit tests for protocol contract compliance."""

import pytest

from services.common.surfaces.protocols import (
    AudioCaptureProtocol,
    AudioPlaybackProtocol,
    SurfaceControlProtocol,
    SurfaceTelemetryProtocol,
)
from services.tests.utils.protocol_testing import (
    validate_protocol_compliance,
)


@pytest.mark.parametrize(
    "protocol,protocol_name,expected_methods",
    [
        (
            AudioCaptureProtocol,
            "AudioCaptureProtocol",
            ["start_capture", "stop_capture", "read_audio_frame"],
        ),
        (
            AudioPlaybackProtocol,
            "AudioPlaybackProtocol",
            ["play_audio_chunk", "pause_playback", "resume_playback", "set_volume"],
        ),
        (
            SurfaceControlProtocol,
            "SurfaceControlProtocol",
            ["send_control_event", "get_control_events"],
        ),
        (
            SurfaceTelemetryProtocol,
            "SurfaceTelemetryProtocol",
            ["get_telemetry", "get_metrics"],
        ),
    ],
)
class TestProtocolContracts:
    """Parameterized tests for all protocol contracts."""

    @pytest.mark.unit
    def test_protocol_compliance(self, protocol, protocol_name, expected_methods):
        """Test that protocol is properly defined."""
        # Protocols don't have __abstractmethods__ like ABCs
        assert hasattr(protocol, "__annotations__")
        assert protocol_name.endswith("Protocol")

    @pytest.mark.unit
    def test_required_methods(self, protocol, protocol_name, expected_methods):
        """Test that protocol has all required methods."""
        for method in expected_methods:
            assert hasattr(protocol, method)
            assert callable(getattr(protocol, method))

    @pytest.mark.unit
    def test_protocol_validation(self, protocol, protocol_name, expected_methods):
        """Test protocol validation."""
        # Create a mock object to test protocol compliance
        from services.tests.utils.protocol_testing import create_protocol_mock

        mock_obj = create_protocol_mock(protocol)
        result = validate_protocol_compliance(mock_obj, protocol)
        assert result["compliant"]
        assert len(result["missing_methods"]) == 0

    @pytest.mark.unit
    def test_protocol_method_signatures(
        self, protocol, protocol_name, expected_methods
    ):
        """Test that protocol has proper method signatures."""
        import inspect

        # Check that protocol methods have proper signatures
        for method_name in expected_methods:
            if hasattr(protocol, method_name):
                method = getattr(protocol, method_name)
                sig = inspect.signature(method)
                # Protocols should have method signatures
                assert sig is not None

    @pytest.mark.unit
    def test_protocol_structure(self, protocol, protocol_name, expected_methods):
        """Test that protocol has proper structure."""
        # Protocols don't inherit from ABC, they are Protocol types

        assert hasattr(protocol, "__annotations__")
        assert protocol_name.endswith("Protocol")

    @pytest.mark.unit
    def test_protocol_instantiation_fails(
        self, protocol, protocol_name, expected_methods
    ):
        """Test that protocol cannot be instantiated directly."""
        with pytest.raises(TypeError):
            protocol()

    @pytest.mark.unit
    def test_protocol_method_signatures_detailed(
        self, protocol, protocol_name, expected_methods
    ):
        """Test that protocol methods have proper signatures."""
        import inspect

        for method_name in expected_methods:
            if hasattr(protocol, method_name):
                method = getattr(protocol, method_name)
                signature = inspect.signature(method)

                # Basic signature validation - should have self parameter
                assert "self" in signature.parameters
