# Discord Voice Lab

[![CI][ci-badge]][ci-workflow]

The Discord Voice Lab packages a voice-first Discord assistant alongside speech-to-text (STT),
language-orchestrator, and text-to-speech (TTS) services. The bot captures voice from Discord,
streams audio to faster-whisper, coordinates Model Context Protocol (MCP) tools, and plays back
synthesized responses. The Python bot handles audio capture, wake-word filtering, transcription
requests, and exposes Discord control tools over MCP.

## Run the Stack

1. Provision environment files using the
   [environment configuration guide](docs/getting-started/environment.md).
2. Launch the stack with Docker Compose following the
   [runtime quickstart](docs/getting-started/runtime.md).
3. Explore linting, testing, and iterative workflows via
   [local development workflows](docs/getting-started/local-development.md).

## Documentation Index

Navigate deeper using the [documentation hub](docs/README.md):

- Getting started — onboarding, environment management, troubleshooting.
- Architecture — system overview, service deep dives, MCP integrations.
- Operations — runbooks, observability, security practices.
- Reference — configuration catalog and API appendices.
- Roadmaps & reports — strategic plans and implementation reviews.
- Proposals — active design discussions with lifecycle metadata.

Keep repository updates in sync with the relevant documentation section to maintain a single
source of truth.

### Documentation freshness checks

- Run `make docs-verify` after editing any guide under `docs/` to confirm front matter,
  index tables, and version history entries align with the new content.
- Use `make docs-verify ARGS="--allow-divergence"` (or call
  `./scripts/verify_last_updated.py --allow-divergence`) only when you intentionally keep a
  `last-updated` value offset from the most recent changes and have documented the rationale in
  the affected page.

## Structured logging

All Python services share the `services.common.logging` helpers to emit JSON logs
to stdout by default. Configure verbosity with `LOG_LEVEL` (e.g., `DEBUG`,
`INFO`) and toggle JSON output via `LOG_JSON`. Docker Compose surfaces these
logs through `docker-compose logs`, making it easy to aggregate or ship them to
your preferred observability stack.

## Voice connection tuning

The Discord bot now retries voice handshakes automatically if the gateway or media edge stalls.
Adjust retry behavior with `DISCORD_VOICE_CONNECT_TIMEOUT`, `DISCORD_VOICE_CONNECT_ATTEMPTS`,
`DISCORD_VOICE_RECONNECT_BASE_DELAY`, and `DISCORD_VOICE_RECONNECT_MAX_DELAY` in
`services/discord/.env.service`.

## Security & Token Management

Rotate AUTH_TOKEN values across all services with the automated script:

```bash
make rotate-tokens          # Rotate all tokens
make rotate-tokens-dry-run  # Preview changes
make validate-tokens        # Check consistency
```

See the [security guidelines](docs/operations/security.md) for comprehensive credential management practices.

## Wake phrase detection

Wake phrase matching now tolerates extra punctuation or spacing in STT transcripts. Ignored
segments log a short `transcript_preview` so you can inspect what was heard without cranking
global log levels.

## Quickstart — Docker Compose services

Populate each `services/**/.env.service` file (see `.env.sample`) with
production-ready values, then adjust `.env.docker` if you need custom UID/GID
ownership for mounted volumes. When everything is in place, build and run the
stack:

```bash
make run
```

This brings up the Discord bot, STT, and orchestrator containers defined in
`docker-compose.yml`. Use `make logs` to follow their output and `make stop` to
tear them down.

## Where to look next

- `services/discord/` — Python Discord interface packages (audio pipeline, wake
  detection, transcription client, MCP server, Discord client wiring).
- `services/stt/` — FastAPI-based STT service using faster-whisper.
- `services/llm/` — lightweight orchestrator service exposing OpenAI-compatible
  APIs.
- `services/tts/` — FastAPI-based text-to-speech service backed by Piper that
  streams synthesized audio for orchestrator responses.
