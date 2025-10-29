# Base Image Architecture

This document outlines the base image strategy for the Audio Orchestrator project, designed to optimize build performance and reduce image sizes.

## Overview

The project uses a tiered base image architecture where services inherit from specialized base images containing only the dependencies they need. This approach provides:

-  **Faster builds**: Services only install what they need
-  **Smaller images**: Reduced layer sizes and fewer dependencies
-  **Better caching**: Base images change less frequently than service code
-  **Consistent versions**: All services use the same core library versions

## Base Image Hierarchy

```text
python-base (foundation)
├── python-web (web services)
├── python-audio (legacy, being phased out)
└── python-ml (ML services)
    ├── python-ml-audio (specialized)
    ├── python-ml-torch (specialized)
    └── python-ml-transformers (specialized)

tools (development/CI)
```

## Base Images

### `python-base`

Foundation image for all services

-  Python 3.11-slim
-  Core system dependencies (build-essential, curl, git, ca-certificates)
-  Base requirements (fastapi, uvicorn, pydantic, httpx, structlog, OpenTelemetry)

### `python-web`

Lightweight base for web services

**Used by:** Discord, Testing, Monitoring, Security

**Includes:**

-  All `python-base` dependencies
-  Audio system libraries (FFmpeg, libopus, libsndfile, espeak-ng, libasound2)
-  No ML libraries (PyTorch, transformers, etc.)

**Pre-installed Python packages:**

-  **Core Web Framework:** fastapi==0.118.0, uvicorn[standard]==0.37.0, pydantic==2.12.0
-  **HTTP & Logging:** httpx==0.26.0, structlog==24.1.0
-  **Observability:** opentelemetry-api==1.24.0, opentelemetry-sdk==1.24.0, opentelemetry-exporter-otlp-proto-http==1.24.0, opentelemetry-instrumentation-fastapi==0.45b0, opentelemetry-instrumentation-httpx==0.45b0, opentelemetry-instrumentation-requests==0.45b0

**Benefits:**

-  Fast startup for web-only services
-  Small image size (~200MB vs ~2GB for ML base)
-  Quick builds for non-AI services

### `python-ml`

Full ML stack for AI services

**Used by:** STT, Orchestrator, FLAN, Bark, Guardrails, Audio

**Includes:**

-  All `python-base` dependencies
-  PyTorch stack (torch, torchvision, torchaudio)
-  ML libraries (transformers, accelerate, safetensors, faster-whisper, speechbrain)
-  Audio processing (librosa, soundfile, scipy, numpy, bark)
-  OpenTelemetry and gRPC packages

**Pre-installed Python packages:**

-  **PyTorch Stack:** torch>=2.0,<3.0, torchvision>=0.15,<1.0, torchaudio>=2.0,<3.0
-  **ML Libraries:** transformers>=4.57,<5.0, accelerate>=0.20,<1.0, safetensors>=0.3,<1.0, faster-whisper>=1.2,<2.0, speechbrain>=0.5,<1.0
-  **Audio Processing:** librosa>=0.10,<1.0, soundfile>=0.12,<1.0, scipy>=1.11,<2.0, numpy>=1.24,<2.0, bark>=0.1.5,<1.0
-  **Observability:** opentelemetry-api>=1.24,<2.0, opentelemetry-sdk>=1.24,<2.0,
    opentelemetry-instrumentation-fastapi>=0.45b0,<1.0, opentelemetry-instrumentation-httpx>=0.45b0,<1.0,
    opentelemetry-instrumentation-requests>=0.45b0,<1.0, opentelemetry-exporter-otlp-proto-http>=1.24,<2.0,
    opentelemetry-exporter-jaeger>=1.20,<1.30
-  **gRPC:** grpcio>=1.60,<2.0, grpcio-tools>=1.60,<2.0, protobuf>=4.25,<5.0

**Benefits:**

-  Complete ML/AI toolkit
-  Optimized for model inference
-  Consistent ML library versions

### `python-audio`

Legacy audio-only base (being phased out)

**Used by:** None (replaced by python-web)

**Includes:**

-  Audio system libraries only (FFmpeg, libopus, libsndfile, espeak-ng, etc.)
-  No Python packages - services must install their own Python dependencies

### `tools`

Development and CI tools

**Used by:** Linter, Tester, Security scanner

**Includes:**

-  All development tools (ruff, mypy, pytest, etc.)
-  System tools (hadolint, checkmake, actionlint)
-  Node.js and Go toolchains

## Service Mapping

| Service | Base Image | Reason |
|---------|------------|--------|
| Discord | python-web | Web service with audio system libs |
| Testing | python-web | Web UI (Gradio) with audio system libs |
| Monitoring | python-web | Web dashboard (Streamlit) |
| Security | python-web | Security scanning tools |
| STT | python-ml | ML inference (faster-whisper) |
| Orchestrator | python-ml | LangChain + ML coordination |
| FLAN | python-ml | Language model inference |
| Bark | python-ml | TTS model inference |
| Guardrails | python-ml | ML-based content filtering |
| Audio | python-ml | Audio processing with ML libraries |

