#!/bin/bash
# Push base images to registry (assumes images are already built locally)
set -euo pipefail

# Resolve script directory for reliable path handling
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REGISTRY="${REGISTRY:-ghcr.io/gabrielpreston}"
TAG="${TAG:-latest}"

# Authenticate Docker to GHCR (required for push)
. "${SCRIPT_DIR}/docker-ghcr-auth.sh"

echo "Pushing base images with tag: ${TAG}"

# Push function
push_base_image() {
    local image_name=$1

    if docker image inspect "${REGISTRY}/${image_name}:${TAG}" >/dev/null 2>&1; then
        echo "Pushing ${image_name} base image..."
        docker push "${REGISTRY}/${image_name}:${TAG}" || {
            echo "Error: Failed to push ${REGISTRY}/${image_name}:${TAG}" >&2
            exit 1
        }
    else
        echo "Warning: Image ${REGISTRY}/${image_name}:${TAG} not found locally. Build it first with 'make docker-build-base'." >&2
        exit 1
    fi
}

# Push all base images
push_base_image "python-web"
push_base_image "python-ml"
push_base_image "tools"

echo "Base images pushed successfully!"
echo "Images:"
echo "  - ${REGISTRY}/python-web:${TAG}"
echo "  - ${REGISTRY}/python-ml:${TAG}"
echo "  - ${REGISTRY}/tools:${TAG}"

