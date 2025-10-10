---
title: System Overview
author: Discord Voice Lab Team
status: active
last-updated: 2024-07-05
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Architecture ▸ System Overview

# System Overview

The Discord Voice Lab combines four core services to transform live Discord audio into orchestrated
actions and synthesized responses.

## Topology

```mermaid
flowchart LR
    DiscordClient[(Discord Voice Bot)] -->|Audio frames| STT[Speech-to-Text API]
    STT -->|Transcripts| Orchestrator[LLM Orchestrator]
    Orchestrator -->|Tool calls| MCPTools[(MCP Integrations)]
    Orchestrator -->|Text| TTS[Text-to-Speech API]
    TTS -->|Audio stream| DiscordClient
```

## Service Responsibilities

| Service | Role | Key Technologies |
| --- | --- | --- |
| `services/discord` | Captures Discord voice, detects wake phrases, forwards audio to STT, plays TTS output, exposes MCP tools. | `discord.py`, `faster-whisper`, MCP SDKs. |
| `services/stt` | Hosts the speech-to-text API backed by faster-whisper for streaming transcription. | FastAPI, `faster-whisper`. |
| `services/llm` | Provides OpenAI-compatible completions, brokers MCP calls, and coordinates responses returned to Discord. | FastAPI, llama.cpp executor. |
| `services/tts` | Streams Piper-generated audio for orchestrator responses with authentication and rate limits. | FastAPI, Piper. |

## Data Flow

1. The Discord bot captures PCM audio once a wake phrase is detected.
2. Audio segments are streamed to the STT service, which returns transcripts.
3. Transcripts feed the orchestrator, which selects MCP tools, composes reasoning, and prepares responses.
4. For spoken replies, the orchestrator calls the TTS service and returns the resulting audio to Discord.
5. Observability flows through shared structured logging helpers and optional `/metrics` endpoints.

## Integration Points

- **Model Context Protocol (MCP)** — Register manifests via `MCP_MANIFESTS`, WebSocket URLs, or command handlers to expose automation tools.
- **Discord tokens** — Configure via `services/discord/.env.service` with guild and channel identifiers.
- **Llama.cpp runtime** — Tuned through `services/llm/.env.service` to set model paths, context size, and threading.

For deeper service details, explore the [service deep dives](service-deep-dives/discord.md) and the
[MCP integration appendix](integration/mcp.md).
