# Audio-First AI Orchestrator Platform — Enhancement Plan

**Repository:** `audio-orchestrator` (renamed from discord-voice-lab)
**Python Version:** 3.11
**Branch Strategy:** Feature branches from `main`, one PR per functional change
**Quality Gates:** All PRs must pass `make test` and `make lint`
**Test Framework:** pytest, pytest-asyncio
**Linting Tools:** black, ruff, mypy

## 🎯 **IMPLEMENTATION PROGRESS**

### ✅ **COMPLETED PHASES**
-  **Phase -1: Infrastructure Preservation & Baseline** ✅ **COMPLETED & MERGED**
-  **Phase 0: Modular Agent Framework** ✅ **COMPLETED & MERGED**
-  **Phase 1: I/O Adapter Framework** ✅ **COMPLETED & MERGED**
-  **Phase 2: Audio Pipeline Enhancement** ✅ **COMPLETED & MERGED**
-  **Phase 3: Context & Session Management** ✅ **COMPLETED & MERGED**
-  **Phase 4: Advanced Agent Capabilities** ✅ **COMPLETED & MERGED**

### 🔄 **CURRENT STATUS**
-  **All core phases complete:** Phases -1 through 4 are fully implemented
-  **All critical functionality working:** Agent framework, adapters, pipeline, context, and advanced agents
-  **All tests passing:** Comprehensive test coverage across all implemented phases
-  **Ready for documentation and optimization:** Focus on Phases 5 and 6

### 📋 **REMAINING PHASES**
-  **Phase 5: Documentation & Developer Experience** (Partially Complete - ~60%)
-  **Phase 6: Performance & Observability** (Partially Complete - ~40%)

---

## 🚨 **CRITICAL AI AGENT WORKFLOW REQUIREMENTS**

### **MANDATORY PR WORKFLOW - NO EXCEPTIONS**

**⚠️ AI AGENT MUST FOLLOW THIS EXACT SEQUENCE FOR EVERY PR:**

-  **Create New Branch:** `git checkout main && git pull origin main && git checkout -b feature/[pr-name]`
-  **Implement Changes:** Complete all tasks for the specific PR
-  **Test & Lint:** Run `make test` and `make lint` - MUST PASS
-  **Commit Changes:** `git add . && git commit -m "[PR Name]: [Description]"`
-  **Push Branch:** `git push origin feature/[pr-name]`
-  **Create PR:** Use GitHub MCP tools to create pull request
-  **Wait for Review:** Do NOT proceed until PR is reviewed and approved
-  **Apply Fixes:** If review feedback, make changes and push updates
-  **Wait for Merge:** Do NOT proceed until PR is merged to main
-  **Return to Main:** `git checkout main && git pull origin main`
-  **Repeat:** Only then start next PR with new branch

### **ABSOLUTE REQUIREMENTS**
-  ❌ **NEVER work on multiple PRs simultaneously**
-  ❌ **NEVER skip the review process**
-  ❌ **NEVER merge your own PRs**
-  ❌ **NEVER proceed to next PR until current is merged**
-  ✅ **ALWAYS create new branch for each PR**
-  ✅ **ALWAYS wait for human review and approval**
-  ✅ **ALWAYS return to main after merge**
-  ✅ **ALWAYS follow the exact sequence above**

---

## Code Quality Standards (All PRs)

### Implementation Requirements
-  **Async patterns:** All I/O operations use `async def` / `await`
-  **Type hints:** Comprehensive type annotations (mypy compliance)
-  **Docstrings:** Module-level docstrings for all new modules
-  **TODO comments:** Mark incomplete integrations with `# TODO: <description>`
-  **Tests:** Generate test file alongside implementation
-  **Style checks:** Must pass `black --check`, `ruff check`, `mypy`
-  **Quality gates:** Must pass `make lint` and `make test`

### Performance Targets
-  **Wake detection:** < 200ms
-  **STT processing:** < 300ms from speech onset
-  **Command response:** < 2s total (end-to-end)
-  **Voice join/response:** 10-15s acceptable
-  **Test coverage:** Maintain ≥ 80% overall

### Core Type Definitions
```python
# Audio Types (Build upon existing types)
# Current: PCMFrame, AudioSegment in services/discord/audio.py
# New: AudioChunk (enhanced version of PCMFrame)
AudioChunk = NamedTuple(
    pcm_bytes: bytes,
    sample_rate: int,
    channels: int,
    timestamp_ms: int
)

# Current: AudioSegment in services/discord/audio.py  
# New: ProcessedSegment (enhanced version of AudioSegment)
ProcessedSegment = NamedTuple(
    transcript: str,
    start_time_ms: int,
    end_time_ms: int,
    confidence: Optional[float] = None,
    language: Optional[str] = None
)

# Context Types (Build upon existing session management)
ConversationContext = NamedTuple(
    session_id: str,
    history: list[tuple[str, str]],  # (user_input, agent_response) pairs
    created_at: datetime,
    last_active_at: datetime,
    metadata: Optional[dict] = None
)

# Agent Types (New)
AgentResponse = dataclass(
    response_text: Optional[str] = None,
    response_audio: Optional[AsyncIterator[AudioChunk]] = None,
    actions: list[ExternalAction] = field(default_factory=list)
)
```

### Monitoring Metrics (prometheus_client)
```python
# Counters
audio_chunks_processed_total = Counter(
    'audio_chunks_processed_total',
    'Total audio chunks processed through pipeline'
)

agent_invocations_total = Counter(
    'agent_invocations_total',
    'Total agent invocations',
    ['agent_name']
)

# Histograms
transcription_latency_seconds = Histogram(
    'transcription_latency_seconds',
    'STT transcription latency in seconds'
)

agent_execution_latency_seconds = Histogram(
    'agent_execution_latency_seconds',
    'Agent execution latency in seconds',
    ['agent_name']
)

tts_synthesis_latency_seconds = Histogram(
    'tts_synthesis_latency_seconds',
    'TTS synthesis latency in seconds'
)

end_to_end_response_latency_seconds = Histogram(
    'end_to_end_response_latency_seconds',
    'Total response time from input to output'
)
```

---

## 🚨 **Critical Plan Corrections Based on Source of Truth Analysis**

### **What We're Preserving (Excellent Work)**
-  **`services/common/config.py`** - `ConfigBuilder` system (excellent, keep as-is)
-  **`services/common/health.py`** - `HealthManager` with dependency tracking (excellent, keep as-is)
-  **`services/common/logging.py`** - Structured JSON logging (excellent, keep as-is)
-  **`services/common/audio.py`** - `AudioProcessor` with format conversion (excellent, keep as-is)
-  **`services/common/correlation.py`** - Correlation ID management (excellent, keep as-is)
-  **`services/common/resilient_http.py`** - Circuit breaker patterns (excellent, keep as-is)
-  **Testing framework** - Current unit/component/integration test structure (excellent, keep as-is)
-  **Docker Compose setup** - Current service orchestration (excellent, keep as-is)

### **What We're Building Upon (Good Patterns)**
-  **MCP Integration concepts** - Current `MCPManager` patterns (repurpose)
-  **Audio processing concepts** - Current VAD and aggregation patterns (repurpose)
-  **Health check patterns** - Current standardized health checks (repurpose)
-  **Configuration patterns** - Current service-specific configs (repurpose)

### **What We're Replacing (Implementation Details)**
-  **Orchestrator logic** - Current HTTP-based transcript processing (replace)
-  **Audio pipeline** - Current `AudioPipeline` implementation (replace)
-  **MCP implementation** - Current stdio-based MCP client (replace)
-  **Service architecture** - Current microservices approach (replace)

