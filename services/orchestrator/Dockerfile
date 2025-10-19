# Build stage for MCP toolchains using shared base
FROM discord-voice-lab/mcp-toolchain:latest as mcp-builder

WORKDIR /app

# Python dependencies stage using shared ML base
FROM discord-voice-lab/python-ml:latest as python-builder

WORKDIR /app

# Copy requirements files
COPY services/orchestrator/requirements.txt /app/services/orchestrator/requirements.txt
COPY services/discord/requirements.txt /app/services/discord/requirements.txt
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/services/orchestrator/requirements.txt && \
    pip install --no-cache-dir -r /app/services/discord/requirements.txt

# Runtime stage using shared ML base
FROM discord-voice-lab/python-ml:latest

WORKDIR /app

# Install runtime dependencies including Go
# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl git golang-go \
    && rm -rf /var/lib/apt/lists/*

# Copy Node.js and npm from MCP builder
COPY --from=mcp-builder /usr/bin/node /usr/bin/node
COPY --from=mcp-builder /usr/bin/npm /usr/bin/npm
COPY --from=mcp-builder /usr/lib/node_modules /usr/lib/node_modules
# Copy Rust toolchain from MCP builder
COPY --from=mcp-builder /root/.cargo /root/.cargo
COPY --from=mcp-builder /root/.rustup /root/.rustup

# Set up environment for MCP tools
ENV GOPATH=/go
ENV PATH=$GOPATH/bin:/usr/local/go/bin:/root/.cargo/bin:$PATH

# Copy Python packages from python builder
COPY --from=python-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python-builder /usr/local/bin /usr/local/bin

COPY services/common /app/services/common
COPY services/orchestrator /app/services/orchestrator

# Create debug directory
RUN mkdir -p /app/debug

ENV PORT=8000

CMD ["uvicorn", "services.orchestrator.app:app", "--host", "0.0.0.0", "--port", "8000"]