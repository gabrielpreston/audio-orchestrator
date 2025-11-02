#!/bin/sh
# Entrypoint script for Grafana that maps project-standard LOG_LEVEL from .env.common
#
# IMPORTANT: Grafana 10.2.2 OSS does NOT support JSON log format.
# JSON logging is only available in Grafana Enterprise.
# We always use "console" format for OSS version, which is the default and works reliably.
#
# Grafana interprets GF_LOG_MODE environment variable, but "json" value causes errors
# in OSS version. We use "console" which produces structured key-value logs that
# can be parsed if needed.

# Always use console format for OSS version
# GF_LOG_MODE valid values: console, file (not json for OSS)
LOG_MODE="console"

# If explicitly overridden, use that value (but note json will fail in OSS)
if [ -n "${GF_LOG_MODE_OVERRIDE}" ]; then
    LOG_MODE="${GF_LOG_MODE_OVERRIDE}"
fi

# Set Grafana environment variables
# GF_LOG_MODE maps to [log] mode setting
export GF_LOG_MODE="${LOG_MODE}"
export GF_LOG_LEVEL="${LOG_LEVEL:-info}"

# Debug: log what we're setting (will appear in Grafana logs)
echo "Grafana logging configuration: GF_LOG_MODE=${LOG_MODE} (OSS limitation: json not supported), LOG_LEVEL=${LOG_LEVEL:-info}"

# Execute Grafana's default entrypoint
exec /run.sh "$@"
