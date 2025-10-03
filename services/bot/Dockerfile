### Builder stage: compile the Go bot
FROM golang:1.25.1 AS builder
WORKDIR /src

# Install native build dependencies required for cgo (opus)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential pkg-config libopus-dev libopusfile-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Cache deps
COPY go.mod go.sum ./
RUN go env -w GOPROXY=https://proxy.golang.org && go mod download

# Copy source and build
COPY . .
# Build with cgo enabled so hraban/opus can be compiled against system opus
# When the build context is `./services` the bot package lives at ./bot/cmd/bot
RUN CGO_ENABLED=1 GO111MODULE=on GOOS=linux GOARCH=amd64 \
    go build -o /out/bot ./bot/cmd/bot


### Final runtime image
FROM debian:stable-slim
# The bot binary is built with cgo against libopus (hraban/opus) and requires
# libopus and libopusfile available at runtime. Install both packages so the
# binary can load `libopusfile.so.0` inside the slim runtime image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopus0 libopusfile0 ca-certificates tini && rm -rf /var/lib/apt/lists/*

COPY --from=builder /out/bot /usr/local/bin/bot

# Use tini as PID 1 to forward signals cleanly
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/usr/local/bin/bot"]
