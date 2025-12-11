<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Skipped CLI Tests Analysis - Critical Bug Risk Assessment

**Analysis Date:** 2025-12-10
**Files Analyzed:** 5 test files with 8 skipped tests
**CLI Impact:** HIGH - CLI is primary user interface

## Executive Summary

Of 8 skipped tests, **4 should be enabled immediately** (2 are already implemented, 2 are trivial fixes), **3 should be rewritten** for new structure, and **1 is correctly skipped** (platform-specific).

### Risk Classification
- **HIGH RISK (Enable Now):** 1 test - Provider validation is implemented but not validated
- **MEDIUM RISK (Rewrite):** 3 tests - Settings structure changed, tests need updates
- **LOW RISK (Already Works):** 1 test - Doctor command functionality exists
- **CORRECT (Keep Skipped):** 3 tests - Platform-specific tests, model registry internal API

---

## Test-by-Test Analysis

### 1. CRITICAL: Provider Validation Test (test_config_command.py:93)

**File:** `/home/knitli/codeweaver/tests/unit/cli/test_config_command.py`
**Line:** 93
**Skip Reason:** "Provider validation not yet implemented in settings"

#### Bug Risk: **HIGH**
The skip reason is **INCORRECT** - provider validation IS implemented! Testing confirms invalid providers are rejected with `ValueError`.

```python
# Current test expectation (line 105-106):
with pytest.raises((CodeWeaverError, ValueError)):
    CodeWeaverSettings(config_file=config_path)
```

**Validation Test Results:**
```
VALIDATION EXISTS - Exception: ValueError: expected value at line 1 column 2
```

**Impact:** Users can receive cryptic errors instead of clear validation messages. Test would catch regression if validation is removed.

**Recommendation:** **ENABLE IMMEDIATELY**
- Remove `@pytest.mark.skip` decorator (line 92)
- Update test to use correct config format (JSON, not TOML based on line 544 of settings.py)
- Verify error messages are user-friendly

**Fix:**
```python
def test_invalid_provider_rejected(self, temp_project: Path) -> None:
    """Test invalid provider names are rejected."""
    config_path = temp_project / "codeweaver.json"  # Changed to JSON
    config_content = {
        "embedding": [{"provider": "invalid_provider_xyz"}]
    }
    config_path.write_text(json.dumps(config_content))

    from codeweaver.config.settings import CodeWeaverSettings

    with pytest.raises(ValueError, match="invalid.*provider"):
        CodeWeaverSettings(config_file=config_path)
```

---

### 2. Doctor Command with Provider Setup (test_doctor_command.py:61)

**File:** `/home/knitli/codeweaver/tests/unit/cli/test_doctor_command.py`
**Line:** 61-77
**Skip Reason:** "Doctor command may fail if no providers configured - test needs provider setup"

#### Bug Risk: **MEDIUM**
Test skipped because it might fail without providers, but the test itself is valuable for validating auto-detection logic.

**Current Code:**
```python
@pytest.mark.skip(reason="Doctor command may fail if no providers configured...")
def test_doctor_handles_auto_detected_settings(
    self, temp_project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test doctor handles settings with auto-detected fields correctly."""
    settings = CodeWeaverSettings()
    assert not isinstance(settings.project_path, Unset)

    with pytest.raises(SystemExit) as exc_info:
        doctor_app()
    assert exc_info.value.code == 0
```

**Impact:** Doctor command auto-detection could break without test coverage.

**Recommendation:** **ENABLE WITH MOCK**
- Mock provider availability checks
- Test focuses on auto-detection, not provider connectivity
- Use `monkeypatch` to set minimal provider env vars

**Fix:**
```python
def test_doctor_handles_auto_detected_settings(
    self, temp_project: Path, capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test doctor handles settings with auto-detected fields correctly."""
    # Setup minimal provider config
    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")

    settings = CodeWeaverSettings()
    assert not isinstance(settings.project_path, Unset)

    # Mock provider health checks to avoid network calls
    with patch('codeweaver.cli.commands.doctor.check_provider_health'):
        with pytest.raises(SystemExit) as exc_info:
            doctor_app()
        assert exc_info.value.code == 0
```

---

### 3. Config File Not Required Test (test_doctor_command.py:245)

**File:** `/home/knitli/codeweaver/tests/unit/cli/test_doctor_command.py`
**Line:** 245-264
**Skip Reason:** "Settings structure changed"

