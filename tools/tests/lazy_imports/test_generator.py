#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for code generator.

Tests cover:
- Sentinel-based preservation of manual code
- Import statement generation (absolute/relative, TYPE_CHECKING)
- __all__ list generation
- Atomic writes with backup and rollback
- Syntax validation
- Error handling (FM-003, FM-010, FM-011)
"""

# sourcery skip: require-return-annotation, require-parameter-annotation, no-relative-imports
from __future__ import annotations

import tempfile

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tools.lazy_imports.common.types import ExportManifest, ExportNode, MemberType, PropagationLevel
from tools.lazy_imports.export_manager.generator import (
    SENTINEL,
    CodeGenerator,
    GeneratedCode,
    validate_init_file,
)


if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def generator(temp_dir: Path) -> CodeGenerator:
    """Create code generator for tests."""
    return CodeGenerator(temp_dir)


# Test data


def make_export(
    name: str,
    module: str,
    member_type: MemberType = MemberType.CLASS,
    defined_in: str | None = None,
) -> ExportNode:
    """Create test export node."""
    return ExportNode(
        name=name,
        module=module,
        member_type=member_type,
        propagation=PropagationLevel.PARENT,
        source_file=Path("/fake/path.py"),
        line_number=1,
        defined_in=defined_in or module,
    )


def make_manifest(
    module_path: str, own_exports: list[ExportNode], propagated: list[ExportNode] | None = None
) -> ExportManifest:
    """Create test export manifest."""
    propagated = propagated or []
    all_exports = own_exports + propagated

    return ExportManifest(
        module_path=module_path,
        own_exports=own_exports,
        propagated_exports=propagated,
        all_exports=all_exports,
    )


# Basic generation tests


def test_generate_empty_manifest(generator: CodeGenerator):
    """Test generating code from empty manifest."""
    manifest = make_manifest("test.module", own_exports=[])

    code = generator.generate(manifest)

    assert code.export_count == 0
    assert "__all__ = []" in code.content
    assert SENTINEL in code.content
    assert "from __future__ import annotations" in code.content


def test_generate_single_export(generator: CodeGenerator):
    """Test generating code with single export."""
    exports = [make_export("MyClass", "test.module.submodule")]
    manifest = make_manifest("test.module", own_exports=exports)

    code = generator.generate(manifest)

    assert code.export_count == 1
    assert '__all__ = ["MyClass"]' in code.content
    assert "from .submodule import MyClass" in code.content


def test_generate_multiple_exports(generator: CodeGenerator):
    """Test generating code with multiple exports."""
    exports = [
        make_export("ClassA", "test.module.sub1"),
        make_export("ClassB", "test.module.sub2"),
        make_export("function_c", "test.module.sub1", MemberType.FUNCTION),
    ]
    manifest = make_manifest("test.module", own_exports=exports)

    code = generator.generate(manifest)

    assert code.export_count == 3
    assert "ClassA" in code.content
    assert "ClassB" in code.content
    assert "function_c" in code.content
    # Should be sorted in __all__
    lines = code.content.split("\n")
    all_section = "\n".join(line for line in lines if line.strip().startswith('"') and "," in line)
    assert all_section.index("ClassA") < all_section.index("ClassB")
    assert all_section.index("ClassB") < all_section.index("function_c")


# TYPE_CHECKING tests


def test_type_alias_in_type_checking_block(generator: CodeGenerator):
    """Test type aliases go in TYPE_CHECKING block."""
    exports = [
        make_export("MyClass", "test.module.sub", MemberType.CLASS),
        make_export("MyType", "test.module.sub", MemberType.TYPE_ALIAS),
    ]
    manifest = make_manifest("test.module", own_exports=exports)

    code = generator.generate(manifest)

    # Should have TYPE_CHECKING import
    assert "from typing import TYPE_CHECKING" in code.content
    assert "if TYPE_CHECKING:" in code.content

    # Type alias should be in TYPE_CHECKING block
    lines = code.content.split("\n")
    type_checking_idx = next(i for i, line in enumerate(lines) if "if TYPE_CHECKING:" in line)
    mytype_idx = next(i for i, line in enumerate(lines) if "MyType" in line and "import" in line)
    assert mytype_idx > type_checking_idx

    # Class should be in runtime imports
    myclass_idx = next(i for i, line in enumerate(lines) if "MyClass" in line and "import" in line)
    assert myclass_idx < type_checking_idx


# Sentinel preservation tests


def test_preserve_manual_section(generator: CodeGenerator, temp_dir: Path):
    """Test preserving manual code above sentinel."""
    module_path = "test.module"
    target = temp_dir / "test" / "module" / "__init__.py"
    target.parent.mkdir(parents=True)

    # Write existing file with manual section
    existing_content = """# My custom imports
