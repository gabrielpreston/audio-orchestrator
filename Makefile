SHELL := /bin/bash

# =============================================================================
# PHONY TARGETS
# =============================================================================
.PHONY: all help
.PHONY: run stop logs logs-follow logs-dump docker-status run-with-build run-test-env stop-test-env restart docker-shell docker-config
.PHONY: docker-buildx-setup docker-buildx-reset
.PHONY: docker-build docker-build-services-parallel docker-build-service docker-build-base docker-build-wheels
.PHONY: docker-push-base-images docker-push-services docker-push-all
.PHONY: docker-pull-images docker-warm-cache
.PHONY: test test-unit test-component test-integration test-unit-service test-component-service
.PHONY: build-test-image build-test-image-force push-test-image push-test-image-force
.PHONY: lint build-lint-image build-lint-image-force push-lint-image push-lint-image-force lint-fix
.PHONY: security build-security-image build-security-image-force push-security-image push-security-image-force
.PHONY: check-syntax
.PHONY: clean docker-clean docker-clean-all
.PHONY: docs-verify validate-changes
.PHONY: rotate-tokens rotate-tokens-dry-run validate-tokens
.PHONY: models-clean models-force-download models-force-download-service models-fix-permissions

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

# Registry configuration
REGISTRY ?= ghcr.io/gabrielpreston
CACHE_SERVICES_REF := $(REGISTRY)/cache:services
CACHE_BASE_IMAGES_REF := $(REGISTRY)/cache:base-images

# Docker push control (0 = local-only, 1 = push to registry)
# Default to local-only builds to avoid requiring authentication
DOCKER_PUSH ?= 0

# Script directory
SCRIPT_DIR := $(CURDIR)/scripts

# Container images and paths
LINT_IMAGE ?= $(REGISTRY)/lint:latest
LINT_DOCKERFILE := services/linter/Dockerfile
LINT_WORKDIR := /workspace
TEST_IMAGE ?= $(REGISTRY)/test:latest
TEST_DOCKERFILE := services/tester/Dockerfile
TEST_WORKDIR := /workspace
SECURITY_IMAGE ?= $(REGISTRY)/security:latest
SECURITY_DOCKERFILE := services/security/Dockerfile
SECURITY_WORKDIR := /workspace
WAKE_TRAINER_IMAGE ?= $(REGISTRY)/waketrainer:latest
WAKE_TRAINER_DOCKERFILE := services/waketrainer/Dockerfile
WAKE_TRAINER_WORKDIR := /workspace

# Test configuration
PYTEST_ARGS ?=

# Dynamic service discovery
SERVICES := $(shell find services -maxdepth 1 -type d -not -name services | sed 's/services\///' | sort)

# Development services (excludes observability stack)
DEV_SERVICES := discord stt flan orchestrator bark testing guardrails

# Production services only (excludes testing and observability stack)
PROD_SERVICES := discord stt flan orchestrator bark guardrails

# All services (excludes observability stack)
ALL_SERVICES := discord stt flan orchestrator bark testing guardrails

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

# Helper to ensure Docker is authenticated to GHCR
# Priority: GHCR_TOKEN > GitHub CLI
define ensure_docker_ghcr_auth
if ! (docker pull $(CACHE_SERVICES_REF) >/dev/null 2>&1 && \
      docker push $(CACHE_SERVICES_REF) >/dev/null 2>&1) 2>/dev/null; then \
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

# Build image only if it doesn't exist locally
# Conditionally pushes based on DOCKER_PUSH variable (0 = local-only, 1 = push)
define build_if_missing
@if [ "$$(docker image inspect $(1) >/dev/null 2>&1 && echo "true" || echo "false")" = "false" ]; then \
    printf "$(COLOR_YELLOW)→ Building $(1) (not found)$(COLOR_OFF)\n"; \
    if [ "$(DOCKER_PUSH)" = "1" ]; then \
        $(call ensure_docker_ghcr_auth); \
        CACHE_TO_ARG="--cache-to type=registry,ref=$(CACHE_SERVICES_REF),mode=max"; \
        PUSH_ARG="--push"; \
    else \
        CACHE_TO_ARG="--cache-to type=local,dest=/tmp/.buildkit-cache"; \
        PUSH_ARG=""; \
    fi; \
    DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) $(DOCKER_BUILD_CMD) \
        --tag $(1) \
        --cache-from type=registry,ref=$(CACHE_SERVICES_REF) \
        $$CACHE_TO_ARG \
        --build-arg BUILDKIT_INLINE_CACHE=1 \
        --load \
        $$PUSH_ARG \
        -f $(2) . || exit 1; \
else \
    printf "$(COLOR_GREEN)→ Using existing $(1)$(COLOR_OFF)\n"; \
fi
endef

