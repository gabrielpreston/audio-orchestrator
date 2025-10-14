# Mobile Voice Assistant – Cross‑Platform Integration Spec (React Native + LiveKit + Wake Word)

**Audience:** Product & Engineering  
**Scope:** Cross‑platform mobile integration that reuses the existing Discord-first audio pipeline and canonical audio contract.  
**Surfaces Covered:** React Native mobile app (iOS/Android), WebRTC transport (LiveKit), server‑side session/agent, STT/TTS services, wake/VAD, metrics, auth, storage, and policy.

---

## 1) Goals & Non‑Goals

### Goals

* Ship a **real‑time, full‑duplex voice** interface on mobile without fully native apps.
* Reuse the **canonical audio contract** and existing backend (STT/TTS/orchestrator).
* Support **push‑to‑talk**, **wake‑word gated** sessions, and **barge‑in** (pause/resume TTS on speech).
* Provide clear **interfaces and contracts** for each touch point so modules are swappable.
* Define **latency, quality, and reliability** acceptance criteria with measurable telemetry.

### Non‑Goals

* Implement custom DSP/AEC; rely on OS voice‑communication modes and WebRTC APM.
* Provide always‑listening in the background on iOS. (Conform to platform constraints; use wake windows or PTT.)
* Lock into any single STT/TTS vendor.

---

## 2) System Overview (High Level)

**Mobile RN App** ⇄ **LiveKit Room (WebRTC/Opus)** ⇄ **Edge/Agent Service** ⇄ **STT Stream** ⇄ **Orchestrator/LLM** ⇄ **TTS Stream** → **Downlink Audio**

**Control Plane:** Device VAD/wake, barge‑in signals, user intents, UI state → **LiveKit Data Channel** → Agent → policies & playback control.

---

## 3) Components & Responsibilities

### 3.1 React Native Mobile App (Client)

* **Audio Capture & Playback:** `react-native-webrtc` media tracks.
* **Audio Session Control (native bridge):** Toggle VOICE_COMMUNICATION/VoiceChat mode, AEC/NS/AGC, route changes (speaker/earpiece/BT), interruptions.
* **Wake/VAD:** On‑device VAD; optional wake‑word (Porcupine/open‑wakeword).
* **Session Control:** Establish/tear down LiveKit connection; publish mic track; subscribe to TTS track; send/receive control messages over Data Channel.
* **UX State:** Push‑to‑talk, wake‑armed indicators, live/recording badges, mute, audio route selection.
* **Telemetry:** Local capture start/stop timestamps, device model, battery/temp, packet loss/jitter from WebRTC stats.

### 3.2 LiveKit (Transport Layer)

* **Media Plane:** SRTP/WebRTC with Opus; jitter buffer; network resilience.
* **Rooms/Participants:** Mobile device is a participant; server "Agent" is another.
* **Data Channel:** Low‑latency control messages (barge‑in, pause/resume, endpointing, UI hints).
* **Auth:** Token‑based room access scoped per user/session.

### 3.3 Agent/Edge Service (Server)

* **Ingress:** Subscribe to uplink audio; decode Opus → canonical PCM.
* **STT Bridge:** Stream PCM frames to STT provider; emit partials/finals with timestamps.
* **Policy Engine:** Endpointing, barge‑in decisions, input gate (PTT/wake windows), turn‑taking.
* **LLM Orchestrator Hook:** Forward STT transcripts + context; receive incremental reply tokens.
* **TTS Bridge:** Stream reply text to TTS; emit audio chunks to downlink track.
* **Control Plane:** Handle client control messages; send back playback, prompts, errors, and state.
* **QoS/Telemetry:** Collect room stats, E2E latency, packet loss, reconnection metrics.

### 3.4 STT/TTS Providers

* **STT:** Streaming API; returns partials, finals, and word‑timecodes.
* **TTS:** Streaming API; returns audio chunks suitable for low‑latency playback; supports pause/resume.
* **Abstraction:** Providers are interchangeable behind a stable adapter interface.

### 3.5 Wake Word & VAD

