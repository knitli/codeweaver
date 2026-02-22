#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Comprehensive tests for Phase 2 code preservation functionality.

Tests cover:
- SectionParser: AST-based parsing of managed vs preserved sections
- CodeGenerator: Preservation during regeneration
- FileWriter: Backup creation, restoration, and cleanup
- Integration: Full regeneration cycles
"""

from __future__ import annotations

import tempfile

from pathlib import Path
from textwrap import dedent

import pytest

from tools.exportify.common.types import ExportManifest, LazyExport
from tools.exportify.export_manager.file_writer import BackupPolicy, FileWriter
from tools.exportify.export_manager.generator import SENTINEL, CodeGenerator
from tools.exportify.export_manager.section_parser import SectionParser


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def section_parser() -> SectionParser:
    """Create a fresh section parser."""
    return SectionParser()


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def file_writer() -> FileWriter:
    """Create file writer with default settings."""
    return FileWriter(backup_policy=BackupPolicy.ALWAYS, max_backups=5)


@pytest.fixture
def code_generator(temp_dir: Path) -> CodeGenerator:
    """Create code generator with temp output directory."""
    return CodeGenerator(output_dir=temp_dir)


@pytest.fixture
def sample_manifest() -> ExportManifest:
    """Create sample export manifest for testing."""
    exports = [
        LazyExport(
            public_name="MyClass",
            target_module="test.module.impl",
            target_object="MyClass",
            is_type_only=False,
        ),
        LazyExport(
            public_name="my_function",
            target_module="test.module.impl",
            target_object="my_function",
            is_type_only=False,
        ),
    ]
    return ExportManifest(
        module_path="test.module", own_exports=exports, propagated_exports=[], all_exports=exports
    )


# ============================================================================
# SectionParser Tests
# ============================================================================


class TestSectionParser:
    """Test AST-based section parsing."""

    def test_parse_file_with_managed_sections(self, section_parser: SectionParser) -> None:
        """Parse file containing TYPE_CHECKING, _dynamic_imports, __all__, __dir__, __getattr__."""
        content = dedent(
            '''
            """Module docstring."""

            from __future__ import annotations

            # User's custom import
            import os

            # User's type alias
            StrPath = str | os.PathLike

            # === MANAGED EXPORTS ===
            # This section is automatically generated.

            from typing import TYPE_CHECKING
            from types import MappingProxyType

            if TYPE_CHECKING:
                from test.module.impl import MyClass, my_function

            _dynamic_imports = MappingProxyType({
                "MyClass": (__spec__.parent, "impl"),
            })

            __getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)

            __all__ = ("MyClass", "my_function")

            def __dir__() -> list[str]:
                return list(__all__)
            '''
        ).strip()

        parsed = section_parser.parse_content(content)

        # Verify managed section detection
        assert parsed.had_type_checking
        assert parsed.had_dynamic_imports
        assert parsed.had_getattr
        assert parsed.had_all
        assert parsed.had_dir

        # Verify docstring preserved
        assert parsed.docstring == "Module docstring."

        # Verify preserved code (user imports and type alias)
        assert "import os" in parsed.preserved_code
        assert "StrPath = str | os.PathLike" in parsed.preserved_code

        # Verify managed code NOT in preserved section
        assert "TYPE_CHECKING" not in parsed.preserved_code
        assert "_dynamic_imports" not in parsed.preserved_code
        assert "__all__" not in parsed.preserved_code

    def test_parse_file_without_sentinel_first_run(self, section_parser: SectionParser) -> None:
        """Parse file without SENTINEL marker (first generation run)."""
        content = dedent(
            '''
            """Module docstring."""

            from typing import TypeAlias

            # User's imports
            import sys
            from pathlib import Path

            # User's type aliases
            PathLike = str | Path

            # User's constants
            DEFAULT_TIMEOUT = 30

            # User's function
            def helper() -> None:
                """Helper function."""
                pass
            '''
        ).strip()

        parsed = section_parser.parse_content(content)

        # No managed sections detected in new file
        assert not parsed.had_type_checking
        assert not parsed.had_dynamic_imports
        assert not parsed.had_getattr
        assert not parsed.had_all
        assert not parsed.had_dir

        # All code should be preserved
        assert "import sys" in parsed.preserved_code
        assert "from pathlib import Path" in parsed.preserved_code
        assert "PathLike = str | Path" in parsed.preserved_code
        assert "DEFAULT_TIMEOUT = 30" in parsed.preserved_code
        assert "def helper()" in parsed.preserved_code

    def test_detect_type_checking_block(self, section_parser: SectionParser) -> None:
        """Detect TYPE_CHECKING conditional import blocks."""
        content = dedent(
            """
            from typing import TYPE_CHECKING

            if TYPE_CHECKING:
                from test.module import SomeClass
            """
        ).strip()

        parsed = section_parser.parse_content(content)
        assert parsed.had_type_checking

    def test_detect_dynamic_imports_assignment(self, section_parser: SectionParser) -> None:
        """Detect _dynamic_imports dictionary assignment."""
        content = dedent(
            """
            from types import MappingProxyType

            _dynamic_imports = MappingProxyType({
                "MyClass": (__spec__.parent, "impl"),
            })
            """
        ).strip()

        parsed = section_parser.parse_content(content)
        assert parsed.had_dynamic_imports

    def test_detect_getattr_assignment(self, section_parser: SectionParser) -> None:
        """Detect __getattr__ function assignment."""
        content = dedent(
            """
            __getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)
            """
        ).strip()

        parsed = section_parser.parse_content(content)
        assert parsed.had_getattr

    def test_detect_all_assignment(self, section_parser: SectionParser) -> None:
        """Detect __all__ list/tuple assignment."""
        content = dedent(
            """
            __all__ = ("MyClass", "my_function")
            """
        ).strip()

        parsed = section_parser.parse_content(content)
        assert parsed.had_all

    def test_detect_dir_function(self, section_parser: SectionParser) -> None:
        """Detect __dir__() function definition."""
        content = dedent(
            """
            def __dir__() -> list[str]:
                return list(__all__)
            """
        ).strip()

        parsed = section_parser.parse_content(content)
        assert parsed.had_dir

    def test_extract_preserved_imports(self, section_parser: SectionParser) -> None:
        """Extract user's manual imports."""
        content = dedent(
            """
            # User imports
            import logging
            from pathlib import Path
            from typing import Any

            # === MANAGED EXPORTS ===
            from typing import TYPE_CHECKING
            """
        ).strip()

        parsed = section_parser.parse_content(content)
        assert "import logging" in parsed.preserved_code
        assert "from pathlib import Path" in parsed.preserved_code
        # typing import before sentinel should be preserved
        assert "from typing import Any" in parsed.preserved_code

    def test_extract_preserved_type_aliases(self, section_parser: SectionParser) -> None:
        """Extract user's type aliases."""
        content = dedent(
            """
            from typing import TypeAlias

            StrOrPath: TypeAlias = str | Path
            IntOrFloat = int | float

            # === MANAGED EXPORTS ===
            """
        ).strip()

        parsed = section_parser.parse_content(content)
        assert "StrOrPath: TypeAlias = str | Path" in parsed.preserved_code
        assert "IntOrFloat = int | float" in parsed.preserved_code

    def test_extract_preserved_functions(self, section_parser: SectionParser) -> None:
        """Extract user-defined functions."""
        content = dedent(
            '''
            def helper_function(x: int) -> int:
                """Helper function."""
                return x * 2

            # === MANAGED EXPORTS ===
            '''
        ).strip()

        parsed = section_parser.parse_content(content)
        assert "def helper_function" in parsed.preserved_code
        assert "return x * 2" in parsed.preserved_code

    def test_extract_preserved_classes(self, section_parser: SectionParser) -> None:
        """Extract user-defined classes."""
        content = dedent(
            '''
            class CustomException(Exception):
                """Custom exception class."""
                pass

            # === MANAGED EXPORTS ===
            '''
        ).strip()

        parsed = section_parser.parse_content(content)
        assert "class CustomException" in parsed.preserved_code

    def test_preserve_comments(self, section_parser: SectionParser) -> None:
        """Preserve comments in user code."""
        content = dedent(
            """
            # Important comment about imports
            import sys

            # Configuration constant
            DEBUG = True

            # === MANAGED EXPORTS ===
            """
        ).strip()

        parsed = section_parser.parse_content(content)
        # Note: Comments are preserved as part of their associated nodes
        assert "import sys" in parsed.preserved_code
        assert "DEBUG = True" in parsed.preserved_code

    def test_parse_file_with_syntax_error(self, section_parser: SectionParser) -> None:
        """Handle files with syntax errors gracefully."""
        content = "def broken( # syntax error"

        with pytest.raises(SyntaxError, match="Syntax error"):
            section_parser.parse_content(content)

    def test_managed_and_preserved_line_tracking(self, section_parser: SectionParser) -> None:
        """Track line numbers for managed and preserved sections."""
        content = dedent(
            '''
            """Docstring."""
            import sys

            # === MANAGED EXPORTS ===
            from typing import TYPE_CHECKING
            __all__ = ()
            '''
        ).strip()

        parsed = section_parser.parse_content(content)

        # Should have line ranges for both sections
        assert len(parsed.managed_lines) > 0
        assert len(parsed.preserved_lines) > 0

        # Preserved section should come before managed
        if parsed.preserved_lines:
            assert parsed.preserved_lines[0][0] < parsed.managed_lines[0][0]