# Build image with registry caching (always builds)
# Conditionally pushes based on DOCKER_PUSH variable (0 = local-only, 1 = push)
# $(1)=image, $(2)=dockerfile, $(3)=additional cache-from refs (optional)
define build_with_registry_cache
@if [ "$(DOCKER_PUSH)" = "1" ]; then \
    $(call ensure_docker_ghcr_auth); \
    CACHE_TO_ARG="--cache-to type=registry,ref=$(CACHE_SERVICES_REF),mode=max"; \
    PUSH_ARG="--push"; \
else \
    CACHE_TO_ARG="--cache-to type=local,dest=/tmp/.buildkit-cache"; \
    PUSH_ARG=""; \
fi; \
DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) $(DOCKER_BUILD_CMD) \
    --tag $(1) \
    --cache-from type=registry,ref=$(CACHE_SERVICES_REF) \
    $(shell [ -n "$(3)" ] && echo "--cache-from type=registry,ref=$(3)") \
    $$CACHE_TO_ARG \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    --load \
    $$PUSH_ARG \
    -f $(2) . || exit 1
endef

# Push existing image to registry
# $(1)=image
define push_image
@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker." >&2; exit 1; }
@if ! docker image inspect $(1) >/dev/null 2>&1; then \
    printf "$(COLOR_RED)→ Error: Image $(1) not found locally. Build it first with 'make <image-target>'$(COLOR_OFF)\n"; \
    exit 1; \
fi
@printf "$(COLOR_YELLOW)→ Pushing $(1)$(COLOR_OFF)\n"; \
$(call ensure_docker_ghcr_auth); \
docker push $(1) || { \
    printf "$(COLOR_RED)→ Error: Failed to push $(1)$(COLOR_OFF)\n"; \
    exit 1; \
}
endef

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

# Custom function for wake trainer with additional volume mounts for models
# Optimized for GPU training with increased CPU, memory, and shared memory limits
define run_wake_trainer_container
@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker." >&2; exit 1; }
@mkdir -p "$(CURDIR)/services/models/wake/piper-models"
@mkdir -p "$(CURDIR)/services/models/wake/infrastructure"
@docker run --rm \
	--gpus all \
	--cpus="9" \
	--memory="24G" \
	--shm-size="16g" \
	--ipc=host \
	-u $$(id -u):$$(id -g) \
	-e HOME=$(2) \
	-e USER=$$(id -un 2>/dev/null || echo user) \
	-e PYTORCH_CUDA_ALLOC_CONF="max_split_size_mb:64,expandable_segments:True,roundup_power2_divisions:2" \
	-e OMP_NUM_THREADS=8 \
	-e MKL_NUM_THREADS=8 \
	-e CUDA_LAUNCH_BLOCKING=0 \
	$(if $(strip $(PYTEST_ARGS)),-e PYTEST_ARGS="$(PYTEST_ARGS)",) \
	-v "$(CURDIR)":$(2) \
	-v "$(CURDIR)/services/models/wake/piper-models:/workspace/piper-sample-generator/models" \
	-v "$(CURDIR)/services/models/wake/infrastructure:/usr/local/lib/python3.11/site-packages/openwakeword/resources/models" \
	$(1) \
	$(3)
endef

# Helper function to select services based on ENV
define select_services_by_env
@ENV=$${ENV:-dev}; \
	if [ "$$ENV" = "prod" ]; then \
		SERVICES="$(PROD_SERVICES)"; \
		ENV_NAME="production"; \
	elif [ "$$ENV" = "dev" ]; then \
		SERVICES="$(DEV_SERVICES)"; \
		ENV_NAME="development"; \
	else \
		printf "$(COLOR_RED)→ Error: ENV must be 'dev' or 'prod', got: $$ENV$(COLOR_OFF)\n"; \
		exit 1; \
	fi; \
	printf "$(COLOR_GREEN)→ Starting $$ENV_NAME services: $$SERVICES$(COLOR_OFF)\n"; \
	DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) COMPOSE_DOCKER_CLI_BUILD=$(COMPOSE_DOCKER_CLI_BUILD) $(DOCKER_COMPOSE) up -d --remove-orphans $$SERVICES
endef

# =============================================================================
# DEFAULT TARGETS
# =============================================================================

all: help ## Default aggregate target

help: ## Show this help (default)
	@printf "$(COLOR_CYAN)audio-orchestrator Makefile — handy targets$(COLOR_OFF)\n"
	@echo
	@echo "Usage: make <target>"
	@echo
	@awk 'BEGIN {FS = ":.*## "} /^[^[:space:]#].*:.*##/ { printf "  %-20s - %s\n", $$1, $$2 }' $(MAKEFILE_LIST) 2>/dev/null || true

.DEFAULT_GOAL := help

# =============================================================================
# APPLICATION LIFECYCLE
# =============================================================================

