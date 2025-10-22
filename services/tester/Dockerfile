# Use shared tools base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/tools:latest

WORKDIR /workspace

# Install torch for speechbrain mocking support
RUN pip install torch

ENTRYPOINT ["/usr/local/bin/run-tests.sh"]
