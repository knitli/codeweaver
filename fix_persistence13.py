import re

with open("src/codeweaver/providers/vector_stores/inmemory.py", "r") as f:
    content = f.read()

# Atomic replace uses Path.rename() which has different behaviors across OSes for directories.
# And here, if `persist_path`'s parent doesn't exist, it throws FileNotFoundError.
# I will use shutil.move instead since rename can fail if moving across devices or if dest exists and is a directory.
# Wait, I previously changed it to shutil.move but then reverted!
# Also, if `AsyncQdrantClient(path=str(temp_path))` writes nothing because the collection is empty, maybe temp_path is not a directory but never created?
# Let's ensure the parent exists and we use `shutil.move` safely.

old_block = """                await temp_path.rename(str(self.persist_path))
        except Exception as e:"""

new_block = """                import shutil
                await asyncio.to_thread(shutil.move, str(temp_path), str(self.persist_path))
        except Exception as e:"""

content = content.replace(old_block, new_block)

with open("src/codeweaver/providers/vector_stores/inmemory.py", "w") as f:
    f.write(content)
