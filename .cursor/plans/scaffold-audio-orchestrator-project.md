# Audio-First AI Orchestrator Platform — Enhancement Plan

**Repository:** `audio-orchestrator` (renamed from discord-voice-lab)
**Python Version:** 3.11
**Branch Strategy:** Feature branches from `main`, one PR per functional change
**Quality Gates:** All PRs must pass `make test` and `make lint`
**Test Framework:** pytest, pytest-asyncio
**Linting Tools:** black, ruff, mypy

---

## Code Quality Standards (All PRs)

### Implementation Requirements
- **Async patterns:** All I/O operations use `async def` / `await`
- **Type hints:** Comprehensive type annotations (mypy compliance)
- **Docstrings:** Module-level docstrings for all new modules
- **TODO comments:** Mark incomplete integrations with `# TODO: <description>`
- **Tests:** Generate test file alongside implementation
- **Style checks:** Must pass `black --check`, `ruff check`, `mypy`
- **Quality gates:** Must pass `make lint` and `make test`

### Performance Targets
- **Wake detection:** < 200ms
- **STT processing:** < 300ms from speech onset
- **Command response:** < 2s total (end-to-end)
- **Voice join/response:** 10-15s acceptable
- **Test coverage:** Maintain ≥ 80% overall

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
- **`services/common/config.py`** - `ConfigBuilder` system (excellent, keep as-is)
- **`services/common/health.py`** - `HealthManager` with dependency tracking (excellent, keep as-is)
- **`services/common/logging.py`** - Structured JSON logging (excellent, keep as-is)
- **`services/common/audio.py`** - `AudioProcessor` with format conversion (excellent, keep as-is)
- **`services/common/correlation.py`** - Correlation ID management (excellent, keep as-is)
- **`services/common/resilient_http.py`** - Circuit breaker patterns (excellent, keep as-is)
- **Testing framework** - Current unit/component/integration test structure (excellent, keep as-is)
- **Docker Compose setup** - Current service orchestration (excellent, keep as-is)

### **What We're Building Upon (Good Patterns)**
- **MCP Integration concepts** - Current `MCPManager` patterns (repurpose)
- **Audio processing concepts** - Current VAD and aggregation patterns (repurpose)
- **Health check patterns** - Current standardized health checks (repurpose)
- **Configuration patterns** - Current service-specific configs (repurpose)

### **What We're Replacing (Implementation Details)**
- **Orchestrator logic** - Current HTTP-based transcript processing (replace)
- **Audio pipeline** - Current `AudioPipeline` implementation (replace)
- **MCP implementation** - Current stdio-based MCP client (replace)
- **Service architecture** - Current microservices approach (replace)

### **Type System Alignment**
- **Current**: `PCMFrame`, `AudioSegment` in `services/discord/audio.py`
- **New**: `AudioChunk`, `ProcessedSegment` (enhanced versions)
- **Current**: `AudioMetadata` in `services/common/audio.py`
- **New**: `AudioFormat` (enhanced version)

### **Implementation Strategy**
1. **Preserve Infrastructure**: Keep excellent `services/common/*` components
2. **Build Upon Patterns**: Extend existing MCP, audio, and health patterns
3. **Replace Implementation**: New agent/adapter system alongside existing
4. **Gradual Migration**: Feature flag to toggle between old/new systems
5. **Learning Focus**: Document trade-offs and architectural decisions

---

## Phase -1: Infrastructure Preservation & Baseline

**Branch:** `cleanup/baseline-state`
**Objective:** Preserve excellent existing infrastructure while establishing clean baseline for new architecture.

### Tasks

1. **Preserve Excellent Infrastructure (Keep As-Is)**
   - **`services/common/config.py`** - `ConfigBuilder` system (excellent, keep)
   - **`services/common/health.py`** - `HealthManager` with dependency tracking (excellent, keep)
   - **`services/common/logging.py`** - Structured JSON logging (excellent, keep)
   - **`services/common/audio.py`** - `AudioProcessor` with format conversion (excellent, keep)
   - **`services/common/correlation.py`** - Correlation ID management (excellent, keep)
   - **`services/common/resilient_http.py`** - Circuit breaker patterns (excellent, keep)

2. **Audit Current System State**
   - Document current API contracts (all service endpoints)
   - Map current data flow patterns (Discord → STT → Orchestrator → LLM → TTS)
   - Catalog existing data types (`PCMFrame`, `AudioSegment`, `AudioMetadata`)
   - Identify current MCP integration patterns
   - Document current configuration patterns

3. **Clean Up Dead Code**
   - Run `vulture` or manual audit to find unused code
   - Remove unused imports across all services
   - Delete commented-out code blocks (convert to issues if needed)
   - Clean up TODO comments (convert to GitHub issues or remove)
   - Remove deprecated functions/classes

4. **Standardize Configuration**
   - Verify all services use `services.common.config.ConfigBuilder` (already excellent)
   - Verify all `.env.sample` entries are documented
   - Remove duplicate configuration patterns
   - Audit environment variable usage for consistency
   - Document all config fields in README

5. **Update Documentation**
   - Fix broken internal links in `docs/`
   - Update outdated service descriptions
   - Ensure all README files are current
   - Update architecture diagrams in `docs/architecture/`
   - Verify MCP documentation is accurate

6. **Test Coverage Baseline**
   - Run `make test` and document current coverage (baseline)
   - Identify untested critical paths
   - Fix any flaky tests
   - Document known test gaps in GitHub issues
   - Set up coverage reporting in CI

7. **Linting Cleanup**
   - Run `make lint-fix` and commit results
   - Address remaining linting violations
   - Ensure all services pass type checking
   - Update `pyproject.toml` if needed

8. **Dependency Audit**
   - Review all `requirements.txt` files
   - Update to latest compatible versions
   - Remove unused dependencies
   - Run `pip-audit` for security vulnerabilities
   - Document any known issues

**PR:** "Infrastructure Preservation: Establish Clean Baseline State"

**Success Criteria:**
- All tests pass: `make test` ✓
- All linters pass: `make lint` ✓
- Documentation current and links working
- Baseline coverage documented
- No critical security vulnerabilities
- **Preserved excellent infrastructure components**
- **Current system state fully documented**

---

## Phase 0: Modular Agent Framework

**Objective:** Create abstractions for pluggable agents within the orchestrator service, enabling flexible response generation strategies. **Build upon existing orchestrator patterns rather than replacing them.**

### PR 0.1: Agent Base Interface & Types

