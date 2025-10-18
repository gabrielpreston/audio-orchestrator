SHELL := /bin/bash

# =============================================================================
# PHONY TARGETS
# =============================================================================
.PHONY: all test help run stop logs logs-dump docker-build docker-restart docker-shell docker-config docker-smoke clean docker-clean docker-status lint lint-container lint-image lint-fix lint-local lint-python lint-dockerfiles lint-compose lint-makefile lint-markdown lint-fix-local lint-fix-python lint-fix-yaml lint-fix-markdown test test-ci test-container test-image test-local test-unit test-unit-local test-unit-container test-component test-component-local test-component-container test-integration test-integration-local test-integration-container test-e2e test-e2e-local test-e2e-container test-coverage test-coverage-local test-coverage-container test-watch test-watch-local test-watch-container test-debug test-debug-local test-debug-container test-specific test-specific-local test-specific-container typecheck security docs-verify models-download models-clean install-dev-deps install-ci-tools ci-setup eval-stt eval-wake eval-stt-all clean-eval

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

# Docker Compose detection
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

COMPOSE_MISSING_MESSAGE := Docker Compose was not found (checked docker compose and docker-compose); please install Docker Compose.

# Docker BuildKit configuration
DOCKER_BUILDKIT ?= 1
COMPOSE_DOCKER_CLI_BUILD ?= 1

# Source paths and file discovery
PYTHON_SOURCES := services
MYPY_PATHS ?= services
DOCKERFILES := $(shell find services -type f -name 'Dockerfile' 2>/dev/null)
YAML_FILES := docker-compose.yml $(shell find .github/workflows -type f -name '*.yaml' -o -name '*.yml' 2>/dev/null)
MARKDOWN_FILES := README.md AGENTS.md $(shell find docs -type f -name '*.md' 2>/dev/null)

# Container images and paths
LINT_IMAGE ?= discord-voice-lab/lint:latest
LINT_DOCKERFILE := services/linter/Dockerfile
LINT_WORKDIR := /workspace
TEST_IMAGE ?= discord-voice-lab/test:latest
TEST_DOCKERFILE := services/tester/Dockerfile
TEST_WORKDIR := /workspace

# Test configuration
PYTEST_ARGS ?=
RUN_SCRIPT := scripts/run-compose.sh

# =============================================================================
# DEFAULT TARGETS
# =============================================================================

all: help ## Default aggregate target

help: ## Show this help (default)
	@echo -e "$(COLOR_CYAN)discord-voice-lab Makefile — handy targets$(COLOR_OFF)"
	@echo
	@echo "Usage: make <target>"
	@echo
	@awk 'BEGIN {FS = ":.*## "} /^[^[:space:]#].*:.*##/ { printf "  %-14s - %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

.DEFAULT_GOAL := help

# =============================================================================
# APPLICATION LIFECYCLE
# =============================================================================

run: stop ## Start docker-compose stack (Discord bot + STT + LLM + orchestrator)
	@$(RUN_SCRIPT)

stop: ## Stop and remove containers for the compose stack
	@echo -e "$(COLOR_BLUE)→ Bringing down containers$(COLOR_OFF)"
	@if [ "$(HAS_DOCKER_COMPOSE)" = "0" ]; then echo "$(COMPOSE_MISSING_MESSAGE)"; exit 1; fi
	@$(DOCKER_COMPOSE) down --remove-orphans

logs: ## Tail logs for compose services (set SERVICE=name to filter)
	@echo -e "$(COLOR_CYAN)→ Tailing logs for docker services (Ctrl+C to stop)$(COLOR_OFF)"; \
	if [ "$(HAS_DOCKER_COMPOSE)" = "0" ]; then echo "$(COMPOSE_MISSING_MESSAGE)"; exit 1; fi; \
	if [ -z "$(SERVICE)" ]; then $(DOCKER_COMPOSE) logs -f --tail=100; else $(DOCKER_COMPOSE) logs -f --tail=100 $(SERVICE); fi

logs-dump: ## Capture docker logs to ./docker.logs
	@echo -e "$(COLOR_CYAN)→ Dumping all logs for docker services$(COLOR_OFF)"
	@if [ "$(HAS_DOCKER_COMPOSE)" = "0" ]; then echo "$(COMPOSE_MISSING_MESSAGE)"; exit 1; fi
	@$(DOCKER_COMPOSE) logs > ./debug/docker.logs

