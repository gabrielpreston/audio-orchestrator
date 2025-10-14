# Testing Guide

This guide covers the unified testing strategy for discord-voice-lab, ensuring identical behavior between local development and CI environments.

## Quick Start

```bash
# Setup
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
pip install -r requirements-dev.txt

# Run tests
make test                  # Unit + component tests
make test-integration      # Integration tests (requires Docker)
make test-coverage         # Generate coverage report
```

## Test Structure

### Test Pyramid
- **Unit Tests (70%)**: Fast, isolated tests for individual functions
- **Component Tests (20%)**: Service-level tests with mocked dependencies
- **Integration Tests (8%)**: Cross-service tests with real containers
- **E2E Tests (2%)**: Full stack tests (manual trigger only)

### Directory Layout
```
services/
├── common/tests/          # Shared library tests
├── discord/tests/         # Discord service tests
├── stt/tests/            # STT service tests
├── llm/tests/            # LLM service tests
├── orchestrator/tests/   # Orchestrator service tests
├── tts/tests/            # TTS service tests
└── tests/                # Cross-service tests
    ├── integration/      # Integration tests
    └── e2e/             # End-to-end tests
```

## Commands

### Local Development
```bash
make test                 # Run all unit + component tests
make test-unit           # Unit tests only
make test-component      # Component tests only
make test-integration    # Integration tests (requires Docker)
make test-e2e           # End-to-end tests (manual trigger)
make test-watch         # Watch mode for unit tests
make test-debug         # Debug mode with verbose output
make test-specific      # Run specific tests (PYTEST_ARGS="-k pattern")
```

### Quality Gates
```bash
make lint                # All linting (black, isort, ruff, mypy, etc.)
make typecheck          # Type checking only
make security           # Security scanning (pip-audit)
```

### Coverage
```bash
make test-coverage      # Generate HTML coverage report
make coverage-report    # View coverage report in browser
```

## Writing Tests

### Unit Tests
- Test individual functions and classes
- Mock all external dependencies
- Use descriptive test names
- Keep tests fast (<100ms each)

### Component Tests
- Test service endpoints and business logic
- Mock external HTTP calls
- Use realistic test data
- Test error handling

### Integration Tests
- Test service-to-service communication
- Use Docker Compose for real services
- Test with real data formats
- Verify end-to-end workflows

## Mocking Guidelines

### Discord API
```python
@pytest.fixture
def mock_discord_client():
    with patch('discord.Client') as mock_client:
        yield mock_client
```

### HTTP Services
```python
@pytest.fixture
def mock_httpx_client():
    with httpx_mock() as mock:
        yield mock
```

### Audio Processing
```python
@pytest.fixture
def sample_audio_data():
    return load_audio_fixture('sample_voice.wav')
```

## Common Issues

### Missing Dependencies
```bash
pip install -r requirements-dev.txt
```

### Coverage Below Threshold
- Add tests for uncovered code paths
- Check coverage report: `make coverage-report`
- Adjust thresholds in `pytest.ini` if needed

### Network Calls in Unit Tests
- Replace with mocks using `pytest-mock`
- Use `httpx_mock` for HTTP calls
- Mock Discord client connections

### Failing Linting
```bash
make lint-fix            # Auto-fix formatting issues
make lint-local          # Run linting locally
```

## CI Integration

### GitHub Actions
- Runs same commands as local development
- Parallel execution of lint, typecheck, security, tests
- Matrix testing across Python versions
- Artifact upload for coverage and logs

### Reproducing CI Locally
1. Install all dependencies: `pip install -r requirements-dev.txt`
2. Run same commands: `make lint-local && make test-local`
3. Check artifacts if tests fail

## Configuration

### pytest.ini
- Test discovery patterns
- Coverage settings
- Markers for test categories
- Output formatting

### .coveragerc
- Source paths
- Exclusion patterns
- Report formatting

### pyproject.toml
- Ruff linting rules
- MyPy type checking
- Black formatting

## Troubleshooting

### Tests Not Found
- Check test file naming: `test_*.py` or `*_test.py`
- Verify test directory structure
- Check `pytest.ini` configuration

### Import Errors
- Ensure `PYTHONPATH` includes repository root
- Check virtual environment activation
- Verify all dependencies installed

### Docker Issues
- Ensure Docker is running
- Check Docker Compose configuration
- Verify environment files exist

### Performance Issues
- Use `pytest-xdist` for parallel execution
- Profile slow tests with `pytest-benchmark`
- Consider test categorization (unit vs integration)

## Best Practices

1. **Write Fast Tests**: Unit tests should run in <100ms
2. **Mock External Dependencies**: Never make real network calls in unit tests
3. **Use Descriptive Names**: Test names should explain what's being tested
4. **Test Edge Cases**: Include error conditions and boundary values
5. **Keep Tests Independent**: Each test should be able to run in isolation
6. **Use Fixtures**: Share common test data and setup
7. **Verify Behavior**: Test the behavior, not the implementation
8. **Clean Up**: Remove temporary files and reset state after tests

## Test Categories and Markers

### Service Markers
- `@pytest.mark.discord`: Discord-related tests
- `@pytest.mark.stt`: Speech-to-text tests
- `@pytest.mark.tts`: Text-to-speech tests
- `@pytest.mark.llm`: Language model tests
- `@pytest.mark.orchestrator`: Orchestration tests

### Test Type Markers
- `@pytest.mark.unit`: Unit tests (fast, isolated)
- `@pytest.mark.component`: Component tests (with mocks)
- `@pytest.mark.integration`: Integration tests (require Docker)
- `@pytest.mark.e2e`: End-to-end tests (manual trigger)

### Special Markers
- `@pytest.mark.slow`: Slow tests (>1 second)
- `@pytest.mark.external`: Tests requiring external services
- `@pytest.mark.audio`: Tests involving audio processing

## Example Test Structure

```python
import pytest
from unittest.mock import Mock, patch
from services.discord.audio import AudioProcessor

class TestAudioProcessor:
    """Test audio processing functionality."""
    
    @pytest.mark.unit
    @pytest.mark.audio
    def test_process_audio_success(self, sample_audio_data):
        """Test successful audio processing."""
        processor = AudioProcessor()
        result = processor.process(sample_audio_data)
        assert result is not None
        assert result.duration > 0
    
    @pytest.mark.unit
    @pytest.mark.audio
    def test_process_audio_invalid_data(self):
        """Test audio processing with invalid data."""
        processor = AudioProcessor()
        with pytest.raises(ValueError):
            processor.process(b"invalid audio data")
    
    @pytest.mark.component
    @pytest.mark.discord
    def test_discord_audio_integration(self, mock_discord_client, sample_audio_data):
        """Test Discord audio integration."""
        with patch('services.discord.audio.AudioProcessor') as mock_processor:
            mock_processor.return_value.process.return_value = sample_audio_data
            # Test Discord audio handling
            pass
```

## Contact

For questions about testing infrastructure:
- Check existing issues in the repository
- Review the CI workflow configuration
- Consult the development team