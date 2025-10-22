#!/usr/bin/env bash
set -euo pipefail

echo "Linting YAML files..."
# Auto-discover: docker-compose.yml + all workflow files
yamllint -c .yamllint docker-compose.yml .github/workflows/*.y*ml

echo "Validating GitHub Actions workflows..."
actionlint .github/workflows/*.y*ml

echo "YAML linting complete!"