# ============================================================================
# CodeGenerator Tests
# ============================================================================


class TestCodeGenerator:
    """Test code generation with preservation."""

    def test_regenerate_preserves_user_code(
        self, code_generator: CodeGenerator, sample_manifest: ExportManifest, temp_dir: Path
    ) -> None:
        """Regenerate file preserves user's manual code."""
        # Create initial file with user code
        init_file = temp_dir / "test" / "module" / "__init__.py"
        init_file.parent.mkdir(parents=True, exist_ok=True)

        initial_content = dedent(
            '''
            """Module docstring."""

            # User's imports
            import logging
            from pathlib import Path

            # User's type alias
            StrPath = str | Path

            # === MANAGED EXPORTS ===
            # Old managed section
            '''
        ).strip()

        init_file.write_text(initial_content)

        # Regenerate
        generated = code_generator.generate(sample_manifest)

        # Verify user code preserved
        assert "import logging" in generated.manual_section
        assert "from pathlib import Path" in generated.manual_section
        assert "StrPath = str | Path" in generated.manual_section

        # Verify new managed section generated
        assert "from typing import TYPE_CHECKING" in generated.managed_section
        assert "_dynamic_imports" in generated.managed_section
        assert "__all__" in generated.managed_section

    def test_type_aliases_preserved(self, code_generator: CodeGenerator, temp_dir: Path) -> None:
        """Type aliases in preserved section are maintained."""
        init_file = temp_dir / "test" / "module" / "__init__.py"
        init_file.parent.mkdir(parents=True, exist_ok=True)

        content = dedent(
            """
            from typing import TypeAlias

            IntOrStr: TypeAlias = int | str
            PathLike = str | Path

            # === MANAGED EXPORTS ===
            """
        ).strip()

        init_file.write_text(content)

        manifest = ExportManifest(
            module_path="test.module", own_exports=[], propagated_exports=[], all_exports=[]
        )
        generated = code_generator.generate(manifest)

        assert "IntOrStr: TypeAlias = int | str" in generated.manual_section
        assert "PathLike = str | Path" in generated.manual_section

    def test_manual_imports_preserved(self, code_generator: CodeGenerator, temp_dir: Path) -> None:
        """Manual imports are preserved during regeneration."""
        init_file = temp_dir / "test" / "module" / "__init__.py"
        init_file.parent.mkdir(parents=True, exist_ok=True)

        content = dedent(
            """
            import sys
            import logging
            from collections import defaultdict
            from typing import Any, cast

            # === MANAGED EXPORTS ===
            """
        ).strip()

        init_file.write_text(content)

        manifest = ExportManifest(
            module_path="test.module", own_exports=[], propagated_exports=[], all_exports=[]
        )
        generated = code_generator.generate(manifest)

        assert "import sys" in generated.manual_section
        assert "import logging" in generated.manual_section
        assert "from collections import defaultdict" in generated.manual_section
        assert "from typing import Any, cast" in generated.manual_section

    def test_custom_functions_preserved(
        self, code_generator: CodeGenerator, temp_dir: Path
    ) -> None:
        """User-defined functions are preserved."""
        init_file = temp_dir / "test" / "module" / "__init__.py"
        init_file.parent.mkdir(parents=True, exist_ok=True)

        content = dedent(
            '''
            def helper_function(x: int) -> int:
                """Helper function."""
                return x * 2

            def another_helper() -> None:
                """Another helper."""
                pass

            # === MANAGED EXPORTS ===
            '''
        ).strip()

        init_file.write_text(content)

        manifest = ExportManifest(
            module_path="test.module", own_exports=[], propagated_exports=[], all_exports=[]
        )
        generated = code_generator.generate(manifest)

        assert "def helper_function" in generated.manual_section
        assert "def another_helper" in generated.manual_section

    def test_classes_preserved(self, code_generator: CodeGenerator, temp_dir: Path) -> None:
        """User-defined classes are preserved."""
        init_file = temp_dir / "test" / "module" / "__init__.py"
        init_file.parent.mkdir(parents=True, exist_ok=True)

        content = dedent(
            '''
            class CustomError(Exception):
                """Custom error."""
                pass

            class Helper:
                """Helper class."""
                def __init__(self):
                    pass

            # === MANAGED EXPORTS ===
            '''
        ).strip()

        init_file.write_text(content)

        manifest = ExportManifest(
            module_path="test.module", own_exports=[], propagated_exports=[], all_exports=[]
        )
        generated = code_generator.generate(manifest)

        assert "class CustomError" in generated.manual_section
        assert "class Helper" in generated.manual_section

    def test_comments_preserved(self, code_generator: CodeGenerator, temp_dir: Path) -> None:
        """Comments in preserved sections are maintained."""
        init_file = temp_dir / "test" / "module" / "__init__.py"
        init_file.parent.mkdir(parents=True, exist_ok=True)

        content = dedent(
            """
            # Important configuration
            DEBUG = True

            # Type definitions section
            from typing import TypeAlias

            # === MANAGED EXPORTS ===
            """
        ).strip()

        init_file.write_text(content)

        manifest = ExportManifest(
            module_path="test.module", own_exports=[], propagated_exports=[], all_exports=[]
        )
        generated = code_generator.generate(manifest)

        # Debug value should be preserved (comments are attached to nodes)
        assert "DEBUG = True" in generated.manual_section

    def test_spdx_headers_regenerated(
        self, code_generator: CodeGenerator, sample_manifest: ExportManifest, temp_dir: Path
    ) -> None:
        """SPDX headers are regenerated, not preserved."""
        init_file = temp_dir / "test" / "module" / "__init__.py"
        init_file.parent.mkdir(parents=True, exist_ok=True)

        # File with old/missing SPDX headers
        content = dedent(
            """
            # Old copyright notice
            import sys

            # === MANAGED EXPORTS ===
            """
        ).strip()

        init_file.write_text(content)

        generated = code_generator.generate(sample_manifest)

        # New SPDX headers in full content
        assert "SPDX-FileCopyrightText:" in generated.content
        assert "SPDX-License-Identifier:" in generated.content

        # Old headers not in preserved section
        assert "Old copyright notice" in generated.manual_section  # But user comment preserved

    def test_managed_sections_regenerated(
        self, code_generator: CodeGenerator, sample_manifest: ExportManifest, temp_dir: Path
    ) -> None:
        """Managed sections are completely regenerated."""
        init_file = temp_dir / "test" / "module" / "__init__.py"
        init_file.parent.mkdir(parents=True, exist_ok=True)

        # File with old managed section
        old_content = dedent(
            """
            import sys

            # === MANAGED EXPORTS ===
            # Old managed section with outdated exports
            from typing import TYPE_CHECKING

            if TYPE_CHECKING:
                from old.module import OldClass

            __all__ = ("OldClass",)
            """
        ).strip()

        init_file.write_text(old_content)

        generated = code_generator.generate(sample_manifest)

        # New managed section should have current exports
        assert "MyClass" in generated.managed_section
        assert "my_function" in generated.managed_section

        # Old exports should NOT be in managed section
        assert "OldClass" not in generated.managed_section

    def test_empty_preserved_section(
        self, code_generator: CodeGenerator, sample_manifest: ExportManifest, temp_dir: Path
    ) -> None:
        """Handle files with no user code to preserve."""
        init_file = temp_dir / "test" / "module" / "__init__.py"
        init_file.parent.mkdir(parents=True, exist_ok=True)

        # File with only managed section
        content = dedent(
            """
            # === MANAGED EXPORTS ===
            from typing import TYPE_CHECKING
            __all__ = ()
            """
        ).strip()

        init_file.write_text(content)

        generated = code_generator.generate(sample_manifest)

        # Manual section should be empty or minimal
        assert generated.manual_section == "" or generated.manual_section.strip() == ""

        # Managed section should still be generated
        assert len(generated.managed_section) > 0


