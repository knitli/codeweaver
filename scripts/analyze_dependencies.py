#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Analyze cross-package dependencies in CodeWeaver."""

import ast
import json

from collections import defaultdict
from pathlib import Path
from typing import Any


class ImportAnalyzer(ast.NodeVisitor):
    """Analyze imports in a Python file."""

    def __init__(self, package_root: str):
        self.package_root = package_root
        self.imports: set[str] = set()
        self.in_type_checking = False

    def visit_If(self, node: ast.If) -> None:
        """Visit If nodes to detect TYPE_CHECKING blocks."""
        is_type_checking = False
        if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
            is_type_checking = True
        elif (
            isinstance(node.test, ast.Attribute)
            and isinstance(node.test.value, ast.Name)
            and node.test.value.id == "typing"
            and node.test.attr == "TYPE_CHECKING"
        ):
            is_type_checking = True

        if is_type_checking:
            old_val = self.in_type_checking
            self.in_type_checking = True
            # Don't visit the body if it's a TYPE_CHECKING block
            # Actually, we want to skip it, so we don't call generic_visit(node) for the body
            # but we might want to visit the orelse
            for item in node.orelse:
                self.visit(item)
            self.in_type_checking = old_val
        else:
            self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        """Visit import statements."""
        if self.in_type_checking:
            return
        for alias in node.names:
            if alias.name.startswith(self.package_root):
                self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Visit from...import statements."""
        if self.in_type_checking:
            return
        if node.module and node.module.startswith(self.package_root):
            self.imports.add(node.module)
        self.generic_visit(node)


def get_package_name(file_path: Path, src_dir: Path) -> str:
    """Get the package name from a file path."""
    rel_path = file_path.relative_to(src_dir)
    parts = list(rel_path.parts)

    # Remove the file name
    if parts[-1].endswith(".py"):
        parts = parts[:-1]

    # Join parts to form package name
    return ".".join(parts) if parts else ""


def extract_top_level_package(import_path: str) -> str:
    """Extract the top-level package from an import path."""
    parts = import_path.split(".")
    # Return up to 2 levels: codeweaver.xxx
    return ".".join(parts[:2]) if len(parts) >= 2 else import_path


def analyze_file(file_path: Path, package_root: str) -> set[str]:
    """Analyze imports in a single file."""
    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))

        analyzer = ImportAnalyzer(package_root)
        analyzer.visit(tree)
        return analyzer.imports
    except (SyntaxError, UnicodeDecodeError) as e:
        print(f"Warning: Could not parse {file_path}: {e}")
        return set()


def analyze_dependencies() -> tuple[dict[str, set[str]], dict[str, list[str]]]:
    """Analyze all dependencies in the codeweaver package."""
    src_dir = Path("src")
    codeweaver_dir = src_dir / "codeweaver"

    # Map: package -> set of imported packages
    dependencies: dict[str, set[str]] = defaultdict(set)

    # Map: package -> list of files in that package
    package_files: dict[str, list[str]] = defaultdict(list)

    # Find all Python files
    for py_file in codeweaver_dir.rglob("*.py"):
        # Get the package this file belongs to
        file_package = get_package_name(py_file, src_dir)
        top_level_pkg = extract_top_level_package(file_package)

        package_files[top_level_pkg].append(str(py_file.relative_to(src_dir)))

        # Analyze imports
        imports = analyze_file(py_file, "codeweaver")

        for imp in imports:
            imported_pkg = extract_top_level_package(imp)
            # Only track cross-package dependencies
            if imported_pkg != top_level_pkg and imported_pkg.startswith("codeweaver."):
                dependencies[top_level_pkg].add(imported_pkg)

    return dict(dependencies), dict(package_files)


def calculate_metrics(dependencies: dict[str, set[str]]) -> dict[str, Any]:
    """Calculate dependency metrics."""
    metrics = {}

    # Calculate afferent (incoming) and efferent (outgoing) couplings
    afferent: dict[str, int] = defaultdict(int)
    efferent: dict[str, int] = defaultdict(int)

    for pkg, deps in dependencies.items():
        efferent[pkg] = len(deps)
        for dep in deps:
            afferent[dep] += 1

    # Calculate instability (I = Ce / (Ca + Ce))
    # I = 0: maximally stable, I = 1: maximally unstable
    for pkg in set(list(dependencies.keys()) + list(afferent.keys())):
        ca = afferent.get(pkg, 0)  # Afferent (incoming)
        ce = efferent.get(pkg, 0)  # Efferent (outgoing)

        instability = ce / (ca + ce) if (ca + ce) > 0 else 0

        metrics[pkg] = {
            "afferent": ca,
            "efferent": ce,
            "instability": round(instability, 2),
            "total_coupling": ca + ce,
        }

    return metrics


def identify_cycles(dependencies: dict[str, set[str]]) -> list[list[str]]:
    """Identify circular dependencies."""
    cycles = []

    def dfs(node: str, path: list[str], visited: set[str]) -> None:
        if node in path:
            # Found a cycle
            cycle_start = path.index(node)
            cycle = [*path[cycle_start:], node]
            if cycle not in cycles and list(reversed(cycle)) not in cycles:
                cycles.append(cycle)
            return

        if node in visited:
            return

        visited.add(node)
        path.append(node)

        for dep in dependencies.get(node, set()):
            dfs(dep, path.copy(), visited)

    for pkg in dependencies:
        dfs(pkg, [], set())

    return cycles


def main():
    """Main analysis function."""
    print("Analyzing dependencies...")
    dependencies, package_files = analyze_dependencies()

    print("\n" + "=" * 80)
    print("CROSS-PACKAGE DEPENDENCY ANALYSIS")
    print("=" * 80)

    # Sort packages by name
    sorted_pkgs = sorted(dependencies.keys())

    print("\n📦 Packages and Their Dependencies:\n")
    for pkg in sorted_pkgs:
        deps = dependencies[pkg]
        print(f"{pkg}")
        print(f"  Files: {len(package_files.get(pkg, []))}")
        if deps:
            print("  Depends on:")
            for dep in sorted(deps):
                print(f"    → {dep}")
        else:
            print("  No dependencies")
        print()

    # Calculate metrics
    metrics = calculate_metrics(dependencies)

    print("\n📊 Dependency Metrics:\n")
    print(f"{'Package':<35} {'Afferent':<10} {'Efferent':<10} {'Instability':<12} {'Total':<8}")
    print("-" * 80)

    for pkg in sorted(metrics.keys()):
        m = metrics[pkg]
        print(
            f"{pkg:<35} {m['afferent']:<10} {m['efferent']:<10} {m['instability']:<12} {m['total_coupling']:<8}"
        )

    # Identify highly coupled packages
    print("\n⚠️  High Coupling (Total > 5):\n")
    high_coupling = {pkg: m for pkg, m in metrics.items() if m["total_coupling"] > 5}
    for pkg, m in sorted(high_coupling.items(), key=lambda x: x[1]["total_coupling"], reverse=True):
        print(
            f"  {pkg}: {m['total_coupling']} connections (afferent={m['afferent']}, efferent={m['efferent']})"
        )

    # Identify unstable packages
    print("\n🔄 Unstable Packages (Instability > 0.7):\n")
    unstable = {pkg: m for pkg, m in metrics.items() if m["instability"] > 0.7}
    for pkg, m in sorted(unstable.items(), key=lambda x: x[1]["instability"], reverse=True):
        print(f"  {pkg}: instability={m['instability']}")

    # Identify stable packages (good candidates for extraction)
    print("\n✅ Stable Packages (Instability < 0.3):\n")
    stable = {pkg: m for pkg, m in metrics.items() if m["instability"] < 0.3}
    for pkg, m in sorted(stable.items(), key=lambda x: x[1]["instability"]):
        print(f"  {pkg}: instability={m['instability']}")

    # Check for cycles
    print("\n🔁 Circular Dependencies:\n")
    cycles = identify_cycles(dependencies)
    if cycles:
        for i, cycle in enumerate(cycles, 1):
            print(f"  Cycle {i}: {' → '.join(cycle)}")
    else:
        print("  ✓ No circular dependencies detected")

    # Save detailed results to JSON
    output = {
        "dependencies": {k: list(v) for k, v in dependencies.items()},
        "metrics": metrics,
        "package_files": package_files,
        "cycles": cycles,
    }

    output_file = Path("claudedocs/dependency_analysis.json")
    output_file.parent.mkdir(exist_ok=True)
    with output_file.open("w") as f:
        json.dump(output, f, indent=2)

    print(f"\n📄 Detailed analysis saved to: {output_file}")

    # Provide recommendations
    print("\n" + "=" * 80)
    print("MONOREPO SPLIT ASSESSMENT")
    print("=" * 80)

    print("\n🎯 Potential Package Candidates:\n")

    if candidates := {
        pkg: m for pkg, m in metrics.items() if m["total_coupling"] <= 3 and m["instability"] <= 0.5
    }:
        for pkg, m in sorted(candidates.items(), key=lambda x: x[1]["total_coupling"]):
            print(f"  ✓ {pkg}")
            print(f"    - Coupling: {m['total_coupling']} (low)")
            print(f"    - Instability: {m['instability']} (stable)")
            print(f"    - Files: {len(package_files.get(pkg, []))}")
            print()
    else:
        print("  No clear standalone candidates found")

    print("\n⚠️  Separation Challenges:\n")

    # High coupling packages will be hard to separate
    challenges = {
        pkg: m for pkg, m in metrics.items() if m["total_coupling"] > 5 or m["efferent"] > 5
    }

    for pkg, m in sorted(challenges.items(), key=lambda x: x[1]["total_coupling"], reverse=True):
        print(f"  {pkg}")
        print(f"    - High coupling: {m['total_coupling']} connections")
        print(f"    - Depends on {m['efferent']} other packages")
        print(f"    - Used by {m['afferent']} other packages")
        print()


if __name__ == "__main__":
    main()
