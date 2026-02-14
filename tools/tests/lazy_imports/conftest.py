# sourcery skip: no-relative-imports
"""Shared fixtures for lazy import tests."""

from __future__ import annotations

import json

from pathlib import Path

import pytest


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """Temporary directory for cache."""
    cache_dir = tmp_path / ".codeweaver" / "cache"
    cache_dir.mkdir(parents=True)
    return cache_dir


@pytest.fixture
def temp_project(tmp_path: Path) -> Path:
    """Create temporary project structure."""
    project = tmp_path / "test_project"
    project.mkdir()

    (project / "src").mkdir()
    (project / "src" / "package").mkdir()

    return project


@pytest.fixture
def sample_rules() -> list[dict]:
    """Sample rule configuration."""
    return [
        {
            "name": "include-public-classes",
            "priority": 800,
            "description": "Include public classes (PascalCase)",
            "match": {"name_pattern": r"^[A-Z][a-zA-Z0-9]*$", "member_type": "class"},
            "action": "include",
            "propagate": "parent",
        },
        {
            "name": "exclude-private",
            "priority": 900,
            "description": "Exclude private members",
            "match": {"name_pattern": r"^_"},
            "action": "exclude",
        },
        {
            "name": "include-version",
            "priority": 950,
            "description": "Include __version__",
            "match": {"name_exact": "__version__"},
            "action": "include",
            "propagate": "root",
        },
    ]


@pytest.fixture
def sample_yaml_rules() -> str:
    """Sample rules in YAML format."""
    return """schema_version: "1.0"

rules:
  - name: "include-public-classes"
    priority: 800
    description: "Include public classes (PascalCase)"
    match:
      name_pattern: "^[A-Z][a-zA-Z0-9]*$"
      member_type: "class"
    action: include
    propagate: parent

  - name: "exclude-private"
    priority: 900
    description: "Exclude private members"
    match:
      name_pattern: "^_"
    action: exclude

  - name: "include-version"
    priority: 950
    description: "Include __version__"
    match:
      name_exact: "__version__"
    action: include
    propagate: root
"""


@pytest.fixture
def rule_engine(sample_rules):
    """Configured rule engine."""
    from tools.lazy_imports.export_manager.rules import RuleEngine

    engine = RuleEngine()
    # Note: RuleEngine() takes no arguments.
    # If rules need to be loaded, use engine.add_rule() or load from config
    return engine


@pytest.fixture
def analysis_cache(temp_cache_dir: Path):
    """Fresh analysis cache."""
    from tools.lazy_imports.common.cache import JSONAnalysisCache

    return JSONAnalysisCache(cache_dir=temp_cache_dir)


def create_test_module(path: Path, content: str) -> Path:
    """Helper to create test module files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def create_test_modules(base_path: Path, count: int) -> list[Path]:
    """Create multiple test modules for benchmarking."""
    modules = []
    for i in range(count):
        module_path = base_path / f"module_{i}.py"
        content = f'''"""Test module {i}."""

class TestClass{i}:
    """Test class."""
    pass


def test_function_{i}():
    """Test function."""
    pass


TEST_CONSTANT_{i} = {i}
'''
        modules.append(create_test_module(module_path, content))
    return modules


def write_yaml_file(path: Path, content: str) -> Path:
    """Write YAML file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def write_json_file(path: Path, data: dict) -> Path:
    """Write JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    return path


@pytest.fixture
def simple_python_module() -> str:
    """Simple Python module content."""
    return '''"""Simple test module."""

class PublicClass:
    """A public class."""
    pass


class _PrivateClass:
    """A private class."""
    pass


def public_function():
    """A public function."""
    pass


def _private_function():
    """A private function."""
    pass


PUBLIC_CONSTANT = "value"
_PRIVATE_CONSTANT = "private"
'''


@pytest.fixture
def complex_python_module() -> str:
    """Complex Python module with multiple types."""
    return '''"""Complex test module."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


class MyClass:
    """Public class."""

    def method(self) -> None:
        """Method."""
        pass


class AnotherClass:
    """Another public class."""
    pass


def get_config() -> dict:
    """Get configuration."""
    return {}


def _internal_helper() -> None:
    """Internal helper."""
    pass


# Type alias
ConfigDict = dict[str, Any]

# Constants
VERSION = "1.0.0"
_INTERNAL_SETTING = "secret"

# Re-exports
from .other_module import ReExported  # noqa: E402, F401
'''


@pytest.fixture
def nested_module_structure(tmp_path: Path) -> Path:
    """Create nested module structure for testing propagation."""
    root = tmp_path / "test_package"

    # Create structure: test_package/core/types/models.py
    models_dir = root / "core" / "types"
    models_dir.mkdir(parents=True)

    # Create models.py
    create_test_module(
        models_dir / "models.py",
        '''"""Models module."""

class MyModel:
    """A model class."""
    pass


class AnotherModel:
    """Another model."""
    pass
''',
    )

    # Create types/__init__.py
    create_test_module(models_dir / "__init__.py", "")

    # Create core/__init__.py
    create_test_module(root / "core" / "__init__.py", "")

    # Create package __init__.py
    create_test_module(root / "__init__.py", "")

    return root
