<!-- 713884fa-6cc1-4220-b282-91f4a4257eb2 2050ba34-8179-4b5d-a3c2-4b596567f03c -->
# OpenTelemetry Observability Stack Implementation

## Phase 0: Pre-Implementation Analysis

### Critical Corrections Applied

1. **Fixed OTel Collector Prometheus Exporter Configuration** - Corrected exporter format and endpoint configuration
2. **Leveraged Existing Tracing Infrastructure** - Extended `services/common/tracing.py` instead of creating new module
3. **Added Memory Limits** - Specified resource constraints for all new services to maintain 25GB total budget
4. **Preserved Existing Metrics Endpoints** - Keep current `/metrics` endpoints during transition
5. **Corrected Environment Variables** - Removed conflicting `OTEL_SERVICE_NAME` from common config
6. **Added Health Checks** - Included proper health check configuration for OTel Collector
7. **Enhanced Grafana Provisioning** - Added complete provisioning configuration structure

## Phase 1: Infrastructure Setup

### Add Observability Services to Docker Compose

Add to `docker-compose.yml` with memory limits to maintain 25GB total budget:

**OpenTelemetry Collector** (port 4317/4318 for OTLP, 13133 for health)

- Receives telemetry from all services via OTLP
- Processes and routes to Prometheus and Jaeger
- Memory limit: 512M, CPU: 0.5
- Configuration file: `config/otel-collector-config.yaml`

**Prometheus** (port 9090)

- Scrapes metrics from OTel Collector
- Time-series database for metrics storage
- Memory limit: 1G, CPU: 1
- Configuration file: `config/prometheus.yml`

**Jaeger** (ports 16686 UI, 14250 gRPC, 14268 HTTP)

- Distributed tracing backend
- Trace storage and visualization
- Memory limit: 1G, CPU: 1

**Grafana** (port 3000)

- Visualization dashboards
- Pre-configured with Prometheus and Jaeger data sources
- Memory limit: 512M, CPU: 0.5
- Configuration files: `config/grafana/datasources.yml`, `config/grafana/dashboards.yml`

### Create Configuration Files

**`config/otel-collector-config.yaml`** (CORRECTED):

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 10s
    send_batch_size: 1024
  memory_limiter:
    limit_mib: 512
    check_interval: 1s

exporters:
  prometheusexporter:
    endpoint: "0.0.0.0:8889"
    namespace: "audio_orchestrator"
    const_labels:
      environment: "production"
  jaeger:
    endpoint: jaeger:14250
    tls:
      insecure: true
  logging:
    loglevel: info

service:
  pipelines:
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [prometheusexporter, logging]
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [jaeger, logging]
```

**`config/prometheus.yml`**:

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'otel-collector'
    static_configs:
      - targets: ['otel-collector:8889']
    scrape_interval: 15s
    metrics_path: /metrics
```

**`config/grafana/datasources.yml`** (NEW):

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true

  - name: Jaeger
    type: jaeger
    access: proxy
    url: http://jaeger:16686
    editable: true
```

**`config/grafana/dashboards.yml`** (NEW):

```yaml
apiVersion: 1

providers:
  - name: 'default'
    orgId: 1
    folder: ''
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
```

## Phase 2: Common Observability Module

### Extend `services/common/tracing.py` (REVISED APPROACH)

**CORRECTED**: Extend existing `TracingManager` class instead of creating new module to leverage existing infrastructure:

```python
# Add to services/common/tracing.py

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource

