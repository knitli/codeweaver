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
COPY pyproject.toml README.md ./
COPY LICENSE* ./

# Copy .git directory for dynamic versioning during build
COPY .git/ .git/

# Copy the entire source code
COPY src/ src/
COPY typings/ typings/

# Install pip and setuptools, then install the package
# Note: In some CI environments, you may need to skip SSL verification
# If you encounter SSL errors, you can add --trusted-host pypi.org --trusted-host files.pythonhosted.org
# hadolint ignore=DL3013
RUN python -m pip install --no-cache-dir --upgrade pip setuptools wheel && \
    python -m pip install --no-cache-dir .

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
    io.modelcontextprotocol.server-name="com.knitli/codeweaver"

# Install runtime dependencies
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
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

# Health check to ensure service is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:9328/health/ || exit 1

# Expose the MCP server port
EXPOSE 9328

# Default command: start the CodeWeaver MCP server
# Users can override this with custom config via docker-compose or docker run
ENTRYPOINT ["/entrypoint.sh"]
CMD ["codeweaver", "server", "--host", "0.0.0.0", "--port", "9328"]
