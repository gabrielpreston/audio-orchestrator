#!/usr/bin/env bash
set -euo pipefail

echo "Running security analysis with bandit..."
# Run bandit security analysis on Python files (skip B104, exclude .venv, only HIGH severity)
bandit -r services/ -f json -o bandit-report.json --skip B104 --exclude "**/.venv/**" --severity-level high

echo "Running secret detection..."
# Run detect-secrets to scan for secrets
detect-secrets scan --baseline .secrets.baseline

echo "Security analysis complete!"
