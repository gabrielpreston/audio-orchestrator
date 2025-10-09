FROM python:3.11-slim
WORKDIR /app

# Install build tools required for llama-cpp-python
RUN apt-get update && \
        apt-get install -y --no-install-recommends \
                build-essential cmake pkg-config libgomp1 libopenblas-dev wget ca-certificates libcurl4-openssl-dev && \
        rm -rf /var/lib/apt/lists/*

COPY services/llm/requirements.txt /app/services/llm/requirements.txt
RUN pip install --no-cache-dir -r /app/services/llm/requirements.txt

COPY services /app/services

ENV PORT=8000
ENV LLAMA_MODEL_PATH=/app/models/llama2-7b.gguf
ENV LLAMA_CTX=2048
ENV LLAMA_THREADS=4

CMD ["uvicorn", "services.llm.app:app", "--host", "0.0.0.0", "--port", "8000"]