from typing import Protocol

# Custom code
CUSTOM_CONSTANT = 42

# === MANAGED EXPORTS ===
# Old managed section (will be replaced)
__all__ = ["OldExport"]
"""
    target.write_text(existing_content)

    # Generate new code
    exports = [make_export("NewExport", "test.module.sub")]
    manifest = make_manifest(module_path, own_exports=exports)
    code = generator.generate(manifest)

    # Should preserve manual section
    assert "# My custom imports" in code.manual_section
    assert "CUSTOM_CONSTANT = 42" in code.manual_section

    # Should NOT preserve old managed section
    assert "OldExport" not in code.managed_section

    # Should have new managed section
    assert "NewExport" in code.managed_section


def test_no_sentinel_preserves_all(generator: CodeGenerator, temp_dir: Path):
    """Test file without sentinel preserves entire content."""
    module_path = "test.module"
    target = temp_dir / "test" / "module" / "__init__.py"
    target.parent.mkdir(parents=True)

    # Write existing file WITHOUT sentinel
    existing_content = """# Legacy file without sentinel
from typing import Protocol

__all__ = ["LegacyExport"]
"""
    target.write_text(existing_content)

    # Generate new code
    exports = [make_export("NewExport", "test.module.sub")]
    manifest = make_manifest(module_path, own_exports=exports)
    code = generator.generate(manifest)

    # Should preserve entire file as manual section
    assert "# Legacy file without sentinel" in code.manual_section
    assert "LegacyExport" in code.manual_section


# Atomic write tests


def test_write_file_creates_directories(generator: CodeGenerator, temp_dir: Path):
    """Test write_file creates parent directories."""
    module_path = "test.deeply.nested.module"
    exports = [make_export("MyClass", module_path)]
    manifest = make_manifest(module_path, own_exports=exports)
    code = generator.generate(manifest)

    generator.write_file(module_path, code)

    # Should create directory structure
    target = temp_dir / "test" / "deeply" / "nested" / "module" / "__init__.py"
    assert target.exists()
    assert target.is_file()


def test_write_file_creates_backup(generator: CodeGenerator, temp_dir: Path):
    """Test write_file creates backup of existing file."""
    module_path = "test.module"
    target = temp_dir / "test" / "module" / "__init__.py"
    target.parent.mkdir(parents=True)

    # Write initial file
    initial_content = "# Initial content\n__all__ = []"
    target.write_text(initial_content)

    # Write new file
    exports = [make_export("NewClass", module_path)]
    manifest = make_manifest(module_path, own_exports=exports)
    code = generator.generate(manifest)
    generator.write_file(module_path, code)

    # Backup should not exist after successful write (cleaned up)
    backup = target.with_suffix(".py.backup")
    assert not backup.exists()

    # But file should have new content
    new_content = target.read_text()
    assert "NewClass" in new_content
    assert initial_content != new_content


def test_write_file_atomic_on_syntax_error(generator: CodeGenerator, temp_dir: Path):
    """Test write_file rolls back on syntax errors (should not happen)."""
    module_path = "test.module"
    target = temp_dir / "test" / "module" / "__init__.py"
    target.parent.mkdir(parents=True)

    # Write initial file
    initial_content = "# Initial content\n__all__ = []"
    target.write_text(initial_content)

    # Create invalid code (force syntax error)
    exports = [make_export("MyClass", module_path)]
    manifest = make_manifest(module_path, own_exports=exports)
    generator.generate(manifest)

    # Corrupt the code to force syntax error
    corrupted = GeneratedCode(
        content="def broken(\n",  # Missing closing paren
        manual_section="",
        managed_section="def broken(\n",
        export_count=1,
        hash="fake",
    )

    # Should raise SyntaxError
    with pytest.raises(SyntaxError) as exc:
        generator.write_file(module_path, corrupted)

    assert "Generated code has syntax errors" in str(exc.value)

    # Original file should be preserved
    assert target.read_text() == initial_content


# Validation tests


def test_validate_generated_valid_code(generator: CodeGenerator):
    """Test validation passes for valid code."""
    exports = [make_export("MyClass", "test.module")]
    manifest = make_manifest("test.module", own_exports=exports)
    code = generator.generate(manifest)

    errors = generator.validate_generated(code)
    assert errors == []


def test_validate_generated_syntax_error(generator: CodeGenerator):
    """Test validation catches syntax errors."""
    code = GeneratedCode(
        content="def broken(\n",
        manual_section="",
        managed_section="def broken(\n",
        export_count=0,
        hash="fake",
    )

    errors = generator.validate_generated(code)
    assert len(errors) > 0
    assert "Syntax error" in errors[0]


def test_validate_generated_missing_all(generator: CodeGenerator):
    """Test validation catches missing __all__."""
    code = GeneratedCode(
        content="# Valid Python but no __all__\npass\n",
        manual_section="",
        managed_section="pass\n",
        export_count=0,
        hash="fake",
    )

    errors = generator.validate_generated(code)
    assert any("__all__" in err for err in errors)


# validate_init_file tests


def test_validate_init_file_valid(temp_dir: Path):
    """Test validating a valid __init__.py file."""
    init_file = temp_dir / "test" / "__init__.py"
    init_file.parent.mkdir(parents=True)

    content = f"""from __future__ import annotations

