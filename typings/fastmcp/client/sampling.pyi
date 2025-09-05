# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from collections.abc import Awaitable, Callable

from mcp import ClientSession, CreateMessageResult
from mcp.client.session import SamplingFnT
from mcp.shared.context import LifespanContextT, RequestContext
from mcp.types import CreateMessageRequestParams as SamplingParams
from mcp.types import SamplingMessage

__all__ = ["SamplingHandler", "SamplingMessage", "SamplingParams"]
type SamplingHandler = Callable[
    [list[SamplingMessage], SamplingParams, RequestContext[ClientSession, LifespanContextT]],
    str | CreateMessageResult | Awaitable[str | CreateMessageResult],
]

def create_sampling_callback(sampling_handler: SamplingHandler) -> SamplingFnT: ...
