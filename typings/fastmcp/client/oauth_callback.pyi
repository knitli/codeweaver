# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

import asyncio

from dataclasses import dataclass

from uvicorn import Server

"""
OAuth callback server for handling authorization code flows.

This module provides a reusable callback server that can handle OAuth redirects
and display styled responses to users.
"""
logger = ...

def create_callback_html(
    message: str, is_success: bool = ..., title: str = ..., server_url: str | None = ...
) -> str:
    ...

@dataclass
class CallbackResponse:
    code: str | None = ...
    state: str | None = ...
    error: str | None = ...
    error_description: str | None = ...
    @classmethod
    def from_dict(cls, data: dict[str, str]) -> CallbackResponse: ...
    def to_dict(self) -> dict[str, str]: ...

def create_oauth_callback_server(
    port: int,
    callback_path: str = ...,
    server_url: str | None = ...,
    response_future: asyncio.Future | None = ...,
) -> Server:
    ...

if __name__ == "__main__":
    port = ...
    server = ...
