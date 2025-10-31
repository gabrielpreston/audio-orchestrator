SHELL := /bin/bash

# =============================================================================
# PHONY TARGETS
# =============================================================================
.PHONY: all help
.PHONY: run stop logs logs-dump docker-status
.PHONY: docker-build docker-build-service docker-build-base docker-restart docker-shell docker-config
.PHONY: docker-buildx-setup docker-buildx-reset
.PHONY: docker-pull-images docker-warm-cache
.PHONY: test test-image test-image-force test-unit test-component test-integration test-observability test-observability-full
.PHONY: lint lint-image lint-image-force lint-fix
.PHONY: security security-image security-image-force
.PHONY: clean docker-clean docker-clean-all
.PHONY: docs-verify validate-changes
.PHONY: rotate-tokens rotate-tokens-dry-run validate-tokens
.PHONY: models-download models-clean

# =============================================================================
# CONFIGURATION & VARIABLES
# =============================================================================

# Color support detection and definitions
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

# Docker Compose (v2) command
DOCKER_COMPOSE := docker compose

# Docker BuildKit configuration
DOCKER_BUILDKIT ?= 1
COMPOSE_DOCKER_CLI_BUILD ?= 1

# Docker build command — standardize on buildx for local builds
DOCKER_BUILD_CMD ?= docker buildx build

# Ensure a buildx builder exists and is selected
BUILDX_BUILDER_NAME ?= ao-builder

# Docker build optimization helpers
define image_exists
@docker image inspect $(1) >/dev/null 2>&1 && echo "true" || echo "false"
endef

# Helper to ensure Docker is authenticated to GHCR
# Priority: GHCR_TOKEN > GitHub CLI
define ensure_docker_ghcr_auth
if ! (docker pull ghcr.io/gabrielpreston/cache:services >/dev/null 2>&1 && \
      docker push ghcr.io/gabrielpreston/cache:services >/dev/null 2>&1) 2>/dev/null; then \
    printf "$(COLOR_CYAN)→ Authenticating Docker to GHCR...$(COLOR_OFF)\n"; \
    if [ -n "$${GHCR_TOKEN:-}" ]; then \
        GHCR_USER=$${GHCR_USERNAME:-$$(gh api user --jq .login 2>/dev/null || echo $$(whoami))}; \
        echo "$${GHCR_TOKEN}" | docker login ghcr.io -u "$${GHCR_USER}" --password-stdin 2>/dev/null || \
            { printf "$(COLOR_RED)→ Error: Failed to authenticate Docker to GHCR using GHCR_TOKEN$(COLOR_OFF)\n"; exit 1; }; \
    elif command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then \
        echo $$(gh auth token) | docker login ghcr.io -u $$(gh api user --jq .login 2>/dev/null || echo $$(whoami)) --password-stdin 2>/dev/null || \
            { printf "$(COLOR_RED)→ Error: Failed to authenticate Docker to GHCR$(COLOR_OFF)\n"; exit 1; }; \
    else \
        printf "$(COLOR_RED)→ Error: Cannot authenticate to GHCR. Either:\n$(COLOR_OFF)"; \
        printf "  1. Set GHCR_TOKEN environment variable (with write:packages scope)\n"; \
        printf "  2. Authenticate GitHub CLI: gh auth login --scopes write:packages\n"; \
        exit 1; \
    fi; \
fi
endef

define build_if_missing
@if [ "$$(docker image inspect $(1) >/dev/null 2>&1 && echo "true" || echo "false")" = "false" ]; then \
    printf "$(COLOR_YELLOW)→ Building $(1) (not found)$(COLOR_OFF)\n"; \
    $(call ensure_docker_ghcr_auth); \
    DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) $(DOCKER_BUILD_CMD) \
        --tag $(1) \
        --cache-from type=registry,ref=ghcr.io/gabrielpreston/cache:services \
        --build-arg BUILDKIT_INLINE_CACHE=1 \
        --load \
        -f $(2) . || exit 1; \
    printf "$(COLOR_CYAN)→ Pushing $(1) to registry and exporting cache...$(COLOR_OFF)\n"; \
    docker push $(1) || exit 1; \
    DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) $(DOCKER_BUILD_CMD) \
        --tag $(1) \
        --cache-from type=registry,ref=ghcr.io/gabrielpreston/cache:services \
        --cache-to type=registry,ref=ghcr.io/gabrielpreston/cache:services,mode=max \
        --build-arg BUILDKIT_INLINE_CACHE=1 \
        -f $(2) . --push || exit 1; \
