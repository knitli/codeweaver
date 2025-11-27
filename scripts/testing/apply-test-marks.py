#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# sourcery skip: avoid-single-character-names-variables, require-return-annotation

"""
Script to apply pytest marks to test files based on their location and patterns.
"""

import re
import sys

from pathlib import Path


# Define test mark mappings based on patterns
MARK_PATTERNS = {
    # Unit tests
    "tests/unit/": ["@pytest.mark.unit"],
    "test_config": ["@pytest.mark.config"],
    "test_telemetry": ["@pytest.mark.telemetry"],
    "test_docarray": ["@pytest.mark.embeddings"],
    "test_protocol": ["@pytest.mark.mcp"],
    "test_factory": ["@pytest.mark.config"],
    # Integration tests
    "tests/integration/": ["@pytest.mark.integration"],
    "test_benchmark": ["@pytest.mark.benchmark", "@pytest.mark.performance"],
    "test_middleware": ["@pytest.mark.mcp", "@pytest.mark.services"],
    "test_service_integration": ["@pytest.mark.services"],
    "test_server": ["@pytest.mark.mcp"],
    "test_clean_server": ["@pytest.mark.mcp"],
    # Validation tests
    "tests/validation/": ["@pytest.mark.validation"],
    "test_pattern_consistency": ["@pytest.mark.validation"],
    "test_services_integration": ["@pytest.mark.services"],
    # Content-based patterns
    "mock": ["@pytest.mark.mock_only"],
    "async": ["@pytest.mark.async_test"],
    "benchmark": ["@pytest.mark.benchmark", "@pytest.mark.performance"],
    "network": ["@pytest.mark.network"],
    "voyageai": ["@pytest.mark.voyageai", "@pytest.mark.external_api"],
    "qdrant": ["@pytest.mark.qdrant", "@pytest.mark.external_api"],
}


def should_add_marks(file_path: Path, content: str) -> list[str]:
    """Determine which marks should be added to a test file."""
    marks = set()

    # Path-based marks
    raw_path = str(file_path)
    for pattern, pattern_marks in MARK_PATTERNS.items():
        if pattern in raw_path:
            marks.update(pattern_marks)

    # Content-based marks
    content_lower = content.lower()

    # Check for async tests
    if "@pytest.mark.asyncio" in content or "async def test_" in content:
        marks.add("@pytest.mark.async_test")

    # Check for mock usage
    if "from unittest.mock import" in content or "MagicMock" in content or "AsyncMock" in content:
        marks.add("@pytest.mark.mock_only")

    # Check for slow tests
    if "benchmark" in content_lower or "performance" in content_lower:
        marks.update(["@pytest.mark.benchmark", "@pytest.mark.performance"])
        if "time.sleep" in content or "asyncio.sleep" in content:
            marks.add("@pytest.mark.slow")

    # Check for external dependencies
    if "voyageai" in content_lower:
        marks.update(["@pytest.mark.voyageai", "@pytest.mark.external_api"])

    if "qdrant" in content_lower:
        marks.update(["@pytest.mark.qdrant", "@pytest.mark.external_api"])

    # Check for parametrized tests
    if "@pytest.mark.parametrize" in content:
        marks.add("@pytest.mark.parametrize")

    return sorted(marks)


def find_test_classes(content: str) -> list[tuple[str, int]]:
    """Find all test classes and their line numbers."""
    lines = content.split("\n")

    return [
        (line.strip(), i)
        for i, line in enumerate(lines, 1)
        if re.match(r"^class Test\w+:", line.strip())
    ]


def add_marks_to_classes(content: str, marks: list[str]) -> str:
    """Add marks to test classes that don't already have them."""
    if not marks:
        return content

    lines = content.split("\n")
    new_lines = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check if this is a test class
        if re.match(r"^class Test\w+:", line.strip()):
            # Check if marks are already present above this class
            i - len(marks)
            existing_marks = []

            # Look backward for existing marks
            j = i - 1
            while j >= 0 and (
                lines[j].strip().startswith("@pytest.mark.") or lines[j].strip() == ""
            ):
                if lines[j].strip().startswith("@pytest.mark."):
                    existing_marks.append(lines[j].strip())
                j -= 1

            # Only add marks if none of our target marks are already present
            needs_marks = any(mark not in existing_marks for mark in marks)

            if needs_marks:
                # Add marks before the class
                new_lines.extend(mark for mark in marks if mark not in existing_marks)
        new_lines.append(line)
        i += 1

    return "\n".join(new_lines)


def process_test_file(file_path: Path) -> None:
    """Process a single test file to add appropriate marks."""
    print(f"Processing {file_path}")

    try:
        with file_path.open("r", encoding="utf-8") as f:
            content = f.read()

        # Skip files that already have extensive marking
        if content.count("@pytest.mark.") > 5:
            print(f"  Skipping {file_path} - already has many marks")
            return

        marks = should_add_marks(file_path, content)
        if not marks:
            print(f"  No marks needed for {file_path}")
            return

        # Add marks to classes
        new_content = add_marks_to_classes(content, marks)

        if new_content != content:
            with file_path.open("w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"  Added marks to {file_path}: {', '.join(marks)}")
        else:
            print(f"  No changes needed for {file_path}")

    except Exception as e:
        print(f"  Error processing {file_path}: {e}")


def main() -> None:
    """Main function to process all test files."""
    test_files = [Path(f) for f in sys.argv[1:]] if len(sys.argv) > 1 else []
    test_dir = Path("tests")

    if not test_dir.exists():
        print("No tests directory found")
        return

    # Find all Python test files
    if not (test_files := test_files or list(test_dir.rglob("*.py"))):
        print("No test files found")
        return

    # Filter out __pycache__ and other non-test files
    test_files = [
        f
        for f in test_files
        if test_files is not None and "__pycache__" not in str(f) and f.name != "__init__.py"
    ]

    print(f"Found {len(test_files)} test files")

    for test_file in sorted(test_files):
        process_test_file(test_file)

    print("\nDone! You can now run tests with specific marks:")
    print("  pytest -m unit                    # Run only unit tests")
    print("  pytest -m integration             # Run only integration tests")
    print("  pytest -m 'not slow'              # Skip slow tests")
    print("  pytest -m 'benchmark and not external_api'  # Benchmarks without external APIs")
    print("  pytest -m config                  # Configuration tests only")


if __name__ == "__main__":
    main()
