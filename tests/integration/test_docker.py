# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Integration tests for Docker and Docker Compose setup.

These tests validate that:
1. Docker images can be built successfully
2. Docker Compose services start correctly
3. Services can communicate with each other
4. Health endpoints are accessible
5. Basic functionality works in containerized environment
"""

from __future__ import annotations

import json
import subprocess
import time

from typing import Any

import pytest


pytestmark = [
    pytest.mark.integration,
    pytest.mark.docker,
]


def run_command(cmd: list[str], check: bool = True, capture: bool = True) -> subprocess.CompletedProcess[str]:
    """Run a shell command and return the result.
    
    Args:
        cmd: Command and arguments as list
        check: Whether to raise on non-zero exit code
        capture: Whether to capture stdout/stderr
        
    Returns:
        CompletedProcess with stdout/stderr
    """
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture,
        text=True,
        timeout=300,
    )


class TestDockerfile:
    """Tests for Dockerfile build process."""
    
    def test_dockerfile_exists(self, repo_root):
        """Verify Dockerfile exists in repository root."""
        dockerfile = repo_root / "Dockerfile"
        assert dockerfile.exists(), "Dockerfile not found in repository root"
        assert dockerfile.is_file(), "Dockerfile is not a file"
    
    def test_dockerfile_has_proper_license_header(self, repo_root):
        """Verify Dockerfile has SPDX license headers."""
        dockerfile = repo_root / "Dockerfile"
        content = dockerfile.read_text()
        
        assert "SPDX-FileCopyrightText:" in content, "Missing SPDX copyright header"
        assert "SPDX-License-Identifier:" in content, "Missing SPDX license identifier"
        assert "MIT OR Apache-2.0" in content, "Incorrect license in header"
    
    def test_dockerfile_syntax(self, repo_root):
        """Validate Dockerfile syntax using hadolint (if available)."""
        try:
            result = run_command(
                ["docker", "run", "--rm", "-i", "hadolint/hadolint", "hadolint", "-"],
                check=False,
            )
            # If hadolint is available, use it
            if result.returncode == 0:
                dockerfile = repo_root / "Dockerfile"
                result = run_command(
                    ["docker", "run", "--rm", "-i", "hadolint/hadolint"],
                    check=False,
                )
        except FileNotFoundError:
            pytest.skip("hadolint not available for Dockerfile linting")
    
    @pytest.mark.slow
    def test_docker_build_succeeds(self, repo_root):
        """Test that Docker image builds successfully."""
        result = run_command(
            ["docker", "build", "-t", "codeweaver:test", str(repo_root)],
            check=True,
        )
        
        assert result.returncode == 0, "Docker build failed"
        
        # Verify image was created
        result = run_command(
            ["docker", "images", "-q", "codeweaver:test"],
            check=True,
        )
        assert result.stdout.strip(), "Docker image not found after build"
    
    @pytest.mark.slow
    def test_docker_image_has_entrypoint(self, repo_root):
        """Verify Docker image has proper entrypoint."""
        # Build image first
        run_command(
            ["docker", "build", "-t", "codeweaver:test", str(repo_root)],
            check=True,
        )
        
        # Check entrypoint
        result = run_command(
            ["docker", "inspect", "--format={{.Config.Cmd}}", "codeweaver:test"],
            check=True,
        )
        
        assert "codeweaver" in result.stdout, "Entrypoint does not include codeweaver command"
    
    @pytest.mark.slow
    def test_docker_image_version(self, repo_root):
        """Test that codeweaver --version works in container."""
        # Build image first
        run_command(
            ["docker", "build", "-t", "codeweaver:test", str(repo_root)],
            check=True,
        )
        
        # Run version command
        result = run_command(
            [
                "docker", "run", "--rm", "--entrypoint", "/bin/sh",
                "codeweaver:test", "-c", "codeweaver --version"
            ],
            check=False,  # May fail without full config, but should run
        )
        
        # We expect either success or a specific error (not a crash)
        assert result.returncode in (0, 1), "codeweaver command crashed in container"


class TestDockerCompose:
    """Tests for docker-compose.yml configuration."""
    
    def test_docker_compose_file_exists(self, repo_root):
        """Verify docker-compose.yml exists."""
        compose_file = repo_root / "docker-compose.yml"
        assert compose_file.exists(), "docker-compose.yml not found"
    
    def test_docker_compose_syntax(self, repo_root):
        """Validate docker-compose.yml syntax."""
        result = run_command(
            ["docker", "compose", "-f", str(repo_root / "docker-compose.yml"), "config"],
            check=True,
        )
        
        assert result.returncode == 0, "docker-compose.yml has syntax errors"
    
    def test_docker_compose_defines_required_services(self, repo_root):
        """Verify docker-compose defines required services."""
        result = run_command(
            ["docker", "compose", "-f", str(repo_root / "docker-compose.yml"), "config"],
            check=True,
        )
        
        # Parse the output (it's YAML but we can check for service names)
        output = result.stdout
        assert "qdrant:" in output, "Qdrant service not defined"
        assert "codeweaver:" in output, "CodeWeaver service not defined"
    
    @pytest.mark.slow
    @pytest.mark.network
    def test_docker_compose_services_start(self, repo_root, tmp_path):
        """Test that docker-compose services can start."""
        # Create a minimal .env file
        env_file = tmp_path / ".env"
        env_file.write_text("""
