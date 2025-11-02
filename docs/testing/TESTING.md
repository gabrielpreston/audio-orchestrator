---
title: Testing Guide
description: Comprehensive guidance for testing the audio-orchestrator audio pipeline
last-updated: 2025-10-20
---

# Testing Guide

This document provides comprehensive guidance for testing the audio-orchestrator audio pipeline.

## Protocol-Based Testing

The audio-orchestrator project uses Protocol-based architecture throughout, replacing Abstract Base Classes (ABCs) with Protocols. This enables structural subtyping and composition over inheritance, creating more flexible and testable code.

### Current Testing Architecture

The project uses Protocol-Based Architecture with focused testing on high-value areas:

**Core Testing Categories**:

-  ✅ **Protocol Compliance Tests** - Validate interface implementation
-  ✅ **Integration Tests** - Test real system behavior
-  ✅ **Business Logic Tests** - Test critical decision-making
-  ✅ **Performance/Chaos Tests** - Test system resilience

### Protocol Testing Utilities

**Location**: `services/tests/utils/protocol_testing.py`

**Key Functions**:

-  `assert_implements_protocol(obj, protocol)` - Assert object implements protocol
-  `create_protocol_mock(protocol)` - Create mock object implementing protocol
-  `validate_protocol_compliance(obj, protocol)` - Validate protocol compliance
-  `assert_protocol_composition(obj, protocols)` - Assert object implements multiple protocols

**Example Usage**:

```python
from services.tests.utils.protocol_testing import assert_implements_protocol
from services.common.surfaces.protocols import AudioCaptureProtocol

def test_audio_adapter_compliance():
    """Test that audio adapter implements required protocols."""
    adapter = AudioAdapter()
    assert_implements_protocol(adapter, AudioCaptureProtocol)
```

### Protocol Compliance Testing

**Location**: `services/tests/unit/interfaces/test_interface_contracts.py`

**Purpose**: Validate that protocols are properly defined and implementations comply

**Key Tests**:

-  Protocol structure validation
-  Method signature verification
-  Protocol compliance checking
-  Mock object creation and validation

**Example**:

```python
@pytest.mark.parametrize(
    "protocol,protocol_name,expected_methods",
    [
        (AudioCaptureProtocol, "AudioCaptureProtocol", ["start_capture", "stop_capture"]),
        (AudioPlaybackProtocol, "AudioPlaybackProtocol", ["play_audio_chunk", "pause_playback"]),
    ],
)
class TestProtocolContracts:
    def test_protocol_compliance(self, protocol, protocol_name, expected_methods):
        """Test that protocol is properly defined."""
        assert hasattr(protocol, "__annotations__")
        assert protocol_name.endswith("Protocol")
```

### Hot-Swap Testing with Protocols

**Location**: `services/tests/integration/hot_swap/`

**Purpose**: Test runtime component replacement using protocols

**Key Features**:

-  Protocol-based component swapping
-  Runtime validation of new implementations
-  Rollback testing on failure
-  Performance impact measurement

**Example**:

```python
async def test_audio_processor_hot_swap():
    """Test hot-swapping audio processors."""
    service = AudioService()
    original_processor = service.processor

    # Create new processor implementing same protocol
    new_processor = AdvancedAudioProcessor()
    assert_implements_protocol(new_processor, AudioProcessingProtocol)

    # Hot-swap processor
    await service.hot_swap_processor(new_processor)

    # Verify new processor works
    result = await service.process_audio(test_data)
    assert result.success
```

## Modern Testing Best Practices

### Testing Focus Areas

**High-Value Testing**:

-  **Business Logic** - Core decision-making and policy engine logic
-  **Protocol Compliance** - Interface implementation validation
-  **Integration Boundaries** - Service-to-service communication
-  **System Behavior** - End-to-end functionality
-  **Performance Requirements** - Latency and throughput validation
-  **Resilience** - Failure recovery and chaos testing

### Protocol-Based Testing Guidelines

**Current Best Practices**:

