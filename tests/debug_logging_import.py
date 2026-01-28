# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

import os
import sys


sys.path.insert(0, os.path.abspath("src"))

try:
    print("Importing codeweaver.core.config._logging...")
    print("Success!")
except Exception as e:
    print(f"Failed: {e}")
    import traceback

    traceback.print_exc()
