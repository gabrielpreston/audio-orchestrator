---
title: Audio Quality Thresholds
description: Quality thresholds and benchmarks for the discord-voice-lab audio pipeline
last-updated: 2025-10-17
---

# Audio Quality Thresholds

This document defines the quality thresholds and benchmarks for the discord-voice-lab audio pipeline.

## Audio Quality Metrics

### Signal-to-Noise Ratio (SNR)

- **Minimum**: 20dB for clean audio
- **Acceptable**: 10dB for noisy audio
- **Measurement**: `calculate_snr()` function
- **Threshold**: `MIN_SNR=20.0`

### Total Harmonic Distortion (THD)

- **Maximum**: 1% for normal amplitude
- **Acceptable**: 2% for high amplitude
- **Measurement**: `calculate_thd()` function
- **Threshold**: `MAX_THD=1.0`

### Frequency Response

- **Voice Range**: 300Hz-3400Hz ratio > 0.8
- **Aliasing**: < 10% aliasing ratio
- **Measurement**: `measure_frequency_response()` function
- **Threshold**: `VOICE_RANGE_RATIO=0.8`, `MAX_ALIASING=0.1`

### Audio Fidelity

- **Correlation**: > 0.9 for processed audio
- **MSE**: < 0.1 for normalized audio
- **Measurement**: `validate_audio_fidelity()` function
- **Threshold**: `MIN_CORRELATION=0.9`, `MAX_MSE=0.1`

## Performance Metrics

### Latency Thresholds

- **End-to-End**: < 2s for short queries
- **STT Processing**: < 300ms from speech onset
- **TTS Synthesis**: < 1s for short text
- **Wake Detection**: < 200ms
- **Measurement**: Time-based measurements
- **Threshold**: `MAX_E2E_LATENCY=2.0`, `MAX_STT_LATENCY=0.3`, `MAX_TTS_LATENCY=1.0`, `MAX_WAKE_LATENCY=0.2`

### Throughput Thresholds

- **STT Requests**: > 0.1 requests/second
- **TTS Requests**: > 0.1 requests/second
- **Concurrent Processing**: > 3 concurrent requests
- **Measurement**: Request rate calculations
- **Threshold**: `MIN_STT_THROUGHPUT=0.1`, `MIN_TTS_THROUGHPUT=0.1`, `MIN_CONCURRENT=3`

### Resource Usage

- **Memory**: < 100MB per service
- **CPU**: < 50% per service
- **Disk**: < 1GB for temporary files
- **Measurement**: System resource monitoring
- **Threshold**: `MAX_MEMORY=100`, `MAX_CPU=50`, `MAX_DISK=1`

## Quality Regression Thresholds

### Audio Quality Regression

- **SNR Regression**: < 5dB decrease
- **THD Regression**: < 1% increase
- **Fidelity Regression**: < 0.1 decrease
- **Measurement**: Baseline vs current comparison
- **Threshold**: `MAX_SNR_REGRESSION=5.0`, `MAX_THD_REGRESSION=1.0`, `MAX_FIDELITY_REGRESSION=0.1`

### Performance Regression

- **Latency Regression**: < 1s increase
- **Throughput Regression**: < 0.05 requests/second decrease
- **Memory Regression**: < 50MB increase
- **CPU Regression**: < 20% increase
- **Measurement**: Performance benchmark comparison
- **Threshold**: `MAX_LATENCY_REGRESSION=1.0`, `MAX_THROUGHPUT_REGRESSION=0.05`, `MAX_MEMORY_REGRESSION=50`, `MAX_CPU_REGRESSION=20`

## Test Environment Thresholds

### Development Environment

- **SNR**: > 15dB (lower due to development setup)
- **THD**: < 2% (higher due to development setup)
- **Latency**: < 3s (higher due to development setup)
- **Memory**: < 200MB (higher due to development setup)
- **Purpose**: Development and local testing

### Staging Environment

- **SNR**: > 18dB (closer to production)
- **THD**: < 1.5% (closer to production)
- **Latency**: < 2.5s (closer to production)
- **Memory**: < 150MB (closer to production)
- **Purpose**: Pre-production validation

### Production Environment

- **SNR**: > 20dB (production quality)
- **THD**: < 1% (production quality)
- **Latency**: < 2s (production quality)
- **Memory**: < 100MB (production quality)
- **Purpose**: Production deployment

## Audio Format Thresholds

### WAV Format Validation

- **Channels**: 1 (mono) or 2 (stereo)
- **Sample Rate**: 16000Hz (STT), 22050Hz (TTS), 48000Hz (Discord)
- **Bit Depth**: 16-bit PCM
- **Duration**: > 0.1s, < 30s
- **Measurement**: `validate_wav_format()` function
- **Threshold**: `MIN_CHANNELS=1`, `MAX_CHANNELS=2`, `MIN_SAMPLE_RATE=16000`, `MAX_SAMPLE_RATE=48000`, `MIN_BIT_DEPTH=16`, `MAX_BIT_DEPTH=16`, `MIN_DURATION=0.1`, `MAX_DURATION=30.0`

### Audio Processing Thresholds

- **Sample Rate Conversion**: < 0.1% quality loss
- **Bit Depth Conversion**: < 0.1% quality loss
- **Channel Conversion**: < 0.1% quality loss
- **Measurement**: Audio fidelity validation
- **Threshold**: `MAX_CONVERSION_LOSS=0.001`

## Service-Specific Thresholds

### STT Service