### **Type System Alignment**
-  **Current**: `PCMFrame`, `AudioSegment` in `services/discord/audio.py`
-  **New**: `AudioChunk`, `ProcessedSegment` (enhanced versions)
-  **Current**: `AudioMetadata` in `services/common/audio.py`
-  **New**: `AudioFormat` (enhanced version)

### **Implementation Strategy**
-  **Preserve Infrastructure**: Keep excellent `services/common/*` components
-  **Build Upon Patterns**: Extend existing MCP, audio, and health patterns
-  **Replace Implementation**: New agent/adapter system alongside existing
-  **Gradual Migration**: Build new architecture alongside existing system
-  **Learning Focus**: Document trade-offs and architectural decisions

---

## Phase -1: Infrastructure Preservation & Baseline ✅ COMPLETED

**Branch:** `cleanup/baseline-state` → **MERGED**
**Objective:** Preserve excellent existing infrastructure while establishing clean baseline for new architecture.

### ✅ COMPLETED TASKS

-  **✅ Preserve Excellent Infrastructure (Keep As-Is)**
   -  **`services/common/config.py`** - `ConfigBuilder` system (excellent, keep) ✅
   -  **`services/common/health.py`** - `HealthManager` with dependency tracking (excellent, keep) ✅
   -  **`services/common/logging.py`** - Structured JSON logging (excellent, keep) ✅
   -  **`services/common/audio.py`** - `AudioProcessor` with format conversion (excellent, keep) ✅
   -  **`services/common/correlation.py`** - Correlation ID management (excellent, keep) ✅
   -  **`services/common/resilient_http.py`** - Circuit breaker patterns (excellent, keep) ✅

-  **✅ Audit Current System State**
   -  Document current API contracts (all service endpoints) ✅
   -  Map current data flow patterns (Discord → STT → Orchestrator → LLM → TTS) ✅
   -  Catalog existing data types (`PCMFrame`, `AudioSegment`, `AudioMetadata`) ✅
   -  Identify current MCP integration patterns ✅
   -  Document current configuration patterns ✅

-  **✅ Clean Up Dead Code**
   -  Run `vulture` or manual audit to find unused code ✅
   -  Remove unused imports across all services ✅
   -  Delete commented-out code blocks (convert to issues if needed) ✅
   -  Clean up TODO comments (convert to GitHub issues or remove) ✅
   -  Remove deprecated functions/classes ✅

-  **✅ Standardize Configuration**
   -  Verify all services use `services.common.config.ConfigBuilder` (already excellent) ✅
   -  Verify all `.env.sample` entries are documented ✅
   -  Remove duplicate configuration patterns ✅
   -  Audit environment variable usage for consistency ✅
   -  Document all config fields in README ✅

-  **✅ Update Documentation**
   -  Fix broken internal links in `docs/` ✅
   -  Update outdated service descriptions ✅
   -  Ensure all README files are current ✅
   -  Update architecture diagrams in `docs/architecture/` ✅
   -  Verify MCP documentation is accurate ✅

-  **✅ Test Coverage Baseline**
   -  Run `make test` and document current coverage (baseline) ✅
   -  Identify untested critical paths ✅
   -  Fix any flaky tests ✅
   -  Document known test gaps in GitHub issues ✅
   -  Set up coverage reporting in CI ✅

-  **✅ Linting Cleanup**
   -  Run `make lint-fix` and commit results ✅
   -  Address remaining linting violations ✅
   -  Ensure all services pass type checking ✅
   -  Update `pyproject.toml` if needed ✅

-  **✅ Dependency Audit**
   -  Review all `requirements.txt` files ✅
   -  Update to latest compatible versions ✅
   -  Remove unused dependencies ✅
   -  Run `pip-audit` for security vulnerabilities ✅
   -  Document any known issues ✅

**✅ COMPLETED:** "Infrastructure Preservation: Establish Clean Baseline State"

**✅ SUCCESS CRITERIA MET:**
-  All tests pass: `make test` ✅
-  All linters pass: `make lint` ✅
-  Documentation current and links working ✅
-  Baseline coverage documented ✅
-  No critical security vulnerabilities ✅
-  **Preserved excellent infrastructure components** ✅
-  **Current system state fully documented** ✅

---

## Phase 0: Modular Agent Framework ✅ COMPLETED

**Objective:** Create abstractions for pluggable agents within the orchestrator service, enabling flexible response generation strategies. **Build upon existing orchestrator patterns rather than replacing them.**

### ✅ PR 0.1: Agent Base Interface & Types - COMPLETED

**Branch:** `feature/agent-base-interface` → **MERGED**

**✅ COMPLETED TASKS:**
-  ✅ Create `services/orchestrator/agents/__init__.py`
-  ✅ Create `services/orchestrator/agents/types.py` with:
  -  `AgentResponse` dataclass with response_text, response_audio, actions, metadata
  -  `ConversationContext` dataclass with session_id, history, created_at, last_active_at, metadata
  -  `ExternalAction` dataclass for agent actions
-  ✅ Create `services/orchestrator/agents/base.py` with:
  -  `BaseAgent` abstract base class
  -  `handle()` abstract method for processing conversations
  -  `name` property for agent identification
  -  `can_handle()` method for agent selection
-  ✅ Add unit tests for type validation in `services/orchestrator/tests/unit/test_agent_types.py`
-  ✅ Add docstrings explaining agent lifecycle and patterns

**✅ EXIT CONDITION MET:** Base abstractions defined, tests pass, documentation complete

---

### ✅ PR 0.2: Echo Agent Implementation - COMPLETED

**Branch:** `feature/echo-agent` → **MERGED**

**✅ COMPLETED TASKS:**
-  ✅ Implement `services/orchestrator/agents/echo_agent.py` with:
  -  `EchoAgent` class inheriting from `BaseAgent`
  -  `name` property returning "echo"
  -  `can_handle()` method for agent selection
  -  `handle()` method that echoes user input back
-  ✅ Create `services/orchestrator/tests/unit/test_echo_agent.py` with:
  -  Tests for `can_handle()` method with various inputs
  -  Tests for `handle()` method with basic and edge cases
  -  Tests for long input handling
-  ✅ Add integration test that invokes echo agent through orchestrator

**✅ EXIT CONDITION MET:** Echo agent functional, all tests pass

---

### ✅ PR 0.3: Agent Manager & Registry - COMPLETED

**Branch:** `feature/agent-manager` → **MERGED**

**✅ COMPLETED TASKS:**
-  ✅ Create `services/orchestrator/agents/registry.py` with:
  -  `AgentRegistry` class for managing available agents
  -  `register()` method to register agents by name
  -  `get()` method to retrieve agents by name
  -  `list_agents()` method to list all registered agent names
  -  `get_stats()` method for registry statistics
-  ✅ Create `services/orchestrator/agents/manager.py` with:
  -  `AgentManager` class for agent selection and routing
  -  `register_agent()` method for adding agents
  -  `select_agent()` async method for agent selection based on transcript and context
  -  `process_transcript()` async method for processing transcripts with selected agents
  -  Keyword-based routing logic (echo detection)
-  ✅ Add configuration support in `services/orchestrator/config.py`:
  -  `AGENT_DEFAULT` environment variable
  -  `AGENT_ROUTING_ENABLED` environment variable
-  ✅ Unit tests for routing logic in `services/orchestrator/tests/unit/test_agent_manager.py`
-  ✅ Integration test for agent selection with multiple agents

**✅ EXIT CONDITION MET:** Agent routing works, multiple agents can be registered, tests pass

---

## Phase 1: I/O Adapter Framework ✅ COMPLETED

**Objective:** Abstract audio input/output to support multiple sources beyond Discord (files, WebRTC, etc.). **Build upon existing AudioProcessor and audio pipeline concepts rather than replacing them.**

