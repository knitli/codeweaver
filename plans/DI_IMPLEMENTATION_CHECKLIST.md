<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# DI Implementation Checklist

**Status**: Planning Complete - Awaiting Approval  
**Created**: 2025-10-31

This checklist tracks the implementation of the Dependency Injection architecture for CodeWeaver.

---

## Pre-Implementation ✅

- [x] Constitutional review (aligned with all 5 principles)
- [x] Current state analysis (40+ providers documented)
- [x] FastAPI DI pattern research
- [x] pydantic-ai provider pattern research
- [x] Comprehensive planning documentation created
- [x] Risk assessment and mitigation strategies defined
- [ ] User review and feedback on planning docs
- [ ] Approval to proceed with implementation
- [ ] PoC implementation
- [ ] PoC feedback and refinement

---

## Phase 1: Foundation (next Alpha feature release Early)

**Goal**: Core DI infrastructure without breaking existing code

### Infrastructure
- [ ] Create `codeweaver/di/` package structure
  - [ ] `__init__.py` - Public API
  - [ ] `container.py` - Container implementation
  - [ ] `depends.py` - Depends marker
  - [ ] `providers.py` - Provider factories
  - [ ] `types.py` - Type definitions

### Container Implementation
- [ ] Container class with registration mechanism
- [ ] Resolution with caching (singleton support)
- [ ] Override mechanism for testing
- [ ] Lifecycle hooks (startup/shutdown)
- [ ] Error handling and validation
- [ ] Async support

### Provider Factories
- [ ] `get_embedding_provider()` factory
- [ ] `get_sparse_embedding_provider()` factory (optional)
- [ ] `get_reranking_provider()` factory (optional)
- [ ] `get_vector_store()` factory
- [ ] Type aliases (EmbeddingDep, etc.)

### Testing
- [ ] Container registration tests
- [ ] Container resolution tests
- [ ] Override mechanism tests
- [ ] Singleton behavior tests
- [ ] Lifecycle hooks tests
- [ ] Factory tests
- [ ] Integration tests
- [ ] Aim for 100% coverage on DI infrastructure

### Documentation
- [ ] API documentation (docstrings)
- [ ] Usage examples
- [ ] Testing guide
- [ ] Architecture decision records

**Acceptance Criteria**:
- [ ] All tests passing
- [ ] No changes to existing production code
- [ ] Documentation complete
- [ ] Code review approved

---

## Phase 2: Integration (next Alpha feature release Mid)

**Goal**: Migrate core services to use DI

### Service Migration
- [ ] Migrate `Indexer` to use DI
  - [ ] Update constructor with dependency injection
  - [ ] Remove manual provider fetching
  - [ ] Update all instantiation points
  - [ ] Update tests to use container overrides
- [ ] Migrate search services
  - [ ] `SemanticSearchService`
  - [ ] `HybridSearchService`
  - [ ] Query processing services
- [ ] Update server initialization
  - [ ] Use container lifecycle
  - [ ] Register providers at startup
  - [ ] Health checks via DI

### Testing
- [ ] Update existing tests to use DI
- [ ] Ensure all tests still pass
- [ ] Add integration tests with DI
- [ ] Performance benchmarks (no regression)

### Documentation
- [ ] Update service documentation
- [ ] Migration examples (before/after)
- [ ] Testing guide updates
- [ ] Troubleshooting guide

### Validation
- [ ] All existing tests pass
- [ ] No breaking changes
- [ ] Performance within 5% of v0.1
- [ ] Old pattern still works (coexistence)

**Acceptance Criteria**:
- [ ] Core services migrated
- [ ] All tests passing
- [ ] Performance validated
- [ ] Documentation updated
- [ ] Code review approved

---

## Phase 3: pydantic-ai Integration (next Alpha feature release Late / 3rd alpha feature release Early)

**Goal**: Integrate pydantic-ai providers into DI system

### Agent Provider Integration
- [ ] Create `get_pydantic_agent()` factory
  - [ ] Handle model string parsing
  - [ ] Settings resolution
  - [ ] Provider-specific configurations
- [ ] Agent type aliases (AgentDep)
- [ ] Agent provider tests

### Data Source Integration
- [ ] Create `get_tavily_search()` factory
- [ ] Create `get_duckduckgo_search()` factory
- [ ] Data source type aliases
- [ ] Data source provider tests

### Agent API Updates
- [ ] Update agent API to use DI
- [ ] Inject agents into tools
- [ ] Inject data sources into agents
- [ ] Integration tests

### Documentation
- [ ] Agent configuration guide
- [ ] Data source configuration guide
- [ ] pydantic-ai integration examples
- [ ] Testing agent-based features

**Acceptance Criteria**:
- [ ] pydantic-ai agents injectable
- [ ] Data sources work via DI
- [ ] Integration tests passing
- [ ] Documentation complete
- [ ] Code review approved

---

## Phase 4: Advanced Features (3rd alpha feature release)

**Goal**: Leverage DI for advanced capabilities

### Health Check System
- [ ] Provider health check protocol
- [ ] Health check via DI injection
- [ ] Aggregated health endpoint
- [ ] Circuit breaker integration
- [ ] Health monitoring tests

### Telemetry Integration
- [ ] Inject telemetry into providers
- [ ] Centralized metrics collection
- [ ] Distributed tracing setup
- [ ] Telemetry tests

### Plugin System Enhancement
- [ ] Custom providers via DI
- [ ] User-defined factories
- [ ] Plugin discovery and registration
- [ ] Plugin tests