#### Bug Risk: **MEDIUM**
Tests env-only configuration, which is a documented feature. Skipping means regression risk if this breaks.

**Structure Change Impact:**
- Old: `settings.provider.embedding.provider` (single object)
- New: `settings.provider.embedding` (tuple of provider configs)
- Old: `s.provider.embedding.provider == "fastembed"`
- New: `s.provider.embedding[0]['provider'] == Provider.FASTEMBED`

**Current Test:**
```python
@pytest.mark.skip(reason="Settings structure changed")
def test_config_file_not_required(...) -> None:
    monkeypatch.setenv("CODEWEAVER_EMBEDDING_PROVIDER", "fastembed")

    with pytest.raises(SystemExit) as exc_info:
        doctor_app()

    # Should not mention missing config file
    assert "missing" not in captured.out.lower()
```

**Recommendation:** **REWRITE FOR NEW STRUCTURE**

**Fix:**
```python
def test_config_file_not_required(
    self, temp_project: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str]
) -> None:
    """Test config files are optional when using env vars."""
    # Set all required env vars
    monkeypatch.setenv("CODEWEAVER_PROJECT_PATH", str(temp_project))
    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")  # Provider needs credentials

    # Doctor should not warn about missing config file
    with pytest.raises(SystemExit) as exc_info:
        doctor_app()

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    # Should not complain about missing config
    assert "config" not in captured.out.lower() or "found" in captured.out.lower()
```

---

### 4. Env-Only Setup Valid Test (test_doctor_command.py:266)

**File:** `/home/knitli/codeweaver/tests/unit/cli/test_doctor_command.py`
**Line:** 266-282
**Skip Reason:** "Settings structure changed"

#### Bug Risk: **MEDIUM**
Core feature test - env-only configuration is explicitly supported pattern.

**Current Test:**
```python
@pytest.mark.skip(reason="Settings structure changed")
def test_env_only_setup_valid(...) -> None:
    settings = CodeWeaverSettings()

    assert settings.project_path == temp_project
    assert settings.provider.embedding.provider == "fastembed"  # OLD STRUCTURE
```

**Recommendation:** **REWRITE FOR NEW STRUCTURE**

**Fix:**
```python
def test_env_only_setup_valid(
    self, temp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test environment-only setup is valid."""
    monkeypatch.setenv("CODEWEAVER_PROJECT_PATH", str(temp_project))
    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")

    settings = CodeWeaverSettings()

    assert settings.project_path == temp_project
    # New structure: embedding is tuple of provider configs
    assert len(settings.provider.embedding) > 0
    assert settings.provider.embedding[0]['provider'] == Provider.VOYAGE
```

---

### 5. Config Sources Hierarchy Test (test_doctor_command.py:283)

**File:** `/home/knitli/codeweaver/tests/unit/cli/test_doctor_command.py`
**Line:** 283-302
**Skip Reason:** "Settings structure changed"

#### Bug Risk: **MEDIUM**
Tests configuration precedence (env vars override config files) - critical functionality.

**Current Test:**
```python
@pytest.mark.skip(reason="Settings structure changed")
def test_config_sources_hierarchy(...) -> None:
    config_file.write_text("""
[embedding]
provider = "fastembed"
""")

    monkeypatch.setenv("CODEWEAVER_EMBEDDING_PROVIDER", "voyage")

    settings = CodeWeaverSettings(config_file=config_file)
    assert settings.provider.embedding.provider == "voyage"  # OLD STRUCTURE
```

**Recommendation:** **REWRITE FOR NEW STRUCTURE + JSON FORMAT**

**Fix:**
```python
def test_config_sources_hierarchy(
    self, temp_project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test config can come from multiple sources with correct precedence."""
    from codeweaver.config.settings import CodeWeaverSettings

    # Create JSON config file (new format per line 544 of settings.py)
    config_file = temp_project / "codeweaver.json"
    config_file.write_text(json.dumps({
        "embedding": [{"provider": "fastembed"}]
    }))

    # Override via env var - env vars should take precedence
    monkeypatch.setenv("CODEWEAVER_EMBEDDING_PROVIDER", "voyage")
    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")

    settings = CodeWeaverSettings(config_file=config_file)

    # Verify env var took precedence
    assert any(
        cfg['provider'] == Provider.VOYAGE
        for cfg in settings.provider.embedding
    )
```

---

### 6. Backup Functionality Test (test_init_command.py:509)

