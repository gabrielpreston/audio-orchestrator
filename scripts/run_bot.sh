#!/usr/bin/env bash
set -euo pipefail

# Run the opus-enabled bot. Requires libopus installed and WHISPER_URL set in .env.local
if [ -f .env.local ]; then
  set -a
  source .env.local
  set +a
fi

echo "Building bot..."
go build -o bin/bot ./cmd/bot

echo "Starting bot"
./bin/bot