* **Local VAD:** Gating network usage and assisting endpointing.
* **Wake Word:** Local keyword spotter; opens a session window and arms barge‑in logic.
* **Confidence & Debounce:** Tunable thresholds; cool‑down to reduce false positives.

---

## 4) Interfaces & Canonical Contracts

### 4.1 Canonical Audio Contract

* **Format:** PCM 16‑bit, mono.
* **Nominal Rate:** 16 kHz (STT‑oriented); convert at edges as needed (e.g., Opus @ 48 kHz on wire).
* **Frame Size:** 20 ms target (320 samples @ 16 kHz).
* **Resampling:** Exactly once per edge; avoid chained resamples.
* **Markers:** Segment/word timestamps; endpointing events; barge‑in events.

### 4.2 Control Plane: Data Channel Message Shapes

*(Representative, code‑free schemas)*

* **Client → Agent**

  * `wake.detected`: `{ ts_device, confidence }`
  * `vad.start_speech`: `{ ts_device }`
  * `vad.end_speech`: `{ ts_device, duration_ms }`
  * `barge_in.request`: `{ reason: "user_speaking" | "button", ts_device }`
  * `session.state`: `{ action: "join" | "leave" | "mute" | "unmute" }`
  * `route.change`: `{ output: "speaker" | "earpiece" | "bt", input: "built_in" | "bt" }`

* **Agent → Client**

  * `playback.control`: `{ action: "pause" | "resume" | "stop", reason }`
  * `endpointing`: `{ state: "listening" | "processing" | "responding" }`
  * `transcript.partial`: `{ text, ts_server, confidence }`
  * `transcript.final`: `{ text, ts_server, words: [{w, start, end}] }`
  * `error`: `{ code, message, recoverable: bool }`
  * `telemetry.snapshot`: `{ rtt_ms, pl_percent, jitter_ms }`

### 4.3 STT Adapter Contract

* **Input:** PCM frames + timestamps.
* **Output:** Streaming partials and finals with token/word timecodes.
* **Controls:** Start/stop stream; flush on endpoint; max interim silence.

### 4.4 TTS Adapter Contract

* **Input:** Token/phrase stream (text chunks).
* **Output:** Audio chunks suitable for near‑real‑time playback; metadata for markers.
* **Controls:** Pause/resume/stop; voice/style selection; max prefetch.

---

## 5) Session Lifecycle & State Machines

### 5.1 Client Session Lifecycle

1. **Idle** → app foreground, wake armed or PTT ready.
2. **Arming** → wake detected or PTT pressed; create/join room; publish mic track.
3. **Live Listen** → VAD gated uplink; send control messages; show recording indicator.
4. **Processing** → client quiet; STT finalizing; orchestrator reasoning; awaiting TTS.
5. **Responding** → downlink TTS track playing; barge‑in allowed.
6. **Teardown** → stop tracks; leave room; return to Idle (or keep warm if allowed).

### 5.2 Barge‑In Policy

* **Trigger:** `vad.start_speech` or `barge_in.request`
* **Action:** Agent issues `playback.control { action: "pause" }`; TTS provider paused; enqueue resume at speech end.
* **Timeouts:** Max pause duration; if exceeded, soft‑stop response and prioritize new turn.

---

## 6) Latency, Quality, and Reliability Targets

* **Round‑trip (mic → first TTS audio):** ≤ **400 ms** median; ≤ 650 ms p95.
* **Barge‑in pause delay:** ≤ **250 ms** from VAD start to downstream pause.
* **Packet loss tolerance:** Smooth at ≤ **10%** with PLC; jitter stable ≤ 80 ms.
* **Uptime:** 99.9% monthly for signaling/media services.
* **Audio MOS/perceptual tests:** Pass in quiet, café, car, and wind scenarios.

---

## 7) Background, Power, and Policy

* **iOS:** Background audio allowed during active session only; no perpetual always‑listening. Prefer PTT or short wake windows.
* **Android:** Foreground service with persistent notification during active session.
* **Battery Budget:** 30‑minute session must avoid thermal throttling on mid‑tier devices; use VAD gating; Opus on the wire.

---

## 8) Authentication & Identity