**Branch:** `feature/agent-base-interface`

**Tasks:**
- Create `services/orchestrator/agents/__init__.py`
- Create `services/orchestrator/agents/types.py`:
  ```python
  from dataclasses import dataclass, field
  from typing import Optional, AsyncIterator, List
  from datetime import datetime
  
  @dataclass
  class AgentResponse:
      """Response from an agent containing text, audio, and/or actions."""
      response_text: Optional[str] = None
      response_audio: Optional[AsyncIterator[AudioChunk]] = None
      actions: List[ExternalAction] = field(default_factory=list)
      metadata: dict = field(default_factory=dict)
  
  @dataclass
  class ConversationContext:
      """Current conversation state and history."""
      session_id: str
      history: List[tuple[str, str]]  # (user_input, agent_response)
      created_at: datetime
      last_active_at: datetime
      metadata: Optional[dict] = None
  ```
- Create `services/orchestrator/agents/base.py`:
  ```python
  from abc import ABC, abstractmethod
  
  class BaseAgent(ABC):
      """Abstract base class for all agents."""
      
      @abstractmethod
      async def handle(
          self,
          context: ConversationContext,
          transcript: str
      ) -> AgentResponse:
          """Handle a conversation turn.
          
          Args:
              context: Current conversation context
              transcript: User's transcribed speech
              
          Returns:
              Agent response with text, audio, and/or actions
          """
          pass
      
      @property
      @abstractmethod
      def name(self) -> str:
          """Unique agent identifier."""
          pass
  ```
- Add unit tests for type validation in `services/orchestrator/tests/unit/test_agent_types.py`
- Add docstrings explaining agent lifecycle and patterns

**Exit Condition:** Base abstractions defined, tests pass, documentation complete

---

### PR 0.2: Echo Agent Implementation

**Branch:** `feature/echo-agent`

**Tasks:**
- Implement `services/orchestrator/agents/echo_agent.py`:
  ```python
  from .base import BaseAgent
  from .types import AgentResponse, ConversationContext
  
  class EchoAgent(BaseAgent):
      """Simple echo agent that repeats user input."""
      
      @property
      def name(self) -> str:
          return "echo"
      
      async def handle(
          self,
          context: ConversationContext,
          transcript: str
      ) -> AgentResponse:
          """Echo the user's transcript back as response text.
          
          Args:
              context: Current conversation context (unused)
              transcript: User's transcribed speech
              
          Returns:
              AgentResponse with echoed text
          """
          return AgentResponse(response_text=transcript)
  ```
- Create `services/orchestrator/tests/unit/test_echo_agent.py`:
  ```python
  @pytest.mark.asyncio
  async def test_echo_agent_returns_transcript():
      agent = EchoAgent()
      context = ConversationContext(
          session_id="test",
          history=[],
          created_at=datetime.now(),
          last_active_at=datetime.now()
      )
      
      response = await agent.handle(context, "hello world")
      
      assert response.response_text == "hello world"
      assert response.response_audio is None
      assert response.actions == []
  ```
- Add integration test that invokes echo agent through orchestrator

**Exit Condition:** Echo agent functional, all tests pass

---

### PR 0.3: Agent Manager & Registry

**Branch:** `feature/agent-manager`

**Tasks:**
- Create `services/orchestrator/agents/registry.py`:
  ```python
  class AgentRegistry:
      """Registry for managing available agents."""
      
      def __init__(self):
          self._agents: dict[str, BaseAgent] = {}
      
      def register(self, agent: BaseAgent) -> None:
          """Register an agent by name."""
          self._agents[agent.name] = agent
      
      def get(self, name: str) -> Optional[BaseAgent]:
          """Get agent by name."""
          return self._agents.get(name)
      
      def list_agents(self) -> list[str]:
          """List all registered agent names."""
          return list(self._agents.keys())
  ```
- Create `services/orchestrator/agents/manager.py`:
  ```python
  class AgentManager:
      """Manages agent selection and routing."""
      
      def __init__(self, agents: list[BaseAgent], default_agent: str = "echo"):
          self.registry = AgentRegistry()
          for agent in agents:
              self.registry.register(agent)
          self.default_agent = default_agent
      
      def select_agent(
          self,
          transcript: str,
          context: ConversationContext
      ) -> BaseAgent:
          """Select appropriate agent based on transcript and context.
          
          Simple keyword-based routing:
          - If transcript contains 'echo' -> EchoAgent
          - Otherwise -> default agent
          
          Args:
              transcript: User's transcribed speech
              context: Current conversation context
              
          Returns:
              Selected agent instance
          """
          # Simple keyword routing
          transcript_lower = transcript.lower()
          
          if 'echo' in transcript_lower or transcript_lower.startswith('echo'):
              return self.registry.get('echo') or self._get_default()
          
          return self._get_default()
      
      def _get_default(self) -> BaseAgent:
          agent = self.registry.get(self.default_agent)
          if not agent:
              raise ValueError(f"Default agent '{self.default_agent}' not found")
          return agent
  ```
- Add configuration support in `services/orchestrator/config.py`:
  ```python
  AGENT_DEFAULT = env.str("AGENT_DEFAULT", default="echo")
  AGENT_ROUTING_ENABLED = env.bool("AGENT_ROUTING_ENABLED", default=True)
  ```
- Unit tests for routing logic in `services/orchestrator/tests/unit/test_agent_manager.py`
- Integration test for agent selection with multiple agents

**Exit Condition:** Agent routing works, multiple agents can be registered, tests pass

---

## Phase 1: I/O Adapter Framework

**Objective:** Abstract audio input/output to support multiple sources beyond Discord (files, WebRTC, etc.). **Build upon existing AudioProcessor and audio pipeline concepts rather than replacing them.**

### PR 1.1: Audio Adapter Interfaces & Types

**Branch:** `feature/audio-adapter-interfaces`

**Tasks:**
- Create `services/common/audio/__init__.py`
- Create `services/common/audio/types.py`:
  ```python
  from typing import NamedTuple
  
  # Build upon existing AudioMetadata in services/common/audio.py
  class AudioChunk(NamedTuple):
      """Raw audio data chunk with metadata (enhanced version of PCMFrame)."""
      pcm_bytes: bytes
      sample_rate: int  # Hz (e.g., 16000, 48000)
      channels: int  # 1=mono, 2=stereo
      timestamp_ms: int  # Relative timestamp in milliseconds
  
  class AudioFormat(NamedTuple):
      """Audio format specification (builds upon existing AudioMetadata)."""
      sample_rate: int = 16000  # Standard: 16kHz
      channels: int = 1  # Standard: mono
      sample_width: int = 2  # bytes per sample (16-bit)
      codec: str = "pcm"  # pcm, opus, etc.
  
  # Standard audio format for internal processing
  STANDARD_AUDIO_FORMAT = AudioFormat(
      sample_rate=16000,
      channels=1,
      sample_width=2,
      codec="pcm"
  )
  ```
