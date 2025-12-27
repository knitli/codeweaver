#!/usr/bin/env python3

"""
Validate architectural dependencies against the planned monorepo structure.
"""

import ast
import os

from collections import defaultdict
from typing import NamedTuple


# --- Configuration ---


class PackageRule(NamedTuple):
    pattern: str
    package: str


# Order matters! Specific paths before general ones.
PATH_RULES = [
    (r"packages/codeweaver-daemon/src/codeweaver_daemon", "codeweaver-daemon"),
    (r"packages/codeweaver-tokenizers/src/codeweaver_tokenizers", "codeweaver-tokenizers"),
    (r"src/codeweaver/common/telemetry", "codeweaver-telemetry"),
    (r"src/codeweaver/common/registry", "codeweaver-engine"),
    (r"src/codeweaver/config", "codeweaver-engine"),
    (r"src/codeweaver/engine", "codeweaver-engine"),
    (r"src/codeweaver/semantic", "codeweaver-semantic"),
    (r"src/codeweaver/providers", "codeweaver-providers"),
    (r"src/codeweaver/core", "codeweaver-core"),
    (r"src/codeweaver/exceptions.py", "codeweaver-core"),
    (r"src/codeweaver/common/types.py", "codeweaver-core"),
    (r"src/codeweaver/common/_logging.py", "codeweaver-core"),
    (r"src/codeweaver/common/statistics.py", "codeweaver-core"),
    (r"src/codeweaver/common/http_pool.py", "codeweaver-core"),
    (r"src/codeweaver/common/__init__.py", "codeweaver-core"),
    (r"src/codeweaver/di", "codeweaver-core"),
    (r"src/codeweaver/_version.py", "codeweaver-core"),
    (r"src/codeweaver/__init__.py", "codeweaver-core"),
    (
        r"src/codeweaver/data",
        "codeweaver-core",
    ),  # Assuming mostly types/interfaces if not providers
    (r"src/codeweaver/agent_api", "codeweaver"),
    (r"src/codeweaver/cli", "codeweaver"),
    (r"src/codeweaver/server", "codeweaver"),
    (r"src/codeweaver/mcp", "codeweaver"),
    (r"src/codeweaver/main.py", "codeweaver"),
    # Catch-alls
    (r"src/codeweaver/tokenizers", "codeweaver-tokenizers"),  # In case old path exists
]

IMPORT_RULES = [
    ("codeweaver_daemon", "codeweaver-daemon"),
    ("codeweaver_tokenizers", "codeweaver-tokenizers"),
    ("codeweaver.common.telemetry", "codeweaver-telemetry"),
    ("codeweaver.common.registry", "codeweaver-engine"),
    ("codeweaver.config", "codeweaver-engine"),
    ("codeweaver.engine", "codeweaver-engine"),
    ("codeweaver.semantic", "codeweaver-semantic"),
    ("codeweaver.providers", "codeweaver-providers"),
    ("codeweaver.core", "codeweaver-core"),
    ("codeweaver.exceptions", "codeweaver-core"),
    ("codeweaver.common.types", "codeweaver-core"),
    ("codeweaver.common._logging", "codeweaver-core"),
    ("codeweaver.common.statistics", "codeweaver-core"),
    ("codeweaver.common.http_pool", "codeweaver-core"),
    ("codeweaver.common", "codeweaver-core"),
    ("codeweaver.di", "codeweaver-core"),
    ("codeweaver._version", "codeweaver-core"),
    ("codeweaver.data", "codeweaver-core"),
    ("codeweaver.agent_api", "codeweaver"),
    ("codeweaver.cli", "codeweaver"),
    ("codeweaver.server", "codeweaver"),
    ("codeweaver.mcp", "codeweaver"),
    ("codeweaver.tokenizers", "codeweaver-tokenizers"),  # In case old path/alias
]

ALLOWED_DEPENDENCIES = {
    "codeweaver-core": set(),
    "codeweaver-tokenizers": set(),
    "codeweaver-daemon": set(),
    "codeweaver-telemetry": {"codeweaver-core"},
    "codeweaver-semantic": {"codeweaver-core", "codeweaver-tokenizers"},
    "codeweaver-providers": {"codeweaver-core", "codeweaver-telemetry", "codeweaver-tokenizers"},
    "codeweaver-engine": {"codeweaver-core", "codeweaver-semantic", "codeweaver-providers"},
    "codeweaver": {
        "codeweaver-engine",
        "codeweaver-core",
        "codeweaver-semantic",
        "codeweaver-providers",
        "codeweaver-telemetry",
        "codeweaver-daemon",
        "codeweaver-tokenizers",
    },
}