-  **Use Protocol Names** - Import and use protocol names (`AudioCaptureProtocol`)
-  **Test Behavior** - Focus on what the system does, not how it does it
-  **Integration Focus** - Test real service interactions via Docker Compose
-  **Business Logic Priority** - Prioritize testing critical decision-making
-  **Performance Validation** - Test latency and throughput requirements
-  **Resilience Testing** - Test failure recovery and system stability

## Test Categories (Industry-Standard Testing Pyramid)

### Unit Tests (70% of tests)

-  **Location**: `services/tests/unit/`
-  **Purpose**: Test individual functions and classes in isolation
-  **Scope**: Single functions, classes, or modules
-  **Execution**: `make test-unit` or `pytest -m unit`
-  **Mocking**: All external dependencies mocked
-  **Examples**: Audio utilities, correlation ID generation, config parsing, business logic

### Component Tests (20% of tests)

-  **Location**: `services/tests/component/`
-  **Purpose**: Test internal service components and adapters
-  **Scope**: Internal logic with mocked external dependencies
-  **Execution**: `make test-component` or `pytest -m component`
-  **Mocking**: External HTTP clients, Discord API, external services
-  **Examples**: Interface compliance tests, service adapters, internal components

#### Audio Pipeline Component Tests

**Location**: `services/tests/component/discord/`

**Purpose**: Test critical integration points in the Discord audio pipeline without full service startup.

**Test Files**:

-  `test_audio_processor_client.py` - HTTP client for audio processor service
-  `test_audio_processor_wrapper.py` - Frame processing and segment creation
-  `test_transcription_client.py` - PCM→WAV conversion and STT client behavior
-  `test_audio_pipeline_stages.py` - Stage-to-stage data flow integration

**What They Test**:

-  **AudioProcessorClient**: HTTP communication, base64 encoding/decoding, circuit breaker behavior, error handling
-  **AudioProcessorWrapper**: Frame registration, segment creation, correlation ID generation, dependency injection
-  **TranscriptionClient**: PCM→WAV conversion (using real AudioProcessor), circuit breaker integration, correlation ID propagation, timeout handling
-  **Pipeline Stages**: Voice capture → processor, processor → segment, segment → STT, format conversion chain

**Mocking Strategy**:

-  **AudioProcessorClient**: Mock `create_resilient_client` factory with `AsyncMock` for async methods
-  **AudioProcessorWrapper**: Inject mocked `AudioProcessorClient` via constructor (dependency injection)
-  **TranscriptionClient**: Patch `ResilientHTTPClient` class constructor or inject mock after `__init__` (client creates ResilientHTTPClient directly)
-  **AudioProcessor for PCM→WAV**: Always use real AudioProcessor - format conversion is core behavior being tested

**Fixtures**: `services/tests/fixtures/discord/audio_pipeline_fixtures.py`

**Running Tests**:

```bash
# All Discord component tests
make test-component SERVICE=discord

# Specific test file
pytest services/tests/component/discord/test_audio_processor_client.py -v

# Specific test class
pytest services/tests/component/discord/test_audio_processor_client.py::TestAudioProcessorClient -v
```

#### Testing Service Tests

**Location**: `services/testing/tests/` (unit tests), `services/tests/component/testing/` (component tests)

**Purpose**: Test the Gradio testing UI service pipeline including preprocessing, transcription, orchestration, and synthesis.

**Test Files**:

-  `services/testing/tests/test_app.py` - Unit tests for core functions (`test_pipeline`, `create_gradio_interface`, health checks)
-  `services/tests/component/testing/test_testing_service.py` - Component tests for pipeline orchestration

**What They Test**:

**Unit Tests** (`test_app.py`):

-  **test_pipeline**: Audio input with preprocessing success/failure, text input bypassing STT, orchestrator audio response handling, TTS fallback, base64 decoding, empty input, error handling for each service failure
-  **create_gradio_interface**: Successful interface creation, error when Gradio unavailable
-  **Health checks**: `_check_service_health` and wrapper functions for all services (success, failure, exceptions)

**Component Tests** (`test_testing_service.py`):

