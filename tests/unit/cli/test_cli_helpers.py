# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Helper utilities for testing CLI commands.

Since cyclopts doesn't have a built-in testing module, we provide
helpers to test CLI commands directly.
"""

from __future__ import annotations

import subprocess
import sys

from pathlib import Path
from typing import Any

import pytest


pytestmark = [pytest.mark.unit]


class CliResult:
    """Result from a CLI command execution."""

    def __init__(self, exit_code: int, output: str, stderr: str = ""):
        self.exit_code = exit_code
        self.output = output
        self.stderr = stderr


def run_cli_command(
    command_args: list[str], cwd: Path | None = None, env: dict[str, str] | None = None
) -> CliResult:
    """Run a CLI command and return the result.

    Args:
        command_args: Command and arguments (e.g., ["codeweaver", "config", "init"])
        cwd: Working directory
        env: Environment variables

    Returns:
        CliResult with exit code and output
    """
    result = subprocess.run(
        [sys.executable, "-m", "codeweaver.cli", *command_args[1:]],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )

    return CliResult(exit_code=result.returncode, output=result.stdout, stderr=result.stderr)


def invoke_command_function(func: Any, *args: Any, **kwargs: Any) -> Any:
    """Invoke a command function directly for testing.

    Args:
        func: Command function to invoke
        args: Positional arguments
        kwargs: Keyword arguments

    Returns:
        Function result
    """
    try:
        return func(*args, **kwargs)
    except SystemExit as e:
        # Command may exit, capture exit code
        return e.code
