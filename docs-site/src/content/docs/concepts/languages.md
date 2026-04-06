---
title: "Language Support"
---

# Language Support

> **TL;DR:** CodeWeaver supports **166+ languages**. Use it to get deep structural context for 27 core languages (AST-aware) or reliable heuristic search for everything else. It saves agents from "context blindness" by understanding the logical boundaries of almost any codebase.

CodeWeaver is designed to be universal. While it provides the deepest intelligence for modern programming languages, its resilient architecture ensures that even legacy systems or niche configuration formats are searchable and understandable for AI agents.

---

## Deep Understanding (AST-Aware)

For **27 core languages**, CodeWeaver uses Abstract Syntax Trees (AST) via `ast-grep`. This allows the system to understand the true structure of your code—identifying functions, classes, and methods as logical units rather than arbitrary chunks of text.

### Supported AST Languages:
- **Web:** HTML, CSS, JavaScript, TypeScript, JSX, TSX
- **Systems:** Rust, Go, C, C++, C#, Swift
- **Data/Config:** JSON, YAML, HCL (Terraform), Nix
- **Scripting:** Python, Ruby, Lua, Bash
- **JVM/Mobile:** Java, Kotlin, Scala
- **Specialized:** PHP, Elixir, Haskell, Solidity

**Why it matters:** AST awareness means CodeWeaver can pinpoint the exact start and end of a function, ensuring your agent receives a complete, logical snippet without "cutting off" important logic at the edge of a text chunk.

---

## Universal Coverage (Heuristic Fallback)

For the other **139+ languages**, CodeWeaver uses **Intelligent Heuristic Chunking**. This system analyzes the file's syntax to identify common delimiters, indentation patterns, and logical markers.

- **Broad Support:** From COBOL and Fortran to specialized DSLs and configuration formats.
- **Smart Boundaries:** Even without a full AST parser, CodeWeaver identifies logical breaks to keep related code together.
- **Semantic Mapping:** All languages benefit from semantic search (dense embeddings), meaning intent-based queries work even for niche languages.

---

## Language Groups & Heuristics

CodeWeaver classifies languages into "families" to apply the best chunking strategy automatically:

| Family | Strategy | Examples |
| :--- | :--- | :--- |
| **C-Style** | Braces/Semicolons | C, C++, Java, Rust |
| **Pythonic** | Indentation/Colons | Python, Mojo, GDScript |
| **Lisp-like** | Parentheses | Clojure, Emacs Lisp |
| **Markup** | Tags/Attributes | HTML, XML, SVG |

---

## Workspace Awareness

CodeWeaver doesn't just look at individual files; it understands **Repository Conventions**. It automatically identifies:
- **Source Directories:** `src/`, `lib/`, `pkg/`
- **Test Suites:** `tests/`, `spec/`, `__tests__`
- **Build Artifacts:** `dist/`, `target/`, `bin/` (usually excluded from indexing)

This structural awareness ensures that search results are prioritized based on their role in the codebase, preventing test files from cluttering implementation-focused searches.

---

## Summary: No Context Blindness

Whether your project is a modern TypeScript monorepo or a legacy C++ system, CodeWeaver provides the "Exquisite Context" needed for AI agents to be productive. Its combination of deep AST analysis and resilient heuristics ensures you are never "context blind."
