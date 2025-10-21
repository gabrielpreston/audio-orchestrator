# Audio-First AI Orchestrator Platform

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Linting: flake8](https://img.shields.io/badge/linting-flake8-yellow.svg)](https://flake8.pycqa.org/)
[![Type checking: mypy](https://img.shields.io/badge/type%20checking-mypy-blue.svg)](https://mypy.readthedocs.io/)
[![Tests: pytest](https://img.shields.io/badge/tests-pytest-green.svg)](https://pytest.org/)

A modular, audio-first AI orchestration platform designed for real-time voice interactions with pluggable I/O adapters and intelligent agent routing.

## Architecture Overview

The platform consists of several key components:

- **I/O Adapters**: Pluggable interfaces for audio input/output (Discord, WebRTC, etc.)
- **Audio Pipeline**: Real-time audio processing, conversion, and transcription
- **Orchestrator Engine**: Core coordination between input, processing, and output
- **Agent System**: Modular AI agents for different conversation contexts
- **Persistence Layer**: Session management and conversation history storage

### Directory Structure

```
audio-orchestrator/
├── bot/                    # Main application entry points
├── config/                 # Configuration management
├── io_adapters/           # Audio I/O adapter implementations
├── audio_pipeline/        # Audio processing and conversion
├── orchestrator/          # Core orchestration engine
├── agents/                # AI agent implementations
├── services/              # External service integrations (STT, TTS)
├── persistence/           # Data storage interfaces
├── monitoring/            # Metrics and observability
├── tests/                 # Test suites
└── docs/                  # Documentation
```

## Quick Start

### Prerequisites

- Python 3.11+
- FFmpeg (for audio processing)
- Discord Bot Token (for Discord adapter)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/audio-orchestrator/platform.git
cd audio-orchestrator
```

2. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -e .
pip install -e ".[dev]"  # For development dependencies
```

4. Create configuration:
```bash
cp .env.sample .env
# Edit .env with your Discord token and other settings
```

5. Run the application:
```bash
python -m bot.main
```

## Configuration

The platform uses environment variables for configuration. Copy `.env.sample` to `.env` and customize:

```env
# Discord Configuration
DISCORD_TOKEN=your_discord_bot_token

# Database
DB_URL=sqlite+aiosqlite:///./audio_orchestrator.db

# Audio Settings
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=1
FFMPEG_PATH=ffmpeg

# Logging
LOG_LEVEL=INFO
```

## Development

### Code Quality

The project enforces code quality through automated tools:

```bash
# Format code
black .

# Lint code
flake8 .

# Type checking
mypy .

# Run tests
pytest
```

### Adding New Adapters

See [docs/adding_adapter.md](docs/adding_adapter.md) for guidance on implementing new I/O adapters.

### Adding New Agents

See [docs/adding_agent.md](docs/adding_agent.md) for guidance on creating new AI agents.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and quality checks
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Roadmap

- [ ] WebRTC adapter for browser-based audio
- [ ] Advanced agent routing with ML-based selection
- [ ] Distributed scaling support
- [ ] Real-time audio quality metrics
- [ ] Plugin system for custom agents

## Support

- Documentation: [audio-orchestrator.dev/docs](https://audio-orchestrator.dev/docs)
- Issues: [GitHub Issues](https://github.com/audio-orchestrator/platform/issues)
- Discussions: [GitHub Discussions](https://github.com/audio-orchestrator/platform/discussions)