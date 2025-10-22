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

**Test Files**:

- `services/tts/tests/test_tts_audio_format.py`
- `services/tts/tests/test_tts_audio_quality.py`

**What They Test**:

- WAV format validation functions
- Audio quality metrics calculation
- Sample rate, bit depth, channel validation
- SNR, THD, frequency response analysis

### Component Tests (`@pytest.mark.component`)

**Purpose**: Test TTS components with mocked external dependencies
**Mocking**: MockTTSAdapter for predictable output
**Duration**: 1-5 seconds per test

**Test Files**:

- `services/tts/tests/test_tts_service_audio.py`
- `services/tts/tests/test_tts_audio_pipeline.py`

**What They Test**:

- TTS service audio validation
- Audio processing pipeline components
- Error handling and edge cases
- Voice parameter handling

### Integration Tests (`@pytest.mark.integration`)

**Purpose**: Test TTS with real services but controlled environment
**Mocking**: Real TTS models, mocked external services
**Duration**: 5-30 seconds per test

**Test Files**:

- `services/tests/integration/test_tts_synthesis_integration.py`
- `services/tests/integration/test_tts_service_integration.py`

**What They Test**:

- Real text-to-audio conversion
- Audio format validation on real output
- Audio quality metrics on real output
- Performance thresholds with real models

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

- **Sample Rate**: 22.05kHz (TTS standard)
- **Channels**: 1 (mono)
- **Bit Depth**: 16-bit PCM
- **Duration**: > 0.1s, < 30s
- **Format**: WAV with proper headers

### Audio Quality Metrics

- **Production TTS Quality**:
   -  **SNR**: ≥ 20dB (clean audio for real TTS integration tests)
   -  **THD**: ≤ 1% (low distortion for real TTS integration tests)
   -  **Voice Range**: 300Hz-3400Hz ratio ≥ 0.8
   -  **Fidelity**: Correlation ≥ 0.9, MSE ≤ 0.1

- **Component Test Quality** (for synthetic MockTTSAdapter):
   -  **SNR**: ≥ 3dB (relaxed for synthetic audio)
   -  **THD**: ≤ 50% (relaxed for synthetic audio with spectral leakage)
   -  **Voice Range**: ≥ 30% (relaxed for single-tone test signals)

### Performance Thresholds

- **TTS Latency**: ≤ 1s per request
- **Memory Usage**: ≤ 50MB per request
- **Throughput**: ≥ 0.1 requests/second
- **End-to-End**: ≤ 2s for short queries

## Running TTS Tests

### All TTS Tests

```bash
# Run all TTS tests
make test TTS_MARKER=tts

# Run specific test categories
make test-unit-container
make test-component-container
make test-integration-container
```

### Specific TTS Tests

```bash
# Unit tests only
pytest -m "unit and tts" services/tts/tests/

# Component tests only
pytest -m "component and tts" services/tts/tests/

# Integration tests only
pytest -m "integration and tts" services/tests/integration/

# Audio quality tests
pytest -m "audio and tts" services/tts/tests/
```

### Test Artifacts

```bash
# Set custom artifacts directory
export TEST_ARTIFACTS_DIR="/custom/path/to/artifacts"

# Run tests with artifacts
make test TTS_MARKER=tts

# Check artifacts
ls -la test_artifacts/tts/
```

## Test Examples

### Unit Test Example

```python
@pytest.mark.unit
@pytest.mark.tts
def test_validate_tts_wav_format():
    """Test WAV format validation for TTS audio."""
    # Generate test audio
    pcm_data = generate_test_audio(
        duration=1.0,
        sample_rate=22050,
        frequency=440.0,
        amplitude=0.5,
    )
    wav_data = create_wav_file(pcm_data, sample_rate=22050, channels=1)
    
    # Validate format
    result = validate_tts_audio_format(wav_data)
    
    assert result["is_valid"]
    assert result["tts_requirements"]["sample_rate_ok"]
    assert result["tts_requirements"]["channels_ok"]
    assert result["tts_requirements"]["bit_depth_ok"]
    assert result["is_tts_compliant"]
```

### Component Test Example

```python
@pytest.mark.component
@pytest.mark.tts
@pytest.mark.audio
def test_tts_service_returns_valid_wav(mock_tts_adapter, tts_artifacts_dir: Path):
    """Test TTS service returns valid WAV format."""
    # Mock the TTS service response
    mock_audio_data = mock_tts_adapter.synthesize("Hello world")
    
    # Validate WAV format
    result = validate_tts_audio_format(mock_audio_data)
    
    assert result["is_valid"]
    assert result["is_tts_compliant"]
    assert result["sample_rate"] == 22050
    assert result["channels"] == 1
    assert result["bit_depth"] == 16
    
    # Save to artifacts directory for debugging
    output_file = tts_artifacts_dir / "test_valid_wav.wav"
    output_file.write_bytes(mock_audio_data)
```

### Integration Test Example

```python
@pytest.mark.integration
@pytest.mark.tts
@pytest.mark.audio
@pytest.mark.slow
def test_real_tts_audio_quality_thresholds(tts_client, tts_artifacts_dir: Path):
    """Test real TTS audio quality meets thresholds."""
    # Make TTS request
    response = tts_client.post(
        "/synthesize",
        json={"text": "Quality threshold test with longer text for better analysis"}
    )
    
    # Validate audio quality
    quality_result = validate_tts_audio_quality(response.content)
    
    assert quality_result["meets_quality_thresholds"]
    assert quality_result["snr_db"] >= 20.0  # MIN_SNR threshold
    assert quality_result["thd_percent"] <= 1.0  # MAX_THD threshold
    assert quality_result["quality_checks"]["voice_range_ok"]
    
    # Save to artifacts directory for analysis
    output_file = tts_artifacts_dir / "real_tts_quality.wav"
    output_file.write_bytes(response.content)
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

- **Import Errors**
   -  Check Python path configuration
   -  Verify service dependencies are installed
   -  Use container environment for consistency

- **Audio Format Issues**
   -  Verify WAV header format
   -  Check sample rate and bit depth
   -  Validate audio duration

- **Quality Threshold Failures**
   -  Check audio generation parameters
   -  Verify quality calculation functions
   -  Review baseline sample quality

- **Performance Issues**
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

- Use descriptive test names
- Include setup and teardown
- Save artifacts for debugging
- Validate both format and quality

### Performance

- Use appropriate test markers
- Mock external dependencies in unit tests
- Use real models only in integration tests
- Clean up test artifacts

### Maintenance

- Update baseline samples when models change
- Review quality thresholds periodically
- Monitor test execution time
- Document test failures

## Related Documentation

- [Test Artifacts Management](TEST_ARTIFACTS.md)
- [Main Testing Documentation](TESTING.md)
- [Quality Thresholds](QUALITY_THRESHOLDS.md)
- [Audio Quality Helpers](../services/tests/utils/audio_quality_helpers.py)