docker-status: ## Show status of docker-compose services
	@if [ "$(HAS_DOCKER_COMPOSE)" = "0" ]; then echo "$(COMPOSE_MISSING_MESSAGE)"; exit 1; fi
	@$(DOCKER_COMPOSE) ps

# =============================================================================
# DOCKER BUILD & MANAGEMENT
# =============================================================================

docker-build: ## Build or rebuild images for the compose stack
	@echo -e "$(COLOR_GREEN)→ Building docker images$(COLOR_OFF)"
	@if [ "$(HAS_DOCKER_COMPOSE)" = "0" ]; then echo "$(COMPOSE_MISSING_MESSAGE)"; exit 1; fi
	@DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) COMPOSE_DOCKER_CLI_BUILD=$(COMPOSE_DOCKER_CLI_BUILD) $(DOCKER_COMPOSE) build --parallel

docker-build-nocache: ## Force rebuild all images without using cache
	@echo -e "$(COLOR_GREEN)→ Building docker images (no cache)$(COLOR_OFF)"
	@if [ "$(HAS_DOCKER_COMPOSE)" = "0" ]; then echo "$(COMPOSE_MISSING_MESSAGE)"; exit 1; fi
	@DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) COMPOSE_DOCKER_CLI_BUILD=$(COMPOSE_DOCKER_CLI_BUILD) $(DOCKER_COMPOSE) build --no-cache --parallel

docker-build-service: ## Build a specific service (set SERVICE=name)
	@if [ "$(HAS_DOCKER_COMPOSE)" = "0" ]; then echo "$(COMPOSE_MISSING_MESSAGE)"; exit 1; fi
	@if [ -z "$(SERVICE)" ]; then echo "Set SERVICE=<service-name> (discord|stt|llm|orchestrator|tts)"; exit 1; fi
	@echo -e "$(COLOR_GREEN)→ Building $(SERVICE) service$(COLOR_OFF)"
	@DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) COMPOSE_DOCKER_CLI_BUILD=$(COMPOSE_DOCKER_CLI_BUILD) $(DOCKER_COMPOSE) build $(SERVICE)

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
	@if [ -z "$(SERVICE)" ]; then echo "Set SERVICE=<service-name> (discord|stt|llm|orchestrator)"; exit 1; fi
	@$(DOCKER_COMPOSE) exec $(SERVICE) /bin/bash

docker-config: ## Render the effective docker-compose configuration
	@if [ "$(HAS_DOCKER_COMPOSE)" = "0" ]; then echo "$(COMPOSE_MISSING_MESSAGE)"; exit 1; fi
	@$(DOCKER_COMPOSE) config

docker-smoke: ## Build images and validate docker-compose configuration for CI parity
	@if [ "$(HAS_DOCKER_COMPOSE)" = "0" ]; then echo "$(COMPOSE_MISSING_MESSAGE)"; exit 1; fi
	@echo -e "$(COLOR_GREEN)→ Validating docker-compose stack$(COLOR_OFF)"
	@DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) COMPOSE_DOCKER_CLI_BUILD=$(COMPOSE_DOCKER_CLI_BUILD) $(DOCKER_COMPOSE) config >/dev/null
	@$(DOCKER_COMPOSE) config --services
	@DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) COMPOSE_DOCKER_CLI_BUILD=$(COMPOSE_DOCKER_CLI_BUILD) $(DOCKER_COMPOSE) build --pull --progress=plain

docker-validate: ## Validate Dockerfiles with hadolint
	@command -v hadolint >/dev/null 2>&1 || { \
		echo "hadolint not found; install it (see https://github.com/hadolint/hadolint#install)." >&2; exit 1; }
	@echo -e "$(COLOR_CYAN)→ Validating Dockerfiles$(COLOR_OFF)"
	@hadolint $(DOCKERFILES)
	@echo -e "$(COLOR_GREEN)→ Dockerfile validation complete$(COLOR_OFF)"

docker-prune-cache: ## Clear BuildKit cache and unused Docker resources
	@echo -e "$(COLOR_YELLOW)→ Pruning Docker BuildKit cache$(COLOR_OFF)"
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; skipping cache prune."; exit 0; }
	@docker buildx prune -f || true
	@echo -e "$(COLOR_GREEN)→ BuildKit cache pruned$(COLOR_OFF)"

# =============================================================================
# TESTING
# =============================================================================

test: test-unit-container test-component-container ## Run unit and component tests in containers (default)

test-ci: test-local ## Run tests using locally installed tooling (for CI)