-  **Complete pipeline flows**: Audio → Preprocess → STT → Orchestrator → Audio output, preprocessing failure fallback, text input bypass, orchestrator audio response file saving, TTS fallback when orchestrator has no audio, voice preset selection
-  **Error handling**: STT failure, orchestrator failure, TTS fallback failure, base64 decoding errors
-  **Data transformation**: Base64 audio decoding correctness, file I/O operations, file path validation, temporary file cleanup

**Mocking Strategy**:

-  **Unit tests**: Mock `httpx.AsyncClient` at module level via `patch("services.testing.app.client")`. Use `AsyncMock` for async methods like `post()`, `get()`, and `aclose()`.
-  **Component tests**: Use `AsyncMock` for `httpx.AsyncClient`, configure response side_effects for multi-step flows. Mock `httpx.Response` objects with `status_code`, `json()`, `content`, and `raise_for_status()`.

**Mock Response Structure**:

-  **Preprocessor**: `Response(content=bytes, status_code=200)`
-  **STT**: `Response.json() = {"text": "...", ...}, status_code=200`
-  **Orchestrator**: `Response.json() = {"response_text": "...", "audio_data": "...", "success": True}, status_code=200`
-  **TTS**: `Response.json() = {"audio": "base64..."}, status_code=200`

**Fixtures**: `services/tests/fixtures/testing/testing_fixtures.py`

-  Reuses: `sample_audio_bytes` (from `integration_fixtures.py`), `realistic_voice_audio` (from `voice_pipeline_fixtures.py`), `temp_dir` (from global `conftest.py`)
-  Testing-specific: `sample_wav_file`, `mock_orchestrator_response`, `mock_tts_response`, `mock_audio_preprocessor_response`

**Running Tests**:

```bash
# Unit tests
make test-unit SERVICE=testing
pytest services/testing/tests/ -v

# Component tests
make test-component SERVICE=testing
pytest services/tests/component/testing/ -v

# Specific test class
pytest services/tests/component/testing/test_testing_service.py::TestTestingServicePipeline -v
```

### Integration Tests (8% of tests)

-  **Location**: `services/tests/integration/`
-  **Purpose**: Test service-to-service HTTP boundaries
-  **Scope**: Real HTTP communication via Docker Compose
-  **Execution**: `make test-integration` or `pytest -m integration`
-  **Mocking**: None - real services via Docker Compose
-  **Network**: Tests run inside `audio-orchestrator-test` Docker network
-  **Service URLs**: Use service names (e.g., `http://stt:9000`)
-  **Subcategories**: `contracts/`, `hot_swap/`, `security/`, `performance/`

#### Voice Pipeline Integration Tests

-  **Complete Voice Pipeline**: `test_voice_pipeline_integration.py`
  -  Tests end-to-end voice feedback loop: Audio → STT → Orchestrator → LLM → TTS
  -  Validates latency thresholds (< 2s total, < 300ms STT, < 1s TTS)
  -  Tests correlation ID propagation through all services
  -  Tests concurrent voice processing (3+ requests)
  -  Tests error recovery and timeout handling

-  **Audio Format Chain**: `test_audio_format_chain.py`
  -  Tests audio format preservation: Discord PCM → STT (16kHz) → TTS (22.05kHz)
  -  Validates quality metrics: SNR > 20dB, THD < 1%
  -  Tests format conversion at each pipeline stage
  -  Tests audio quality preservation through pipeline

-  **Performance Integration**: `test_performance_integration.py`
  -  Benchmarks voice pipeline latency and performance
  -  Tests concurrent voice processing without interference
  -  Tests service health under load
  -  Tests memory usage under concurrent load
  -  Tests latency consistency across multiple requests

-  **Discord Service Integration**: `test_discord_service_integration.py`
  -  Tests Discord HTTP API endpoints (`/api/v1/messages`, `/api/v1/transcripts`, `/api/v1/capabilities`)
  -  Tests Discord health endpoints
  -  Tests Discord → STT → Orchestrator chain
  -  Tests correlation ID propagation through Discord service
  -  Tests error handling and timeout behavior

