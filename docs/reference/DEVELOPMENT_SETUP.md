---
title: Development Environment Setup
description: Multi-virtual environment setup for the discord-voice-lab project
last-updated: 2025-10-19
---

# Development Environment Setup

This document describes the development setup for the `discord-voice-lab` project.

## 🏗️ Architecture Overview

The project uses a **Docker-based development approach**:

- **Docker Compose**: All services run in containers for consistency
- **Shared utilities**: `services.common` library provides shared functionality
- **Service isolation**: Each service runs in its own container with specific dependencies
- **Optimized builds**: CI uses shared base images and parallel builds for 80-90% faster build times

## 📁 Directory Structure

```text
discord-voice-lab/
├── .vscode/settings.json           # Root workspace settings
├── discord-voice-lab.code-workspace # Multi-root workspace file
├── docker-compose.yml              # Service orchestration
├── services/
│   ├── common/                     # Shared library
│   ├── discord/                    # Discord service
│   ├── stt/                        # Speech-to-text service
│   ├── llm/                        # Language model service
│   ├── orchestrator/               # Orchestrator service
│   └── tts/                        # Text-to-speech service
```

## 🚀 Getting Started

### 1. Open the Workspace

```bash
# Open the workspace file in Cursor/VS Code
cursor discord-voice-lab.code-workspace
```

This will open the project with proper Python path configuration for the monorepo structure.

### 2. Start the Development Environment

```bash
# Start all services with Docker Compose
make run

# View logs
make logs

# Stop services
make stop
```

### 3. Development Workflow

When working on the project:

1. **Use Docker Compose** for running services
2. **Edit code locally** - changes are reflected in containers
3. **Use make targets** for common operations (test, lint, etc.)

## 🔧 Build Optimization

The project includes optimized Docker builds for CI/CD:

- **Local Development**: Uses standard `make` targets (`make run`, `make test`, `make lint`)
- **CI/CD**: Uses optimized targets (`make docker-build-ci`, `make test-ci`, `make lint-ci`)
- **Base Images**: Shared base images reduce build times by 80-90%
- **Parallel Builds**: Services build in parallel for maximum efficiency

## 🔧 Environment Details

### Docker-Based Development

**Purpose**: Consistent development environment across all services

**Contains**:

- Service-specific Dockerfiles with dependencies
- Shared base requirements (`requirements-base.txt`)
- Development tools (`requirements-dev.txt`)

**Usage**: All services run in containers for consistency

### Service Dependencies

Each service has its own `requirements.txt` with:

**Discord Service**:

- `discord.py[voice]`, `discord-ext-voice_recv`, `PyNaCl`, `rapidfuzz`, `webrtcvad`

**STT Service**:

- `faster-whisper`, `python-multipart`

**LLM Service**:

- `llama-cpp-python`

**Orchestrator Service**:

- `mcp`, `instructor`

**TTS Service**:

- `piper-tts`, `prometheus_client`

## 🎯 Development Workflows

### Working on a Single Service

```bash
# Start all services
make run

# View logs for specific service
make logs SERVICE=discord

# Run tests for specific service
make test SERVICE=discord
```

### Working on Shared Library

```bash
# Edit services/common/ files
# Changes are reflected in running containers
# Use make targets for testing
```

### Full-Stack Development

```bash
# Start all services
make run

# Run all tests
make test

# Run linting
make lint

# Stop services
make stop
```

## 🔍 Cursor/VS Code Configuration

### Workspace Configuration

The `discord-voice-lab.code-workspace` file provides:

- **Proper Python path configuration** for the monorepo structure
- **Shared settings** across all services
- **Import resolution** for `services.common` library

### Root Settings

The `.vscode/settings.json` file provides:

```json
{
    "python.analysis.extraPaths": [
        "services/common",
        "."
    ],
    "python.analysis.autoImportCompletions": true,
    "python.analysis.typeCheckingMode": "basic"
}
```

## 🧪 Testing the Setup

### Test Service Health

```bash
# Start all services
make run

# Test service health
curl http://localhost:8000/health/ready  # Orchestrator
curl http://localhost:9000/health/ready  # STT
curl http://localhost:7000/health/ready  # TTS
```

### Test Development Environment

```bash
# Run tests
make test

# Run linting
make lint

# Check service logs
make logs
```

## 🛠️ Troubleshooting

### Service Issues

If services aren't starting:

1. **Check Docker**: Ensure Docker is running
2. **Check logs**: `make logs` to see service logs
3. **Restart services**: `make stop && make run`

### Import Errors

If you get `ModuleNotFoundError: No module named 'services'`:

1. **Check Python path**: Ensure the project root is in PYTHONPATH
2. **Check workspace**: Ensure you're in the correct workspace folder
3. **Reload window**: `Ctrl+Shift+P` → "Developer: Reload Window"

### Cursor/VS Code Issues

If IntelliSense isn't working:

1. **Reload window**: `Ctrl+Shift+P` → "Developer: Reload Window"
2. **Check workspace**: Ensure you're in the correct workspace folder
3. **Check Python path**: Verify Python path configuration

## 📋 Benefits

### ✅ Advantages

- **Consistent environment**: All services run in Docker containers
- **Service isolation**: Each service runs in its own container
- **Shared utilities**: `services.common` available everywhere
- **Easy debugging**: Service-specific containers prevent conflicts
- **Scalable**: Easy to add new services
- **Production parity**: Development environment matches production

### 🎯 Use Cases

- **Service development**: Work on one service without affecting others
- **Dependency management**: Each service manages its own dependencies
- **Testing**: Test services independently
- **Debugging**: Isolate issues to specific services
- **Team development**: Different developers can work on different services

## 🔄 Maintenance

### Adding New Dependencies

**For a specific service**:

```bash
# Add to service requirements.txt
echo "new-package==1.0.0" >> services/[service-name]/requirements.txt

# Rebuild service container
make docker-build SERVICE=[service-name]
```

**For shared dependencies**:

```bash
# Add to requirements-base.txt
echo "new-package==1.0.0" >> requirements-base.txt

# Rebuild all containers
make docker-build
```

### Updating Dependencies

**Service-specific**:

```bash
# Update service requirements.txt
# Rebuild service container
make docker-build SERVICE=[service-name]
```

**Global**:

```bash
# Update requirements-base.txt
# Rebuild all containers
make docker-build
```

This setup provides the best of both worlds: complete service isolation with shared library access, optimized for the `discord-voice-lab` project architecture using Docker containers.