test-container: test-image ## Build test container (if needed) and run the test suite
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to run containerized tests." >&2; exit 1; }
	@docker run --rm \
		-u $$(id -u):$$(id -g) \
		-e HOME=$(TEST_WORKDIR) \
		-e USER=$$(id -un 2>/dev/null || echo tester) \
		$(if $(strip $(PYTEST_ARGS)),-e PYTEST_ARGS="$(PYTEST_ARGS)",) \
		-v "$(CURDIR)":$(TEST_WORKDIR) \
		$(TEST_IMAGE)

test-image: ## Build the test toolchain container image
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to build test container images." >&2; exit 1; }
	@docker build --pull --tag $(TEST_IMAGE) -f $(TEST_DOCKERFILE) .

test-local: ## Run tests using locally installed tooling
	@command -v pytest >/dev/null 2>&1 || { echo "pytest not found; install it (e.g. pip install pytest)." >&2; exit 1; }
	@PYTHONPATH=$(CURDIR)$${PYTHONPATH:+:$$PYTHONPATH} pytest $(PYTEST_ARGS) || { \
		status=$$?; \
		if [ $$status -eq 5 ]; then \
			echo "pytest reported that no tests were collected; treating this as success." >&2; \
			exit 0; \
		fi; \
		exit $$status; \
	}

# Test categories
test-unit: test-unit-local ## Run unit tests only (fast, isolated) - local version
test-unit-local: ## Run unit tests using locally installed tooling
	@command -v pytest >/dev/null 2>&1 || { echo "pytest not found; install it (e.g. pip install pytest)." >&2; exit 1; }
	@echo -e "$(COLOR_CYAN)→ Running unit tests (local)$(COLOR_OFF)"
	@PYTHONPATH=$(CURDIR)$${PYTHONPATH:+:$$PYTHONPATH} pytest -m unit $(PYTEST_ARGS) || { \
		status=$$?; \
		if [ $$status -eq 5 ]; then \
			echo "pytest reported that no tests were collected; treating this as success." >&2; \
			exit 0; \
		fi; \
		exit $$status; \
	}

test-unit-container: test-image ## Run unit tests in Docker container
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to run containerized tests." >&2; exit 1; }
	@echo -e "$(COLOR_CYAN)→ Running unit tests (container)$(COLOR_OFF)"
	@docker run --rm \
		-u $$(id -u):$$(id -g) \
		-e HOME=$(TEST_WORKDIR) \
		-e USER=$$(id -un 2>/dev/null || echo tester) \
		$(if $(strip $(PYTEST_ARGS)),-e PYTEST_ARGS="$(PYTEST_ARGS)",) \
		-v "$(CURDIR)":$(TEST_WORKDIR) \
		$(TEST_IMAGE) \
		pytest -m unit $(PYTEST_ARGS)

test-component: test-component-local ## Run component tests (with mocked external dependencies) - local version
test-component-local: ## Run component tests using locally installed tooling
	@command -v pytest >/dev/null 2>&1 || { echo "pytest not found; install it (e.g. pip install pytest)." >&2; exit 1; }
	@echo -e "$(COLOR_CYAN)→ Running component tests (local)$(COLOR_OFF)"
	@PYTHONPATH=$(CURDIR)$${PYTHONPATH:+:$$PYTHONPATH} pytest -m component $(PYTEST_ARGS) || { \
		status=$$?; \
		if [ $$status -eq 5 ]; then \
			echo "pytest reported that no tests were collected; treating this as success." >&2; \
			exit 0; \
		fi; \
		exit $$status; \
	}

test-component-container: test-image ## Run component tests in Docker container
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to run containerized tests." >&2; exit 1; }
	@echo -e "$(COLOR_CYAN)→ Running component tests (container)$(COLOR_OFF)"
	@docker run --rm \
		-u $$(id -u):$$(id -g) \
		-e HOME=$(TEST_WORKDIR) \
		-e USER=$$(id -un 2>/dev/null || echo tester) \
		$(if $(strip $(PYTEST_ARGS)),-e PYTEST_ARGS="$(PYTEST_ARGS)",) \
		-v "$(CURDIR)":$(TEST_WORKDIR) \
		$(TEST_IMAGE) \
		pytest -m component $(PYTEST_ARGS)

