"""
Reusable contract test suite for surface adapters.

This module provides a comprehensive test suite that validates the compliance
of surface adapters with the defined interfaces and contracts.
"""

import asyncio
import time
from datetime import datetime
from typing import Any

from services.common.surfaces.events import WakeDetectedEvent
from services.common.surfaces.interfaces import (
    AudioSink,
    AudioSource,
    ControlChannel,
    SurfaceLifecycle,
)
from services.common.surfaces.types import PCMFrame


class SurfaceAdapterContractTester:
    """
    Contract tester for surface adapters.

    This class provides comprehensive testing of surface adapters to ensure
    they comply with the defined interfaces and contracts.
    """

    def __init__(self):
        """Initialize the contract tester."""
        self.test_results: dict[str, list[dict[str, Any]]] = {}
        self.test_metrics: dict[str, Any] = {}

    async def test_audio_source_contract(self, adapter: AudioSource) -> dict[str, Any]:
        """
        Test AudioSource adapter contract compliance.

        Args:
            adapter: AudioSource adapter to test

        Returns:
            Test results dictionary
        """
        results: dict[str, Any] = {
            "adapter_type": "AudioSource",
            "tests_passed": 0,
            "tests_failed": 0,
            "test_details": [],
        }

        try:
            # Test initialization
            init_result = await self._test_initialization(adapter)
            results["test_details"].append(init_result)
            if init_result["passed"]:
                results["tests_passed"] += 1
            else:
                results["tests_failed"] += 1

            # Test connection
            conn_result = await self._test_connection(adapter)
            results["test_details"].append(conn_result)
            if conn_result["passed"]:
                results["tests_passed"] += 1
            else:
                results["tests_failed"] += 1

            # Test audio frame reading
            frame_result = await self._test_audio_frame_reading(adapter)
            results["test_details"].append(frame_result)
            if frame_result["passed"]:
                results["tests_passed"] += 1
            else:
                results["tests_failed"] += 1

            # Test telemetry
            telemetry_result = await self._test_telemetry(adapter)
            results["test_details"].append(telemetry_result)
            if telemetry_result["passed"]:
                results["tests_passed"] += 1
            else:
                results["tests_failed"] += 1

            # Test disconnection
            disconnect_result = await self._test_disconnection(adapter)
            results["test_details"].append(disconnect_result)
            if disconnect_result["passed"]:
                results["tests_passed"] += 1
            else:
                results["tests_failed"] += 1

        except (ValueError, TypeError, KeyError, RuntimeError) as e:
            results["error"] = str(e)
            results["tests_failed"] += 1

        return results

    async def test_audio_sink_contract(self, adapter: AudioSink) -> dict[str, Any]:
        """
        Test AudioSink adapter contract compliance.

        Args:
            adapter: AudioSink adapter to test

        Returns:
            Test results dictionary
        """
        results: dict[str, Any] = {
            "adapter_type": "AudioSink",
            "tests_passed": 0,
            "tests_failed": 0,
            "test_details": [],
        }

        try:
            # Test initialization
            init_result = await self._test_initialization(adapter)
            results["test_details"].append(init_result)
            if init_result["passed"]:
                results["tests_passed"] += 1
            else:
                results["tests_failed"] += 1

            # Test connection
            conn_result = await self._test_connection(adapter)
            results["test_details"].append(conn_result)
            if conn_result["passed"]:
                results["tests_passed"] += 1
            else:
                results["tests_failed"] += 1

            # Test audio playback
            playback_result = await self._test_audio_playback(adapter)
            results["test_details"].append(playback_result)
            if playback_result["passed"]:
                results["tests_passed"] += 1
            else:
                results["tests_failed"] += 1

            # Test telemetry
            telemetry_result = await self._test_telemetry(adapter)
            results["test_details"].append(telemetry_result)
            if telemetry_result["passed"]:
                results["tests_passed"] += 1
            else:
                results["tests_failed"] += 1

            # Test disconnection
            disconnect_result = await self._test_disconnection(adapter)
            results["test_details"].append(disconnect_result)
            if disconnect_result["passed"]:
                results["tests_passed"] += 1
            else:
                results["tests_failed"] += 1

        except (ValueError, TypeError, KeyError, RuntimeError) as e:
            results["error"] = str(e)
            results["tests_failed"] += 1

        return results

    async def test_control_channel_contract(
        self, adapter: ControlChannel
    ) -> dict[str, Any]:
        """
        Test ControlChannel adapter contract compliance.

        Args:
            adapter: ControlChannel adapter to test

        Returns:
            Test results dictionary
        """
        results: dict[str, Any] = {
            "adapter_type": "ControlChannel",
            "tests_passed": 0,
            "tests_failed": 0,
            "test_details": [],
        }

        try:
            # Test initialization
            init_result = await self._test_initialization(adapter)
            results["test_details"].append(init_result)
            if init_result["passed"]:
                results["tests_passed"] += 1
            else:
                results["tests_failed"] += 1

            # Test connection
            conn_result = await self._test_connection(adapter)
            results["test_details"].append(conn_result)
            if conn_result["passed"]:
                results["tests_passed"] += 1
            else:
                results["tests_failed"] += 1

            # Test event sending
            send_result = await self._test_event_sending(adapter)
            results["test_details"].append(send_result)
            if send_result["passed"]:
                results["tests_passed"] += 1
            else:
                results["tests_failed"] += 1

            # Test event receiving
            receive_result = await self._test_event_receiving(adapter)
            results["test_details"].append(receive_result)
            if receive_result["passed"]:
                results["tests_passed"] += 1
            else:
                results["tests_failed"] += 1

            # Test telemetry
            telemetry_result = await self._test_telemetry(adapter)
            results["test_details"].append(telemetry_result)
            if telemetry_result["passed"]:
                results["tests_passed"] += 1
            else:
                results["tests_failed"] += 1

            # Test disconnection
            disconnect_result = await self._test_disconnection(adapter)
            results["test_details"].append(disconnect_result)
            if disconnect_result["passed"]:
                results["tests_passed"] += 1
            else:
                results["tests_failed"] += 1

        except (ValueError, TypeError, KeyError, RuntimeError) as e:
            results["error"] = str(e)
            results["tests_failed"] += 1

        return results

    async def test_surface_lifecycle_contract(
        self, adapter: SurfaceLifecycle
    ) -> dict[str, Any]:
        """
        Test SurfaceLifecycle adapter contract compliance.

        Args:
            adapter: SurfaceLifecycle adapter to test

        Returns:
            Test results dictionary
        """
        results: dict[str, Any] = {
            "adapter_type": "SurfaceLifecycle",
            "tests_passed": 0,
            "tests_failed": 0,
            "test_details": [],
        }

        try:
            # Test initialization
            init_result = await self._test_initialization(adapter)
            results["test_details"].append(init_result)
            if init_result["passed"]:
                results["tests_passed"] += 1
            else:
                results["tests_failed"] += 1

            # Test connection
            conn_result = await self._test_connection(adapter)
            results["test_details"].append(conn_result)
            if conn_result["passed"]:
                results["tests_passed"] += 1
            else:
                results["tests_failed"] += 1

            # Test lifecycle management
            lifecycle_result = await self._test_lifecycle_management(adapter)
            results["test_details"].append(lifecycle_result)
            if lifecycle_result["passed"]:
                results["tests_passed"] += 1
            else:
                results["tests_failed"] += 1

            # Test telemetry
            telemetry_result = await self._test_telemetry(adapter)
            results["test_details"].append(telemetry_result)
            if telemetry_result["passed"]:
                results["tests_passed"] += 1
            else:
                results["tests_failed"] += 1

            # Test disconnection
            disconnect_result = await self._test_disconnection(adapter)
            results["test_details"].append(disconnect_result)
            if disconnect_result["passed"]:
                results["tests_passed"] += 1
            else:
                results["tests_failed"] += 1

        except (ValueError, TypeError, KeyError, RuntimeError) as e:
            results["error"] = str(e)
            results["tests_failed"] += 1

        return results

    async def _test_initialization(self, adapter: Any) -> dict[str, Any]:
        """Test adapter initialization."""
        try:
            if hasattr(adapter, "initialize"):
                result = await adapter.initialize()
                return {
                    "test_name": "initialization",
                    "passed": result is True,
                    "details": f"Initialize returned: {result}",
                }
            else:
                return {
                    "test_name": "initialization",
                    "passed": True,
                    "details": "No initialize method required",
                }
        except (ValueError, TypeError, KeyError, RuntimeError) as e:
            return {
                "test_name": "initialization",
                "passed": False,
                "details": f"Initialization failed: {e}",
            }

    async def _test_connection(self, adapter: Any) -> dict[str, Any]:
        """Test adapter connection."""
        try:
            if hasattr(adapter, "connect"):
                result = await adapter.connect()
                return {
                    "test_name": "connection",
                    "passed": result is True,
                    "details": f"Connect returned: {result}",
                }
            else:
                return {
                    "test_name": "connection",
                    "passed": True,
                    "details": "No connect method required",
                }
        except (ValueError, TypeError, KeyError, RuntimeError) as e:
            return {
                "test_name": "connection",
                "passed": False,
                "details": f"Connection failed: {e}",
            }

    async def _test_disconnection(self, adapter: Any) -> dict[str, Any]:
        """Test adapter disconnection."""
        try:
            if hasattr(adapter, "disconnect"):
                await adapter.disconnect()
                return {
                    "test_name": "disconnection",
                    "passed": True,
                    "details": "Disconnect completed successfully",
                }
            else:
                return {
                    "test_name": "disconnection",
                    "passed": True,
                    "details": "No disconnect method required",
                }
        except (ValueError, TypeError, KeyError, RuntimeError) as e:
            return {
                "test_name": "disconnection",
                "passed": False,
                "details": f"Disconnection failed: {e}",
            }

    async def _test_audio_frame_reading(self, adapter: AudioSource) -> dict[str, Any]:
        """Test audio frame reading."""
        try:
            if hasattr(adapter, "read_audio_frame"):
                frames = await adapter.read_audio_frame()
                return {
                    "test_name": "audio_frame_reading",
                    "passed": frames is not None,
                    "details": f"Read {1 if frames else 0} frames",
                }
            else:
                return {
                    "test_name": "audio_frame_reading",
                    "passed": False,
                    "details": "No read_audio_frame method found",
                }
        except (ValueError, TypeError, KeyError, RuntimeError) as e:
            return {
                "test_name": "audio_frame_reading",
                "passed": False,
                "details": f"Audio frame reading failed: {e}",
            }

    async def _test_audio_playback(self, adapter: AudioSink) -> dict[str, Any]:
        """Test audio playback."""
        try:
            if hasattr(adapter, "play_audio_chunk"):
                # Create dummy audio frame
                dummy_frame = PCMFrame(
                    pcm=b"\x00" * 1024,
                    timestamp=time.time(),
                    rms=0.0,
                    duration=0.1,
                    sequence=1,
                    sample_rate=16000,
                )
                await adapter.play_audio_chunk(dummy_frame)
                return {
                    "test_name": "audio_playback",
                    "passed": True,
                    "details": "Audio playback completed successfully",
                }
            else:
                return {
                    "test_name": "audio_playback",
                    "passed": False,
                    "details": "No play_audio_chunk method found",
                }
        except (ValueError, TypeError, KeyError, RuntimeError) as e:
            return {
                "test_name": "audio_playback",
                "passed": False,
                "details": f"Audio playback failed: {e}",
            }

    async def _test_event_sending(self, adapter: ControlChannel) -> dict[str, Any]:
        """Test event sending."""
        try:
            if hasattr(adapter, "send_event"):
                # Create dummy event
                dummy_event = WakeDetectedEvent(
                    timestamp=datetime.now().timestamp(),
                    confidence=0.9,
                    ts_device=datetime.now().timestamp(),
                )
                await adapter.send_event(dummy_event)
                return {
                    "test_name": "event_sending",
                    "passed": True,
                    "details": "Event sending completed successfully",
                }
            else:
                return {
                    "test_name": "event_sending",
                    "passed": False,
                    "details": "No send_event method found",
                }
        except (ValueError, TypeError, KeyError, RuntimeError) as e:
            return {
                "test_name": "event_sending",
                "passed": False,
                "details": f"Event sending failed: {e}",
            }

    async def _test_event_receiving(self, adapter: ControlChannel) -> dict[str, Any]:
        """Test event receiving."""
        try:
            if hasattr(adapter, "receive_event"):
                # Try to receive an event (with timeout)
                try:
                    event = await asyncio.wait_for(adapter.receive_event(), timeout=1.0)
                    return {
                        "test_name": "event_receiving",
                        "passed": True,
                        "details": f"Received event: {type(event).__name__}",
                    }
                except TimeoutError:
                    return {
                        "test_name": "event_receiving",
                        "passed": True,
                        "details": "No events received (timeout expected)",
                    }
            else:
                return {
                    "test_name": "event_receiving",
                    "passed": False,
                    "details": "No receive_event method found",
                }
        except (ValueError, TypeError, KeyError, RuntimeError) as e:
            return {
                "test_name": "event_receiving",
                "passed": False,
                "details": f"Event receiving failed: {e}",
            }

    async def _test_lifecycle_management(
        self, adapter: SurfaceLifecycle
    ) -> dict[str, Any]:
        """Test lifecycle management."""
        try:
            if hasattr(adapter, "is_connected"):
                is_connected = adapter.is_connected()
                return {
                    "test_name": "lifecycle_management",
                    "passed": True,
                    "details": f"Connection status: {is_connected}",
                }
            else:
                return {
                    "test_name": "lifecycle_management",
                    "passed": False,
                    "details": "No is_connected method found",
                }
        except (ValueError, TypeError, KeyError, RuntimeError) as e:
            return {
                "test_name": "lifecycle_management",
                "passed": False,
                "details": f"Lifecycle management failed: {e}",
            }

    async def _test_telemetry(self, adapter: Any) -> dict[str, Any]:
        """Test telemetry."""
        try:
            if hasattr(adapter, "get_telemetry"):
                telemetry = await adapter.get_telemetry()
                return {
                    "test_name": "telemetry",
                    "passed": isinstance(telemetry, dict),
                    "details": f"Telemetry data: {len(telemetry)} keys",
                }
            else:
                return {
                    "test_name": "telemetry",
                    "passed": False,
                    "details": "No get_telemetry method found",
                }
        except (ValueError, TypeError, KeyError, RuntimeError) as e:
            return {
                "test_name": "telemetry",
                "passed": False,
                "details": f"Telemetry failed: {e}",
            }

    async def run_comprehensive_tests(self, adapters: dict[str, Any]) -> dict[str, Any]:
        """
        Run comprehensive tests on all adapters.

        Args:
            adapters: Dictionary of adapters to test

        Returns:
            Comprehensive test results
        """
        results: dict[str, Any] = {
            "total_adapters": len(adapters),
            "total_tests_passed": 0,
            "total_tests_failed": 0,
            "adapter_results": {},
            "summary": {},
        }

        for adapter_name, adapter in adapters.items():
            try:
                # Determine adapter type and run appropriate tests
                if isinstance(adapter, AudioSource):
                    adapter_results = await self.test_audio_source_contract(adapter)
                elif isinstance(adapter, AudioSink):
                    adapter_results = await self.test_audio_sink_contract(adapter)
                elif isinstance(adapter, ControlChannel):
                    adapter_results = await self.test_control_channel_contract(adapter)
                elif isinstance(adapter, SurfaceLifecycle):
                    adapter_results = await self.test_surface_lifecycle_contract(
                        adapter
                    )
                else:
                    adapter_results = {
                        "adapter_type": "Unknown",
                        "tests_passed": 0,
                        "tests_failed": 1,
                        "test_details": [
                            {
                                "test_name": "type_detection",
                                "passed": False,
                                "details": f"Unknown adapter type: {type(adapter).__name__}",
                            }
                        ],
                    }

                results["adapter_results"][adapter_name] = adapter_results
                results["total_tests_passed"] += adapter_results["tests_passed"]
                results["total_tests_failed"] += adapter_results["tests_failed"]

            except (ValueError, TypeError, KeyError, RuntimeError) as e:
                results["adapter_results"][adapter_name] = {
                    "error": str(e),
                    "tests_passed": 0,
                    "tests_failed": 1,
                }
                results["total_tests_failed"] += 1

        # Generate summary
        results["summary"] = {
            "success_rate": (
                results["total_tests_passed"]
                / (results["total_tests_passed"] + results["total_tests_failed"])
                if (results["total_tests_passed"] + results["total_tests_failed"]) > 0
                else 0
            ),
            "total_tests": results["total_tests_passed"]
            + results["total_tests_failed"],
            "passed_adapters": sum(
                1
                for r in results["adapter_results"].values()
                if r.get("tests_failed", 0) == 0
            ),
            "failed_adapters": sum(
                1
                for r in results["adapter_results"].values()
                if r.get("tests_failed", 0) > 0
            ),
        }

        return results
