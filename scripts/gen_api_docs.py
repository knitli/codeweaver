#!/usr/bin/env -S uv -s
# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Generate API documentation MDX files from Python source code.
"""

from pathlib import Path
from typing import Any

from griffe import Alias, GriffeLoader, Parser, load_extensions


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
        if not m_name.startswith("_") and method.is_function:
            md.extend((f"### Method: `{m_name}`", "", "```python"))
            md.extend((f"{m_name}{get_signature(method)}", "```", ""))
            md.extend((escape_mdx(method.docstring.value) if method.docstring else "", ""))


def _generate_module_docs(loader: GriffeLoader, mod_name: str, docs_output: Path) -> None:
    """Generate documentation for a single module."""
    print(f"Processing {mod_name}...")
    try:
        module = loader.load(mod_name)
        rel_path = mod_name.replace("codeweaver.", "").replace(".", "/")
        output_path = docs_output / f"{rel_path}.mdx"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        md = [
            "---",
            f"title: {module.name}",
            f"description: API reference for {module.canonical_path}",
            "---",
            "",
            f"# {module.name}",
            "",
            escape_mdx(module.docstring.value) if module.docstring else "",
            "",
        ]
        for name, member in sorted(module.members.items()):
            if name.startswith("_"):
                continue
            try:
                if member.is_class:
                    _append_class_docs(md, name, member)
                elif member.is_function:
                    _append_function_signature(md, name, member)
            except Exception as e:
                print(f"  Warning: Resolution issues for {name}: {e}")
                continue
        output_path.write_text("\n".join(md))
        print(f"Generated: {output_path}")
    except Exception as e:
        print(f"Error rendering {mod_name}: {e}")


def main() -> None:
    """Main function to generate API docs."""
    project_root = Path(__file__).parent.parent
    src_path = project_root / "src"
    docs_output = project_root / "docs-site" / "src" / "content" / "docs" / "api"
    docs_output.mkdir(parents=True, exist_ok=True)

    extensions = _load_griffe_extensions()
    loader = GriffeLoader(
        search_paths=[str(src_path)], extensions=extensions, docstring_parser=Parser.google
    )
    modules_to_document = [
        "codeweaver.core.config.core_settings",
        "codeweaver.core.di",
        "codeweaver.engine",
        "codeweaver.server",
        "codeweaver.providers",
    ]
    for mod_name in modules_to_document:
        _generate_module_docs(loader, mod_name, docs_output)


def _append_function_signature(md: list[str], name: str, member: Alias | Any) -> None:
    """Append function signature and docstring to the markdown list."""
    md.extend((f"## Function: `{name}`", "", "```python"))
    md.extend((f"{name}{get_signature(member)}", "```", ""))
    md.extend((escape_mdx(member.docstring.value) if member.docstring else "", ""))


if __name__ == "__main__":
    main()
