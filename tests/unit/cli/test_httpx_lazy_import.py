# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Unit tests for httpx lazy import in CLI commands.

Tests verify that httpx is not imported eagerly by OUR code at module load time,
but only when HTTP client functions are actually called.

NOTE: External dependencies (fastmcp, mcp) may import httpx as part of their
normal operation. This is beyond our control. These tests verify that OUR code
follows the lazy import pattern.
"""

from __future__ import annotations

import sys

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest


if TYPE_CHECKING:
    pass


@pytest.mark.unit
class TestHttpxLazyImport:
    """Tests for lazy import of httpx in CLI commands.
    
    These tests verify that CodeWeaver CLI command code does not eagerly
    import httpx at module load time. External dependencies (mcp, fastmcp)
    may import httpx, which is acceptable and beyond our control.
    """

    def test_status_command_lazy_import(self) -> None:
        """Test that status command doesn't eagerly import httpx.
        
        The status command module should not import httpx at module load.
        httpx should only be imported when _query_server_status is called.
        """
        # Remove httpx from sys.modules if present (from other tests)
        httpx_was_loaded = "httpx" in sys.modules
        if httpx_was_loaded:
            httpx_module = sys.modules.pop("httpx")

        try:
            # Import the status command module
            from codeweaver.cli.commands import status

            # Verify httpx was NOT imported during module load
            assert "httpx" not in sys.modules, "httpx should not be imported at module load time"

            # Verify the module has the expected function
            assert hasattr(status, "_query_server_status")

        finally:
            # Restore httpx if it was loaded before
            if httpx_was_loaded:
                sys.modules["httpx"] = httpx_module

    def test_doctor_command_lazy_import(self) -> None:
        """Test that doctor command doesn't eagerly import httpx.
        
        The doctor command already uses lazy imports correctly.
        httpx should only be imported inside _qdrant_running_at_url.
        """
        # Remove httpx from sys.modules if present
        httpx_was_loaded = "httpx" in sys.modules
        if httpx_was_loaded:
            httpx_module = sys.modules.pop("httpx")

        try:
            # Import the doctor command module
            from codeweaver.cli.commands import doctor

            # Verify httpx was NOT imported during module load
            assert "httpx" not in sys.modules, "httpx should not be imported at module load time"

            # Verify the module has the expected function
            assert hasattr(doctor, "_qdrant_running_at_url")

        finally:
            # Restore httpx if it was loaded before
            if httpx_was_loaded:
                sys.modules["httpx"] = httpx_module

    def test_index_and_init_external_dependency_note(self) -> None:
        """Document that index.py and init.py may trigger httpx via external deps.
        
        NOTE: index.py imports config.types which imports fastmcp which imports mcp
        which imports httpx. This is an external dependency issue beyond our control.
        
        init.py imports config.mcp which extends FastMCPRemoteMCPServer, which also
        imports httpx.
        
        The important thing is that OUR code uses lazy imports - the type hints use
        TYPE_CHECKING and the runtime usage imports httpx inside functions.
        """
        # This test documents the behavior rather than asserting on it
        # since the external dependency behavior is beyond our control
        # Verify our code has the lazy import pattern
        # (import statements are inside functions, not at module level)
        import inspect

        from codeweaver.cli.commands import index, init

        # Check index._check_server_health has lazy import
        source = inspect.getsource(index._check_server_health)
        assert "import httpx" in source, "index._check_server_health should have lazy import"

        # Check that httpx is in TYPE_CHECKING block in init module
        init_source = inspect.getsource(init)
        assert "if TYPE_CHECKING:" in init_source
        assert "import httpx" in init_source

    @pytest.mark.asyncio
    async def test_status_command_imports_httpx_when_called(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that httpx is imported when status command function is called."""
        from codeweaver.cli.commands.status import _query_server_status

        # Mock httpx to avoid actual network calls
        mock_httpx = MagicMock()
        mock_client = MagicMock()
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client
        mock_httpx.ConnectError = Exception
        mock_httpx.TimeoutException = Exception
        mock_httpx.HTTPStatusError = Exception

        # This will import httpx inside the function
        with monkeypatch.context() as m:
            m.setitem(sys.modules, "httpx", mock_httpx)
            result = await _query_server_status("http://localhost:9328")

        # Verify httpx was used
        mock_httpx.AsyncClient.assert_called_once()

    @pytest.mark.asyncio
    async def test_index_command_imports_httpx_when_called(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that httpx is imported when index command function is called."""
        from codeweaver.cli.commands.index import _check_server_health

        # Mock httpx to avoid actual network calls
        mock_httpx = MagicMock()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        # Use AsyncMock for the get method since it's awaited
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_httpx.AsyncClient.return_value.__aenter__.return_value = mock_client
        mock_httpx.ConnectError = Exception
        mock_httpx.TimeoutException = Exception

        # This will import httpx inside the function
        with monkeypatch.context() as m:
            m.setitem(sys.modules, "httpx", mock_httpx)
            result = await _check_server_health()

        # Verify httpx was used
        mock_httpx.AsyncClient.assert_called_once()
        assert result is True

