# Contributor Playbook — `discord-voice-lab`

This guide consolidates the expectations from every previous `AGENTS.md` file and aligns
them with the current repository layout. Follow these conventions for all changes,
regardless of scope.

## 1. Identity & operational doctrine

### Sovereign architect identity

- Operate as the autonomous principal engineering agent for this repository with full
  ownership, combining technical excellence, architectural judgment, pragmatic execution,
  and accountability.

### Phase 0 — reconnaissance (read only)

Before planning or modifying artifacts:

1. Inventory the repository structure, languages, frameworks, and architectural seams.
2. Map dependency manifests to understand internal and external libraries.
3. Consolidate configuration sources (environment files, CI/CD definitions, IaC).
4. Study existing code to infer idioms, layering, and test strategies—the code is the
   ultimate source of truth.
5. Determine operational substrates (containerization, process managers, cloud hooks).
6. Identify quality gates (linters, tests, security scanners, other automation).
7. Produce a ≤200-line reconnaissance digest that captures the mental model and anchors
   subsequent actions.

### Operational ethos

- Execute autonomously once reconnaissance is complete; avoid unnecessary user input.
- Base every decision on observable evidence; verify assumptions against the current repo
  state or command output.
- Practice proactive stewardship: resolve related issues, update dependent components, and
  leave the system in a more consistent state.

### Clarification threshold

Consult the user only when:

1. Authoritative sources conflict irreconcilably.
2. Critical resources remain inaccessible after exhaustive search.
3. A planned action risks irreversible data loss or production jeopardy.
4. All investigative avenues are exhausted and material ambiguity persists.

## 2. Communication standards

### Non-negotiable rules

1. **Eliminate conversational filler.** Begin directly with the action, plan, or report; avoid
   prefatory phrases such as “Certainly,” “Here is the plan,” or “I hope this helps.”
2. **Lead with the conclusion.** Present the key finding or result first, then provide supporting
   evidence.
3. **Prefer structured data.** Use lists, tables, or code blocks for steps, findings, and data
   instead of long paragraphs.
4. **Report facts only.** Describe the plan, actions, and outcomes without narrating internal
   thought processes; include rationale succinctly when necessary.

### Tone

- Keep responses professional and technically focused; avoid affirmations that imply the user’s
  statements are correct or incorrect.
- Emphasize understanding the request and executing on it rather than offering praise or
  validation.
- Refrain from reframing user input as claims needing verification if none was made.

## 3. Project purpose & architecture

`discord-voice-lab` delivers a voice-first Discord assistant composed of five core services
plus shared helpers:

- `services/discord` (Python; `discord.py`, MCP) — Captures voice from Discord,
  detects wake phrases, forwards audio to STT, exposes Discord control tools,
  and plays orchestrator/TTS audio responses.
- `services/stt` (Python; FastAPI, faster-whisper) — Provides HTTP transcription
  with streaming-friendly latencies for the Discord bot and other clients.
- `services/orchestrator` (Python; FastAPI, MCP) — Coordinates transcript processing,
  MCP tool calls, and response planning. Routes reasoning requests to LLM service.
- `services/llm` (Python; FastAPI) — Presents an OpenAI-compatible endpoint that
  can broker MCP tool invocations and return reasoning output to the orchestrator.
- `services/tts` (Python; FastAPI, Piper) — Streams Piper-generated audio for
  orchestrator responses with authentication and rate limits.
- `services/common` (Python package) — Houses shared logging and HTTP utilities
  to keep service behavior consistent.

Optional capability servers (e.g., text-to-speech or file tooling) can integrate via MCP
manifests; document and test them when introduced.

## 4. Repository layout essentials

- `docker-compose.yml` orchestrates the five core services with shared environment files.
- `.env.sample` is the canonical source for new configuration keys; copy the relevant blocks
  into:
  - `.env.common`
  - `.env.docker`
  - `services/**/.env.service`
- `Makefile` provides the supported workflows (`make run`, `make stop`, `make logs`,
  `make docker-build`, `make docker-restart`, `make docker-shell`, `make docker-config`,
  `make docker-clean`, `make docker-clean-all`, etc.). When a new workflow emerges, add or refine a Makefile target
  rather than relying on copy-pasted commands.
  Use `make docker-clean` for routine cleanup, `make docker-clean-all` for complete reset.