test-integration: test-integration-local ## Run integration tests (requires Docker Compose) - local version
test-integration-local: ## Run integration tests using locally installed tooling
	@command -v pytest >/dev/null 2>&1 || { echo "pytest not found; install it (e.g. pip install pytest)." >&2; exit 1; }
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to run integration tests." >&2; exit 1; }
	@if [ "$(HAS_DOCKER_COMPOSE)" = "0" ]; then echo "$(COMPOSE_MISSING_MESSAGE)"; exit 1; fi
	@echo -e "$(COLOR_CYAN)→ Running integration tests (local)$(COLOR_OFF)"
	@echo -e "$(COLOR_YELLOW)→ Starting Docker Compose services for integration tests$(COLOR_OFF)"
	@$(DOCKER_COMPOSE) up -d --build
	@echo -e "$(COLOR_YELLOW)→ Waiting for services to be ready$(COLOR_OFF)"
	@sleep 10
	@PYTHONPATH=$(CURDIR)$${PYTHONPATH:+:$$PYTHONPATH} pytest -m integration $(PYTEST_ARGS) || { \
		status=$$?; \
		echo -e "$(COLOR_YELLOW)→ Stopping Docker Compose services$(COLOR_OFF)"; \
		$(DOCKER_COMPOSE) down; \
		exit $$status; \
	}
	@echo -e "$(COLOR_YELLOW)→ Stopping Docker Compose services$(COLOR_OFF)"
	@$(DOCKER_COMPOSE) down

test-integration-container: test-image ## Run integration tests in Docker container
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to run containerized tests." >&2; exit 1; }
	@if [ "$(HAS_DOCKER_COMPOSE)" = "0" ]; then echo "$(COMPOSE_MISSING_MESSAGE)"; exit 1; fi
	@echo -e "$(COLOR_CYAN)→ Running integration tests (container)$(COLOR_OFF)"
	@echo -e "$(COLOR_YELLOW)→ Starting Docker Compose services for integration tests$(COLOR_OFF)"
	@$(DOCKER_COMPOSE) up -d --build
	@echo -e "$(COLOR_YELLOW)→ Waiting for services to be ready$(COLOR_OFF)"
	@sleep 10
	@docker run --rm \
		-u $$(id -u):$$(id -g) \
		-e HOME=$(TEST_WORKDIR) \
		-e USER=$$(id -un 2>/dev/null || echo tester) \
		$(if $(strip $(PYTEST_ARGS)),-e PYTEST_ARGS="$(PYTEST_ARGS)",) \
		-v "$(CURDIR)":$(TEST_WORKDIR) \
		--network host \
		$(TEST_IMAGE) \
		pytest -m integration $(PYTEST_ARGS) || { \
			status=$$?; \
			echo -e "$(COLOR_YELLOW)→ Stopping Docker Compose services$(COLOR_OFF)"; \
			$(DOCKER_COMPOSE) down; \
			exit $$status; \
		}
	@echo -e "$(COLOR_YELLOW)→ Stopping Docker Compose services$(COLOR_OFF)"
	@$(DOCKER_COMPOSE) down

test-e2e: test-e2e-local ## Run end-to-end tests (manual trigger only) - local version
test-e2e-local: ## Run end-to-end tests using locally installed tooling
	@command -v pytest >/dev/null 2>&1 || { echo "pytest not found; install it (e.g. pip install pytest)." >&2; exit 1; }
	@echo -e "$(COLOR_RED)→ Running end-to-end tests (requires real Discord API)$(COLOR_OFF)"
	@echo -e "$(COLOR_YELLOW)→ WARNING: This will make real API calls and may incur costs$(COLOR_OFF)"
	@read -p "Are you sure you want to continue? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		PYTHONPATH=$(CURDIR)$${PYTHONPATH:+:$$PYTHONPATH} pytest -m e2e $(PYTEST_ARGS) || { \
			status=$$?; \
			exit $$status; \
		}; \
	else \
		echo -e "$(COLOR_YELLOW)→ E2E tests cancelled$(COLOR_OFF)"; \
		exit 0; \
	fi

test-e2e-container: test-image ## Run end-to-end tests in Docker container
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to run containerized tests." >&2; exit 1; }
	@echo -e "$(COLOR_RED)→ Running end-to-end tests (requires real Discord API)$(COLOR_OFF)"
	@echo -e "$(COLOR_YELLOW)→ WARNING: This will make real API calls and may incur costs$(COLOR_OFF)"
	@read -p "Are you sure you want to continue? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker run --rm \
			-u $$(id -u):$$(id -g) \
			-e HOME=$(TEST_WORKDIR) \
			-e USER=$$(id -un 2>/dev/null || echo tester) \
			$(if $(strip $(PYTEST_ARGS)),-e PYTEST_ARGS="$(PYTEST_ARGS)",) \
			-v "$(CURDIR)":$(TEST_WORKDIR) \
			$(TEST_IMAGE) \
			pytest -m e2e $(PYTEST_ARGS); \
	else \
		echo -e "$(COLOR_YELLOW)→ E2E tests cancelled$(COLOR_OFF)"; \
		exit 0; \
	fi

