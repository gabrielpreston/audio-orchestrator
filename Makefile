SHELL := /bin/bash
.PHONY: help test build bot fmt vet lint run clean ci version stop logs dev-bot dev-stt dev-bot-daemon dev-stop-bot docker-status

# --- colors & helpers ----------------------------------------------------
# Detect terminal color support via tput. If tput is missing or reports 0,
# leave color vars empty so output stays plain.
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

GO := go
BINARY := bin/bot
PKG := ./...

# Enable BuildKit by default for faster, modern builds. Set to 0 to disable.
DOCKER_BUILDKIT ?= 1
# For legacy docker-compose, enable Docker CLI build integration so BuildKit is used
COMPOSE_DOCKER_CLI_BUILD ?= 1

# Choose the docker compose command at Makefile parse time so recipes can
# use a simple variable. Prefer the new 'docker compose' subcommand, fall
# back to the legacy 'docker-compose' binary.
DOCKER_COMPOSE := $(shell if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 2>/dev/null; then echo "docker compose"; elif command -v docker-compose >/dev/null 2>&1; then echo "docker-compose"; else echo ""; fi)

help: ## Show this help (default)
	@echo -e "$(COLOR_CYAN)discord-voice-lab Makefile — handy targets$(COLOR_OFF)"
	@echo
	@echo "Usage: make <target>"
	@echo
	@awk 'BEGIN {FS = ":.*## "} /^[^[:space:]#].*:.*##/ { printf "  %-12s - %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

test: ## Run unit tests (verbose)
	@echo -e "$(COLOR_YELLOW)→ Running go tests...$(COLOR_OFF)"
	$(GO) test -v $(PKG)

build: ## Build the bot binary
	@echo -e "$(COLOR_YELLOW)→ Building $(BINARY)$(COLOR_OFF)"
	$(GO) build -o $(BINARY) ./cmd/bot


stop: ## Stop and remove containers for the compose stack
	@echo -e "$(COLOR_BLUE)→ Bringing down containers via docker compose$(COLOR_OFF)"
	@# Ensure we have a compose command available
	@if [ -z "$(DOCKER_COMPOSE)" ]; then echo "Neither 'docker compose' nor 'docker-compose' was found; please install Docker Compose."; exit 1; fi
	@$(DOCKER_COMPOSE) down --remove-orphans

run: stop ## Stop all running services before starting all services
	@echo -e "$(COLOR_GREEN)🚀 Bringing up containers via docker compose (press Ctrl+C to stop)$(COLOR_OFF)"
	@# Fail early if no compose command is available
	@if [ -z "$(DOCKER_COMPOSE)" ]; then echo "Neither 'docker compose' nor 'docker-compose' was found; please install Docker Compose."; exit 1; fi
	@# Prefer BuildKit with buildx when requested; otherwise run a plain compose up
	@if [ "$(DOCKER_BUILDKIT)" = "1" ] && (command -v docker-buildx >/dev/null 2>&1 || docker buildx version >/dev/null 2>&1 2>/dev/null); then \
		DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) COMPOSE_DOCKER_CLI_BUILD=$(COMPOSE_DOCKER_CLI_BUILD) $(DOCKER_COMPOSE) up -d --build --remove-orphans; \
	else \
		if [ "$(DOCKER_BUILDKIT)" = "1" ]; then echo "Warning: BuildKit requested but 'docker buildx' is missing; running without BuildKit."; fi; \
		$(DOCKER_COMPOSE) up -d --build --remove-orphans; \
	fi

logs: ## Tail logs for compose services (live). Optionally set SERVICE=bot to tail a single service
	@echo -e "$(COLOR_CYAN)→ Tailing logs for compose services (Ctrl+C to stop)$(COLOR_OFF)"
	@# Ensure we have a compose command available
	@if [ -z "$(DOCKER_COMPOSE)" ]; then echo "Neither 'docker compose' nor 'docker-compose' was found; please install Docker Compose."; exit 1; fi
	@if [ -z "$(SERVICE)" ]; then \
		$(DOCKER_COMPOSE) logs -f --tail=100; \
	else \
		$(DOCKER_COMPOSE) logs -f --tail=100 $(SERVICE); \
	fi

