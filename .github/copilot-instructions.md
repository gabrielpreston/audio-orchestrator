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

Local dev tools to remember:
- Use `docker-compose` instead of `docker`
- When working with Python, always use `venv` for safety and isolation

If something's unclear or you want more examples (patches, tests, CI guidance), tell
me which area to expand and I will iterate.
