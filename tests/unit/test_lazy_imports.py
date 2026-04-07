# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Regression tests for lazy-import discipline of optional provider SDKs.

These exist to catch a specific class of bug that's invisible in dev environments
that always have every extra installed: a module under `src/codeweaver/` doing a
top-level `import openai` (or any other optional SDK) instead of routing through
`lateimport`. Such a module will import fine in dev but crash at import time for
any user who runs a minimal `pip install code-weaver` — because the SDK has moved
out of base dependencies into a per-provider extra.

The test runs `import codeweaver` in a *fresh subprocess* and inspects the resulting
sys.modules to see whether any optional SDK leaked in. Subprocess isolation is the
only way to get a deterministic answer: purging modules in-process leaves other
tests' import state unpredictable, and the SDKs may already be cached in the main
pytest interpreter for reasons unrelated to codeweaver.
"""

import json
import subprocess
import sys
import textwrap

import pytest


# Every optional SDK that was moved out of base dependencies by the pyproject
# refactor. If any of these show up in sys.modules after `import codeweaver`,
# something in the package is importing them at module top level instead of
# lazily, which will break bare-base installs.
#
# Match both the top-level package name and any submodule (e.g. `boto3` AND
# `boto3.session`). `google.genai` is the submodule path used by the
# `google-genai` PyPI package; matching on `google` alone would be wrong
# because `google` is a namespace package used by many unrelated libraries.
OPTIONAL_SDK_PREFIXES: tuple[str, ...] = (
    "boto3",
    "botocore",
    "cohere",
    "google.genai",
    "huggingface_hub",
    "mistralai",
    "openai",
)


@pytest.mark.unit
@pytest.mark.install_smoke
def test_base_import_does_not_pull_optional_provider_sdks() -> None:
    """Importing `codeweaver` must not pull any optional provider SDK.

    Optional provider SDKs (boto3, botocore, cohere, google-genai, huggingface-hub,
    mistralai, openai) live in per-provider extras, not base
    `[project.dependencies]`. A top-level `import openai` anywhere in
    `src/codeweaver/` would crash base installs. This test runs `import codeweaver` in
    a clean subprocess and asserts none of those SDKs ended up in `sys.modules` as a
    side effect.

    If this test fails: find the offending module with `grep -rn "^import <sdk>\\|^from
    <sdk>" src/codeweaver/` and route the import through `lateimport` (see
    `codeweaver/core/utils/lazy_importer` history or `lateimport` package docs).
    """
    probe = textwrap.dedent(
        f"""
        import importlib, json, sys
        importlib.import_module("codeweaver")
        prefixes = {OPTIONAL_SDK_PREFIXES!r}
        leaked = sorted(
            m for m in sys.modules
            if any(m == p or m.startswith(f"{{p}}.") for p in prefixes)
        )
        print(json.dumps(leaked))
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"Subprocess `import codeweaver` failed (returncode={result.returncode}).\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

    leaked = json.loads(result.stdout.strip().splitlines()[-1])
    assert not leaked, (
        f"Top-level import of `codeweaver` pulled {len(leaked)} optional provider SDK "
        f"module(s) into sys.modules:\n  {leaked}\n\n"
        f"These SDKs live in per-provider extras, not base dependencies — importing "
        f"them at module top level will crash bare-base installs. Route the offending "
        f"import through `lateimport` so it only fires when the provider is selected."
    )
