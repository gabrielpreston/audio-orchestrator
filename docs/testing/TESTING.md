---
title: Testing Guide
description: Comprehensive guidance for testing the discord-voice-lab audio pipeline
last-updated: 2025-10-17
---

# Testing Guide

This document provides comprehensive guidance for testing the discord-voice-lab audio pipeline.

## Test Categories

### Unit Tests

- **Location**: `services/*/tests/test_*.py`
- **Purpose**: Test individual components in isolation
- **Scope**: Single functions, classes, or modules
- **Execution**: `pytest -m unit`

### Component Tests

- **Location**: `services/*/tests/test_*.py`
- **Purpose**: Test component interactions and interfaces
- **Scope**: Multiple related components
- **Execution**: `pytest -m component`

### Integration Tests

- **Location**: `services/tests/integration/test_*.py`
- **Purpose**: Test service-to-service interactions
- **Scope**: Multiple services working together
- **Execution**: `pytest -m integration`

### Quality Tests

- **Location**: `services/tests/quality/test_*.py`
- **Purpose**: Test audio quality, performance, and regression
- **Scope**: End-to-end quality validation
- **Execution**: `pytest -m quality`

## Test Organization

### Service-Specific Tests

#### STT Service Tests

- **Model Loading**: Test model initialization, configuration, and fallback behavior
- **Health Endpoints**: Test `/health/live` and `/health/ready` endpoints
- **Transcription**: Test audio transcription with various formats and parameters
- **Error Handling**: Test failure scenarios and recovery

#### TTS Service Tests

- **Model Loading**: Test voice model initialization and configuration
- **Synthesis**: Test text-to-speech synthesis with various parameters
- **Voice Selection**: Test voice selection and fallback behavior
- **Concurrency**: Test rate limiting and concurrent requests
- **Error Handling**: Test synthesis failures and degraded mode

#### Adapter Tests

- **FastWhisper Adapter**: Test STT model integration, transcription, and telemetry
- **Piper Adapter**: Test TTS model integration, synthesis, and voice management

### End-to-End Integration Tests

#### Full Pipeline E2E

- **Complete Flow**: Test Discord → STT → LLM → TTS → Discord pipeline
- **Correlation ID Propagation**: Test correlation ID flow through all services
- **Failure Scenarios**: Test circuit breakers and recovery mechanisms
- **Performance**: Test end-to-end latency and throughput

#### Service Integration

- **STT-LLM Integration**: Test transcription to LLM processing with correlation IDs
- **LLM-TTS Integration**: Test LLM response to TTS synthesis with format validation
- **Service Health**: Test service discovery and health check integration

### Audio Quality Tests

#### Audio Fidelity

- **Sample Rate Preservation**: Test Discord (48kHz) → STT (16kHz) → TTS (22.05kHz) → Discord (48kHz) conversion
- **Bit Depth Preservation**: Test 16-bit PCM maintenance throughout pipeline
- **Channel Preservation**: Test mono audio preservation and no channel mixing
- **RMS Level Consistency**: Test audio normalization and no clipping
- **Frequency Response**: Test frequency spectrum preservation using FFT

#### Audio Synchronization

- **Latency Measurements**: Test end-to-end latency < 2s, STT latency < 300ms, TTS latency reasonable
- **Timestamp Accuracy**: Test audio segment timestamps and correlation between capture/playback
- **Drift Compensation**: Test timestamp drift detection and correction

#### Noise and Distortion

- **Signal-to-Noise Ratio (SNR)**: Test SNR > 20dB, background noise handling, quantization noise limits
- **Total Harmonic Distortion (THD)**: Test THD < 1%, no clipping distortion, harmonic analysis
- **Silence Detection**: Test VAD accuracy, silence timeout, no false positives/negatives

#### Quality Regression

- **Reference Audio**: Test known-good audio samples produce consistent results
- **Performance Benchmarks**: Test processing time, memory usage, CPU usage within limits
- **Quality Thresholds**: Test quality metrics remain within bounds

## Quality Thresholds

### Audio Quality Metrics

- **SNR**: > 20dB for clean audio, > 10dB for noisy audio
- **THD**: < 1% for normal amplitude, < 2% for high amplitude
- **Frequency Response**: Voice range (300Hz-3400Hz) ratio > 0.8
- **Aliasing**: < 10% aliasing ratio

### Performance Metrics

- **End-to-End Latency**: < 2s for short queries
- **STT Latency**: < 300ms from speech onset
- **TTS Latency**: < 1s for short text
- **Wake Detection**: < 200ms
- **Memory Usage**: < 100MB per service
- **CPU Usage**: < 50% per service

### Quality Regression Thresholds

- **SNR Regression**: < 5dB decrease
- **THD Regression**: < 1% increase
- **Performance Regression**: < 1s increase
- **Memory Regression**: < 50MB increase

## Test Execution

### Running Tests

#### All Tests

```bash
pytest
```

#### By Category

```bash
# Unit tests only
pytest -m unit

# Component tests only
pytest -m component

# Integration tests only
pytest -m integration

# Quality tests only
pytest -m quality
```

#### By Service

```bash
# STT service tests
pytest services/stt/tests/

# TTS service tests
pytest services/tts/tests/

# Integration tests
pytest services/tests/integration/

# Quality tests
pytest services/tests/quality/
```

#### Specific Test Files

