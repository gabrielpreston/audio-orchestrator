---
title: Testing Troubleshooting Guide
description: Guide for diagnosing and resolving common testing issues in the audio-orchestrator audio pipeline
last-updated: 2025-10-20
---

# Testing Troubleshooting Guide

This guide helps diagnose and resolve common issues encountered during testing of the audio-orchestrator audio pipeline.

## Common Test Failures

### Service Not Ready

#### Service Not Ready Symptoms


- Tests fail with "Service not ready" errors
- Health check endpoints return 503 status
- Services fail to start or respond

#### Service Not Ready Diagnosis


```bash
# Check service health
curl http://localhost:9000/health/ready  # STT service
curl http://localhost:7000/health/ready  # TTS service
curl http://localhost:8000/health/ready  # LLM service
curl http://localhost:8001/health/ready  # Orchestrator service

# Check service logs
make logs SERVICE=stt
make logs SERVICE=tts
make logs SERVICE=llm
make logs SERVICE=orchestrator
```

#### Solutions


- **Check Service Dependencies**: Ensure all required services are running
- **Verify Configuration**: Check environment variables and configuration files
- **Check Resource Usage**: Ensure sufficient CPU, memory, and disk space
- **Restart Services**: Use `make restart` to restart services
- **Check Network**: Verify network connectivity between services

### Audio Format Issues

#### Audio Format Symptoms


- Tests fail with "Invalid audio format" errors
- WAV validation failures
- Audio processing errors

#### Audio Format Diagnosis


```bash
# Check audio format
file test_audio.wav
mediainfo test_audio.wav

# Validate WAV format
python -c "
from services.tests.utils.audio_quality_helpers import validate_wav_format
with open('test_audio.wav', 'rb') as f:
    data = f.read()
result = validate_wav_format(data)
print(result)
"
```

#### Service Not Ready Solutions


- **Check Audio Format**: Ensure audio is 16-bit PCM WAV
- **Verify Sample Rate**: Check sample rate matches requirements
- **Check Channels**: Ensure mono or stereo as required
- **Validate Headers**: Check WAV header format
- **Regenerate Audio**: Use `generate_samples_simple.py` to create new samples

### Quality Threshold Failures

#### Quality Threshold Symptoms


- Tests fail with quality threshold violations
- SNR below threshold
- THD above threshold
- Latency above threshold

#### Quality Threshold Diagnosis


```bash
# Check quality metrics
python -c "
from services.tests.utils.audio_quality_helpers import calculate_snr, calculate_thd
import generate_test_audio

audio_data = generate_test_audio(duration=1.0, frequency=440.0, amplitude=0.5)
snr = calculate_snr(audio_data, noise_floor=0.01)
thd = calculate_thd(audio_data, fundamental_freq=440.0, sample_rate=16000)
print(f'SNR: {snr:.2f}dB')
print(f'THD: {thd:.2f}%')
"
```

#### Quality Threshold Solutions


- **Adjust Thresholds**: Modify quality thresholds if appropriate
- **Check Audio Quality**: Ensure test audio meets quality requirements
- **Verify Environment**: Check for environmental noise or interference
- **Update Baselines**: Update quality baselines if system has changed
- **Check Hardware**: Verify audio hardware is functioning correctly

### Performance Issues

#### Performance Symptoms


- Tests fail with performance threshold violations
- High latency
- High memory usage
- High CPU usage

#### Performance Diagnosis


```bash
# Check system resources
top
htop
free -h
df -h

# Check service performance
make logs SERVICE=stt | grep -i performance
make logs SERVICE=tts | grep -i performance
```

#### Performance Solutions


- **Optimize Configuration**: Adjust service configuration for better performance
- **Check Resource Usage**: Ensure sufficient system resources
- **Update Thresholds**: Adjust performance thresholds if appropriate
- **Check Dependencies**: Verify all dependencies are properly installed
- **Restart Services**: Restart services to clear memory leaks

## Debugging Techniques

### Enable Debug Logging

#### Configuration


```bash
# Set debug logging
export LOG_LEVEL=DEBUG

# Enable debug WAV generation
export DEBUG_WAV_ENABLED=true
export DEBUG_WAV_DIR=./debug_wavs

# Enable correlation ID logging
export CORRELATION_ID_ENABLED=true
```

#### Usage


```bash
# Run tests with debug logging
LOG_LEVEL=DEBUG pytest services/tests/quality/test_audio_fidelity.py -v

# Check debug logs
make logs SERVICE=stt | grep -i debug
make logs SERVICE=tts | grep -i debug
```

### Save Debug Audio

#### Debug Audio Configuration


```bash
# Enable debug WAV generation
export DEBUG_WAV_ENABLED=true
export DEBUG_WAV_DIR=./debug_wavs

# Create debug directory
mkdir -p ./debug_wavs
```