dev-stt: ## Run STT locally (virtualenv) via scripts/run_stt.sh (sources .env.local if present)
	@echo -e "$(COLOR_GREEN)→ Starting STT (local dev)$(COLOR_OFF)"
	@bash -lc 'if [ -f .env.local ]; then set -a; . ./.env.local; set +a; fi; exec ./scripts/run_stt.sh'

dev-bot: ## Run the bot binary locally and log to file via scripts/run_bot.sh
	@echo -e "$(COLOR_GREEN)→ Starting bot (local dev)$(COLOR_OFF)"
	@bash -lc 'if [ -f .env.local ]; then set -a; . ./.env.local; set +a; fi; mkdir -p logs; nohup ./scripts/run_bot.sh >> logs/bot.log 2>&1 & echo $$! > logs/dev-bot.pid; echo "dev-bot started (background)";'

dev-bot-stop: ## Stop a backgrounded dev-bot started by dev-bot (uses logs/dev-bot.pid)
	@echo -e "$(COLOR_BLUE)→ Stopping background dev-bot (if running)$(COLOR_OFF)"
	@if [ -f logs/dev-bot.pid ]; then \
		PID=`cat logs/dev-bot.pid`; \
		echo "Found PID $$PID, sending SIGINT..."; \
		kill -INT $$PID 2>/dev/null || true; \
		COUNT=0; while kill -0 $$PID 2>/dev/null; do \
			sleep 1; COUNT=$$((COUNT+1)); if [ $$COUNT -ge 10 ]; then break; fi; done; \
		if kill -0 $$PID 2>/dev/null; then \
			echo "Process still running after SIGINT, sending SIGTERM..."; \
			kill -TERM $$PID 2>/dev/null || true; \
			COUNT=0; while kill -0 $$PID 2>/dev/null; do sleep 1; COUNT=$$((COUNT+1)); if [ $$COUNT -ge 5 ]; then break; fi; done; \
		fi; \
		if ! kill -0 $$PID 2>/dev/null; then rm -f logs/dev-bot.pid; echo "dev-bot stopped"; else echo "Failed to stop dev-bot (PID $$PID is still running)"; fi; \
	else \
		echo "No logs/dev-bot.pid found; is the bot running in background?"; exit 1; \
	fi

fmt: ## Run gofmt and goimports (best-effort)
	@echo -e "$(COLOR_YELLOW)→ Formatting Go code...$(COLOR_OFF)"
	@find . -name '*.go' -not -path './vendor/*' -print0 | xargs -0 gofmt -s -w || true

vet: ## Run go vet
	@echo -e "$(COLOR_YELLOW)→ Running go vet...$(COLOR_OFF)"
	$(GO) vet ./... || true

lint: ## Run golangci-lint if available (else print hint)
	@if command -v golangci-lint >/dev/null 2>&1; then \
		echo -e "$(COLOR_YELLOW)→ Running golangci-lint...$(COLOR_OFF)"; \
		golangci-lint run; \
	else \
		echo -e "$(COLOR_RED)golangci-lint not found. Install from https://github.com/golangci/golangci-lint#install $(COLOR_OFF)"; \
		false; \
	fi