- Create `services/common/audio/input_adapter.py`:
  ```python
  from abc import ABC, abstractmethod
  from typing import AsyncIterator
  
  class AudioInputAdapter(ABC):
      """Abstract base class for audio input sources."""
      
      @abstractmethod
      async def start(self) -> None:
          """Initialize and start the audio input stream."""
          pass
      
      @abstractmethod
      async def stop(self) -> None:
          """Stop the audio input stream and cleanup resources."""
          pass
      
      @abstractmethod
      def get_audio_stream(self) -> AsyncIterator[AudioChunk]:
          """Get async iterator of audio chunks.
          
          Yields:
              AudioChunk: Continuous stream of audio data
          """
          pass
      
      @property
      @abstractmethod
      def is_active(self) -> bool:
          """Check if input is currently active."""
          pass
  ```
- Create `services/common/audio/output_adapter.py`:
  ```python
  from abc import ABC, abstractmethod
  from typing import AsyncIterator
  
  class AudioOutputAdapter(ABC):
      """Abstract base class for audio output destinations."""
      
      @abstractmethod
      async def play_audio(self, audio_stream: AsyncIterator[AudioChunk]) -> None:
          """Play audio from the given stream.
          
          Args:
              audio_stream: Async iterator of audio chunks to play
          """
          pass
      
      @abstractmethod
      async def stop(self) -> None:
          """Stop audio playback and cleanup resources."""
          pass
  ```
- Add comprehensive docstrings with usage examples
- Unit tests for type validation in `services/common/tests/unit/test_audio_types.py`

**Exit Condition:** Interfaces defined, documented, tested

---

### PR 1.2: Adapter Registry

**Branch:** `feature/adapter-registry`

**Tasks:**
- Create `services/common/audio/registry.py`:
  ```python
  from typing import Type, Optional
  
  class AdapterRegistry:
      """Registry for managing audio I/O adapters."""
      
      def __init__(self):
          self._input_adapters: dict[str, Type[AudioInputAdapter]] = {}
          self._output_adapters: dict[str, Type[AudioOutputAdapter]] = {}
      
      def register_input_adapter(
          self,
          name: str,
          adapter_class: Type[AudioInputAdapter]
      ) -> None:
          """Register an audio input adapter."""
          self._input_adapters[name] = adapter_class
      
      def register_output_adapter(
          self,
          name: str,
          adapter_class: Type[AudioOutputAdapter]
      ) -> None:
          """Register an audio output adapter."""
          self._output_adapters[name] = adapter_class
      
      def get_input_adapter(self, name: str) -> Optional[Type[AudioInputAdapter]]:
          """Get input adapter class by name."""
          return self._input_adapters.get(name)
      
      def get_output_adapter(self, name: str) -> Optional[Type[AudioOutputAdapter]]:
          """Get output adapter class by name."""
          return self._output_adapters.get(name)
      
      def list_input_adapters(self) -> list[str]:
          """List registered input adapter names."""
          return list(self._input_adapters.keys())
      
      def list_output_adapters(self) -> list[str]:
          """List registered output adapter names."""
          return list(self._output_adapters.keys())
  
  # Global registry instance
  _registry = AdapterRegistry()
  
  # Convenience functions
  def register_input_adapter(name: str, adapter_class: Type[AudioInputAdapter]) -> None:
      _registry.register_input_adapter(name, adapter_class)
  
  def register_output_adapter(name: str, adapter_class: Type[AudioOutputAdapter]) -> None:
      _registry.register_output_adapter(name, adapter_class)
  
  def get_input_adapter(name: str) -> Optional[Type[AudioInputAdapter]]:
      return _registry.get_input_adapter(name)
  
  def get_output_adapter(name: str) -> Optional[Type[AudioOutputAdapter]]:
      return _registry.get_output_adapter(name)
  ```
- Add configuration-based adapter selection in `services/common/config.py`:
  ```python
  AUDIO_INPUT_ADAPTER = env.str("AUDIO_INPUT_ADAPTER", default="discord")
  AUDIO_OUTPUT_ADAPTER = env.str("AUDIO_OUTPUT_ADAPTER", default="discord")
  ```
- Unit tests for registry operations in `services/common/tests/unit/test_adapter_registry.py`

**Exit Condition:** Registry functional, tests pass

---

### PR 1.3: Refactor Discord to Use Adapters

**Branch:** `feature/discord-adapter-refactor`

**Tasks:**
- Create `services/discord/adapters/__init__.py`
- Create `services/discord/adapters/discord_input_adapter.py`:
  ```python
  from services.common.audio import AudioInputAdapter, AudioChunk, STANDARD_AUDIO_FORMAT
  from typing import AsyncIterator
  
  class DiscordAudioInputAdapter(AudioInputAdapter):
      """Discord voice channel audio input adapter."""
      
      def __init__(self, voice_client):
          self.voice_client = voice_client
          self._active = False
          # TODO: Implement audio capture from Discord voice
      
      async def start(self) -> None:
          """Start capturing audio from Discord voice channel."""
          self._active = True
          # TODO: Start Discord audio capture
      
      async def stop(self) -> None:
          """Stop audio capture."""
          self._active = False
          # TODO: Stop Discord audio capture
      
      async def get_audio_stream(self) -> AsyncIterator[AudioChunk]:
          """Yield audio chunks from Discord voice."""
          while self._active:
              # TODO: Capture audio from Discord
              # For now, stub
              yield AudioChunk(
                  pcm_bytes=b'',
                  sample_rate=STANDARD_AUDIO_FORMAT.sample_rate,
                  channels=STANDARD_AUDIO_FORMAT.channels,
                  timestamp_ms=0
              )
      
      @property
      def is_active(self) -> bool:
          return self._active
  ```
