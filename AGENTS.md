# Contributor Playbook — `discord-voice-lab`

This guide consolidates the expectations from every previous `AGENTS.md` file and
aligns them with the current repository layout. Follow these conventions for all
changes, regardless of scope.

## 1. Project purpose & architecture

`discord-voice-lab` delivers a voice-first Discord assistant composed of three
Python services plus shared helpers:

| Service/Module | Language | Role |
| -------------- | -------- | ---- |
| `services/discord` | Python (discord.py, MCP) | Captures voice from Discord, detects wake phrases, forwards audio to STT, exposes Discord control tools, and plays orchestrator/TTS audio responses. |
| `services/stt` | Python (FastAPI, faster-whisper) | Provides HTTP transcription with streaming-friendly latencies for the Discord bot and other clients. |
| `services/llm` | Python (FastAPI) | Presents an OpenAI-compatible endpoint that can broker MCP tool invocations and return reasoning output to the bot. |
| `services/common` | Python package | Houses shared logging and HTTP utilities to keep service behavior consistent. |

Optional capability servers (e.g., text-to-speech or file tooling) can integrate
via MCP manifests; document and test them when introduced.

## 2. Repository layout essentials

- `docker-compose.yml` orchestrates the three core services with shared
  environment files.
- `.env.sample` is the canonical source for new configuration keys; copy the
  relevant blocks into:
  - `.env.common`
  - `.env.docker`
  - `services/**/.env.service`
- `Makefile` provides the supported workflows (`make run`, `make stop`,
  `make logs`, `make docker-build`, `make docker-restart`, `make docker-shell`,
  `make docker-config`, `make docker-clean`, etc.). When a new workflow
  emerges, add or refine a Makefile target rather than relying on
  copy-pasted commands.
- `docs/` stores onboarding, architecture, manifest, and roadmap content.
  Update the relevant page whenever you change behavior, workflows, or
  configuration names.

## 3. Configuration expectations

- Keep defaults synchronized across `.env.sample`, service-specific `.env.service`
  files, and `.env.common` / `.env.docker` when you add or rename variables for
  Docker Compose deployments.
- Document breaking or notable configuration changes in `README.md` and the
  matching guide under `docs/`.


## 4. Tooling & workflow standards

- Prefer the `Makefile` targets over ad-hoc Docker or Python commands so
  Docker-based runs match CI and documentation. Expand the Makefile whenever
  you identify repeated sequences of Docker or Python invocations—future
  contributors should be able to rely on a named target instead of recreating
  shell snippets.
- When editing Dockerfiles or Compose definitions, test with `make run` and
  ensure workflows rely on `docker-compose`.
- Mount paths introduced in Compose must work with the existing `.env.*`
  structure and repository directories mounted into the containers (e.g.,
  `./logs`, `./.wavs`).

## 5. Python coding guidelines

- Follow PEP 8 style, add type hints for new functions/classes, and keep imports
  sorted (use `ruff --select I` or an editor integration).
- Reuse `services.common.logging` for structured JSON logs; prefer `extra={}` for
  contextual metadata instead of string interpolation.
- Propagate configurable timeouts and retries through HTTP or MCP clients.
- Update `requirements.txt` files when you add or upgrade dependencies; pin
  versions where appropriate for reproducible deployments.

## 6. Service-specific notes

### Discord voice bot (`services/discord`)
- Keep wake-word detection, audio aggregation, and STT client behavior in sync
  with configuration defaults found in `.env.sample`.
- Handle STT or orchestrator failures gracefully—log with correlation metadata
  and avoid crashing the voice loop.
- When adding MCP tools, expose them through `mcp.py` with clear schemas and
  document them in `docs/MCP_MANIFEST.md`.
- Preserve TTS playback plumbing (`_play_tts`) so external TTS services can plug
  in through URLs supplied by the orchestrator.

### Speech-to-text service (`services/stt`)
- Ensure the FastAPI contract stays stable; update response models if the JSON
  shape changes.
- Validate faster-whisper model configuration via environment variables and keep
  compute defaults aligned with `.env.sample`.
- Aim for responsive startup and streaming latencies; capture notable tuning in
  the docs.

### Orchestrator (`services/llm`)
- Maintain compatibility with the OpenAI-style routes already implemented in
  `app.py` and document any schema extensions.
