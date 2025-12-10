# CodeWeaver Test Suite

Comprehensive testing infrastructure for CodeWeaver's semantic code search platform.

## Overview

CodeWeaver uses a **multi-tier testing strategy** with pytest markers to organize tests by speed, complexity, and resource requirements.

### Testing Philosophy

- **Tier 1 (Unit/Mock)**: Fast tests with mocked dependencies for structure validation and rapid feedback
- **Tier 2 (Real Providers)**: Integration tests using actual embedding models and vector stores to validate search quality
- **Contract Tests**: Validate API contracts and response structures
- **E2E Tests**: Complete user journey validation
- **Performance Tests**: Benchmark and validate performance requirements

### Test Statistics

```bash
# See current test distribution
mise run test-categories
```

## Quick Start

### Running Tests Locally

```bash
# Fast tests (default) - unit tests with mocks
pytest

# Or use mise shortcuts
mise run test

# Fast unit tests only (CI subset)
mise run test-fast
```

### Common Test Commands

```bash
# Integration tests (excluding real providers)
mise run test-integration

# Real provider tests (requires model downloads)
mise run test-real

# Heavy tests with models and benchmarks
mise run test-heavy

# All tests including expensive ones
mise run test-all

# With coverage reporting
mise run test-cov
```

## Test Organization

### Directory Structure

```
tests/
├── unit/                    # Fast unit tests with mocks
│   ├── cli/                 # CLI command tests
│   ├── core/                # Core functionality
│   ├── engine/              # Indexer, chunker, etc.
│   ├── providers/           # Provider implementations
│   ├── server/              # Server-specific logic
│   ├── telemetry/           # Telemetry and analytics
│   └── ui/                  # UI components
├── integration/             # Integration tests (Tier 1)
│   ├── cli/                 # CLI workflow tests
│   ├── providers/           # Provider integration
│   ├── real/                # Tier 2 real provider tests
│   └── conftest.py          # Integration fixtures
├── contract/                # API contract validation
├── e2e/                     # End-to-end user journeys
├── benchmark/               # Performance benchmarks
├── performance/             # Performance validation
├── smoke/                   # Smoke tests for releases
├── fixtures/                # Test data and fixtures
└── conftest.py              # Global fixtures and configuration
```

### Test Types

| Type | Location | Purpose | Speed | Markers |
|------|----------|---------|-------|---------|
| **Unit** | `tests/unit/` | Component isolation, fast feedback | <1s | `unit`, `mock_only` |
| **Integration (Tier 1)** | `tests/integration/` | Component interaction with mocks | 1-3s | `integration` |
| **Integration (Tier 2)** | `tests/integration/real/` | Actual search behavior validation | 2-15s | `integration`, `real_providers` |
| **Contract** | `tests/contract/` | API contract validation | <1s | `validation` |
| **E2E** | `tests/e2e/` | Complete user workflows | 10-30s | `e2e`, `slow` |
| **Performance** | `tests/performance/`, `tests/benchmark/` | Performance benchmarks | 10-60s | `performance`, `benchmark` |
| **Smoke** | `tests/smoke/` | Release validation | Varies | `external_api`, `skip` |

## Pytest Markers

### Test Categories

| Marker | Purpose | When to Use |
|--------|---------|-------------|
| `unit` | Unit tests testing individual components | Isolated component testing |
| `integration` | Integration tests for component interaction | Multi-component workflows |
| `e2e` | End-to-end tests for complete workflows | Full user journeys |
| `contract` | API contract and schema validation | Response structure validation |

### Resource Requirements

| Marker | Purpose | Why Excluded by Default |
|--------|---------|-------------------------|
| `expensive` | Tests taking >30 seconds | Slow feedback loop |
| `requires_models` | Requires ML model downloads | Large downloads (100MB+) |
| `requires_gpu` | Requires GPU hardware | Not available in all environments |
| `requires_api_keys` | Requires external API credentials | Security and cost concerns |

### Provider Types

| Marker | Purpose | Use Case |
|--------|---------|----------|
| `mock_only` | Tests using only mocked dependencies | Fast unit testing |
| `real_providers` | Tests using actual embedding/vector providers | Search quality validation |

### Performance & Stability

| Marker | Purpose | When to Use |
|--------|---------|-------------|
| `benchmark` | Performance benchmark tests | Performance validation |
| `slow` | Tests with significant runtime | Long-running operations |
| `timing_sensitive` | Tests with strict timing requirements | Race conditions, timeouts |
| `flaky` | Tests that may occasionally fail | Known intermittent issues |

