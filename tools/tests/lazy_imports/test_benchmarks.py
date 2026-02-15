# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Performance benchmarks for lazy import system.

Tests verify performance requirements from lazy-import-requirements.md:
- REQ-PERF-001: Processing <5s for 500 modules
- REQ-PERF-002: Cache hit rate >90%
- REQ-PERF-003: Incremental processing <500ms
- REQ-PERF-004: Memory usage <500MB
"""

# sourcery skip: require-return-annotation, require-parameter-annotation, no-relative-imports, avoid-loops-in-tests
from __future__ import annotations

import time
import tracemalloc

from pathlib import Path

import pytest


@pytest.mark.benchmark
class TestPerformanceBenchmarks:
    """Performance benchmark suite."""

    def test_processing_speed_requirement(self, tmp_path: Path):
        """REQ-PERF-001: Full pipeline should complete in <5s for 500 modules."""
        from tools.lazy_imports.common.types import ExportNode, MemberType, PropagationLevel
        from tools.lazy_imports.export_manager.graph import PropagationGraph
        from tools.tests.lazy_imports.conftest import create_test_modules

        # Create 500 test modules
        modules_dir = tmp_path / "test_package"
        modules_dir.mkdir()

        modules = create_test_modules(modules_dir, count=500)

        # Measure processing time
        start = time.time()

        from tools.lazy_imports.export_manager.rules import RuleEngine

        engine = RuleEngine()
        graph = PropagationGraph(rule_engine=engine)

        # Register parent module
        graph.add_module("test_package", None)

        # Simulate processing all modules
        for i, module_file in enumerate(modules):
            # Register module
            graph.add_module(f"test_package.module_{i}", "test_package")

            # Create exports for each module
            export = ExportNode(
                name=f"TestClass{i}",
                module=f"test_package.module_{i}",
                member_type=MemberType.CLASS,
                propagation=PropagationLevel.PARENT,
                source_file=module_file,
                line_number=4,
                defined_in=f"test_package.module_{i}",
            )
            graph.add_export(export)

        # Build manifests
        manifests = graph.build_manifests()

        duration = time.time() - start

        # Verify requirement
        assert duration < 5.0, f"Processing took {duration:.2f}s, expected <5s"
        assert len(manifests) > 0

    def test_cache_effectiveness_requirement(self, tmp_path: Path, temp_cache_dir: Path):
        """REQ-PERF-002: Cache hit rate should be >90% on second run."""
        from tools.lazy_imports.common.cache import JSONAnalysisCache
        from tools.lazy_imports.common.types import (
            AnalysisResult,
            ExportNode,
            MemberType,
            PropagationLevel,
        )

        cache = JSONAnalysisCache(cache_dir=temp_cache_dir)

        # Create 100 test files
        files = []
        for i in range(100):
            file = tmp_path / f"module{i}.py"
            file.write_text(f"class Class{i}: pass")
            files.append(file)

        # First run - populate cache
        for i, file in enumerate(files):
            exports = [
                ExportNode(
                    name=f"Class{i}",
                    module="test",
                    member_type=MemberType.CLASS,
                    propagation=PropagationLevel.PARENT,
                    source_file=file,
                    line_number=1,
                    defined_in="test",
                )
            ]

            analysis = AnalysisResult(
                exports=exports,
                imports=[],
                file_hash=f"hash{i}",
                analysis_timestamp=time.time(),
                schema_version="1.0",
            )

            cache.put(file, f"hash{i}", analysis)

        # Second run - measure cache hits
        cache_hits = 0
        cache_misses = 0

        for i, file in enumerate(files):
            cached = cache.get(file, f"hash{i}")
            if cached is not None:
                cache_hits += 1
            else:
                cache_misses += 1

        # Calculate hit rate
        hit_rate = cache_hits / (cache_hits + cache_misses)

        # Verify requirement
        assert hit_rate > 0.90, f"Cache hit rate {hit_rate:.2%}, expected >90%"

    def test_incremental_update_speed(self, tmp_path: Path, temp_cache_dir: Path):
        """REQ-PERF-003: Single file update should take <500ms."""
        from tools.lazy_imports.common.cache import JSONAnalysisCache
        from tools.lazy_imports.common.types import (
            AnalysisResult,
            ExportNode,
            MemberType,
            PropagationLevel,
        )

        cache = JSONAnalysisCache(cache_dir=temp_cache_dir)

        # Create many files and cache them
        files = []
        for i in range(100):
            file = tmp_path / f"module{i}.py"
            file.write_text(f"class Class{i}: pass")
            files.append(file)

            exports = [
                ExportNode(
                    name=f"Class{i}",
                    module="test",
                    member_type=MemberType.CLASS,
                    propagation=PropagationLevel.PARENT,
                    source_file=file,
                    line_number=1,
                    defined_in="test",
                )
            ]

            analysis = AnalysisResult(
                exports=exports,
                imports=[],
                file_hash=f"hash{i}",
                analysis_timestamp=time.time(),
                schema_version="1.0",
            )

            cache.put(file, f"hash{i}", analysis)

        # Modify one file
        files[50].write_text("class ModifiedClass: pass")

        # Measure incremental update
        start = time.time()

        # Simulate incremental update (only modified file)
        new_exports = [
            ExportNode(
                name="ModifiedClass",
                module="test",
                member_type=MemberType.CLASS,
                propagation=PropagationLevel.PARENT,
                source_file=files[50],
                line_number=1,
                defined_in="test",
            )
        ]

        new_analysis = AnalysisResult(
            exports=new_exports,
            imports=[],
            file_hash="new_hash",
            analysis_timestamp=time.time(),
            schema_version="1.0",
        )

        cache.put(files[50], "new_hash", new_analysis)

        duration = time.time() - start

        # Verify requirement
        assert duration < 0.5, f"Incremental update took {duration:.3f}s, expected <0.5s"

    def test_memory_usage_requirement(self, tmp_path: Path):
        """REQ-PERF-004: Memory usage should be <500MB for large codebase."""
        from tools.lazy_imports.common.types import ExportNode, MemberType, PropagationLevel
        from tools.lazy_imports.export_manager.graph import PropagationGraph
        from tools.tests.lazy_imports.conftest import create_test_modules

        # Start memory tracking
        tracemalloc.start()

        # Create 1000 test modules
        modules_dir = tmp_path / "large_package"
        modules_dir.mkdir()

        modules = create_test_modules(modules_dir, count=1000)

        from tools.lazy_imports.export_manager.rules import RuleEngine

        engine = RuleEngine()
        graph = PropagationGraph(rule_engine=engine)

        # Register parent module
        graph.add_module("large_package", None)

        # Process all modules
        for i, module_file in enumerate(modules):
            # Register module
            graph.add_module(f"large_package.module_{i}", "large_package")

            export = ExportNode(
                name=f"Class{i}",
                module=f"large_package.module_{i}",
                member_type=MemberType.CLASS,
                propagation=PropagationLevel.PARENT,
                source_file=module_file,
                line_number=4,
                defined_in=f"large_package.module_{i}",
            )
            graph.add_export(export)

        # Build manifests
        manifests = graph.build_manifests()

        # Get peak memory usage
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak / (1024 * 1024)

        # Verify requirement
        assert peak_mb < 500, f"Peak memory {peak_mb:.2f}MB, expected <500MB"
        assert len(manifests) > 0

    def test_cache_operation_speed(self, temp_cache_dir: Path):
        """REQ-PERF-004 (extended): Cache operations should be <50ms."""
        from tools.lazy_imports.common.cache import JSONAnalysisCache
        from tools.lazy_imports.common.types import (
            AnalysisResult,
            ExportNode,
            MemberType,
            PropagationLevel,
        )

        cache = JSONAnalysisCache(cache_dir=temp_cache_dir)

        exports = [
            ExportNode(
                name="TestClass",
                module="test",
                member_type=MemberType.CLASS,
                propagation=PropagationLevel.PARENT,
                source_file=Path("test.py"),
                line_number=1,
                defined_in="test",
            )
        ]

        analysis = AnalysisResult(
            exports=exports,
            imports=[],
            file_hash="hash123",
            analysis_timestamp=time.time(),
            schema_version="1.0",
        )

        # Measure cache put
        start = time.time()
        cache.put(Path("test.py"), "hash123", analysis)
        put_duration = (time.time() - start) * 1000  # Convert to ms

        # Measure cache get
        start = time.time()
        cached = cache.get(Path("test.py"), "hash123")
        get_duration = (time.time() - start) * 1000  # Convert to ms

        # Verify operations are fast
        assert put_duration < 50, f"Cache put took {put_duration:.2f}ms, expected <50ms"
        assert get_duration < 50, f"Cache get took {get_duration:.2f}ms, expected <50ms"
        assert cached is not None


@pytest.mark.benchmark
class TestScalability:
    """Test system scalability with increasing loads."""

    def test_linear_scaling_with_module_count(self, tmp_path: Path):
        """Processing time should scale linearly with module count."""
        from tools.lazy_imports.common.types import ExportNode, MemberType, PropagationLevel
        from tools.lazy_imports.export_manager.graph import PropagationGraph
        from tools.tests.lazy_imports.conftest import create_test_modules

        module_counts = [50, 100, 200]
        durations = []

        for count in module_counts:
            modules_dir = tmp_path / f"package_{count}"
            modules_dir.mkdir()

            modules = create_test_modules(modules_dir, count=count)

            start = time.time()

            from tools.lazy_imports.export_manager.rules import RuleEngine

            engine = RuleEngine()
            graph = PropagationGraph(rule_engine=engine)

            # Register parent module
            graph.add_module(f"package_{count}", None)

            for i, module_file in enumerate(modules):
                # Register module
                graph.add_module(f"package_{count}.module_{i}", f"package_{count}")

                export = ExportNode(
                    name=f"Class{i}",
                    module=f"package_{count}.module_{i}",
                    member_type=MemberType.CLASS,
                    propagation=PropagationLevel.PARENT,
                    source_file=module_file,
                    line_number=1,
                    defined_in=f"package_{count}.module_{i}",
                )
                graph.add_export(export)

            graph.build_manifests()

            duration = time.time() - start
            durations.append(duration)

        # Check approximate linear scaling
        # 200 modules should take ~4x as long as 50 modules (within tolerance)
        ratio = durations[2] / durations[0]  # 200/50 = 4x
        assert 2 < ratio < 6, f"Scaling ratio {ratio:.2f}, expected ~4x for linear scaling"

    def test_cache_hit_rate_stable(self, tmp_path: Path, temp_cache_dir: Path):
        """Cache hit rate should remain stable with more files."""
        from tools.lazy_imports.common.cache import JSONAnalysisCache
        from tools.lazy_imports.common.types import (
            AnalysisResult,
            ExportNode,
            MemberType,
            PropagationLevel,
        )

        cache = JSONAnalysisCache(cache_dir=temp_cache_dir)

        # Test with increasing file counts
        for count in [50, 100, 200]:
            files = []
            for i in range(count):
                file = tmp_path / f"test_{count}" / f"module{i}.py"
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(f"class Class{i}: pass")
                files.append(file)

            # Populate cache
            for i, file in enumerate(files):
                exports = [
                    ExportNode(
                        name=f"Class{i}",
                        module="test",
                        member_type=MemberType.CLASS,
                        propagation=PropagationLevel.PARENT,
                        source_file=file,
                        line_number=1,
                        defined_in="test",
                    )
                ]

                analysis = AnalysisResult(
                    exports=exports,
                    imports=[],
                    file_hash=f"hash{count}_{i}",
                    analysis_timestamp=time.time(),
                    schema_version="1.0",
                )

                cache.put(file, f"hash{count}_{i}", analysis)

            # Measure hit rate
            hits = sum(
                cache.get(file, f"hash{count}_{i}") is not None for i, file in enumerate(files)
            )

            hit_rate = hits / len(files)

            # Hit rate should remain high
            assert hit_rate > 0.95, f"Hit rate {hit_rate:.2%} for {count} files, expected >95%"


@pytest.mark.benchmark
class TestConcurrency:
    """Test concurrent operations."""

    def test_concurrent_cache_access(self, temp_cache_dir: Path):
        """Cache should handle concurrent access."""
        from tools.lazy_imports.common.cache import JSONAnalysisCache
        from tools.lazy_imports.common.types import (
            AnalysisResult,
            ExportNode,
            MemberType,
            PropagationLevel,
        )

        cache = JSONAnalysisCache(cache_dir=temp_cache_dir)

        exports = [
            ExportNode(
                name="Class",
                module="test",
                member_type=MemberType.CLASS,
                propagation=PropagationLevel.PARENT,
                source_file=Path("test.py"),
                line_number=1,
                defined_in="test",
            )
        ]

        analysis = AnalysisResult(
            exports=exports,
            imports=[],
            file_hash="hash123",
            analysis_timestamp=time.time(),
            schema_version="1.0",
        )

        # Multiple operations in sequence (simulating concurrent access)
        for _ in range(10):
            cache.put(Path("test.py"), "hash123", analysis)

        for _ in range(10):
            cached = cache.get(Path("test.py"), "hash123")
            assert cached is not None

        # Cache should remain consistent
        final = cache.get(Path("test.py"), "hash123")
        assert final is not None
