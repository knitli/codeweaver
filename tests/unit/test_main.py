import pytest
from unittest.mock import patch
from pathlib import Path
from codeweaver.main import run

@pytest.mark.asyncio
@patch("codeweaver.main._run_stdio_server")
@patch("codeweaver.main._run_http_server")
async def test_run_stdio_transport(mock_run_http_server, mock_run_stdio_server):
    """Test that run() calls _run_stdio_server when transport is 'stdio'."""
    await run(
        config_file=Path("/fake/config.yaml"),
        project_path=Path("/fake/project"),
        host="127.0.0.1",
        port=8080,
        transport="stdio",
        verbose=True,
        debug=False,
    )

    mock_run_stdio_server.assert_called_once_with(
        config_file=Path("/fake/config.yaml"),
        project_path=Path("/fake/project"),
        host="127.0.0.1",
        port=8080,
        verbose=True,
        debug=False,
    )
    mock_run_http_server.assert_not_called()

@pytest.mark.asyncio
@patch("codeweaver.main._run_stdio_server")
@patch("codeweaver.main._run_http_server")
async def test_run_streamable_http_transport(mock_run_http_server, mock_run_stdio_server):
    """Test that run() calls _run_http_server when transport is 'streamable-http'."""
    await run(
        config_file=None,
        project_path=None,
        host="0.0.0.0",
        port=9090,
        transport="streamable-http",
        verbose=False,
        debug=True,
    )

    mock_run_http_server.assert_called_once_with(
        config_file=None,
        project_path=None,
        host="0.0.0.0",
        port=9090,
        verbose=False,
        debug=True,
    )
    mock_run_stdio_server.assert_not_called()
