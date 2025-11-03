# AI Agent Playbook — `audio-orchestrator`

This guide provides AI agents with essential context for solo development with AI assistance.
Follow these conventions for all changes, optimized for rapid iteration and AI-human collaboration.

## Quick Reference for AI Agents

### Common Tasks

-  **New Feature**: See sections 1, 3, 6, 8
-  **Bug Fix**: See sections 1, 7, 11
-  **Service Integration**: See sections 3, 8, 9
-  **Testing**: See section 11.1

### AI Review Process

1.  **Create feature branch** from `main`
2.  **Implement changes** following existing patterns
3.  **Create PR** with detailed description
4.  **Tag AI reviewers**: `@codex review` and `@cursor review`
5.  **Address AI review feedback** with fixes
6.  **Human reviews** for business logic and final validation

## 1. Solo AI-Human Collaboration Workflow

### Core Workflow for Solo Development

When working on this project, follow this streamlined workflow optimized for solo development with AI assistance:

#### Solo Development Workflow Steps

1.  **Create feature branch** from `main` for significant changes
2.  **Plan Phase**: Analyze existing patterns and decompose task into logical chunks
3.  **Do Phase**: Implement changes following existing patterns with clear commits
4.  **Check Phase**: Run basic quality checks (`make test` and `make lint`)
5.  **Create Pull Request** with detailed description
6.  **Tag AI reviewers**: `@codex review` and `@cursor review`
7.  **Address AI review feedback** with fixes
8.  **Human reviews** for business logic and final validation
9.  **Human merges** when satisfied

#### Absolute Requirements

-  ✅ **DO**: Create branches for features (not every small change)
-  ✅ **DO**: Run basic tests before pushing (`make test`)
-  ✅ **DO**: Tag both AI bots for review
-  ✅ **DO**: Address AI review feedback before human review
-  ✅ **DO**: Follow simplified PDCA framework
-  ✅ **DO**: Include context analysis before AI tasks
-  ✅ **DO**: Use structured prompts with existing patterns
-  ✅ **DO**: Create comprehensive PR descriptions for AI context
-  ❌ **DON'T**: Work directly on main branch for features
-  ❌ **DON'T**: Skip basic quality checks
-  ❌ **DON'T**: Skip AI review process
-  ❌ **DON'T**: Skip context analysis before AI tasks
-  ❌ **DON'T**: Use unstructured AI prompts
-  ❌ **DON'T**: Skip addressing AI review feedback

### Simplified PDCA for Solo Development

#### Plan Phase (AI Analysis)

-  **Codebase Analysis**: Analyze existing patterns and similar implementations
-  **Task Decomposition**: Break features into logical chunks (not atomic)
-  **Pattern Recognition**: Identify existing code patterns to follow
-  **Success Criteria**: Define functional outcomes (not statistical)

#### Do Phase (AI Implementation)

-  **Structured Prompts**: Use context-rich prompts with existing patterns
-  **Follow Patterns**: Implement changes following established codebase patterns
-  **Clear Commits**: Each commit should have descriptive messages
-  **Basic Testing**: Ensure code runs without crashing

#### Check Phase (AI + Human Review)

-  **AI Review**: Address feedback from `@codex review` and `@cursor review`
-  **Quality Gates**: Run basic validations (`make test`, `make lint`)
-  **Pattern Verification**: Ensure code follows existing patterns
-  **Human Review**: Business logic validation and final approval

#### Act Phase (Implementation)

-  **Address Feedback**: Fix issues identified by AI and human reviewers
-  **Merge Changes**: Human merges when satisfied
-  **Document Lessons**: Capture successful patterns for future reference

### AI Collaboration Standards

#### Structured Prompting Framework

```markdown
## AI Task: [Specific Task]

### Context Analysis Required
- Analyze existing codebase patterns
- Identify similar implementations
- Review architectural constraints
- Assess integration points

### Task Decomposition
- Break into atomic, testable chunks
- Identify dependencies and order
- Define success criteria for each chunk
- Plan validation checkpoints

### Implementation Strategy
- Follow existing patterns
- Write tests first (red-green cycle)
- Implement incrementally
- Validate at each checkpoint
```

#### AI Code Generation Quality Gates

-  **Pattern Analysis**: AI must analyze existing patterns before generating code
-  **Test-First**: AI must write failing tests before implementation
-  **Atomic Commits**: Each AI-generated change must be independently testable
-  **Validation Checkpoints**: AI must include validation steps in workflows

