# Use shared tools base image
FROM ghcr.io/gabrielpreston/tools:latest

WORKDIR /workspace

# Copy all linting scripts
COPY services/linter/run-lint-parallel.sh /usr/local/bin/
COPY services/linter/run-lint-fix.sh /usr/local/bin/
COPY services/linter/run-lint-single.sh /usr/local/bin/

# Make scripts executable
RUN chmod +x /usr/local/bin/run-lint-*.sh

# No ENTRYPOINT - let Makefile specify exactly what to run