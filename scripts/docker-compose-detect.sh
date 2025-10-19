#!/usr/bin/env bash
# Helper script to detect Docker Compose command

if command -v docker-compose >/dev/null 2>&1; then
  echo "docker-compose"
elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  echo "docker compose"
else
  echo ""
fi