#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Context Reduction Measurement Script for CodeWeaver Alpha 6.

This script measures the "Exquisite Context" claim (60-80% context reduction) by:
1. Calculating the 'Naive' baseline (all source files for a given language/query).
2. Running real CodeWeaver searches (find_code).
3. Comparing the total tokens returned vs. the naive baseline.
"""

import asyncio
import logging
import os
import statistics
import sys

from collections.abc import Sequence
from pathlib import Path


# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from codeweaver.server.agent_api.search import IntentType, find_code


# Setup logging
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("measure-reduction")

QUERIES = [
    ("How is the Dependency Injection system implemented?", "python"),
    ("What are the core configuration settings?", "python"),
    ("How does the CLI doctor command work?", "python"),
    ("What are the backup embedding models used for failover?", "python"),
    ("Explain the hybrid search scoring pipeline.", "python"),
]


async def calculate_naive_baseline(project_path: Path, languages: Sequence[str]) -> int:
    """Calculate total tokens for all files of given languages in the repo."""
    total_chars = 0
    from codeweaver.core.file_extensions import CODE_FILES_EXTENSIONS

    # Get extensions for target languages
    target_exts = {
        pair.ext
        for pair in CODE_FILES_EXTENSIONS
        if str(pair.language).lower() in [l.lower() for l in languages]
    }

    for root, _, files in os.walk(project_path):
        if any(ignored in root for ignored in [".git", ".venv", "__pycache__", "dist", "build"]):
            continue
        for file in files:
            file_path = Path(root) / file
            # Check if file matches any target extension
            if any(str(file_path).endswith(str(ext)) for ext in target_exts):
                try:
                    total_chars += file_path.stat().st_size
                except OSError:
                    continue

    return total_chars // 4


async def measure_reduction():
    print("=" * 70)
    print("CodeWeaver Alpha 6: Context Reduction Benchmark")
    print("=" * 70)

    # Initialize DI
    from codeweaver.cli.dependencies import setup_cli_di

    project_path = Path(os.getcwd())
    config_file = project_path / "codeweaver.toml"
    setup_cli_di(config_file=config_file, project_path=project_path)

    print(f"Project: {project_path.name}")

    # 1. Baseline
    naive_baseline = await calculate_naive_baseline(project_path, ["python"])
    print(f"Naive Baseline (Total Python Tokens): {naive_baseline:,} tokens")

    if naive_baseline == 0:
        print("Error: Could not find any Python files to measure.")
        return

    # 2. Run Searches
    results = []

    for query_text, lang in QUERIES:
        print(f"\nQuery: '{query_text}'")

        # Execute search
        response = await find_code(
            query=query_text,
            intent=IntentType.UNDERSTAND,
            token_limit=30000,
            focus_languages=(lang,),
        )

        returned_tokens = getattr(response, "token_count", 0)

        # Calculate reduction
        reduction = 100 * (1 - (returned_tokens / naive_baseline))
        results.append(reduction)

        print(f"   Matches: {len(response.matches)}")
        print(f"   Tokens Returned: {returned_tokens:,}")
        print(f"   Reduction vs Naive: {reduction:.1f}%")

    # 3. Final Report
    if not results:
        print("No results collected.")
        return

    avg_reduction = statistics.mean(results)
    min_reduction = min(results)
    max_reduction = max(results)

    print("\n" + "=" * 70)
    print("Final Result")
    print("=" * 70)
    print(f"Average Context Reduction: {avg_reduction:.1f}%")
    print(f"Range: {min_reduction:.1f}% to {max_reduction:.1f}%")

    if avg_reduction >= 60:
        print("\nStatus: ✅ Claim Verified (>= 60% reduction)")
        if avg_reduction > 80:
            print("Note: CodeWeaver significantly outperformed the 80% upper bound.")
    else:
        print("\nStatus: ⚠️ Claim Not Met (< 60% reduction)")
    print("=" * 70)


if __name__ == "__main__":
    try:
        asyncio.run(measure_reduction())
    except Exception as e:
        print(f"\nError running benchmark: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