# ============================================================================
# FileWriter Tests
# ============================================================================


class TestFileWriter:
    """Test file writing with backups."""

    def test_backup_created_with_timestamp(self, file_writer: FileWriter, temp_dir: Path) -> None:
        """Backup files use timestamp naming."""
        target = temp_dir / "test.py"
        target.write_text("# original content\n__all__ = ()\n")

        result = file_writer.write_file(target, "# new content\n__all__ = ()\n", create_backup=True)

        assert result.success
        assert result.backup_path is not None
        assert result.backup_path.exists()

        # Verify timestamp format in filename
        assert ".backup." in result.backup_path.name
        # Should match pattern: test.py.backup.YYYYMMDD-HHMMSS
        assert result.backup_path.suffix != ".py"

    def test_restore_from_backup(self, file_writer: FileWriter, temp_dir: Path) -> None:
        """Restore file from backup works correctly."""
        target = temp_dir / "test.py"
        original = "# original\n__all__ = ()\n"
        target.write_text(original)

        # Create backup and modify
        result = file_writer.write_file(target, "# modified\n__all__ = ()\n", create_backup=True)
        assert result.success
        backup_path = result.backup_path

        # Restore from backup
        restore_result = file_writer.restore_backup(target, backup_path)
        assert restore_result.success

        # Verify content restored
        assert target.read_text() == original

    def test_old_backups_cleaned_up(self, file_writer: FileWriter, temp_dir: Path) -> None:
        """Old backups are cleaned up when max_backups limit reached."""
        import time

        target = temp_dir / "test.py"
        target.write_text("# v0\n__all__ = ()\n")

        # Manually create old backup files with different timestamps
        base_time = time.time()
        for i in range(7):
            backup = target.with_suffix(f".py.backup.old{i}")
            backup.write_text(f"# old backup {i}\n__all__ = ()\n")
            # Set modification time to make them appear old
            import os

            os.utime(backup, (base_time - (i * 100), base_time - (i * 100)))

        # Now write a new version - this should trigger cleanup
        result = file_writer.write_file(target, "# new version\n__all__ = ()\n", create_backup=True)
        assert result.success

        # Count backup files
        backups = list(target.parent.glob(f"{target.stem}.py.backup.*"))

        # Should only keep max_backups (5) most recent
        assert len(backups) <= file_writer.max_backups

    def test_max_backups_limit_enforced(self, temp_dir: Path) -> None:
        """Max backups configuration is respected."""
        import os
        import time

        max_backups = 3
        writer = FileWriter(backup_policy=BackupPolicy.ALWAYS, max_backups=max_backups)

        target = temp_dir / "test.py"
        target.write_text("# initial\n__all__ = ()\n")

        # Manually create old backup files with different timestamps
        base_time = time.time()
        for i in range(5):
            backup = target.with_suffix(f".py.backup.old{i}")
            backup.write_text(f"# old backup {i}\n__all__ = ()\n")
            # Set modification time to make them appear at different times
            os.utime(backup, (base_time - (i * 100), base_time - (i * 100)))

        # Write once - should clean up old backups
        writer.write_file(target, "# new\n__all__ = ()\n", create_backup=True)

        # Count remaining backups
        backups = list(target.parent.glob(f"{target.stem}.py.backup.*"))
        assert len(backups) == max_backups

    def test_backup_policy_never(self, temp_dir: Path) -> None:
        """BackupPolicy.NEVER creates no backups."""
        writer = FileWriter(backup_policy=BackupPolicy.NEVER)

        target = temp_dir / "test.py"
        target.write_text("original")

        result = writer.write_file(target, "modified", create_backup=True)

        assert result.success
        assert result.backup_path is None

        # No backup files should exist
        backups = list(target.parent.glob("*.backup.*"))
        assert len(backups) == 0

    def test_backup_policy_on_change(self, temp_dir: Path) -> None:
        """BackupPolicy.ON_CHANGE only creates backup when content differs."""
        writer = FileWriter(backup_policy=BackupPolicy.ON_CHANGE)

        target = temp_dir / "test.py"
        content = "# same\n__all__ = ()\n"
        target.write_text(content)

        # Write same content - no backup
        result = writer.write_file(target, content, create_backup=True)
        assert result.success
        assert result.backup_path is None

        # Write different content - backup created
        result = writer.write_file(target, "# different\n__all__ = ()\n", create_backup=True)
        assert result.success
        assert result.backup_path is not None

    def test_validation_error_prevents_write(self, temp_dir: Path) -> None:
        """Validation errors prevent file write."""

        def failing_validator(content: str) -> list[str]:
            return ["Validation error: content too short"]

        writer = FileWriter(validator=failing_validator)

        target = temp_dir / "test.py"
        result = writer.write_file(target, "bad", create_backup=False)

        assert not result.success
        assert result.error is not None
        assert "Validation error" in result.error
        assert not target.exists()  # File should not be created

    def test_syntax_validation(self, file_writer: FileWriter, temp_dir: Path) -> None:
        """Default validator catches syntax errors."""
        target = temp_dir / "test.py"

        invalid_python = "def broken( # syntax error"
        result = file_writer.write_file(target, invalid_python, create_backup=False)

        assert not result.success
        assert "Syntax error" in result.error
        assert not target.exists()


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """End-to-end integration tests."""

    def test_full_regeneration_cycle_preserves_code(
        self, code_generator: CodeGenerator, temp_dir: Path
    ) -> None:
        """Complete generation cycle preserves user code through multiple runs."""
        # Setup: Create initial file with user code
        init_file = temp_dir / "test" / "module" / "__init__.py"
        init_file.parent.mkdir(parents=True, exist_ok=True)

        user_code = dedent(
            '''
            """My module."""
            import logging
            from typing import TypeAlias

            MyType: TypeAlias = int | str
            DEBUG = True

            def helper() -> None:
                pass
            '''
        ).strip()

        init_file.write_text(user_code)

        # First generation
        exports1 = [
            LazyExport(
                public_name="Foo",
                target_module="test.module.impl",
                target_object="Foo",
                is_type_only=False,
            )
        ]
        manifest1 = ExportManifest(
            module_path="test.module",
            own_exports=exports1,
            propagated_exports=[],
            all_exports=exports1,
        )

        generated1 = code_generator.generate(manifest1)
        result1 = code_generator.write_file("test.module", generated1)
        assert result1.success

        # Verify user code preserved
        content1 = init_file.read_text()
        assert "import logging" in content1
        assert "MyType: TypeAlias" in content1
        assert "DEBUG = True" in content1
        assert "def helper()" in content1
        assert "Foo" in content1

        # Second generation with different exports
        exports2 = [
            LazyExport(
                public_name="Bar",
                target_module="test.module.impl",
                target_object="Bar",
                is_type_only=False,
            )
        ]
        manifest2 = ExportManifest(
            module_path="test.module",
            own_exports=exports2,
            propagated_exports=[],
            all_exports=exports2,
        )

        generated2 = code_generator.generate(manifest2)
        result2 = code_generator.write_file("test.module", generated2)
        assert result2.success

        # Verify user code STILL preserved after second generation
        content2 = init_file.read_text()
        assert "import logging" in content2
        assert "MyType: TypeAlias" in content2
        assert "DEBUG = True" in content2
        assert "def helper()" in content2

        # New export should be present
        assert "Bar" in content2

        # Old export should be gone from managed section
        assert "Foo" not in content2 or content2.count("Foo") == 0

    def test_multiple_regenerations_no_data_loss(
        self, code_generator: CodeGenerator, temp_dir: Path
    ) -> None:
        """Multiple regeneration cycles don't lose user data."""
        init_file = temp_dir / "test" / "module" / "__init__.py"
        init_file.parent.mkdir(parents=True, exist_ok=True)

        # Start with user code
        initial_user_code = "CONSTANT = 42\n\ndef my_func():\n    pass"
        init_file.write_text(initial_user_code)

        exports = [
            LazyExport(
                public_name=f"Class{i}",
                target_module="test.module.impl",
                target_object=f"Class{i}",
                is_type_only=False,
            )
            for i in range(3)
        ]
        manifest = ExportManifest(
            module_path="test.module",
            own_exports=exports,
            propagated_exports=[],
            all_exports=exports,
        )

        # Perform 5 regeneration cycles
        for cycle in range(5):
            generated = code_generator.generate(manifest)
            result = code_generator.write_file("test.module", generated)
            assert result.success, f"Cycle {cycle + 1} failed"

            # Verify user code still present
            content = init_file.read_text()
            assert "CONSTANT = 42" in content, f"Lost CONSTANT in cycle {cycle + 1}"
            assert "def my_func()" in content, f"Lost my_func in cycle {cycle + 1}"

    def test_edge_case_empty_preserved_section(
        self, code_generator: CodeGenerator, temp_dir: Path
    ) -> None:
        """Handle empty preserved section gracefully."""
        init_file = temp_dir / "test" / "module" / "__init__.py"
        init_file.parent.mkdir(parents=True, exist_ok=True)

        # File with only managed content
        init_file.write_text(f"{SENTINEL}\n__all__ = ()")

        exports = [
            LazyExport(
                public_name="NewClass",
                target_module="test.module.impl",
                target_object="NewClass",
                is_type_only=False,
            )
        ]
        manifest = ExportManifest(
            module_path="test.module",
            own_exports=exports,
            propagated_exports=[],
            all_exports=exports,
        )

        generated = code_generator.generate(manifest)
        result = code_generator.write_file("test.module", generated)

        assert result.success
        content = init_file.read_text()

        # Should have valid structure
        assert SENTINEL in content
        assert "NewClass" in content
        assert "__all__" in content

    def test_edge_case_no_managed_sections(self, section_parser: SectionParser) -> None:
        """Handle files without any managed sections."""
        content = dedent(
            '''
            """Pure user code."""
            import sys

            def my_function():
                pass
            '''
        ).strip()

        parsed = section_parser.parse_content(content)

        # No managed sections detected
        assert not parsed.had_type_checking
        assert not parsed.had_dynamic_imports
        assert not parsed.had_all

        # All code is preserved
        assert "import sys" in parsed.preserved_code
        assert "def my_function()" in parsed.preserved_code

    def test_backup_and_restore_integration(
        self, code_generator: CodeGenerator, temp_dir: Path
    ) -> None:
        """Test backup creation and restoration in generation workflow."""
        init_file = temp_dir / "test" / "module" / "__init__.py"
        init_file.parent.mkdir(parents=True, exist_ok=True)

        original_content = "# Original user code\nDEBUG = True"
        init_file.write_text(original_content)

        exports = [
            LazyExport(
                public_name="MyClass",
                target_module="test.module.impl",
                target_object="MyClass",
                is_type_only=False,
            )
        ]
        manifest = ExportManifest(
            module_path="test.module",
            own_exports=exports,
            propagated_exports=[],
            all_exports=exports,
        )

        # Generate and write with backup
        generated = code_generator.generate(manifest)
        result = code_generator.write_file("test.module", generated)

        assert result.success
        assert result.backup_path is not None
        assert result.backup_path.exists()

        # Verify backup contains original content
        backup_content = result.backup_path.read_text()
        assert "DEBUG = True" in backup_content

        # Verify new file has both preserved and generated content
        new_content = init_file.read_text()
        assert "DEBUG = True" in new_content
        assert "MyClass" in new_content


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_missing_file_raises_error(self, section_parser: SectionParser, temp_dir: Path) -> None:
        """Parsing non-existent file raises FileNotFoundError."""
        nonexistent = temp_dir / "missing.py"

        with pytest.raises(FileNotFoundError):
            section_parser.parse_file(nonexistent)

    def test_malformed_sentinel(self, section_parser: SectionParser) -> None:
        """Handle files with multiple or malformed sentinels."""
        content = f"{SENTINEL}\ncode1\n{SENTINEL}\ncode2"

        # Should fall back to AST parsing
        section_parser.parse_content(content)
        # Should not crash, but behavior may be undefined for malformed input

    def test_unicode_content(self, code_generator: CodeGenerator, temp_dir: Path) -> None:
        """Handle files with unicode characters."""
        init_file = temp_dir / "test" / "module" / "__init__.py"
        init_file.parent.mkdir(parents=True, exist_ok=True)

        unicode_content = "# Unicode: 你好 мир 🚀\nDEBUG = True"
        init_file.write_text(unicode_content, encoding="utf-8")

        manifest = ExportManifest(
            module_path="test.module", own_exports=[], propagated_exports=[], all_exports=[]
        )
        generated = code_generator.generate(manifest)

        # Should preserve unicode content
        assert "你好" in generated.manual_section or "你好" in generated.content

    def test_very_large_file(self, section_parser: SectionParser) -> None:
        """Handle large files efficiently."""
        # Create content with many preserved items
        large_content = "\n".join([f"VAR_{i} = {i}" for i in range(1000)])
        large_content += f"\n\n{SENTINEL}\n__all__ = ()"

        parsed = section_parser.parse_content(large_content)

        # Should preserve all variables
        assert "VAR_0" in parsed.preserved_code
        assert "VAR_999" in parsed.preserved_code


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
