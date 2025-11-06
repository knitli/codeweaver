<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Critical Production Bug Fix

**Date**: 2025-11-04
**Priority**: CRITICAL
**Status**: ✅ FIXED

## Issue

**Location**: `src/codeweaver/common/registry/provider.py`
- Line 678 (Bedrock provider)
- Line 711 (Generic provider creation)

**Error**: `TypeError: unsupported operand type(s) for |: 'NoneType' and 'dict'`

**Root Cause**: `provider_settings` parameter can be `None`, but code attempts dictionary merge operation (`provider_settings | client_options`) without None check.

## Impact

**Severity**: CRITICAL - Production runtime failure
**Scope**: Provider creation when no settings configured
**User Impact**: Application crashes when creating providers without explicit settings

## Fix Applied

### Line 678 (Bedrock)
```python
# BEFORE
if provider == Provider.BEDROCK:
    return client_class("bedrock-runtime", **(provider_settings | client_options))

# AFTER
if provider == Provider.BEDROCK:
    provider_settings = provider_settings or {}
    return client_class("bedrock-runtime", **(provider_settings | client_options))
```

### Line 711 (Generic)
```python
# BEFORE
args, kwargs = set_args_on_signature(
    client_class, kwargs=provider_settings | client_options
)

# AFTER
provider_settings = provider_settings or {}
args, kwargs = set_args_on_signature(
    client_class, kwargs=provider_settings | client_options
)
```

## Validation

✅ Fix applied successfully
✅ Defensive programming pattern (or {}) prevents None errors
⚠️ Pre-existing ruff complexity warning unrelated to fix

## Discovery Credit

Discovered by Agent N (Quality Engineer) during Phase 4 client factory test infrastructure improvement.

## Recommendation

This fix should be included in any main branch integration as it prevents potential production crashes.
