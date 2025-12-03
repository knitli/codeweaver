#!/usr/bin/env python3
"""
Generate API documentation markdown files from Python source code.

Uses Griffe to extract docstrings and type information, then generates
Starlight-compatible markdown files with proper frontmatter.
"""

import sys
from pathlib import Path
from typing import Any

try:
    from griffe import (
        GriffeLoader,
        Module,
        Class,
        Function,
        Attribute,
        DocstringSectionKind,
    )
except ImportError as e:
    print(f"Error: griffe is not installed or imports failed: {e}")
    print("Run: pip install griffe")
    sys.exit(1)

try:
    from pydantic import BaseModel
except ImportError:
    print("Warning: pydantic not found. Pydantic model field descriptions will not be extracted.")
    BaseModel = None


def get_pydantic_fields(cls: Class) -> dict[str, str]:
    """Extract Pydantic field descriptions from model schema."""
    if not BaseModel:
        return {}

    # Check if this is a Pydantic model by looking at bases
    is_pydantic = any("BaseModel" in str(base) or "pydantic" in str(base)
                      for base in cls.bases)

    if not is_pydantic:
        return {}

    field_descriptions = {}

    # Extract field descriptions from docstring or annotations
    for member_name, member in cls.members.items():
        if isinstance(member, Attribute) and member.docstring:
            field_descriptions[member_name] = member.docstring.value

    return field_descriptions


def format_signature(func: Function) -> str:
    """Format function signature for markdown."""
    params = []
    for param in func.parameters:
        param_str = param.name
        if param.annotation:
            param_str += f": {param.annotation}"
        if param.default:
            param_str += f" = {param.default}"
        params.append(param_str)

    sig = f"{func.name}({', '.join(params)})"
    if func.returns:
        sig += f" -> {func.returns}"

    return sig


def extract_docstring_sections(obj: Any) -> dict[str, list[str]]:
    """Extract structured docstring sections (Args, Returns, etc.)."""
    if not obj.docstring or not obj.docstring.parsed:
        return {}

    sections = {}
    for section in obj.docstring.parsed:
        if section.kind == DocstringSectionKind.text:
            sections["description"] = [section.value]
        elif section.kind == DocstringSectionKind.parameters:
            sections["parameters"] = [
                f"- **{param.name}** ({param.annotation or 'Any'}): {param.description}"
                for param in section.value
            ]
        elif section.kind == DocstringSectionKind.returns:
            sections["returns"] = [f"{section.value.annotation or ''}: {section.value.description}"]
        elif section.kind == DocstringSectionKind.raises:
            sections["raises"] = [
                f"- **{exc.annotation}**: {exc.description}"
                for exc in section.value
            ]
        elif section.kind == DocstringSectionKind.examples:
            sections["examples"] = [section.value]

    return sections


def generate_function_docs(func: Function, depth: int = 2) -> str:
    """Generate markdown documentation for a function."""
    md = []
    header = "#" * depth

    # Function signature
    md.append(f"{header} `{format_signature(func)}`\n")

    # Docstring sections
    sections = extract_docstring_sections(func)

    if "description" in sections:
        md.extend(sections["description"])
        md.append("")

    if "parameters" in sections:
        md.append("**Parameters:**\n")
        md.extend(sections["parameters"])
        md.append("")

    if "returns" in sections:
        md.append("**Returns:**\n")
        md.extend(sections["returns"])
        md.append("")

    if "raises" in sections:
        md.append("**Raises:**\n")
        md.extend(sections["raises"])
        md.append("")

    if "examples" in sections:
        md.append("**Examples:**\n")
        md.extend(sections["examples"])
        md.append("")

    return "\n".join(md)