- Create `services/discord/adapters/discord_output_adapter.py`:
  ```python
  from services.common.audio import AudioOutputAdapter, AudioChunk
  from typing import AsyncIterator
  
  class DiscordAudioOutputAdapter(AudioOutputAdapter):
      """Discord voice channel audio output adapter."""
      
      def __init__(self, voice_client):
          self.voice_client = voice_client
          # TODO: Implement audio playback to Discord
      
      async def play_audio(self, audio_stream: AsyncIterator[AudioChunk]) -> None:
          """Play audio stream to Discord voice channel."""
          async for chunk in audio_stream:
              # TODO: Send audio to Discord voice
              pass
      
      async def stop(self) -> None:
          """Stop audio playback."""
          # TODO: Stop Discord audio playback
          pass
  ```
- Refactor existing Discord voice code to implement adapter interfaces
- Register adapters in `services/discord/app.py`:
  ```python
  from services.common.audio import register_input_adapter, register_output_adapter
  from .adapters.discord_input_adapter import DiscordAudioInputAdapter
  from .adapters.discord_output_adapter import DiscordAudioOutputAdapter
  
  # Register Discord adapters
  register_input_adapter("discord", DiscordAudioInputAdapter)
  register_output_adapter("discord", DiscordAudioOutputAdapter)
  ```
- Integration tests for Discord adapters in `services/discord/tests/integration/test_discord_adapters.py`
- Verify no regression in Discord functionality

**Exit Condition:** Discord service uses adapter pattern, all tests pass, no functional regression

---

### PR 1.4: File-Based Audio Adapter (Testing)

**Branch:** `feature/file-audio-adapter`

**Tasks:**
- Create `services/common/audio/file_adapter.py`:
  ```python
  class FileAudioInputAdapter(AudioInputAdapter):
      """Read audio from file for testing."""
      
      def __init__(self, file_path: str, chunk_size_ms: int = 20):
          self.file_path = file_path
          self.chunk_size_ms = chunk_size_ms
          self._active = False
          # TODO: Load audio file (WAV, MP3)
      
      async def start(self) -> None:
          """Load audio file."""
          self._active = True
          # TODO: Open and prepare file
      
      async def stop(self) -> None:
          """Close file."""
          self._active = False
          # TODO: Close file handle
      
      async def get_audio_stream(self) -> AsyncIterator[AudioChunk]:
          """Yield audio chunks from file."""
          # TODO: Read file in chunks, yield AudioChunks
          pass
  
  class FileAudioOutputAdapter(AudioOutputAdapter):
      """Write audio to file for testing/debugging."""
      
      def __init__(self, output_path: str):
          self.output_path = output_path
          # TODO: Prepare output file
      
      async def play_audio(self, audio_stream: AsyncIterator[AudioChunk]) -> None:
          """Write audio stream to file."""
          # TODO: Write chunks to file
          pass
      
      async def stop(self) -> None:
          """Close output file."""
          # TODO: Close file, finalize
          pass
  ```
- Register file adapters in registry
- Integration tests using test audio files from `tests/fixtures/`
- Document usage for testing in `docs/guides/testing_with_file_adapter.md`

**Exit Condition:** File adapter works, useful for testing, documented

---

## Phase 2: Audio Pipeline Enhancement

**Objective:** Formalize audio processing pipeline with conversion, normalization, and streaming support. **Build upon existing AudioPipeline in services/discord/audio.py rather than replacing it.**

### PR 2.1: Audio Conversion Module

**Branch:** `feature/audio-conversion`

**Tasks:**
- Create `services/common/audio/conversion.py`:
  ```python
  # Build upon existing AudioProcessor in services/common/audio.py
  from services.common.audio import AudioProcessor
  
  async def convert_to_standard(audio_chunk: AudioChunk) -> AudioChunk:
      """Convert audio chunk to standard format.
      
      Standard format: 16kHz, mono, 16-bit PCM
      Builds upon existing AudioProcessor capabilities.
      
      Args:
          audio_chunk: Input audio in any format
          
      Returns:
          Audio chunk in standard format
      """
      if (audio_chunk.sample_rate == STANDARD_AUDIO_FORMAT.sample_rate and
          audio_chunk.channels == STANDARD_AUDIO_FORMAT.channels):
          return audio_chunk
      
      # Use existing AudioProcessor for conversion
      processor = AudioProcessor("conversion")
      
      # TODO: Use existing AudioProcessor methods for conversion
      # For now, log and pass through
      logger.warning(
          f"Converting audio from {audio_chunk.sample_rate}Hz/"
          f"{audio_chunk.channels}ch to standard format"
      )
      
      # Placeholder conversion
      return AudioChunk(
          pcm_bytes=audio_chunk.pcm_bytes,
          sample_rate=STANDARD_AUDIO_FORMAT.sample_rate,
          channels=STANDARD_AUDIO_FORMAT.channels,
          timestamp_ms=audio_chunk.timestamp_ms
      )
  
  def detect_format(audio_data: bytes) -> AudioFormat:
      """Detect audio format from raw data using existing AudioProcessor."""
      # TODO: Use existing AudioProcessor.extract_metadata()
      pass
  
  def validate_format(audio_chunk: AudioChunk) -> bool:
      """Validate audio chunk format."""
      return (
          audio_chunk.sample_rate > 0 and
          audio_chunk.channels > 0 and
          len(audio_chunk.pcm_bytes) > 0
      )
  ```
- Use `ffmpeg-python` or `PyAV` for actual conversion
- Add format detection and validation
- Unit tests with various audio formats in `services/common/tests/unit/test_audio_conversion.py`
- Performance benchmarks for conversion operations

**Exit Condition:** Audio conversion works reliably, tests pass, performance acceptable

---

### PR 2.2: Audio Processing Pipeline

**Branch:** `feature/audio-pipeline`

**Tasks:**
- Create `services/common/audio/pipeline.py`:
  ```python
  async def process_audio_pipeline(
      input_stream: AsyncIterator[AudioChunk],
      stt_service: 'STTService'
  ) -> AsyncIterator[ProcessedSegment]:
      """Process audio stream through complete pipeline.
      
      Pipeline: input → standardization → STT → segments
      
      Args:
          input_stream: Raw audio chunks from input adapter
          stt_service: STT service for transcription
          
      Yields:
          ProcessedSegment: Transcribed audio segments
      """
      async for chunk in input_stream:
          # Convert to standard format
          standard_chunk = await convert_to_standard(chunk)
          
          # Validate format
          if not validate_format(standard_chunk):
              logger.warning("Invalid audio chunk, skipping")
              continue
          
          # Transcribe
          try:
              transcript = await stt_service.transcribe(standard_chunk)
              
              yield ProcessedSegment(
                  transcript=transcript,
                  start_time_ms=chunk.timestamp_ms,
                  end_time_ms=chunk.timestamp_ms + 1000,  # TODO: Calculate actual duration
                  confidence=None,  # TODO: Get from STT
                  language=None  # TODO: Get from STT
              )
          except Exception as e:
              logger.error(f"Transcription failed: {e}")
              continue
  ```