models-fix-permissions: ## Fix host model directory permissions (creates directories and sets ownership)
	@printf "$(COLOR_CYAN)→ Ensuring model directories exist with correct permissions$(COLOR_OFF)\n"
	@PUID=$${PUID:-$$(id -u)}; \
	PGID=$${PGID:-$$(id -g)}; \
	for dir in stt flan-t5 guardrails bark wake/detection wake/infrastructure; do \
		full_path="./services/models/$$dir"; \
		if [ ! -d "$$full_path" ]; then \
			printf "$(COLOR_YELLOW)  Creating $$full_path$(COLOR_OFF)\n"; \
			mkdir -p "$$full_path"; \
		fi; \
		current_owner=$$(stat -c '%U:%G' "$$full_path" 2>/dev/null || echo "unknown"); \
		current_uid=$$(stat -c '%u' "$$full_path" 2>/dev/null || echo "0"); \
		if [ "$$current_uid" != "$$PUID" ] && [ "$$current_uid" = "0" ]; then \
			printf "$(COLOR_YELLOW)  Fixing permissions for $$full_path (was $$current_owner, setting to UID $$PUID:$$PGID)$(COLOR_OFF)\n"; \
			sudo chown -R "$$PUID:$$PGID" "$$full_path" 2>/dev/null || \
			( printf "$(COLOR_RED)    Warning: Could not fix permissions (may need sudo)$(COLOR_OFF)\n"; ) ; \
			chmod -R 755 "$$full_path" 2>/dev/null || true; \
		else \
			printf "$(COLOR_GREEN)  ✓ $$full_path permissions OK ($$current_owner)$(COLOR_OFF)\n"; \
		fi; \
	done
	@PUID=$${PUID:-$$(id -u)}; \
	PGID=$${PGID:-$$(id -g)}; \
	bark_cache="./services/models/bark/.cache"; \
	if [ ! -d "$$bark_cache" ]; then \
		printf "$(COLOR_YELLOW)  Creating $$bark_cache for Bark models$(COLOR_OFF)\n"; \
		mkdir -p "$$bark_cache"; \
		current_uid=$$(stat -c '%u' "$$bark_cache" 2>/dev/null || echo "0"); \
		if [ "$$current_uid" = "0" ]; then \
			sudo chown -R "$$PUID:$$PGID" "$$bark_cache" 2>/dev/null || true; \
		fi; \
		chmod -R 755 "$$bark_cache" 2>/dev/null || true; \
	fi

run: stop models-fix-permissions ## Start services (use ENV=dev or ENV=prod, default is dev)
	$(call select_services_by_env)

run-with-build: docker-build-services-parallel run ## Build with enhanced caching then start containers (base images must exist)

run-test-env: stop-test-env models-fix-permissions ## Start all services in test environment using docker-compose.test.yml
	@printf "$(COLOR_GREEN)→ Starting test environment services with docker-compose.test.yml$(COLOR_OFF)\n"
	@DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) COMPOSE_DOCKER_CLI_BUILD=$(COMPOSE_DOCKER_CLI_BUILD) $(DOCKER_COMPOSE) -f docker-compose.test.yml up -d --remove-orphans

stop-test-env: ## Stop and remove test environment containers (deprecated - use 'make stop' for full stack)
	@printf "$(COLOR_BLUE)→ Bringing down test environment containers$(COLOR_OFF)\n"
	@$(DOCKER_COMPOSE) -f docker-compose.test.yml down --remove-orphans

stop: ## Stop and remove containers
	@printf "$(COLOR_BLUE)→ Bringing down containers$(COLOR_OFF)\n"
	@$(DOCKER_COMPOSE) down --remove-orphans

restart: ## Restart compose services (set SERVICE=name to limit scope)
	@printf "$(COLOR_BLUE)→ Restarting docker services$(COLOR_OFF)\n"
	@if [ -z "$(SERVICE)" ]; then $(DOCKER_COMPOSE) restart; else $(DOCKER_COMPOSE) restart $(SERVICE); fi

logs: ## Show logs for compose services (set SERVICE=name to filter)
	@printf "$(COLOR_CYAN)→ Showing logs for docker services$(COLOR_OFF)\n"; \
	if [ -z "$(SERVICE)" ]; then $(DOCKER_COMPOSE) logs --tail=100; else $(DOCKER_COMPOSE) logs --tail=100 $(SERVICE); fi

logs-follow: ## Follow logs for compose services (set SERVICE=name to filter)
	@printf "$(COLOR_CYAN)→ Following logs for docker services (Ctrl+C to stop)$(COLOR_OFF)\n"; \
	if [ -z "$(SERVICE)" ]; then $(DOCKER_COMPOSE) logs -f --tail=100; else $(DOCKER_COMPOSE) logs -f --tail=100 $(SERVICE); fi

logs-dump: ## Capture docker logs to ./debug/docker.logs
	@printf "$(COLOR_CYAN)→ Dumping all logs for docker services$(COLOR_OFF)\n"
	@$(DOCKER_COMPOSE) logs > ./debug/docker.logs

docker-status: ## Show status of docker-compose services
	@$(DOCKER_COMPOSE) ps

