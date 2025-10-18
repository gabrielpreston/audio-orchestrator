# Build stage for MCP toolchains
FROM python:3.11-slim as mcp-builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install build tools required for MCP server toolchains
# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential cmake pkg-config libgomp1 libopenblas-dev wget ca-certificates libcurl4-openssl-dev \
    curl git unzip gnupg lsb-release \
    python3-dev python3-pip python3-venv \
    golang-go \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js and npm for MCP servers
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y --no-install-recommends nodejs=18.*

# Install Rust for MCP servers that use Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
RUN /root/.cargo/bin/rustup default stable

# Install Go tools for MCP servers
ENV GOPATH=/go
ENV PATH=$GOPATH/bin:/usr/local/go/bin:$PATH

# Pre-install MCP servers to avoid startup delays
RUN npm install -g @mondaydotcomorg/monday-api-mcp@1.4.2

# Python dependencies stage
FROM python:3.11-slim as python-builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install build dependencies for Python packages
# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential cmake pkg-config libgomp1 libopenblas-dev wget ca-certificates libcurl4-openssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files
COPY requirements-base.txt /app/requirements-base.txt
COPY services/orchestrator/requirements.txt /app/services/orchestrator/requirements.txt
COPY services/discord/requirements.txt /app/services/discord/requirements.txt
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/services/orchestrator/requirements.txt && \
    pip install --no-cache-dir -r /app/services/discord/requirements.txt

# Runtime stage
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install runtime dependencies including Go and audio processing tools
# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgomp1 libopenblas-dev ca-certificates libcurl4-openssl-dev \
    curl git golang-go \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy Node.js and npm from MCP builder
COPY --from=mcp-builder /usr/bin/node /usr/bin/node
COPY --from=mcp-builder /usr/bin/npm /usr/bin/npm
COPY --from=mcp-builder /usr/lib/node_modules /usr/lib/node_modules
# Copy Rust toolchain from MCP builder
COPY --from=mcp-builder /root/.cargo /root/.cargo
COPY --from=mcp-builder /root/.rustup /root/.rustup

# Copy Go toolchain from MCP builder (Go is installed via apt, not in /usr/local/go)
# COPY --from=mcp-builder /usr/local/go /usr/local/go

# Set up environment for MCP tools
ENV GOPATH=/go
ENV PATH=$GOPATH/bin:/usr/local/go/bin:/root/.cargo/bin:$PATH

# Copy Python packages from python builder
COPY --from=python-builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=python-builder /usr/local/bin /usr/local/bin

COPY services/common /app/services/common
COPY services/orchestrator /app/services/orchestrator

# Create recordings directory
RUN mkdir -p /app/recordings

# Create debug directory
RUN mkdir -p /app/debug

ENV PORT=8000

CMD ["uvicorn", "services.orchestrator.app:app", "--host", "0.0.0.0", "--port", "8000"]