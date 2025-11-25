# Docker Test Fixes - Implementation Guide

## Summary

Two Docker Compose tests are failing due to port conflicts and missing environment variables. This document provides the exact fixes needed.

---

## Root Cause Summary

1. **Port Conflict**: Existing Qdrant container running on ports 6333/6334 conflicts with test containers
2. **Missing Variable**: `PROJECT_NAME` not included in test environment files
3. **No Test Isolation**: Tests don't use unique project names, causing resource collisions

---

## Required Changes

### File: `/home/knitli/codeweaver/tests/integration/test_docker.py`

#### Change 1: Add Helper Functions (after imports, before test classes)

```python
import socket
import uuid


def get_free_port() -> int:
    """Find and return an available port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def generate_test_project_name() -> str:
    """Generate unique project name for test isolation."""
    return f"test-codeweaver-{uuid.uuid4().hex[:8]}"
```

#### Change 2: Update `test_docker_compose_services_start` (lines 169-225)

Replace the entire test method with:

```python
@pytest.mark.slow
@pytest.mark.network
def test_docker_compose_services_start(self, repo_root, tmp_path):
    """Test that docker-compose services can start."""
    # Generate unique test environment
    project_name = generate_test_project_name()
    qdrant_port = get_free_port()
    qdrant_grpc_port = get_free_port()
    codeweaver_port = get_free_port()

    # Create a minimal .env file with all required variables
    env_file = tmp_path / ".env"
    env_file.write_text(f"""
PROJECT_PATH=.
PROJECT_NAME={project_name}
CODEWEAVER_PORT={codeweaver_port}
QDRANT_PORT={qdrant_port}
QDRANT_GRPC_PORT={qdrant_grpc_port}
VOYAGE_API_KEY=test-key
ENABLE_TELEMETRY=false
LOG_LEVEL=DEBUG
""")

    compose_file = repo_root / "docker-compose.yml"

    try:
        # Start services with unique project name for isolation
        result = run_command(
            [
                "docker",
                "compose",
                "-p", project_name,  # CRITICAL: Isolates test resources
                "-f", str(compose_file),
                "--env-file", str(env_file),
                "up", "-d",
            ],
            check=True,
        )

        assert result.returncode == 0, "Failed to start docker-compose services"

        # Wait for services to be ready using polling instead of fixed sleep
        max_attempts = 30
        for _attempt in range(max_attempts):
            result_ps = run_command(
                [
                    "docker", "compose",
                    "-p", project_name,
                    "-f", str(compose_file),
                    "ps", "--format", "json"
                ],
                check=False,
            )
            if result_ps.returncode == 0:
                break
            time.sleep(2)
        else:
            pytest.fail("Services did not become healthy in time")

        # Check that services are running
        result = run_command(
            [
                "docker", "compose",
                "-p", project_name,
                "-f", str(compose_file),
                "ps"
            ],
            check=True
        )

        assert "qdrant" in result.stdout, "Qdrant service not running"
        assert "codeweaver" in result.stdout, "CodeWeaver service not running"

    finally:
        # Cleanup with project name
        run_command(
            [
                "docker", "compose",
                "-p", project_name,
                "-f", str(compose_file),
                "down", "-v"
            ],
            check=False
        )
```

#### Change 3: Update `test_qdrant_health_endpoint` (lines 227-278)

Replace the entire test method with:

```python
@pytest.mark.slow
@pytest.mark.network
def test_qdrant_health_endpoint(self, repo_root, tmp_path):
    """Test that Qdrant health endpoint is accessible."""
    # Generate unique test environment
    project_name = generate_test_project_name()
    qdrant_port = get_free_port()
    qdrant_grpc_port = get_free_port()
    codeweaver_port = get_free_port()

    env_file = tmp_path / ".env"
    env_file.write_text(f"""
PROJECT_PATH=.
PROJECT_NAME={project_name}
CODEWEAVER_PORT={codeweaver_port}
QDRANT_PORT={qdrant_port}
QDRANT_GRPC_PORT={qdrant_grpc_port}
VOYAGE_API_KEY=test-key
ENABLE_TELEMETRY=false
""")

    compose_file = repo_root / "docker-compose.yml"

    try:
        # Start services with unique project name
        run_command(
            [
                "docker", "compose",
                "-p", project_name,
                "-f", str(compose_file),
                "--env-file", str(env_file),
                "up", "-d",
            ],
            check=True,
        )

        # Wait for Qdrant to be ready
        max_attempts = 30
        for _attempt in range(max_attempts):
            with contextlib.suppress(Exception):
                result = run_command(
                    ["curl", "-sf", f"http://localhost:{qdrant_port}/health"],
                    check=False
                )
                if result.returncode == 0:
                    break
            time.sleep(2)

        # Verify health endpoint responds
        result = run_command(
            ["curl", "-sf", f"http://localhost:{qdrant_port}/health"],
            check=False
        )

        assert result.returncode == 0, "Qdrant health endpoint not accessible"

    finally:
        # Cleanup with project name
        run_command(
            [
                "docker", "compose",
                "-p", project_name,
                "-f", str(compose_file),
                "down", "-v"
            ],
            check=False
        )
```