#### AI Collaboration Anti-Patterns

-  ❌ **Don't**: Accept AI code without pattern analysis
-  ❌ **Don't**: Skip test-first approach with AI
-  ❌ **Don't**: Allow AI to make architectural decisions without human review
-  ✅ **Do**: Use structured prompts that include existing code patterns
-  ✅ **Do**: Require AI to write tests before implementation
-  ✅ **Do**: Include validation checkpoints in AI workflows

## 2. Communication Standards

### Non-negotiable rules

-  **Eliminate conversational filler.** Begin directly with the action, plan, or report; avoid
   prefatory phrases such as "Certainly," "Here is the plan," or "I hope this helps."
-  **Lead with the conclusion.** Present the key finding or result first, then provide supporting
   evidence.
-  **Prefer structured data.** Use lists, tables, or code blocks for steps, findings, and data
   instead of long paragraphs.
-  **Report facts only.** Describe the plan, actions, and outcomes without narrating internal
   thought processes; include rationale succinctly when necessary.

### Tone

-  Keep responses professional and technically focused; avoid affirmations that imply the user's
  statements are correct or incorrect.
-  Emphasize understanding the request and executing on it rather than offering praise or
  validation.
-  Refrain from reframing user input as claims needing verification if none was made.

## 3. Project Purpose & Architecture

`audio-orchestrator` delivers a voice-first Discord assistant composed of core services
plus shared helpers:

### Core Services

-  `services/discord` (Python; `discord.py`) — Captures voice from Discord,
  detects wake phrases, forwards audio to STT, exposes Discord control tools,
  and plays orchestrator/TTS audio responses. Uses common audio processing libraries directly.
-  `services/stt` (Python; FastAPI, faster-whisper) — Provides HTTP transcription
  with streaming-friendly latencies for the Discord bot and other clients. Uses common audio enhancement libraries directly.
-  `services/orchestrator` (Python; FastAPI, LangChain) — Coordinates transcript processing,
  LangChain tool calls, and response planning. Routes reasoning requests to LLM service.
-  `services/flan` (Python; FastAPI) — Presents an OpenAI-compatible endpoint that
  can broker LangChain tool invocations and return reasoning output to the orchestrator.
-  `services/bark` (Python; FastAPI, Bark) — Streams Bark-generated audio for
  orchestrator responses with authentication and rate limits.
-  `services/common` (Python package) — Houses shared logging, HTTP utilities, and audio processing
  libraries (VAD, quality metrics, core processing, ML enhancement) to keep service behavior consistent.

### Service Communication

```text
Discord Voice → STT → Orchestrator → LLM → TTS → Discord Voice
```

**Note**: Audio processing (VAD, enhancement, quality metrics) is now handled via direct library calls in Discord and STT services using `services/common` modules, eliminating the need for a separate audio service.

### Service Dependencies

-  **Discord** depends on: STT, Orchestrator (uses audio processing libraries directly)
-  **Orchestrator** depends on: LLM, TTS
-  **STT** depends on: (uses audio enhancement libraries directly)

## 4. Repository Layout Essentials

### Core Files

-  `docker-compose.yml` orchestrates the core services with shared environment files.
-  `.env.sample` is the canonical source for new configuration keys; copy the relevant blocks
   into:
  -  `.env.common`
  -  `.env.docker`
  -  `services/**/.env.service`
-  `Makefile` provides the supported workflows (`make run`, `make stop`, `make logs`,
  `make docker-build`, `make docker-restart`, `make docker-shell`, `make docker-config`,
  `make docker-clean`, `make docker-clean-all`, etc.). When a new workflow emerges, add or refine a Makefile target
  rather than relying on copy-pasted commands.
  Use `make docker-clean` for routine cleanup, `make docker-clean-all` for complete reset.

### Documentation Structure

```text
docs/
├── ARCHITECTURE.md          # System architecture for AI context
├── README.md                # Project overview and setup
└── proposals/               # Architecture proposals (when needed)
    └── major-changes.md
```

## 5. Configuration Management

### Environment Variables

-  Keep defaults synchronized across `.env.sample`, service-specific `.env.service` files, and
  `.env.common` / `.env.docker` when you add or rename variables for Docker Compose deployments.
-  When introducing new environment variables, update `.env.sample`, copy the values into each
  affected `services/**/.env.service` file, and call out the requirement in README/docs so local and
  containerized runs stay aligned.
-  Document all configuration changes in `README.md` and the matching guide under `docs/`.

