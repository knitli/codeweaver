import re

with open("src/codeweaver/providers/vector_stores/inmemory.py", "r") as f:
    content = f.read()

# Ah! temp_path.rename() fails if the parent directory doesn't exist?
# No, `await temp_path.rename(str(self.persist_path))` might throw FileNotFoundError if `persist_path` isn't created or some paths are missing.
# Let's ensure the parent directories exist before saving!

old_block = """        # Atomic persistence via temporary directory
        persist_path = AsyncPath(str(self.persist_path))
        temp_path = persist_path.with_suffix(".tmp")"""

new_block = """        # Atomic persistence via temporary directory
        persist_path = AsyncPath(str(self.persist_path))
        await persist_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = persist_path.with_suffix(".tmp")"""

content = content.replace(old_block, new_block)

with open("src/codeweaver/providers/vector_stores/inmemory.py", "w") as f:
    f.write(content)
