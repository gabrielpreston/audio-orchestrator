# Use shared web base image (includes audio system libs)
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/python-web:latest AS base

WORKDIR /app

# Copy service-specific requirements and constraints FIRST for better caching
COPY services/discord/requirements.txt /app/services/discord/requirements.txt

# Install Python dependencies with BuildKit cache mount and wheel caching
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/tmp/wheels \
    pip install --no-cache-dir --find-links=/tmp/wheels -r /app/services/discord/requirements.txt

# Set Python environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy application code LAST (changes most frequently)
COPY services/common /app/services/common
COPY services/discord /app/services/discord
COPY scripts/health_check.py /app/scripts/health_check.py

HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=6 \
    CMD python /app/scripts/health_check.py http://localhost:8001/health/ready --ci

CMD ["python", "-m", "services.discord.main"]