### ✅ PR 1.1: Audio Adapter Interfaces & Types - COMPLETED

**Branch:** `feature/audio-adapter-interfaces` → **MERGED**

**✅ COMPLETED TASKS:**
-  ✅ Create `services/orchestrator/adapters/__init__.py`
-  ✅ Create `services/orchestrator/adapters/types.py` with:
  -  `AudioMetadata` dataclass with sample_rate, channels, sample_width, duration, frames, format, bit_depth
  -  `AudioChunk` dataclass with data, metadata, correlation_id, sequence_number, is_silence, volume_level
  -  `AdapterConfig` dataclass for adapter configuration
-  ✅ Create `services/orchestrator/adapters/base.py` with:
  -  `AudioInputAdapter` abstract base class with start_capture(), stop_capture(), get_audio_stream(), is_active
  -  `AudioOutputAdapter` abstract base class with play_audio(), stop_playback(), is_playing
-  ✅ Add comprehensive docstrings with usage examples
-  ✅ Unit tests for type validation in `services/orchestrator/tests/unit/adapters/test_adapter_types.py`

**✅ EXIT CONDITION MET:** Interfaces defined, documented, tested

---

### ✅ PR 1.2: Adapter Registry - COMPLETED

**Branch:** `feature/adapter-registry` → **MERGED**

**✅ COMPLETED TASKS:**
-  ✅ Create `services/orchestrator/adapters/manager.py` with:
  -  `AdapterManager` class for managing audio I/O adapters
  -  `register_input_adapter()` and `register_output_adapter()` methods
  -  `get_input_adapter()` and `get_output_adapter()` methods
  -  `list_input_adapters()` and `list_output_adapters()` methods
  -  `health_check()` method for adapter health monitoring
-  ✅ Add configuration-based adapter selection in `services/orchestrator/config.py`:
  -  `AUDIO_INPUT_ADAPTER` environment variable
  -  `AUDIO_OUTPUT_ADAPTER` environment variable
-  ✅ Unit tests for registry operations in `services/orchestrator/tests/unit/adapters/test_adapter_manager.py`

**✅ EXIT CONDITION MET:** Registry functional, tests pass

---

### ✅ PR 1.3: Discord Adapter Implementation - COMPLETED

**Branch:** `feature/discord-adapter-refactor` → **MERGED**

**✅ COMPLETED TASKS:**
-  ✅ Create `services/orchestrator/adapters/discord_input.py` with:
  -  `DiscordAudioInputAdapter` class implementing `AudioInputAdapter`
  -  `start_capture()` method for starting Discord audio capture
  -  `stop_capture()` method for stopping audio capture
  -  `get_audio_stream()` async generator for yielding audio chunks
  -  `is_active` property for checking capture status
-  ✅ Create `services/orchestrator/adapters/discord_output.py` with:
  -  `DiscordAudioOutputAdapter` class implementing `AudioOutputAdapter`
  -  `play_audio()` method for playing audio to Discord voice channel
  -  `stop_playback()` method for stopping audio playback
  -  `is_playing` property for checking playback status
-  ✅ Refactor existing Discord voice code to implement adapter interfaces
-  ✅ Register adapters in `services/orchestrator/adapters/manager.py`
-  ✅ Integration tests for Discord adapters in `services/orchestrator/tests/unit/adapters/test_discord_adapters.py`
-  ✅ Verify no regression in Discord functionality

**✅ EXIT CONDITION MET:** Discord service uses adapter pattern, all tests pass, no functional regression

---

### ✅ PR 1.4: File-Based Audio Adapter (Testing) - COMPLETED

**Branch:** `feature/file-audio-adapter` → **MERGED**

**✅ COMPLETED TASKS:**
-  ✅ Create `services/orchestrator/adapters/file_adapter.py` with:
  -  `FileAudioInputAdapter` class for reading audio from files
  -  `FileAudioOutputAdapter` class for writing audio to files
  -  File-based audio processing for testing and debugging
-  ✅ Register file adapters in `services/orchestrator/adapters/manager.py`
-  ✅ Integration tests using test audio files from `tests/fixtures/`
-  ✅ Document usage for testing in `docs/guides/testing_with_file_adapter.md`

**✅ EXIT CONDITION MET:** File adapter works, useful for testing, documented

---

## Phase 2: Audio Pipeline Enhancement ✅ COMPLETED

**Objective:** Formalize audio processing pipeline with conversion, normalization, and streaming support. **Build upon existing AudioPipeline in services/discord/audio.py rather than replacing it.**

### ✅ PR 2.1: Audio Conversion Module - COMPLETED

**Branch:** `feature/audio-conversion` → **MERGED**

**✅ COMPLETED TASKS:**
-  ✅ Create `services/orchestrator/pipeline/audio_processor.py` with:
  -  `AudioProcessor` class for audio format conversion and processing
  -  `process_audio_chunk()` method for processing individual audio chunks
  -  Format conversion, resampling, normalization, noise reduction, enhancement
  -  Audio quality metrics calculation (volume, noise, clarity)
  -  Error handling with proper ProcessedSegment validation
-  ✅ Use `ffmpeg-python` or `PyAV` for actual conversion
-  ✅ Add format detection and validation
-  ✅ Unit tests with various audio formats in `services/orchestrator/tests/unit/pipeline/test_audio_processor.py`
-  ✅ Performance benchmarks for conversion operations

**✅ EXIT CONDITION MET:** Audio conversion works reliably, tests pass, performance acceptable

---

### ✅ PR 2.2: Audio Processing Pipeline - COMPLETED

**Branch:** `feature/audio-pipeline` → **MERGED**

**✅ COMPLETED TASKS:**
-  ✅ Create `services/orchestrator/pipeline/pipeline.py` with:
  -  `AudioPipeline` class for processing audio streams
  -  `process_audio_stream()` async generator for streaming audio processing
  -  Integration with `AudioProcessor` and `WakeDetector`
  -  Chunking and buffering logic
  -  Back-pressure handling
-  ✅ Create `services/orchestrator/pipeline/wake_detector.py` with:
  -  `WakeDetector` class for wake phrase detection
  -  `detect_wake_phrase()` method for analyzing audio segments
  -  Audio-based analysis using energy and complexity metrics
  -  Confidence threshold validation
-  ✅ Create `services/orchestrator/pipeline/types.py` with:
  -  `ProcessingConfig` dataclass for pipeline configuration
  -  `ProcessedSegment` dataclass for processed audio segments
  -  `ProcessingStatus` enum for segment status
  -  `AudioFormat` enum for audio format types
-  ✅ Implement async generator pattern for streaming
-  ✅ Integration tests with real audio streams in `services/orchestrator/tests/unit/pipeline/test_audio_pipeline.py`

**✅ EXIT CONDITION MET:** Pipeline handles streaming audio efficiently, tests pass

---

### ✅ PR 2.3: Integrate Pipeline with Orchestrator - COMPLETED

**Branch:** `feature/integrate-audio-pipeline` → **MERGED**

**✅ COMPLETED TASKS:**
-  ✅ Create `services/orchestrator/integration/pipeline_integration.py` with:
  -  `PipelineIntegration` class for coordinating audio pipeline with I/O adapters
  -  `start_processing()` and `stop_processing()` methods for session management
  -  `_process_audio_stream()` method for processing audio streams
  -  `_handle_processed_segment()` method for handling processed segments
  -  Segment callback mechanism for forwarding to agents
-  ✅ Create `services/orchestrator/integration/agent_integration.py` with:
  -  `AgentIntegration` class for coordinating processed audio with agent framework
  -  `handle_processed_segment()` method for processing segments with agents
  -  `_get_or_create_context()` method for session context management
  -  `_process_with_agents()` method for agent processing
