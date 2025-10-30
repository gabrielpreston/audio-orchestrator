---
title: Build Optimization Guide
author: Audio Orchestrator Team
status: active
last-updated: 2025-10-29
---

# Build Optimization Guide

This guide covers the build optimization strategies implemented in the Audio Orchestrator project to achieve faster, more reliable builds.

## Overview

The project implements a multi-layered optimization strategy:

1.  **Base Image Strategy**: Specialized base images for different service types
2.  **Wheel Caching**: Pre-built wheels for native dependencies
3.  **Constraints-based Dependencies**: Reproducible builds with pinned versions
4.  **Layer Caching**: Optimal Docker layer ordering for maximum cache hits
5.  **Parallel Builds**: Multi-service builds in CI/CD

## Base Image Strategy

### Service Classification

Services are classified by their dependency needs:

-  **Web Services** (Discord, Testing, Monitoring, Security)
  -  Use `python-web` base
  -  FastAPI, OpenTelemetry, audio system libs
  -  No ML libraries (PyTorch, transformers, etc.)

-  **ML Services** (STT, Orchestrator, FLAN, Bark, Guardrails, Audio)
  -  Use `python-ml` base
  -  Full ML stack (PyTorch, transformers, faster-whisper, etc.)
  -  Optimized for AI/ML workloads

### Performance Impact

| Service Type | Base Image | Size | Build Time | Memory |
|--------------|------------|------|------------|--------|
| Web | python-web | ~200MB | 2-3 min | ~50MB |
| ML | python-ml | ~2GB | 8-12 min | ~200MB |

## Wheel Caching

### Pre-built Wheels

Native dependencies are pre-built as wheels to avoid compilation during service builds:

```bash
# Build wheels for common native dependencies
make docker-build-wheels

# Wheels are cached and reused across builds
```

**Supported packages:**

-  numpy, scipy (OpenBLAS optimized)
-  webrtcvad (audio processing)
-  PyNaCl (cryptography)
-  openwakeword (wake phrase detection)
-  rapidfuzz (fuzzy matching)

### Wheel Cache Usage

Services automatically use cached wheels when available:

```dockerfile
RUN --mount=type=cache,target=/tmp/wheels \
    pip install --find-links=/tmp/wheels -r requirements.txt
```

## Constraints-based Dependencies

### Global Constraints

All services use pinned versions in their individual `requirements.txt` files for reproducible builds:

```bash
# Install with pinned versions for deterministic builds
pip install -r requirements.txt
```

**Benefits:**

-  Consistent versions across all services
-  Faster resolver (no version negotiation)
-  Reproducible builds across environments
-  Reduced dependency conflicts

### Service Requirements

Services only declare what they need, not exact versions:

```python
# services/discord/requirements.txt
-r ../requirements-base.txt  # Inherit base dependencies

# Service-specific dependencies only
discord.py[voice]>=2.4,<3.0
numpy>=1.26,<2.0
PyNaCl>=1.5,<2.0
```

## Layer Caching Optimization

### Optimal Layer Order

Dockerfiles are structured for maximum cache efficiency:

```dockerfile
# 1. System dependencies (changes rarely)
RUN apt-get update && apt-get install -y ...

# 2. Python packages (changes occasionally)
COPY requirements.txt /app/
RUN pip install -r requirements.txt

# 3. Application code (changes frequently)
COPY services/discord /app/services/discord
```

### Multi-stage Builds

ML services use multi-stage builds to minimize runtime size:

```dockerfile
FROM python-ml:latest AS builder
# Install and build dependencies

FROM python-ml:latest
# Copy only runtime artifacts
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
```

## Build Commands

### Local Development

```bash
# Smart incremental builds (recommended)
make docker-build

# Enhanced caching builds
make docker-build-enhanced

# Single service builds
make docker-build-service SERVICE=discord

# Base image builds
make docker-build-base

# Wheel building
make docker-build-wheels
```

### CI/CD Integration

The CI pipeline automatically:

1.  **Detects changes** and builds only affected services
2.  **Uses wheel caching** for native dependencies
3.  **Builds in parallel** for maximum speed
4.  **Caches base images** across workflow runs
5.  **Reports build metrics** for optimization tracking

## Performance Metrics

### Build Time Improvements

| Scenario | Before | After | Improvement |
|----------|--------|-------|-------------|
| Single service change | 8-12 min | 1-2 min | 80-90% |
| Common library change | 8-12 min | 2-3 min | 70-80% |
| Base image change | 12-15 min | 3-5 min | 60-70% |
| No changes | N/A | instant | 100% (cache hit) |

### Cache Hit Rates

-  **Service images**: 70-85% cache hits (up from 20-30%)
-  **Base images**: 90-95% cache hits
-  **Wheel cache**: 95-98% hit rate for native dependencies

## Troubleshooting

### Slow Builds

**Check cache usage:**

```bash
# View build cache
docker system df

# Clear cache if needed
make docker-clean
```

**Verify base image usage:**

```bash
# Check service is using correct base
grep "FROM" services/discord/Dockerfile
```

### Build Failures

**Dependency conflicts:**

```bash
# Check constraints alignment
pip check

# Verify service requirements
pip install -r services/discord/requirements.txt --dry-run
```

**Wheel cache issues:**

```bash
# Rebuild wheels
make docker-build-wheels

# Check wheel availability
ls -la wheels/
```

### Large Images

**Check for duplicates:**

```bash
# Analyze image layers
docker history ghcr.io/gabrielpreston/discord:latest

# Check for unnecessary packages
docker run --rm ghcr.io/gabrielpreston/discord:latest pip list
```

## Best Practices

### Service Development

1.  **Use appropriate base image** for service type
2.  **Minimize service requirements** - rely on base image
3.  **Test with constraints** to ensure reproducibility
4.  **Use wheel caching** for native dependencies

### Base Image Updates

1.  **Update requirements.txt** when adding packages
2.  **Rebuild base images** after constraint changes
3.  **Test all services** after base image updates
4.  **Document changes** in base image coverage docs

### CI/CD Optimization

1.  **Monitor build times** and cache hit rates
2.  **Use parallel builds** where possible
3.  **Clean up old cache** entries periodically
4.  **Report metrics** for continuous improvement

## Future Improvements

-  **Distroless images**: Security-hardened minimal runtime
-  **Multi-arch builds**: ARM64 support for Apple Silicon
-  **BuildKit features**: Advanced caching and parallel builds
-  **Registry optimization**: Better layer deduplication
-  **Build analytics**: Detailed performance tracking and optimization suggestions