docker-shell: ## Open an interactive shell inside a running service (set SERVICE=name)
	@if [ -z "$(SERVICE)" ]; then \
		echo "Set SERVICE=<service-name> ($(ALL_SERVICES))"; \
		exit 1; \
	fi
	@if ! echo "$(ALL_SERVICES)" | grep -q "\b$(SERVICE)\b"; then \
		echo "Invalid service: $(SERVICE). Valid services: $(ALL_SERVICES)"; \
		exit 1; \
	fi
	@$(DOCKER_COMPOSE) exec $(SERVICE) /bin/bash

docker-config: ## Render the effective docker-compose configuration
	@$(DOCKER_COMPOSE) config

# =============================================================================
# DOCKER BUILDX SETUP & MANAGEMENT
# =============================================================================

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

# =============================================================================
# DOCKER IMAGE BUILDING
# =============================================================================

# Main build targets
docker-build: docker-buildx-setup docker-build-base docker-build-services-parallel ## Build service images using smart incremental detection

# Service image builds
docker-build-services-parallel: ## Build all services locally in parallel with registry caching (local-only, no push)
	@printf "$(COLOR_GREEN)→ Building docker images with enhanced caching (local-only)$(COLOR_OFF)\n"
	@DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) COMPOSE_DOCKER_CLI_BUILD=$(COMPOSE_DOCKER_CLI_BUILD) $(DOCKER_COMPOSE) build --parallel

docker-build-service: ## Build a specific service (set SERVICE=name)
	@if [ -z "$(SERVICE)" ]; then \
		echo "Set SERVICE=<service-name> ($(ALL_SERVICES))"; \
		exit 1; \
	fi
	@if ! echo "$(ALL_SERVICES)" | grep -q "\b$(SERVICE)\b"; then \
		echo "Invalid service: $(SERVICE). Valid services: $(ALL_SERVICES)"; \
		exit 1; \
	fi
	@printf "$(COLOR_GREEN)→ Building $(SERVICE) service$(COLOR_OFF)\n"
	@DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) COMPOSE_DOCKER_CLI_BUILD=$(COMPOSE_DOCKER_CLI_BUILD) $(DOCKER_COMPOSE) build $(SERVICE)

# Base image builds
docker-build-base: ## Build base images locally (python-web, python-ml, tools)
	@printf "$(COLOR_GREEN)→ Building base images locally$(COLOR_OFF)\n"
	@PUSH=false bash $(SCRIPT_DIR)/build-base-images.sh

docker-build-wheels: ## Build and cache wheels for native dependencies
	@printf "$(COLOR_GREEN)→ Building wheels for native dependencies$(COLOR_OFF)\n"
	@bash $(SCRIPT_DIR)/build-wheels.sh

# =============================================================================
# DOCKER IMAGE PUSHING
# =============================================================================

docker-push-base-images: ## Push base images to registry (build with 'make docker-build-base' first)
	@printf "$(COLOR_GREEN)→ Pushing base images to registry$(COLOR_OFF)\n"
	@bash $(SCRIPT_DIR)/push-base-images.sh

docker-push-services: ## Push service images to registry (build with 'make docker-build-services-parallel' first)
	@printf "$(COLOR_GREEN)→ Pushing service images to registry$(COLOR_OFF)\n"
	@$(call ensure_docker_ghcr_auth)
	@$(DOCKER_COMPOSE) config --images | while read image; do \
		if [ -n "$$image" ]; then \
			# Only push images from our registry, skip community images \
			if echo "$$image" | grep -q "^$(REGISTRY)/"; then \
				if docker image inspect "$$image" >/dev/null 2>&1; then \
					printf "$(COLOR_YELLOW)→ Pushing $$image$(COLOR_OFF)\n"; \
					docker push "$$image" || { \
						printf "$(COLOR_RED)→ Error: Failed to push $$image$(COLOR_OFF)\n"; \
						exit 1; \
					}; \
				else \
					printf "$(COLOR_YELLOW)→ Warning: Image $$image not found locally. Skipping.$(COLOR_OFF)\n"; \
				fi; \
			else \
				printf "$(COLOR_CYAN)→ Skipping community image: $$image$(COLOR_OFF)\n"; \
			fi; \
		fi; \
	done

docker-push-all: docker-push-base-images docker-push-services push-test-image push-lint-image push-security-image ## Push all images to registry (base, services, and toolchain)
	@printf "$(COLOR_GREEN)→ All images pushed successfully$(COLOR_OFF)\n"

# =============================================================================
# DOCKER IMAGE CACHE MANAGEMENT
# =============================================================================

docker-pull-images: ## Pre-pull images for all compose files and toolchain (cache warmup)
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker." >&2; exit 1; }
	@printf "$(COLOR_GREEN)→ Pulling images defined in docker-compose files$(COLOR_OFF)\n"
	@for f in docker-compose.yml docker-compose.test.yml docker-compose.ci.yml; do \
		if [ -f "$$f" ]; then \
			printf "$(COLOR_CYAN)→ Pulling images from %s$(COLOR_OFF)\n" "$$f"; \
			$(DOCKER_COMPOSE) -f "$$f" pull --ignore-pull-failures || true; \
		fi; \
	 done
	@printf "$(COLOR_GREEN)→ Pulling toolchain images$(COLOR_OFF)\n"
	@for img in $(LINT_IMAGE) $(TEST_IMAGE) $(SECURITY_IMAGE) $(WAKE_TRAINER_IMAGE); do \
		printf "Pulling %s\n" "$$img"; \
		docker pull "$$img" || true; \
	 done
	@printf "$(COLOR_GREEN)→ Docker cache warmup complete$(COLOR_OFF)\n"