else \
    printf "$(COLOR_GREEN)→ Using existing $(1)$(COLOR_OFF)\n"; \
fi
endef

define build_with_cache
@printf "$(COLOR_CYAN)→ Building $(1) with registry caching$(COLOR_OFF)\n"; \
$(call ensure_docker_ghcr_auth); \
DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) $(DOCKER_BUILD_CMD) \
    --tag $(1) \
    --cache-from type=registry,ref=ghcr.io/gabrielpreston/cache:services \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    --load \
    -f $(2) . || exit 1; \
printf "$(COLOR_CYAN)→ Pushing $(1) to registry and exporting cache...$(COLOR_OFF)\n"; \
docker push $(1) || exit 1; \
DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) $(DOCKER_BUILD_CMD) \
    --tag $(1) \
    --cache-from type=registry,ref=ghcr.io/gabrielpreston/cache:services \
    --cache-to type=registry,ref=ghcr.io/gabrielpreston/cache:services,mode=max \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    -f $(2) . --push || exit 1
endef

define build_service_with_enhanced_cache
@printf "$(COLOR_CYAN)→ Building $(1) with enhanced caching$(COLOR_OFF)\n"; \
$(call ensure_docker_ghcr_auth); \
DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) $(DOCKER_BUILD_CMD) \
    --tag $(1) \
    --cache-from type=registry,ref=ghcr.io/gabrielpreston/cache:services \
    --cache-from type=registry,ref=ghcr.io/gabrielpreston/cache:base-images \
    --cache-to type=registry,ref=ghcr.io/gabrielpreston/cache:services,mode=max \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    --load \
    --push \
    -f $(2) .
endef

# Source paths and file discovery
PYTHON_SOURCES := services
MYPY_PATHS ?= services
DOCKERFILES := $(shell find services -type f -name 'Dockerfile' 2>/dev/null)
YAML_FILES := docker-compose.yml $(shell find .github/workflows -type f -name '*.yaml' -o -name '*.yml' 2>/dev/null)
MARKDOWN_FILES := README.md AGENTS.md $(shell find docs -type f -name '*.md' 2>/dev/null)

# Container images and paths
LINT_IMAGE ?= ghcr.io/gabrielpreston/lint:latest
LINT_DOCKERFILE := services/linter/Dockerfile
LINT_WORKDIR := /workspace
TEST_IMAGE ?= ghcr.io/gabrielpreston/test:latest
TEST_DOCKERFILE := services/tester/Dockerfile
TEST_WORKDIR := /workspace
SECURITY_IMAGE ?= ghcr.io/gabrielpreston/security:latest
SECURITY_DOCKERFILE := services/security/Dockerfile
SECURITY_WORKDIR := /workspace

# Test configuration
PYTEST_ARGS ?=

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

# Helper function for Docker container execution
define run_docker_container
@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker." >&2; exit 1; }
@docker run --rm \
	-u $$(id -u):$$(id -g) \
	-e HOME=$(2) \
	-e USER=$$(id -un 2>/dev/null || echo user) \
	$(if $(strip $(PYTEST_ARGS)),-e PYTEST_ARGS="$(PYTEST_ARGS)",) \
	-v "$(CURDIR)":$(2) \
	$(1) \
	$(3)
endef

# Dynamic service discovery
SERVICES := $(shell find services -maxdepth 1 -type d -not -name services | sed 's/services\///' | sort)
VALID_SERVICES := $(shell echo "$(SERVICES)" | tr '\n' ' ')

# Runtime services (excludes tooling services like linter, tester, security)
RUNTIME_SERVICES := discord stt flan orchestrator bark audio monitoring testing

