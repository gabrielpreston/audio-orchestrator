---
title: TTS Service Evaluation
author: Discord Voice Lab Team
status: published
last-updated: 2024-07-05
---

> Docs ▸ Reports ▸ TTS Service Evaluation

# Text-to-Speech Service Review

## Overview

The current text-to-speech (TTS) microservice is implemented with FastAPI and a
Piper-backed neural synthesis engine. It exposes `/voices`, `/synthesize`,
`/metrics`, and `/health` endpoints and streams synthesized WAV audio directly
to callers.

## Status update — Piper integration

The previous iteration relied on `pyttsx3` and local filesystem retention. The
service now loads Piper models once on startup, caps concurrency, enforces
bearer authentication and rate limits, and streams synthesized audio without
writing it to disk. Prometheus metrics track latency and payload sizes for the
streaming pipeline.

## Alignment with Industry Best Practices

### API design and observability

- ✅ Uses standard JSON request/response bodies and descriptive HTTP status codes.
- ✅ Emits structured logs through the shared logging helpers, enabling aggregation
  across services.
- ✅ Adds `/health` and `/metrics` endpoints so orchestrators and monitoring
  agents can observe Piper readiness and latency/size distributions.
- ✅ Streams synthesized responses to minimize playback latency for short
  utterances while keeping the audio ephemeral.
- ✅ Enforces bearer authentication and per-minute rate limits to prevent abuse in
  shared environments.

### Audio generation pipeline

- ✅ Migrated to Piper for neural-quality synthesis with multi-speaker support.
- ✅ Keeps a warm synthesizer in memory and gates concurrency through a global
  semaphore to avoid repeated initialization and CPU contention.
- ✅ Accepts SSML payloads with adjustable length/noise parameters to control
  prosody.
- ✅ Streams generated audio directly to callers without persisting it on disk.

### Scalability and resilience

- ✅ Streams responses on demand to avoid persisting synthesized audio on disk.
- ✅ Caps concurrency and exposes Prometheus metrics so operators can size the
  service and drive autoscaling.
- ⚠️ Consider adding request tracing headers and queue depth metrics if the
  synthesizer later backs a multi-tenant deployment.

## Python Libraries and Services to Consider

| Category | Option | Notes |
| --- | --- | --- |
| Local neural TTS | [Coqui TTS](https://github.com/coqui-ai/TTS) | Open-source, supports multilingual neural voices, GPU acceleration, and speaker cloning. |
|  | [Mozilla TTS (Mycroft fork)](https://github.com/mozilla/TTS) | Mature Tacotron/Glow-based stack with SSML support and vocoder selection. |
|  | [Piper](https://github.com/rhasspy/piper) | Lightweight C++/Python interface with fast inference on CPU and Raspberry Pi-class hardware. |
| Cloud-hosted APIs | [Azure Cognitive Services Speech SDK](https://learn.microsoft.com/azure/ai-services/speech-service/) | Enterprise-grade neural voices, SSML, streaming, speech styles, and robust Python SDK. |
|  | [Google Cloud Text-to-Speech](https://cloud.google.com/text-to-speech/docs/reference/libraries) | 220+ voices, fine-grained prosody control, supports long-form audio via asynchronous APIs. |
|  | [Amazon Polly](https://aws.amazon.com/polly/) | Neural voices with lexicon support, S3 integration, and event notifications. |
| Hybrid / hosted SaaS | [ElevenLabs Python SDK](https://github.com/elevenlabs/elevenlabs-python) | High-quality voices, voice cloning, streaming WebSocket API, pay-per-use pricing. |
|  | [PlayHT Python client](https://docs.play.ht/docs/python-sdk) | Realistic voices, multilingual, fine-tuning, streaming endpoints. |

## Recommendations

1. ✅ Replace `pyttsx3` with a neural TTS engine (Piper) for higher fidelity,
   richer voice options, and improved multi-language support.
2. ✅ Maintain a reusable synthesizer instance and concurrency guard to avoid
   repeated initialization overhead.
3. ✅ Add authentication middleware and configurable rate limiting to secure the
   service in shared deployments.
4. ✅ Extend the API to support streaming (`audio/wav` chunked responses) and SSML
   payloads for richer prosody control.
5. ✅ Stream synthesized audio with Prometheus telemetry covering latency and
   payload size so downstream services can play responses reliably.
