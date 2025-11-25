# Docker Compose Test Failures - Root Cause Analysis

**Investigation Date**: 2025-11-25
**Tests Affected**:
1. `test_docker.py::TestDockerCompose::test_docker_compose_services_start`
2. `test_docker.py::TestDockerCompose::test_qdrant_health_endpoint`

**Error Message**:
```
Command '['docker', 'compose', '-f', '/home/knitli/codeweaver/docker-compose.yml',
'--env-file', '/tmp/pytest-of-knitli/pytest-67/.../.env', 'up', '-d']'
returned non-zero exit status 1
```

---

## Root Causes Identified

### 1. Port Conflicts (PRIMARY)

**Issue**: Default Qdrant ports (6333, 6334) are already in use on the test system.

**Evidence**:
```bash
$ ss -tuln | grep -E ':(6333|6334)'
tcp   LISTEN 0      4096                *:6334             *:*
tcp   LISTEN 0      4096                *:6333             *:*

$ docker ps --filter publish=6333
NAMES            IMAGE                  PORTS                           STATUS
festive_colden   qdrant/qdrant:latest   0.0.0.0:6333-6334->6333-6334   Up 9 hours
```

**Docker Compose Error**:
```
Error response from daemon: failed to set up container networking:
driver failed programming external connectivity on endpoint codeweaver-qdrant:
Bind for 0.0.0.0:6333 failed: port is already allocated
```

**Analysis**:
- A standalone Qdrant container is running on the system using default ports
- Tests attempt to bind to the same ports, causing immediate failure
- Tests specify alternate ports in .env file (16333, 16334) but conflict still occurs

### 2. Missing Required Environment Variable

**Issue**: `PROJECT_NAME` environment variable is required but not provided in test env files.

**Evidence**:
```yaml
# docker-compose.yml line 82
environment:
  - CODEWEAVER_PROJECT_NAME=${PROJECT_NAME}
```

**Test env file** (lines 173-182):
```python
env_file.write_text("""
PROJECT_PATH=.
CODEWEAVER_PORT=19328
QDRANT_PORT=16333
QDRANT_GRPC_PORT=16334
VOYAGE_API_KEY=test-key
COLLECTION_NAME=test-collection  # Not used by docker-compose
ENABLE_TELEMETRY=false
LOG_LEVEL=DEBUG
""")
```

**Missing**: `PROJECT_NAME` variable

**Impact**:
- `CODEWEAVER_PROJECT_NAME` in container will be empty/undefined
- May cause issues with CodeWeaver initialization
- Not documented in test requirements

### 3. Test Isolation Issues

**Issue**: Tests don't check for or handle existing Docker resources.

**Problems**:
- No pre-test cleanup of potentially conflicting containers
- No verification that required ports are available
- No unique naming/namespacing for test containers
- Tests assume clean Docker environment

---

## Detailed Analysis

### Test Environment Assumptions

The tests make several assumptions that don't hold in all environments:

1. **Clean Docker State**: Assumes no conflicting containers are running
2. **Port Availability**: Assumes default ports are available
3. **System Isolation**: Doesn't account for development containers running locally

### docker-compose.yml Port Binding

```yaml
qdrant:
  ports:
    - ${QDRANT_PORT:-6333}:6333  # Host:Container
    - ${QDRANT_GRPC_PORT:-6334}:6334
```

**How it works**:
- `${QDRANT_PORT:-6333}` reads from environment, defaults to 6333
- Even when test sets `QDRANT_PORT=16333`, a conflict with 6333 causes failure
- The conflict happens at the Docker daemon level, not in docker-compose parsing

### Why Port Override Doesn't Work

The test sets alternate ports in the env file:
```
QDRANT_PORT=16333
QDRANT_GRPC_PORT=16334
```

But the error shows:
```
Bind for 0.0.0.0:6333 failed: port is already allocated
```

**This suggests**:
1. Either the env file isn't being parsed correctly
2. Or there's a timing issue where default values are used
3. Or another container is being created with default ports

### Container Creation Flow

From test output:
```
Network codeweaver_codeweaver-network  Created
Volume codeweaver_codeweaver_config  Created
Volume codeweaver_qdrant_storage  Created
Container codeweaver-qdrant  Creating
Container codeweaver-qdrant  Created
Container codeweaver-qdrant  Starting  # FAILS HERE
```

The failure occurs during the **Starting** phase, not during creation. This confirms it's a port binding issue at the Docker daemon level.

---

## Solutions Required

### 1. Fix Port Conflicts (CRITICAL)

**Option A**: Pre-test cleanup
```python
def setup_method(self):
    """Ensure clean Docker environment before test."""
    # Stop any existing containers using test ports
    subprocess.run(
        ["docker", "stop", "festive_colden"],  # or generic cleanup
        check=False,
        capture_output=True
    )
```

**Option B**: Use unique project names (RECOMMENDED)
```python
# Generate unique project name per test
project_name = f"test-codeweaver-{uuid.uuid4().hex[:8]}"

# Run with project name to namespace containers
run_command([
    "docker", "compose",
    "-p", project_name,  # Add project flag
    "-f", str(compose_file),
    "--env-file", str(env_file),
    "up", "-d",
])
```

