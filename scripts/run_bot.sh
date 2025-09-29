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

echo "Starting bot (logging to $LOGFILE)"

# Start the bot pipeline in its own session/process-group so we can target it
# on shutdown without killing the parent process (e.g. `make`). Prefer `setsid`
# when available; otherwise fall back to running the pipeline in background.
child=0
if command -v setsid >/dev/null 2>&1; then
  # `setsid` starts the command in a new session. The PID we get back is the
  # session leader; killing its process group (negative PID) will terminate
  # the bot and the tee, but not the parent `make` process.
  setsid bash -c './bin/bot 2>&1 | tee -a "'$LOGFILE'"' &
  child=$!
else
  ( ./bin/bot 2>&1 | tee -a "$LOGFILE" ) &
  child=$!
fi

# Trap only forwards the signal to the child process group we started above.
stop_child() {
  echo "Stopping..."
  # try to terminate the whole process group for the child session
  kill -INT -- -$child 2>/dev/null || kill -INT $child 2>/dev/null || true
  # wait for child to exit, but don't let wait propagate non-zero
  wait $child 2>/dev/null || true
  # exit success so make doesn't treat Ctrl+C as a build failure
  exit 0
}

trap 'stop_child' INT TERM

# Wait for the child (pipeline) to exit
wait $child
