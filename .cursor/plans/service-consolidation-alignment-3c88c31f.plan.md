<!-- 3c88c31f-ff89-4039-8680-3fac956bb4db 9e799639-940f-4755-a851-5b7434be5c85 -->
# Service Consolidation Alignment Plan

## Overview

Consolidate service duplication by removing four legacy services and updating all references to use enhanced alternatives. This reduces memory usage by 18.75% (32GB to 26GB) and simplifies maintenance.

## Alignment Decisions

1. **LLM Service**: Keep `llm_flan` (FLAN-T5), remove `llm` (llama.cpp)
2. **Orchestrator Service**: Keep `orchestrator_enhanced` (LangChain), remove `orchestrator` (MCP-based)
3. **TTS Service**: Keep `tts_bark` (Bark + Piper fallback), remove `tts` (Piper only)
4. **Audio Processing**: Keep `audio_processor` (comprehensive), remove `audio_preprocessor` (MetricGAN+ only)

## Phase 1: Eliminate All Fallbacks (CRITICAL)

### 1.1 Update orchestrator_enhanced Configuration
**File**: `docker-compose.yml` (lines 59-62)
```yaml
# REMOVE these fallback lines:
- LLM_FALLBACK_URL=http://llm:8000
```

**File**: `services/orchestrator_enhanced/Dockerfile` (line 30)
```dockerfile
# REMOVE this line:
ENV LLM_FALLBACK_URL=http://llm:8000
```

**File**: `services/orchestrator_enhanced/app.py` (lines 299-303)
```python
# REMOVE fallback logic in orchestrator.py
fallback_url = os.getenv("LLM_FALLBACK_URL", "http://llm:8000")
llm_urls = [
    ("primary", self.config.llm_url),  # FLAN-T5
    ("fallback", fallback_url),  # REMOVE THIS
]
```

### 1.2 Update tts_bark Configuration
**File**: `docker-compose.yml` (lines 402-406)
```yaml
# REMOVE these fallback lines:
- PIPER_FALLBACK_URL=http://tts:7000
depends_on:
  tts:  # REMOVE THIS DEPENDENCY
```

**File**: `services/tts_bark/app.py` (lines 220-231)
```python
# REMOVE fallback health check method
async def _check_piper_fallback() -> bool:
    # REMOVE ENTIRE METHOD
```

**File**: `services/tts_bark/synthesis.py` (lines 142-146)
```python
# REMOVE fallback synthesis logic
async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://tts:7000/synthesize",  # REMOVE THIS FALLBACK
        json={"text": text, "voice": voice},
        timeout=30.0,
```

### 1.3 Update testing_ui Configuration
**File**: `services/testing_ui/app.py` (line 41)
```python
# CHANGE from audio-preprocessor to audio-processor
AUDIO_PREPROCESSOR_URL = "http://audio-processor:9100"  # UPDATED URL
```

**File**: `docker-compose.yml` (lines 449-451)
```yaml
# UPDATE environment variables
- AUDIO_PREPROCESSOR_URL=http://audio-processor:9100
- STT_URL=http://stt:9000
- ORCHESTRATOR_URL=http://orchestrator-enhanced:8200
```

## Phase 2: Update All Service References (EXTENSIVE - 158+ files)

### 2.1 Update Core Service URLs
**Pattern**: `http://llm:8000` → `http://llm-flan:8100`
**Files**: 15+ files including:
- `services/common/config/presets.py` (line 116)
- `services/tests/integration/contracts/llm_contract.py` (line 14)
- `services/tests/unit/services/test_service_contracts.py` (line 21)

**Pattern**: `http://orchestrator:8000` → `http://orchestrator-enhanced:8200`
**Files**: 25+ files including:
- `services/common/config/presets.py` (line 124)
- `services/discord/app.py` (line 138)
- `services/discord/discord_voice.py` (line 97)
- `services/discord/orchestrator_client.py` (line 19)

**Pattern**: `http://tts:7000` → `http://tts-bark:7100`
**Files**: 20+ files including:
- `services/tests/integration/contracts/tts_contract.py` (line 14)
- `services/tests/unit/services/test_service_contracts.py` (line 22)

**Pattern**: `http://audio-preprocessor:9200` → `http://audio-processor:9100`
**Files**: 5+ files including:
- `services/testing_ui/app.py` (line 41)