# =============================================================================
# DEFAULT TARGETS
# =============================================================================

all: help ## Default aggregate target

help: ## Show this help (default)
	@printf "$(COLOR_CYAN)audio-orchestrator Makefile — handy targets$(COLOR_OFF)\n"
	@echo
	@echo "Usage: make <target>"
	@echo
	@awk 'BEGIN {FS = ":.*## "} /^[^[:space:]#].*:.*##/ { printf "  %-14s - %s\n", $$1, $$2 }' $(MAKEFILE_LIST) 2>/dev/null || true

.DEFAULT_GOAL := help

# =============================================================================
# APPLICATION LIFECYCLE
# =============================================================================

run: stop ## Start docker-compose stack (Discord bot + STT + LLM + orchestrator)
	@printf "$(COLOR_GREEN)→ Starting containers with cached images$(COLOR_OFF)\n"
	@DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) COMPOSE_DOCKER_CLI_BUILD=$(COMPOSE_DOCKER_CLI_BUILD) $(DOCKER_COMPOSE) up -d --remove-orphans

run-with-build: docker-build-enhanced run ## Build with caching then start containers

stop: ## Stop and remove containers for the compose stack
	@printf "$(COLOR_BLUE)→ Bringing down containers$(COLOR_OFF)\n"
	@$(DOCKER_COMPOSE) down --remove-orphans

logs: ## Tail logs for compose services (set SERVICE=name to filter)
	@printf "$(COLOR_CYAN)→ Tailing logs for docker services (Ctrl+C to stop)$(COLOR_OFF)\n"; \
	if [ -z "$(SERVICE)" ]; then $(DOCKER_COMPOSE) logs -f --tail=100; else $(DOCKER_COMPOSE) logs -f --tail=100 $(SERVICE); fi

logs-dump: ## Capture docker logs to ./docker.logs
	@printf "$(COLOR_CYAN)→ Dumping all logs for docker services$(COLOR_OFF)\n"
	@$(DOCKER_COMPOSE) logs > ./debug/docker.logs

docker-status: ## Show status of docker-compose services
	@$(DOCKER_COMPOSE) ps

# =============================================================================
# DOCKER BUILD & MANAGEMENT
# =============================================================================

# Buildx setup
.PHONY: docker-buildx-setup
docker-buildx-setup: ## Create/select a local buildx builder if missing
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker." >&2; exit 1; }
	@if ! docker buildx ls | grep -q "^$(BUILDX_BUILDER_NAME)"; then \
		echo "Creating buildx builder: $(BUILDX_BUILDER_NAME)"; \
		docker buildx create --use --name $(BUILDX_BUILDER_NAME); \
	else \
		echo "Using buildx builder: $(BUILDX_BUILDER_NAME)"; \
		docker buildx use $(BUILDX_BUILDER_NAME); \
	fi

docker-buildx-reset: ## Reset local buildx/buildkit after Docker Desktop crash
	@printf "$(COLOR_YELLOW)→ Resetting buildx/buildkit (builder: $(BUILDX_BUILDER_NAME))$(COLOR_OFF)\n"
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker." >&2; exit 1; }
	@docker buildx ls || true
	@docker buildx stop $(BUILDX_BUILDER_NAME) || true
	@docker buildx rm -f $(BUILDX_BUILDER_NAME) || true
	@docker builder prune -a -f || true
	@docker ps -a --filter name=buildx_buildkit_ -q | xargs -r docker rm -f || true
	@docker buildx create --use --name $(BUILDX_BUILDER_NAME) --driver docker-container
	@docker buildx inspect --bootstrap

docker-build: docker-buildx-setup ## Build or rebuild images for the compose stack (smart incremental by default)
	@printf "$(COLOR_GREEN)→ Building docker images (smart incremental)$(COLOR_OFF)\n"
	@bash scripts/build-incremental.sh