# Test utilities
test-coverage: test-coverage-local ## Generate coverage report - local version
test-coverage-local: ## Generate coverage report using locally installed tooling
	@command -v pytest >/dev/null 2>&1 || { echo "pytest not found; install it (e.g. pip install pytest)." >&2; exit 1; }
	@echo -e "$(COLOR_CYAN)→ Running tests with coverage (local)$(COLOR_OFF)"
	@PYTHONPATH=$(CURDIR)$${PYTHONPATH:+:$$PYTHONPATH} pytest --cov=services --cov-report=html:htmlcov --cov-report=xml:coverage.xml $(PYTEST_ARGS) || { \
		status=$$?; \
		if [ $$status -eq 5 ]; then \
			echo "pytest reported that no tests were collected; treating this as success." >&2; \
			exit 0; \
		fi; \
		exit $$status; \
	}
	@echo -e "$(COLOR_GREEN)→ Coverage report generated in htmlcov/index.html$(COLOR_OFF)"

test-coverage-container: test-image ## Generate coverage report in Docker container
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to run containerized tests." >&2; exit 1; }
	@echo -e "$(COLOR_CYAN)→ Running tests with coverage (container)$(COLOR_OFF)"
	@docker run --rm \
		-u $$(id -u):$$(id -g) \
		-e HOME=$(TEST_WORKDIR) \
		-e USER=$$(id -un 2>/dev/null || echo tester) \
		$(if $(strip $(PYTEST_ARGS)),-e PYTEST_ARGS="$(PYTEST_ARGS)",) \
		-v "$(CURDIR)":$(TEST_WORKDIR) \
		$(TEST_IMAGE) \
		pytest --cov=services --cov-report=html:htmlcov --cov-report=xml:coverage.xml $(PYTEST_ARGS) || { \
			status=$$?; \
			if [ $$status -eq 5 ]; then \
				echo "pytest reported that no tests were collected; treating this as success." >&2; \
				exit 0; \
			fi; \
			exit $$status; \
		}
	@echo -e "$(COLOR_GREEN)→ Coverage report generated in htmlcov/index.html$(COLOR_OFF)"

test-watch: test-watch-local ## Run tests in watch mode (requires pytest-watch) - local version
test-watch-local: ## Run tests in watch mode using locally installed tooling
	@command -v ptw >/dev/null 2>&1 || { echo "pytest-watch not found; install it (e.g. pip install pytest-watch)." >&2; exit 1; }
	@echo -e "$(COLOR_CYAN)→ Running tests in watch mode (local)$(COLOR_OFF)"
	@PYTHONPATH=$(CURDIR)$${PYTHONPATH:+:$$PYTHONPATH} ptw --runner "pytest -xvs" $(PYTEST_ARGS)

test-watch-container: test-image ## Run tests in watch mode in Docker container
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to run containerized tests." >&2; exit 1; }
	@echo -e "$(COLOR_CYAN)→ Running tests in watch mode (container)$(COLOR_OFF)"
	@docker run --rm -it \
		-u $$(id -u):$$(id -g) \
		-e HOME=$(TEST_WORKDIR) \
		-e USER=$$(id -un 2>/dev/null || echo tester) \
		$(if $(strip $(PYTEST_ARGS)),-e PYTEST_ARGS="$(PYTEST_ARGS)",) \
		-v "$(CURDIR)":$(TEST_WORKDIR) \
		$(TEST_IMAGE) \
		ptw --runner "pytest -xvs" $(PYTEST_ARGS)

test-debug: test-debug-local ## Run tests in debug mode with verbose output - local version
test-debug-local: ## Run tests in debug mode using locally installed tooling
	@command -v pytest >/dev/null 2>&1 || { echo "pytest not found; install it (e.g. pip install pytest)." >&2; exit 1; }
	@echo -e "$(COLOR_CYAN)→ Running tests in debug mode (local)$(COLOR_OFF)"
	@PYTHONPATH=$(CURDIR)$${PYTHONPATH:+:$$PYTHONPATH} pytest -xvs --tb=long --capture=no $(PYTEST_ARGS)

