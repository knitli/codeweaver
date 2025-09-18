# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

import httpx

__all__ = ["BearerAuth"]
logger = ...

class BearerAuth(httpx.Auth):
    def __init__(self, token: str) -> None: ...
    def auth_flow(self, request):  # -> Generator[Request, Any, None]:
        ...
