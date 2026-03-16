# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Tests for the conditional transport branching in codeweaver.main.run()."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from codeweaver.main import run


pytestmark = [pytest.mark.unit]

_TRANSPORT_CASES = [
    pytest.param(
        "stdio", "codeweaver.main._run_stdio_server", "codeweaver.main._run_http_server", id="stdio"
    ),
    pytest.param(
        "streamable-http",
        "codeweaver.main._run_http_server",
        "codeweaver.main._run_stdio_server",
        id="streamable-http",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("config_file", "project_path"),
    [
        pytest.param(Path("/fake/config.yaml"), Path("/fake/project"), id="with-paths"),
        pytest.param(None, None, id="none-paths"),
    ],
)
@pytest.mark.parametrize(("transport", "expected_patch", "other_patch"), _TRANSPORT_CASES)
async def test_run_dispatches_to_correct_server(
    transport: str,
    expected_patch: str,
    other_patch: str,
    config_file: Path | None,
    project_path: Path | None,
) -> None:
    """Test that run() calls the correct server helper for each transport value."""
    host = "127.0.0.1"
    port = 8080

    with (
        patch(expected_patch, new_callable=AsyncMock) as mock_expected,
        patch(other_patch, new_callable=AsyncMock) as mock_other,
    ):
        await run(
            config_file=config_file,
            project_path=project_path,
            host=host,
            port=port,
            transport=transport,
            verbose=False,
            debug=False,
        )

        mock_expected.assert_awaited_once_with(
            config_file=config_file,
            project_path=project_path,
            host=host,
            port=port,
            transport=transport,
            verbose=False,
            debug=False,
        )
        mock_other.assert_not_awaited()
