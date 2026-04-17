#!/usr/bin/env -S uv run --script
# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Generate API documentation MDX files from Python source code.

Walks the `codeweaver` package tree, skips anything matching the exclude
globs in `EXCLUDE_PATTERNS`, and emits one `.mdx` file per surviving module
into `docs-site/src/content/docs/api/`, mirroring the source package layout.

Packages (directories with `__init__.py`) become `{pkg}/index.mdx`, modules
become `{mod}.mdx`. The entire output directory is wiped at the start of
each run so stale files can't accumulate.

Usage:
    uv run scripts/gen_api_docs.py
"""

import fnmatch
import shutil

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from griffe import Alias, GriffeLoader, Parser, load_extensions


# ── Configuration ────────────────────────────────────────────────────────

ROOT_PACKAGE = "codeweaver"

# Exclude globs matched against dotted module names (fnmatch syntax).
# Anything matching is skipped entirely; its file is not emitted and its
# submodules are still independently evaluated against these patterns.
EXCLUDE_PATTERNS: list[str] = [
    # Private modules at any depth (names starting with "_" other than
    # __init__ itself). These are implementation details, not API.
    "codeweaver._*",
    "codeweaver.*._*",
    "codeweaver.*.*._*",
    "codeweaver.*.*.*._*",
    "codeweaver.*.*.*.*._*",
    # Internal test scaffolding shipped inside the package, if any.
    "codeweaver.testing",
    "codeweaver.testing.*",
    "codeweaver.*.tests",
    "codeweaver.*.tests.*",
    # modules that aren't particularly useful to document
    "codeweaver.providers.embedding.capabilities.*",
    "codeweaver.providers.reranking.capabilities.*",
    "codeweaver.cli.*",
    "codeweaver.cli.*.*",
    "codeweaver.data.*",
    "codeweaver.semantic.data.*",
]

FORCE_INCLUDE_PATTERNS: list[str] = [
    # If any module matches both EXCLUDE_PATTERNS and FORCE_INCLUDE_PATTERNS,
    # it will be included. This is for modules that are private but still
    # worth documenting, or that would otherwise be excluded by an overly
    # broad pattern.
    #
    # NOTE: For __init__.py files, use the package name WITHOUT .__init__
    # suffix, since _iter_modules strips __init__ from dotted names.
    "codeweaver.server.agent_api.search",
    "codeweaver.providers.embedding.capabilities.base",
    "codeweaver.providers.reranking.capabilities.base",
]


def escape_mdx(text: str) -> str:
    """Escape characters that would break MDX parsing in plain text."""
    return (
        text.replace("{", "&#123;").replace("}", "&#125;").replace("<", "&lt;").replace(">", "&gt;")
    )


def get_signature(obj: Alias | Any) -> str:
    """Get the signature of a function or method, handling Aliases."""
    try:
        target = obj
        if isinstance(obj, Alias):
            try:
                target = obj.target
            except Exception:
                return "()"
        if hasattr(target, "signature"):
            sig = str(target.signature)
            return "()" if "Function(" in sig or "Alias(" in sig else sig
    except Exception:
        return "()"
    else:
        return "()"


def _load_griffe_extensions() -> Any:
    """Load optional Griffe extensions, logging a warning if unavailable."""
    print("Loading codeweaver package with Griffe...")
    try:
        return load_extensions(["griffe_pydantic"])
    except Exception as e:
        print(f"Warning: Could not load griffe_pydantic: {e}")
        return None


def _append_pydantic_fields(md: list[str], member: Any) -> None:
    """Append Pydantic model fields table to the markdown list."""
    md.append("### Fields")
    md.extend(("", "| Field | Type | Default | Description |", "| :--- | :--- | :--- | :--- |"))
    for f_name, field in sorted(member.members.items()):
        if not f_name.startswith("_") and field.is_attribute:
            doc = field.docstring.value if field.docstring else ""
            doc = escape_mdx(doc.replace("\n", " ").strip())
            md.append(
                f"| `{f_name}` | `{field.annotation or 'Any'}` | `{field.value or 'None'}` | {doc} |"
            )
    md.append("")


def _append_class_docs(md: list[str], name: str, member: Any) -> None:
    """Append class documentation (including Pydantic fields and methods)."""
    md.extend((f"## Class: `{name}`", ""))
    md.extend((escape_mdx(member.docstring.value) if member.docstring else "", ""))

    is_pydantic = bool(hasattr(member, "extra") and "pydantic" in member.extra)
    if is_pydantic:
        _append_pydantic_fields(md, member)

    for m_name, method in sorted(member.members.items()):
        if m_name.startswith("_"):
            continue
        # Skip inherited / imported methods — document them where they are
        # actually defined (Griffe marks re-exports and imports as aliases).
        if getattr(method, "is_alias", False):
            continue
        if method.is_function:
            md.extend((f"### Method: `{m_name}`", "", "```python"))
            md.extend((f"{m_name}{get_signature(method)}", "```", ""))
            md.extend((escape_mdx(method.docstring.value) if method.docstring else "", ""))


def _generate_module_docs(loader: GriffeLoader, mod_name: str, output_path: Path) -> None:
    """Generate documentation for a single module into `output_path`."""
    print(f"Processing {mod_name}...")
    try:
        module = loader.load(mod_name)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        md = [
            "---",
            f"title: {module.name}",
            f"description: API reference for {module.canonical_path}",
            "---",
            "",
            f"# `{module.canonical_path}`",
            "",
            escape_mdx(module.docstring.value) if module.docstring else "",
            "",
        ]
        body_start = len(md)
        for name, member in sorted(module.members.items()):
            if name.startswith("_"):
                continue
            # Skip re-exports and imports. Griffe represents them as Alias
            # objects; we want each symbol documented once, in the file
            # where it is actually defined. (Without this filter, package
            # __init__.py pages become huge dumps of every re-exported
            # child, and submodule pages repeat stdlib imports like
            # `typing.Any`, `logging`, etc.)
            if getattr(member, "is_alias", False):
                continue
            try:
                if member.is_class:
                    _append_class_docs(md, name, member)
                elif member.is_function:
                    _append_function_signature(md, name, member)
            except Exception as e:  # pragma: no cover - diagnostic only
                print(f"  Warning: Resolution issues for {name}: {e}")
                continue

        # Packages that just re-export children have no standalone body;
        # skip writing them to keep the nav tree clean. The child modules
        # themselves still get their own pages.
        has_body = len(md) > body_start
        is_package = output_path.name == "index.mdx"
        has_module_docstring = bool(module.docstring and module.docstring.value.strip())
        if is_package and not has_body and not has_module_docstring:
            print(f"  Skipping {mod_name}: empty package re-export")
            return

        output_path.write_text("\n".join(md))
        print(f"Generated: {output_path}")
    except Exception as e:
        print(f"Error rendering {mod_name}: {e}")


def _is_excluded(dotted_name: str) -> bool:
    """Return True if `dotted_name` matches any `EXCLUDE_PATTERNS` glob."""
    return any(fnmatch.fnmatchcase(dotted_name, pat) for pat in EXCLUDE_PATTERNS) and not any(fnmatch.fnmatchcase(dotted_name, pat) for pat in FORCE_INCLUDE_PATTERNS)


def _iter_modules(src_path: Path) -> Iterator[tuple[str, Path]]:
    """Yield `(dotted_name, output_rel_path)` for every module to document.

    Walks `src_path / ROOT_PACKAGE`, converts filesystem paths to dotted
    module names, applies `EXCLUDE_PATTERNS`, and yields mirror-layout
    output paths (relative to the `api/` docs directory).
    """
    pkg_root = src_path / ROOT_PACKAGE
    if not pkg_root.is_dir():
        raise RuntimeError(f"Source package not found: {pkg_root}")

    for py_file in sorted(pkg_root.rglob("*.py")):
        # Skip anything under a __pycache__ directory.
        if "__pycache__" in py_file.parts:
            continue

        rel = py_file.relative_to(src_path)
        parts = rel.with_suffix("").parts  # e.g. ("codeweaver", "engine", "chunker")

        # Drop the trailing "__init__" component for packages.
        dotted_parts = parts[:-1] if rel.name == "__init__.py" else parts

        if not dotted_parts:
            continue

        dotted = ".".join(dotted_parts)

        if _is_excluded(dotted):
            print(f"  Excluded: {dotted}")
            continue

        # Drop the leading root-package segment for the output path so
        # `codeweaver.engine.chunker` → `api/engine/chunker.mdx`, and the
        # root package itself → `api/index.mdx`.
        sub_parts = dotted_parts[1:]

        if rel.name == "__init__.py":
            out_rel = Path(*sub_parts, "index.mdx") if sub_parts else Path("index.mdx")
        else:
            out_rel = Path(*sub_parts[:-1], f"{sub_parts[-1]}.mdx")

        yield dotted, out_rel


def _wipe_output_dir(docs_output: Path) -> None:
    """Remove every file/subdir inside `docs_output` (but not the dir itself)."""
    if not docs_output.exists():
        return
    for entry in docs_output.iterdir():
        if entry.is_file() or entry.is_symlink():
            entry.unlink()
        else:
            shutil.rmtree(entry)


def main() -> None:
    """Main function to generate API docs."""
    project_root = Path(__file__).parent.parent
    src_path = project_root / "src"
    docs_output = project_root / "docs-site" / "src" / "content" / "docs" / "api"

    _wipe_output_dir(docs_output)
    docs_output.mkdir(parents=True, exist_ok=True)

    extensions = _load_griffe_extensions()
    loader = GriffeLoader(
        search_paths=[str(src_path)], extensions=extensions, docstring_parser=Parser.google
    )

    count = 0
    for dotted_name, out_rel in _iter_modules(src_path):
        _generate_module_docs(loader, dotted_name, docs_output / out_rel)
        count += 1
    print(f"\nDone. Processed {count} modules into {docs_output}.")


def _append_function_signature(md: list[str], name: str, member: Alias | Any) -> None:
    """Append function signature and docstring to the markdown list."""
    md.extend((f"## Function: `{name}`", "", "```python"))
    md.extend((f"{name}{get_signature(member)}", "```", ""))
    md.extend((escape_mdx(member.docstring.value) if member.docstring else "", ""))


if __name__ == "__main__":
    main()
