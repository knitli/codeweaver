<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

└─ codeweaver-mcp
   ├─ src
   │  ├─ embedding
   │  │  └─ fastembed.py
   │  │     └─ line 47: TODO : Adjust method calls to match EmbeddingModelProfile once we have a standard interface
   │  ├─ models
   │  │  └─ core.py
   │  │     ├─ line 152: TODO : query_intent should *not* be exposed to the user or user's agent. It needs to be created *from* the information available from them. We can expose the simpler `IntentType` instead, but we shouldn't be asking them to assess their intent.
   │  │     └─ line 153: TODO : query_intent should *not* be exposed to the user or user's agent. It needs to be created *from* the information available from them. We can expose the simpler `IntentType` instead, but we shouldn't be asking them to assess their intent.
   │  ├─ services
   │  │  ├─ discovery.py
   │  │  │  └─ line 26: TODO : Add process_filename implementation and probably remove detect_language. It probably makes the most sense to unify returning paths, ExtKind/language detection into a single data structure. A TypedDict would do it, or just add to ExtKind.
   │  │  └─ indexer.py
   │  │     ├─ line 5: TODO : implement file watcher
   │  │     └─ line 6: TODO : register with providers registry
   │  ├─ tools
   │  │  ├─ __init__.py
   │  │  │  └─ line 13: TODO : replace these constants with registrations to the providers registry
   │  │  └─ find_code.py
   │  │     ├─ line 49: TODO : why isn't this used?
   │  │     └─ line 50: TODO : why isn't this used?
   │  ├─ vector_stores
   │  │  └─ memory.py
   │  │     └─ line 9: TODO : We should consider a few things to improve this implementation:
   │  ├─ _capabilities.py
   │  │  └─ line 8: TODO : The vector provider capabilities aren't what they need to be.... it needs to be things like sparse vectors, quantization, etc.
   │  ├─ settings_types.py
   │  │  ├─ line 112: TODO : We need to allow for dynamic providers in the future, we would check if there's a provider class registered for the value, then register the provider here with `cls.add_member("NEW_PROVIDER", "new_provider")`.
   │  │  └─ line 113: TODO : We need to allow for dynamic providers in the future, we would check if there's a provider class registered for the value, then register the provider here with `cls.add_member("NEW_PROVIDER", "new_provider")`.
   │  ├─ _statistics.py
   │  │  ├─ line 193: TODO : This needs to come from the config; it consists of any optional includes the user sets
   │  │  ├─ line 212: TODO : We'd ideally want to make sure these are pushed to the indexer, unless we receive these in the same action
   │  │  └─ line 331: TODO : To implement this correctly, we need to pull the model name from the fastmcp.Context object and use the pricing for that model. We could use [`genai_prices`](https://github.com/pydantic/genai-prices) to get the pricing information, either remotely or as a dependency.
   │  ├─ language.py
   │  │  ├─ line 211: TODO : Validate the `dependency_key_paths` for each config file to ensure they are correct. If you use these languages, please let us know if you find any issues with the `dependency_key_paths` in the config files. Some are probably incorrect.
   │  │  └─ line 704: TODO : Integrate into indexing and search services to use these languages.
   │  ├─ main.py
   │  │  ├─ line 53: TODO : Integrate fastmcp middleware here -- error handling, logging, timing, rate_limiting, etc.
   │  │  ├─ line 57: TODO : This is a placeholder. We need to implement the provider registry in _registry.py
   │  │  ├─ line 70: TODO : We need a proper health check system -- this doesn't do anything
   │  │  ├─ line 74: TODO : We need a proper health check system -- this doesn't do anything
   │  │  ├─ line 80: TODO : setup application state
   │  │  ├─ line 84: TODO : setup application state
   │  │  ├─ line 85: TODO : teardown application state
   │  │  ├─ line 89: TODO : teardown application state
   │  │  ├─ line 90: TODO : Add middleware, dependency injection, etc.
   │  │  ├─ line 94: TODO : Add middleware, dependency injection, etc.
   │  │  ├─ line 126: TODO : handle context properly and inject it into app state
   │  │  ├─ line 130: TODO : handle context properly and inject it into app state
   │  │  ├─ line 151: TODO : This shouldn't be a tool, but a proper health check endpoint. We can also expose it as a Resource. But not a tool.
   │  │  ├─ line 155: TODO : This shouldn't be a tool, but a proper health check endpoint. We can also expose it as a Resource. But not a tool.
   │  │  ├─ line 183: TODO : the typechecker doesn't like this and probably neither does uvicorn.
   │  │  └─ line 187: TODO : the typechecker doesn't like this and probably neither does uvicorn.
   │  └─ providers.py
   │     ├─ line 77: TODO : We need to allow for dynamic providers in the future, we would check if there's a provider class registered for the value, then register the provider here with `cls.add_member("NEW_PROVIDER", "new_provider")`.
   │     └─ line 78: TODO : We need to allow for dynamic providers in the future, we would check if there's a provider class registered for the value, then register the provider here with `cls.add_member("NEW_PROVIDER", "new_provider")`.
   └─ pyproject.toml
      ├─ line 255: TODO : Implement authentication and authorization middleware -- should be simple to add
      ├─ line 279: TODO : Implement authentication and authorization middleware -- should be simple to add
      ├─ line 317: TODO : Implement authentication and authorization middleware -- should be simple to add
      └─ line 319: TODO : Implement authentication and authorization middleware -- should be simple to add
