# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# Multi-stage build for CodeWeaver MCP Server
# Optimized for production deployment with Qdrant integration

# =============================================================================
# Stage 1: Builder - Install dependencies and build the application
# =============================================================================
FROM python:3.12-slim AS builder

# Build arguments for versioning
ARG VERSION
ARG BUILD_DATE
ARG VCS_REF

# Install uv for workspace-aware package building
# uv-dynamic-versioning derives a single VCS version for all workspace packages;
# uv build ensures all workspace members resolve the same git-derived version
# consistently, which is critical for the root package's exact-version pins
# on code-weaver-daemon and code-weaver-tokenizers.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Install system dependencies required for building Python packages
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && update-ca-certificates

# Set working directory
WORKDIR /app

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock README.md SECURITY.md sbom.spdx ./
COPY LICENSE* ./
COPY LICENSES/ LICENSES/
COPY packages/ packages/
COPY .git/ .git/
COPY typings/ typings/

# Create minimal package structure for initial dependency installation
# This allows Docker to cache the expensive dependency layer
RUN mkdir -p src/codeweaver && \
    echo "# Placeholder for initial build" > src/codeweaver/__init__.py

# Build all workspace wheels with consistent VCS-derived versions.
# uv-dynamic-versioning ensures code-weaver, code-weaver-daemon, and
# code-weaver-tokenizers all share the same git-tag-derived version, so
# the root wheel's `code-weaver-daemon=={{ version }}` pin resolves.
RUN uv build --wheel --all-packages --out-dir /tmp/wheels

# Install the pre-built wheels and their PyPI dependencies
RUN uv pip install --system --no-cache /tmp/wheels/*.whl

# NOW copy source code (frequent changes don't trigger dependency reinstall)
COPY src/ src/

# Rebuild root package with actual source code (workspace members already have
# real source from the packages/ COPY above) and reinstall without re-resolving deps
RUN uv build --wheel --out-dir /tmp/wheels-final && \
    uv pip install --system --no-cache --no-deps --reinstall /tmp/wheels-final/*.whl

# =============================================================================
# Stage 2: Runtime - Minimal production image
# =============================================================================
FROM python:3.12-slim

# Build arguments for image metadata
ARG VERSION
ARG BUILD_DATE
ARG VCS_REF

# Add image metadata
LABEL org.opencontainers.image.version="${VERSION}" \
    org.opencontainers.image.created="${BUILD_DATE}" \
    org.opencontainers.image.revision="${VCS_REF}" \
    io.modelcontextprotocol.server.name="com.knitli/codeweaver"

# Install runtime dependencies
# Note: git is required for CodeWeaver to detect project root directory
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash codeweaver

# Set working directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app/src /app/src
COPY docker/entrypoint.sh /entrypoint.sh

# Set up environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # CodeWeaver specific settings
    CODEWEAVER_HOST=0.0.0.0 \
    CODEWEAVER_PORT=9328
# to disable telemetry (anonymous and only for product improvement)
# CODEWEAVER__TELEMETRY__DISABLE_TELEMETRY=true

# Create directories for data persistence
RUN mkdir -p /app/data /app/config /app/.codeweaver && \
    chown -R codeweaver:codeweaver /app && \
    chmod +x /entrypoint.sh

# Switch to non-root user
USER codeweaver

# Health check via management server
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:9329/health || exit 1

# Expose the MCP HTTP server port (9328) and management server port (9329)
EXPOSE 9328 9329

# Default command: start the CodeWeaver daemon in foreground mode
# This runs both management server (9329) and MCP HTTP server (9328)
# For stdio-only mode (MCP clients), use: codeweaver server
ENTRYPOINT ["/entrypoint.sh"]
CMD ["codeweaver", "start", "--foreground"]
