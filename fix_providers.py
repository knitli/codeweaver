import re

with open("src/codeweaver/providers/config/providers.py", "r") as f:
    content = f.read()

old_block = """        (DuckDuckGoProviderSettings(provider=Provider.DUCKDUCKGO),) if has_package("ddgs") else ()"""
new_block = """        (DuckDuckGoProviderSettings(provider=Provider.DUCKDUCKGO),) if has_package("duckduckgo-search") else ()"""
content = content.replace(old_block, new_block)

with open("src/codeweaver/providers/config/providers.py", "w") as f:
    f.write(content)