## Service Requirements Guidelines

### Services using `python-web` base

**DO NOT include:**

-  fastapi, uvicorn, pydantic, httpx, structlog, OpenTelemetry packages

**DO include:**

-  Service-specific dependencies and audio libraries if needed
-  **Example:** Discord includes numpy, PyNaCl, openwakeword, etc. Testing includes gradio.

### Services using `python-ml` base

**DO NOT include:**

-  torch, torchvision, torchaudio, transformers, accelerate, safetensors, faster-whisper, speechbrain, librosa, soundfile, scipy, numpy, bark, OpenTelemetry packages, gRPC packages

**DO include:**

-  Only service-specific dependencies not in base
-  **Example:** STT only needs `python-multipart`, Audio only needs `webrtcvad` and `prometheus-client`

### Services using `python-base` base

**DO include:**

-  All dependencies including ML libraries if needed
-  **Example:** Security service includes only `pip-audit`

## Build Optimization

### Wheel Caching

Native dependencies are pre-built as wheels to speed up builds:

```bash
# Build wheels for native dependencies
make docker-build-wheels

# Services automatically use cached wheels
make docker-build-service SERVICE=discord
```

### Layer Caching

Base images are built with optimal layer ordering:

1.  **System dependencies** (changes rarely)
2.  **Python packages** (changes occasionally)
3.  **Application code** (changes frequently)

### Multi-stage Builds

ML services use multi-stage builds to minimize runtime image size:

```dockerfile
FROM python-ml:latest AS builder
# Install dependencies and build

FROM python-ml:latest
# Copy only runtime artifacts
```

## Performance Metrics

| Metric | python-web | python-ml |
|--------|------------|-----------|
| Base image size | ~200MB | ~2GB |
| Build time (cold) | 2-3 min | 8-12 min |
| Build time (cached) | 30-60s | 2-3 min |
| Memory usage | ~50MB | ~200MB |

## Migration Guide

### Adding New Services

1.  **Determine service type:**
    -  Web service → use `python-web`
    -  ML/AI service → use `python-ml`
    -  Development tool → use `tools`

2.  **Create service requirements:**

   ```bash
   # For web services
   echo "-r ../requirements-base.txt" > services/new-service/requirements.txt
   echo "# Add only service-specific dependencies" >> services/new-service/requirements.txt

   # For ML services
   echo "-r ../requirements-base.txt" > services/new-service/requirements.txt
   echo "# ML libraries already in base, add only service-specific deps" >> services/new-service/requirements.txt
   ```

1.  **Create Dockerfile:**

   ```dockerfile
   FROM ghcr.io/gabrielpreston/python-web:latest  # or python-ml
   COPY services/new-service/requirements.txt /app/
   COPY constraints.txt /app/
   RUN pip install -r /app/requirements.txt -c /app/constraints.txt
   ```

### Updating Base Images

1.  **Modify base Dockerfile** in `services/base/`
2.  **Update constraints.txt** if adding new packages
3.  **Rebuild base images:** `make docker-build-base`
4.  **Test services:** `make docker-build-service SERVICE=<name>`

## Troubleshooting

### Common Issues

**Service fails to start:**

-  Check if base image includes required dependencies
-  Verify service requirements don't duplicate base packages

**Build takes too long:**

-  Ensure wheel caching is enabled
-  Check if service is using correct base image
-  Verify constraints.txt is being used

**Image too large:**

-  Review service requirements for unnecessary packages
-  Consider if service should use lighter base image
-  Check for duplicate dependencies

### Debugging Commands

```bash
# Check base image contents
docker run --rm ghcr.io/gabrielpreston/python-web:latest pip list

# Compare image sizes
docker images | grep python-

# Build with verbose output
DOCKER_BUILDKIT=1 docker build --progress=plain -f services/discord/Dockerfile .
```

## Optimization Benefits

-  **Faster builds:** No redundant package installations
-  **Smaller images:** Avoid duplicate dependencies
-  **Consistent versions:** All services use same ML library versions
-  **Better caching:** Base image changes less frequently than service code

## Migration Notes

-  **Audio service:** Removed numpy/scipy from requirements, removed OpenBLAS rebuild from Dockerfile
-  **STT service:** Already correctly excludes faster-whisper (in base)
-  **All other ML services:** Already correctly structured

## Future Improvements

-  **python-web-light**: Even smaller base for simple services
-  **python-ml-cpu**: CPU-only ML base for smaller deployments
-  **python-ml-gpu**: GPU-optimized ML base for production
-  **Multi-arch builds**: ARM64 support for Apple Silicon
-  **Distroless images**: Security-hardened minimal images
