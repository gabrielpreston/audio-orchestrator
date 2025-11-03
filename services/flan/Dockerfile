# FLAN-T5 LLM Service Dockerfile
# Multi-stage build with shared base image for optimal caching

FROM ghcr.io/gabrielpreston/python-ml:latest AS builder

WORKDIR /app

# Copy requirements files FIRST for better caching
COPY services/requirements-base.txt /app/services/requirements-base.txt
COPY services/flan/requirements.txt /app/services/flan/requirements.txt

# Install Python dependencies with aggressive cleanup for GitHub Actions
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/services/flan/requirements.txt && \
    find /usr/local/lib/python3.11/site-packages -name "*.pyc" -delete && \
    find /usr/local/lib/python3.11/site-packages -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.11/site-packages -name "tests" -type d -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.11/site-packages -name "test" -type d -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.11/site-packages -name "*.so" -size +10M -delete 2>/dev/null || true

# Runtime stage
FROM ghcr.io/gabrielpreston/python-ml:latest

WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create models directory and clean up unnecessary files
RUN --mount=type=cache,target=/var/cache/apt \
    mkdir -p /app/models && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
    echo "LLM environment configured"

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8100
ENV FLAN_T5_MODEL_SIZE=google/flan-t5-large
ENV LLM_FLAN_SERVICE_PORT=8100
ENV LLM_FLAN_SERVICE_HOST=0.0.0.0

# Copy application code LAST (changes most frequently)
COPY services/flan /app/services/flan
COPY services/common /app/services/common
COPY scripts/health_check.py /app/scripts/health_check.py

# Create user with matching UID/GID for torch.compile() compatibility
# This fixes getpwuid() errors in Docker containers without /etc/passwd entries
ARG PUID=1000
ARG PGID=1000

RUN groupadd -g ${PGID} appuser 2>/dev/null || true && \
    useradd -u ${PUID} -g ${PGID} -ms /bin/bash appuser 2>/dev/null || true && \
    chown -R ${PUID}:${PGID} /app 2>/dev/null || true

USER appuser

# Extended start-period to allow for model loading, compilation, and pre-warming
HEALTHCHECK --interval=10s --timeout=5s --start-period=60s --retries=6 \
    CMD python /app/scripts/health_check.py http://localhost:8100/health/ready --ci


# Expose port
EXPOSE 8100

# Run the service
CMD ["uvicorn", "services.flan.app:app", "--host", "0.0.0.0", "--port", "8100"]
