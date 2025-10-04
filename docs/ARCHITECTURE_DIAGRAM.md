# Architecture Diagram (Mermaid)

```mermaid
flowchart LR
  subgraph Discord_Service[Discord]
    direction TB
    User(("User (voice)")) -->|"Voice packets (Opus)"| VoiceChannel(("Discord Voice Channel"))
  end

  subgraph Bot_Service[services/bot]
    direction LR
    Bot(("Discord Bot\n(cmd/bot/main.go)")) -->|"receive voice"| VoiceGlue(("Voice receive handlers"))
    VoiceGlue --> Processor(("internal/voice/processor.go"))
    Processor -->|"decoded PCM POST"| STT(("STT service (WHISPER_URL) - services/stt/app.py"))
    Processor -->|"resolve names"| Resolver(("discord_resolver.go"))
    Processor -->|"save audio"| SaveAudio(("saveaudio.go"))
    Processor --> MCP(("MCP client (internal/mcp)"))
  end

  subgraph STT_Service[services/stt]
    direction TB
    STT -->|"text"| LLM(("LLM/orchestrator service (services/llm/app.py)"))
  end

  subgraph LLM_Service[services/llm]
    direction TB
    LLM -->|"commands/events"| Orchestrator(("orchestrator"))
    Orchestrator -->|"TTS request"| TTS(("TTS (internal/voice/tts.go or external)"))
  end

  subgraph MCP_Service[MCP Server]
    direction TB
    MCPServer(("mcp-server"))
    MCPServer <--->|"service registry / ws"| MCPClient(("internal/mcp client"))
  end

  Bot_Service -.->|"registers with"| MCP_Service
  LLM_Service -.->|"registers with"| MCP_Service
  STT_Service -.->|"may register with"| MCP_Service

  TTS -->|"audio bytes"| Bot
  LLM -->|"text responses"| Bot

  classDef service fill:#f9f,stroke:#333,stroke-width:1px;
  class Bot_Service,STT_Service,LLM_Service,MCP_Service service;
```


## Notes

- The central audio path is: Discord (Opus frames) -> Bot receives -> Processor decodes Opus to PCM -> POST to STT (WHISPER_URL) -> text to LLM -> orchestrator issues TTS -> Bot plays audio back to voice channel.
- MCP (services/mcp-server) provides service discovery and a WebSocket bridge used by `services/llm` and `services/bot`.
- Important files: `cmd/bot/main.go`, `internal/voice/processor.go`, `internal/voice/whisper_client.go`, `services/stt/app.py`, `services/llm/app.py`, `mcp-server/main.go`.