## 6. Tooling & Workflow Standards

### Makefile Targets

-  Prefer the `Makefile` targets over ad-hoc Docker or Python commands so Docker-based runs match
  CI and documentation. Expand the Makefile whenever you identify repeated sequences of Docker or
  Python invocations—future contributors should be able to rely on a named target instead of
  recreating shell snippets.
-  Keep edits incremental and validate after each change: rebuild the stack with `make run`,
  inspect `make logs` (optionally scoped via `SERVICE`), and perform focused service smoke tests
  rather than deferring checks to later.
-  When editing Dockerfiles or Compose definitions, test with `make run` and ensure workflows rely
  on `docker compose`.
-  Mount paths introduced in Compose must work with the existing `.env.*` structure and repository
  directories mounted into the containers (e.g., `./logs`, `./.wavs`).

### Quality Gates & Commands

-  **All changes must pass tests**: `make test-component`
-  **All changes must pass linters**: `make lint`
-  **Auto-fix issues**: `make lint-fix`
-  **Use container targets**: For consistency with CI/CD
-  **Prefer Makefile targets**: Over direct command-line tools

### GitHub Actions Workflow Standards

#### Enhanced Job Reporting

The project implements comprehensive job reporting across all workflows:

##### Test Results Reporting

-  **dorny/test-reporter@v1**: Aggregates test results from unit, component, and integration tests
-  **Artifact Uploads**: 7-day retention for test results and coverage reports
-  **Coverage Summaries**: Automatic generation of coverage metrics in job summaries
-  **Docker Awareness**: Handles artifacts generated inside Docker containers

##### Custom Metrics Reporting

-  **Audio Pipeline Metrics**: Performance targets and service architecture overview
-  **Build Metrics**: Docker build configuration and performance notes
-  **Security Metrics**: Dependency and container security scan results
-  **Workflow Status**: Enhanced status reporting with build information

##### Security Scanning Integration

-  **Trivy Container Scanning**: Filesystem vulnerability scanning with SARIF upload
-  **GitHub Security Integration**: Results uploaded to GitHub Security tab
-  **Dependency Scanning**: Safety and Bandit integration via `make security`

#### Cancellation-Aware Workflow Patterns

-  ✅ **DO**: Use `if: ${{ !cancelled() }}` instead of `if: always()`
-  ✅ **DO**: Add step-level timeouts to long-running operations
-  ✅ **DO**: Implement emergency cleanup on cancellation
-  ✅ **DO**: Use `timeout-minutes` for all Docker build steps
-  ✅ **DO**: Add cancellation-specific cleanup steps
-  ❌ **DON'T**: Use `if: always()` conditions that ignore cancellation
-  ❌ **DON'T**: Skip timeout configuration for Docker builds
-  ❌ **DON'T**: Allow workflows to run indefinitely after cancellation

#### Workflow Quality Gates

-  **Cancellation Response**: Workflows stop within seconds of cancellation
-  **Resource Cleanup**: Emergency cleanup prevents resource waste
-  **Timeout Management**: Step-level timeouts prevent indefinite execution
-  **Cost Control**: Cancelled workflows don't consume unnecessary GitHub Actions minutes

#### Workflow Pattern Examples

##### Cancellation-Aware Job Conditions

```yaml
# Good: Respects cancellation
if: ${{ !cancelled() && needs.build-python-base.result == 'success' }}

# Bad: Ignores cancellation
if: always() && needs.build-python-base.result == 'success'
```

##### Step-Level Timeouts

```yaml
# Good: Prevents indefinite execution
- name: "Build Docker image"
  timeout-minutes: 15
  run: docker buildx build ...

# Bad: No timeout protection
- name: "Build Docker image"
  run: docker buildx build ...
```

##### Emergency Cleanup

```yaml
# Good: Cleanup on cancellation
- name: "Emergency cleanup on cancellation"
  if: cancelled()
  timeout-minutes: 1
  run: |
    echo "Workflow cancelled - emergency cleanup"
    docker system prune -f || true
```

## 7. Python Coding Guidelines

### Code Quality Standards

-  Follow PEP 8 style, add type hints for new functions/classes, and keep imports sorted (use
  `ruff --select I` or an editor integration).
-  Reuse `services.common.logging` (`services/common/logging.py`) for structured JSON logs; prefer
  `extra={}` for contextual metadata instead of string interpolation.