### Platform-Specific

| Marker | Purpose |
|--------|---------|
| `linux_only` | Tests that only run on Linux |
| `windows_only` | Tests that only run on Windows |
| `macos_only` | Tests that only run on macOS |

### Environment & Infrastructure

| Marker | Purpose | Why Excluded from CI |
|--------|---------|---------------------|
| `docker` | Requires Docker/Docker Compose | May fail in some CI environments |
| `qdrant` | Requires Qdrant instance | External dependency management |
| `network` | Requires network access | Flaky in CI, slow |
| `external_api` | Interacts with external APIs | Reliability and cost |

### Development Markers

| Marker | Purpose |
|--------|---------|
| `skip_ci` | Skip in CI/CD environments |
| `dev_only` | Development/debugging only |
| `debug` | Debugging purposes |

### Feature-Specific

| Marker | Purpose |
|--------|---------|
| `embeddings` | Embedding functionality tests |
| `indexing` | Code indexing tests |
| `search` | Search functionality tests |
| `mcp` | MCP protocol tests |
| `telemetry` | Telemetry and metrics tests |

## Running Tests

### By Category

```bash
# Fast unit tests only
pytest -m "unit"

# Integration tests (mocked providers)
pytest -m "integration and not real_providers"

# Real provider tests (actual search quality)
pytest -m "real_providers"

# End-to-end workflows
pytest -m "e2e"

# Contract validation
pytest -m "validation"
```

### By Marker Combination

```bash
# Fast unit tests without expensive operations
pytest -m "unit and not expensive and not requires_models"

# Integration tests excluding real providers and expensive tests
pytest -m "integration and not real_providers and not expensive"

# Only expensive or model-requiring tests
pytest -m "requires_models or expensive"

# All tests except docker-dependent
pytest -m "not docker"
```

### By Directory

```bash
# All unit tests
pytest tests/unit/

# CLI tests only
pytest tests/unit/cli/

# Real provider integration tests
pytest tests/integration/real/

# Specific test file
pytest tests/unit/core/test_chunks.py
```

### With Additional Options

```bash
# Verbose output
pytest -v

# Stop on first failure
pytest -x

# Show print statements
pytest -s

# Run specific test function
pytest tests/unit/test_file.py::test_function_name

# Parallel execution (requires pytest-xdist)
pytest -n auto

# With timeout (configured: 300s default)
pytest --timeout=60
```

## CI Integration

### What Runs Where

#### Pull Request CI (`.github/workflows/ci.yml`)

```yaml
# Fast quality checks - runs on every PR
test-markers: "not docker and not qdrant and not dev_only and not skip_ci and not network and not external_api and not flaky"
```

**Excluded from PR CI:**
- Docker-dependent tests (infrastructure)
- Network-dependent tests (flaky)
- External API tests (cost/reliability)
- Flaky tests (known intermittent failures)
- Development-only tests

#### Nightly Builds (Future)

```bash
# More comprehensive testing including real providers
pytest -m "real_providers and not expensive and not benchmark"
```

#### Weekly/Release Builds (Future)

```bash
# Full validation including benchmarks
pytest -m "real_providers"
```

### Model Caching in CI

Models are cached to speed up CI runs:

```yaml
- name: Cache embedding models
  uses: actions/cache@v4
  with:
    path: |
      ~/.cache/huggingface/
      ~/.cache/sentence_transformers/
    key: embedding-models-v1-${{ runner.os }}-${{ hashFiles('pyproject.toml', 'uv.lock') }}
```

**Models pre-downloaded in CI:**
- IBM Granite Embedding English R2 (dense embeddings)
- MS MARCO MiniLM L6 v2 (reranking)

## Two-Tier Testing Strategy

### Tier 1: Mocked Providers (Fast)

**Purpose**: Validate structure, API contracts, error handling

**Speed**: <1 second per test

**What it validates:**
- ✅ Response structure and types
- ✅ Error handling and edge cases
- ✅ API contracts and interfaces
- ✅ Configuration validation

**What it CANNOT validate:**
- ❌ Search actually finds relevant code
- ❌ Embeddings capture semantic meaning
- ❌ Vector search performs similarity matching
- ❌ Quality meets production standards

**Example:**
```python
@pytest.mark.unit
@pytest.mark.mock_only
async def test_response_structure(mock_embedding_provider):
    """Validate FindCodeResponse structure (fast)."""
    response = await find_code(query="test", cwd="/tmp/project")
    assert isinstance(response, FindCodeResponse)
    assert hasattr(response, "results")
```

