---
title: TTS Testing Guide
description: TTS (Text-to-Speech) testing strategy and implementation for the audio-orchestrator project
last-updated: 2025-10-17
---

# TTS Testing Guide

This document describes the TTS (Text-to-Speech) testing strategy and implementation for the audio-orchestrator project.

## Overview

TTS testing covers audio format validation, quality metrics, performance thresholds, and integration testing with real TTS models. Tests are organized by category (unit, component, integration) and use appropriate mocking strategies.

## Test Categories

### Unit Tests (`@pytest.mark.unit`)

**Purpose**: Fast, isolated tests of individual TTS components
**Mocking**: No external dependencies
**Duration**: < 1 second per test

**Note**: Direct TTS unit tests are not currently implemented. TTS functionality is tested via:

-  Integration tests in `services/tests/integration/test_orchestrator_text_pipeline.py` (TTS synthesis)
-  Service-level integration tests in `services/tests/integration/test_bark_service.py` (Bark TTS service)
-  Audio quality helpers in `services/tests/utils/audio_quality_helpers.py`

**What They Would Test** (if implemented):

-  WAV format validation functions
-  Audio quality metrics calculation
-  Sample rate, bit depth, channel validation
-  SNR, THD, frequency response analysis

### Component Tests (`@pytest.mark.component`)

**Purpose**: Test TTS components with mocked external dependencies
**Mocking**: MockTTSAdapter for predictable output
**Duration**: 1-5 seconds per test

**Note**: Direct TTS component tests are not currently implemented. TTS functionality is tested via:

-  Integration tests using real Bark TTS service in `services/tests/integration/test_bark_service.py`
-  Mock TTS adapter available in `services/tests/mocks/tts_adapter.py` for use in other tests

**What They Would Test** (if implemented):

-  TTS service audio validation
-  Audio processing pipeline components
-  Error handling and edge cases
-  Voice parameter handling

### Integration Tests (`@pytest.mark.integration`)

**Purpose**: Test TTS with real services but controlled environment
**Mocking**: Real TTS models (Bark), no mocked services
**Duration**: 5-30 seconds per test

**Test Files**:

-  `services/tests/integration/test_bark_service.py` - Direct Bark TTS service tests
-  `services/tests/integration/test_orchestrator_text_pipeline.py` - TTS synthesis via orchestrator

**What They Test**:

-  Real text-to-audio conversion using Bark TTS service
-  Audio format validation on real output (base64-encoded WAV)
-  Audio quality metrics on real output (via quality helpers)
-  Performance thresholds with real models
-  Service health and readiness endpoints

## Test Infrastructure

### Test Artifacts

**Temporary Files**: `test_artifacts/tts/` (auto-cleanup)
**Baseline Samples**: `services/tests/fixtures/tts/samples/` (version controlled)
**Configuration**: `TEST_ARTIFACTS_DIR` environment variable

### Test Fixtures

```python
# TTS-specific fixtures
@pytest.fixture
def tts_baseline_samples() -> dict[str, Path]:
    """Load baseline TTS samples from fixtures."""

@pytest.fixture
def tts_artifacts_dir(test_artifacts_dir: Path) -> Path:
    """Get TTS test artifacts directory."""

@pytest.fixture
def mock_tts_audio(temp_dir: Path) -> Path:
    """Generate mock TTS audio in temp directory."""
```

### Mock TTS Adapter

```python
class MockTTSAdapter:
    """Mock TTS adapter that generates synthetic audio for testing."""

    async def synthesize(self, text: str, voice: Optional[str] = None, **kwargs) -> bytes:
        """Generate synthetic audio based on text."""
        # Calculate duration based on text length (0.1s per character)
        duration = max(0.1, len(text) * 0.1)

        # Generate synthetic audio
        pcm_data = generate_test_audio(
            duration=duration,
            sample_rate=self.sample_rate,
            frequency=frequency,
            amplitude=amplitude,
            noise_level=noise_level,
        )

        # Create WAV file
        wav_data = create_wav_file(pcm_data, self.sample_rate, channels=1)
        return wav_data
```

## Quality Thresholds

### Audio Format Requirements

-  **Sample Rate**: 22.05kHz (TTS standard)
-  **Channels**: 1 (mono)
-  **Bit Depth**: 16-bit PCM
-  **Duration**: > 0.1s, < 30s
-  **Format**: WAV with proper headers

### Audio Quality Metrics

-  **Production TTS Quality**:
   -  **SNR**: ≥ 20dB (clean audio for real TTS integration tests)
   -  **THD**: ≤ 1% (low distortion for real TTS integration tests)
   -  **Voice Range**: 300Hz-3400Hz ratio ≥ 0.8
   -  **Fidelity**: Correlation ≥ 0.9, MSE ≤ 0.1

-  **Component Test Quality** (for synthetic MockTTSAdapter):
   -  **SNR**: ≥ 3dB (relaxed for synthetic audio)
   -  **THD**: ≤ 50% (relaxed for synthetic audio with spectral leakage)
   -  **Voice Range**: ≥ 30% (relaxed for single-tone test signals)

### Performance Thresholds

-  **TTS Latency**: ≤ 1s per request
-  **Memory Usage**: ≤ 50MB per request
-  **Throughput**: ≥ 0.1 requests/second
-  **End-to-End**: ≤ 2s for short queries

## Running TTS Tests

### All TTS Tests