-  Propagate configurable timeouts and retries through HTTP clients.
-  Update `requirements.txt` files when you add or upgrade dependencies; pin versions where
  appropriate for reproducible deployments.

### Type Annotations (MANDATORY)

-  **Function parameters**: `def process_audio(data: bytes, sample_rate: int) -> AudioResult:`
-  **Return types**: `-> Dict[str, Any]`, `-> Optional[AudioData]`, `-> List[AudioChunk]`
-  **Variable annotations**: `audio_buffer: List[float] = []`
-  **Class attributes**: `model_path: str`, `is_loaded: bool = False`

## 8. Solo Health Check Implementation

### Basic Health Check Standards

All services must implement simple health checks for solo development:

#### Basic Health Endpoints

-  **GET /health/live**: Always returns 200 if process is alive
-  **GET /health/ready**: Returns basic status if service can handle requests

#### Simple Implementation

-  **Basic functionality**: Service can handle requests
-  **No complex metrics**: Keep it simple
-  **No extensive dependency checking**: Focus on core functionality

### Simple Implementation Pattern

```python
from fastapi import FastAPI, HTTPException
from typing import Dict, Any

app = FastAPI()

# Simple startup tracking
_startup_complete = False

@app.on_event("startup")
async def _startup():
    """Service startup event handler."""
    global _startup_complete
    try:
        # Initialize core components
        await _initialize_core_components()
        _startup_complete = True
    except Exception as exc:
        # Continue without crashing - service will report not_ready
        pass

@app.get("/health/live")
async def health_live():
    """Liveness check - always returns 200 if process is alive."""
    return {"status": "alive", "service": "discord"}

@app.get("/health/ready")
async def health_ready() -> Dict[str, Any]:
    """Readiness check - basic functionality."""
    if not _startup_complete:
        raise HTTPException(status_code=503, detail="Service not ready")

    return {
        "status": "ready",
        "service": "discord",
        "startup_complete": _startup_complete
    }
```

### Basic Health Check Requirements

-  **Startup Management**: Track if service has completed initialization
-  **Basic Endpoints**: Implement `/health/live` and `/health/ready`
-  **Simple Status**: Return basic status information
-  **No Complex Metrics**: Keep it simple for solo development

## 9. Service-Specific Notes

### Discord voice bot (`services/discord`)

-  Keep wake-word detection, audio aggregation, and STT client behavior in sync with configuration
  defaults found in `.env.sample`.
-  Handle STT or orchestrator failures gracefully—log with correlation metadata and avoid crashing
  the voice loop.
-  Preserve TTS playback plumbing (`_play_tts`) so external TTS services can plug in through URLs
  supplied by the orchestrator.

### Speech-to-text service (`services/stt`)

-  Ensure the FastAPI contract stays stable; update response models if the JSON shape changes.
-  Validate faster-whisper model configuration via environment variables and keep compute defaults
  aligned with `.env.sample`.
-  Aim for responsive startup and streaming latencies; capture notable tuning in the docs.

### Orchestrator service (`services/orchestrator`)

-  Coordinate transcript processing, LangChain tool calls, and response planning.
-  Route reasoning requests to the LLM service for natural language processing.
-  Manage conversation flow and response planning.
-  Coordinate with TTS service for spoken responses.
-  Provide bearer-authenticated APIs for downstream callers.

### LLM service (`services/llm`)

-  Maintain compatibility with the OpenAI-style routes already implemented in `app.py` and document
  any schema extensions.
-  Surface external actions carefully: validate inputs, guard credentials, and return structured
  JSON so downstream clients remain deterministic.

### TTS service (`services/tts`)

-  Stream Piper-generated audio for orchestrator responses with authentication and rate limits.
-  Manage Piper model loading, concurrency limits, and SSML parameterization.
-  Enforce bearer authentication and per-minute rate limits to protect resources.

### Shared utilities (`services/common`)

-  Keep helpers generic and well-documented; prefer adding shared logic here instead of duplicating
  code across services.

## 10. Solo Documentation Standards

### Required Documentation Files (Simplified)

-  **README.md**: Project overview and quick start
-  **docs/ARCHITECTURE.md**: System architecture for AI understanding
-  **PR descriptions**: Detailed explanation of changes and rationale

### PR Description Standards

```markdown
## Feature: [Brief Description]

### Changes Made
- [List of key changes]
- [Architecture decisions]
- [Integration points]

### Rationale
- [Why these changes were made]
- [How they fit into existing patterns]
- [Expected outcomes]

### Testing
- [Basic functionality tested]
- [Integration points verified]
- [Manual testing completed]
```

