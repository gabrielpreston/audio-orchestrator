FROM python:3.11-slim
WORKDIR /app

# Install build tools required for llama-cpp-python and common MCP server toolchains
# hadolint ignore=DL3008
RUN apt-get update && \
        apt-get install -y --no-install-recommends \
                build-essential cmake pkg-config libgomp1 libopenblas-dev wget ca-certificates libcurl4-openssl-dev \
                curl git unzip gnupg lsb-release \
                python3-dev python3-pip python3-venv \
                golang-go \
                && rm -rf /var/lib/apt/lists/*

# Install Node.js and npm for MCP servers
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
        apt-get install -y nodejs

# Install Rust for MCP servers that use Rust
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y && \
        . $HOME/.cargo/env && \
        rustup default stable

# Install Go tools for MCP servers
ENV GOPATH=/go
ENV PATH=$GOPATH/bin:/usr/local/go/bin:$PATH

# Pre-install MCP servers to avoid startup delays
RUN npm install -g @mondaydotcomorg/monday-api-mcp@1.4.2

COPY services/llm/requirements.txt /app/services/llm/requirements.txt
COPY services/discord/requirements.txt /app/services/discord/requirements.txt
# hadolint ignore=DL3013
RUN pip install --no-cache-dir -r /app/services/llm/requirements.txt && \
    pip install --no-cache-dir -r /app/services/discord/requirements.txt

COPY services/common /app/services/common
COPY services/llm /app/services/llm

# Create models directory (models will be mounted via volume)
RUN mkdir -p /app/models

ENV PORT=8000
ENV LLAMA_MODEL_PATH=/app/models/llama-2-7b.Q4_K_M.gguf
ENV LLAMA_CTX=2048
ENV LLAMA_THREADS=4

CMD ["uvicorn", "services.llm.app:app", "--host", "0.0.0.0", "--port", "8000"]
