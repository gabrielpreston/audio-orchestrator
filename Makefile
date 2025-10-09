SHELL := /bin/bash
.PHONY: help run stop logs logs-dump docker-build docker-restart docker-shell docker-config clean docker-clean docker-status lint lint-container lint-image lint-local lint-python lint-dockerfiles lint-compose lint-makefile lint-markdown

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

PYTHON_SOURCES := services
DOCKERFILES := services/discord/Dockerfile services/stt/Dockerfile services/llm/Dockerfile
MARKDOWN_FILES := README.md AGENTS.md $(shell find docs -type f -name '*.md' -print | tr '\n' ' ')
LINT_IMAGE ?= discord-voice-lab/lint:latest
LINT_DOCKERFILE := services/linter/Dockerfile
LINT_WORKDIR := /workspace

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

lint: lint-container ## Run all linters inside the lint toolchain container

lint-container: lint-image ## Build lint container (if needed) and run lint suite
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to run containerized linting." >&2; exit 1; }
	@docker run --rm \
		-u $$(id -u):$$(id -g) \
		-e HOME=$(LINT_WORKDIR) \
		-e USER=$$(id -un 2>/dev/null || echo lint) \
		-v "$(CURDIR)":$(LINT_WORKDIR) \
		$(LINT_IMAGE)

lint-image: ## Build the lint toolchain container image
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to build lint container images." >&2; exit 1; }
	@docker build --pull --tag $(LINT_IMAGE) -f $(LINT_DOCKERFILE) .

lint-local: lint-python lint-dockerfiles lint-compose lint-makefile lint-markdown ## Run all linters using locally installed tooling

lint-python: ## Run Python linters and type checks (black, isort, ruff, mypy)
	@command -v black >/dev/null 2>&1 || { echo "black not found; install it (e.g. pip install black)." >&2; exit 1; }
	@command -v isort >/dev/null 2>&1 || { echo "isort not found; install it (e.g. pip install isort)." >&2; exit 1; }
	@command -v ruff >/dev/null 2>&1 || { echo "ruff not found; install it (e.g. pip install ruff)." >&2; exit 1; }
	@command -v mypy >/dev/null 2>&1 || { echo "mypy not found; install it (e.g. pip install mypy)." >&2; exit 1; }
	@black --check $(PYTHON_SOURCES)
	@isort --check-only $(PYTHON_SOURCES)
	@ruff check $(PYTHON_SOURCES)
	@mypy $(PYTHON_SOURCES)

lint-dockerfiles: ## Lint service Dockerfiles with hadolint
	@command -v hadolint >/dev/null 2>&1 || { \
		echo "hadolint not found; install it (see https://github.com/hadolint/hadolint#install)." >&2; exit 1; }
	@hadolint $(DOCKERFILES)

lint-compose: ## Lint docker-compose.yml with yamllint
	@command -v yamllint >/dev/null 2>&1 || { echo "yamllint not found; install it (e.g. pip install yamllint)." >&2; exit 1; }
	@yamllint docker-compose.yml

lint-makefile: ## Lint Makefile with checkmake
	@command -v checkmake >/dev/null 2>&1 || { \
		echo "checkmake not found; install via 'go install github.com/mrtazz/checkmake/cmd/checkmake@latest'." >&2; exit 1; }
	@checkmake Makefile

lint-markdown: ## Lint Markdown docs with markdownlint
	@command -v markdownlint >/dev/null 2>&1 || { \
		echo "markdownlint not found; install it (e.g. npm install -g markdownlint-cli)." >&2; exit 1; }
	@markdownlint $(MARKDOWN_FILES)

.DEFAULT_GOAL := help