class ObservabilityManager(TracingManager):
    """Enhanced manager that handles both tracing and metrics."""
    
    def __init__(self, service_name: str, service_version: str = "1.0.0"):
        super().__init__(service_name, service_version)
        self._meter: metrics.Meter | None = None
        self._metrics_enabled = False
    
    def setup_observability(self) -> None:
        """Setup both tracing and metrics for the service."""
        # Setup tracing (existing functionality)
        self.setup_tracing()
        
        # Setup metrics (new functionality)
        self._setup_metrics()
    
    def _setup_metrics(self) -> None:
        """Set up OpenTelemetry metrics for the service."""
        if os.getenv("OTEL_ENABLED", "false").lower() != "true":
            logger.info("metrics.disabled", service=self.service_name)
            return
        
        try:
            # Create resource with service information
            resource = Resource.create({
                "service.name": self.service_name,
                "service.version": self.service_version,
                "service.namespace": "audio-orchestrator",
            })
            
            # Setup metrics
            otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "otel-collector:4317")
            metric_reader = PeriodicExportingMetricReader(
                OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True),
                export_interval_millis=15000
            )
            meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
            metrics.set_meter_provider(meter_provider)
            
            # Get meter
            self._meter = metrics.get_meter(self.service_name, self.service_version)
            self._metrics_enabled = True
            
            logger.info("metrics.initialized", service=self.service_name)
            
        except Exception as exc:
            logger.error("metrics.setup_failed", service=self.service_name, error=str(exc))
            self._meter = None
    
    def get_meter(self) -> metrics.Meter | None:
        """Get the configured meter."""
        return self._meter
    
    def create_counter(self, name: str, description: str, **kwargs):
        """Create a counter metric."""
        if not self._meter:
            return None
        return self._meter.create_counter(name, description, **kwargs)
    
    def create_histogram(self, name: str, description: str, **kwargs):
        """Create a histogram metric."""
        if not self._meter:
            return None
        return self._meter.create_histogram(name, description, **kwargs)
    
    def create_gauge(self, name: str, description: str, **kwargs):
        """Create a gauge metric."""
        if not self._meter:
            return None
        return self._meter.create_gauge(name, description, **kwargs)

# Convenience function for backward compatibility
def setup_service_observability(service_name: str, service_version: str = "1.0.0") -> ObservabilityManager:
    """Set up observability for a service and return the manager."""
    manager = ObservabilityManager(service_name, service_version)
    manager.setup_observability()
    manager.instrument_http_clients()
    return manager
```

## Phase 3: Service Instrumentation

### Update All 9 Services (REVISED APPROACH)

**CORRECTED**: Use existing `tracing.py` infrastructure and preserve existing `/metrics` endpoints during transition.

For each service (`guardrails`, `orchestrator-enhanced`, `llm-flan`, `audio-processor`, `discord`, `stt`, `tts-bark`, `testing-ui`, `monitoring-dashboard`):

**1. Update `app.py` startup (REVISED):**

```python
# Replace existing tracing setup with observability setup
from services.common.tracing import setup_service_observability

# Setup observability (extends existing TracingManager)
observability_manager = setup_service_observability("service-name", "1.0.0")

# Instrument FastAPI (existing functionality)
observability_manager.instrument_fastapi(app)

# Get meter for service-specific metrics
meter = observability_manager.get_meter()
```

**2. Add service-specific metrics (REVISED):**

```python
# Example for STT service using ObservabilityManager
if meter:
    transcription_counter = meter.create_counter(
        "stt_transcriptions_total",
        description="Total transcriptions processed"
    )
    
    transcription_duration = meter.create_histogram(
        "stt_transcription_duration_seconds",
        description="Transcription processing duration"
    )
    
    # Use in code
    transcription_counter.add(1, {"status": "success", "model": "whisper"})
```

**3. Add distributed tracing (REVISED):**

```python
# Use existing tracing infrastructure
tracer = observability_manager.get_tracer()

# Example for audio processing
@tracer.start_as_current_span("process_audio_segment")
async def process_audio_segment(audio_data: bytes):
    with tracer.start_as_current_span("validate_audio"):
        # validation logic
        pass
    
    with tracer.start_as_current_span("transcribe"):
        result = await transcribe(audio_data)
    
    return result