### Tier 2: Real Providers (Comprehensive)

**Purpose**: Validate actual search behavior and quality

**Speed**: 2-15 seconds per test

**What it validates:**
- ✅ Search finds semantically relevant code
- ✅ Embeddings capture code semantics
- ✅ Vector search similarity works
- ✅ Ranking prioritizes best matches
- ✅ Performance meets SLA requirements

**Models used (all local, no API keys):**
- **IBM Granite English R2** - Dense embeddings (~100MB)
- **OpenSearch Neural Sparse** - Sparse embeddings
- **MS MARCO MiniLM** - Reranking
- **Qdrant In-Memory** - Vector storage

**Example:**
```python
@pytest.mark.integration
@pytest.mark.real_providers
async def test_search_finds_auth_code(real_providers, known_test_codebase):
    """Validate search actually finds authentication code."""
    response = await find_code(
        query="authentication logic",
        cwd=str(known_test_codebase),
        index_if_needed=True
    )

    # Validate ACTUAL search behavior
    result_files = [r.file_path.name for r in response.results[:3]]
    assert "auth.py" in result_files, "Should find auth-related code"
```

**See**: [`tests/integration/real/README.md`](integration/real/README.md) for comprehensive Tier 2 documentation.

## Writing Tests

### Test Naming Conventions

```python
# ✅ Good - descriptive, follows pattern
def test_search_returns_relevant_results():
def test_indexer_handles_file_deletion():
def test_embedding_provider_validates_dimensions():

# ❌ Bad - vague, unclear
def test_stuff():
def test_case_1():
def test_it_works():
```

### Fixture Patterns

#### Using Existing Fixtures

```python
import pytest

@pytest.mark.unit
async def test_with_temp_file(temp_test_file):
    """Use temp file fixture from conftest.py."""
    content = temp_test_file.read_text()
    assert content

@pytest.mark.integration
async def test_with_qdrant(qdrant_test_manager):
    """Use Qdrant test manager for vector storage."""
    async with qdrant_test_manager.collection_context() as (client, collection):
        # Use client and collection
        points = await client.get_collection(collection)
        assert points
```

#### Common Global Fixtures

Located in `tests/conftest.py`:

| Fixture | Purpose | Scope |
|---------|---------|-------|
| `mock_tokenizer_for_unit_tests` | Auto-patches tokenizer for unit tests | function (autouse) |
| `initialize_test_settings` | Initialize settings with test defaults | function |
| `qdrant_test_manager` | Qdrant instance manager | function |
| `qdrant_test_client` | Connected Qdrant client | function |
| `qdrant_test_collection` | Test collection with cleanup | function |
| `temp_test_file` | Temporary test file | function |
| `clear_semantic_chunker_stores` | Clear chunker state | function (autouse) |

#### CLI Test Fixtures

Located in `tests/conftest.py`:

| Fixture | Purpose |
|---------|---------|
| `clean_cli_env` | Clean environment variables |
| `isolated_home` | Isolated home directory |
| `cli_test_project` | Test project with git repo |
| `cli_api_keys` | Test API keys |
| `reset_cli_settings_cache` | Reset settings cache (autouse) |

#### Integration Test Fixtures

Located in `tests/integration/conftest.py`:

| Fixture | Purpose |
|---------|---------|
| `real_embedding_provider` | IBM Granite dense embeddings |
| `real_sparse_provider` | OpenSearch sparse encoding |
| `real_reranking_provider` | MS MARCO reranker |
| `real_vector_store` | Qdrant in-memory |
| `real_provider_registry` | Complete provider ecosystem |
| `real_providers` | Main fixture - patches registry |
| `known_test_codebase` | 5-file test codebase |

### Marker Usage

```python
import pytest

# Unit test with mocks
@pytest.mark.unit
@pytest.mark.mock_only
def test_parser_handles_syntax_error():
    """Fast unit test with mocked dependencies."""
    pass

# Integration test with real providers
@pytest.mark.integration
@pytest.mark.real_providers
@pytest.mark.asyncio
async def test_search_quality(real_providers):
    """Validate actual search behavior."""
    pass

# Expensive test (excluded by default)
@pytest.mark.integration
@pytest.mark.expensive
async def test_large_codebase_indexing():
    """Test with 1000+ files."""
    pass

# Performance benchmark
@pytest.mark.benchmark
@pytest.mark.real_providers
async def test_search_performance():
    """Validate performance SLA."""
    pass

# Platform-specific
@pytest.mark.linux_only
def test_linux_file_permissions():
    """Linux-specific behavior."""
    pass

# Requires external resources
@pytest.mark.requires_models
@pytest.mark.requires_api_keys
async def test_with_external_service():
    """Requires model downloads and API access."""
    pass
```

