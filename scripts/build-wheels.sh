#!/bin/bash
# Build and cache wheels for native dependencies
# This script pre-builds wheels for packages that require compilation

set -euo pipefail

WHEEL_DIR="${WHEEL_DIR:-/tmp/wheels}"
PYTHON_VERSION="${PYTHON_VERSION:-3.11}"

echo "Building wheels for Python ${PYTHON_VERSION} in ${WHEEL_DIR}"

# Create wheel directory
mkdir -p "${WHEEL_DIR}"

# Install wheel and build tools
pip install --upgrade pip setuptools wheel

# Build wheels for packages that benefit from pre-compilation
echo "Building numpy wheel..."
pip wheel --no-deps --wheel-dir="${WHEEL_DIR}" "numpy>=1.24,<2.0"

echo "Building scipy wheel..."
pip wheel --no-deps --wheel-dir="${WHEEL_DIR}" "scipy>=1.11,<2.0"

echo "Building webrtcvad wheel..."
pip wheel --no-deps --wheel-dir="${WHEEL_DIR}" "webrtcvad>=2.0,<3.0"

echo "Building PyNaCl wheel..."
pip wheel --no-deps --wheel-dir="${WHEEL_DIR}" "PyNaCl>=1.5,<2.0"

echo "Building openwakeword wheel..."
pip wheel --no-deps --wheel-dir="${WHEEL_DIR}" "openwakeword>=0.6,<1.0"

echo "Building rapidfuzz wheel..."
pip wheel --no-deps --wheel-dir="${WHEEL_DIR}" "rapidfuzz>=3.5,<4.0"

echo "Wheels built successfully in ${WHEEL_DIR}"
echo "Contents:"
ls -la "${WHEEL_DIR}"