-  ✅ Create `services/orchestrator/integration/audio_orchestrator.py` with:
  -  `AudioOrchestrator` class as main system coordinator
  -  `initialize()` method for orchestrator initialization
  -  `start_session()` and `stop_session()` methods for session management
  -  `handle_processed_segment()` method for processing segments
  -  `get_session_status()` and `get_orchestrator_status()` methods for status
-  ✅ Add pipeline configuration options to `services/orchestrator/config.py`
-  ✅ Verify latency remains acceptable (< 2s end-to-end)
-  ✅ Integration tests across services in `services/orchestrator/tests/integration/test_audio_orchestrator.py`
-  ✅ Add metrics tracking for pipeline stages

**✅ EXIT CONDITION MET:** Orchestrator uses unified pipeline, no performance regression, all tests pass

---

## Phase 3: Context & Session Management

**🚨 AI AGENT REMINDER: FOLLOW PR WORKFLOW**
-  **Create new branch:** `git checkout main && git pull origin main && git checkout -b feature/phase-3-context-types`
-  **Complete PR tasks:** Implement all requirements below
-  **Test & lint:** Run `make test` and `make lint` - MUST PASS
-  **Create PR:** Use GitHub MCP tools, tag `@codex review` and `@cursor review`
-  **Wait for review:** Do NOT proceed until PR is reviewed and merged
-  **Return to main:** Only then start next PR

**Objective:** Formalize conversation context and session persistence for multi-turn conversations. **Build upon existing session management patterns in orchestrator rather than replacing them.**

### PR 3.1: Context Types & Storage Interface

**Branch:** `feature/context-types`

**Tasks:**
-  Create `services/orchestrator/context/types.py`:
  ```python
  from dataclasses import dataclass
  from datetime import datetime
  from typing import Optional, List
  
  @dataclass
  class Session:
      """User session metadata."""
      id: str
      created_at: datetime
      last_active_at: datetime
      metadata: dict
  
  @dataclass
  class ConversationContext:
      """Complete conversation state."""
      session_id: str
      history: List[tuple[str, str]]  # (user, agent) pairs
      created_at: datetime
      last_active_at: datetime
      metadata: Optional[dict] = None
  ```
-  Create `services/orchestrator/context/storage_interface.py`:
  ```python
  from abc import ABC, abstractmethod
  
  class StorageInterface(ABC):
      """Abstract interface for context/session storage."""
      
      @abstractmethod
      async def get_session(self, session_id: str) -> Session:
          """Retrieve or create session."""
          pass
      
      @abstractmethod
      async def save_context(
          self,
          session_id: str,
          context: ConversationContext
      ) -> None:
          """Save conversation context."""
          pass
      
      @abstractmethod
      async def log_agent_execution(
          self,
          session_id: str,
          agent_name: str,
          transcript: str,
          response_text: str,
          latency_ms: int
      ) -> None:
          """Log agent execution for analytics."""
          pass
  ```
-  Add validation and serialization helpers
-  Unit tests for types in `services/orchestrator/tests/unit/test_context_types.py`

**Exit Condition:** Context types defined and tested

---

### PR 3.2: In-Memory Context Storage

**Branch:** `feature/memory-context-storage`

**Tasks:**
-  Implement `services/orchestrator/context/memory_storage.py`:
  ```python
  from collections import OrderedDict
  from datetime import datetime, timedelta
  import asyncio
  
  class MemoryStorage(StorageInterface):
      """In-memory context storage with LRU eviction."""
      
      def __init__(self, max_sessions: int = 1000, ttl_minutes: int = 60):
          self._sessions: OrderedDict[str, Session] = OrderedDict()
          self._contexts: OrderedDict[str, ConversationContext] = OrderedDict()
          self._lock = asyncio.Lock()
          self.max_sessions = max_sessions
          self.ttl = timedelta(minutes=ttl_minutes)
      
      async def get_session(self, session_id: str) -> Session:
          """Get or create session."""
          async with self._lock:
              if session_id not in self._sessions:
                  self._sessions[session_id] = Session(
                      id=session_id,
                      created_at=datetime.now(),
                      last_active_at=datetime.now(),
                      metadata={}
                  )
              else:
                  # Move to end (LRU)
                  self._sessions.move_to_end(session_id)
                  self._sessions[session_id].last_active_at = datetime.now()
              
              # Evict old sessions
              await self._evict_old_sessions()
              
              return self._sessions[session_id]
      
      async def save_context(
          self,
          session_id: str,
          context: ConversationContext
      ) -> None:
          """Save context to memory."""
          async with self._lock:
              self._contexts[session_id] = context
              if session_id in self._sessions:
                  self._sessions[session_id].last_active_at = datetime.now()
      
      async def log_agent_execution(
          self,
          session_id: str,
          agent_name: str,
          transcript: str,
          response_text: str,
          latency_ms: int
      ) -> None:
          """Log execution (print for now)."""
          logger.info(
              f"Agent execution: {agent_name} for session {session_id}, "
              f"latency: {latency_ms}ms"
          )
      
      async def _evict_old_sessions(self) -> None:
          """Evict sessions based on TTL and max count."""
          now = datetime.now()
          
          # Remove expired sessions
          expired = [
              sid for sid, session in self._sessions.items()
              if now - session.last_active_at > self.ttl
          ]
          for sid in expired:
              del self._sessions[sid]
              if sid in self._contexts:
                  del self._contexts[sid]
          
          # LRU eviction if over max
          while len(self._sessions) > self.max_sessions:
              sid, _ = self._sessions.popitem(last=False)  # Remove oldest
              if sid in self._contexts:
                  del self._contexts[sid]
  ```
-  Thread-safe operations using asyncio locks
-  TTL-based expiration
-  Unit tests for storage operations in `services/orchestrator/tests/unit/test_memory_storage.py`

**Exit Condition:** In-memory storage works for single-instance deployment

---

### PR 3.3: Context Manager

**Branch:** `feature/context-manager`

**Tasks:**
-  Create `services/orchestrator/context/manager.py`:
  ```python
  class ContextManager:
      """Manages conversation context lifecycle."""
      
      def __init__(self, storage: StorageInterface):
          self.storage = storage
      
      async def get_context(self, session_id: str) -> ConversationContext:
          """Get or create context for session."""
          session = await self.storage.get_session(session_id)
          
          # Try to load existing context
          # TODO: Implement context retrieval
          
          # Create new context if none exists
          return ConversationContext(
              session_id=session_id,
              history=[],
              created_at=session.created_at,
              last_active_at=session.last_active_at
          )
      
      async def update_context(self, context: ConversationContext) -> None:
          """Update and persist context."""
          await self.storage.save_context(context.session_id, context)
      
      async def save_context(self, context: ConversationContext) -> None:
          """Explicitly save context."""
          await self.storage.save_context(context.session_id, context)
  ```
-  Implement `get_context()`, `update_context()`, `save_context()`
-  Add context lifecycle management (creation, updates, expiration)
-  Integration with agent manager
-  Unit tests in `services/orchestrator/tests/unit/test_context_manager.py`
-  Integration tests in `services/orchestrator/tests/integration/test_context_lifecycle.py`

**Exit Condition:** Context management works end-to-end

---

### PR 3.4: SQL-Based Context Storage (Optional)

**Branch:** `feature/sql-context-storage`