docker-build-enhanced: ## Build with enhanced multi-source caching (GitHub Actions + registry)
	@printf "$(COLOR_GREEN)→ Building docker images with enhanced caching$(COLOR_OFF)\n"
	@$(call ensure_docker_ghcr_auth)
	@DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) COMPOSE_DOCKER_CLI_BUILD=$(COMPOSE_DOCKER_CLI_BUILD) $(DOCKER_COMPOSE) build --parallel


docker-build-service: ## Build a specific service (set SERVICE=name)
	@if [ -z "$(SERVICE)" ]; then \
		echo "Set SERVICE=<service-name> ($(RUNTIME_SERVICES))"; \
		exit 1; \
	fi
	@if ! echo "$(RUNTIME_SERVICES)" | grep -q "\b$(SERVICE)\b"; then \
		echo "Invalid service: $(SERVICE). Valid services: $(RUNTIME_SERVICES)"; \
		exit 1; \
	fi
	@printf "$(COLOR_GREEN)→ Building $(SERVICE) service$(COLOR_OFF)\n"
	@DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) COMPOSE_DOCKER_CLI_BUILD=$(COMPOSE_DOCKER_CLI_BUILD) $(DOCKER_COMPOSE) build $(SERVICE)

docker-build-base: ## Build base images (python-web, python-ml, python-audio, tools)
	@printf "$(COLOR_GREEN)→ Building base images$(COLOR_OFF)\n"
	@bash scripts/build-base-images.sh

docker-build-wheels: ## Build and cache wheels for native dependencies
	@printf "$(COLOR_GREEN)→ Building wheels for native dependencies$(COLOR_OFF)\n"
	@bash scripts/build-wheels.sh

docker-restart: ## Restart compose services (set SERVICE=name to limit scope)
	@printf "$(COLOR_BLUE)→ Restarting docker services$(COLOR_OFF)\n"
	@if [ -z "$(SERVICE)" ]; then \
	$(DOCKER_COMPOSE) restart; \
	else \
	$(DOCKER_COMPOSE) restart $(SERVICE); \
	fi

docker-shell: ## Open an interactive shell inside a running service (SERVICE=name)
	@if [ -z "$(SERVICE)" ]; then \
		echo "Set SERVICE=<service-name> ($(RUNTIME_SERVICES))"; \
		exit 1; \
	fi
	@if ! echo "$(RUNTIME_SERVICES)" | grep -q "\b$(SERVICE)\b"; then \
		echo "Invalid service: $(SERVICE). Valid services: $(RUNTIME_SERVICES)"; \
		exit 1; \
	fi
	@$(DOCKER_COMPOSE) exec $(SERVICE) /bin/bash

docker-config: ## Render the effective docker-compose configuration
	@$(DOCKER_COMPOSE) config


# =============================================================================
# DOCKER IMAGE PULL (CACHE WARMUP)
# =============================================================================

docker-pull-images: ## Pre-pull images for all compose files and toolchain (cache warmup)
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker." >&2; exit 1; }
	@printf "$(COLOR_GREEN)→ Pulling images defined in docker-compose files$(COLOR_OFF)\n"
	@for f in docker-compose.yml docker-compose.test.yml docker-compose.observability-test.yml docker-compose.ci.yml; do \
		if [ -f "$$f" ]; then \
			printf "$(COLOR_CYAN)→ Pulling images from %s$(COLOR_OFF)\n" "$$f"; \
			$(DOCKER_COMPOSE) -f "$$f" pull --ignore-pull-failures || true; \
		fi; \
	 done
	@printf "$(COLOR_GREEN)→ Pulling toolchain images$(COLOR_OFF)\n"
	@for img in $(LINT_IMAGE) $(TEST_IMAGE) $(SECURITY_IMAGE); do \
		printf "Pulling %s\n" "$$img"; \
		docker pull "$$img" || true; \
	 done
	@printf "$(COLOR_GREEN)→ Docker cache warmup complete$(COLOR_OFF)\n"

docker-warm-cache: docker-pull-images ## Alias: warm Docker cache by downloading images first

# =============================================================================
# TESTING
# =============================================================================

test: test-unit test-component ## Run unit and component tests (fast, reliable)



