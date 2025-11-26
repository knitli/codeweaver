#!/usr/bin/env bash

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# Free up disk space on GitHub Actions runners
#
# This script removes unused pre-installed packages and Docker artifacts
# to prevent disk space exhaustion during UV cache extraction (~3.5 GB).
#
# Usage:
#   ./scripts/dev-env/ci-free-disk-space.sh
#
# Referenced in:
#   - .github/workflows/ci.yml
#   - .github/workflows/release.yml
#   - .github/workflows/publish-test.yml
#   - .github/workflows/copilot-setup-steps.yml

set -euo pipefail

echo "=== Disk space before cleanup ==="
df -h

echo ""
echo "=== Cleaning up disk space ==="

# Remove unused Docker images and containers
echo "Removing Docker images and containers..."
docker system prune -af --volumes || true

# Remove unnecessary large packages to free disk space
echo "Removing unused pre-installed packages..."
sudo rm -rf /opt/hostedtoolcache/CodeQL || true
sudo rm -rf /opt/hostedtoolcache/Java_Temurin-Hotspot_jdk || true
sudo rm -rf /opt/hostedtoolcache/Ruby || true
sudo rm -rf /opt/hostedtoolcache/go || true
sudo rm -rf /usr/share/dotnet || true
sudo rm -rf /usr/local/lib/android || true

echo ""
echo "=== Disk space after cleanup ==="
df -h
