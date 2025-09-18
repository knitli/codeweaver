#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Simple import checker to identify missing dependencies."""

import sys


MODULES_TO_CHECK = (
    # Add the modules you want to check for importability
)

FAILED_IMPORTS = []
SUCCESSFUL_IMPORTS = []

for module in MODULES_TO_CHECK:
    try:
        __import__(module)
        SUCCESSFUL_IMPORTS.append(module)
        print(f"✅ {module}")
    except Exception as e:
        FAILED_IMPORTS.append((module, str(e)))
        print(f"❌ {module}: {e}")

print("\n📊 Summary:")
print(f"✅ Successful: {len(SUCCESSFUL_IMPORTS)}")
print(f"❌ Failed: {len(FAILED_IMPORTS)}")

if FAILED_IMPORTS:
    print("\n🔍 Failed imports:")
    for module, error in FAILED_IMPORTS:
        print(f"  - {module}: {error}")
    sys.exit(1)
else:
    print("\n🎉 All modules imported successfully!")
