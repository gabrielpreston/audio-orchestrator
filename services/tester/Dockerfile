# Use shared tools base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/tools:latest

WORKDIR /workspace

# Copy requirements files FIRST for better caching
COPY services/tester/requirements.txt /workspace/services/tester/requirements.txt
COPY services/requirements-base.txt /workspace/services/requirements-base.txt
COPY services/requirements-test.txt /workspace/services/requirements-test.txt
COPY services/requirements-dev.txt /workspace/services/requirements-dev.txt

# Install Python dependencies with BuildKit cache mount
# hadolint ignore=DL3013
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir -r /workspace/services/tester/requirements.txt

ENTRYPOINT ["/usr/local/bin/run-tests.sh"]
