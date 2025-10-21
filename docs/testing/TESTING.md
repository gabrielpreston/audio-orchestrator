---
title: Testing Guide
description: Comprehensive guidance for testing the audio-orchestrator audio pipeline
last-updated: 2025-10-20
---

# Testing Guide

This document provides comprehensive guidance for testing the audio-orchestrator audio pipeline.

## Test Categories

### Unit Tests

- **Location**: `services/tests/unit/`
- **Purpose**: Test individual functions and classes in isolation
- **Scope**: Single functions, classes, or modules
- **Execution**: `make test-unit` or `pytest -m unit`
- **Mocking**: All external dependencies mocked

### Component Tests

- **Location**: `services/tests/component/`
- **Purpose**: Test internal service components and adapters
- **Scope**: Internal logic with mocked external dependencies
- **Execution**: `make test-component` or `pytest -m component`
- **Mocking**: External HTTP clients, Discord API, external services

### Integration Tests

- **Location**: `services/tests/integration/`
- **Purpose**: Test service-to-service HTTP boundaries
- **Scope**: Real HTTP communication via Docker Compose
- **Execution**: `make test-integration` or `pytest -m integration`
- **Mocking**: None - real services via Docker Compose
- **Network**: Tests run inside `audio-orchestrator-test` Docker network
- **Service URLs**: Use service names (e.g., `http://stt:9000`)

#### Voice Pipeline Integration Tests

- **Complete Voice Pipeline**: `test_voice_pipeline_integration.py`
  - Tests end-to-end voice feedback loop: Audio → STT → Orchestrator → LLM → TTS
  - Validates latency thresholds (< 2s total, < 300ms STT, < 1s TTS)
  - Tests correlation ID propagation through all services
  - Tests concurrent voice processing (3+ requests)
  - Tests error recovery and timeout handling

- **Audio Format Chain**: `test_audio_format_chain.py`
  - Tests audio format preservation: Discord PCM → STT (16kHz) → TTS (22.05kHz)
  - Validates quality metrics: SNR > 20dB, THD < 1%
  - Tests format conversion at each pipeline stage
  - Tests audio quality preservation through pipeline

- **Performance Integration**: `test_performance_integration.py`
  - Benchmarks voice pipeline latency and performance
  - Tests concurrent voice processing without interference
  - Tests service health under load
  - Tests memory usage under concurrent load
  - Tests latency consistency across multiple requests

- **Discord Service Integration**: `test_discord_service_integration.py`
  - Tests Discord HTTP API endpoints (`/mcp/send_message`, `/mcp/transcript`, `/mcp/tools`)
  - Tests Discord health endpoints
  - Tests Discord → STT → Orchestrator chain
  - Tests correlation ID propagation through Discord service
  - Tests error handling and timeout behavior

- **MCP Integration**: `test_mcp_integration.py`
  - Tests MCP tool discovery and execution
  - Tests MCP tool schema validation
  - Tests correlation ID propagation through MCP
  - Tests MCP error handling and recovery
  - Tests MCP concurrent request handling

- **Cross-Service Authentication**: `test_cross_service_auth.py`
  - Tests Bearer token authentication: Orchestrator → LLM, Orchestrator → TTS
  - Tests unauthorized access rejection (401 responses)
  - Tests Discord MCP endpoints (no auth required for internal services)
  - Tests invalid auth token rejection
  - Tests auth token propagation through voice pipeline

### End-to-End Tests

- **Location**: `services/tests/e2e/`
- **Purpose**: Full system validation
- **Scope**: Complete workflows from Discord to response
- **Execution**: `pytest -m e2e`
- **Note**: Manual trigger only

#### Voice Pipeline E2E Tests

- **Real Discord Voice Pipeline**: `test_e2e_voice_pipeline.py`
  - Tests complete voice pipeline with real Discord bot
  - Requires `DISCORD_TOKEN` environment variable
  - Tests Discord bot voice channel integration
  - Tests Discord bot error recovery scenarios
  - Tests concurrent voice requests with real Discord
  - Tests Discord bot health monitoring during operations
  - Tests correlation ID tracking through E2E Discord bot operations

### Quality Tests

- **Location**: `services/tests/quality/`
- **Purpose**: Audio quality and performance regression
- **Scope**: Quality metrics and benchmarks
- **Execution**: `pytest -m quality`

## Migration from Old Test Structure

### Changes from Previous Structure

**Old approach** (DEPRECATED):

- Integration tests used `test_services_context()` with subprocess
- Integration tests mocked internal classes
- Tests ran from host connecting to localhost ports

**New approach** (CURRENT):

- Integration tests use `docker_compose_test_context()` with Docker Compose
- Integration tests test real HTTP boundaries
- Tests run inside Docker network using service names
- Component tests handle internal logic with mocking

### Migration Guide

1. **Identify test type**: Does it test HTTP boundaries or internal logic?
2. **HTTP boundaries** → Move to `integration/`, use `docker_compose_test_context()`
3. **Internal logic** → Move to `component/`, use mocks
4. **Update service URLs**: `localhost:PORT` → `service_name:PORT`
5. **Update markers**: Add appropriate `@pytest.mark.component` or `@pytest.mark.integration`

## Integration Test Patterns

### HTTP Client Fixtures

Use the shared `http_client` fixture for all integration tests:

```python
@pytest.mark.integration
async def test_my_integration(http_client, services):
    """Test description."""
    for service_name, base_url in services:
        response = await http_client.get(f"{base_url}/health/live")
        assert response.status_code == 200
```

