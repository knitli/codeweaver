#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Diagnostic script to capture the full traceback of pydantic warnings."""

import sys
import traceback
import warnings


def warning_with_traceback(
    message: object,
    category: type[Warning],
    filename: str,
    lineno: int,
    file: object = None,
    line: str | None = None,
) -> None:
    """Print warning with full stack trace."""
    log = sys.stderr
    traceback.print_stack(file=log)
    _ = log.write(warnings.formatwarning(message, category, filename, lineno, line))  # type: ignore


warnings.showwarning = warning_with_traceback

# Convert only UnsupportedFieldAttributeWarning to errors to get traceback
warnings.filterwarnings("error", category=Warning, message=".*default_factory.*")

# Now import and test your application
try:
    import codeweaver.config.types  # noqa: F401

    print("✓ Successfully imported config types")
except Warning as w:
    if "UnsupportedFieldAttributeWarning" not in str(type(w)):
        raise
    print("\n✗ Found the problematic warning!")
    traceback.print_exc()