-  **Cross-Service Authentication**: `test_cross_service_auth.py`
  -  Tests Bearer token authentication: Orchestrator → LLM, Orchestrator → TTS
  -  Tests unauthorized access rejection (401 responses)
  -  Tests Discord API endpoints (no auth required for internal services)
  -  Tests invalid auth token rejection
  -  Tests auth token propagation through voice pipeline

### Interface-First Tests (Dual Marking)

-  **Location**: Distributed across `component/` and `integration/` directories
-  **Purpose**: Validate service boundaries and hot-swappability
-  **Scope**: Interface compliance and contract validation
-  **Execution**: `make test-interface`, `make test-contract`, `make test-hot-swap`
-  **Markers**: `@pytest.mark.interface`, `@pytest.mark.contract`, `@pytest.mark.hot_swap`
-  **Dual Marking**: Tests marked with both industry-standard and interface-first markers

#### Interface Compliance Tests

-  **AudioSource Interface**: Test audio input implementations
-  **AudioSink Interface**: Test audio output implementations
-  **ControlChannel Interface**: Test control channel implementations
-  **SurfaceLifecycle Interface**: Test surface lifecycle management
-  **Health Contracts**: Test standardized health check compliance

#### Contract Validation Tests

-  **Service Contracts**: Validate API endpoints, performance, and security
-  **Performance Contracts**: Test latency, throughput, and resource usage
-  **Security Contracts**: Test authentication, authorization, and data handling
-  **Hot-Swap Validation**: Test service and surface interchangeability

## Validation Framework

The `services.common.validation` module provides validation utilities for testing:

### Audio Validation

-  `validate_audio_data()`: Validates audio quality and format
  -  Returns quality score, issues list, and comprehensive analysis
  -  Detects silence, clipping, NaN/Inf values, and empty data
  -  Supports comprehensive analysis with frequency and dynamic range data

### Interface Validation

-  `validate_interface_contract()`: Validates interface definitions
  -  Checks abstract method compliance
  -  Validates interface structure and inheritance
  -  Returns compliance status and missing methods

### Service Contract Validation

-  `validate_service_contract()`: Validates service contract definitions
  -  Checks required fields (service_name, base_url, endpoints)
  -  Validates endpoint structure and health check presence
  -  Returns validation status, issues, and warnings
-  `check_contract_compliance()`: Calculates compliance scores
  -  Evaluates performance and security requirements
  -  Returns compliance score and missing requirements

### Hot-Swap Validation

-  `validate_service_contract_compliance()`: Validates service implementations comply with contracts
-  `validate_service_interchangeability()`: Validates services can be interchanged
-  `validate_surface_interface_compliance()`: Validates surface implements interface
-  `validate_surface_interchangeability()`: Validates surfaces can be interchanged
-  Various compatibility validation functions for performance, security, and data formats

### Usage Examples

```python
from services.common.validation import validate_audio_data, validate_service_contract

# Audio validation
audio_data = np.random.randn(1000)
result = validate_audio_data(audio_data, comprehensive=True)
assert result['valid'] is True
assert result['quality_score'] > 0.8

# Service contract validation
result = validate_service_contract(STT_CONTRACT)
assert result['valid'] is True
assert len(result['issues']) == 0
```

### End-to-End Tests (2% of tests)

-  **Location**: `services/tests/e2e/`
-  **Purpose**: Full system validation
-  **Scope**: Complete workflows from Discord to response
-  **Execution**: `make test-e2e` or `pytest -m e2e`
-  **Note**: Manual trigger only
-  **Subcategories**: `discord/`, `voice_pipeline/`

#### Voice Pipeline E2E Tests

-  **Real Discord Voice Pipeline**: `test_e2e_voice_pipeline.py`
  -  Tests complete voice pipeline with real Discord bot
  -  Requires `DISCORD_TOKEN` environment variable
  -  Tests Discord bot voice channel integration
  -  Tests Discord bot error recovery scenarios
  -  Tests concurrent voice requests with real Discord
  -  Tests Discord bot health monitoring during operations
  -  Tests correlation ID tracking through E2E Discord bot operations

### Quality Tests

-  **Location**: `services/tests/quality/`
-  **Purpose**: Audio quality and performance regression
-  **Scope**: Quality metrics and benchmarks
-  **Execution**: `pytest -m quality`

