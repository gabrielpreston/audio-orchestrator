#!/usr/bin/env bash
set -euo pipefail

detect_docker_compose() {
  if command -v docker-compose >/dev/null 2>&1; then
    echo "docker-compose"
  elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    echo "docker compose"
  else
    echo ""
  fi
}

COLOR_OFF=${COLOR_OFF:-$(printf '\033[0m')}
COLOR_GREEN=${COLOR_GREEN:-$(printf '\033[32m')}
COMPOSE_MISSING_MESSAGE=${COMPOSE_MISSING_MESSAGE:-"Docker Compose was not found (checked docker compose and docker-compose); please install Docker Compose."}
DOCKER_BUILDKIT=${DOCKER_BUILDKIT:-1}
COMPOSE_DOCKER_CLI_BUILD=${COMPOSE_DOCKER_CLI_BUILD:-1}

DOCKER_COMPOSE=${DOCKER_COMPOSE:-$(detect_docker_compose)}
if [[ -z "${DOCKER_COMPOSE}" ]]; then
  echo "${COMPOSE_MISSING_MESSAGE}"
  exit 1
fi

echo -e "${COLOR_GREEN}🚀 Bringing up containers (press Ctrl+C to stop)${COLOR_OFF}"
if [[ "${DOCKER_BUILDKIT}" == "1" ]] && (command -v docker-buildx >/dev/null 2>&1 || docker buildx version >/dev/null 2>&1 2>/dev/null); then
  DOCKER_BUILDKIT=${DOCKER_BUILDKIT} COMPOSE_DOCKER_CLI_BUILD=${COMPOSE_DOCKER_CLI_BUILD} "${DOCKER_COMPOSE}" up -d --build --remove-orphans
else
  if [[ "${DOCKER_BUILDKIT}" == "1" ]]; then
    echo "Warning: BuildKit requested but docker buildx is missing; running without BuildKit."
  fi
  "${DOCKER_COMPOSE}" up -d --build --remove-orphans
fi
