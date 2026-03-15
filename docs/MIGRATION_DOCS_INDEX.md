<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Migration Documentation Index

Complete documentation for CodeWeaver's embedding configuration migration system (Phase 3).

## Documentation Overview

### 📘 [Migration Guide](embedding-migration-guide.md)
**User-focused guide for performing migrations**

**Topics Covered**:
- Quick start workflows
- When to migrate vs reindex
- Collection policies explained
- Profile management
- Migration workflows with examples
- Advanced features (parallel processing, checkpointing)
- Best practices

**Audience**: All users performing configuration changes

**Start Here If**: You need to change embedding models, reduce dimensions, or optimize your collection

---

### 📗 [API Reference](migration-api-reference.md)
**Complete API documentation with code examples**

**Topics Covered**:
- `ConfigChangeAnalyzer` API
- `MigrationService` API
- Collection policy configuration
- Profile management API
- CLI command reference
- Type definitions
- Integration examples

**Audience**: Developers integrating migration features, power users, automation scripts

**Start Here If**: You need detailed API signatures, type definitions, or programmatic integration

---

### 📙 [Troubleshooting Guide](troubleshooting-migration.md)
**Comprehensive problem-solving reference**

**Topics Covered**:
- Quick diagnostics
- Common error messages and solutions
- Recovery procedures (rollback, checkpoint restoration)
- Performance troubleshooting
- Policy configuration issues
- Profile version conflicts
- Data integrity problems
- Advanced debugging techniques

**Audience**: Users experiencing issues, production operators, support teams

**Start Here If**: You're encountering errors, performance issues, or need to recover from failed migrations

---

## Quick Navigation

### By Task

