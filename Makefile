SHELL := /bin/bash
.PHONY: help test build bot fmt vet lint run clean ci version

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

run: build ## Build then run the bot via script
	@echo -e "$(COLOR_GREEN)🚀 Launching bot (press Ctrl+C to stop)$(COLOR_OFF)"
	./scripts/run_bot.sh

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

ci: fmt vet test lint ## Run CI-like checks locally
	@echo -e "$(COLOR_MAGENTA)✓ CI checks complete (locally)$(COLOR_OFF)"

version: ## Show Go version and module info
	@echo -e "$(COLOR_CYAN)→ Go version:$(COLOR_OFF)"; $(GO) version
	@echo -e "$(COLOR_CYAN)→ Module:$(COLOR_OFF)"; cat go.mod | sed -n '1,3p'

# end of file

.DEFAULT_GOAL := help