# --- Analysis Logic ---


def get_package_for_file(file_path: str) -> str | None:
    """Determine the logical package for a given file path."""
    return next(
        (
            package
            for pattern, package in PATH_RULES
            if pattern in file_path
            and (file_path.startswith(pattern) or f"/{pattern}" in file_path)
        ),
        None,
    )


def get_package_for_import(import_name: str) -> str | None:
    """Determine the logical package for a given import string."""
    for pattern, package in IMPORT_RULES:
        if import_name == pattern or import_name.startswith(pattern + "."):
            return package

    # Fallback for unmapped codeweaver imports
    if import_name.startswith("codeweaver.") or import_name == "codeweaver":
        return "codeweaver-unknown"

    return None


class ImportVisitor(ast.NodeVisitor):
    def __init__(self):
        self.imports = set()

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.add(alias.name)

    def visit_ImportFrom(self, node):
        if node.module:
            self.imports.add(node.module)


def analyze_file(file_path: str, source_package: str) -> list[tuple[str, str]]:
    """Return list of (imported_package, import_statement) violations."""
    violations = []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return []

    visitor = ImportVisitor()
    visitor.visit(tree)

    for imp in visitor.imports:
        target_package = get_package_for_import(imp)

        # Ignore external imports or unknown ones (unless they are codeweaver-unknown)
        if not target_package:
            continue

        # Ignore self-references
        if target_package == source_package:
            continue

        # Check allowed dependencies
        allowed = ALLOWED_DEPENDENCIES.get(source_package, set())

        if target_package == "codeweaver-unknown" or target_package not in allowed:
            violations.append((target_package, imp))

    return violations


def main():
    root_dirs = ["src", "packages"]
    all_violations = defaultdict(list)
    unknown_files = []

    # Track all known packages to ensure we report on them even if empty
    known_packages = sorted(ALLOWED_DEPENDENCIES.keys())
    packages_with_violations = set()

    print("Analyzing dependencies...")

    for root_dir in root_dirs:
        for root, _, files in os.walk(root_dir):
            for file in files:
                if not file.endswith(".py"):
                    continue

                file_path = os.path.join(root, file)

                # Exclude specific legacy/root files from analysis
                if file_path == "src/codeweaver/__init__.py":
                    continue

                source_package = get_package_for_file(file_path)

                if not source_package:
                    # Only flag if it looks like source code
                    if "test" not in file_path and "codeweaver" in file_path:
                        unknown_files.append(file_path)
                    continue

                violations = analyze_file(file_path, source_package)
                for target, imp in violations:
                    all_violations[source_package].append((file_path, target, imp))

    print("\n=== Architectural Violations ===\n")

    found_violations = False

    for pkg in known_packages:
        violations = all_violations.get(pkg, [])
        if violations:
            print(f"Package: {pkg}")
            packages_with_violations.add(pkg)
            for file_path, target, imp in violations:
                print(f"  FAILED: {file_path}")
                print(f"    -> Imports: {imp} ({target})")
                if target == "codeweaver-unknown":
                    print("    (Unmapped import)")
                else:
                    print(f"    (Not in allowed dependencies: {ALLOWED_DEPENDENCIES.get(pkg)})")
            found_violations = True
            print()
        else:
            # Explicitly report success for packages with no violations
            print(f"Package: {pkg}")
            print("  ✅ No violations found")
            print()

    # Handle codeweaver-unknown or other inferred packages that weren't in ALLOWED_DEPENDENCIES
    for pkg, violations in sorted(all_violations.items()):
        if pkg not in known_packages:
            print(f"Package: {pkg} (Unexpected Package Name)")
            for file_path, target, imp in violations:
                print(f"  FAILED: {file_path}")
                print(f"    -> Imports: {imp} ({target})")
            print()

    if unknown_files:
        print("\n=== Unmapped Files (Could not determine package) ===\n")
        for f in unknown_files:
            print(f"  {f}")

    if not found_violations and not unknown_files:
        print("\n✅ No architectural violations found!")


if __name__ == "__main__":
    main()
