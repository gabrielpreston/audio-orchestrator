FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install runtime dependencies required for voice capture and playback
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        ffmpeg \
        libffi-dev \
        libsodium-dev \
        libopus0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/services/discord/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install -r /app/services/discord/requirements.txt

COPY . /app/services/discord

CMD ["python", "-m", "services.discord.main"]