## Migration from Old Test Structure

### Changes from Previous Structure

**Old approach** (DEPRECATED):

-  Integration tests used legacy subprocess-based test helpers
-  Integration tests mocked internal classes
-  Tests ran from host connecting to localhost ports

**New approach** (CURRENT):

-  Integration tests use `docker_compose_test_context()` with Docker Compose
-  Integration tests test real HTTP boundaries
-  Tests run inside Docker network using service names
-  Component tests handle internal logic with mocking

### Migration Guide

-  **Identify test type**: Does it test HTTP boundaries or internal logic?
-  **HTTP boundaries** → Move to `integration/`, use `docker_compose_test_context()`
-  **Internal logic** → Move to `component/`, use mocks
-  **Update service URLs**: `localhost:PORT` → `service_name:PORT`
-  **Update markers**: Add appropriate `@pytest.mark.component` or `@pytest.mark.integration`

## Integration Test Patterns

### Environment-Based Service URLs

All integration tests use the standardized `{SERVICE}_BASE_URL` environment variable pattern with agnostic service names. Service URLs are loaded from environment variables with sensible defaults:

```python
from services.tests.integration.conftest import get_service_url

# Get service URL using agnostic service name
stt_url = get_service_url("STT")  # Loads STT_BASE_URL or defaults to http://stt:9000
llm_url = get_service_url("LLM")  # Loads LLM_BASE_URL or defaults to http://flan:8100
tts_url = get_service_url("TTS")  # Loads TTS_BASE_URL or defaults to http://bark:7100
```

**Standardized Environment Variables** (agnostic service names):

-  `AUDIO_BASE_URL` → defaults to `http://audio:9100`
-  `STT_BASE_URL` → defaults to `http://stt:9000`
-  `ORCHESTRATOR_BASE_URL` → defaults to `http://orchestrator:8200`
-  `LLM_BASE_URL` → defaults to `http://flan:8100` (service: LLM, implementation: FLAN-T5)
-  `TTS_BASE_URL` → defaults to `http://bark:7100` (service: TTS, implementation: Bark)
-  `GUARDRAILS_BASE_URL` → defaults to `http://guardrails:9300`
-  `DISCORD_BASE_URL` → defaults to `http://discord:8001`
-  `TESTING_BASE_URL` → defaults to `http://testing:8080`

**Overriding URLs for Different Test Environments**:

```bash
# Override URLs for local testing
export LLM_BASE_URL=http://localhost:8110
export TTS_BASE_URL=http://localhost:7120
pytest services/tests/integration/
```

### HTTP Client Fixtures

Use the shared `http_client` fixture for all integration tests:

```python
@pytest.mark.integration
async def test_my_integration(http_client, service_url):
    """Test description."""
    stt_url = service_url("STT")
    response = await http_client.get(f"{stt_url}/health/live")
    assert response.status_code == 200
```

### Utility Functions

Use shared utility functions from `services.tests.fixtures.integration_fixtures`:

-  `check_service_health()` - Check if service is healthy
-  `check_service_ready()` - Check if service is ready
-  `get_service_metrics()` - Get Prometheus metrics
-  `retry_request()` - Retry requests with backoff

All utility functions accept base URLs that should be obtained via `get_service_url()` helper.

### Timeout Constants

Use standardized timeout constants from `Timeouts` class:

-  `Timeouts.HEALTH_CHECK` - 5.0s for health endpoints
-  `Timeouts.SHORT` - 1.0s for fast operations
-  `Timeouts.STRESS_TEST` - 0.1s for timeout testing
-  `Timeouts.STANDARD` - 30.0s for normal requests
-  `Timeouts.LONG_RUNNING` - 60.0s for STT/LLM processing

## Test Organization

### Service-Specific Tests

#### STT Service Tests

-  **Model Loading**: Test model initialization, configuration, and fallback behavior
-  **Health Endpoints**: Test `/health/live` and `/health/ready` endpoints
-  **Transcription**: Test audio transcription with various formats and parameters
-  **Error Handling**: Test failure scenarios and recovery

