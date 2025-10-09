# Project Roadmap

## AI Development Agent — 2-Week Strategic Roadmap

**Goal:**  
Transition from an experimental voice-enabled Discord bot into the foundation
of a **Cursor-centric AI development agent** — one capable of understanding
spoken commands, iterating on ideas, writing and testing code, and driving the
software delivery lifecycle (SDLC) end-to-end.  
Discord (or similar platforms) become optional interfaces; the core system’s
value is its ability to act as a **hands-on, voice-driven collaborator inside
the development environment itself.**

---

## 1. Strategic Vision

Build an AI agent that:

- 🧠 **Understands context deeply** — not just natural language, but project structure, architecture, and constraints.
- 🛠️ **Writes, tests, builds, and ships code autonomously** — able to operate as a “pair programmer++” that closes loops without needing manual follow-up.
- 🎙️ **Takes spoken direction** — letting developers guide work conversationally while staying in flow.
- 🔄 **Integrates seamlessly with the developer toolchain** — particularly Cursor, Git, build pipelines, and test harnesses.
- 🚀 **Improves over time** — learning from past decisions, style guides, and review feedback.

---

## 2. 14-Day Roadmap (Strategic Focus)

### Current status (codebase)

- ✅ STT service available (`services/stt/app.py`) and configured via `STT_BASE_URL`.
- ✅ Audio pipeline / Opus decode / POST to STT (`services/discord/audio.py`, `services/discord/transcription.py`).
- ✅ Discord integration and resolver wired (`services/discord/discord_voice.py`, `services/discord/main.py`).
- ✅ Centralized logging helpers (`services/common/logging.py`).
- ✅ Docker helpers (`Makefile`): `run`, `logs`, `docker-build`.

Additional implemented pieces discovered in the codebase:

- ✅ Allow-listing of users via `AUDIO_ALLOWLIST` (`services/discord/config.py`, `services/discord/audio.py`).
- ✅ Wake phrase configuration and filtering (`services/discord/wake.py`, `services/discord/config.py`).
- ✅ Transcript aggregation with retry/backoff when calling STT (`services/discord/transcription.py`).
- ✅ Structured MCP manifest loading for downstream tools (`services/discord/mcp.py`).

### Phase 1 — Stabilize the Core Voice Layer (Days 1-3)

Objective: Finalize the base voice ingestion pipeline so the agent can reliably hear and understand instructions.

- ✅ Voice input pipeline — Finalize PCM → STT → text pipeline, ensuring stable transcription from microphone or Discord. (Agent reliably receives commands in text form.)
- ✅ Command framing — Define a lightweight schema for “intent parsing” (e.g., `action: create_file`, `action: run_tests`). (Voice commands map to actionable tasks.)
- ⬜ Optional: Multi-channel input — Support local mic input *and* Discord voice input with identical downstream handling. (Voice source becomes interchangeable.)

---

### Phase 2 — Cursor Environment Integration (Days 4-7)

Objective: Establish two-way communication between the voice agent and Cursor’s API / local environment.

- ⬜ Cursor context access — Implement connection to Cursor API / local workspace to read project files, structure, and open buffers. (Agent can “see” the project and reason about it.)
- ⬜ Codegen orchestration — Define how agent proposals (from LLM) are written into files or suggested as diffs. (AI can write code directly into the repo.)
- ✅ Action verification layer — Implement test harness commands: e.g., “run unit tests”, “check for linter errors”. (Infrastructure present: `Makefile` targets `run`, `logs`.)

---

### Phase 3 — Voice-Driven Dev Flows (Days 8-11)

Objective: Prototype meaningful real-world use cases driven entirely by voice.

- ⬜ Voice-to-feature workflow — Example: “Add a new `/healthz` endpoint” → design, generate code, run tests, commit. (End-to-end task completion by voice.)
- ⬜ Task chaining — Allow multi-step workflows (e.g., “refactor this service and write tests for it”). (Agent executes chained commands without micromanagement.)
- ⬜ Feedback refinement loop — Add conversational refinement (“make that function generic”, “try a different error strategy”). (Voice iteration feels natural and productive.)

---

### Phase 4 — Developer Workflow Integration (Days 12-14)

Objective: Tighten the feedback loop so the agent operates as a “team member” inside the SDLC.

- ⬜ Git integration — Voice-triggered git actions (branch creation, commits, PR prep). (Agent contributes changes like a human developer.)
- ⬜ Build + deploy hooks — Voice commands trigger builds, CI runs, and deployment workflows. (AI can close the loop and ship code.)
- ⬜ Onboarding doc + demo — Document current capabilities, limitations, and roadmap to next iteration. (Ready for next contributors or productization phase.)

---

## 3. Guiding Principles

- **Cursor as the “operating system”:** The IDE is the primary surface where AI acts. Voice input is just one modality.
- **Voice is command, not gimmick:** Voice should translate to *intent* — “generate”, “test”, “refactor” — not just text input.
- **Autonomy over assistance:** Aim for the agent to complete tasks end-to-end without manual hand-offs.
- **LLM as orchestrator, not executor:** LLM plans and reasons; deterministic code and tools actually execute.
- **Safety and reviewability:** All AI actions should be inspectable and reversible. Every change should go through version control.

---

## 4. Stretch Goals (Beyond 2 Weeks)

- 🤝 Team-aware collaboration: Allow the agent to join standups, write summaries, or propose tickets.  
- 🧠 Persistent memory: Track architectural decisions and coding style over time.  
- 🌐 Multi-agent workflows: Split tasks into “planner”, “coder”, “reviewer”, and “deployer” personas.  
- 🗣️ Natural dialogue understanding: Handle ambiguous or incomplete instructions through clarifying questions.

---

## 5. Definition of Success

By the end of this 2-week sprint:

- The agent can **accept a spoken request**, **plan a solution**, **generate code**, **test it**, and **commit it** — all without leaving Cursor.
- The integration is **stable, modular, and extensible** enough to evolve into a full autonomous SDLC agent.
- There is enough documentation and architectural clarity for new contributors (or future you) to build on top confidently.

---
