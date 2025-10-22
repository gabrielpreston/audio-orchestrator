# Source of Truth: Current System Analysis

**Date:** 2025-01-27  
**Purpose:** Comprehensive analysis of current system state before implementing new architecture  
**Status:** Complete

---

## 🏗️ **Current Architecture Overview**

### **Service Topology**
```
Discord Bot (discord.py) 
    ↓ Audio frames
STT Service (faster-whisper)
    ↓ Transcripts  
Orchestrator Service (MCP + LLM)
    ↓ Reasoning requests
LLM Service (llama.cpp)
    ↓ Responses
Orchestrator Service
    ↓ Tool calls
MCP Tools (external)
    ↓ Text responses
TTS Service (Piper)
    ↓ Audio stream
Discord Bot
```

### **Service Responsibilities**

| Service | Current Role | Key Technologies | Port |
|---------|-------------|------------------|------|
| `discord` | Voice capture, wake detection, audio playback, MCP tools | `discord.py`, `webrtcvad`, `openwakeword` | 8001 |
| `stt` | Speech-to-text transcription | `faster-whisper`, FastAPI | 9000 |
| `orchestrator` | Transcript processing, MCP coordination, LLM routing | FastAPI, MCP SDKs | 8000 |
| `llm` | OpenAI-compatible completions | `llama.cpp`, FastAPI | 8000 |
| `tts` | Text-to-speech synthesis | `piper`, FastAPI | 7000 |

---

## 🔌 **Current API Contracts**

### **Discord Service Endpoints**
-  `GET /health/live` - Liveness check
-  `GET /health/ready` - Readiness check  
-  `POST /mcp/send_message` - Send Discord message
-  `POST /mcp/transcript` - Handle transcript notifications
-  `GET /mcp/tools` - List MCP tools

### **STT Service Endpoints**
-  `GET /health/live` - Liveness check
-  `GET /health/ready` - Readiness check
-  `POST /asr` - Raw WAV transcription
-  `POST /transcribe` - Multipart form transcription
-  `GET /metrics` - Prometheus metrics

### **Orchestrator Service Endpoints**
-  `GET /health/live` - Liveness check
-  `GET /health/ready` - Readiness check
-  `POST /mcp/transcript` - Process transcripts
-  `GET /mcp/tools` - List available MCP tools
-  `GET /mcp/connections` - List MCP connections
-  `GET /metrics` - Prometheus metrics

### **LLM Service Endpoints**
-  `GET /health/live` - Liveness check
-  `GET /health/ready` - Readiness check
-  `POST /v1/chat/completions` - OpenAI-compatible completions
-  `GET /metrics` - Prometheus metrics

### **TTS Service Endpoints**
-  `GET /health/live` - Liveness check
-  `GET /health/ready` - Readiness check
-  `POST /synthesize` - Text-to-speech synthesis
-  `GET /voices` - List available voices
-  `GET /metrics` - Prometheus metrics

---

## 📊 **Current Data Flow Patterns**

### **Audio Processing Flow**
-  **Discord Bot** captures PCM audio frames
-  **AudioPipeline** aggregates frames with VAD (Voice Activity Detection)
-  **AudioSegment** created when silence detected or max duration reached
-  **STT Service** transcribes audio segment to text
-  **Orchestrator** processes transcript and coordinates MCP tools
-  **LLM Service** provides reasoning for complex queries
-  **TTS Service** synthesizes spoken responses
-  **Discord Bot** plays audio back to voice channel

### **Current Data Types**
```python
# Discord Service Audio Types
@dataclass(slots=True)
class PCMFrame:
    pcm: bytes
    timestamp: float
    rms: float
    duration: float
    sequence: int
    sample_rate: int

@dataclass(slots=True)
class AudioSegment:
    user_id: int
    pcm: bytes
    start_timestamp: float
    end_timestamp: float
    correlation_id: str
    frame_count: int
    sample_rate: int

# Common Audio Types
@dataclass
class AudioMetadata:
    sample_rate: int
    channels: int
    sample_width: int
    duration: float
    frames: int
    format: str
    bit_depth: int
```

