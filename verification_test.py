#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Verification test showing that the identified field is the source and how to fix it."""

import warnings
from typing import Annotated
from pydantic import Field, BaseModel

print("="*70)
print("VERIFICATION: Demonstrating the issue and solution")
print("="*70)

# PROBLEMATIC PATTERN (as found in NodeTypeDTO.subtypes)
print("\n1. PROBLEMATIC PATTERN (current code):")
print("-" * 70)
code_bad = '''
class NodeTypeDTOBad(BaseModel):
    subtypes: (
        Annotated[
            list[str],
            Field(
                description="List of subtype objects.",
                default_factory=list,  # ⚠️ This causes the warning
            ),
        ]
        | None
    ) = None
'''
print(code_bad)

with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    exec(code_bad, {'BaseModel': BaseModel, 'Annotated': Annotated, 'Field': Field, 'list': list})
    
    if w:
        print("⚠️  WARNING TRIGGERED:")
        for warning in w:
            print(f"   {warning.message}")
    else:
        print("✓ No warnings")

# SOLUTION 1: Remove default_factory (already has = None)
print("\n2. SOLUTION 1: Remove default_factory (simplest fix):")
print("-" * 70)
code_solution1 = '''
class NodeTypeDTOFixed1(BaseModel):
    subtypes: (
        Annotated[
            list[str],
            Field(description="List of subtype objects."),
        ]
        | None
    ) = None  # This is already a valid default
'''
print(code_solution1)

with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    exec(code_solution1, {'BaseModel': BaseModel, 'Annotated': Annotated, 'Field': Field, 'list': list})
    
    if w:
        print("⚠️  WARNING TRIGGERED")
    else:
        print("✓ No warnings - FIXED!")

# SOLUTION 2: Use Field assignment syntax
print("\n3. SOLUTION 2: Use Field assignment syntax:")
print("-" * 70)
code_solution2 = '''
class NodeTypeDTOFixed2(BaseModel):
    subtypes: Annotated[
        list[str] | None,
        Field(description="List of subtype objects."),
    ] = Field(default_factory=list)
'''
print(code_solution2)

with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    exec(code_solution2, {'BaseModel': BaseModel, 'Annotated': Annotated, 'Field': Field, 'list': list})
    
    if w:
        print("⚠️  WARNING TRIGGERED")
    else:
        print("✓ No warnings - FIXED!")

# SOLUTION 3: Don't use union (if None is not needed)
print("\n4. SOLUTION 3: Remove union if None is not semantically needed:")
print("-" * 70)
code_solution3 = '''
class NodeTypeDTOFixed3(BaseModel):
    subtypes: Annotated[
        list[str],
        Field(
            default_factory=list,
            description="List of subtype objects.",
        ),
    ]
'''
print(code_solution3)

with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    exec(code_solution3, {'BaseModel': BaseModel, 'Annotated': Annotated, 'Field': Field, 'list': list})
    
    if w:
        print("⚠️  WARNING TRIGGERED")
    else:
        print("✓ No warnings - FIXED!")

print("\n" + "="*70)
print("CONCLUSION")
print("="*70)
print("""
The issue is in src/codeweaver/semantic/types.py, line 109-118.
The field NodeTypeDTO.subtypes uses the problematic pattern.

Recommended fix: SOLUTION 1 (simplest)
- Remove 'default_factory=list' from the Field() call
- Keep the existing '= None' default value
- This maintains current behavior without the warning
""")
