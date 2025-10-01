FROM ubuntu:24.04

# Install build deps and runtime
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    build-essential cmake git python3 python3-venv python3-pip wget unzip libopenblas-dev \
    libcurl4-openssl-dev ccache pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Create app dir
WORKDIR /app

# Install python deps
COPY requirements.txt /app/requirements.txt
# Create a venv to avoid PEP 668 / externally-managed-environment errors
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --upgrade pip setuptools wheel \
    && /opt/venv/bin/pip install --no-cache-dir -r /app/requirements.txt

# Ensure venv binaries are used by default
ENV PATH="/opt/venv/bin:${PATH}"

# Clone and build llama.cpp (will use CPU ggml/GGUF runtime)
RUN git clone --depth 1 https://github.com/ggerganov/llama.cpp.git /app/llama.cpp \
    && cd /app/llama.cpp \
    && mkdir -p build && cd build \
    && cmake .. -DLLAMA_USE_ACCELERATE=OFF -DCMAKE_BUILD_TYPE=Release \
    && cmake --build . --parallel

# Copy app
COPY app.py /app/app.py
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

VOLUME ["/app/models"]

EXPOSE 5000

CMD ["/app/entrypoint.sh"]
