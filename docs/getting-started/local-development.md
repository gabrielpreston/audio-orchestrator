---
title: Local Development Workflows
author: Discord Voice Lab Team
status: active
last-updated: 2025-10-18
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Getting Started ▸ Local Development Workflows

# Local Development Workflows

Follow these steps to run services locally, lint the codebase, and execute automated tests.

## Task Runners

This project supports both Makefile and Taskfile for task automation. Both provide identical functionality:

### Makefile Commands

| Command | Description |
| --- | --- |
| `make run` | Build and launch the Discord, STT, Orchestrator, LLM, and TTS services via Docker Compose. |
| `make stop` | Stop running containers without removing volumes. |
| `make logs [SERVICE=name]` | Stream JSON logs for the entire stack or a single service. |
| `make lint` | Run containerized linting for Python, Dockerfiles, Markdown, and YAML. |
| `make lint-fix` | Apply `black` and `isort` formatting in the lint container. |
| `make lint-local` | Run lint tools installed on the host machine. |
| `make test` | Execute `pytest` inside the tester container. |
| `make test-local` | Run `pytest` on the host; set `PYTEST_ARGS` for filtering. |

### Taskfile Commands

| Command | Description |
| --- | --- |
| `task run` | Build and launch the Discord, STT, Orchestrator, LLM, and TTS services via Docker Compose. |
| `task stop` | Stop running containers without removing volumes. |
| `task logs [SERVICE=name]` | Stream JSON logs for the entire stack or a single service. |
| `task lint` | Run containerized linting for Python, Dockerfiles, Markdown, and YAML. |
| `task lint-fix` | Apply `black` and `isort` formatting in the lint container. |
| `task lint-ci` | Run lint tools installed on the host machine. |
| `task test` | Execute `pytest` inside the tester container. |
| `task test-local` | Run `pytest` on the host; set `PYTEST_ARGS` for filtering. |

> **Note**: Both Makefile and Taskfile provide identical functionality. Choose whichever you prefer. Taskfile offers better cross-platform support and more readable task definitions.

## Development Loop

1. Start the stack with `make run` (or `task run`) and confirm voice connection in Discord.
2. Tail logs per service (`make logs SERVICE=discord`) to validate wake phrase detection and transcription flow.
3. Iterate on code changes; rerun `make run` to rebuild containers when dependencies change.
4. Run `make lint` before pushing to catch style or formatting issues.
5. Use `make test` to verify the automated suite; pass `PYTEST_ARGS` to scope runs during development.

## Tips

- Keep the lint container warm by running `make lint` once before frequent edits; subsequent runs reuse the cached image.
- For debugging outside Docker, export `PYTHONPATH=$PWD` so Python resolves the monorepo modules.
- Use feature branches and small commits to keep diffs reviewable; reference affected docs in your PR summary.
- Capture notable manual checks (audio latency, MCP tool coverage) in the [reports section](../reports/README.md).
