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
| `make lint-local` | Run lint tools installed on the host machine. |
| `make test` | Execute `pytest` inside the tester container. |
| `make test-local` | Run `pytest` on the host; set `PYTEST_ARGS` for filtering. |
| `make workflows-validate` | Validate GitHub Actions workflows with yamllint and actionlint (containerized). |
| `make workflows-validate-syntax` | Validate workflow YAML syntax only (containerized yamllint). |
| `make workflows-validate-actionlint` | Validate workflows with actionlint (containerized actionlint). |
| `make validate-all` | Run all validation checks (lint, test, security, docs, workflows). |

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
-  Capture notable manual checks (audio latency, MCP tool coverage) in the [reports section](../reports/README.md).

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