* **Client Auth:** App obtains short‑lived JWT/room token via API; tokens scoped to user/session.
* **Transport Auth:** LiveKit token for room join; rotated per session.
* **Service Auth:** STT/TTS keys kept server‑side only.
* **PII/Privacy:** Explicit mic consent, visible indicators when live, configurable retention for transcripts and audio.

---

## 9) Telemetry, Observability, and Health

### Metrics (emit from client, transport, agent)

* **Client:** capture start/stop, device model/OS, audio route, wake confidence, VAD durations, local buffer underruns, battery/thermal state.
* **Transport:** RTT, packet loss %, jitter, bitrate, reconnects, ICE state changes.
* **Agent:** E2E latency breakdown (capture→STT first partial; partial→final; final→TTS first byte), barge‑in count, pause/resume timings, errors by code.

### Logs/Tracing

* **Correlation IDs:** Per session, propagate across client → agent → STT/TTS.
* **Sampling:** Adjustable; full traces for failures and p95+ outliers.

---

## 10) Error Handling & Recovery

* **Signaling failure:** Retry with backoff; present user action (retry/cancel).
* **Media failure:** ICE restart; renegotiate tracks; fall back to PTT if needed.
* **BT route changes:** Graceful re‑init of audio session; notify UI; preserve room.
* **STT/TTS outages:** Switch to alternate provider if configured; OS TTS fallback for responses.
* **Wake false positives:** Confidence threshold + debounce window; cooldown after repeated misfires.

---

## 11) Configuration & Feature Flags

* **Audio:** sample rate, frame size, AGC/NS/AEC toggles, preferred route.
* **Wake/VAD:** detector type, thresholds, cooldowns, language model.
* **Transport:** TURN/STUN pool, bitrate caps, preferred codecs.
* **Policies:** barge‑in enable, pause caps, endpointing timeouts.
* **Providers:** primary/secondary STT/TTS with weights and failover order.

---

## 12) Security & Compliance Considerations

* **Data at Rest:** Encrypt transcripts; configurable retention; redact sensitive entities on device if recording.
* **Data in Transit:** SRTP for media; TLS for signaling/APIs; signed control messages.
* **Access:** Principle of least privilege for tokens and service accounts.

---

## 13) Acceptance Tests (Go/No‑Go)

1. **Latency:** Median ≤ 400 ms mic→first‑audio; p95 ≤ 650 ms.
2. **Barge‑In:** Pause ≤ 250 ms after speech onset in 95% of trials.
3. **Route Handling:** Clean transitions among speaker/earpiece/BT mid‑session without teardown.
4. **Recovery:** Successful ICE restart after toggling airplane mode; session resumes within 2 s.
5. **Battery/Thermal:** 30‑minute continuous session on mid‑tier device without thermal throttling.
6. **Privacy:** Visible live indicators; microphone permission prompts; retention settings honored.

---

## 14) Deliverables & Artifacts (for Repo)

* **`/docs/mobile-integration-spec.md`** (this document).
* **Interface stubs:** Provider‑agnostic STT/TTS adapter signatures and Data Channel message enums (code‑free outlines).
* **QA Protocol:** Latency/barge‑in/battery test scripts (procedural, not code).
* **Config Samples:** YAML/JSON examples for audio, transport, wake, providers (values illustrative only).

---

## 15) Open Questions (Track, Not Blockers)

* Minimum viable background behavior on iOS beyond active session windows.
* Preferred secondary STT/TTS providers and automatic failover rules.
* On‑device caching of short TTS phrases (earcons/prompts) vs. streaming-only.

---

## Implementation Status

### ✅ Completed
- [x] Canonical audio contracts and interfaces
- [x] LiveKit agent service for WebRTC transport
- [x] React Native mobile app with WebRTC integration
- [x] STT/TTS adapter interfaces for provider abstraction
- [x] Session management and state machines
- [x] Control plane messaging system
- [x] Telemetry and observability features
- [x] Comprehensive documentation

### 🔄 In Progress
- [ ] Integration testing and validation
- [ ] Performance optimization
- [ ] Error handling refinement

### 📋 Pending
- [ ] Production deployment configuration
- [ ] Monitoring and alerting setup
- [ ] User acceptance testing