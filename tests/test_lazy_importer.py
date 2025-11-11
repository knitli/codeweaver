# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Tests for lazy import functionality."""

import sys
import threading

from types import ModuleType

import pytest

from codeweaver.common.utils.lazy_importer import LazyImport, lazy_import


pytestmark = [pytest.mark.unit]


@pytest.mark.benchmark
@pytest.mark.performance
class TestLazyImportBasics:
    """Test basic LazyImport functionality."""

    def test_lazy_import_module(self):
        """Test lazy importing a module."""
        # Create lazy import
        os_lazy = lazy_import("os")

        # Should not be resolved yet
        assert not os_lazy.is_resolved()
        assert "not resolved" in repr(os_lazy)

        # Access an attribute - should still not resolve
        path_lazy = os_lazy.path
        assert not os_lazy.is_resolved()
        assert isinstance(path_lazy, LazyImport)

        # Actually use it - should resolve
        path_lazy = os_lazy.path
        assert isinstance(path_lazy, LazyImport)
        assert not path_lazy.is_resolved()

        result = os_lazy.path.join("a", "b")
        assert result == "a/b"
        assert os_lazy.is_resolved()

    def test_lazy_import_function(self):
        """Test lazy importing a specific function."""
        # Import specific function
        join_lazy = lazy_import("os.path", "join")

        assert not join_lazy.is_resolved()

        # Call it - should resolve and execute
        result = join_lazy("a", "b", "c")
        assert result == "a/b/c"
        assert join_lazy.is_resolved()

    def test_lazy_import_class(self):
        """Test lazy importing a class."""
        # Import a class
        Path = lazy_import("pathlib", "Path")

        assert not Path.is_resolved()

        # Instantiate it
        p = Path("/tmp")
        assert Path.is_resolved()
        assert str(p) == "/tmp"

    def test_lazy_import_nested_attributes(self):
        """Test lazy importing with nested attribute access."""
        # Create lazy import with nested attributes
        lazy = lazy_import("collections", "abc", "Mapping")

        assert not lazy.is_resolved()

        # Should work when used
        from collections.abc import Mapping

        assert lazy._resolve() is Mapping
        assert lazy.is_resolved()

    def test_lazy_import_chaining(self):
        """Test attribute chaining without resolution."""
        # Start with module
        collections = lazy_import("collections")
        assert not collections.is_resolved()

        # Chain attribute access
        abc = collections.abc
        assert not collections.is_resolved()
        assert isinstance(abc, LazyImport)

        # Chain more
        Mapping = abc.Mapping
        assert not collections.is_resolved()
        assert isinstance(Mapping, LazyImport)

        # Finally resolve
        from collections.abc import Mapping as ActualMapping

        assert Mapping._resolve() is ActualMapping
        assert Mapping.is_resolved()


@pytest.mark.benchmark
@pytest.mark.performance
class TestLazyImportErrors:
    """Test error handling in LazyImport."""

    def test_module_not_found(self):
        """Test ImportError for non-existent module."""
        lazy = lazy_import("nonexistent_module_xyz")

        with pytest.raises(ImportError, match="Cannot import module"):
            lazy._resolve()

    def test_attribute_not_found(self):
        """Test AttributeError for non-existent attribute."""
        lazy = lazy_import("os", "nonexistent_function")

        with pytest.raises(AttributeError, match="has no attribute"):
            lazy._resolve()

    def test_nested_attribute_not_found(self):
        """Test AttributeError for nested non-existent attributes."""
        lazy = lazy_import("os", "path", "nonexistent_attr")

        with pytest.raises(AttributeError, match="has no attribute"):
            lazy._resolve()

    def test_not_callable_error(self):
        """Test TypeError when calling non-callable."""
        # Import a non-callable attribute
        lazy = lazy_import("os", "name")  # os.name is a string

        with pytest.raises(TypeError):
            lazy()


