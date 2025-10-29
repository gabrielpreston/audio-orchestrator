#!/bin/bash
# Build and push base images with wheel caching
set -euo pipefail

REGISTRY="${REGISTRY:-ghcr.io/gabrielpreston}"
TAG="${TAG:-latest}"

echo "Building base images with tag: ${TAG}"

# Build python-web base
echo "Building python-web base image..."
docker build -f services/base/Dockerfile.python-web -t "${REGISTRY}/python-web:${TAG}" .

# Build python-ml base (existing)
echo "Building python-ml base image..."
docker build -f services/base/Dockerfile.python-ml -t "${REGISTRY}/python-ml:${TAG}" .

# Build python-audio base (existing)
echo "Building python-audio base image..."
docker build -f services/base/Dockerfile.python-audio -t "${REGISTRY}/python-audio:${TAG}" .

# Build tools base (existing)
echo "Building tools base image..."
docker build -f services/base/Dockerfile.tools -t "${REGISTRY}/tools:${TAG}" .

echo "Base images built successfully!"
echo "Images:"
echo "  - ${REGISTRY}/python-web:${TAG}"
echo "  - ${REGISTRY}/python-ml:${TAG}"
echo "  - ${REGISTRY}/python-audio:${TAG}"
echo "  - ${REGISTRY}/tools:${TAG}"
