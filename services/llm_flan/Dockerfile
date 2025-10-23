# FLAN-T5 LLM Service Dockerfile
# Multi-stage build with shared base image for optimal caching

FROM ghcr.io/gabrielpreston/python-ml:latest AS builder

WORKDIR /app

# Copy requirements FIRST for better caching
COPY services/llm_flan/requirements.txt /app/services/llm_flan/requirements.txt
COPY services/requirements-base.txt /app/services/requirements-base.txt

# Install Python dependencies with BuildKit cache mount
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/services/llm_flan/requirements.txt

# Runtime stage
FROM ghcr.io/gabrielpreston/python-ml:latest

WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code LAST (changes most frequently)
COPY services/llm_flan /app/services/llm_flan
COPY services/common /app/services/common
COPY scripts/health_check.py /app/scripts/health_check.py

# Create models directory (models will be downloaded on first run)
RUN mkdir -p /app/models

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8100
ENV FLAN_T5_MODEL_SIZE=google/flan-t5-large
ENV LLM_FLAN_SERVICE_PORT=8100
ENV LLM_FLAN_SERVICE_HOST=0.0.0.0

# Health check
HEALTHCHECK --interval=10s --timeout=5s --start-period=45s --retries=3 \
    CMD python /app/scripts/health_check.py http://localhost:8100/health/ready --timeout 5

# Expose port
EXPOSE 8100

# Run the service
CMD ["uvicorn", "services.llm_flan.app:app", "--host", "0.0.0.0", "--port", "8100"]