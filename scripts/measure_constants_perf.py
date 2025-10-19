#!/usr/bin/env python3
"""Measure performance of _constants module import and usage."""

import sys
import time

from pathlib import Path


# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def measure_import_time() -> float:
    """Measure time to import _constants module."""
    start = time.perf_counter()
    from codeweaver.semantic import _constants  # noqa: F401

    return time.perf_counter() - start


def measure_get_checks_performance() -> dict[str, float]:
    """Measure get_checks performance for different scenarios."""
    from codeweaver.language import SemanticSearchLanguage
    from codeweaver.semantic._constants import get_checks

    results = {}

    # Test cases
    test_cases = [
        ("function", SemanticSearchLanguage.PYTHON),
        ("class_declaration", SemanticSearchLanguage.TYPESCRIPT),
        ("method_signature", SemanticSearchLanguage.RUST),
        ("import_statement", SemanticSearchLanguage.GO),
    ]

    for thing_name, language in test_cases:
        start = time.perf_counter()
        # Consume the iterator to measure full execution
        list(get_checks(thing_name, language))
        duration = time.perf_counter() - start
        results[f"{thing_name}_{language.value}"] = duration

    return results


def main() -> None:
    """Run all performance measurements."""
    print("=" * 60)
    print("CodeWeaver _constants Performance Measurement")
    print("=" * 60)

    # Measure import time
    print("\n1. Import Time:")
    import_time = measure_import_time()
    print(f"   Module import: {import_time * 1000:.2f}ms")

    # Measure get_checks performance
    print("\n2. get_checks() Performance (single call):")
    checks_perf = measure_get_checks_performance()
    for test_case, duration in checks_perf.items():
        print(f"   {test_case}: {duration * 1_000_000:.2f}µs")

    # Measure repeated calls (cache benefit)
    print("\n3. Repeated calls (1000 iterations):")
    from codeweaver.language import SemanticSearchLanguage
    from codeweaver.semantic._constants import get_checks

    start = time.perf_counter()
    for _ in range(1000):
        list(get_checks("function", SemanticSearchLanguage.PYTHON))
    total = time.perf_counter() - start
    print(f"   Total: {total * 1000:.2f}ms")
    print(f"   Per call: {total / 1000 * 1_000_000:.2f}µs")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