### Multi-Tenant Support (if needed)
- [ ] Scoped containers per tenant
- [ ] Isolated provider instances
- [ ] Tenant-specific overrides
- [ ] Multi-tenancy tests

### Performance Optimization
- [ ] Benchmark DI overhead
- [ ] Optimize hot paths
- [ ] Profile memory usage
- [ ] Performance tests

**Acceptance Criteria**:
- [ ] All advanced features working
- [ ] Performance optimized
- [ ] Tests passing
- [ ] Documentation complete
- [ ] Code review approved

---

## Phase 5: Cleanup (3rd alpha feature release Late)

**Goal**: Finalize migration and deprecate old patterns

### Deprecation
- [ ] Add deprecation warnings to old pattern
- [ ] Update all remaining usages
- [ ] Migration guide published
- [ ] Support for questions

### Registry Cleanup
- [ ] Simplify registry (thin layer over DI)
- [ ] Remove duplicate code
- [ ] Optimize registry performance
- [ ] Registry tests updated

### Documentation Overhaul
- [ ] Architecture docs updated
- [ ] Migration guide finalized
- [ ] Best practices guide
- [ ] API reference complete
- [ ] Tutorial videos/guides (optional)

### Performance & Validation
- [ ] Final performance benchmarking
- [ ] Memory profiling
- [ ] Load testing
- [ ] Production readiness checklist

**Acceptance Criteria**:
- [ ] Old pattern deprecated (warnings)
- [ ] All code uses DI
- [ ] Registry simplified
- [ ] Documentation complete
- [ ] Performance validated
- [ ] Code review approved

---

## Post-Implementation (4th alpha feature release or later)

### Breaking Changes
- [ ] Remove old pattern entirely
- [ ] Breaking change communicated
- [ ] Migration period complete
- [ ] Final cleanup

### Monitoring
- [ ] Track adoption in production
- [ ] Monitor performance metrics
- [ ] Collect user feedback
- [ ] Issue tracking and resolution

---

## Success Criteria (Overall)

### Phase 1 Success
- [ ] Container can register and resolve dependencies
- [ ] Override mechanism works for testing
- [ ] Singleton caching functions correctly
- [ ] 100% test coverage for DI infrastructure
- [ ] No changes to existing production code

### Phase 2 Success
- [ ] Core services migrated to DI
- [ ] All existing tests still pass
- [ ] New tests use override mechanism
- [ ] No performance regression
- [ ] Documentation updated

### Phase 3 Success
- [ ] pydantic-ai agents injectable
- [ ] Data sources work via DI
- [ ] Agent API updated
- [ ] Integration tests passing
- [ ] pydantic-ai patterns documented

### Overall Success (3rd alpha feature release)
- [ ] All provider types work via DI
- [ ] Test code 50% less verbose (measured)
- [ ] New provider integration takes < 1 hour (documented)
- [ ] Zero breaking changes from next Alpha feature release to 3rd alpha feature release
- [ ] Architecture documentation complete
- [ ] Migration guide published
- [ ] Performance within 5% of v0.1

---

## Risk Tracking

### Phase 1 Risks
- [ ] **Performance overhead** - Mitigation: Benchmark early, optimize if needed
- [ ] **Complexity for contributors** - Mitigation: Comprehensive docs, clear examples

### Phase 2 Risks
- [ ] **Edge cases in provider instantiation** - Mitigation: Extensive testing
- [ ] **Breaking existing code** - Mitigation: Careful migration, old pattern coexists

### Phase 3 Risks
- [ ] **pydantic-ai integration surprises** - Mitigation: Study patterns deeply, have escape hatches

### Overall Risks
- [ ] **Scope creep** - Mitigation: Strict phase boundaries
- [ ] **Breaking changes** - Mitigation: Careful deprecation process, clear communication

---

## Questions & Decisions Log

### Decisions Made
- **Architecture**: Hybrid container + function signatures
- **Singleton behavior**: Configurable per provider type (default: singleton)
- **Settings resolution**: Auto-resolved in factories
- **pydantic-ai integration**: Expose directly, don't wrap

### Questions Awaiting Answers
- [ ] **Timing**: Phase 1-2 in next Alpha feature release, or different split?
- [ ] **pydantic-ai priority**: Fast-track Phase 3?
- [ ] **Breaking changes**: Deprecate 3rd alpha feature release, remove 4th alpha?
- [ ] **DI mandate**: Required after Phase 1?
- [ ] **Multi-tenancy**: Near-term requirement?
- [ ] **Plugin system**: Custom providers via DI in Phase 4 or later?

---

## Resources

- **Planning Docs**: `plans/dependency-injection-architecture-plan.md`
- **Summary**: `plans/DI_ARCHITECTURE_SUMMARY.md`
- **Diagrams**: `plans/DI_ARCHITECTURE_DIAGRAMS.md`
- **Examples**: `plans/DI_PROVIDER_EXAMPLES.md`
- **Constitution**: `.specify/memory/constitution.md`
- **Architecture**: `ARCHITECTURE.md`

---

## Progress Tracking

**Current Status**: Planning Complete ✅  
**Next Milestone**: User approval and PoC  
**Target next Alpha feature release**: Phase 1 + 2 complete  
**Target 3rd alpha feature release Release**: Phase 3 + 4 + 5 complete

---

**Last Updated**: 2025-10-31  
**Maintained By**: Implementation team