### Utility Functions

Use shared utility functions from `services.tests.fixtures.integration_fixtures`:

- `check_service_health()` - Check if service is healthy
- `check_service_ready()` - Check if service is ready
- `get_service_metrics()` - Get Prometheus metrics
- `retry_request()` - Retry requests with backoff

### Timeout Constants

Use standardized timeout constants from `Timeouts` class:

- `Timeouts.HEALTH_CHECK` - 5.0s for health endpoints
- `Timeouts.SHORT` - 1.0s for fast operations
- `Timeouts.STRESS_TEST` - 0.1s for timeout testing
- `Timeouts.STANDARD` - 30.0s for normal requests
- `Timeouts.LONG_RUNNING` - 60.0s for STT/LLM processing

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
# Quality test thresholds (used in TTS integration tests)
export MIN_SNR=20.0
export MAX_THD=1.0
export MAX_LATENCY=2.0
export MAX_MEMORY=100
```

#### Pytest Configuration

```toml
# pyproject.toml
[tool.pytest.ini_options]
# Test discovery
testpaths = ["services"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]

# Test execution options
addopts = [
    "--strict-markers",
    "--strict-config",
    "--cov=services",
    "--cov-report=term-missing",
    "--cov-report=html:htmlcov",
    "--cov-report=xml:coverage.xml",
    "--cov-fail-under=25",
    "--junitxml=junit.xml",
    "-ra",
    "--tb=short",
    "--maxfail=10",
]

# Markers for test categorization
markers = [
    "unit: Unit tests (fast, isolated, no external dependencies)",
    "component: Component tests (with mocked external dependencies)",
    "integration: Integration tests (require Docker Compose)",
    "e2e: End-to-end tests (manual trigger only)",
    "slow: Slow tests (>1 second execution time)",
    "external: Tests requiring external services or network access",
    "audio: Tests involving audio processing",
    "discord: Tests involving Discord API",
    "stt: Tests involving speech-to-text",
    "tts: Tests involving text-to-speech",
    "llm: Tests involving language model",
    "orchestrator: Tests involving orchestration logic",
]
```

### Test Data

#### Audio Samples

- **Location**: `services/tests/fixtures/audio/`
- **Format**: WAV files with 16-bit PCM, 16kHz sample rate
- **Types**: Sine waves, voice range frequencies, silence, various amplitudes
- **Generation**: `python services/tests/fixtures/audio/generate_samples_simple.py`

#### TTS Baseline Samples

- **Location**: `services/tests/fixtures/tts/samples/`
- **Format**: WAV files with 16-bit PCM, 22.05kHz sample rate
- **Types**: Short phrases, medium phrases, SSML samples, silence
- **Generation**: `python services/tests/fixtures/tts/generate_baselines.py`
- **Metadata**: JSON files with quality metrics and parameters

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
  - `docker_compose_test_context()`: Context manager for Docker Compose test services
  - `DockerComposeManager`: Manages Docker Compose test services
  - `get_service_health()`: Get service health status
  - `is_service_running()`: Check if a service is running
  - **Legacy functions** (DEPRECATED):
    - `test_services_context()`: Legacy context manager (use `docker_compose_test_context()` instead)
    - `start_test_services()`: Legacy function (use `docker_compose_test_context()` instead)
    - `wait_for_service_ready()`: Legacy function (use `docker_compose_test_context()` instead)
    - `stop_test_services()`: Legacy function (use `docker_compose_test_context()` instead)

### TTS Test Helpers

- **Location**: `services/tests/fixtures/tts/tts_test_helpers.py`
- **Functions**:
  - `generate_tts_baseline_samples()`: Generate baseline audio with metadata
  - `load_tts_baseline_metadata()`: Load baseline sample metadata
  - `validate_tts_audio_format()`: Validate TTS WAV format
  - `validate_tts_audio_quality()`: Validate TTS audio quality metrics

### Test Artifacts Management

- **Location**: `services/tests/conftest.py`
- **Functions**:
  - `test_artifacts_dir()`: Centralized test artifacts directory
  - `tts_artifacts_dir()`: TTS-specific artifacts directory
  - `temp_dir()`: Temporary directory for test files
- **Configuration**: `TEST_ARTIFACTS_DIR` environment variable
- **Cleanup**: Automatic after test session

## TTS Testing

### Overview

TTS (Text-to-Speech) testing covers audio format validation, quality metrics, performance thresholds, and integration testing with real TTS models. Tests are organized by category and use appropriate mocking strategies.

### Test Categories

- **Unit Tests**: Fast, isolated tests of TTS components
- **Component Tests**: TTS components with mocked dependencies
- **Integration Tests**: Real TTS synthesis with actual models

### Quality Thresholds

- **Audio Format**: 22.05kHz, mono, 16-bit PCM
- **Production Quality Metrics**: SNR ≥ 20dB, THD ≤ 1% (for real TTS integration tests)
- **Test Quality Metrics**: SNR ≥ 3dB, THD ≤ 50%, Voice Range ≥ 30% (for synthetic component tests)
- **Performance**: Latency ≤ 1s, Memory ≤ 50MB

### Documentation

- [TTS Testing Guide](TTS_TESTING.md) - Detailed TTS testing documentation
- [Test Artifacts Management](TEST_ARTIFACTS.md) - Test artifact storage and cleanup

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

## Current Status

**Note**: Coverage threshold temporarily lowered to 20% while resolving async test configuration issues. Will be restored to 25% once all integration tests pass consistently.
