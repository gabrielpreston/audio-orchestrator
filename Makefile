SHELL := /bin/bash
.PHONY: test build bot

test:
	go test -v ./...

build:
	go build -o bin/bot ./cmd/bot

bot: build
	./scripts/run_bot.sh