docker-warm-cache: docker-pull-images ## Alias: warm Docker cache by downloading images first

# =============================================================================
# TESTING
# =============================================================================

# Test toolchain image management
build-test-image: ## Build the test toolchain container image (only if missing)
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to build test container images." >&2; exit 1; }
	$(call build_if_missing,$(TEST_IMAGE),$(TEST_DOCKERFILE))

build-test-image-force: ## Force rebuild the test toolchain container image
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to build test container images." >&2; exit 1; }
	@printf "$(COLOR_YELLOW)→ Force rebuilding $(TEST_IMAGE)$(COLOR_OFF)\n"
	$(call build_with_registry_cache,$(TEST_IMAGE),$(TEST_DOCKERFILE))

push-test-image: ## Push test image to registry (build with 'make build-test-image' first)
	$(call push_image,$(TEST_IMAGE))

push-test-image-force: build-test-image-force push-test-image ## Force rebuild and push test image

# Test execution
test: test-unit test-component ## Run unit and component tests (fast, reliable)

test-unit: build-test-image ## Run unit tests (fast, isolated)
	@printf "$(COLOR_CYAN)→ Running unit tests$(COLOR_OFF)\n"
	$(call run_docker_container,$(TEST_IMAGE),$(TEST_WORKDIR),pytest -m unit $(PYTEST_ARGS))

test-component: build-test-image ## Run component tests (with mocked external dependencies)
	@printf "$(COLOR_CYAN)→ Running component tests$(COLOR_OFF)\n"
	$(call run_docker_container,$(TEST_IMAGE),$(TEST_WORKDIR),pytest -m component $(PYTEST_ARGS))

test-integration: build-test-image ## Run integration tests against already-running test services (run 'make run-test-env' first)
	@printf "$(COLOR_CYAN)→ Running integration tests against running test services$(COLOR_OFF)\n"
	@printf "$(COLOR_YELLOW)→ Connecting to Docker network: audio-orchestrator-test$(COLOR_OFF)\n"
	@docker run --rm \
		--network audio-orchestrator-test \
		-u $$(id -u):$$(id -g) \
		-e HOME=$(TEST_WORKDIR) \
		-e USER=$$(id -un 2>/dev/null || echo tester) \
		$(if $(strip $(PYTEST_ARGS)),-e PYTEST_ARGS="$(PYTEST_ARGS)",) \
		-v "$(CURDIR)":$(TEST_WORKDIR) \
		$(TEST_IMAGE) \
		pytest -m integration -x $(PYTEST_ARGS)

test-unit-service: build-test-image ## Run unit tests for specific service (set SERVICE=name)
	@if [ -z "$(SERVICE)" ]; then \
		printf "$(COLOR_RED)Error: Set SERVICE=<service-name> ($(ALL_SERVICES))$(COLOR_OFF)\n"; \
		exit 1; \
	fi
	@if ! echo "$(ALL_SERVICES) common" | grep -q "\b$(SERVICE)\b"; then \
		printf "$(COLOR_RED)Error: Unknown service $(SERVICE). Valid: $(ALL_SERVICES), common$(COLOR_OFF)\n"; \
		exit 1; \
	fi
	@printf "$(COLOR_CYAN)→ Running unit tests for $(SERVICE) service$(COLOR_OFF)\n"
	@$(call run_docker_container,$(TEST_IMAGE),$(TEST_WORKDIR),bash -c "test_paths=''; [ -d services/tests/unit/$(SERVICE) ] && test_paths=\"services/tests/unit/$(SERVICE)\"; [ -d services/$(SERVICE)/tests ] && test_paths=\"\$$test_paths services/$(SERVICE)/tests\"; if [ -n \"\$$test_paths\" ]; then pytest -m unit \$$test_paths $(PYTEST_ARGS); else echo 'No unit tests found for $(SERVICE) service'; fi")

test-component-service: build-test-image ## Run component tests for specific service (set SERVICE=name)
	@if [ -z "$(SERVICE)" ]; then \
		printf "$(COLOR_RED)Error: Set SERVICE=<service-name> ($(ALL_SERVICES))$(COLOR_OFF)\n"; \
		exit 1; \
	fi
	@if ! echo "$(ALL_SERVICES) common" | grep -q "\b$(SERVICE)\b"; then \
		printf "$(COLOR_RED)Error: Unknown service $(SERVICE). Valid: $(ALL_SERVICES), common$(COLOR_OFF)\n"; \
		exit 1; \
	fi
	@printf "$(COLOR_CYAN)→ Running component tests for $(SERVICE) service$(COLOR_OFF)\n"
	@$(call run_docker_container,$(TEST_IMAGE),$(TEST_WORKDIR),bash -c "test_paths=''; [ -d services/tests/component/$(SERVICE) ] && test_paths=\"services/tests/component/$(SERVICE)\"; [ -d services/$(SERVICE)/tests ] && test_paths=\"\$$test_paths services/$(SERVICE)/tests\"; if [ -n \"\$$test_paths\" ]; then pytest -m component \$$test_paths $(PYTEST_ARGS); else echo 'No component tests found for $(SERVICE) service'; fi")

