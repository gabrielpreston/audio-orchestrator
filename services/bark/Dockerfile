# Build stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest AS builder

WORKDIR /app

# Copy requirements files
COPY services/requirements-base.txt /app/services/requirements-base.txt
COPY services/bark/requirements.txt /app/services/bark/requirements.txt
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/services/bark/requirements.txt

# Runtime stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest

WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create models directory
RUN mkdir -p /app/models && \
    echo "TTS environment configured"

# Copy application code LAST (changes most frequently)
COPY services/common /app/services/common
COPY services/bark /app/services/bark
COPY scripts/health_check.py /app/scripts/health_check.py

# Extended start-period to allow for model loading, compilation, and pre-warming
# Pre-warming can take 60-120s with torch.compile() max-autotune-no-cudagraphs mode
HEALTHCHECK --interval=10s --timeout=5s --start-period=180s --retries=12 \
    CMD python /app/scripts/health_check.py http://localhost:7100/health/ready --ci

# Create user with matching UID/GID for torch.compile() compatibility
# This fixes getpwuid() errors in Docker containers
ARG PUID=1000
ARG PGID=1000

RUN groupadd -g ${PGID} appuser 2>/dev/null || true && \
    useradd -l -u ${PUID} -g ${PGID} -ms /bin/bash appuser 2>/dev/null || true && \
    chown -R ${PUID}:${PGID} /app 2>/dev/null || true

USER appuser

CMD ["uvicorn", "services.bark.app:app", "--host", "0.0.0.0", "--port", "7100"]
