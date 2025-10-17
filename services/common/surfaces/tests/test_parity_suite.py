"""
Tests for cross-surface parity test suite.

This module provides unit tests for the parity testing framework
to ensure it correctly validates performance across different surfaces.
"""

import time
from unittest.mock import AsyncMock

from services.common.surfaces.interfaces import (
    AudioSink,
    AudioSource,
    ControlChannel,
    SurfaceLifecycle,
)
from services.common.surfaces.tests.parity_test_suite import (
    CrossSurfaceParityTester,
    LatencyTarget,
    ParityTestResult,
    ParityTestSuite,
)
from services.common.surfaces.types import PCMFrame


class TestCrossSurfaceParityTester:
    """Test cases for CrossSurfaceParityTester."""

    def test_initialization(self):
        """Test parity tester initialization."""
        tester = CrossSurfaceParityTester()

        assert len(tester.test_results) == 0
        assert len(tester.surface_adapters) == 0
        assert tester.config is not None

    def test_initialization_with_config(self):
        """Test parity tester initialization with custom config."""
        config = ParityTestSuite(
            audio_capture_target_ms=100.0, test_duration_seconds=5.0, sample_count=50
        )
        tester = CrossSurfaceParityTester(config)

        assert tester.config.audio_capture_target_ms == 100.0
        assert tester.config.test_duration_seconds == 5.0
        assert tester.config.sample_count == 50

    def test_register_surface(self):
        """Test surface registration."""
        tester = CrossSurfaceParityTester()

        # Create mock adapters
        audio_source = AsyncMock(spec=AudioSource)
        audio_sink = AsyncMock(spec=AudioSink)
        control_channel = AsyncMock(spec=ControlChannel)
        surface_lifecycle = AsyncMock(spec=SurfaceLifecycle)

        adapters = {
            "audio_source": audio_source,
            "audio_sink": audio_sink,
            "control_channel": control_channel,
            "surface_lifecycle": surface_lifecycle,
        }

        tester.register_surface("test_surface", adapters)

        assert "test_surface" in tester.surface_adapters
        assert tester.surface_adapters["test_surface"] == adapters

    async def test_audio_capture_parity_tests_success(self):
        """Test successful audio capture parity tests."""
        tester = CrossSurfaceParityTester()

        # Create mock audio source
        audio_source = AsyncMock(spec=AudioSource)
        audio_source.initialize.return_value = None
        audio_source.connect.return_value = None
        audio_source.disconnect.return_value = None
        audio_source.read_audio_frame.return_value = [
            PCMFrame(
                pcm=b"\x00" * 1024,
                timestamp=time.time(),
                rms=0.0,
                duration=0.1,
                sequence=1,
                sample_rate=16000,
            )
        ]

        adapters = {"audio_source": audio_source}
        tester.register_surface("test_surface", adapters)

        results = await tester.run_audio_capture_parity_tests()

        assert len(results) == 1
        result = results[0]
        assert result.test_name == "audio_capture"
        assert result.surface_id == "test_surface"
        assert result.success is True
        assert result.latency_ms >= 0
        assert result.target_latency_ms == tester.config.audio_capture_target_ms

    async def test_audio_capture_parity_tests_failure(self):
        """Test audio capture parity tests with failure."""
        tester = CrossSurfaceParityTester()

        # Create mock audio source that fails
        audio_source = AsyncMock(spec=AudioSource)
        audio_source.initialize.return_value = None
        audio_source.connect.return_value = None
        audio_source.read_audio_frame.side_effect = Exception("Read failed")

        adapters = {"audio_source": audio_source}
        tester.register_surface("test_surface", adapters)

        results = await tester.run_audio_capture_parity_tests()

        assert len(results) == 1
        result = results[0]
        assert result.test_name == "audio_capture"
        assert result.surface_id == "test_surface"
        assert result.success is False
        assert result.error_message == "Read failed"

    async def test_audio_playback_parity_tests_success(self):
        """Test successful audio playback parity tests."""
        tester = CrossSurfaceParityTester()

        # Create mock audio sink
        audio_sink = AsyncMock(spec=AudioSink)
        audio_sink.initialize.return_value = None
        audio_sink.connect.return_value = None
        audio_sink.disconnect.return_value = None
        audio_sink.play_audio_chunk.return_value = None

        adapters = {"audio_sink": audio_sink}
        tester.register_surface("test_surface", adapters)

        results = await tester.run_audio_playback_parity_tests()

        assert len(results) == 1
        result = results[0]
        assert result.test_name == "audio_playback"
        assert result.surface_id == "test_surface"
        assert result.success is True
        assert result.latency_ms >= 0
        assert result.target_latency_ms == tester.config.audio_playback_target_ms

    async def test_event_processing_parity_tests_success(self):
        """Test successful event processing parity tests."""
        tester = CrossSurfaceParityTester()

        # Create mock control channel
        control_channel = AsyncMock(spec=ControlChannel)
        control_channel.initialize.return_value = None
        control_channel.connect.return_value = None
        control_channel.disconnect.return_value = None
        control_channel.send_event.return_value = None

        adapters = {"control_channel": control_channel}
        tester.register_surface("test_surface", adapters)

        results = await tester.run_event_processing_parity_tests()

        assert len(results) == 1
        result = results[0]
        assert result.test_name == "event_processing"
        assert result.surface_id == "test_surface"
        assert result.success is True
        assert result.latency_ms >= 0
        assert result.target_latency_ms == tester.config.event_processing_target_ms

    async def test_connection_parity_tests_success(self):
        """Test successful connection parity tests."""
        tester = CrossSurfaceParityTester()

        # Create mock surface lifecycle
        surface_lifecycle = AsyncMock(spec=SurfaceLifecycle)
        surface_lifecycle.initialize.return_value = None
        surface_lifecycle.connect.return_value = True
        surface_lifecycle.disconnect.return_value = None

        adapters = {"surface_lifecycle": surface_lifecycle}
        tester.register_surface("test_surface", adapters)

        results = await tester.run_connection_parity_tests()

        assert len(results) == 1
        result = results[0]
        assert result.test_name == "connection"
        assert result.surface_id == "test_surface"
        assert result.success is True
        assert result.latency_ms >= 0
        assert result.target_latency_ms == tester.config.connection_target_ms

    async def test_health_check_parity_tests_success(self):
        """Test successful health check parity tests."""
        tester = CrossSurfaceParityTester()

        # Create mock surface lifecycle
        surface_lifecycle = AsyncMock(spec=SurfaceLifecycle)
        surface_lifecycle.initialize.return_value = None
        surface_lifecycle.connect.return_value = None
        surface_lifecycle.disconnect.return_value = None
        surface_lifecycle.is_connected.return_value = True

        adapters = {"surface_lifecycle": surface_lifecycle}
        tester.register_surface("test_surface", adapters)

        results = await tester.run_health_check_parity_tests()

        assert len(results) == 1
        result = results[0]
        assert result.test_name == "health_check"
        assert result.surface_id == "test_surface"
        assert result.success is True
        assert result.latency_ms >= 0
        assert result.target_latency_ms == tester.config.health_check_target_ms

    async def test_comprehensive_parity_tests(self):
        """Test comprehensive parity tests."""
        tester = CrossSurfaceParityTester()

        # Create mock adapters
        audio_source = AsyncMock(spec=AudioSource)
        audio_source.initialize.return_value = None
        audio_source.connect.return_value = None
        audio_source.disconnect.return_value = None
        audio_source.read_audio_frame.return_value = [
            PCMFrame(
                pcm=b"\x00" * 1024,
                timestamp=time.time(),
                rms=0.0,
                duration=0.1,
                sequence=1,
                sample_rate=16000,
            )
        ]

        audio_sink = AsyncMock(spec=AudioSink)
        audio_sink.initialize.return_value = None
        audio_sink.connect.return_value = None
        audio_sink.disconnect.return_value = None
        audio_sink.play_audio_chunk.return_value = None

        control_channel = AsyncMock(spec=ControlChannel)
        control_channel.initialize.return_value = None
        control_channel.connect.return_value = None
        control_channel.disconnect.return_value = None
        control_channel.send_event.return_value = None

        surface_lifecycle = AsyncMock(spec=SurfaceLifecycle)
        surface_lifecycle.initialize.return_value = None
        surface_lifecycle.connect.return_value = True
        surface_lifecycle.disconnect.return_value = None
        surface_lifecycle.is_connected.return_value = True

        adapters = {
            "audio_source": audio_source,
            "audio_sink": audio_sink,
            "control_channel": control_channel,
            "surface_lifecycle": surface_lifecycle,
        }

        tester.register_surface("test_surface", adapters)

        results = await tester.run_comprehensive_parity_tests()

        assert "total_tests" in results
        assert "successful_tests" in results
        assert "success_rate" in results
        assert "tests_meeting_targets" in results
        assert "target_meeting_rate" in results
        assert "latency_statistics" in results
        assert "test_results" in results
        assert "timestamp" in results

        assert results["total_tests"] > 0
        assert results["successful_tests"] > 0
        assert 0 <= results["success_rate"] <= 1
        assert 0 <= results["target_meeting_rate"] <= 1

    def test_get_parity_report(self):
        """Test parity report generation."""
        tester = CrossSurfaceParityTester()

        # Add some test results
        result1 = ParityTestResult(
            test_name="audio_capture",
            surface_id="surface1",
            success=True,
            latency_ms=25.0,
            target_latency_ms=50.0,
            meets_target=True,
        )

        result2 = ParityTestResult(
            test_name="audio_playback",
            surface_id="surface1",
            success=True,
            latency_ms=30.0,
            target_latency_ms=50.0,
            meets_target=True,
        )

        result3 = ParityTestResult(
            test_name="audio_capture",
            surface_id="surface2",
            success=False,
            latency_ms=0.0,
            target_latency_ms=50.0,
            meets_target=False,
            error_message="Connection failed",
        )

        tester.test_results = [result1, result2, result3]

        report = tester.get_parity_report()

        assert "overall_statistics" in report
        assert "surface_statistics" in report
        assert "test_results" in report
        assert "timestamp" in report

        assert report["overall_statistics"]["total_tests"] == 3
        assert report["overall_statistics"]["successful_tests"] == 2
        assert report["overall_statistics"]["success_rate"] == 2 / 3
        assert report["overall_statistics"]["tests_meeting_targets"] == 2
        assert report["overall_statistics"]["target_meeting_rate"] == 2 / 3

        assert "surface1" in report["surface_statistics"]
        assert "surface2" in report["surface_statistics"]

        assert len(report["test_results"]) == 3


