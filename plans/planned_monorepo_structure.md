<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

packages/
  codeweaver-core/
    - Core types, exceptions
    - DI infrastructure
    - search_types (moved in Phase 1)
    - No cross-package dependencies 
    - Depends: None

  codeweaver-tokenizers/  ✅ (Extracted in Phase 1)
    - Tokenizer implementations
    - Tree-sitter integrations
    - Depends: None
    
  codeweaver-daemon/  ✅ (Extracted in Phase 1)
    - Background daemon logic
    - Process management
    - Depends: None

  codeweaver-telemetry/
    - Telemetry client (DI-enabled)
    - Analytics
    - Depends: core

  codeweaver-semantic/
    - Semantic chunking
    - AST analysis
    - Depends: core, tokenizers


  codeweaver-providers/
    - All provider implementations
    - Embedding, vector store, reranking
    - Provider factories (DI)
    - Depends: core, telemetry

  codeweaver-engine/
    - Indexer, search services
    - Config, registry (simplified)
    - Depends: core, semantic, providers

  codeweaver/
    - CLI, server, MCP
    - agent_api orchestration
    - Depends: engine, all other packages