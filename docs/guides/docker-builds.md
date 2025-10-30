# Docker builds and caching

This project uses Docker Buildx with a registry-backed build cache to speed up builds locally and in CI.

## Registry cache overview

- Each image exports/imports cache to `:buildcache` in GHCR.
- Multi-stage builds benefit from `mode=max` (intermediate layers cached).
- CI also keeps `type=gha` as a secondary cache source.

## CI flags (reference)

The CI build steps include:

- `--cache-from type=registry,ref=ghcr.io/<owner>/<image>:buildcache`
- `--cache-to type=registry,ref=ghcr.io/<owner>/<image>:buildcache,mode=max`
- `--push` to publish the image tag and the cache.

## Local setup

1) Verify Buildx plugin is installed

```bash
docker buildx version
```

If missing on Linux, install the plugin via your distro (e.g., `apt install docker-buildx-plugin`). See Docker docs.

2) Build with Make targets

- Prefer `make docker-build-enhanced` to build via Compose with caching.
- For tool images:

```bash
make lint-image-force
make test-image-force
```

3) Forcing build modes

- Default attempts Buildx. To force classic builds:

```bash
AO_USE_BUILDX=0 make docker-build-service SERVICE=discord
```

- To set platform for Buildx builds (default `linux/amd64`):

```bash
AO_PLATFORM=linux/arm64 make test-image-force
```

## Troubleshooting

- If you see low cache hits on first run, re-run after CI has populated `:buildcache` tags.
- To inspect Buildx setup:

```bash
docker buildx ls
docker buildx version
```

- If necessary, create/use a builder:

```bash
docker buildx create --name ao-builder --driver docker-container --use
docker buildx inspect ao-builder --bootstrap
```

## References

- Blacksmith: Cache is King — registry cache `mode=max`
- Docker Buildx cache backends (registry)
- docker/build-push-action caching flags
