"""
Tests for the contract test suite.

This module provides unit tests for the SurfaceLifecycleContractTester
to ensure it correctly validates adapter compliance.
"""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.common.surfaces.interfaces import AudioSink, AudioSource
from services.common.surfaces.tests.contract_test_suite import (
    SurfaceAdapterContractTester,
)
from services.common.surfaces.types import PCMFrame


class TestSurfaceAdapterContractTester:
    """Test cases for SurfaceAdapterContractTester."""

    @pytest.fixture
    def contract_tester(self):
        """Create contract tester instance."""
        return SurfaceAdapterContractTester()

    @pytest.fixture
    def mock_audio_source(self):
        """Create mock AudioSource adapter."""
        adapter = AsyncMock()
        adapter.initialize.return_value = True
        adapter.connect.return_value = True
        adapter.disconnect.return_value = None
        # Make isinstance() checks work
        adapter.__class__ = AudioSource  # type: ignore[assignment]
        adapter.read_audio_frame.return_value = [
            PCMFrame(
                pcm=b"\x00" * 1024,
                timestamp=time.time(),
                rms=0.0,
                duration=0.1,
                sequence=1,
                sample_rate=16000,
            )
        ]
        adapter.get_telemetry.return_value = {"status": "healthy"}
        return adapter

    @pytest.fixture
    def mock_audio_sink(self):
        """Create mock AudioSink adapter."""
        adapter = AsyncMock()
        adapter.initialize.return_value = True
        adapter.connect.return_value = True
        adapter.disconnect.return_value = None
        # Make isinstance() checks work
        adapter.__class__ = AudioSink  # type: ignore[assignment]
        adapter.play_audio_chunk.return_value = None
        adapter.get_telemetry.return_value = {"status": "healthy"}
        return adapter

    @pytest.fixture
    def mock_control_channel(self):
        """Create mock ControlChannel adapter."""
        adapter = AsyncMock()
        adapter.initialize.return_value = True
        adapter.connect.return_value = True
        adapter.disconnect.return_value = None
        adapter.send_event.return_value = None
        adapter.receive_event.return_value = None
        adapter.get_telemetry.return_value = {"status": "healthy"}
        return adapter

    @pytest.fixture
    def mock_surface_lifecycle(self):
        """Create mock SurfaceLifecycle adapter."""
        adapter = AsyncMock()
        adapter.initialize.return_value = True
        adapter.connect.return_value = True
        adapter.disconnect.return_value = None
        adapter.is_connected.return_value = True
        adapter.get_telemetry.return_value = {"status": "healthy"}
        return adapter

    @pytest.mark.component
    async def test_audio_source_contract_success(self):
        """Test successful AudioSource contract validation."""
        contract_tester = self.contract_tester()
        mock_audio_source = self.mock_audio_source()
        results = await contract_tester.test_audio_source_contract(mock_audio_source)

        assert results["adapter_type"] == "AudioSource"
        assert results["tests_passed"] > 0
        assert results["tests_failed"] == 0
        assert len(results["test_details"]) > 0

        # Verify all tests passed
        for test_detail in results["test_details"]:
            assert test_detail["passed"] is True

    @pytest.mark.asyncio
    @pytest.mark.component
    async def test_audio_sink_contract_success(self, contract_tester, mock_audio_sink):
        """Test successful AudioSink contract validation."""
        results = await contract_tester.test_audio_sink_contract(mock_audio_sink)

        assert results["adapter_type"] == "AudioSink"
        assert results["tests_passed"] > 0
        assert results["tests_failed"] == 0
        assert len(results["test_details"]) > 0

        # Verify all tests passed
        for test_detail in results["test_details"]:
            assert test_detail["passed"] is True

    @pytest.mark.asyncio
    @pytest.mark.component
    async def test_control_channel_contract_success(
        self, contract_tester, mock_control_channel
    ):
        """Test successful ControlChannel contract validation."""
        results = await contract_tester.test_control_channel_contract(
            mock_control_channel
        )

        assert results["adapter_type"] == "ControlChannel"
        assert results["tests_passed"] > 0
        assert results["tests_failed"] == 0
        assert len(results["test_details"]) > 0

        # Verify all tests passed
        for test_detail in results["test_details"]:
            assert test_detail["passed"] is True

    @pytest.mark.asyncio
    @pytest.mark.component
    async def test_surface_lifecycle_contract_success(
        self, contract_tester, mock_surface_lifecycle
    ):
        """Test successful SurfaceLifecycle contract validation."""
        results = await contract_tester.test_surface_lifecycle_contract(
            mock_surface_lifecycle
        )

        assert results["adapter_type"] == "SurfaceLifecycle"
        assert results["tests_passed"] > 0
        assert results["tests_failed"] == 0
        assert len(results["test_details"]) > 0

        # Verify all tests passed
        for test_detail in results["test_details"]:
            assert test_detail["passed"] is True

    @pytest.mark.asyncio
    @pytest.mark.component
    async def test_audio_source_contract_failure(self, contract_tester):
        """Test AudioSource contract validation with failing adapter."""
        # Create adapter that fails initialization
        failing_adapter = AsyncMock()
        failing_adapter.initialize.return_value = False
        failing_adapter.connect.return_value = False
        failing_adapter.disconnect.return_value = None
        failing_adapter.read_audio_frame.side_effect = RuntimeError("Read failed")
        failing_adapter.get_telemetry.return_value = {"status": "error"}

        results = await contract_tester.test_audio_source_contract(failing_adapter)

        assert results["adapter_type"] == "AudioSource"
        assert results["tests_failed"] > 0
        assert len(results["test_details"]) > 0

        # Verify some tests failed
        failed_tests = [test for test in results["test_details"] if not test["passed"]]
        assert len(failed_tests) > 0

    @pytest.mark.asyncio
    @pytest.mark.component
    async def test_comprehensive_tests(
        self, contract_tester, mock_audio_source, mock_audio_sink
    ):
        """Test comprehensive test suite."""
        adapters = {"audio_source": mock_audio_source, "audio_sink": mock_audio_sink}

        results = await contract_tester.run_comprehensive_tests(adapters)

        assert results["total_adapters"] == 2
        assert results["total_tests_passed"] > 0
        assert results["total_tests_failed"] == 0
        assert "audio_source" in results["adapter_results"]
        assert "audio_sink" in results["adapter_results"]
        assert "summary" in results
        assert results["summary"]["success_rate"] == 1.0

    @pytest.mark.asyncio
    @pytest.mark.component
    async def test_comprehensive_tests_mixed_results(self, contract_tester):
        """Test comprehensive test suite with mixed results."""
        # Create one successful adapter
        successful_adapter = AsyncMock()
        successful_adapter.__class__ = AudioSource  # type: ignore[assignment]
        successful_adapter.initialize.return_value = True
        successful_adapter.connect.return_value = True
        successful_adapter.disconnect.return_value = None
        successful_adapter.read_audio_frame.return_value = []
        successful_adapter.get_telemetry.return_value = {"status": "healthy"}

        # Create one failing adapter
        failing_adapter = AsyncMock()
        failing_adapter.__class__ = AudioSink  # type: ignore[assignment]
        failing_adapter.initialize.return_value = False
        failing_adapter.connect.return_value = False
        failing_adapter.disconnect.return_value = None
        failing_adapter.play_audio_chunk.side_effect = RuntimeError("Playback failed")
        failing_adapter.get_telemetry.return_value = {"status": "error"}

        adapters = {"successful": successful_adapter, "failing": failing_adapter}

        results = await contract_tester.run_comprehensive_tests(adapters)

        assert results["total_adapters"] == 2
        assert results["total_tests_passed"] > 0
        assert results["total_tests_failed"] > 0
        assert results["summary"]["success_rate"] < 1.0
        assert results["summary"]["passed_adapters"] == 1
        assert results["summary"]["failed_adapters"] == 1

    @pytest.mark.asyncio
    @pytest.mark.component
    async def test_unknown_adapter_type(self, contract_tester):
        """Test handling of unknown adapter types."""
        unknown_adapter = MagicMock()  # Not implementing any interface

        adapters = {"unknown": unknown_adapter}

        results = await contract_tester.run_comprehensive_tests(adapters)

        assert results["total_adapters"] == 1
        assert results["total_tests_failed"] > 0
        assert "unknown" in results["adapter_results"]
        assert results["adapter_results"]["unknown"]["adapter_type"] == "Unknown"

    @pytest.mark.asyncio
    @pytest.mark.component
    async def test_telemetry_validation(self, contract_tester):
        """Test telemetry validation."""
        adapter = AsyncMock()
        adapter.initialize.return_value = True
        adapter.connect.return_value = True
        adapter.disconnect.return_value = None
        adapter.read_audio_frame.return_value = []
        adapter.get_telemetry.return_value = {
            "status": "healthy",
            "metrics": {"cpu": 0.5},
        }

        results = await contract_tester.test_audio_source_contract(adapter)

        # Find telemetry test
        telemetry_test = next(
            (
                test
                for test in results["test_details"]
                if test["test_name"] == "telemetry"
            ),
            None,
        )
        assert telemetry_test is not None
        assert telemetry_test["passed"] is True
        assert "Telemetry data: 2 keys" in telemetry_test["details"]

    @pytest.mark.asyncio
    @pytest.mark.component
    async def test_event_timeout_handling(self, contract_tester):
        """Test event timeout handling in control channel."""
        adapter = AsyncMock()
        adapter.initialize.return_value = True
        adapter.connect.return_value = True
        adapter.disconnect.return_value = None
        adapter.send_event.return_value = None
        adapter.receive_event.side_effect = TimeoutError()
        adapter.get_telemetry.return_value = {"status": "healthy"}

        results = await contract_tester.test_control_channel_contract(adapter)

        # Find event receiving test
        receive_test = next(
            (
                test
                for test in results["test_details"]
                if test["test_name"] == "event_receiving"
            ),
            None,
        )
        assert receive_test is not None
        assert receive_test["passed"] is True
        assert "timeout expected" in receive_test["details"]
