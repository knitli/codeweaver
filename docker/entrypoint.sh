#!/usr/bin/env sh
set -eu

# =============================================================================
# CodeWeaver Docker Entrypoint
# =============================================================================
# Handles profile-based configuration generation and provider validation
# =============================================================================

# Configuration defaults
PROFILE="${CODEWEAVER_PROFILE:-recommended}"
VECTOR_DEPLOYMENT="${CODEWEAVER_VECTOR_DEPLOYMENT:-local}"
VECTOR_URL="${CODEWEAVER_VECTOR_URL:-}"
CONFIG_DIR="${XDG_CONFIG_HOME:-/app/config}/codeweaver"
CONFIG_FILE="${CONFIG_DIR}/codeweaver.toml"

# Ensure config directory exists
mkdir -p "$CONFIG_DIR"

# =============================================================================
# Configuration Generation
# =============================================================================

generate_config() {
    echo "Generating CodeWeaver configuration..."
    echo "  Profile: $PROFILE"
    echo "  Vector deployment: $VECTOR_DEPLOYMENT"

    # Build init command
    INIT_CMD="codeweaver init config --profile $PROFILE --config-path $CONFIG_FILE --force"
    INIT_CMD="$INIT_CMD --vector-deployment $VECTOR_DEPLOYMENT"

    if [ -n "$VECTOR_URL" ]; then
        INIT_CMD="$INIT_CMD --vector-url $VECTOR_URL"
    fi

    # Generate config
    eval $INIT_CMD

    # Post-process: Override Qdrant URL for Docker networking (local deployment)
    if [ "$VECTOR_DEPLOYMENT" = "local" ]; then
        QDRANT_URL="${CODEWEAVER_QDRANT_URL:-http://qdrant:6333}"
        if command -v sed >/dev/null 2>&1; then
            # Update Qdrant URL to use Docker network hostname
            sed -i "s|url = \"http://localhost:6333\"|url = \"$QDRANT_URL\"|g" "$CONFIG_FILE" 2>/dev/null || true
            sed -i "s|url = \"http://127.0.0.1:6333\"|url = \"$QDRANT_URL\"|g" "$CONFIG_FILE" 2>/dev/null || true
        fi
    fi

    echo ""
    echo "Configuration generated at: $CONFIG_FILE"
    echo ""
    echo "To customize your configuration:"
    echo "  1. Copy config out:  docker cp codeweaver-server:$CONFIG_FILE ./codeweaver.toml"
    echo "  2. Edit locally:     vim codeweaver.toml"
    echo "  3. Mount in docker-compose.yml:"
    echo "     volumes:"
    echo "       - ./codeweaver.toml:$CONFIG_FILE:ro"
    echo ""
}

# Check if config exists or if we should generate it
# CodeWeaver auto-discovers config in: $XDG_CONFIG_HOME/codeweaver/codeweaver.toml
# Also checks: /workspace/codeweaver.toml, /workspace/.codeweaver/codeweaver.toml, etc.
if [ -f "$CONFIG_FILE" ]; then
    echo "Using existing configuration: $CONFIG_FILE"
else
    generate_config
fi

# =============================================================================
# Provider Validation
# =============================================================================

# Normalize provider name to lowercase
normalize_provider() {
    if [ -n "$1" ]; then
        printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
    else
        printf '%s' "$2"
    fi
}

# Check if profile requires API keys
validate_api_keys() {
    case "$PROFILE" in
        recommended)
            # Recommended profile uses Voyage AI
            if [ -z "${VOYAGE_API_KEY:-}" ]; then
                cat >&2 <<'EOF'
╔════════════════════════════════════════════════════════════════════════════╗
║  CodeWeaver - API Key Required                                              ║
╠════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  The 'recommended' profile uses Voyage AI for embeddings and reranking.     ║
║  VOYAGE_API_KEY environment variable is not set.                            ║
║                                                                              ║
║  Options:                                                                    ║
║                                                                              ║
║  1. Set VOYAGE_API_KEY (get free key at https://voyage.ai/):                ║
║     docker run -e VOYAGE_API_KEY="sk-..." knitli/codeweaver:latest          ║
║                                                                              ║
║  2. Use 'quickstart' profile (free, local models):                          ║
║     docker run -e CODEWEAVER_PROFILE=quickstart knitli/codeweaver:latest    ║
║                                                                              ║
║  3. Use 'backup' profile (lightest local models, in-memory vectors):        ║
║     docker run -e CODEWEAVER_PROFILE=backup knitli/codeweaver:latest        ║
║                                                                              ║
╚════════════════════════════════════════════════════════════════════════════╝
EOF
                exit 78  # EX_CONFIG
            fi
            ;;
        quickstart|backup)
            # These profiles use local models - no API keys required
            echo "Using '$PROFILE' profile with local models (no API keys required)"
            ;;
        *)
            echo "Warning: Unknown profile '$PROFILE', skipping API key validation"
            ;;
    esac
}

validate_api_keys

# =============================================================================
# Startup Information
# =============================================================================

echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║  CodeWeaver MCP Server                                                     ║"
echo "╠════════════════════════════════════════════════════════════════════════════╣"
printf "║  Profile: %-66s ║\n" "$PROFILE"
printf "║  Config:  %-66s ║\n" "$CONFIG_FILE"
printf "║  Project: %-66s ║\n" "${CODEWEAVER_PROJECT_PATH:-/workspace}"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Execute the main command
exec "$@"
