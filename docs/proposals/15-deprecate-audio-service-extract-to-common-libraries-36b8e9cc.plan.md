<!-- 36b8e9cc-a05e-4d7f-b760-9ff66aaf77d0 927de695-44fb-4204-8c39-29a66842f3bd -->
# Audio Service Deprecation Plan

## Problem Analysis

### Current Architecture

-  **Audio Service**: Standalone FastAPI service (`services/audio/`) on port 9100
-  **Consumers**: Discord (frame processing) and STT (enhancement only)
-  **Communication**: HTTP with base64 encoding, circuit breakers, retry logic
-  **Dependencies**: Audio service requires `python-ml` base (PyTorch, SpeechBrain, GPU)

### Data Flow Tracing

**Discord Service Flow:**

```
discord_voice.py:ingest_voice_packet()
  → AudioProcessorWrapper.register_frame_async()
    → AudioProcessorClient.process_frame() [HTTP POST to audio:9100/process/frame]
      → Audio service processes with VAD + normalization
      → Returns processed PCMFrame
  → Wrapper converts to AudioSegment
  → Enqueued for STT transcription
```

**STT Service Flow:**

```
stt/app.py:transcribe()
  → _enhance_audio_if_enabled()
    → STTAudioProcessorClient.enhance_audio() [HTTP POST to audio:9100/enhance/audio]
      → Audio service applies MetricGAN+ enhancement
      → Returns enhanced WAV bytes
  → STT transcribes enhanced audio
```

### Dependency Tree

```
audio service:
 - Base: python-ml (PyTorch, SpeechBrain, numpy, scipy)
 - Dependencies: webrtcvad==2.0.10
 - GPU: Required for MetricGAN+

discord service:
 - Base: python-web (no ML, has numpy)
 - Current: Uses AudioProcessorClient (HTTP dependency)
 - Has: webrtcvad==2.0.10 already installed

stt service:
 - Base: python-ml (has PyTorch, SpeechBrain already)
 - Current: Uses STTAudioProcessorClient (HTTP dependency)
 - Needs: Direct MetricGAN+ access
```

## Solution: Modular Library Extraction

### Core Principle

Extract technical utilities to `services/common/` following existing patterns (`audio.py`, `model_loader.py`, `http_client.py`). Maintain service independence through optional dependencies and graceful degradation.

## Implementation Plan

### Phase 1: Extract Core Modules (No Breaking Changes)

#### 1.1 Create `services/common/audio_vad.py`

**Purpose**: Lightweight VAD module for frame-level speech detection

**Dependencies**: `webrtcvad`, `numpy` (both already in bases)

**Source**: Extract from `services/audio/processor.py:_apply_vad()`

```python
class VADProcessor:
    """Voice Activity Detection using WebRTC VAD."""
    async def detect_speech(self, frame: PCMFrame) -> bool
    async def apply_vad(self, frame: PCMFrame) -> PCMFrame
```

**Confidence**: 95%

-  Simple extraction, no business logic
-  Follows existing `services/common/audio.py` pattern
-  Discord already has `webrtcvad` dependency

#### 1.2 Create `services/common/audio_quality.py`

**Purpose**: Audio quality metrics calculation (RMS, SNR, clarity)

**Dependencies**: `numpy` only

**Source**: Extract from `services/audio/processor.py:calculate_quality_metrics()`

```python
class AudioQualityMetrics:
    """Calculate audio quality metrics."""
    @staticmethod
    async def calculate_metrics(audio_data: PCMFrame | AudioSegment) -> dict[str, Any]
```

**Confidence**: 98%

-  Pure technical utility, no state
-  Static methods reduce coupling
-  Aligns with existing quality testing utilities

#### 1.3 Create `services/common/audio_processing_core.py`

**Purpose**: Core frame/segment processing without ML dependencies

**Dependencies**: `numpy`, `webrtcvad`, uses `services/common/audio.py`

**Source**: Extract from `services/audio/processor.py:process_frame()` and `process_segment()`

```python
class AudioProcessingCore:
    """Core audio processing - frame and segment processing."""
    async def process_frame(self, frame: PCMFrame) -> PCMFrame
    async def process_segment(self, segment: AudioSegment) -> AudioSegment
    async def calculate_quality_metrics(self, audio_data: ...) -> dict[str, Any]
```

**Confidence**: 90%

-  Combines VAD + quality + format conversion
-  Reuses existing `services/common/audio.py` (unified pattern)
-  Note: Segment processing uses WAV conversion already in common

#### 1.4 Create `services/common/audio_enhancement_ml.py`

**Purpose**: Optional ML-based enhancement (MetricGAN+)

**Dependencies**: PyTorch, SpeechBrain (via lazy imports)

**Source**: Extract from `services/audio/enhancement.py`

```python
class OptionalAudioEnhancer:
    """Optional MetricGAN+ enhancement - requires python-ml."""
    @classmethod
    def is_available(cls) -> bool  # Check if ML dependencies available
    async def enhance_audio_bytes(self, audio_data: bytes) -> bytes
```

