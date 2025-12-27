#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Demonstration script for LazyImport functionality.

This script shows how the new LazyImport class solves the problems with
the old lazy_importer implementation, specifically:

1. No more awkward double-call syntax: lazy_importer("module")()
2. True lazy loading: imports deferred until actual use, not just attribute access
3. Clean global-level usage: can assign at module scope without triggering imports
"""

import sys

from pathlib import Path


# Add src to path for direct import
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root / "src"))

from codeweaver.core import lazy_import


def demo_basic_usage() -> None:
    """Demonstrate basic lazy import functionality."""
    print("=" * 70)
    print("DEMO 1: Basic Module Import")
    print("=" * 70)

    # Create lazy import
    os_lazy = lazy_import("os")
    print(f"✓ Created: {os_lazy}")
    print(f"  Is resolved: {os_lazy.is_resolved()}")
    print()

    # Chain attribute access WITHOUT triggering import
    path_lazy = os_lazy.path
    print(f"✓ Chained .path: {path_lazy}")
    print(f"  Original os_lazy resolved: {os_lazy.is_resolved()}")
    print(f"  path_lazy is still a LazyImport: {type(path_lazy).__name__}")
    print()

    # Actually use it - THIS triggers the import
    result = path_lazy.join("a", "b", "c")
    print(f"✓ Called path.join('a', 'b', 'c'): {result}")
    print(f"  path_lazy is NOW resolved: {path_lazy.is_resolved()}")
    print()


def demo_function_import() -> None:
    """Demonstrate importing a specific function."""
    print("=" * 70)
    print("DEMO 2: Direct Function Import")
    print("=" * 70)

    # Import specific function
    join = lazy_import("os.path", "join")
    print(f"✓ Created: {join}")
    print(f"  Is resolved: {join.is_resolved()}")
    print()

    # Call it - import happens here
    result = join("home", "user", "documents")
    print(f"✓ Called join('home', 'user', 'documents'): {result}")
    print(f"  Is resolved now: {join.is_resolved()}")
    print()


def demo_class_import() -> None:
    """Demonstrate importing and instantiating a class."""
    print("=" * 70)
    print("DEMO 3: Class Import and Instantiation")
    print("=" * 70)

    # Import a class
    Path = lazy_import("pathlib", "Path")
    print(f"✓ Created: {Path}")
    print(f"  Is resolved: {Path.is_resolved()}")
    print()

    # Instantiate it - import happens here
    p = Path("/tmp/test")
    print("✓ Instantiated: Path('/tmp/test')")
    print(f"  Result: {p}")
    print(f"  Type: {type(p)}")
    print(f"  Is resolved now: {Path.is_resolved()}")
    print()


def demo_settings_pattern() -> None:
    """Demonstrate the settings getter pattern (your main use case)."""
    print("=" * 70)
    print("DEMO 4: Settings Getter Pattern (YOUR USE CASE)")
    print("=" * 70)

    print("Simulating: _get_settings = lazy_import('codeweaver.config').get_settings")
    print("Using os.getcwd as a stand-in for get_settings()")
    print()

    # Global-level assignment
    _get_cwd = lazy_import("os").getcwd
    print("✓ Assigned at 'global' level: _get_cwd = lazy_import('os').getcwd")
    print(f"  Is resolved: {_get_cwd.is_resolved()}")
    print(f"  Type: {type(_get_cwd).__name__}")
    print()

    # Later in code - call the function
    print("Later in code, when you actually need it:")
    cwd = _get_cwd()
    print("✓ Called: _get_cwd()")
    print(f"  Result: {cwd}")
    print(f"  Is resolved now: {_get_cwd.is_resolved()}")
    print()


def demo_type_checking_pattern() -> None:
    """Demonstrate TYPE_CHECKING + runtime type pattern."""
    print("=" * 70)
    print("DEMO 5: TYPE_CHECKING + Runtime Type Pattern")
    print("=" * 70)

    print("Pattern for pydantic models:")
    print()
    print("  from __future__ import annotations")
    print("  from typing import TYPE_CHECKING")
    print()
    print("  if TYPE_CHECKING:")
    print("      from codeweaver.config import CodeWeaverSettings")
    print("  else:")
    print("      CodeWeaverSettings = lazy_import('codeweaver.config', 'CodeWeaverSettings')")
    print()
    print("  class MyModel(BaseModel):")
    print("      config: CodeWeaverSettings  # String annotation, no import!")
    print()

    # Simulate runtime usage
    print("For runtime (non-annotation) use:")
    Path = lazy_import("pathlib", "Path")
    print("✓ Path = lazy_import('pathlib', 'Path')")
    print(f"  Is resolved: {Path.is_resolved()}")
    print()

    instance = Path("/home")
    print("✓ instance = Path('/home')")
    print(f"  Result: {instance}")
    print(f"  Is resolved now: {Path.is_resolved()}")
    print()


def demo_comparison_old_vs_new() -> None:
    """Compare old lazy_importer vs new LazyImport."""
    print("=" * 70)
    print("DEMO 6: Comparison - Old vs New")
    print("=" * 70)

    print("OLD (awkward double-call syntax):")
    print("  module = lazy_importer('os')()")
    print("  result = module.path.join('a', 'b')")
    print()

    print("NEW (clean, natural syntax):")
    module = lazy_import("os")
    print("  module = lazy_import('os')")
    print(f"  Is resolved: {module.is_resolved()}")
    result = module.path.join("a", "b")
    print("  result = module.path.join('a', 'b')")
    print(f"  Result: {result}")
    print()

    print("OLD (attribute access would trigger import immediately):")
    print("  Settings = lazy_importer('config').CodeWeaverSettings  # ❌ Imports NOW")
    print()

    print("NEW (attribute access is STILL lazy):")
    Path = lazy_import("pathlib").Path
    print("  Path = lazy_import('pathlib').Path")
    print(f"  Is resolved: {Path.is_resolved()}  # ✅ Still lazy!")
    Path("/tmp")
    print("  instance = Path('/tmp')")
    print(f"  Is resolved now: {Path.is_resolved()}  # ✅ Imported when instantiated")
    print()


def demo_thread_safety() -> None:
    """Demonstrate thread-safe resolution."""
    import threading

    print("=" * 70)
    print("DEMO 7: Thread Safety")
    print("=" * 70)

    join = lazy_import("os.path", "join")
    results = []

    def resolve_and_use():
        result = join("thread", "safe", "test")
        results.append(result)

    # Create multiple threads
    threads = [threading.Thread(target=resolve_and_use) for _ in range(10)]

    print(f"✓ Created 10 threads to concurrently use: {join}")
    print(f"  Is resolved before threads: {join.is_resolved()}")
    print()

    # Start all threads
    for t in threads:
        t.start()

    # Wait for all to complete
    for t in threads:
        t.join()

    print("✓ All threads completed")
    print(f"  Is resolved now: {join.is_resolved()}")
    print(f"  All results identical: {all(r == results[0] for r in results)}")
    print(f"  Sample result: {results[0]}")
    print()


def main() -> None:
    """Run all demonstrations."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  LazyImport Demonstration - Solving Your Lazy Import Problems".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    demo_basic_usage()
    demo_function_import()
    demo_class_import()
    demo_settings_pattern()
    demo_type_checking_pattern()
    demo_comparison_old_vs_new()
    demo_thread_safety()

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print()
    print("✅ LazyImport solves your problems:")
    print()
    print("   1. No more awkward double-call syntax")
    print("      OLD: lazy_importer('module')()")
    print("      NEW: lazy_import('module')")
    print()
    print("   2. True lazy loading - defers until ACTUAL use")
    print("      OLD: lazy_import('config').get_settings()  # Imports immediately")
    print("      NEW: lazy_import('config').get_settings()  # Still lazy!")
    print()
    print("   3. Clean global-level usage")
    print("      Can assign at module scope without triggering imports")
    print()
    print("   4. Thread-safe resolution")
    print("      Multiple threads can safely access the same LazyImport")
    print()
    print("   5. Attribute chaining")
    print("      lazy_import('pkg').module.Class  # All lazy!")
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
