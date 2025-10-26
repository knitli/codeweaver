#!/usr/bin/env python3
"""Diagnostic script to identify pickling issues with parallel processing objects.

SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
"""

import pickle
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_pickle(obj, name: str) -> tuple[bool, str]:
    """Test if an object is picklable.

    Args:
        obj: Object to test
        name: Name for reporting

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        pickled = pickle.dumps(obj)
        unpickled = pickle.loads(pickled)
        return True, f"✅ {name}: Picklable ({len(pickled)} bytes)"
    except Exception as e:
        return False, f"❌ {name}: NOT picklable - {type(e).__name__}: {e}"


def main():
    """Run pickling diagnostics."""
    print("=" * 80)
    print("ProcessPoolExecutor Pickling Diagnostics")
    print("=" * 80)
    print()

    results = []

    # Test 1: DiscoveredFile
    print("Test 1: DiscoveredFile")
    print("-" * 40)
    try:
        from codeweaver.core.discovery import DiscoveredFile

        # Create a real discovered file
        test_file = Path("tests/fixtures/sample.py")
        if test_file.exists():
            discovered = DiscoveredFile.from_path(test_file)
            if discovered:
                success, msg = test_pickle(discovered, "DiscoveredFile instance")
                results.append((success, msg))
                print(msg)

                # Test individual attributes
                for attr in ['path', 'ext_kind', 'file_hash', 'source_id']:
                    value = getattr(discovered, attr)
                    success, msg = test_pickle(value, f"  - {attr}")
                    results.append((success, msg))
                    print(msg)
            else:
                print("⚠️  Could not create DiscoveredFile from sample.py")
        else:
            print("⚠️  Sample file not found")
    except Exception as e:
        msg = f"❌ DiscoveredFile: Import/creation failed - {e}"
        results.append((False, msg))
        print(msg)

    print()

    # Test 2: ChunkGovernor
    print("Test 2: ChunkGovernor")
    print("-" * 40)
    try:
        from codeweaver.engine.chunker.base import ChunkGovernor
        from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
        from codeweaver.config.chunker import ChunkerSettings

        # Create a governor
        capabilities = EmbeddingModelCapabilities(
            context_window=8192,
            embedding_dimensions=1536,
        )
        settings = ChunkerSettings()
        governor = ChunkGovernor(capabilities=(capabilities,), settings=settings)

        success, msg = test_pickle(governor, "ChunkGovernor instance")
        results.append((success, msg))
        print(msg)

        # Test individual components
        success, msg = test_pickle(capabilities, "  - EmbeddingModelCapabilities")
        results.append((success, msg))
        print(msg)

        success, msg = test_pickle(settings, "  - ChunkerSettings")
        results.append((success, msg))
        print(msg)

    except Exception as e:
        msg = f"❌ ChunkGovernor: Import/creation failed - {e}"
        results.append((False, msg))
        print(msg)

    print()

    # Test 3: ChunkerSelector
    print("Test 3: ChunkerSelector")
    print("-" * 40)
    try:
        from codeweaver.engine.chunker.selector import ChunkerSelector
        from codeweaver.engine.chunker.base import ChunkGovernor
        from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities

        capabilities = EmbeddingModelCapabilities(
            context_window=8192,
            embedding_dimensions=1536,
        )
        governor = ChunkGovernor(capabilities=(capabilities,))
        selector = ChunkerSelector(governor)

        success, msg = test_pickle(selector, "ChunkerSelector instance")
        results.append((success, msg))
        print(msg)

    except Exception as e:
        msg = f"❌ ChunkerSelector: Import/creation failed - {e}"
        results.append((False, msg))
        print(msg)

    print()

    # Test 4: Worker function
    print("Test 4: Worker Function")
    print("-" * 40)
    try:
        from codeweaver.engine.chunker.parallel import _chunk_single_file

        success, msg = test_pickle(_chunk_single_file, "_chunk_single_file function")
        results.append((success, msg))
        print(msg)

    except Exception as e:
        msg = f"❌ _chunk_single_file: Import failed - {e}"
        results.append((False, msg))
        print(msg)

    print()

    # Test 5: Full worker call simulation
    print("Test 5: Full Worker Call Simulation")
    print("-" * 40)
    try:
        from codeweaver.core.discovery import DiscoveredFile
        from codeweaver.engine.chunker.base import ChunkGovernor
        from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
        from codeweaver.engine.chunker.parallel import _chunk_single_file

        test_file = Path("tests/fixtures/sample.py")
        if test_file.exists():
            discovered = DiscoveredFile.from_path(test_file)
            capabilities = EmbeddingModelCapabilities(
                context_window=8192,
                embedding_dimensions=1536,
            )
            governor = ChunkGovernor(capabilities=(capabilities,))

            if discovered:
                # Test pickling the complete arguments
                args = (discovered, governor)
                success, msg = test_pickle(args, "Worker args tuple")
                results.append((success, msg))
                print(msg)

                # Try to pickle a lambda that calls the worker
                try:
                    import functools
                    worker_call = functools.partial(_chunk_single_file, discovered, governor)
                    success, msg = test_pickle(worker_call, "Partial worker call")
                    results.append((success, msg))
                    print(msg)
                except Exception as e:
                    msg = f"❌ Partial worker call: {type(e).__name__}: {e}"
                    results.append((False, msg))
                    print(msg)
    except Exception as e:
        msg = f"❌ Worker simulation: {type(e).__name__}: {e}"
        results.append((False, msg))
        print(msg)

    print()
    print("=" * 80)
    print("Summary")
    print("=" * 80)

    total = len(results)
    passed = sum(1 for success, _ in results if success)
    failed = total - passed

    print(f"Total tests: {total}")
    print(f"Passed: {passed} ({100*passed//total if total else 0}%)")
    print(f"Failed: {failed} ({100*failed//total if total else 0}%)")
    print()

    if failed > 0:
        print("Failed tests:")
        for success, msg in results:
            if not success:
                print(f"  {msg}")
        print()
        print("Recommendation: Objects that cannot be pickled need to be:")
        print("  1. Refactored to be pickle-compatible, OR")
        print("  2. Serialized using 'dill' library instead of 'pickle', OR")
        print("  3. Passed as simpler data structures and reconstructed in worker")
        return 1
    else:
        print("✅ All objects are picklable!")
        print("The ProcessPoolExecutor issue may be elsewhere.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