**Tasks:**
-  Implement `services/orchestrator/context/sql_storage.py`:
  ```python
  from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
  from sqlalchemy.orm import sessionmaker
  
  class SqlStorage(StorageInterface):
      """SQL-based persistent storage using SQLAlchemy."""
      
      def __init__(self, db_url: str):
          self.engine = create_async_engine(db_url)
          self.async_session = sessionmaker(
              self.engine,
              class_=AsyncSession,
              expire_on_commit=False
          )
          # TODO: Define SQLAlchemy models
      
      async def init_db(self) -> None:
          """Initialize database schema."""
          # TODO: Create tables
          pass
      
      async def get_session(self, session_id: str) -> Session:
          """Retrieve or create session from DB."""
          # TODO: Query session table
          pass
      
      async def save_context(
          self,
          session_id: str,
          context: ConversationContext
      ) -> None:
          """Save context to database."""
          # TODO: Insert/update context
          pass
      
      async def log_agent_execution(
          self,
          session_id: str,
          agent_name: str,
          transcript: str,
          response_text: str,
          latency_ms: int
      ) -> None:
          """Log execution to analytics table."""
          # TODO: Insert execution log
          pass
  ```
-  Use SQLAlchemy async for PostgreSQL
-  Schema migration support (Alembic)
-  Integration tests with test database in `services/orchestrator/tests/integration/test_sql_storage.py`
-  Configuration for storage backend selection in `.env`:
  ```bash
  CONTEXT_STORAGE_BACKEND=memory  # or "sql"
  CONTEXT_DB_URL=postgresql+asyncpg://user:pass@localhost/db
  ```

**Exit Condition:** SQL storage available for production use

---

## Phase 4: Advanced Agent Capabilities

**🚨 AI AGENT REMINDER: FOLLOW PR WORKFLOW**
-  **Create new branch:** `git checkout main && git pull origin main && git checkout -b feature/phase-4-summarization-agent`
-  **Complete PR tasks:** Implement all requirements below
-  **Test & lint:** Run `make test` and `make lint` - MUST PASS
-  **Create PR:** Use GitHub MCP tools, tag `@codex review` and `@cursor review`
-  **Wait for review:** Do NOT proceed until PR is reviewed and merged
-  **Return to main:** Only then start next PR

**Objective:** Implement sophisticated agents with LLM integration and multi-turn conversations.

### PR 4.1: Summarization Agent

**Branch:** `feature/summarization-agent`

**Tasks:**
-  Create `services/orchestrator/agents/summarization_agent.py`:
  ```python
  class SummarizationAgent(BaseAgent):
      """Agent that summarizes conversation history."""
      
      def __init__(self, llm_service_url: str):
          self.llm_url = llm_service_url
      
      @property
      def name(self) -> str:
          return "summarization"
      
      async def handle(
          self,
          context: ConversationContext,
          transcript: str
      ) -> AgentResponse:
          """Generate summary of conversation history.
          
          Args:
              context: Conversation context with history
              transcript: User's request (e.g., "summarize our conversation")
              
          Returns:
              AgentResponse with summary text
          """
          if not context.history:
              return AgentResponse(
                  response_text="There's no conversation history to summarize yet."
              )
          
          # Build prompt from history
          history_text = "\n".join([
              f"User: {user}\nAssistant: {agent}"
              for user, agent in context.history
          ])
          
          # TODO: Call LLM service to generate summary
          summary = f"(Summary placeholder for {len(context.history)} turns)"
          
          return AgentResponse(response_text=summary)
  ```
-  Use context history to generate summaries
-  Integrate with LLM service via HTTP
-  Add configuration for summary triggers:
  ```python
  SUMMARY_MIN_TURNS = env.int("SUMMARY_MIN_TURNS", default=5)
  SUMMARY_TRIGGER_KEYWORDS = env.list("SUMMARY_TRIGGER_KEYWORDS", default=["summarize", "summary"])
  ```
-  Unit tests in `services/orchestrator/tests/unit/test_summarization_agent.py`
-  Integration tests with LLM service in `services/orchestrator/tests/integration/test_summarization_integration.py`

**Exit Condition:** Summarization agent functional, tests pass

---

### PR 4.2: Intent Classification Agent

**Branch:** `feature/intent-agent`

**Tasks:**
-  Create `services/orchestrator/agents/intent_agent.py`:
  ```python
  class IntentClassificationAgent(BaseAgent):
      """Classifies user intent and routes to specialized agents."""
      
      def __init__(self, llm_service_url: str, agent_manager: 'AgentManager'):
          self.llm_url = llm_service_url
          self.agent_manager = agent_manager
      
      @property
      def name(self) -> str:
          return "intent_classifier"
      
      async def handle(
          self,
          context: ConversationContext,
          transcript: str
      ) -> AgentResponse:
          """Classify intent and route to appropriate agent."""
          # TODO: Call LLM for intent classification
          intent = await self._classify_intent(transcript)
          
          # Route to specialized agent
          agent = self._get_agent_for_intent(intent)
          return await agent.handle(context, transcript)
      
      async def _classify_intent(self, transcript: str) -> str:
          """Classify user intent using LLM."""
          # TODO: LLM call
          return "general"
      
      def _get_agent_for_intent(self, intent: str) -> BaseAgent:
          """Get agent based on classified intent."""
          # TODO: Intent-to-agent mapping
          return self.agent_manager.registry.get("echo")
  ```
-  Integrate with LLM service for classification
-  Add intent configuration:
  ```python
  INTENT_CLASSES = env.json("INTENT_CLASSES", default={
      "echo": "echo",
      "summarize": "summarization",
      "general": "conversation"
  })
  ```
-  Tests with various intent types in `services/orchestrator/tests/unit/test_intent_agent.py`

**Exit Condition:** Intent-based routing works

---

### PR 4.3: Multi-Turn Conversation Agent

**Branch:** `feature/conversation-agent`

**Tasks:**
-  Create `services/orchestrator/agents/conversation_agent.py`:
  ```python
  class ConversationAgent(BaseAgent):
      """Agent for natural multi-turn conversations."""
      
      def __init__(self, llm_service_url: str, max_history: int = 10):
          self.llm_url = llm_service_url
          self.max_history = max_history
      
      @property
      def name(self) -> str:
          return "conversation"
      
      async def handle(
          self,
          context: ConversationContext,
          transcript: str
      ) -> AgentResponse:
          """Generate contextual response using conversation history."""
          # Build conversation history for LLM
          messages = self._build_message_history(context)
          messages.append({"role": "user", "content": transcript})
          
          # TODO: Call LLM service with history
          response_text = await self._generate_response(messages)
          
          return AgentResponse(response_text=response_text)
      
      def _build_message_history(
          self,
          context: ConversationContext
      ) -> list[dict]:
          """Convert history to LLM message format."""
          messages = []
          for user_msg, agent_msg in context.history[-self.max_history:]:
              messages.append({"role": "user", "content": user_msg})
              messages.append({"role": "assistant", "content": agent_msg})
          return messages
      
      async def _generate_response(self, messages: list[dict]) -> str:
          """Call LLM to generate response."""
          # TODO: HTTP call to LLM service
          return "(LLM response placeholder)"
  ```
-  Maintain conversation state across turns
-  Generate contextual responses
-  Integration with LLM service
-  Tests for multi-turn conversations in `services/orchestrator/tests/integration/test_conversation_agent.py`

**Exit Condition:** Multi-turn conversations work naturally

---

## Phase 5: Documentation & Developer Experience

**🚨 AI AGENT REMINDER: FOLLOW PR WORKFLOW**
-  **Create new branch:** `git checkout main && git pull origin main && git checkout -b feature/phase-5-adapter-guide`
-  **Complete PR tasks:** Implement all requirements below
-  **Test & lint:** Run `make test` and `make lint` - MUST PASS
-  **Create PR:** Use GitHub MCP tools, tag `@codex review` and `@cursor review`
-  **Wait for review:** Do NOT proceed until PR is reviewed and merged
-  **Return to main:** Only then start next PR

**Objective:** Comprehensive documentation for extending the platform.

### PR 5.1: Adapter Development Guide

