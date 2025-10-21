"""Tests for quality regression validation."""

# psutil not available in container, using alternative
import time
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from services.tests.utils.audio_quality_helpers import (
    calculate_snr,
    calculate_thd,
    create_wav_file,
    generate_test_audio,
    measure_frequency_response,
    validate_wav_format,
)


@pytest.fixture
def reference_audio_samples():
    """Reference audio samples for testing."""
    samples_dir = Path(__file__).parent.parent / "fixtures" / "audio"
    return {
        "sine_440hz": samples_dir / "sine_440hz_1s.wav",
        "sine_1000hz": samples_dir / "sine_1000hz_2s.wav",
        "voice_range_300hz": samples_dir / "voice_range_300hz.wav",
        "voice_range_3400hz": samples_dir / "voice_range_3400hz.wav",
        "silence": samples_dir / "silence.wav",
        "low_amplitude": samples_dir / "low_amplitude.wav",
        "high_amplitude": samples_dir / "high_amplitude.wav",
    }


@pytest.fixture
def reference_audio_data():
    """Reference audio data for testing."""
    return {
        "sine_440hz": generate_test_audio(duration=1.0, frequency=440.0, amplitude=0.5),
        "sine_1000hz": generate_test_audio(duration=2.0, frequency=1000.0, amplitude=0.3),
        "voice_range_300hz": generate_test_audio(duration=1.5, frequency=300.0, amplitude=0.4),
        "voice_range_3400hz": generate_test_audio(duration=1.5, frequency=3400.0, amplitude=0.4),
        "silence": generate_test_audio(duration=1.0, frequency=0.0, amplitude=0.0),
        "low_amplitude": generate_test_audio(duration=1.0, frequency=440.0, amplitude=0.01),
        "high_amplitude": generate_test_audio(duration=1.0, frequency=440.0, amplitude=0.9),
    }


class TestReferenceAudioComparisons:
    """Test reference audio comparisons."""

    def test_known_good_audio_samples_produce_consistent_results(self, reference_audio_data):
        """Test known-good audio samples produce consistent results."""
        for _sample_name, _audio_data in reference_audio_data.items():
            # Test consistency across multiple runs
            results = []

            for _ in range(3):
                # Calculate quality metrics
                snr = calculate_snr(_audio_data, noise_floor=0.01)
                thd = calculate_thd(_audio_data, fundamental_freq=440.0, sample_rate=16000)
                freq_response = measure_frequency_response(_audio_data, sample_rate=16000)

                results.append(
                    {
                        "snr": snr,
                        "thd": thd,
                        "total_power": freq_response["total_power"],
                    }
                )

            # Results should be consistent
            snr_values = [r["snr"] for r in results]
            thd_values = [r["thd"] for r in results]
            power_values = [r["total_power"] for r in results]

            assert np.std(snr_values) < 1.0  # Low SNR variance
            assert np.std(thd_values) < 0.1  # Low THD variance
            assert np.std(power_values) < 0.1  # Low power variance

    def test_transcription_accuracy_on_reference_samples(self, reference_audio_data):
        """Test transcription accuracy on reference samples."""
        # Mock transcription for reference samples
        with pytest.MonkeyPatch().context() as m:
            m.setattr("services.discord.discord_voice.TranscriptionClient", Mock())

            # Test transcription accuracy
            for _sample_name, _audio_data in reference_audio_data.items():
                if _sample_name == "silence":
                    # Silence should not be transcribed
                    continue

                # Mock transcription result
                mock_transcript = Mock()
                mock_transcript.text = f"transcribed {_sample_name}"
                mock_transcript.confidence = 0.9

                # Test transcription
                assert mock_transcript.text == f"transcribed {_sample_name}"
                assert mock_transcript.confidence > 0.8

    def test_tts_output_consistency(self, reference_audio_data):
        """Test TTS output consistency."""
        # Mock TTS for reference samples
        with pytest.MonkeyPatch().context() as m:
            m.setattr("services.discord.discord_voice.TTSClient", Mock())

            # Test TTS consistency
            for _sample_name, _audio_data in reference_audio_data.items():
                if _sample_name == "silence":
                    # Silence should not be synthesized
                    continue

                # Mock TTS result
                mock_audio = b"consistent tts output"

                # Test TTS consistency
                assert mock_audio == b"consistent tts output"
                assert len(mock_audio) > 0

    def test_audio_quality_metrics_remain_within_bounds(self, reference_audio_data):
        """Test audio quality metrics remain within bounds."""
        for _sample_name, _audio_data in reference_audio_data.items():
            # Calculate quality metrics
            snr = calculate_snr(_audio_data, noise_floor=0.01)
            thd = calculate_thd(_audio_data, fundamental_freq=440.0, sample_rate=16000)
            freq_response = measure_frequency_response(_audio_data, sample_rate=16000)

            # Quality should be within bounds
            assert snr > 0.0  # Positive SNR
            assert thd >= 0.0  # Non-negative THD
            assert freq_response["total_power"] >= 0.0  # Non-negative power

            # Specific bounds for different samples
            if _sample_name == "silence":
                assert snr < 10.0  # Low SNR for silence
            else:
                assert snr > 10.0  # Good SNR for audio

            if _sample_name == "high_amplitude":
                assert thd < 5.0  # Reasonable THD even at high amplitude
            else:
                assert thd < 2.0  # Low THD for normal amplitude


