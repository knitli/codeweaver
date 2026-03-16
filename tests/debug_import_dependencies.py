# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

import os
import sys


# Add src to sys.path explicitly
sys.path.insert(0, os.path.abspath("src"))

try:
    print("Attempting to import codeweaver.core.dependencies...")
    import codeweaver.core.dependencies

    print("Successfully imported codeweaver.core.dependencies")
    print(
        f"bootstrap_settings in module: {'bootstrap_settings' in dir(codeweaver.core.dependencies)}"
    )
except ImportError as e:
    print(f"Import failed: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
