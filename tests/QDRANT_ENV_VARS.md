<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Qdrant Test Environment Variables

## Overview

The Qdrant test infrastructure now supports test-specific environment variables to prevent pollution from other Qdrant instances and enable Docker auto-start capabilities.

## Test-Specific Environment Variables

All test-specific variables use the `QDRANT_TEST_*` prefix to avoid conflicts with production/development Qdrant instances.

### Available Variables

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `QDRANT_TEST_URL` | Direct URL override (highest priority) | - | `http://localhost:6336` |
| `QDRANT_TEST_HOST` | Test host | `localhost` | `192.168.1.100` |
| `QDRANT_TEST_PORT` | Test port override | Auto-detect | `6336` |
| `QDRANT_TEST_API_KEY` | Test-specific API key | - | `your-test-key` |
| `QDRANT_TEST_SKIP_DOCKER` | Disable Docker auto-start | `false` | `1`, `true`, `yes` |
| `QDRANT_TEST_IMAGE` | Custom Docker image | `qdrant/qdrant:latest` | `qdrant/qdrant:v1.7.4` |
| `QDRANT_TEST_CONTAINER_NAME` | Custom container name | `qdrant-test` | `my-test-qdrant` |

## Usage Examples

### Using Existing Qdrant Instance

```bash
# Point tests to specific port
export QDRANT_TEST_PORT=6336
pytest tests/integration/

# Or use direct URL
export QDRANT_TEST_URL=http://localhost:6336
pytest tests/integration/
```

### Using Docker Auto-Start

```bash
# Let the test infrastructure auto-start Qdrant
# (Docker must be installed and running)
pytest tests/integration/

# Customize Docker image
export QDRANT_TEST_IMAGE=qdrant/qdrant:v1.7.4
pytest tests/integration/
```

### Disable Docker Auto-Start

```bash
# Force tests to skip if no instance found
export QDRANT_TEST_SKIP_DOCKER=1
pytest tests/integration/
```

### WSL/Windows Users

The test infrastructure automatically detects WSL and uses the appropriate Docker command (`docker.exe` vs `docker`).

```bash
# In WSL, this automatically uses docker.exe if available
pytest tests/integration/
```

## How It Works

1. **Port Scanning**: Scans ports 6333-6400 for running Qdrant instances
2. **Accessibility Testing**: Tests each found instance for unauthenticated access
3. **Docker Fallback**: If no accessible instance found, attempts to start Docker container
4. **Auto-Cleanup**: Stops and removes Docker containers started by tests

## Priority Order

The test infrastructure uses this priority order for configuration:

1. **Direct URL**: `QDRANT_TEST_URL` (highest priority)
2. **Explicit Port**: `QDRANT_TEST_PORT`
3. **Port Scanning**: Auto-detect accessible instance (6333-6400)
4. **Docker Auto-Start**: Start new container on available port

## Platform Support

- **Linux**: Full support, uses `docker` command
- **WSL (Windows Subsystem for Linux)**: Full support, automatically detects and uses `docker.exe`
- **macOS**: Full support, uses `docker` command
- **Windows**: Not directly tested, but should work with Docker Desktop

## Troubleshooting

### Tests Skip with "No accessible Qdrant instance found"

**Solution 1**: Set explicit port
```bash
export QDRANT_TEST_PORT=6336
pytest tests/integration/
```

**Solution 2**: Check Docker availability
```bash
docker info  # Should show Docker info
docker run -d -p 6336:6333 qdrant/qdrant:latest
```

**Solution 3**: Check if port requires authentication
```bash
curl http://localhost:6333/collections  # Should NOT return 401
```

### Docker Auto-Start Fails

Check Docker status:
```bash
docker info
docker ps  # List running containers
```

For WSL users:
```bash
# Check if Docker Desktop is running on Windows
docker.exe info
```

### Port Conflicts

If auto-start fails due to port conflicts:
```bash
# Use a different port
export QDRANT_TEST_PORT=6337
pytest tests/integration/
```

## Migration from Old Setup

### Before (Hard-coded Port)
```python
# Old tests used hard-coded localhost:6336
config = {"url": "http://localhost:6336", ...}
```

### After (Environment Variables)
```bash
# Now configurable via environment
export QDRANT_TEST_PORT=6336
pytest tests/integration/
```

### Benefits

1. ✅ No pollution from production/development Qdrant instances
2. ✅ Auto-detection of accessible instances
3. ✅ Docker auto-start for CI/CD environments
4. ✅ WSL/Windows support
5. ✅ Automatic cleanup of test containers
6. ✅ Flexible configuration via environment variables

## CI/CD Integration

### GitHub Actions Example
```yaml
- name: Start Qdrant for testing
  run: docker run -d -p 6333:6333 qdrant/qdrant:latest

- name: Run integration tests
  run: |
    export QDRANT_TEST_PORT=6333
    pytest tests/integration/
```

### With Docker Auto-Start
```yaml
- name: Run integration tests
  run: pytest tests/integration/
  # Docker auto-start will handle Qdrant setup
```