- Implement async generator pattern for streaming
- Add chunking and buffering logic
- Add back-pressure handling
- Integration tests with real audio streams in `services/common/tests/integration/test_audio_pipeline.py`

**Exit Condition:** Pipeline handles streaming audio efficiently, tests pass

---

### PR 2.3: Integrate Pipeline with Orchestrator

**Branch:** `feature/integrate-audio-pipeline`

**Tasks:**
- Update `services/orchestrator/orchestrator.py` to use audio pipeline:
  ```python
  async def handle_audio(
      self,
      input_adapter: AudioInputAdapter,
      output_adapter: AudioOutputAdapter
  ) -> None:
      """Main orchestration loop for audio processing.
      
      Flow:
      1. Start input adapter
      2. Get audio stream
      3. For each chunk:
         a. Convert to standard format
         b. Transcribe via STT
         c. Get/update conversation context
         d. Select appropriate agent
         e. Execute agent to get response
         f. Synthesize response via TTS (if text response)
         g. Play audio response
      4. Stop input adapter on exit
      
      Args:
          input_adapter: Audio input source
          output_adapter: Audio output destination
      """
      try:
          await input_adapter.start()
          logger.info("Audio input started")
          
          async for chunk in input_adapter.get_audio_stream():
              try:
                  # Convert to standard format
                  standard_chunk = await convert_to_standard(chunk)
                  
                  # Transcribe
                  transcript = await self.stt_service.transcribe(standard_chunk)
                  if not transcript:
                      continue
                  
                  # Get conversation context
                  context = await self.context_manager.get_context(
                      session_id=self._get_session_id()
                  )
                  
                  # Select agent
                  agent = self.agent_manager.select_agent(transcript, context)
                  
                  # Execute agent
                  response = await agent.handle(context, transcript)
                  
                  # Update context
                  context.history.append((transcript, response.response_text or ""))
                  await self.context_manager.update_context(context)
                  
                  # Handle response
                  if response.response_audio:
                      await output_adapter.play_audio(response.response_audio)
                  elif response.response_text:
                      audio_stream = await self.tts_service.synthesize(
                          response.response_text
                      )
                      await output_adapter.play_audio(audio_stream)
                  
                  # Handle actions
                  for action in response.actions:
                      await self._execute_action(action)
                      
              except Exception as e:
                  logger.error(f"Error processing audio chunk: {e}")
                  continue
                  
      except Exception as e:
          logger.error(f"Fatal error in audio handling: {e}")
          raise
      finally:
          await input_adapter.stop()
          logger.info("Audio input stopped")
  ```
- Add pipeline configuration options to `services/orchestrator/config.py`
- Verify latency remains acceptable (< 2s end-to-end)
- Integration tests across services in `services/tests/integration/test_orchestrator_pipeline.py`
- Add metrics tracking for pipeline stages

**Exit Condition:** Orchestrator uses unified pipeline, no performance regression, all tests pass

---

## Phase 3: Context & Session Management

**Objective:** Formalize conversation context and session persistence for multi-turn conversations. **Build upon existing session management patterns in orchestrator rather than replacing them.**

### PR 3.1: Context Types & Storage Interface

**Branch:** `feature/context-types`

**Tasks:**
- Create `services/orchestrator/context/types.py`:
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
- Create `services/orchestrator/context/storage_interface.py`:
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
- Add validation and serialization helpers
- Unit tests for types in `services/orchestrator/tests/unit/test_context_types.py`

**Exit Condition:** Context types defined and tested

---

### PR 3.2: In-Memory Context Storage

**Branch:** `feature/memory-context-storage`

**Tasks:**
- Implement `services/orchestrator/context/memory_storage.py`:
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
- Thread-safe operations using asyncio locks
- TTL-based expiration
- Unit tests for storage operations in `services/orchestrator/tests/unit/test_memory_storage.py`

**Exit Condition:** In-memory storage works for single-instance deployment

---

### PR 3.3: Context Manager

**Branch:** `feature/context-manager`

**Tasks:**
- Create `services/orchestrator/context/manager.py`:
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
- Implement `get_context()`, `update_context()`, `save_context()`
- Add context lifecycle management (creation, updates, expiration)
- Integration with agent manager
- Unit tests in `services/orchestrator/tests/unit/test_context_manager.py`
- Integration tests in `services/orchestrator/tests/integration/test_context_lifecycle.py`

**Exit Condition:** Context management works end-to-end

---

### PR 3.4: SQL-Based Context Storage (Optional)

**Branch:** `feature/sql-context-storage`

**Tasks:**
- Implement `services/orchestrator/context/sql_storage.py`:
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
- Use SQLAlchemy async for PostgreSQL
- Schema migration support (Alembic)
- Integration tests with test database in `services/orchestrator/tests/integration/test_sql_storage.py`
- Configuration for storage backend selection in `.env`:
  ```bash
  CONTEXT_STORAGE_BACKEND=memory  # or "sql"
  CONTEXT_DB_URL=postgresql+asyncpg://user:pass@localhost/db
  ```

**Exit Condition:** SQL storage available for production use

---

## Phase 4: Advanced Agent Capabilities

**Objective:** Implement sophisticated agents with LLM integration and multi-turn conversations.

### PR 4.1: Summarization Agent

**Branch:** `feature/summarization-agent`

**Tasks:**
- Create `services/orchestrator/agents/summarization_agent.py`:
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
- Use context history to generate summaries
- Integrate with LLM service via HTTP
- Add configuration for summary triggers:
  ```python
  SUMMARY_MIN_TURNS = env.int("SUMMARY_MIN_TURNS", default=5)
  SUMMARY_TRIGGER_KEYWORDS = env.list("SUMMARY_TRIGGER_KEYWORDS", default=["summarize", "summary"])
  ```
- Unit tests in `services/orchestrator/tests/unit/test_summarization_agent.py`
- Integration tests with LLM service in `services/orchestrator/tests/integration/test_summarization_integration.py`

**Exit Condition:** Summarization agent functional, tests pass

---

### PR 4.2: Intent Classification Agent

**Branch:** `feature/intent-agent`

