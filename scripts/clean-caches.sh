#!/bin/bash
# Clean Python caches, test artifacts, and build outputs
set -euo pipefail

# Resolve script directory for reliable path handling
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

echo "→ Cleaning logs, caches, and artifacts..."

# Logs and debug files
if [ -d "logs" ]; then
    echo "  Removing logs in ./logs"
    rm -rf logs/* || true
fi

if [ -d ".wavs" ]; then
    echo "  Removing saved wavs/sidecars in ./.wavs"
    rm -rf .wavs/* || true
fi

if [ -d "debug" ]; then
    echo "  Removing debug files in ./debug"
    rm -rf debug/* || true
fi

# Python bytecode and cache directories
echo "  Removing Python cache directories and bytecode..."
find . -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
find . -type f \( -name "*.pyc" -o -name "*.pyo" -o -name "*.pyd" \) -delete 2>/dev/null || true
find . -type d -name "*.egg-info" -prune -exec rm -rf {} + 2>/dev/null || true

# Test and coverage artifacts
if [ -d ".pytest_cache" ]; then
    echo "  Removing .pytest_cache"
    rm -rf .pytest_cache || true
fi

if [ -d "test_artifacts" ]; then
    echo "  Removing test_artifacts"
    rm -rf test_artifacts || true
fi

if [ -f ".coverage" ]; then
    echo "  Removing .coverage"
    rm -f .coverage || true
fi

if [ -f "coverage.xml" ]; then
    echo "  Removing coverage.xml"
    rm -f coverage.xml || true
fi

if [ -d "htmlcov" ]; then
    echo "  Removing htmlcov"
    rm -rf htmlcov || true
fi

if [ -f "junit.xml" ]; then
    echo "  Removing junit.xml"
    rm -f junit.xml || true
fi

# Type checking and linting caches
if [ -d ".mypy_cache" ]; then
    echo "  Removing .mypy_cache"
    rm -rf .mypy_cache || true
fi

if [ -d ".ruff_cache" ]; then
    echo "  Removing .ruff_cache"
    rm -rf .ruff_cache || true
fi

# Build artifacts
if [ -d "build" ]; then
    echo "  Removing build directory"
    rm -rf build || true
fi

if [ -d "dist" ]; then
    echo "  Removing dist directory"
    rm -rf dist || true
fi

# Security scanning artifacts
if [ -d ".bandit" ]; then
    echo "  Removing .bandit cache"
    rm -rf .bandit || true
fi

if [ -d ".pip-audit-cache" ]; then
    echo "  Removing .pip-audit-cache"
    rm -rf .pip-audit-cache || true
fi

if [ -d "security-reports" ]; then
    echo "  Removing security-reports"
    rm -rf security-reports || true
fi

if [ -f "bandit-report.json" ]; then
    echo "  Removing bandit-report.json"
    rm -f bandit-report.json || true
fi

# Generic cache directories
if [ -d ".tox" ]; then
    echo "  Removing .tox"
    rm -rf .tox || true
fi

if [ -d ".cache" ]; then
    echo "  Removing .cache"
    rm -rf .cache || true
fi

if [ -d "cache" ]; then
    echo "  Removing cache directory"
    rm -rf cache || true
fi

echo "→ Cleanup complete"