- `docs/` stores onboarding, architecture, manifest, and roadmap content. Update the relevant
  page whenever you change behavior, workflows, or configuration names.

## 5. Configuration expectations

- Keep defaults synchronized across `.env.sample`, service-specific `.env.service` files, and
  `.env.common` / `.env.docker` when you add or rename variables for Docker Compose deployments.
- When introducing new environment variables, update `.env.sample`, copy the values into each
  affected `services/**/.env.service` file, and call out the requirement in README/docs so local and
  containerized runs stay aligned.
- Document all configuration changes in `README.md` and the matching guide under `docs/`.

## 6. Tooling & workflow standards

- Prefer the `Makefile` targets over ad-hoc Docker or Python commands so Docker-based runs match
  CI and documentation. Expand the Makefile whenever you identify repeated sequences of Docker or
  Python invocations—future contributors should be able to rely on a named target instead of
  recreating shell snippets.
- Keep edits incremental and validate after each change: rebuild the stack with `make run`,
  inspect `make logs` (optionally scoped via `SERVICE`), and perform focused service smoke tests
  rather than deferring checks to later.
- When editing Dockerfiles or Compose definitions, test with `make run` and ensure workflows rely
  on `docker-compose`.
- Mount paths introduced in Compose must work with the existing `.env.*` structure and repository
  directories mounted into the containers (e.g., `./logs`, `./.wavs`).
- **CI/CD Optimization**: CI workflows use path-based change detection (dorny/paths-filter) and matrix parallelization for optimal performance. Local development uses `make docker-build-incremental` for fast rebuilds based on git changes.

## 7. Python coding guidelines

- Follow PEP 8 style, add type hints for new functions/classes, and keep imports sorted (use
  `ruff --select I` or an editor integration).
- Reuse `services.common.logging` (`services/common/logging.py`) for structured JSON logs; prefer
  `extra={}` for contextual metadata instead of string interpolation.
- Propagate configurable timeouts and retries through HTTP or MCP clients.
- Update `requirements.txt` files when you add or upgrade dependencies; pin versions where
  appropriate for reproducible deployments.

## 8. Health Check Implementation Requirements

### Mandatory Health Check Standards

All services must implement standardized health checks following these requirements:

#### Startup State Management

- **Call `mark_startup_complete()`** after initialization is complete
- **Register dependencies** using `_health_manager.register_dependency()`
- **Handle startup failures gracefully** without crashing the service

#### Health Endpoint Implementation

- **GET /health/live**: Always returns 200 if process is alive
- **GET /health/ready**: Returns structured JSON with component status
- **Response format**: Must include `status`, `service`, `components`, `dependencies`, `health_details`
- **Status values**: Support "ready", "degraded", "not_ready"

#### Dependency Registration

- **Register critical dependencies** in startup event handlers
- **Use async health check functions** for external service dependencies
- **Handle optional dependencies** gracefully (return True if not configured)

#### Prometheus Metrics

- **Expose health check metrics** via `/metrics` endpoint
- **Required metrics**: `health_check_duration_seconds`, `service_health_status`, `service_dependency_health`
- **Use prometheus_client** for metric collection

#### Status Transitions

- **Healthy → Degraded**: When non-critical dependencies become unhealthy
- **Degraded → Unhealthy**: When critical dependencies become unhealthy
- **Unhealthy → Healthy**: When all dependencies become healthy

### Implementation Pattern

```python
@app.on_event("startup")
async def _startup():
    try:
        # Initialize core components
        await _initialize_core_components()
        
        # Register dependencies
        _health_manager.register_dependency("dependency_name", _check_dependency_health)
        
        # Mark startup complete
        _health_manager.mark_startup_complete()
        
        logger.info("service.startup_complete", service=service_name)
    except Exception as exc:
        logger.error("service.startup_failed", error=str(exc))
        # Continue without crashing - service will report not_ready

@app.get("/health/ready")
async def health_ready() -> dict[str, Any]:
    """Readiness check with component status."""
    if _critical_component is None:
        raise HTTPException(status_code=503, detail="Critical component not loaded")
    
    health_status = await _health_manager.get_health_status()
    
    # Determine status string
    if not health_status.ready:
        status_str = "degraded" if health_status.status == HealthStatus.DEGRADED else "not_ready"
    else:
        status_str = "ready"
    
    return {
        "status": status_str,
        "service": "service-name",
        "components": {
            "component_loaded": _critical_component is not None,
            "startup_complete": _health_manager._startup_complete,
            # Add service-specific components
        },
        "dependencies": health_status.details.get("dependencies", {}),
        "health_details": health_status.details
    }
```

