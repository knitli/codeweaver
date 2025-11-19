#!/usr/bin/env python
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""
Generates the API documentation pages and navigation for CodeWeaver.

This script is triggered by `mkdocs-gen-files` during the build process.
"""

import sys

from pathlib import Path

import mkdocs_gen_files


def find_python_files(src_dir: Path, *, debug: bool = False) -> list[Path]:
    """Recursively find all Python files in the source directory."""
    py_files = list(src_dir.rglob("*.py"))
    if debug:
        print(f"DEBUG: Found {len(py_files)} Python files")
    return py_files


def generate_doc_file(
    path: Path, src_dir: Path, root_dir: Path, *, debug: bool = False
) -> tuple[str, str] | None:
    """Generate a documentation file for a given Python module."""
    module_path = path.relative_to(src_dir).with_suffix("")
    doc_path = path.relative_to(src_dir).with_suffix(".md")

    # Skip __init__.py and __main__.py files
    if doc_path.name in ("__init__.md", "__main__.md"):
        if debug:
            print(f"DEBUG: Skipping {doc_path.name} file")
        return None

    full_doc_path = Path("api", doc_path)
    parts = tuple(module_path.parts)
    identifier = "codeweaver." + ".".join(parts) if parts else "codeweaver"

    if debug:
        print(f"DEBUG: Processing file: {path}")
        print(f"DEBUG: Module parts: {parts}")
        print(f"DEBUG: Generated identifier: {identifier}")
        print(f"DEBUG: Full doc path: {full_doc_path}")

    # Generate the documentation file
    with mkdocs_gen_files.open(full_doc_path, "w") as fd:
        print(f"::: {identifier}", file=fd)

    mkdocs_gen_files.set_edit_path(full_doc_path, path.relative_to(root_dir))

    # Remove 'api/api/' prefix if present
    clean_doc_path = Path(str(full_doc_path).replace("api/api/", "api/"))

    if debug:
        print(f"DEBUG: Generated doc file: {clean_doc_path}")

    return (str(clean_doc_path), identifier)


def build_navigation(nav_items: tuple[str, str], *, debug: bool = False) -> None:
    """Build and write the API index page with organized navigation."""
    with mkdocs_gen_files.open("api/index.md", "w") as nav_file:
        nav_file.write("# API Reference\n\n")
        nav_file.write("Complete API documentation for CodeWeaver.\n\n")

        # Group by top-level modules
        modules = {}
        for doc_path, identifier in nav_items:
            parts = identifier.split(".")
            if len(parts) > 1:
                module = parts[1]  # Skip 'codeweaver' prefix
                modules.setdefault(module, []).append((doc_path, identifier))
            else:
                modules.setdefault("root", []).append((doc_path, identifier))

        # Write organized navigation
        for module_name in sorted(modules.keys()):
            if module_name == "root":
                nav_file.write("## Core Modules\n\n")
            else:
                nav_file.write(f"## {module_name.title()}\n\n")

            for doc_path, identifier in sorted(modules[module_name]):
                # Create a readable title from the identifier
                title = identifier.replace("codeweaver.", "").replace(".", " › ")
                # Convert to relative path from api/index.md
                relative_path = str(doc_path).replace("api/", "")
                nav_file.write(f"- [{title}]({relative_path})\n")
            nav_file.write("\n")

    if debug:
        print(f"DEBUG: Generated API index with {len(nav_items)} items")


def main(*, debug: bool = True) -> None:
    """Main function to generate API documentation pages."""
    root = Path(__file__).parent.parent.parent
    src = root / "src" / "codeweaver"

    if debug:
        print(f"DEBUG: Root path: {root}")
        print(f"DEBUG: Source path: {src}")
        print(f"DEBUG: Source exists: {src.exists()}")

    py_files = find_python_files(src, debug=debug)

    nav_items = [
        result
        for path in sorted(py_files)
        if (result := generate_doc_file(path, src, root, debug=debug))
    ]

    build_navigation(nav_items, debug=debug)


if __name__ == "__main__":
    DEBUG = len(sys.argv) <= 1 or sys.argv[1] != "--no-debug"
    main(debug=DEBUG)
