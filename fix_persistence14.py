import re

with open("src/codeweaver/providers/vector_stores/inmemory.py", "r") as f:
    content = f.read()

# Add await temp_path.mkdir(parents=True, exist_ok=True) back because earlier I reverted it!
old_block = """        try:
            # Initialize persistent client at temp path
            # We use AsyncQdrantClient with path to create local storage
            dest_client = AsyncQdrantClient(path=str(temp_path))"""

new_block = """        try:
            # Initialize persistent client at temp path
            # We use AsyncQdrantClient with path to create local storage
            await temp_path.mkdir(parents=True, exist_ok=True)
            dest_client = AsyncQdrantClient(path=str(temp_path))"""

content = content.replace(old_block, new_block)

with open("src/codeweaver/providers/vector_stores/inmemory.py", "w") as f:
    f.write(content)