### Documentation Requirements

**All tests should include docstrings that explain:**

1. **What is being tested**
2. **Why this test matters**
3. **What could break** (for Tier 2 tests)

```python
@pytest.mark.integration
@pytest.mark.real_providers
async def test_search_distinguishes_concepts(real_providers, known_test_codebase):
    """Validate embeddings differentiate between distinct code concepts.

    Tests that searching for "authentication" returns different results than
    searching for "database", proving embeddings capture semantic distinctions.

    **Production failure modes this catches:**
    - Embeddings don't capture semantic nuances
    - All queries return same results (broken ranking)
    - Vector search returns unrelated code
    """
    # Test implementation
```

### Test Structure Pattern

```python
import pytest
from pathlib import Path

@pytest.mark.integration
@pytest.mark.real_providers
async def test_feature_name(real_providers, known_test_codebase):
    """Test description.

    Detailed explanation of what's being validated and why it matters.
    """
    # 1. Arrange - set up test data and state
    project_path = known_test_codebase
    query = "authentication logic"

    # 2. Act - execute the operation
    response = await find_code(
        query=query,
        cwd=str(project_path),
        index_if_needed=True
    )

    # 3. Assert - validate results
    assert response.results
    result_files = [r.file_path.name for r in response.results[:3]]
    assert "auth.py" in result_files, "Should find authentication code"

    # 4. Optional - verify behavior details
    assert response.results[0].score > 0.7, "Top result should be highly relevant"
```

## Troubleshooting

### Common Issues

#### Tests Are Slow

**Expected behavior:**
- Unit tests: <1s per test
- Integration (Tier 1): 1-3s per test
- Integration (Tier 2): 2-15s per test
- Real provider tests are 10-50x slower than mocks

**Solutions:**
- Use `pytest -m "unit"` for fast feedback during development
- Use Tier 2 tests only for validation before commits
- Check if you're accidentally including `real_providers` tests

#### Model Download Errors

```bash
# Download models manually
uv pip install sentence-transformers
uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('ibm-granite/granite-embedding-english-r2')"
uv run python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L6-v2')"
```

Models are cached in:
- `~/.cache/huggingface/`
- `~/.cache/sentence_transformers/`

#### Qdrant Connection Errors

```bash
# Check if Qdrant is running
docker ps | grep qdrant

# Start Qdrant for testing (unauthenticated instance)
docker run -p 6336:6333 qdrant/qdrant:latest

# Or use fixture auto-start (default behavior)
QDRANT_TEST_SKIP_DOCKER=false pytest
```

**Environment variables:**
- `QDRANT_TEST_URL`: Direct URL override
- `QDRANT_TEST_PORT`: Port override (e.g., 6336)
- `QDRANT_TEST_SKIP_DOCKER`: Set to '1' to disable auto-start
- `QDRANT_TEST_API_KEY`: Test-specific API key

See [`QDRANT_TESTING.md`](QDRANT_TESTING.md) for comprehensive Qdrant testing documentation.

#### Search Quality Test Failures

**This is likely a real quality issue - don't just disable the test!**

Investigate:
1. Are embeddings capturing semantic meaning?
2. Is chunking producing good code segments?
3. Is the ranking algorithm working correctly?
4. Is the vector store properly configured?

These tests are designed to catch quality regressions.

#### Permission Errors

```bash
# Tests create files in temp directories
# Ensure you have write permissions

# Check temp directory
echo $TMPDIR

# On WSL/Linux, may need to clean old temp files
rm -rf /tmp/pytest-*
```

#### Import Errors

```bash
# Sync test dependencies
mise run sync

# Or manually
uv sync --group test

# Verify pytest is installed
uv run pytest --version
```

### Debug Mode

```bash
# Show print statements and logging
pytest -s

# Stop on first failure
pytest -x

# Show local variables on failure
pytest -l

# Enter debugger on failure (requires pdbpp)
pytest --pdb

# Verbose output with test names
pytest -vv
```

### Coverage Reports

```bash
# Generate coverage report
mise run test-cov

# View HTML coverage report
open htmlcov/index.html

# Coverage is configured with minimum threshold: 50%
# See pyproject.toml [tool.pytest] section
```

## Performance Expectations

### Target Times