class TestParityTestResult:
    """Test cases for ParityTestResult dataclass."""

    def test_result_creation(self):
        """Test result creation."""
        result = ParityTestResult(
            test_name="audio_capture",
            surface_id="test_surface",
            success=True,
            latency_ms=25.0,
            target_latency_ms=50.0,
            meets_target=True,
            error_message=None,
        )

        assert result.test_name == "audio_capture"
        assert result.surface_id == "test_surface"
        assert result.success is True
        assert result.latency_ms == 25.0
        assert result.target_latency_ms == 50.0
        assert result.meets_target is True
        assert result.error_message is None
        assert result.timestamp is not None

    def test_result_to_dict(self):
        """Test result to dictionary conversion."""
        result = ParityTestResult(
            test_name="audio_capture",
            surface_id="test_surface",
            success=True,
            latency_ms=25.0,
            target_latency_ms=50.0,
            meets_target=True,
            error_message="Test error",
        )

        data = result.to_dict()

        assert data["test_name"] == "audio_capture"
        assert data["surface_id"] == "test_surface"
        assert data["success"] is True
        assert data["latency_ms"] == 25.0
        assert data["target_latency_ms"] == 50.0
        assert data["meets_target"] is True
        assert data["error_message"] == "Test error"
        assert "timestamp" in data


