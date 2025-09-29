<!--
This file provides concise, actionable guidance for AI coding agents working on the
discord-voice-lab repository. Keep it short (20-50 lines) and reference specific
files, commands, and patterns found in the tree.
-->
# Copilot instructions for this repo

- Big picture: this repo is a minimal Go scaffold for a voice-driven "agent". The
  Discord bot in `cmd/bot` is a client: audio -> STT -> Orchestrator/LLM -> TTS.
  The core pieces to inspect are `cmd/bot/main.go`, `internal/voice/processor.go`,
  `llm/client.go`, and `internal/logging/logging.go`.

- Build & dev commands: use `Makefile` targets. Common commands:
  - `make bot` (builds and runs the bot via `./scripts/run_bot.sh`)
  - `make test` (runs `go test ./...`)
  - `go build -tags opus -o bin/bot ./cmd/bot` if building manually (see `run_bot.sh`).

- Configuration: env vars control runtime behavior. Important ones:
  - `DISCORD_BOT_TOKEN`, `GUILD_ID`, `VOICE_CHANNEL_ID` for Discord connectivity.
  - `WHISPER_URL` for STT; `OPENAI_BASE_URL`, `OPENAI_MODEL`, `OPENAI_FALLBACK_MODEL` for LLMs.
  - `LOG_LEVEL`, `PAYLOAD_MAX_BYTES`, `REDACT_LARGE_BYTES`, `DETAILED_EVENTS` affect logging details.

- Code patterns and conventions to follow:
  - Centralized logging via `internal/logging.Init()` and `logging.Sugar()`; use structured
    `Sugar().Infow/Debugw/Warnf` calls. See `cmd/bot/main.go` and `internal/voice/processor.go`.
  - Voice pipeline: `discordgo` events are logged generically in `cmd/bot/main.go`, then
    voice-specific events forwarded to `voice.Processor` (see `voice.NewProcessor()` and `ProcessOpusFrame`).
  - External service calls (STT, LLM) are synchronous HTTP requests with timeouts; prefer
    context-aware requests and guarded retries (see `llm.Client` and `Processor.handleOpusPacket`).

- Testing and safety notes for edits:
  - Preserve allow-list semantics when adding shell/git runners (discussed in docs/ARCHITECTURE.md).
  - Avoid introducing uncontrolled external writes; repo assumes sandboxing and explicit
    confirmation for destructive operations.

- Examples to reference when producing code or patches:
  - Add logging: follow `logging.Init()` usage and include fields like `sessionId` or `ssrc`.
  - LLM call: use `llm.NewClientFromEnv()` and `CreateChatCompletion(ctx, ChatRequest{...})`.
  - Processor flow: enqueue frames with `ProcessOpusFrame(ssrc, opusBytes)` and honor `Close()`.

- When suggesting edits that change architecture or add services, link to `docs/ARCHITECTURE.md`
  and `docs/DEVELOPMENT_GUIDE.md` for rationale and developer commands.

- Avoid generic instructions: prefer concrete file edits and provide exact code snippets
  or unified diffs. If proposing a new env var, include a default and where it is consumed. Be concise in 
  your responses to save on processing time and bytes over the band.

If anything here is unclear or you want the file expanded with more examples (patchs, tests,
or CI guidance), ask and I'll iterate.