**Branch:** `docs/adapter-guide`

**Tasks:**
-  Create `docs/guides/adding_adapter.md`:
  ```markdown
  # Adding a New Audio Adapter
  
  ## Overview
  Audio adapters enable the orchestrator to work with different audio sources...
  
  ## Interface Requirements
  ### Input Adapter
  -  Implement `AudioInputAdapter` ABC
  -  Methods: `start()`, `stop()`, `get_audio_stream()`, `is_active`
  
  ### Output Adapter
  -  Implement `AudioOutputAdapter` ABC
  -  Methods: `play_audio()`, `stop()`
  
  ## Step-by-Step Guide
  -  Create adapter file in `services/common/audio/`
  -  Implement interface methods
  -  Register adapter in registry
  -  Add configuration
  -  Write tests
  
  ## Example: WebRTC Adapter
  [Full code example]
  ```
-  Include code examples for both input and output adapters
-  Explain registration process
-  Show testing strategies
-  Include common pitfalls and solutions

**Exit Condition:** Guide clear and actionable

---

### PR 5.2: Agent Development Guide

**Branch:** `docs/agent-guide`

**Tasks:**
-  Create `docs/guides/adding_agent.md`:
  ```markdown
  # Adding a New Agent
  
  ## Overview
  Agents process user input and generate responses...
  
  ## BaseAgent Interface
  -  Implement `BaseAgent` ABC
  -  Methods: `handle()`, `name` property
  
  ## Step-by-Step Guide
  -  Create agent file in `services/orchestrator/agents/`
  -  Implement `handle()` method
  -  Register in AgentManager
  -  Add routing logic
  -  Write tests
  
  ## Example: Weather Agent
  [Full code example with API integration]
  
  ## Testing Strategies
  -  Unit tests with mocked services
  -  Integration tests with real services
  -  Test routing logic
  ```
-  Explain BaseAgent interface in detail
-  Show routing registration
-  Cover testing approaches
-  Include best practices (error handling, timeouts, etc.)

**Exit Condition:** Guide enables agent development

---

### PR 5.3: Architecture Documentation Update

**Branch:** `docs/architecture-update`

**Tasks:**
-  Update `docs/architecture/system-overview.md`:
  -  Add section on adapter framework
  -  Add section on agent framework
  -  Update service interaction diagrams
  -  Add data flow diagrams
-  Create `docs/architecture/audio_pipeline.md`:
  -  Document pipeline stages
  -  Show conversion flow
  -  Explain buffering strategy
-  Create `docs/architecture/agent_system.md`:
  -  Document agent lifecycle
  -  Show routing logic
  -  Explain context management
-  Add sequence diagrams for key flows:
  -  Voice input → response (end-to-end)
  -  Agent selection flow
  -  Context retrieval and update
-  Update all architecture diagrams using Mermaid

**Exit Condition:** Architecture documentation current and comprehensive

---

## Phase 6: Performance & Observability

**🚨 AI AGENT REMINDER: FOLLOW PR WORKFLOW**
-  **Create new branch:** `git checkout main && git pull origin main && git checkout -b feature/phase-6-performance-metrics`
-  **Complete PR tasks:** Implement all requirements below
-  **Test & lint:** Run `make test` and `make lint` - MUST PASS
-  **Create PR:** Use GitHub MCP tools, tag `@codex review` and `@cursor review`
-  **Wait for review:** Do NOT proceed until PR is reviewed and merged
-  **Return to main:** Only then start next PR

**Objective:** Optimize performance and improve monitoring capabilities.

### PR 6.1: Performance Instrumentation

**Branch:** `feature/performance-metrics`

**Tasks:**
-  Create `services/common/metrics.py`:
  ```python
  from prometheus_client import Counter, Histogram, Gauge
  
  # Define all metrics
  audio_chunks_processed_total = Counter(...)
  agent_invocations_total = Counter(...)
  transcription_latency_seconds = Histogram(...)
  # ... etc (see monitoring section above)
  
  def init_metrics_registry() -> None:
      """Initialize Prometheus metrics."""
      pass
  ```
-  Add timing decorators to critical paths:
  ```python
  @track_latency(transcription_latency_seconds)
  async def transcribe(audio: AudioChunk) -> str:
      ...
  ```
-  Instrument audio pipeline stages
-  Add latency tracking to agent execution
-  Expose metrics via `/metrics` endpoint in each service
-  Create example Grafana dashboard configuration in `monitoring/grafana/`

**Exit Condition:** Performance metrics available and accurate

---

### PR 6.2: Distributed Tracing

**Branch:** `feature/distributed-tracing`

**Tasks:**
-  Add OpenTelemetry instrumentation:
  ```python
  from opentelemetry import trace
  from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
  
  # Initialize tracer
  tracer = trace.get_tracer(__name__)
  
  # Instrument FastAPI apps
  FastAPIInstrumentor.instrument_app(app)
  ```
-  Trace audio processing pipeline with spans
-  Trace cross-service calls (STT, LLM, TTS)
-  Add correlation IDs throughout:
  ```python
  correlation_id = str(uuid.uuid4())
  logger.info("Processing audio", extra={"correlation_id": correlation_id})
  ```
-  Integration with Jaeger or Zipkin
-  Configuration in `.env`:
  ```bash
  OTEL_ENABLED=true
  OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
  ```
-  Documentation for setting up tracing infrastructure

**Exit Condition:** Traces available for debugging, correlation IDs propagated

---

### PR 6.3: Performance Optimization

**Branch:** `optimize/audio-pipeline`

**Tasks:**
-  Profile audio pipeline bottlenecks using `cProfile` or `py-spy`
-  Optimize buffer sizes based on profiling:
  ```python
  OPTIMAL_CHUNK_SIZE_MS = 20  # Based on benchmarks
  BUFFER_SIZE_CHUNKS = 5  # Minimize latency while preventing drops
  ```
-  Reduce unnecessary memory copies in audio handling
-  Add caching where appropriate (e.g., model loading)
-  Implement connection pooling for HTTP clients
-  Benchmark improvements against baseline:
  ```python
  # Before: 2.5s average end-to-end
  # After:  1.8s average end-to-end (28% improvement)
  ```
-  Document optimization decisions in `docs/operations/performance.md`

**Exit Condition:** Measurable latency improvements, meets performance targets

---

## Success Criteria (Overall)

### Functional Requirements
-  [ ] Platform abstracts I/O adapters (Discord, File, future: WebRTC)
-  [ ] Audio pipeline end-to-end works: adapter → STT → agent → TTS → adapter
-  [ ] Multiple agents functional (Echo, Summarization, Intent, Conversation)
-  [ ] Agent routing works correctly based on transcript and context
-  [ ] Core orchestrator logic is adapter-agnostic
-  [ ] Context persists across conversation turns
-  [ ] Session management handles multiple concurrent users

### Quality Requirements
-  [ ] Test coverage ≥ 80% maintained throughout
-  [ ] All PRs pass `make test` and `make lint`
-  [ ] No regressions in existing functionality
-  [ ] Documentation complete and current

### Performance Requirements
-  [ ] Wake detection: < 200ms
-  [ ] STT processing: < 300ms from speech onset
-  [ ] Command response: < 2s total (end-to-end)
-  [ ] Voice join/response: 10-15s acceptable
-  [ ] System handles concurrent audio streams

### Operational Requirements
-  [ ] All PRs reviewed and merged to main
-  [ ] Monitoring and observability in place
-  [ ] Metrics exported to Prometheus
-  [ ] Distributed tracing functional
-  [ ] Health checks for all services

---

## AI Agent Sequential Management

### 🚨 **MANDATORY PR WORKFLOW FOR AI AGENT**