**Confidence**: 85%

-  Uses `TYPE_CHECKING` and lazy imports to prevent dependency propagation
-  Follows `BackgroundModelLoader` pattern (unified approach)
-  Graceful degradation when ML unavailable

**Risk Mitigation**: Use function-level imports inside methods to prevent transitive dependencies

### Phase 2: Migrate Discord Service

#### 2.1 Update `services/discord/audio_processor_wrapper.py`

**Change**: Replace HTTP client with direct library calls

```python
# BEFORE: HTTP client
from services.discord.audio_processor_client import AudioProcessorClient
self._audio_processor_client = AudioProcessorClient(...)

# AFTER: Direct library
from services.common.audio_processing_core import AudioProcessingCore
from services.common.audio_quality import AudioQualityMetrics
self._processor = AudioProcessingCore(audio_config)
self._quality = AudioQualityMetrics()
```

**Confidence**: 95%

-  Simple replacement, same interface
-  Eliminates HTTP overhead (~10-50ms per call)
-  Matches existing `services/common/` usage pattern

#### 2.2 Remove `services/discord/audio_processor_client.py`

**Confidence**: 100%

-  No longer needed after wrapper update

#### 2.3 Update `services/discord/app.py`

**Change**: Remove `AudioProcessorClient` import (wrapper handles it)

**Confidence**: 98%

-  Minimal change, wrapper interface unchanged

#### 2.4 Update Discord Tests

**Files**:

-  `services/tests/component/discord/test_audio_processor_client.py` → DELETE
-  `services/tests/component/discord/test_audio_processor_wrapper.py` → Update mocks
-  `services/tests/component/discord/test_audio_pipeline_stages.py` → Update mocks

**Change**: Mock `AudioProcessingCore` instead of `AudioProcessorClient`

**Confidence**: 85%

-  Need to verify all test coverage maintained
-  Update fixtures in `services/tests/fixtures/discord/audio_pipeline_fixtures.py`

### Phase 3: Migrate STT Service

#### 3.1 Update `services/stt/app.py`

**Change**: Replace HTTP client with optional enhancement library

```python
# BEFORE: HTTP client
from .audio_processor_client import STTAudioProcessorClient
_audio_processor_client = STTAudioProcessorClient(...)

# AFTER: Optional library
from services.common.audio_enhancement_ml import OptionalAudioEnhancer
if OptionalAudioEnhancer.is_available():
    _audio_enhancer = OptionalAudioEnhancer(...)
```

**Confidence**: 90%

-  STT already has ML base, so enhancement available
-  Graceful fallback to unenhanced audio (already handled)
-  Health check update needed

#### 3.2 Remove `services/stt/audio_processor_client.py`

**Confidence**: 100%

#### 3.3 Update STT Health Checks

**Change**: Replace `audio_processor_client_loaded` with `audio_enhancer` check

**Confidence**: 95%

-  Straightforward replacement

### Phase 4: Update Testing Service

#### 4.1 Update `services/testing/app.py`

**Change**: Replace `AUDIO_BASE_URL` HTTP calls with direct library usage

**Confidence**: 80%

-  Need to verify testing service actually uses audio endpoints
-  May be minimal usage

### Phase 5: Configuration Cleanup

#### 5.1 Remove Audio Service Configuration

**Files**:

-  `services/common/config/presets.py`: Remove `"service_url": "http://audio:9100"` entries
-  `services/common/config/base.py`: Remove `AUDIO_BASE_URL` default
-  `.env.sample`: Remove `AUDIO_BASE_URL=http://audio:9100`
-  All `.env.service` files: Remove audio service URL references

**Confidence**: 98%

-  Straightforward cleanup

#### 5.2 Update Service Configurations

**Discord**: Add VAD config (already exists, verify)

**STT**: Add enhancement config flags (already exists)

**Confidence**: 95%

### Phase 6: Remove Audio Service

#### 6.1 Remove from Docker Compose

**File**: `docker-compose.yml`

**Change**: Delete audio service section (lines 121-164)

**Confidence**: 100%

#### 6.2 Delete Audio Service Directory

**Directory**: `services/audio/`

**Confidence**: 95%

-  Verify no other references first

#### 6.3 Update Documentation

**Files**:

-  `docs/reference/service-urls.md`: Remove audio service
-  `docs/architecture/shared-utilities.md`: Add new audio modules
-  Update any architecture diagrams

**Confidence**: 90%

### Phase 7: Test Updates

#### 7.1 Integration Tests

**File**: `services/tests/integration/conftest.py`

**Change**: Remove `"AUDIO": "http://audio:9100"` from service URLs

**Confidence**: 95%

#### 7.2 Component Tests

**Change**: Update mocks to use library classes instead of HTTP clients

**Confidence**: 85%

-  Requires test-by-test verification

#### 7.3 E2E Tests

