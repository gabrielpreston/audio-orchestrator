#!/usr/bin/env bash
set -euo pipefail

if [[ $# -gt 0 ]]; then
  exec "$@"
fi

echo "Running secret detection..."
# Run detect-secrets to scan for secrets (without updating baseline)
detect-secrets scan --baseline .secrets.baseline --force-use-all-plugins

echo "Secret detection completed!"
