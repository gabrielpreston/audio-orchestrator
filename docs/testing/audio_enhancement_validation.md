---
title: Audio Enhancement Validation Testing
description: Testing strategy for audio enhancement validation in the audio-orchestrator STT service
last-updated: 2025-10-22
---

# Audio Enhancement Validation Testing

## Overview

This document describes the testing strategy for audio enhancement validation in the audio-orchestrator STT service. The enhancement pipeline uses MetricGAN+ to improve audio quality before transcription.

## Testing Strategy

### Test Categories

1.  **Integration Tests**: Test enhancement with real STT service
2.  **Component Tests**: Test enhancement performance and error handling
3.  **Quality Tests**: Test audio quality improvements
4.  **Edge Case Tests**: Test various audio formats and error conditions

### Test Structure

```text
services/tests/
├── integration/
│   └── test_stt_enhancement_integration.py
├── component/
│   ├── test_enhancement_performance.py
│   ├── test_enhancement_errors.py
│   ├── test_enhancement_config.py
│   └── test_enhancement_audio_formats.py
├── quality/
│   ├── test_audio_quality.py
│   └── wer_calculator.py
├── fixtures/
│   └── audio_samples.py
└── utils/
    └── performance.py
```

## Running Tests

### Integration Tests

Test enhancement with real STT service:

```bash
# Run integration tests
make test-integration SERVICE=stt

# Run specific enhancement integration tests
pytest services/tests/integration/test_stt_enhancement_integration.py -v
```

### Component Tests

Test enhancement performance and error handling:

```bash
# Run component tests
make test-component SERVICE=stt

# Run specific enhancement component tests
pytest services/tests/component/test_enhancement_*.py -v
```

### Quality Tests

Test audio quality improvements:

```bash
# Run quality tests
pytest services/tests/quality/test_audio_quality.py -v

# Run WER calculator tests
pytest services/tests/quality/wer_calculator.py -v
```

### All Enhancement Tests

```bash
# Run all enhancement-related tests
pytest services/tests/ -k "enhancement" -v
```

## Baseline Measurements

### Running Baseline Measurements

Establish baseline performance before making improvements:

```bash
# Run baseline measurement script
python -m services.tests.measure_baseline

# Run with specific STT URL
python -m services.tests.measure_baseline --stt-url http://localhost:9000
```

### Baseline Output

The baseline measurement script outputs:

-  **Transcription latency**: Baseline transcription performance
-  **Enhancement overhead**: Additional latency from enhancement
-  **Chunk performance**: Chunk-level processing performance
-  **Service health**: STT service health and configuration

### Interpreting Results

```json
{
  "transcription_baseline": {
    "status": "success",
    "latency_ms": 1500.0,
    "transcript": "Hello world",
    "stats": {...}
  },
  "enhancement_overhead": {
    "enhancement_results": [...],
    "stats": {...}
  },
  "chunk_performance": {
    "chunk_results": [...],
    "stats": {...}
  }
}
```

## Performance Validation

### Latency Budgets

Default latency budgets for enhancement:

-  **File-level enhancement**: p95 < 500ms, p99 < 800ms, mean < 300ms
-  **Chunk-level enhancement**: p95 < 50ms, p99 < 100ms, mean < 30ms
-  **File-level transcription**: p95 < 2000ms, p99 < 3000ms, mean < 1500ms

### Performance Testing

```python
from services.tests.utils.performance import FileLevelPerformanceCollector

# Create performance collector
collector = FileLevelPerformanceCollector()

# Measure enhancement performance
with measure_latency("enhancement", collector):
    result = enhance_audio(audio_data)

# Validate against budget
validation = collector.validate_all()
assert validation["enhancement"]["overall_pass"]
```

## Quality Validation

### Audio Quality Testing

Test enhancement improves transcription quality:

```python
from services.tests.quality.test_audio_quality import TestAudioQuality

# Test enhancement with noisy audio
async def test_enhancement_improves_noisy_audio():
    # Use synthetic noisy samples
    # Transcribe with/without enhancement
    # Compare results
```

### WER Calculation

Calculate Word Error Rate for quality assessment:

```python
from services.tests.quality.wer_calculator import WERCalculator

calculator = WERCalculator()
wer_result = calculator.calculate_wer(reference, hypothesis)
print(f"WER: {wer_result.wer:.2f}%")
```

## Error Handling Testing

### Error Recovery Tests