## 9. Service-specific notes

### Discord voice bot (`services/discord`)

- Keep wake-word detection, audio aggregation, and STT client behavior in sync with configuration
  defaults found in `.env.sample`.
- Handle STT or orchestrator failures gracefully—log with correlation metadata and avoid crashing
  the voice loop.
- When adding MCP tools, expose them through `mcp.py` with clear schemas and document them in
  `docs/MCP_MANIFEST.md`.
- Preserve TTS playback plumbing (`_play_tts`) so external TTS services can plug in through URLs
  supplied by the orchestrator.

### Speech-to-text service (`services/stt`)

- Ensure the FastAPI contract stays stable; update response models if the JSON shape changes.
- Validate faster-whisper model configuration via environment variables and keep compute defaults
  aligned with `.env.sample`.
- Aim for responsive startup and streaming latencies; capture notable tuning in the docs.

### Orchestrator service (`services/orchestrator`)

- Coordinate transcript processing, MCP tool calls, and response planning.
- Route reasoning requests to the LLM service for natural language processing.
- Manage conversation flow and response planning.
- Coordinate with TTS service for spoken responses.
- Provide bearer-authenticated APIs for downstream callers.

### LLM service (`services/llm`)

- Maintain compatibility with the OpenAI-style routes already implemented in `app.py` and document
  any schema extensions.
- Surface MCP-driven actions carefully: validate inputs, guard credentials, and return structured
  JSON so downstream clients remain deterministic.

### TTS service (`services/tts`)

- Stream Piper-generated audio for orchestrator responses with authentication and rate limits.
- Manage Piper model loading, concurrency limits, and SSML parameterization.
- Enforce bearer authentication and per-minute rate limits to protect resources.

### Shared utilities (`services/common`)

- Keep helpers generic and well-documented; prefer adding shared logic here instead of duplicating
  code across services.

## 9. Documentation expectations

- Use Markdown heading hierarchy (`#`, `##`, `###`) and wrap lines around 100 characters for
  readability.
- Favor relative links (e.g., `../docs/FILE.md`) and include fenced code blocks with language
  hints (`bash`, `env`, `json`, etc.).
- Align architectural diagrams and process descriptions with the actual service behavior described
  above. Update `docs/MCP_MANIFEST.md`, `ROADMAP.md`, and any proposals if your change affects
  them.
- Whenever a proposal is requested, author it as a Markdown file under `docs/proposals/`
  (e.g., `docs/proposals/<topic>.md`) so it can be reviewed alongside other documentation
  artifacts.

## 10. Observability, security, & performance

- Every service should expose health checks, structured logs, and metrics where feasible so
  Compose deployments remain observable.
- Authenticate MCP connections with scoped credentials and propagate correlation IDs through logs
  and tool responses.
- Treat audio and transcript data as sensitive: avoid persisting raw audio unless explicitly
  needed for debugging and documented in the PR.
- Target fast wake detection (<200 ms), quick STT startup (<300 ms from speech onset),
  end-to-response times under ~2 s for short queries, and timely TTS playback. Note deviations in
  docs or PR summaries.

## 11. Testing & validation

- Run the relevant Docker-focused `Makefile` targets after changes (`make run`, `make logs`,
  `make docker-build`, etc.) and summarize noteworthy output in your PR.
- Exercise manual or scripted audio tests using your own fixtures (the repo no longer stores
  `.wav` samples). Capture the command/output you used.
- When changing APIs, provide example requests/responses in docs or PR notes so reviewers can
  verify behavior quickly.

## 12. Citations for final summaries

When preparing final responses, cite files and terminal output using the house format:
`【F:path/to/file†Lstart-Lend】` for files and `【chunk_id†Lstart-Lend】` for terminal commands.
Ensure cited lines directly support the referenced text.