test-image-force: ## Force rebuild the test toolchain container image
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to build test container images." >&2; exit 1; }
	@printf "$(COLOR_YELLOW)→ Force rebuilding $(TEST_IMAGE)$(COLOR_OFF)\n"
	$(call build_with_cache,$(TEST_IMAGE),$(TEST_DOCKERFILE))

lint-image-force: ## Force rebuild the lint toolchain container image (no cache)
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to build lint container images." >&2; exit 1; }
	@printf "$(COLOR_YELLOW)→ Force rebuilding $(LINT_IMAGE) (no cache)$(COLOR_OFF)\n"
	@docker rmi $(LINT_IMAGE) 2>/dev/null || true
	@$(call ensure_docker_ghcr_auth); \
	DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) $(DOCKER_BUILD_CMD) \
		--tag $(LINT_IMAGE) \
		--no-cache \
		--build-arg BUILDKIT_INLINE_CACHE=1 \
		--load \
		-f $(LINT_DOCKERFILE) . || exit 1; \
	printf "$(COLOR_CYAN)→ Pushing $(LINT_IMAGE) to registry...$(COLOR_OFF)\n"; \
	docker push $(LINT_IMAGE) || exit 1; \
	DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) $(DOCKER_BUILD_CMD) \
		--tag $(LINT_IMAGE) \
		--no-cache \
		--cache-to type=registry,ref=ghcr.io/gabrielpreston/cache:services,mode=max \
		--build-arg BUILDKIT_INLINE_CACHE=1 \
		-f $(LINT_DOCKERFILE) . --push || exit 1

security-image-force: ## Force rebuild the security scanning container image
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to build security container images." >&2; exit 1; }
	@printf "$(COLOR_YELLOW)→ Force rebuilding $(SECURITY_IMAGE)$(COLOR_OFF)\n"
	$(call build_with_cache,$(SECURITY_IMAGE),$(SECURITY_DOCKERFILE))

test-image: ## Build the test toolchain container image (only if missing)
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to build test container images." >&2; exit 1; }
	$(call build_if_missing,$(TEST_IMAGE),$(TEST_DOCKERFILE))


# Test categories
test-unit: test-image ## Run unit tests (fast, isolated)
	@printf "$(COLOR_CYAN)→ Running unit tests$(COLOR_OFF)\n"
	$(call run_docker_container,$(TEST_IMAGE),$(TEST_WORKDIR),pytest -m unit $(PYTEST_ARGS))

test-component: test-image ## Run component tests (with mocked external dependencies)
	@printf "$(COLOR_CYAN)→ Running component tests$(COLOR_OFF)\n"
	$(call run_docker_container,$(TEST_IMAGE),$(TEST_WORKDIR),pytest -m component $(PYTEST_ARGS))

test-integration: test-image ## Run integration tests (requires Docker Compose)
	@printf "$(COLOR_CYAN)→ Running integration tests with Docker Compose$(COLOR_OFF)\n"
	@printf "$(COLOR_YELLOW)→ Building test services$(COLOR_OFF)\n"
	@$(DOCKER_COMPOSE) -f docker-compose.test.yml build
	@printf "$(COLOR_YELLOW)→ Starting test services$(COLOR_OFF)\n"
	@$(DOCKER_COMPOSE) -f docker-compose.test.yml up -d
	@printf "$(COLOR_YELLOW)→ Running integration tests$(COLOR_OFF)\n"
	@docker run --rm \
		--network audio-orchestrator-test \
		-u $$(id -u):$$(id -g) \
		-e HOME=$(TEST_WORKDIR) \
		-e USER=$$(id -un 2>/dev/null || echo tester) \
		$(if $(strip $(PYTEST_ARGS)),-e PYTEST_ARGS="$(PYTEST_ARGS)",) \
		-v "$(CURDIR)":$(TEST_WORKDIR) \
		$(TEST_IMAGE) \
		pytest -m integration $(PYTEST_ARGS) || { \
			status=$$?; \
			printf "$(COLOR_YELLOW)→ Stopping test services$(COLOR_OFF)\n"; \
			$(DOCKER_COMPOSE) -f docker-compose.test.yml down -v; \
			exit $$status; \
		}
	@printf "$(COLOR_YELLOW)→ Stopping test services$(COLOR_OFF)\n"
	@$(DOCKER_COMPOSE) -f docker-compose.test.yml down -v