Test enhancement handles various error conditions:

-  **MetricGAN+ runtime failures**
-  **Memory errors**
-  **Network timeouts**
-  **Corrupted model files**
-  **Invalid audio formats**

### Error Logging

Enhanced error logging includes:

-  **Correlation ID**: Request tracking
-  **Error type**: Specific error classification
-  **Audio metadata**: Input size, format, duration
-  **Fallback behavior**: Whether original audio was returned

## Configuration Testing

### Configuration Edge Cases

Test enhancement with various configurations:

-  **Missing dependencies**: speechbrain not installed
-  **Invalid model paths**: Corrupted or missing models
-  **Environment variables**: Various FW_ENABLE_ENHANCEMENT values
-  **Resource constraints**: Insufficient memory, disk space

### Configuration Validation

```python
# Test enhancement configuration
def test_enhancement_with_missing_dependencies():
    with patch('speechbrain', side_effect=ImportError):
        # Should handle gracefully
        result = enhance_audio(audio_data)
        assert result == audio_data  # Fallback to original
```

## Audio Format Testing

### Format Edge Cases

Test enhancement with various audio formats:

-  **Sample rates**: 8kHz, 16kHz, 48kHz
-  **Channels**: Mono, stereo
-  **Duration**: Very short (< 100ms), very long (> 30s)
-  **Amplitude**: Silent, maximum, clipped
-  **Frequency**: Low frequency, high frequency
-  **Quality**: Low bitrate, corrupted headers

### Format Validation

```python
# Test different sample rates
sample_rates = [8000, 16000, 22050, 44100, 48000]
for rate in sample_rates:
    audio = generate_audio(sample_rate=rate)
    result = enhance_audio(audio)
    assert result is not None
```

## Continuous Validation

### Validation Script

Run comprehensive audio pipeline validation:

```bash
# Run validation script
./scripts/validate_audio_pipeline.sh

# Or run individual components
python -m services.tests.measure_baseline
make test-component SERVICE=stt
make test-integration SERVICE=stt
pytest services/tests/quality/ -v
```

### CI/CD Integration

Add to CI/CD pipeline:

```yaml
# .github/workflows/audio-enhancement-tests.yml
- name: Run Enhancement Tests
  run: |
    make test-component SERVICE=stt
    make test-integration SERVICE=stt
    pytest services/tests/quality/ -v
```

## Monitoring and Observability

### Health Check Integration

Enhancement status in health endpoint:

```json
{
  "status": "ready",
  "service": "stt",
  "components": {
    "enhancer_loaded": true,
    "enhancer_enabled": true
  },
  "enhancement_stats": {
    "total_processed": 100,
    "successful": 95,
    "failed": 5,
    "success_rate": 95.0,
    "avg_duration_ms": 250.0,
    "last_error": null,
    "last_error_time": null
  }
}
```

### Logging

Enhanced logging includes:

-  **Success logs**: Enhancement duration, input/output sizes
-  **Error logs**: Error type, correlation ID, fallback behavior
-  **Performance logs**: Latency measurements, throughput

## Troubleshooting

### Common Issues

1.  **Enhancement not working**: Check FW_ENABLE_ENHANCEMENT environment variable
2.  **High latency**: Check enhancement budget and performance
3.  **Memory errors**: Check available memory and model size
4.  **Import errors**: Check speechbrain installation

### Debug Commands

```bash
# Check enhancement status
curl http://localhost:9000/health/ready

# Check environment variables
env | grep FW_

# Check model loading
python -c "from services.common.audio_enhancement import AudioEnhancer; print('Enhancer loaded')"
```

## Future Improvements

### Planned Enhancements

1.  **Prometheus metrics**: Real-time performance monitoring
2.  **A/B testing**: Compare enhancement effectiveness
3.  **WER validation**: Full quality assessment with labeled data
4.  **Real-time monitoring**: Dashboards for enhancement performance

### Known Limitations

1.  **WER validation**: Requires labeled test datasets
2.  **Real-time monitoring**: Currently logs-based, metrics planned
3.  **A/B testing**: Framework not yet implemented
4.  **Quality assessment**: Subjective without ground truth

## References

-  [Audio Enhancement Implementation](../audio_enhancement.md)
-  [STT Service Documentation](../stt_service.md)
-  [Testing Framework](../testing_framework.md)
-  [Performance Monitoring](../performance_monitoring.md)
