#!/bin/sh
set -e

if [ -z "$MONDAY_API_KEY" ]; then
  echo "MONDAY_API_KEY is not set. Provide it via environment or .env.docker"
  exit 1
fi

echo "Starting monday API MCP with provided API key..."

# The monday API MCP CLI exposes a local server; run via npx
# We forward any args, but by default run in host 0.0.0.0 so compose port mapping works
exec npx --yes @mondaydotcomorg/monday-api-mcp -t "$MONDAY_API_KEY" --host 0.0.0.0
