# Discord Voice Lab

[![CI][ci-badge]][ci-workflow]

A voice-first Discord assistant with speech-to-text, language orchestration, and text-to-speech services. The bot captures voice from Discord, streams audio to faster-whisper, coordinates Model Context Protocol (MCP) tools, and plays back synthesized responses.

## Quickstart

1. **Set up environment files** using the [environment configuration guide](docs/getting-started/environment.md)
2. **Launch the stack** with `make run`
3. **Configure Discord** following the [runtime quickstart](docs/getting-started/runtime.md)
4. **Explore development workflows** via [local development guide](docs/getting-started/local-development.md)

## Architecture

The system consists of five core services working together to process voice input and generate intelligent responses:

**Discord Service** (`services/discord`) - Captures Discord voice, detects wake phrases, forwards audio to STT, plays TTS output, and exposes MCP tools for automation.

**Speech-to-Text Service** (`services/stt`) - Provides HTTP transcription with streaming-friendly latencies using faster-whisper for the Discord bot and other clients.

**Orchestrator Service** (`services/orchestrator`) - Coordinates transcript processing, MCP tool calls, and response planning. Routes reasoning requests to the LLM service.

**Language Model Service** (`services/llm`) - Presents an OpenAI-compatible endpoint that can broker MCP tool invocations and return reasoning output to the orchestrator.

**Text-to-Speech Service** (`services/tts`) - Streams Piper-generated audio for orchestrator responses with authentication and rate limits.

## Key Features

- **Optimized CI/CD** with parallel validation (5min feedback), per-service conditional builds (60-80% resource savings), native retry logic, automatic resource cleanup, and clear error reproduction guides
- **Wake phrase detection** with configurable phrases and confidence thresholds
- **Real-time audio processing** with voice activity detection and silence filtering
- **MCP tool integration** for extending bot capabilities with external services
- **Streaming audio pipeline** for low-latency voice interactions
- **Modular architecture** with independent, containerized services
- **Structured logging** with JSON output and correlation IDs
- **Health checks** and circuit breakers for service resilience

## Development

- **Linting & Testing**: Run `make lint` and `make test` for code quality checks
- **Local Development**: Use `make run` to start services, `make logs` to follow output
- **CI/CD**: Automated testing, linting, and security scanning on every push
- **Documentation**: Comprehensive guides in the [documentation hub](docs/README.md)

## Documentation

Navigate deeper using the [documentation hub](docs/README.md):

- **Getting Started** — Onboarding, environment management, troubleshooting
- **Architecture** — System overview, service deep dives, MCP integrations  
- **Operations** — Runbooks, observability, security practices
- **Reference** — Configuration catalog and API appendices
- **Roadmaps & Reports** — Strategic plans and implementation reviews

## Contributing

This project follows the [Contributor Playbook](AGENTS.md) for development workflows, code quality standards, and contribution guidelines. All changes must pass tests and linters before merging.

---

[ci-badge]: https://github.com/gabrielpreston/discord-voice-lab/actions/workflows/ci.yaml/badge.svg
[ci-workflow]: https://github.com/gabrielpreston/discord-voice-lab/actions/workflows/ci.yaml