```

**4. PRESERVE existing metrics endpoints (CORRECTED):**

**DO NOT REMOVE** `@app.get("/metrics")` endpoints from services during initial implementation. These are used by:
- `monitoring-dashboard` service
- Existing health monitoring
- Development debugging

**Migration Strategy**: Add OTel metrics alongside existing metrics, then phase out old endpoints in future iteration.

## Phase 4: Environment Configuration

### Update `.env.common` (CORRECTED)

Add OpenTelemetry configuration (removed conflicting `OTEL_SERVICE_NAME`):

```env
# OpenTelemetry Configuration
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=otel-collector:4317
OTEL_EXPORTER_OTLP_PROTOCOL=grpc
OTEL_TRACES_SAMPLER=parentbased_traceratio
OTEL_TRACES_SAMPLER_ARG=1.0
```

**Note**: Service names are set in code via `ObservabilityManager` constructor, not environment variables.

### Update Service Dependencies

Add to each service's `depends_on` in `docker-compose.yml`:

```yaml
depends_on:
  otel-collector:
    condition: service_healthy
```

### Add OTel Collector Health Check

Add to `docker-compose.yml` for `otel-collector` service:

```yaml
otel-collector:
  healthcheck:
    test: ["CMD", "wget", "--spider", "-q", "http://localhost:13133/"]
    interval: 10s
    timeout: 5s
    retries: 3
    start_period: 10s
```

## Phase 5: Audio-Specific Metrics

### Create `services/common/audio_metrics.py` (REVISED)

Standardized audio pipeline metrics using `ObservabilityManager`:

```python
from services.common.tracing import ObservabilityManager
from typing import Dict, Any, Optional

def create_audio_metrics(observability_manager: ObservabilityManager) -> Dict[str, Any]:
    """Create audio-specific metrics for services."""
    meter = observability_manager.get_meter()
    if not meter:
        return {}
    
    return {
        "audio_processing_duration": meter.create_histogram(
            "audio_processing_duration_seconds",
            description="Audio processing duration",
            unit="s"
        ),
        "audio_quality_score": meter.create_histogram(
            "audio_quality_score",
            description="Audio quality score (0-1)",
            unit="1"
        ),
        "audio_chunks_processed": meter.create_counter(
            "audio_chunks_processed_total",
            description="Total audio chunks processed"
        ),
        "wake_detection_duration": meter.create_histogram(
            "wake_detection_duration_seconds",
            description="Wake phrase detection duration"
        ),
        "end_to_end_latency": meter.create_histogram(
            "end_to_end_response_duration_seconds",
            description="Voice input to response latency"
        )
    }

# Special handling for Discord service (migrate existing Prometheus metrics)
def migrate_discord_metrics(observability_manager: ObservabilityManager) -> Dict[str, Any]:
    """Migrate existing Prometheus metrics in Discord service to OpenTelemetry."""
    meter = observability_manager.get_meter()
    if not meter:
        return {}
    
    return {
        "stt_requests": meter.create_counter(
            "stt_requests_total",
            description="Total STT requests (migrated from Prometheus)"
        ),
        "stt_latency": meter.create_histogram(
            "stt_latency_seconds",
            description="STT processing latency (migrated from Prometheus)"
        ),
        "pre_stt_encode": meter.create_histogram(
            "pre_stt_encode_seconds",
            description="Pre-STT encoding duration (migrated from Prometheus)"
        )
    }
```

## Phase 6: Grafana Dashboards

### Create Pre-configured Dashboards (ENHANCED)

**Dashboard Structure**:
```
config/grafana/
├── datasources.yml (already defined in Phase 1)
├── dashboards.yml (already defined in Phase 1)
└── dashboards/
    ├── audio-orchestrator-overview.json
    ├── audio-pipeline.json
    └── service-details.json
```

**`config/grafana/dashboards/audio-orchestrator-overview.json`**:

- Service health overview (from existing health checks)
- Request rates and latencies (from OTel metrics)
- Error rates by service (from OTel metrics)
- Active sessions (from Discord service metrics)
- Memory and CPU utilization (from Docker metrics)

**`config/grafana/dashboards/audio-pipeline.json`**:

- End-to-end audio pipeline latency (distributed traces)
- STT processing times (OTel metrics)
- TTS synthesis times (OTel metrics)
- Audio quality metrics (OTel metrics)
- Wake detection performance (OTel metrics)
- Cross-service communication (distributed traces)

**`config/grafana/dashboards/service-details.json`**:

- Per-service detailed metrics (OTel metrics)
- Resource utilization (Docker + OTel metrics)
- Dependency health (existing health checks + OTel)
- Error tracking (OTel traces + metrics)
- Custom metrics from existing `/metrics` endpoints (during transition)

## Phase 7: Testing & Validation

### Verify Observability Stack (ENHANCED)

1. **Start services**: `make run`
2. **Check OTel Collector health**: `http://localhost:13133/` (health endpoint)
3. **Verify Prometheus targets**: `http://localhost:9090/targets`
4. **Check Jaeger UI**: `http://localhost:16686`
5. **Access Grafana**: `http://localhost:3000` (admin/admin)
6. **Verify existing metrics still work**: Check `/metrics` endpoints on services
7. **Generate test traffic** and verify traces appear in Jaeger
8. **Verify metrics in Prometheus** and Grafana dashboards
9. **Test monitoring-dashboard compatibility** with existing `/metrics` endpoints

