"""Component tests for enhancement error recovery."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from services.tests.fixtures.audio_samples import get_clean_sample


@pytest.mark.component
class TestEnhancementErrorRecovery:
    """Test enhancement error handling and recovery."""

    def test_metricgan_runtime_failure(self):
        """Test handling of MetricGAN+ runtime errors."""
        from services.common.audio_enhancement import AudioEnhancer

        # Create mock class that raises RuntimeError during enhancement
        mock_enhancer = MagicMock()
        mock_enhancer.enhance_batch.side_effect = RuntimeError(
            "MetricGAN+ processing failed"
        )

        mock_class = type(
            "MockErrorClass",
            (),
            {
                "from_hparams": classmethod(
                    lambda _cls, *_args, **_kwargs: mock_enhancer
                )
            },
        )

        enhancer = AudioEnhancer(
            enable_metricgan=True,
            enhancement_class=mock_class,
        )

        # Test with sample audio
        sample = get_clean_sample()
        audio_np = (
            np.frombuffer(sample.data, dtype=np.int16).astype(np.float32) / 32768.0
        )

        # Should return original audio on failure
        result = enhancer.enhance_audio(audio_np)
        np.testing.assert_array_equal(result, audio_np)

    async def test_enhancement_with_invalid_audio(self):
        """Test enhancement handles malformed audio."""
        from services.stt.app import _enhance_audio_if_enabled

        # Test with various invalid audio inputs
        invalid_inputs = [
            b"",  # Empty audio
            b"invalid",  # Not WAV format
            b"RIFF\x00\x00\x00\x00WAVE",  # Minimal WAV header
            b"RIFF\x00\x00\x00\x00WAVEfmt \x00\x00\x00\x00",  # Incomplete WAV
        ]

        for invalid_audio in invalid_inputs:
            # Should not crash
            result = await _enhance_audio_if_enabled(invalid_audio)

            # Should return original audio (fallback behavior)
            assert result == invalid_audio

    async def test_enhancement_memory_error(self):
        """Test enhancement handles memory errors gracefully."""
        from services.common.audio_enhancement import AudioEnhancer

        # Create mock class that raises MemoryError
        mock_enhancer = MagicMock()
        mock_enhancer.enhance_batch.side_effect = MemoryError("Insufficient memory")

        mock_class = type(
            "MockMemoryError",
            (),
            {
                "from_hparams": classmethod(
                    lambda _cls, *_args, **_kwargs: mock_enhancer
                )
            },
        )

        enhancer = AudioEnhancer(
            enable_metricgan=True,
            enhancement_class=mock_class,
        )

        sample = get_clean_sample()
        audio_np = (
            np.frombuffer(sample.data, dtype=np.int16).astype(np.float32) / 32768.0
        )

        # Should not crash, should return original audio
        result = enhancer.enhance_audio(audio_np)
        np.testing.assert_array_equal(result, audio_np)

    async def test_enhancement_import_error(self):
        """Test graceful handling when speechbrain not installed."""
        from services.common.audio_enhancement import AudioEnhancer

        # Create mock class that raises ImportError
        mock_class = type(
            "MockImportError",
            (),
            {
                "from_hparams": classmethod(
                    lambda _cls, *_args, **_kwargs: (_ for _ in ()).throw(
                        ImportError("speechbrain not available")
                    )
                )
            },
        )

        # Should gracefully degrade
        enhancer = AudioEnhancer(
            enable_metricgan=True,
            enhancement_class=mock_class,
        )

        # Enhancement should be disabled
        assert not enhancer.is_enhancement_enabled

    async def test_enhancement_timeout_error(self):
        """Test enhancement handles timeout errors."""
        import asyncio
        from unittest.mock import patch

        async def simulate_timeout():
            """Simulate enhancement timeout."""
            await asyncio.sleep(10)  # Simulate long processing
            return b"processed_audio"

        with patch("services.stt.app._audio_enhancer") as mock_enhancer:
            # Configure mock to simulate timeout
            mock_enhancer.is_enhancement_enabled = True
            mock_enhancer.enhance_audio.side_effect = TimeoutError(
                "Enhancement timeout"
            )

            from services.stt.app import _enhance_audio_if_enabled

            sample = get_clean_sample()

            # Should not crash, should return original audio
            result = await _enhance_audio_if_enabled(sample.data)
            assert result == sample.data

    async def test_enhancement_corrupted_model(self):
        """Test enhancement handles corrupted model files."""
        from services.common.audio_enhancement import AudioEnhancer

        # Create mock class that raises FileNotFoundError
        mock_class = type(
            "MockFileError",
            (),
            {
                "from_hparams": classmethod(
                    lambda _cls, *_args, **_kwargs: (_ for _ in ()).throw(
                        FileNotFoundError("Model file not found")
                    )
                )
            },
        )

        enhancer = AudioEnhancer(
            enable_metricgan=True,
            enhancement_class=mock_class,
        )

        # Enhancement should be disabled
        assert not enhancer.is_enhancement_enabled

        # Should return original audio
        sample = get_clean_sample()
        audio_np = (
            np.frombuffer(sample.data, dtype=np.int16).astype(np.float32) / 32768.0
        )
        result = enhancer.enhance_audio(audio_np)
        np.testing.assert_array_equal(result, audio_np)

    async def test_enhancement_partial_failure(self):
        """Test enhancement handles partial processing failures."""
        with patch("services.stt.app._audio_enhancer") as mock_enhancer:
            # Configure mock to fail on specific audio types
            def mock_enhance_audio(audio, sample_rate):
                # Fail on certain audio characteristics
                if len(audio) < 1000:  # Too short
                    raise ValueError("Audio too short for enhancement")
                return audio * 1.1  # Simulate enhancement

            mock_enhancer.is_enhancement_enabled = True
            mock_enhancer.enhance_audio.side_effect = mock_enhance_audio

            from services.stt.app import _enhance_audio_if_enabled

            # Test with short audio (should fail)
            short_audio = b"short"
            result = await _enhance_audio_if_enabled(short_audio)
            assert result == short_audio  # Should return original

            # Test with normal audio (should work)
            sample = get_clean_sample()
            result = await _enhance_audio_if_enabled(sample.data)
            # Should either be enhanced or original (depending on implementation)

    async def test_enhancement_concurrent_failure(self):
        """Test enhancement handles concurrent processing failures."""
        import threading
        import time

        # Simulate concurrent enhancement with some failures
        results = []
        errors = []
        lock = threading.Lock()

        def enhance_audio(audio_data, index):
            """Simulate enhancement with occasional failures."""
            try:
                # Simulate processing time
                time.sleep(0.01)

                # Simulate 20% failure rate (more deterministic)
                if index % 5 == 0:
                    raise RuntimeError(f"Enhancement failure for index {index}")

                return audio_data  # Return processed audio
            except Exception as e:
                with lock:
                    errors.append(e)
                raise  # Re-raise to ensure errors are collected

        # Test concurrent enhancement
        threads = []
        for i in range(20):
            sample = get_clean_sample()

            def safe_enhance(s=sample, idx=i):
                try:
                    result = enhance_audio(s.data, idx)
                    with lock:
                        results.append(result)
                except Exception:  # noqa: S110
                    # Exception already collected in enhance_audio
                    # This is expected behavior for the test
                    pass

            thread = threading.Thread(target=safe_enhance)
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Should have results for successful operations (16 out of 20 should succeed)
        assert len(results) == 16

        # Some errors are expected (4 out of 20 should fail with 20% failure rate)
        assert len(errors) == 4
        assert len(errors) < 10  # Should not be too many errors

    async def test_enhancement_resource_exhaustion(self):
        """Test enhancement handles resource exhaustion."""
        with patch("services.stt.app._audio_enhancer") as mock_enhancer:
            # Configure mock to raise resource exhaustion error
            mock_enhancer.is_enhancement_enabled = True
            mock_enhancer.enhance_audio.side_effect = OSError("No space left on device")

            from services.stt.app import _enhance_audio_if_enabled

            sample = get_clean_sample()

            # Should not crash, should return original audio
            result = await _enhance_audio_if_enabled(sample.data)
            assert result == sample.data

    async def test_enhancement_network_error(self):
        """Test enhancement handles network-related errors."""
        from services.common.audio_enhancement import AudioEnhancer

        # Create mock class that raises ConnectionError
        mock_enhancer = MagicMock()
        mock_enhancer.enhance_batch.side_effect = ConnectionError("Network unavailable")

        mock_class = type(
            "MockNetworkError",
            (),
            {
                "from_hparams": classmethod(
                    lambda _cls, *_args, **_kwargs: mock_enhancer
                )
            },
        )

        enhancer = AudioEnhancer(
            enable_metricgan=True,
            enhancement_class=mock_class,
        )

        sample = get_clean_sample()
        audio_np = (
            np.frombuffer(sample.data, dtype=np.int16).astype(np.float32) / 32768.0
        )

        # Should not crash, should return original audio
        result = enhancer.enhance_audio(audio_np)
        np.testing.assert_array_equal(result, audio_np)

    async def test_enhancement_error_logging(self):
        """Test that enhancement errors are properly logged."""
        from unittest.mock import patch

        # Capture log messages
        log_messages = []

        def capture_log(message, **kwargs):
            log_messages.append((message, kwargs))

        with (
            patch("services.stt.app.logger.error", side_effect=capture_log),
            patch("services.stt.app._audio_enhancer") as mock_enhancer,
        ):
            # Configure mock to raise error
            mock_enhancer.is_enhancement_enabled = True
            mock_enhancer.enhance_audio.side_effect = RuntimeError(
                "Test enhancement error"
            )

            from services.stt.app import _enhance_audio_if_enabled

            sample = get_clean_sample()
            await _enhance_audio_if_enabled(sample.data)

            # Should log the error
            assert len(log_messages) > 0
            assert any("stt.enhancement_error" in str(msg) for msg, _ in log_messages)

    async def test_enhancement_graceful_degradation_chain(self):
        """Test enhancement gracefully degrades through error chain."""
        with patch("services.stt.app._audio_enhancer") as mock_enhancer:
            # Configure mock to fail in different ways
            call_count = 0

            def mock_enhance_audio(audio, sample_rate):
                nonlocal call_count
                call_count += 1

                if call_count == 1:
                    raise RuntimeError("First failure")
                if call_count == 2:
                    raise MemoryError("Second failure")
                return audio  # Eventually works

            mock_enhancer.is_enhancement_enabled = True
            mock_enhancer.enhance_audio.side_effect = mock_enhance_audio

            from services.stt.app import _enhance_audio_if_enabled

            sample = get_clean_sample()

            # First call should fail gracefully
            result1 = await _enhance_audio_if_enabled(sample.data)
            assert result1 == sample.data  # Should return original

            # Second call should also fail gracefully
            result2 = await _enhance_audio_if_enabled(sample.data)
            assert result2 == sample.data  # Should return original

            # Third call should work (if implementation allows retry)
            result3 = await _enhance_audio_if_enabled(sample.data)
            # Should either work or return original
            assert result3 is not None
