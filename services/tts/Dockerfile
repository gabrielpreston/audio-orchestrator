# Build stage
FROM python:3.11-slim as builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Copy requirements files
COPY requirements-base.txt /app/requirements-base.txt
COPY services/tts/requirements.txt /app/services/tts/requirements.txt

# Install Python dependencies
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install --upgrade pip setuptools wheel && \
    pip install -r /app/services/tts/requirements.txt

# Runtime stage
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies required for Piper + espeak phonemizer
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng \
    libespeak-ng1 \
    libasound2 \
    libsndfile1 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY services/common /app/services/common
COPY services/tts /app/services/tts

# Create models directory (Piper models will be mounted via volume)
RUN mkdir -p /app/models

EXPOSE 7000

ENV HOST=0.0.0.0
ENV PORT=7000

CMD ["uvicorn", "services.tts.app:app", "--host", "0.0.0.0", "--port", "7000"]