- `docs/` — architecture and development guides shared between runtimes.

## MCP tools

The Discord service exposes a small set of MCP tools for orchestration. The
`discord.send_message` tool now works with both traditional text channels and
voice channel chats. Pass either channel ID and the bot will post the supplied
content directly into the active conversation. Pair this with
`discord.join_voice` to bring the bot into the target voice channel before
sending follow-up text.

That's all you need to get started. Update environment defaults and
documentation in tandem with any behavior changes to keep the project
consistent.

## Continuous integration

GitHub Actions now mirrors the local Makefile workflow so every push and pull
request to `main` exercises the same checks you run locally:

- `Lint` — executes `make lint-ci`, covering Black, isort, Ruff, MyPy,
  Hadolint, Yamllint, Checkmake, and Markdownlint.
- `Tests` — calls `make test-local` with the repository root on `PYTHONPATH`
  so pytest behavior matches the `services/tester` container.
- `Docker smoke` — runs `make docker-smoke` to render the Compose config, list
  services, and build all images with BuildKit enabled.
- `Security scan` — runs `pip-audit` against every `services/**/requirements.txt`
  file and uploads JSON reports as workflow artifacts.

### Reproducing CI locally

1. Pull the latest `main` branch and install host dependencies (`pip install`
   the lint/test packages, `npm install -g markdownlint-cli`, `go install
   github.com/checkmake/checkmake/cmd/checkmake@latest`, and download the
   Hadolint binary).
2. Run `python scripts/prepare_env_files.py` to materialize any missing
   `.env.common`, `.env.docker`, and `services/**/.env.service` files expected by
   `docker-compose`. Pass `--force` if you want to regenerate files that already
   exist (the CI workflow does this so every run starts from the sample defaults).
3. Run `make lint-ci`, `make test-local`, and `make docker-smoke` in that
   order to match the GitHub Actions jobs.
4. When a job fails in CI, download the corresponding artifact (`pytest-log`,
   `docker-smoke-artifacts`, or `pip-audit-reports`) from the Actions run for
   additional diagnostics.

## Linting

Run `make lint` (defaults to `make lint-docker`) to exercise all static checks inside a purpose-built container
(`services/linter/`). Docker builds the `discord-voice-lab/lint` image (cached
after the first run) and executes:

- Python: `black`, `isort`, `ruff`, and `mypy`
- Dockerfiles: `hadolint` (auto-discovers all Dockerfiles)
- YAML files: `yamllint` (docker-compose.yml + GitHub workflows)
- Makefile: `checkmake`
- Markdown: `markdownlint` (auto-discovers all docs)

Need to apply auto-formatting from the containerized toolchain? Run `make lint-fix`
to execute `black` and `isort` inside the lint image with repository binds.

For CI environments or local debugging without Docker, use `make lint-ci` to run the same
toolchain with host-installed binaries. Install the Python packages via
`pip install -r requirements-dev.txt`, the Dockerfile linter with
`hadolint`, the Makefile linter using
`go install github.com/checkmake/checkmake/cmd/checkmake@v0.2.2`, and the
Markdown linter with `npm install -g markdownlint-cli@0.39.0`.

## Testing

Run `make test` to execute the Python test suite inside a dedicated container
(`services/tester/`). Docker builds the `discord-voice-lab/test` image (cached
after the first run), mounts the repository into `/workspace`, and runs
`pytest`. Pass arguments to `pytest` by setting `PYTEST_ARGS`, for example
`make test PYTEST_ARGS="-k wake_phrase"`.

Need to debug with locally installed tooling? Use `make test-local` to run the
same `pytest` invocation on the host. Set `PYTHONPATH` to include the repository
root if you call `pytest` directly.

[ci-badge]: https://github.com/gabrielpreston/discord-voice-lab/actions/workflows/ci.yaml/badge.svg
[ci-workflow]: https://github.com/gabrielpreston/discord-voice-lab/actions/workflows/ci.yaml
