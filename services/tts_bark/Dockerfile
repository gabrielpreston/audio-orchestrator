# Build stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest AS builder

WORKDIR /app

# Copy service-specific requirements
COPY services/tts_bark/requirements.txt /app/services/tts_bark/requirements.txt
COPY services/requirements-base.txt /app/services/requirements-base.txt
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/services/tts_bark/requirements.txt

# Runtime stage using shared ML base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-ml:latest

WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY services/common /app/services/common
COPY services/tts_bark /app/services/tts_bark
COPY scripts/health_check.py /app/scripts/health_check.py

# Create models directory
RUN mkdir -p /app/models

ENV PORT=7100
ENV BARK_USE_SMALL_MODELS=false

CMD ["uvicorn", "services.tts_bark.app:app", "--host", "0.0.0.0", "--port", "7100"]
