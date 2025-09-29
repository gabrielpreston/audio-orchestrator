#!/usr/bin/env bash
# Quick smoke test to POST a WAV to local STT server
# Usage: ./scripts/test_stt.sh [translate] or set FILE env to override

HOST=${STT_HOST:-http://127.0.0.1:9000}
# Default to the generated human speech test file. Can be overridden by
# setting FILE env var or passing a different file path.
FILE=${FILE:-test_speech_16k.wav}

# If docker-compose is available and the stt service isn't running, attempt to start it
start_stt_with_compose() {
  if ! command -v docker-compose >/dev/null 2>&1; then
    return 1
  fi
  # Check if service 'stt' is listed as running
  if docker-compose ps stt >/dev/null 2>&1; then
    # If ps shows the service but it's not up, try to bring it up
    STATES=$(docker-compose ps -q stt | xargs -r docker inspect -f '{{.State.Status}}' 2>/dev/null || true)
    if echo "$STATES" | grep -q "running"; then
      return 0
    fi
  fi
  echo "Starting stt service via docker-compose..."
  docker-compose up -d stt
  return $?
}

## wait_for_tcp waits up to $3 seconds (default 30) for host:port to accept TCP connections.
## Usage: wait_for_tcp host port [timeout]
wait_for_tcp() {
  local host=$1
  local port=$2
  local timeout=${3:-30}
  local start=$(date +%s)
  while true; do
    # bash built-in /dev/tcp works on many systems
    if (echo > /dev/tcp/${host}/${port}) >/dev/null 2>&1; then
      return 0
    fi
    now=$(date +%s)
    if [ $((now - start)) -ge $timeout ]; then
      return 1
    fi
    sleep 1
  done
}

if [ ! -f "$FILE" ]; then
  echo "Missing $FILE in repo root"
  exit 2
fi

if [ "$1" = "translate" ]; then
  echo "Posting $FILE with task=translate to $HOST/asr"
  # ensure STT endpoint up
  if start_stt_with_compose; then
    echo "Waiting for STT endpoint to be ready (TCP)..."
    # extract host and port from HOST (format http[s]://host:port)
    hostport=${HOST#*://}
    host=${hostport%%/*}
    host=${host%%:*}
    port=${hostport##*:}
    if [ "$port" = "$host" ]; then
      port=9000
    fi
    if ! wait_for_tcp "$host" "$port" 30; then
      echo "STT endpoint did not become ready in time"
      exit 3
    fi
  fi
  curl -sS -X POST "$HOST/asr?task=translate" -H "Content-Type: audio/wav" --data-binary "@${FILE}" | jq -C '.'
else
  echo "Posting $FILE to $HOST/asr"
  if start_stt_with_compose; then
    echo "Waiting for STT endpoint to be ready (TCP)..."
    hostport=${HOST#*://}
    host=${hostport%%/*}
    host=${host%%:*}
    port=${hostport##*:}
    if [ "$port" = "$host" ]; then
      port=9000
    fi
    if ! wait_for_tcp "$host" "$port" 30; then
      echo "STT endpoint did not become ready in time"
      exit 3
    fi
  fi
  curl -sS -X POST "$HOST/asr" -H "Content-Type: audio/wav" --data-binary "@${FILE}" | jq -C '.'
fi
