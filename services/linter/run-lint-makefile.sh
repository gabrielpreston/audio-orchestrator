#!/usr/bin/env bash
set -euo pipefail

echo "Linting Makefile..."
checkmake --config .checkmake.ini Makefile

echo "Makefile linting complete!"
