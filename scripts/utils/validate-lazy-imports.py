#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""
Validate lazy imports in CodeWeaver modules.

This script validates both:
1. LazyImport class usage (from codeweaver.common.utils.lazy_importer)
2. __init__.py style lazy imports (pydantic-style with __getattr__ and _dynamic_imports)

It checks for:
- Consistency between __all__ and _dynamic_imports
- Validity of import paths in _dynamic_imports
- Missing TYPE_CHECKING blocks for IDE support
- Broken or nonexistent imports
"""

import ast
import sys
from importlib import import_module
from pathlib import Path
from typing import Any


# Add src to path
REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))


class LazyImportValidator:
    """Validate lazy import patterns in CodeWeaver."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.info: list[str] = []

    def validate_module_lazy_imports(self, module_name: str) -> None:
        """
        Validate __init__.py style lazy imports in a module.

        Args:
            module_name: Full module name (e.g., 'codeweaver.config')
        """
        print(f"\n{'='*70}")
        print(f"Validating: {module_name}")
        print('='*70)

        try:
            module = import_module(module_name)
        except ImportError as e:
            self.errors.append(f"{module_name}: Cannot import module - {e}")
            print(f"❌ Cannot import {module_name}: {e}")
            return

        # Check for __all__
        __all__ = getattr(module, '__all__', None)
        if __all__ is None:
            self.warnings.append(f"{module_name}: No __all__ defined")
            print(f"⚠️  No __all__ defined")
            return

        # Check for _dynamic_imports
        _dynamic_imports = getattr(module, '_dynamic_imports', None)
        if _dynamic_imports is None:
            self.info.append(f"{module_name}: No _dynamic_imports (not using lazy import pattern)")
            print(f"ℹ️  No _dynamic_imports (not using lazy import pattern)")
            return

        # Check for __getattr__
        __getattr__ = getattr(module, '__getattr__', None)
        if __getattr__ is None:
            self.errors.append(f"{module_name}: Has _dynamic_imports but no __getattr__")
            print(f"❌ Has _dynamic_imports but no __getattr__")
            return

        print(f"✓ Has __all__, _dynamic_imports, and __getattr__")

        # Check consistency between __all__ and _dynamic_imports
        self._check_consistency(module_name, __all__, _dynamic_imports)

        # Check for TYPE_CHECKING block
        self._check_type_checking_block(module_name, module)

        # Validate import paths
        self._validate_import_paths(module_name, _dynamic_imports)

    def _check_consistency(
        self, module_name: str, __all__: tuple[str, ...], _dynamic_imports: dict[str, tuple[str, str]]
    ) -> None:
        """Check consistency between __all__ and _dynamic_imports."""
        print("\nChecking consistency...")

        # Items in __all__ but not in _dynamic_imports
        # (These should be either imported at module level or constants)
        missing_in_dynamic = [name for name in __all__ if name not in _dynamic_imports]
        if missing_in_dynamic:
            # Check if these are module-level constants or imports
            module = import_module(module_name)
            for name in missing_in_dynamic:
                if hasattr(module, name):
                    # It's defined in the module, could be a constant
                    value = getattr(module, name)
                    if not callable(value) and not isinstance(value, type):
                        self.info.append(
                            f"{module_name}: '{name}' in __all__ but not _dynamic_imports (appears to be a constant)"
                        )
                        print(f"ℹ️  '{name}' not in _dynamic_imports (constant: {type(value).__name__})")
                    else:
                        self.warnings.append(
                            f"{module_name}: '{name}' in __all__ but not in _dynamic_imports"
                        )
                        print(f"⚠️  '{name}' in __all__ but NOT in _dynamic_imports")
                else:
                    self.errors.append(
                        f"{module_name}: '{name}' in __all__ but not in _dynamic_imports and not found in module"
                    )
                    print(f"❌ '{name}' in __all__ but NOT in _dynamic_imports and not found in module")
        else:
            print("✓ All items in __all__ are in _dynamic_imports or are module-level")

        # Items in _dynamic_imports but not in __all__
        missing_in_all = [name for name in _dynamic_imports if name not in __all__]
        if missing_in_all:
            for name in missing_in_all:
                self.warnings.append(f"{module_name}: '{name}' in _dynamic_imports but not in __all__")
                print(f"⚠️  '{name}' in _dynamic_imports but NOT in __all__")
        else:
            print("✓ All items in _dynamic_imports are in __all__")

    def _check_type_checking_block(self, module_name: str, module: Any) -> None:
        """Check if module has TYPE_CHECKING block for IDE support."""
        print("\nChecking TYPE_CHECKING block...")

        # Read the module source
        module_file = Path(module.__file__)
        if not module_file.exists():
            print("⚠️  Cannot read module file")
            return

        source = module_file.read_text()

        # Parse the AST to check for TYPE_CHECKING
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            self.errors.append(f"{module_name}: Cannot parse source - {e}")
            print(f"❌ Cannot parse source: {e}")
            return

        # Look for TYPE_CHECKING import and usage
        has_type_checking_import = False
        has_type_checking_block = False

        for node in ast.walk(tree):
            # Check for "from typing import TYPE_CHECKING"
            if isinstance(node, ast.ImportFrom):
                if node.module == 'typing':
                    for alias in node.names:
                        if alias.name == 'TYPE_CHECKING':
                            has_type_checking_import = True

            # Check for "if TYPE_CHECKING:" block
            if isinstance(node, ast.If):
                if isinstance(node.test, ast.Name) and node.test.id == 'TYPE_CHECKING':
                    has_type_checking_block = True

        if not has_type_checking_import:
            self.warnings.append(f"{module_name}: No TYPE_CHECKING import (IDE may not resolve types)")
            print("⚠️  No TYPE_CHECKING import from typing")
        else:
            print("✓ Has TYPE_CHECKING import")

        if not has_type_checking_block:
            self.warnings.append(f"{module_name}: No TYPE_CHECKING block (IDE may not resolve types)")
            print("⚠️  No TYPE_CHECKING block (IDE may not resolve types)")
            print("   💡 Add a TYPE_CHECKING block with real imports for IDE support")
        else:
            print("✓ Has TYPE_CHECKING block")

    def _validate_import_paths(self, module_name: str, _dynamic_imports: dict[str, tuple[str, str]]) -> None:
        """Validate that import paths in _dynamic_imports are correct."""
        print("\nValidating import paths...")

        errors_found = False
        for name, (parent, submodule) in _dynamic_imports.items():
            # Construct full module path
            if submodule.startswith('.'):
                # Relative import
                full_module = f"{parent}{submodule}"
            else:
                # Absolute-style (parent.submodule)
                full_module = f"{parent}.{submodule}"

            try:
                # Try to import the module
                target_module = import_module(full_module)

                # Check if the attribute exists
                if not hasattr(target_module, name):
                    self.errors.append(
                        f"{module_name}: '{name}' -> {full_module}.{name} - Module exists but attribute doesn't"
                    )
                    print(f"❌ '{name}' -> {full_module} exists but has no attribute '{name}'")
                    errors_found = True
                else:
                    # Successful validation
                    pass  # Don't print success for each item to reduce noise

            except ImportError as e:
                self.errors.append(f"{module_name}: '{name}' -> Cannot import {full_module} - {e}")
                print(f"❌ '{name}' -> Cannot import {full_module}: {e}")
                errors_found = True

        if not errors_found:
            print(f"✓ All {len(_dynamic_imports)} import paths validated successfully")

    def print_summary(self) -> None:
        """Print validation summary."""
        print("\n" + "="*70)
        print("VALIDATION SUMMARY")
        print("="*70)

        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  • {error}")

        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  • {warning}")

        if self.info:
            print(f"\nℹ️  INFO ({len(self.info)}):")
            for info in self.info:
                print(f"  • {info}")

        if not self.errors and not self.warnings:
            print("\n✅ All validations passed!")

        print(f"\nTotal: {len(self.errors)} errors, {len(self.warnings)} warnings, {len(self.info)} info")

    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0


def main() -> int:
    """Main validation function."""
    print("="*70)
    print("CodeWeaver Lazy Import Validator")
    print("="*70)

    validator = LazyImportValidator()

    # Modules to check
    modules_to_check = [
        'codeweaver.core',
        'codeweaver.config',
        'codeweaver.common',
    ]

    for module_name in modules_to_check:
        validator.validate_module_lazy_imports(module_name)

    validator.print_summary()

    return 1 if validator.has_errors() else 0


if __name__ == '__main__':
    sys.exit(main())
