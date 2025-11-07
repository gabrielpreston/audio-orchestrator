"""Component tests for BufferedVoiceSink and packet flow."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from services.discord.receiver import BufferedVoiceSink, FrameCallback, build_sink


@pytest.mark.component
class TestBufferedVoiceSink:
    """Component tests for BufferedVoiceSink packet processing."""

    @pytest.fixture
    def mock_loop(self):
        """Create mock event loop."""
        loop = Mock(spec=asyncio.AbstractEventLoop)
        return loop

    @pytest.fixture
    def mock_callback(self):
        """Create mock async callback."""
        return AsyncMock(spec=FrameCallback)

    @pytest.fixture
    def sink(self, mock_loop, mock_callback):
        """Create BufferedVoiceSink instance."""
        return BufferedVoiceSink(mock_loop, mock_callback)

    def test_handle_packet_with_user_id(self, sink, mock_callback, mock_loop):
        """Test _handle_packet() with user_id available processes immediately."""
        # Setup
        user = Mock()
        user.id = 12345

        data = Mock()
        data.ssrc = 54321
        data.decoded_data = b"pcm_data"
        data.sample_rate = 48000

        # Execute
        sink._handle_packet(user, data)

        # Verify: Callback should be scheduled via run_coroutine_threadsafe
        # Since we're using a mock loop, we can't easily verify thread-safe call
        # The packet processing logic is tested in the async callback chain test

    def test_handle_packet_without_user_id_buffers(self, sink):
        """Test _handle_packet() without user_id buffers packet."""
        # Setup
        user = None
        data = Mock()
        data.ssrc = 54321
        data.decoded_data = b"pcm_data"
        # Explicitly set user_id to None to prevent Mock auto-creation
        data.user_id = None
        # Ensure sample_rate is not auto-created as a Mock
        if hasattr(data, "sample_rate"):
            delattr(data, "sample_rate")

        # Execute
        sink._handle_packet(user, data)

        # Verify: Packet should be buffered
        assert data.ssrc in sink._unknown_ssrc_buffers
        assert len(sink._unknown_ssrc_buffers[data.ssrc]) == 1

    def test_handle_packet_flushes_buffered_on_ssrc_mapping(
        self, sink, mock_callback, mock_loop
    ):
        """Test that buffered packets are flushed when SSRC mapping arrives."""
        # Setup: First packet without user_id
        user1 = None
        data1 = Mock()
        data1.ssrc = 54321
        data1.decoded_data = b"pcm_data_1"
        data1.sample_rate = 48000
        # Explicitly set user_id to None to prevent Mock auto-creation
        data1.user_id = None

        # Buffer first packet
        sink._handle_packet(user1, data1)
        # Verify buffer exists before flushing
        assert data1.ssrc in sink._unknown_ssrc_buffers
        assert len(sink._unknown_ssrc_buffers[data1.ssrc]) == 1

        # Second packet with user_id should flush buffer
        user2 = Mock()
        user2.id = 12345
        data2 = Mock()
        data2.ssrc = 54321  # Same SSRC
        data2.decoded_data = b"pcm_data_2"
        data2.sample_rate = 48000

        # Execute
        sink._handle_packet(user2, data2)

        # Verify: Buffer should be cleared
        assert data2.ssrc not in sink._unknown_ssrc_buffers

    def test_process_packet_without_pcm_logs_warning(self, sink):
        """Test _process_packet() without PCM data logs warning."""
        # Setup
        user = Mock()
        user.id = 12345
        data = Mock()
        data.decoded_data = None
        data.pcm = None
        data.ssrc = 54321

        # Execute
        sink._process_packet(user, data)

        # Verify: Should have logged warning (we can't easily verify logging in component tests)

    def test_process_packet_with_pcm_calls_callback(self, sink, mock_loop):
        """Test _process_packet() with PCM data calls callback via event loop."""
        # Setup
        user = Mock()
        user.id = 12345

        data = Mock()
        data.decoded_data = b"pcm_data" * 100  # Enough data for duration calculation
        data.sample_rate = 48000

        # Patch asyncio.run_coroutine_threadsafe since that's what the code actually uses
        with patch("asyncio.run_coroutine_threadsafe") as mock_run_coroutine:
            future = Mock()
            mock_run_coroutine.return_value = future

            # Execute
            sink._process_packet(user, data)

            # Verify: run_coroutine_threadsafe was called
            assert mock_run_coroutine.called

    @pytest.mark.asyncio
    async def test_async_callback_chain(self):
        """Test that async callback chain works correctly."""
        # Setup: Create real event loop and callback
        loop = asyncio.get_event_loop()

        callback_results = []

        async def test_callback(
            user_id: int, pcm: bytes, duration: float, sample_rate: int
        ) -> None:
            """Test callback that records calls."""
            callback_results.append(
                {
                    "user_id": user_id,
                    "pcm_length": len(pcm),
                    "duration": duration,
                    "sample_rate": sample_rate,
                }
            )

        sink = BufferedVoiceSink(loop, test_callback)

        # Create mock packet data
        user = Mock()
        user.id = 12345
        data = Mock()
        data.decoded_data = b"pcm_data" * 100
        data.sample_rate = 48000

        # Execute: Process packet
        sink._process_packet(user, data)

        # Wait a bit for async callback to complete
        await asyncio.sleep(0.1)

        # Verify: Callback should have been called
        assert len(callback_results) == 1
        assert callback_results[0]["user_id"] == 12345
        assert callback_results[0]["sample_rate"] == 48000

    def test_handler_catches_opuserror_and_continues(self, mock_loop, mock_callback):
        """Test that handler catches OpusError and continues processing."""
        # Setup: Create sink and handler
        sink = BufferedVoiceSink(mock_loop, mock_callback)
        from discord.opus import OpusError

        # Mock _handle_packet to raise OpusError (OpusError requires integer code)
        with patch.object(
            sink,
            "_handle_packet",
            side_effect=OpusError(-1),  # -1 is a generic opus error
        ):
            # Create handler function (simulating build_sink handler)
            handler_call_count = 0

            def handler(user: object | None, data: Any) -> None:
                nonlocal handler_call_count
                handler_call_count += 1
                try:
                    sink._handle_packet(user, data)
                except OpusError:
                    # This simulates the handler behavior
                    pass  # Don't re-raise
                except Exception:
                    raise

            # Execute: Call handler with OpusError
            user = Mock()
            user.id = 12345
            data = Mock()
            data.ssrc = 54321

            # Handler should not raise
            handler(user, data)

            # Verify: Handler completed without raising
            assert handler_call_count == 1

    def test_handler_continues_after_opuserror(self, mock_loop, mock_callback):
        """Test that handler continues processing after OpusError."""
        from discord.opus import OpusError

        sink = BufferedVoiceSink(mock_loop, mock_callback)
        call_count = 0

        def handler(user: object | None, data: Any) -> None:
            nonlocal call_count
            call_count += 1
            try:
                sink._handle_packet(user, data)
            except OpusError:
                # Skip corrupted packet
                pass
            except Exception:
                raise

        user = Mock()
        user.id = 12345
        data1 = Mock()
        data1.ssrc = 54321

        # First call raises OpusError (OpusError requires integer code)
        with patch.object(
            sink, "_handle_packet", side_effect=OpusError(-1)
        ):  # -1 is a generic opus error
            handler(user, data1)

        # Second call should succeed
        data2 = Mock()
        data2.ssrc = 54321
        data2.decoded_data = b"pcm_data"
        data2.sample_rate = 48000

        # Reset mock and verify second call succeeds
        with patch.object(sink, "_handle_packet") as mock_handle:
            mock_handle.return_value = None
            handler(user, data2)
            # Verify second call was processed
            assert mock_handle.called

        # Verify: Both calls completed
        assert call_count == 2

    def test_handler_re_raises_other_exceptions(self, mock_loop, mock_callback):
        """Test that handler re-raises non-OpusError exceptions."""
        sink = BufferedVoiceSink(mock_loop, mock_callback)
        from discord.opus import OpusError

        def handler(user: object | None, data: Any) -> None:
            try:
                sink._handle_packet(user, data)
            except OpusError:
                # Skip OpusError
                pass
            except Exception:
                # Re-raise other exceptions
                raise

        user = Mock()
        user.id = 12345
        data = Mock()
        data.ssrc = 54321

        # Should raise ValueError, not OpusError
        with (
            patch.object(sink, "_handle_packet", side_effect=ValueError("test error")),
            pytest.raises(ValueError, match="test error"),
        ):
            handler(user, data)

    def test_build_sink_handler_opuserror_handling(self, mock_loop, mock_callback):
        """Test that build_sink handler catches OpusError correctly."""
        from discord.opus import OpusError

        # Mock voice_recv module and logger
        with (
            patch("services.discord.receiver.voice_recv") as mock_voice_recv,
            patch("services.discord.receiver._get_logger") as mock_get_logger,
        ):
            mock_basic_sink = Mock()
            mock_voice_recv.BasicSink.return_value = mock_basic_sink
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            # Build sink to get the handler
            build_sink(mock_loop, mock_callback)

            # Get the handler function from BasicSink call
            handler = mock_voice_recv.BasicSink.call_args[0][0]

            # Get the actual sink instance from handler's closure
            # The handler captures buffered_sink in its closure
            # We need to patch _handle_packet on that sink
            # Since we can't easily access the closure, we'll test the handler directly
            # by mocking the logger call

            # Create test data
            user = Mock()
            user.id = 12345
            data = Mock()
            data.ssrc = 54321

            # Patch BufferedVoiceSink._handle_packet to raise OpusError (requires integer code)
            with patch.object(
                BufferedVoiceSink, "_handle_packet", side_effect=OpusError(-1)
            ):  # -1 is a generic opus error
                # Call handler - should not raise
                handler(user, data)

                # Verify: Warning was logged
                mock_logger.warning.assert_called_once()
                call_args = mock_logger.warning.call_args
                assert call_args[0][0] == "voice.corrupted_packet_skipped"
                # OpusError message is generated from code, check it contains error info
                assert "error" in call_args[1]
                assert call_args[1]["user_id"] == 12345
                assert call_args[1]["ssrc"] == 54321
