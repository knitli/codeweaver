#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Generate JSON schema for CodeWeaver settings.

This script generates the JSON schema file for CodeWeaver settings validation.
It should be run during the build process when the schema version changes or
when the schema file doesn't exist.
"""

from __future__ import annotations

import sys

from pathlib import Path


def main() -> int:
    """Generate the JSON schema file for CodeWeaver settings."""
    # Add src to path so we can import codeweaver
    repo_root = Path(__file__).parent.parent.parent
    src_path = repo_root / "src"
    if src_path not in sys.path:
        sys.path.insert(0, str(src_path))

    from codeweaver.config.settings import get_settings
    # Get the schema version from CodeWeaverSettings
    settings = get_settings()
    version = settings.__version__
    schema_dir = repo_root / "schema" / f"v{version}"
    schema_file = schema_dir / "codeweaver.schema.json"

    # Check if schema file already exists
    if schema_file.exists():
        print(f"Schema file already exists: {schema_file}")
        print("Skipping schema generation. Delete the file to regenerate.")
        return 0

    # Generate schema
    print(f"Generating schema for version {version}...")
    schema_dir.mkdir(parents=True, exist_ok=True)

    schema_bytes = type(settings).json_schema()
    bytes_written = schema_file.write_bytes(schema_bytes)

    print(f"✓ Generated schema file: {schema_file}")
    print(f"  Size: {bytes_written:,} bytes")

    return 0


if __name__ == "__main__":
    sys.exit(main())