clean: ## Remove build artifacts
	@echo -e "$(COLOR_BLUE)→ Cleaning...$(COLOR_OFF)"
	@rm -f $(BINARY)
	@# Remove saved wavs/sidecars in ./.wavs when present and logs
	@if [ -d "logs" ]; then \
		echo "Removing logs in ./logs"; \
		rm -rf logs/* || true; \
	fi
	@if [ -d ".wavs" ]; then \
		echo "Removing saved wavs/sidecars in ./.wavs"; \
		rm -rf .wavs/* || true; \
	fi

ci: fmt vet test lint ## Run CI-like checks locally
	@echo -e "$(COLOR_MAGENTA)✓ CI checks complete (locally)$(COLOR_OFF)"

version: ## Show Go version and module info
	@echo -e "$(COLOR_CYAN)→ Go version:$(COLOR_OFF)"; $(GO) version
	@echo -e "$(COLOR_CYAN)→ Module:$(COLOR_OFF)"; cat go.mod | sed -n '1,3p'

# end of file

.DEFAULT_GOAL := help

# --- docker buildx helpers -----------------------------------------------
IMAGE_NAME := discord-voice-bot
IMAGE_TAG ?= latest

.PHONY: build-image push-image buildx-ensure docker-clean

# Ensure a buildx builder exists (no-op if already present)
buildx-ensure:
	@command -v docker >/dev/null 2>&1 || { echo "docker not found"; exit 1; }
	@if docker buildx inspect mybuilder >/dev/null 2>&1; then \
		echo "buildx builder 'mybuilder' already exists"; \
	else \
		echo "creating buildx builder 'mybuilder'"; \
		docker buildx create --use --name mybuilder || true; \
	fi

# Build image with buildx (multi-platform optional). Falls back to docker build
build-image: ## Build the docker image using buildx if available
	@echo -e "$(COLOR_YELLOW)→ Building docker image $(IMAGE_NAME):$(IMAGE_TAG)$(COLOR_OFF)"
	@if command -v docker-buildx >/dev/null 2>&1 || docker buildx version >/dev/null 2>&1; then \
		$(MAKE) buildx-ensure >/dev/null; \
		DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) COMPOSE_DOCKER_CLI_BUILD=$(COMPOSE_DOCKER_CLI_BUILD) docker buildx build --tag $(IMAGE_NAME):$(IMAGE_TAG) --load .; \
	else \
		if [ "$(DOCKER_BUILDKIT)" = "1" ]; then echo "Warning: BuildKit requested but 'docker buildx' is missing; using legacy docker build."; fi; \
		DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .; \
	fi

# Push image using buildx (useful for multi-arch builds)
push-image: ## Push the docker image via buildx (requires login)
	@echo -e "$(COLOR_YELLOW)→ Pushing docker image $(IMAGE_NAME):$(IMAGE_TAG)$(COLOR_OFF)"
	@if docker buildx version >/dev/null 2>&1; then \
		docker buildx build --tag $(IMAGE_NAME):$(IMAGE_TAG) --push .; \
	else \
		echo "docker buildx not available; run 'docker login' and push manually"; \
	fi

docker-clean: ## Bring down compose stack (if any) and prune unused containers/images/volumes/networks (non-interactive)
	@echo -e "$(COLOR_RED)→ Cleaning Docker: compose down, prune images/containers/volumes/networks$(COLOR_OFF)"
	@# Try to bring down compose stack if a compose command is available
	@if [ -z "$(DOCKER_COMPOSE)" ]; then \
		echo "No docker compose command found; skipping compose down."; \
	else \
		$(DOCKER_COMPOSE) down --rmi all -v --remove-orphans || true; \
	fi
	@# If docker itself is missing, skip pruning steps
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; skipping docker prune steps."; exit 0; }
	@echo "Pruning stopped containers..."
	@docker container prune -f || true
	@echo "Pruning unused images (this will remove dangling and unused images)..."
	@docker image prune -a -f || true
	@echo "Pruning unused volumes..."
	@docker volume prune -f || true
	@echo "Pruning unused networks..."
	@docker network prune -f || true
	@echo -e "$(COLOR_GREEN)→ docker-clean complete$(COLOR_OFF)"

docker-status: ## Check whether compose services (stt, bot) are up and running
	@echo -e "$(COLOR_CYAN)→ Checking docker-compose service status$(COLOR_OFF)"
	@# Ensure we have a compose command available
	@if [ -z "$(DOCKER_COMPOSE)" ]; then echo "Neither 'docker compose' nor 'docker-compose' was found; please install Docker Compose."; exit 1; fi
	@SERVICES="stt bot"; \
	FAILED=0; \
	for svc in $$SERVICES; do \
		CID=`$(DOCKER_COMPOSE) ps -q $$svc 2>/dev/null || true`; \
		if [ -z "$$CID" ]; then \
			echo "$$svc: no container"; \
			FAILED=1; \
			continue; \
		fi; \
		STATUS=`docker inspect -f '{{.State.Status}}' $$CID 2>/dev/null || echo unknown`; \
		if [ "$$STATUS" != "running" ]; then \
			echo "$$svc: $$STATUS"; \
			FAILED=1; \
		else \
			echo "$$svc: running"; \
		fi; \
	done; \
	if [ $$FAILED -eq 0 ]; then \
		echo -e "$(COLOR_GREEN)→ All services running$(COLOR_OFF)"; exit 0; \
	else \
		echo -e "$(COLOR_RED)→ Some services not running$(COLOR_OFF)"; exit 2; \
	fi
