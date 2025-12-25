# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from codeweaver_daemon import _get_daemon_cmd_and_args, check_daemon_health


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_daemon_health_success() -> None:
    """Test that the daemon health check returns True on a successful health check."""
    mock_response = MagicMock()
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await check_daemon_health()
        assert result is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_check_daemon_health_failure() -> None:
    """Test that the daemon health check returns False on a failed health check."""
    mock_client = AsyncMock()
    mock_client.get.side_effect = Exception("Connection refused")
    mock_client.__aenter__.return_value = mock_client

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await check_daemon_health()
        assert result is False


@pytest.mark.unit
def test_get_daemon_cmd_and_args_default() -> None:
    """Test that the daemon command and arguments default to python -m codeweaver.cli start when no binary is found."""
    with patch("shutil.which", return_value=None):
        cmd, args = _get_daemon_cmd_and_args(None, None, None, None, None, None)
        assert "python" in cmd.lower()
        assert "-m" in args
        assert "codeweaver.cli" in args
        assert "start" in args


@pytest.mark.unit
def test_get_daemon_cmd_and_args_with_binary() -> None:
    """Test that the daemon command and arguments use the binary when it is found."""
    with patch("shutil.which", return_value="/usr/local/bin/cw"):
        cmd, args = _get_daemon_cmd_and_args(None, None, None, None, None, None)
        assert cmd == "/usr/local/bin/cw"
        assert args == ["start"]
