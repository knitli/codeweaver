#!/usr/bin/env -S uv run -s
# ///script
# requires-python = ">=3.11"
# dependencies = ["rich"]
# ///
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Benchmark language family detection performance.

Compares sync vs async detection and demonstrates non-blocking behavior.
"""

from __future__ import annotations

import asyncio
import sys
import time

from pathlib import Path

from rich.console import Console
from rich.table import Table


# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from codeweaver.services.chunker.delimiters import LanguageFamily, detect_language_family


console = Console()

# Sample code snippets for testing
SAMPLES = {
    "python": '''
def fibonacci(n: int) -> int:
    """Calculate nth Fibonacci number."""
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

@decorator
class MyClass:
    def method(self):
        return "result"
''',
    "javascript": """
function fibonacci(n) {
    // Calculate nth Fibonacci number
    if (n <= 1) {
        return n;
    }
    return fibonacci(n - 1) + fibonacci(n - 2);
}

class MyClass {
    method() {
        return "result";
    }
}
""",
    "rust": """
/// Calculate nth Fibonacci number
fn fibonacci(n: u32) -> u32 {
    if n <= 1 {
        return n;
    }
    fibonacci(n - 1) + fibonacci(n - 2)
}

struct MyStruct {
    field: i32,
}

impl MyStruct {
    fn method(&self) -> &str {
        "result"
    }
}
""",
    "haskell": """
-- Calculate nth Fibonacci number
fibonacci :: Int -> Int
fibonacci n
    | n <= 1 = n
    | otherwise = fibonacci (n - 1) + fibonacci (n - 2)

data MyType = MyType { field :: Int }

myFunction :: String
myFunction = "result"
""",
    "lisp": """
(defun fibonacci (n)
  "Calculate nth Fibonacci number"
  (if (<= n 1)
      n
      (+ (fibonacci (- n 1))
         (fibonacci (- n 2)))))

(defclass my-class ()
  ((field :initarg :field)))

(defmethod my-method ((obj my-class))
  "result")
""",
}


async def benchmark_async_detection() -> dict[str, tuple[LanguageFamily, float]]:
    """Benchmark asynchronous detection."""

    async def detect_one(name: str, code: str) -> tuple[str, LanguageFamily, float]:
        start = time.perf_counter()
        family = await detect_language_family(code)
        elapsed = time.perf_counter() - start
        return name, family, elapsed

    # Run all detections concurrently
    tasks = [detect_one(name, code) for name, code in SAMPLES.items()]
    task_results = await asyncio.gather(*tasks)

    return {name: (family, elapsed) for name, family, elapsed in task_results}


async def benchmark_parallel() -> tuple[dict[str, tuple[LanguageFamily, float]], float]:
    """Benchmark parallel async detection (shows true concurrency benefit).

    Returns:
        A tuple containing:
          - results: dict mapping sample name to (detected LanguageFamily, elapsed seconds)
          - total_elapsed: total elapsed seconds for the parallel benchmark
    """
    start_total = time.perf_counter()
    results = await benchmark_async_detection()
    total_elapsed = time.perf_counter() - start_total

    return results, total_elapsed


def main() -> None:
    """Run benchmarks and display results."""
    console.print("\n[bold cyan]Language Family Detection Benchmark[/bold cyan]\n")

    # Async benchmark (sequential)
    console.print("[yellow]Running asynchronous detection (sequential)...[/yellow]")
    async_results = asyncio.run(benchmark_async_detection())
    async_total = sum(elapsed for _, elapsed in async_results.values())

    # Async benchmark (parallel)
    console.print("[yellow]Running asynchronous detection (parallel)...[/yellow]")
    _parallel_results, parallel_total = asyncio.run(benchmark_parallel())

    # Create comparison table
    table = Table(title="Detection Performance Comparison")
    table.add_column("Language", style="cyan")
    table.add_column("Expected Family", style="yellow")
    table.add_column("Detected Family", style="green")
    table.add_column("Sync Time (ms)", justify="right", style="magenta")
    table.add_column("Async Time (ms)", justify="right", style="blue")
    table.add_column("Match", style="bold")

    expected_families = {
        "python": LanguageFamily.PYTHON_STYLE,
        "javascript": LanguageFamily.C_STYLE,
        "rust": LanguageFamily.C_STYLE,
        "haskell": LanguageFamily.FUNCTIONAL_STYLE,
        "lisp": LanguageFamily.LISP_STYLE,
    }

    for name in SAMPLES:
        expected = expected_families[name]
        async_family, async_time = async_results[name]

        match = "✅" if async_family == expected else "❌"

        table.add_row(name, expected.value, async_family.value, f"{async_time * 1000:.3f}", match)

    console.print(table)

    # Summary
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Async total time:    {async_total * 1000:.3f} ms")
    console.print(f"  Parallel total time: {parallel_total * 1000:.3f} ms")
    # Validate correctness
    all_correct = all(async_results[name][0] == expected_families[name] for name in SAMPLES)

    if all_correct:
        console.print("[bold green]✅ All detections correct![/bold green]")
    else:
        console.print("[bold red]❌ Some detections incorrect![/bold red]")


if __name__ == "__main__":
    main()