test-debug-container: test-image ## Run tests in debug mode in Docker container
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to run containerized tests." >&2; exit 1; }
	@echo -e "$(COLOR_CYAN)→ Running tests in debug mode (container)$(COLOR_OFF)"
	@docker run --rm \
		-u $$(id -u):$$(id -g) \
		-e HOME=$(TEST_WORKDIR) \
		-e USER=$$(id -un 2>/dev/null || echo tester) \
		$(if $(strip $(PYTEST_ARGS)),-e PYTEST_ARGS="$(PYTEST_ARGS)",) \
		-v "$(CURDIR)":$(TEST_WORKDIR) \
		$(TEST_IMAGE) \
		pytest -xvs --tb=long --capture=no $(PYTEST_ARGS)

test-specific: test-specific-local ## Run specific tests (use PYTEST_ARGS="-k pattern") - local version
test-specific-local: ## Run specific tests using locally installed tooling
	@command -v pytest >/dev/null 2>&1 || { echo "pytest not found; install it (e.g. pip install pytest)." >&2; exit 1; }
	@if [ -z "$(PYTEST_ARGS)" ]; then \
		echo -e "$(COLOR_RED)→ Error: PYTEST_ARGS must be specified for test-specific$(COLOR_OFF)"; \
		echo -e "$(COLOR_YELLOW)→ Example: make test-specific PYTEST_ARGS='-k test_audio'$(COLOR_OFF)"; \
		exit 1; \
	fi
	@echo -e "$(COLOR_CYAN)→ Running specific tests (local): $(PYTEST_ARGS)$(COLOR_OFF)"
	@PYTHONPATH=$(CURDIR)$${PYTHONPATH:+:$$PYTHONPATH} pytest -xvs $(PYTEST_ARGS)

test-specific-container: test-image ## Run specific tests in Docker container
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to run containerized tests." >&2; exit 1; }
	@if [ -z "$(PYTEST_ARGS)" ]; then \
		echo -e "$(COLOR_RED)→ Error: PYTEST_ARGS must be specified for test-specific$(COLOR_OFF)"; \
		echo -e "$(COLOR_YELLOW)→ Example: make test-specific-container PYTEST_ARGS='-k test_audio'$(COLOR_OFF)"; \
		exit 1; \
	fi
	@echo -e "$(COLOR_CYAN)→ Running specific tests (container): $(PYTEST_ARGS)$(COLOR_OFF)"
	@docker run --rm \
		-u $$(id -u):$$(id -g) \
		-e HOME=$(TEST_WORKDIR) \
		-e USER=$$(id -un 2>/dev/null || echo tester) \
		$(if $(strip $(PYTEST_ARGS)),-e PYTEST_ARGS="$(PYTEST_ARGS)",) \
		-v "$(CURDIR)":$(TEST_WORKDIR) \
		$(TEST_IMAGE) \
		pytest -xvs $(PYTEST_ARGS)

# =============================================================================
# LINTING & CODE QUALITY
# =============================================================================

lint: lint-docker ## Run all linters in Docker container (default for local dev)

lint-ci: lint-python lint-mypy lint-yaml lint-dockerfiles lint-makefile lint-markdown ## Run linting with local tools (for CI)
	@echo "✓ All linting checks passed"

# Docker-based linting
lint-docker: lint-image ## Run linting via Docker container
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker." >&2; exit 1; }
	@docker run --rm \
		-u $$(id -u):$$(id -g) \
		-e HOME=$(LINT_WORKDIR) \
		-e USER=$$(id -un 2>/dev/null || echo lint) \
		-v "$(CURDIR)":$(LINT_WORKDIR) \
		$(LINT_IMAGE)

lint-image: ## Build the lint toolchain container image
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to build lint container images." >&2; exit 1; }
	@docker build --pull --tag $(LINT_IMAGE) -f $(LINT_DOCKERFILE) .

# Local linting tools
lint-python: ## Python formatting and linting (black, isort, ruff)
	@echo "→ Checking Python code formatting with black..."
	@command -v black >/dev/null 2>&1 || { echo "black not found" >&2; exit 1; }
	@black --check $(PYTHON_SOURCES)
	@echo "→ Checking Python import sorting with isort..."
	@command -v isort >/dev/null 2>&1 || { echo "isort not found" >&2; exit 1; }
	@isort --check-only $(PYTHON_SOURCES)
	@echo "→ Running Python linting with ruff..."
	@command -v ruff >/dev/null 2>&1 || { echo "ruff not found" >&2; exit 1; }
	@ruff check $(PYTHON_SOURCES)
	@echo "✓ Python linting passed"