```bash
# Run all TTS integration tests
make test-integration

# Run Bark service tests specifically
pytest services/tests/integration/test_bark_service.py

# Run orchestrator tests that exercise TTS
pytest services/tests/integration/test_orchestrator_text_pipeline.py -k tts
```

### Specific TTS Tests

```bash
# Bark service integration tests
pytest services/tests/integration/test_bark_service.py -v

# Orchestrator TTS integration (indirect TTS testing)
pytest services/tests/integration/test_orchestrator_text_pipeline.py -v

# All integration tests (includes TTS)
pytest -m integration services/tests/integration/
```

### Test Artifacts

```bash
# Set custom artifacts directory
export TEST_ARTIFACTS_DIR="/custom/path/to/artifacts"

# Run TTS integration tests
pytest services/tests/integration/test_bark_service.py -v

# Check artifacts (if test artifacts directory exists)
ls -la test_artifacts/tts/ 2>/dev/null || echo "No TTS artifacts directory"
```

## Test Examples

### Integration Test Example (Bark Service)

```python
@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_bark_synthesize():
    """Test Bark TTS synthesis endpoint."""
    from services.tests.fixtures.integration_fixtures import Timeouts
    from services.tests.integration.conftest import get_service_url
    from services.tests.utils.service_helpers import docker_compose_test_context
    import httpx

    tts_url = get_service_url("TTS")
    required_services = ["bark"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.LONG_RUNNING) as client,
    ):
        response = await client.post(
            f"{tts_url}/synthesize",
            json={"text": "Hello, this is a test.", "voice": "v2/en_speaker_1", "speed": 1.0},
            timeout=Timeouts.LONG_RUNNING,
        )

        assert response.status_code == 200
        data = response.json()
        assert "audio" in data  # Base64-encoded audio
        assert "engine" in data
        assert "processing_time_ms" in data
        assert "voice_used" in data
```

### Integration Test Example (Orchestrator TTS)

```python
@pytest.mark.integration
@pytest.mark.timeout(120)
async def test_orchestrator_tts_integration():
    """Test orchestrator TTS synthesis via transcript processing."""
    from services.tests.fixtures.integration_fixtures import Timeouts
    from services.tests.integration.conftest import get_service_url
    from services.tests.utils.service_helpers import docker_compose_test_context
    import httpx

    orchestrator_url = get_service_url("ORCHESTRATOR")
    required_services = ["orchestrator", "flan", "guardrails", "bark"]

    async with (
        docker_compose_test_context(required_services, timeout=120.0),
        httpx.AsyncClient(timeout=Timeouts.STANDARD) as client,
    ):
        response = await client.post(
            f"{orchestrator_url}/api/v1/transcripts",
            json={
                "transcript": "Hello, how are you?",
                "user_id": "test_user",
                "channel_id": "test_channel",
            },
            timeout=Timeouts.STANDARD,
        )

        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "response_text" in data
        # TTS audio may be included if TTS service is available
        if data.get("audio_data"):
            assert data.get("audio_format") == "wav"
```

## Baseline Sample Generation

### Generate Baseline Samples

```bash
# Generate baseline TTS samples
python services/tests/fixtures/tts/generate_baselines.py
```

### Baseline Sample Structure

```text
services/tests/fixtures/tts/samples/
├── short_phrase.wav
├── short_phrase.json          # Metadata
├── medium_phrase.wav
├── medium_phrase.json
├── ssml_sample.wav
├── ssml_sample.json
└── ...
```

### Baseline Metadata

```json
{
  "text": "Hello world, this is a test.",
  "sample_rate": 22050,
  "duration": 2.5,
  "voice": "default",
  "quality_metrics": {
    "snr_db": 25.3,
    "thd_percent": 0.8,
    "voice_range_ratio": 0.85
  },
  "generated_at": "2025-01-15T10:30:00Z"
}
```

## Troubleshooting

### Common Issues

-  **Import Errors**
   -  Check Python path configuration
   -  Verify service dependencies are installed
   -  Use container environment for consistency

-  **Audio Format Issues**
   -  Verify WAV header format
   -  Check sample rate and bit depth
   -  Validate audio duration

-  **Quality Threshold Failures**
   -  Check audio generation parameters
   -  Verify quality calculation functions
   -  Review baseline sample quality

-  **Performance Issues**
   -  Check test execution time
   -  Verify memory usage
   -  Review test data size

### Debug Commands

```bash
# Check test artifacts
ls -la test_artifacts/tts/

# Validate audio files
file test_artifacts/tts/*.wav

# Check audio properties
ffprobe test_artifacts/tts/*.wav

# Monitor test execution
pytest -v -s services/tts/tests/
```

## Best Practices

### Test Design

-  Use descriptive test names
-  Include setup and teardown
-  Save artifacts for debugging
-  Validate both format and quality

### Performance

-  Use appropriate test markers
-  Mock external dependencies in unit tests
-  Use real models only in integration tests
-  Clean up test artifacts

### Maintenance

-  Update baseline samples when models change
-  Review quality thresholds periodically
-  Monitor test execution time
-  Document test failures

## Related Documentation

-  [Test Artifacts Management](TEST_ARTIFACTS.md)
-  [Main Testing Documentation](TESTING.md)
-  [Quality Thresholds](QUALITY_THRESHOLDS.md)
-  [Audio Quality Helpers](../services/tests/utils/audio_quality_helpers.py)
