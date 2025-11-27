#!/usr/bin/env -S uv run -s

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# ///script
# python-version: ">=3.12"
# dependencies: ["packaging>=25.0"]
# ////script
"""A git driver to resolve version file conflicts by using the latest version (like in src/codeweaver/_version.py)."""

from __future__ import annotations

import contextlib
import re
import sys

from packaging.version import parse as parse_version
from packaging.version import Version
from pathlib import Path
from typing import NoReturn

VERSION_PATTERN = re.compile(r"""__version__(?P<annotation>: (Final\[str\]|str))? ?= ?["'](?P<major>\d{1,3})\.(?P<minor>\d{1,3})\.(?P<patch>\d{1,3})(?P<pre>(a|b|rc)\d+)?\+?(?P<commit>g[0-9a-f]+)?["']""")
        

def flatten_version(match: re.Match) -> str:
    """Flatten version components into a single version string."""
    major = match["major"]
    minor = match["minor"]
    patch = match["patch"]
    pre = match["pre"] or ""
    commit = match["commit"] or ""
    if pre and commit:
        return f"{major}.{minor}.{patch}{pre}+{commit}"
    elif pre:
        return f"{major}.{minor}.{patch}{pre}"
    elif commit:
        return f"{major}.{minor}.{patch}+{commit}"
    else:
        return f"{major}.{minor}.{patch}"

def extract_version(path: Path) -> Version | None:
    """Extract version string from the given file path."""
    with contextlib.suppress(FileNotFoundError):
        content = path.read_text()
        for line in content.splitlines():
            if "__version__" in line and (match := VERSION_PATTERN.search(line)):
                return parse_version(flatten_version(match))
    return None

def main(ours_path: str, theirs_path: str) -> NoReturn:
    """Resolve the version conflict by using the latest version."""
    ours = Path(ours_path)
    theirs = Path(theirs_path)
    if ours.exists() and theirs.exists() and (ours_version := extract_version(ours)) and (theirs_version := extract_version(theirs)):
        src = theirs if theirs_version > ours_version else ours
    else:
        src = ours or theirs
    other = theirs if src == ours else ours
    _ = Path(other).write_bytes(Path(src).read_bytes())
    sys.exit(0)


if __name__ == "__main__":
    _, ours_path, theirs_path = sys.argv[1:4]
    main(ours_path, theirs_path)

