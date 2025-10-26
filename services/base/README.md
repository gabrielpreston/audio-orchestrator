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
│   ├── python-ml-compiled (3-4 min)
│   │   └── Pre-compiled wheels
│   ├── stt, llm_flan, orchestrator_enhanced services
│   ├── tts_bark, guardrails services
│   ├── audio_processor, testing_ui services
│   └── monitoring_dashboard service
├── tools (8-10 min after optimization)
│   └── linter, tester services
└── mcp-toolchain (5-7 min)
    └── orchestrator services (future)
```

## Build Time Estimates

- **Total Pipeline**: 12-15 minutes (optimized from 20+ minutes)
- **Critical Path**: python-base → python-ml → tools
- **Parallel Builds**: python-audio, python-ml can build in parallel after python-base

## Optimization Strategies

1. **Layer Caching**: BuildKit cache mounts for pip, npm, go
2. **Multi-stage Builds**: Separate builder and runtime stages
3. **Dependency Ordering**: Install stable dependencies first
4. **Minimal Installations**: Only install what's needed for each image

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

### python-ml-compiled
- Pre-compiled wheels for faster installation
- Used by: Services requiring compiled dependencies
- Build time: 3-4 minutes

### tools
- Development tools (linter, tester, hadolint, etc.)
- Used by: linter, tester services
- Build time: 8-10 minutes (after optimization)
- **Optimized**: Only includes linter and tester requirements

### mcp-toolchain
- MCP server toolchain (Node.js, Rust, Go)
- Used by: orchestrator services (future)
- Build time: 5-7 minutes
- **Optimized**: Uses minimal Rust profile

## Build Configuration

### Timeouts
- **Base workflow**: 60 minutes (increased from 45)
- **Individual builds**: 15-20 minutes
- **Tools build**: 20 minutes (increased from 15)

### Cache Strategy
- **GitHub Actions Cache v2**: Enabled
- **BuildKit cache mounts**: For pip, npm, go installations
- **Registry cache**: Pre-pull existing images for cache warming

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
- Check GitHub Actions logs for timeout issues
- Verify cache hit rates in build logs
- Monitor disk space usage during builds
- Review BuildKit driver configuration
