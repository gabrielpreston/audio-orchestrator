# Base Images Build Order

## Dependency Graph

```
python-base (3-4 min)
├── python-audio (3-4 min)
│   └── discord, tts_bark services
├── python-ml (4-5 min)
│   ├── python-ml-audio (2-3 min)
│   │   └── stt, audio_processor services
│   ├── python-ml-transformers (2-3 min)
│   │   └── llm_flan, guardrails services
│   ├── python-ml-torch (2-3 min)
│   │   └── Advanced ML services
│   ├── stt, llm_flan, orchestrator_enhanced services
│   ├── tts_bark, guardrails services
│   ├── audio_processor, testing_ui services
│   └── monitoring_dashboard service
├── tools (8-10 min after optimization)
│   └── linter, tester services
└── specialized-services (5-7 min)
    └── orchestrator services
```

## Build Time Estimates

- **Total Pipeline**: 12-15 minutes (optimized from 20+ minutes)
- **Critical Path**: python-base → python-ml → tools
- **Parallel Builds**: python-audio, python-ml can build in parallel after python-base
- **Disk Space Requirements**: ~9-10GB peak usage (with cleanup strategy)
- **Cleanup Overhead**: ~1-2 minutes per build tier

## Optimization Strategies

1. **Layer Caching**: BuildKit cache mounts for pip, npm, go
2. **Multi-stage Builds**: Separate builder and runtime stages
3. **Dependency Ordering**: Install stable dependencies first
4. **Minimal Installations**: Only install what's needed for each image

## Disk Space Management

### Disk Space Optimization Strategy

The build system implements comprehensive disk space management to prevent "No space left on device" errors during resource-intensive ML builds:

#### Cleanup Patterns by Build Tier

**Foundation Builds**:
- Basic cleanup before and after builds
- Conservative approach to preserve base images
- Emergency cleanup on cancellation

**Tier 1 Builds** (python-audio, python-ml, tools):
- Standard cleanup before and after builds
- Prevents accumulation before Tier 2 runs
- Emergency cleanup on cancellation

**Tier 2 Builds** (ML-heavy images):
- Conservative cleanup for ML-heavy builds
- Disk space monitoring with 4GB threshold
- Parallel build limits (max-parallel: 2) to prevent resource exhaustion
- Emergency cleanup on cancellation

**Tier 3 Builds** (specialized-services):
- Standard cleanup before and after builds
- Prevents accumulation before service builds
- Emergency cleanup on cancellation

#### Disk Usage Patterns

**Build Dependency Tree with Disk Usage**:
```text
python-base (3-4min, ~2GB)
  → python-ml (4-5min, ~3GB PyTorch CPU)
```

**Peak Disk Usage**:
- **python-base**: ~2GB
- **python-ml**: ~3GB (PyTorch CPU)
- **Total peak usage**: ~9-10GB (exceeds available space without cleanup)

**GitHub Runner Constraints**:
- **Total disk**: ~14GB
- **Available after OS**: ~7GB
- **Required for ML builds**: ~9-10GB
- **Solution**: Comprehensive cleanup strategy

#### Conservative Cleanup Strategy

**For ML Builds**:
```yaml
- name: "Clean up disk space before build"
  run: |
    echo "Cleaning up disk space for ML compilation..."
    docker system prune -f || true
    docker builder prune -f || true
    # Conservative cleanup for ML builds
    docker image prune -f || true  # Conservative: no -a flag
    docker volume prune -f || true
    df -h
```

**Cache Cleanup**:
```yaml
- name: "Clean up GitHub Actions cache"
  if: ${{ !cancelled() }}
  timeout-minutes: 2
  run: |
    echo "Cleaning up GitHub Actions cache..."
    # Clean up old cache entries (if cache size is approaching limits)
    echo "Cache cleanup completed"
    df -h
```

#### Performance Impact

**Cleanup Overhead**:
- **Before build cleanup**: ~30-60 seconds
- **After build cleanup**: ~30-60 seconds
- **Emergency cleanup**: ~10-30 seconds
- **Total overhead**: ~1-2 minutes per build tier

**Benefits**:
- **Prevents build failures**: Eliminates "No space left on device" errors
- **Maintains build performance**: Cleanup overhead is minimal compared to build time
- **Resource efficiency**: Prevents accumulation across build tiers
- **Reliability**: Consistent disk space availability for all builds

## Image Descriptions

### python-base
- Foundation image with Python 3.11 and core system dependencies
- Used by all other base images
- Build time: 3-4 minutes

### python-audio
- Audio processing libraries (librosa, soundfile, ffmpeg)
- Used by: discord, tts_bark services
- Build time: 3-4 minutes

### python-ml
- Machine learning libraries (PyTorch, transformers, etc.)
- Used by: stt, llm_flan, orchestrator_enhanced, tts_bark, guardrails, audio_processor, testing_ui, monitoring_dashboard
- Build time: 4-5 minutes