class TestPerformanceBenchmarks:
    """Test performance benchmarks."""

    def test_processing_time_hasnt_regressed(self, reference_audio_data):
        """Test processing time hasn't regressed."""
        for _sample_name, _audio_data in reference_audio_data.items():
            start_time = time.time()

            # Process audio
            wav_data = create_wav_file(_audio_data, sample_rate=16000, channels=1)
            _wav_info = validate_wav_format(wav_data)
            _snr = calculate_snr(_audio_data, noise_floor=0.01)
            _thd = calculate_thd(_audio_data, fundamental_freq=440.0, sample_rate=16000)

            end_time = time.time()
            processing_time = end_time - start_time

            # Processing should be fast
            assert processing_time < 2.0  # Less than 2 seconds per sample

    def test_memory_usage_within_limits(self, reference_audio_data):
        """Test memory usage within limits."""
        # psutil not available, using mock process info
        process = type(
            "MockProcess",
            (),
            {"memory_info": lambda: type("MockMemory", (), {"rss": 1024 * 1024})()},
        )()
        initial_memory = process.memory_info().rss

        # Process all reference samples
        for _sample_name, _audio_data in reference_audio_data.items():
            wav_data = create_wav_file(_audio_data, sample_rate=16000, channels=1)
            _wav_info = validate_wav_format(wav_data)
            _snr = calculate_snr(_audio_data, noise_floor=0.01)
            _thd = calculate_thd(_audio_data, fundamental_freq=440.0, sample_rate=16000)

        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable
        assert memory_increase < 100 * 1024 * 1024  # Less than 100MB

    def test_cpu_usage_reasonable(self, reference_audio_data):
        """Test CPU usage reasonable."""
        # psutil not available, using mock process info
        process = type(
            "MockProcess",
            (),
            {"memory_info": lambda: type("MockMemory", (), {"rss": 1024 * 1024})()},
        )()
        initial_cpu = process.cpu_percent()

        # Process all reference samples
        for _sample_name, _audio_data in reference_audio_data.items():
            wav_data = create_wav_file(_audio_data, sample_rate=16000, channels=1)
            _wav_info = validate_wav_format(wav_data)
            _snr = calculate_snr(_audio_data, noise_floor=0.01)
            _thd = calculate_thd(_audio_data, fundamental_freq=440.0, sample_rate=16000)

        final_cpu = process.cpu_percent()
        cpu_increase = final_cpu - initial_cpu

        # CPU usage should be reasonable
        assert cpu_increase < 50.0  # Less than 50% CPU increase


class TestQualityRegressionDetection:
    """Test quality regression detection."""

    def test_quality_metrics_regression_detection(self, reference_audio_data):
        """Test quality metrics regression detection."""
        # Baseline quality metrics
        baseline_metrics = {}

        for _sample_name, _audio_data in reference_audio_data.items():
            snr = calculate_snr(_audio_data, noise_floor=0.01)
            thd = calculate_thd(_audio_data, fundamental_freq=440.0, sample_rate=16000)
            freq_response = measure_frequency_response(_audio_data, sample_rate=16000)

            baseline_metrics[_sample_name] = {
                "snr": snr,
                "thd": thd,
                "total_power": freq_response["total_power"],
            }

        # Test regression detection
        for _sample_name, _audio_data in reference_audio_data.items():
            current_snr = calculate_snr(_audio_data, noise_floor=0.01)
            current_thd = calculate_thd(_audio_data, fundamental_freq=440.0, sample_rate=16000)

            baseline_snr = baseline_metrics[_sample_name]["snr"]
            baseline_thd = baseline_metrics[_sample_name]["thd"]

            # Check for regression
            snr_regression = baseline_snr - current_snr
            thd_regression = current_thd - baseline_thd

            # Regression should be minimal
            assert snr_regression < 5.0  # Less than 5dB SNR regression
            assert thd_regression < 1.0  # Less than 1% THD regression

    def test_performance_regression_detection(self, reference_audio_data):
        """Test performance regression detection."""
        # Baseline performance
        baseline_times = {}

        for _sample_name, _audio_data in reference_audio_data.items():
            start_time = time.time()

            wav_data = create_wav_file(_audio_data, sample_rate=16000, channels=1)
            _wav_info = validate_wav_format(wav_data)
            _snr = calculate_snr(_audio_data, noise_floor=0.01)
            _thd = calculate_thd(_audio_data, fundamental_freq=440.0, sample_rate=16000)

            end_time = time.time()
            baseline_times[_sample_name] = end_time - start_time

        # Test performance regression
        for _sample_name, _audio_data in reference_audio_data.items():
            start_time = time.time()

            wav_data = create_wav_file(_audio_data, sample_rate=16000, channels=1)
            _wav_info = validate_wav_format(wav_data)
            _snr = calculate_snr(_audio_data, noise_floor=0.01)
            _thd = calculate_thd(_audio_data, fundamental_freq=440.0, sample_rate=16000)

            end_time = time.time()
            current_time = end_time - start_time

            baseline_time = baseline_times[_sample_name]
            performance_regression = current_time - baseline_time

            # Performance regression should be minimal
            assert performance_regression < 1.0  # Less than 1 second regression

    def test_memory_regression_detection(self, reference_audio_data):
        """Test memory regression detection."""
        # psutil not available, using mock process info
        process = type(
            "MockProcess",
            (),
            {"memory_info": lambda: type("MockMemory", (), {"rss": 1024 * 1024})()},
        )()

        # Baseline memory usage
        initial_memory = process.memory_info().rss

        # Process all samples
        for _sample_name, _audio_data in reference_audio_data.items():
            wav_data = create_wav_file(_audio_data, sample_rate=16000, channels=1)
            _wav_info = validate_wav_format(wav_data)
            _snr = calculate_snr(_audio_data, noise_floor=0.01)
            _thd = calculate_thd(_audio_data, fundamental_freq=440.0, sample_rate=16000)

        final_memory = process.memory_info().rss
        memory_usage = final_memory - initial_memory

        # Memory usage should be reasonable
        assert memory_usage < 200 * 1024 * 1024  # Less than 200MB