**Tasks:**
- Create `services/orchestrator/agents/intent_agent.py`:
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
- Integrate with LLM service for classification
- Add intent configuration:
  ```python
  INTENT_CLASSES = env.json("INTENT_CLASSES", default={
      "echo": "echo",
      "summarize": "summarization",
      "general": "conversation"
  })
  ```
- Tests with various intent types in `services/orchestrator/tests/unit/test_intent_agent.py`

**Exit Condition:** Intent-based routing works

---

### PR 4.3: Multi-Turn Conversation Agent

**Branch:** `feature/conversation-agent`

**Tasks:**
- Create `services/orchestrator/agents/conversation_agent.py`:
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
- Maintain conversation state across turns
- Generate contextual responses
- Integration with LLM service
- Tests for multi-turn conversations in `services/orchestrator/tests/integration/test_conversation_agent.py`

**Exit Condition:** Multi-turn conversations work naturally

---

## Phase 5: Documentation & Developer Experience

**Objective:** Comprehensive documentation for extending the platform.

### PR 5.1: Adapter Development Guide

**Branch:** `docs/adapter-guide`

**Tasks:**
- Create `docs/guides/adding_adapter.md`:
  ```markdown
  # Adding a New Audio Adapter
  
  ## Overview
  Audio adapters enable the orchestrator to work with different audio sources...
  
  ## Interface Requirements
  ### Input Adapter
  - Implement `AudioInputAdapter` ABC
  - Methods: `start()`, `stop()`, `get_audio_stream()`, `is_active`
  
  ### Output Adapter
  - Implement `AudioOutputAdapter` ABC
  - Methods: `play_audio()`, `stop()`
  
  ## Step-by-Step Guide
  1. Create adapter file in `services/common/audio/`
  2. Implement interface methods
  3. Register adapter in registry
  4. Add configuration
  5. Write tests
  
  ## Example: WebRTC Adapter
  [Full code example]
  ```
- Include code examples for both input and output adapters
- Explain registration process
- Show testing strategies
- Include common pitfalls and solutions

**Exit Condition:** Guide clear and actionable

---

### PR 5.2: Agent Development Guide

**Branch:** `docs/agent-guide`

**Tasks:**
- Create `docs/guides/adding_agent.md`:
  ```markdown
  # Adding a New Agent
  
  ## Overview
  Agents process user input and generate responses...
  
  ## BaseAgent Interface
  - Implement `BaseAgent` ABC
  - Methods: `handle()`, `name` property
  
  ## Step-by-Step Guide
  1. Create agent file in `services/orchestrator/agents/`
  2. Implement `handle()` method
  3. Register in AgentManager
  4. Add routing logic
  5. Write tests
  
  ## Example: Weather Agent
  [Full code example with API integration]
  
  ## Testing Strategies
  - Unit tests with mocked services
  - Integration tests with real services
  - Test routing logic
  ```
- Explain BaseAgent interface in detail
- Show routing registration
- Cover testing approaches
- Include best practices (error handling, timeouts, etc.)

**Exit Condition:** Guide enables agent development

---

### PR 5.3: Architecture Documentation Update

**Branch:** `docs/architecture-update`

**Tasks:**
- Update `docs/architecture/system-overview.md`:
  - Add section on adapter framework
  - Add section on agent framework
  - Update service interaction diagrams
  - Add data flow diagrams
- Create `docs/architecture/audio_pipeline.md`:
  - Document pipeline stages
  - Show conversion flow
  - Explain buffering strategy
- Create `docs/architecture/agent_system.md`:
  - Document agent lifecycle
  - Show routing logic
  - Explain context management
- Add sequence diagrams for key flows:
  - Voice input → response (end-to-end)
  - Agent selection flow
  - Context retrieval and update
- Update all architecture diagrams using Mermaid

**Exit Condition:** Architecture documentation current and comprehensive

---

## Phase 6: Performance & Observability

**Objective:** Optimize performance and improve monitoring capabilities.

### PR 6.1: Performance Instrumentation

**Branch:** `feature/performance-metrics`

**Tasks:**
- Create `services/common/metrics.py`:
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
- Add timing decorators to critical paths:
  ```python
  @track_latency(transcription_latency_seconds)
  async def transcribe(audio: AudioChunk) -> str:
      ...
  ```
- Instrument audio pipeline stages
- Add latency tracking to agent execution
- Expose metrics via `/metrics` endpoint in each service
- Create example Grafana dashboard configuration in `monitoring/grafana/`

**Exit Condition:** Performance metrics available and accurate

---

### PR 6.2: Distributed Tracing

**Branch:** `feature/distributed-tracing`

**Tasks:**
- Add OpenTelemetry instrumentation:
  ```python
  from opentelemetry import trace
  from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
  
  # Initialize tracer
  tracer = trace.get_tracer(__name__)
  
  # Instrument FastAPI apps
  FastAPIInstrumentor.instrument_app(app)
  ```
- Trace audio processing pipeline with spans
- Trace cross-service calls (STT, LLM, TTS)
- Add correlation IDs throughout:
  ```python
  correlation_id = str(uuid.uuid4())
  logger.info("Processing audio", extra={"correlation_id": correlation_id})
  ```
- Integration with Jaeger or Zipkin
- Configuration in `.env`:
  ```bash
  OTEL_ENABLED=true
  OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
  ```
- Documentation for setting up tracing infrastructure

**Exit Condition:** Traces available for debugging, correlation IDs propagated

---

### PR 6.3: Performance Optimization

**Branch:** `optimize/audio-pipeline`

**Tasks:**
- Profile audio pipeline bottlenecks using `cProfile` or `py-spy`
- Optimize buffer sizes based on profiling:
  ```python
  OPTIMAL_CHUNK_SIZE_MS = 20  # Based on benchmarks
  BUFFER_SIZE_CHUNKS = 5  # Minimize latency while preventing drops
  ```
- Reduce unnecessary memory copies in audio handling
- Add caching where appropriate (e.g., model loading)
- Implement connection pooling for HTTP clients
- Benchmark improvements against baseline:
  ```python
  # Before: 2.5s average end-to-end
  # After:  1.8s average end-to-end (28% improvement)
  ```
- Document optimization decisions in `docs/operations/performance.md`

**Exit Condition:** Measurable latency improvements, meets performance targets

---

## Success Criteria (Overall)

