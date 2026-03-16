import re

with open("src/codeweaver/providers/vector_stores/inmemory.py", "r") as f:
    content = f.read()

# Make sure we don't throw FileNotFoundError anywhere in persistence cleanup
# If `temp_path` exists but doesn't exist anymore when shutil.move runs, it will raise FileNotFoundError
# I'll just wrap the whole `Atomic replace` block in try except (FileNotFoundError, OSError).
old_block = """            # Atomic replace
            if await temp_path.exists():
                if await persist_path.exists():
                    import shutil

                    if await persist_path.is_dir():
                        await asyncio.to_thread(shutil.rmtree, str(self.persist_path), ignore_errors=True)
                    else:
                        await persist_path.unlink()

                import shutil
                await asyncio.to_thread(shutil.move, str(temp_path), str(self.persist_path))
        except Exception as e:"""

new_block = """            # Atomic replace
            try:
                if await temp_path.exists():
                    if await persist_path.exists():
                        import shutil
                        if await persist_path.is_dir():
                            await asyncio.to_thread(shutil.rmtree, str(self.persist_path), ignore_errors=True)
                        else:
                            await persist_path.unlink()
                    import shutil
                    await asyncio.to_thread(shutil.move, str(temp_path), str(self.persist_path))
            except (FileNotFoundError, OSError):
                pass
        except Exception as e:"""

content = content.replace(old_block, new_block)

with open("src/codeweaver/providers/vector_stores/inmemory.py", "w") as f:
    f.write(content)
