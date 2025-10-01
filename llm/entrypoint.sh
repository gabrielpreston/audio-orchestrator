#!/usr/bin/env bash
set -euo pipefail

# Ensure model directory exists
mkdir -p /app/models

echo "Starting LLM service..."
exec gunicorn --bind 0.0.0.0:5000 --workers 1 --threads 4 app:app
