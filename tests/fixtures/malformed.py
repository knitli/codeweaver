# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Intentionally malformed Python file for testing parse error handling.

This file contains syntax errors that should trigger ParseError when
the semantic chunker attempts to parse it.
"""

# Missing closing parenthesis
def broken_function(a, b:
    return a + b

# Missing colon
class BrokenClass
    def method(self):
        pass

# Incomplete statement
if True
    print("This won't parse")

# Mismatched brackets
result = [1, 2, 3}

# Invalid indentation mixing tabs and spaces
def another_function():
	mixed_indent = "tabs"
        more_mixed = "spaces"