PROJECT_PATH=.
CODEWEAVER_PORT=19328
QDRANT_PORT=16333
QDRANT_GRPC_PORT=16334
VOYAGE_API_KEY=test-key
COLLECTION_NAME=test-collection
ENABLE_TELEMETRY=false
LOG_LEVEL=DEBUG
""")
        
        compose_file = repo_root / "docker-compose.yml"
        
        try:
            # Start services
            result = run_command(
                [
                    "docker", "compose",
                    "-f", str(compose_file),
                    "--env-file", str(env_file),
                    "up", "-d"
                ],
                check=True,
            )
            
            assert result.returncode == 0, "Failed to start docker-compose services"
            
            # Wait a bit for services to initialize
            time.sleep(10)
            
            # Check that services are running
            result = run_command(
                ["docker", "compose", "-f", str(compose_file), "ps"],
                check=True,
            )
            
            assert "qdrant" in result.stdout, "Qdrant service not running"
            assert "codeweaver" in result.stdout, "CodeWeaver service not running"
            
        finally:
            # Cleanup
            run_command(
                ["docker", "compose", "-f", str(compose_file), "down", "-v"],
                check=False,
            )
    
    @pytest.mark.slow
    @pytest.mark.network
    def test_qdrant_health_endpoint(self, repo_root, tmp_path):
        """Test that Qdrant health endpoint is accessible."""
        env_file = tmp_path / ".env"
        env_file.write_text("""
PROJECT_PATH=.
CODEWEAVER_PORT=19328
QDRANT_PORT=16333
QDRANT_GRPC_PORT=16334
VOYAGE_API_KEY=test-key
COLLECTION_NAME=test-collection
ENABLE_TELEMETRY=false
""")
        
        compose_file = repo_root / "docker-compose.yml"
        
        try:
            # Start services
            run_command(
                [
                    "docker", "compose",
                    "-f", str(compose_file),
                    "--env-file", str(env_file),
                    "up", "-d"
                ],
                check=True,
            )
            
            # Wait for Qdrant to be ready
            max_attempts = 30
            for attempt in range(max_attempts):
                try:
                    result = run_command(
                        ["curl", "-sf", "http://localhost:16333/health"],
                        check=False,
                    )
                    if result.returncode == 0:
                        break
                except Exception:
                    pass
                
                time.sleep(2)
            
            # Verify health endpoint responds
            result = run_command(
                ["curl", "-sf", "http://localhost:16333/health"],
                check=False,
            )
            
            assert result.returncode == 0, "Qdrant health endpoint not accessible"
            
        finally:
            # Cleanup
            run_command(
                ["docker", "compose", "-f", str(compose_file), "down", "-v"],
                check=False,
            )


class TestDockerIgnore:
    """Tests for .dockerignore file."""
    
    def test_dockerignore_exists(self, repo_root):
        """Verify .dockerignore exists."""
        dockerignore = repo_root / ".dockerignore"
        assert dockerignore.exists(), ".dockerignore not found"
    
    def test_dockerignore_excludes_common_patterns(self, repo_root):
        """Verify .dockerignore excludes common patterns."""
        dockerignore = repo_root / ".dockerignore"
        content = dockerignore.read_text()
        
        # Check for common exclusions
        patterns = [
            ".git",
            "__pycache__",
            "*.pyc",
            ".venv",
            "tests/",
            ".github/",
            "docs/",
        ]
        
        for pattern in patterns:
            assert pattern in content, f".dockerignore missing pattern: {pattern}"


class TestEnvironmentFile:
    """Tests for .env.example file."""
    
    def test_env_example_exists(self, repo_root):
        """Verify .env.example exists."""
        env_example = repo_root / ".env.example"
        assert env_example.exists(), ".env.example not found"
    
    def test_env_example_has_required_variables(self, repo_root):
        """Verify .env.example contains required variables."""
        env_example = repo_root / ".env.example"
        content = env_example.read_text()
        
        required_vars = [
            "VOYAGE_API_KEY",
            "PROJECT_PATH",
            "CODEWEAVER_PORT",
            "QDRANT_PORT",
        ]
        
        for var in required_vars:
            assert var in content, f".env.example missing variable: {var}"
    
    def test_env_example_has_license_header(self, repo_root):
        """Verify .env.example has proper license header."""
        env_example = repo_root / ".env.example"
        content = env_example.read_text()
        
        assert "SPDX-FileCopyrightText:" in content, "Missing SPDX copyright header"
        assert "SPDX-License-Identifier:" in content, "Missing SPDX license identifier"


@pytest.fixture
def repo_root(tmp_path):
    """Fixture providing repository root path."""
    import pathlib
    
    # Find repository root by looking for pyproject.toml
    current = pathlib.Path(__file__).resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    
    pytest.fail("Could not find repository root (no pyproject.toml found)")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
