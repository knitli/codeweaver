<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Migration Quick Reference Card

Fast reference for common migration operations in CodeWeaver.

## Quick Start (30 seconds)

```bash
# Check if migration needed
codeweaver config analyze

# Apply migration
codeweaver migrate apply

# Verify
codeweaver doctor
```

---

## Common Tasks

### Change Embedding Model

```bash
# 1. Update codeweaver.toml
[embedding]
model = "new-model"

# 2. Check compatibility
codeweaver config validate

# 3. Migrate or reindex
codeweaver migrate apply  # or: codeweaver index --force-reindex
```

### Reduce Dimensions

```bash
# 1. Update config: dimension = 512
# 2. Migrate
codeweaver migrate apply --workers 4 --checkpoint-interval 1000
```

### Optimize with Quantization

```bash
# 1. Update config: datatype = "int8"
# 2. Migrate
codeweaver migrate apply --validate strict
```

### Rollback Failed Migration

```bash
codeweaver migrate rollback
codeweaver doctor
```

---

## Collection Policies

| Policy | Use Case | Changes Allowed |
|--------|----------|-----------------|
| `strict` | Production | None |
| `family_aware` | Development | Safe migrations only |
| `flexible` | Testing | Most changes (with warnings) |
| `unlocked` | Advanced | All changes |

```bash
# Set policy
codeweaver config set-policy family_aware
```

---

## Migration Options

### Performance

```bash
# Fast (uses more resources)
codeweaver migrate apply --workers 8 --batch-size 500

# Safe (uses less resources)
codeweaver migrate apply --workers 2 --checkpoint-interval 500
```

### Resume Interrupted Migration

```bash
codeweaver migrate resume --workers 4
```

### Validation

```bash
# After migration
codeweaver migrate validate --strict
```

---

## Troubleshooting

### Check Status

```bash
codeweaver doctor --verbose
codeweaver migrate status
tail -f ~/.codeweaver/logs/migration.log
```

### Common Errors

| Error | Quick Fix |
|-------|-----------|
| ConfigurationLockError | `codeweaver config set-policy flexible` |
| Cross-family change | Use `codeweaver index --force-reindex` |
| Out of memory | `codeweaver migrate resume --workers 1` |
| Corrupted checkpoint | `codeweaver migrate rollback` |

### Recovery

```bash
# List checkpoints
codeweaver migrate checkpoint list

# Restore specific checkpoint
codeweaver migrate checkpoint restore checkpoint_YYYYMMDD_HHMMSS

# Clean old checkpoints
codeweaver migrate checkpoint clean --keep 5
```

---

## Decision Tree

```
Need to change config?
│
├─ Model change within same family?
│  └─ migrate apply
│
├─ Dimension reduction (Matryoshka)?
│  └─ migrate apply
│
├─ Quantization?
│  └─ migrate apply
│
├─ Cross-family model change?
│  └─ index --force-reindex
│
└─ Dimension increase?
   └─ index --force-reindex
```

---

## Best Practices

✅ **Always**:
- Backup before migration: `codeweaver backup create`
- Validate after: `codeweaver migrate validate`
- Use checkpoints: `--checkpoint-interval 1000`
- Test in dev first

❌ **Never**:
- Skip validation in production
- Use `unlocked` policy in production
- Interrupt during checkpoint writes
- Ignore error messages

---

## For More Information

- **Full Guide**: [Migration Guide](embedding-migration-guide.md)
- **API Docs**: [API Reference](migration-api-reference.md)
- **Problems**: [Troubleshooting](troubleshooting-migration.md)
- **Index**: [Documentation Index](MIGRATION_DOCS_INDEX.md)

---

## Empirical Data (Voyage-Code-3)

| Transformation | Storage | Accuracy Impact |
|---------------|---------|-----------------|
| float32 → int8 @ 2048d | -75% | +0.40% ✅ |
| 2048d → 512d (float32) | -75% | -0.47% |
| 2048d → 512d + int8 | -93.75% | -0.62% |

**Baseline**: float32@2048d = 75.16% (MTEB)

---

## CLI Command Reference

```bash
# Configuration
codeweaver config validate [--show-details]
codeweaver config analyze [--preview] [--show-alternatives]
codeweaver config set-policy POLICY

# Migration
codeweaver migrate apply [--workers N] [--checkpoint-interval N]
codeweaver migrate resume [--workers N]
codeweaver migrate rollback [--checkpoint ID]
codeweaver migrate validate [--strict] [--sample-size N]
codeweaver migrate status [--watch]

# Checkpoints
codeweaver migrate checkpoint list
codeweaver migrate checkpoint create NAME
codeweaver migrate checkpoint restore ID
codeweaver migrate checkpoint clean [--keep N]

# Profiles
codeweaver profile list [--verbose]
codeweaver profile upgrade PROFILE [--preview]
```

---

## Python API Quick Start

```python
from codeweaver.config import Settings, EmbeddingConfig
from codeweaver.engine.services import (
    get_config_analyzer,
    get_migration_service,
)

# Initialize
settings = Settings()
analyzer = get_config_analyzer(settings)
service = get_migration_service(settings)

# Analyze
analysis = await analyzer.analyze_current_config()

# Migrate
result = await service.migrate_collection(
    target_config,
    workers=4,
    checkpoint_interval=1000,
)

# Validate
validation = await service.validate_migration()
```

---

## Support

- **Issues**: https://github.com/knitli/codeweaver/issues
- **Docs**: https://docs.codeweaver.dev
- **Community**: https://discord.gg/codeweaver