@pytest.mark.benchmark
@pytest.mark.performance
class TestLazyImportCaching:
    """Test that LazyImport caches resolved values."""

    def test_resolution_caching(self):
        """Test that resolution is cached."""
        lazy = lazy_import("os.path", "join")

        # Resolve twice
        result1 = lazy._resolve()
        result2 = lazy._resolve()

        # Should be the same object
        assert result1 is result2
        assert lazy.is_resolved()

    def test_multiple_calls_same_resolution(self):
        """Test that multiple calls use cached resolution."""
        lazy = lazy_import("os.path", "join")

        # Call multiple times
        result1 = lazy("a", "b")
        result2 = lazy("c", "d")

        # Both should work
        assert result1 == "a/b"
        assert result2 == "c/d"
        assert lazy.is_resolved()


@pytest.mark.benchmark
@pytest.mark.performance
class TestLazyImportThreadSafety:
    """Test thread safety of LazyImport."""

    def test_concurrent_resolution(self):
        """Test that concurrent resolution is thread-safe."""
        lazy = lazy_import("os.path", "join")

        results = []
        errors = []

        def resolve_and_call():
            try:
                result = lazy("a", "b")
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Create multiple threads that try to resolve concurrently
        threads = [threading.Thread(target=resolve_and_call) for _ in range(10)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Should have no errors
        assert not errors
        # All results should be the same
        assert all(r == "a/b" for r in results)
        # Should be resolved exactly once
        assert lazy.is_resolved()


@pytest.mark.benchmark
@pytest.mark.performance
class TestLazyImportRealWorldUseCases:
    """Test real-world use cases from codeweaver."""

    def test_settings_pattern(self):
        """Test the settings getter pattern from codeweaver."""
        # Simulate: _settings = lazy_import("module").get_settings()
        # Create a mock module for testing
        test_module = ModuleType("test_settings_module")

        def get_settings():
            return {"key": "value"}

        test_module.get_settings = get_settings
        sys.modules["test_settings_module"] = test_module

        try:
            # Create lazy import chain
            lazy_getter = lazy_import("test_settings_module").get_settings
            assert not lazy_getter.is_resolved()

            # Call it - should resolve and execute
            settings = lazy_getter()
            assert settings == {"key": "value"}
            assert lazy_getter.is_resolved()
        finally:
            del sys.modules["test_settings_module"]

    def test_type_checking_runtime_pattern(self):
        """Test TYPE_CHECKING + runtime type access pattern."""
        # Create a mock module with a class
        test_module = ModuleType("test_types_module")

        class MyClass:
            def __init__(self, x):
                self.x = x

        test_module.MyClass = MyClass
        sys.modules["test_types_module"] = test_module

        try:
            # Simulate: CodeWeaverSettings = lazy_import("module", "Class")
            LazyClass = lazy_import("test_types_module", "MyClass")
            assert not LazyClass.is_resolved()

            # Use it at runtime
            instance = LazyClass(42)
            assert instance.x == 42
            assert LazyClass.is_resolved()
        finally:
            del sys.modules["test_types_module"]

    def test_global_level_lazy_imports(self):
        """Test using lazy imports at global/module level."""
        # This simulates the main use case: global-level lazy imports

        # Create mock modules
        config_module = ModuleType("mock_config")
        config_module.get_settings = lambda: {"loaded": True}

        tiktoken_module = ModuleType("mock_tiktoken")
        tiktoken_module.get_encoding = lambda name: f"Encoding({name})"

        sys.modules["mock_config"] = config_module
        sys.modules["mock_tiktoken"] = tiktoken_module

        try:
            # Global-level lazy imports (like at module scope)
            _get_settings = lazy_import("mock_config").get_settings
            _tiktoken = lazy_import("mock_tiktoken")

            # Neither should be resolved yet
            assert not _get_settings.is_resolved()
            assert not _tiktoken.is_resolved()

            # Use them later (like in functions)
            settings = _get_settings()
            assert settings == {"loaded": True}
            assert _get_settings.is_resolved()

            encoder = _tiktoken.get_encoding("gpt2")
            assert encoder == "Encoding(gpt2)"
            assert _tiktoken.is_resolved()
        finally:
            del sys.modules["mock_config"]
            del sys.modules["mock_tiktoken"]


@pytest.mark.benchmark
@pytest.mark.performance
class TestLazyImportMagicMethods:
    """Test magic method forwarding."""

    def test_repr(self):
        """Test __repr__ shows path and status."""
        lazy = lazy_import("os", "path", "join")

        repr_str = repr(lazy)
        assert "os.path.join" in repr_str
        assert "not resolved" in repr_str

        # Resolve it
        lazy._resolve()
        repr_str = repr(lazy)
        assert "resolved" in repr_str
        assert "not resolved" not in repr_str

    def test_dir(self):
        """Test __dir__ forwards to resolved object."""
        lazy = lazy_import("os")

        # dir() should resolve and forward
        assert not lazy.is_resolved()
        dirs = dir(lazy)
        assert lazy.is_resolved()
        assert "path" in dirs
        assert "name" in dirs

    def test_setattr(self):
        """Test __setattr__ forwards to resolved object."""
        # Create a mock module
        test_module = ModuleType("test_setattr_module")
        sys.modules["test_setattr_module"] = test_module

        try:
            lazy = lazy_import("test_setattr_module")

            # Set an attribute - should resolve
            assert not lazy.is_resolved()
            lazy.custom_attr = "value"
            assert lazy.is_resolved()
            assert test_module.custom_attr == "value"
        finally:
            del sys.modules["test_setattr_module"]


@pytest.mark.benchmark
@pytest.mark.performance
class TestLazyImportComparison:
    """Compare LazyImport with old lazy_importer pattern."""

    def test_old_vs_new_syntax(self):
        """Compare old awkward syntax vs new clean syntax."""
        # OLD pattern (what you had before):
        # module = lazy_importer("os")()  # Awkward double-call

        # NEW pattern:
        module = lazy_import("os")
        result = module.path.join("a", "b")

        assert result == "a/b"

    def test_chaining_impossible_with_old_pattern(self):
        """Show that attribute chaining was impossible with old pattern."""
        # OLD: lazy_importer("os").path  # Would execute import immediately!

        # NEW: Can chain without execution
        lazy = lazy_import("os").path.join
        assert not lazy.is_resolved()  # Still lazy!

        result = lazy("a", "b")
        assert result == "a/b"
        assert lazy.is_resolved()


@pytest.mark.benchmark
@pytest.mark.performance
class TestEdgeCases:
    """Test edge cases and special scenarios."""

    def test_empty_attribute_chain(self):
        """Test LazyImport with no attributes (just module)."""
        lazy = LazyImport("os")
        result = lazy._resolve()

        import os

        assert result is os

    def test_single_attribute(self):
        """Test LazyImport with single attribute."""
        lazy = LazyImport("os", "name")
        result = lazy._resolve()

        import os

        assert result == os.name

    def test_multiple_attribute_chains(self):
        """Test multiple levels of attribute chaining."""
        lazy = lazy_import("os")
        chained = lazy.path.join

        assert isinstance(chained, LazyImport)
        result = chained("a", "b", "c")
        assert result == "a/b/c"

    def test_lazy_import_with_existing_import(self):
        """Test LazyImport when module is already imported."""
        # Import normally first

        # Now create lazy import
        lazy = lazy_import("os")

        # Should still work
        result = lazy.path.join("a", "b")
        assert result == "a/b"

    def test_multiple_lazy_imports_same_module(self):
        """Test multiple LazyImport instances for same module."""
        lazy1 = lazy_import("os")
        lazy2 = lazy_import("os")

        # Different LazyImport instances
        assert lazy1 is not lazy2

        # But resolve to same module
        assert lazy1._resolve() is lazy2._resolve()


@pytest.mark.benchmark
@pytest.mark.performance
class TestDocumentationExamples:
    """Test all examples from the documentation."""

    def test_basic_module_import_example(self):
        """Test example from LazyImport docstring."""
        lazy_import("tiktoken")
        # Would normally do: encoding = tiktoken.get_encoding("cl100k_base")
        # But tiktoken might not be installed, so we test with os instead

        os_lazy = lazy_import("os")
        result = os_lazy.path.join("a", "b")
        assert result == "a/b"

    def test_function_import_example(self):
        """Test function import example."""
        join = lazy_import("os.path", "join")
        result = join("a", "b", "c")
        assert result == "a/b/c"

    def test_attribute_chaining_example(self):
        """Test attribute chaining example."""
        Mapping = lazy_import("collections").abc.Mapping

        assert isinstance(Mapping, LazyImport)
        from collections.abc import Mapping as ActualMapping

        assert Mapping._resolve() is ActualMapping


@pytest.mark.benchmark
@pytest.mark.performance
class TestLazyImportPerformance:
    """Test performance characteristics of LazyImport."""

    def test_resolution_overhead(self):
        """Test that lazy resolution overhead is reasonable."""
        import time

        # Measure lazy import + resolution
        iterations = 1000
        start = time.perf_counter()
        for _ in range(iterations):
            lazy = lazy_import("os.path", "join")
            result = lazy("a", "b")
            assert result == "a/b"
        lazy_time = time.perf_counter() - start

        # Measure direct import (baseline)
        start = time.perf_counter()
        for _ in range(iterations):
            from os.path import join

            result = join("a", "b")
            assert result == "a/b"
        direct_time = time.perf_counter() - start

        # Lazy import should be within reasonable overhead (10x)
        # This is a sanity check, not a strict performance requirement
        assert lazy_time < direct_time * 10, (
            f"Lazy import too slow: {lazy_time:.4f}s vs direct {direct_time:.4f}s "
            f"(ratio: {lazy_time / direct_time:.1f}x)"
        )

    def test_cached_resolution_performance(self):
        """Test that cached resolution is fast (minimal overhead)."""
        import time

        lazy = lazy_import("os.path", "join")
        # Pre-resolve it
        lazy._resolve()

        # Measure cached access
        iterations = 10000
        start = time.perf_counter()
        for _ in range(iterations):
            result = lazy("a", "b")
            assert result == "a/b"
        cached_time = time.perf_counter() - start

        # Measure direct access (baseline)
        from os.path import join

        start = time.perf_counter()
        for _ in range(iterations):
            result = join("a", "b")
            assert result == "a/b"
        direct_time = time.perf_counter() - start

        # Cached access should be reasonably fast (within 3x of direct access)
        # Note: There is inherent overhead from __call__ forwarding even after resolution
        assert cached_time < direct_time * 3, (
            f"Cached access too slow: {cached_time:.4f}s vs direct {direct_time:.4f}s "
            f"(ratio: {cached_time / direct_time:.1f}x)"
        )


@pytest.mark.benchmark
@pytest.mark.performance
class TestLazyImportIntrospection:
    """Test LazyImport compatibility with introspection tools like inspect and pydantic."""

    def test_inspect_signature_compatibility(self):
        """Test that inspect.signature() works with LazyImport objects."""
        from inspect import signature

        # Create a lazy import to a function
        get_settings_lazy = lazy_import("codeweaver.config.settings", "get_settings")

        # This should not raise AttributeError
        sig = signature(get_settings_lazy)

        # Verify we got a valid signature
        assert sig is not None
        assert "config_file" in str(sig)

        # The lazy import should now be resolved
        assert get_settings_lazy.is_resolved()

    def test_pydantic_default_factory_compatibility(self):
        """Test that LazyImport can be used as a pydantic default_factory."""
        from pydantic import Field
        from pydantic.dataclasses import dataclass

        # This is the pattern used in AppState
        get_settings_lazy = lazy_import("codeweaver.config.settings", "get_settings")

        @dataclass
@pytest.mark.benchmark
@pytest.mark.performance
        class TestModel:
            settings: object = Field(default_factory=get_settings_lazy)

        # This should not raise during schema generation
        model = TestModel()
        assert model.settings is not None

    def test_introspection_attributes_resolve(self):
        """Test that accessing introspection attributes resolves the object."""
        from codeweaver.config.settings import get_settings

        get_settings_lazy = lazy_import("codeweaver.config.settings", "get_settings")

        # Should not be resolved yet
        assert not get_settings_lazy.is_resolved()

        # Accessing __name__ should resolve
        name = get_settings_lazy.__name__
        assert name == get_settings.__name__
        assert get_settings_lazy.is_resolved()

    def test_introspection_attributes_missing(self):
        """Test that missing introspection attributes raise AttributeError."""
        # Create lazy import to something that doesn't have __text_signature__
        lazy = lazy_import("os")

        # Should raise AttributeError for missing introspection attributes
        with pytest.raises(AttributeError):
            _ = lazy.__text_signature__