```bash
# Specific test file
pytest services/stt/tests/test_stt_service.py

# Specific test class
pytest services/stt/tests/test_stt_service.py::TestSTTServiceHealth

# Specific test method
pytest services/stt/tests/test_stt_service.py::TestSTTServiceHealth::test_health_live_endpoint
```

### Test Configuration

#### Environment Variables

```bash
# Test environment
export TEST_ENV=true

# Service URLs for integration tests
export STT_SERVICE_URL=http://localhost:9000
export TTS_SERVICE_URL=http://localhost:7000
export LLM_SERVICE_URL=http://localhost:8000
export ORCHESTRATOR_SERVICE_URL=http://localhost:8001

# Quality test thresholds
export MIN_SNR=20.0
export MAX_THD=1.0
export MAX_LATENCY=2.0
export MAX_MEMORY=100
```

#### Pytest Configuration

```ini
# pytest.ini
[tool:pytest]
markers =
    unit: Unit tests
    component: Component tests
    integration: Integration tests
    quality: Quality tests
    slow: Slow tests
    audio: Audio processing tests
    performance: Performance tests
    regression: Regression tests

testpaths = services
python_files = test_*.py
python_classes = Test*
python_functions = test_*

addopts = 
    --strict-markers
    --strict-config
    --verbose
    --tb=short
    --maxfail=5
```

### Test Data

#### Audio Samples

- **Location**: `services/tests/fixtures/audio/`
- **Format**: WAV files with 16-bit PCM, 16kHz sample rate
- **Types**: Sine waves, voice range frequencies, silence, various amplitudes
- **Generation**: `python services/tests/fixtures/audio/generate_samples_simple.py`

#### Reference Data

- **Location**: `services/tests/fixtures/audio/`
- **Purpose**: Known-good audio samples for regression testing
- **Format**: WAV files with documented characteristics
- **Usage**: Quality regression tests and performance benchmarks

## Test Utilities

### Audio Quality Helpers

- **Location**: `services/tests/utils/audio_quality_helpers.py`
- **Functions**:
  - `calculate_snr()`: Calculate Signal-to-Noise Ratio
  - `calculate_thd()`: Calculate Total Harmonic Distortion
  - `measure_frequency_response()`: Measure frequency response
  - `validate_audio_fidelity()`: Validate audio fidelity
  - `validate_wav_format()`: Validate WAV format
  - `generate_test_audio()`: Generate synthetic audio
  - `create_wav_file()`: Create WAV files

### Service Helpers

- **Location**: `services/tests/utils/service_helpers.py`
- **Functions**:
  - `start_test_services()`: Start test services
  - `wait_for_service_ready()`: Wait for service readiness
  - `stop_test_services()`: Stop test services
  - `get_service_health()`: Get service health status
  - `test_services_context()`: Context manager for test services

## Troubleshooting

### Common Issues

#### Test Failures

1. **Service Not Ready**: Check service health endpoints
2. **Audio Format Issues**: Verify WAV format and sample rate
3. **Quality Thresholds**: Adjust thresholds based on test environment
4. **Performance Issues**: Check system resources and service configuration

#### Debugging

1. **Enable Debug Logging**: Set `LOG_LEVEL=DEBUG`
2. **Save Debug Audio**: Enable debug WAV generation
3. **Check Service Logs**: Use `make logs` to view service logs
4. **Monitor Resources**: Check CPU, memory, and disk usage

#### Performance Issues

1. **Slow Tests**: Use `pytest -m "not slow"` to skip slow tests
2. **Memory Issues**: Check for memory leaks in long-running tests
3. **CPU Issues**: Check for CPU-intensive operations in tests
4. **Network Issues**: Check service connectivity and timeouts

### Test Maintenance

#### Adding New Tests

1. **Follow Naming Convention**: `test_*.py` for test files
2. **Use Appropriate Markers**: `@pytest.mark.unit`, `@pytest.mark.component`, etc.
3. **Add Documentation**: Document test purpose and expected behavior
4. **Update Thresholds**: Update quality thresholds if needed

#### Updating Quality Thresholds

1. **Measure Baseline**: Run tests on known-good system
2. **Adjust Thresholds**: Set thresholds based on baseline measurements
3. **Document Changes**: Update documentation with new thresholds
4. **Validate Changes**: Run tests to ensure thresholds are appropriate

#### Test Data Management

1. **Generate Samples**: Use `generate_samples_simple.py` for new audio samples
2. **Validate Samples**: Ensure samples meet quality requirements
3. **Update References**: Update reference data when needed
4. **Clean Up**: Remove outdated test data

## Continuous Integration

### GitHub Actions

- **Unit/Component Tests**: Run on every commit
- **Integration Tests**: Run on pull requests
- **Quality Tests**: Run nightly or on release branches
- **Performance Tests**: Run on performance-critical changes

### Test Execution Strategy

1. **Fast Tests First**: Run unit tests before integration tests
2. **Parallel Execution**: Run independent tests in parallel
3. **Fail Fast**: Stop on first failure for quick feedback
4. **Resource Management**: Limit concurrent test execution

### Quality Gates

1. **Test Coverage**: Maintain > 80% test coverage
2. **Quality Thresholds**: All quality tests must pass
3. **Performance Benchmarks**: Performance tests must pass
4. **Regression Tests**: No quality regressions allowed