class TestParityTestSuite:
    """Test cases for ParityTestSuite dataclass."""

    def test_suite_creation(self):
        """Test test suite creation."""
        suite = ParityTestSuite()

        assert suite.audio_capture_target_ms == 50.0
        assert suite.audio_playback_target_ms == 50.0
        assert suite.event_processing_target_ms == 10.0
        assert suite.connection_target_ms == 1000.0
        assert suite.health_check_target_ms == 100.0
        assert suite.test_duration_seconds == 10.0
        assert suite.sample_count == 100
        assert suite.warmup_samples == 10
        assert suite.latency_tolerance_percent == 20.0
        assert suite.max_failure_rate == 5.0

    def test_suite_custom_config(self):
        """Test test suite with custom configuration."""
        suite = ParityTestSuite(
            audio_capture_target_ms=100.0,
            test_duration_seconds=5.0,
            sample_count=50,
            warmup_samples=5,
        )

        assert suite.audio_capture_target_ms == 100.0
        assert suite.test_duration_seconds == 5.0
        assert suite.sample_count == 50
        assert suite.warmup_samples == 5


class TestLatencyTarget:
    """Test cases for LatencyTarget enum."""

    def test_latency_targets(self):
        """Test latency target values."""
        assert LatencyTarget.AUDIO_CAPTURE.value == 50.0
        assert LatencyTarget.AUDIO_PLAYBACK.value == 50.0
        assert LatencyTarget.EVENT_PROCESSING.value == 10.0
        assert LatencyTarget.CONNECTION_ESTABLISHMENT.value == 1000.0
        assert LatencyTarget.HEALTH_CHECK.value == 100.0
