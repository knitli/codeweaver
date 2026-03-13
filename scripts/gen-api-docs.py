#!/usr/bin/env -S uv run -s
# ruff: noqa: N999
# ///script
# requires-python = ">=3.11"
# dependencies = ["griffe", "griffe-pydantic", "pydantic", "jinja2"]
# ///
# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Generate API documentation MDX files from Python source code.
"""

import sys
from pathlib import Path
from griffe import GriffeLoader, load_extensions, Parser, Alias, Function

def get_signature(obj):
    try:
        # If it's an alias, try to get the target's signature
        target = obj
        if isinstance(obj, Alias):
            try:
                target = obj.target
            except Exception:
                return "()"
        
        if hasattr(target, "signature"):
            sig = str(target.signature)
            # Remove messy internal Griffe representation if present
            if "Function(" in sig or "Alias(" in sig:
                return "()"
            return sig
        return "()"
    except Exception:
        return "()"

def main() -> None:
    project_root = Path(__file__).parent.parent
    src_path = project_root / "src"
    docs_output = project_root / "docs-site" / "src" / "content" / "docs" / "api"
    docs_output.mkdir(parents=True, exist_ok=True)

    print("Loading codeweaver package with Griffe...")
    
    # Correct way to load extensions in Griffe
    try:
        extensions = load_extensions(["griffe_pydantic"])
    except Exception as e:
        print(f"Warning: Could not load griffe_pydantic: {e}")
        extensions = None

    loader = GriffeLoader(
        search_paths=[str(src_path)], 
        extensions=extensions,
        docstring_parser=Parser.google,
    )
    
    # Load specific modules
    modules_to_document = [
        "codeweaver.core.config.core_settings",
        "codeweaver.core.di",
        "codeweaver.engine",
        "codeweaver.server",
        "codeweaver.providers",
    ]

    for mod_name in modules_to_document:
        print(f"Processing {mod_name}...")
        try:
            # We try to load without resolving everything to prevent early failures
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
                module.docstring.value if module.docstring else "",
                ""
            ]
            
            for name, member in sorted(module.members.items()):
                if name.startswith("_"): continue
                
                try:
                    if member.is_class:
                        md.append(f"## Class: `{name}`")
                        md.append("")
                        md.append(member.docstring.value if member.docstring else "")
                        md.append("")
                        
                        # Pydantic support check
                        is_pydantic = False
                        if hasattr(member, "extra") and "pydantic" in member.extra:
                            is_pydantic = True
                        
                        if is_pydantic:
                            md.append("### Fields")
                            md.append("")
                            md.append("| Field | Type | Default | Description |")
                            md.append("| :--- | :--- | :--- | :--- |")
                            for f_name, field in sorted(member.members.items()):
                                if not f_name.startswith("_") and field.is_attribute:
                                    doc = field.docstring.value if field.docstring else ""
                                    doc = doc.replace("\n", " ").strip()
                                    md.append(f"| `{f_name}` | `{field.annotation or 'Any'}` | `{field.value or 'None'}` | {doc} |")
                            md.append("")

                        for m_name, method in sorted(member.members.items()):
                            if not m_name.startswith("_") and method.is_function:
                                md.append(f"### Method: `{m_name}`")
                                md.append("")
                                md.append("```python")
                                md.append(f"{m_name}{get_signature(method)}")
                                md.append("```")
                                md.append("")
                                md.append(method.docstring.value if method.docstring else "")
                                md.append("")

                    elif member.is_function:
                        md.append(f"## Function: `{name}`")
                        md.append("")
                        md.append("```python")
                        md.append(f"{name}{get_signature(member)}")
                        md.append("```")
                        md.append("")
                        md.append(member.docstring.value if member.docstring else "")
                        md.append("")
                except Exception as e:
                    # Log but continue
                    print(f"  Warning: Resolution issues for {name}: {e}")
                    continue

            output_path.write_text("\n".join(md))
            print(f"Generated: {output_path}")
        except Exception as e:
            print(f"Error rendering {mod_name}: {e}")

if __name__ == "__main__":
    main()