#### Debug Audio Usage


```bash
# Run tests with debug audio
DEBUG_WAV_ENABLED=true pytest services/tests/quality/test_audio_fidelity.py -v

# Check debug audio files
ls -la ./debug_wavs/
```

### Check Service Logs

#### STT Service


```bash
# Check STT service logs
make logs SERVICE=stt

# Filter for specific issues
make logs SERVICE=stt | grep -i error
make logs SERVICE=stt | grep -i warning
make logs SERVICE=stt | grep -i performance
```

#### TTS Service


```bash
# Check TTS service logs
make logs SERVICE=tts

# Filter for specific issues
make logs SERVICE=tts | grep -i error
make logs SERVICE=tts | grep -i warning
make logs SERVICE=tts | grep -i performance
```

#### LLM Service


```bash
# Check LLM service logs
make logs SERVICE=llm

# Filter for specific issues
make logs SERVICE=llm | grep -i error
make logs SERVICE=llm | grep -i warning
make logs SERVICE=llm | grep -i performance
```

#### Orchestrator Service


```bash
# Check Orchestrator service logs
make logs SERVICE=orchestrator

# Filter for specific issues
make logs SERVICE=orchestrator | grep -i error
make logs SERVICE=orchestrator | grep -i warning
make logs SERVICE=orchestrator | grep -i performance
```

### Monitor Resources

#### CPU Usage


```bash
# Monitor CPU usage
top -p $(pgrep -f "python.*stt")
top -p $(pgrep -f "python.*tts")
top -p $(pgrep -f "python.*llm")
top -p $(pgrep -f "python.*orchestrator")
```

#### Memory Usage


```bash
# Monitor memory usage
ps aux | grep -E "(stt|tts|llm|orchestrator)" | grep -v grep

# Check memory usage in detail
pmap -x $(pgrep -f "python.*stt")
pmap -x $(pgrep -f "python.*tts")
pmap -x $(pgrep -f "python.*llm")
pmap -x $(pgrep -f "python.*orchestrator")
```

#### Disk Usage


```bash
# Check disk usage
df -h

# Check temporary files
ls -la /tmp/ | grep -E "(stt|tts|llm|orchestrator)"
```

## Performance Optimization

### Slow Tests

#### Slow Test Symptoms


- Tests take too long to complete
- Timeout errors
- Performance threshold violations

#### Slow Test Solutions


- **Skip Slow Tests**: Use `pytest -m "not slow"` to skip slow tests
- **Parallel Execution**: Use `pytest -n auto` for parallel execution
- **Optimize Configuration**: Adjust service configuration for better performance
- **Check Dependencies**: Ensure all dependencies are properly installed
- **Update Hardware**: Consider upgrading hardware for better performance

### Memory Issues

#### Memory Symptoms


- Out of memory errors
- High memory usage
- Memory leaks

#### Memory Solutions


- **Check Memory Usage**: Monitor memory usage during tests
- **Optimize Configuration**: Adjust memory-related configuration
- **Check for Leaks**: Look for memory leaks in long-running tests
- **Restart Services**: Restart services to clear memory
- **Update Dependencies**: Update dependencies to fix memory issues

### CPU Issues

#### CPU Symptoms


- High CPU usage
- CPU timeout errors
- Performance degradation

#### CPU Solutions


- **Check CPU Usage**: Monitor CPU usage during tests
- **Optimize Configuration**: Adjust CPU-related configuration
- **Check Dependencies**: Ensure all dependencies are properly installed
- **Update Hardware**: Consider upgrading hardware for better performance
- **Check Background Processes**: Stop unnecessary background processes

## Network Issues

### Connectivity Problems

#### Connectivity Symptoms


- Connection refused errors
- Timeout errors
- Network unreachable errors

#### Connectivity Diagnosis


```bash
# Check network connectivity
ping localhost
telnet localhost 9000  # STT service
telnet localhost 7000  # TTS service
telnet localhost 8000  # LLM service
telnet localhost 8001  # Orchestrator service

# Check port availability
netstat -tlnp | grep -E "(9000|7000|8000|8001)"
```

#### Connectivity Solutions


- **Check Port Availability**: Ensure ports are available
- **Check Firewall**: Verify firewall settings
- **Check Service Status**: Ensure services are running
- **Check Network Configuration**: Verify network configuration
- **Restart Services**: Restart services to fix connectivity issues

### Timeout Issues

#### Timeout Symptoms


- Request timeout errors
- Connection timeout errors
- Service timeout errors

#### Timeout Solutions


- **Increase Timeouts**: Adjust timeout settings
- **Check Service Performance**: Ensure services are performing well
- **Check Network Latency**: Verify network latency is acceptable
- **Optimize Configuration**: Adjust service configuration for better performance
- **Check Dependencies**: Ensure all dependencies are properly installed

