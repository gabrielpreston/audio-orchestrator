# Contributor Guidelines for `discord-voice-lab`

This repository houses a Python-based Discord voice bot along with supporting FastAPI speech-to-text (STT) and lightweight orchestration services, helper scripts, and documentation. Follow the conventions below for any change you make anywhere in this repo.

## Repository map
- `services/discord/` — Python package containing the Discord voice interface (audio pipeline, wake detection, transcription client, MCP tooling).
- `services/stt/` — Python FastAPI app for faster-whisper inference (Dockerfile + app + requirements).
- `services/llm/` — Python FastAPI app exposing an OpenAI-compatible endpoint backed by local tooling.
- `scripts/` — Bash helpers invoked by `make` (dev runners, STT smoke tests). Keep these POSIX-friendly when possible.
- `docs/` — Markdown guides for architecture, onboarding, configuration, and operations. Update the relevant guide whenever you change behavior or workflows.
- Audio fixtures in repo root (`test.wav`, `test_speech_16k.wav`) support automated/manual verification of the STT pipeline.

## Build & local tooling
- Prefer the `Makefile` targets over ad-hoc commands so CI and local workflows stay aligned: `make run`, `make stop`, `make logs`, `make dev-discord`, `make dev-stt`, `make clean`, and `make docker-clean` are the common entry points.
- `scripts/run_stt.sh` is used by the `make dev-stt` helper; keep it idempotent and ensure it respects `.env.local` when sourced.
- `scripts/test_stt.sh` performs a curl-based smoke test (optionally booting the STT container); update it alongside any API or port changes so developers can quickly validate audio ingestion.

## Configuration & environment files
- `.env.local` powers local `make dev-*` runs and `.env.docker` feeds Docker Compose. When you add or rename environment variables, update both files (or their documented examples) plus `README.md` and any affected guide in `docs/`.
- Keep defaults and validation logic in sync between Python components (`services/discord/config.py`, `services/stt/app.py`, `services/llm/*`). Document any breaking changes in configuration.

## Docker & Compose
- `docker-compose.yml` must continue to work with both `docker compose` (plugin) and the legacy `docker-compose` binary. Test changes with `make run`.
- Respect the BuildKit toggles already wired in the `Makefile`. If you introduce new images or services, add matching `Makefile` targets or extend existing ones instead of duplicating shell commands.
- Ensure any new container mounts or env files remain compatible with the existing `.env.docker` and local volume layout (`./logs`, `./.wavs`).

## Discord interface (`services/discord`)
- Stick to PEP 8 style and add type hints for new functions, request models, and helper utilities.
- Use the shared `services.common.logging` helpers to emit structured logs; prefer contextual metadata (`extra={...}`) over string interpolation.
- Keep FastAPI/HTTP client interactions resilient—propagate timeouts and retries through configuration.
- Run relevant unit or integration tests (when available) and capture smoke-test output (manual Discord runs, STT interactions) in your summary when submitting changes that affect runtime behavior.

## Python services (`services/stt`, `services/llm`)
- Stick to PEP 8 style and add type hints for new functions, request models, and helper utilities.
- Reuse `services.common.logging` for structured output so container logs stay consistent.
- Keep FastAPI response models (`pydantic`) up-to-date when the API shape changes. Document any new query params or headers in the relevant doc.
- Sort imports (`ruff --select I`, `isort`, or the tooling in your editor) and freeze dependencies by updating the service-specific `requirements.txt` files when libraries change.
- Use `scripts/test_stt.sh` against `test_speech_16k.wav` (and the translate variant) after modifying the STT service. Add lightweight unit tests if feasible for pure-Python helpers.

## Shell scripts
- Target POSIX sh-compatible syntax (current scripts use `bash` pragmas when necessary). Guard environment variable usage with defaults where appropriate and prefer `set -euo pipefail` for safety.
- Keep scripts idempotent so repeated runs are safe. If a script manages background processes, ensure PID files are cleaned up reliably.

## Documentation
- Maintain Markdown heading hierarchy (`#`, `##`, `###`) and wrap lines at ~100 characters for readability.
- Use relative links between docs (e.g., `../docs/FILE.md`). Mirror configuration or API changes in `README.md`, `docs/CONFIGURATION.md`, and other affected guides.
- Include command examples as fenced code blocks with language hints (`bash`, `env`, `go`).

## Testing expectations
- For Python service updates, run service-specific checks (virtualenv or Docker) and capture smoke-test output (`scripts/test_stt.sh`, manual FastAPI calls) in your summary.
- Mention any additional manual or automated verification (Docker Compose runs, API smoke tests, audio fixture validation) in your summary when submitting changes.

## Citations instructions

* If you browsed files or used terminal commands, you must add citations to the final response (not the body of the PR message) where relevant. Citations reference file paths and terminal outputs with the following formats:

  - `[F:<file_path>:L<line_start>(-L<line_end>)?]`

    - File path citations must start with `F:`. `file_path` is the exact file path of the file relative to the root of the repository that contains the relevant text.
    - `line_start` is the 1-indexed start line number of the relevant output within that file.

  - `[<chunk_id>:L<line_start>(-L<line_end>)?]`

    - Where `chunk_id` is the chunk_id of the terminal output, `line_start` and `line_end` are the 1-indexed start and end line numbers of the relevant output within that chunk.

- Line ends are optional, and if not provided, line end is the same as line start, so only 1 line is cited.
- Ensure that the line numbers are correct, and that the cited file paths or terminal outputs are directly relevant to the word or clause before the citation.
- Do not cite completely empty lines inside the chunk, only cite lines that have content.
- Only cite from file paths and terminal outputs, DO NOT cite from previous pr diffs and comments, nor cite git hashes as chunk ids.
- Use file path citations that reference any code changes, documentation or files, and use terminal citations only for relevant terminal output.
- Prefer file citations over terminal citations unless the terminal output is directly relevant to the clauses before the citation, i.e. clauses on test results.
  - For PR creation tasks, use file citations when referring to code changes in the summary section of your final response, and terminal citations in the testing section.
  - For question-answering tasks, you should only use terminal citations if you need to programmatically verify an answer (i.e., counting lines of code). Otherwise, use file citations.