{SENTINEL}
# Managed section

__all__ = ["MyClass"]
"""
    init_file.write_text(content)

    errors = validate_init_file(init_file)
    assert errors == []


def test_validate_init_file_missing(temp_dir: Path):
    """Test validating non-existent file."""
    init_file = temp_dir / "nonexistent" / "__init__.py"

    errors = validate_init_file(init_file)
    assert len(errors) > 0
    assert "does not exist" in errors[0]


def test_validate_init_file_syntax_error(temp_dir: Path):
    """Test validating file with syntax error."""
    init_file = temp_dir / "test" / "__init__.py"
    init_file.parent.mkdir(parents=True)

    init_file.write_text("def broken(\n")

    errors = validate_init_file(init_file)
    assert len(errors) > 0
    assert "Syntax error" in errors[0]


def test_validate_init_file_missing_all(temp_dir: Path):
    """Test validating file without __all__."""
    init_file = temp_dir / "test" / "__init__.py"
    init_file.parent.mkdir(parents=True)

    init_file.write_text("# Valid Python but no __all__\n")

    errors = validate_init_file(init_file)
    assert any("__all__" in err for err in errors)


# Import generation tests


def test_import_generation_grouping(generator: CodeGenerator):
    """Test imports are grouped by source module."""
    exports = [
        make_export("ClassA", "test.module", defined_in="test.module.sub1"),
        make_export("ClassB", "test.module", defined_in="test.module.sub1"),
        make_export("ClassC", "test.module", defined_in="test.module.sub2"),
    ]
    manifest = make_manifest("test.module", own_exports=exports)

    code = generator.generate(manifest)

    # Should have two import statements (one per source module)
    import_lines = [line for line in code.content.split("\n") if "from ." in line]
    assert len(import_lines) == 2

    # Should group ClassA and ClassB together
    assert any("ClassA" in line and "ClassB" in line for line in import_lines)


def test_import_generation_sorting(generator: CodeGenerator):
    """Test imports and __all__ are sorted."""
    exports = [
        make_export("Zebra", "test.module.sub"),
        make_export("Apple", "test.module.sub"),
        make_export("Banana", "test.module.sub"),
    ]
    manifest = make_manifest("test.module", own_exports=exports)

    code = generator.generate(manifest)

    # __all__ should be sorted
    all_section = code.content[code.content.index("__all__") :]
    assert all_section.index("Apple") < all_section.index("Banana")
    assert all_section.index("Banana") < all_section.index("Zebra")


# Edge cases


def test_generate_with_empty_manual_section(generator: CodeGenerator):
    """Test generating with no manual section."""
    exports = [make_export("MyClass", "test.module")]
    manifest = make_manifest("test.module", own_exports=exports)

    code = generator.generate(manifest)

    # Should start with sentinel
    assert code.content.startswith(SENTINEL)
    assert code.manual_section == ""


def test_generate_with_long_manual_section(generator: CodeGenerator, temp_dir: Path):
    """Test preserving long manual section."""
    module_path = "test.module"
    target = temp_dir / "test" / "module" / "__init__.py"
    target.parent.mkdir(parents=True)

    # Write file with long manual section
    manual_lines = [f"# Line {i}" for i in range(100)]
    manual_section = "\n".join(manual_lines)

    existing = f"{manual_section}\n\n{SENTINEL}\n__all__ = []"
    target.write_text(existing)

    # Generate new code
    exports = [make_export("NewClass", module_path)]
    manifest = make_manifest(module_path, own_exports=exports)
    code = generator.generate(manifest)

    # Should preserve all 100 lines
    assert code.manual_section.count("\n") >= 99


def test_generated_code_hash(generator: CodeGenerator):
    """Test generated code has correct hash."""
    exports = [make_export("MyClass", "test.module")]
    manifest = make_manifest("test.module", own_exports=exports)

    code = generator.generate(manifest)

    # Hash should be SHA-256 of content
    import hashlib

    expected_hash = hashlib.sha256(code.content.encode()).hexdigest()
    assert code.hash == expected_hash


# Error handling tests


def test_write_file_permission_error(generator: CodeGenerator, temp_dir: Path):
    """Test write_file handles permission errors gracefully."""
    module_path = "test.module"
    target = temp_dir / "test" / "module" / "__init__.py"
    target.parent.mkdir(parents=True)

    # Create file and make directory read-only (prevents writing/replacing)
    target.write_text("# Initial")
    target.parent.chmod(0o555)

    try:
        _cause_os_error(module_path, generator)
    finally:
        # Cleanup
        target.parent.chmod(0o755)


def _cause_os_error(module_path, generator):
    exports = [make_export("MyClass", module_path)]
    manifest = make_manifest(module_path, own_exports=exports)
    code = generator.generate(manifest)

    # Should raise OSError with helpful message (backup creation fails)
    with pytest.raises(OSError, match="Permission denied") as exc:
        generator.write_file(module_path, code)

    assert "chmod" in str(exc.value)


# Integration tests


def test_full_generation_workflow(generator: CodeGenerator, temp_dir: Path):
    """Test complete generation workflow."""
    module_path = "codeweaver.core.types"

    # Create manifest with mixed exports
    exports = [
        make_export("MyClass", module_path, MemberType.CLASS, "codeweaver.core.types.models"),
        make_export("MyEnum", module_path, MemberType.CLASS, "codeweaver.core.types.enums"),
        make_export("MyType", module_path, MemberType.TYPE_ALIAS, "codeweaver.core.types.aliases"),
        make_export(
            "CONSTANT", module_path, MemberType.CONSTANT, "codeweaver.core.types.constants"
        ),
    ]
    manifest = make_manifest(module_path, own_exports=exports)

    # Generate code
    code = generator.generate(manifest)

    # Validate
    errors = generator.validate_generated(code)
    assert errors == []

    # Write
    generator.write_file(module_path, code)

    # Verify file exists and is valid
    target = temp_dir / "codeweaver" / "core" / "types" / "__init__.py"
    assert target.exists()

    # Validate written file
    errors = validate_init_file(target)
    assert errors == []

    # Check content
    content = target.read_text()
    assert "MyClass" in content
    assert "MyEnum" in content
    assert "MyType" in content
    assert "CONSTANT" in content
    assert "TYPE_CHECKING" in content  # For MyType
    assert "__all__" in content


def test_regeneration_preserves_manual(generator: CodeGenerator, temp_dir: Path):
    """Test regenerating file preserves manual section."""
    module_path = "test.module"
    target = temp_dir / "test" / "module" / "__init__.py"
    target.parent.mkdir(parents=True)

    # First generation
    manual_code = """# User's custom imports
from typing import Protocol

# Custom constant
CUSTOM = 42
"""
    target.write_text(f"{manual_code}\n{SENTINEL}\n__all__ = []")

    _create_file("ClassV1", module_path, generator)
    _create_file("ClassV2", module_path, generator)
    # Manual section should be preserved across both regenerations
    final_content = target.read_text()
    assert "CUSTOM = 42" in final_content
    assert "ClassV2" in final_content
    assert "ClassV1" not in final_content  # Old export replaced


def _create_file(arg0, module_path, generator):
    # First regeneration
    exports_v1 = [make_export(arg0, module_path)]
    manifest_v1 = make_manifest(module_path, own_exports=exports_v1)
    code_v1 = generator.generate(manifest_v1)
    generator.write_file(module_path, code_v1)