### Content Guidelines for Solo Development

-  **Clear and concise**: Avoid unnecessary jargon
-  **Technical accuracy**: Verify all technical details
-  **Up-to-date**: Keep documentation current with code changes
-  **AI-focused**: Write for AI understanding and context

## 10. Observability, security, & performance

-  Every service should expose health checks, structured logs, and metrics where feasible so
  Compose deployments remain observable.
-  Authenticate external connections with scoped credentials and propagate correlation IDs through logs
  and tool responses.
-  Treat audio and transcript data as sensitive: avoid persisting raw audio unless explicitly
  needed for debugging and documented in the PR.
-  Target fast wake detection (<200 ms), quick STT startup (<300 ms from speech onset),
  end-to-response times under ~2 s for short queries, and timely TTS playback. Note deviations in
  docs or PR summaries.

## 12. Solo Testing Strategy

### Test Categories (Simplified)

-  **Smoke Tests**: Basic functionality and service health (`services/tests/smoke/`)
-  **Integration Tests**: Service HTTP boundaries via Docker Compose (`services/tests/integration/`)
-  **E2E Tests**: Full system tests for critical paths (`services/tests/e2e/`)

### Testing Approach for Solo Development

-  Run the relevant Docker-focused `Makefile` targets after changes (`make run`, `make logs`,
  `make docker-build`, etc.) and summarize noteworthy output in your PR.
-  Exercise manual or scripted audio tests using your own fixtures (the repo no longer stores
  `.wav` samples). Capture the command/output you used.
-  When changing APIs, provide example requests/responses in docs or PR notes so reviewers can
  verify behavior quickly.

### Quality Gates (Simplified)

-  **Smoke Tests**: Basic functionality works
-  **Integration Tests**: Critical service boundaries work
-  **E2E Tests**: Critical user journeys work

### Performance Requirements (Relaxed)

-  **Smoke Tests**: < 5 seconds per test
-  **Integration Tests**: < 30 seconds per test
-  **E2E Tests**: < 2 minutes per test

### Integration Test Pattern

Integration tests must:

-  Use `docker_compose_test_context()` to start real services
-  Test actual HTTP communication between services
-  Use service names (e.g., `http://stt:9000`) - tests run inside Docker network
-  Verify request/response formats and contracts
-  Test error handling and timeouts
-  NOT mock internal service classes

Example:

```python
@pytest.mark.integration
async def test_service_boundary():
    async with docker_compose_test_context(["stt"]):
        async with httpx.AsyncClient() as client:
            response = await client.post("http://stt:9000/transcribe", json={...})
            assert response.status_code == 200
```

### Success Criteria Framework

For solo development, focus on functional outcomes:

#### Functional Success Criteria

-  **Basic Functionality**: Feature works as intended
-  **Integration**: Changes integrate with existing system
-  **Performance**: No obvious performance regressions
-  **User Experience**: Changes improve or maintain user experience

#### Anti-Patterns to Avoid

-  ❌ **Don't**: Over-engineer with complex metrics
-  ❌ **Don't**: Require statistical validation for simple changes
-  ❌ **Don't**: Create extensive test suites for every feature
-  ✅ **Do**: Focus on "does it work" over "is it perfect"
-  ✅ **Do**: Use manual testing for rapid iteration
-  ✅ **Do**: Write tests only when you break something

## 13. Git Workflow & Branch Management

### Branch Strategy

-  **`main`**: Production-ready code, always deployable
-  **`feat/*`**: Feature development branches
-  **`hotfix/*`**: Critical bug fixes

### Branch Naming Convention

```text
feat/phase-{N}-{description}
feat/audio-platform-cutover
```

### Commit Message Convention

```text
type(scope): description

[optional body]
```

**Types**: feat, fix, test, docs, refactor, perf, chore

**Examples**:

```text
feat(orchestrator): add audio pipeline framework
fix(adapters): resolve async/await issues in discord adapters
test(pipeline): add unit tests for wake detector
```

### Quality Gates

-  **Pre-Push**: `make lint` and `make test` must pass
-  **Bypassing Hooks**: Only use `--no-verify` when necessary and after manual verification

## 14. Citations for Final Summaries

When preparing final responses, cite files and terminal output using the house format:
`【F:path/to/file†Lstart-Lend】` for files and `【chunk_id†Lstart-Lend】` for terminal commands.
Ensure cited lines directly support the referenced text.
