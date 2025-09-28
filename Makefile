.PHONY: test build

test:
	go test ./...

build:
	go build ./...

bot-build:
	go build -o bin/bot ./cmd/bot

bot-run: bot-build
	./scripts/run_bot.sh
