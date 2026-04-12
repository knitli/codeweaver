#!/usr/bin/env sh
# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
#
# Install the workspace wheels with a given profile's extras into an existing
# venv and run the install_smoke pytest suite against it. Shared between the
# `mise run test-profiles` local runner and the `_reusable-install-smoke.yml`
# matrix workflow so wheel discovery, install flags, and pytest invocation
# stay identical across both entry points.
#
# Usage:
#     install-smoke.sh VENV_PY DIST_DIR PROFILE [JUNIT_OUT]
#
# Args:
#   VENV_PY    - Path to the python interpreter of an already-created venv.
#                The caller is responsible for venv creation so this script
#                doesn't need to know about uv vs virtualenv vs conda etc.
#   DIST_DIR   - Directory containing the three workspace wheels
#                (code_weaver, code_weaver_daemon, code_weaver_tokenizers).
#   PROFILE    - Extras profile name. "base" means install the root wheel
#                with no extras; any other value N installs
#                `code_weaver-<ver>-py3-none-any.whl[N]`.
#   JUNIT_OUT  - Optional junit-xml output path. When present, pytest writes
#                a junit report there (used by CI to upload cell results).
#
# Assumes `uv` is on PATH. Both call sites already guarantee that: mise has
# `tools.uv = "latest"` on the task, and the workflow's setup-uv-env action
# drops uv on PATH before invoking this script.
set -e

if [ "$#" -lt 3 ]; then
    echo "usage: install-smoke.sh VENV_PY DIST_DIR PROFILE [JUNIT_OUT]" >&2
    exit 2
fi

VENV_PY="$1"
DIST_DIR="$2"
PROFILE="$3"
JUNIT_OUT="${4:-}"

# `find -print -quit` bails after the first match and tolerates spaces in
# filenames (unlike `ls | head -n 1`). Empty output means no match, which the
# next block detects and fails loudly.
ROOT_WHEEL=$(find "$DIST_DIR" -maxdepth 1 -type f -name 'code_weaver-*.whl' -print -quit)
DAEMON_WHEEL=$(find "$DIST_DIR" -maxdepth 1 -type f -name 'code_weaver_daemon-*.whl' -print -quit)
TOKENIZERS_WHEEL=$(find "$DIST_DIR" -maxdepth 1 -type f -name 'code_weaver_tokenizers-*.whl' -print -quit)

if [ -z "$ROOT_WHEEL" ] || [ -z "$DAEMON_WHEEL" ] || [ -z "$TOKENIZERS_WHEEL" ]; then
    echo "ERROR: one or more workspace wheels missing from ${DIST_DIR}" >&2
    ls -la "$DIST_DIR" >&2 || true
    exit 1
fi

if [ "$PROFILE" = "base" ]; then
    ROOT_SPEC="$ROOT_WHEEL"
else
    ROOT_SPEC="${ROOT_WHEEL}[${PROFILE}]"
fi

# Install the root wheel with its profile's extras plus the two workspace
# siblings explicitly. --find-links lets uv resolve the sibling version pins
# against the local dist/ instead of PyPI (where they don't exist yet).
# pytest + plugins are installed because the smoke suite needs a test runner
# but the wheel itself (correctly) doesn't ship dev dependencies.
uv pip install \
    --python "$VENV_PY" \
    --find-links "$DIST_DIR" \
    "$ROOT_SPEC" \
    "$DAEMON_WHEEL" \
    "$TOKENIZERS_WHEEL" \
    "pytest>=9" \
    "pytest-asyncio>=1" \
    "pytest-timeout>=2"

# Pytest invocation notes:
#   -o "addopts=" clears the project's --cov-fail-under / --cov=codeweaver
#     defaults. Coverage doesn't work in isolation because the source tree
#     isn't on sys.path (which is the whole point — we're testing the
#     installed wheel, not `src/`).
#   -o "pythonpath=" clears the project's `pythonpath = ["src"]` setting.
#     If we left it, pytest would prepend the source tree to sys.path and
#     `import codeweaver` would resolve there instead of the installed
#     wheel, defeating the entire isolation.
#   --import-mode=importlib matches the rest of the project's test runner.
if [ -n "$JUNIT_OUT" ]; then
    "$VENV_PY" -m pytest \
        tests/unit/smoke \
        -m install_smoke \
        -o "addopts=" \
        -o "pythonpath=" \
        --import-mode=importlib \
        --junit-xml="$JUNIT_OUT" \
        -v
else
    "$VENV_PY" -m pytest \
        tests/unit/smoke \
        -m install_smoke \
        -o "addopts=" \
        -o "pythonpath=" \
        --import-mode=importlib \
        -v
fi