| I Need To... | Documentation | Section |
|-------------|---------------|---------|
| Change my embedding model | [Migration Guide](embedding-migration-guide.md) | [Migration Workflows](embedding-migration-guide.md#migration-workflows) |
| Reduce vector dimensions | [Migration Guide](embedding-migration-guide.md) | [Workflow 2: Dimension Reduction](embedding-migration-guide.md#workflow-2-dimension-reduction) |
| Optimize storage with quantization | [Migration Guide](embedding-migration-guide.md) | [Workflow 1: Optimize Existing Collection](embedding-migration-guide.md#workflow-1-optimize-existing-collection) |
| Understand collection policies | [Migration Guide](embedding-migration-guide.md) | [Collection Policies](embedding-migration-guide.md#collection-policies) |
| Recover from failed migration | [Troubleshooting](troubleshooting-migration.md) | [Recovery Procedures](troubleshooting-migration.md#recovery-procedures) |
| Fix "ConfigurationLockError" | [Troubleshooting](troubleshooting-migration.md) | [Common Errors](troubleshooting-migration.md#error-configurationlockerror-collection-policy-is-strict) |
| Use migration API in code | [API Reference](migration-api-reference.md) | [ConfigChangeAnalyzer](migration-api-reference.md#configchangeanalyzer) |
| Upgrade a profile version | [Migration Guide](embedding-migration-guide.md) | [Profile Management](embedding-migration-guide.md#profile-management) |
| Debug slow migrations | [Troubleshooting](troubleshooting-migration.md) | [Performance Issues](troubleshooting-migration.md#performance-issues) |
| Write migration scripts | [API Reference](migration-api-reference.md) | [Integration Examples](migration-api-reference.md#integration-examples) |

### By Error Message

| Error | Documentation | Section |
|-------|---------------|---------|
| ConfigurationLockError | [Troubleshooting](troubleshooting-migration.md) | [Policy Errors](troubleshooting-migration.md#error-configurationlockerror-collection-policy-is-strict) |
| MigrationError: Cross-family change | [Troubleshooting](troubleshooting-migration.md) | [Model Errors](troubleshooting-migration.md#error-migrationerror-model-change-across-families-not-supported) |
| DimensionError: Cannot increase | [Troubleshooting](troubleshooting-migration.md) | [Dimension Errors](troubleshooting-migration.md#error-dimensionerror-cannot-increase-dimensions) |
| CheckpointError: Corrupted | [Troubleshooting](troubleshooting-migration.md) | [Checkpoint Errors](troubleshooting-migration.md#error-checkpointerror-checkpoint-file-corrupted) |
| MemoryError: Insufficient memory | [Troubleshooting](troubleshooting-migration.md) | [Resource Errors](troubleshooting-migration.md#error-memoryerror-insufficient-memory-for-migration) |
| RateLimitError | [Troubleshooting](troubleshooting-migration.md) | [API Errors](troubleshooting-migration.md#error-ratelimiterror-api-rate-limit-exceeded) |
| ValidationError | [Troubleshooting](troubleshooting-migration.md) | [Data Errors](troubleshooting-migration.md#error-validationerror-migration-validation-failed) |
| TimeoutError | [Troubleshooting](troubleshooting-migration.md) | [Performance Errors](troubleshooting-migration.md#error-timeouterror-migration-exceeded-timeout) |

### By Use Case

| Use Case | Recommended Reading Order |
|----------|--------------------------|
| **First-time migration** | 1. [Migration Guide - Quick Start](embedding-migration-guide.md#quick-start)<br>2. [Migration Guide - Understanding](embedding-migration-guide.md#understanding-migrations)<br>3. [Migration Guide - Workflows](embedding-migration-guide.md#migration-workflows) |
| **Production optimization** | 1. [Migration Guide - Best Practices](embedding-migration-guide.md#best-practices)<br>2. [Migration Guide - Collection Policies](embedding-migration-guide.md#collection-policies)<br>3. [API Reference - CLI Commands](migration-api-reference.md#cli-commands) |
| **Development automation** | 1. [API Reference - ConfigChangeAnalyzer](migration-api-reference.md#configchangeanalyzer)<br>2. [API Reference - MigrationService](migration-api-reference.md#migrationservice)<br>3. [API Reference - Integration Examples](migration-api-reference.md#integration-examples) |
| **Troubleshooting issues** | 1. [Troubleshooting - Quick Diagnostics](troubleshooting-migration.md#quick-diagnostics)<br>2. [Troubleshooting - Common Errors](troubleshooting-migration.md#common-errors)<br>3. [Troubleshooting - Recovery](troubleshooting-migration.md#recovery-procedures) |
| **Policy configuration** | 1. [Migration Guide - Collection Policies](embedding-migration-guide.md#collection-policies)<br>2. [API Reference - Collection Policies](migration-api-reference.md#collection-policies)<br>3. [Troubleshooting - Policy Issues](troubleshooting-migration.md#policy-configuration-issues) |

---

## Feature Coverage

### Collection Policies ✅

**Documentation**:
- [Guide: Collection Policies](embedding-migration-guide.md#collection-policies)
- [API: CollectionPolicy Enum](migration-api-reference.md#collection-policies)
- [Troubleshooting: Policy Issues](troubleshooting-migration.md#policy-configuration-issues)

**Policies**:
- STRICT: No changes allowed (production)
- FAMILY_AWARE: Safe migrations only (recommended default)
- FLEXIBLE: Most changes with warnings (experimentation)
- UNLOCKED: All changes allowed (advanced users)

---

### Profile Versioning ✅

**Documentation**:
- [Guide: Profile Management](embedding-migration-guide.md#profile-management)
- [API: VersionedProfile](migration-api-reference.md#profile-management)
- [Troubleshooting: Version Conflicts](troubleshooting-migration.md#profile-version-conflicts)

**Features**:
- Semantic versioning for profiles
- Compatibility checking
- Profile upgrade workflows
- Custom profile support

---

### Migration Operations ✅

**Documentation**:
- [Guide: Migration Workflows](embedding-migration-guide.md#migration-workflows)
- [API: MigrationService](migration-api-reference.md#migrationservice)
- [Troubleshooting: Migration Issues](troubleshooting-migration.md#recovery-procedures)

**Operations**:
- Dimension reduction (Matryoshka)
- Quantization (float32 → int8)
- Model changes (within families)
- Parallel processing
- Checkpoint/resume
- Rollback

---

### Advanced Features ✅

**Documentation**:
- [Guide: Advanced Features](embedding-migration-guide.md#advanced-features)
- [API: Worker Pool Config](migration-api-reference.md#workerpoolconfig)
- [Troubleshooting: Performance](troubleshooting-migration.md#performance-issues)

**Features**:
- Parallel worker pools
- Configurable checkpointing
- Resource management
- Rate limiting
- Retry with exponential backoff
- Data integrity validation

---

## Examples Quick Reference

### Basic Migration
```bash
# Check what would happen
codeweaver config analyze --preview

# Apply migration
codeweaver migrate apply

# Validate results
codeweaver migrate validate
```

**Full Example**: [Migration Guide - Quick Start](embedding-migration-guide.md#quick-start)

---

### Dimension Reduction
```bash
# Update config: dimension = 512
codeweaver migrate apply \
  --workers 4 \
  --checkpoint-interval 1000
```

**Full Example**: [Migration Guide - Workflow 2](embedding-migration-guide.md#workflow-2-dimension-reduction)

---

### Quantization
```bash
# Update config: datatype = "int8"
codeweaver migrate apply --validate strict
```

**Full Example**: [Migration Guide - Workflow 1](embedding-migration-guide.md#workflow-1-optimize-existing-collection)

---

### Rollback
```bash
# Rollback to last checkpoint
codeweaver migrate rollback

# Or specific checkpoint
codeweaver migrate rollback --checkpoint checkpoint_20250212_143022
```

**Full Example**: [Troubleshooting - Recovery Procedures](troubleshooting-migration.md#procedure-1-complete-migration-rollback)

---

### Programmatic Migration
```python
from codeweaver.engine.services import get_migration_service

service = get_migration_service()
result = await service.migrate_collection(
    target_config,
    workers=4,
    checkpoint_interval=1000,
)
```

**Full Example**: [API Reference - Integration Examples](migration-api-reference.md#full-migration-workflow)

---

## Related Documentation

### Core Documentation
- [CLI Reference](CLI.md) - Complete command reference
- [Configuration Guide](configuration.md) - Config file reference
- [Architecture](ARCHITECTURE.md) - System architecture

### Implementation Documentation
- [Unified Implementation Plan](../claudedocs/unified-implementation-plan.md) - Technical specification
- [Config Analyzer Testing](../claudedocs/config-analyzer-testing-guide.md) - Testing guide
- [Collection Policy Implementation](../claudedocs/collection-policy-implementation-summary.md) - Implementation details

---

## Documentation Standards

All migration documentation follows these standards:

### Structure
- Clear table of contents
- Progressive complexity (simple → advanced)
- Cross-references between documents
- Code examples for every feature

### Code Examples
- Complete, runnable examples
- Expected output shown
- Error handling demonstrated
- Real-world use cases

### Error Documentation
- Error message quoted exactly
- Root cause explained
- Multiple solution paths
- Prevention strategies

### Best Practices
- Production recommendations
- Performance considerations
- Security implications
- Testing strategies

---

## Feedback and Contributions

Found an issue or have suggestions for improving the documentation?

- **Report issues**: [GitHub Issues](https://github.com/knitli/codeweaver/issues)
- **Suggest improvements**: Pull requests welcome
- **Ask questions**: [Community Discord](https://discord.gg/codeweaver)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-02-12 | Initial migration documentation release |

---

## License

<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-License-Identifier: MIT OR Apache-2.0
-->

This documentation is dual-licensed under MIT OR Apache-2.0.
