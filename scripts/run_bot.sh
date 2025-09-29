#!/usr/bin/env bash
set -euo pipefail

# Run the opus-enabled bot. Requires libopus installed and WHISPER_URL set in .env.local
if [ -f .env.local ]; then
  set -a
  source .env.local
  set +a
fi

# Allow overriding logfile via env, default to logs/bot.log
LOGFILE="${LOGFILE:-logs/bot.log}"

# Ensure logs dir exists
mkdir -p "$(dirname "$LOGFILE")"

# Pipe all output (stdout+stderr) through tee which appends to the logfile
# so the output is both written to the log file and shown in the terminal.
exec > >(tee -a "$LOGFILE") 2>&1

echo "Building bot..."
go build -o bin/bot ./cmd/bot

echo "Starting bot (logging to $LOGFILE)"
./bin/bot
