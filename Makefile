SHELL := /bin/bash
.PHONY: help run stop logs logs-dump docker-build docker-restart docker-shell docker-config clean docker-clean docker-status

# --- colors & helpers ----------------------------------------------------
COLORS := $(shell tput colors 2>/dev/null || echo 0)
ifeq ($(COLORS),0)
        COLOR_OFF :=
        COLOR_RED :=
        COLOR_GREEN :=
        COLOR_YELLOW :=
        COLOR_BLUE :=
        COLOR_MAGENTA :=
        COLOR_CYAN :=
else
        COLOR_OFF := $(shell printf '\033[0m')
        COLOR_RED := $(shell printf '\033[31m')
        COLOR_GREEN := $(shell printf '\033[32m')
        COLOR_YELLOW := $(shell printf '\033[33m')
        COLOR_BLUE := $(shell printf '\033[34m')
        COLOR_MAGENTA := $(shell printf '\033[35m')
        COLOR_CYAN := $(shell printf '\033[36m')
endif

DOCKER_COMPOSE := $(shell \
        if command -v docker-compose >/dev/null 2>&1; then \
		    echo "docker-compose"; \
        elif command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then \
		    echo "docker compose"; \
        else \
		    echo ""; \
        fi)

ifeq ($(strip $(DOCKER_COMPOSE)),)
HAS_DOCKER_COMPOSE := 0
else
HAS_DOCKER_COMPOSE := 1
endif

COMPOSE_MISSING_MESSAGE := Docker Compose was not found (checked 'docker compose' and 'docker-compose'); please install Docker Compose.

# Enable BuildKit by default for faster builds when Docker is available.
DOCKER_BUILDKIT ?= 1
COMPOSE_DOCKER_CLI_BUILD ?= 1

help: ## Show this help (default)
	@echo -e "$(COLOR_CYAN)discord-voice-lab Makefile — handy targets$(COLOR_OFF)"
	@echo
	@echo "Usage: make <target>"
	@echo
	@awk 'BEGIN {FS = ":.*## "} /^[^[:space:]#].*:.*##/ { printf "  %-14s - %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

run: stop ## Start docker-compose stack (Discord bot + STT + orchestrator)
	@echo -e "$(COLOR_GREEN)🚀 Bringing up containers (press Ctrl+C to stop)$(COLOR_OFF)"
	@if [ "$(HAS_DOCKER_COMPOSE)" = "0" ]; then echo "$(COMPOSE_MISSING_MESSAGE)"; exit 1; fi
	@if [ "$(DOCKER_BUILDKIT)" = "1" ] && (command -v docker-buildx >/dev/null 2>&1 || docker buildx version >/dev/null 2>&1 2>/dev/null); then \
	DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) COMPOSE_DOCKER_CLI_BUILD=$(COMPOSE_DOCKER_CLI_BUILD) $(DOCKER_COMPOSE) up -d --build --remove-orphans; \
	else \
	if [ "$(DOCKER_BUILDKIT)" = "1" ]; then echo "Warning: BuildKit requested but 'docker buildx' is missing; running without BuildKit."; fi; \
	$(DOCKER_COMPOSE) up -d --build --remove-orphans; \
	fi


stop: ## Stop and remove containers for the compose stack
	@echo -e "$(COLOR_BLUE)→ Bringing down containers$(COLOR_OFF)"
	@if [ "$(HAS_DOCKER_COMPOSE)" = "0" ]; then echo "$(COMPOSE_MISSING_MESSAGE)"; exit 1; fi
	@$(DOCKER_COMPOSE) down --remove-orphans

logs: ## Tail logs for compose services (set SERVICE=name to filter)
	@echo -e "$(COLOR_CYAN)→ Tailing logs for docker services (Ctrl+C to stop)$(COLOR_OFF)"
	@if [ "$(HAS_DOCKER_COMPOSE)" = "0" ]; then echo "$(COMPOSE_MISSING_MESSAGE)"; exit 1; fi
	@if [ -z "$(SERVICE)" ]; then \
	$(DOCKER_COMPOSE) logs -f --tail=100; \
	else \
	$(DOCKER_COMPOSE) logs -f --tail=100 $(SERVICE); \
	fi