test-observability: test-image ## Run observability stack integration tests
	@printf "$(COLOR_CYAN)→ Running observability stack tests$(COLOR_OFF)\n"
	@printf "$(COLOR_YELLOW)→ Building observability test services$(COLOR_OFF)\n"
	@$(DOCKER_COMPOSE) -f docker-compose.observability-test.yml build
	@printf "$(COLOR_YELLOW)→ Starting observability stack$(COLOR_OFF)\n"
	@$(DOCKER_COMPOSE) -f docker-compose.observability-test.yml up -d
	@printf "$(COLOR_YELLOW)→ Running observability tests$(COLOR_OFF)\n"
	@docker run --rm \
		--network audio-orchestrator-observability-test \
		-u $$(id -u):$$(id -g) \
		-e HOME=$(TEST_WORKDIR) \
		-e USER=$$(id -un 2>/dev/null || echo tester) \
		$(if $(strip $(PYTEST_ARGS)),-e PYTEST_ARGS="$(PYTEST_ARGS)",) \
		-v "$(CURDIR)":$(TEST_WORKDIR) \
		$(TEST_IMAGE) \
		pytest services/tests/integration/observability/ $(PYTEST_ARGS) || { \
			status=$$?; \
			printf "$(COLOR_YELLOW)→ Stopping observability services$(COLOR_OFF)\n"; \
			$(DOCKER_COMPOSE) -f docker-compose.observability-test.yml down -v; \
			exit $$status; \
		}
	@printf "$(COLOR_YELLOW)→ Stopping observability services$(COLOR_OFF)\n"
	@$(DOCKER_COMPOSE) -f docker-compose.observability-test.yml down -v

test-observability-full: test-image ## Run full observability stack with application services
	@printf "$(COLOR_CYAN)→ Running full observability stack tests$(COLOR_OFF)\n"
	@printf "$(COLOR_YELLOW)→ Building all services$(COLOR_OFF)\n"
	@$(DOCKER_COMPOSE) build
	@printf "$(COLOR_YELLOW)→ Starting full stack with observability$(COLOR_OFF)\n"
	@$(DOCKER_COMPOSE) up -d
	@printf "$(COLOR_YELLOW)→ Waiting for services to be ready$(COLOR_OFF)\n"
	@sleep 30
	@printf "$(COLOR_YELLOW)→ Running observability tests$(COLOR_OFF)\n"
	@docker run --rm \
		--network audio-orchestrator_default \
		-u $$(id -u):$$(id -g) \
		-e HOME=$(TEST_WORKDIR) \
		-e USER=$$(id -un 2>/dev/null || echo tester) \
		$(if $(strip $(PYTEST_ARGS)),-e PYTEST_ARGS="$(PYTEST_ARGS)",) \
		-v "$(CURDIR)":$(TEST_WORKDIR) \
		$(TEST_IMAGE) \
		pytest services/tests/integration/observability/ $(PYTEST_ARGS) || { \
			status=$$?; \
			printf "$(COLOR_YELLOW)→ Stopping full stack$(COLOR_OFF)\n"; \
			$(DOCKER_COMPOSE) down -v; \
			exit $$status; \
		}
	@printf "$(COLOR_YELLOW)→ Stopping full stack$(COLOR_OFF)\n"
	@$(DOCKER_COMPOSE) down -v


# =============================================================================
# LINTING & CODE QUALITY
# =============================================================================

# =============================================================================
# LINTING TARGETS
# =============================================================================

lint: lint-image ## Run all linters (validation only)
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker." >&2; exit 1; }
	@docker run --rm -u $$(id -u):$$(id -g) -e HOME=$(LINT_WORKDIR) \
		-e USER=$$(id -un 2>/dev/null || echo lint) \
		-v "$(CURDIR)":$(LINT_WORKDIR) $(LINT_IMAGE) \
		bash $(LINT_WORKDIR)/services/linter/run-lint.sh

