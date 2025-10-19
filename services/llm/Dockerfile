# Build stage using shared ML base image
FROM discord-voice-lab/python-ml:latest as builder

WORKDIR /app

# Copy service-specific requirements
COPY services/llm/requirements.txt /app/services/llm/requirements.txt
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/services/llm/requirements.txt

# Runtime stage using shared ML base image
FROM discord-voice-lab/python-ml:latest

WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY services/common /app/services/common
COPY services/llm /app/services/llm

# Create models directory (models will be mounted via volume)
RUN mkdir -p /app/models

ENV PORT=8000
ENV LLAMA_MODEL_PATH=/app/models/llama-2-7b.Q4_K_M.gguf
ENV LLAMA_CTX=2048
ENV LLAMA_THREADS=4

CMD ["uvicorn", "services.llm.app:app", "--host", "0.0.0.0", "--port", "8000"]