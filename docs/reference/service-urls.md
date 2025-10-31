---
title: Service URLs Reference
author: Audio Orchestrator Team
status: active
last-updated: 2025-01-27
---

<!-- markdownlint-disable-next-line MD041 -->
> Docs ▸ Reference ▸ Service URLs Reference

# Service URLs Reference

Complete list of all service URLs accessible from your browser when running the Docker Compose stack locally.

## Core Services

| Service | URL | Description | Health Check |
|---------|-----|-------------|--------------|
| **Audio Processor** | [http://localhost:8010](http://localhost:8010) | Unified audio processing service (VAD, enhancement, quality metrics) | [http://localhost:8010/health/ready](http://localhost:8010/health/ready) |
| **STT (Speech-to-Text)** | [http://localhost:8011](http://localhost:8011) | Speech transcription service using faster-whisper | [http://localhost:8011/health/ready](http://localhost:8011/health/ready) |
| **Orchestrator** | [http://localhost:8220](http://localhost:8220) | Main orchestration service coordinating LangChain tool calls | [http://localhost:8220/health/ready](http://localhost:8220/health/ready) |
| **FLAN-T5 (LLM)** | [http://localhost:8110](http://localhost:8110) | Language model service providing OpenAI-compatible API | [http://localhost:8110/health/ready](http://localhost:8110/health/ready) |
| **Bark (TTS)** | [http://localhost:7120](http://localhost:7120) | Text-to-speech service streaming Bark-generated audio | [http://localhost:7120/health/ready](http://localhost:7120/health/ready) |
| **Guardrails** | [http://localhost:9310](http://localhost:9310) | Content moderation service (toxicity detection, PII detection) | [http://localhost:9310/health/ready](http://localhost:9310/health/ready) |
| **Discord Bot** | [http://localhost:8009](http://localhost:8009) | Discord bot HTTP API for voice and message handling | [http://localhost:8009/health/ready](http://localhost:8009/health/ready) |

## UI Services

| Service | URL | Description |
|---------|-----|-------------|
| **Testing UI (Gradio)** | [http://localhost:8080](http://localhost:8080) | Interactive testing interface for the audio pipeline |
| **Monitoring Dashboard (Streamlit)** | [http://localhost:8501](http://localhost:8501) | Real-time monitoring dashboard for service health and metrics |

## Observability Stack

| Service | URL | Description | Credentials |
|---------|-----|-------------|-------------|
| **Prometheus** | [http://localhost:9090](http://localhost:9090) | Metrics and monitoring database | No authentication required |
| **Grafana** | [http://localhost:3000](http://localhost:3000) | Visualization dashboards and analytics | Username: `admin`, Password: `admin` |
| **Jaeger UI** | [http://localhost:16686](http://localhost:16686) | Distributed tracing UI for request flow analysis | No authentication required |
| **OTEL Collector Health** | [http://localhost:13133](http://localhost:13133) | OpenTelemetry collector health check endpoint | No authentication required |

## Health Check Endpoints

All services expose standardized health check endpoints:

-  **Liveness**: `http://localhost:<PORT>/health/live` — Always returns 200 if process is alive
-  **Readiness**: `http://localhost:<PORT>/health/ready` — Returns service readiness status

### Example Health Checks

```bash
# Check Audio Processor readiness
curl http://localhost:8010/health/ready

# Check Orchestrator readiness
curl http://localhost:8220/health/ready

# Check STT readiness
curl http://localhost:8011/health/ready
```

## API Documentation

All FastAPI services expose interactive API documentation:

### Swagger UI (Interactive)

-  Audio Processor: [http://localhost:8010/docs](http://localhost:8010/docs)
-  STT Service: [http://localhost:8011/docs](http://localhost:8011/docs)
-  Orchestrator: [http://localhost:8220/docs](http://localhost:8220/docs)
-  FLAN-T5: [http://localhost:8110/docs](http://localhost:8110/docs)
-  Bark TTS: [http://localhost:7120/docs](http://localhost:7120/docs)
-  Guardrails: [http://localhost:9310/docs](http://localhost:9310/docs)
-  Discord Bot: [http://localhost:8009/docs](http://localhost:8009/docs)

### ReDoc (Alternative Documentation)

Replace `/docs` with `/redoc` in any of the above URLs (e.g., [http://localhost:8220/redoc](http://localhost:8220/redoc)).

### OpenAPI Schema

Replace `/docs` with `/openapi.json` to get the raw OpenAPI schema (e.g., [http://localhost:8220/openapi.json](http://localhost:8220/openapi.json)).

## Quick Access Reference

### Most Frequently Used

1.  **Testing UI**: [http://localhost:8080](http://localhost:8080) — Primary interface for testing the audio pipeline
2.  **Orchestrator API Docs**: [http://localhost:8220/docs](http://localhost:8220/docs) — Main orchestration service API
3.  **Monitoring Dashboard**: [http://localhost:8501](http://localhost:8501) — Real-time service monitoring
4.  **Grafana**: [http://localhost:3000](http://localhost:3000) — Metrics visualization (login: `admin`/`admin`)
5.  **Jaeger**: [http://localhost:16686](http://localhost:16686) — Distributed tracing visualization

### Port Mapping Reference

| External Port | Internal Port | Service |
|---------------|---------------|---------|
| 8010 | 9100 | Audio Processor |
| 8011 | 9000 | STT |
| 8220 | 8200 | Orchestrator |
| 8110 | 8100 | FLAN-T5 LLM |
| 7120 | 7100 | Bark TTS |
| 9310 | 9300 | Guardrails |
| 8009 | 8001 | Discord Bot |
| 8080 | 8080 | Testing UI (Gradio) |
| 8501 | 8501 | Monitoring Dashboard (Streamlit) |
| 9090 | 9090 | Prometheus |
| 3000 | 3000 | Grafana |
| 16686 | 16686 | Jaeger UI |

> **Note**: External ports are what you use in your browser (`localhost:<external>`). Internal ports are used for service-to-service communication within the Docker network.

## Internal Service URLs

For service-to-service communication within the Docker network, use the internal service names and ports:

| Service | Internal URL |
|---------|--------------|
| Audio Processor | `http://audio:9100` |
| STT | `http://stt:9000` |
| Orchestrator | `http://orchestrator:8200` |
| FLAN-T5 | `http://flan:8100` |
| Bark TTS | `http://bark:7100` |
| Guardrails | `http://guardrails:9300` |
| Discord Bot | `http://discord:8001` |

These URLs are configured via environment variables (see [Configuration Catalog](configuration-catalog.md)) and are used by services to communicate with each other.

## Related Documentation

-  [Configuration Catalog](configuration-catalog.md) — Environment variables and service configuration
-  [Local Development Workflows](../getting-started/local-development.md) — How to run services locally
-  [REST API Documentation](../api/rest-api.md) — API endpoint specifications
-  [Health Check Standards](../operations/health-check-standards.md) — Health endpoint implementation details
