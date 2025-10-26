# Use shared audio base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-audio:latest AS base

WORKDIR /app

# Copy service-specific requirements FIRST for better caching
COPY services/discord/requirements.txt /app/services/discord/requirements.txt
COPY services/requirements-base.txt /app/services/requirements-base.txt

# Install Python dependencies with BuildKit cache mount
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /app/services/discord/requirements.txt

# Set Python environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy application code LAST (changes most frequently)
COPY services/common /app/services/common
COPY services/discord /app/services/discord
COPY scripts/health_check.py /app/scripts/health_check.py

CMD ["python", "-m", "services.discord.main"]
