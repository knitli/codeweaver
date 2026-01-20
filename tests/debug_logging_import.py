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
