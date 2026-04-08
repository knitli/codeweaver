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
import re
import subprocess
import sys
import textwrap
import tomllib

from pathlib import Path

import pytest


# Map pypi package names (as they appear in `[project.optional-dependencies]`)
# to the top-level import prefixes they provide. Used to translate the extras
# list into a set of sys.modules prefixes to scan for leaks. Most packages
# follow the "name.replace('-', '_')" convention and don't need an override
# entry; this dict only exists for the exceptions.
#
# Namespace packages are the main reason this exists: `google` is shared by
# protobuf, grpcio, googleapis-common-protos, google-genai, google-auth, …,
# so checking for a bare `google` prefix would flag unrelated transitives
# and produce false positives. We list the specific `google.*` submodules
# we know come from the `google` extra instead.
#
# `boto3` pulls in `botocore` as a runtime dependency; both live in the
# same extra and leaking either is a bug, so we map boto3 to both prefixes.
_PACKAGE_TO_IMPORT_PREFIXES: dict[str, tuple[str, ...]] = {
    "boto3": ("boto3", "botocore"),
    "google-genai": ("google.genai", "google.auth"),
    "google-auth": ("google.auth",),
    "huggingface-hub": ("huggingface_hub",),
    "sentence-transformers": ("sentence_transformers",),
    "qdrant-client": ("qdrant_client",),
    "pydantic-ai": ("pydantic_ai",),
    "pydantic-ai-slim": ("pydantic_ai",),
    "pydantic-settings": ("pydantic_settings",),
    "py-cpuinfo": ("cpuinfo",),
    "tavily-python": ("tavily",),
    "exa-py": ("exa_py",),
}


def _extract_package_name(requirement: str) -> str:
    """Extract the bare package name from a PEP 508 requirement string."""
    # Strip extras (`pkg[extra]`), version specifiers, environment markers,
    # and whitespace. Leaves just the distribution name.
    match = re.match(r"^\s*([A-Za-z0-9_.\-]+)", requirement)
    return match.group(1) if match else ""


def _derive_optional_sdk_prefixes() -> tuple[str, ...]:
    """Derive the leak-check prefix list from `pyproject.toml` extras.

    Walking `[project.optional-dependencies]` and mapping each package to
    its import prefix means new provider SDKs are covered automatically as
    long as either their pypi name matches the importable module (the usual
    case) or they appear in `_PACKAGE_TO_IMPORT_PREFIXES`. Falls back to a
    hardcoded minimum set if pyproject.toml can't be located (e.g. running
    from an installed wheel with no repo context), which keeps the test
    runnable in the install-profile matrix workflow even though that's
    normally checked out with the repo.
    """
    # Walk up from this file to find pyproject.toml. tests/unit/smoke/ → repo
    # root is three parents up; use rglob up the tree so a future reorganize
    # doesn't silently break this.
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "pyproject.toml"
        if candidate.is_file():
            pyproject_path = candidate
            break
    else:
        # Fallback: minimum known-optional SDK set for installed-wheel runs.
        return (
            "boto3",
            "botocore",
            "cohere",
            "google.auth",
            "google.genai",
            "huggingface_hub",
            "mistralai",
            "openai",
        )

    with pyproject_path.open("rb") as f:
        data = tomllib.load(f)

    # CodeWeaver uses PEP 621 dynamic dependencies driven by the
    # uv-dynamic-versioning hatch metadata hook; both base deps and extras
    # live under the hook's table at source time. `[project.dependencies]`
    # and `[project.optional-dependencies]` are only populated at wheel
    # build time, so they're empty when read from the source tree. Prefer
    # the hook table, fall back to the static PEP 621 tables for any future
    # reorg that inlines them.
    hook_cfg = (
        data
        .get("tool", {})
        .get("hatch", {})
        .get("metadata", {})
        .get("hooks", {})
        .get("uv-dynamic-versioning", {})
    )
    base_requirements: list[str] = hook_cfg.get("dependencies") or data.get("project", {}).get(
        "dependencies", []
    )
    extras: dict[str, list[str]] = hook_cfg.get("optional-dependencies") or data.get(
        "project", {}
    ).get("optional-dependencies", {})

    # Build the set of base package names first — anything already in base
    # deps is legitimately importable and must NOT flag as a leak even if
    # it also appears in an extra (e.g. pydantic-settings is base and also
    # shows up in extras that add sub-extras to it).
    base_names: set[str] = set()
    for req in base_requirements:
        pkg_name = _extract_package_name(req)
        if pkg_name:
            base_names.add(pkg_name.lower())

    def _prefixes_for(pkg_lower: str) -> tuple[str, ...]:
        mapped = _PACKAGE_TO_IMPORT_PREFIXES.get(pkg_lower)
        return mapped if mapped is not None else (pkg_lower.replace("-", "_"),)

    # Start from all extras-introduced prefixes, then remove anything that
    # a base dep already legitimizes.
    prefixes: set[str] = set()
    for requirements in extras.values():
        for req in requirements:
            pkg_name = _extract_package_name(req)
            if not pkg_name:
                continue
            pkg_lower = pkg_name.lower()
            # Skip self-reference extras (`code-weaver[other-extra]`).
            if pkg_lower.startswith(("code-weaver", "code_weaver")):
                continue
            if pkg_lower in base_names:
                continue
            prefixes.update(_prefixes_for(pkg_lower))

    base_prefixes: set[str] = set()
    for name in base_names:
        base_prefixes.update(_prefixes_for(name))
    prefixes -= base_prefixes

    return tuple(sorted(prefixes))


OPTIONAL_SDK_PREFIXES: tuple[str, ...] = _derive_optional_sdk_prefixes()


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
    <sdk>" src/codeweaver/` and route the import through `lateimport` (for examples in
    this repo, search `src/codeweaver/` for `lateimport`; also see the `lateimport`
    package docs).
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
        [sys.executable, "-c", probe], capture_output=True, text=True, check=False, timeout=30
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
