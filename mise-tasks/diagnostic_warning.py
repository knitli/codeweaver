#!/usr/bin/env -S uv run -s
# ///script
# requires-python = ">=3.10"
# dependencies = ["rich"]
# ///
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Diagnostic script to capture the full traceback of pydantic warnings."""

import sys
import traceback
import warnings

from rich.console import Console
from rich.traceback import install


console = Console()


install(console=console, width=120, max_frames=100, show_locals=True)
console.begin_capture()


def warning_with_traceback(
    message: object,
    category: type[Warning],
    filename: str,
    lineno: int,
    file: object = None,
    line: str | None = None,
) -> None:
    """Print warning with full stack trace."""
    console.print("file=", file)
    console.print("line=", line)
    console.print("filename=", filename)
    console.print("lineno=", lineno)
    traceback.print_stack(file=sys.stdout)


warnings.showwarning = warning_with_traceback

# Convert only UnsupportedFieldAttributeWarning to errors to get traceback
warnings.filterwarnings("error", category=Warning, message=".*default_factory.*")

# Now import and test your application
try:
    from codeweaver.cli import __main__ as main

    main.main()
except Warning as w:
    if "UnsupportedFieldAttributeWarning" not in str(type(w)):
        raise
    print("\n✗ Found the problematic warning!")
    traceback.print_exc()
console.end_capture()
output = console.export_text()
console.print(output)