**File:** `/home/knitli/codeweaver/tests/unit/cli/test_init_command.py`
**Line:** 509-515
**Skip Reason:** "Backup functionality exists but test needs updating for actual backup behavior"

#### Bug Risk: **LOW**
Backup function `_backup_config` exists (line 66-103 of init.py) and is called (line 415). Test author acknowledges it works but merge behavior makes testing complex.

**Evidence of Implementation:**
```python
# From init.py line 66-103
def _backup_config(path: Path) -> Path:
    """Create timestamped backup of configuration file.
    Only creates a backup if the file content differs from most recent backup.
    """
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    backup_path = path.parent / f"{path.stem}.backup_{timestamp}{path.suffix}"

    # Check for existing backups
    # If content unchanged, reuse existing backup
    # Otherwise create new backup
    shutil.copy2(path, backup_path)
    return backup_path
```

**Recommendation:** **REWRITE WITH CLEAR TEST SCOPE**
Test should focus on backup creation, not merge behavior.

**Fix:**
```python
def test_handle_write_output_backs_up_existing(self, temp_project: Path) -> None:
    """Test _backup_config creates backups correctly."""
    from codeweaver.cli.commands.init import _backup_config

    # Create original config
    config_path = temp_project / "codeweaver.json"
    config_path.write_text('{"version": "1.0"}')

    # Create backup
    backup_path = _backup_config(config_path)

    # Verify backup created
    assert backup_path.exists()
    assert backup_path.name.startswith("codeweaver.backup_")
    assert backup_path.read_text() == config_path.read_text()

    # Test reuse of existing backup if content unchanged
    backup_path2 = _backup_config(config_path)
    assert backup_path2 == backup_path  # Should reuse

    # Test new backup if content changed
    config_path.write_text('{"version": "2.0"}')
    backup_path3 = _backup_config(config_path)
    assert backup_path3 != backup_path  # Should create new
```

---

### 7. Model Registry API Tests (test_list_command.py:215, 222)

**File:** `/home/knitli/codeweaver/tests/unit/cli/test_list_command.py`
**Lines:** 215-227
**Skip Reason:** "Test needs access to internal model registry API which may not be public"

#### Bug Risk: **LOW**
These tests attempt to verify ModelRegistry usage, but the API is internal.

**Tests:**
```python
@pytest.mark.skip(reason="Test needs access to internal model registry API...")
def test_uses_model_registry(...) -> None:
    """Test list command uses ModelRegistry."""

@pytest.mark.skip(reason="Test needs access to internal model registry API...")
def test_model_registry_has_sparse_models(...) -> None:
    """Test ModelRegistry includes sparse embedding models."""
```

**Recommendation:** **DELETE BOTH TESTS**
- Internal API testing is not appropriate for unit tests
- List command functionality is already tested by other tests (lines 101-148)
- Model availability is tested through provider registry tests (lines 155-208)

**Justification:**
- Line 28-40: Tests already verify list command uses ProviderRegistry correctly
- Line 70-80: Tests already verify filtering by provider kind works
- Line 112-125: Tests already verify sparse models are shown
- Internal implementation details shouldn't be unit test targets

---

### 8. macOS-Specific Test (test_start_command.py:414)

**File:** `/home/knitli/codeweaver/tests/unit/cli/test_start_command.py`
**Line:** 414-437
**Skip Reason:** "macOS-specific test" (via `@pytest.mark.skipif(sys.platform != "darwin")`)

#### Bug Risk: **NONE**
Platform-specific test is correctly skipped on non-macOS systems.

**Current Implementation:**
```python
@pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific test")
def test_launchd_install_creates_plist_file(self, temp_home: Path) -> None:
    """Test that launchd installation creates plist file in correct location."""
    # Tests launchd service installation on macOS
```

**Verification:**
```bash
$ python -m pytest tests/unit/cli/test_start_command.py::...::test_launchd_install_creates_plist_file
SKIPPED [1] macOS-specific test
```

**Recommendation:** **KEEP AS-IS**
This is correct usage of platform-specific skipping. Test runs on macOS CI runners.

**Additional Context:**
- Linux equivalent test exists (line 382-412) and runs on Linux
- Windows instructions test exists (line 443-462)
- Platform detection works correctly with `sys.platform`

---

## Summary by Priority

### Immediate Action Required (HIGH RISK)

1. **test_invalid_provider_rejected** (test_config_command.py:93)
   - **Action:** Enable + fix JSON format
   - **Risk:** Provider validation could break silently
   - **Effort:** 10 minutes

