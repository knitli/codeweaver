<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Migration Troubleshooting Guide

Complete troubleshooting reference for embedding configuration migrations in CodeWeaver.

## Table of Contents

- [Quick Diagnostics](#quick-diagnostics)
- [Common Errors](#common-errors)
- [Recovery Procedures](#recovery-procedures)
- [Performance Issues](#performance-issues)
- [Policy Configuration Issues](#policy-configuration-issues)
- [Profile Version Conflicts](#profile-version-conflicts)
- [Data Integrity Issues](#data-integrity-issues)
- [Advanced Troubleshooting](#advanced-troubleshooting)

---

## Quick Diagnostics

### First Steps for Any Issue

```bash
# 1. Check system health
codeweaver doctor --verbose

# 2. Check migration status
codeweaver migrate status

# 3. View logs
tail -f ~/.codeweaver/logs/migration.log

# 4. Validate configuration
codeweaver config validate --show-details
```

### Diagnostic Checklist

```bash
# Check collection state
codeweaver doctor

# Check available resources
df -h ~/.codeweaver/  # Disk space
free -h               # Memory
top                   # CPU usage

# Check configuration
codeweaver config validate

# Check for corruption
codeweaver migrate validate --strict
```

---

## Common Errors

### Error: "ConfigurationLockError: Collection policy is STRICT"

**Cause**: Attempting configuration change with STRICT policy.

**Error Message**:
```
ConfigurationLockError: Collection policy is STRICT - no changes allowed.
Current policy blocks modification of model from 'voyage-code-3' to 'voyage-4-large'.
```

**Solution 1**: Change Collection Policy
```bash
# Option A: Use FAMILY_AWARE (recommended)
codeweaver config set-policy family_aware

# Option B: Use FLEXIBLE (for experimentation)
codeweaver config set-policy flexible

# Then retry your config change
codeweaver config validate
```

**Solution 2**: Reindex with New Configuration
```bash
# If policy change is not appropriate, reindex
codeweaver index --force-reindex
```

**Prevention**:
- Use `FAMILY_AWARE` policy for development
- Reserve `STRICT` for production
- Document policy requirements in team guidelines

---

### Error: "MigrationError: Model change across families not supported"

**Cause**: Attempting to change between incompatible model families.

**Error Message**:
```
MigrationError: Cannot migrate from 'voyage-3' family to 'openai' family.
Cross-family migrations require full reindexing.
```

**Solution 1**: Reindex (Recommended)
```bash
# Update config to new model
# Edit codeweaver.toml:
[embedding]
model = "openai/text-embedding-3-large"

# Force reindex
codeweaver index --force-reindex
```

**Solution 2**: Use Compatible Model
```bash
# Instead, use model within same family
# Edit codeweaver.toml:
[embedding]
model = "voyage-4-large"  # Same family as voyage-code-3

# Validate and migrate
codeweaver config validate
codeweaver migrate apply
```

**Prevention**:
- Plan model migrations carefully
- Use family-compatible models when possible
- Test in development before production changes

---

### Error: "DimensionError: Cannot increase dimensions"

**Cause**: Attempting to increase vector dimensions.

**Error Message**:
```
DimensionError: Cannot increase dimensions from 512 to 2048.
Dimension increases require full reindexing.
```

**Solution**: Reindex Required
```bash
# Dimension increases cannot be migrated
# Update config and reindex
codeweaver index --force-reindex
```

**Why It Fails**: You can't create information that doesn't exist. Dimension reduction works (truncation), but dimension increase requires regenerating embeddings.

**Prevention**:
- Start with larger dimensions if unsure
- Use Matryoshka models for flexibility
- Plan dimension strategy upfront

---

### Error: "CheckpointError: Checkpoint file corrupted"

**Cause**: Checkpoint file damaged or incomplete.

**Error Message**:
```
CheckpointError: Cannot load checkpoint 'checkpoint_20250212_143022'.
File may be corrupted or incomplete.
```

**Solution 1**: Rollback to Earlier Checkpoint
```bash
# List available checkpoints
codeweaver migrate checkpoint list

# Rollback to earlier checkpoint
codeweaver migrate checkpoint restore checkpoint_20250212_142500
```

**Solution 2**: Start Fresh Migration
```bash
# If no good checkpoints exist, restart
codeweaver migrate rollback --to-original

# Then retry with more frequent checkpoints
codeweaver migrate apply --checkpoint-interval 500
```

**Solution 3**: Manual Recovery
```bash
# Locate checkpoint files
ls -lh ~/.codeweaver/checkpoints/

# Remove corrupted checkpoint
rm ~/.codeweaver/checkpoints/checkpoint_20250212_143022.json

# Resume from previous checkpoint
codeweaver migrate resume
```

**Prevention**:
- Use frequent checkpoints (--checkpoint-interval 500-1000)
- Ensure sufficient disk space
- Don't interrupt migrations during checkpoint writes
- Enable checkpoint validation

---

### Error: "MemoryError: Insufficient memory for migration"

**Cause**: Not enough RAM for parallel workers.

**Error Message**:
```
MemoryError: Failed to allocate memory for worker pool.
Current usage: 92% of 16GB. Reduce worker count or free memory.
```

**Solution 1**: Reduce Worker Count
```bash
# Use fewer workers
codeweaver migrate apply --workers 2

# Or even single-threaded
codeweaver migrate apply --workers 1
```

**Solution 2**: Reduce Batch Size
```bash
# Smaller batches use less memory
codeweaver migrate apply \
  --workers 2 \
  --batch-size 50
```

**Solution 3**: Free Memory
```bash
# Close unnecessary applications
# Clear system cache (Linux)
sudo sync && sudo sysctl -w vm.drop_caches=3

# Then retry
codeweaver migrate apply --workers 2
```

**Prevention**:
- Monitor memory during migration
- Start with conservative worker counts
- Scale workers based on available RAM
- Plan for ~500MB per worker

---

### Error: "RateLimitError: API rate limit exceeded"

**Cause**: Too many concurrent requests to embedding provider.

**Error Message**:
```
RateLimitError: Rate limit exceeded for embedding provider.
Current rate: 150 req/sec, limit: 100 req/sec.
```

**Solution**: Adjust Rate Limiting
```bash
# Reduce request rate
codeweaver migrate apply \
  --workers 2 \
  --rate-limit 50 \
  --max-concurrent-requests 25
```

**Solution 2**: Use Exponential Backoff
```bash
# Enable retry with backoff (automatic in most cases)
codeweaver migrate apply \
  --retry-limit 5 \
  --retry-backoff exponential
```

**Prevention**:
- Check provider rate limits
- Configure appropriate rate limits
- Use fewer workers for rate-limited APIs
- Consider upgrading API tier

---

### Error: "ValidationError: Migration validation failed"

**Cause**: Post-migration data integrity check failed.

**Error Message**:
```
ValidationError: Migration validation failed.
Found 25 vectors with dimension mismatch (expected 512, got 2048).
```

**Solution 1**: Rollback and Retry
```bash
# Rollback to safe state
codeweaver migrate rollback

# Retry with strict validation
codeweaver migrate apply --validate strict
```

**Solution 2**: Incremental Fix
```bash
# Identify problematic vectors
codeweaver migrate validate --strict --json > issues.json

# Fix specific vectors (advanced)
# See Advanced Troubleshooting section
```

**Solution 3**: Force Reindex
```bash
# If validation consistently fails, reindex
codeweaver index --force-reindex
```

**Prevention**:
- Always enable validation
- Use frequent checkpoints
- Test migrations on small subsets first
- Monitor validation metrics

---

### Error: "TimeoutError: Migration exceeded timeout"

**Cause**: Migration taking longer than configured timeout.

**Error Message**:
```
TimeoutError: Migration exceeded 30 minute timeout.
Processed 15000/50000 vectors. Consider resuming with checkpoint.
```

**Solution 1**: Resume from Checkpoint
```bash
# Migration auto-checkpoints, just resume
codeweaver migrate resume --workers 4
```

**Solution 2**: Increase Timeout
```bash
# Set longer timeout (if configured)
codeweaver migrate apply --timeout 7200  # 2 hours
```

**Solution 3**: Optimize Performance
```bash
# Use more workers for faster completion
codeweaver migrate resume --workers 8

# Or reduce checkpoint frequency
codeweaver migrate apply --checkpoint-interval 5000
```

**Prevention**:
- Estimate migration time: vectors / (100-500 vectors/sec * workers)
- Use appropriate timeouts for collection size
- Monitor progress with `--watch` flag
- Use resume capability for large collections

---

## Recovery Procedures

### Procedure 1: Complete Migration Rollback

**When to Use**: Migration failed, need to return to original state.

```bash
# Step 1: Check current status
codeweaver migrate status

# Step 2: List checkpoints
codeweaver migrate checkpoint list

# Step 3: Rollback to original
codeweaver migrate rollback

# Step 4: Verify rollback
codeweaver doctor
codeweaver config validate

# Step 5: Check search works
codeweaver search "test query"
```

**Verification**:
```bash
# Check collection metadata
codeweaver config show

# Verify vector dimensions
codeweaver doctor --verbose | grep -i dimension

# Test search quality
codeweaver search "critical query" --limit 10
```

---

### Procedure 2: Partial Migration Recovery

**When to Use**: Migration partially completed but failed.

```bash
# Step 1: Assess damage
codeweaver migrate status
codeweaver migrate validate --sample-size 1000

# Step 2: Identify last good checkpoint
codeweaver migrate checkpoint list

# Step 3: Restore to checkpoint
codeweaver migrate checkpoint restore checkpoint_YYYYMMDD_HHMMSS

# Step 4: Resume or restart
# Option A: Resume from checkpoint
codeweaver migrate resume --workers 2

# Option B: Restart with new settings
codeweaver migrate apply \
  --workers 2 \
  --checkpoint-interval 500
```

---

### Procedure 3: Checkpoint Corruption Recovery

**When to Use**: Checkpoint file is corrupted.

```bash
# Step 1: Identify corruption
codeweaver migrate checkpoint list --verify

# Step 2: Remove corrupted checkpoint
rm ~/.codeweaver/checkpoints/checkpoint_CORRUPTED.json

# Step 3: Try earlier checkpoint
codeweaver migrate checkpoint list  # Find earlier checkpoint
codeweaver migrate checkpoint restore checkpoint_EARLIER

# Step 4: Resume migration
codeweaver migrate resume

# If no good checkpoints exist
# Step 5: Start over
codeweaver migrate rollback --to-original
codeweaver migrate apply --checkpoint-interval 250  # More frequent
```

---

### Procedure 4: Manual Vector Store Repair

**When to Use**: Vector store data corrupted (advanced).

```bash
# ⚠️ ADVANCED PROCEDURE - Use with caution

# Step 1: Backup current state
codeweaver backup create emergency_backup_$(date +%Y%m%d)

# Step 2: Export vectors
codeweaver export vectors --output vectors_backup.json

# Step 3: Recreate collection
codeweaver migrate rollback --to-original
codeweaver index --clear

# Step 4: Reimport vectors (if possible)
# This step depends on vector store implementation

# Step 5: Verify
codeweaver doctor --verbose
codeweaver migrate validate --strict
```

---

## Performance Issues

### Issue: Migration Too Slow

**Symptoms**:
- Migration taking hours
- Low CPU utilization
- Slow progress updates

**Diagnosis**:
```bash
# Check current settings
codeweaver migrate status

# Check resource utilization
top  # CPU usage
iostat  # Disk I/O
```

**Solutions**:

**Solution 1**: Increase Parallelism
```bash
# More workers
codeweaver migrate resume --workers 8

# Larger batches
codeweaver migrate apply \
  --workers 8 \
  --batch-size 500
```

**Solution 2**: Reduce Overhead
```bash
# Less frequent checkpoints
codeweaver migrate apply \
  --workers 4 \
  --checkpoint-interval 5000

# Disable strict validation during migration
codeweaver migrate apply --validate relaxed
```

**Solution 3**: Optimize Vector Store
```bash
# Use in-memory vector store for faster operations
# Edit codeweaver.toml:
[embedding.vector_store]
provider = "inmemory"

# Then migrate
codeweaver migrate apply --workers 8
```

---

### Issue: High Memory Usage

**Symptoms**:
- System memory >90%
- Swap usage increasing
- OOM errors

**Diagnosis**:
```bash
# Check memory usage
free -h
ps aux | grep codeweaver | awk '{sum+=$6} END {print sum/1024 " MB"}'
```

**Solutions**:

**Solution 1**: Reduce Workers
```bash
codeweaver migrate resume --workers 1
```

**Solution 2**: Smaller Batches
```bash
codeweaver migrate apply \
  --workers 2 \
  --batch-size 50
```

**Solution 3**: Clear Memory
```bash
# Stop migration
# Press Ctrl+C during migration

# Free memory
sudo sync && sudo sysctl -w vm.drop_caches=3

# Resume with conservative settings
codeweaver migrate resume --workers 1
```

---

### Issue: Disk Space Exhausted

**Symptoms**:
- "No space left on device" errors
- Migration fails during checkpoint
- Unable to write logs

**Diagnosis**:
```bash
# Check disk usage
df -h ~/.codeweaver/
du -sh ~/.codeweaver/*
```

**Solutions**:

**Solution 1**: Clean Old Checkpoints
```bash
# Remove old checkpoints
codeweaver migrate checkpoint clean --keep 2

# Check space saved
df -h ~/.codeweaver/
```

**Solution 2**: Clean Logs
```bash
# Remove old log files
find ~/.codeweaver/logs/ -name "*.log.*" -mtime +7 -delete

# Or compress logs
find ~/.codeweaver/logs/ -name "*.log" -mtime +1 -exec gzip {} \;
```

**Solution 3**: Move Data Directory
```bash
# Move to larger partition
mv ~/.codeweaver /mnt/large_disk/codeweaver
ln -s /mnt/large_disk/codeweaver ~/.codeweaver

# Or configure in settings
# Edit codeweaver.toml:
[storage]
data_dir = "/mnt/large_disk/codeweaver"
```

---

## Policy Configuration Issues

### Issue: Policy Too Restrictive

**Symptoms**:
- All config changes blocked
- Cannot migrate or optimize
- "ConfigurationLockError" for valid changes

**Solution**:
```bash
# Check current policy
codeweaver config show | grep policy

# Change to more permissive policy
codeweaver config set-policy family_aware  # Recommended balance

# Or for experimentation
codeweaver config set-policy flexible

# Verify change
codeweaver config validate
```

---

### Issue: Policy Too Permissive

**Symptoms**:
- Accidental breaking changes
- Unexpected reindex requirements
- Team members changing configs inadvertently

**Solution**:
```bash
# Lock down policy
codeweaver config set-policy strict

# Or use balanced policy
codeweaver config set-policy family_aware

# Document policy in project
echo "Policy: FAMILY_AWARE - allows safe migrations only" > CODEWEAVER_POLICY.md
```

---

### Issue: Policy Not Applied

**Symptoms**:
- Config changes work despite policy
- Policy setting appears ignored

**Diagnosis**:
```bash
# Check policy in config
codeweaver config show --json | jq '.embedding.collection.policy'

# Check collection metadata
cat ~/.codeweaver/collection/manifest.json | jq '.policy'
```

**Solution**:
```bash
# Ensure policy is saved
codeweaver config set-policy family_aware
codeweaver config apply  # Apply settings

# Verify in both places
codeweaver config show
codeweaver doctor --verbose
```

---

## Profile Version Conflicts

### Issue: Profile Version Mismatch

**Symptoms**:
- "Profile version incompatible" warning
- Unexpected migration requirements

**Error Message**:
```
Warning: Profile 'recommended' version 0.3.0 does not match collection version 0.2.0.
Major version mismatch may require migration.
```

**Solution 1**: Upgrade Profile
```bash
# Preview upgrade
codeweaver profile upgrade recommended --preview

# Apply upgrade
codeweaver profile upgrade recommended
```

**Solution 2**: Downgrade Profile (if needed)
```bash
# Switch to compatible profile version
# Edit codeweaver.toml:
[profiles.recommended]
version = "0.2.0"  # Match collection

# Apply
codeweaver config apply
```

**Prevention**:
- Track profile versions in version control
- Test profile upgrades in development first
- Document profile version requirements

---

### Issue: Custom Profile Not Loading

**Symptoms**:
- Custom profile not recognized
- "Profile not found" errors

**Diagnosis**:
```bash
# List available profiles
codeweaver profile list

# Check config file
cat codeweaver.toml | grep -A 10 "\[profiles\."
```

**Solution**:
```bash
# Ensure profile is properly defined
# codeweaver.toml must have:
[profiles.my_custom]
version = "1.0.0"
model = "voyage-code-3"
dimension = 1024

# Reload config
codeweaver config reload

# Verify profile appears
codeweaver profile list
```

---

## Data Integrity Issues

### Issue: Vector Dimension Mismatch

**Symptoms**:
- Search returns errors
- "Dimension mismatch" in logs
- Inconsistent search results

**Diagnosis**:
```bash
# Validate collection
codeweaver migrate validate --strict --sample-size 5000

# Check dimensions in config vs collection
codeweaver config show | grep dimension
codeweaver doctor --verbose | grep dimension
```

**Solution 1**: Rollback and Retry
```bash
# Rollback to consistent state
codeweaver migrate rollback

# Reapply migration carefully
codeweaver migrate apply --validate strict
```

**Solution 2**: Force Consistency
```bash
# If rollback doesn't work, reindex
codeweaver index --force-reindex
```

---

### Issue: Quantization Precision Loss Too High

**Symptoms**:
- Search quality degraded after quantization
- Accuracy metrics below acceptable threshold

**Diagnosis**:
```bash
# Run precision validation
codeweaver migrate validate --precision-check

# Compare search results before/after
codeweaver search "test query" --limit 10
```

**Solution 1**: Rollback Quantization
```bash
# Restore float32
codeweaver migrate rollback
```

**Solution 2**: Use Higher Precision
```bash
# If int8 too lossy, try float16
# Edit codeweaver.toml:
[embedding.vector_store]
datatype = "float16"  # Instead of int8

codeweaver migrate apply
```

**Solution 3**: Reindex Without Quantization
```bash
# Keep float32
# Edit codeweaver.toml:
[embedding.vector_store]
datatype = "float32"

codeweaver index --force-reindex
```

---

### Issue: Missing Vectors After Migration

**Symptoms**:
- Vector count decreased after migration
- Some files not searchable

**Diagnosis**:
```bash
# Compare vector counts
codeweaver doctor --verbose | grep "vectors"

# Check migration logs
grep -i "failed\|error\|skipped" ~/.codeweaver/logs/migration.log

# Validate completeness
codeweaver migrate validate --strict
```

**Solution**:
```bash
# Rollback and identify issue
codeweaver migrate rollback

# Check which vectors failed
codeweaver migrate apply --dry-run --verbose 2>&1 | grep -i "skip\|fail"

# Fix underlying issues (file permissions, corruption, etc.)

# Retry migration
codeweaver migrate apply --retry-limit 5
```

---

## Advanced Troubleshooting

### Debug Mode

Enable detailed logging for troubleshooting:

```bash
# Enable debug logging
export CODEWEAVER_LOG_LEVEL=DEBUG

# Run migration with verbose output
codeweaver migrate apply --verbose

# Check detailed logs
tail -f ~/.codeweaver/logs/migration.log
tail -f ~/.codeweaver/logs/debug.log
```

---

### Checkpoint Analysis

Examine checkpoint internals:

```bash
# List checkpoints with details
codeweaver migrate checkpoint list --verbose

# Verify checkpoint integrity
codeweaver migrate checkpoint verify checkpoint_20250212_143022

# Export checkpoint data
codeweaver migrate checkpoint export checkpoint_20250212_143022 \
  --output checkpoint_data.json

# Analyze checkpoint
cat checkpoint_data.json | jq '.metadata'
```

---

### Manual Vector Store Inspection

Inspect vector store directly (advanced):

```bash
# Qdrant inspection
curl http://localhost:6333/collections/codeweaver | jq

# Check collection info
curl http://localhost:6333/collections/codeweaver | jq '.result'

# Check vector count
curl http://localhost:6333/collections/codeweaver/points/count | jq

# Sample vectors
curl -X POST http://localhost:6333/collections/codeweaver/points/scroll \
  -H 'Content-Type: application/json' \
  -d '{"limit": 10}' | jq
```

---

### Performance Profiling

Profile migration performance:

```bash
# Enable profiling
export CODEWEAVER_PROFILE=1

# Run migration
codeweaver migrate apply --workers 4

# Analyze profile
python -m pstats ~/.codeweaver/logs/migration.prof
```

---

### Health Check After Issues

Complete health check after resolving issues:

```bash
# 1. System health
codeweaver doctor --verbose

# 2. Configuration validation
codeweaver config validate --show-details

# 3. Migration validation
codeweaver migrate validate --strict --sample-size 2000

# 4. Search quality test
codeweaver search "critical test query" --limit 10

# 5. Performance test
time codeweaver search "test" --limit 100

# 6. Check logs for warnings
grep -i "warn\|error" ~/.codeweaver/logs/*.log | tail -20
```

---

## Getting Help

### Collecting Diagnostic Information

Before reporting issues:

```bash
# Generate diagnostic report
codeweaver doctor --verbose --json > diagnostics.json

# Collect logs
tar -czf codeweaver-logs.tar.gz ~/.codeweaver/logs/

# Collect config (sanitize secrets!)
codeweaver config show --sanitize > config_sanitized.toml

# Document issue
cat > issue_report.md << EOF
# Issue Report

## Environment
- CodeWeaver version: $(codeweaver --version)
- Python version: $(python --version)
- OS: $(uname -a)

## Issue Description
[Describe the issue]

## Steps to Reproduce
1. [Step 1]
2. [Step 2]

## Expected Behavior
[What should happen]

## Actual Behavior
[What actually happens]

## Error Messages
[Paste relevant error messages]

## Attachments
- diagnostics.json
- codeweaver-logs.tar.gz
- config_sanitized.toml
EOF
```

### Contact Support

- GitHub Issues: https://github.com/knitli/codeweaver/issues
- Documentation: https://docs.codeweaver.dev
- Community: https://discord.gg/codeweaver

---

## Related Documentation

- [Migration Guide](embedding-migration-guide.md) - Complete migration workflows
- [API Reference](migration-api-reference.md) - API documentation
- [CLI Reference](CLI.md) - Command reference
- [Configuration Guide](configuration.md) - Configuration options
