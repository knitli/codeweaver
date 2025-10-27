# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Performance benchmarks for chunker system.

Validates that chunking performance meets targets specified in architecture spec §6.1:
- Typical files (100-1000 lines): 100-500 files/second
- Large files (1000-5000 lines): 50-200 files/second
- Very large files (5000+ lines): 10-50 files/second
- Memory usage < 100MB per operation
"""

import time

from pathlib import Path

import pytest

from codeweaver.core.discovery import DiscoveredFile
from codeweaver.engine.chunker.base import ChunkGovernor
from codeweaver.engine.chunker.selector import ChunkerSelector
from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities


# Test data generators
def generate_python_file(num_lines: int) -> str:
    """Generate Python file with specified number of lines."""
    functions_count = num_lines // 10
    lines = ["# Test file for performance benchmarking\n\n"]

    for i in range(functions_count):
        lines.extend([
            f"def function_{i}(x, y):\n",
            f'    """Function {i} docstring."""\n',
            "    result = x + y\n",
            "    if result > 100:\n",
            "        return result * 2\n",
            "    else:\n",
            "        return result + 10\n",
            "\n",
        ])

    return "".join(lines)


def generate_javascript_file(num_lines: int) -> str:
    """Generate JavaScript file with specified number of lines."""
    functions_count = num_lines // 12
    lines = ["// Test file for performance benchmarking\n\n"]

    for i in range(functions_count):
        lines.extend([
            f"function process_{i}(data) {{\n",
            f"  // Process data {i}\n",
            "  const result = data.map(x => x * 2);\n",
            "  if (result.length > 100) {\n",
            "    return result.filter(x => x > 50);\n",
            "  } else {\n",
            "    return result.reduce((a, b) => a + b, 0);\n",
            "  }\n",
            "}\n",
            "\n",
        ])

    return "".join(lines)


class TestChunkerPerformance:
    """Performance benchmarks for chunking operations."""

    @pytest.fixture
    def governor(self):
        """Create chunk governor with default settings."""
        # Create mock capabilities with typical context window
        mock_cap = EmbeddingModelCapabilities(
            model_name="test-model",
            embedding_dimensions=768,
            context_window=8192,
            max_batch_size=100,
        )
        return ChunkGovernor(capabilities=(mock_cap,))

    @pytest.fixture
    def selector(self, governor):
        """Create chunker selector."""
        return ChunkerSelector(governor)

    # Typical files: 100-1000 lines
    @pytest.mark.benchmark
    def test_typical_python_file_performance(self, selector, benchmark):
        """Benchmark typical Python file (500 lines).

        Target: 100-500 files/second
        Expected: ~200-300 files/second on typical hardware
        """
        content = generate_python_file(500)
        file_path = Path("benchmark_test.py")

        def chunk_file():
            discovered_file = DiscoveredFile(path=file_path)
            chunker = selector.select_for_file(discovered_file)
            return chunker.chunk(content, file_path=file_path)

        result = benchmark(chunk_file)

        # Verify results are valid
        assert len(result) > 0, "Should produce chunks"
        assert all(chunk.content for chunk in result), "All chunks should have content"

        # Performance target: < 5ms per file (200 files/second)
        assert benchmark.stats["mean"] < 0.005, (
            f"Mean time {benchmark.stats['mean']:.4f}s exceeds target of 0.005s"
        )

    @pytest.mark.benchmark
    def test_typical_javascript_file_performance(self, selector, benchmark):
        """Benchmark typical JavaScript file (500 lines).

        Target: 100-500 files/second
        """
        content = generate_javascript_file(500)
        file_path = Path("benchmark_test.js")

        def chunk_file():
            discovered_file = DiscoveredFile(path=file_path)
            chunker = selector.select_for_file(discovered_file)
            return chunker.chunk(content, file_path=file_path)

        result = benchmark(chunk_file)

        assert len(result) > 0
        assert benchmark.stats["mean"] < 0.005

    # Large files: 1000-5000 lines
    @pytest.mark.benchmark
    def test_large_python_file_performance(self, selector, benchmark):
        """Benchmark large Python file (3000 lines).

        Target: 50-200 files/second
        Expected: ~100-150 files/second
        """
        content = generate_python_file(3000)
        file_path = Path("large_benchmark.py")

        def chunk_file():
            discovered_file = DiscoveredFile(path=file_path)
            chunker = selector.select_for_file(discovered_file)
            return chunker.chunk(content, file_path=file_path)

        result = benchmark(chunk_file)

        assert len(result) > 0
        # Performance target: < 20ms per file (50 files/second)
        assert benchmark.stats["mean"] < 0.020, (
            f"Mean time {benchmark.stats['mean']:.4f}s exceeds target of 0.020s"
        )

    # Very large files: 5000+ lines
    @pytest.mark.benchmark
    def test_very_large_python_file_performance(self, selector, benchmark):
        """Benchmark very large Python file (7000 lines).

        Target: 10-50 files/second
        Expected: ~20-30 files/second
        """
        content = generate_python_file(7000)
        file_path = Path("very_large_benchmark.py")

        def chunk_file():
            discovered_file = DiscoveredFile(path=file_path)
            chunker = selector.select_for_file(discovered_file)
            return chunker.chunk(content, file_path=file_path)

        result = benchmark(chunk_file)

        assert len(result) > 0
        # Performance target: < 100ms per file (10 files/second)
        assert benchmark.stats["mean"] < 0.100, (
            f"Mean time {benchmark.stats['mean']:.4f}s exceeds target of 0.100s"
        )

    # Memory profiling
    @pytest.mark.benchmark
    @pytest.mark.skipif(
        not pytest.importorskip("memory_profiler", minversion=None),
        reason="memory_profiler not installed",
    )
    def test_memory_usage_typical_file(self, selector):
        """Verify memory usage stays under 100MB for typical files.

        Target: < 100MB per operation
        """
        import tracemalloc

        content = generate_python_file(500)
        file_path = Path("memory_test.py")

        # Start memory tracking
        tracemalloc.start()
        snapshot_before = tracemalloc.take_snapshot()

        # Perform chunking
        chunker = selector.select_for_file_path(file_path)
        result = chunker.chunk(content, file_path=file_path)

        # Measure memory delta
        snapshot_after = tracemalloc.take_snapshot()
        top_stats = snapshot_after.compare_to(snapshot_before, "lineno")

        total_memory_mb = sum(stat.size_diff for stat in top_stats) / (1024 * 1024)
        tracemalloc.stop()

        assert len(result) > 0
        assert total_memory_mb < 100, (
            f"Memory usage {total_memory_mb:.2f}MB exceeds target of 100MB"
        )

    @pytest.mark.benchmark
    @pytest.mark.skipif(
        not pytest.importorskip("memory_profiler", minversion=None),
        reason="memory_profiler not installed",
    )
    def test_memory_usage_large_file(self, selector):
        """Verify memory usage stays under 100MB even for large files.

        Target: < 100MB per operation
        """
        import tracemalloc

        content = generate_python_file(3000)
        file_path = Path("memory_large_test.py")

        tracemalloc.start()
        snapshot_before = tracemalloc.take_snapshot()

        chunker = selector.select_for_file_path(file_path)
        result = chunker.chunk(content, file_path=file_path)

        snapshot_after = tracemalloc.take_snapshot()
        top_stats = snapshot_after.compare_to(snapshot_before, "lineno")

        total_memory_mb = sum(stat.size_diff for stat in top_stats) / (1024 * 1024)
        tracemalloc.stop()

        assert len(result) > 0
        assert total_memory_mb < 100, (
            f"Memory usage {total_memory_mb:.2f}MB exceeds target of 100MB"
        )

    # Throughput test
    @pytest.mark.benchmark
    def test_bulk_file_throughput(self, selector):
        """Test throughput with multiple files of varying sizes."""
        test_files = [
            (generate_python_file(200), Path("small_1.py")),
            (generate_python_file(500), Path("typical_1.py")),
            (generate_python_file(800), Path("typical_2.py")),
            (generate_javascript_file(300), Path("small_1.js")),
            (generate_javascript_file(600), Path("typical_1.js")),
        ]

        start_time = time.perf_counter()
        total_chunks = 0

        for content, file_path in test_files:
            discovered_file = DiscoveredFile(path=file_path)
            chunker = selector.select_for_file(discovered_file)
            chunks = chunker.chunk(content, file_path=file_path)
            total_chunks += len(chunks)

        elapsed = time.perf_counter() - start_time
        files_per_second = len(test_files) / elapsed

        assert total_chunks > 0, "Should produce chunks"
        assert files_per_second > 50, (
            f"Throughput {files_per_second:.1f} files/sec below minimum of 50"
        )

    # Performance regression tracking
    @pytest.mark.benchmark
    def test_semantic_vs_delimiter_performance(self, selector, benchmark):
        """Compare semantic and delimiter chunker performance on same content."""
        from codeweaver.core.language import SemanticSearchLanguage
        from codeweaver.engine.chunker.delimiter import DelimiterChunker
        from codeweaver.engine.chunker.semantic import SemanticChunker

        content = generate_python_file(500)
        file_path = Path("comparison.py")

        # Test semantic chunker
        governor = selector.governor
        semantic_chunker = SemanticChunker(governor, SemanticSearchLanguage.PYTHON)

        start = time.perf_counter()
        semantic_result = semantic_chunker.chunk(content, file_path=file_path)
        semantic_time = time.perf_counter() - start

        # Test delimiter chunker
        delimiter_chunker = DelimiterChunker(governor, "python")

        start = time.perf_counter()
        delimiter_result = delimiter_chunker.chunk(content, file_path=file_path)
        delimiter_time = time.perf_counter() - start

        # Log results for regression tracking
        print(f"\nSemantic: {len(semantic_result)} chunks in {semantic_time * 1000:.2f}ms")
        print(f"Delimiter: {len(delimiter_result)} chunks in {delimiter_time * 1000:.2f}ms")
        print(f"Ratio: {semantic_time / delimiter_time:.2f}x")

        # Both should complete reasonably fast
        assert semantic_time < 0.010, "Semantic chunker too slow"
        assert delimiter_time < 0.010, "Delimiter chunker too slow"


class TestChunkerScalability:
    """Test chunker behavior under various load conditions."""

    @pytest.fixture
    def governor(self):
        """Create chunk governor with default settings."""
        # Create mock capabilities with typical context window
        mock_cap = EmbeddingModelCapabilities(
            model_name="test-model",
            embedding_dimensions=768,
            context_window=8192,
            max_batch_size=100,
        )
        return ChunkGovernor(capabilities=(mock_cap,))

    @pytest.fixture
    def selector(self, governor):
        """Create chunker selector."""
        return ChunkerSelector(governor)

    @pytest.mark.benchmark
    def test_chunking_consistency_across_sizes(self, selector):
        """Verify chunking quality doesn't degrade with file size."""
        file_sizes = [100, 500, 1000, 2000, 5000]

        for size in file_sizes:
            content = generate_python_file(size)
            file_path = Path(f"test_{size}.py")

            discovered_file = DiscoveredFile(path=file_path)
            chunker = selector.select_for_file(discovered_file)
            chunks = chunker.chunk(content, file_path=file_path)

            # Quality checks
            assert len(chunks) > 0, f"No chunks for {size} line file"
            assert all(chunk.content.strip() for chunk in chunks), (
                f"Empty chunks in {size} line file"
            )
            assert all(chunk.metadata for chunk in chunks), f"Missing metadata in {size} line file"

    @pytest.mark.benchmark
    def test_concurrent_chunking_safety(self, selector):
        """Verify concurrent chunking operations are safe."""
        import concurrent.futures

        def chunk_file(file_id: int):
            content = generate_python_file(300)
            file_path = Path(f"concurrent_{file_id}.py")
            discovered_file = DiscoveredFile(path=file_path)
            chunker = selector.select_for_file(discovered_file)
            return chunker.chunk(content, file_path=file_path)

        # Process multiple files concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(chunk_file, i) for i in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Verify all completed successfully
        assert len(results) == 10
        assert all(len(chunks) > 0 for chunks in results)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--benchmark-only"])
