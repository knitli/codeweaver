import re

with open("src/codeweaver/providers/config/profiles.py", "r") as f:
    content = f.read()

# Looks like it unconditionally assigns DuckDuckGo if tavily isn't available! Let's fix that.
old_block1 = """        data=(TavilyProviderSettings(provider=Provider.TAVILY),)
        if Provider.TAVILY.has_env_auth and has_package("tavily")
        else (DuckDuckGoProviderSettings(provider=Provider.DUCKDUCKGO),),"""

new_block1 = """        data=(TavilyProviderSettings(provider=Provider.TAVILY),)
        if Provider.TAVILY.has_env_auth and has_package("tavily")
        else ((DuckDuckGoProviderSettings(provider=Provider.DUCKDUCKGO),) if has_package("duckduckgo-search") else ()),"""

old_block2 = """        data=(
            TavilyProviderSettings(provider=Provider.TAVILY)
            if has_package("tavily") and Provider.TAVILY.has_env_auth
            else DuckDuckGoProviderSettings(provider=Provider.DUCKDUCKGO),
        ),"""

new_block2 = """        data=(
            (TavilyProviderSettings(provider=Provider.TAVILY),)
            if has_package("tavily") and Provider.TAVILY.has_env_auth
            else ((DuckDuckGoProviderSettings(provider=Provider.DUCKDUCKGO),) if has_package("duckduckgo-search") else ())
        ),"""

content = content.replace(old_block1, new_block1).replace(old_block2, new_block2)

with open("src/codeweaver/providers/config/profiles.py", "w") as f:
    f.write(content)
