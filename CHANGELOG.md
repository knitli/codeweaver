# Changelog

Here is what we've been working on!

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] - 2026-04-16
<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Changelog

Here is what we've been working on!

>[!NOTE]
>The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
>and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- git-cliff prepends new release sections above this marker. Do not move or delete. -->
<!-- BEGIN-CURATED-HISTORY -->

## [0.1.1] - 2026-04-07

Minor documentation and metadata fixes

## [0.1.0] - 2026-04-06

CodeWeaver's first stable release. This release represents 4 months of development since alpha.5, spanning 300+ commits across architecture, performance, security, testing, and developer experience.

### Highlights

* **DI First Architecture**: Complete rewrite of dependency and provider system to use new type safe DI architecture.The test fixtures were also completely rewritten to make best use of the new architecture. This was the primary motivation for the delays between releases and our decision to upgrade CodeWeaver to stable. We are much more confident in this architecture.
* **FastMCP v3 Migration**: Upgraded from FastMCP v2 to v3, with updated tool registration and middleware ([#239](https://github.com/knitli/codeweaver/pull/239))
* **Claude Code Plugin**: CodeWeaver can now be distributed and used as a Claude Code plugin ([#290](https://github.com/knitli/codeweaver/pull/290))
* **First-Run Onboarding**: Guided onboarding experience via SessionStart hook and onboarding agent ([#291](https://github.com/knitli/codeweaver/pull/291))
  * **Using new CodeWeaver Claude plugin**:  See the new knitli agent [toolshed marketplace](https://github.com/knitli/toolshed) for installation and setup instructions.
* **AST-Based Change Detection**: Semantic file change detection using AST hashing for smarter incremental indexing ([#259](https://github.com/knitli/codeweaver/pull/259))
* **New Config System**: The config system was re-engineered from scratch to align with associated providers, clients, and function APIs. This gives users complete configuration control, and greatly simplifies internal config handling. We essentially take your config and inject it directly where it's needed.
* **Alpha 6 "Pull the Band-Aid"**: Major internal refactoring milestone — server architecture separation, background services, daemon mode, stdio transport ([#213](https://github.com/knitli/codeweaver/pull/213)) (note: this release *is* what was planned for Alpha 6 -- we were so confident in it we decided to leave Alpha behind us)

* **Docs Site launches soon**: We will launch the docs site in the next couple of days.

### Breaking

* This is a breaking release. If you have a previous CodeWeaver configuration, it **will not work**. You need to start with a new config -- we recommend you [use the Claude plugin](https://github.com/knitli/toolshed).

### Added

* feat: guided first-run onboarding via SessionStart hook + onboarding agent ([#291](https://github.com/knitli/codeweaver/pull/291))
* feat: distribute CodeWeaver as a Claude Code plugin ([#290](https://github.com/knitli/codeweaver/pull/290))
* feat(chunker): add `FileTooLargeError` for oversized files ([#289](https://github.com/knitli/codeweaver/pull/289))
* feat: implement custom delimiter loading with override, type safety, and new-language detection ([#275](https://github.com/knitli/codeweaver/pull/275))
* feat: smarter exception messaging — deduplicated chains, `format_for_display`, log record enhancement ([#278](https://github.com/knitli/codeweaver/pull/278))
* feat: migrate from FastMCP v2 to v3 ([#239](https://github.com/knitli/codeweaver/pull/239))
* feat: AST-based hashing for semantic file change detection ([#259](https://github.com/knitli/codeweaver/pull/259))
* feat: integrate docs site with Knitli theme
* feat: implement connection pooling for supported providers ([#194](https://github.com/knitli/codeweaver/pull/194))
* feat: improve docs clarity and features ([#202](https://github.com/knitli/codeweaver/pull/202))
* feat(dev): add semantic analysis scripts for static rule analysis and generation
* feat: add setup actions for Mise and UV environments; update CI workflows for improved integration
* feat: streamline dev tooling — lesser-used tools now use `mise exec` (download-on-use)
* feat: add automated changelog generation with git-cliff ([#180](https://github.com/knitli/codeweaver/pull/180))
* feat: add automated git rebase conflict resolver script (dev tooling)
* Alpha 6 — "Pull the Band-Aid": server architecture separation, daemon mode, background services, stdio transport, management server ([#213](https://github.com/knitli/codeweaver/pull/213))
  * Separate daemon, management (port 9329), MCP HTTP (port 9328), and stdio proxy servers
  * Default transport changed from HTTP to stdio
  * Background daemon with `start`/`stop` CLI commands
  * Service persistence via `init` command
  * `CodeWeaverState` replaces `AppState` for clarity

### Fixed

* fix: handle oversized chunks in reranking capabilities ([#285](https://github.com/knitli/codeweaver/pull/285))
* fix: preserve duplicate keyword delimiter matches ([#282](https://github.com/knitli/codeweaver/pull/282))
* fix: defer fastembed import errors to use time instead of import time ([#280](https://github.com/knitli/codeweaver/pull/280))
* fix: CI green across all Python versions (3.12 – 3.14t) — pytest, persistence, cffi, voyageai ([#276](https://github.com/knitli/codeweaver/pull/276))
* fix: invalid parameter for MCP tool registration following FastMCP 3+ upgrade
* fix: namespace conflict preventing initialization when Fastembed provider enabled
* fix: incorrect property access causing indexing failures ([#200](https://github.com/knitli/codeweaver/pull/200))
* fix: Mise configuration changes causing blocking CI failures ([#196](https://github.com/knitli/codeweaver/pull/196))
* fix: correct uuid7 timestamp handling and generator resolution
* fix: `has_package()` is None checks — `has_package` returns a boolean
* fix: test_init tests bypassing themselves
* fix: feature gating for DuckDuckGo
* fix: integration test failures
* fix: disable free-threaded Python (3.13t/3.14t) CI matrix to stop noisy issue creation ([#294](https://github.com/knitli/codeweaver/pull/294))
* fix: various CI/workflow fixes for Mise, UV, and GitHub Actions compatibility
* fix: `mteb_to_codeweaver.py` — undefined names, broken init block, wrong imports ([#214](https://github.com/knitli/codeweaver/pull/214))

### Security

* fix: remove dangerous `eval()` in DI container resolution — replaced with safe lookup ([#229](https://github.com/knitli/codeweaver/pull/229))
* fix: replace insecure pickle with JSON for node types cache ([#233](https://github.com/knitli/codeweaver/pull/233))

### Performance

* perf: optimize extend() list allocations ([#295](https://github.com/knitli/codeweaver/pull/295))
* perf: fast generation of line position lengths in Chunker with `itertools` ([#293](https://github.com/knitli/codeweaver/pull/293))
* perf: optimize string length summation in config types ([#284](https://github.com/knitli/codeweaver/pull/284))
* perf: avoid single-item list allocations in spans ([#274](https://github.com/knitli/codeweaver/pull/274))
* perf: optimize `BedrockEmbeddingProvider` — use append instead of extend ([#264](https://github.com/knitli/codeweaver/pull/264))
* perf: optimize language family detection pattern caching ([#263](https://github.com/knitli/codeweaver/pull/263))
* perf: optimize list conversion for uvicorn loggers ([#271](https://github.com/knitli/codeweaver/pull/271))
* perf: optimize chunker line length calculation ([#256](https://github.com/knitli/codeweaver/pull/256))
* perf: use logical operators instead of `any([...])` for lazy evaluation ([#253](https://github.com/knitli/codeweaver/pull/253))
* perf: batch backup vector updates during reconciliation ([#248](https://github.com/knitli/codeweaver/pull/248))
* perf: optimize `_cleanup_deleted_files` with batched deletion ([#241](https://github.com/knitli/codeweaver/pull/241))
* perf: `HttpClientPool.close_all` with concurrent execution ([#244](https://github.com/knitli/codeweaver/pull/244))
* perf: optimize Exa tool registration with `asyncio.gather` ([#246](https://github.com/knitli/codeweaver/pull/246))
* perf: optimize Qdrant point deletion by removing unnecessary batching ([#247](https://github.com/knitli/codeweaver/pull/247))
* perf: optimize membership checks across CLI, profiles, providers, and HTML tags ([#216](https://github.com/knitli/codeweaver/pull/216), [#218](https://github.com/knitli/codeweaver/pull/218), [#220](https://github.com/knitli/codeweaver/pull/220), [#234](https://github.com/knitli/codeweaver/pull/234))
* perf: optimize in-memory vector store persistence I/O ([#206](https://github.com/knitli/codeweaver/pull/206))

### Code Health

* refactor: remove empty exceptions in start command ([#265](https://github.com/knitli/codeweaver/pull/265))
* refactor: remove unnecessary try/except blocks with pass in vector stores ([#268](https://github.com/knitli/codeweaver/pull/268))
* refactor: remove bare `except Exception:` suppressing errors silently ([#227](https://github.com/knitli/codeweaver/pull/227))
* refactor: rename `_check_family_dimension_validation` and its arguments ([#266](https://github.com/knitli/codeweaver/pull/266))
* refactor: remove deprecated `combined_lifespan` alias ([#226](https://github.com/knitli/codeweaver/pull/226))
* refactor: remove empty `TYPE_CHECKING` blocks
* chore: consistent use of `from __future__ import annotations` across codebase
* chore: remove vendored `types_boto3_custom`
* chore: update dependencies and REUSE.toml coverage

### Testing

* test: add missing unit tests for `detect_intent` ([#272](https://github.com/knitli/codeweaver/pull/272))
* test: add tests for `build_success_response` ([#273](https://github.com/knitli/codeweaver/pull/273))
* test: testing improvement for `generate_summary` ([#270](https://github.com/knitli/codeweaver/pull/270))
* test: conditional branches in `from_chunk` ([#243](https://github.com/knitli/codeweaver/pull/243))
* test: transport conditional branches in `main.py` ([#242](https://github.com/knitli/codeweaver/pull/242))
* test: `DiscoveredFile.from_path` conditional logic ([#245](https://github.com/knitli/codeweaver/pull/245))
* test: `DiscoveredFile` `absolute_path` property ([#215](https://github.com/knitli/codeweaver/pull/215))
* test: `get_version` fallback mechanisms ([#219](https://github.com/knitli/codeweaver/pull/219))
* test: force shutdown handler coverage ([#217](https://github.com/knitli/codeweaver/pull/217))
* test: `CircuitBreakerState` update to use `.variable` ([#228](https://github.com/knitli/codeweaver/pull/228))
* test: automatic test skipping for Python 3.14+ and missing dependencies ([#251](https://github.com/knitli/codeweaver/pull/251))

## [0.1.0-alpha.5] - 2025-12-04

### Added

* feat: implement automatic embedding reconciliation in indexer, add related tests, fix issue preventing sparse embedding storage ([#188](https://github.com/knitli/codeweaver/pull/188))
* feat: Initial docs implementation with Starlight -- Proof of Concept ([#193](https://github.com/knitli/codeweaver/pull/193))

### Fixed

* fix: health endpoint uptime, sparse provider detection, exception handling, vector normalization ([#189](https://github.com/knitli/codeweaver/pull/189))
* fix: copilot-oom errors and qdrant healthcheck failures in ci ([#192](https://github.com/knitli/codeweaver/pull/192))
* Fix test failures: HealthService parameter name and test assertion corrections ([#190](https://github.com/knitli/codeweaver/pull/190))


### Other Changes

* feat: Add verbose and debug flags to CLI commands ([#187](https://github.com/knitli/codeweaver/pull/187))

## [0.1.0-alpha.4] - 2025-12-03
