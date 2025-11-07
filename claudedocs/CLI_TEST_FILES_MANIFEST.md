<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

[38;5;238m─────┬──────────────────────────────────────────────────────────────────────────[0m
     [38;5;238m│ [0m[1mSTDIN[0m
[38;5;238m─────┼──────────────────────────────────────────────────────────────────────────[0m
[38;5;238m   1[0m [38;5;238m│[0m [38;2;248;248;242m# CLI Test Suite - File Manifest[0m
[38;5;238m   2[0m [38;5;238m│[0m 
[38;5;238m   3[0m [38;5;238m│[0m [38;2;248;248;242mComplete list of all files created for the CLI test suite.[0m
[38;5;238m   4[0m [38;5;238m│[0m 
[38;5;238m   5[0m [38;5;238m│[0m [38;2;248;248;242m## Test Files (6 files - 135+ tests)[0m
[38;5;238m   6[0m [38;5;238m│[0m 
[38;5;238m   7[0m [38;5;238m│[0m [38;2;248;248;242m### Unit Tests (4 files - 95 tests)[0m
[38;5;238m   8[0m [38;5;238m│[0m 
[38;5;238m   9[0m [38;5;238m│[0m [38;2;248;248;242m1. **`tests/unit/cli/test_config_command.py`** (298 lines, 25 tests)[0m
[38;5;238m  10[0m [38;5;238m│[0m [38;2;248;248;242m   - Path: `/home/knitli/codeweaver-mcp/tests/unit/cli/test_config_command.py`[0m
[38;5;238m  11[0m [38;5;238m│[0m [38;2;248;248;242m   - Tests: Config init, profiles, registry integration, env vars[0m
[38;5;238m  12[0m [38;5;238m│[0m 
[38;5;238m  13[0m [38;5;238m│[0m [38;2;248;248;242m2. **`tests/unit/cli/test_doctor_command.py`** (367 lines, 30 tests)[0m
[38;5;238m  14[0m [38;5;238m│[0m [38;2;248;248;242m   - Path: `/home/knitli/codeweaver-mcp/tests/unit/cli/test_doctor_command.py`[0m
[38;5;238m  15[0m [38;5;238m│[0m [38;2;248;248;242m   - Tests: Unset handling, imports, Qdrant detection, env-only configs[0m
[38;5;238m  16[0m [38;5;238m│[0m 
[38;5;238m  17[0m [38;5;238m│[0m [38;2;248;248;242m3. **`tests/unit/cli/test_init_command.py`** (236 lines, 15 tests)[0m
[38;5;238m  18[0m [38;5;238m│[0m [38;2;248;248;242m   - Path: `/home/knitli/codeweaver-mcp/tests/unit/cli/test_init_command.py`[0m
[38;5;238m  19[0m [38;5;238m│[0m [38;2;248;248;242m   - Tests: HTTP streaming, command unification, MCP config[0m
[38;5;238m  20[0m [38;5;238m│[0m 
[38;5;238m  21[0m [38;5;238m│[0m [38;2;248;248;242m4. **`tests/unit/cli/test_list_command.py`** (335 lines, 25 tests)[0m
[38;5;238m  22[0m [38;5;238m│[0m [38;2;248;248;242m   - Path: `/home/knitli/codeweaver-mcp/tests/unit/cli/test_list_command.py`[0m
[38;5;238m  23[0m [38;5;238m│[0m [38;2;248;248;242m   - Tests: Registry usage, sparse embeddings, model registry[0m
[38;5;238m  24[0m [38;5;238m│[0m 
[38;5;238m  25[0m [38;5;238m│[0m [38;2;248;248;242m### Integration Tests (1 file - 20 tests)[0m
[38;5;238m  26[0m [38;5;238m│[0m 
[38;5;238m  27[0m [38;5;238m│[0m [38;2;248;248;242m5. **`tests/integration/cli/test_init_workflows.py`** (262 lines, 15 tests)[0m
[38;5;238m  28[0m [38;5;238m│[0m [38;2;248;248;242m   - Path: `/home/knitli/codeweaver-mcp/tests/integration/cli/test_init_workflows.py`[0m
[38;5;238m  29[0m [38;5;238m│[0m [38;2;248;248;242m   - Tests: Full init workflows, HTTP streaming, multiple clients[0m
[38;5;238m  30[0m [38;5;238m│[0m 
[38;5;238m  31[0m [38;5;238m│[0m [38;2;248;248;242m### E2E Tests (1 file - 15 tests)[0m
[38;5;238m  32[0m [38;5;238m│[0m 
[38;5;238m  33[0m [38;5;238m│[0m [38;2;248;248;242m6. **`tests/e2e/test_user_journeys.py`** (404 lines, 15 tests)[0m
[38;5;238m  34[0m [38;5;238m│[0m [38;2;248;248;242m   - Path: `/home/knitli/codeweaver-mcp/tests/e2e/test_user_journeys.py`[0m
[38;5;238m  35[0m [38;5;238m│[0m [38;2;248;248;242m   - Tests: User scenarios (quick start, offline, production, team)[0m
[38;5;238m  36[0m [38;5;238m│[0m 
[38;5;238m  37[0m [38;5;238m│[0m [38;2;248;248;242m## Support Files (4 files)[0m
[38;5;238m  38[0m [38;5;238m│[0m 
[38;5;238m  39[0m [38;5;238m│[0m [38;2;248;248;242m7. **`tests/unit/cli/__init__.py`** (5 lines)[0m
[38;5;238m  40[0m [38;5;238m│[0m [38;2;248;248;242m   - Path: `/home/knitli/codeweaver-mcp/tests/unit/cli/__init__.py`[0m
[38;5;238m  41[0m [38;5;238m│[0m [38;2;248;248;242m   - Purpose: Package marker for unit tests[0m
[38;5;238m  42[0m [38;5;238m│[0m 
[38;5;238m  43[0m [38;5;238m│[0m [38;2;248;248;242m8. **`tests/integration/cli/__init__.py`** (5 lines)[0m
[38;5;238m  44[0m [38;5;238m│[0m [38;2;248;248;242m   - Path: `/home/knitli/codeweaver-mcp/tests/integration/cli/__init__.py`[0m
[38;5;238m  45[0m [38;5;238m│[0m [38;2;248;248;242m   - Purpose: Package marker for integration tests[0m
[38;5;238m  46[0m [38;5;238m│[0m 
[38;5;238m  47[0m [38;5;238m│[0m [38;2;248;248;242m9. **`tests/e2e/__init__.py`** (5 lines)[0m
[38;5;238m  48[0m [38;5;238m│[0m [38;2;248;248;242m   - Path: `/home/knitli/codeweaver-mcp/tests/e2e/__init__.py`[0m
[38;5;238m  49[0m [38;5;238m│[0m [38;2;248;248;242m   - Purpose: Package marker for E2E tests[0m
[38;5;238m  50[0m [38;5;238m│[0m 
[38;5;238m  51[0m [38;5;238m│[0m [38;2;248;248;242m10. **`tests/unit/cli/test_cli_helpers.py`** (86 lines)[0m
[38;5;238m  52[0m [38;5;238m│[0m [38;2;248;248;242m    - Path: `/home/knitli/codeweaver-mcp/tests/unit/cli/test_cli_helpers.py`[0m
[38;5;238m  53[0m [38;5;238m│[0m [38;2;248;248;242m    - Purpose: CLI testing utilities (CliResult, run_cli_command)[0m
[38;5;238m  54[0m [38;5;238m│[0m 
[38;5;238m  55[0m [38;5;238m│[0m [38;2;248;248;242m## Enhanced Files (1 file)[0m
[38;5;238m  56[0m [38;5;238m│[0m 
[38;5;238m  57[0m [38;5;238m│[0m [38;2;248;248;242m11. **`tests/conftest.py`** (enhanced)[0m
[38;5;238m  58[0m [38;5;238m│[0m [38;2;248;248;242m    - Path: `/home/knitli/codeweaver-mcp/tests/conftest.py`[0m
[38;5;238m  59[0m [38;5;238m│[0m [38;2;248;248;242m    - Added: CLI-specific fixtures (lines 310-390)[0m
[38;5;238m  60[0m [38;5;238m│[0m [38;2;248;248;242m    - Fixtures: clean_cli_env, isolated_home, cli_test_project, cli_api_keys, reset_cli_settings_cache[0m
[38;5;238m  61[0m [38;5;238m│[0m 
[38;5;238m  62[0m [38;5;238m│[0m [38;2;248;248;242m## Documentation Files (4 files)[0m
[38;5;238m  63[0m [38;5;238m│[0m 
[38;5;238m  64[0m [38;5;238m│[0m [38;2;248;248;242m12. **`tests/CLI_TESTS_README.md`** (507 lines)[0m
[38;5;238m  65[0m [38;5;238m│[0m [38;2;248;248;242m    - Path: `/home/knitli/codeweaver-mcp/tests/CLI_TESTS_README.md`[0m
[38;5;238m  66[0m [38;5;238m│[0m [38;2;248;248;242m    - Purpose: Complete test suite documentation[0m
[38;5;238m  67[0m [38;5;238m│[0m [38;2;248;248;242m    - Contents: Test organization, running tests, fixtures, validation[0m
[38;5;238m  68[0m [38;5;238m│[0m 
[38;5;238m  69[0m [38;5;238m│[0m [38;2;248;248;242m13. **`claudedocs/CLI_TESTING_COMPLETE.md`** (396 lines)[0m
[38;5;238m  70[0m [38;5;238m│[0m [38;2;248;248;242m    - Path: `/home/knitli/codeweaver-mcp/claudedocs/CLI_TESTING_COMPLETE.md`[0m
[38;5;238m  71[0m [38;5;238m│[0m [38;2;248;248;242m    - Purpose: Implementation status and next steps[0m
[38;5;238m  72[0m [38;5;238m│[0m [38;2;248;248;242m    - Contents: Status, coverage, next steps, evidence sources[0m
[38;5;238m  73[0m [38;5;238m│[0m 
[38;5;238m  74[0m [38;5;238m│[0m [38;2;248;248;242m14. **`claudedocs/CLI_TEST_SUITE_SUMMARY.md`** (271 lines)[0m
[38;5;238m  75[0m [38;5;238m│[0m [38;2;248;248;242m    - Path: `/home/knitli/codeweaver-mcp/claudedocs/CLI_TEST_SUITE_SUMMARY.md`[0m
[38;5;238m  76[0m [38;5;238m│[0m [38;2;248;248;242m    - Purpose: Executive summary[0m
[38;5;238m  77[0m [38;5;238m│[0m [38;2;248;248;242m    - Contents: Overview, coverage, running tests, success criteria[0m
[38;5;238m  78[0m [38;5;238m│[0m 
[38;5;238m  79[0m [38;5;238m│[0m [38;2;248;248;242m15. **`claudedocs/CLI_TEST_FILES_MANIFEST.md`** (this file)[0m
[38;5;238m  80[0m [38;5;238m│[0m [38;2;248;248;242m    - Path: `/home/knitli/codeweaver-mcp/claudedocs/CLI_TEST_FILES_MANIFEST.md`[0m
[38;5;238m  81[0m [38;5;238m│[0m [38;2;248;248;242m    - Purpose: Complete file listing with locations[0m
[38;5;238m  82[0m [38;5;238m│[0m 
[38;5;238m  83[0m [38;5;238m│[0m [38;2;248;248;242m## Total Stats[0m
[38;5;238m  84[0m [38;5;238m│[0m 
[38;5;238m  85[0m [38;5;238m│[0m [38;2;248;248;242m| Category | Files | Lines | Tests |[0m
[38;5;238m  86[0m [38;5;238m│[0m [38;2;248;248;242m|----------|-------|-------|-------|[0m
[38;5;238m  87[0m [38;5;238m│[0m [38;2;248;248;242m| Unit Test Files | 4 | 1,236 | 95 |[0m
[38;5;238m  88[0m [38;5;238m│[0m [38;2;248;248;242m| Integration Test Files | 1 | 262 | 20 |[0m
[38;5;238m  89[0m [38;5;238m│[0m [38;2;248;248;242m| E2E Test Files | 1 | 404 | 15 |[0m
[38;5;238m  90[0m [38;5;238m│[0m [38;2;248;248;242m| Support Files | 4 | 101 | - |[0m
[38;5;238m  91[0m [38;5;238m│[0m [38;2;248;248;242m| Enhanced Files | 1 | 80* | - |[0m
[38;5;238m  92[0m [38;5;238m│[0m [38;2;248;248;242m| Documentation Files | 4 | 1,174 | - |[0m
[38;5;238m  93[0m [38;5;238m│[0m [38;2;248;248;242m| **Total** | **15** | **3,257** | **130+** |[0m
[38;5;238m  94[0m [38;5;238m│[0m 
[38;5;238m  95[0m [38;5;238m│[0m [38;2;248;248;242m*Lines added to conftest.py[0m
[38;5;238m  96[0m [38;5;238m│[0m 
[38;5;238m  97[0m [38;5;238m│[0m [38;2;248;248;242m## Quick Access[0m
[38;5;238m  98[0m [38;5;238m│[0m 
[38;5;238m  99[0m [38;5;238m│[0m [38;2;248;248;242m### Run All Tests[0m
[38;5;238m 100[0m [38;5;238m│[0m [38;2;248;248;242m```bash[0m
[38;5;238m 101[0m [38;5;238m│[0m [38;2;248;248;242m# All CLI tests[0m
[38;5;238m 102[0m [38;5;238m│[0m [38;2;248;248;242mpytest tests/ -m cli -v[0m
[38;5;238m 103[0m [38;5;238m│[0m 
[38;5;238m 104[0m [38;5;238m│[0m [38;2;248;248;242m# By category[0m
[38;5;238m 105[0m [38;5;238m│[0m [38;2;248;248;242mpytest tests/unit/cli/ -v              # Unit tests[0m
[38;5;238m 106[0m [38;5;238m│[0m [38;2;248;248;242mpytest tests/integration/cli/ -v       # Integration tests[0m
[38;5;238m 107[0m [38;5;238m│[0m [38;2;248;248;242mpytest tests/e2e/ -v                   # E2E tests[0m
[38;5;238m 108[0m [38;5;238m│[0m 
[38;5;238m 109[0m [38;5;238m│[0m [38;2;248;248;242m# Specific file[0m
[38;5;238m 110[0m [38;5;238m│[0m [38;2;248;248;242mpytest tests/unit/cli/test_config_command.py -v[0m
[38;5;238m 111[0m [38;5;238m│[0m [38;2;248;248;242m```[0m
[38;5;238m 112[0m [38;5;238m│[0m 
[38;5;238m 113[0m [38;5;238m│[0m [38;2;248;248;242m### View Documentation[0m
[38;5;238m 114[0m [38;5;238m│[0m [38;2;248;248;242m```bash[0m
[38;5;238m 115[0m [38;5;238m│[0m [38;2;248;248;242m# Complete documentation[0m
[38;5;238m 116[0m [38;5;238m│[0m [38;2;248;248;242mcat tests/CLI_TESTS_README.md[0m
[38;5;238m 117[0m [38;5;238m│[0m 
[38;5;238m 118[0m [38;5;238m│[0m [38;2;248;248;242m# Implementation status[0m
[38;5;238m 119[0m [38;5;238m│[0m [38;2;248;248;242mcat claudedocs/CLI_TESTING_COMPLETE.md[0m
[38;5;238m 120[0m [38;5;238m│[0m 
[38;5;238m 121[0m [38;5;238m│[0m [38;2;248;248;242m# Quick summary[0m
[38;5;238m 122[0m [38;5;238m│[0m [38;2;248;248;242mcat claudedocs/CLI_TEST_SUITE_SUMMARY.md[0m
[38;5;238m 123[0m [38;5;238m│[0m 
[38;5;238m 124[0m [38;5;238m│[0m [38;2;248;248;242m# This manifest[0m
[38;5;238m 125[0m [38;5;238m│[0m [38;2;248;248;242mcat claudedocs/CLI_TEST_FILES_MANIFEST.md[0m
[38;5;238m 126[0m [38;5;238m│[0m [38;2;248;248;242m```[0m
[38;5;238m 127[0m [38;5;238m│[0m 
[38;5;238m 128[0m [38;5;238m│[0m [38;2;248;248;242m### Check Test Status[0m
[38;5;238m 129[0m [38;5;238m│[0m [38;2;248;248;242m```bash[0m
[38;5;238m 130[0m [38;5;238m│[0m [38;2;248;248;242m# Collect tests (check for errors)[0m
[38;5;238m 131[0m [38;5;238m│[0m [38;2;248;248;242mpytest tests/ -m cli --collect-only[0m
[38;5;238m 132[0m [38;5;238m│[0m 
[38;5;238m 133[0m [38;5;238m│[0m [38;2;248;248;242m# Run with coverage[0m
[38;5;238m 134[0m [38;5;238m│[0m [38;2;248;248;242mpytest tests/ -m cli --cov=src/codeweaver/cli --cov-report=html[0m
[38;5;238m 135[0m [38;5;238m│[0m 
[38;5;238m 136[0m [38;5;238m│[0m [38;2;248;248;242m# View coverage report[0m
[38;5;238m 137[0m [38;5;238m│[0m [38;2;248;248;242mopen htmlcov/index.html[0m
[38;5;238m 138[0m [38;5;238m│[0m [38;2;248;248;242m```[0m
[38;5;238m 139[0m [38;5;238m│[0m 
[38;5;238m 140[0m [38;5;238m│[0m [38;2;248;248;242m## File Dependencies[0m
[38;5;238m 141[0m [38;5;238m│[0m 
[38;5;238m 142[0m [38;5;238m│[0m [38;2;248;248;242m### Test Files Import Structure[0m
[38;5;238m 143[0m [38;5;238m│[0m [38;2;248;248;242m```[0m
[38;5;238m 144[0m [38;5;238m│[0m [38;2;248;248;242mtest_config_command.py[0m
[38;5;238m 145[0m [38;5;238m│[0m [38;2;248;248;242m├── pytest[0m
[38;5;238m 146[0m [38;5;238m│[0m [38;2;248;248;242m├── cyclopts (via cli commands)[0m
[38;5;238m 147[0m [38;5;238m│[0m [38;2;248;248;242m├── codeweaver.cli.commands.config[0m
[38;5;238m 148[0m [38;5;238m│[0m [38;2;248;248;242m├── codeweaver.common.registry[0m
[38;5;238m 149[0m [38;5;238m│[0m [38;2;248;248;242m└── codeweaver.providers.provider[0m
[38;5;238m 150[0m [38;5;238m│[0m 
[38;5;238m 151[0m [38;5;238m│[0m [38;2;248;248;242mtest_doctor_command.py[0m
[38;5;238m 152[0m [38;5;238m│[0m [38;2;248;248;242m├── pytest[0m
[38;5;238m 153[0m [38;5;238m│[0m [38;2;248;248;242m├── codeweaver.cli.commands.doctor[0m
[38;5;238m 154[0m [38;5;238m│[0m [38;2;248;248;242m├── codeweaver.config.settings[0m
[38;5;238m 155[0m [38;5;238m│[0m [38;2;248;248;242m├── codeweaver.core.types.sentinel[0m
[38;5;238m 156[0m [38;5;238m│[0m [38;2;248;248;242m└── codeweaver.providers.provider[0m
[38;5;238m 157[0m [38;5;238m│[0m 
[38;5;238m 158[0m [38;5;238m│[0m [38;2;248;248;242mtest_init_command.py[0m
[38;5;238m 159[0m [38;5;238m│[0m [38;2;248;248;242m├── pytest[0m
[38;5;238m 160[0m [38;5;238m│[0m [38;2;248;248;242m├── json[0m
[38;5;238m 161[0m [38;5;238m│[0m [38;2;248;248;242m├── codeweaver.cli.commands.init[0m
[38;5;238m 162[0m [38;5;238m│[0m [38;2;248;248;242m└── Path handling[0m
[38;5;238m 163[0m [38;5;238m│[0m 
[38;5;238m 164[0m [38;5;238m│[0m [38;2;248;248;242mtest_list_command.py[0m
[38;5;238m 165[0m [38;5;238m│[0m [38;2;248;248;242m├── pytest[0m
[38;5;238m 166[0m [38;5;238m│[0m [38;2;248;248;242m├── codeweaver.cli.commands.list[0m
[38;5;238m 167[0m [38;5;238m│[0m [38;2;248;248;242m├── codeweaver.common.registry[0m
[38;5;238m 168[0m [38;5;238m│[0m [38;2;248;248;242m└── codeweaver.providers.provider[0m
[38;5;238m 169[0m [38;5;238m│[0m 
[38;5;238m 170[0m [38;5;238m│[0m [38;2;248;248;242mtest_init_workflows.py[0m
[38;5;238m 171[0m [38;5;238m│[0m [38;2;248;248;242m├── pytest[0m
[38;5;238m 172[0m [38;5;238m│[0m [38;2;248;248;242m├── json[0m
[38;5;238m 173[0m [38;5;238m│[0m [38;2;248;248;242m├── codeweaver.cli.commands.init[0m
[38;5;238m 174[0m [38;5;238m│[0m [38;2;248;248;242m└── Path handling[0m
[38;5;238m 175[0m [38;5;238m│[0m 
[38;5;238m 176[0m [38;5;238m│[0m [38;2;248;248;242mtest_user_journeys.py[0m
[38;5;238m 177[0m [38;5;238m│[0m [38;2;248;248;242m├── pytest[0m
[38;5;238m 178[0m [38;5;238m│[0m [38;2;248;248;242m├── tomli[0m
[38;5;238m 179[0m [38;5;238m│[0m [38;2;248;248;242m├── codeweaver.cli.commands.{config,doctor,init,list}[0m
[38;5;238m 180[0m [38;5;238m│[0m [38;2;248;248;242m└── Path handling[0m
[38;5;238m 181[0m [38;5;238m│[0m [38;2;248;248;242m```[0m
[38;5;238m 182[0m [38;5;238m│[0m 
[38;5;238m 183[0m [38;5;238m│[0m [38;2;248;248;242m### Fixture Dependencies[0m
[38;5;238m 184[0m [38;5;238m│[0m [38;2;248;248;242m```[0m
[38;5;238m 185[0m [38;5;238m│[0m [38;2;248;248;242mconftest.py (CLI fixtures)[0m
[38;5;238m 186[0m [38;5;238m│[0m [38;2;248;248;242m├── clean_cli_env → MonkeyPatch[0m
[38;5;238m 187[0m [38;5;238m│[0m [38;2;248;248;242m├── isolated_home → tmp_path + MonkeyPatch[0m
[38;5;238m 188[0m [38;5;238m│[0m [38;2;248;248;242m├── cli_test_project → tmp_path + MonkeyPatch[0m
[38;5;238m 189[0m [38;5;238m│[0m [38;2;248;248;242m├── cli_api_keys → MonkeyPatch[0m
[38;5;238m 190[0m [38;5;238m│[0m [38;2;248;248;242m└── reset_cli_settings_cache → codeweaver.config.settings[0m
[38;5;238m 191[0m [38;5;238m│[0m [38;2;248;248;242m```[0m
[38;5;238m 192[0m [38;5;238m│[0m 
[38;5;238m 193[0m [38;5;238m│[0m [38;2;248;248;242m## Verification Commands[0m
[38;5;238m 194[0m [38;5;238m│[0m 
[38;5;238m 195[0m [38;5;238m│[0m [38;2;248;248;242m### Check All Files Created[0m
[38;5;238m 196[0m [38;5;238m│[0m [38;2;248;248;242m```bash[0m
[38;5;238m 197[0m [38;5;238m│[0m [38;2;248;248;242m# Test files exist[0m
[38;5;238m 198[0m [38;5;238m│[0m [38;2;248;248;242mls -lh tests/unit/cli/test_*.py[0m
[38;5;238m 199[0m [38;5;238m│[0m [38;2;248;248;242mls -lh tests/integration/cli/test_*.py[0m
[38;5;238m 200[0m [38;5;238m│[0m [38;2;248;248;242mls -lh tests/e2e/test_*.py[0m
[38;5;238m 201[0m [38;5;238m│[0m 
[38;5;238m 202[0m [38;5;238m│[0m [38;2;248;248;242m# Documentation exists[0m
[38;5;238m 203[0m [38;5;238m│[0m [38;2;248;248;242mls -lh tests/CLI_TESTS_README.md[0m
[38;5;238m 204[0m [38;5;238m│[0m [38;2;248;248;242mls -lh claudedocs/CLI_TEST*.md[0m
[38;5;238m 205[0m [38;5;238m│[0m 
[38;5;238m 206[0m [38;5;238m│[0m [38;2;248;248;242m# Support files exist[0m
[38;5;238m 207[0m [38;5;238m│[0m [38;2;248;248;242mls -lh tests/unit/cli/__init__.py[0m
[38;5;238m 208[0m [38;5;238m│[0m [38;2;248;248;242mls -lh tests/integration/cli/__init__.py[0m
[38;5;238m 209[0m [38;5;238m│[0m [38;2;248;248;242mls -lh tests/e2e/__init__.py[0m
[38;5;238m 210[0m [38;5;238m│[0m [38;2;248;248;242m```[0m
[38;5;238m 211[0m [38;5;238m│[0m 
[38;5;238m 212[0m [38;5;238m│[0m [38;2;248;248;242m### Count Test Cases[0m
[38;5;238m 213[0m [38;5;238m│[0m [38;2;248;248;242m```bash[0m
[38;5;238m 214[0m [38;5;238m│[0m [38;2;248;248;242m# Count test functions[0m
[38;5;238m 215[0m [38;5;238m│[0m [38;2;248;248;242mgrep -r "def test_" tests/unit/cli/ tests/integration/cli/ tests/e2e/ | wc -l[0m
[38;5;238m 216[0m [38;5;238m│[0m 
[38;5;238m 217[0m [38;5;238m│[0m [38;2;248;248;242m# Count test classes[0m
[38;5;238m 218[0m [38;5;238m│[0m [38;2;248;248;242mgrep -r "class Test" tests/unit/cli/ tests/integration/cli/ tests/e2e/ | wc -l[0m
[38;5;238m 219[0m [38;5;238m│[0m 
[38;5;238m 220[0m [38;5;238m│[0m [38;2;248;248;242m# Show test distribution[0m
[38;5;238m 221[0m [38;5;238m│[0m [38;2;248;248;242mecho "Unit tests:"[0m
[38;5;238m 222[0m [38;5;238m│[0m [38;2;248;248;242mgrep "def test_" tests/unit/cli/test_*.py | wc -l[0m
[38;5;238m 223[0m [38;5;238m│[0m [38;2;248;248;242mecho "Integration tests:"[0m
[38;5;238m 224[0m [38;5;238m│[0m [38;2;248;248;242mgrep "def test_" tests/integration/cli/test_*.py | wc -l[0m
[38;5;238m 225[0m [38;5;238m│[0m [38;2;248;248;242mecho "E2E tests:"[0m
[38;5;238m 226[0m [38;5;238m│[0m [38;2;248;248;242mgrep "def test_" tests/e2e/test_*.py | wc -l[0m
[38;5;238m 227[0m [38;5;238m│[0m [38;2;248;248;242m```[0m
[38;5;238m 228[0m [38;5;238m│[0m 
[38;5;238m 229[0m [38;5;238m│[0m [38;2;248;248;242m### Validate Test Structure[0m
[38;5;238m 230[0m [38;5;238m│[0m [38;2;248;248;242m```bash[0m
[38;5;238m 231[0m [38;5;238m│[0m [38;2;248;248;242m# Check pytest can discover tests[0m
[38;5;238m 232[0m [38;5;238m│[0m [38;2;248;248;242mpytest tests/ -m cli --collect-only[0m
[38;5;238m 233[0m [38;5;238m│[0m 
[38;5;238m 234[0m [38;5;238m│[0m [38;2;248;248;242m# Check for syntax errors[0m
[38;5;238m 235[0m [38;5;238m│[0m [38;2;248;248;242mpython -m py_compile tests/unit/cli/test_*.py[0m
[38;5;238m 236[0m [38;5;238m│[0m [38;2;248;248;242mpython -m py_compile tests/integration/cli/test_*.py[0m
[38;5;238m 237[0m [38;5;238m│[0m [38;2;248;248;242mpython -m py_compile tests/e2e/test_*.py[0m
[38;5;238m 238[0m [38;5;238m│[0m 
[38;5;238m 239[0m [38;5;238m│[0m [38;2;248;248;242m# Validate imports[0m
[38;5;238m 240[0m [38;5;238m│[0m [38;2;248;248;242mpython -c "import tests.unit.cli.test_cli_helpers"[0m
[38;5;238m 241[0m [38;5;238m│[0m [38;2;248;248;242m```[0m
[38;5;238m 242[0m [38;5;238m│[0m 
[38;5;238m 243[0m [38;5;238m│[0m [38;2;248;248;242m## Related Files (Not Created, Referenced)[0m
[38;5;238m 244[0m [38;5;238m│[0m 
[38;5;238m 245[0m [38;5;238m│[0m [38;2;248;248;242m- `/home/knitli/codeweaver-mcp/claudedocs/CLI_CORRECTIONS_PLAN.md` (original plan)[0m
[38;5;238m 246[0m [38;5;238m│[0m [38;2;248;248;242m- `/home/knitli/codeweaver-mcp/.specify/memory/constitution.md` (project constitution)[0m
[38;5;238m 247[0m [38;5;238m│[0m [38;2;248;248;242m- `/home/knitli/codeweaver-mcp/pyproject.toml` (pytest config, lines 368-435)[0m
[38;5;238m 248[0m [38;5;238m│[0m [38;2;248;248;242m- `/home/knitli/codeweaver-mcp/src/codeweaver/cli/commands/*.py` (CLI commands under test)[0m
[38;5;238m 249[0m [38;5;238m│[0m 
[38;5;238m 250[0m [38;5;238m│[0m [38;2;248;248;242m---[0m
[38;5;238m 251[0m [38;5;238m│[0m 
[38;5;238m 252[0m [38;5;238m│[0m [38;2;248;248;242m**Document Version**: 1.0[0m
[38;5;238m 253[0m [38;5;238m│[0m [38;2;248;248;242m**Last Updated**: 2025-01-06[0m
[38;5;238m 254[0m [38;5;238m│[0m [38;2;248;248;242m**Total Files Created**: 15 (11 new + 1 enhanced + 3 documentation)[0m
[38;5;238m─────┴──────────────────────────────────────────────────────────────────────────[0m
