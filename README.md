# Audio Orchestrator

[![CI][ci-badge]][ci-workflow]

A voice-first Discord assistant with speech-to-text, language orchestration, and text-to-speech services.
The bot captures voice from Discord, streams audio to faster-whisper, coordinates REST API tools, and plays back synthesized responses.

## Quickstart

-  **Set up environment files** using the [environment configuration guide](docs/getting-started/environment.md)
-  **Launch the stack** with `make run`
-  **Configure Discord** following the [runtime quickstart](docs/getting-started/runtime.md)
-  **Explore development workflows** via [local development guide](docs/getting-started/local-development.md)

## Architecture

The system consists of five core services working together to process voice input and generate intelligent responses:

-  **Discord Service** (`services/discord`)
  -  Captures Discord voice, detects wake phrases, forwards audio to STT, plays TTS output, and exposes REST API endpoints for automation.

-  **Speech-to-Text Service** (`services/stt`)
  -  Provides HTTP transcription with streaming-friendly latencies using faster-whisper for the Discord bot and other clients.

-  **Orchestrator Service** (`services/orchestrator`)
  -  Coordinates transcript processing, LangChain tool calls, and response planning. Routes reasoning requests to the LLM service.

-  **Language Model Service** (`services/flan`)
  -  Presents an OpenAI-compatible endpoint that can broker LangChain tool invocations and return reasoning output to the orchestrator.

-  **Text-to-Speech Service** (`services/bark`)
  -  Streams Bark-generated audio for orchestrator responses with authentication and rate limits.

## CI/CD Architecture

The project uses a modern multi-workflow CI architecture:

-  **Main CI**: Orchestrates change detection and routes to specialized workflows
-  **Core CI**: Fast Python feedback (lint, unit tests, component tests) - ~5-10 minutes
-  **Docker CI**: Base image building and service smoke tests - ~20-30 minutes
-  **Docs CI**: Documentation validation - ~2-3 minutes
-  **Security CI**: Dependency vulnerability scanning - ~5-10 minutes

Each workflow runs independently based on detected changes, providing faster feedback and better resource utilization.

## Key Features

-  **Optimized CI/CD** with parallel validation (5min feedback), per-service conditional builds (60-80% resource savings), native retry logic, automatic resource cleanup, and clear error reproduction guides
-  **Wake phrase detection** with configurable phrases and confidence thresholds
-  **Real-time audio processing** with voice activity detection and silence filtering
-  **REST API tool integration** for extending bot capabilities with external services
-  **Streaming audio pipeline** for low-latency voice interactions
-  **Modular architecture** with independent, containerized services
-  **Structured logging** with JSON output and correlation IDs
-  **Standardized health checks** with common module implementation across all services

## Development

-  **Linting & Testing**: Run `make lint` and `make test` for code quality checks
-  **Unit Tests**: `make test-unit` - Fast, isolated tests
-  **Component Tests**: `make test-component` - Internal logic with mocks
-  **Service-Specific Tests**: `make test-unit-service SERVICE=stt` or `make test-component-service SERVICE=orchestrator` - Run tests for a specific service
-  **Integration Tests**: `make test-integration` - Service HTTP boundaries via Docker Compose
  -  **Voice Pipeline Tests**: Complete end-to-end voice feedback loop validation
  -  **Audio Format Chain**: Format preservation and quality validation
  -  **Performance Tests**: Latency benchmarks and concurrent processing
  -  **Discord Integration**: REST API endpoints and service communication
  -  **Cross-Service Auth**: Authentication flow validation
-  **End-to-End Tests**: `pytest -m e2e` - Full system validation with real Discord (manual trigger)
-  **Workflow Validation**: Run `make workflows-validate` to validate GitHub Actions workflows with yamllint and actionlint
-  **Local Development**: Use `make run` to start services, `make logs` to follow output
-  **CI/CD**: Automated testing, linting, and security scanning on every push
-  **Documentation**: Comprehensive guides in the [documentation hub](docs/README.md)

### Build Optimization

**Enhanced Caching Architecture:**

The project now includes multi-layer caching for maximum build performance with build/push separation:

```bash
# Smart incremental builds (recommended for development - local-only, no auth required)
make docker-build  # Detects changes, rebuilds only affected services

# Enhanced caching builds (maximum cache utilization - local-only)
make docker-build-services-parallel     # Multi-source caching (GitHub Actions + registry)

# Single service builds
make docker-build-service SERVICE=stt  # Build specific service only

# Push to registry (after building locally)
make docker-push-base-images    # Push base images
make docker-push-services       # Push service images
make docker-push-all           # Push all images (base, services, toolchain)
```

**Build vs Push Separation:**

All build operations default to **local-only** (no authentication required):

  -  Base images: `make docker-build-base` (local-only)
  -  Service images: `make docker-build-services-parallel` (local-only)
  -  Toolchain images: `make build-test-image`, `make build-lint-image`, `make build-security-image` (local-only)

Push operations are **explicit and separate** (requires authentication):

  -  `make docker-push-base-images` - Push base images
  -  `make docker-push-services` - Push service images
  -  `make push-test-image`, `make push-lint-image`, `make push-security-image` - Push toolchain images
  -  `make docker-push-all` - Push everything

This separation allows fast local iteration without authentication, while CI/CD workflows can use explicit push targets.

**Performance Improvements:**

-  **Local builds**: 80-95% faster with shared pip cache volumes
-  **CI builds**: 60-70% faster with service-level registry caching
-  **Cache hit rates**: Service images now achieve 70-85% cache hits (up from 20-30%)
-  **Parallel builds**: All services build in parallel in CI workflows

**Build Time Expectations:**

| Scenario | Before | After | Improvement |
|----------|--------|-------|-------------|
| Single service change | 8-12 min | 1-2 min | 80-90% |
| Common library change | 8-12 min | 2-3 min | 70-80% |
| Base image change | 12-15 min | 3-5 min | 60-70% |
| No changes | N/A | instant | 100% (cache hit) |

## Documentation

Navigate deeper using the [documentation hub](docs/README.md):

-  **Getting Started** — Onboarding, environment management, troubleshooting
-  **Architecture** — System overview, service deep dives, REST API integrations
-  **Operations** — Runbooks, observability, security practices
-  **Reference** — Configuration catalog and API appendices
-  **Roadmaps & Reports** — Strategic plans and implementation reviews

## Contributing

This project follows the [Contributor Playbook](AGENTS.md) for development workflows, code quality standards, and contribution guidelines. All changes must pass tests and linters before merging.

---

[ci-badge]: https://github.com/gabrielpreston/audio-orchestrator/actions/workflows/main-ci.yaml/badge.svg
[ci-workflow]: https://github.com/gabrielpreston/audio-orchestrator/actions/workflows/main-ci.yaml
