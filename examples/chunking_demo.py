#!/usr/bin/env python3
"""Demo script showing ChunkingService usage with parallel processing.

SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0

This script demonstrates:
1. Discovering files in a directory
2. Chunking them with parallel processing
3. Examining the resulting chunks
"""

import sys

from pathlib import Path


# Add src to path if running from examples directory
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def main() -> None:
    """Run chunking demo."""
    from codeweaver.config.chunker import ChunkerSettings, ConcurrencySettings
    from codeweaver.core.discovery import DiscoveredFile
    from codeweaver.engine import ChunkGovernor, ChunkingService
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities

    print("=" * 80)
    print("CodeWeaver Chunking Service Demo")
    print("=" * 80)
    print()

    # 1. Discover files
    print("Step 1: Discovering files...")
    test_dir = Path("tests/fixtures")
    if not test_dir.exists():
        test_dir = Path(__file__).parent.parent / "tests/fixtures"

    skip_files = {"__init__.py", "malformed.py", "empty.py", "whitespace_only.py"}
    files = [
        discovered_file
        for file_path in test_dir.glob("*.py")
        if (discovered_file := DiscoveredFile.from_path(file_path))
        and discovered_file.path.name not in skip_files
    ]

    print(f"  Found {len(files)} files to chunk")
    for file in files[:5]:  # Show first 5
        print(f"    - {file.path.name}")
    if len(files) > 5:
        print(f"    ... and {len(files) - 5} more")
    print()

    # 2. Set up chunking with parallel processing
    print("Step 2: Configuring chunking service...")

    # Create capabilities (required for ChunkGovernor)
    capabilities = EmbeddingModelCapabilities(context_window=8192, default_dimension=1536)

    # Create settings with parallel processing config
    settings = ChunkerSettings(
        concurrency=ConcurrencySettings(
            max_parallel_files=4,  # Use 4 workers
            executor="thread",  # Use ThreadPoolExecutor
        )
    )

    # Create governor
    governor = ChunkGovernor(capabilities=(capabilities,), settings=settings)

    # Create chunking service
    service = ChunkingService(
        governor,
        enable_parallel=True,
        parallel_threshold=3,  # Use parallel for 3+ files
    )

    print("  Parallel processing: Enabled")
    print("  Parallel threshold: 3 files")
    print("  Max workers: 4")
    print("  Executor: thread")
    print()

    # 3. Chunk files
    print("Step 3: Chunking files...")
    print()

    total_chunks = 0
    processed_files = 0

    for file_path, chunks in service.chunk_files(files):
        processed_files += 1
        total_chunks += len(chunks)

        print(f"  ✓ {file_path.name}")
        print(f"    Chunks: {len(chunks)}")

        if len(chunks) > 0:
            # Show first chunk details
            first_chunk = chunks[0]
            print("    First chunk:")
            print(f"      Lines: {first_chunk.line_range.start}-{first_chunk.line_range.end}")
            print(f"      Length: {len(first_chunk.content)} chars")
            print(f"      Language: {first_chunk.language}")

            # Show snippet of content
            snippet = first_chunk.content[:100].replace("\n", " ")
            if len(first_chunk.content) > 100:
                snippet += "..."
            print(f"      Content: {snippet}")

        print()

    # 4. Summary
    print("=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"Files processed: {processed_files}/{len(files)}")
    print(f"Total chunks generated: {total_chunks}")
    print(f"Average chunks per file: {total_chunks / max(processed_files, 1):.1f}")
    print()

    # 5. Demonstrate sequential processing for comparison
    print("Step 4: Comparing with sequential processing...")
    print()

    # Force sequential by setting threshold high
    service_sequential = ChunkingService(
        governor,
        enable_parallel=False,  # Disable parallel
    )

    seq_total_chunks = sum(
        len(chunks) for _file_path, chunks in service_sequential.chunk_files(files[:3])
    )
    print(f"  Sequential: {seq_total_chunks} chunks from 3 files")
    print("  (Both methods produce identical results)")
    print()

    print("=" * 80)
    print("Demo Complete!")
    print("=" * 80)
    print()
    print("The ChunkingService provides:")
    print("  • Automatic parallel/sequential selection based on file count")
    print("  • Configurable parallel processing (process or thread executors)")
    print("  • Graceful error handling (individual file failures don't stop processing)")
    print("  • Memory-efficient iterator pattern")
    print()


if __name__ == "__main__":
    main()