---

## Key Changes Explained

### 1. Unique Project Names (`-p` flag)

**Before**:
```bash
docker compose -f docker-compose.yml up -d
# Creates: codeweaver-qdrant, codeweaver-server
```

**After**:
```bash
docker compose -p test-codeweaver-a1b2c3d4 -f docker-compose.yml up -d
# Creates: test-codeweaver-a1b2c3d4-qdrant-1, test-codeweaver-a1b2c3d4-server-1
```

**Benefits**:
- No collision with existing containers
- Multiple test runs can happen in parallel
- Automatic namespace isolation

### 2. Dynamic Port Allocation

**Before**: Hardcoded ports (16333, 16334, 19328)
**After**: Dynamically allocated free ports

**Benefits**:
- Works even if "test ports" are occupied
- No race conditions in parallel test execution
- More reliable in CI/CD environments

### 3. Added PROJECT_NAME

**Before**: Missing from env file
**After**: Included with unique value

**Benefits**:
- Satisfies docker-compose.yml requirements
- Enables proper CodeWeaver initialization
- Aligns with production configuration

---

## Testing the Fixes

### 1. Verify existing containers won't interfere
```bash
docker ps --filter name=codeweaver
docker ps --filter name=qdrant
```

### 2. Run individual tests
```bash
pytest tests/integration/test_docker.py::TestDockerCompose::test_docker_compose_services_start -v
pytest tests/integration/test_docker.py::TestDockerCompose::test_qdrant_health_endpoint -v
```

### 3. Run all Docker tests
```bash
pytest tests/integration/test_docker.py::TestDockerCompose -v
```

### 4. Verify cleanup
```bash
docker ps -a | grep test-codeweaver
# Should be empty
```

---

## Alternative Fix (Simpler but Less Robust)

If you want a minimal fix without dynamic port allocation:

1. **Just add `-p` flag and PROJECT_NAME**
2. **Use fixed high ports** (19328, 16333, 16334)
3. **Add pre-test check** for port availability

This is simpler but won't work if those ports are occupied.

---

## CI/CD Considerations

These tests require:
- Docker daemon access
- Network connectivity for image pulls
- Sufficient permissions for port binding
- Clean Docker state (or isolation via `-p` flag)

Recommended CI marks:
```python
@pytest.mark.slow  # Already present
@pytest.mark.network  # Already present
@pytest.mark.requires_docker  # Consider adding
```

---

## Expected Behavior After Fix

1. ✅ Tests create isolated resources (unique names)
2. ✅ No port conflicts with running containers
3. ✅ Parallel test execution possible
4. ✅ Clean automatic cleanup after tests
5. ✅ Works in any Docker environment

---

## Files Modified

- `/home/knitli/codeweaver/tests/integration/test_docker.py` (main changes)

## Files Not Requiring Changes

- `/home/knitli/codeweaver/docker-compose.yml` (already correct)
- `/home/knitli/codeweaver/.env.example` (documentation only)
- `/home/knitli/codeweaver/Dockerfile` (not related to issue)

---

## Verification Commands

After implementing fixes:

```bash
# Clean environment
docker compose down -v
docker stop festive_colden 2>/dev/null || true

# Run tests
pytest tests/integration/test_docker.py::TestDockerCompose -xvs

# Verify no leaked resources
docker ps -a | grep test-codeweaver
docker network ls | grep test-codeweaver
docker volume ls | grep test-codeweaver
```

All should be empty after test completion.
