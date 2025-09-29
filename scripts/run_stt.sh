#!/usr/bin/env bash
set -euo pipefail

# Create .env.local if not present sample
if [ -f .env.local ]; then
  set -a
  source .env.local
  set +a
fi

VENV_DIR=".venv-stt"
PYTHON=${PYTHON:-python3}

echo "Using python: $(command -v $PYTHON)"

if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtualenv in $VENV_DIR"
  $PYTHON -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

pip install --upgrade pip
if [ -f stt/requirements.txt ]; then
  echo "Installing Python dependencies (this may take a while)..."
  pip install -r stt/requirements.txt
fi

PORT=${STT_PORT:-9000}
HOST=${STT_HOST:-127.0.0.1}

echo "Starting STT server on http://$HOST:$PORT"
exec uvicorn stt.app:app --host "$HOST" --port "$PORT" --proxy-headers