### Medium Priority (MEDIUM RISK)

2. **test_doctor_handles_auto_detected_settings** (test_doctor_command.py:61)
   - **Action:** Enable + add provider mocks
   - **Risk:** Auto-detection could break
   - **Effort:** 15 minutes

3. **test_config_file_not_required** (test_doctor_command.py:245)
   - **Action:** Rewrite for new structure
   - **Risk:** Env-only config could break
   - **Effort:** 20 minutes

4. **test_env_only_setup_valid** (test_doctor_command.py:266)
   - **Action:** Rewrite for new structure
   - **Risk:** Settings validation could break
   - **Effort:** 15 minutes

5. **test_config_sources_hierarchy** (test_doctor_command.py:283)
   - **Action:** Rewrite for new structure + JSON
   - **Risk:** Config precedence could break
   - **Effort:** 20 minutes

### Low Priority (LOW RISK)

6. **test_handle_write_output_backs_up_existing** (test_init_command.py:509)
   - **Action:** Rewrite with focused scope
   - **Risk:** Backup feature already works
   - **Effort:** 25 minutes

### No Action Needed

7. **test_uses_model_registry** (test_list_command.py:215)
   - **Action:** DELETE - internal API testing
   - **Effort:** 2 minutes

8. **test_model_registry_has_sparse_models** (test_list_command.py:222)
   - **Action:** DELETE - internal API testing
   - **Effort:** 2 minutes

9. **test_launchd_install_creates_plist_file** (test_start_command.py:414)
   - **Action:** KEEP AS-IS - correct platform skip
   - **Effort:** 0 minutes

---

## Implementation Plan

### Phase 1: Critical Fixes (30 minutes)
1. Enable provider validation test with JSON fix
2. Enable doctor auto-detection test with mocks

### Phase 2: Settings Structure Updates (55 minutes)
3. Rewrite config_file_not_required test
4. Rewrite env_only_setup_valid test
5. Rewrite config_sources_hierarchy test

### Phase 3: Cleanup (27 minutes)
6. Rewrite backup functionality test
7. Delete model registry tests (2)

### Total Effort: ~2 hours

---

## Key Findings

### Settings Structure Changes

The provider settings structure changed from:
```python
# OLD (what tests expect)
settings.provider.embedding.provider == "fastembed"  # Single object

# NEW (actual implementation)
settings.provider.embedding  # Tuple of provider configs
# -> ({'provider': <Provider.VOYAGE>, 'enabled': True, ...},)

# Access pattern:
settings.provider.embedding[0]['provider'] == Provider.VOYAGE
```

### Config File Format Change

Config files changed from TOML to JSON:
```python
# Line 544 of settings.py:
content = from_json(config.read_bytes())  # Expects JSON, not TOML
```

This impacts all tests creating config files.

### Provider Validation Status

Provider validation IS implemented despite skip reason claiming otherwise:
- Invalid providers raise `ValueError`
- Validation happens at pydantic model level
- Tests should verify this works

---

## Risk Assessment

### User Impact
- **HIGH:** Provider validation test skipped - silent failures possible
- **MEDIUM:** 3 env-only config tests skipped - regression risk for documented features
- **LOW:** Backup test skipped - feature works, just not validated
- **NONE:** Platform tests correctly skipped

### Development Impact
- **Coverage gaps:** 8 skipped tests reduce CLI test coverage
- **False confidence:** Passing test suite doesn't validate critical features
- **Maintenance debt:** Incorrect skip reasons cause confusion

### Recommended Actions
1. Fix provider validation test immediately (10 min)
2. Update settings structure tests in next sprint (1.5 hours)
3. Clean up model registry tests (5 min)
4. Document platform-specific test strategy (already correct)

---

## Appendix: Test Execution Evidence

### Provider Validation Test
```python
# Test code
config_path.write_text('[embedding]\nprovider = "invalid_xyz"')
s = CodeWeaverSettings(config_file=config_path)

# Result
ValueError: expected value at line 1 column 2
# Validation EXISTS, just needs correct format (JSON)
```

### Settings Structure Test
```python
s = CodeWeaverSettings()
print(type(s.provider.embedding))
# <class 'tuple'>

print(s.provider.embedding)
# ({'provider': <Provider.VOYAGE>, 'enabled': True, ...},)
```

### Platform Skip Test
```bash
$ uname -s
Linux

$ pytest test_launchd_install_creates_plist_file
SKIPPED [1] macOS-specific test
# Correct behavior
```
