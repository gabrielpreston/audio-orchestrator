# Use shared tools base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/tools:latest

WORKDIR /workspace

# Install additional linting tools (pin Ruff for stable GitHub formatting)
RUN pip install \
    ruff==0.6.7 \
    bandit \
    detect-secrets \
    radon

# No ENTRYPOINT - let Makefile specify exactly what to run
# Scripts are mounted as volumes at runtime from services/linter/