logs-dump: ## Capture docker logs to ./docker.logs
	@echo -e "$(COLOR_CYAN)→ Dumping all logs for docker services$(COLOR_OFF)"
	@if [ "$(HAS_DOCKER_COMPOSE)" = "0" ]; then echo "$(COMPOSE_MISSING_MESSAGE)"; exit 1; fi
	@$(DOCKER_COMPOSE) logs > ./docker.logs

docker-build: ## Build or rebuild images for the compose stack
	@echo -e "$(COLOR_GREEN)→ Building docker images$(COLOR_OFF)"
	@if [ "$(HAS_DOCKER_COMPOSE)" = "0" ]; then echo "$(COMPOSE_MISSING_MESSAGE)"; exit 1; fi
	@DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) COMPOSE_DOCKER_CLI_BUILD=$(COMPOSE_DOCKER_CLI_BUILD) $(DOCKER_COMPOSE) build --parallel

docker-restart: ## Restart compose services (set SERVICE=name to limit scope)
	@echo -e "$(COLOR_BLUE)→ Restarting docker services$(COLOR_OFF)"
	@if [ "$(HAS_DOCKER_COMPOSE)" = "0" ]; then echo "$(COMPOSE_MISSING_MESSAGE)"; exit 1; fi
	@if [ -z "$(SERVICE)" ]; then \
	$(DOCKER_COMPOSE) restart; \
	else \
	$(DOCKER_COMPOSE) restart $(SERVICE); \
	fi

docker-shell: ## Open an interactive shell inside a running service (SERVICE=name)
	@if [ "$(HAS_DOCKER_COMPOSE)" = "0" ]; then echo "$(COMPOSE_MISSING_MESSAGE)"; exit 1; fi
	@if [ -z "$(SERVICE)" ]; then echo "Set SERVICE=<service-name> (discord|stt|orch)"; exit 1; fi
	@$(DOCKER_COMPOSE) exec $(SERVICE) /bin/bash

docker-config: ## Render the effective docker-compose configuration
	@if [ "$(HAS_DOCKER_COMPOSE)" = "0" ]; then echo "$(COMPOSE_MISSING_MESSAGE)"; exit 1; fi
	@$(DOCKER_COMPOSE) config

clean: ## Remove logs and cached audio artifacts
	@echo -e "$(COLOR_BLUE)→ Cleaning...$(COLOR_OFF)"
	@if [ -d "logs" ]; then \
	echo "Removing logs in ./logs"; \
	rm -rf logs/* || true; \
	fi
	@if [ -d ".wavs" ]; then \
	echo "Removing saved wavs/sidecars in ./.wavs"; \
	rm -rf .wavs/* || true; \
	fi
	@if [ -d "services" ]; then \
	echo "Removing __pycache__ directories under ./services"; \
	find services -type d -name "__pycache__" -prune -print -exec rm -rf {} + || true; \
	fi

docker-clean: ## Bring down compose stack and prune unused docker resources
	@echo -e "$(COLOR_RED)→ Cleaning Docker: compose down, prune images/containers/volumes/networks$(COLOR_OFF)"
	@if [ "$(HAS_DOCKER_COMPOSE)" = "0" ]; then \
		echo "$(COMPOSE_MISSING_MESSAGE) Skipping compose down."; \
	else \
		$(DOCKER_COMPOSE) down --rmi all -v --remove-orphans || true; \
	fi
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; skipping docker prune steps."; exit 0; }
	@echo "Pruning stopped containers..."
	@docker container prune -f || true
	@echo "Pruning unused images (this will remove dangling and unused images)..."
	@docker image prune -a -f || true
	@echo "Pruning unused volumes..."
	@docker volume prune -f || true
	@echo "Pruning unused networks..."
	@docker network prune -f || true


docker-status: ## Show status of docker-compose services
	@if [ "$(HAS_DOCKER_COMPOSE)" = "0" ]; then echo "$(COMPOSE_MISSING_MESSAGE)"; exit 1; fi
	@$(DOCKER_COMPOSE) ps

.DEFAULT_GOAL := help
