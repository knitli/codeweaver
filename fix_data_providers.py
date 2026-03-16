import re

with open("src/codeweaver/providers/data/providers.py", "r") as f:
    content = f.read()

old_block = """    if provider == Provider.DUCKDUCKGO and has_package("ddgs"):"""
new_block = """    if provider == Provider.DUCKDUCKGO and has_package("duckduckgo-search"):"""
content = content.replace(old_block, new_block)

with open("src/codeweaver/providers/data/providers.py", "w") as f:
    f.write(content)
