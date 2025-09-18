# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from collections.abc import Awaitable, Callable

import mcp.types

from mcp import ClientSession
from mcp.client.session import ListRootsFnT
from mcp.shared.context import LifespanContextT, RequestContext

type RootsList = list[str] | list[mcp.types.Root] | list[str | mcp.types.Root]
type RootsHandler = (
    Callable[[RequestContext[ClientSession, LifespanContextT]], RootsList]
    | Callable[[RequestContext[ClientSession, LifespanContextT]], Awaitable[RootsList]]
)

def convert_roots_list(roots: RootsList) -> list[mcp.types.Root]: ...
def create_roots_callback(handler: RootsList | RootsHandler) -> ListRootsFnT: ...