## Test Environment Issues

### Environment Variables

#### Environment Symptoms


- Configuration errors
- Service startup failures
- Test failures due to missing configuration

#### Environment Diagnosis


```bash
# Check environment variables
env | grep -E "(STT|TTS|LLM|ORCHESTRATOR|TEST)"

# Check configuration files
cat .env.sample
cat .env.common
cat .env.docker
```

#### Environment Solutions


- **Check Environment Variables**: Ensure all required environment variables are set
- **Check Configuration Files**: Verify configuration files are correct
- **Update Documentation**: Update documentation with correct configuration
- **Check Dependencies**: Ensure all dependencies are properly installed
- **Restart Services**: Restart services with correct configuration

### Dependency Issues

#### Dependency Symptoms


- Import errors
- Module not found errors
- Version compatibility issues

#### Dependency Diagnosis


```bash
# Check Python dependencies
pip list | grep -E "(fastapi|discord|numpy|scipy)"

# Check system dependencies
ldd $(which python)
```

#### Dependency Solutions


- **Install Dependencies**: Install missing dependencies
- **Update Dependencies**: Update dependencies to compatible versions
- **Check Version Compatibility**: Ensure version compatibility
- **Check System Dependencies**: Ensure system dependencies are installed
- **Use Virtual Environment**: Use virtual environment for dependency isolation

## Best Practices

### Test Maintenance

#### Regular Updates


- **Update Test Data**: Regularly update test data and reference samples
- **Update Thresholds**: Adjust quality thresholds based on system changes
- **Update Documentation**: Keep documentation up to date
- **Review Test Results**: Regularly review test results for patterns
- **Optimize Tests**: Continuously optimize tests for better performance

#### Test Organization


- **Follow Naming Convention**: Use consistent naming for test files and functions
- **Use Appropriate Markers**: Use appropriate pytest markers for test categorization
- **Add Documentation**: Document test purpose and expected behavior
- **Keep Tests Focused**: Keep tests focused on specific functionality
- **Avoid Test Dependencies**: Avoid dependencies between tests

### Quality Assurance

#### Regular Testing


- **Run Tests Regularly**: Run tests regularly to catch issues early
- **Monitor Quality Metrics**: Monitor quality metrics continuously
- **Update Baselines**: Update quality baselines when system changes
- **Review Thresholds**: Review quality thresholds periodically
- **Continuous Improvement**: Continuously improve testing processes

#### Performance Monitoring


- **Monitor Performance**: Monitor performance metrics continuously
- **Set Alerts**: Set up alerts for performance issues
- **Optimize Configuration**: Optimize configuration for better performance
- **Update Hardware**: Update hardware when necessary
- **Check Dependencies**: Ensure all dependencies are properly installed

### Troubleshooting Process

#### Systematic Approach


- **Identify Symptoms**: Clearly identify the symptoms of the problem
- **Check Logs**: Check service logs for error messages
- **Verify Configuration**: Verify configuration is correct
- **Check Dependencies**: Ensure all dependencies are properly installed
- **Test Isolation**: Isolate the problem to specific components
- **Apply Solutions**: Apply appropriate solutions
- **Verify Fix**: Verify the fix resolves the problem
- **Document Solution**: Document the solution for future reference

### Async Tests Being Skipped

#### Async Test Symptoms


- Tests with `async def` are skipped with warning "async def functions are not natively supported"
- Integration tests show "SKIPPED" status instead of running
- Coverage collection fails due to skipped tests

#### Async Test Diagnosis


```bash
# Check pytest configuration
grep -A 5 -B 5 "asyncio" pyproject.toml

# Run tests with verbose output
pytest -v -m integration

# Check for async test warnings
pytest --tb=short -m integration 2>&1 | grep -i "async"
```

#### Solutions


- **Verify pytest-asyncio Configuration**: Ensure `pyproject.toml` has:

   ```toml
   [tool.pytest.ini_options]
   asyncio_mode = "auto"
   asyncio_default_fixture_loop_scope = "function"
   ```

- **Check pytest-asyncio Installation**: Verify pytest-asyncio is installed:

   ```bash
   pip list | grep pytest-asyncio
   ```

- **Restart Test Environment**: Sometimes configuration changes require restart:

   ```bash
   make stop
   make run
   ```

- **Check Test Markers**: Ensure integration tests have proper markers:

   ```python
   @pytest.mark.integration
   async def test_example():
       pass
   ```

#### Prevention


- **Regular Maintenance**: Perform regular maintenance on test environment
- **Monitor Quality**: Monitor quality metrics continuously
- **Update Dependencies**: Keep dependencies up to date
- **Check Configuration**: Regularly check configuration for issues
- **Document Issues**: Document common issues and solutions