**Option C**: Dynamic port allocation
```python
def get_free_port():
    """Find an available port."""
    import socket
    with socket.socket() as s:
        s.bind(('', 0))
        return s.getsockname()[1]

# Assign free ports dynamically
qdrant_port = get_free_port()
qdrant_grpc_port = get_free_port()
```

### 2. Add PROJECT_NAME to Test Env

```python
env_file.write_text(f"""
PROJECT_PATH=.
PROJECT_NAME={project_name}  # ADD THIS
CODEWEAVER_PORT={codeweaver_port}
QDRANT_PORT={qdrant_port}
QDRANT_GRPC_PORT={qdrant_grpc_port}
VOYAGE_API_KEY=test-key
ENABLE_TELEMETRY=false
LOG_LEVEL=DEBUG
""")
```

### 3. Improve Test Isolation

**Add fixtures**:
```python
@pytest.fixture
def isolated_docker_env(tmp_path):
    """Provide isolated Docker environment with unique ports and names."""
    project_name = f"test-codeweaver-{uuid.uuid4().hex[:8]}"
    ports = {
        'qdrant': get_free_port(),
        'qdrant_grpc': get_free_port(),
        'codeweaver': get_free_port(),
    }

    env_file = tmp_path / ".env"
    env_file.write_text(f"""
    PROJECT_NAME={project_name}
    PROJECT_PATH=.
    CODEWEAVER_PORT={ports['codeweaver']}
    QDRANT_PORT={ports['qdrant']}
    QDRANT_GRPC_PORT={ports['qdrant_grpc']}
    VOYAGE_API_KEY=test-key
    ENABLE_TELEMETRY=false
    """)

    yield {
        'project_name': project_name,
        'ports': ports,
        'env_file': env_file,
    }

    # Cleanup
    subprocess.run(
        ["docker", "compose", "-p", project_name, "down", "-v"],
        check=False,
        capture_output=True
    )
```

### 4. Add Pre-Flight Checks

```python
def test_docker_compose_services_start(self, repo_root, isolated_docker_env):
    """Test that docker-compose services can start."""
    # Verify ports are free BEFORE starting
    for port_name, port in isolated_docker_env['ports'].items():
        assert is_port_free(port), f"Port {port} ({port_name}) is not available"

    # Run compose with isolated environment
    ...
```

---

## Recommended Fix Priority

1. **CRITICAL**: Implement unique project naming (`-p` flag) - prevents all collisions
2. **HIGH**: Add `PROJECT_NAME` to test env files - fixes config issues
3. **MEDIUM**: Add cleanup fixture - ensures test isolation
4. **LOW**: Dynamic port allocation - nice-to-have, project naming is sufficient

---

## Test Environment Requirements

For tests to pass reliably:

1. **Docker daemon running** with proper permissions
2. **No port conflicts** on default or test ports (6333, 6334, 9328, 16333, 16334, 19328)
3. **Network access** for pulling images (qdrant/qdrant, python:3.12-slim)
4. **Sufficient disk space** for Docker volumes
5. **Clean test isolation** between test runs

---

## Additional Findings

### Environment Variable Handling

The docker-compose.yml uses pydantic_settings-compatible variable names:
- `CODEWEAVER_PROJECT_NAME` (with prefix)
- `CODEWEAVER_PROFILE`
- `CODEWEAVER_VECTOR_DEPLOYMENT`

But .env.example uses shorter names:
- `PROJECT_NAME` (no prefix)

**Resolution**: The compose file uses `${PROJECT_NAME}` and maps it to `CODEWEAVER_PROJECT_NAME`, so both work.

### Test Execution Context

Tests are marked as:
```python
@pytest.mark.slow
@pytest.mark.network
```

These should be skipped in CI/CD without Docker or in restrictive network environments.

---

## Verification Steps

After fixes are applied:

1. **Stop conflicting containers**:
   ```bash
   docker stop festive_colden
   docker compose down -v
   ```

2. **Run tests with isolation**:
   ```bash
   pytest tests/integration/test_docker.py::TestDockerCompose -v
   ```

3. **Verify cleanup**:
   ```bash
   docker ps -a | grep test-codeweaver
   # Should be empty after test completion
   ```

4. **Check port availability**:
   ```bash
   ss -tuln | grep -E ':(6333|6334|9328)'
   # Should not show lingering test containers
   ```

---

## Conclusion

**Root causes**:
1. Port conflicts with existing Qdrant container (PRIMARY)
2. Missing PROJECT_NAME in test env files (SECONDARY)
3. Insufficient test isolation (TERTIARY)

**Recommended fixes**:
1. Use unique project names for test isolation
2. Add PROJECT_NAME to all test env files
3. Implement cleanup fixtures
4. Add pre-flight port availability checks

**Impact**: Tests will be reliable across different development environments and won't interfere with running development containers.
