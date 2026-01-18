
import sys
import os

# Add src to sys.path explicitly
sys.path.insert(0, os.path.abspath("src"))

try:
    print("Attempting to import codeweaver.core.dependencies...")
    import codeweaver.core.dependencies
    print("Successfully imported codeweaver.core.dependencies")
    print(f"bootstrap_settings in module: {'bootstrap_settings' in dir(codeweaver.core.dependencies)}")
except ImportError as e:
    print(f"Import failed: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