| Test Type | Target | Acceptable | Needs Optimization |
|-----------|--------|------------|-------------------|
| Unit | <1s | <2s | >2s |
| Integration (Tier 1) | 1-3s | <5s | >5s |
| Integration (Tier 2) | 2-15s | <30s | >30s |
| E2E | 10-30s | <60s | >60s |
| Benchmark | Varies | Per SLA | Regression |

### Optimization Tips

1. **Use appropriate markers** - Don't mark fast tests as `expensive`
2. **Prefer Tier 1 for structure** - Use mocks for non-behavior tests
3. **Small test data** - Use minimal data that validates behavior
4. **Parallel execution** - Use `pytest -n auto` for independent tests
5. **Fixture scope** - Use appropriate scope (session, module, function)

## Configuration

### pytest.ini (in pyproject.toml)

```toml
[tool.pytest]
testpaths = ["tests"]
python_files = ["*_test.py", "test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"
timeout = 300  # 5 minute default timeout
timeout_method = "thread"
minversion = "9.0"
```

### Default Exclusions

Tests excluded by default (override with explicit marker):

```bash
not expensive and not requires_models and not requires_gpu and not requires_api_keys
```

To run excluded tests:

```bash
# Run expensive tests
pytest -m "expensive"

# Run tests requiring models
pytest -m "requires_models"

# Run everything
pytest -m ""  # Empty marker runs all tests
```

## Test Quality Standards

### Test Requirements

1. **Clear purpose** - Docstring explains what and why
2. **Proper markers** - Appropriate markers for categorization
3. **Fast by default** - Unit tests should be <1s
4. **Isolated** - Tests don't depend on order
5. **Deterministic** - Same input = same output
6. **Documented failures** - Clear assertion messages

### Code Coverage

- **Minimum threshold**: 50% (enforced in CI)
- **Target**: 70%+ for core modules
- **Focus**: Quality over quantity - meaningful tests

**Coverage configuration:**
```toml
[tool.coverage.run]
omit = ["scripts/*", "mise-tasks/*", "typings/*", ".venv/*"]
```

### When to Add Tests

**Always add tests for:**
- ✅ New features or functionality
- ✅ Bug fixes (regression test)
- ✅ API changes or extensions
- ✅ Performance-critical paths
- ✅ Error handling and edge cases

**Consider adding tests for:**
- Configuration changes
- Documentation updates (doctest)
- Refactoring (if coverage gaps exist)

## Additional Resources

### Test Documentation

- [CLI Tests README](CLI_TESTS_README.md) - CLI-specific testing guide
- [Tier 2 Real Provider Tests](integration/real/README.md) - Comprehensive Tier 2 documentation
- [Qdrant Testing Guide](QDRANT_TESTING.md) - Qdrant test infrastructure
- [Qdrant Environment Variables](QDRANT_ENV_VARS.md) - Qdrant configuration
- [Qdrant Quick Reference](QDRANT_QUICKREF.md) - Common Qdrant operations

### Project Documentation

- [ARCHITECTURE.md](../ARCHITECTURE.md) - System architecture and design
- [CODE_STYLE.md](../CODE_STYLE.md) - Code quality standards
- [AGENTS.md](../AGENTS.md) - Agent system documentation

### Configuration Files

- [pyproject.toml](../pyproject.toml) - Pytest configuration and markers
- [mise.toml](../mise.toml) - Task runner configuration
- [.github/workflows/ci.yml](../.github/workflows/ci.yml) - CI workflow

## Contributing Tests

### Before Submitting

1. **Run relevant test suites:**
   ```bash
   # Fast feedback
   pytest -m "unit"

   # Quality validation
   pytest -m "integration and not real_providers"

   # Search quality (if touching search code)
   pytest -m "real_providers and not benchmark"
   ```

2. **Verify coverage:**
   ```bash
   mise run test-cov
   # Check coverage.xml or htmlcov/index.html
   ```

3. **Add appropriate markers:**
   ```python
   @pytest.mark.unit  # Or integration, e2e, etc.
   @pytest.mark.real_providers  # If using real providers
   @pytest.mark.expensive  # If >30 seconds
   ```

4. **Document test purpose:**
   ```python
   def test_feature():
       """Clear description of what and why.

       Additional context about production failure modes or edge cases.
       """
   ```

### PR Requirements

- All tests must pass in CI
- Coverage should not decrease significantly
- New features require tests
- Bug fixes require regression tests
- Performance-sensitive code requires benchmarks

---

**Last Updated**: 2025-12-10

**Questions?** Check existing test files for examples or open an issue.
