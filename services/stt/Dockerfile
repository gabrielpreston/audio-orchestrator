# Build stage using shared ML base image
FROM ghcr.io/gabrielpreston/python-ml:latest AS builder

WORKDIR /app

# Copy service-specific requirements
COPY services/stt/requirements.txt /app/services/stt/requirements.txt

# Install Python deps from the copied requirements
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r /app/services/stt/requirements.txt

# Runtime stage using shared ML base image
FROM ghcr.io/gabrielpreston/python-ml:latest

WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY services/common /app/services/common
COPY services/stt /app/services/stt

# Create models directory (faster-whisper models will be mounted via volume)
RUN mkdir -p /app/models

EXPOSE 9000

ENV HOST=0.0.0.0
ENV PORT=9000

CMD ["uvicorn", "services.stt.app:app", "--host", "0.0.0.0", "--port", "9000"]