---

## ⚙️ **Current Configuration System**

### **Configuration Architecture**
-  **`services/common/config.py`** - `ConfigBuilder` system (excellent)
-  **`services/common/service_configs.py`** - Service-specific configs
-  **`.env.sample`** - Comprehensive environment template
-  **Service-specific `.env.service`** files

### **Key Configuration Patterns**
```python
# Current ConfigBuilder usage
_cfg: ServiceConfig = (
    ConfigBuilder.for_service("orchestrator", Environment.DOCKER)
    .add_config("logging", LoggingConfig)
    .add_config("http", HttpConfig)
    .add_config("llm_client", LLMClientConfig)
    .add_config("tts_client", TTSClientConfig)
    .add_config("orchestrator", OrchestratorConfig)
    .load()
)
```

### **Environment Variables by Service**

#### **Discord Service**
-  `DISCORD_BOT_TOKEN`, `DISCORD_GUILD_ID`, `DISCORD_VOICE_CHANNEL_ID`
-  `AUDIO_SAMPLE_RATE`, `AUDIO_VAD_SAMPLE_RATE`, `AUDIO_VAD_AGGRESSIVENESS`
-  `WAKE_PHRASES`, `WAKE_THRESHOLD`, `WAKE_SAMPLE_RATE`
-  `STT_BASE_URL`, `STT_TIMEOUT`, `STT_MAX_RETRIES`
-  `ORCHESTRATOR_URL`, `MCP_MANIFESTS`

#### **STT Service**
-  `FW_MODEL`, `FW_DEVICE`, `FW_COMPUTE_TYPE`
-  `FW_MODEL_PATH`, `FW_SAMPLE_RATE`

#### **Orchestrator Service**
-  `LLM_BASE_URL`, `LLM_AUTH_TOKEN`
-  `TTS_BASE_URL`, `TTS_AUTH_TOKEN`
-  `MCP_CONFIG_PATH`

#### **LLM Service**
-  `LLAMA_BIN`, `LLAMA_MODEL_PATH`, `LLAMA_CTX`, `LLAMA_THREADS`
-  `LLM_AUTH_TOKEN`, `TTS_BASE_URL`, `TTS_VOICE`

#### **TTS Service**
-  `TTS_MODEL_PATH`, `TTS_MODEL_CONFIG_PATH`
-  `TTS_DEFAULT_VOICE`, `TTS_MAX_CONCURRENCY`
-  `TTS_RATE_LIMIT_PER_MINUTE`, `TTS_AUTH_TOKEN`

---

## 🧪 **Current Testing Framework**

### **Test Structure**
```
services/tests/
├── unit/           # Fast, isolated, mocked dependencies
├── component/      # Internal logic with mocked external services
├── integration/    # Service HTTP boundaries via Docker Compose
├── e2e/           # Full system tests
├── quality/       # Audio quality and performance regression
└── fixtures/      # Test fixtures and mocks
```

### **Test Categories**
-  **Unit Tests**: Fast, isolated, mocked dependencies
-  **Component Tests**: Internal logic with mocked external dependencies
-  **Integration Tests**: Service HTTP boundaries via Docker Compose
-  **E2E Tests**: Full system tests
-  **Quality Tests**: Audio quality and performance regression

### **Current Test Patterns**
```python
# Integration test pattern
@pytest.mark.integration
async def test_service_boundary():
    async with docker_compose_test_context(["stt"]):
        async with httpx.AsyncClient() as client:
            response = await client.post("http://stt:9000/transcribe", json={...})
            assert response.status_code == 200
```

---

## 🔧 **Current Infrastructure Components**

### **Excellent Infrastructure (Keep)**
-  **`services/common/config.py`** - `ConfigBuilder` system (excellent)
-  **`services/common/health.py`** - `HealthManager` with dependency tracking
-  **`services/common/logging.py`** - Structured JSON logging
-  **`services/common/audio.py`** - `AudioProcessor` with format conversion
-  **`services/common/correlation.py`** - Correlation ID management
-  **`services/common/resilient_http.py`** - Circuit breaker patterns

