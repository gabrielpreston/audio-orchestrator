.PHONY: test build

test:
	go test -v ./...

build:
	go build ./...

bot-build:
	go build -o bin/bot ./cmd/bot

bot: bot-build
	./scripts/run_bot.sh