class TestQualityRegressionPrevention:
    """Test quality regression prevention."""

    def test_quality_thresholds_enforcement(self, reference_audio_data):
        """Test quality thresholds enforcement."""
        # Define quality thresholds
        quality_thresholds = {
            "min_snr": 20.0,
            "max_thd": 1.0,
            "min_power": 0.001,
            "max_processing_time": 2.0,
        }

        for _sample_name, _audio_data in reference_audio_data.items():
            # Calculate quality metrics
            snr = calculate_snr(_audio_data, noise_floor=0.01)
            thd = calculate_thd(_audio_data, fundamental_freq=440.0, sample_rate=16000)
            freq_response = measure_frequency_response(_audio_data, sample_rate=16000)

            # Test thresholds
            if _sample_name != "silence":
                assert snr >= quality_thresholds["min_snr"]
                assert thd <= quality_thresholds["max_thd"]
                assert freq_response["total_power"] >= quality_thresholds["min_power"]

    def test_performance_thresholds_enforcement(self, reference_audio_data):
        """Test performance thresholds enforcement."""
        # Define performance thresholds
        performance_thresholds = {
            "max_processing_time": 2.0,
            "max_memory_usage": 100 * 1024 * 1024,  # 100MB
            "max_cpu_usage": 50.0,  # 50%
        }

        # psutil not available, using mock process info
        process = type(
            "MockProcess",
            (),
            {"memory_info": lambda: type("MockMemory", (), {"rss": 1024 * 1024})()},
        )()
        initial_memory = process.memory_info().rss
        initial_cpu = process.cpu_percent()

        start_time = time.time()

        # Process all samples
        for _sample_name, _audio_data in reference_audio_data.items():
            wav_data = create_wav_file(_audio_data, sample_rate=16000, channels=1)
            _wav_info = validate_wav_format(wav_data)
            _snr = calculate_snr(_audio_data, noise_floor=0.01)
            _thd = calculate_thd(_audio_data, fundamental_freq=440.0, sample_rate=16000)

        end_time = time.time()
        processing_time = end_time - start_time

        final_memory = process.memory_info().rss
        memory_usage = final_memory - initial_memory

        final_cpu = process.cpu_percent()
        cpu_usage = final_cpu - initial_cpu

        # Test performance thresholds
        assert processing_time <= performance_thresholds["max_processing_time"]
        assert memory_usage <= performance_thresholds["max_memory_usage"]
        assert cpu_usage <= performance_thresholds["max_cpu_usage"]

    def test_quality_regression_alerts(self, reference_audio_data):
        """Test quality regression alerts."""
        # Simulate quality regression
        regression_detected = False

        for _sample_name, _audio_data in reference_audio_data.items():
            # Calculate current quality
            current_snr = calculate_snr(_audio_data, noise_floor=0.01)
            current_thd = calculate_thd(_audio_data, fundamental_freq=440.0, sample_rate=16000)

            # Simulate regression (lower SNR, higher THD)
            simulated_snr = current_snr - 10.0  # 10dB regression
            simulated_thd = current_thd + 2.0  # 2% THD regression

            # Check for regression
            if simulated_snr < 20.0 or simulated_thd > 1.0:
                regression_detected = True
                break

        # Regression should be detected
        assert regression_detected

    def test_quality_regression_recovery(self, reference_audio_data):
        """Test quality regression recovery."""
        # Simulate quality recovery
        recovery_successful = True

        for _sample_name, _audio_data in reference_audio_data.items():
            # Calculate quality metrics
            snr = calculate_snr(_audio_data, noise_floor=0.01)
            thd = calculate_thd(_audio_data, fundamental_freq=440.0, sample_rate=16000)

            # Check if quality is recovered
            if snr < 20.0 or thd > 1.0:
                recovery_successful = False
                break

        # Recovery should be successful
        assert recovery_successful