# =============================================================================
# LINTING & CODE QUALITY
# =============================================================================

# Lint toolchain image management
build-lint-image: ## Build the lint toolchain container image (only if missing)
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to build lint container images." >&2; exit 1; }
	$(call build_if_missing,$(LINT_IMAGE),$(LINT_DOCKERFILE))

build-lint-image-force: ## Force rebuild the lint toolchain container image
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to build lint container images." >&2; exit 1; }
	@printf "$(COLOR_YELLOW)→ Force rebuilding $(LINT_IMAGE)$(COLOR_OFF)\n"
	$(call build_with_registry_cache,$(LINT_IMAGE),$(LINT_DOCKERFILE))

push-lint-image: ## Push lint image to registry (build with 'make build-lint-image' first)
	$(call push_image,$(LINT_IMAGE))

push-lint-image-force: build-lint-image-force push-lint-image ## Force rebuild and push lint image

# Lint execution
lint: build-lint-image ## Run all linters (validation only)
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker." >&2; exit 1; }
	@docker run --rm -u $$(id -u):$$(id -g) -e HOME=$(LINT_WORKDIR) \
		-e USER=$$(id -un 2>/dev/null || echo lint) \
		-v "$(CURDIR)":$(LINT_WORKDIR) $(LINT_IMAGE) \
		bash $(LINT_WORKDIR)/services/linter/run-lint.sh

lint-fix: build-lint-image ## Apply all automatic fixes
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker." >&2; exit 1; }
	@docker run --rm -u $$(id -u):$$(id -g) -e HOME=$(LINT_WORKDIR) \
		-e USER=$$(id -un 2>/dev/null || echo lint) \
		-v "$(CURDIR)":$(LINT_WORKDIR) $(LINT_IMAGE) \
		bash $(LINT_WORKDIR)/services/linter/run-lint-fix.sh

# =============================================================================
# SECURITY
# =============================================================================

# Security toolchain image management
build-security-image: ## Build the security scanning container image (only if missing)
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to build security container images." >&2; exit 1; }
	$(call build_if_missing,$(SECURITY_IMAGE),$(SECURITY_DOCKERFILE))

build-security-image-force: ## Force rebuild the security scanning container image
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to build security container images." >&2; exit 1; }
	@printf "$(COLOR_YELLOW)→ Force rebuilding $(SECURITY_IMAGE)$(COLOR_OFF)\n"
	$(call build_with_registry_cache,$(SECURITY_IMAGE),$(SECURITY_DOCKERFILE))

push-security-image: ## Push security image to registry (build with 'make build-security-image' first)
	$(call push_image,$(SECURITY_IMAGE))

push-security-image-force: build-security-image-force push-security-image ## Force rebuild and push security image

# Security execution
security: build-security-image ## Run security scanning with pip-audit
	@printf "$(COLOR_CYAN)→ Running security scan$(COLOR_OFF)\n"
	$(call run_docker_container,$(SECURITY_IMAGE),$(SECURITY_WORKDIR),)

# =============================================================================
# WAKE WORD TRAINING
# =============================================================================

# Wake trainer toolchain image management
build-wake-trainer-image: ## Build the wake trainer toolchain container image (only if missing)
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to build wake trainer container images." >&2; exit 1; }
	$(call build_if_missing,$(WAKE_TRAINER_IMAGE),$(WAKE_TRAINER_DOCKERFILE))

build-wake-trainer-image-force: ## Force rebuild the wake trainer toolchain container image
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to build wake trainer container images." >&2; exit 1; }
	@printf "$(COLOR_YELLOW)→ Force rebuilding $(WAKE_TRAINER_IMAGE)$(COLOR_OFF)\n"
	$(call build_with_registry_cache,$(WAKE_TRAINER_IMAGE),$(WAKE_TRAINER_DOCKERFILE))

push-wake-trainer-image: ## Push wake trainer image to registry (build with 'make build-wake-trainer-image' first)
	$(call push_image,$(WAKE_TRAINER_IMAGE))

push-wake-trainer-image-force: build-wake-trainer-image-force push-wake-trainer-image ## Force rebuild and push wake trainer image

