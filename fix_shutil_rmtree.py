import re

with open("src/codeweaver/providers/vector_stores/inmemory.py", "r") as f:
    content = f.read()

# Replace shutil.rmtree with ignore_errors=True to be sure it ignores FileNotFoundError inside nested dirs
old_block1 = """await asyncio.to_thread(shutil.rmtree, str(temp_path))"""
new_block1 = """await asyncio.to_thread(shutil.rmtree, str(temp_path), ignore_errors=True)"""
content = content.replace(old_block1, new_block1)

old_block2 = """await asyncio.to_thread(shutil.rmtree, str(self.persist_path))"""
new_block2 = """await asyncio.to_thread(shutil.rmtree, str(self.persist_path), ignore_errors=True)"""
content = content.replace(old_block2, new_block2)

with open("src/codeweaver/providers/vector_stores/inmemory.py", "w") as f:
    f.write(content)