def generate_class_docs(cls: Class, depth: int = 2) -> str:
    """Generate markdown documentation for a class."""
    md = []
    header = "#" * depth

    # Class header
    bases_str = f"({', '.join(str(b) for b in cls.bases)})" if cls.bases else ""
    md.append(f"{header} class `{cls.name}{bases_str}`\n")

    # Class docstring
    if cls.docstring:
        md.append(cls.docstring.value)
        md.append("")

    # Pydantic fields
    pydantic_fields = get_pydantic_fields(cls)
    if pydantic_fields:
        md.append(f"{header}# Fields\n")
        md.append("| Field | Description |")
        md.append("|-------|-------------|")
        for field_name, description in pydantic_fields.items():
            md.append(f"| `{field_name}` | {description} |")
        md.append("")

    # Methods
    methods = [m for m in cls.members.values() if isinstance(m, Function)]
    if methods:
        md.append(f"{header}# Methods\n")
        for method in methods:
            if not method.name.startswith("_"):  # Skip private methods
                md.append(generate_function_docs(method, depth + 2))

    return "\n".join(md)


def generate_module_docs(module: Module, output_path: Path):
    """Generate markdown file for a Python module."""
    md = []

    # Frontmatter
    module_title = module.name.replace("codeweaver.", "")
    md.append("---")
    md.append(f"title: {module_title}")
    md.append(f"description: API reference for {module.name}")
    md.append("---\n")

    # Module docstring
    if module.docstring:
        md.append(f"# {module_title}\n")
        md.append(module.docstring.value)
        md.append("")

    # Classes
    classes = [m for m in module.members.values() if isinstance(m, Class)]
    if classes:
        md.append("## Classes\n")
        for cls in classes:
            if not cls.name.startswith("_"):  # Skip private classes
                md.append(generate_class_docs(cls))
                md.append("")

    # Functions
    functions = [m for m in module.members.values() if isinstance(m, Function)]
    if functions:
        md.append("## Functions\n")
        for func in functions:
            if not func.name.startswith("_"):  # Skip private functions
                md.append(generate_function_docs(func))
                md.append("")

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(md))
    print(f"Generated: {output_path}")


def main():
    """Main entry point."""
    # Paths
    project_root = Path(__file__).parent.parent
    src_path = project_root / "src"
    docs_output = project_root / "docs-site" / "src" / "content" / "docs" / "api"

    # Ensure output directory exists
    docs_output.mkdir(parents=True, exist_ok=True)

    # Load CodeWeaver package
    print("Loading codeweaver package with Griffe...")
    loader = GriffeLoader(search_paths=[str(src_path)])

    try:
        codeweaver = loader.load("codeweaver")
    except Exception as e:
        print(f"Error loading codeweaver: {e}")
        sys.exit(1)

    # Generate index page
    index_md = [
        "---",
        "title: API Reference",
        "description: Complete API reference for CodeWeaver",
        "---\n",
        "# API Reference\n",
        "Complete documentation for CodeWeaver's Python API.\n",
        "## Modules\n",
    ]

    # Track generated modules
    generated = []

    # Process all submodules
    for module_name, module in codeweaver.modules.items():
        # Skip __init__ and __main__
        if module_name.endswith("__init__") or module_name.endswith("__main__"):
            continue

        # Generate relative path for output
        rel_path = module_name.replace("codeweaver.", "").replace(".", "/")
        output_path = docs_output / f"{rel_path}.md"

        # Generate docs
        try:
            generate_module_docs(module, output_path)
            generated.append((module_name, rel_path))
        except Exception as e:
            print(f"Warning: Failed to generate docs for {module_name}: {e}")

    # Add to index
    # Group by top-level module
    grouped = {}
    for full_name, rel_path in generated:
        top_level = rel_path.split("/")[0]
        if top_level not in grouped:
            grouped[top_level] = []
        grouped[top_level].append((full_name, rel_path))

    for group, modules in sorted(grouped.items()):
        index_md.append(f"### {group.title()}\n")
        for full_name, rel_path in sorted(modules):
            display_name = full_name.replace("codeweaver.", "")
            index_md.append(f"- [`{display_name}`](/api/{rel_path}/)")
        index_md.append("")

    # Write index
    index_path = docs_output / "index.md"
    index_path.write_text("\n".join(index_md))
    print(f"\nGenerated API index: {index_path}")
    print(f"Total modules documented: {len(generated)}")


if __name__ == "__main__":
    main()
