---
title: Taskfile Migration Guide
author: Discord Voice Lab Team
status: active
last-updated: 2025-01-27
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Getting Started ▸ Taskfile Migration Guide

# Taskfile Migration Guide

This guide explains the migration from Makefile to Taskfile and how to use both task runners side by side.

## Overview

The `discord-voice-lab` project now supports both Makefile and Taskfile for task automation. Both provide identical functionality, allowing teams to choose their preferred task runner while maintaining full feature parity.

## Why Taskfile?

Taskfile offers several advantages over traditional Makefiles:

- **Better cross-platform support** - Works consistently across Windows, macOS, and Linux
- **More readable syntax** - YAML-based configuration is easier to understand and maintain
- **Better error handling** - More descriptive error messages and better debugging
- **Dependency management** - Cleaner task dependencies and parallel execution
- **Variable handling** - More flexible variable substitution and templating
- **No shell dependencies** - Doesn't rely on specific shell features

## Installation

### Install Taskfile

```bash
# Using Go (recommended)
go install github.com/go-task/task/v3/cmd/task@latest

# Using Homebrew (macOS)
brew install go-task/tap/go-task

# Using Scoop (Windows)
scoop install task

# Using Chocolatey (Windows)
choco install go-task

# Using package managers
# See: https://taskfile.dev/installation/
```

### Verify Installation

```bash
task --version
# Should output: 3.x.x
```

## Command Mapping

All Makefile commands have equivalent Taskfile commands:

| Makefile | Taskfile | Description |
|----------|----------|-------------|
| `make run` | `task run` | Start docker-compose stack |
| `make stop` | `task stop` | Stop containers |
| `make logs` | `task logs` | Tail logs |
| `make test` | `task test` | Run tests |
| `make lint` | `task lint` | Run linting |
| `make clean` | `task clean` | Clean artifacts |
| `make help` | `task help` | Show help |

## Usage Examples

### Basic Commands

```bash
# Start the development stack
task run

# View logs
task logs

# View logs for specific service
task logs SERVICE=discord

# Run tests
task test

# Run specific tests
task test-specific PYTEST_ARGS='-k test_audio'

# Run linting
task lint

# Clean up
task clean
```

### Advanced Usage

```bash
# Build specific service
task docker-build-service SERVICE=discord

# Run integration tests
task test-integration

# Generate coverage report
task test-coverage

# Install development dependencies
task install-dev-deps

# Download models
task models-download
```

## Environment Variables

Taskfile supports the same environment variables as Makefile:

```bash
# Set pytest arguments
task test PYTEST_ARGS='-v --tb=short'

# Set service for targeted operations
task logs SERVICE=stt
task docker-shell SERVICE=orchestrator
```

## Parallel Usage

You can use both Makefile and Taskfile in the same project:

```bash
# Mix and match as needed
make run
task logs
make test
task clean
```

Both task runners:
- Use the same Docker Compose configuration
- Share the same environment variables
- Produce identical results
- Can be used interchangeably

## Migration Strategy

### Phase 1: Parallel Usage (Current)
- Both Makefile and Taskfile are maintained
- Teams can choose their preferred tool
- Full feature parity is maintained
- Documentation covers both approaches

### Phase 2: Gradual Adoption
- New team members can start with Taskfile
- Existing workflows continue with Makefile
- No forced migration required

### Phase 3: Future Consideration
- Evaluate adoption rates and team preferences
- Consider deprecating Makefile if Taskfile adoption is high
- Maintain backward compatibility during transition

## Troubleshooting

### Common Issues

**Taskfile not found:**
```bash
# Install Taskfile
go install github.com/go-task/task/v3/cmd/task@latest

# Add to PATH
export PATH=$PATH:$(go env GOPATH)/bin
```

**Docker Compose not detected:**
```bash
# Taskfile uses the same detection as Makefile
# Ensure Docker Compose is installed and accessible
docker compose version
```

**Permission denied on scripts:**
```bash
# Make helper scripts executable
chmod +x scripts/docker-compose-detect.sh
```

### Getting Help

```bash
# Show all available tasks
task help

# Show specific task details
task --list

# Run with verbose output
task --verbose run
```

## Configuration

The Taskfile configuration is in `Taskfile.yml` at the project root. Key features:

- **Variables**: Defined in the `vars` section
- **Tasks**: Each task has a description and command list
- **Dependencies**: Tasks can depend on other tasks
- **Templates**: Support for variable substitution

## Contributing

When adding new tasks:

1. **Add to both Makefile and Taskfile** to maintain parity
2. **Update documentation** to include both command formats
3. **Test both implementations** to ensure identical behavior
4. **Follow naming conventions** for consistency

## Resources

- [Taskfile Documentation](https://taskfile.dev/)
- [Taskfile Examples](https://github.com/go-task/task/tree/main/examples)
- [Makefile Reference](https://www.gnu.org/software/make/manual/make.html)
- [Project Makefile](./Makefile) - Current Makefile implementation
- [Project Taskfile](./Taskfile.yml) - Current Taskfile implementation