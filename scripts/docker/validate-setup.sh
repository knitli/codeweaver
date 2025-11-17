#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# Docker Setup Validation Script
# Checks prerequisites and validates Docker configuration

set -e

echo "=================================="
echo "CodeWeaver Docker Setup Validator"
echo "=================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

errors=0
warnings=0

# Check Docker
echo -n "Checking Docker... "
if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version)
    echo -e "${GREEN}✓${NC} $DOCKER_VERSION"
else
    echo -e "${RED}✗${NC} Docker not found"
    errors=$((errors + 1))
fi

# Check Docker Compose
echo -n "Checking Docker Compose... "
if docker compose version &> /dev/null; then
    COMPOSE_VERSION=$(docker compose version --short)
    echo -e "${GREEN}✓${NC} Docker Compose v$COMPOSE_VERSION"
else
    echo -e "${RED}✗${NC} Docker Compose not found"
    errors=$((errors + 1))
fi

# Check if Docker is running
echo -n "Checking Docker daemon... "
if docker info &> /dev/null; then
    echo -e "${GREEN}✓${NC} Running"
else
    echo -e "${RED}✗${NC} Docker daemon not running"
    errors=$((errors + 1))
fi

# Check docker-compose.yml
echo -n "Checking docker-compose.yml... "
if [ -f "docker-compose.yml" ]; then
    if docker compose config --quiet 2>/dev/null; then
        echo -e "${GREEN}✓${NC} Valid"
    else
        echo -e "${RED}✗${NC} Invalid syntax"
        errors=$((errors + 1))
    fi
else
    echo -e "${RED}✗${NC} Not found"
    errors=$((errors + 1))
fi

# Check .env file
echo -n "Checking .env file... "
if [ -f ".env" ]; then
    echo -e "${GREEN}✓${NC} Found"
    
    # Check for required variables
    if grep -q "VOYAGE_API_KEY=" .env 2>/dev/null; then
        if grep -q "VOYAGE_API_KEY=your-" .env 2>/dev/null; then
            echo -e "  ${YELLOW}⚠${NC} VOYAGE_API_KEY needs to be set"
            warnings=$((warnings + 1))
        fi
    else
        echo -e "  ${YELLOW}⚠${NC} VOYAGE_API_KEY not found in .env"
        warnings=$((warnings + 1))
    fi
else
    echo -e "${YELLOW}⚠${NC} Not found (optional)"
    echo "    Run: cp .env.example .env"
    warnings=$((warnings + 1))
fi

# Check Dockerfile
echo -n "Checking Dockerfile... "
if [ -f "Dockerfile" ]; then
    echo -e "${GREEN}✓${NC} Found"
else
    echo -e "${RED}✗${NC} Not found"
    errors=$((errors + 1))
fi

# Check system resources
echo -n "Checking available memory... "
if command -v free &> /dev/null; then
    AVAILABLE_MEM=$(free -g | awk '/^Mem:/{print $7}')
    if [ "$AVAILABLE_MEM" -ge 4 ]; then
        echo -e "${GREEN}✓${NC} ${AVAILABLE_MEM}GB available"
    else
        echo -e "${YELLOW}⚠${NC} ${AVAILABLE_MEM}GB available (4GB recommended)"
        warnings=$((warnings + 1))
    fi
elif command -v vm_stat &> /dev/null; then
    # macOS
    FREE_BLOCKS=$(vm_stat | grep free | awk '{ print $3 }' | sed 's/\.//')
    if [[ -n "$FREE_BLOCKS" && "$FREE_BLOCKS" =~ ^[0-9]+$ ]]; then
        FREE_GB=$((FREE_BLOCKS * 4096 / 1024 / 1024 / 1024))
        if [ "$FREE_GB" -ge 4 ]; then
            echo -e "${GREEN}✓${NC} ~${FREE_GB}GB available"
        else
            echo -e "${YELLOW}⚠${NC} ~${FREE_GB}GB available (4GB recommended)"
            warnings=$((warnings + 1))
        fi
    else
        echo -e "${YELLOW}⚠${NC} Unable to determine available memory"
    fi
else
    echo -e "${YELLOW}⚠${NC} Unable to check"
fi

# Check disk space
echo -n "Checking disk space... "
if command -v df &> /dev/null; then
    AVAILABLE_DISK=$(df -h . | awk 'NR==2 {print $4}')
    echo -e "${GREEN}✓${NC} $AVAILABLE_DISK available"
else
    echo -e "${YELLOW}⚠${NC} Unable to check"
fi

echo ""
echo "=================================="
echo "Summary"
echo "=================================="

if [ $errors -eq 0 ] && [ $warnings -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    echo ""
    echo "You're ready to start CodeWeaver:"
    echo "  docker compose up -d"
    exit 0
elif [ $errors -eq 0 ]; then
    echo -e "${YELLOW}⚠ $warnings warning(s)${NC}"
    echo ""
    echo "You can proceed, but review the warnings above."
    echo "To start CodeWeaver:"
    echo "  docker compose up -d"
    exit 0
else
    echo -e "${RED}✗ $errors error(s), $warnings warning(s)${NC}"
    echo ""
    echo "Please fix the errors above before proceeding."
    exit 1
fi
