FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install runtime dependencies required for voice capture and playback
# hadolint ignore=DL3008
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        build-essential \
        ffmpeg \
        libffi-dev \
        libsodium-dev \
        libopus0 \
    && rm -rf /var/lib/apt/lists/*

COPY services/discord/requirements.txt /app/services/discord/requirements.txt
# hadolint ignore=DL3013
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install -r /app/services/discord/requirements.txt

COPY services/common /app/services/common
COPY services/discord /app/services/discord

CMD ["python", "-m", "services.discord.main"]
