# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Sample Python file for testing semantic chunking."""

def greet(name: str) -> str:
    """Greet someone by name."""
    return f"Hello, {name}!"

class Calculator:
    """A simple calculator class."""

    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    def multiply(self, a: int, b: int) -> int:
        """Multiply two numbers."""
        return a * b

if __name__ == "__main__":
    calc = Calculator()
    result = calc.add(2, 3)
    print(greet("World"))
    print(f"2 + 3 = {result}")
