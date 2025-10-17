# Build stage
FROM python:3.11-slim as builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install build dependencies
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    libsndfile1 \
    pkg-config \
    libavdevice-dev libavformat-dev libavfilter-dev libavcodec-dev libavutil-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements files
COPY requirements-base.txt /app/requirements-base.txt
COPY services/stt/requirements.txt /app/services/stt/requirements.txt

# Install Python deps from the copied requirements
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip setuptools wheel && \
    pip install -r /app/services/stt/requirements.txt

# Runtime stage
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install only runtime dependencies
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    libavdevice-dev libavformat-dev libavfilter-dev libavcodec-dev libavutil-dev \
    && rm -rf /var/lib/apt/lists/*

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
