<!--
This file provides concise, actionable guidance for AI coding agents working on the
discord-voice-lab repository. Keep it short (20-50 lines) and reference specific
files, commands, and patterns found in the tree.
-->
# Copilot instructions for this repo

This repository is a minimal Go scaffold for a voice-driven agent. The Discord bot
in `cmd/bot` is a client: audio -> STT (Whisper) -> LLM/Orchestrator -> TTS. Keep
guidance short and concrete so contributors (and AI agents) can be productive.

Core files to read first:
- `cmd/bot/main.go` — application entry: logging, env-driven config, Discord session
  setup, event handlers, and voice join/recv wiring.
- `internal/voice/processor.go` — audio pipeline, SSRC <-> user mapping, opus decode,
  and HTTP POSTs to `WHISPER_URL`.
- `internal/logging/logging.go` — centralized zap logger helpers (User/Guild/Channel
  fields) used pervasively in structured logs.

Build / run / test (use Makefile):
- `make build` — build the `bin/bot` binary.
- `make run` — build + run with environment variables.
- `make test` — run Go tests (small repo; prefer targeted tests when iterating).

Important env vars (concrete usage found in `cmd/bot/main.go` and `processor.go`):
- `DISCORD_BOT_TOKEN` (required)
- `GUILD_ID`, `VOICE_CHANNEL_ID` — optional auto-join parameters used at startup
- `WHISPER_URL` — HTTP endpoint that receives PCM audio (Processor POSTs audio here)
- `LOG_LEVEL`, `PAYLOAD_MAX_BYTES`, `REDACT_LARGE_BYTES`, `DETAILED_EVENTS` — logging
  and debug dump controls
- `ALLOWED_USER_IDS` — comma-separated allow-list used by `Processor.SetAllowedUsers`

Project conventions and patterns to follow (examples):
- Centralized logging: call `logging.Init()` early and use `logging.Sugar()` helpers.
  Include `logging.UserFields`, `GuildFields`, `ChannelFields` in structured logs
  (see `cmd/bot/main.go` event logger and `processor.go` handlers).
- Event handling: register small wrapper functions with `discordgo` (e.g.,
  `dg.AddHandler(func(s *discordgo.Session, evt *discordgo.Event) { ... })`) so
  discordgo's reflection validation accepts them.
- Audio processing: enqueue Opus frames via `Processor.ProcessOpusFrame(ssrc, data)`
  and rely on `Processor.Close()` for clean shutdown. Avoid blocking sends; the
  processor uses a bounded channel and drops frames when full.
- External calls: use context-aware HTTP requests with timeouts (see
  `NewProcessorWithResolver` and `handleOpusPacket`) and fail-safe behavior when
  `WHISPER_URL` is not configured.
- Documentation for guidance on multiple topics can be found in `docs/` and should be
  consulted when making changes, and kept updated as needed.

Integration points to be aware of:
- `discordgo` session state is used by `internal/voice/discord_resolver.go` (resolver)
  to map IDs -> human-friendly names; many logs consult the resolver for nicer output.
- The Processor decodes Opus (via `hraban/opus`) into PCM and posts to `WHISPER_URL`.
- Sensitive data handling is implemented in `cmd/bot/main.go`: event payloads are
  redacted (`sensitiveKeys`) and large strings truncated (`REDACT_LARGE_BYTES`).

Editing guidance for AI agents (do this, not generic items):
- When adding new env vars: document defaults in `cmd/bot/main.go` and update README
  if the var affects runtime behavior.
- Preserve allow-list semantics: `Processor.SetAllowedUsers` and early-drop logic in
  `ProcessOpusFrame` must remain intact.
- Add logs with `logging.Sugar().Infow/Debugw/Warnf` and include entity fields using
  the helper functions to maintain consistent structured logs.
- For any change that touches external integrations (Discord, Whisper, OpenAI), link
  the rationale to `docs/ARCHITECTURE.md` and `docs/DEVELOPMENT_GUIDE.md`.
- Agent should make small, incremental changes and run `make build` and `make test`
  after each change to ensure correctness.

<!--
Concise, actionable guidance for AI coding agents working on
the discord-voice-lab repository. Keep it short (20-50 lines), concrete,
and reference exact files/commands in this repo.
-->

# Copilot instructions for discord-voice-lab