lint-image: ## Build the lint toolchain container image (only if missing)
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to build lint container images." >&2; exit 1; }
	$(call build_if_missing,$(LINT_IMAGE),$(LINT_DOCKERFILE))

lint-fix: lint-image ## Apply all automatic fixes
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker." >&2; exit 1; }
	@docker run --rm -u $$(id -u):$$(id -g) -e HOME=$(LINT_WORKDIR) \
		-e USER=$$(id -un 2>/dev/null || echo lint) \
		-v "$(CURDIR)":$(LINT_WORKDIR) $(LINT_IMAGE) \
		bash $(LINT_WORKDIR)/services/linter/run-lint-fix.sh


# =============================================================================
# SECURITY & QUALITY GATES
# =============================================================================

security: security-image ## Run security scanning with pip-audit
	@printf "$(COLOR_CYAN)→ Running security scan$(COLOR_OFF)\n"
	$(call run_docker_container,$(SECURITY_IMAGE),$(SECURITY_WORKDIR),)

security-image: ## Build the security scanning container image (only if missing)
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to build security container images." >&2; exit 1; }
	$(call build_if_missing,$(SECURITY_IMAGE),$(SECURITY_DOCKERFILE))


# =============================================================================
# CLEANUP & MAINTENANCE
# =============================================================================

