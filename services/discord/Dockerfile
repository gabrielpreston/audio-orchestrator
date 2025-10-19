# Use shared audio base image
FROM discord-voice-lab/python-audio:latest as base

WORKDIR /app

# Copy service-specific requirements
COPY services/discord/requirements.txt /app/services/discord/requirements.txt
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r /app/services/discord/requirements.txt

COPY services/common /app/services/common
COPY services/discord /app/services/discord

CMD ["python", "-m", "services.discord.main"]