#### TTS Service Tests

-  **Model Loading**: Test voice model initialization and configuration
-  **Synthesis**: Test text-to-speech synthesis with various parameters
-  **Voice Selection**: Test voice selection and fallback behavior
-  **Concurrency**: Test rate limiting and concurrent requests
-  **Error Handling**: Test synthesis failures and degraded mode

#### Adapter Tests

-  **FastWhisper Adapter**: Test STT model integration, transcription, and telemetry
-  **Piper Adapter**: Test TTS model integration, synthesis, and voice management

### End-to-End Integration Tests

#### Full Pipeline E2E

-  **Complete Flow**: Test Discord → STT → LLM → TTS → Discord pipeline
-  **Correlation ID Propagation**: Test correlation ID flow through all services
-  **Failure Scenarios**: Test circuit breakers and recovery mechanisms
-  **Performance**: Test end-to-end latency and throughput

#### Service Integration

-  **STT-LLM Integration**: Test transcription to LLM processing with correlation IDs
-  **LLM-TTS Integration**: Test LLM response to TTS synthesis with format validation
-  **Service Health**: Test service discovery and health check integration

### Audio Quality Tests

#### Audio Fidelity

-  **Sample Rate Preservation**: Test Discord (48kHz) → STT (16kHz) → TTS (22.05kHz) → Discord (48kHz) conversion
-  **Bit Depth Preservation**: Test 16-bit PCM maintenance throughout pipeline
-  **Channel Preservation**: Test mono audio preservation and no channel mixing
-  **RMS Level Consistency**: Test audio normalization and no clipping
-  **Frequency Response**: Test frequency spectrum preservation using FFT

#### Audio Synchronization

-  **Latency Measurements**: Test end-to-end latency < 2s, STT latency < 300ms, TTS latency reasonable
-  **Timestamp Accuracy**: Test audio segment timestamps and correlation between capture/playback
-  **Drift Compensation**: Test timestamp drift detection and correction

#### Noise and Distortion

-  **Signal-to-Noise Ratio (SNR)**: Test SNR > 20dB, background noise handling, quantization noise limits
-  **Total Harmonic Distortion (THD)**: Test THD < 1%, no clipping distortion, harmonic analysis
-  **Silence Detection**: Test VAD accuracy, silence timeout, no false positives/negatives

#### Quality Regression

-  **Reference Audio**: Test known-good audio samples produce consistent results
-  **Performance Benchmarks**: Test processing time, memory usage, CPU usage within limits
-  **Quality Thresholds**: Test quality metrics remain within bounds

## Quality Thresholds

### Audio Quality Metrics

-  **SNR**: > 20dB for clean audio, > 10dB for noisy audio
-  **THD**: < 1% for normal amplitude, < 2% for high amplitude
-  **Frequency Response**: Voice range (300Hz-3400Hz) ratio > 0.8
-  **Aliasing**: < 10% aliasing ratio

### Performance Metrics

-  **End-to-End Latency**: < 2s for short queries
-  **STT Latency**: < 300ms from speech onset
-  **TTS Latency**: < 1s for short text
-  **Wake Detection**: < 200ms
-  **Memory Usage**: < 100MB per service
-  **CPU Usage**: < 50% per service

### Quality Regression Thresholds

-  **SNR Regression**: < 5dB decrease
-  **THD Regression**: < 1% increase
-  **Performance Regression**: < 1s increase
-  **Memory Regression**: < 50MB increase

## Test Execution

### Running Tests

#### All Tests

```bash
pytest
```

#### By Category (Industry-Standard)

```bash
# Unit tests only (70% of tests)
pytest -m unit

# Component tests only (20% of tests)
pytest -m component

# Integration tests only (8% of tests)
pytest -m integration

# End-to-end tests only (2% of tests)
pytest -m e2e

# All tests following testing pyramid
make test
```

#### By Interface-First Category

