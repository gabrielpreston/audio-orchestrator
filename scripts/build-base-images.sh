#!/bin/bash
# Build and push base images with wheel caching
set -euo pipefail

REGISTRY="${REGISTRY:-ghcr.io/gabrielpreston}"
TAG="${TAG:-latest}"

# Authenticate Docker to GHCR
# Priority: GHCR_TOKEN > GitHub CLI
echo "Authenticating Docker to GHCR..."
if [ -n "${GHCR_TOKEN:-}" ]; then
    GHCR_USER="${GHCR_USERNAME:-$(gh api user --jq .login 2>/dev/null || echo $(whoami))}"
    echo "${GHCR_TOKEN}" | docker login ghcr.io -u "${GHCR_USER}" --password-stdin || \
        { echo "Error: Failed to authenticate Docker to GHCR using GHCR_TOKEN" >&2; exit 1; }
elif command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    echo "$(gh auth token)" | docker login ghcr.io -u "$(gh api user --jq .login 2>/dev/null || echo $(whoami))" --password-stdin || \
        { echo "Error: Failed to authenticate Docker to GHCR" >&2; exit 1; }
else
    echo "Error: Cannot authenticate to GHCR. Either:" >&2
    echo "  1. Set GHCR_TOKEN environment variable (with write:packages scope)" >&2
    echo "  2. Authenticate GitHub CLI: gh auth login --scopes write:packages" >&2
    exit 1
fi

echo "Building base images with tag: ${TAG}"

# Build and push python-web base
echo "Building python-web base image..."
docker buildx build -f services/base/Dockerfile.python-web -t "${REGISTRY}/python-web:${TAG}" \
  --cache-from type=registry,ref=${REGISTRY}/cache:base-images \
  --cache-to type=registry,ref=${REGISTRY}/cache:base-images,mode=max \
  --build-arg BUILDKIT_INLINE_CACHE=1 \
  --load \
  --push \
  .

# Build and push python-ml base (existing)
echo "Building python-ml base image..."
docker buildx build -f services/base/Dockerfile.python-ml -t "${REGISTRY}/python-ml:${TAG}" \
  --cache-from type=registry,ref=${REGISTRY}/cache:base-images \
  --cache-to type=registry,ref=${REGISTRY}/cache:base-images,mode=max \
  --build-arg BUILDKIT_INLINE_CACHE=1 \
  --load \
  --push \
  .

# Build and push python-audio base (existing)
echo "Building python-audio base image..."
docker buildx build -f services/base/Dockerfile.python-audio -t "${REGISTRY}/python-audio:${TAG}" \
  --cache-from type=registry,ref=${REGISTRY}/cache:base-images \
  --cache-to type=registry,ref=${REGISTRY}/cache:base-images,mode=max \
  --build-arg BUILDKIT_INLINE_CACHE=1 \
  --load \
  --push \
  .

# Build and push tools base (existing)
echo "Building tools base image..."
docker buildx build -f services/base/Dockerfile.tools -t "${REGISTRY}/tools:${TAG}" \
  --cache-from type=registry,ref=${REGISTRY}/cache:base-images \
  --cache-to type=registry,ref=${REGISTRY}/cache:base-images,mode=max \
  --build-arg BUILDKIT_INLINE_CACHE=1 \
  --load \
  --push \
  .

echo "Base images built successfully!"
echo "Images:"
echo "  - ${REGISTRY}/python-web:${TAG}"
echo "  - ${REGISTRY}/python-ml:${TAG}"
echo "  - ${REGISTRY}/python-audio:${TAG}"
echo "  - ${REGISTRY}/tools:${TAG}"
