# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Configuration types for CodeWeaver."""

from __future__ import annotations

from typing import NotRequired, TypedDict

from pydantic import DirectoryPath, FilePath, PositiveInt

from codeweaver.core.config._logging import LoggingSettingsDict
from codeweaver.core.config.telemetry import TelemetrySettingsDict
from codeweaver.core.types.sentinel import Unset
from codeweaver.core.utils.environment import detect_root_package


ROOT_PACKAGE = detect_root_package()


class BaseCodeWeaverSettingsDict(TypedDict, total=False):
    """Base TypedDict for CodeWeaver settings.

    Not intended to be used directly; used for internal type checking and validation.
    """

    project_path: NotRequired[DirectoryPath | Unset]
    project_name: NotRequired[str | Unset]
    config_file: NotRequired[FilePath | Unset]
    logging: NotRequired[LoggingSettingsDict | Unset]
    telemetry: NotRequired[TelemetrySettingsDict | Unset]


match ROOT_PACKAGE:
    case "core":

        class CodeWeaverSettingsDict(BaseCodeWeaverSettingsDict):
            """TypedDict for CodeWeaver settings.

            Not intended to be used directly; used for internal type checking and validation.
            """

            # just the base settings for the core package

    case "provider":
        from codeweaver.providers.config import ProviderProfile, ProviderSettingsDict

        class CodeWeaverSettingsDict(BaseCodeWeaverSettingsDict):
            """TypedDict for CodeWeaver settings.

            Not intended to be used directly; used for internal type checking and validation.
            """

            provider: NotRequired[ProviderSettingsDict | Unset]
            profile: NotRequired[ProviderProfile | Unset]

    case "engine":
        from codeweaver.engine.config import (
            ChunkerSettingsDict,
            FailoverSettingsDict,
            IndexerSettingsDict,
        )
        from codeweaver.providers.config import ProviderProfile, ProviderSettingsDict

        class CodeWeaverSettingsDict(BaseCodeWeaverSettingsDict):
            """TypedDict for CodeWeaver settings.

            Not intended to be used directly; used for internal type checking and validation.
            """

            profile: NotRequired[ProviderProfile | Unset]
            provider: NotRequired[ProviderSettingsDict | Unset]

            indexer: NotRequired[IndexerSettingsDict | Unset]
            chunker: NotRequired[ChunkerSettingsDict | Unset]
            failover: NotRequired[FailoverSettingsDict | Unset]

    case "server":
        from codeweaver.server.config import (
            EndpointSettingsDict,
            FastMcpServerSettingsDict,
            MiddlewareOptions,
            UvicornServerSettingsDict,
        )

        class CodeWeaverSettingsDict(BaseCodeWeaverSettingsDict):
            """TypedDict for CodeWeaver settings.

            Not intended to be used directly; used for internal type checking and validation.
            """

            token_limit: NotRequired[PositiveInt | Unset]
            max_results: NotRequired[PositiveInt | Unset]

            profile: NotRequired[ProviderProfile | Unset]
            provider: NotRequired[ProviderSettingsDict | Unset]

            indexer: NotRequired[IndexerSettingsDict | Unset]
            chunker: NotRequired[ChunkerSettingsDict | Unset]
            failover: NotRequired[FailoverSettingsDict | Unset]

            # Mcp HTTP Server Settings
            mcp_server: NotRequired[FastMcpServerSettingsDict | Unset]
            stdio_server: NotRequired[FastMcpServerSettingsDict | Unset]
            middleware: NotRequired[MiddlewareOptions | Unset]
            uvicorn: NotRequired[UvicornServerSettingsDict | Unset]
            # Management Server (Always HTTP, independent of MCP transport)
            management_host: NotRequired[str | Unset]
            management_port: NotRequired[PositiveInt | Unset]
            endpoints: NotRequired[EndpointSettingsDict | Unset]
            default_mcp_config: NotRequired[dict[str, dict] | Unset]


__all__ = ("CodeWeaverSettingsDict",)