### Update Documentation (CORRECTED)

Update `docs/operations/observability.md` (not `docs/ARCHITECTURE.md`) with observability architecture section covering:

- OpenTelemetry instrumentation approach (evolution from solo development)
- Metrics collection strategy (OTel + existing metrics)
- Distributed tracing setup
- Dashboard access and usage
- Troubleshooting guide
- Migration strategy from existing metrics to OTel metrics

**Note**: The existing `docs/operations/observability.md` emphasizes "solo development" simplicity. This plan represents an evolution to production-ready observability while maintaining backward compatibility.

### To-dos (REVISED)

**Phase 1: Infrastructure Setup**
- [ ] Add OTel Collector, Prometheus, Jaeger, and Grafana to docker-compose.yml with memory limits and health checks
- [ ] Create otel-collector-config.yaml with corrected Prometheus exporter configuration
- [ ] Create prometheus.yml with proper scrape configuration
- [ ] Create Grafana datasources.yml and dashboards.yml provisioning configuration
- [ ] Add OTel Collector health check to docker-compose.yml

**Phase 2: Common Observability Module**
- [ ] Extend services/common/tracing.py with ObservabilityManager class (metrics support)
- [ ] Add setup_service_observability convenience function
- [ ] Create services/common/audio_metrics.py with standardized audio pipeline metrics
- [ ] Add migrate_discord_metrics function for Discord service Prometheus migration

**Phase 3: Service Instrumentation**
- [ ] Instrument guardrails service with OTel (setup, metrics, tracing, preserve existing /metrics)
- [ ] Instrument orchestrator-enhanced service with OTel (setup, metrics, tracing, preserve existing /metrics)
- [ ] Instrument llm-flan service with OTel (setup, metrics, tracing)
- [ ] Instrument audio-processor service with OTel (setup, metrics, tracing, preserve existing /metrics)
- [ ] Instrument discord service with OTel (setup, metrics, tracing, migrate existing Prometheus metrics)
- [ ] Instrument stt service with OTel (setup, metrics, tracing)
- [ ] Instrument tts-bark service with OTel (setup, metrics, tracing, preserve existing /metrics)
- [ ] Instrument testing-ui service with OTel (setup, metrics, tracing)
- [ ] Instrument monitoring-dashboard service with OTel (setup, metrics, tracing)

**Phase 4: Environment Configuration**
- [ ] Update .env.common with OpenTelemetry configuration variables (OTEL_ENABLED, OTLP_ENDPOINT, etc.)
- [ ] Add otel-collector dependency to all service depends_on sections

**Phase 5-6: Audio Metrics & Dashboards**
- [ ] Create Grafana dashboards for overview, audio pipeline, and service details
- [ ] Test dashboard provisioning and data source connectivity

**Phase 7: Testing & Validation**
- [ ] Test observability stack (OTel Collector, Prometheus, Jaeger, Grafana) and verify telemetry flow
- [ ] Verify existing /metrics endpoints still work with monitoring-dashboard
- [ ] Update docs/operations/observability.md with observability architecture and usage guide
- [ ] Document migration strategy from existing metrics to OTel metrics

**Total Estimated Effort**: 3-4 hours (17 todos)
**Memory Budget**: 25GB total (22GB existing + 3GB observability stack)
**Risk Level**: Medium (requires careful attention to existing infrastructure)