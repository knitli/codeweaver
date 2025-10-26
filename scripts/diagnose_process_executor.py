#!/usr/bin/env python3
"""Diagnostic script to debug ProcessPoolExecutor behavior with chunking.

SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
"""

import sys
import traceback
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def simple_worker(x: int) -> int:
    """Simple test worker to verify ProcessPoolExecutor works."""
    return x * 2


def chunking_worker_verbose(file, governor):
    """Worker with verbose error reporting."""
    import sys
    import traceback
    from pathlib import Path

    # Add src to path in worker process
    worker_src = Path(__file__).parent.parent / "src"
    if str(worker_src) not in sys.path:
        sys.path.insert(0, str(worker_src))

    try:
        from codeweaver.engine.chunker.selector import ChunkerSelector

        print(f"[Worker] Processing {file.path}", file=sys.stderr, flush=True)

        # Create selector
        selector = ChunkerSelector(governor)
        print(f"[Worker] Created selector", file=sys.stderr, flush=True)

        # Select chunker
        chunker = selector.select_for_file(file)
        print(f"[Worker] Selected chunker: {type(chunker).__name__}", file=sys.stderr, flush=True)

        # Read content
        content = file.path.read_text(encoding="utf-8", errors="ignore")
        print(f"[Worker] Read {len(content)} chars", file=sys.stderr, flush=True)

        # Chunk
        chunks = chunker.chunk(content, file=file)
        print(f"[Worker] Generated {len(chunks)} chunks", file=sys.stderr, flush=True)

        return (file.path, chunks)

    except Exception as e:
        print(f"[Worker] ERROR: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        return (file.path, None)


def main():
    """Run ProcessPoolExecutor diagnostics."""
    print("=" * 80)
    print("ProcessPoolExecutor Execution Diagnostics")
    print("=" * 80)
    print()

    # Test 1: Simple worker
    print("Test 1: Simple Worker (baseline)")
    print("-" * 40)
    try:
        with ProcessPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(simple_worker, i) for i in range(5)]
            results = [f.result() for f in as_completed(futures)]
        print(f"✅ ProcessPoolExecutor works: {sorted(results)}")
    except Exception as e:
        print(f"❌ ProcessPoolExecutor failed: {e}")
        traceback.print_exc()
        return 1

    print()

    # Test 2: Chunking worker with ProcessPoolExecutor
    print("Test 2: Chunking Worker with ProcessPoolExecutor")
    print("-" * 40)
    try:
        from codeweaver.core.discovery import DiscoveredFile
        from codeweaver.engine.chunker.base import ChunkGovernor
        from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities

        # Create test file
        test_file = Path("tests/fixtures/sample.py")
        if not test_file.exists():
            print("❌ Test file not found")
            return 1

        discovered = DiscoveredFile.from_path(test_file)
        if not discovered:
            print("❌ Could not create DiscoveredFile")
            return 1

        capabilities = EmbeddingModelCapabilities(
            context_window=8192,
            embedding_dimensions=1536,
        )
        governor = ChunkGovernor(capabilities=(capabilities,))

        print(f"Created governor: {governor}")
        print(f"Discovered file: {discovered.path}")
        print()

        print("Submitting to ProcessPoolExecutor...")
        with ProcessPoolExecutor(max_workers=1) as executor:
            future = executor.submit(chunking_worker_verbose, discovered, governor)
            print("Future submitted, waiting for result...")

            try:
                result = future.result(timeout=10)
                file_path, chunks = result

                if chunks is None:
                    print(f"❌ Worker returned None chunks (error occurred)")
                else:
                    print(f"✅ ProcessPoolExecutor chunking works: {len(chunks)} chunks")
            except Exception as e:
                print(f"❌ Future.result() failed: {type(e).__name__}: {e}")
                traceback.print_exc()

    except Exception as e:
        print(f"❌ Setup failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        return 1

    print()

    # Test 3: ThreadPoolExecutor for comparison
    print("Test 3: Chunking Worker with ThreadPoolExecutor (comparison)")
    print("-" * 40)
    try:
        print("Submitting to ThreadPoolExecutor...")
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(chunking_worker_verbose, discovered, governor)
            print("Future submitted, waiting for result...")

            result = future.result(timeout=10)
            file_path, chunks = result

            if chunks is None:
                print(f"❌ Worker returned None chunks (error occurred)")
            else:
                print(f"✅ ThreadPoolExecutor chunking works: {len(chunks)} chunks")

    except Exception as e:
        print(f"❌ ThreadPoolExecutor test failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        return 1

    print()

    # Test 4: Test the actual implementation
    print("Test 4: Actual Implementation (_chunk_single_file)")
    print("-" * 40)
    try:
        from codeweaver.engine.chunker.parallel import _chunk_single_file

        print("Testing with ProcessPoolExecutor...")
        with ProcessPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_chunk_single_file, discovered, governor)

            try:
                result = future.result(timeout=10)
                file_path, chunks = result

                if chunks is None:
                    print(f"❌ _chunk_single_file returned None (error in worker)")
                else:
                    print(f"✅ _chunk_single_file with ProcessPoolExecutor works: {len(chunks)} chunks")
            except Exception as e:
                print(f"❌ Future.result() failed: {type(e).__name__}: {e}")
                traceback.print_exc()

    except Exception as e:
        print(f"❌ Implementation test failed: {type(e).__name__}: {e}")
        traceback.print_exc()
        return 1

    print()
    print("=" * 80)
    print("Diagnosis Complete")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
