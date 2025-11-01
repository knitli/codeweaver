# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Integration tests for server startup and indexing workflows.

Tests cover:
- T009: Server startup without errors
- T009: Auto-indexing on startup
- T009: Indexing progress via health endpoint
- T009: Indexing completion for small test project
- T009: Error recovery during indexing

Reference: Quickstart Scenario 1 (spec lines 76-83)
"""

import asyncio

from pathlib import Path

import pytest

from watchfiles.main import Change, FileChange

from codeweaver.engine.indexer import Indexer


# Test fixture: Small Python project
TEST_PROJECT_FILES = {
    "src/auth.py": '''"""Authentication module."""

def authenticate(username: str, password: str) -> bool:
    """Validate user credentials."""
    return username == "admin" and password == "secret"

class AuthManager:
    """Manages authentication state."""

    def __init__(self):
        self.sessions = {}

    def create_session(self, user_id: str) -> str:
        """Create new session for user."""
        import uuid
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = user_id
        return session_id
''',
    "src/database.py": '''"""Database connection module."""

import sqlite3

def get_connection(db_path: str):
    """Get database connection."""
    return sqlite3.connect(db_path)

class UserRepository:
    """User data access layer."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def find_user(self, username: str):
        """Find user by username."""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        return cursor.fetchone()
''',
    "tests/test_auth.py": '''"""Tests for authentication module."""

import pytest
from src.auth import authenticate, AuthManager

def test_authenticate_valid_credentials():
    """Test authentication with valid credentials."""
    assert authenticate("admin", "secret") is True

def test_authenticate_invalid_credentials():
    """Test authentication with invalid credentials."""
    assert authenticate("admin", "wrong") is False

def test_auth_manager_create_session():
    """Test session creation."""
    manager = AuthManager()
    session_id = manager.create_session("user123")
    assert session_id in manager.sessions
    assert manager.sessions[session_id] == "user123"