**⚠️ CRITICAL: AI AGENT MUST FOLLOW PR WORKFLOW - NO EXCEPTIONS**

The AI Agent MUST follow this exact sequence for EVERY PR:

#### **Step 1: Create New Branch**
```bash
git checkout main
git pull origin main
git checkout -b feature/[pr-name]
```

#### **Step 2: Implement Changes**
-  Complete ALL tasks for the specific PR
-  Follow the exact requirements listed in the PR section
-  Write comprehensive tests for all new code
-  Add proper docstrings and type hints

#### **Step 3: Test & Lint (MUST PASS)**
```bash
make test
make lint
```
-  **MUST PASS** - no exceptions
-  Fix any failing tests or linting issues
-  Ensure no regressions in existing functionality

#### **Step 4: Commit Changes**
```bash
git add .
git commit -m "[PR Name]: [Description]"
```

#### **Step 5: Push Branch**
```bash
git push origin feature/[pr-name]
```

#### **Step 6: Create PR**
-  Use GitHub MCP tools to create pull request
-  Include detailed description of changes
-  Tag for review: `@codex review` and `@cursor review`

#### **Step 7: Wait for Review**
-  **DO NOT PROCEED** until PR is reviewed and approved
-  **DO NOT START** next PR until current is merged
-  Apply any review feedback and push updates

#### **Step 8: Wait for Merge**
-  **DO NOT PROCEED** until PR is merged to main
-  **DO NOT START** next PR until current is merged

#### **Step 9: Return to Main**
```bash
git checkout main
git pull origin main
```

#### **Step 10: Repeat**
-  Only then start next PR with new branch
-  Follow exact same sequence for each PR

### **ABSOLUTE REQUIREMENTS - NO EXCEPTIONS**
-  ❌ **NEVER work on multiple PRs simultaneously**
-  ❌ **NEVER skip the review process**
-  ❌ **NEVER merge your own PRs**
-  ❌ **NEVER proceed to next PR until current is merged**
-  ✅ **ALWAYS create new branch for each PR**
-  ✅ **ALWAYS wait for human review and approval**
-  ✅ **ALWAYS return to main after merge**
-  ✅ **ALWAYS follow the exact sequence above**

---

## Branch Strategy (AI Agent Sequential)

### 🚨 **MANDATORY PR WORKFLOW - NO EXCEPTIONS**

**⚠️ AI AGENT MUST FOLLOW PR WORKFLOW FOR EVERY CHANGE**

### **PR-Based Branch Strategy**
-  **`main`** - current production code (always up-to-date)
-  **`feature/[pr-name]`** - individual PR branches (one per PR)
-  **NO single development branch** - each PR gets its own branch

### **AI Agent Workflow (PR-by-PR)**
```
main
  ├── feature/phase-0-agents-base-interface (PR → Review → Merge)
  ├── feature/phase-0-echo-agent (PR → Review → Merge)
  ├── feature/phase-0-agent-manager (PR → Review → Merge)
  ├── feature/phase-1-adapter-interfaces (PR → Review → Merge)
  ├── feature/phase-1-adapter-registry (PR → Review → Merge)
  ├── feature/phase-1-discord-adapters (PR → Review → Merge)
  ├── feature/phase-1-file-adapters (PR → Review → Merge)
  ├── feature/phase-2-audio-processor (PR → Review → Merge)
  ├── feature/phase-2-audio-pipeline (PR → Review → Merge)
  ├── feature/phase-2-pipeline-integration (PR → Review → Merge)
  └── [Continue for each PR...]
```

### **AI Agent Branching Rules - MANDATORY**
-  ✅ **One branch per PR:** Each PR gets its own feature branch
-  ✅ **Return to main:** Always start from `main` for each new PR
-  ✅ **Wait for merge:** Never start next PR until current is merged
-  ✅ **Human review:** Every PR must be reviewed and approved
-  ✅ **Sequential work:** Complete one PR fully before starting next
-  ❌ **NO single development branch**
-  ❌ **NO parallel PRs**
-  ❌ **NO self-merging**
-  ❌ **NO skipping review process**

---


## AI Agent Sequential Work Strategy

### Sequential Phase Dependencies (AI Agent)
-  **Phase -1: Cleanup** (2-3 days) - Foundation (must be first)
-  **Phase 0: Agents** (3-4 days) - Core abstractions (depends on cleanup)
-  **Phase 1: Adapters** (3-4 days) - I/O abstractions (depends on cleanup)
-  **Phase 2: Pipeline** (3-4 days) - Audio processing (depends on 0,1)
-  **Phase 3: Context** (2-3 days) - Session management (depends on 0)
-  **Phase 4: Advanced Agents** (2-3 days) - Sophisticated agents (depends on 0,2,3)
-  **Phase 5: Documentation** (1-2 days) - Complete docs (can start after 4)
-  **Phase 6: Performance** (1-2 days) - Optimization (depends on 2)

### AI Agent Workflow
**Single AI Agent (Cursor) working sequentially:**

```
Day 1-2:  Phase -1 (Cleanup)
├─ Audit codebase
├─ Remove dead code
├─ Standardize configuration
├─ Update documentation
└─ Commit: "Phase -1: Repository cleanup complete"

Day 3-6:  Phase 0 (Agents)
├─ Create agent base interfaces
├─ Implement echo agent
├─ Build agent manager
└─ Commit: "Phase 0: Agent framework complete"

Day 7-10: Phase 1 (Adapters)
├─ Create adapter interfaces
├─ Build adapter registry
├─ Refactor Discord to use adapters
├─ Add file adapter for testing
└─ Commit: "Phase 1: Adapter framework complete"

Day 11-14: Phase 2 (Pipeline)
├─ Build audio conversion
├─ Create processing pipeline
├─ Integrate with orchestrator
└─ Commit: "Phase 2: Audio pipeline complete"

Day 15-17: Phase 3 (Context)
├─ Create context types
├─ Implement memory storage
├─ Build context manager
└─ Commit: "Phase 3: Context management complete"

Day 18-20: Phase 4 (Advanced Agents)
├─ Summarization agent
├─ Intent classification agent
├─ Conversation agent
└─ Commit: "Phase 4: Advanced agents complete"

Day 21-22: Phase 5 (Documentation)
├─ Adapter development guide
├─ Agent development guide
├─ Architecture documentation
└─ Commit: "Phase 5: Documentation complete"

Day 23-24: Phase 6 (Performance)
├─ Add performance metrics
├─ Optimize audio pipeline
├─ Load testing
└─ Commit: "Phase 6: Performance optimization complete"

Day 25-26: Final Integration & Cutover
├─ Full test suite
├─ Load testing
├─ Integration testing
├─ Final merge to main
└─ Deploy with monitoring
```

### AI Agent Success Criteria Per Phase
Each phase must be **100% complete** before moving to next:
-  [ ] All code implemented and tested
-  [ ] All tests pass (`make test`)
-  [ ] All linters pass (`make lint`)
-  [ ] Phase objectives met (see exit conditions)
-  [ ] No regressions in existing functionality
-  [ ] Commit with descriptive message
-  [ ] Ready for next phase

---

## Fast Cutover Strategy

### What Already Exists (Excellent Infrastructure)
-  ✅ Microservices architecture (discord, stt, llm, orchestrator, tts)
-  ✅ Docker Compose orchestration
-  ✅ Configuration management (`services.common.config`) - **EXCELLENT, KEEP**
-  ✅ Health checks and monitoring basics - **EXCELLENT, KEEP**
-  ✅ Test framework (pytest, integration tests) - **EXCELLENT, KEEP**
-  ✅ Linting and formatting setup
-  ✅ Audio processing (`AudioProcessor`, `AudioPipeline`) - **EXCELLENT, BUILD UPON**
-  ✅ MCP integration patterns - **GOOD, REPURPOSE**