# Wake trainer execution
wake-train: build-wake-trainer-image ## Run full wake word training (all 3 stages) - requires CONFIG=path/to/config.yaml
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker." >&2; exit 1; }
	@if [ -z "$(CONFIG)" ]; then \
		printf "$(COLOR_RED)→ Error: CONFIG is required. Example: make wake-train CONFIG=services/waketrainer/config/example_config.yaml$(COLOR_OFF)\n"; \
		exit 1; \
	fi
	$(call run_wake_trainer_container,$(WAKE_TRAINER_IMAGE),$(WAKE_TRAINER_WORKDIR),bash -c "export CONFIG=\"$(CONFIG)\" && export STAGE=all && bash $(WAKE_TRAINER_WORKDIR)/services/waketrainer/run-train.sh")

wake-train-generate: build-wake-trainer-image ## Run wake word training stage 1 (generate clips) - requires CONFIG=path/to/config.yaml
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker." >&2; exit 1; }
	@if [ -z "$(CONFIG)" ]; then \
		printf "$(COLOR_RED)→ Error: CONFIG is required. Example: make wake-train-generate CONFIG=services/waketrainer/config/example_config.yaml$(COLOR_OFF)\n"; \
		exit 1; \
	fi
	$(call run_wake_trainer_container,$(WAKE_TRAINER_IMAGE),$(WAKE_TRAINER_WORKDIR),bash -c "export CONFIG=\"$(CONFIG)\" && export STAGE=generate && bash $(WAKE_TRAINER_WORKDIR)/services/waketrainer/run-train.sh")

wake-train-augment: build-wake-trainer-image ## Run wake word training stage 2 (augment clips) - requires CONFIG=path/to/config.yaml. Use OVERWRITE=true to regenerate existing features.
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker." >&2; exit 1; }
	@if [ -z "$(CONFIG)" ]; then \
		printf "$(COLOR_RED)→ Error: CONFIG is required. Example: make wake-train-augment CONFIG=services/waketrainer/config/example_config.yaml$(COLOR_OFF)\n"; \
		exit 1; \
	fi
	$(call run_wake_trainer_container,$(WAKE_TRAINER_IMAGE),$(WAKE_TRAINER_WORKDIR),bash -c "export CONFIG=\"$(CONFIG)\" && export STAGE=augment && export OVERWRITE=\"$(OVERWRITE)\" && bash $(WAKE_TRAINER_WORKDIR)/services/waketrainer/run-train.sh")

wake-train-train: build-wake-trainer-image ## Run wake word training stage 3 (train model) - requires CONFIG=path/to/config.yaml
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker." >&2; exit 1; }
	@if [ -z "$(CONFIG)" ]; then \
		printf "$(COLOR_RED)→ Error: CONFIG is required. Example: make wake-train-train CONFIG=services/waketrainer/config/example_config.yaml$(COLOR_OFF)\n"; \
		exit 1; \
	fi
	$(call run_wake_trainer_container,$(WAKE_TRAINER_IMAGE),$(WAKE_TRAINER_WORKDIR),bash -c "export CONFIG=\"$(CONFIG)\" && export STAGE=train && bash $(WAKE_TRAINER_WORKDIR)/services/waketrainer/run-train.sh")

extract-background-audio: build-wake-trainer-image ## Extract background audio from Parquet to WAV files
	@mkdir -p "$(CURDIR)/services/models/wake/training-data/background_clips/wav"
	$(call run_wake_trainer_container,$(WAKE_TRAINER_IMAGE),$(WAKE_TRAINER_WORKDIR),\
		python services/waketrainer/extract-background-audio.py \
			--dataset-dir /workspace/services/models/wake/training-data/background_clips \
			--output-dir /workspace/services/models/wake/training-data/background_clips/wav)

wake-train-diagnose: build-wake-trainer-image ## Diagnose validation OOM issue - inspect validation data and openwakeword code
	$(call run_wake_trainer_container,$(WAKE_TRAINER_IMAGE),$(WAKE_TRAINER_WORKDIR),\
		python $(WAKE_TRAINER_WORKDIR)/services/waketrainer/diagnose_oom.py)

wake-train-create-validation-subset: build-wake-trainer-image ## Create smaller validation dataset subset (use SIZE=10000 to set subset size)
	@if [ -z "$(SIZE)" ]; then \
		printf "$(COLOR_YELLOW)→ Using default subset size: 10000 samples$(COLOR_OFF)\n"; \
		SIZE=10000; \
	fi
	$(call run_wake_trainer_container,$(WAKE_TRAINER_IMAGE),$(WAKE_TRAINER_WORKDIR),\
		python $(WAKE_TRAINER_WORKDIR)/services/waketrainer/create_validation_subset.py \
			--input /workspace/services/models/wake/training-data/validation_set_features.npy \
			--output /workspace/services/models/wake/training-data/validation_set_features_small.npy \
			--size $(SIZE))

# =============================================================================
# PYTHON SYNTAX CHECKING
# =============================================================================

check-syntax: build-test-image ## Check Python syntax by compiling Python files (use TARGET=dir or file, default: all services/)
	@printf "$(COLOR_CYAN)→ Checking Python syntax$(COLOR_OFF)\n"
	@$(call run_docker_container,$(TEST_IMAGE),$(TEST_WORKDIR),bash $(TEST_WORKDIR)/scripts/check-syntax.sh $(TARGET))

