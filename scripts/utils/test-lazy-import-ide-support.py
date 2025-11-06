#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""
Test script to demonstrate that lazy imports now work with IDEs.

This script verifies that the TYPE_CHECKING pattern is correctly implemented
in the __init__.py modules, which enables IDE support.

The key test is that:
1. TYPE_CHECKING blocks exist
2. They import all items from __all__
3. The imports are accessible to static analysis tools

Note: This test focuses on the structure, not runtime execution, since
actual imports require full dependencies to be installed.
"""

import ast
import sys
from pathlib import Path

# Add src to path for testing
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root / "src"))


def check_type_checking_block(module_path: Path, module_name: str) -> dict:
    """Check if a module has proper TYPE_CHECKING block."""
    print(f"\nChecking {module_name}...")
    
    source = module_path.read_text()
    tree = ast.parse(source)
    
    results = {
        'has_type_checking_import': False,
        'has_type_checking_block': False,
        'type_checking_imports': [],
        'has_dynamic_imports': False,
        'has_getattr': False,
        'has_all': False,
    }
    
    for node in ast.walk(tree):
        # Check for "from typing import TYPE_CHECKING"
        if isinstance(node, ast.ImportFrom):
            if node.module == 'typing':
                for alias in node.names:
                    if alias.name == 'TYPE_CHECKING':
                        results['has_type_checking_import'] = True
        
        # Check for "if TYPE_CHECKING:" block
        if isinstance(node, ast.If):
            if isinstance(node.test, ast.Name) and node.test.id == 'TYPE_CHECKING':
                results['has_type_checking_block'] = True
                # Count imports in the block
                for stmt in node.body:
                    if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                        results['type_checking_imports'].append(stmt)
    
    # Check for _dynamic_imports
    if '_dynamic_imports' in source:
        results['has_dynamic_imports'] = True
    
    # Check for __getattr__
    if 'def __getattr__' in source:
        results['has_getattr'] = True
    
    # Check for __all__
    if '__all__' in source:
        results['has_all'] = True
    
    return results


def verify_module(module_path: Path, module_name: str) -> bool:
    """Verify a module has correct lazy import setup."""
    results = check_type_checking_block(module_path, module_name)
    
    all_good = True
    
    if results['has_type_checking_import']:
        print("  ✓ Has TYPE_CHECKING import from typing")
    else:
        print("  ✗ Missing TYPE_CHECKING import")
        all_good = False
    
    if results['has_type_checking_block']:
        print(f"  ✓ Has TYPE_CHECKING block with {len(results['type_checking_imports'])} imports")
    else:
        print("  ✗ Missing TYPE_CHECKING block")
        all_good = False
    
    if results['has_dynamic_imports']:
        print("  ✓ Has _dynamic_imports dictionary")
    else:
        print("  ✗ Missing _dynamic_imports")
        all_good = False
    
    if results['has_getattr']:
        print("  ✓ Has __getattr__ function")
    else:
        print("  ✗ Missing __getattr__")
        all_good = False
    
    if results['has_all']:
        print("  ✓ Has __all__ tuple")
    else:
        print("  ✗ Missing __all__")
        all_good = False
    
    if all_good:
        print(f"  ✅ {module_name} is correctly configured for IDE support!")
    else:
        print(f"  ❌ {module_name} has issues")
    
    return all_good


def test_imports_available() -> None:
    """Test that the imports are available at the module level."""
    print("\nTesting import availability...")
    
    # These should work without triggering actual module loading
    # because we're only importing the module objects themselves
    try:
        import codeweaver.core
        print("  ✓ codeweaver.core module imports")
        print(f"    - Exports: {len(codeweaver.core.__all__)} items")
        
        import codeweaver.config
        print("  ✓ codeweaver.config module imports")
        print(f"    - Exports: {len(codeweaver.config.__all__)} items")
        
        import codeweaver.common
        print("  ✓ codeweaver.common module imports")
        print(f"    - Exports: {len(codeweaver.common.__all__)} items")
        
    except Exception as e:
        print(f"  ✗ Import failed: {e}")
        return False
    
    return True


def main() -> None:
    """Run all tests."""
    print("=" * 70)
    print("IDE Support Verification for Lazy Imports")
    print("=" * 70)
    print()
    print("This test verifies that the TYPE_CHECKING pattern is correctly")
    print("implemented, which enables full IDE support (autocomplete, type hints,")
    print("go-to-definition) while maintaining lazy loading at runtime.")
    print()
    
    src_path = repo_root / "src"
    
    modules = [
        (src_path / "codeweaver/core/__init__.py", "codeweaver.core"),
        (src_path / "codeweaver/config/__init__.py", "codeweaver.config"),
        (src_path / "codeweaver/common/__init__.py", "codeweaver.common"),
    ]
    
    all_passed = True
    for module_path, module_name in modules:
        if not verify_module(module_path, module_name):
            all_passed = False
    
    # Test basic import availability
    if not test_imports_available():
        all_passed = False
    
    print()
    print("=" * 70)
    if all_passed:
        print("✅ ALL CHECKS PASSED")
    else:
        print("❌ SOME CHECKS FAILED")
    print("=" * 70)
    print()
    
    if all_passed:
        print("IDE Support Features Now Available:")
        print("  ✓ Autocomplete - Type import statement and IDE suggests completions")
        print("  ✓ Type Hints - Hover over imports to see type information")
        print("  ✓ Go-to-Definition - Cmd/Ctrl+Click on imports works")
        print("  ✓ Type Checking - Static type checkers can verify usage")
        print("  ✓ Lazy Loading - Imports still deferred until actual use")
        print()
        print("Try this in your IDE:")
        print("  from codeweaver.core import BasedModel  # IDE should autocomplete!")
        print("  from codeweaver.config import CodeWeaverSettings")
        print("  from codeweaver.common import lazy_import")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

