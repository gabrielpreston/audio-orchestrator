#!/usr/bin/env bash
set -euo pipefail

echo "Linting Makefile..."
checkmake --config .checkmake.yaml Makefile

echo "Makefile linting complete!"