### 2.2 Update Service Contracts
**File**: `services/tests/integration/contracts/llm_contract.py
```python
LLM_CONTRACT = ServiceContract(
    service_name="llm-flan",  # UPDATED
    base_url="http://llm-flan:8100",  # UPDATED
    version="1.0.0",
    endpoints=[
        # ... existing endpoints
    ]
)
```

**File**: `services/tests/integration/contracts/orchestrator_contract.py`
```python
ORCHESTRATOR_CONTRACT = ServiceContract(
    service_name="orchestrator-enhanced",  # UPDATED
    base_url="http://orchestrator-enhanced:8200",  # UPDATED
    version="1.0.0",
    endpoints=[
        # ... existing endpoints
    ]
)
```

**File**: `services/tests/integration/contracts/tts_contract.py`
```python
TTS_CONTRACT = ServiceContract(
    service_name="tts-bark",  # UPDATED
    base_url="http://tts-bark:7100",  # UPDATED
    version="1.0.0",
    endpoints=[
        # ... existing endpoints
    ]
)
```

### 2.3 Update Configuration Presets
**File**: `services/common/config/presets.py` (lines 114-126)
```python
def __init__(
    self,
    llm_url: str = "http://llm-flan:8100",  # UPDATED
    tts_url: str = "http://tts-bark:7100",  # UPDATED
    llm_auth_token: str = "",
    # ... other parameters
    base_url: str = "http://orchestrator-enhanced:8200",  # UPDATED
    **kwargs: Any,
) -> None:
```

## Phase 3: Update All Documentation (EXTENSIVE)

### 3.1 Update README.md
**File**: `README.md` (lines 25-32)
```markdown
- **Orchestrator Service** (`services/orchestrator_enhanced`)
  - Coordinates transcript processing, LangChain tool calls, and response planning. Routes reasoning requests to the LLM service.

- **Language Model Service** (`services/llm_flan`)
  - Presents an OpenAI-compatible endpoint that can broker LangChain tool invocations and return reasoning output to the orchestrator.

- **Text-to-Speech Service** (`services/tts_bark`)
  - Streams Bark-generated audio for orchestrator responses with authentication and rate limits.
```

### 3.2 Update AGENTS.md
**File**: `AGENTS.md` (lines 163-168)
```markdown
- `services/orchestrator_enhanced` (Python; FastAPI, LangChain) — Coordinates transcript processing,
  LangChain tool calls, and response planning. Routes reasoning requests to LLM service.
- `services/llm_flan` (Python; FastAPI) — Presents an OpenAI-compatible endpoint that
  can broker LangChain tool invocations and return reasoning output to the orchestrator.
- `services/tts_bark` (Python; FastAPI, Bark) — Streams Bark-generated audio for
  orchestrator responses with authentication and rate limits.
```

### 3.3 Update Architecture Documentation
**File**: `docs/architecture/system-overview.md` (lines 60-63)
```markdown
| `services/orchestrator_enhanced` | Coordinates audio pipeline, agent management, transcript processing, LangChain tool calls, and response planning. Routes reasoning requests to LLM service. | FastAPI, LangChain SDKs, Agent Framework. |
| `services/llm_flan` | Provides OpenAI-compatible completions and reasoning capabilities for the orchestrator. | FastAPI, FLAN-T5 executor. |
| `services/tts_bark` | Streams Bark-generated audio for orchestrator responses with authentication and rate limits. | FastAPI, Bark. |
```

### 3.4 Update All Test Documentation
**Files**: Multiple test documentation files need updates:
- `docs/testing/TESTING.md`
- `docs/testing/TTS_TESTING.md`
- `docs/guides/testing_agents.md`
- `docs/guides/testing_audio_adapters.md`

## Phase 4: Remove Legacy Services (DESTRUCTIVE)

### 4.1 Remove from docker-compose.yml
**File**: `docker-compose.yml`
- **Remove `llm` service** (lines 242-271)
- **Remove `orchestrator` service** (lines 273-308)
- **Remove `tts` service** (lines 310-339)
- **Remove `audio-preprocessor` service** (lines 342-386)

### 4.2 Remove Service Directories
```bash
# Remove legacy service directories
rm -rf services/llm/
rm -rf services/orchestrator/
rm -rf services/tts/
rm -rf services/audio_preprocessor/
```

### 4.3 Remove Service-Specific Files
```bash
# Remove service-specific requirements files
rm services/llm/requirements.txt
rm services/orchestrator/requirements.txt
rm services/tts/requirements.txt
rm services/audio_preprocessor/requirements.txt

# Remove service-specific Dockerfiles
rm services/llm/Dockerfile
rm services/orchestrator/Dockerfile
rm services/tts/Dockerfile
rm services/audio_preprocessor/Dockerfile

# Remove service-specific .env.service files
rm services/llm/.env.service
rm services/orchestrator/.env.service
rm services/tts/.env.service
rm services/audio_preprocessor/.env.service
```

## Phase 5: Enhance Audio Processor (DESTRUCTIVE)

### 5.1 Integrate audio_preprocessor Capabilities
**File**: `services/audio_processor/enhancement.py`
- **Enhance existing `AudioEnhancer` class** with additional capabilities from removed `audio_preprocessor`
- **Add unified enhancement methods** combining existing capabilities with MetricGAN+ from removed service
- **Implement `enhance_audio_pipeline()` method** for comprehensive audio processing

### 5.2 Add Denoising Endpoints
**File**: `services/audio_processor/app.py`
- **Add `POST /denoise` endpoint** - Full audio denoising
- **Add `POST /denoise/streaming` endpoint** - Real-time frame denoising
- **Update startup** to initialize enhanced `AudioEnhancer` with additional capabilities

### 5.3 Update Environment Configuration
**File**: `.env.sample`
```bash
# UPDATE LLM section
LLM_BASE_URL=http://llm-flan:8100
LLM_AUTH_TOKEN=changeme

