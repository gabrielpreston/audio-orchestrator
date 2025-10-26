#!/usr/bin/env bash
set -euo pipefail

# Resolve script directory for reliable path handling
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source color definitions from Makefile environment
COLOR_OFF=${COLOR_OFF:-'\033[0m'}
COLOR_GREEN=${COLOR_GREEN:-'\033[32m'}
COLOR_YELLOW=${COLOR_YELLOW:-'\033[33m'}
COLOR_CYAN=${COLOR_CYAN:-'\033[36m'}
COLOR_BLUE=${COLOR_BLUE:-'\033[34m'}
COLOR_RED=${COLOR_RED:-'\033[31m'}

# Export Docker BuildKit settings
export DOCKER_BUILDKIT="${DOCKER_BUILDKIT:-1}"
export COMPOSE_DOCKER_CLI_BUILD="${COMPOSE_DOCKER_CLI_BUILD:-1}"

DOCKER_COMPOSE="${DOCKER_COMPOSE:-docker-compose}"
START_TIME=$(date +%s)

# Detect changes
printf "${COLOR_CYAN}🔍 Detecting changes...${COLOR_OFF}\n"
CHANGED=$("$SCRIPT_DIR/detect-changed-services.sh" "$@")

printf "${COLOR_BLUE}Changed: $CHANGED${COLOR_OFF}\n"
echo ""

# Handle different cases
case "$CHANGED" in
    "none")
        printf "${COLOR_GREEN}✓ No service changes detected${COLOR_OFF}\n"
        printf "${COLOR_YELLOW}All services up to date (using Docker layer cache)${COLOR_OFF}\n"
        exit 0
        ;;
    "all")
        printf "${COLOR_YELLOW}⚠ Common files changed - rebuilding ALL services${COLOR_OFF}\n"
        echo "  Reason: services/common/, requirements-base.txt, or .dockerignore changed"
        echo ""
        SERVICES="discord stt llm-flan orchestrator-enhanced tts-bark"
        ;;
    "base-images")
        printf "${COLOR_RED}⚠ Base images changed - manual rebuild required${COLOR_OFF}\n"
        echo ""
        echo "  Base images need to be rebuilt first:"
        printf "    ${COLOR_CYAN}make base-images${COLOR_OFF}\n"
        echo ""
        echo "  Then rebuild all services:"
        printf "    ${COLOR_CYAN}make docker-build${COLOR_OFF}\n"
        echo ""
        exit 1
        ;;
    *)
        SERVICES="$CHANGED"
        printf "${COLOR_GREEN}✓ Selective rebuild${COLOR_OFF}\n"
        echo "  Building: $SERVICES"
        echo "  Skipping: $(echo "discord stt llm-flan orchestrator-enhanced tts-bark" | tr ' ' '\n' | grep -v -w -f <(echo "$SERVICES" | tr ' ' '\n') | xargs)"
        echo ""
        ;;
esac

# Build services with enhanced monitoring
printf "${COLOR_GREEN}🏗️  Building services...${COLOR_OFF}\n"
for service in $SERVICES; do
    printf "${COLOR_CYAN}  → Building $service${COLOR_OFF}\n"
    SERVICE_START=$(date +%s)
    
    # Build with enhanced cache options
    if $DOCKER_COMPOSE build --build-arg BUILDKIT_INLINE_CACHE=1 "$service"; then
        SERVICE_END=$(date +%s)
        SERVICE_DURATION=$((SERVICE_END - SERVICE_START))
        printf "${COLOR_GREEN}    ✓ $service built in ${SERVICE_DURATION}s${COLOR_OFF}\n"
    else
        printf "${COLOR_RED}    ✗ $service build failed${COLOR_OFF}\n"
        exit 1
    fi
done

# Calculate time
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Estimate savings (rough heuristic: full build ~10min, single service ~2min)
FULL_BUILD_TIME=600  # 10 minutes average
SERVICE_COUNT=$(echo "$SERVICES" | wc -w)
TOTAL_SERVICES=5
if [ "$SERVICE_COUNT" -lt "$TOTAL_SERVICES" ]; then
    ESTIMATED_FULL=$FULL_BUILD_TIME
    SAVED=$((ESTIMATED_FULL - DURATION))
    PERCENT_SAVED=$((SAVED * 100 / ESTIMATED_FULL))
else
    SAVED=0
    PERCENT_SAVED=0
fi

echo ""
printf "${COLOR_GREEN}✨ Build complete in ${DURATION}s${COLOR_OFF}\n"
if [ "$SAVED" -gt 0 ]; then
    printf "${COLOR_BLUE}   Estimated savings: ~${SAVED}s (${PERCENT_SAVED}%) vs full rebuild${COLOR_OFF}\n"
fi
