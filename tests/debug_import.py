import os
import sys


# Add src to sys.path explicitly
sys.path.insert(0, os.path.abspath("src"))

try:
    from codeweaver.core import bootstrap_settings

    print("Successfully imported bootstrap_settings")
except ImportError as e:
    print(f"Import failed: {e}")
    # Inspect what IS available
    import codeweaver.core

    print(f"codeweaver.core path: {codeweaver.core.__file__}")
    print(f"dir(codeweaver.core): {dir(codeweaver.core)}")