# UPDATE TTS section
TTS_BASE_URL=http://tts-bark:7100
TTS_AUTH_TOKEN=changeme

# UPDATE Orchestrator section
ORCHESTRATOR_BASE_URL=http://orchestrator-enhanced:8200
ORCHESTRATOR_AUTH_TOKEN=changeme
```

## Phase 6: Update All Test Files (FINAL PHASE - 15+ files)

### 6.1 Update Integration Tests
**File**: `services/tests/integration/stt/test_stt_orchestrator_integration.py`
```python
# UPDATE all references from orchestrator:8000 to orchestrator-enhanced:8200
response = await client.post(
    "http://orchestrator-enhanced:8200/process",  # UPDATED
    json={
        "guild_id": test_guild_id,
        # ... rest of request
    }
)
```

### 6.2 Update E2E Tests
**File**: `services/tests/e2e/discord/test_e2e_voice_pipeline.py`
```python
# UPDATE orchestrator references
orch_response = await client.post(
    "http://orchestrator-enhanced:8200/mcp/transcript",  # UPDATED
    json={
        "guild_id": test_voice_context["guild_id"],
        # ... rest of request
    }
)

# UPDATE TTS references
tts_response = await client.post(
    "http://tts-bark:7100/synthesize",  # UPDATED
    json={
        "text": f"E2E test response to: {transcript}",
        # ... rest of request
    }
)
```

### 6.3 Update Unit Tests
**File**: `services/tests/unit/services/test_service_contracts.py`
```python
# UPDATE service contract references
[
    (STT_CONTRACT, "stt", "http://stt:9000"),
    (LLM_CONTRACT, "llm-flan", "http://llm-flan:8100"),  # UPDATED
    (TTS_CONTRACT, "tts-bark", "http://tts-bark:7100"),  # UPDATED
    (ORCHESTRATOR_CONTRACT, "orchestrator-enhanced", "http://orchestrator-enhanced:8200"),  # UPDATED
],
```

### 6.4 Update Additional Test Files
**Files**: 15+ additional test files need updates:
- `services/tests/integration/orchestrator/test_orchestrator_tts_integration.py`
- `services/tests/integration/orchestrator/test_voice_pipeline_integration.py`
- `services/tests/integration/orchestrator/test_mcp_integration.py`
- `services/tests/integration/orchestrator/test_orchestrator_llm_integration.py`
- `services/tests/integration/orchestrator/test_cross_service_auth.py`
- `services/tests/integration/audio_processor/test_audio_format_chain.py`
- `services/tests/integration/audio_processor/test_performance_integration.py`
- `services/tests/fixtures/voice_pipeline_fixtures.py`
- `services/tests/fixtures/integration_fixtures.py`

## Phase 7: Validation Section

### 7.1 Pre-Implementation Validation
```bash
# Verify all services are running
make run

# Check service health
make logs SERVICE=llm-flan
make logs SERVICE=orchestrator-enhanced
make logs SERVICE=tts-bark
make logs SERVICE=audio-processor
```

### 7.2 Post-Implementation Validation
```bash
# Run all tests
make test

# Run integration tests
make test-integration

# Run E2E tests
make test-e2e

# Verify no legacy service references
grep -r "http://llm:8000" . --exclude-dir=.git
grep -r "http://orchestrator:8000" . --exclude-dir=.git
grep -r "http://tts:7000" . --exclude-dir=.git
grep -r "http://audio-preprocessor:9200" . --exclude-dir=.git
```

## Expected Outcomes

- Memory reduction: 32GB to 26GB (18.75% reduction)
- Simplified service architecture with clear responsibilities
- Enhanced capabilities through unified services
- Reduced maintenance overhead
- Improved performance through optimized service communication
- **Eliminated all fallbacks** as requested
- **Updated all test files** as requested (moved to final phase)
- **Updated all documentation** as requested

## Confidence Scores

- **Phase 1 (Eliminate Fallbacks)**: 95% confidence - straightforward configuration updates
- **Phase 2 (Update References)**: 85% confidence - extensive but systematic URL updates
- **Phase 3 (Update Documentation)**: 90% confidence - comprehensive but straightforward
- **Phase 4 (Remove Services)**: 95% confidence - direct file/directory deletion
- **Phase 5 (Enhance Audio Processor)**: 85% confidence - integration of existing capabilities
- **Phase 6 (Update Tests)**: 80% confidence - extensive but systematic test updates

## Summary

This reordered plan addresses all identified issues with the correct sequence:

- ✅ **Eliminates all fallbacks** as requested
- ✅ **Updates all test files** as requested (moved to final phase)
- ✅ **Updates all documentation** as requested
- ✅ **Corrects line numbers** for service removal
- ✅ **Accounts for 158+ references** throughout codebase
- ✅ **Includes comprehensive validation** steps
- ✅ **Proper sequence**: Destructive changes first, test updates last

The plan is significantly more extensive than originally proposed, requiring updates to 158+ references across the codebase, extensive documentation updates, and comprehensive test file updates, but now follows the correct logical sequence with test updates at the end.