### **Good Patterns (Repurpose)**
-  **MCP Integration**: Current `MCPManager` and `StdioMCPClient`
-  **Audio Processing**: VAD, aggregation, and segmentation concepts
-  **Health Checks**: Standardized health check patterns
-  **Configuration**: Service-specific config classes

### **Replaceable Components**
-  **Orchestrator Logic**: Current HTTP-based transcript processing
-  **Audio Pipeline**: Current `AudioPipeline` implementation
-  **MCP Implementation**: Current stdio-based MCP client
-  **Service Architecture**: Current microservices approach

---

## 🚨 **Critical Gaps in Proposed Plan**

### **1. Missing Current System Analysis**
-  Plan doesn't account for existing `AudioProcessor` class
-  Plan doesn't leverage existing `ConfigBuilder` system
-  Plan doesn't build upon existing health check patterns

### **2. Type System Conflicts**
-  Plan proposes `AudioChunk` but `PCMFrame` already exists
-  Plan proposes `ProcessedSegment` but `AudioSegment` already exists
-  Plan proposes `ConversationContext` but session management exists

### **3. Architecture Mismatch**
-  Plan assumes greenfield but system is working microservices
-  Plan proposes replacing working MCP integration
-  Plan doesn't leverage existing audio processing concepts

### **4. Missing Integration Points**
-  Plan doesn't account for current Docker Compose setup
-  Plan doesn't leverage existing CI/CD patterns
-  Plan doesn't build upon existing testing framework

---

## 🎯 **Recommended Approach**

### **Phase -1: Infrastructure Preservation**
-  **Keep**: `services/common/config.py`, `services/common/health.py`, `services/common/logging.py`
-  **Audit**: Current configuration patterns and environment variables
-  **Document**: Current API contracts and data flow patterns

### **Phase 0: Agent Framework (New)**
-  **Create**: New agent system alongside existing orchestrator
-  **Build**: Upon existing MCP concepts but with new implementation
-  **Integrate**: With existing health check and configuration patterns

### **Phase 1: Audio Adapter System (New)**
-  **Create**: New audio adapter system alongside existing audio pipeline
-  **Build**: Upon existing `AudioProcessor` concepts
-  **Integrate**: With existing VAD and aggregation patterns

### **Phase 2: Pipeline Integration (Replace)**
-  **Replace**: Current `AudioPipeline` with new adapter-based system
-  **Replace**: Current orchestrator with new agent-based system
-  **Replace**: Current MCP implementation with new tool system

### **Phase 3: Testing & Documentation**
-  **Test**: New system with existing testing framework
-  **Document**: Architecture decisions and learning outcomes
-  **Validate**: End-to-end functionality

---

## 📋 **Implementation Checklist**

### **Before Starting**
-  [ ] Audit current configuration system
-  [ ] Document current API contracts
-  [ ] Map current data flow patterns
-  [ ] Identify reusable components
-  [ ] Plan integration points

### **During Implementation**
-  [ ] Preserve excellent infrastructure
-  [ ] Build upon good patterns
-  [ ] Replace implementation details
-  [ ] Maintain existing testing framework
-  [ ] Document architectural decisions

### **After Implementation**
-  [ ] Validate end-to-end functionality
-  [ ] Update documentation
-  [ ] Create learning examples
-  [ ] Document trade-offs and decisions

---

## 🎯 **Success Criteria**

### **Technical Success**
-  New agent framework working
-  New audio adapter system working
-  New pipeline integration working
-  All tests passing
-  Documentation complete

### **Learning Success**
-  Understand trade-offs between approaches
-  Know when to use old vs. new patterns
-  Can explain architectural decisions
-  Have examples for future reference

---

**Next Steps:**
-  Audit current configuration system
-  Document current API contracts
-  Map current data flow patterns
-  Identify reusable components
-  Plan integration points
-  Begin implementation with preserved infrastructure
