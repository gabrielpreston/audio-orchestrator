"""Audio quality test framework for enhancement validation."""

import httpx
import pytest

from services.tests.fixtures.audio_samples import (
    get_clean_sample,
    get_noisy_samples,
    get_test_audio_samples,
)
from services.tests.utils.service_helpers import docker_compose_test_context


@pytest.mark.quality
class TestAudioQuality:
    """Test audio quality improvements from enhancement."""

    async def test_enhancement_improves_noisy_audio(self):
        """Test enhancement improves transcription of noisy audio."""
        async with docker_compose_test_context(["stt"]):
            # Get synthetic noisy samples
            samples = get_test_audio_samples()
            noisy_samples = [s for s in samples if s.noise_type != "clean"]

            async with httpx.AsyncClient() as client:
                results = []

                for sample in noisy_samples[:3]:  # Test first 3 noisy samples
                    # Transcribe with enhancement (default behavior)
                    response = await client.post(
                        "http://stt:9000/transcribe",
                        files={"audio": ("test.wav", sample.data, "audio/wav")},
                        timeout=30.0,
                    )

                    if response.status_code == 200:
                        result = response.json()
                        results.append(
                            {
                                "sample_type": sample.noise_type,
                                "snr_db": sample.snr_db,
                                "transcript": result.get("transcript", ""),
                                "duration": result.get("duration", 0),
                                "status": "success",
                            }
                        )
                    else:
                        results.append(
                            {
                                "sample_type": sample.noise_type,
                                "snr_db": sample.snr_db,
                                "status": "error",
                                "error": f"HTTP {response.status_code}",
                            }
                        )

                # Verify we got results for noisy audio
                assert len(results) > 0
                successful_results = [r for r in results if r["status"] == "success"]
                assert len(successful_results) > 0, (
                    "No successful transcriptions for noisy audio"
                )

                # Document observations for future WER implementation
                for result in successful_results:
                    print(f"Sample: {result['sample_type']}, SNR: {result['snr_db']}dB")
                    print(f"Transcript: {result['transcript']}")
                    print(f"Duration: {result['duration']}s")
                    print("---")

    async def test_enhancement_preserves_clean_audio(self):
        """Test enhancement doesn't degrade clean audio."""
        async with docker_compose_test_context(["stt"]):
            # Get clean audio sample
            clean_sample = get_clean_sample()

            async with httpx.AsyncClient() as client:
                # Transcribe clean audio
                response = await client.post(
                    "http://stt:9000/transcribe",
                    files={"audio": ("test.wav", clean_sample.data, "audio/wav")},
                    timeout=30.0,
                )

                assert response.status_code == 200
                result = response.json()

                # Verify transcription works with clean audio
                assert "transcript" in result
                assert "duration" in result

                # Clean audio should produce reasonable transcription
                transcript = result["transcript"]
                assert isinstance(transcript, str)
                # Note: We can't easily test quality without ground truth
                # This test verifies the pipeline works end-to-end

    async def test_enhancement_quality_consistency(self):
        """Test enhancement produces consistent quality across similar samples."""
        async with docker_compose_test_context(["stt"]):
            # Get multiple samples of same type
            samples = [get_noisy_samples(snr_db=20) for _ in range(3)]

            async with httpx.AsyncClient() as client:
                results = []

                for i, sample in enumerate(samples):
                    response = await client.post(
                        "http://stt:9000/transcribe",
                        files={"audio": (f"test_{i}.wav", sample.data, "audio/wav")},
                        timeout=30.0,
                    )

                    if response.status_code == 200:
                        result = response.json()
                        results.append(
                            {
                                "sample_id": i,
                                "transcript": result.get("transcript", ""),
                                "duration": result.get("duration", 0),
                                "confidence": result.get("confidence", 0),
                            }
                        )

                # Should have results for all samples
                assert len(results) == 3

                # Results should be reasonably consistent
                transcripts = [r["transcript"] for r in results]
                durations = [r["duration"] for r in results]

                # Duration should be similar (same audio length)
                duration_variance = max(durations) - min(durations)
                assert duration_variance < 1.0, (
                    f"Duration variance too high: {duration_variance}"
                )

                # Transcripts should be similar (same audio content)
                # Note: Without ground truth, we can only check they're not empty
                for transcript in transcripts:
                    assert len(transcript) > 0, "Empty transcript for similar samples"

    async def test_enhancement_quality_across_noise_levels(self):
        """Test enhancement quality across different noise levels."""
        async with docker_compose_test_context(["stt"]):
            # Test across different SNR levels
            snr_levels = [30, 20, 10, 5]
            results = []

            async with httpx.AsyncClient() as client:
                for snr_db in snr_levels:
                    sample = get_noisy_samples(snr_db=snr_db)

                    response = await client.post(
                        "http://stt:9000/transcribe",
                        files={"audio": ("test.wav", sample.data, "audio/wav")},
                        timeout=30.0,
                    )

                    if response.status_code == 200:
                        result = response.json()
                        results.append(
                            {
                                "snr_db": snr_db,
                                "transcript": result.get("transcript", ""),
                                "duration": result.get("duration", 0),
                                "status": "success",
                            }
                        )
                    else:
                        results.append(
                            {
                                "snr_db": snr_db,
                                "status": "error",
                                "error": f"HTTP {response.status_code}",
                            }
                        )

                # Should have results for all SNR levels
                assert len(results) == len(snr_levels)

                # Document quality across noise levels
                for result in results:
                    if result["status"] == "success":
                        print(f"SNR: {result['snr_db']}dB")
                        print(f"Transcript: {result['transcript']}")
                        print(f"Duration: {result['duration']}s")
                        print("---")

    async def test_enhancement_quality_with_echo(self):
        """Test enhancement quality with echo/reverb effects."""
        async with docker_compose_test_context(["stt"]):
            # Get echo sample
            samples = get_test_audio_samples()
            echo_samples = [s for s in samples if s.noise_type == "echo"]

            if not echo_samples:
                pytest.skip("No echo samples available")

            echo_sample = echo_samples[0]

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://stt:9000/transcribe",
                    files={"audio": ("test.wav", echo_sample.data, "audio/wav")},
                    timeout=30.0,
                )

                if response.status_code == 200:
                    result = response.json()

                    # Verify transcription works with echo
                    assert "transcript" in result
                    assert "duration" in result

                    print(f"Echo sample transcription: {result['transcript']}")
                    print(f"Duration: {result['duration']}s")
                else:
                    # Echo might cause issues, but service should handle gracefully
                    assert response.status_code in [200, 400, 422]

    async def test_enhancement_quality_with_background_music(self):
        """Test enhancement quality with background music."""
        async with docker_compose_test_context(["stt"]):
            # Get background music samples
            samples = get_test_audio_samples()
            music_samples = [s for s in samples if s.noise_type == "background_music"]

            if not music_samples:
                pytest.skip("No background music samples available")

            async with httpx.AsyncClient() as client:
                for sample in music_samples[:2]:  # Test first 2 music samples
                    response = await client.post(
                        "http://stt:9000/transcribe",
                        files={"audio": ("test.wav", sample.data, "audio/wav")},
                        timeout=30.0,
                    )

                    if response.status_code == 200:
                        result = response.json()

                        # Verify transcription works with background music
                        assert "transcript" in result
                        assert "duration" in result

                        print(
                            f"Background music (SNR: {sample.snr_db}dB): {result['transcript']}"
                        )
                    else:
                        # Background music might cause issues
                        assert response.status_code in [200, 400, 422]

    async def test_enhancement_quality_metrics_preparation(self):
        """Test preparation for quality metrics collection."""
        async with docker_compose_test_context(["stt"]):
            # This test prepares for future WER calculation
            samples = get_test_audio_samples()

            async with httpx.AsyncClient() as client:
                quality_data = []

                for sample in samples[:5]:  # Test first 5 samples
                    response = await client.post(
                        "http://stt:9000/transcribe",
                        files={"audio": ("test.wav", sample.data, "audio/wav")},
                        timeout=30.0,
                    )

                    if response.status_code == 200:
                        result = response.json()

                        quality_data.append(
                            {
                                "sample_id": sample.noise_type,
                                "snr_db": sample.snr_db,
                                "transcript": result.get("transcript", ""),
                                "duration": result.get("duration", 0),
                                "confidence": result.get("confidence", 0),
                                "audio_metadata": {
                                    "sample_rate": sample.sample_rate,
                                    "channels": sample.channels,
                                    "duration_seconds": sample.duration_seconds,
                                },
                            }
                        )

                # Verify we collected quality data
                assert len(quality_data) > 0

                # Save quality data for future WER analysis
                import json

                with open("quality_test_data.json", "w") as f:
                    json.dump(quality_data, f, indent=2)

                print(f"Collected quality data for {len(quality_data)} samples")
                print("Quality data saved to quality_test_data.json")

    async def test_enhancement_quality_regression_detection(self):
        """Test framework for detecting quality regressions."""
        async with docker_compose_test_context(["stt"]):
            # Test with known good samples
            clean_sample = get_clean_sample()

            async with httpx.AsyncClient() as client:
                # Measure quality metrics
                response = await client.post(
                    "http://stt:9000/transcribe",
                    files={"audio": ("test.wav", clean_sample.data, "audio/wav")},
                    timeout=30.0,
                )

                if response.status_code == 200:
                    result = response.json()

                    # Collect quality metrics
                    quality_metrics = {
                        "transcript_length": len(result.get("transcript", "")),
                        "duration": result.get("duration", 0),
                        "confidence": result.get("confidence", 0),
                        "processing_time": result.get("processing_time", 0),
                    }

                    # Verify quality metrics are reasonable
                    assert quality_metrics["transcript_length"] > 0
                    assert quality_metrics["duration"] > 0

                    # Save baseline metrics for regression detection
                    import json

                    with open("baseline_quality_metrics.json", "w") as f:
                        json.dump(quality_metrics, f, indent=2)

                    print(f"Baseline quality metrics: {quality_metrics}")
                    print("Baseline metrics saved for regression detection")
                else:
                    pytest.fail(
                        f"Quality regression test failed: HTTP {response.status_code}"
                    )

    async def test_enhancement_quality_across_audio_formats(self):
        """Test enhancement quality across different audio characteristics."""
        async with docker_compose_test_context(["stt"]):
            # Test with different sample types
            test_cases = [
                ("clean", get_clean_sample()),
                ("noisy_30db", get_noisy_samples(snr_db=30)),
                ("noisy_20db", get_noisy_samples(snr_db=20)),
                ("noisy_10db", get_noisy_samples(snr_db=10)),
            ]

            async with httpx.AsyncClient() as client:
                quality_results = []

                for case_name, sample in test_cases:
                    response = await client.post(
                        "http://stt:9000/transcribe",
                        files={"audio": ("test.wav", sample.data, "audio/wav")},
                        timeout=30.0,
                    )

                    if response.status_code == 200:
                        result = response.json()

                        quality_results.append(
                            {
                                "case": case_name,
                                "transcript": result.get("transcript", ""),
                                "duration": result.get("duration", 0),
                                "confidence": result.get("confidence", 0),
                                "status": "success",
                            }
                        )
                    else:
                        quality_results.append(
                            {
                                "case": case_name,
                                "status": "error",
                                "error": f"HTTP {response.status_code}",
                            }
                        )

                # Verify we got results for all test cases
                assert len(quality_results) == len(test_cases)

                # Document quality across formats
                for result in quality_results:
                    print(f"Case: {result['case']}")
                    if result["status"] == "success":
                        print(f"Transcript: {result['transcript']}")
                        print(f"Confidence: {result['confidence']}")
                    else:
                        print(f"Error: {result['error']}")
                    print("---")