### Functional Requirements
- [ ] Platform abstracts I/O adapters (Discord, File, future: WebRTC)
- [ ] Audio pipeline end-to-end works: adapter → STT → agent → TTS → adapter
- [ ] Multiple agents functional (Echo, Summarization, Intent, Conversation)
- [ ] Agent routing works correctly based on transcript and context
- [ ] Core orchestrator logic is adapter-agnostic
- [ ] Context persists across conversation turns
- [ ] Session management handles multiple concurrent users

### Quality Requirements
- [ ] Test coverage ≥ 80% maintained throughout
- [ ] All PRs pass `make test` and `make lint`
- [ ] No regressions in existing functionality
- [ ] Documentation complete and current

### Performance Requirements
- [ ] Wake detection: < 200ms
- [ ] STT processing: < 300ms from speech onset
- [ ] Command response: < 2s total (end-to-end)
- [ ] Voice join/response: 10-15s acceptable
- [ ] System handles concurrent audio streams

### Operational Requirements
- [ ] All PRs reviewed and merged to main
- [ ] Monitoring and observability in place
- [ ] Metrics exported to Prometheus
- [ ] Distributed tracing functional
- [ ] Health checks for all services

---

## AI Agent Sequential Management

### AI Agent Workflow (No PRs During Development)
- **Direct commits:** AI agent commits directly to `feature/audio-platform-cutover`
- **No intermediate PRs:** Work happens on single branch until complete
- **Commit per phase:** Each phase gets one comprehensive commit
- **Continuous testing:** Run `make test` and `make lint` after each phase
- **Phase validation:** Ensure phase objectives met before next phase

### Phase Commit Requirements (AI Agent)
- [ ] All tests pass: `make test`
- [ ] All linters pass: `make lint`
- [ ] Phase objectives met (see phase exit conditions)
- [ ] No regressions in existing tests
- [ ] Clear commit message: "Phase X: [Description] complete"
- [ ] Ready for next phase

### Final Cutover PR Requirements (Merging to main)
- [ ] ALL phases complete on cutover branch
- [ ] Full test suite passes (100% of tests)
- [ ] Performance benchmarks meet or exceed baseline
- [ ] Load testing completed (simulate 10x normal load)
- [ ] Feature flag system tested (can toggle on/off)
- [ ] Documentation complete (Phase 5)
- [ ] CHANGELOG.md updated with comprehensive release notes
- [ ] Security audit passed
- [ ] Human review required (AI agent cannot self-approve final merge)

### AI Agent Development Process
1. **Start phase:** Read phase objectives and requirements
2. **Implement:** Complete all phase tasks sequentially
3. **Test:** Run full test suite and linters
4. **Validate:** Ensure phase objectives met
5. **Commit:** Single commit with descriptive message
6. **Next phase:** Move to next phase (no parallel work)
7. **Repeat:** Until all phases complete
8. **Final review:** Human review before merge to main

---

## Branch Strategy (AI Agent Sequential)

### Single Branch Strategy
- **`main`** - current production code
- **`feature/audio-platform-cutover`** - AI agent development branch (2-3 weeks)

### AI Agent Workflow
```
main
  └── feature/audio-platform-cutover (AI agent works here)
       ├── Phase -1: Cleanup (commit)
       ├── Phase 0: Agents (commit)
       ├── Phase 1: Adapters (commit)
       ├── Phase 2: Pipeline (commit)
       ├── Phase 3: Context (commit)
       ├── Phase 4: Advanced Agents (commit)
       ├── Phase 5: Documentation (commit)
       ├── Phase 6: Performance (commit)
       └── Final: Integration testing (commit)

Once complete: Merge feature/audio-platform-cutover → main
```

### AI Agent Branching Rules
- **Single branch:** AI agent works directly on `feature/audio-platform-cutover`
- **No sub-branches:** All work happens on the same branch sequentially
- **Commit per phase:** Each phase gets its own commit with clear message
- **No parallel work:** AI agent focuses on one phase at a time
- **Final merge:** Single large PR to main when all phases complete
- **Keep branch:** Maintain cutover branch for 1 week as backup

---

## Fast Cutover Rollback Strategy

### Design for Fast Rollback
Since this IS a "big bang" deployment, we need robust rollback:

**Primary Rollback Mechanism - Feature Flag:**
```python
# services/orchestrator/app.py
ENABLE_NEW_ARCHITECTURE = env.bool("ENABLE_NEW_ARCHITECTURE", default=True)

if ENABLE_NEW_ARCHITECTURE:
    logger.info("Using NEW architecture (agent/adapter system)")
    orchestrator = NewOrchestrator(
        agents=agent_manager,
        adapters=adapter_registry,
        pipeline=audio_pipeline
    )
else:
    logger.warning("Using LEGACY architecture (fallback mode)")
    orchestrator = LegacyOrchestrator()  # Current implementation
```

**Rollback Triggers:**
- Error rate > 5% within first hour
- Latency > 3s (50% worse than baseline)
- Service crashes or restart loops
- User reports of broken functionality

**Immediate Rollback Process (< 5 minutes):**
1. Set `ENABLE_NEW_ARCHITECTURE=false` in all `.env` files
2. Restart all services: `make docker-restart`
3. Verify services healthy: `make logs`
4. Monitor for 1 hour
5. If stable, investigate issues offline

**Secondary Rollback - Git Revert:**
If feature flag fails:
1. `git revert <cutover-merge-commit>` on main
2. Force push to main (emergency only)
3. Redeploy all services
4. Full incident review

**Keep Legacy Code for 1 Week:**
- Don't delete old orchestrator code immediately
- Mark as `@deprecated` but keep functional
- Remove after 1 week of successful new architecture operation

---

## AI Agent Sequential Work Strategy