- **Transcription Accuracy**: > 90% for clean audio
- **Language Detection**: > 95% accuracy
- **Processing Time**: < 300ms per request
- **Memory Usage**: < 50MB per request
- **Threshold**: `MIN_TRANSCRIPTION_ACCURACY=0.9`, `MIN_LANGUAGE_ACCURACY=0.95`, `MAX_STT_PROCESSING_TIME=0.3`, `MAX_STT_MEMORY=50`

### TTS Service

- **Synthesis Quality**: > 90% similarity to reference
- **Voice Consistency**: > 95% consistency across requests
- **Processing Time**: < 1s per request
- **Memory Usage**: < 50MB per request
- **Threshold**: `MIN_SYNTHESIS_QUALITY=0.9`, `MIN_VOICE_CONSISTENCY=0.95`, `MAX_TTS_PROCESSING_TIME=1.0`, `MAX_TTS_MEMORY=50`

### Orchestrator Service

- **Response Time**: < 500ms per request
- **Memory Usage**: < 30MB per request
- **CPU Usage**: < 30% per request
- **Threshold**: `MAX_ORCHESTRATOR_RESPONSE_TIME=0.5`, `MAX_ORCHESTRATOR_MEMORY=30`, `MAX_ORCHESTRATOR_CPU=30`

## Monitoring and Alerting

### Quality Alerts

- **SNR Alert**: < 15dB for 5 consecutive samples
- **THD Alert**: > 2% for 5 consecutive samples
- **Latency Alert**: > 3s for 5 consecutive requests
- **Memory Alert**: > 150MB for 5 consecutive samples
- **Purpose**: Early warning of quality degradation

### Performance Alerts

- **Throughput Alert**: < 0.05 requests/second for 1 minute
- **CPU Alert**: > 80% for 1 minute
- **Memory Alert**: > 200MB for 1 minute
- **Disk Alert**: > 2GB for 1 minute
- **Purpose**: Early warning of performance issues

### Regression Alerts

- **Quality Regression**: > 5dB SNR decrease or > 1% THD increase
- **Performance Regression**: > 1s latency increase or > 50MB memory increase
- **Purpose**: Early warning of quality or performance regression

## Threshold Adjustment

### When to Adjust Thresholds

1. **New Hardware**: Different hardware may have different performance characteristics
2. **New Software**: Software updates may affect performance
3. **New Requirements**: Business requirements may change
4. **Environmental Changes**: Different deployment environments may require different thresholds

### How to Adjust Thresholds

1. **Measure Baseline**: Run tests on known-good system
2. **Analyze Results**: Identify patterns and outliers
3. **Set New Thresholds**: Set thresholds based on baseline measurements
4. **Validate Thresholds**: Run tests to ensure thresholds are appropriate
5. **Document Changes**: Update documentation with new thresholds
6. **Monitor Impact**: Monitor system behavior with new thresholds

### Threshold Validation

1. **Statistical Analysis**: Use statistical methods to validate thresholds
2. **Historical Data**: Compare with historical performance data
3. **A/B Testing**: Test different threshold values
4. **Expert Review**: Have experts review threshold settings
5. **Continuous Monitoring**: Monitor system behavior with new thresholds

## Implementation

### Configuration

```bash
# Environment variables for quality thresholds
export MIN_SNR=20.0
export MAX_THD=1.0
export MAX_E2E_LATENCY=2.0
export MAX_STT_LATENCY=0.3
export MAX_TTS_LATENCY=1.0
export MAX_WAKE_LATENCY=0.2
export MAX_MEMORY=100
export MAX_CPU=50
export MAX_SNR_REGRESSION=5.0
export MAX_THD_REGRESSION=1.0
export MAX_LATENCY_REGRESSION=1.0
export MAX_MEMORY_REGRESSION=50
```

### Test Implementation

```python
# Quality threshold validation
def test_quality_thresholds():
    snr = calculate_snr(audio_data, noise_floor=0.01)
    thd = calculate_thd(audio_data, fundamental_freq=440.0, sample_rate=16000)
    
    assert snr >= MIN_SNR
    assert thd <= MAX_THD
    assert latency <= MAX_E2E_LATENCY
    assert memory_usage <= MAX_MEMORY
```

### Monitoring Implementation

```python
# Quality monitoring
def monitor_quality():
    current_snr = calculate_snr(audio_data, noise_floor=0.01)
    baseline_snr = get_baseline_snr()
    
    if current_snr < baseline_snr - MAX_SNR_REGRESSION:
        alert_quality_regression("SNR", current_snr, baseline_snr)
```

## Best Practices

### Threshold Setting

1. **Start Conservative**: Set initial thresholds conservatively
2. **Monitor Closely**: Monitor system behavior with new thresholds
3. **Adjust Gradually**: Adjust thresholds gradually based on data
4. **Document Changes**: Document all threshold changes
5. **Validate Changes**: Validate threshold changes with testing

### Quality Assurance

1. **Regular Testing**: Run quality tests regularly
2. **Baseline Updates**: Update baselines when system changes
3. **Threshold Reviews**: Review thresholds periodically
4. **Expert Input**: Get expert input on threshold settings
5. **Continuous Improvement**: Continuously improve threshold settings

### Quality Monitoring

1. **Proactive Monitoring**: Monitor quality metrics proactively
2. **Early Warning**: Set up early warning systems
3. **Automated Alerts**: Use automated alerting systems
4. **Response Procedures**: Have procedures for responding to alerts
5. **Escalation**: Have escalation procedures for critical issues
