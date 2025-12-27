import time


def check_import(module_name) -> None:
    print(f"Importing {module_name}...", flush=True)
    start = time.time()
    try:
        __import__(module_name)
        print(f"Imported {module_name} in {time.time() - start:.2f}s", flush=True)
    except ImportError as e:
        print(f"Failed to import {module_name}: {e}", flush=True)
    except Exception as e:
        print(f"Error importing {module_name}: {e}", flush=True)


print("Starting import checks...", flush=True)
check_import("fastembed")
check_import("sentence_transformers")
check_import("codeweaver.providers.embedding.providers.fastembed")
check_import("codeweaver.providers.vector_stores.inmemory")
print("Done.", flush=True)