### Sequential Phase Dependencies (AI Agent)
1. **Phase -1: Cleanup** (2-3 days) - Foundation (must be first)
2. **Phase 0: Agents** (3-4 days) - Core abstractions (depends on cleanup)
3. **Phase 1: Adapters** (3-4 days) - I/O abstractions (depends on cleanup)
4. **Phase 2: Pipeline** (3-4 days) - Audio processing (depends on 0,1)
5. **Phase 3: Context** (2-3 days) - Session management (depends on 0)
6. **Phase 4: Advanced Agents** (2-3 days) - Sophisticated agents (depends on 0,2,3)
7. **Phase 5: Documentation** (1-2 days) - Complete docs (can start after 4)
8. **Phase 6: Performance** (1-2 days) - Optimization (depends on 2)

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
├─ Feature flag testing
├─ Final merge to main
└─ Deploy with monitoring
```

### AI Agent Success Criteria Per Phase
Each phase must be **100% complete** before moving to next:
- [ ] All code implemented and tested
- [ ] All tests pass (`make test`)
- [ ] All linters pass (`make lint`)
- [ ] Phase objectives met (see exit conditions)
- [ ] No regressions in existing functionality
- [ ] Commit with descriptive message
- [ ] Ready for next phase

---

## Fast Cutover Strategy

### What Already Exists (Excellent Infrastructure)
- ✅ Microservices architecture (discord, stt, llm, orchestrator, tts)
- ✅ Docker Compose orchestration
- ✅ Configuration management (`services.common.config`) - **EXCELLENT, KEEP**
- ✅ Health checks and monitoring basics - **EXCELLENT, KEEP**
- ✅ Test framework (pytest, integration tests) - **EXCELLENT, KEEP**
- ✅ Linting and formatting setup
- ✅ Audio processing (`AudioProcessor`, `AudioPipeline`) - **EXCELLENT, BUILD UPON**
- ✅ MCP integration patterns - **GOOD, REPURPOSE**

### What We're Adding (New Architecture)
- 🆕 Agent abstraction framework (builds upon existing orchestrator patterns)
- 🆕 Audio adapter abstraction framework (builds upon existing audio processing)
- 🆕 Formalized audio processing pipeline (enhances existing AudioPipeline)
- 🆕 Session and context persistence (builds upon existing session management)
- 🆕 Advanced agents (summarization, intent, conversation)
- 🆕 Comprehensive monitoring and tracing (builds upon existing health checks)
- 🆕 Developer documentation

### Fast Cutover Approach (AI Agent Sequential)
- **Sequential Development:** AI agent works through phases one at a time
- **Feature Branch:** Build complete new architecture on single feature branch
- **Aggressive Timeline:** Complete in 2-3 weeks with focused AI work
- **Test in Isolation:** Full test suite before merge to main
- **Single Merge:** One large PR with entire new architecture
- **Rollback Plan:** Keep old code path available via feature flag for 1 week

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
- Day 1-2: Phase -1 (Cleanup) - Establish clean baseline
- Day 3-4: Phase 0 (Agents) - Build agent framework
- Day 5-7: Phase 1 (Adapters) - Build adapter framework

**Week 2: Integration & Context**
- Day 1-3: Phase 2 (Pipeline) - Integrate audio processing
- Day 4-5: Phase 3 (Context) - Add session management
- Day 6-7: Integration testing and bug fixes

**Week 3: Polish & Cutover**
- Day 1-2: Phase 4 (Advanced Agents) - Add sophisticated agents
- Day 3: Phase 5 (Documentation) - Complete docs
- Day 4: Phase 6 (Performance) - Optimize and benchmark
- Day 5-7: Final testing, load testing, and cutover preparation

### Cutover Prerequisites
- [ ] All tests pass on feature branch (100% of existing + new tests)
- [ ] Performance meets or exceeds current benchmarks
- [ ] Feature flag system in place for rollback
- [ ] Load testing completed successfully
- [ ] Documentation complete
- [ ] Team trained on new architecture

### Rollback Plan
**If cutover fails within first week:**
1. Toggle `ENABLE_NEW_ARCHITECTURE=false` in environment
2. Restart services (falls back to old code paths)
3. Monitor for 24 hours
4. Fix issues on feature branch
5. Re-attempt cutover when ready

**Feature flag implementation:**
```python
# In orchestrator startup
if env.bool("ENABLE_NEW_ARCHITECTURE", default=True):
    # Use new agent/adapter system
    orchestrator = NewOrchestrator(agents, adapters, pipeline)
else:
    # Use legacy system (preserved for 1 week)
    orchestrator = LegacyOrchestrator()
```

---

## Notes for AI Agent (Cursor)

### Sequential Development Principles
- **One phase at a time:** Complete each phase fully before moving to next
- **No parallel work:** Focus entirely on current phase objectives
- **Generate tests alongside implementation:** Never leave testing for later
- **Include comprehensive docstrings:** Explain why and how, not just what
- **Use type hints everywhere:** Enable static analysis and IDE support
- **Follow existing patterns:** Study codebase before adding new patterns
- **Commit per phase:** Each phase gets one comprehensive commit
- **Validate before next:** Ensure phase objectives met before proceeding

### AI Agent Workflow Per Phase
1. **Read phase objectives:** Understand what needs to be built
2. **Study existing code:** Look for similar patterns to follow
3. **Implement systematically:** Work through phase tasks in order
4. **Test continuously:** Run `make test` and `make lint` frequently
5. **Validate completion:** Ensure all phase objectives met
6. **Commit with clear message:** "Phase X: [Description] complete"
7. **Move to next phase:** Only after current phase is 100% complete

### Code Quality Focus for AI Agent
- **Design:** Does this fit the overall architecture? Is it the right abstraction?
- **Correctness:** Handle edge cases and error conditions properly
- **Performance:** Will it meet latency targets? Consider memory usage
- **Maintainability:** Write clear, understandable code with good docstrings
- **Security:** Validate inputs, handle errors safely
- **Testing:** Write comprehensive tests that verify behavior

### When Stuck (AI Agent)
1. **Re-read phase objectives:** Make sure you understand what's needed
2. **Study existing code:** Look for similar implementations to follow
3. **Check dependencies:** Ensure previous phases are complete
4. **Run tests:** Make sure current work doesn't break existing functionality
5. **Ask for clarification:** If requirements are unclear, ask the user
6. **Focus on current phase:** Don't jump ahead to future phases

### AI Agent Success Pattern
```
For each phase:
1. Read phase objectives and requirements
2. Study existing codebase for patterns
3. Implement phase functionality systematically
4. Write comprehensive tests
5. Run make test and make lint
6. Validate phase objectives are met
7. Commit with clear message
8. Move to next phase only after current is complete
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
- **`pyproject.toml`** - Python tooling config (black, ruff, mypy, pytest)
- **`docker-compose.yml`** - Service orchestration
- **`.env.sample`** - Environment variable template
- **`services/*/requirements.txt`** - Service dependencies

### Key Directories
- **`services/`** - All microservices
- **`services/common/`** - Shared utilities
- **`services/orchestrator/agents/`** - Agent implementations
- **`services/common/audio/`** - Audio adapters and pipeline
- **`docs/`** - All documentation
- **`tests/`** - Shared test fixtures

---

**Last Updated:** 2025-10-21
**Version:** 2.0 (Enhanced with cleanup phase, PR workflow, and technical specifics)