```bash
# Interface compliance tests
pytest -m interface

# Contract validation tests
pytest -m contract

# Hot-swap validation tests
pytest -m hot_swap

# All interface-first tests
pytest -m "interface or contract"

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
    # Industry-standard testing pyramid markers (primary)
    "unit: Unit tests (fast, isolated, no external dependencies) - 70% of tests",
    "component: Component tests (with mocked external dependencies) - 20% of tests",
    "integration: Integration tests (require Docker Compose) - 8% of tests",
    "e2e: End-to-end tests (manual trigger only) - 2% of tests",

    # Interface-first testing markers (secondary)
    "interface: Interface compliance tests (validate service boundaries)",
    "contract: Contract validation tests (validate API contracts)",
    "hot_swap: Hot-swap validation tests (validate interchangeability)",
    "security: Security validation tests (validate security contracts)",
    "performance: Performance benchmark tests",

    # Legacy markers (being phased out)
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

-  **Location**: `services/tests/fixtures/audio/`
-  **Format**: WAV files with 16-bit PCM, 16kHz sample rate
-  **Types**: Sine waves, voice range frequencies, silence, various amplitudes
-  **Generation**: `python services/tests/fixtures/audio/generate_samples_simple.py`

#### TTS Baseline Samples

-  **Location**: `services/tests/fixtures/tts/samples/`
-  **Format**: WAV files with 16-bit PCM, 22.05kHz sample rate
-  **Types**: Short phrases, medium phrases, SSML samples, silence
-  **Generation**: `python services/tests/fixtures/tts/generate_baselines.py`
-  **Metadata**: JSON files with quality metrics and parameters

#### Reference Data

-  **Location**: `services/tests/fixtures/audio/`
-  **Purpose**: Known-good audio samples for regression testing
-  **Format**: WAV files with documented characteristics
-  **Usage**: Quality regression tests and performance benchmarks

## Test Utilities

### Audio Quality Helpers

-  **Location**: `services/tests/utils/audio_quality_helpers.py`
-  **Functions**:
   -  `calculate_snr()`: Calculate Signal-to-Noise Ratio
   -  `calculate_thd()`: Calculate Total Harmonic Distortion
   -  `measure_frequency_response()`: Measure frequency response
   -  `validate_audio_fidelity()`: Validate audio fidelity
   -  `validate_wav_format()`: Validate WAV format
   -  `generate_test_audio()`: Generate synthetic audio
   -  `create_wav_file()`: Create WAV files

### Service Helpers

-  **Location**: `services/tests/utils/service_helpers.py`
-  **Functions**:
   -  `docker_compose_test_context()`: Context manager for Docker Compose test services
   -  `DockerComposeManager`: Manages Docker Compose test services
   -  `get_service_health()`: Get service health status
   -  `is_service_running()`: Check if a service is running

### TTS Test Helpers

-  **Location**: `services/tests/fixtures/tts/tts_test_helpers.py`
-  **Functions**:
   -  `generate_tts_baseline_samples()`: Generate baseline audio with metadata
   -  `load_tts_baseline_metadata()`: Load baseline sample metadata
   -  `validate_tts_audio_format()`: Validate TTS WAV format
   -  `validate_tts_audio_quality()`: Validate TTS audio quality metrics

### Test Artifacts Management

-  **Location**: `services/tests/conftest.py`
-  **Functions**:
   -  `test_artifacts_dir()`: Centralized test artifacts directory
   -  `tts_artifacts_dir()`: TTS-specific artifacts directory
   -  `temp_dir()`: Temporary directory for test files
-  **Configuration**: `TEST_ARTIFACTS_DIR` environment variable
-  **Cleanup**: Automatic after test session

## TTS Testing

### Overview

TTS (Text-to-Speech) testing covers audio format validation, quality metrics, performance thresholds, and integration testing with real TTS models. Tests are organized by category and use appropriate mocking strategies.

### Test Categories

-  **Unit Tests**: Fast, isolated tests of TTS components
-  **Component Tests**: TTS components with mocked dependencies
-  **Integration Tests**: Real TTS synthesis with actual models

### Quality Thresholds

-  **Audio Format**: 22.05kHz, mono, 16-bit PCM
-  **Production Quality Metrics**: SNR ≥ 20dB, THD ≤ 1% (for real TTS integration tests)
-  **Test Quality Metrics**: SNR ≥ 3dB, THD ≤ 50%, Voice Range ≥ 30% (for synthetic component tests)
-  **Performance**: Latency ≤ 1s, Memory ≤ 50MB

### Documentation

-  [TTS Testing Guide](TTS_TESTING.md) - Detailed TTS testing documentation
-  [Test Artifacts Management](TEST_ARTIFACTS.md) - Test artifact storage and cleanup

## Troubleshooting

### Common Issues

#### Test Failures

-  **Service Not Ready**: Check service health endpoints
-  **Audio Format Issues**: Verify WAV format and sample rate
-  **Quality Thresholds**: Adjust thresholds based on test environment
-  **Performance Issues**: Check system resources and service configuration

#### Debugging

-  **Enable Debug Logging**: Set `LOG_LEVEL=DEBUG`
-  **Save Debug Audio**: Enable debug WAV generation
-  **Check Service Logs**: Use `make logs` to view service logs
-  **Monitor Resources**: Check CPU, memory, and disk usage

#### Performance Issues

-  **Slow Tests**: Use `pytest -m "not slow"` to skip slow tests
-  **Memory Issues**: Check for memory leaks in long-running tests
-  **CPU Issues**: Check for CPU-intensive operations in tests
-  **Network Issues**: Check service connectivity and timeouts

### Test Maintenance

#### Adding New Tests

-  **Follow Naming Convention**: `test_*.py` for test files
-  **Use Appropriate Markers**: `@pytest.mark.unit`, `@pytest.mark.component`, etc.
-  **Add Documentation**: Document test purpose and expected behavior
-  **Update Thresholds**: Update quality thresholds if needed

#### Updating Quality Thresholds

-  **Measure Baseline**: Run tests on known-good system
-  **Adjust Thresholds**: Set thresholds based on baseline measurements
-  **Document Changes**: Update documentation with new thresholds
-  **Validate Changes**: Run tests to ensure thresholds are appropriate

#### Test Data Management

-  **Generate Samples**: Use `generate_samples_simple.py` for new audio samples
-  **Validate Samples**: Ensure samples meet quality requirements
-  **Update References**: Update reference data when needed
-  **Clean Up**: Remove outdated test data

## Continuous Integration

### GitHub Actions Integration

The project implements comprehensive CI/CD with enhanced job reporting:

#### Test Results Reporting

-  **dorny/test-reporter@v1**: Aggregates test results from unit, component, and integration tests
-  **Artifact Uploads**: 7-day retention for test results and coverage reports
-  **Coverage Summaries**: Automatic generation of coverage metrics in job summaries
-  **Docker Awareness**: Handles artifacts generated inside Docker containers

#### Custom Metrics Reporting

-  **Audio Pipeline Metrics**: Performance targets and service architecture overview
-  **Build Metrics**: Docker build configuration and performance notes
-  **Security Metrics**: Dependency and container security scan results
-  **Workflow Status**: Enhanced status reporting with build information

#### Security Scanning Integration

-  **Trivy Container Scanning**: Filesystem vulnerability scanning with SARIF upload
-  **GitHub Security Integration**: Results uploaded to GitHub Security tab
-  **Dependency Scanning**: Safety and Bandit integration via `make security`

### GitHub Actions

-  **Unit/Component Tests**: Run on every commit
-  **Integration Tests**: Run on pull requests
-  **Quality Tests**: Run nightly or on release branches
-  **Performance Tests**: Run on performance-critical changes

### Test Execution Strategy

-  **Fast Tests First**: Run unit tests before integration tests
-  **Parallel Execution**: Run independent tests in parallel
-  **Fail Fast**: Stop on first failure for quick feedback
-  **Resource Management**: Limit concurrent test execution

### Quality Gates

-  **Test Coverage**: Maintain > 80% test coverage
-  **Quality Thresholds**: All quality tests must pass
-  **Performance Benchmarks**: Performance tests must pass
-  **Regression Tests**: No quality regressions allowed

## Current Status

**Note**: Coverage threshold temporarily lowered to 20% while resolving async test configuration issues. Will be restored to 25% once all integration tests pass consistently.