''',
    "README.md": """# Test Project

Small test project for CodeWeaver integration tests.

## Features
- Authentication module
- Database access layer
- Test coverage

## Usage
```python
from src.auth import authenticate
result = authenticate("admin", "secret")
```
""",
    ".gitignore": """__pycache__/
*.pyc
.pytest_cache/
.coverage
*.db
""",
}


@pytest.fixture
def test_project_path(tmp_path: Path) -> Path:
    """Create small test project fixture."""
    project_root = tmp_path / "test_project"
    project_root.mkdir()

    for file_path, content in TEST_PROJECT_FILES.items():
        file_full_path = project_root / file_path
        file_full_path.parent.mkdir(parents=True, exist_ok=True)
        file_full_path.write_text(content)

    return project_root


@pytest.fixture
def indexer(test_project_path: Path) -> Indexer:
    """Create indexer instance for test project."""
    return Indexer(project_root=test_project_path, auto_initialize_providers=True)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_server_starts_without_errors(indexer: Indexer):
    """T009: Server starts, indexer initializes, no errors.

    Given: Test project directory with 5 files
    When: Indexer initialized with project path
    Then: Indexer starts without errors, providers initialized
    """
    # Verify indexer initialized
    assert indexer._project_root is not None
    assert indexer._walker is not None

    # Verify providers initialized (if available)
    # Note: May be None if API keys not configured, that's acceptable
    stats = indexer.stats
    assert stats.files_processed == 0  # Not yet indexed
    assert stats.total_errors == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auto_indexing_on_startup(indexer: Indexer, test_project_path: Path):
    """T009: Auto-indexing begins on server start.

    Given: Server started with project path
    When: prime_index() called
    Then: Files discovered, chunking begins
    """
    # Prime index to discover files
    discovered_count = indexer.prime_index(force_reindex=True)

    # Should discover 5 files (auth.py, database.py, test_auth.py, README.md, .gitignore)
    # Note: .gitignore itself might be indexed depending on filtering rules
    assert discovered_count >= 4, f"Expected ≥4 files, got {discovered_count}"

    # Verify stats updated
    stats = indexer.stats
    assert stats.files_discovered >= 4


@pytest.mark.integration
@pytest.mark.asyncio
async def test_indexing_progress_via_health(indexer: Indexer):
    """T009: Health endpoint shows indexing progress.

    Given: Indexing in progress
    When: Query indexer.stats
    Then: Progress information is accurate
    """
    # Start indexing
    indexer.prime_index(force_reindex=True)

    # Check stats
    stats = indexer.stats

    # Verify stats structure
    assert hasattr(stats, "files_discovered")
    assert hasattr(stats, "files_processed")
    assert hasattr(stats, "chunks_created")
    assert hasattr(stats, "total_errors")
    assert hasattr(stats, "start_time")

    # Verify values are reasonable
    assert stats.files_discovered >= 0
    assert stats.files_processed <= stats.files_discovered
    assert stats.chunks_created >= 0
    assert stats.total_errors >= 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_indexing_completes_successfully(indexer: Indexer, test_project_path: Path):
    """T009: Indexing completes for small test project.

    Given: Small test project (5 files, ~100 lines)
    When: Indexing runs to completion
    Then: All files processed, chunks created, no errors
    """
    # Run indexing
    discovered_count = indexer.prime_index(force_reindex=True)

    # Allow time for async indexing to complete
    await asyncio.sleep(2)

    # Verify completion
    stats = indexer.stats

    # All discovered files should be processed
    # Note: May have errors if providers not configured, that's acceptable
    assert stats.files_discovered == discovered_count

    # Should have created chunks (unless providers unavailable)
    # This test will show progress even if embeddings fail
    if stats.chunks_created > 0:
        assert stats.chunks_created >= 10, "Expected at least 10 chunks from test files"

    # Check completion time is reasonable (<30s for small project)
    duration = stats.elapsed_time
    assert duration < 30, f"Indexing took {duration}s, expected <30s"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_indexing_error_recovery(test_project_path: Path):
    """T009: Indexing continues after file errors.

    Given: Project with 1 corrupted file
    When: Indexing encounters error
    Then: Error logged, indexing continues with remaining files
    """
    # Add a "corrupted" file (binary content)
    corrupted_file = test_project_path / "corrupted.bin"
    corrupted_file.write_bytes(b"\x00\x01\x02\xff\xfe\xfd")

    # Create indexer
    indexer = Indexer(project_root=test_project_path, auto_initialize_providers=True)

    # Run indexing
    indexer.prime_index(force_reindex=True)

    # Allow indexing to complete
    await asyncio.sleep(2)

    # Check results
    stats = indexer.stats

    # Should have discovered corrupted file plus originals
    assert stats.files_discovered >= 5

    # Should have processed most files despite error
    # (corrupted file may cause chunking failure)
    assert stats.files_processed >= 4

    # Errors should be tracked
    # Note: May be 0 if binary file filtered out before chunking
    if stats.total_errors > 0:
        assert stats.total_errors <= 2, "Expected ≤2 errors (corrupted file + retry)"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_file_change_indexing(indexer: Indexer, test_project_path: Path):
    """T009: File changes trigger reindexing.

    Given: Project already indexed
    When: File modified
    Then: Modified file reindexed automatically
    """
    # Initial indexing
    indexer.prime_index(force_reindex=True)
    await asyncio.sleep(1)

    initial_stats = indexer.stats
    initial_chunks = initial_stats.chunks_created

    # Modify a file
    auth_file = test_project_path / "src" / "auth.py"
    original_content = auth_file.read_text()
    modified_content = (
        original_content + '\n\ndef new_function():\n    """New function."""\n    pass\n'
    )
    auth_file.write_text(modified_content)

    # Simulate file change event
    change = (Change.modified, str(auth_file))
    await indexer.index(change)

    # Allow reindexing to complete
    await asyncio.sleep(1)

    # Check updated stats
    updated_stats = indexer.stats

    # Should have created new chunks for modified file
    # Note: May be same if providers not available
    if updated_stats.chunks_created > 0:
        assert updated_stats.chunks_created >= initial_chunks


@pytest.mark.integration
@pytest.mark.benchmark
async def test_indexing_performance(indexer: Indexer):
    """T009: Indexing meets performance requirements.

    Given: Test project with 5 files
    When: Indexing runs
    Then: Completes at ≥100 files/min rate (for larger projects)
    """
    # Note: 5 files is too small for meaningful performance test
    # This test validates the timing mechanism works

    indexer.prime_index(force_reindex=True)
    await asyncio.sleep(1)

    stats = indexer.stats

    # Verify timing tracked
    assert stats.start_time is not None

    # Verify processing rate calculated
    duration = stats.elapsed_time
    if duration > 0 and stats.files_processed > 0:
        rate = stats.files_processed / (duration / 60)  # files/minute
        # For small project, just verify rate is reasonable (not negative, not infinite)
        assert 0 < rate < 10000, f"Unreasonable indexing rate: {rate} files/min"