clean: ## Remove logs, cached audio artifacts, and debug files
	@printf "$(COLOR_BLUE)→ Cleaning...$(COLOR_OFF)\n"; \
	if [ -d "logs" ]; then echo "Removing logs in ./logs"; rm -rf logs/* || true; fi; \
	if [ -d ".wavs" ]; then echo "Removing saved wavs/sidecars in ./.wavs"; rm -rf .wavs/* || true; fi; \
	if [ -d "debug" ]; then echo "Removing debug files in ./debug"; rm -rf debug/* || true; fi; \
	if [ -d "services" ]; then echo "Removing __pycache__ directories under ./services"; find services -type d -name "__pycache__" -prune -print -exec rm -rf {} + || true; fi

docker-clean: ## Clean unused Docker resources (safe - preserves images/volumes in use)
	@printf "$(COLOR_BLUE)→ Cleaning unused Docker resources (safe mode)...$(COLOR_OFF)\n"
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; skipping docker prune."; exit 0; }
	@echo "Removing stopped containers, dangling images, unused networks, and build cache..."
	@docker system prune -f

docker-clean-all: ## Nuclear cleanup: stop compose stack, remove ALL images/volumes/networks
	@printf "$(COLOR_RED)⚠️  WARNING: Aggressive cleanup - removes ALL images and volumes$(COLOR_OFF)\n"
	@$(DOCKER_COMPOSE) down --rmi all -v --remove-orphans || true
	@docker system prune -a -f --volumes || true

# =============================================================================
# DOCUMENTATION & UTILITIES
# =============================================================================

docs-verify: ## Validate documentation last-updated metadata and indexes
	@./scripts/verify_last_updated.py --allow-divergence $(ARGS)

validate-changes: ## Validate uncommitted changes (lint, tests); use ARGS='--verbose' to customize
	@bash scripts/validate-changes.sh $(ARGS)

# Token management
rotate-tokens: ## Rotate AUTH_TOKEN values across all environment files
	@printf "$(COLOR_CYAN)→ Rotating AUTH_TOKEN values$(COLOR_OFF)\n"
	@./scripts/rotate_auth_tokens.py

rotate-tokens-dry-run: ## Show what token rotation would change without modifying files
	@printf "$(COLOR_CYAN)→ Dry run: AUTH_TOKEN rotation preview$(COLOR_OFF)\n"
	@./scripts/rotate_auth_tokens.py --dry-run

validate-tokens: ## Validate AUTH_TOKEN consistency across environment files
	@printf "$(COLOR_CYAN)→ Validating AUTH_TOKEN consistency$(COLOR_OFF)\n"
	@./scripts/rotate_auth_tokens.py --validate-only

# Model management
models-download: ## Download required models to ./services/models/ subdirectories
	@printf "$(COLOR_GREEN)→ Downloading models to ./services/models/$(COLOR_OFF)\n"
	@mkdir -p ./services/models/llm ./services/models/tts ./services/models/stt
	@echo "Downloading LLM model (llama-2-7b.Q4_K_M.gguf)..."
	@if [ ! -f "./services/models/llm/llama-2-7b.Q4_K_M.gguf" ]; then \
		wget -O ./services/models/llm/llama-2-7b.Q4_K_M.gguf \
		"https://huggingface.co/TheBloke/Llama-2-7B-GGUF/resolve/main/llama-2-7b.Q4_K_M.gguf" || \
		echo "Failed to download LLM model. You may need to download it manually."; \
	else \
		echo "LLM model already exists, skipping download."; \
	fi
	@echo "Downloading TTS model (en_US-amy-medium)..."
	@if [ ! -f "./services/models/tts/en_US-amy-medium.onnx" ]; then \
		wget -O ./services/models/tts/en_US-amy-medium.onnx \
		"https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx" || \
		echo "Failed to download TTS model. You may need to download it manually."; \
	else \
		echo "TTS model already exists, skipping download."; \
	fi
	@if [ ! -f "./services/models/tts/en_US-amy-medium.onnx.json" ]; then \
		wget -O ./services/models/tts/en_US-amy-medium.onnx.json \
		"https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx.json" || \
		echo "Failed to download TTS model config. You may need to download it manually."; \
	else \
		echo "TTS model config already exists, skipping download."; \
	fi
	@echo "Downloading STT model (faster-whisper medium.en)..."
	@if [ ! -d "./services/models/stt/medium.en" ]; then \
		mkdir -p ./services/models/stt/medium.en; \
		wget -O ./services/models/stt/medium.en/config.json \
		"https://huggingface.co/Systran/faster-whisper-medium.en/resolve/main/config.json" || \
		echo "Failed to download STT model config."; \
		wget -O ./services/models/stt/medium.en/model.bin \
		"https://huggingface.co/Systran/faster-whisper-medium.en/resolve/main/model.bin" || \
		echo "Failed to download STT model weights."; \
		wget -O ./services/models/stt/medium.en/tokenizer.json \
		"https://huggingface.co/Systran/faster-whisper-medium.en/resolve/main/tokenizer.json" || \
		echo "Failed to download STT tokenizer."; \
		wget -O ./services/models/stt/medium.en/vocabulary.txt \
		"https://huggingface.co/Systran/faster-whisper-medium.en/resolve/main/vocabulary.txt" || \
		echo "Failed to download STT vocabulary."; \
	else \
		echo "STT model already exists, skipping download."; \
	fi
	@echo "Downloading FLAN-T5 model (flan-t5-large)..."
	@if [ ! -d "./services/models/flan-t5" ]; then \
		mkdir -p ./services/models/flan-t5; \
		python3 scripts/download_flan_t5.py large || \
		echo "Failed to download FLAN-T5 model. You may need to download it manually."; \
	else \
		echo "FLAN-T5 model already exists, skipping download."; \
	fi
	@printf "$(COLOR_GREEN)→ Model download complete$(COLOR_OFF)\n"
	@echo "Models downloaded to:"
	@echo "  - LLM: ./services/models/llm/llama-2-7b.Q4_K_M.gguf"
	@echo "  - TTS: ./services/models/tts/en_US-amy-medium.onnx"
	@echo "  - TTS: ./services/models/tts/en_US-amy-medium.onnx.json"
	@echo "  - STT: ./services/models/stt/medium.en/"
	@echo "  - FLAN-T5: ./services/models/flan-t5/"

models-clean: ## Remove downloaded models from ./services/models/
	@printf "$(COLOR_RED)→ Cleaning downloaded models$(COLOR_OFF)\n"
	@if [ -d "./services/models" ]; then \
		echo "Removing models from ./services/models/"; \
		rm -rf ./services/models/* || true; \
		echo "Models cleaned."; \
	else \
		echo "No models directory found."; \
	fi
