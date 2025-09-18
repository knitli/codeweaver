# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from typing import Any

from mcp.server.lowlevel.server import LifespanResultT, NotificationOptions, RequestT
from mcp.server.lowlevel.server import Server as _Server
from mcp.server.models import InitializationOptions

class LowLevelServer(_Server[LifespanResultT, RequestT]):
    def __init__(self, *args, **kwargs) -> None: ...
    def create_initialization_options(
        self,
        notification_options: NotificationOptions | None = ...,
        experimental_capabilities: dict[str, dict[str, Any]] | None = ...,
        **kwargs: Any,
    ) -> InitializationOptions: ...
