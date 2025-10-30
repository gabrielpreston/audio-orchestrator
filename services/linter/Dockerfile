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

# Copy linting scripts
COPY services/linter/run-lint.sh /usr/local/bin/
COPY services/linter/run-lint-fix.sh /usr/local/bin/

# Make scripts executable
RUN chmod +x /usr/local/bin/run-lint.sh /usr/local/bin/run-lint-fix.sh

# No ENTRYPOINT - let Makefile specify exactly what to run

# Copy specialized linting scripts
COPY services/linter/run-lint-python.sh /usr/local/bin/
COPY services/linter/run-lint-yaml.sh /usr/local/bin/
COPY services/linter/run-lint-markdown.sh /usr/local/bin/
COPY services/linter/run-lint-security.sh /usr/local/bin/
COPY services/linter/run-lint-complexity.sh /usr/local/bin/
COPY services/linter/run-lint-dockerfile.sh /usr/local/bin/
COPY services/linter/run-lint-makefile.sh /usr/local/bin/
COPY services/linter/update-secrets-baseline.sh /usr/local/bin/

# Make all scripts executable
RUN chmod +x /usr/local/bin/run-lint*.sh /usr/local/bin/update-secrets-baseline.sh
