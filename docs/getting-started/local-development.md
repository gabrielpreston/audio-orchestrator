---
title: Local Development Workflows
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-20
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Getting Started ▸ Local Development Workflows

# Local Development Workflows

Follow these steps to run services locally, lint the codebase, and execute automated tests.

## Make Targets

| Command | Description |
| --- | --- |
| `make run` | Build and launch the Discord, STT, Orchestrator, LLM, and TTS services via Docker Compose. |
| `make stop` | Stop running containers without removing volumes. |
| `make logs [SERVICE=name]` | Stream JSON logs for the entire stack or a single service. |
| `make lint` | Run containerized linting for Python, Dockerfiles, Markdown, and YAML. |
| `make lint-fix` | Apply Ruff formatting in the lint container. |
| `make docker-build-service SERVICE=name` | Build a specific service (set SERVICE=name). |
| `make test-integration` | Run integration tests (requires Docker Compose). |

## Development Loop

-  Start the stack with `make run` and confirm voice connection in Discord.
-  Tail logs per service (`make logs SERVICE=discord`) to validate wake phrase detection and transcription flow.
-  Iterate on code changes; rerun `make run` to rebuild containers when dependencies change.
-  Run `make lint` before pushing to catch style or formatting issues.
-  Use `make test` to verify the automated suite; pass `PYTEST_ARGS` to scope runs during development.

## Tips

-  Keep the lint container warm by running `make lint` once before frequent edits; subsequent runs reuse the cached image.
-  For debugging outside Docker, export `PYTHONPATH=$PWD` so Python resolves the monorepo modules.
-  Use feature branches and small commits to keep diffs reviewable; reference affected docs in your PR summary.
-  Capture notable manual checks (audio latency, tool coverage) in the [reports section](../reports/README.md).

## Python Development Environment

The project uses a **single root virtual environment** (`.venv`) for all local development:

```bash
# Create and activate virtual environment (first time only)
python3 -m venv .venv
source .venv/bin/activate

# Install all development dependencies
pip install -r services/requirements-dev.txt
pip install -r services/requirements-base.txt

# Install all service-specific dependencies
pip install -r services/discord/requirements.txt
pip install -r services/stt/requirements.txt
pip install -r services/orchestrator_enhanced/requirements.txt
pip install -r services/guardrails/requirements.txt
pip install -r services/tts_bark/requirements.txt
pip install -r services/audio_processor/requirements.txt
pip install -r services/testing_ui/requirements.txt
pip install -r services/monitoring_dashboard/requirements.txt
pip install -r services/security/requirements.txt
pip install -r services/linter/requirements.txt
pip install -r services/tester/requirements.txt
```

**Why single environment?**

-  Services run in Docker containers (each with isolated Python environments)
-  Local `.venv` is for development tools: linting, testing, IDE support
-  Eliminates virtual environment confusion in IDEs
-  Matches industry best practices for microservices monorepos

**IDE Configuration:**

The workspace is configured for Cursor IDE with:

-  **Language Server**: Uses Cursor's built-in Python language server (not Pylance)
-  **PYTHONPATH**: Automatically configured to include `services/` and `services/common/`
-  **Python Interpreter**: Points to root `.venv/bin/python`
-  **Import Resolution**: All service imports resolve correctly across the monorepo

## Workflow Validation

Validate GitHub Actions workflows locally before committing:

-  **`make workflows-validate`** — Runs yamllint and actionlint validation (containerized, no local installation required)
-  **`make workflows-validate-syntax`** — YAML syntax only (containerized yamllint)
-  **`make workflows-validate-actionlint`** — GitHub Actions static analysis (containerized actionlint)

### How It Works

All workflow validation uses the containerized linting infrastructure:

-  **yamllint** validates YAML syntax and formatting
-  **actionlint** validates GitHub Actions semantics, expressions, and action versions

No local tool installation required - everything runs in Docker containers.

### Manual Tool Installation (Optional)

If you want to run validation tools directly on your host:

**actionlint**:

```bash
go install github.com/rhysd/actionlint/cmd/actionlint@latest
```

**yamllint**:

```bash
pip install yamllint
```

The containerized approach (`make workflows-validate`) is recommended as it ensures consistency with CI.