# =============================================================================
# MODEL MANAGEMENT
# =============================================================================

models-clean: ## Remove downloaded models from ./services/models/
	@printf "$(COLOR_RED)→ Cleaning downloaded models$(COLOR_OFF)\n"
	@if [ -d "./services/models" ]; then \
		echo "Removing models from ./services/models/"; \
		rm -rf ./services/models/* || true; \
		echo "Models cleaned."; \
	else \
		echo "No models directory found."; \
	fi

# Service name to environment variable mapping for force download
FORCE_DOWNLOAD_ENV_VARS := \
	stt:FORCE_MODEL_DOWNLOAD_WHISPER_MODEL \
	flan:FORCE_MODEL_DOWNLOAD_FLAN_T5 \
	guardrails:FORCE_MODEL_DOWNLOAD_TOXICITY_MODEL \
	bark:FORCE_MODEL_DOWNLOAD_BARK_MODELS

models-force-download: ## Force download all models (sets FORCE_MODEL_DOWNLOAD=true)
	@printf "$(COLOR_GREEN)→ Force downloading all models$(COLOR_OFF)\n"
	@FORCE_MODEL_DOWNLOAD=true $(DOCKER_COMPOSE) restart stt flan guardrails bark

models-force-download-service: ## Force download for specific service (set SERVICE=stt|flan|guardrails|bark)
	@[ -z "$(SERVICE)" ] && (printf "$(COLOR_RED)Error: Set SERVICE=stt|flan|guardrails|bark$(COLOR_OFF)\n" && exit 1) || true
	@found=0; \
	for mapping in $(FORCE_DOWNLOAD_ENV_VARS); do \
		svc=$$(echo $$mapping | cut -d: -f1); \
		env_var=$$(echo $$mapping | cut -d: -f2); \
		if [ "$$svc" = "$(SERVICE)" ]; then \
			printf "$(COLOR_GREEN)→ Force downloading models for $(SERVICE) service$(COLOR_OFF)\n"; \
			$$env_var=true $(DOCKER_COMPOSE) restart $(SERVICE); \
			found=1; \
			break; \
		fi; \
	done; \
	if [ $$found -eq 0 ]; then \
		printf "$(COLOR_RED)Error: Unknown service $(SERVICE). Valid: stt, flan, guardrails, bark$(COLOR_OFF)\n"; \
		exit 1; \
	fi

# =============================================================================
# CLEANUP & MAINTENANCE
# =============================================================================

clean: ## Remove logs, cached audio artifacts, debug files, and Python cache directories
	@printf "$(COLOR_BLUE)→ Cleaning caches and artifacts...$(COLOR_OFF)\n"
	@bash $(SCRIPT_DIR)/clean-caches.sh

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
	@python3 $(SCRIPT_DIR)/verify_last_updated.py --allow-divergence $(ARGS)

validate-changes: ## Validate uncommitted changes (lint, tests); use ARGS='--verbose' to customize
	@bash $(SCRIPT_DIR)/validate-changes.sh $(ARGS)

analyze-audio-quality: ## Analyze audio quality from logs (set LOG_FILE=path, default: debug/docker.logs)
	@printf "$(COLOR_CYAN)→ Analyzing audio quality from logs$(COLOR_OFF)\n"
	@LOG_FILE=$${LOG_FILE:-debug/docker.logs}; \
	if [ -f "$$LOG_FILE" ]; then \
		python3 $(SCRIPT_DIR)/analyze_audio_quality.py "$$LOG_FILE"; \
	else \
		printf "$(COLOR_YELLOW)Warning: Log file not found: $$LOG_FILE$(COLOR_OFF)\n"; \
		printf "$(COLOR_YELLOW)Reading from stdin...$(COLOR_OFF)\n"; \
		python3 $(SCRIPT_DIR)/analyze_audio_quality.py; \
	fi

# =============================================================================
# TOKEN MANAGEMENT
# =============================================================================

rotate-tokens: ## Rotate AUTH_TOKEN values across all environment files
	@printf "$(COLOR_CYAN)→ Rotating AUTH_TOKEN values$(COLOR_OFF)\n"
	@python3 $(SCRIPT_DIR)/rotate_auth_tokens.py

rotate-tokens-dry-run: ## Show what token rotation would change without modifying files
	@printf "$(COLOR_CYAN)→ Dry run: AUTH_TOKEN rotation preview$(COLOR_OFF)\n"
	@python3 $(SCRIPT_DIR)/rotate_auth_tokens.py --dry-run

validate-tokens: ## Validate AUTH_TOKEN consistency across environment files
	@printf "$(COLOR_CYAN)→ Validating AUTH_TOKEN consistency$(COLOR_OFF)\n"
	@python3 $(SCRIPT_DIR)/rotate_auth_tokens.py --validate-only