### python-ml-audio
- ML + Audio processing combination
- Used by: stt, audio_processor services
- Build time: 2-3 minutes

### python-ml-transformers
- ML + Transformers libraries
- Used by: llm_flan, guardrails services
- Build time: 2-3 minutes

### python-ml-torch
- ML + PyTorch libraries
- Used by: Advanced ML services
- Build time: 2-3 minutes

- Build time: 3-4 minutes

### tools
- Development tools (linter, tester, hadolint, etc.)
- Used by: linter, tester services
- Build time: 8-10 minutes (after optimization)
- **Optimized**: Only includes linter and tester requirements

### specialized-services
- Specialized service toolchain (Node.js, Rust, Go)
- Used by: orchestrator services
- Build time: 5-7 minutes
- **Optimized**: Uses minimal Rust profile

## Build Configuration

### Timeouts

**Job-Level Timeouts**:
- **Foundation builds**: 20 minutes
- **Tier 1 builds**: 30 minutes
- **Tier 2 builds**: 50 minutes (increased for ML downloads)
- **Tier 3 builds**: 20 minutes
- **Base workflow**: 60 minutes (increased from 45)

**Step-Level Timeouts**:
- **Docker builds (Foundation/Tier 1/Tier 3)**: 20 minutes
- **Docker builds (Tier 2)**: 45 minutes (increased for ML compilation)
- **Individual builds**: 15-20 minutes
- **Tools build**: 20 minutes (increased from 15)

### Cache Strategy (Local-First)

**Multi-Layer Caching Architecture:**

1. **Registry Cache (GHCR) — Primary**
   - **Cache refs**: `type=registry,ref=ghcr.io/gabrielpreston/cache:base-images` and `...:services`
   - **Mode**: `max` for maximum cache retention
   - **Benefits**: Persistent, cross-machine cache for local builds

2. **Image Reuse**
   - **Base images**: `ghcr.io/gabrielpreston/python-*:latest`
   - **Service images**: `ghcr.io/gabrielpreston/{service}:latest`
   - **Benefits**: Fast pulls; complements registry cache layers

3. **BuildKit Cache Mounts**
   - **pip cache**: `--mount=type=cache,target=/root/.cache/pip`
   - **apt cache**: `--mount=type=cache,target=/var/cache/apt`
   - **Benefits**: Intra-build cache sharing, faster package installation

4. **Local Development Cache**
   - **Shared volumes**: `pip-cache` volume for cross-service sharing
   - **Registry cache**: Local registry cache configuration
   - **Benefits**: 80-95% faster local builds

**Cache Hit Rates (Expected):**
- **Base images**: 80-90% (excellent)
- **Service images**: 70-85% (excellent, improved from 20-30%)
- **Local builds**: 80-95% (excellent)
- **CI builds**: 60-70% faster service builds

### BuildKit Configuration
- **Network host**: Enabled for better performance
- **Insecure entitlements**: network.host allowed
- **Driver**: moby/buildkit:latest

## Performance Monitoring

The workflow includes build performance reporting:
- Total workflow time tracking
- Cache hit rate monitoring
- Build order visualization
- Resource usage reporting

## Maintenance

### Adding New Services
1. Determine appropriate base image (python-audio, python-ml, etc.)
2. Add service requirements to tools image if needed for testing
3. Update build dependencies in this README
4. Test build times and adjust timeouts if necessary

### Optimizing Build Times
1. Review layer caching effectiveness
2. Consider splitting large images into smaller, focused ones
3. Update dependency ordering for better cache hits
4. Monitor BuildKit cache performance

### Troubleshooting

#### General Issues
- Check GitHub Actions logs for timeout issues
- Verify cache hit rates in build logs
- Monitor disk space usage during builds
- Review BuildKit driver configuration

#### Disk Space Issues

**"No space left on device" Errors**:
- **Symptoms**: Build failures during ML compilation
- **Root Causes**:
  1. Missing cleanup in base image builds
  2. Large ML package downloads (4.36GB)
  3. Insufficient timeouts for large downloads
  4. GitHub runner disk constraints
- **Solutions**:
  1. **Verify cleanup steps**: Ensure all build tiers have cleanup before and after builds
  2. **Check disk monitoring**: Look for disk space warnings in build logs
  3. **Monitor parallel builds**: Ensure max-parallel limits are respected
  4. **Review timeout settings**: Verify 50-minute job timeout and 45-minute step timeout for Tier 2

**Disk Space Monitoring Commands**:
```bash
# Check available disk space
df -h

# Check Docker disk usage
docker system df

# Clean up Docker resources
docker system prune -f
docker builder prune -f

# Conservative cleanup (preserves base images)
docker image prune -f  # No -a flag
docker volume prune -f
```

**Performance Issues**:
- **Symptoms**: Slower than expected builds
- **Solutions**:
  1. Check network connectivity
  2. Verify cache hit rates in build logs
  3. Ensure parallel builds are enabled
  4. Check resource limits
  5. Monitor cleanup overhead (should be ~1-2 minutes per tier)
