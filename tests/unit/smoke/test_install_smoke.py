# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Install-profile smoke tests.

These are the tests the install-profile matrix workflow runs against each
(python x extras) cell to verify that a minimal wheel install is actually
usable — not just that dependencies resolve. Each test exercises a single,
narrow capability that any valid install profile must support: importing
the public API, importing the MCP server module, etc.

All tests in this module must:

- Use subprocess isolation. The main pytest interpreter has every extra
  installed, so in-process assertions about "is this importable with only
  base deps?" are meaningless. A subprocess gives us a clean interpreter
  that only sees what's currently installed in the venv pytest is running
  in — which, under the matrix workflow, is the minimal profile under test.
- Check BOTH exit code AND that stderr contains no "Traceback" string.
  `codeweaver/cli/__main__.py` currently has an error handler that can
  print a rich-panel traceback and still return exit 0 (see #300), so
  relying on the exit code alone is insufficient.
- Complete in under ~2 seconds per test. The matrix runs 9+ cells and
  smoke budget is a few minutes total.
- Carry both `@pytest.mark.unit` and `@pytest.mark.install_smoke` so they
  run in the normal unit suite AND can be selected alone via
  `pytest -m install_smoke` in the matrix workflow.
"""

import subprocess
import sys

import pytest


def _run_probe(code: str, timeout: float = 15.0) -> subprocess.CompletedProcess[str]:
    """Execute a short Python probe in a fresh subprocess and return the result.

    Uses `sys.executable` so the subprocess runs in the same venv as pytest.
    Tests are responsible for asserting on returncode, stdout, and stderr.

    Timeout note: the module docstring's "~2 seconds per test" target reflects
    what a successful probe should take on a lean install profile; the 15s
    timeout is a deadlock/hang backstop, not the expected budget. Cold-start
    `import codeweaver` in a full-gpu dev env can take 8-10s because
    transitive imports pull in torch, transformers, and onnxruntime, so
    dropping below ~15s would produce false positives locally. Lean matrix
    cells finish in well under 2 seconds.
    """
    return subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False, timeout=timeout
    )


def _assert_clean(result: subprocess.CompletedProcess[str], probe_description: str) -> None:
    """Assert a probe exited 0 AND its stderr contains no Python traceback.

    Exit code alone is insufficient because the CLI error handler can print
    tracebacks and still return 0 (see knitli/codeweaver#300). This helper
    catches both failure modes in one place.
    """
    assert result.returncode == 0, (
        f"{probe_description} exited with {result.returncode}.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert "Traceback" not in result.stderr, (
        f"{probe_description} exited 0 but stderr contains a Python traceback — "
        f"the process likely caught an exception in a rich-panel handler and "
        f"silently returned success. See knitli/codeweaver#300.\n"
        f"stderr:\n{result.stderr}"
    )


def _last_nonempty_line(stdout: str) -> str:
    """Return the last non-empty stripped line of stdout.

    Probes print a single-line result as their last action, but transitive
    imports can emit arbitrary warnings to stdout (e.g. onnxruntime's CUDA
    version warnings in GPU-adjacent envs). Reading the last non-empty line
    keeps probes robust to that noise without trying to silence individual
    offenders.
    """
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    return lines[-1] if lines else ""


@pytest.mark.unit
@pytest.mark.install_smoke
def test_public_api_importable() -> None:
    """`from codeweaver import find_code` must work on any valid install profile.

    `find_code` is the one documented public entry point. Any install profile
    that can't import it is broken by definition, regardless of which extras
    are selected. This test catches top-level import failures in the package
    root and the `find_code` re-export chain.
    """
    # The contract is "callable", not "plain function". find_code could
    # legitimately become a `functools.partial`, a class with __call__, or
    # a decorator-wrapped function in the future — any of those still
    # satisfies `from codeweaver import find_code; find_code(...)`. Assert
    # on behavior (callable), not on `type(find_code).__name__`.
    result = _run_probe(
        "from codeweaver import find_code\n"
        "assert callable(find_code), f'find_code is not callable: {type(find_code).__name__}'\n"
        "print('PROBE_RESULT:callable')"
    )
    _assert_clean(result, "`from codeweaver import find_code`")
    last_line = _last_nonempty_line(result.stdout)
    assert last_line == "PROBE_RESULT:callable", (
        f"Expected `find_code` to be callable (last stdout line "
        f"'PROBE_RESULT:callable'), got: {last_line!r}\n"
        f"full stdout:\n{result.stdout}"
    )


@pytest.mark.unit
@pytest.mark.install_smoke
def test_server_mcp_module_importable() -> None:
    """`import codeweaver.server.mcp.server` must succeed on any valid profile.

    The MCP server module is the entry point for `cw server` / FastMCP stdio
    and HTTP transports. It pulls in a significant chunk of the server-side
    dependency graph (fastmcp, mcp, uvicorn, …) and has historically been
    a hotspot for import-time regressions when provider modules sneak
    top-level SDK imports into their module chain. A bare `import` is enough
    to catch those — we don't need to instantiate the server.
    """
    result = _run_probe("import codeweaver.server.mcp.server")
    _assert_clean(result, "`import codeweaver.server.mcp.server`")
