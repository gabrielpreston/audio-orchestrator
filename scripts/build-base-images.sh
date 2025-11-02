#!/bin/bash
# Build base images with optional push support
set -euo pipefail

# Resolve script directory for reliable path handling
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REGISTRY="${REGISTRY:-ghcr.io/gabrielpreston}"
TAG="${TAG:-latest}"
PUSH="${PUSH:-false}"

# Only authenticate when pushing
if [ "${PUSH}" = "true" ]; then
    # Authenticate Docker to GHCR (using shared script)
    . "${SCRIPT_DIR}/docker-ghcr-auth.sh"
fi

if [ "${PUSH}" = "true" ]; then
    echo "Building and pushing base images with tag: ${TAG}"
else
    echo "Building base images locally with tag: ${TAG}"
fi

# Build function to avoid duplication
build_base_image() {
    local dockerfile=$1
    local image_name=$2

    echo "Building ${image_name} base image..."

    if [ "${PUSH}" = "true" ]; then
        docker buildx build -f "${dockerfile}" -t "${REGISTRY}/${image_name}:${TAG}" \
            --cache-from type=registry,ref=${REGISTRY}/cache:base-images \
            --cache-to type=registry,ref=${REGISTRY}/cache:base-images,mode=max \
            --build-arg BUILDKIT_INLINE_CACHE=1 \
            --load \
            --push \
            .
    else
        docker buildx build -f "${dockerfile}" -t "${REGISTRY}/${image_name}:${TAG}" \
            --cache-from type=registry,ref=${REGISTRY}/cache:base-images \
            --cache-to type=local,dest=/tmp/.buildkit-cache \
            --build-arg BUILDKIT_INLINE_CACHE=1 \
            --load \
            .
    fi
}

# Build all base images
build_base_image "services/base/Dockerfile.python-web" "python-web"
build_base_image "services/base/Dockerfile.python-ml" "python-ml"
build_base_image "services/base/Dockerfile.python-audio" "python-audio"
build_base_image "services/base/Dockerfile.tools" "tools"

echo "Base images built successfully!"
echo "Images:"
echo "  - ${REGISTRY}/python-web:${TAG}"
echo "  - ${REGISTRY}/python-ml:${TAG}"
echo "  - ${REGISTRY}/python-audio:${TAG}"
echo "  - ${REGISTRY}/tools:${TAG}"
if [ "${PUSH}" = "false" ]; then
    echo "  (built locally - use PUSH=true to push to registry)"
fi