lint-mypy: ## Type checking with mypy
	@echo "→ Running type checking with mypy..."
	@command -v mypy >/dev/null 2>&1 || { echo "mypy not found" >&2; exit 1; }
	@mypy $(MYPY_PATHS)
	@echo "✓ Type checking passed"

lint-yaml: ## Lint all YAML files
	@echo "→ Linting YAML files..."
	@command -v yamllint >/dev/null 2>&1 || { echo "yamllint not found" >&2; exit 1; }
	@yamllint $(YAML_FILES)
	@echo "✓ YAML linting passed"

lint-dockerfiles: ## Lint all Dockerfiles
	@echo "→ Linting Dockerfiles..."
	@command -v hadolint >/dev/null 2>&1 || { echo "hadolint not found" >&2; exit 1; }
	@for dockerfile in $(DOCKERFILES); do \
		echo "  Checking $$dockerfile"; \
		hadolint $$dockerfile || exit 1; \
	done
	@echo "✓ Dockerfile linting passed"

lint-makefile: ## Lint Makefile
	@echo "→ Linting Makefile..."
	@command -v checkmake >/dev/null 2>&1 || { echo "checkmake not found" >&2; exit 1; }
	@checkmake Makefile
	@echo "✓ Makefile linting passed"

lint-markdown: ## Lint Markdown files
	@echo "→ Linting Markdown files..."
	@command -v markdownlint >/dev/null 2>&1 || { echo "markdownlint not found" >&2; exit 1; }
	@markdownlint $(MARKDOWN_FILES)
	@echo "✓ Markdown linting passed"

# Code formatting
lint-fix: lint-image ## Format sources using the lint container toolchain
	@command -v docker >/dev/null 2>&1 || { echo "docker not found; install Docker to run containerized linting." >&2; exit 1; }
	@docker run --rm \
		-u $$(id -u):$$(id -g) \
		-e HOME=$(LINT_WORKDIR) \
		-e USER=$$(id -un 2>/dev/null || echo lint) \
		-v "$(CURDIR)":$(LINT_WORKDIR) \
		$(LINT_IMAGE) \
		bash -c "black $(PYTHON_SOURCES) && isort $(PYTHON_SOURCES) && ruff check --fix $(PYTHON_SOURCES) && yamllint $(YAML_FILES) && markdownlint --fix $(MARKDOWN_FILES)"

# =============================================================================
# SECURITY & QUALITY GATES
# =============================================================================

