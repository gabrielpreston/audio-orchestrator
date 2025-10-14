FROM python:3.11-slim
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

COPY services/orchestrator/requirements.txt /app/services/orchestrator/requirements.txt
COPY services/discord/requirements.txt /app/services/discord/requirements.txt
# hadolint ignore=DL3013
RUN pip install --no-cache-dir -r /app/services/orchestrator/requirements.txt && \
    pip install --no-cache-dir -r /app/services/discord/requirements.txt

COPY services/common /app/services/common
COPY services/orchestrator /app/services/orchestrator

# Create debug directory
RUN mkdir -p /app/debug

ENV PORT=8000

CMD ["uvicorn", "services.orchestrator.app:app", "--host", "0.0.0.0", "--port", "8000"]