# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from collections.abc import Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

from fastmcp.server.auth.auth import OAuthProvider
from fastmcp.server.server import FastMCP
from mcp.server.lowlevel.server import LifespanResultT
from mcp.server.streamable_http import EventStore
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.routing import BaseRoute
from starlette.types import Lifespan

if TYPE_CHECKING: ...
logger = ...
_current_http_request: ContextVar[Request | None] = ...

class StarletteWithLifespan(Starlette):
    @property
    def lifespan(self) -> Lifespan: ...

@contextmanager
def set_http_request(request: Request) -> Generator[Request, None, None]: ...

class RequestContextMiddleware:

    def __init__(self, app) -> None: ...
    async def __call__(self, scope, receive, send):  # -> None:
        ...

def setup_auth_middleware_and_routes(
    auth: OAuthProvider,
) -> tuple[list[Middleware], list[BaseRoute], list[str]]:
    ...

def create_base_app(
    routes: list[BaseRoute],
    middleware: list[Middleware],
    debug: bool = ...,
    lifespan: Callable | None = ...,
) -> StarletteWithLifespan:
    ...

def create_sse_app(
    server: FastMCP[LifespanResultT],
    message_path: str,
    sse_path: str,
    auth: OAuthProvider | None = ...,
    debug: bool = ...,
    routes: list[BaseRoute] | None = ...,
    middleware: list[Middleware] | None = ...,
) -> StarletteWithLifespan:
    ...

def create_streamable_http_app(
    server: FastMCP[LifespanResultT],
    streamable_http_path: str,
    event_store: EventStore | None = ...,
    auth: OAuthProvider | None = ...,
    json_response: bool = ...,
    stateless_http: bool = ...,
    debug: bool = ...,
    routes: list[BaseRoute] | None = ...,
    middleware: list[Middleware] | None = ...,
) -> StarletteWithLifespan:
    ...