### What We're Adding (New Architecture)
-  🆕 Agent abstraction framework (builds upon existing orchestrator patterns)
-  🆕 Audio adapter abstraction framework (builds upon existing audio processing)
-  🆕 Formalized audio processing pipeline (enhances existing AudioPipeline)
-  🆕 Session and context persistence (builds upon existing session management)
-  🆕 Advanced agents (summarization, intent, conversation)
-  🆕 Comprehensive monitoring and tracing (builds upon existing health checks)
-  🆕 Developer documentation

### Fast Cutover Approach (AI Agent Sequential)
-  **Sequential Development:** AI agent works through phases one at a time
-  **Feature Branch:** Build complete new architecture on single feature branch
-  **Aggressive Timeline:** Complete in 2-3 weeks with focused AI work
-  **Test in Isolation:** Full test suite before merge to main
-  **Single Merge:** One large PR with entire new architecture
-  **Clean Architecture**: Build new system with clear separation from existing

### Cutover Branch Strategy (AI Sequential)
```
main (current production)
  └── feature/audio-platform-cutover (AI development)
       ├── Phase -1: Cleanup (2-3 days)
       ├── Phase 0: Agents (3-4 days)
       ├── Phase 1: Adapters (3-4 days)
       ├── Phase 2: Pipeline (3-4 days)
       ├── Phase 3: Context (2-3 days)
       ├── Phase 4: Advanced Agents (2-3 days)
       ├── Phase 5: Documentation (1-2 days)
       └── Phase 6: Performance (1-2 days)

Once complete: Merge feature/audio-platform-cutover → main
```

### AI Agent Sequential Strategy
**Week 1: Foundation & Core Abstractions**
-  Day 1-2: Phase -1 (Cleanup) - Establish clean baseline
-  Day 3-4: Phase 0 (Agents) - Build agent framework
-  Day 5-7: Phase 1 (Adapters) - Build adapter framework

**Week 2: Integration & Context**
-  Day 1-3: Phase 2 (Pipeline) - Integrate audio processing
-  Day 4-5: Phase 3 (Context) - Add session management
-  Day 6-7: Integration testing and bug fixes

**Week 3: Polish & Cutover**
-  Day 1-2: Phase 4 (Advanced Agents) - Add sophisticated agents
-  Day 3: Phase 5 (Documentation) - Complete docs
-  Day 4: Phase 6 (Performance) - Optimize and benchmark
-  Day 5-7: Final testing, load testing, and cutover preparation

### Cutover Prerequisites
-  [ ] All tests pass on feature branch (100% of existing + new tests)
-  [ ] Performance meets or exceeds current benchmarks
-  [ ] New architecture fully tested and validated
-  [ ] Load testing completed successfully
-  [ ] Documentation complete
-  [ ] Team trained on new architecture


---

## Notes for AI Agent (Cursor)

### Sequential Development Principles
-  **One phase at a time:** Complete each phase fully before moving to next
-  **No parallel work:** Focus entirely on current phase objectives
-  **Generate tests alongside implementation:** Never leave testing for later
-  **Include comprehensive docstrings:** Explain why and how, not just what
-  **Use type hints everywhere:** Enable static analysis and IDE support
-  **Follow existing patterns:** Study codebase before adding new patterns
-  **Commit per phase:** Each phase gets one comprehensive commit
-  **Validate before next:** Ensure phase objectives met before proceeding

### AI Agent Workflow Per Phase
-  **Read phase objectives:** Understand what needs to be built
-  **Study existing code:** Look for similar patterns to follow
-  **Implement systematically:** Work through phase tasks in order
-  **Test continuously:** Run `make test` and `make lint` frequently
-  **Validate completion:** Ensure all phase objectives met
-  **Commit with clear message:** "Phase X: [Description] complete"
-  **Move to next phase:** Only after current phase is 100% complete

### Code Quality Focus for AI Agent
-  **Design:** Does this fit the overall architecture? Is it the right abstraction?
-  **Correctness:** Handle edge cases and error conditions properly
-  **Performance:** Will it meet latency targets? Consider memory usage
-  **Maintainability:** Write clear, understandable code with good docstrings
-  **Security:** Validate inputs, handle errors safely
-  **Testing:** Write comprehensive tests that verify behavior

### When Stuck (AI Agent)
-  **Re-read phase objectives:** Make sure you understand what's needed
-  **Study existing code:** Look for similar implementations to follow
-  **Check dependencies:** Ensure previous phases are complete
-  **Run tests:** Make sure current work doesn't break existing functionality
-  **Ask for clarification:** If requirements are unclear, ask the user
-  **Focus on current phase:** Don't jump ahead to future phases

### AI Agent Success Pattern
```
For each phase:
-  Read phase objectives and requirements
-  Study existing codebase for patterns
-  Implement phase functionality systematically
-  Write comprehensive tests
-  Run make test and make lint
-  Validate phase objectives are met
-  Commit with clear message
-  Move to next phase only after current is complete
```

---

## Appendix: Quick Reference

### Common Commands
```bash
# Testing
make test                    # Run all tests
make test-unit              # Unit tests only
make test-integration       # Integration tests only

# Linting
make lint                   # Check all linting rules
make lint-fix               # Auto-fix formatting

# Development
make run                    # Start all services
make logs                   # View service logs
make docker-build           # Build service images

# Cleanup
make docker-clean           # Clean containers/volumes
```

### Configuration Files
-  **`pyproject.toml`** - Python tooling config (black, ruff, mypy, pytest)
-  **`docker-compose.yml`** - Service orchestration
-  **`.env.sample`** - Environment variable template
-  **`services/*/requirements.txt`** - Service dependencies

### Key Directories
-  **`services/`** - All microservices
-  **`services/common/`** - Shared utilities
-  **`services/orchestrator/agents/`** - Agent implementations
-  **`services/common/audio/`** - Audio adapters and pipeline
-  **`docs/`** - All documentation
-  **`tests/`** - Shared test fixtures

---

---

## 🚨 **FINAL AI AGENT REMINDER**

### **MANDATORY PR WORKFLOW - NO EXCEPTIONS**

**⚠️ AI AGENT MUST FOLLOW THIS EXACT SEQUENCE FOR EVERY PR:**

-  **Create New Branch:** `git checkout main && git pull origin main && git checkout -b feature/[pr-name]`
-  **Implement Changes:** Complete all tasks for the specific PR
-  **Test & Lint:** Run `make test` and `make lint` - MUST PASS
-  **Commit Changes:** `git add . && git commit -m "[PR Name]: [Description]"`
-  **Push Branch:** `git push origin feature/[pr-name]`
-  **Create PR:** Use GitHub MCP tools to create pull request
-  **Wait for Review:** Do NOT proceed until PR is reviewed and approved
-  **Apply Fixes:** If review feedback, make changes and push updates
-  **Wait for Merge:** Do NOT proceed until PR is merged to main
-  **Return to Main:** `git checkout main && git pull origin main`
-  **Repeat:** Only then start next PR with new branch

### **ABSOLUTE REQUIREMENTS - NO EXCEPTIONS**
-  ❌ **NEVER work on multiple PRs simultaneously**
-  ❌ **NEVER skip the review process**
-  ❌ **NEVER merge your own PRs**
-  ❌ **NEVER proceed to next PR until current is merged**
-  ✅ **ALWAYS create new branch for each PR**
-  ✅ **ALWAYS wait for human review and approval**
-  ✅ **ALWAYS return to main after merge**
-  ✅ **ALWAYS follow the exact sequence above**

**Last Updated:** 2025-10-21
**Version:** 2.0 (Enhanced with cleanup phase, PR workflow, and technical specifics)
