---
title: Test Artifacts Management
description: Test artifact storage strategy and management for the audio-orchestrator project
last-updated: 2025-10-17
---

# Test Artifacts Management

This document describes the test artifact storage strategy and management for the audio-orchestrator project.

## Overview

Test artifacts are temporary files generated during test execution that need to be stored, managed, and cleaned up appropriately. This includes audio files, debug outputs, and other test-generated content.

## Storage Strategy

### Temporary Artifacts (Auto-Cleanup)

**Location**: `test_artifacts/` (gitignored)
**Purpose**: Temporary test outputs, debug files, integration test results
**Cleanup**: Automatic after test session
**Configuration**: `TEST_ARTIFACTS_DIR` environment variable

### Permanent Fixtures (Version Controlled)

**Location**: `services/tests/fixtures/`
**Purpose**: Reference samples, baseline data, known-good test data
**Cleanup**: Never (committed to git)
**Configuration**: Fixed paths

## Directory Structure

```text
project_root/
├── test_artifacts/              # Temporary (gitignored, auto-cleanup)
│   ├── tts/                     # TTS test outputs
│   ├── integration/             # Integration test outputs
│   └── debug/                   # Debug outputs
├── services/tests/
│   ├── fixtures/
│   │   ├── audio/               # Existing audio fixtures
│   │   └── tts/                 # TTS fixtures (new)
│   │       ├── samples/         # Baseline samples (version controlled)
│   │       │   ├── short_phrase.wav
│   │       │   ├── short_phrase.json  # Metadata
│   │       │   └── ...
│   │       ├── conftest.py
│   │       ├── tts_test_helpers.py
│   │       └── generate_baselines.py
│   └── mocks/
│       └── tts_adapter.py
```

## Configuration

### Environment Variables

```bash
# Set custom test artifacts directory
export TEST_ARTIFACTS_DIR="/custom/path/to/artifacts"

# Default: test_artifacts/ (relative to project root)
```

### Pytest Fixtures

```python
@pytest.fixture(scope="session")
def test_artifacts_dir() -> Generator[Path, None, None]:
    """Centralized test artifacts directory with auto-cleanup."""
    artifacts_dir = Path(os.getenv("TEST_ARTIFACTS_DIR", "test_artifacts"))
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    yield artifacts_dir
    # Cleanup after all tests
    if artifacts_dir.exists():
        shutil.rmtree(artifacts_dir, ignore_errors=True)
```

## Usage Examples

### Saving Test Artifacts

```python
def test_tts_audio_validation(tts_artifacts_dir: Path):
    """Test TTS audio validation."""
    # Generate test audio
    audio_data = generate_test_audio()
    
    # Save to artifacts directory for debugging
    output_file = tts_artifacts_dir / "test_audio.wav"
    output_file.write_bytes(audio_data)
    
    # Validate audio
    result = validate_tts_audio_format(audio_data)
    assert result["is_valid"]
```

### Loading Baseline Samples

```python
def test_tts_baseline_comparison(tts_baseline_samples):
    """Test TTS baseline comparison."""
    # Load baseline sample
    baseline_file = tts_baseline_samples["short_phrase"]
    baseline_data = baseline_file.read_bytes()
    
    # Compare with generated audio
    generated_data = generate_tts_audio("Hello world")
    
    # Validate similarity
    similarity = calculate_audio_similarity(baseline_data, generated_data)
    assert similarity > 0.8
```

## Cleanup Procedures

### Automatic Cleanup

- **Session-scoped fixtures**: Clean up after all tests complete
- **Function-scoped fixtures**: Clean up after each test
- **Temporary directories**: Auto-deleted by pytest

### Manual Cleanup

```bash
# Clean test artifacts manually
rm -rf test_artifacts/

# Clean specific service artifacts
rm -rf test_artifacts/tts/
rm -rf test_artifacts/integration/
```

### CI/CD Cleanup

```yaml
# GitHub Actions example
- name: Clean test artifacts
  run: |
    rm -rf test_artifacts/
    rm -rf .pytest_cache/
```

## Troubleshooting

### Common Issues

1. **Artifacts not cleaning up**
   - Check if processes are still using files
   - Verify fixture scope (session vs function)
   - Check for permission issues

2. **Artifacts directory not found**
   - Verify `TEST_ARTIFACTS_DIR` environment variable
   - Check if directory is being created
   - Ensure proper permissions

3. **Large artifact files**
   - Check for memory leaks in test generation
   - Verify cleanup is working properly
   - Consider reducing test data size

### Debug Commands

```bash
# Check artifacts directory
ls -la test_artifacts/

# Check disk usage
du -sh test_artifacts/

# Check for open files
lsof +D test_artifacts/
```

## Best Practices

### File Naming

- Use descriptive names: `test_audio_quality.wav`
- Include test context: `integration_tts_synthesis.wav`
- Use timestamps for unique files: `debug_20240115_103000.wav`

### File Organization

- Group by test type: `tts/`, `integration/`, `debug/`
- Use subdirectories for complex tests
- Keep related files together

### Performance

- Clean up large files immediately after use
- Use temporary files for intermediate processing
- Avoid storing large files in version control

### Security

- Don't store sensitive data in artifacts
- Use appropriate file permissions
- Clean up artifacts in CI/CD pipelines

## Integration with CI/CD

### GitHub Actions

```yaml
- name: Run tests
  run: make test
  env:
    TEST_ARTIFACTS_DIR: ${{ runner.temp }}/test_artifacts

- name: Upload test artifacts
  if: always()
  uses: actions/upload-artifact@v3
  with:
    name: test-artifacts
    path: test_artifacts/
    retention-days: 7
```

### Docker

```dockerfile
# Clean up artifacts in Docker
RUN rm -rf test_artifacts/
RUN rm -rf .pytest_cache/
```

## Monitoring

### Disk Usage

```bash
# Monitor test artifacts disk usage
watch -n 5 'du -sh test_artifacts/'
```

### File Count

```bash
# Count test artifacts
find test_artifacts/ -type f | wc -l
```

### Cleanup Verification

```bash
# Verify cleanup worked
ls -la test_artifacts/  # Should be empty or not exist
```

## Related Documentation

- [TTS Testing Guide](TTS_TESTING.md)
- [Main Testing Documentation](TESTING.md)
- [Quality Thresholds](QUALITY_THRESHOLDS.md)
