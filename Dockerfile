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

# Install system dependencies required for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock README.md ./
COPY LICENSE* ./
COPY src/codeweaver/_version.py src/codeweaver/_version.py

# Create a minimal version file if it doesn't exist
RUN mkdir -p src/codeweaver && \
    echo '# SPDX-FileCopyrightText: 2025 Knitli Inc.' > src/codeweaver/__init__.py && \
    echo '# SPDX-License-Identifier: MIT OR Apache-2.0' >> src/codeweaver/__init__.py && \
    echo '__version__ = "0.1.0a1"' >> src/codeweaver/__init__.py || true

# Install dependencies using uv (much faster than pip)
# Install only production dependencies, excluding dev/test/docs groups
RUN uv sync --no-dev --no-install-project

# Copy the entire source code
COPY src/ src/
COPY typings/ typings/

# Install the package itself
RUN uv sync --no-dev

# =============================================================================
# Stage 2: Runtime - Minimal production image
# =============================================================================
FROM python:3.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash codeweaver

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

# Set up environment
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # CodeWeaver specific settings
    CODEWEAVER_HOST=0.0.0.0 \
    CODEWEAVER_PORT=9328 \
    # Disable telemetry in Docker by default (can be overridden)
    CODEWEAVER_ENABLE_TELEMETRY=false

# Create directories for data persistence
RUN mkdir -p /app/data /app/config /app/.codeweaver && \
    chown -R codeweaver:codeweaver /app

# Switch to non-root user
USER codeweaver

# Health check to ensure service is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:9328/health/ || exit 1

# Expose the MCP server port
EXPOSE 9328

# Default command: start the CodeWeaver MCP server
# Users can override this with custom config via docker-compose or docker run
CMD ["codeweaver", "server", "--host", "0.0.0.0", "--port", "9328"]
