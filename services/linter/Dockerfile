# Use shared tools base image
# hadolint ignore=DL3007
FROM ghcr.io/gabrielpreston/tools:latest

WORKDIR /workspace

# Install additional linting tools
RUN pip install bandit detect-secrets radon

# Copy linting scripts
COPY services/linter/run-lint.sh /usr/local/bin/
COPY services/linter/run-lint-fix.sh /usr/local/bin/

# Make scripts executable
RUN chmod +x /usr/local/bin/run-lint.sh /usr/local/bin/run-lint-fix.sh

# No ENTRYPOINT - let Makefile specify exactly what to run
