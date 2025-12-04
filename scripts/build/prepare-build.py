#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Master build preparation script for CodeWeaver.

This script orchestrates all the build preparation steps in the correct order:
1. Generate supported languages list
2. Generate provider lists
3. Update node-types from tree-sitter grammars
4. Preprocess node-types into cached format
5. Generate JSON schema (if needed)
"""

from __future__ import annotations

import subprocess
import sys

from pathlib import Path


def run_script(script_path: Path, *args: str) -> int:
    """Run a script and return its exit code."""
    script_name = script_path.name
    print(f"\n{'=' * 70}")
    print(f"Running: {script_name}")
    print(f"{'=' * 70}")

    result = subprocess.run( # noqa: S603
        [sys.executable, str(script_path), *args],
        cwd=script_path.parent.parent.parent,
        check=False,
    )

    if result.returncode != 0:
        print(f"✗ {script_name} failed with exit code {result.returncode}")
        return result.returncode

    print(f"✓ {script_name} completed successfully")
    return 0


def main() -> int:
    """Run all build preparation steps."""
    repo_root = Path(__file__).parent.parent.parent
    scripts_build = repo_root / "scripts" / "build"
    scripts_lang = repo_root / "scripts" / "language-support"

    print("=" * 70)
    print("CodeWeaver Build Preparation")
    print("=" * 70)

    # Step 1: Generate supported languages
    exit_code = run_script(scripts_build / "generate-supported-languages.py")
    if exit_code != 0:
        return exit_code

    # Step 2: Generate provider lists
    exit_code = run_script(scripts_build / "generate-provider-lists.py")
    if exit_code != 0:
        return exit_code

    # Step 3: Update node-types from tree-sitter grammars
    exit_code = run_script(
        scripts_lang / "download-ts-grammars.py", "fetch", "--only-node-types"
    )
    # we don't exit if this fails
    # it's a flaky step prone to rate limiting issues and isn't critical

    # Step 4: Preprocess node-types into cache
    exit_code = run_script(scripts_build / "preprocess-node-types.py")
    if exit_code != 0:
        return exit_code

    # Step 5: Generate schema (if needed)
    exit_code = run_script(scripts_build / "generate-schema.py")
    if exit_code != 0:
        return exit_code

    print("\n" + "=" * 70)
    print("✓ Build preparation completed successfully!")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
