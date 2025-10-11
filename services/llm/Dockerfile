FROM python:3.11-slim
WORKDIR /app

# Install build tools required for llama-cpp-python
# hadolint ignore=DL3008
RUN apt-get update && \
        apt-get install -y --no-install-recommends \
                build-essential cmake pkg-config libgomp1 libopenblas-dev wget ca-certificates libcurl4-openssl-dev && \
        rm -rf /var/lib/apt/lists/*

COPY services/llm/requirements.txt /app/services/llm/requirements.txt
# hadolint ignore=DL3013
RUN pip install --no-cache-dir -r /app/services/llm/requirements.txt

COPY services/common /app/services/common
COPY services/llm /app/services/llm

# Create models directory (models will be mounted via volume)
RUN mkdir -p /app/models

ENV PORT=8000
ENV LLAMA_MODEL_PATH=/app/models/llama-2-7b.Q4_K_M.gguf
ENV LLAMA_CTX=2048
ENV LLAMA_THREADS=4

CMD ["uvicorn", "services.llm.app:app", "--host", "0.0.0.0", "--port", "8000"]
