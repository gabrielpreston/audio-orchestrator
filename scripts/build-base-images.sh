#!/bin/bash
# Build and push base images with wheel caching
set -euo pipefail

# Resolve script directory for reliable path handling
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REGISTRY="${REGISTRY:-ghcr.io/gabrielpreston}"
TAG="${TAG:-latest}"

# Authenticate Docker to GHCR (using shared script)
. "${SCRIPT_DIR}/docker-ghcr-auth.sh"

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
