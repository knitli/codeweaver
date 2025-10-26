# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Test fixture: Indivisible huge string literal.

Used to test text splitter fallback when semantic and delimiter
chunking cannot split the content (e.g., long string literal).

The string is generated programmatically to avoid storing
massive literals in version control.
"""


def generate_huge_string():
    """Generate a huge indivisible string for testing."""
    # Generate ~30KB of text (approximately 7500+ tokens)
    base_text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
    return base_text * 500


# This will be a very large string literal that cannot be split semantically
HUGE_TEXT = f'''"""
{generate_huge_string()}
"""'''