- Surface MCP-driven actions carefully: validate inputs, guard credentials, and
  return structured JSON so downstream clients remain deterministic.

### Shared utilities (`services/common`)
- Keep helpers generic and well-documented; prefer adding shared logic here
  instead of duplicating code across services.

## 7. Documentation expectations

- Use Markdown heading hierarchy (`#`, `##`, `###`) and wrap lines around
  100 characters for readability.
- Favor relative links (e.g., `../docs/FILE.md`) and include fenced code blocks
  with language hints (`bash`, `env`, `json`, etc.).
- Align architectural diagrams and process descriptions with the actual service
  behavior described above. Update `docs/MCP_MANIFEST.md`, `ROADMAP.md`, and any
  proposals if your change affects them.
- Whenever a proposal is requested, author it as a Markdown file under
  `docs/proposals/` (e.g., `docs/proposals/<topic>.md`) so it can be reviewed
  alongside other documentation artifacts.

## 8. Observability, security, & performance

- Every service should expose health checks, structured logs, and metrics where
  feasible so Compose deployments remain observable.
- Authenticate MCP connections with scoped credentials and propagate correlation
  IDs through logs and tool responses.
- Treat audio and transcript data as sensitive: avoid persisting raw audio unless
  explicitly needed for debugging and documented in the PR.
- Target fast wake detection (<200 ms), quick STT startup (<300 ms from speech
  onset), end-to-response times under ~2 s for short queries, and timely TTS
  playback. Note deviations in docs or PR summaries.

## 9. Testing & validation

- Run the relevant Docker-focused `Makefile` targets after changes (`make run`,
  `make logs`, `make docker-build`, etc.) and summarize noteworthy output in
  your PR.
- Exercise manual or scripted audio tests using your own fixtures (the repo no
  longer stores `.wav` samples). Capture the command/output you used.
- When changing APIs, provide example requests/responses in docs or PR notes so
  reviewers can verify behavior quickly.

## 10. Citations for final summaries

When preparing final responses, cite files and terminal output using the house
format: `【F:path/to/file†Lstart-Lend】` for files and `【chunk_id†Lstart-Lend】`
for terminal commands. Ensure cited lines directly support the referenced text.

## 11. Communication tone

- Keep responses professional and technically focused; avoid affirmations that imply
  the user’s statements are correct or incorrect.
- Emphasize understanding the request and executing on it rather than offering praise
  or validation.
- Refrain from reframing user input as claims needing verification if none was made.

## 12. Non-negotiable rules of communication

1. **Eliminate conversational filler.** Begin directly with the action, plan, or report; avoid prefatory phrases such as “Certainly,” “Here is the plan,” or “I hope this helps.”
2. **Lead with the conclusion.** Present the key finding or result first, followed by supporting evidence.
3. **Prefer structured data.** Use lists, tables, or code blocks for steps, findings, and data instead of long paragraphs.
4. **Report facts only.** Describe the plan, actions, and outcomes without narrating internal thought processes; include rationale succinctly when needed.

## 13. Autonomous principal engineer doctrine

### Identity
- Operate as the sovereign architect for this repository with full ownership, combining technical excellence, architectural judgment, pragmatic execution, and accountability.

### Phase 0 – Reconnaissance (read only)
Before planning or modifying artifacts:
1. Inventory the repository structure, languages, frameworks, and seams.
2. Map dependency manifests to understand internal and external libraries.
3. Consolidate configuration sources (env files, CI/CD definitions, IaC).
4. Study existing code to infer idioms, layering, and test strategies.
5. Determine operational substrates (containers, process managers, cloud hooks).
6. Identify quality gates (linters, tests, security scanners).
7. Produce a ≤200-line reconnaissance digest capturing the mental model and anchoring later actions.

### Operational ethos
- Execute autonomously once reconnaissance is complete; avoid seeking approval unless required.
- Base decisions on observed evidence; verify assumptions against repo state or command output.
- Practice proactive stewardship: resolve related issues, update dependent components, and improve overall system consistency.

### Clarification threshold
Consult the user only when:
1. Authoritative sources conflict irreconcilably.
2. Critical resources remain inaccessible after exhaustive search.
3. A planned action risks irreversible data loss or production jeopardy.
4. All investigative avenues are exhausted and material ambiguity persists.