**Change**: Verify pipeline works without audio service

**Confidence**: 90%

## Over-Engineering Review

### Simplified Approaches

1.  **Unified Library Pattern**: Use single `audio_processing_core.py` instead of separate VAD/quality modules

      -  **Decision**: Keep separate modules (VAD, quality, core) for selective imports
      -  **Rationale**: Discord may only need VAD, STT may only need enhancement. Modular approach matches `services/common/` pattern.

2.  **Optional Enhancement Strategy**:

      -  **Simplified**: Use `is_available()` check instead of complex dependency injection
      -  **Decision**: ✅ Already using simple availability check

3.  **Wrapper Removal**:

      -  **Consideration**: Remove `AudioProcessorWrapper` entirely, use `AudioProcessingCore` directly
      -  **Decision**: Keep wrapper for accumulator logic (frame→segment aggregation) but simplify to direct library calls
      -  **Rationale**: Wrapper contains Discord-specific segment building logic, not just HTTP client

## Unified Patterns Applied

1.  **Reuse Existing Common Patterns**:

      -  `services/common/audio.py` already provides format conversion ✅
      -  `BackgroundModelLoader` pattern for optional ML features ✅
      -  Protocol-based architecture for testability ✅

2.  **Consistent Module Structure**:

      -  Lightweight modules: `audio_vad.py`, `audio_quality.py` (numpy only)
      -  Core processing: `audio_processing_core.py` (composes lightweight modules)
      -  Optional ML: `audio_enhancement_ml.py` (lazy imports)

3.  **No New Abstractions**:

      -  Direct library calls, no new wrapper layers
      -  Follows existing `services/common/` usage patterns

## Confidence Scores Summary

| Phase | Component | Confidence | Risk |

|-------|-----------|------------|------|

| 1.1 | Extract VAD module | 95% | Low - Simple extraction |

| 1.2 | Extract quality metrics | 98% | Low - Pure functions |

| 1.3 | Extract core processing | 90% | Medium - Combines multiple concerns |

| 1.4 | Extract ML enhancement | 85% | Medium - Lazy import complexity |

| 2 | Discord migration | 95% | Low - Direct replacement |

| 3 | STT migration | 90% | Low - Already has ML stack |

| 4 | Testing service | 80% | Medium - Unknown usage |

| 5 | Configuration cleanup | 95% | Low - Straightforward |

| 6 | Service removal | 95% | Low - Clean deletion |

| 7 | Test updates | 85% | Medium - Requires verification |

**Overall Confidence**: 90%

## Success Criteria

1.  ✅ All tests pass (unit, component, integration, E2E)
2.  ✅ Discord frame processing works without HTTP calls
3.  ✅ STT enhancement works with direct library calls
4.  ✅ No references to `audio:9100` or `AUDIO_BASE_URL` in codebase
5.  ✅ Docker Compose starts without audio service
6.  ✅ Documentation updated
7.  ✅ No dependency bloat (services only import what they need)

## Rollback Strategy

If issues arise:

1.  Revert commits phase-by-phase (Phase 7 → Phase 1)
2.  Re-enable audio service in Docker Compose
3.  Services can temporarily use HTTP clients again

## Dependencies to Verify

1.  Check if testing service actually uses audio endpoints
2.  Verify all integration test fixtures
3.  Confirm no hidden audio service references in docs
4.  Check CI/CD pipelines for audio service references

### To-dos

-  [ ] Extract VAD functionality to services/common/audio_vad.py from services/audio/processor.py
-  [ ] Extract quality metrics to services/common/audio_quality.py from services/audio/processor.py
-  [ ] Extract core processing to services/common/audio_processing_core.py combining VAD, quality, and format conversion
-  [ ] Extract ML enhancement to services/common/audio_enhancement_ml.py with lazy imports and availability checks
-  [ ] Update services/discord/audio_processor_wrapper.py to use AudioProcessingCore directly instead of HTTP client
-  [ ] Remove AudioProcessorClient import from services/discord/app.py
-  [ ] Delete services/discord/audio_processor_client.py
-  [ ] Update services/stt/app.py to use OptionalAudioEnhancer instead of STTAudioProcessorClient
-  [ ] Update STT health checks to use audio_enhancer instead of audio_processor_client
-  [ ] Delete services/stt/audio_processor_client.py
-  [ ] Update services/testing/app.py to use direct libraries instead of AUDIO_BASE_URL
-  [ ] Remove audio service URLs from services/common/config/presets.py
-  [ ] Remove AUDIO_BASE_URL from services/common/config/base.py
-  [ ] Remove AUDIO_BASE_URL from .env.sample
-  [ ] Remove audio service from docker-compose.yml
-  [ ] Remove audio service from services/tests/integration/conftest.py service URLs
-  [ ] Update all component tests to mock library classes instead of HTTP clients
-  [ ] Update docs to remove audio service references and document new common modules
-  [ ] Delete services/audio/ directory after verification
