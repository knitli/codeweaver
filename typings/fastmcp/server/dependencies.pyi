# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from typing import TYPE_CHECKING, ParamSpec, TypeVar

from fastmcp.server.context import Context
from starlette.requests import Request

if TYPE_CHECKING: ...
P = ParamSpec("P")
R = TypeVar("R")
__all__ = ["AccessToken", "get_access_token", "get_context", "get_http_headers", "get_http_request"]

def get_context() -> Context: ...
def get_http_request() -> Request: ...
def get_http_headers(include_all: bool = ...) -> dict[str, str]:
    ...
