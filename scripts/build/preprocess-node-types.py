#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Preprocess node-types JSON files and cache the parsed grammar data.

This script loads all tree-sitter node-types.json files, parses them into
CodeWeaver's internal Thing/Category representation, and serializes the
result to a pickle cache. This cache is loaded at runtime for fast startup.
"""

from __future__ import annotations

import pickle
import sys
from pathlib import Path


def main() -> int:
    """Preprocess node types and generate cache file."""
    # Add src to path so we can import codeweaver
    repo_root = Path(__file__).parent.parent.parent
    src_path = repo_root / "src"
    if src_path not in sys.path:
        sys.path.insert(0, str(src_path))

    from codeweaver.semantic.node_type_parser import NodeTypeParser

    print("Preprocessing node-types JSON files...")

    # Create parser and process all languages (disable cache since we're building it)
    parser = NodeTypeParser(use_cache=False)
    all_things = parser.parse_all_nodes()

    print(f"  Parsed {len(all_things)} Things/Categories across all languages")

    # Get the cache from the parser's registration cache
    # Note: We only cache the registration_cache, not all_things,
    # since all_things can be reconstructed from the cache at runtime
    cache_data = {
        "registration_cache": parser.registration_cache,
    }

    # Write cache file
    cache_file = repo_root / "src" / "codeweaver" / "data" / "node_types_cache.pkl"
    print(f"Writing cache to {cache_file}...")

    with cache_file.open("wb") as f:
        pickle.dump(cache_data, f, protocol=pickle.HIGHEST_PROTOCOL)

    cache_size = cache_file.stat().st_size
    print(f"✓ Generated node_types cache: {cache_file}")
    print(f"  Size: {cache_size:,} bytes ({cache_size / 1024:.1f} KB)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