security: ## Run security scanning with pip-audit
	@command -v pip-audit >/dev/null 2>&1 || { echo "pip-audit not found; install it (e.g. pip install pip-audit)." >&2; exit 1; }
	@echo -e "$(COLOR_CYAN)→ Running security scan$(COLOR_OFF)"
	@mkdir -p security-reports; audit_status=0; for req in services/*/requirements.txt; do report="security-reports/$$(basename $$(dirname "$$req"))-requirements.json"; echo "Auditing $$req"; pip-audit --progress-spinner off --format json --requirement "$$req" > "$$report" || audit_status=$$?; done; if [ "$$audit_status" -ne 0 ]; then echo -e "$(COLOR_RED)→ pip-audit reported vulnerabilities$(COLOR_OFF)"; exit $$audit_status; fi; echo -e "$(COLOR_GREEN)→ Security scan completed$(COLOR_OFF)"

# =============================================================================
# CLEANUP & MAINTENANCE
# =============================================================================

clean: ## Remove logs, cached audio artifacts, and debug files
	@echo -e "$(COLOR_BLUE)→ Cleaning...$(COLOR_OFF)"; \
	if [ -d "logs" ]; then echo "Removing logs in ./logs"; rm -rf logs/* || true; fi; \
	if [ -d ".wavs" ]; then echo "Removing saved wavs/sidecars in ./.wavs"; rm -rf .wavs/* || true; fi; \
	if [ -d "debug" ]; then echo "Removing debug files in ./debug"; rm -rf debug/* || true; fi; \
	if [ -d "services" ]; then echo "Removing __pycache__ directories under ./services"; find services -type d -name "__pycache__" -prune -print -exec rm -rf {} + || true; fi

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

# =============================================================================
# CI SETUP & DEPENDENCIES
# =============================================================================

install-dev-deps: ## Install development dependencies for CI
	@echo "→ Installing development dependencies"
	@python -m pip install --upgrade pip
	@pip install -r requirements-dev.txt

install-ci-tools: ## Install CI-specific tools (hadolint, checkmake, markdownlint)
	@echo "→ Installing CI tools"
	@command -v hadolint >/dev/null 2>&1 || { \
		echo "Installing Hadolint..."; \
		curl -sSL https://github.com/hadolint/hadolint/releases/download/v2.12.0/hadolint-Linux-x86_64 \
			-o /usr/local/bin/hadolint && chmod +x /usr/local/bin/hadolint; \
	}
	@command -v checkmake >/dev/null 2>&1 || { \
		echo "Installing Checkmake..."; \
		go install github.com/checkmake/checkmake/cmd/checkmake@latest; \
		echo "$${HOME}/go/bin" >> $$GITHUB_PATH; \
	}
	@command -v markdownlint >/dev/null 2>&1 || { \
		echo "Installing Markdownlint..."; \
		npm install -g markdownlint-cli@0.39.0; \
	}
	@echo "✓ CI tools installed"

ci-setup: install-dev-deps install-ci-tools ## Complete CI environment setup
	@echo "✓ CI environment ready"

# =============================================================================
# DOCUMENTATION & UTILITIES
# =============================================================================

docs-verify: ## Validate documentation last-updated metadata and indexes
	@./scripts/verify_last_updated.py $(ARGS)

# Token management
rotate-tokens: ## Rotate AUTH_TOKEN values across all environment files
	@echo -e "$(COLOR_CYAN)→ Rotating AUTH_TOKEN values$(COLOR_OFF)"
	@./scripts/rotate_auth_tokens.py

rotate-tokens-dry-run: ## Show what token rotation would change without modifying files
	@echo -e "$(COLOR_CYAN)→ Dry run: AUTH_TOKEN rotation preview$(COLOR_OFF)"
	@./scripts/rotate_auth_tokens.py --dry-run

validate-tokens: ## Validate AUTH_TOKEN consistency across environment files
	@echo -e "$(COLOR_CYAN)→ Validating AUTH_TOKEN consistency$(COLOR_OFF)"
	@./scripts/rotate_auth_tokens.py --validate-only

# Model management
models-download: ## Download required models to ./services/models/ subdirectories
	@echo -e "$(COLOR_GREEN)→ Downloading models to ./services/models/$(COLOR_OFF)"
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
	@echo -e "$(COLOR_GREEN)→ Model download complete$(COLOR_OFF)"
	@echo "Models downloaded to:"
	@echo "  - LLM: ./services/models/llm/llama-2-7b.Q4_K_M.gguf"
	@echo "  - TTS: ./services/models/tts/en_US-amy-medium.onnx"
	@echo "  - TTS: ./services/models/tts/en_US-amy-medium.onnx.json"
	@echo "  - STT: ./services/models/stt/medium.en/"

models-clean: ## Remove downloaded models from ./services/models/
	@echo -e "$(COLOR_RED)→ Cleaning downloaded models$(COLOR_OFF)"
	@if [ -d "./services/models" ]; then \
		echo "Removing models from ./services/models/"; \
		rm -rf ./services/models/* || true; \
		echo "Models cleaned."; \
	else \
		echo "No models directory found."; \
	fi

# =============================================================================
# EVALUATION
# =============================================================================

.PHONY: eval-stt eval-stt-all clean-eval

eval-stt: ## Evaluate a single provider on specified phrase files (PROVIDER=stt PHRASES=path1 path2)
	@echo -e "$(COLOR_CYAN)→ Evaluating STT provider $(PROVIDER) on $(PHRASES)$(COLOR_OFF)"; \
	PYTHONPATH=$(CURDIR)$${PYTHONPATH:+:$$PYTHONPATH} \
	python3 scripts/eval_stt.py --provider "$${PROVIDER:-stt}" --phrases $(PHRASES)

eval-wake: ## Evaluate wake phrases with default provider
	@$(MAKE) eval-stt PROVIDER=$${PROVIDER:-stt} PHRASES="tests/fixtures/phrases/en/wake.txt"

eval-stt-all: ## Evaluate across all configured providers
	@set -e; \
	providers="stt"; \
	for p in $$providers; do \
		echo -e "$(COLOR_CYAN)→ Provider: $$p$(COLOR_OFF)"; \
		$(MAKE) eval-stt PROVIDER=$$p PHRASES="tests/fixtures/phrases/en/wake.txt tests/fixtures/phrases/en/core.txt" || echo "Skipped $$p"; \
	done

clean-eval: ## Remove eval outputs and generated audio
	@echo -e "$(COLOR_BLUE)→ Cleaning evaluation artifacts$(COLOR_OFF)"; \
	rm -rf .artifacts/eval_wavs || true; \
	rm -rf debug/eval || true