This repo implements a small multi-service voice agent. Core pieces live under `services/`:
- `services/bot` — the Discord client (audio -> STT -> LLM/Orchestrator -> TTS).
- `services/stt` — STT HTTP service (FastAPI + Whisper/processing).
- `services/llm` — local orchestrator / OpenAI-compatible LLM shim.
- `services/mcp-server` — small MCP registry & WebSocket bridge used for service discovery/coordination.

Read these first (fast path to comprehension):
- `services/bot/cmd/bot/main.go` — app entry, logging, env-driven config, Discord session and voice join/recv wiring.
- `services/bot/Dockerfile` — how the bot is built inside Docker (note build context expectations).
- `services/bot/cmd/bot/*` and `internal/voice/*.go` — audio pipeline, SSRC <-> user mapping, opus decode, and POSTs to STT.
- `services/mcp-server/main.go` and `ws_transport.go` — MCP server and WebSocket transport implementation.

Build / run / debug (practical commands):
- Local binary (fast): `make build` — builds `bin/bot` (Makefile builds from `services/` module).
- Full stack (recommended for integration): `make run` — builds images and starts compose stack (stt, bot, orch, mcp).
- Tail logs: `make logs` or `docker-compose logs -f --tail=200`.
- Rebuild a single service: `docker-compose build <service>` then `docker-compose up -d <service>`.
- Run bot locally with environment: `make dev-bot` (starts `scripts/run_bot.sh` in background).

Key environment variables (most used in `services/bot/cmd/bot/main.go`):
- `DISCORD_BOT_TOKEN` (required)
- `GUILD_ID`, `VOICE_CHANNEL_ID` — optional auto-join
- `WHISPER_URL` — STT HTTP endpoint (bot POSTS decoded PCM here)
- `MCP_SERVER_URL`, `MCP_SERVICE_NAME` — service registry URL/name (mcp-server is used in compose)
- `ALLOWED_USER_IDS` — comma-separated allow-list for Processor
- `LOG_LEVEL`, `REDACT_LARGE_BYTES`, `DETAILED_EVENTS` — logging/debug behavior

Project-specific conventions (do these):
- Centralized structured logging: call `logging.Init()` early and use `logging.Sugar()` helpers. Include `logging.UserFields`, `GuildFields`, `ChannelFields` in structured logs.
- Small discordgo handlers: always register thin wrapper functions with `dg.AddHandler(func(s *discordgo.Session, evt *discordgo.Event){...})` so discordgo's reflection accepts them.
- Audio path: enqueue Opus frames via `Processor.ProcessOpusFrame(ssrc, data)`; the processor decodes (hraban/opus) and POSTs PCM to `WHISPER_URL` using context-aware HTTP requests.
- Preserve allow-list semantics: `Processor.SetAllowedUsers` + early-drop logic must remain intact when changing audio flow.
- External calls: always use context + timeout. See `NewProcessorWithResolver` for examples.

Integration & cross-component points to inspect before editing:
- `internal/voice/discord_resolver.go` — maps Discord IDs to human-friendly names; used by logs and the processor.
- `services/llm/app.py` — orchestration service registers with MCP at startup via `${MCP_SERVER_URL}/mcp/register`.
- `services/mcp-server/ws_transport.go` — WebSocket transport; ensures MCP server <-> client connections.

Editing guidance for AI agents (concrete):
- When adding new env vars: update `services/bot/cmd/bot/main.go` defaults and add a note in `README.md` or `docs/`.
- Keep changes small and test locally: run `make build` and `make run`, then `docker compose logs` to validate behavior.
- Add logs with `logging.Sugar().Infow/Debugw/Warnf` and include entity fields (`logging.UserFields`, etc.).
- If touching Docker builds, ensure `services/go.mod` remains in the build context (Dockerfiles assume the build context includes `services/`).

Quick examples:
- Add a discord handler:
  `dg.AddHandler(func(s *discordgo.Session, vs *discordgo.VoiceStateUpdate) { vp.HandleVoiceState(s, vs) })`
- Post PCM to STT (pattern): use context with timeout, build request with Content-Type and send bytes; see `internal/voice/whisper_client.go` for the canonical approach.

Where not to be speculative
- Don't change external integration behavior (Discord intents, MCP protocol, or STT POST shapes) without updating `docs/ARCHITECTURE.md` and adding tests or a migration note.

If something's unclear or you want a focused patch (optimize Docker context, persist MCP registry, or add tests), tell me which and I'll prepare a small, testable change.
