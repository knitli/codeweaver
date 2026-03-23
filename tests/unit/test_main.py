# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

import signal

from unittest.mock import patch

import pytest

from codeweaver.main import _setup_signal_handler


def test_setup_signal_handler_first_interrupt():
    """Test that the first interrupt raises KeyboardInterrupt."""
    with patch("signal.signal") as mock_signal:
        _setup_signal_handler()

        # Get the registered handler
        mock_signal.assert_called_with(signal.SIGINT, mock_signal.call_args[0][1])
        force_shutdown_handler = mock_signal.call_args[0][1]

        # Test first call raises KeyboardInterrupt
        with pytest.raises(KeyboardInterrupt):
            force_shutdown_handler(signal.SIGINT, None)

def test_setup_signal_handler_second_interrupt():
    """Test that the second interrupt exits immediately."""
    with patch("signal.signal") as mock_signal:
        _setup_signal_handler()

        force_shutdown_handler = mock_signal.call_args[0][1]

        # First call raises KeyboardInterrupt
        with pytest.raises(KeyboardInterrupt):
            force_shutdown_handler(signal.SIGINT, None)

        # Second call exits with 1
        with patch("sys.exit") as mock_exit, patch("codeweaver.main.logger.warning") as mock_warning:
            force_shutdown_handler(signal.SIGINT, None)

            mock_warning.assert_called_with("Force shutdown requested, exiting immediately...")
            mock_exit.assert_called_with(1)

def test_setup_signal_handler_suppress_errors():
    """Test that ValueError and OSError are suppressed when setting the signal."""
    # Test ValueError
    with patch("signal.signal", side_effect=ValueError):
        original_handler = _setup_signal_handler()
        assert original_handler is None

    # Test OSError
    with patch("signal.signal", side_effect=OSError):
        original_handler = _setup_signal_handler()
        assert original_handler is None

from unittest.mock import AsyncMock

@pytest.mark.asyncio
@patch("codeweaver.main._run_stdio_server", new_callable=AsyncMock)
async def test_run_stdio_transport(mock_run_stdio):
    """Test that run() with transport='stdio' delegates to _run_stdio_server."""
    from codeweaver.main import run

    await run(
        config_file=None,
        project_path=None,
        host="127.0.0.1",
        port=8080,
        transport="stdio",
        verbose=True,
        debug=False,
    )

    mock_run_stdio.assert_called_once_with(
        config_file=None,
        project_path=None,
        host="127.0.0.1",
        port=8080,
        verbose=True,
        debug=False,
    )


@pytest.mark.asyncio
@patch("codeweaver.main._run_http_server", new_callable=AsyncMock)
async def test_run_http_transport(mock_run_http):
    """Test that run() with transport='streamable-http' delegates to _run_http_server."""
    from codeweaver.main import run

    await run(
        config_file=None,
        project_path=None,
        host="0.0.0.0",
        port=9090,
        transport="streamable-http",
        verbose=False,
        debug=True,
    )

    mock_run_http.assert_called_once_with(
        config_file=None,
        project_path=None,
        host="0.0.0.0",
        port=9090,
        verbose=False,
        debug=True,
    )
